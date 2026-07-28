import assert from "node:assert/strict";
import test from "node:test";

import {
  ORGANIZATION_ID,
  PROJECT_ID,
  SEED_AGENTS,
} from "@followville/company-os-core";

import { createAgentMessage } from "./structured-message";

const TASK = {
  id: "50000000-0000-4000-8000-000000000001",
  organizationId: ORGANIZATION_ID,
  projectId: PROJECT_ID,
  goalId: "30000000-0000-4000-8000-000000000001",
};
const MESSAGE_ID = "80000000-0000-4000-8000-000000000001";

test("agent messages are task-threaded, expiring, and deterministic", () => {
  const input = {
    task: TASK,
    senderId: SEED_AGENTS.engineer.id,
    recipientId: SEED_AGENTS.reviewer.id,
    type: "review_request" as const,
    priority: "normal" as const,
    contextSummary: "Review this checkpoint.",
    requestedAction: "Inspect the evidence.",
    expectedOutput: "Findings or approval.",
    evidenceArtifactIds: [] as string[],
    now: new Date("2026-07-28T20:00:00.000Z"),
  };
  const first = createAgentMessage(input, () => MESSAGE_ID);
  const second = createAgentMessage(input, () => MESSAGE_ID);

  assert.equal(first.threadId, TASK.id);
  assert.equal(first.expiresAt, "2026-08-04T20:00:00.000Z");
  assert.equal(first.confidence, "confirmed");
  assert.equal(first.fingerprint.length, 64);
  assert.equal(first.fingerprint, second.fingerprint);
});

test("message payloads are bounded before validation and hashing", () => {
  const message = createAgentMessage(
    {
      task: TASK,
      senderId: SEED_AGENTS.engineer.id,
      recipientId: SEED_AGENTS.reviewer.id,
      type: "evidence",
      priority: "high",
      contextSummary: "x".repeat(9_000),
      requestedAction: null,
      expectedOutput: null,
      evidenceArtifactIds: Array.from(
        { length: 30 },
        (_, index) =>
          `70000000-0000-4000-8000-${String(index + 1).padStart(12, "0")}`,
      ),
      now: new Date("2026-07-28T20:00:00.000Z"),
    },
    () => MESSAGE_ID,
  );

  assert.equal(message.contextSummary.length, 8_000);
  assert.equal(message.evidenceArtifactIds.length, 25);
});
