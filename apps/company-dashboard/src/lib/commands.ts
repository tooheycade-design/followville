import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";

import {
  ApprovalDecisionSchema,
  AuditEventSchema,
  CodexProvider,
  HeuristicPlanner,
  ModelPlanner,
  ORGANIZATION_ID,
  PROJECT_ID,
  TaskSchema,
  applyApprovalDecision,
  planInitiative,
  assertTaskTransition,
  digest,
  simulateGoal,
  type ApprovalRequest,
  type AuditEvent,
  type OwnerRegistry,
  type Task,
} from "@followville/company-os-core";

import { OWNER_REGISTRY, ownerName } from "./config";
import { companyRepository, type CompanyRepository } from "./state";

export interface SubmitGoalInput {
  title: string;
  objective: string;
  createdByUserId: string;
}

export interface SubmitGoalResult {
  ok: boolean;
  message: string;
  goalId?: string;
}

/**
 * What the CEO needs to know to plan about Followville rather than in the
 * abstract. Kept short deliberately: a planner given the whole project history
 * spends its attention reading instead of deciding.
 */
const FOLLOWVILLE_CONTEXT = [
  "Followville is a persistent low-poly town. Every Instagram follower gets a house.",
  "The canonical world lives in world_state.json and neighborhood.blend, both of",
  "which are owner-controlled and must never be modified by an agent.",
  "The website (index.html, town.html) is a Three.js walkable town backed by",
  "exported GLB geometry. Supabase holds accounts, house claims, and multiplayer.",
  "You may only plan work inside the company-os directory for now.",
].join("\n");

function repositoryRoot(): string {
  let directory = process.cwd();
  for (let depth = 0; depth < 6; depth += 1) {
    if (existsSync(path.join(directory, "company-os", "README.md"))) {
      return directory;
    }
    directory = path.dirname(directory);
  }
  throw new Error(
    "Could not locate the repository root containing company-os/.",
  );
}

export async function submitGoal(
  input: SubmitGoalInput,
  repository: CompanyRepository = companyRepository(),
): Promise<SubmitGoalResult> {
  const title = input.title.trim();
  const objective = input.objective.trim();
  if (title.length === 0 || title.length > 180) {
    return { ok: false, message: "A goal needs a title of 1-180 characters." };
  }
  if (objective.length === 0) {
    return { ok: false, message: "A goal needs an objective." };
  }

  const result = simulateGoal({
    title,
    objective,
    now: new Date().toISOString(),
    idFactory: randomUUID,
    repositoryRoot: repositoryRoot(),
    createdByUserId: input.createdByUserId,
  });

  await repository.appendGoalSimulation({
    goal: result.goal,
    task: result.task,
    run: result.run,
    approvalRequest: result.approvalRequest,
    auditEvents: result.auditEvents,
  });

  return {
    ok: true,
    message: `Simulated "${title}" through to a pending human approval.`,
    goalId: result.goal.id,
  };
}

export interface DirectCeoInput {
  title: string;
  detail: string;
  createdByUserId: string;
}

export interface DirectCeoResult {
  ok: boolean;
  message: string;
  escalations: readonly string[];
  clamped: readonly string[];
}

/**
 * Hands owner intent to the CEO, which turns it into queued work.
 *
 * The CEO decides what should happen; it cannot widen what any agent is
 * permitted to do. Capabilities it asked for and did not get are returned so
 * an attempt to exceed its authority is visible rather than silent.
 */
export async function directCeo(
  input: DirectCeoInput,
  repository: CompanyRepository = companyRepository(),
): Promise<DirectCeoResult> {
  const title = input.title.trim();
  const detail = input.detail.trim();
  if (title.length === 0 || title.length > 180) {
    return {
      ok: false,
      message: "Give the CEO a short title of 1-180 characters.",
      escalations: [],
      clamped: [],
    };
  }
  if (detail.length === 0) {
    return {
      ok: false,
      message: "Tell the CEO what you actually want.",
      escalations: [],
      clamped: [],
    };
  }

  // The CEO reasons with a real model when one is signed in, and falls back to
  // the heuristic planner otherwise. An owner who states a goal always gets a
  // plan; the model changes its quality, never its permissions.
  const heuristic = new HeuristicPlanner();
  const provider = CodexProvider.defaultExecutablePath();
  const planner =
    provider === null
      ? heuristic
      : new ModelPlanner({
          provider: new CodexProvider(provider, "read-only"),
          workingDirectory: repositoryRoot(),
          timeoutMs: 5 * 60_000,
          context: FOLLOWVILLE_CONTEXT,
          fallback: heuristic,
        });

  const initiative = await planInitiative({
    intent: { title, detail, createdByUserId: input.createdByUserId },
    planner,
    idFactory: randomUUID,
  });

  await repository.appendInitiative(initiative.goal, initiative.tasks);

  const queued = initiative.tasks.filter((task) => task.status === "queued").length;
  const held = initiative.tasks.length - queued;
  const message =
    held > 0
      ? `The CEO planned ${initiative.tasks.length} task(s) and held ${held} for your decision.`
      : `The CEO queued ${queued} task(s) for the workers.`;

  return {
    ok: true,
    message,
    escalations: initiative.escalations,
    clamped: initiative.clampedCapabilities.map(
      (entry) => `${entry.task}: removed ${entry.removed.join(", ")}`,
    ),
  };
}

