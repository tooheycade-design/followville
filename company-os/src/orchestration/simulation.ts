import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  ApprovalRequestSchema,
  AuditEventSchema,
  GoalSchema,
  RunSchema,
  TaskSchema,
  type ApprovalRequest,
  type AuditEvent,
  type Goal,
  type Run,
  type Task,
  type TaskStatus,
} from "../domain/schemas.js";
import { digest } from "../domain/fingerprints.js";
import { assertTaskTransition } from "../domain/transitions.js";
import {
  ORGANIZATION_ID,
  OWNER_USER_ID,
  PROJECT_ID,
  SEED_AGENTS,
} from "../config/seed-agents.js";
import { authorize } from "../policy/policy-engine.js";

const IDS = {
  goal: "50000000-0000-4000-8000-000000000001",
  task: "50000000-0000-4000-8000-000000000002",
  criterion: "50000000-0000-4000-8000-000000000003",
  run: "50000000-0000-4000-8000-000000000004",
  approval: "50000000-0000-4000-8000-000000000005",
  correlation: "50000000-0000-4000-8000-000000000006",
} as const;

export interface SimulationResult {
  mode: "simulation";
  goal: Goal;
  task: Task;
  run: Run;
  approvalRequest: ApprovalRequest;
  auditEvents: readonly AuditEvent[];
  executedSideEffects: readonly [];
  totalModelCostUsdMicros: 0;
}

export interface SimulationInput {
  title: string;
  objective: string;
  now?: string;
  /**
   * Optional UUID factory. When omitted the simulator uses fixed identifiers
   * so existing deterministic tests and CLI output stay stable. Callers that
   * persist more than one simulated goal (for example the owner dashboard)
   * must provide a real factory such as `crypto.randomUUID` to avoid
   * identifier collisions between goals.
   */
  idFactory?: () => string;
  /**
   * Real filesystem root of the repository, used by the policy engine's
   * canonical-path containment check. Defaults to the checkout containing
   * this source file, which is correct for the CLI and tests; bundled
   * callers (for example the Next.js dashboard) must pass it explicitly.
   */
  repositoryRoot?: string;
  /**
   * The human who created the goal. Defaults to the fixed development owner.
   * A persistent backend requires a real account identifier, because the
   * database enforces that every goal has a genuine creator.
   */
  createdByUserId?: string;
}

function defaultRepositoryRoot(): string {
  return path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "..",
    "..",
    "..",
  );
}

function transition(task: Task, status: TaskStatus, now: string): Task {
  assertTaskTransition(task.status, status);
  return TaskSchema.parse({
    ...task,
    status,
    version: task.version + 1,
    updatedAt: now,
  });
}

function audit(
  sequence: number,
  input: {
    id: string;
    correlationId: string;
    taskId?: string;
    runId?: string;
    actorType: "human" | "agent" | "system";
    actorId: string;
    action: string;
    targetType: string;
    targetId: string;
    outcome: "allowed" | "denied" | "approval_required" | "succeeded" | "failed";
    reason: string;
    request: unknown;
    result?: unknown;
    now: string;
  },
): AuditEvent {
  return AuditEventSchema.parse({
    id: input.id,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: input.taskId ?? null,
    runId: input.runId ?? null,
    actorType: input.actorType,
    actorId: input.actorId,
    action: input.action,
    targetType: input.targetType,
    targetId: input.targetId,
    outcome: input.outcome,
    reason: input.reason,
    correlationId: input.correlationId,
    idempotencyKey: digest({
      sequence,
      action: input.action,
      targetId: input.targetId,
    }),
    requestDigest: digest(input.request),
    resultDigest: input.result === undefined ? null : digest(input.result),
    evidenceArtifactIds: [],
    createdAt: input.now,
  });
}

