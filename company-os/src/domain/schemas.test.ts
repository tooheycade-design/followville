import assert from "node:assert/strict";
import test from "node:test";

import { SEED_AGENTS } from "../config/seed-agents.js";
import { TaskSchema } from "./schemas.js";

test("seed agent profiles satisfy the strict schema", () => {
  assert.equal(Object.keys(SEED_AGENTS).length, 5);
});

test("a worker cannot review its own task", () => {
  const now = "2026-07-26T12:00:00.000Z";
  const result = TaskSchema.safeParse({
    id: "70000000-0000-4000-8000-000000000001",
    organizationId: SEED_AGENTS.engineer.organizationId,
    projectId: "70000000-0000-4000-8000-000000000002",
    goalId: "70000000-0000-4000-8000-000000000003",
    parentTaskId: null,
    title: "Invalid self-review",
    objective: "Prove the validation works.",
    reason: "Test",
    status: "assigned",
    priority: 50,
    riskLevel: "low",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.engineer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: "70000000-0000-4000-8000-000000000004",
        description: "Rejected",
        verificationMethod: "Schema",
        required: true,
      },
    ],
    allowedCapabilities: [],
    repositoryScopes: [],
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["Validation error"],
    testRequirements: [],
    approvalRequired: false,
    version: 1,
    createdAt: now,
    updatedAt: now,
  });
  assert.equal(result.success, false);
});
