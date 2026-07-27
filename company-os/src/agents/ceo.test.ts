import assert from "node:assert/strict";
import { test } from "node:test";

import type { Capability } from "../domain/schemas.js";
import { SEED_AGENTS } from "../config/seed-agents.js";
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
  // git_commit is held by the engineer but is deliberately outside the CEO's
  // grantable set, so only an explicit owner grant can put it on a task.
  const initiative = await planInitiative({
    intent: { title: "Commit the work", detail: "Land the change on a branch." },
    planner: plannerReturning([
      proposal({ requestedCapabilities: ["git_commit"] }),
    ]),
    idFactory: nextId,
    now: NOW,
    ownerGrantedCapabilities: ["git_commit"],
  });
  assert.deepEqual(initiative.tasks[0]?.allowedCapabilities, ["git_commit"]);
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

test("prohibiting a sensitive action does not request that action", async () => {
  const prohibitions = [
    ["Do not deploy", "Make the local code change only."],
    ["Safety first", "Never publish this to Instagram."],
    ["Keep the database", "Do not accidentally delete or reset anything."],
    ["No pricing changes", "Improve the existing free workflow."],
    ["Protect the town", "Do not touch world_state or grow the town."],
    ["Safety policy", "Production deployment must not happen."],
  ] as const;

  for (const [title, detail] of prohibitions) {
    const initiative = await planInitiative({
      intent: { title, detail },
      planner: new HeuristicPlanner(),
      idFactory: nextId,
      now: NOW,
    });
    assert.deepEqual(
      initiative.escalations,
      [],
      `${title}: ${detail} is a prohibition, not an action request`,
    );
    assert.ok(initiative.tasks.every((task) => task.status === "queued"));
  }
});

test("a positive sensitive action still escalates beside a prohibition", async () => {
  const initiative = await planInitiative({
    intent: {
      title: "Prepare local materials",
      detail: "Do not deploy the code, but publish the approved announcement.",
    },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });

  assert.equal(
    initiative.escalations.some((reason) => /production/i.test(reason)),
    false,
  );
  assert.equal(
    initiative.escalations.some((reason) => /public/i.test(reason)),
    true,
  );
});

test("contrastive not does not hide a real production request", async () => {
  const initiative = await planInitiative({
    intent: {
      title: "Release everywhere",
      detail: "Not only deploy the build, but publish the announcement.",
    },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });

  assert.ok(initiative.escalations.some((reason) => /production/i.test(reason)));
  assert.ok(initiative.escalations.some((reason) => /public/i.test(reason)));
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

test("the CEO cannot grant a capability no agent holds", async () => {
  // This is what browser_preview used to be: in the CEO's grantable set but
  // held by no agent, so tasks were planned, queued, leased, and only then
  // blocked at execution. The planner must catch that at plan time.
  const initiative = await planInitiative({
    intent: { title: "Prepare a migration", detail: "Draft the schema change." },
    planner: plannerReturning([
      proposal({
        requestedCapabilities: ["repository_read", "database_migration_prepare"],
      }),
    ]),
    idFactory: nextId,
    now: NOW,
    ownerGrantedCapabilities: ["database_migration_prepare"],
  });
  const task = initiative.tasks[0];
  assert.ok(task);
  assert.deepEqual(task.allowedCapabilities, ["repository_read"]);
  assert.deepEqual(initiative.clampedCapabilities[0]?.removed, [
    "database_migration_prepare",
  ]);
});

test("every capability the CEO grants is one the worker can actually use", async () => {
  const initiative = await planInitiative({
    intent: { title: "Ordinary work", detail: "Make a small change." },
    planner: new HeuristicPlanner(),
    idFactory: nextId,
    now: NOW,
  });
  for (const task of initiative.tasks) {
    for (const capability of task.allowedCapabilities) {
      assert.ok(
        SEED_AGENTS.engineer.capabilities.includes(capability),
        `engineer must hold ${capability}`,
      );
    }
  }
});

test("the CEO can now grant preview capabilities the engineer holds", async () => {
  const initiative = await planInitiative({
    intent: { title: "Check the UI", detail: "Look at the claim flow." },
    planner: plannerReturning([
      proposal({
        requestedCapabilities: ["repository_read", "browser_preview", "blender_preview"],
      }),
    ]),
    idFactory: nextId,
    now: NOW,
  });
  assert.deepEqual(initiative.tasks[0]?.allowedCapabilities, [
    "repository_read",
    "browser_preview",
    "blender_preview",
  ]);
  assert.equal(initiative.clampedCapabilities.length, 0);
});

test("preview capabilities did not smuggle in production authority", () => {
  const production = [
    "production_merge",
    "production_deploy",
    "production_database_write",
    "canonical_world_growth",
    "public_communication",
    "social_publish",
    "payment_charge",
    "price_change",
    "destructive_delete",
  ];
  for (const capability of production) {
    assert.ok(
      !SEED_AGENTS.engineer.capabilities.includes(capability as never),
      `engineer must still not hold ${capability}`,
    );
  }
});
