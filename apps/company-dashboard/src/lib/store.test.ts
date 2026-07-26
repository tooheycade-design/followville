import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { emptyState, mutateState, readState, writeState } from "./store";

function temporaryStatePath(): string {
  return path.join(mkdtempSync(path.join(tmpdir(), "fv-store-")), "state.json");
}

test("reading a missing store returns an empty validated state", () => {
  const state = readState(temporaryStatePath());
  assert.deepEqual(state, emptyState());
});

test("writing then reading round-trips and validates", () => {
  const statePath = temporaryStatePath();
  writeState(emptyState(), statePath);
  const parsed = JSON.parse(readFileSync(statePath, "utf8"));
  assert.deepEqual(Object.keys(parsed).sort(), [
    "approvalDecisions",
    "approvalRequests",
    "auditEvents",
    "goals",
    "runs",
    "tasks",
  ]);
  assert.deepEqual(readState(statePath), emptyState());
});

test("corrupt store content fails loudly instead of returning bad data", () => {
  const statePath = temporaryStatePath();
  writeFileSync(statePath, '{"goals": [{"nonsense": true}]}', "utf8");
  assert.throws(() => {
    readState(statePath);
  });
  const invalid = emptyState();
  (invalid.goals as unknown[]).push({ nonsense: true });
  assert.throws(() => {
    writeState(invalid, temporaryStatePath());
  });
});

test("mutations are serialized in submission order", async () => {
  const statePath = temporaryStatePath();
  const order: number[] = [];
  await Promise.all([
    mutateState((state) => {
      order.push(1);
      return state;
    }, statePath),
    mutateState((state) => {
      order.push(2);
      return state;
    }, statePath),
    mutateState((state) => {
      order.push(3);
      return state;
    }, statePath),
  ]);
  assert.deepEqual(order, [1, 2, 3]);
});
