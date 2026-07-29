import { AuditEventSchema, type AuditEvent, type Task } from "../domain/schemas.js";
import { digest } from "../domain/fingerprints.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import { decodeWorkerReport } from "./report.js";

export type ReviewVerdict = "approved_for_owner" | "changes_requested";

export interface ReviewFinding {
  criterion: string;
  met: boolean;
  note: string;
}

export interface ReviewResult {
  verdict: ReviewVerdict;
  summary: string;
  findings: readonly ReviewFinding[];
}

export interface ReviewInput {
  task: Task;
  /** Evidence the worker recorded, read from the audit trail. */
  workerEvidence: readonly string[];
  workerSummary: string;
  filesChanged: readonly string[];
  /** Present in production; optional only for callers reading historical rows. */
  runId?: string | null;
  testsCompleted?: readonly string[];
  testsFailed?: readonly string[];
}

export interface Reviewer {
  readonly name: string;
  review(input: ReviewInput): Promise<ReviewResult>;
}

/** Gives a revision the recorded reviewer reason and failed runtime checks. */
export function reviewReworkBriefing(
  events: readonly { action: string; reason: string }[],
): string {
  const review = [...events]
    .reverse()
    .find(
      (event) =>
        event.action === "review.changes_requested" ||
        event.action === "visual_review.changes_requested",
    );
  const completion = [...events]
    .reverse()
    .find((event) => event.action === "worker.completed");
  const report =
    completion === undefined ? null : decodeWorkerReport(completion.reason);
  const diagnostics =
    report?.evidence.filter(
      (line) =>
        /^check=.* failed /.test(line) ||
        line.startsWith("check_output=") ||
        line.startsWith("unverified="),
    ) ?? [];
  if (review === undefined && diagnostics.length === 0) {
    return "";
  }
  return [
    "",
    "This task was previously sent back by the independent reviewer.",
    ...(review === undefined ? [] : [`Reviewer: ${review.reason.slice(0, 1_500)}`]),
    ...(diagnostics.length === 0
      ? []
      : ["Runtime verification diagnostics:", ...diagnostics.map((line) => `- ${line}`)]),
    "Fix the recorded failure before presenting the revision again.",
  ].join("\n");
}

/**
 * A reviewer that checks the claim against the recorded evidence.
 *
 * It deliberately does not ask the worker whether it succeeded. The worker's
 * summary is treated as a claim, and the review is over what was actually
 * recorded: that evidence exists, that a task claiming code changes produced
 * some, and that a task claiming none did not quietly change files anyway.
 *
 * This is a floor, not a substitute for judgement. It catches the failure mode
 * that matters most in an autonomous loop, which is work that reports success
 * without anything to show for it.
 */
export class EvidenceReviewer implements Reviewer {
  readonly name = "evidence-reviewer";

  async review(input: ReviewInput): Promise<ReviewResult> {
    const findings: ReviewFinding[] = [];

    findings.push({
      criterion: "Evidence was recorded",
      met: input.workerEvidence.length > 0,
      note:
        input.workerEvidence.length > 0
          ? `${input.workerEvidence.length} evidence line(s).`
          : "The worker recorded no evidence.",
    });

    if (input.runId !== undefined) {
      findings.push({
        criterion: "The worker attempt has a durable run record",
        met: input.runId !== null,
        note:
          input.runId === null
            ? "The completion is not linked to a run ledger entry."
            : `Run ${input.runId} recorded.`,
      });
    }

    if (input.testsCompleted !== undefined && input.task.testRequirements.length > 0) {
      findings.push({
        criterion: "Required checks were executed by the runtime",
        met: input.testsCompleted.length > 0,
        note:
          input.testsCompleted.length > 0
            ? `${input.testsCompleted.length} runtime-verified check(s) recorded.`
            : "The task requires checks, but the runtime recorded none.",
      });
    }

    if (input.testsFailed !== undefined) {
      findings.push({
        criterion: "Every runtime-owned check passed",
        met: input.testsFailed.length === 0,
        note:
          input.testsFailed.length === 0
            ? "No failed runtime checks."
            : `Failed checks: ${input.testsFailed.join(", ")}.`,
      });
    }

    const summary = input.workerSummary.trim();
    findings.push({
      criterion: "A substantive summary was written",
      met: summary.length >= 20,
      note:
        summary.length >= 20
          ? "Summary present."
          : "The summary is missing or too short to review.",
    });

    const claimsChange = /\b(added|changed|updated|fixed|created|removed|edited)\b/i.test(
      summary,
    );
    findings.push({
      criterion: "Claimed changes match the recorded diff",
      met: !claimsChange || input.filesChanged.length > 0,
      note: claimsChange
        ? input.filesChanged.length > 0
          ? `${input.filesChanged.length} file(s) changed, consistent with the summary.`
          : "The summary claims changes but no files were modified."
        : "No file changes were claimed.",
    });

    for (const criterion of input.task.acceptanceCriteria) {
      findings.push({
        criterion: criterion.description,
        met: input.workerEvidence.length > 0,
        note:
          input.workerEvidence.length > 0
            ? "Evidence is available for an owner to check against this criterion."
            : "No evidence supports this criterion.",
      });
    }

    const failed = findings.filter((finding) => !finding.met);
    return {
      verdict: failed.length === 0 ? "approved_for_owner" : "changes_requested",
      summary:
        failed.length === 0
          ? `All ${findings.length} checks passed; ready for an owner decision.`
          : `${failed.length} of ${findings.length} checks failed: ${failed
              .map((finding) => finding.note)
              .join(" ")}`,
      findings,
    };
  }
}

export function reviewAuditEvent(
  task: Task,
  result: ReviewResult,
  reviewerAgentId: string,
  idFactory: () => string,
  now: string = new Date().toISOString(),
  runId: string | null = null,
): AuditEvent {
  return AuditEventSchema.parse({
    id: idFactory(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: task.id,
    runId,
    actorType: "agent",
    actorId: reviewerAgentId,
    action: `review.${result.verdict}`,
    targetType: "task",
    targetId: task.id,
    outcome: result.verdict === "approved_for_owner" ? "succeeded" : "failed",
    reason: result.summary,
    correlationId: idFactory(),
    idempotencyKey: digest({
      taskId: task.id,
      verdict: result.verdict,
      cycle: task.reviewCycleCount,
    }),
    requestDigest: digest({ taskId: task.id, criteria: task.acceptanceCriteria }),
    resultDigest: digest(result.findings),
    evidenceArtifactIds: [],
    createdAt: now,
  });
}

/** The reviewer must never be the agent that did the work. */
export function assertIndependentReviewer(task: Task): void {
  const reviewerId = task.reviewerAgentId ?? SEED_AGENTS.reviewer.id;
  if (reviewerId === task.assignedAgentId) {
    throw new Error(
      "The reviewer and the assigned worker are the same agent; review would not be independent.",
    );
  }
}