export interface DecideHeldTaskInput {
  taskId: string;
  decision: "release" | "reject";
  comment: string;
  deciderUserId: string;
  /** Capabilities the owner is authorizing. May narrow, never widen. */
  grantedCapabilities: readonly string[];
  /** The task version the owner was shown. */
  expectedVersion: number;
}

export interface DecideHeldTaskResult {
  ok: boolean;
  message: string;
}

/**
 * Releases work the Chief Executive held for an owner, or rejects it.
 *
 * The CEO can recognize risky intent and park it, but until this existed
 * nothing could act on the result, so the company could stop unsafe work and
 * never resume it once a human agreed.
 *
 * The authorization is deliberately narrow. It names the task, the exact
 * capabilities granted, and the version the owner was reading, and the
 * database re-checks every one of those independently. An owner may hand back
 * less than was asked for; nothing can hand back more.
 */
export async function decideHeldTask(
  input: DecideHeldTaskInput,
  repository: CompanyRepository = companyRepository(),
  owners: OwnerRegistry = OWNER_REGISTRY,
): Promise<DecideHeldTaskResult> {
  const comment = input.comment.trim();
  if (comment.length === 0) {
    return { ok: false, message: "A decision needs a written comment." };
  }
  if (!owners.ownerUserIds.includes(input.deciderUserId)) {
    return { ok: false, message: "Only a registered owner can release held work." };
  }

  const state = await repository.load();
  const task = state.tasks.find((candidate) => candidate.id === input.taskId);
  if (task === undefined) {
    return { ok: false, message: "That task does not exist." };
  }
  if (task.status !== "proposed") {
    return {
      ok: false,
      message: `That task is ${task.status.replaceAll("_", " ")}, not held.`,
    };
  }
  // Compared against the version the owner was shown, not the one just read
  // back. Using the fresh value would make this check always pass and quietly
  // apply a decision to a task nobody reviewed.
  if (task.version !== input.expectedVersion) {
    return {
      ok: false,
      message:
        "The task changed after it was reviewed; re-read it before deciding.",
    };
  }

  const granted =
    input.decision === "release"
      ? input.grantedCapabilities.filter((capability) =>
          task.allowedCapabilities.includes(capability as never),
        )
      : [];
  if (input.decision === "release" && granted.length === 0) {
    return { ok: false, message: "Choose at least one capability to authorize." };
  }

  // The durable record of exactly what was put in front of the owner.
  const authorizationDigest = digest({
    taskId: task.id,
    objective: task.objective,
    riskLevel: task.riskLevel,
    proposed: [...task.allowedCapabilities].sort(),
    granted: [...granted].sort(),
    version: task.version,
  });

  let status: string;
  try {
    status = await repository.decideHeldTask({
      taskId: task.id,
      decision: input.decision,
      decidedByUserId: input.deciderUserId,
      comment,
      grantedCapabilities: granted,
      authorizationDigest,
      expectedVersion: input.expectedVersion,
    });
  } catch (error) {
    const reason = (error as Error).message;
    await repository.appendAuditEvent(
      heldTaskAudit(input, "denied", reason, task.id, authorizationDigest),
    );
    return { ok: false, message: reason };
  }

  await repository.appendAuditEvent(
    heldTaskAudit(
      input,
      "succeeded",
      input.decision === "release"
        ? `Released with ${granted.join(", ")}. ${comment}`
        : `Rejected. ${comment}`,
      task.id,
      authorizationDigest,
    ),
  );

  return {
    ok: true,
    message:
      input.decision === "release"
        ? `Released for work with ${granted.length} capability(ies). Task is now ${status}.`
        : "The task was rejected and will not be worked.",
  };
}

