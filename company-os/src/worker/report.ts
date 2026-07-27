/**
 * The worker's report, as it survives the audit trail.
 *
 * Evidence reaches the reviewer and the Chief Executive as text read back out
 * of `audit_events.reason`, because a digest proves nothing was altered but
 * cannot be read. That makes this encoding load-bearing: whatever does not
 * survive the round trip is something a judge decides without, silently.
 *
 * The first version appended `evidence: a | b` to the summary and recovered the
 * summary with `split("\n")[0]`. Codex writes multi-line reports — what it did,
 * how it checked, and the diff it produced — so every line but the first was
 * dropped between the worker and the gate. The Chief Executive then rejected
 * sound work for `missing_evidence`, which was the correct reading of what it
 * had been shown and the wrong reading of what had happened.
 *
 * So the format is explicit rather than incidental: a sentinel line that cannot
 * collide with the prose around it, named sections after it, and a decoder that
 * still understands rows written by the old format.
 */

/**
 * Separates the report body from its structured trailer.
 *
 * Both the summary and the diff are untrusted text that can contain anything,
 * including this line. `encodeWorkerReport` neutralizes any occurrence in them,
 * so the sentinel appears exactly once and the split is never ambiguous.
 */
export const EVIDENCE_SENTINEL = "--- company-os:evidence ---";

/**
 * How much diff is carried. Large enough to judge an ordinary change on, small
 * enough that it cannot crowd out the rest of a judgement prompt. A diff over
 * this is cut and labelled with its true size, because a judge told it is
 * seeing a fragment can ask for a smaller change, whereas one silently handed
 * a fragment just judges it as though it were the whole.
 */
export const MAX_DIFF_CHARS = 12_000;

/** Bounds an unusually wide change so one task cannot write an enormous row. */
export const MAX_LISTED_FILES = 200;

/** An artifact as it survives the audit trail: enough to find and open it. */
export interface ReportedArtifact {
  kind: string;
  label: string;
  mediaType: string;
  sizeBytes: number;
  /** `git show <commit>:<path>`, or "inline". */
  retrieval: string;
}

export interface WorkerReport {
  /** Everything the worker said, not just its opening line. */
  summary: string;
  evidence: readonly string[];
  filesChanged: readonly string[];
  artifacts: readonly ReportedArtifact[];
  /** The change itself, or null when none was captured. */
  diff: string | null;
  /** True when `diff` is a prefix of a larger one. */
  diffTruncated: boolean;
  /** File count before `MAX_LISTED_FILES` was applied. */
  totalFilesChanged: number;
}

export interface WorkerReportInput {
  summary: string;
  evidence: readonly string[];
  filesChanged: readonly string[];
  diff?: string | null;
  artifacts?: readonly ReportedArtifact[];
}

/** One artifact line. Tab-separated so a label may contain spaces. */
function encodeArtifact(artifact: ReportedArtifact): string {
  return [
    "artifact:",
    artifact.kind,
    artifact.mediaType,
    String(artifact.sizeBytes),
    artifact.retrieval,
    artifact.label,
  ].join("\t");
}

function decodeArtifact(line: string): ReportedArtifact | null {
  const [, kind, mediaType, size, retrieval, ...label] = line.split("\t");
  if (kind === undefined || mediaType === undefined || retrieval === undefined) {
    return null;
  }
  return {
    kind,
    mediaType,
    sizeBytes: Number.parseInt(size ?? "0", 10) || 0,
    retrieval,
    label: label.join("\t"),
  };
}

/** Prevents untrusted text from forging the sentinel. */
function neutralize(text: string): string {
  return text
    .split("\n")
    .map((line) => (line.trimEnd() === EVIDENCE_SENTINEL ? ` ${line}` : line))
    .join("\n");
}

