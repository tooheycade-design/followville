import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";

import { SEED_AGENTS } from "../config/seed-agents.js";
import { simulateGoal } from "../orchestration/simulation.js";
import { LoopDetector } from "./loop-detector.js";
import { authorize } from "./policy-engine.js";

const REPOSITORY_ROOT = path.resolve(process.cwd(), "..");

function simulationTask() {
  const task = simulateGoal({
    title: "Policy fixture",
    objective: "Construct a valid task.",
    now: "2026-07-26T12:00:00.000Z",
  }).task;
  return { ...task, status: "in_progress" as const };
}

test("explicitly prohibited capabilities are denied", () => {
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task: simulationTask(),
    capability: "production_merge",
    environment: "production",
  });
  assert.equal(decision.outcome, "denied");
});

test("production actions require approval even when granted", () => {
  const task = { ...simulationTask(), status: "approved" as const };
  const elevatedManager = {
    ...SEED_AGENTS.manager,
    capabilities: [...SEED_AGENTS.manager.capabilities, "production_merge" as const],
    prohibitedCapabilities: SEED_AGENTS.manager.prohibitedCapabilities.filter(
      (capability) => capability !== "production_merge",
    ),
  };
  const decision = authorize({
    agent: elevatedManager,
    task,
    capability: "production_merge",
    environment: "production",
  });
  assert.equal(decision.outcome, "approval_required");
});

test("deployment authorization requires the merged lifecycle state", () => {
  const agent = {
    ...SEED_AGENTS.manager,
    capabilities: [...SEED_AGENTS.manager.capabilities, "production_deploy" as const],
    prohibitedCapabilities: SEED_AGENTS.manager.prohibitedCapabilities.filter(
      (capability) => capability !== "production_deploy",
    ),
  };
  const task = {
    ...simulationTask(),
    status: "merged" as const,
    allowedCapabilities: [
      ...simulationTask().allowedCapabilities,
      "production_deploy" as const,
    ],
  };
  const decision = authorize({
    agent,
    task,
    capability: "production_deploy",
    environment: "production",
  });
  assert.equal(decision.outcome, "approval_required");
});

test("repository path traversal fails closed", () => {
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task: simulationTask(),
    capability: "repository_write",
    repository: "followville_repo",
    relativePath: "company-os/../../world_state.json",
    repositoryRoot: REPOSITORY_ROOT,
    environment: "local",
  });
  assert.equal(decision.outcome, "denied");
});

test("OS-canonical repository targets must remain inside the repository", () => {
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task: simulationTask(),
    capability: "repository_write",
    repository: "followville_repo",
    relativePath: "company-os/missing-parent/declared-safe.ts",
    repositoryRoot: REPOSITORY_ROOT,
    environment: "local",
  });
  assert.equal(decision.outcome, "denied");
});

test("spend beyond the task budget is denied", () => {
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task: simulationTask(),
    capability: "repository_write",
    repository: "followville_repo",
    relativePath: "company-os/example.ts",
    repositoryRoot: REPOSITORY_ROOT,
    environment: "local",
    estimatedCostUsdMicros: 1,
  });
  assert.equal(decision.outcome, "denied");
});

test("repository context cannot be omitted", () => {
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task: simulationTask(),
    capability: "repository_write",
    environment: "local",
  });
  assert.equal(decision.outcome, "denied");
});

test("only the assigned worker can write", () => {
  const task = {
    ...simulationTask(),
    status: "in_progress" as const,
    assignedAgentId: SEED_AGENTS.manager.id,
  };
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task,
    capability: "repository_write",
    repository: "followville_repo",
    relativePath: "company-os/example.ts",
    repositoryRoot: REPOSITORY_ROOT,
    environment: "local",
  });
  assert.equal(decision.outcome, "denied");
});

test("work cannot resume after the task reaches human approval", () => {
  const task = {
    ...simulationTask(),
    status: "awaiting_human_approval" as const,
  };
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task,
    capability: "repository_write",
    repository: "followville_repo",
    relativePath: "company-os/example.ts",
    repositoryRoot: REPOSITORY_ROOT,
    environment: "local",
  });
  assert.equal(decision.outcome, "denied");
});

test("worker mutation freezes while independent review is underway", () => {
  const task = { ...simulationTask(), status: "awaiting_review" as const };
  const decision = authorize({
    agent: SEED_AGENTS.engineer,
    task,
    capability: "repository_write",
    repository: "followville_repo",
    relativePath: "company-os/example.ts",
    repositoryRoot: REPOSITORY_ROOT,
    environment: "local",
  });
  assert.equal(decision.outcome, "denied");
});

test("loop detector blocks after the configured repeat count", () => {
  const detector = new LoopDetector(2);
  assert.deepEqual(detector.record("same"), { blocked: false, count: 1 });
  assert.deepEqual(detector.record("same"), { blocked: false, count: 2 });
  assert.deepEqual(detector.record("same"), { blocked: true, count: 3 });
});

test("model invocation fails closed without complete ledger context", () => {
  const agent = {
    ...SEED_AGENTS.engineer,
    capabilities: [...SEED_AGENTS.engineer.capabilities, "model_invoke" as const],
    maxTaskCostUsdMicros: 100,
    maxDailyCostUsdMicros: 100,
  };
  const task = {
    ...simulationTask(),
    allowedCapabilities: [
      ...simulationTask().allowedCapabilities,
      "model_invoke" as const,
    ],
    budgetUsdMicros: 100,
  };
  const decision = authorize({
    agent,
    task,
    capability: "model_invoke",
    environment: "local",
    estimatedCostUsdMicros: 1,
  });
  assert.equal(decision.outcome, "denied");
  assert.match(decision.reason, /complete budget/i);
});
