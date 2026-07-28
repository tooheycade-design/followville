import assert from "node:assert/strict";
import test from "node:test";

import { SEED_AGENTS } from "../config/seed-agents.js";
import { TaskSchema, WorkerNodeSchema } from "./schemas.js";

test("seed agent profiles satisfy the strict schema", () => {
  // ceo, manager, engineer, reviewer, costAuditor, reporter
  assert.equal(Object.keys(SEED_AGENTS).length, 6);
});

test("no seed agent holds a production capability", () => {
  const production = [
    "production_merge",
    "production_deploy",
    "production_database_write",
    "canonical_world_growth",
    "public_communication",
    "social_publish",
    "payment_charge",
    "price_change",
    "destructive_delete",
  ];
  for (const agent of Object.values(SEED_AGENTS)) {
    for (const capability of production) {
      assert.ok(
        !agent.capabilities.includes(capability as never),
        `${agent.slug} must not hold ${capability}`,
      );
    }
  }
});

test("the CEO cannot write to the repository", () => {
  assert.ok(!SEED_AGENTS.ceo.capabilities.includes("repository_write"));
  assert.ok(SEED_AGENTS.ceo.prohibitedCapabilities.includes("repository_write"));
});

test("worker health records are strict and capability-aware", () => {
  const worker = WorkerNodeSchema.parse({
    workerId: "Cades-Omen-1234",
    organizationId: SEED_AGENTS.engineer.organizationId,
    projectId: "70000000-0000-4000-8000-000000000002",
    agentId: SEED_AGENTS.engineer.id,
    displayName: "Cade's worker",
    machineName: "Cades-Omen",
    platform: "win32-x64",
    provider: "codex",
    modelId: null,
    softwareVersion: "test",
    capabilities: ["repository_read", "test_execute"],
    status: "online",
    currentTaskId: null,
    currentRunId: null,
    metadata: {},
    startedAt: "2026-07-28T20:00:00.000Z",
    lastSeenAt: "2026-07-28T20:00:00.000Z",
  });

  assert.deepEqual(worker.capabilities, ["repository_read", "test_execute"]);
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
