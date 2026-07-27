import assert from "node:assert/strict";
import { test } from "node:test";

import { withRetry } from "./supabase-queue";

test("a transient network failure is retried and then succeeds", async () => {
  let attempts = 0;
  const result = await withRetry("test", async () => {
    attempts += 1;
    if (attempts < 3) {
      throw new Error("TypeError: fetch failed");
    }
    return "ok";
  });
  assert.equal(result, "ok");
  assert.equal(attempts, 3);
});

test("a rejected write is not retried, because it is a decision", async () => {
  let attempts = 0;
  await assert.rejects(
    () =>
      withRetry("test", async () => {
        attempts += 1;
        throw new Error("approval request is not pending");
      }),
    /not pending/,
  );
  assert.equal(attempts, 1, "a refusal must not be repeated");
});

test("persistent network failure eventually gives up with context", async () => {
  await assert.rejects(
    () =>
      withRetry(
        "audit append",
        async () => {
          throw new Error("fetch failed");
        },
        2,
      ),
    /audit append failed after 2 attempts/,
  );
});

test("a successful call is not retried", async () => {
  let attempts = 0;
  await withRetry("test", async () => {
    attempts += 1;
    return 1;
  });
  assert.equal(attempts, 1);
});
