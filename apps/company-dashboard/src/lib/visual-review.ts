import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import type {
  EvidenceArtifact,
  Task,
  VisualEvidenceFile,
  VisualReviewResult,
} from "@followville/company-os-core";

export interface VerifiedVisualArtifactLoader {
  loadVerified(artifact: EvidenceArtifact): Promise<Buffer>;
}

export interface PixelVisualReviewer {
  review(input: {
    task: Task;
    workingDirectory: string;
    evidence: readonly VisualEvidenceFile[];
  }): Promise<VisualReviewResult>;
}

const EXTENSIONS: Readonly<Record<string, string>> = {
  "image/png": ".png",
  "image/jpeg": ".jpg",
};

export function visualReviewArtifacts(
  artifacts: readonly EvidenceArtifact[],
): EvidenceArtifact[] {
  return artifacts
    .filter(
      (artifact) =>
        artifact.location.kind === "object" &&
        artifact.visibility === "owner_only" &&
        artifact.safeToDisplay &&
        !artifact.containsSensitiveData &&
        EXTENSIONS[artifact.mediaType] !== undefined,
    );
}

/**
 * Gives the Design Director verified pixels in an isolated, short-lived folder.
 * Durable object paths and owner-provided labels never become local paths.
 */
export async function runPixelBackedVisualReview(input: {
  task: Task;
  artifacts: readonly EvidenceArtifact[];
  artifactLoader: VerifiedVisualArtifactLoader;
  reviewer: PixelVisualReviewer;
}): Promise<{
  result: VisualReviewResult;
  evidenceArtifactIds: string[];
} | null> {
  const selected = visualReviewArtifacts(input.artifacts);
  if (selected.length === 0) {
    return null;
  }
  if (selected.length > 6) {
    throw new Error(
      `Visual evidence contains ${selected.length} images; the bounded review manifest allows at most 6.`,
    );
  }
  const workingDirectory = await mkdtemp(
    path.join(tmpdir(), "company-os-visual-review-"),
  );
  try {
    const evidence = [];
    for (const [index, artifact] of selected.entries()) {
      const fileName = `evidence-${String(index + 1).padStart(2, "0")}${
        EXTENSIONS[artifact.mediaType]
      }`;
      const bytes = await input.artifactLoader.loadVerified(artifact);
      await writeFile(path.join(workingDirectory, fileName), bytes, {
        flag: "wx",
      });
      evidence.push({
        fileName,
        label: artifact.label,
        mediaType: artifact.mediaType,
        sha256: artifact.sha256,
      });
    }
    return {
      result: await input.reviewer.review({
        task: input.task,
        workingDirectory,
        evidence,
      }),
      evidenceArtifactIds: selected.map((artifact) => artifact.id),
    };
  } finally {
    await rm(workingDirectory, { recursive: true, force: true });
  }
}
