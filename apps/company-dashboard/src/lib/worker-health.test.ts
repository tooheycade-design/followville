import assert from "node:assert/strict";
import test from "node:test";

import { workerHealth } from "./worker-health";

const now = Date.parse("2026-07-28T20:00:00.000Z");

test("explicit worker lifecycle state wins over a fresh heartbeat", () => {
  assert.deepEqual(
    workerHealth(
      { status: "offline", lastSeenAt: "2026-07-28T20:00:00.000Z" },
      now,
    ),
    { label: "offline", className: "denied" },
  );
  assert.deepEqual(
    workerHealth(
      { status: "draining", lastSeenAt: "2026-07-28T20:00:00.000Z" },
      now,
    ),
    { label: "draining", className: "pending" },
  );
});

test("heartbeat age detects delayed and crashed online workers", () => {
  assert.equal(
    workerHealth(
      { status: "online", lastSeenAt: "2026-07-28T19:59:30.000Z" },
      now,
    ).label,
    "online",
  );
  assert.equal(
    workerHealth(
      { status: "online", lastSeenAt: "2026-07-28T19:58:00.000Z" },
      now,
    ).label,
    "delayed",
  );
  assert.equal(
    workerHealth(
      { status: "online", lastSeenAt: "2026-07-28T19:54:00.000Z" },
      now,
    ).label,
    "offline",
  );
});
