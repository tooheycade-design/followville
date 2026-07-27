import { createHash } from "node:crypto";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";

import {
  EvidenceArtifactSchema,
  type ArtifactKind,
  type EvidenceArtifact,
  type Task,
} from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID } from "../config/seed-agents.js";

/**
 * Turns what an agent produced into artifacts an owner can open.
 *
 * The gap this closes: `evidenceArtifactIds` has been on runs, approvals, and
 * audit events since the first migration and has always been empty. An
 * approval packet could describe a screenshot and point at nothing, so any
 * visual evidence an agent made was as good as lost.
 *
 * Files are recorded by reference into the task's checkpoint commit rather
 * than copied somewhere else. The bytes are already durable there, and a
 * second copy is a second thing to keep consistent.
 */

/** Extensions worth showing a human, and what they are. */
const RECOGNIZED: readonly { pattern: RegExp; kind: ArtifactKind; mediaType: string }[] = [
  { pattern: /\.png$/i, kind: "screenshot", mediaType: "image/png" },
  { pattern: /\.jpe?g$/i, kind: "screenshot", mediaType: "image/jpeg" },
  { pattern: /\.webp$/i, kind: "screenshot", mediaType: "image/webp" },
  { pattern: /\.gif$/i, kind: "recording", mediaType: "image/gif" },
  { pattern: /\.svg$/i, kind: "render", mediaType: "image/svg+xml" },
  { pattern: /\.mp4$/i, kind: "recording", mediaType: "video/mp4" },
  { pattern: /\.webm$/i, kind: "recording", mediaType: "video/webm" },
  { pattern: /\.log$/i, kind: "log", mediaType: "text/plain" },
];

/** Bytes above which a file is recorded but not read into memory to hash. */
const MAX_HASH_BYTES = 64 * 1024 * 1024;

function classify(
  file: string,
): { kind: ArtifactKind; mediaType: string } | null {
  return RECOGNIZED.find((entry) => entry.pattern.test(file)) ?? null;
}

export interface CollectArtifactsInput {
  task: Task;
  /** Where the files still exist, before the worktree is removed. */
  worktreePath: string;
  filesChanged: readonly string[];
  /** The checkpoint the files were recorded in, if one was made. */
  commitSha: string | null;
  diff: string | null;
  createdByAgentId: string;
  idFactory: () => string;
  now?: () => string;
}

/**
 * Collects artifacts from a finished run.
 *
 * Called while the worktree still exists, because afterwards the files are
 * only reachable through the commit. A file that cannot be read is skipped
 * rather than failing the task: evidence collection must not be able to turn
 * finished work into a failure.
 */
export async function collectArtifacts(
  input: CollectArtifactsInput,
): Promise<EvidenceArtifact[]> {
  const at = (input.now ?? (() => new Date().toISOString()))();
  const artifacts: EvidenceArtifact[] = [];

  const base = {
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: input.task.id,
    runId: null,
    createdByAgentId: input.createdByAgentId,
    createdAt: at,
    // Evidence outlives the decision it supports; an approval whose evidence
    // expired cannot be audited afterwards.
    expiresAt: null,
  };

  // The change itself, always. It is the one artifact that exists for every
  // run that touched anything.
  if (input.diff !== null && input.diff.length > 0) {
    artifacts.push(
      EvidenceArtifactSchema.parse({
        ...base,
        id: input.idFactory(),
        kind: "patch",
        label: `Diff of ${input.filesChanged.length} file(s)`,
        mediaType: "text/x-diff",
        sizeBytes: Buffer.byteLength(input.diff, "utf8"),
        sha256: createHash("sha256").update(input.diff).digest("hex"),
        location: { kind: "inline", text: input.diff },
      }),
    );
  }

  if (input.commitSha === null) {
    // Without a checkpoint there is nowhere durable to point, and recording a
    // path into a worktree about to be deleted would be a broken reference.
    return artifacts;
  }

  for (const file of input.filesChanged) {
    const recognized = classify(file);
    if (recognized === null) {
      continue;
    }
    try {
      const absolute = path.join(input.worktreePath, file);
      const info = await stat(absolute);
      if (!info.isFile() || info.size > MAX_HASH_BYTES) {
        continue;
      }
      const bytes = await readFile(absolute);
      artifacts.push(
        EvidenceArtifactSchema.parse({
          ...base,
          id: input.idFactory(),
          kind: recognized.kind,
          label: path.posix.basename(file.replaceAll("\\", "/")),
          mediaType: recognized.mediaType,
          sizeBytes: info.size,
          sha256: createHash("sha256").update(bytes).digest("hex"),
          location: {
            kind: "git",
            commitSha: input.commitSha,
            repositoryPath: file,
          },
        }),
      );
    } catch {
      // Unreadable or vanished. Skip it rather than fail the task.
      continue;
    }
  }

  return artifacts;
}

/** How to retrieve an artifact, for a human reading an approval packet. */
export function retrievalHint(artifact: EvidenceArtifact): string {
  return artifact.location.kind === "git"
    ? `git show ${artifact.location.commitSha}:${artifact.location.repositoryPath}`
    : "held inline with the record";
}
