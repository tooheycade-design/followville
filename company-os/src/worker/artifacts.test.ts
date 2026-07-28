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
  type ArtifactStore,
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

function worktreeWith(files: Record<string, string | Buffer>): string {
  const root = mkdtempSync(path.join(tmpdir(), "fv-artifacts-"));
  for (const [relative, content] of Object.entries(files)) {
    const target = path.join(root, relative);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, content);
  }
  return root;
}

function pngBytes(content: string): Buffer {
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    Buffer.from(content),
  ]);
}

test("a screenshot becomes an artifact pointing at the checkpoint", async () => {
  const worktreePath = worktreeWith({
    "company-os/docs/images/claim.png": pngBytes("claim panel"),
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
  const bytes = pngBytes("exact content");
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
  assert.equal(artifact?.sizeBytes, bytes.byteLength);
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

test("required shared evidence fails closed when its bytes do not match its type", async () => {
  const store: ArtifactStore = {
    async store() {
      throw new Error("should not upload invalid bytes");
    },
  };
  await assert.rejects(
    collectArtifacts({
      task: makeTask(),
      worktreePath: worktreeWith({ "company-os/fake.png": "plain text" }),
      filesChanged: ["company-os/fake.png"],
      commitSha: "abc123def456",
      diff: null,
      runId: "94000000-0000-4000-8000-000000000099",
      artifactStore: store,
      createdByAgentId: SEED_AGENTS.engineer.id,
      idFactory: randomUUID,
    }),
    /does not match image\/png/,
  );
});

test("runtime browser evidence is uploaded even though it is not in the checkpoint", async () => {
  const relative =
    ".company-os/evidence/94000000-0000-4000-8000-000000000098/browser/desktop-home.png";
  const worktreePath = worktreeWith({ [relative]: pngBytes("browser proof") });
  const stored: string[] = [];
  const store: ArtifactStore = {
    async store(input) {
      stored.push(input.fileName);
      return {
        kind: "object",
        provider: "supabase_storage",
        bucket: "company-os-evidence",
        objectPath: `private/${input.artifactId}/${input.sha256}`,
      };
    },
  };

  const artifacts = await collectArtifacts({
    task: makeTask(),
    worktreePath,
    filesChanged: ["town.html"],
    evidenceFiles: [relative],
    commitSha: "abc123def456",
    diff: null,
    runId: "94000000-0000-4000-8000-000000000098",
    artifactStore: store,
    createdByAgentId: SEED_AGENTS.engineer.id,
    idFactory: randomUUID,
  });

  assert.deepEqual(stored, ["desktop-home.png"]);
  assert.equal(artifacts.length, 1);
  assert.equal(artifacts[0]?.location.kind, "object");
});

test("runtime browser evidence fails closed without shared storage", async () => {
  const relative = ".company-os/evidence/run/browser/desktop-home.png";
  await assert.rejects(
    collectArtifacts({
      task: makeTask(),
      worktreePath: worktreeWith({ [relative]: pngBytes("browser proof") }),
      filesChanged: [],
      evidenceFiles: [relative],
      commitSha: null,
      diff: null,
      runId: "94000000-0000-4000-8000-000000000097",
      createdByAgentId: SEED_AGENTS.engineer.id,
      idFactory: randomUUID,
    }),
    /requires shared object storage/,
  );
});

test("runtime Blender preview and metrics are preserved in the private store", async () => {
  const prefix = ".company-os/evidence/run/blender/model-hash";
  const preview = `${prefix}/preview.png`;
  const metrics = `${prefix}/metrics.json`;
  const stored: string[] = [];
  const artifactStore: ArtifactStore = {
    async store(input) {
      stored.push(input.fileName);
      return {
        kind: "object",
        provider: "supabase_storage",
        bucket: "company-os-evidence",
        objectPath: `test/${input.artifactId}/${input.fileName}`,
      };
    },
  };
  const artifacts = await collectArtifacts({
    task: makeTask(),
    worktreePath: worktreeWith({
      [preview]: pngBytes("blender proof"),
      [metrics]: Buffer.from('{"triangles":12}\n'),
    }),
    filesChanged: [],
    evidenceFiles: [preview, metrics],
    commitSha: null,
    diff: null,
    runId: "94000000-0000-4000-8000-000000000096",
    artifactStore,
    createdByAgentId: SEED_AGENTS.engineer.id,
    idFactory: randomUUID,
  });

  assert.deepEqual(stored, ["preview.png", "metrics.json"]);
  assert.deepEqual(
    artifacts.map((artifact) => [artifact.kind, artifact.mediaType]),
    [
      ["screenshot", "image/png"],
      ["report", "application/json"],
    ],
  );
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
    inlineText: null,
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

test("an object artifact keeps its exact private location through the audit trail", () => {
  const task = makeTask();
  const runId = "94000000-0000-4000-8000-000000000010";
  const original = {
    id: "94000000-0000-4000-8000-000000000011",
    goalId: task.goalId,
    runId,
    kind: "screenshot",
    label: "desktop.png",
    mediaType: "image/png",
    sizeBytes: 100,
    sha256: "d".repeat(64),
    commitSha: null,
    repositoryPath: null,
    inlineText: null,
    storageProvider: "supabase_storage" as const,
    storageBucket: "company-os-evidence",
    storageObjectPath:
      `organizations/${task.organizationId}/projects/${task.projectId}/` +
      `goals/${task.goalId}/tasks/${task.id}/runs/${runId}/artifacts/` +
      `94000000-0000-4000-8000-000000000011/${"d".repeat(64)}`,
    visibility: "owner_only" as const,
    containsSensitiveData: false,
    safeToDisplay: true,
    retentionPolicy: "approval_record" as const,
  };
  const decoded = decodeWorkerReport(
    encodeWorkerReport({
      summary: "Captured it.",
      evidence: ["provider=codex"],
      filesChanged: ["evidence/desktop.png"],
      artifacts: [original],
    }),
  );
  const rebuilt = artifactFromReport(
    decoded.artifacts[0]!,
    task,
    SEED_AGENTS.engineer.id,
    NOW,
    runId,
  );

  assert.deepEqual(rebuilt.location, {
    kind: "object",
    provider: "supabase_storage",
    bucket: "company-os-evidence",
    objectPath: original.storageObjectPath,
  });
  assert.equal(rebuilt.runId, runId);
  assert.equal(rebuilt.goalId, task.goalId);
  assert.equal(retrievalHint(rebuilt), "private supabase_storage object");
});

test("an inline patch rebuilt from the trail keeps the bytes it hashes", () => {
  const text = "diff --git a/a.md b/a.md\n+kept\n";
  const rebuilt = artifactFromReport(
    {
      id: "94000000-0000-4000-8000-000000000003",
      kind: "patch",
      label: "Diff of 1 file(s)",
      mediaType: "text/x-diff",
      sizeBytes: Buffer.byteLength(text),
      sha256: "c".repeat(64),
      commitSha: null,
      repositoryPath: null,
      inlineText: text,
    },
    makeTask(),
    SEED_AGENTS.engineer.id,
    NOW,
  );

  assert.deepEqual(rebuilt.location, { kind: "inline", text });
});
