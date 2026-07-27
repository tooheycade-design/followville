import {
  ApprovalRequestSchema,
  type ApprovalRequest,
  type Capability,
  type EvidenceArtifact,
  type Task,
} from "../domain/schemas.js";
import { digest } from "../domain/fingerprints.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";

/**
 * The packet an owner decides on.
 *
 * Work that passed review and the Chief Executive's gate used to stop at
 * `awaiting_human_approval` with nothing to act on: the approvals page lists
 * approval requests, and the worker flow never made one. Five tasks reached
 * that state and sat there. The task trigger also refuses `approved` without
 * an approved decision, so the status could not be advanced by hand either.
 *
 * So the last step of the loop is to write the request, citing the evidence
 * that already exists rather than restating it.
 */

/** How long an owner has before the packet must be rebuilt from fresh evidence. */
const VALID_FOR_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * The capability the owner is being asked to bless.
 *
 * The most consequential one the task holds, so the request names the real
 * subject rather than whichever happened to be listed first.
 */
const BY_WEIGHT: readonly Capability[] = [
  "production_deploy",
  "production_merge",
  "production_database_write",
  "canonical_world_growth",
  "pull_request_create",
  "git_push_review_branch",
  "git_commit",
  "repository_write",
  "git_checkpoint",
  "repository_read",
];

export function principalCapability(task: Task): Capability {
  return (
    BY_WEIGHT.find((capability) => task.allowedCapabilities.includes(capability)) ??
    task.allowedCapabilities[0] ??
    "repository_read"
  );
}

export interface CompletedWorkInput {
  task: Task;
  /** The worker's full report, as recorded. */
  summary: string;
  evidence: readonly string[];
  filesChanged: readonly string[];
  artifacts: readonly EvidenceArtifact[];
  /** The checkpoint the work is recoverable from, when one was made. */
  commitSha: string | null;
  /** What the Chief Executive said when it accepted. */
  gateNotes: string;
  idFactory: () => string;
  now?: () => string;
}

/**
 * Builds the approval request for finished work.
 *
 * `scopeDigest` covers what the owner is shown. The decision kernel refuses a
 * decision made against a different digest, so work that changes after an
 * owner reads it cannot be approved on the strength of the older reading.
 */
export function completedWorkApproval(
  input: CompletedWorkInput,
): ApprovalRequest {
  const at = (input.now ?? (() => new Date().toISOString()))();
  const { task } = input;

  const scopeDigest = digest({
    taskId: task.id,
    cycle: task.reviewCycleCount,
    summary: input.summary,
    files: [...input.filesChanged].sort(),
    artifacts: [...input.artifacts].map((artifact) => artifact.sha256).sort(),
    commitSha: input.commitSha,
  });

  const where =
    input.commitSha === null
      ? "No checkpoint was recorded; the change exists only as the diff in the audit trail."
      : `Recoverable at ${input.commitSha} on the task's review branch.`;

  return ApprovalRequestSchema.parse({
    id: input.idFactory(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: task.id,
    runId: null,
    requestedByType: "agent",
    requestedById: SEED_AGENTS.ceo.id,
    action: principalCapability(task),
    summary: task.title,
    reason: [
      input.summary,
      "",
      where,
      input.artifacts.length > 0
        ? `Evidence: ${input.artifacts.map((a) => `${a.kind} "${a.label}"`).join(", ")}.`
        : "Evidence: the recorded diff only.",
      `Chief Executive: ${input.gateNotes}`,
    ].join("\n"),
    scopeDigest,
    // Pins the exact checkpoint being accepted. This authorizes no merge.
    commitSha: input.commitSha,
    evidenceArtifactIds: input.artifacts.map((artifact) => artifact.id),
    testsCompleted: [],
    riskLevel: task.riskLevel,
    // Nothing has been merged, pushed, or deployed. Undoing this is deleting
    // a branch nobody depends on.
    reversible: true,
    rollbackPlan:
      "Delete the task's review branch. Nothing was pushed, merged, or deployed.",
    estimatedCostUsdMicros: 0,
    recommendation: "approve",
    alternatives: [],
    requiredApprovals: 1,
    requiredRole: "owner",
    status: "pending",
    // One request per task per review cycle. A worker that recorded the
    // packet and then lost its lease must not produce a second.
    idempotencyKey: digest({
      taskId: task.id,
      cycle: task.reviewCycleCount,
      purpose: "completed-work",
    }),
    createdAt: at,
    expiresAt: new Date(Date.parse(at) + VALID_FOR_MS).toISOString(),
  });
}
