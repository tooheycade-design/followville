import assert from "node:assert/strict";
import { test } from "node:test";

import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import { TaskSchema, type Task } from "../domain/schemas.js";
import type { ModelProvider, ProviderResponse } from "../providers/types.js";
import {
  ModelVisualReviewer,
  taskRequiresVisualReview,
  visualReviewAuditEvent,
} from "./visual-review.js";

const NOW = "2026-07-29T12:00:00.000Z";
let id = 0;
const nextId = (): string =>
  `95000000-0000-4000-8000-${String(++id).padStart(12, "0")}`;

function task(): Task {
  return TaskSchema.parse({
    id: nextId(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: nextId(),
    parentTaskId: null,
    title: "Polish the owner dashboard",
    objective: "Make the review queue clear and visually coherent.",
    reason: "Owners need a legible operating view.",
    status: "awaiting_review",
    priority: 50,
    riskLevel: "low",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: nextId(),
        description: "Desktop and mobile evidence is legible.",
        verificationMethod: "Inspect screenshots.",
        required: true,
      },
    ],
    allowedCapabilities: ["repository_read", "browser_preview"],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["Screenshots"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
  });
}

function provider(output: string, available = true): {
  value: ModelProvider;
  prompts: string[];
  directories: string[];
} {
  const prompts: string[] = [];
  const directories: string[] = [];
  return {
    prompts,
    directories,
    value: {
      name: "fake-design-judge",
      billingMode: "subscription",
      async checkAvailability() {
        return available
          ? ({ available: true, detail: "test" } as const)
          : ({
              available: false,
              reason: "not_authenticated",
              detail: "test",
            } as const);
      },
      async invoke(request): Promise<ProviderResponse> {
        prompts.push(request.prompt);
        directories.push(request.workingDirectory);
        return {
          ok: true,
          text: output,
          usage: {
            inputTokens: 1,
            outputTokens: 1,
            cachedInputTokens: 0,
            costUsdMicros: 0,
          },
          model: "fake",
          sessionId: null,
          failureReason: null,
        };
      },
    },
  };
}

const evidence = [
  {
    fileName: "evidence-01.png",
    label: "Mobile approval queue",
    mediaType: "image/png",
    sha256: "a".repeat(64),
  },
];

test("the Design Director is told to inspect actual untrusted image files", async () => {
  const fake = provider("[]");
  const result = await new ModelVisualReviewer(fake.value).review({
    task: task(),
    workingDirectory: "C:\\private-review",
    evidence,
  });
  assert.equal(result.accepted, true);
  assert.equal(fake.directories[0], "C:\\private-review");
  assert.match(fake.prompts[0] ?? "", /Inspect every listed image file/);
  assert.match(fake.prompts[0] ?? "", /untrusted evidence/);
  assert.match(fake.prompts[0] ?? "", /evidence-01\.png/);
});

test("visual work is recognized from its task contract", () => {
  assert.equal(taskRequiresVisualReview(task()), true);
  assert.equal(
    taskRequiresVisualReview(
      TaskSchema.parse({
        ...task(),
        allowedCapabilities: ["repository_read"],
        expectedOutputs: ["A text report"],
      }),
    ),
    false,
  );
});

test("specific valid visual findings send work back", async () => {
  const fake = provider(
    '[{"code":"mobile_problem","note":"The primary action is clipped."}]',
  );
  const result = await new ModelVisualReviewer(fake.value).review({
    task: task(),
    workingDirectory: "C:\\private-review",
    evidence,
  });
  assert.equal(result.accepted, false);
  assert.match(result.summary, /primary action is clipped/);
});

test("malformed or partially invalid findings fail closed", async () => {
  const fake = provider(
    '[{"code":"clutter","note":"Too dense."},{"code":"invented","note":"x"}]',
  );
  const result = await new ModelVisualReviewer(fake.value).review({
    task: task(),
    workingDirectory: "C:\\private-review",
    evidence,
  });
  assert.equal(result.accepted, false);
  assert.equal(result.findings[0]?.code, "evidence_unreadable");
});

test("an unavailable judge fails closed", async () => {
  const fake = provider("[]", false);
  const result = await new ModelVisualReviewer(fake.value).review({
    task: task(),
    workingDirectory: "C:\\private-review",
    evidence,
  });
  assert.equal(result.accepted, false);
  assert.match(result.summary, /unavailable/);
});

test("visual decisions pin the evidence and Design Director identity", () => {
  const current = task();
  const event = visualReviewAuditEvent(
    current,
    { accepted: false, findings: [], summary: "Spacing is inconsistent." },
    SEED_AGENTS.designDirector.id,
    [nextId()],
    nextId,
    NOW,
  );
  assert.equal(event.actorId, SEED_AGENTS.designDirector.id);
  assert.equal(event.action, "visual_review.changes_requested");
  assert.equal(event.evidenceArtifactIds.length, 1);
});
