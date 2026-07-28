import assert from "node:assert/strict";
import test from "node:test";

import type { CompanyState } from "./state/types";
import { emptyState } from "./state/types";
import { buildOperatingReport } from "./operating-report";

const NOW = new Date("2026-07-28T20:00:00.000Z");

test("an empty company produces an honest quiet report", () => {
  const report = buildOperatingReport(emptyState(), NOW);

  assert.equal(report.pendingApprovals, 0);
  assert.equal(report.subscriptionRuns, 0);
  assert.deepEqual(report.attention, []);
  assert.deepEqual(report.risks, [
    "No current operating risk needs owner attention.",
  ]);
});

test("the report separates daily work, weekly work, spend, and owner attention", () => {
  const state = emptyState() as CompanyState;
  state.tasks = [
    {
      id: "10000000-0000-4000-8000-000000000102",
      organizationId: "10000000-0000-4000-8000-000000000001",
      projectId: "20000000-0000-4000-8000-000000000001",
      goalId: "10000000-0000-4000-8000-000000000101",
      parentTaskId: null,
      title: "Owner-held change",
      objective: "Wait for an owner.",
      reason: "Production authority requested.",
      status: "proposed",
      priority: 50,
      riskLevel: "high",
      assignedAgentId: null,
      reviewerAgentId: null,
      dependencyIds: [],
      acceptanceCriteria: [],
      allowedCapabilities: ["repository_read"],
      repositoryScopes: [],
      budgetUsdMicros: 0,
      estimatedCostUsdMicros: 0,
      actualCostUsdMicros: 0,
      retryCount: 0,
      reviewCycleCount: 0,
      branchName: null,
      expectedOutputs: [],
      testRequirements: [],
      approvalRequired: true,
      version: 1,
      createdAt: "2026-07-28T12:00:00.000Z",
      updatedAt: "2026-07-28T12:00:00.000Z",
    },
  ];
  state.runs = [
    {
      id: "10000000-0000-4000-8000-000000000103",
      organizationId: "10000000-0000-4000-8000-000000000001",
      projectId: "20000000-0000-4000-8000-000000000001",
      taskId: state.tasks[0]!.id,
      agentId: "40000000-0000-4000-8000-000000000002",
      reviewerAgentId: null,
      trigger: "human",
      mode: "execute",
      status: "failed",
      modelProvider: "claude-code",
      modelId: null,
      promptVersion: "test",
      contextManifestDigest: "a".repeat(64),
      workspaceId: null,
      budgetReservationUsdMicros: 0,
      actualCostUsdMicros: 0,
      retryCount: 0,
      startedAt: "2026-07-28T12:00:00.000Z",
      completedAt: "2026-07-28T12:10:00.000Z",
    },
  ];
  state.auditEvents = [
    {
      id: "10000000-0000-4000-8000-000000000104",
      organizationId: "10000000-0000-4000-8000-000000000001",
      projectId: "20000000-0000-4000-8000-000000000001",
      taskId: state.tasks[0]!.id,
      runId: state.runs[0]!.id,
      actorType: "agent",
      actorId: "40000000-0000-4000-8000-000000000002",
      action: "worker.failed",
      targetType: "task",
      targetId: state.tasks[0]!.id,
      outcome: "failed",
      reason: "A trusted check failed.",
      correlationId: "10000000-0000-4000-8000-000000000105",
      idempotencyKey: "worker-failed-test-key",
      requestDigest: "b".repeat(64),
      resultDigest: null,
      evidenceArtifactIds: [],
      createdAt: "2026-07-28T12:10:00.000Z",
    },
  ];

  const report = buildOperatingReport(state, NOW);

  assert.equal(report.day.failures, 1);
  assert.equal(report.week.failures, 1);
  assert.equal(report.heldTasks, 1);
  assert.equal(report.subscriptionRuns, 1);
  assert.equal(report.meteredSpendUsdMicros, 0);
  assert.equal(report.attention[0]?.kind, "held");
});
