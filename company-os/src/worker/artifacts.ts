import { createHash } from "node:crypto";
import { lstat, readFile, realpath } from "node:fs/promises";
import path from "node:path";

import {
  EvidenceArtifactSchema,
  type ArtifactKind,
  type ArtifactLocation,
  type EvidenceArtifact,
  type Task,
} from "../domain/schemas.js";
import { MAX_DIFF_CHARS, type ReportedArtifact } from "./report.js";
import { ORGANIZATION_ID, PROJECT_ID } from "../config/seed-agents.js";

/**
 * Turns what an agent produced into artifacts an owner can open.
 *
 * The gap this closes: `evidenceArtifactIds` has been on runs, approvals, and
 * audit events since the first migration and has always been empty. An
 * approval packet could describe a screenshot and point at nothing, so any
 * visual evidence an agent made was as good as lost.
 *
 * Small code-adjacent evidence can be recorded by reference into the task's
 * checkpoint. Visual and large evidence can instead be copied into a private
 * object store so both owners can inspect it without cloning a task branch.
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
  { pattern: /\.glb$/i, kind: "model", mediaType: "model/gltf-binary" },
  { pattern: /\.gltf$/i, kind: "model", mediaType: "model/gltf+json" },
  { pattern: /(?:^|\/)(?:trace|.*-trace)\.zip$/i, kind: "trace", mediaType: "application/zip" },
  { pattern: /(?:^|\/)junit\.xml$/i, kind: "report", mediaType: "application/xml" },
  {
    pattern: /(?:^|\/)(?:browser-preview-report|evidence-report)\.json$/i,
    kind: "report",
    mediaType: "application/json",
  },
  {
    pattern: /(?:^|\/)(?:playwright-report|evidence|artifacts)\/.*\.html$/i,
    kind: "report",
    mediaType: "text/html",
  },
];

/** Upper bound for one approval artifact. Larger outputs need chunking. */
export const MAX_ARTIFACT_BYTES = 100 * 1024 * 1024;

export interface ArtifactStoreInput {
  artifactId: string;
  task: Task;
  runId: string;
  absolutePath: string;
  fileName: string;
  mediaType: string;
  sha256: string;
  sizeBytes: number;
}

export interface ArtifactStore {
  store(input: ArtifactStoreInput): Promise<ArtifactLocation>;
}

function classify(
  file: string,
): { kind: ArtifactKind; mediaType: string } | null {
  const normalized = file.replaceAll("\\", "/");
  return RECOGNIZED.find((entry) => entry.pattern.test(normalized)) ?? null;
}

function isInside(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);
  return (
    relative.length === 0 ||
    (!relative.startsWith("..") && !path.isAbsolute(relative))
  );
}

function hasExpectedSignature(mediaType: string, bytes: Buffer): boolean {
  if (mediaType === "image/png") {
    return bytes.subarray(0, 8).equals(
      Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    );
  }
  if (mediaType === "image/jpeg") {
    return bytes[0] === 0xff && bytes[1] === 0xd8;
  }
  if (mediaType === "image/gif") {
    return bytes.subarray(0, 3).toString("ascii") === "GIF";
  }
  if (mediaType === "image/webp") {
    return (
      bytes.subarray(0, 4).toString("ascii") === "RIFF" &&
      bytes.subarray(8, 12).toString("ascii") === "WEBP"
    );
  }
  if (mediaType === "video/mp4") {
    return bytes.subarray(4, 8).toString("ascii") === "ftyp";
  }
  if (mediaType === "model/gltf-binary") {
    return bytes.subarray(0, 4).toString("ascii") === "glTF";
  }
  if (mediaType === "application/zip") {
    return bytes[0] === 0x50 && bytes[1] === 0x4b;
  }
  return true;
}

