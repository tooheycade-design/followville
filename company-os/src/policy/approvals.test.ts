import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  type ApprovalDecision,
} from "../domain/schemas.js";
import { OWNER_USER_ID } from "../config/seed-agents.js";
import { simulateGoal } from "../orchestration/simulation.js";
import { applyApprovalDecision } from "./approvals.js";

const NOW = "2026-07-26T12:00:00.000Z";
const SECOND_OWNER_ID = "30000000-0000-4000-8000-000000000002";
const OPERATOR_ID = "30000000-0000-4000-8000-000000000003";
const OWNERS = {
  ownerUserIds: [OWNER_USER_ID, SECOND_OWNER_ID],
  operatorUserIds: [OPERATOR_ID],
};

function pendingRequest() {
  return simulateGoal({
    title: "Approval kernel fixture",
    objective: "Provide a valid pending approval request.",
    now: NOW,
  }).approvalRequest;
}

function decision(overrides: Partial<ApprovalDecision> = {}): ApprovalDecision {
  const request = pendingRequest();
  return ApprovalDecisionSchema.parse({
    id: "70000000-0000-4000-8000-000000000001",
    approvalRequestId: request.id,
    decidedByUserId: OWNER_USER_ID,
    decision: "approve",
    comment: "Reviewed the evidence.",
    requestScopeDigest: request.scopeDigest,
    decidedAt: NOW,
    ...overrides,
  });
}

test("an owner approval resolves the request and targets the approved task status", () => {
  const result = applyApprovalDecision({
    request: pendingRequest(),
    decision: decision(),
    owners: OWNERS,
    now: NOW,
  });
  assert.equal(result.outcome, "applied");
  assert.equal(result.outcome === "applied" && result.request.status, "approved");
  assert.equal(result.outcome === "applied" && result.taskStatusTarget, "approved");
});

test("a non-owner decision is denied even with a matching digest", () => {
  const result = applyApprovalDecision({
    request: pendingRequest(),
    decision: decision({
      decidedByUserId: "40000000-0000-4000-8000-000000000001",
    }),
    owners: OWNERS,
    now: NOW,
  });
  assert.equal(result.outcome, "denied");
  assert.match(
    result.outcome === "denied" ? result.reason : "",
    /human owner/,
  );
});

test("a stale scope digest is denied so a changed request cannot reuse an old approval", () => {
  const result = applyApprovalDecision({
    request: pendingRequest(),
    decision: decision({ requestScopeDigest: "0".repeat(64) }),
    owners: OWNERS,
    now: NOW,
  });
  assert.equal(result.outcome, "denied");
});

test("a decision after expiry marks the request expired instead of applying it", () => {
  const lateNow = "2026-07-28T12:00:00.000Z";
  const result = applyApprovalDecision({
    request: pendingRequest(),
    decision: decision({ decidedAt: lateNow }),
    owners: OWNERS,
    now: lateNow,
  });
  assert.equal(result.outcome, "expired");
  assert.equal(result.outcome === "expired" && result.request.status, "expired");
});

test("a decision on an already-resolved request is denied", () => {
  const resolved = ApprovalRequestSchema.parse({
    ...pendingRequest(),
    status: "approved",
  });
  const result = applyApprovalDecision({
    request: resolved,
    decision: decision(),
    owners: OWNERS,
    now: NOW,
  });
  assert.equal(result.outcome, "denied");
});

test("a rejection applies immediately regardless of required approvals", () => {
  const twoApprovalRequest = ApprovalRequestSchema.parse({
    ...pendingRequest(),
    requiredApprovals: 2,
  });
  const result = applyApprovalDecision({
    request: twoApprovalRequest,
    decision: decision({ decision: "reject" }),
    owners: OWNERS,
    now: NOW,
  });
  assert.equal(result.outcome, "applied");
  assert.equal(result.outcome === "applied" && result.request.status, "rejected");
  assert.equal(result.outcome === "applied" && result.taskStatusTarget, "rejected");
});

test("two required approvals need two distinct owners, and one owner cannot count twice", () => {
  const twoApprovalRequest = ApprovalRequestSchema.parse({
    ...pendingRequest(),
    requiredApprovals: 2,
  });

  const firstResult = applyApprovalDecision({
    request: twoApprovalRequest,
    decision: decision(),
    owners: OWNERS,
    now: NOW,
  });
  assert.equal(firstResult.outcome, "applied");
  assert.equal(
    firstResult.outcome === "applied" && firstResult.request.status,
    "pending",
  );
  assert.equal(
    firstResult.outcome === "applied" && firstResult.taskStatusTarget,
    null,
  );

  const repeatBySameOwner = applyApprovalDecision({
    request: twoApprovalRequest,
    decision: decision({ id: "70000000-0000-4000-8000-000000000002" }),
    owners: OWNERS,
    priorDecisions: [decision()],
    now: NOW,
  });
  assert.equal(
    repeatBySameOwner.outcome === "applied" && repeatBySameOwner.request.status,
    "pending",
  );

  const secondOwner = applyApprovalDecision({
    request: twoApprovalRequest,
    decision: decision({
      id: "70000000-0000-4000-8000-000000000003",
      decidedByUserId: SECOND_OWNER_ID,
    }),
    owners: OWNERS,
    priorDecisions: [decision()],
    now: NOW,
  });
  assert.equal(secondOwner.outcome, "applied");
  assert.equal(
    secondOwner.outcome === "applied" && secondOwner.request.status,
    "approved",
  );
  assert.equal(
    secondOwner.outcome === "applied" && secondOwner.distinctApprovers,
    2,
  );
});

test("a lower-risk operator approval uses the request's required role", () => {
  const request = ApprovalRequestSchema.parse({
    ...pendingRequest(),
    action: "git_commit",
    requiredRole: "operator",
  });
  const result = applyApprovalDecision({
    request,
    decision: decision({ decidedByUserId: OPERATOR_ID }),
    owners: OWNERS,
    now: NOW,
  });
  assert.equal(result.outcome, "applied");
  assert.equal(result.outcome === "applied" && result.request.status, "approved");
});
