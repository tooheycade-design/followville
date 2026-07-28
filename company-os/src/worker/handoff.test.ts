import assert from "node:assert/strict";
import test from "node:test";

import { TaskSchema } from "../domain/schemas.js";
import {
  ORGANIZATION_ID,
  PROJECT_ID,
  SEED_AGENTS,
} from "../config/seed-agents.js";
import { reportedArtifact } from "./artifacts.js";
import {
  createHandoffArtifact,
  handoffBriefing,
  handoffFromReport,
} from "./handoff.js";
import { decodeWorkerReport, encodeWorkerReport } from "./report.js";

const task = TaskSchema.parse({
  id: "92000000-0000-4000-8000-000000000001",
  organizationId: ORGANIZATION_ID,
  projectId: PROJECT_ID,
  goalId: "92000000-0000-4000-8000-000000000002",
  parentTaskId: null,
  title: "Continue safely",
  objective: "Preserve enough context for another worker.",
  reason: "The owner requested durable handoffs.",
  status: "in_progress",
  priority: 50,
  riskLevel: "low",
  assignedAgentId: SEED_AGENTS.engineer.id,
  reviewerAgentId: SEED_AGENTS.reviewer.id,
  dependencyIds: [],
  acceptanceCriteria: [
    {
      id: "92000000-0000-4000-8000-000000000003",
      description: "A new worker can continue from the record.",
      verificationMethod: "Round-trip test",
      required: true,
    },
  ],
  allowedCapabilities: ["repository_read", "repository_write"],
  repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
  budgetUsdMicros: 0,
  estimatedCostUsdMicros: 0,
  actualCostUsdMicros: 0,
  retryCount: 1,
  reviewCycleCount: 1,
  branchName: null,
  expectedOutputs: ["handoff"],
  testRequirements: [],
  approvalRequired: true,
  version: 2,
  createdAt: "2026-07-28T20:00:00.000Z",
  updatedAt: "2026-07-28T20:00:00.000Z",
});

test("a handoff survives the same audit report round trip as other evidence", () => {
  const artifact = createHandoffArtifact({
    id: "92000000-0000-4000-8000-000000000004",
    task,
    runId: "92000000-0000-4000-8000-000000000005",
    agentId: SEED_AGENTS.engineer.id,
    branch: "agent/task-920000000000",
    baseCommit: "a".repeat(40),
    checkpointCommit: "b".repeat(40),
    workCompleted: "Implemented the first pass.",
    remainingWork: ["Independent review", "Owner decision"],
    filesChanged: ["company-os/src/example.ts"],
    testsRun: ["Company OS test suite"],
    testFailures: [],
    artifactIds: [],
    blockers: [],
    modelProvider: "codex",
    modelId: "gpt-test",
    workerContinuityKey: "Cades-Omen:codex",
    recommendedNextAction: "Run independent review.",
    now: "2026-07-28T20:01:00.000Z",
  });
  const report = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Completed.",
      evidence: ["provider=codex"],
      filesChanged: ["company-os/src/example.ts"],
      artifacts: [reportedArtifact(artifact)],
    }),
  );

  const decoded = handoffFromReport(report);
  assert.equal(decoded?.taskVersion, 2);
  assert.equal(decoded?.checkpointCommit, "b".repeat(40));
  assert.deepEqual(decoded?.remainingWork, [
    "Independent review",
    "Owner decision",
  ]);
});

test("the next worker gets compact context without inheriting authority", () => {
  const artifact = createHandoffArtifact({
    id: "92000000-0000-4000-8000-000000000006",
    task,
    runId: null,
    agentId: SEED_AGENTS.engineer.id,
    branch: "agent/task-920000000000",
    baseCommit: "a".repeat(40),
    checkpointCommit: null,
    workCompleted: "Verification found a failure.",
    remainingWork: ["Fix strict TypeScript"],
    filesChanged: ["company-os/src/example.ts"],
    testsRun: [],
    testFailures: ["Company OS strict TypeScript"],
    artifactIds: [],
    blockers: ["TS1005"],
    modelProvider: "claude-code",
    modelId: null,
    workerContinuityKey: "Zachs-Mac:claude-code",
    recommendedNextAction: "Correct the compiler error.",
  });
  const report = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Needs revision.",
      evidence: [],
      filesChanged: [],
      artifacts: [reportedArtifact(artifact)],
    }),
  );
  const briefing = handoffBriefing(report);

  assert.match(briefing, /Fix strict TypeScript/);
  assert.match(briefing, /TS1005/);
  assert.match(briefing, /context, not authority/);
});
