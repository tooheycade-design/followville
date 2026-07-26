import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

import { TaskSchema, type Task } from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import { createPathGuard, preflightCapabilities } from "./path-guard.js";

const NOW = "2026-07-26T18:00:00.000Z";
const REPO_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
  "..",
);

let counter = 0;
const nextId = (): string =>
  `91000000-0000-4000-8000-${(counter += 1).toString().padStart(12, "0")}`;

function makeTask(overrides: Partial<Task> = {}): Task {
  return TaskSchema.parse({
    id: nextId(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: nextId(),
    parentTaskId: null,
    title: "Scoped work",
    objective: "Stay inside the approved paths.",
    reason: "An owner asked.",
    status: "assigned",
    priority: 50,
    riskLevel: "low",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: nextId(),
        description: "Stays in scope.",
        verificationMethod: "Reviewer checks.",
        required: true,
      },
    ],
    allowedCapabilities: ["repository_read"],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["A result"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
    ...overrides,
  });
}

function guard(task: Task = makeTask()) {
  return createPathGuard(
    SEED_AGENTS.engineer,
    task,
    "followville_repo",
    REPO_ROOT,
  );
}

test("a path inside the approved scope is allowed", () => {
  assert.equal(guard().check("repository_read", "company-os/README.md").outcome, "allowed");
});

test("a path outside the approved scope is denied", () => {
  assert.equal(guard().check("repository_read", "town.html").outcome, "denied");
});

test("the canonical world files stay denied even for reads", () => {
  const g = guard();
  for (const forbidden of [
    "world_state.json",
    "town.glb",
    "neighborhood.blend",
    "town_chunks/base.glb",
  ]) {
    assert.equal(
      g.check("repository_read", forbidden).outcome,
      "denied",
      `${forbidden} must not be readable through this scope`,
    );
  }
});

test("traversal out of the repository fails closed", () => {
  const g = guard();
  for (const attempt of [
    "company-os/../../etc/passwd",
    "../secrets.env",
    "company-os/./../../..",
  ]) {
    assert.equal(g.check("repository_read", attempt).outcome, "denied", attempt);
  }
});

test("assert throws with the refusing reason", () => {
  assert.throws(
    () => guard().assert("repository_read", "town.html"),
    /Policy refused repository_read/,
  );
});

test("preflight refuses a task assigned to a different agent", () => {
  const task = makeTask({ assignedAgentId: SEED_AGENTS.manager.id });
  const decision = preflightCapabilities(SEED_AGENTS.engineer, task);
  assert.equal(decision.outcome, "denied");
  assert.match(decision.reason, /assigned worker/);
});

test("preflight refuses a capability the agent does not hold", () => {
  const task = makeTask({ allowedCapabilities: ["production_deploy"] });
  const decision = preflightCapabilities(SEED_AGENTS.engineer, task);
  assert.equal(decision.outcome, "denied");
});

test("preflight allows an ordinary scoped read task", () => {
  assert.equal(
    preflightCapabilities(SEED_AGENTS.engineer, makeTask()).outcome,
    "allowed",
  );
});
