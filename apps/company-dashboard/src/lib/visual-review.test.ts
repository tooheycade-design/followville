import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

import {
  EvidenceArtifactSchema,
  TaskSchema,
  type EvidenceArtifact,
  type Task,
} from "@followville/company-os-core";
import {
  runPixelBackedVisualReview,
  visualReviewArtifacts,
} from "./visual-review";

const bytes = Buffer.from("pixel bytes");
const task = TaskSchema.parse({
  id: "92000000-0000-4000-8000-000000000001",
  organizationId: "10000000-0000-4000-8000-000000000001",
  projectId: "20000000-0000-4000-8000-000000000001",
  goalId: "92000000-0000-4000-8000-000000000002",
  parentTaskId: null,
  title: "Review visuals",
  objective: "Inspect the evidence.",
  reason: "Quality gate.",
  status: "awaiting_review",
  priority: 50,
  riskLevel: "low",
  assignedAgentId: "40000000-0000-4000-8000-000000000003",
  reviewerAgentId: "40000000-0000-4000-8000-000000000002",
  dependencyIds: [],
  acceptanceCriteria: [{ id: "92000000-0000-4000-8000-000000000003", description: "The visual is legible.", verificationMethod: "Inspect it.", required: true }],
  allowedCapabilities: ["repository_read"],
  repositoryScopes: [],
  budgetUsdMicros: 0,
  estimatedCostUsdMicros: 0,
  actualCostUsdMicros: 0,
  retryCount: 0,
  reviewCycleCount: 0,
  branchName: null,
  expectedOutputs: ["Visual evidence"],
  testRequirements: [],
  approvalRequired: true,
  version: 1,
  createdAt: "2026-07-29T12:00:00.000Z",
  updatedAt: "2026-07-29T12:00:00.000Z",
});

function artifact(id: string, overrides: Partial<EvidenceArtifact> = {}) {
  return EvidenceArtifactSchema.parse({
    id,
    organizationId: task.organizationId,
    projectId: task.projectId,
    goalId: task.goalId,
    taskId: task.id,
    runId: "92000000-0000-4000-8000-000000000004",
    kind: "screenshot",
    label: "../../Owner label cannot become a path",
    mediaType: "image/png",
    sizeBytes: bytes.byteLength,
    sha256: createHash("sha256").update(bytes).digest("hex"),
    location: { kind: "object", provider: "supabase_storage", bucket: "company-os-evidence", objectPath: "private/object" },
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

test("only safe object-backed images are selected without silently truncating", () => {
  const candidates = Array.from({ length: 8 }, (_, index) =>
    artifact(`92000000-0000-4000-8000-${String(index + 10).padStart(12, "0")}`),
  );
  candidates.push(artifact("92000000-0000-4000-8000-000000000099", { mediaType: "text/plain" }));
  assert.equal(visualReviewArtifacts(candidates).length, 8);
});

test("verified pixels exist during review and the temporary directory is removed", async () => {
  let directory = "";
  const reviewer = {
    async review(input: { task: Task; workingDirectory: string; evidence: readonly { fileName: string }[] }) {
      directory = input.workingDirectory;
      assert.equal(input.evidence[0]?.fileName, "evidence-01.png");
      assert.deepEqual(await readFile(path.join(directory, "evidence-01.png")), bytes);
      return { accepted: true, findings: [], summary: "Pixels inspected." };
    },
  };
  const result = await runPixelBackedVisualReview({
    task,
    artifacts: [artifact("92000000-0000-4000-8000-000000000010")],
    artifactLoader: { async loadVerified() { return bytes; } },
    reviewer,
  });
  assert.equal(result?.result.accepted, true);
  await assert.rejects(access(directory));
});
