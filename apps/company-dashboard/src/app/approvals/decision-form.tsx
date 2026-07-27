"use client";

import { useActionState } from "react";

import { decideApprovalAction, type ActionState } from "../actions";

export function DecisionForm({
  approvalRequestId,
  scopeDigest,
  canApprove,
  blockers,
}: {
  approvalRequestId: string;
  scopeDigest: string;
  canApprove: boolean;
  blockers: readonly string[];
}) {
  const [result, formAction, pending] = useActionState<
    ActionState | null,
    FormData
  >(decideApprovalAction, null);

  return (
    <form action={formAction}>
      <input type="hidden" name="approvalRequestId" value={approvalRequestId} />
      <input type="hidden" name="scopeDigest" value={scopeDigest} />
      {!canApprove && (
        <div className="approval-blocker" role="alert">
          <b>Approval is blocked</b>
          {blockers.map((blocker) => (
            <span key={blocker}>{blocker}</span>
          ))}
          <span>You can still request changes or reject this work.</span>
        </div>
      )}
      {canApprove && (
        <label className="understanding-check">
          <input
            type="checkbox"
            name="confirmedUnderstanding"
            value="yes"
            required
          />
          I understand what this action authorizes and what it does not do.
        </label>
      )}
      <div className="decision-row">
        <label className="field">
          Comment (required)
          <input
            type="text"
            name="comment"
            required
            placeholder="What did you check before deciding?"
          />
        </label>
        <button
          type="submit"
          name="decision"
          value="approve"
          disabled={pending || !canApprove}
        >
          Approve this action
        </button>
        <button
          type="submit"
          name="decision"
          value="request_changes"
          className="quiet"
          disabled={pending}
        >
          Request changes
        </button>
        <button
          type="submit"
          name="decision"
          value="reject"
          className="danger"
          disabled={pending}
        >
          Reject
        </button>
      </div>
      {result !== null && (
        <p className={`notice${result.ok ? "" : " notice--error"}`}>
          {result.message}
        </p>
      )}
    </form>
  );
}