/** Renders a worker's result as the text stored in the audit reason. */
export function encodeWorkerReport(input: WorkerReportInput): string {
  const files = input.filesChanged.slice(0, MAX_LISTED_FILES);
  const lines = [neutralize(input.summary), EVIDENCE_SENTINEL];

  if (input.evidence.length > 0) {
    lines.push(`evidence: ${input.evidence.join(" | ")}`);
  }
  lines.push(`files: ${input.filesChanged.length}`);
  if (files.length > 0) {
    lines.push(`changed: ${files.join(", ")}`);
  }
  for (const artifact of input.artifacts ?? []) {
    lines.push(encodeArtifact(artifact));
  }

  const diff = input.diff ?? "";
  if (diff.length > 0) {
    const kept = diff.slice(0, MAX_DIFF_CHARS);
    lines.push(`diff: ${kept.length} of ${diff.length} chars`);
    lines.push(neutralize(kept));
  }

  return lines.join("\n");
}

/**
 * Reads a report written before the sentinel existed.
 *
 * The trailer was the last line, so anything before it is summary. Taking the
 * last match matters: Codex prose regularly contains its own "Evidence:" line,
 * and a lowercase one would otherwise be mistaken for the trailer and swallow
 * the real evidence.
 */
function decodeLegacy(reason: string): WorkerReport {
  const lines = reason.split("\n");
  let trailerIndex = -1;
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    if (lines[index]!.startsWith("evidence: ")) {
      trailerIndex = index;
      break;
    }
  }
  if (trailerIndex === -1) {
    return {
      summary: reason,
      evidence: [],
      filesChanged: [],
      artifacts: [],
      diff: null,
      diffTruncated: false,
      totalFilesChanged: 0,
    };
  }

  const evidence = lines[trailerIndex]!
    .slice("evidence: ".length)
    .split(" | ")
    .filter((item) => item.length > 0);
  const changed = evidence.find((item) => item.startsWith("changed: "));
  const filesChanged =
    changed === undefined
      ? []
      : changed
          .slice("changed: ".length)
          .split(", ")
          .filter((file) => file.length > 0);

  return {
    summary: lines.slice(0, trailerIndex).join("\n").trimEnd(),
    evidence,
    filesChanged,
    // Rows written before artifacts existed have none, which is different from
    // having produced none — but nothing was recorded either way.
    artifacts: [],
    diff: null,
    diffTruncated: false,
    totalFilesChanged: filesChanged.length,
  };
}

/** Recovers a worker's result from the audit reason it was stored in. */
export function decodeWorkerReport(reason: string): WorkerReport {
  const lines = reason.split("\n");
  const sentinel = lines.indexOf(EVIDENCE_SENTINEL);
  if (sentinel === -1) {
    return decodeLegacy(reason);
  }

  const summary = lines.slice(0, sentinel).join("\n").trimEnd();
  const trailer = lines.slice(sentinel + 1);

  let evidence: readonly string[] = [];
  let filesChanged: readonly string[] = [];
  let totalFilesChanged = 0;
  let diff: string | null = null;
  let diffTruncated = false;
  const artifacts: ReportedArtifact[] = [];

  for (let index = 0; index < trailer.length; index += 1) {
    const line = trailer[index]!;
    if (line.startsWith("artifact:\t")) {
      const artifact = decodeArtifact(line);
      if (artifact !== null) {
        artifacts.push(artifact);
      }
      continue;
    }
    if (line.startsWith("evidence: ")) {
      evidence = line
        .slice("evidence: ".length)
        .split(" | ")
        .filter((item) => item.length > 0);
      continue;
    }
    if (line.startsWith("files: ")) {
      totalFilesChanged = Number.parseInt(line.slice("files: ".length), 10) || 0;
      continue;
    }
    if (line.startsWith("changed: ")) {
      filesChanged = line
        .slice("changed: ".length)
        .split(", ")
        .filter((file) => file.length > 0);
      continue;
    }
    const measured = /^diff: (\d+) of (\d+) chars$/.exec(line);
    if (measured !== null) {
      diffTruncated = Number(measured[1]) < Number(measured[2]);
      // Everything after the header is diff, including blank lines.
      diff = trailer.slice(index + 1).join("\n");
      break;
    }
  }

  return {
    summary,
    evidence,
    filesChanged,
    artifacts,
    diff,
    diffTruncated,
    totalFilesChanged: Math.max(totalFilesChanged, filesChanged.length),
  };
}
