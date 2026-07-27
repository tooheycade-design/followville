"use client";

import { useActionState } from "react";

import { submitGoalAction, type ActionState } from "../actions";

export function GoalForm() {
  const [result, formAction, pending] = useActionState<
    ActionState | null,
    FormData
  >(submitGoalAction, null);

  return (
    <form action={formAction} className="stack">
      <label className="field">
        Title
        <input
          type="text"
          name="title"
          maxLength={180}
          required
          placeholder="Add a bench count to the town map"
        />
      </label>
      <label className="field">
        Objective
        <textarea
          name="objective"
          rows={3}
          required
          placeholder="What should exist when this goal is done, and how will we know?"
        />
      </label>
      <button type="submit" disabled={pending}>
        {pending ? "Running test…" : "Run lifecycle test"}
      </button>
      {result !== null && (
        <p className={`notice${result.ok ? "" : " notice--error"}`}>
          {result.message}
        </p>
      )}
    </form>
  );
}