function heldTaskAudit(
  input: DecideHeldTaskInput,
  outcome: "succeeded" | "denied",
  reason: string,
  taskId: string,
  scopeDigest: string,
): AuditEvent {
  return AuditEventSchema.parse({
    id: randomUUID(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId,
    runId: null,
    actorType: "human",
    actorId: input.deciderUserId,
    action: `held_task.${input.decision}`,
    targetType: "task",
    targetId: taskId,
    outcome,
    reason,
    correlationId: randomUUID(),
    idempotencyKey: digest({
      taskId,
      decision: input.decision,
      decider: input.deciderUserId,
      scopeDigest,
    }),
    requestDigest: scopeDigest,
    resultDigest: digest({ outcome, reason }),
    evidenceArtifactIds: [],
    createdAt: new Date().toISOString(),
  });
}

export interface DecideApprovalInput {
  approvalRequestId: string;
  decision: "approve" | "reject" | "request_changes";
  comment: string;
  deciderUserId: string;
  /** The scope digest the decider saw when the page rendered. */
  viewedScopeDigest: string;
}

export interface DecideApprovalResult {
  ok: boolean;
  message: string;
}

export function approvalReadiness(
  request: ApprovalRequest,
  task: Task | undefined,
): { canApprove: boolean; blockers: string[] } {
  const blockers: string[] = [];
  if (
    task !== undefined &&
    task.testRequirements.length > 0 &&
    request.testsCompleted.length === 0
  ) {
    blockers.push(
      `Required checks have not run: ${task.testRequirements.join(", ")}.`,
    );
  }
  return { canApprove: blockers.length === 0, blockers };
}

function decisionAudit(
  input: DecideApprovalInput,
  outcome: "succeeded" | "denied" | "failed",
  reason: string,
  taskId: string | null,
  priorDecisionCount: number,
): AuditEvent {
  return AuditEventSchema.parse({
    id: randomUUID(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId,
    runId: null,
    actorType: "human",
    actorId: input.deciderUserId,
    action: `approval.${input.decision}`,
    targetType: "approval_request",
    targetId: input.approvalRequestId,
    outcome,
    reason,
    correlationId: randomUUID(),
    idempotencyKey: digest({
      approvalRequestId: input.approvalRequestId,
      deciderUserId: input.deciderUserId,
      decision: input.decision,
      priorDecisions: priorDecisionCount,
    }),
    requestDigest: digest(input),
    resultDigest: null,
    evidenceArtifactIds: [],
    createdAt: new Date().toISOString(),
  });
}

export async function decideApproval(
  input: DecideApprovalInput,
  repository: CompanyRepository = companyRepository(),
  owners: OwnerRegistry = OWNER_REGISTRY,
): Promise<DecideApprovalResult> {
  const comment = input.comment.trim();
  if (comment.length === 0) {
    return { ok: false, message: "A decision needs a written comment." };
  }

  const state = await repository.load();
  const request = state.approvalRequests.find(
    (candidate) => candidate.id === input.approvalRequestId,
  );
  if (request === undefined) {
    return { ok: false, message: "That approval request does not exist." };
  }
  const task = state.tasks.find((candidate) => candidate.id === request.taskId);
  const readiness = approvalReadiness(request, task);
  if (input.decision === "approve" && !readiness.canApprove) {
    const reason = `Approval blocked. ${readiness.blockers.join(" ")}`;
    await repository.appendAuditEvent(
      decisionAudit(
        input,
        "denied",
        reason,
        request.taskId,
        state.approvalDecisions.length,
      ),
    );
    return { ok: false, message: reason };
  }

  const decision = ApprovalDecisionSchema.parse({
    id: randomUUID(),
    approvalRequestId: request.id,
    decidedByUserId: input.deciderUserId,
    decision: input.decision,
    comment,
    requestScopeDigest: input.viewedScopeDigest,
    decidedAt: new Date().toISOString(),
  });

  const outcome = applyApprovalDecision({
    request,
    decision,
    owners,
    priorDecisions: state.approvalDecisions,
    now: decision.decidedAt,
  });

  if (outcome.outcome !== "applied") {
    await repository.appendAuditEvent(
      decisionAudit(
        input,
        outcome.outcome === "expired" ? "failed" : "denied",
        outcome.reason,
        request.taskId,
        state.approvalDecisions.length,
      ),
    );
    return { ok: false, message: outcome.reason };
  }

  let updatedTask = null;
  let message = `Recorded ${ownerName(input.deciderUserId)}'s ${input.decision.replaceAll("_", " ")}.`;

  if (outcome.taskStatusTarget !== null) {
    const task = state.tasks.find(
      (candidate) => candidate.id === request.taskId,
    );
    if (task !== undefined) {
      assertTaskTransition(task.status, outcome.taskStatusTarget);
      updatedTask = TaskSchema.parse({
        ...task,
        status: outcome.taskStatusTarget,
        version: task.version + 1,
        updatedAt: decision.decidedAt,
      });
      message += ` Task is now ${outcome.taskStatusTarget.replaceAll("_", " ")}.`;
    }
  } else {
    message += ` Waiting for a second distinct owner (${outcome.distinctApprovers}/${outcome.request.requiredApprovals}).`;
  }

  await repository.appendApprovalDecision({
    decision,
    resolvedRequest: outcome.request,
    updatedTask,
    auditEvent: decisionAudit(
      input,
      "succeeded",
      message,
      request.taskId,
      state.approvalDecisions.length,
    ),
  });

  return { ok: true, message };
}