export function simulateGoal(input: SimulationInput): SimulationResult {
  const now = input.now ?? new Date().toISOString();
  const makeId = input.idFactory;
  const ids = makeId
    ? {
        goal: makeId(),
        task: makeId(),
        criterion: makeId(),
        run: makeId(),
        approval: makeId(),
        correlation: makeId(),
      }
    : IDS;
  const auditId = (sequence: number): string =>
    makeId
      ? makeId()
      : `60000000-0000-4000-8000-${sequence.toString().padStart(12, "0")}`;
  const goal = GoalSchema.parse({
    id: ids.goal,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    createdByUserId: input.createdByUserId ?? OWNER_USER_ID,
    title: input.title,
    objective: input.objective,
    successDefinition:
      "A scoped implementation is independently reviewed and presented for human approval.",
    constraints: [
      "Simulation only",
      "No provider calls",
      "No repository writes",
      "No production effects",
    ],
    riskLevel: "medium",
    budgetUsdMicros: 0,
    status: "awaiting_approval",
    createdAt: now,
  });

  let task = TaskSchema.parse({
    id: ids.task,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: goal.id,
    parentTaskId: null,
    title: `Implement: ${input.title}`,
    objective: input.objective,
    reason: "Translate the owner goal into a bounded, reviewable change.",
    status: "proposed",
    priority: 50,
    riskLevel: "medium",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: ids.criterion,
        description: "The requested behavior is implemented and verified.",
        verificationMethod: "Independent reviewer checks scoped evidence and tests.",
        required: true,
      },
    ],
    allowedCapabilities: [
      "repository_read",
      "repository_write",
      "git_branch_create",
      "test_execute",
      "git_commit",
      "production_merge",
    ],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: "codex/simulated-task",
    expectedOutputs: ["Reviewed branch", "Test evidence", "Human approval packet"],
    testRequirements: ["Focused automated tests", "Independent review"],
    approvalRequired: true,
    version: 1,
    createdAt: now,
    updatedAt: now,
  });

  for (const status of [
    "planned",
    "approved_for_work",
    "queued",
    "assigned",
    "in_progress",
  ] as const) {
    task = transition(task, status, now);
  }

  const writeDecision = authorize({
    agent: SEED_AGENTS.engineer,
    task,
    capability: "repository_write",
    repository: "followville_repo",
    relativePath: "company-os/README.md",
    repositoryRoot: input.repositoryRoot ?? defaultRepositoryRoot(),
    environment: "local",
    estimatedCostUsdMicros: 0,
    agentDailySpendUsdMicros: 0,
  });
  if (writeDecision.outcome !== "allowed") {
    throw new Error(`Unexpected simulation policy result: ${writeDecision.reason}`);
  }

  for (const status of ["awaiting_review", "awaiting_human_approval"] as const) {
    task = transition(task, status, now);
  }

  const run = RunSchema.parse({
    id: ids.run,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: task.id,
    agentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    trigger: "human",
    mode: "simulation",
    status: "completed",
    modelProvider: null,
    modelId: null,
    promptVersion: SEED_AGENTS.engineer.promptVersion,
    contextManifestDigest: digest({
      files: ["company-os"],
      constitution: "proposed-v0.1.0",
    }),
    workspaceId: null,
    budgetReservationUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    startedAt: now,
    completedAt: now,
  });

  const commitSha = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const scopeDigest = digest({
    taskId: task.id,
    branchName: task.branchName,
    expectedOutputs: task.expectedOutputs,
    action: "production_merge",
    commitSha,
  });
  const approvalRequest = ApprovalRequestSchema.parse({
    id: ids.approval,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: task.id,
    runId: run.id,
    requestedByType: "agent",
    requestedById: SEED_AGENTS.manager.id,
    action: "production_merge",
    summary: `Approve or reject the reviewed result for "${input.title}".`,
    reason: "Production integration is reserved for a named human decision.",
    scopeDigest,
    commitSha,
    evidenceArtifactIds: [],
    testsCompleted: ["Simulation policy checks"],
    riskLevel: "medium",
    reversible: true,
    rollbackPlan: "Do not merge; if already merged, revert the exact approved commit.",
    estimatedCostUsdMicros: 0,
    recommendation: "request_changes",
    alternatives: ["Keep the branch unmerged", "Revise the task scope"],
    requiredApprovals: 1,
    requiredRole: "owner",
    status: "pending",
    idempotencyKey: digest({ scopeDigest, action: "production_merge" }),
    createdAt: now,
    expiresAt: new Date(Date.parse(now) + 86_400_000).toISOString(),
  });

  const auditEvents = [
    audit(1, {
      id: auditId(1),
      correlationId: ids.correlation,
      actorType: "human",
      actorId: OWNER_USER_ID,
      action: "goal.accepted_for_simulation",
      targetType: "goal",
      targetId: goal.id,
      outcome: "succeeded",
      reason: "The owner supplied a goal for a no-side-effect simulation.",
      request: input,
      result: goal,
      now,
    }),
    audit(2, {
      id: auditId(2),
      correlationId: ids.correlation,
      taskId: task.id,
      runId: run.id,
      actorType: "system",
      actorId: SEED_AGENTS.manager.id,
      action: "policy.repository_write",
      targetType: "task",
      targetId: task.id,
      outcome: writeDecision.outcome,
      reason: writeDecision.reason,
      request: { capability: "repository_write", path: "company-os/README.md" },
      result: writeDecision,
      now,
    }),
    audit(3, {
      id: auditId(3),
      correlationId: ids.correlation,
      taskId: task.id,
      runId: run.id,
      actorType: "agent",
      actorId: SEED_AGENTS.reviewer.id,
      action: "review.simulated",
      targetType: "task",
      targetId: task.id,
      outcome: "succeeded",
      reason: "A distinct reviewer checked the simulated evidence contract.",
      request: { assignedAgentId: task.assignedAgentId },
      result: { reviewerAgentId: task.reviewerAgentId },
      now,
    }),
    audit(4, {
      id: auditId(4),
      correlationId: ids.correlation,
      taskId: task.id,
      runId: run.id,
      actorType: "system",
      actorId: SEED_AGENTS.manager.id,
      action: "approval.requested",
      targetType: "approval_request",
      targetId: approvalRequest.id,
      outcome: "approval_required",
      reason: "The task stops before production integration.",
      request: approvalRequest,
      result: { status: approvalRequest.status },
      now,
    }),
  ] as const;

  return {
    mode: "simulation",
    goal,
    task,
    run,
    approvalRequest,
    auditEvents,
    executedSideEffects: [],
    totalModelCostUsdMicros: 0,
  };
}
