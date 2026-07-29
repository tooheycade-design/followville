import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import {
  EvidenceArtifactSchema,
  TaskSchema,
  type EvidenceArtifact,
} from "@followville/company-os-core";
import {
  EVIDENCE_BUCKET,
  SupabaseArtifactStore,
  evidenceObjectPath,
  type ArtifactStorageClient,
} from "./artifact-storage";

const task = TaskSchema.parse({
  id: "91000000-0000-4000-8000-000000000001",
  organizationId: "10000000-0000-4000-8000-000000000001",
  projectId: "20000000-0000-4000-8000-000000000001",
  goalId: "91000000-0000-4000-8000-000000000002",
  parentTaskId: null,
  title: "Capture a preview",
  objective: "Capture a private preview.",
  reason: "Owner review needs visual evidence.",
  status: "in_progress",
  priority: 50,
  riskLevel: "low",
  assignedAgentId: "40000000-0000-4000-8000-000000000003",
  reviewerAgentId: "40000000-0000-4000-8000-000000000004",
  dependencyIds: [],
  acceptanceCriteria: [
    {
      id: "91000000-0000-4000-8000-000000000003",
      description: "The preview is stored.",
      verificationMethod: "Open the owner link.",
      required: true,
    },
  ],
  allowedCapabilities: ["repository_read", "browser_preview"],
  repositoryScopes: [
    {
      repository: "followville_repo",
      allowedPathPrefixes: ["apps/company-dashboard/"],
      deniedPathPrefixes: [],
      environments: ["local"],
    },
  ],
  budgetUsdMicros: 0,
  estimatedCostUsdMicros: 0,
  actualCostUsdMicros: 0,
  retryCount: 0,
  reviewCycleCount: 0,
  branchName: null,
  expectedOutputs: ["Screenshot"],
  testRequirements: [],
  approvalRequired: true,
  version: 1,
  createdAt: "2026-07-28T12:00:00.000Z",
  updatedAt: "2026-07-28T12:00:00.000Z",
});

function input(absolutePath: string, bytes: Buffer) {
  return {
    artifactId: "91000000-0000-4000-8000-000000000004",
    task,
    runId: "91000000-0000-4000-8000-000000000005",
    absolutePath,
    fileName: "../../owner supplied name.png",
    mediaType: "image/png",
    sha256: createHash("sha256").update(bytes).digest("hex"),
    sizeBytes: bytes.byteLength,
  };
}

function artifact(bytes: Buffer, overrides: Partial<EvidenceArtifact> = {}) {
  return EvidenceArtifactSchema.parse({
    id: "91000000-0000-4000-8000-000000000004",
    organizationId: task.organizationId,
    projectId: task.projectId,
    goalId: task.goalId,
    taskId: task.id,
    runId: "91000000-0000-4000-8000-000000000005",
    kind: "screenshot",
    label: "Desktop preview",
    mediaType: "image/png",
    sizeBytes: bytes.byteLength,
    sha256: createHash("sha256").update(bytes).digest("hex"),
    location: {
      kind: "object",
      provider: "supabase_storage",
      bucket: EVIDENCE_BUCKET,
      objectPath: "organizations/example/evidence",
    },
    visibility: "owner_only",
    containsSensitiveData: false,
    safeToDisplay: true,
    retentionPolicy: "approval_record",
    createdByAgentId: "40000000-0000-4000-8000-000000000003",
    createdAt: "2026-07-29T12:00:00.000Z",
    expiresAt: null,
    ...overrides,
  });
}

function boundedPng(width = 100, height = 100): Buffer {
  const value = Buffer.alloc(24);
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]).copy(value);
  value.write("IHDR", 12, "ascii");
  value.writeUInt32BE(width, 16);
  value.writeUInt32BE(height, 20);
  return value;
}

test("object paths are scope-derived and ignore the supplied filename", () => {
  const bytes = Buffer.from("bytes");
  const value = evidenceObjectPath(input("C:\\ignored", bytes));
  assert.equal(
    value,
    `organizations/${task.organizationId}/projects/${task.projectId}/` +
      `goals/${task.goalId}/tasks/${task.id}/` +
      `runs/91000000-0000-4000-8000-000000000005/` +
      `artifacts/91000000-0000-4000-8000-000000000004/` +
      createHash("sha256").update(bytes).digest("hex"),
  );
  assert.doesNotMatch(value, /owner supplied|\.\./);
});

test("uploads never overwrite and are verified by downloading the stored bytes", async () => {
  const root = mkdtempSync(path.join(tmpdir(), "fv-object-store-"));
  const file = path.join(root, "preview.png");
  const bytes = Buffer.from("verified bytes");
  writeFileSync(file, bytes);
  let uploadedPath = "";
  const storage: ArtifactStorageClient = {
    from(bucket) {
      assert.equal(bucket, EVIDENCE_BUCKET);
      return {
        async upload(objectPath, body, options) {
          uploadedPath = objectPath;
          assert.equal(Buffer.from(body).toString(), bytes.toString());
          assert.equal(options.upsert, false);
          return { error: null };
        },
        async download(objectPath) {
          assert.equal(objectPath, uploadedPath);
          return { data: new Blob([Uint8Array.from(bytes)]), error: null };
        },
        async createSignedUrl() {
          return { data: null, error: { message: "not used" } };
        },
      };
    },
  };

  const location = await new SupabaseArtifactStore(storage).store(
    input(file, bytes),
  );
  assert.deepEqual(location, {
    kind: "object",
    provider: "supabase_storage",
    bucket: EVIDENCE_BUCKET,
    objectPath: uploadedPath,
  });
});

test("a stored byte mismatch is refused rather than cited as evidence", async () => {
  const root = mkdtempSync(path.join(tmpdir(), "fv-object-store-"));
  const file = path.join(root, "preview.png");
  const bytes = Buffer.from("expected");
  writeFileSync(file, bytes);
  const storage: ArtifactStorageClient = {
    from() {
      return {
        async upload() {
          return { error: null };
        },
        async download() {
          return { data: new Blob(["different"]), error: null };
        },
        async createSignedUrl() {
          return { data: null, error: { message: "not used" } };
        },
      };
    },
  };

  await assert.rejects(
    new SupabaseArtifactStore(storage).store(input(file, bytes)),
    /does not match/,
  );
});

test("visual review downloads and verifies owner-safe image evidence", async () => {
  const bytes = boundedPng();
  const storage: ArtifactStorageClient = {
    from(bucket) {
      assert.equal(bucket, EVIDENCE_BUCKET);
      return {
        async upload() {
          return { error: null };
        },
        async download(objectPath) {
          assert.equal(objectPath, "organizations/example/evidence");
          return { data: new Blob([Uint8Array.from(bytes)]), error: null };
        },
        async createSignedUrl() {
          return { data: null, error: { message: "not used" } };
        },
      };
    },
  };
  assert.deepEqual(
    await new SupabaseArtifactStore(storage).loadVerified(artifact(bytes)),
    bytes,
  );
});

test("visual review refuses unsafe or altered evidence", async () => {
  const bytes = boundedPng();
  const storage: ArtifactStorageClient = {
    from() {
      return {
        async upload() {
          return { error: null };
        },
        async download() {
          return { data: new Blob(["altered"]), error: null };
        },
        async createSignedUrl() {
          return { data: null, error: { message: "not used" } };
        },
      };
    },
  };
  const store = new SupabaseArtifactStore(storage);
  await assert.rejects(
    store.loadVerified(artifact(bytes, { safeToDisplay: false })),
    /not eligible/,
  );
  await assert.rejects(store.loadVerified(artifact(bytes)), /does not match/);
});
