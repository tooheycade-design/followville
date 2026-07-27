"use client";

import { useActionState } from "react";

import { decideHeldTaskAction, type ActionState } from "../actions";

/**
 * The owner's decision on held work.
 *
 * Every proposed capability is a separate box, ticked by default, so releasing
 * with less than was asked for is an ordinary action rather than something an
 * owner has to know is possible. Unticking one is how a grant is narrowed; the
 * database independently refuses anything the task did not propose.
 */
export function ReleaseForm({
  taskId,
  expectedVersion,
  proposedCapabilities,
}: {
  taskId: string;
  expectedVersion: number;
  proposedCapabilities: readonly string[];
}) {
  const [result, formAction, pending] = useActionState<
    ActionState | null,
    FormData
  >(decideHeldTaskAction, null);

  return (
    <form action={formAction}>
      <input type="hidden" name="taskId" value={taskId} />
      <input type="hidden" name="expectedVersion" value={expectedVersion} />

      <fieldset className="capability-set">
        <legend>Authorize these capabilities</legend>
        {proposedCapabilities.map((capability) => (
          <label key={capability} className="capability">
            <input
              type="checkbox"
              name="capability"
              value={capability}
              defaultChecked
            />
            <span className="mono">{capability}</span>
          </label>
        ))}
      </fieldset>

      <div className="decision-row">
        <label className="field">
          Comment (required)
          <input
            type="text"
            name="comment"
            required
            placeholder="Why is this safe to start?"
          />
        </label>
        <button type="submit" name="decision" value="release" disabled={pending}>
          Release for work
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