export interface CollectArtifactsInput {
  task: Task;
  /** Where the files still exist, before the worktree is removed. */
  worktreePath: string;
  filesChanged: readonly string[];
  /**
   * Runtime-created evidence that was not part of the checkpoint. These files
   * may only be preserved in the shared object store.
   */
  evidenceFiles?: readonly string[];
  /** The checkpoint the files were recorded in, if one was made. */
  commitSha: string | null;
  diff: string | null;
  runId?: string | null;
  artifactStore?: ArtifactStore;
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
    goalId: input.task.goalId,
    taskId: input.task.id,
    runId: input.runId ?? null,
    visibility: "owner_only" as const,
    containsSensitiveData: false,
    safeToDisplay: false,
    retentionPolicy: "approval_record" as const,
    createdByAgentId: input.createdByAgentId,
    createdAt: at,
    // Evidence outlives the decision it supports; an approval whose evidence
    // expired cannot be audited afterwards.
    expiresAt: null,
  };

  // The change itself, always. It is the one artifact that exists for every
  // run that touched anything.
  if (input.diff !== null && input.diff.length > 0) {
    const patch = input.diff.slice(0, MAX_DIFF_CHARS);
    artifacts.push(
      EvidenceArtifactSchema.parse({
        ...base,
        id: input.idFactory(),
        kind: "patch",
        label:
          patch.length < input.diff.length
            ? `Diff preview of ${input.filesChanged.length} file(s)`
            : `Diff of ${input.filesChanged.length} file(s)`,
        mediaType: "text/x-diff",
        sizeBytes: Buffer.byteLength(patch, "utf8"),
        sha256: createHash("sha256").update(patch).digest("hex"),
        location: { kind: "inline", text: patch },
        containsSensitiveData: true,
      }),
    );
  }

  const checkpointFiles =
    input.commitSha === null ? [] : input.filesChanged.map((file) => ({ file, runtime: false }));
  const runtimeFiles = (input.evidenceFiles ?? []).map((file) => ({
    file,
    runtime: true,
  }));
  const seen = new Set<string>();

  for (const { file, runtime } of [...checkpointFiles, ...runtimeFiles]) {
    const normalizedFile = file.replaceAll("\\", "/");
    if (seen.has(normalizedFile)) {
      continue;
    }
    seen.add(normalizedFile);
    const recognized = classify(file);
    if (recognized === null) {
      continue;
    }
    try {
      if (
        runtime &&
        (input.artifactStore === undefined || !input.runId)
      ) {
        throw new Error(
          `Runtime evidence requires shared object storage and a run ID: ${file}`,
        );
      }
      const worktreeRoot = path.resolve(input.worktreePath);
      const absolute = path.resolve(worktreeRoot, file);
      if (!isInside(worktreeRoot, absolute)) {
        throw new Error(`Artifact path escapes the worktree: ${file}`);
      }
      const info = await lstat(absolute);
      if (info.isSymbolicLink()) {
        throw new Error(`Artifact is a symbolic link: ${file}`);
      }
      const resolved = await realpath(absolute);
      if (!isInside(worktreeRoot, resolved)) {
        throw new Error(`Artifact resolves outside the worktree: ${file}`);
      }
      if (!info.isFile() || info.size > MAX_ARTIFACT_BYTES) {
        continue;
      }
      const bytes = await readFile(absolute);
      if (!hasExpectedSignature(recognized.mediaType, bytes)) {
        throw new Error(
          `Artifact content does not match ${recognized.mediaType}: ${file}`,
        );
      }
      const sha256 = createHash("sha256").update(bytes).digest("hex");
      const artifactId = input.idFactory();
      const location =
        input.artifactStore !== undefined && input.runId
          ? await input.artifactStore.store({
              artifactId,
              task: input.task,
              runId: input.runId,
              absolutePath: absolute,
              fileName: path.posix.basename(file.replaceAll("\\", "/")),
              mediaType: recognized.mediaType,
              sha256,
              sizeBytes: info.size,
            })
          : {
              kind: "git" as const,
              commitSha: input.commitSha!,
              repositoryPath: file,
            };
      artifacts.push(
        EvidenceArtifactSchema.parse({
          ...base,
          id: artifactId,
          kind: recognized.kind,
          label: path.posix.basename(file.replaceAll("\\", "/")),
          mediaType: recognized.mediaType,
          sizeBytes: info.size,
          sha256,
          location,
          containsSensitiveData: ["log", "report", "trace"].includes(
            recognized.kind,
          ),
          safeToDisplay:
            ["screenshot", "recording", "render"].includes(recognized.kind) &&
            recognized.mediaType !== "image/svg+xml",
        }),
      );
    } catch (error) {
      if (runtime || input.artifactStore !== undefined) {
        throw error;
      }
      // Unreadable or vanished. Skip it rather than fail the task.
      continue;
    }
  }

  return artifacts;
}

