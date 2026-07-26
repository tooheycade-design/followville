import assert from "node:assert/strict";
import test from "node:test";

import { assertTaskTransition, canTransitionTask } from "./transitions.js";

test("task lifecycle permits review but not direct deployment", () => {
  assert.equal(canTransitionTask("in_progress", "awaiting_review"), true);
  assert.equal(canTransitionTask("in_progress", "deployed"), false);
  assert.throws(
    () => assertTaskTransition("proposed", "production" as never),
    /Invalid task transition/,
  );
});
