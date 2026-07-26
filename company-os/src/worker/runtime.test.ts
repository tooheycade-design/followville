import assert from "node:assert/strict";
import { test } from "node:test";

import { TaskSchema, type AuditEvent, type Task } from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import { runLeasedTask, runWorker } from "./runtime.js";
import type { LeasedTask, TaskExecutor, WorkQueue, WorkResult } from "./types.js";

const NOW = "2026-07-26T18:00:00.000Z";
let counter = 0;
const nextId = (): string =>
  `90000000-0000-4000-8000-${(counter += 1).toString().padStart(12, "0")}`;

const OPTIONS = {
  workerId: "worker-a",
  leaseSeconds: 300,
  heartbeatIntervalMs: 10_000,
  maxTaskDurationMs: 5_000,
};

function makeTask(overrides: Partial<Task> = {}): Task {
  return TaskSchema.parse({
    id: nextId(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: nextId(),
    parentTaskId: null,
    title: "Investigate something",
    objective: "Look at the repository and report.",
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
        description: "Reports the repository state.",
        verificationMethod: "Reviewer checks evidence.",
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
    expectedOutputs: ["A written result"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
    ...overrides,
  });
}

class FakeQueue implements WorkQueue {
  transitions: { status: string; released: boolean }[] = [];
  audits: AuditEvent[] = [];
  heartbeatHolds = true;
  private pending: LeasedTask[] = [];

  constructor(tasks: Task[] = []) {
    this.pending = tasks.map((task) => ({
      task,
      leaseEpoch: 1,
      leaseExpiresAt: NOW,
    }));
  }

  async leaseNextTask(): Promise<LeasedTask | null> {
    return this.pending.shift() ?? null;
  }

  async heartbeat(): Promise<boolean> {
    return this.heartbeatHolds;
  }

  async transition(
    _taskId: string,
    _workerId: string,
    nextStatus: Task["status"],
    releaseLease: boolean,
  ): Promise<boolean> {
    if (!this.heartbeatHolds) {
      return false;
    }
    this.transitions.push({ status: nextStatus, released: releaseLease });
    return true;
  }

  async appendAuditEvent(event: AuditEvent): Promise<void> {
    this.audits.push(event);
  }
}

function executor(result: Partial<WorkResult>, name = "fake"): TaskExecutor {
  return {
    name,
    async execute(): Promise<WorkResult> {
      return {
        outcome: "completed",
        summary: "done",
        evidence: ["some evidence"],
        filesChanged: [],
        modelProvider: null,
        modelId: null,
        inputTokens: 0,
        outputTokens: 0,
        costUsdMicros: 0,
        ...result,
      };
    },
  };
}

test("a completed task moves to review and releases its lease", async () => {
  const queue = new FakeQueue();
  const outcome = await runLeasedTask(
    { task: makeTask(), leaseEpoch: 1, leaseExpiresAt: NOW },
    executor({}),
    queue,
    OPTIONS,
    nextId,
  );
  assert.equal(outcome.status, "completed");
  assert.deepEqual(queue.transitions, [
    { status: "in_progress", released: false },
    { status: "awaiting_review", released: true },
  ]);
});

test("success without evidence is refused rather than sent to review", async () => {
  const queue = new FakeQueue();
  const outcome = await runLeasedTask(
    { task: makeTask(), leaseEpoch: 1, leaseExpiresAt: NOW },
    executor({ evidence: [] }),
    queue,
    OPTIONS,
    nextId,
  );
  assert.equal(outcome.status, "failed");
  assert.ok(queue.transitions.some((t) => t.status === "failed"));
  assert.ok(queue.audits.some((event) => event.outcome === "denied"));
});

test("a capability the agent lacks blocks the task before any work runs", async () => {
  const queue = new FakeQueue();
  let executed = false;
  const outcome = await runLeasedTask(
    {
      task: makeTask({ allowedCapabilities: ["production_deploy"] }),
      leaseEpoch: 1,
      leaseExpiresAt: NOW,
    },
    {
      name: "never",
      async execute() {
        executed = true;
        throw new Error("must not run");
      },
    },
    queue,
    OPTIONS,
    nextId,
  );
  assert.equal(outcome.status, "blocked");
  assert.equal(executed, false);
  assert.ok(queue.audits.some((event) => event.outcome === "denied"));
});

test("losing the lease discards the result instead of writing it back", async () => {
  const queue = new FakeQueue();
  queue.heartbeatHolds = false;
  const outcome = await runLeasedTask(
    { task: makeTask(), leaseEpoch: 1, leaseExpiresAt: NOW },
    executor({}),
    queue,
    OPTIONS,
    nextId,
  );
  assert.equal(outcome.status, "lost_lease");
  assert.equal(queue.transitions.length, 0);
});

test("an executor that throws fails the task and records the reason", async () => {
  const queue = new FakeQueue();
  const outcome = await runLeasedTask(
    { task: makeTask(), leaseEpoch: 1, leaseExpiresAt: NOW },
    {
      name: "throws",
      async execute() {
        throw new Error("boom");
      },
    },
    queue,
    OPTIONS,
    nextId,
  );
  assert.equal(outcome.status, "failed");
  assert.match(outcome.summary, /boom/);
  assert.ok(queue.transitions.some((t) => t.status === "failed"));
});

test("the worker drains the queue and stops when it is empty", async () => {
  const queue = new FakeQueue([makeTask(), makeTask()]);
  const outcomes = await runWorker(executor({}), queue, OPTIONS, nextId);
  assert.equal(outcomes.length, 2);
  assert.ok(outcomes.every((outcome) => outcome.status === "completed"));
});

test("maxTasks bounds a single run", async () => {
  const queue = new FakeQueue([makeTask(), makeTask(), makeTask()]);
  const outcomes = await runWorker(
    executor({}),
    queue,
    { ...OPTIONS, maxTasks: 1 },
    nextId,
  );
  assert.equal(outcomes.length, 1);
});