/** How to retrieve an artifact, for a human reading an approval packet. */
export function retrievalHint(artifact: EvidenceArtifact): string {
  if (artifact.location.kind === "git") {
    return `git show ${artifact.location.commitSha}:${artifact.location.repositoryPath}`;
  }
  return artifact.location.kind === "object"
    ? `private ${artifact.location.provider} object`
    : "held inline with the record";
}

/** Flattens an artifact for the audit trail. */
export function reportedArtifact(artifact: EvidenceArtifact): ReportedArtifact {
  return {
    id: artifact.id,
    goalId: artifact.goalId,
    runId: artifact.runId,
    kind: artifact.kind,
    label: artifact.label,
    mediaType: artifact.mediaType,
    sizeBytes: artifact.sizeBytes,
    sha256: artifact.sha256,
    commitSha:
      artifact.location.kind === "git" ? artifact.location.commitSha : null,
    repositoryPath:
      artifact.location.kind === "git" ? artifact.location.repositoryPath : null,
    inlineText:
      artifact.location.kind === "inline" ? artifact.location.text : null,
    storageProvider:
      artifact.location.kind === "object" ? artifact.location.provider : null,
    storageBucket:
      artifact.location.kind === "object" ? artifact.location.bucket : null,
    storageObjectPath:
      artifact.location.kind === "object" ? artifact.location.objectPath : null,
    visibility: artifact.visibility,
    containsSensitiveData: artifact.containsSensitiveData,
    safeToDisplay: artifact.safeToDisplay,
    retentionPolicy: artifact.retentionPolicy,
  };
}

/**
 * Rebuilds an artifact row from what the audit trail kept.
 *
 * The approval packet is assembled in the review pass, after the executor's
 * objects are gone, so this is how evidence recorded during a run reaches the
 * owner who decides on it.
 */
export function artifactFromReport(
  reported: ReportedArtifact,
  task: Task,
  createdByAgentId: string,
  createdAt: string,
  runId: string | null = null,
): EvidenceArtifact {
  return EvidenceArtifactSchema.parse({
    id: reported.id,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: reported.goalId ?? task.goalId,
    taskId: task.id,
    runId: reported.runId ?? runId,
    kind: reported.kind,
    label: reported.label,
    mediaType: reported.mediaType,
    sizeBytes: reported.sizeBytes,
    sha256: reported.sha256,
    location:
      reported.storageProvider === "supabase_storage" &&
      reported.storageBucket !== null &&
      reported.storageObjectPath !== null
        ? {
            kind: "object",
            provider: reported.storageProvider,
            bucket: reported.storageBucket,
            objectPath: reported.storageObjectPath,
          }
        : reported.commitSha !== null && reported.repositoryPath !== null
          ? {
              kind: "git",
              commitSha: reported.commitSha,
              repositoryPath: reported.repositoryPath,
            }
          : { kind: "inline", text: reported.inlineText ?? "" },
    visibility: reported.visibility ?? "owner_only",
    containsSensitiveData: reported.containsSensitiveData ?? false,
    safeToDisplay: reported.safeToDisplay ?? true,
    retentionPolicy: reported.retentionPolicy ?? "approval_record",
    createdByAgentId,
    createdAt,
    expiresAt: null,
  });
}
