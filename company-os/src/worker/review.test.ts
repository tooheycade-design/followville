import assert from "node:assert/strict";
import { test } from "node:test";

import { TaskSchema, type Task } from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import {
  EvidenceReviewer,
  assertIndependentReviewer,
  reviewReworkBriefing,
} from "./review.js";
import { encodeWorkerReport } from "./report.js";

let counter = 0;
const nextId = (): string =>
  `93000000-0000-4000-8000-${(counter += 1).toString().padStart(12, "0")}`;

function makeTask(overrides: Partial<Task> = {}): Task {
  return TaskSchema.parse({
    id: nextId(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: nextId(),
    parentTaskId: null,
    title: "Reviewed work",
    objective: "Do something checkable.",
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
        description: "The objective is addressed.",
        verificationMethod: "Reviewer inspects evidence.",
        required: true,
      },
    ],
    allowedCapabilities: ["repository_read"],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["A result"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: "2026-07-26T19:00:00.000Z",
    updatedAt: "2026-07-26T19:00:00.000Z",
    ...overrides,
  });
}

const reviewer = new EvidenceReviewer();

test("work with evidence and a real summary is passed to the owner", async () => {
  const result = await reviewer.review({
    task: makeTask(),
    workerEvidence: ["branch=agent/task-1", "files_changed=0"],
    workerSummary: "Inspected the repository and reported its current state.",
    filesChanged: [],
  });
  assert.equal(result.verdict, "approved_for_owner");
});

test("success claimed without evidence is sent back", async () => {
  const result = await reviewer.review({
    task: makeTask(),
    workerEvidence: [],
    workerSummary: "Everything went perfectly and the work is complete.",
    filesChanged: [],
  });
  assert.equal(result.verdict, "changes_requested");
  assert.match(result.summary, /no evidence/i);
});

test("a summary claiming edits with no diff is sent back", async () => {
  const result = await reviewer.review({
    task: makeTask(),
    workerEvidence: ["branch=agent/task-2"],
    workerSummary: "Updated the configuration and fixed the failing check.",
    filesChanged: [],
  });
  assert.equal(result.verdict, "changes_requested");
  assert.match(result.summary, /claims changes but no files/i);
});

test("a summary claiming edits with a real diff passes", async () => {
  const result = await reviewer.review({
    task: makeTask(),
    workerEvidence: ["branch=agent/task-3", "files_changed=1"],
    workerSummary: "Updated company-os/notes.md with the requested detail.",
    filesChanged: ["company-os/notes.md"],
  });
  assert.equal(result.verdict, "approved_for_owner");
});

test("an empty summary is sent back", async () => {
  const result = await reviewer.review({
    task: makeTask(),
    workerEvidence: ["branch=agent/task-4"],
    workerSummary: "   ",
    filesChanged: [],
  });
  assert.equal(result.verdict, "changes_requested");
});

test("a failed runtime-owned check is always sent back", async () => {
  const result = await reviewer.review({
    task: makeTask(),
    workerEvidence: ["check=core-tests failed 50ms"],
    workerSummary: "Updated the implementation and recorded the failed check.",
    filesChanged: ["company-os/src/example.ts"],
    testsCompleted: ["Company OS strict TypeScript"],
    testsFailed: ["Company OS test suite"],
  });

  assert.equal(result.verdict, "changes_requested");
  assert.match(result.summary, /Failed checks: Company OS test suite/);
});

test("the next attempt receives reviewer and failed-check diagnostics", () => {
  const briefing = reviewReworkBriefing([
    {
      action: "worker.completed",
      reason: encodeWorkerReport({
        summary: "Changed the implementation.",
        evidence: [
          "check=core-tests failed 50ms",
          "check_output=one assertion failed",
        ],
        filesChanged: ["company-os/src/example.ts"],
        testsFailed: ["Company OS test suite"],
      }),
    },
    {
      action: "review.changes_requested",
      reason: "Failed checks: Company OS test suite.",
    },
  ]);

  assert.match(briefing, /independent reviewer/);
  assert.match(briefing, /Failed checks: Company OS test suite/);
  assert.match(briefing, /one assertion failed/);
});

test("a task whose worker and reviewer differ passes the independence check", () => {
  assert.doesNotThrow(() => assertIndependentReviewer(makeTask()));
});

test("a reviewer that is also the worker is refused", () => {
  // The schema forbids constructing this, which is the first line of defence.
  // The runtime guard is the second, for state that reached memory by another
  // route, so the check is exercised against a deliberately corrupted task.
  const corrupted = {
    ...makeTask(),
    reviewerAgentId: SEED_AGENTS.engineer.id,
  } as Task;
  assert.throws(
    () => assertIndependentReviewer(corrupted),
    /would not be independent/,
  );
});
