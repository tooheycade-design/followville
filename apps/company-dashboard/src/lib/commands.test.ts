import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { OWNER_USER_ID } from "@followville/company-os-core";

import { decideApproval, submitGoal } from "./commands";
import { FileCompanyRepository } from "./state";

const ZACH_ID = "30000000-0000-4000-8000-000000000002";

function newRepository(): FileCompanyRepository {
  return new FileCompanyRepository(
    path.join(mkdtempSync(path.join(tmpdir(), "fv-cmd-")), "state.json"),
  );
}

test("submitting two goals persists distinct entities up to pending approval", async () => {
  const repository = newRepository();
  const first = await submitGoal(
    { title: "First goal", objective: "Do the first thing.", createdByUserId: OWNER_USER_ID },
    repository,
  );
  const second = await submitGoal(
    { title: "Second goal", objective: "Do the second thing.", createdByUserId: OWNER_USER_ID },
    repository,
  );
  assert.equal(first.ok, true);
  assert.equal(second.ok, true);

  const state = await repository.load();
  assert.equal(state.goals.length, 2);
  assert.equal(state.tasks.length, 2);
  assert.equal(state.approvalRequests.length, 2);
  assert.notEqual(state.goals[0]?.id, state.goals[1]?.id);
  assert.ok(
    state.approvalRequests.every((request) => request.status === "pending"),
  );
  assert.ok(
    state.tasks.every((task) => task.status === "awaiting_human_approval"),
  );
  assert.equal(
    state.runs.reduce((sum, run) => sum + run.actualCostUsdMicros, 0),
    0,
  );
});

test("blank goals are rejected without touching the store", async () => {
  const repository = newRepository();
  const result = await submitGoal({ title: "  ", objective: "x", createdByUserId: OWNER_USER_ID }, repository);
  assert.equal(result.ok, false);
  assert.equal((await repository.load()).goals.length, 0);
});

test("an owner approval resolves the request and advances the task", async () => {
  const repository = newRepository();
  await submitGoal({ title: "Approve me", objective: "Test.", createdByUserId: OWNER_USER_ID }, repository);
  const request = (await repository.load()).approvalRequests[0];
  assert.ok(request);

  const result = await decideApproval(
    {
      approvalRequestId: request.id,
      decision: "approve",
      comment: "Checked the evidence.",
      deciderUserId: OWNER_USER_ID,
      viewedScopeDigest: request.scopeDigest,
    },
    repository,
  );
  assert.equal(result.ok, true);

  const state = await repository.load();
  assert.equal(state.approvalRequests[0]?.status, "approved");
  assert.equal(state.tasks[0]?.status, "approved");
  assert.equal(state.approvalDecisions.length, 1);
  assert.ok(
    state.auditEvents.some((event) => event.action === "approval.approve"),
  );
});

test("a stale scope digest is refused and recorded in the audit trail", async () => {
  const repository = newRepository();
  await submitGoal({ title: "Stale digest", objective: "Test.", createdByUserId: OWNER_USER_ID }, repository);
  const request = (await repository.load()).approvalRequests[0];
  assert.ok(request);

  const result = await decideApproval(
    {
      approvalRequestId: request.id,
      decision: "approve",
      comment: "Looks fine.",
      deciderUserId: ZACH_ID,
      viewedScopeDigest: "0".repeat(64),
    },
    repository,
  );
  assert.equal(result.ok, false);

  const state = await repository.load();
  assert.equal(state.approvalRequests[0]?.status, "pending");
  assert.equal(state.tasks[0]?.status, "awaiting_human_approval");
  assert.equal(state.approvalDecisions.length, 0);
  assert.ok(
    state.auditEvents.some(
      (event) =>
        event.action === "approval.approve" && event.outcome === "denied",
    ),
  );
});

test("a rejection moves the task to rejected", async () => {
  const repository = newRepository();
  await submitGoal({ title: "Reject me", objective: "Test.", createdByUserId: OWNER_USER_ID }, repository);
  const request = (await repository.load()).approvalRequests[0];
  assert.ok(request);

  const result = await decideApproval(
    {
      approvalRequestId: request.id,
      decision: "reject",
      comment: "Not this way.",
      deciderUserId: ZACH_ID,
      viewedScopeDigest: request.scopeDigest,
    },
    repository,
  );
  assert.equal(result.ok, true);

  const state = await repository.load();
  assert.equal(state.approvalRequests[0]?.status, "rejected");
  assert.equal(state.tasks[0]?.status, "rejected");
});

test("a decision on an already-resolved request is refused", async () => {
  const repository = newRepository();
  await submitGoal({ title: "Double decide", objective: "Test.", createdByUserId: OWNER_USER_ID }, repository);
  const request = (await repository.load()).approvalRequests[0];
  assert.ok(request);

  await decideApproval(
    {
      approvalRequestId: request.id,
      decision: "approve",
      comment: "First decision.",
      deciderUserId: OWNER_USER_ID,
      viewedScopeDigest: request.scopeDigest,
    },
    repository,
  );
  const second = await decideApproval(
    {
      approvalRequestId: request.id,
      decision: "reject",
      comment: "Second decision.",
      deciderUserId: ZACH_ID,
      viewedScopeDigest: request.scopeDigest,
    },
    repository,
  );
  assert.equal(second.ok, false);
  assert.equal(
    (await repository.load()).approvalRequests[0]?.status,
    "approved",
  );
});
