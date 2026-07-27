import assert from "node:assert/strict";
import { test } from "node:test";

import { parseCodexOutput } from "./codex.js";

const TRANSCRIPT = [
  "sandbox: read-only",
  "reasoning effort: medium",
  "session id: 019fa1dd-925c-7893-aea7-d30c8c9af4ee",
  "--------",
  "user",
  "Do the thing.",
  "codex",
  "I inspected the file and changed nothing.",
  "It already behaves correctly.",
  "tokens used",
  "13,048",
].join("\n");

test("the final assistant turn is extracted, not the whole transcript", () => {
  const result = parseCodexOutput(TRANSCRIPT, false);
  assert.equal(
    result.text,
    "I inspected the file and changed nothing.\nIt already behaves correctly.",
  );
  assert.equal(result.ok, true);
});

test("token usage is read and comma-separated numbers are handled", () => {
  assert.equal(parseCodexOutput(TRANSCRIPT, false).usage.inputTokens, 13048);
});

test("the session id is captured for evidence", () => {
  assert.equal(
    parseCodexOutput(TRANSCRIPT, false).sessionId,
    "019fa1dd-925c-7893-aea7-d30c8c9af4ee",
  );
});

test("a failed run is reported as not ok even with output", () => {
  const result = parseCodexOutput(TRANSCRIPT, true);
  assert.equal(result.ok, false);
  assert.match(result.failureReason ?? "", /exited with an error/);
});

test("empty output is not treated as success", () => {
  assert.equal(parseCodexOutput("", false).ok, false);
});

test("an unrecognized shape falls back to the tail rather than throwing", () => {
  const odd = "some unexpected output\nwith no markers at all";
  const result = parseCodexOutput(odd, false);
  assert.match(result.text, /unexpected output/);
  assert.equal(result.usage.inputTokens, 0);
});

test("only the last assistant turn is taken when several appear", () => {
  const multi = [
    "codex",
    "first thought",
    "user",
    "follow up",
    "codex",
    "final answer",
    "tokens used",
    "100",
  ].join("\n");
  assert.equal(parseCodexOutput(multi, false).text, "final answer");
});
