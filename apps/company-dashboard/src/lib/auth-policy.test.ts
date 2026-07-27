import assert from "node:assert/strict";
import { test } from "node:test";

import { safeReturnPath } from "./auth-policy";

test("accepts local dashboard paths", () => {
  assert.equal(safeReturnPath("/"), "/");
  assert.equal(safeReturnPath("/held"), "/held");
  assert.equal(
    safeReturnPath("/approvals?status=pending"),
    "/approvals?status=pending",
  );
});

test("rejects absolute and protocol-relative destinations", () => {
  assert.equal(safeReturnPath("https://example.com"), "/");
  assert.equal(safeReturnPath("//example.com"), "/");
  assert.equal(safeReturnPath("\\\\example.com"), "/");
  assert.equal(safeReturnPath("/%2fexample.com"), "/");
  assert.equal(safeReturnPath("/%5cexample.com"), "/");
});

test("rejects missing and non-path destinations", () => {
  assert.equal(safeReturnPath(null), "/");
  assert.equal(safeReturnPath("held"), "/");
  assert.equal(safeReturnPath("/%not-valid"), "/");
});
