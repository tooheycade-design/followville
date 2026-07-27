import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { test } from "node:test";

import { TaskSchema, type Task } from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import {
  artifactFromReport,
  collectArtifacts,
  retrievalHint,
} from "./artifacts.js";
import { decodeWorkerReport, encodeWorkerReport } from "./report.js";

const NOW = "2026-07-27T12:00:00.000Z";

function makeTask(): Task {
  return TaskSchema.parse({
    id: "93000000-0000-4000-8000-000000000001",
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: "93000000-0000-4000-8000-000000000002",
    parentTaskId: null,
    title: "Show the claim panel",
    objective: "Capture what a visitor sees.",
    reason: "An owner asked.",
    status: "in_progress",
    priority: 50,
    riskLevel: "low",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: "93000000-0000-4000-8000-000000000003",
        description: "A screenshot exists.",
        verificationMethod: "Owner opens it.",
        required: true,
      },
    ],
    allowedCapabilities: ["repository_read", "repository_write", "git_checkpoint"],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["A screenshot"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
  });
}

function worktreeWith(files: Record<string, string>): string {
  const root = mkdtempSync(path.join(tmpdir(), "fv-artifacts-"));
  for (const [relative, content] of Object.entries(files)) {
    const target = path.join(root, relative);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, content);
  }
  return root;
}

test("a screenshot becomes an artifact pointing at the checkpoint", async () => {
  const worktreePath = worktreeWith({
    "company-os/docs/images/claim.png": "not really a png, but bytes are bytes",
    "company-os/docs/GUIDE.md": "# Guide\n",
  });

  const artifacts = await collectArtifacts({
    task: makeTask(),
    worktreePath,
    filesChanged: ["company-os/docs/images/claim.png", "company-os/docs/GUIDE.md"],
    commitSha: "abc123def456",
    diff: null,
    createdByAgentId: SEED_AGENTS.engineer.id,
    idFactory: randomUUID,
  });

  assert.equal(artifacts.length, 1, "the markdown file is not an artifact");
  const [screenshot] = artifacts;
  assert.equal(screenshot?.kind, "screenshot");
  assert.equal(screenshot?.mediaType, "image/png");
  assert.equal(screenshot?.label, "claim.png");
  assert.deepEqual(screenshot?.location, {
    kind: "git",
    commitSha: "abc123def456",
    repositoryPath: "company-os/docs/images/claim.png",
  });
  assert.equal(
    retrievalHint(screenshot!),
    "git show abc123def456:company-os/docs/images/claim.png",
  );
});

test("the hash is of the real bytes, so an artifact can be verified", async () => {
  const bytes = "exact content";
  const worktreePath = worktreeWith({ "company-os/shot.png": bytes });

  const [artifact] = await collectArtifacts({
    task: makeTask(),
    worktreePath,
    filesChanged: ["company-os/shot.png"],
    commitSha: "0123456789ab",
    diff: null,
    createdByAgentId: SEED_AGENTS.engineer.id,
    idFactory: randomUUID,
  });

  assert.equal(
    artifact?.sha256,
    createHash("sha256").update(bytes).digest("hex"),
  );
  assert.equal(artifact?.sizeBytes, Buffer.byteLength(bytes));
});

test("the diff is always an artifact, even with nothing else to show", async () => {
  const artifacts = await collectArtifacts({
    task: makeTask(),
    worktreePath: worktreeWith({}),
    filesChanged: ["company-os/docs/GUIDE.md"],
    commitSha: null,
    diff: "diff --git a/company-os/docs/GUIDE.md\n+# Guide",
    createdByAgentId: SEED_AGENTS.engineer.id,
    idFactory: randomUUID,
  });

  assert.equal(artifacts.length, 1);
  assert.equal(artifacts[0]?.kind, "patch");
  assert.equal(artifacts[0]?.location.kind, "inline");
});

test("without a checkpoint no file artifact is recorded", async () => {
  // Pointing at a path inside a worktree about to be deleted would be a
  // reference that breaks the moment the task finishes.
  const worktreePath = worktreeWith({ "company-os/shot.png": "bytes" });

  const artifacts = await collectArtifacts({
    task: makeTask(),
    worktreePath,
    filesChanged: ["company-os/shot.png"],
    commitSha: null,
    diff: null,
    createdByAgentId: SEED_AGENTS.engineer.id,
    idFactory: randomUUID,
  });

  assert.deepEqual(artifacts, []);
});

test("a file that vanished is skipped rather than failing the task", async () => {
  const artifacts = await collectArtifacts({
    task: makeTask(),
    worktreePath: worktreeWith({}),
    filesChanged: ["company-os/gone.png"],
    commitSha: "abc123def456",
    diff: null,
    createdByAgentId: SEED_AGENTS.engineer.id,
    idFactory: randomUUID,
  });

  assert.deepEqual(artifacts, [], "evidence collection must not fail the work");
});

test("artifacts survive the audit trail so an owner can find them", () => {
  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Captured the claim panel.",
      evidence: ["provider=codex"],
      filesChanged: ["company-os/docs/images/claim panel.png"],
      artifacts: [
        {
          id: "94000000-0000-4000-8000-000000000001",
          kind: "screenshot",
          // A label with a tab and a comma: the encoding must not corrupt what
          // an owner later decides on.
          label: "claim panel\t(wide), v2.png",
          mediaType: "image/png",
          sizeBytes: 45_210,
          sha256: "a".repeat(64),
          commitSha: "abc123",
          repositoryPath: "company-os/docs/images/claim panel.png",
        },
      ],
    }),
  );

  assert.equal(decoded.artifacts.length, 1);
  assert.deepEqual(decoded.artifacts[0], {
    id: "94000000-0000-4000-8000-000000000001",
    kind: "screenshot",
    label: "claim panel\t(wide), v2.png",
    mediaType: "image/png",
    sizeBytes: 45_210,
    sha256: "a".repeat(64),
    commitSha: "abc123",
    repositoryPath: "company-os/docs/images/claim panel.png",
  });
});

test("an artifact rebuilt from the trail still points at the same bytes", () => {
  const original = {
    id: "94000000-0000-4000-8000-000000000002",
    kind: "screenshot",
    label: "claim.png",
    mediaType: "image/png",
    sizeBytes: 100,
    sha256: "b".repeat(64),
    commitSha: "abc123def456",
    repositoryPath: "company-os/docs/claim.png",
  };
  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Captured it.",
      evidence: ["provider=codex"],
      filesChanged: ["company-os/docs/claim.png"],
      artifacts: [original],
    }),
  );

  const rebuilt = artifactFromReport(
    decoded.artifacts[0]!,
    makeTask(),
    SEED_AGENTS.engineer.id,
    NOW,
  );
  assert.equal(rebuilt.sha256, original.sha256);
  assert.equal(
    retrievalHint(rebuilt),
    "git show abc123def456:company-os/docs/claim.png",
  );
});
