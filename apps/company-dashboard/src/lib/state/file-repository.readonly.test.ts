import assert from "node:assert/strict";
import { mkdtempSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { FileCompanyRepository, writeState } from "./file-repository";
import { emptyState } from "./types";

test("loading does not rewrite the state file", async () => {
  const statePath = path.join(
    mkdtempSync(path.join(tmpdir(), "fv-read-")),
    "state.json",
  );
  writeState(emptyState(), statePath);
  const before = statSync(statePath).mtimeMs;

  const repository = new FileCompanyRepository(statePath);
  await repository.load();
  await repository.load();

  assert.equal(statSync(statePath).mtimeMs, before);
});
