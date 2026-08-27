import type {
  ApprovalDecision,
  ApprovalRequest,
  Capability,
} from "../domain/schemas.js";
import {
  authorize,
  type AuthorizationRequest,
  type PolicyDecision,
} from "./policy-engine.js";

export interface ApprovalVerificationRequest {
  request: ApprovalRequest;
  decisions: readonly ApprovalDecision[];
  action: Capability;
  scopeDigest: string;
  commitSha: string | null;
  authorizedApproverUserIds: ReadonlySet<string>;
  now: string;
}

export function verifyApproval(
  input: ApprovalVerificationRequest,
): PolicyDecision {
  const now = Date.parse(input.now);
  if (!Number.isFinite(now)) {
    return { outcome: "denied", reason: "The verification timestamp is invalid." };
  }
  if (input.request.status !== "approved") {
    return { outcome: "denied", reason: "The approval request is not approved." };
  }
  if (Date.parse(input.request.expiresAt) <= now) {
    return { outcome: "denied", reason: "The approval request has expired." };
  }
  if (
    input.request.action !== input.action ||
    input.request.scopeDigest !== input.scopeDigest ||
    input.request.commitSha !== input.commitSha
  ) {
    return {
      outcome: "denied",
      reason: "The requested action, scope, or commit differs from the approval.",
    };
  }

  const validApprovers = new Set<string>();
  for (const decision of input.decisions) {
    if (
      decision.approvalRequestId !== input.request.id ||
      decision.requestScopeDigest !== input.request.scopeDigest ||
      decision.decision !== "approve" ||
      !input.authorizedApproverUserIds.has(decision.decidedByUserId)
    ) {
      continue;
    }
    validApprovers.add(decision.decidedByUserId);
  }
  if (validApprovers.size < input.request.requiredApprovals) {
    return {
      outcome: "denied",
      reason: "The request does not have enough distinct authorized approvals.",
    };
  }
  return {
    outcome: "allowed",
    reason: "The unexpired approval matches the exact action, scope, and commit.",
  };
}

export function authorizeApprovedAction(
  authorization: AuthorizationRequest,
  approval: ApprovalVerificationRequest,
): PolicyDecision {
  if (
    approval.request.organizationId !== authorization.task.organizationId ||
    approval.request.projectId !== authorization.task.projectId ||
    approval.request.taskId !== authorization.task.id
  ) {
    return {
      outcome: "denied",
      reason: "The approval belongs to a different organization, project, or task.",
    };
  }
  const policy = authorize(authorization);
  if (policy.outcome !== "approval_required") {
    return policy.outcome === "allowed"
      ? {
          outcome: "denied",
          reason: "Approval evidence was supplied for an action that is not approval-gated.",
        }
      : policy;
  }
  return verifyApproval(approval);
}
