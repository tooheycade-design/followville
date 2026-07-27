import assert from "node:assert/strict";
import { test } from "node:test";

import { TaskSchema, type Task } from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import type { ModelProvider, ProviderResponse } from "../providers/types.js";
import {
  CeoGate,
  gateAuditEvent,
  mechanicalFindings,
  priorRejectionsFrom,
  reworkBriefing,
  type GateInput,
} from "./ceo-gate.js";

let counter = 0;
const nextId = (): string =>
  `96000000-0000-4000-8000-${(counter += 1).toString().padStart(12, "0")}`;
const NOW = "2026-07-27T07:00:00.000Z";

function makeTask(criteria = "Add a note file describing the runtime."): Task {
  return TaskSchema.parse({
    id: nextId(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: nextId(),
    parentTaskId: null,
    title: "Do the work",
    objective: "Make the change.",
    reason: "An owner asked.",
    status: "awaiting_review",
    priority: 50,
    riskLevel: "low",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: nextId(),
        description: criteria,
        verificationMethod: "Reviewer checks the diff.",
        required: true,
      },
    ],
    allowedCapabilities: ["repository_read", "repository_write"],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["A change"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
  });
}

function goodInput(overrides: Partial<GateInput> = {}): GateInput {
  return {
    task: makeTask(),
    workerSummary:
      "Created company-os/NOTE.md with four lines describing how the worker leases and runs tasks.",
    workerEvidence: ["branch=agent/task-1", "changed: company-os/NOTE.md"],
    filesChanged: ["company-os/NOTE.md"],
    priorRejections: [],
    ...overrides,
  };
}

function provider(text: string, ok = true): ModelProvider {
  return {
    name: "fake",
    billingMode: "subscription",
    async checkAvailability() {
      return { available: true, detail: "test" };
    },
    async invoke(): Promise<ProviderResponse> {
      return {
        ok,
        text,
        usage: { inputTokens: 5, outputTokens: 5, cachedInputTokens: 0, costUsdMicros: 0 },
        model: "fake",
        sessionId: null,
        failureReason: ok ? null : "refused",
      };
    },
  };
}

test("good work with evidence is accepted", async () => {
  const verdict = await new CeoGate().judge(goodInput());
  assert.equal(verdict.accepted, true);
  assert.deepEqual(verdict.reasons, []);
});

test("work with no evidence is sent back", async () => {
  const verdict = await new CeoGate().judge(goodInput({ workerEvidence: [] }));
  assert.equal(verdict.accepted, false);
  assert.ok(verdict.reasons.includes("missing_evidence"));
});

test("a criterion implying a change with no diff is unmet", () => {
  const reasons = mechanicalFindings(goodInput({ filesChanged: [] }));
  assert.ok(reasons.includes("criteria_unmet"));
});

test("a terse summary is sent back for insufficient detail", () => {
  const reasons = mechanicalFindings(goodInput({ workerSummary: "Done." }));
  assert.ok(reasons.includes("insufficient_detail"));
});

test("an enormous change is sent back to be split", () => {
  const many = Array.from({ length: 41 }, (_, i) => `company-os/f${i}.ts`);
  const reasons = mechanicalFindings(goodInput({ filesChanged: many }));
  assert.ok(reasons.includes("too_large"));
});

test("the model can send back work that passed mechanical checks", async () => {
  const gate = new CeoGate({ provider: provider('["visually_weak","not_followville"]') });
  const verdict = await gate.judge(goodInput());
  assert.equal(verdict.accepted, false);
  assert.deepEqual(verdict.reasons, ["visually_weak", "not_followville"]);
});

test("an empty model verdict accepts", async () => {
  const gate = new CeoGate({ provider: provider("[]") });
  assert.equal((await gate.judge(goodInput())).accepted, true);
});

test("invented reason codes are ignored rather than trusted", async () => {
  const gate = new CeoGate({ provider: provider('["totally_made_up","visually_weak"]') });
  const verdict = await gate.judge(goodInput());
  assert.deepEqual(verdict.reasons, ["visually_weak"]);
});

test("a failed model call does not accept by default", async () => {
  const gate = new CeoGate({ provider: provider("[]", false) });
  const verdict = await gate.judge(goodInput({ workerEvidence: [] }));
  assert.equal(verdict.accepted, false, "mechanical findings must still stand");
});

test("the model is not consulted when mechanical checks already failed", async () => {
  let called = false;
  const counting: ModelProvider = {
    ...provider("[]"),
    async invoke() {
      called = true;
      throw new Error("must not be called");
    },
  };
  await new CeoGate({ provider: counting }).judge(goodInput({ workerEvidence: [] }));
  assert.equal(called, false, "a plainly failing task must not cost a model call");
});

test("rejection reasons survive the audit trail and reach the retry", () => {
  const task = makeTask();
  const event = gateAuditEvent(
    task,
    { accepted: false, reasons: ["visually_weak", "criteria_unmet"], notes: "n" },
    nextId,
    NOW,
  );
  assert.equal(event.action, "ceo.sent_back");

  const recovered = priorRejectionsFrom([event]);
  assert.deepEqual(recovered, ["visually_weak", "criteria_unmet"]);

  const briefing = reworkBriefing(recovered);
  assert.match(briefing, /previously sent back/);
  assert.match(briefing, /Visually poor/);
});

test("an accepted task records acceptance, not a rejection", () => {
  const event = gateAuditEvent(
    makeTask(),
    { accepted: true, reasons: [], notes: "good" },
    nextId,
    NOW,
  );
  assert.equal(event.action, "ceo.accepted");
  assert.equal(priorRejectionsFrom([event]).length, 0);
});

test("a first attempt gets no rework briefing", () => {
  assert.equal(reworkBriefing([]), "");
});
