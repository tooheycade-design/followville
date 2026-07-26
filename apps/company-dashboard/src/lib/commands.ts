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
import { mutateState, type CompanyState } from "./store";

export interface SubmitGoalInput {
  title: string;
  objective: string;
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
  statePath?: string,
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
  });

  return mutateState((state) => {
    state.goals.push(result.goal);
    state.tasks.push(result.task);
    state.runs.push(result.run);
    state.approvalRequests.push(result.approvalRequest);
    state.auditEvents.push(...result.auditEvents);
    return {
      ok: true,
      message: `Simulated "${title}" through to a pending human approval.`,
      goalId: result.goal.id,
    };
  }, statePath);
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
  state: CompanyState,
  input: DecideApprovalInput,
  outcome: "succeeded" | "denied" | "failed",
  reason: string,
  taskId: string | null,
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
      priorDecisions: state.approvalDecisions.length,
    }),
    requestDigest: digest(input),
    resultDigest: null,
    evidenceArtifactIds: [],
    createdAt: new Date().toISOString(),
  });
}

export async function decideApproval(
  input: DecideApprovalInput,
  statePath?: string,
): Promise<DecideApprovalResult> {
  const comment = input.comment.trim();
  if (comment.length === 0) {
    return { ok: false, message: "A decision needs a written comment." };
  }

  return mutateState((state) => {
    const requestIndex = state.approvalRequests.findIndex(
      (request) => request.id === input.approvalRequestId,
    );
    const request = state.approvalRequests[requestIndex];
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

    if (outcome.outcome === "denied") {
      state.auditEvents.push(
        decisionAudit(state, input, "denied", outcome.reason, request.taskId),
      );
      return { ok: false, message: outcome.reason };
    }

    if (outcome.outcome === "expired") {
      state.approvalRequests[requestIndex] = outcome.request;
      state.auditEvents.push(
        decisionAudit(state, input, "failed", outcome.reason, request.taskId),
      );
      return { ok: false, message: outcome.reason };
    }

    state.approvalRequests[requestIndex] = outcome.request;
    state.approvalDecisions.push(decision);

    let message = `Recorded ${ownerName(input.deciderUserId)}'s ${input.decision.replaceAll("_", " ")}.`;
    if (outcome.taskStatusTarget !== null) {
      const taskIndex = state.tasks.findIndex(
        (task) => task.id === request.taskId,
      );
      const task = state.tasks[taskIndex];
      if (task !== undefined) {
        assertTaskTransition(task.status, outcome.taskStatusTarget);
        state.tasks[taskIndex] = TaskSchema.parse({
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

    state.auditEvents.push(
      decisionAudit(state, input, "succeeded", message, request.taskId),
    );
    return { ok: true, message };
  }, statePath);
}
