import assert from "node:assert/strict";
import { test } from "node:test";

import {
  DEFAULT_SCHEDULE,
  HOUR,
  MINUTE,
  dueJobs,
  isDue,
  recordRun,
  type ScheduleDefinition,
  type ScheduleState,
} from "./schedule.js";

const JOB: ScheduleDefinition = {
  name: "work-queue",
  intervalMs: 2 * MINUTE,
  catchUp: false,
  description: "test job",
};

const T0 = Date.parse("2026-07-26T20:00:00.000Z");

function state(overrides: Partial<ScheduleState> = {}): ScheduleState {
  return {
    name: JOB.name,
    lastRunAt: new Date(T0).toISOString(),
    lastOutcome: "succeeded",
    consecutiveFailures: 0,
    ...overrides,
  };
}

test("a job that has never run is due immediately", () => {
  assert.equal(isDue(JOB, undefined, T0).due, true);
  assert.equal(isDue(JOB, state({ lastRunAt: null }), T0).due, true);
});

test("a job is not due before its interval elapses", () => {
  assert.equal(isDue(JOB, state(), T0 + MINUTE).due, false);
});

test("a job is due once its interval elapses", () => {
  assert.equal(isDue(JOB, state(), T0 + 2 * MINUTE).due, true);
});

test("a machine that slept wakes overdue and runs once", () => {
  const decision = isDue(JOB, state(), T0 + 8 * HOUR);
  assert.equal(decision.due, true);
  assert.match(decision.reason, /Last ran/);
});

test("repeated failures back off exponentially instead of spinning", () => {
  const failing = state({ lastOutcome: "failed", consecutiveFailures: 3 });
  // 2 minutes * 2^3 = 16 minutes.
  assert.equal(isDue(JOB, failing, T0 + 10 * MINUTE).due, false);
  assert.equal(isDue(JOB, failing, T0 + 17 * MINUTE).due, true);
});

test("backoff is capped at an hour", () => {
  const failing = state({ lastOutcome: "failed", consecutiveFailures: 20 });
  assert.equal(isDue(JOB, failing, T0 + HOUR + MINUTE).due, true);
});

test("a success clears the failure count", () => {
  const after = recordRun(
    state({ consecutiveFailures: 4 }),
    JOB.name,
    "succeeded",
    new Date(T0).toISOString(),
  );
  assert.equal(after.consecutiveFailures, 0);
  assert.equal(after.lastOutcome, "succeeded");
});

test("a failure increments the failure count", () => {
  const after = recordRun(
    state({ consecutiveFailures: 1 }),
    JOB.name,
    "failed",
    new Date(T0).toISOString(),
  );
  assert.equal(after.consecutiveFailures, 2);
});

test("an unreadable last-run time does not wedge the job", () => {
  assert.equal(isDue(JOB, state({ lastRunAt: "not a date" }), T0).due, true);
});

test("due jobs are ordered most overdue first", () => {
  const states = new Map<string, ScheduleState>([
    [
      "work-queue",
      { name: "work-queue", lastRunAt: new Date(T0 - HOUR).toISOString(), lastOutcome: "succeeded", consecutiveFailures: 0 },
    ],
    [
      "reclaim-leases",
      { name: "reclaim-leases", lastRunAt: new Date(T0 - 6 * HOUR).toISOString(), lastOutcome: "succeeded", consecutiveFailures: 0 },
    ],
  ]);
  const due = dueJobs(DEFAULT_SCHEDULE, states, T0);
  assert.equal(due[0]?.name, "daily-report", "never-run jobs sort first");
  assert.ok(
    due.map((job) => job.name).includes("reclaim-leases"),
    "the longest-idle job is included",
  );
});

test("the default schedule keeps the frequent job cheap", () => {
  const queue = DEFAULT_SCHEDULE.find((job) => job.name === "work-queue");
  assert.ok(queue);
  assert.ok(queue.intervalMs <= 5 * MINUTE, "the queue is checked often");
  const daily = DEFAULT_SCHEDULE.filter((job) => job.intervalMs >= 24 * HOUR);
  assert.ok(daily.length >= 2, "reporting jobs are daily, not frequent");
});
