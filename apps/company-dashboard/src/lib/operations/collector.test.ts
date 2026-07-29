import assert from "node:assert/strict";
import { test } from "node:test";

import {
  PublicTownStateAdapter,
  PublicWebsiteHealthAdapter,
} from "./collector";

const NOW = new Date("2026-07-29T18:00:00.000Z");

test("public town state reads only bounded canonical counters", async () => {
  const adapter = new PublicTownStateAdapter("https://example.test/state.json");
  const reading = await adapter.read(async () =>
    new Response(
      JSON.stringify({
        day: 27,
        pop: 500,
        seed_counter: 561,
        buildings: [{ id: 1 }, { id: 2 }],
        ignored: { private: "not retained" },
      }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      },
    ),
  );

  assert.deepEqual(reading.metrics, {
    day: 27,
    population: 500,
    buildingCount: 2,
    seedCounter: 561,
  });
  assert.match(reading.sourceDigest, /^[0-9a-f]{64}$/);
  assert.equal("ignored" in reading.metrics, false);
});

test("public town state rejects malformed counters", async () => {
  const adapter = new PublicTownStateAdapter("https://example.test/state.json");
  await assert.rejects(
    adapter.read(async () =>
      new Response('{"day":"27","pop":500,"seed_counter":561,"buildings":[]}', {
        status: 200,
      }),
    ),
    /invalid_day/,
  );
});

test("website health records status without retaining page content", async () => {
  const adapter = new PublicWebsiteHealthAdapter("https://example.test/");
  const reading = await adapter.read(async () =>
    new Response("<html>sensitive page body</html>", {
      status: 200,
      headers: { "content-type": "text/html; charset=utf-8" },
    }),
  );

  assert.equal(reading.metrics.reachable, true);
  assert.equal(reading.metrics.statusCode, 200);
  assert.equal(reading.metrics.contentType, "text/html; charset=utf-8");
  assert.equal(JSON.stringify(reading.metrics).includes("sensitive"), false);
  assert.equal(reading.confidence, "confirmed");
  assert.equal(NOW.toISOString(), "2026-07-29T18:00:00.000Z");
});
