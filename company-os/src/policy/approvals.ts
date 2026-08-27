import {
  ApprovalRequestSchema,
  type ApprovalDecision,
  type ApprovalRequest,
  type TaskStatus,
} from "../domain/schemas.js";

export interface OwnerRegistry {
  readonly ownerUserIds: readonly string[];
  readonly operatorUserIds: readonly string[];
}

export interface DecisionContext {
  request: ApprovalRequest;
  decision: ApprovalDecision;
  owners: OwnerRegistry;
  priorDecisions?: readonly ApprovalDecision[];
  now: string;
}

export type DecisionResult =
  | {
      outcome: "applied";
      request: ApprovalRequest;
      taskStatusTarget: TaskStatus | null;
      distinctApprovers: number;
    }
  | { outcome: "denied"; reason: string }
  | { outcome: "expired"; request: ApprovalRequest; reason: string };

const DECISION_TO_REQUEST_STATUS = {
  approve: "approved",
  reject: "rejected",
  request_changes: "changes_requested",
} as const;

const DECISION_TO_TASK_STATUS: Record<
  ApprovalDecision["decision"],
  TaskStatus
> = {
  approve: "approved",
  reject: "rejected",
  request_changes: "changes_requested",
};

function denied(reason: string): DecisionResult {
  return { outcome: "denied", reason };
}

export function applyApprovalDecision(context: DecisionContext): DecisionResult {
  const { request, decision, owners, now } = context;
  const priorDecisions = context.priorDecisions ?? [];

  if (decision.approvalRequestId !== request.id) {
    return denied("The decision references a different approval request.");
  }
  const authorizedUserIds =
    request.requiredRole === "owner"
      ? owners.ownerUserIds
      : owners.operatorUserIds;
  if (!authorizedUserIds.includes(decision.decidedByUserId)) {
    return denied(
      `Only a registered human ${request.requiredRole} can decide this approval.`,
    );
  }
  if (decision.requestScopeDigest !== request.scopeDigest) {
    return denied(
      "The decision was made against a different scope digest; the request changed after review.",
    );
  }
  if (request.status !== "pending") {
    return denied(`The approval request is already ${request.status}.`);
  }
  if (Date.parse(now) >= Date.parse(request.expiresAt)) {
    const expired = ApprovalRequestSchema.parse({
      ...request,
      status: "expired",
    });
    return {
      outcome: "expired",
      request: expired,
      reason: "The approval request expired before a decision was recorded.",
    };
  }

  if (decision.decision === "reject" || decision.decision === "request_changes") {
    const updated = ApprovalRequestSchema.parse({
      ...request,
      status: DECISION_TO_REQUEST_STATUS[decision.decision],
    });
    return {
      outcome: "applied",
      request: updated,
      taskStatusTarget: DECISION_TO_TASK_STATUS[decision.decision],
      distinctApprovers: 0,
    };
  }

  const approvers = new Set<string>();
  for (const prior of priorDecisions) {
    if (
      prior.approvalRequestId === request.id &&
      prior.decision === "approve" &&
      prior.requestScopeDigest === request.scopeDigest &&
      authorizedUserIds.includes(prior.decidedByUserId)
    ) {
      approvers.add(prior.decidedByUserId);
    }
  }
  approvers.add(decision.decidedByUserId);

  if (approvers.size >= request.requiredApprovals) {
    const updated = ApprovalRequestSchema.parse({
      ...request,
      status: "approved",
    });
    return {
      outcome: "applied",
      request: updated,
      taskStatusTarget: "approved",
      distinctApprovers: approvers.size,
    };
  }

  return {
    outcome: "applied",
    request,
    taskStatusTarget: null,
    distinctApprovers: approvers.size,
  };
}
