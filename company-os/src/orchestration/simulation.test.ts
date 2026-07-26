import assert from "node:assert/strict";
import test from "node:test";

import { simulateGoal } from "./simulation.js";

test("simulation stops at human approval with no spend or side effects", () => {
  const result = simulateGoal({
    title: "Safe demo",
    objective: "Demonstrate the lifecycle.",
    now: "2026-07-26T12:00:00.000Z",
  });

  assert.equal(result.task.status, "awaiting_human_approval");
  assert.notEqual(result.task.assignedAgentId, result.task.reviewerAgentId);
  assert.equal(result.approvalRequest.status, "pending");
  assert.equal(result.approvalRequest.action, "production_merge");
  assert.equal(result.executedSideEffects.length, 0);
  assert.equal(result.totalModelCostUsdMicros, 0);
  assert.equal(result.auditEvents.length, 4);
});
