import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  GoalSchema,
  TaskSchema,
  type Goal,
  type Task,
} from "../domain/schemas.js";
import {
  ORGANIZATION_ID,
  OWNER_USER_ID,
  PROJECT_ID,
  SEED_AGENTS,
} from "../config/seed-agents.js";

export interface PlanGoalInput {
  title: string;
  objective: string;
  createdByUserId?: string;
  now?: string;
  idFactory: () => string;
  /** Capabilities the task may use. Defaults to read-only investigation. */
  allowedCapabilities?: Task["allowedCapabilities"];
  acceptanceCriteria?: readonly string[];
}

export interface PlannedGoal {
  goal: Goal;
  task: Task;
}

function defaultRepositoryScopes() {
  return SEED_AGENTS.engineer.repositoryScopes;
}

/**
 * Turns an owner goal into one bounded task queued for a worker.
 *
 * Unlike `simulateGoal`, which walks a task all the way to a pending approval
 * without doing anything, this leaves the task in `queued` so a real worker can
 * lease it. The task starts with read-only capabilities; widening that is a
 * deliberate act, not a default.
 */
export function planGoal(input: PlanGoalInput): PlannedGoal {
  const now = input.now ?? new Date().toISOString();
  const make = input.idFactory;

  const goal = GoalSchema.parse({
    id: make(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    createdByUserId: input.createdByUserId ?? OWNER_USER_ID,
    title: input.title,
    objective: input.objective,
    successDefinition:
      "A worker completes the task within its capabilities and an independent reviewer confirms the evidence.",
    constraints: [
      "No production capability",
      "No model spend beyond the configured budget",
      "Work stays inside the approved repository scope",
    ],
    riskLevel: "low",
    budgetUsdMicros: 0,
    status: "active",
    createdAt: now,
  });

  const criteria = input.acceptanceCriteria ?? [
    "The stated objective is addressed and the evidence supports it.",
  ];

  const task = TaskSchema.parse({
    id: make(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: goal.id,
    parentTaskId: null,
    title: input.title,
    objective: input.objective,
    reason: "An owner asked for this work.",
    status: "queued",
    priority: 50,
    riskLevel: "low",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: criteria.map((description) => ({
      id: make(),
      description,
      verificationMethod: "Independent reviewer inspects the recorded evidence.",
      required: true,
    })),
    allowedCapabilities: input.allowedCapabilities ?? ["repository_read"],
    repositoryScopes: defaultRepositoryScopes(),
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["A written result with evidence"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: now,
    updatedAt: now,
  });

  return { goal, task };
}

export function defaultRepositoryRoot(): string {
  return path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "..",
    "..",
  );
}
