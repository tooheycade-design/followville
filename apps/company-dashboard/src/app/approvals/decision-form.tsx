"use client";

import { useActionState } from "react";

import { decideApprovalAction, type ActionState } from "../actions";

export function DecisionForm({
  approvalRequestId,
  scopeDigest,
}: {
  approvalRequestId: string;
  scopeDigest: string;
}) {
  const [result, formAction, pending] = useActionState<
    ActionState | null,
    FormData
  >(decideApprovalAction, null);

  return (
    <form action={formAction}>
      <input type="hidden" name="approvalRequestId" value={approvalRequestId} />
      <input type="hidden" name="scopeDigest" value={scopeDigest} />
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
        <button type="submit" name="decision" value="approve" disabled={pending}>
          Approve
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
