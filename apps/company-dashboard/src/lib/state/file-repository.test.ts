import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { FileCompanyRepository, readState, writeState } from "./file-repository";
import { emptyState } from "./types";

function temporaryStatePath(): string {
  return path.join(mkdtempSync(path.join(tmpdir(), "fv-store-")), "state.json");
}

test("reading a missing store returns an empty validated state", () => {
  assert.deepEqual(readState(temporaryStatePath()), emptyState());
});

test("writing then reading round-trips and validates", () => {
  const statePath = temporaryStatePath();
  writeState(emptyState(), statePath);
  const parsed = JSON.parse(readFileSync(statePath, "utf8"));
  assert.deepEqual(Object.keys(parsed).sort(), [
    "approvalDecisions",
    "approvalRequests",
    "auditEvents",
    "evidenceArtifacts",
    "goals",
    "runs",
    "tasks",
    "workers",
  ]);
  assert.deepEqual(readState(statePath), emptyState());
});

test("corrupt store content fails loudly instead of returning bad data", () => {
  const statePath = temporaryStatePath();
  writeFileSync(statePath, '{"goals": [{"nonsense": true}]}', "utf8");
  assert.throws(() => readState(statePath));

  const invalid = emptyState();
  (invalid.goals as unknown[]).push({ nonsense: true });
  assert.throws(() => writeState(invalid, temporaryStatePath()));
});

test("mutations are serialized in submission order", async () => {
  const repository = new FileCompanyRepository(temporaryStatePath());
  const order: number[] = [];
  await Promise.all([
    repository.load().then(() => order.push(1)),
    repository.load().then(() => order.push(2)),
    repository.load().then(() => order.push(3)),
  ]);
  assert.deepEqual(order, [1, 2, 3]);
});

test("the file repository identifies its backend", () => {
  assert.equal(new FileCompanyRepository(temporaryStatePath()).backend, "file");
});
