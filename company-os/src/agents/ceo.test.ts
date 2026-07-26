import assert from "node:assert/strict";
import { test } from "node:test";

import type { Capability } from "../domain/schemas.js";
import {
  HeuristicPlanner,
  planInitiative,
  type Planner,
  type ProposedTask,
} from "./ceo.js";

let counter = 0;
const nextId = (): string =>
  `94000000-0000-4000-8000-${(counter += 1).toString().padStart(12, "0")}`;

const NOW = "2026-07-26T20:00:00.000Z";

function plannerReturning(tasks: ProposedTask[]): Planner {
  return { name: "fixed", async propose() { return tasks; } };
}

function proposal(overrides: Partial<ProposedTask> = {}): ProposedTask {
  return {
    title: "Do a thing",
    objective: "Change something small.",
    reason: "Because an owner asked.",
    acceptanceCriteria: ["It works."],
    requestedCapabilities: ["repository_read"],
    priority: 50,
    riskLevel: "low",
    ...overrides,
  };
}

test("ordinary intent becomes queued work", async () => {
  const initiative = await planInitiative({
    intent: { title: "Speed up the map", detail: "The town map feels slow to open." },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });
  assert.equal(initiative.tasks.length, 2);
  assert.ok(initiative.tasks.every((task) => task.status === "queued"));
  assert.deepEqual(initiative.escalations, []);
});

test("a planner cannot grant production capability", async () => {
  const initiative = await planInitiative({
    intent: { title: "Ship it", detail: "Make the change." },
    planner: plannerReturning([
      proposal({
        requestedCapabilities: [
          "repository_read",
          "production_deploy",
          "payment_charge",
        ] as Capability[],
      }),
    ]),
    idFactory: nextId,
    now: NOW,
  });

  const task = initiative.tasks[0];
  assert.ok(task);
  assert.deepEqual(task.allowedCapabilities, ["repository_read"]);
  assert.equal(initiative.clampedCapabilities.length, 1);
  assert.deepEqual(initiative.clampedCapabilities[0]?.removed, [
    "production_deploy",
    "payment_charge",
  ]);
});

test("an owner may grant a capability the CEO cannot grant itself", async () => {
  const initiative = await planInitiative({
    intent: { title: "Prepare a migration", detail: "Draft the schema change." },
    planner: plannerReturning([
      proposal({ requestedCapabilities: ["database_migration_prepare"] }),
    ]),
    idFactory: nextId,
    now: NOW,
    ownerGrantedCapabilities: ["database_migration_prepare"],
  });
  assert.deepEqual(initiative.tasks[0]?.allowedCapabilities, [
    "database_migration_prepare",
  ]);
  assert.equal(initiative.clampedCapabilities.length, 0);
});

test("monetization intent is escalated and held for an owner", async () => {
  const initiative = await planInitiative({
    intent: {
      title: "Add pricing",
      detail: "Charge for premium house colors.",
    },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });
  assert.ok(initiative.escalations.some((e) => /Monetization/i.test(e)));
  assert.ok(initiative.tasks.every((task) => task.status === "proposed"));
  assert.equal(initiative.goal.status, "awaiting_approval");
  assert.equal(initiative.goal.riskLevel, "high");
});

test("intent touching the canonical town is escalated", async () => {
  const initiative = await planInitiative({
    intent: { title: "Grow", detail: "Please grow the town by ten houses." },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });
  assert.ok(
    initiative.escalations.some((e) => /canonical town/i.test(e)),
    "growing the town must be escalated",
  );
});

test("publishing intent is escalated", async () => {
  const initiative = await planInitiative({
    intent: { title: "Share it", detail: "Post the new reel to Instagram." },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });
  assert.ok(initiative.escalations.some((e) => /public/i.test(e)));
});

test("a planner proposing nothing is an error, not an empty initiative", async () => {
  await assert.rejects(
    () =>
      planInitiative({
        intent: { title: "Nothing", detail: "Do nothing." },
        planner: plannerReturning([]),
        idFactory: nextId,
        now: NOW,
      }),
    /proposed no tasks/,
  );
});

test("priority is clamped into range", async () => {
  const initiative = await planInitiative({
    intent: { title: "Urgent", detail: "Very important." },
    planner: plannerReturning([proposal({ priority: 5000 })]),
    idFactory: nextId,
    now: NOW,
  });
  assert.equal(initiative.tasks[0]?.priority, 100);
});

test("the worker and reviewer are never the same agent", async () => {
  const initiative = await planInitiative({
    intent: { title: "Anything", detail: "Do a small thing." },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });
  for (const task of initiative.tasks) {
    assert.notEqual(task.assignedAgentId, task.reviewerAgentId);
  }
});
