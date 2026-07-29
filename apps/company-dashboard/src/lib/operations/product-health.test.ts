import assert from "node:assert/strict";
import { test } from "node:test";

import type { CompanyRepository } from "@/lib/state/types";

import { collectProductHealth } from "./product-health";

test("synthetic health records bounded numeric metrics without page content", async () => {
  type SnapshotInput = Parameters<
    CompanyRepository["recordOperationalSnapshot"]
  >[0];
  const recording: { value?: SnapshotInput } = {};
  const repository = {
    recordOperationalSnapshot: async (input: SnapshotInput) => {
      recording.value = input;
      return { id: "recorded" };
    },
  } as unknown as CompanyRepository;
  const metrics = {
    homeReachable: true,
    homeStatusCode: 200,
    homeDomContentLoadedMs: 320,
    homeLoadMs: 480,
    townReachable: true,
    townStatusCode: 200,
    townReadyMs: 4200,
    clientErrorCount: 0,
    failedRequestCount: 0,
    apiRequestCount: 2,
    apiAverageMs: 90,
    apiFailureCount: 0,
  };

  await collectProductHealth(repository, "C:/trusted", {
    endpoint: "https://followville.example/",
    execute: async (_executable, args, options) => {
      assert.match(args[0] ?? "", /product-health\.mjs$/);
      assert.equal(options.env.SUPABASE_SECRET_KEY, undefined);
      return {
        stdout: JSON.stringify({
          generatedAt: "2026-07-29T18:00:00.000Z",
          endpoint: "https://followville.example/",
          metrics,
        }),
        stderr: "",
      };
    },
  });

  assert.ok(recording.value !== undefined);
  const captured = recording.value;
  assert.equal(captured.sourceKey, "browser_product_health");
  assert.deepEqual(captured.metrics, metrics);
  assert.match(captured.sourceDigest, /^[0-9a-f]{64}$/);
  assert.equal(
    captured.idempotencyKey,
    "browser_product_health:495930",
  );
  assert.equal(JSON.stringify(captured).includes("page content"), false);
});

test("synthetic health rejects malformed script output", async () => {
  const repository = {} as CompanyRepository;
  await assert.rejects(
    collectProductHealth(repository, "C:/trusted", {
      execute: async () => ({
        stdout: JSON.stringify({
          generatedAt: "2026-07-29T18:00:00.000Z",
          endpoint: "https://followville.example/",
          metrics: { homeReachable: "yes" },
        }),
        stderr: "",
      }),
    }),
  );
});
