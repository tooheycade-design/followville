import { randomUUID } from "node:crypto";
import { existsSync } from "node:fs";
import path from "node:path";

import {
  ApprovalDecisionSchema,
  AuditEventSchema,
  ORGANIZATION_ID,
  PROJECT_ID,
  TaskSchema,
  applyApprovalDecision,
  assertTaskTransition,
  digest,
  simulateGoal,
  type AuditEvent,
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
    owners: OWNER_REGISTRY,
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
