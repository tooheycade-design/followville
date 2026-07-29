"use client";

import { useActionState } from "react";

import { correctMemoryAction, type ActionState } from "@/app/actions";

const INITIAL_STATE: ActionState = { ok: false, message: "" };

export function CorrectionForm({
  memoryId,
  expectedVersion,
  currentBody,
}: {
  memoryId: string;
  expectedVersion: number;
  currentBody: string;
}) {
  const [state, action, pending] = useActionState(
    correctMemoryAction,
    INITIAL_STATE,
  );
  return (
    <form action={action} className="memory-correction">
      <input type="hidden" name="memoryId" value={memoryId} />
      <input type="hidden" name="expectedVersion" value={expectedVersion} />
      <label className="field">
        Corrected fact
        <textarea name="body" defaultValue={currentBody} rows={5} required />
      </label>
      <label className="field">
        Why this changed
        <input name="reason" minLength={3} required />
      </label>
      <button type="submit" disabled={pending}>
        {pending ? "Recording..." : "Record correction"}
      </button>
      {state.message.length === 0 ? null : (
        <p className={state.ok ? "notice" : "notice notice--error"}>
          {state.message}
        </p>
      )}
    </form>
  );
}
