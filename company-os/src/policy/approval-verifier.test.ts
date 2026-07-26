import assert from "node:assert/strict";
import test from "node:test";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
} from "../domain/schemas.js";
import { SEED_AGENTS } from "../config/seed-agents.js";
import { simulateGoal } from "../orchestration/simulation.js";
import {
  authorizeApprovedAction,
  verifyApproval,
} from "./approval-verifier.js";

const request = ApprovalRequestSchema.parse({
  id: "80000000-0000-4000-8000-000000000001",
  organizationId: "80000000-0000-4000-8000-000000000002",
  projectId: "80000000-0000-4000-8000-000000000003",
  taskId: "80000000-0000-4000-8000-000000000004",
  runId: null,
  requestedByType: "agent",
  requestedById: "80000000-0000-4000-8000-000000000005",
  action: "production_merge",
  summary: "Merge reviewed commit.",
  reason: "Release requested.",
  scopeDigest: "scope-digest-1234567890",
  commitSha: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  evidenceArtifactIds: [],
  testsCompleted: ["tests"],
  riskLevel: "high",
  reversible: true,
  rollbackPlan: "Revert the commit.",
  estimatedCostUsdMicros: 0,
  recommendation: "approve",
  alternatives: ["Do not merge"],
  requiredApprovals: 1,
  requiredRole: "owner",
  status: "approved",
  idempotencyKey: "idempotency-key-1234567890",
  createdAt: "2026-07-26T12:00:00.000Z",
  expiresAt: "2026-07-27T12:00:00.000Z",
});

const decision = ApprovalDecisionSchema.parse({
  id: "80000000-0000-4000-8000-000000000006",
  approvalRequestId: request.id,
  decidedByUserId: "80000000-0000-4000-8000-000000000007",
  decision: "approve",
  comment: "Approved exact commit.",
  requestScopeDigest: request.scopeDigest,
  decidedAt: "2026-07-26T13:00:00.000Z",
});

test("exact current authorized approval is accepted", () => {
  const result = verifyApproval({
    request,
    decisions: [decision],
    action: "production_merge",
    scopeDigest: request.scopeDigest,
    commitSha: request.commitSha,
    authorizedApproverUserIds: new Set([decision.decidedByUserId]),
    now: "2026-07-26T14:00:00.000Z",
  });
  assert.equal(result.outcome, "allowed");
});

test("commit drift and expired approvals are denied", () => {
  const drift = verifyApproval({
    request,
    decisions: [decision],
    action: "production_merge",
    scopeDigest: request.scopeDigest,
    commitSha: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    authorizedApproverUserIds: new Set([decision.decidedByUserId]),
    now: "2026-07-26T14:00:00.000Z",
  });
  const expired = verifyApproval({
    request,
    decisions: [decision],
    action: "production_merge",
    scopeDigest: request.scopeDigest,
    commitSha: request.commitSha,
    authorizedApproverUserIds: new Set([decision.decidedByUserId]),
    now: "2026-07-28T14:00:00.000Z",
  });
  assert.equal(drift.outcome, "denied");
  assert.equal(expired.outcome, "denied");
});

test("an approved production action must pass policy and exact approval together", () => {
  const simulation = simulateGoal({
      title: "Approval fixture",
      objective: "Build exact authorization evidence.",
      now: "2026-07-26T12:00:00.000Z",
    });
  const task = {
    ...simulation.task,
    status: "approved" as const,
  };
  const boundRequest = {
    ...request,
    organizationId: task.organizationId,
    projectId: task.projectId,
    taskId: task.id,
  };
  const elevatedManager = {
    ...SEED_AGENTS.manager,
    capabilities: [...SEED_AGENTS.manager.capabilities, "production_merge" as const],
    prohibitedCapabilities: SEED_AGENTS.manager.prohibitedCapabilities.filter(
      (capability) => capability !== "production_merge",
    ),
  };
  const result = authorizeApprovedAction(
    {
      agent: elevatedManager,
      task,
      capability: "production_merge",
      environment: "production",
    },
    {
      request: boundRequest,
      decisions: [decision],
      action: "production_merge",
      scopeDigest: request.scopeDigest,
      commitSha: request.commitSha,
      authorizedApproverUserIds: new Set([decision.decidedByUserId]),
      now: "2026-07-26T14:00:00.000Z",
    },
  );
  assert.equal(result.outcome, "allowed");
});

test("approval evidence cannot be replayed against another task", () => {
  const task = {
    ...simulateGoal({
      title: "Other task",
      objective: "Reject unrelated approval evidence.",
      now: "2026-07-26T12:00:00.000Z",
    }).task,
    status: "approved" as const,
  };
  const elevatedManager = {
    ...SEED_AGENTS.manager,
    capabilities: [...SEED_AGENTS.manager.capabilities, "production_merge" as const],
    prohibitedCapabilities: SEED_AGENTS.manager.prohibitedCapabilities.filter(
      (capability) => capability !== "production_merge",
    ),
  };
  const result = authorizeApprovedAction(
    {
      agent: elevatedManager,
      task,
      capability: "production_merge",
      environment: "production",
    },
    {
      request,
      decisions: [decision],
      action: "production_merge",
      scopeDigest: request.scopeDigest,
      commitSha: request.commitSha,
      authorizedApproverUserIds: new Set([decision.decidedByUserId]),
      now: "2026-07-26T14:00:00.000Z",
    },
  );
  assert.equal(result.outcome, "denied");
  assert.match(result.reason, /different organization, project, or task/i);
});
