import assert from "node:assert/strict";
import { test } from "node:test";

import type {
  ModelProvider,
  ProviderAvailability,
  ProviderResponse,
} from "../providers/types.js";
import { HeuristicPlanner, planInitiative } from "./ceo.js";
import {
  ModelPlanner,
  coerceProposals,
  extractJsonArray,
} from "./model-planner.js";

let counter = 0;
const nextId = (): string =>
  `95000000-0000-4000-8000-${(counter += 1).toString().padStart(12, "0")}`;

function provider(
  text: string,
  ok = true,
  available: ProviderAvailability = { available: true, detail: "test" },
): ModelProvider {
  return {
    name: "fake",
    billingMode: "subscription",
    async checkAvailability() {
      return available;
    },
    async invoke(): Promise<ProviderResponse> {
      return {
        ok,
        text,
        usage: { inputTokens: 10, outputTokens: 5, cachedInputTokens: 0, costUsdMicros: 0 },
        model: "fake",
        sessionId: null,
        failureReason: ok ? null : "refused",
      };
    },
  };
}

function plannerWith(text: string, ok = true, available?: ProviderAvailability) {
  return new ModelPlanner({
    provider: provider(text, ok, available),
    workingDirectory: process.cwd(),
    timeoutMs: 1000,
    fallback: new HeuristicPlanner(),
  });
}

const VALID = JSON.stringify([
  {
    title: "Measure map load time",
    objective: "Record how long the town map takes to open on mobile.",
    reason: "Establish a baseline before changing anything.",
    acceptanceCriteria: ["A measured number is recorded."],
    requestedCapabilities: ["repository_read"],
    priority: 70,
    riskLevel: "low",
  },
]);

test("a well-formed plan is used", async () => {
  const proposals = await plannerWith(VALID).propose({
    title: "Speed up the map",
    detail: "It feels slow.",
  });
  assert.equal(proposals.length, 1);
  assert.equal(proposals[0]?.title, "Measure map load time");
});

test("JSON wrapped in prose or a code fence is still extracted", () => {
  const wrapped = "Sure! Here is the plan:\n```json\n" + VALID + "\n```\nHope that helps.";
  const parsed = extractJsonArray(wrapped);
  assert.ok(parsed);
  assert.equal(parsed.length, 1);
});

test("a bracket inside a string does not confuse extraction", () => {
  const tricky = '[{"title":"a] b","objective":"x","acceptanceCriteria":[]}]';
  const parsed = extractJsonArray(tricky);
  assert.ok(parsed);
  assert.equal((parsed[0] as Record<string, unknown>)["title"], "a] b");
});

test("unparseable output falls back to the heuristic planner", async () => {
  const proposals = await plannerWith("I cannot help with that.").propose({
    title: "Do a thing",
    detail: "Please.",
  });
  assert.ok(proposals.length > 0, "an owner must still get a plan");
  assert.match(proposals[0]?.title ?? "", /^Investigate:/);
});

test("an unavailable provider falls back rather than failing", async () => {
  const proposals = await plannerWith(VALID, true, {
    available: false,
    reason: "not_authenticated",
    detail: "signed out",
  }).propose({ title: "Do a thing", detail: "Please." });
  assert.ok(proposals.length > 0);
  assert.match(proposals[0]?.title ?? "", /^Investigate:/);
});

test("a refused provider falls back", async () => {
  const proposals = await plannerWith(VALID, false).propose({
    title: "Do a thing",
    detail: "Please.",
  });
  assert.match(proposals[0]?.title ?? "", /^Investigate:/);
});

test("malformed entries are discarded, not passed through", () => {
  const proposals = coerceProposals([
    { title: "", objective: "x" },
    { title: "ok", objective: "" },
    null,
    "nonsense",
    { title: "good", objective: "real work" },
  ]);
  assert.equal(proposals.length, 1);
  assert.equal(proposals[0]?.title, "good");
});

test("the plan is capped so one reply cannot flood the queue", () => {
  const many = Array.from({ length: 12 }, (_, index) => ({
    title: `t${index}`,
    objective: "work",
  }));
  assert.equal(coerceProposals(many).length, 4);
});

test("a model asking for production capability still does not get it", async () => {
  const greedy = JSON.stringify([
    {
      title: "Ship it",
      objective: "Deploy the change.",
      acceptanceCriteria: ["It is live."],
      requestedCapabilities: ["repository_write", "production_deploy", "payment_charge"],
      priority: 50,
      riskLevel: "low",
    },
  ]);
  const initiative = await planInitiative({
    intent: { title: "Ship", detail: "Make it live." },
    planner: plannerWith(greedy),
    idFactory: nextId,
    now: "2026-07-27T06:00:00.000Z",
  });
  const task = initiative.tasks[0];
  assert.ok(task);
  assert.ok(!task.allowedCapabilities.includes("production_deploy" as never));
  assert.ok(!task.allowedCapabilities.includes("payment_charge" as never));
  assert.equal(initiative.clampedCapabilities.length, 1);
});
