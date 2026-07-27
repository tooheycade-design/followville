import { AuditEventSchema, type AuditEvent, type Task } from "../domain/schemas.js";
import { digest } from "../domain/fingerprints.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import type { ModelProvider } from "../providers/types.js";
import { extractJsonArray } from "./model-planner.js";

/**
 * Why work was sent back.
 *
 * A closed vocabulary rather than free text, because these accumulate into the
 * company's standards. "Looks wrong" teaches nothing on the tenth repetition;
 * `visually_weak` counted ten times is a measurable pattern an owner can act
 * on and a router can eventually learn from.
 */
export type RejectionReason =
  | "missing_evidence"
  | "criteria_unmet"
  | "out_of_scope"
  | "technically_broken"
  | "too_large"
  | "wrong_direction"
  | "visually_weak"
  | "not_followville"
  | "insufficient_detail";

export const REJECTION_REASON_LABELS: Record<RejectionReason, string> = {
  missing_evidence: "No evidence supports the claim",
  criteria_unmet: "An acceptance criterion was not addressed",
  out_of_scope: "Changed more, or other things, than the task asked for",
  technically_broken: "The change does not work",
  too_large: "Too big to review safely; split it",
  wrong_direction: "Solves the wrong problem",
  visually_weak: "Visually poor or generic",
  not_followville: "Does not match Followville's style or world",
  insufficient_detail: "The summary does not explain what was actually done",
};

export interface GateVerdict {
  accepted: boolean;
  reasons: readonly RejectionReason[];
  notes: string;
}

export interface GateInput {
  task: Task;
  workerSummary: string;
  workerEvidence: readonly string[];
  filesChanged: readonly string[];
  /** Reasons this task was previously sent back, oldest first. */
  priorRejections: readonly RejectionReason[];
  /** The change itself. Null when none was captured. */
  diff?: string | null;
  /** True when `diff` is only the beginning of a larger one. */
  diffTruncated?: boolean;
  /** Things an owner could open: screenshots, renders, logs. */
  artifacts?: readonly { kind: string; label: string; retrieval: string }[];
}

/**
 * Checks that hold regardless of judgement.
 *
 * These are cheap, deterministic, and run before any model is consulted, so a
 * task that plainly fails never spends a model call to find that out.
 */
export function mechanicalFindings(input: GateInput): RejectionReason[] {
  const reasons: RejectionReason[] = [];
  const summary = input.workerSummary.trim();

  if (input.workerEvidence.length === 0) {
    reasons.push("missing_evidence");
  }
  if (summary.length < 40) {
    reasons.push("insufficient_detail");
  }
  // A task whose criteria imply a change, that produced none, has not been done.
  const impliesChange = input.task.acceptanceCriteria.some((criterion) =>
    /\b(add|create|change|update|fix|implement|remove|rename)\b/i.test(
      criterion.description,
    ),
  );
  if (impliesChange && input.filesChanged.length === 0) {
    reasons.push("criteria_unmet");
  }
  if (input.filesChanged.length > 40) {
    reasons.push("too_large");
  }
  return reasons;
}

function buildJudgementPrompt(input: GateInput): string {
  const criteria = input.task.acceptanceCriteria
    .map((criterion, index) => `${index + 1}. ${criterion.description}`)
    .join("\n");
  const history =
    input.priorRejections.length > 0
      ? `This task was previously sent back for: ${input.priorRejections.join(", ")}. Check those were addressed.`
      : "This is the first attempt.";

  // The diff is shown when there is one. Judging `missing_evidence` on a file
  // list alone is close to unavoidable: a path proves a file was touched and
  // nothing about whether the contents meet the criteria.
  const change =
    input.diff !== undefined && input.diff !== null && input.diff.length > 0
      ? [
          "",
          input.diffTruncated === true
            ? "Change (first part only; the full diff is larger):"
            : "Change:",
          input.diff,
        ]
      : ["", "Change: no diff was captured."];

  return [
    "You are the Chief Executive of the company that maintains Followville.",
    "You are judging whether finished work is good enough to put in front of",
    "the human owners. Hold a high bar. It is better to send work back than to",
    "waste an owner's attention on something half-done.",
    "",
    `Task: ${input.task.title}`,
    `Objective: ${input.task.objective}`,
    "",
    "Acceptance criteria:",
    criteria,
    "",
    history,
    "",
    "Worker report:",
    input.workerSummary,
    "",
    `Evidence: ${input.workerEvidence.join(" | ") || "none"}`,
    `Files changed: ${input.filesChanged.join(", ") || "none"}`,
    `Artifacts: ${
      (input.artifacts ?? [])
        .map((artifact) => `${artifact.kind} "${artifact.label}"`)
        .join(", ") || "none"
    }`,
    ...change,
    "",
    "Judge the work on the report and the change above. Use missing_evidence",
    "only when the work itself is genuinely unsupported, not when you would",
    "simply have liked more detail.",
    "",
    "Reply with ONLY a JSON array of rejection reasons, no prose. Use an empty",
    "array if the work is good enough for an owner to review.",
    `Valid reasons: ${Object.keys(REJECTION_REASON_LABELS).join(", ")}.`,
  ].join("\n");
}

