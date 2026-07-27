import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { OWNER_USER_ID } from "@followville/company-os-core";

import { decideApproval, decideHeldTask, submitGoal } from "./commands";
import { FileCompanyRepository } from "./state";
import { writeState } from "./state/file-repository";

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

test("approval is blocked when a task requires tests but none are recorded", async () => {
  const statePath = path.join(
    mkdtempSync(path.join(tmpdir(), "fv-cmd-")),
    "state.json",
  );
  const repository = new FileCompanyRepository(statePath);
  await submitGoal(
    {
      title: "Unchecked work",
      objective: "Do not approve this without tests.",
      createdByUserId: OWNER_USER_ID,
    },
    repository,
  );
  const state = await repository.load();
  const request = state.approvalRequests[0];
  assert.ok(request);
  state.approvalRequests[0] = { ...request, testsCompleted: [] };
  writeState(state, statePath);

  const result = await decideApproval(
    {
      approvalRequestId: request.id,
      decision: "approve",
      comment: "I did not notice the missing tests.",
      deciderUserId: OWNER_USER_ID,
      viewedScopeDigest: request.scopeDigest,
    },
    repository,
  );

  assert.equal(result.ok, false);
  assert.match(result.message, /Required checks have not run/);
  const after = await repository.load();
  assert.equal(after.approvalRequests[0]?.status, "pending");
  assert.equal(after.approvalDecisions.length, 0);
  assert.ok(
    after.auditEvents.some(
      (event) =>
        event.action === "approval.approve" && event.outcome === "denied",
    ),
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

test("requesting changes preserves feedback and automatically queues a revision", async () => {
  const repository = newRepository();
  await submitGoal(
    {
      title: "Revise me",
      objective: "Test the owner revision path.",
      createdByUserId: OWNER_USER_ID,
    },
    repository,
  );
  const before = await repository.load();
  const request = before.approvalRequests[0];
  const task = before.tasks[0];
  assert.ok(request);
  assert.ok(task);

  const result = await decideApproval(
    {
      approvalRequestId: request.id,
      decision: "request_changes",
      comment: "The mobile layout still overlaps.",
      deciderUserId: OWNER_USER_ID,
      viewedScopeDigest: request.scopeDigest,
    },
    repository,
  );

  assert.equal(result.ok, true, result.message);
  assert.match(result.message, /new revision cycle is queued/);
  const after = await repository.load();
  assert.equal(after.approvalRequests[0]?.status, "changes_requested");
  assert.equal(after.tasks[0]?.status, "queued");
  assert.equal(after.tasks[0]?.reviewCycleCount, task.reviewCycleCount + 1);
  assert.equal(after.tasks[0]?.version, task.version + 2);
  assert.equal(after.approvalDecisions[0]?.comment, "The mobile layout still overlaps.");
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

/**
 * Held work: a task the Chief Executive would not release on its own.
 *
 * These build one directly rather than going through the planner, because the
 * planner only holds work when the owner's wording trips an escalation, and
 * these are about what happens afterwards.
 */
async function heldTask(
  repository: FileCompanyRepository,
  capabilities: readonly string[] = ["repository_read", "repository_write"],
): Promise<string> {
  const { HeuristicPlanner, planInitiative } = await import(
    "@followville/company-os-core"
  );
  const { randomUUID } = await import("node:crypto");
  const initiative = await planInitiative({
    // "publish" trips an escalation, so every task is held.
    intent: {
      title: "Publish a note",
      detail: "Publish a short note about the town.",
      createdByUserId: OWNER_USER_ID,
    },
    planner: new HeuristicPlanner(),
    idFactory: randomUUID,
  });
  const tasks = initiative.tasks.map((task) => ({
    ...task,
    allowedCapabilities: capabilities as typeof task.allowedCapabilities,
  }));
  await repository.appendInitiative(initiative.goal, tasks);
  return tasks[0]!.id;
}

test("releasing held work queues it with exactly the capabilities granted", async () => {
  const repository = newRepository();
  const taskId = await heldTask(repository);
  const before = (await repository.load()).tasks.find((t) => t.id === taskId)!;
  assert.equal(before.status, "proposed", "the CEO must hold this");

  const result = await decideHeldTask(
    {
      taskId,
      decision: "release",
      comment: "Checked the scope; documentation only.",
      deciderUserId: OWNER_USER_ID,
      grantedCapabilities: ["repository_read"],
      expectedVersion: before.version,
    },
    repository,
  );
  assert.equal(result.ok, true, result.message);

  const after = (await repository.load()).tasks.find((t) => t.id === taskId)!;
  assert.equal(after.status, "queued");
  assert.deepEqual(
    after.allowedCapabilities,
    ["repository_read"],
    "an owner may hand back less than was asked for",
  );
});

test("a release cannot grant more than the task proposed", async () => {
  const repository = newRepository();
  const taskId = await heldTask(repository, ["repository_read"]);
  const task = (await repository.load()).tasks.find((t) => t.id === taskId)!;

  const result = await decideHeldTask(
    {
      taskId,
      decision: "release",
      comment: "Trying to widen this.",
      deciderUserId: OWNER_USER_ID,
      grantedCapabilities: ["repository_read", "production_deploy"],
      expectedVersion: task.version,
    },
    repository,
  );

  assert.equal(result.ok, true, result.message);
  const after = (await repository.load()).tasks.find((t) => t.id === taskId)!;
  assert.deepEqual(
    after.allowedCapabilities,
    ["repository_read"],
    "the unproposed capability must be dropped, not granted",
  );
  assert.ok(
    !after.allowedCapabilities.includes("production_deploy" as never),
    "an authorization must never widen a grant",
  );
});

test("a decision against a stale version is refused", async () => {
  const repository = newRepository();
  const taskId = await heldTask(repository);
  const task = (await repository.load()).tasks.find((t) => t.id === taskId)!;

  const result = await decideHeldTask(
    {
      taskId,
      decision: "release",
      comment: "Deciding on something I did not read.",
      deciderUserId: OWNER_USER_ID,
      grantedCapabilities: ["repository_read"],
      expectedVersion: task.version + 5,
    },
    repository,
  );

  assert.equal(result.ok, false);
  assert.match(result.message, /changed after it was reviewed/);
  assert.equal(
    (await repository.load()).tasks.find((t) => t.id === taskId)!.status,
    "proposed",
    "a refused decision must leave the task held",
  );
});

test("only a registered owner can release held work", async () => {
  const repository = newRepository();
  const taskId = await heldTask(repository);
  const task = (await repository.load()).tasks.find((t) => t.id === taskId)!;

  const result = await decideHeldTask(
    {
      taskId,
      decision: "release",
      comment: "I am not an owner.",
      deciderUserId: "40000000-0000-4000-8000-000000000002",
      grantedCapabilities: ["repository_read"],
      expectedVersion: task.version,
    },
    repository,
  );
  assert.equal(result.ok, false);
  assert.match(result.message, /registered owner/);
});

test("rejecting held work stops it and records why", async () => {
  const repository = newRepository();
  const taskId = await heldTask(repository);
  const task = (await repository.load()).tasks.find((t) => t.id === taskId)!;

  const result = await decideHeldTask(
    {
      taskId,
      decision: "reject",
      comment: "Not something we want built.",
      deciderUserId: OWNER_USER_ID,
      grantedCapabilities: [],
      expectedVersion: task.version,
    },
    repository,
  );
  assert.equal(result.ok, true, result.message);

  const state = await repository.load();
  assert.equal(state.tasks.find((t) => t.id === taskId)!.status, "rejected");
  assert.ok(
    state.auditEvents.some(
      (event) =>
        event.action === "held_task.reject" &&
        event.reason.includes("Not something we want built"),
    ),
    "the reason must survive in the audit trail",
  );
});
