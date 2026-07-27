"use client";

import { useActionState } from "react";

import { directCeoAction, type CeoActionState } from "../actions";

export function CeoForm() {
  const [result, formAction, pending] = useActionState<
    CeoActionState | null,
    FormData
  >(directCeoAction, null);

  return (
    <form action={formAction} className="stack">
      <label className="field">
        What do you want?
        <input
          type="text"
          name="title"
          maxLength={180}
          required
          placeholder="Make the town map open faster"
        />
      </label>
      <label className="field">
        Say more
        <textarea
          name="detail"
          rows={3}
          required
          placeholder="Opening the map takes several seconds on my phone. It should feel instant."
        />
      </label>
      <button type="submit" disabled={pending}>
        {pending ? "Planning…" : "Give it to the CEO"}
      </button>

      {result !== null && (
        <>
          <p className={`notice${result.ok ? "" : " notice--error"}`}>
            {result.message}
          </p>
          {result.escalations.length > 0 && (
            <div className="notice notice--error">
              <b>Held for your decision</b>
              <ul>
                {result.escalations.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            </div>
          )}
          {result.clamped.length > 0 && (
            <div className="notice notice--error">
              <b>Capabilities refused</b>
              <ul>
                {result.clamped.map((entry) => (
                  <li key={entry} className="mono">
                    {entry}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </form>
  );
}