export interface CeoGateOptions {
  /** Optional. Without it the gate is mechanical only, which still bites. */
  provider?: ModelProvider;
  workingDirectory?: string;
  timeoutMs?: number;
}

/**
 * The CEO's acceptance gate.
 *
 * The reviewer checks that evidence exists; this checks whether the work is
 * actually good. Both must pass before an owner is asked to look, which is the
 * difference between a queue of finished work and a queue of things to triage.
 *
 * A model failure never accepts by default. When the model cannot be reached
 * the mechanical findings stand alone, so an unavailable provider makes the
 * gate stricter rather than opening it.
 */
export class CeoGate {
  readonly name = "ceo-gate";

  constructor(private readonly options: CeoGateOptions = {}) {}

  async judge(input: GateInput): Promise<GateVerdict> {
    const mechanical = mechanicalFindings(input);

    let modelReasons: RejectionReason[] = [];
    let consulted = false;
    if (this.options.provider !== undefined && mechanical.length === 0) {
      const availability = await this.options.provider.checkAvailability();
      if (availability.available) {
        const response = await this.options.provider.invoke({
          workingDirectory: this.options.workingDirectory ?? process.cwd(),
          prompt: buildJudgementPrompt(input),
          timeoutMs: this.options.timeoutMs ?? 3 * 60_000,
          signal: new AbortController().signal,
        });
        if (response.ok) {
          consulted = true;
          const raw = extractJsonArray(response.text);
          modelReasons = (raw ?? []).filter(
            (item): item is RejectionReason =>
              typeof item === "string" && item in REJECTION_REASON_LABELS,
          );
        }
      }
    }

    const reasons = [...new Set([...mechanical, ...modelReasons])];
    return {
      accepted: reasons.length === 0,
      reasons,
      notes:
        reasons.length === 0
          ? consulted
            ? "The CEO reviewed the work and accepted it."
            : "The work passed the CEO's mechanical checks."
          : reasons.map((reason) => REJECTION_REASON_LABELS[reason]).join("; "),
    };
  }
}

export function gateAuditEvent(
  task: Task,
  verdict: GateVerdict,
  idFactory: () => string,
  now: string = new Date().toISOString(),
): AuditEvent {
  return AuditEventSchema.parse({
    id: idFactory(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: task.id,
    runId: null,
    actorType: "agent",
    actorId: SEED_AGENTS.ceo.id,
    action: verdict.accepted ? "ceo.accepted" : "ceo.sent_back",
    targetType: "task",
    targetId: task.id,
    outcome: verdict.accepted ? "succeeded" : "failed",
    // The reason codes are written into the text so a later attempt can read
    // them back; a digest cannot be read.
    reason:
      verdict.reasons.length > 0
        ? `${verdict.notes}\nreasons: ${verdict.reasons.join(", ")}`
        : verdict.notes,
    correlationId: idFactory(),
    idempotencyKey: digest({
      taskId: task.id,
      cycle: task.reviewCycleCount,
      accepted: verdict.accepted,
    }),
    requestDigest: digest({ taskId: task.id, criteria: task.acceptanceCriteria }),
    resultDigest: digest(verdict.reasons),
    evidenceArtifactIds: [],
    createdAt: now,
  });
}

/** Reads prior rejection codes back out of the audit trail. */
export function priorRejectionsFrom(
  events: readonly { action: string; reason: string }[],
): RejectionReason[] {
  const found: RejectionReason[] = [];
  for (const event of events) {
    if (event.action !== "ceo.sent_back") {
      continue;
    }
    const line = event.reason
      .split("\n")
      .find((candidate) => candidate.startsWith("reasons: "));
    if (line === undefined) {
      continue;
    }
    for (const code of line.slice("reasons: ".length).split(", ")) {
      if (code in REJECTION_REASON_LABELS && !found.includes(code as RejectionReason)) {
        found.push(code as RejectionReason);
      }
    }
  }
  return found;
}

/**
 * What a retry is told about its previous failure.
 *
 * A task sent back without its reasons is retried blind, which usually
 * reproduces the same result and burns another run.
 */
export function reworkBriefing(reasons: readonly RejectionReason[]): string {
  if (reasons.length === 0) {
    return "";
  }
  return [
    "",
    "This task was previously sent back by the Chief Executive for:",
    ...reasons.map((reason) => `- ${REJECTION_REASON_LABELS[reason]}`),
    "Address each of these specifically. Do not repeat the previous attempt.",
  ].join("\n");
}
