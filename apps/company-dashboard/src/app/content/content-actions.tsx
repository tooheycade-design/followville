"use client";

import { useActionState } from "react";

import {
  createContentPacketAction,
  selectContentConceptAction,
  type ActionState,
} from "../actions";

export function ContentBriefForm() {
  const [result, action, pending] = useActionState<ActionState | null, FormData>(
    createContentPacketAction,
    null,
  );
  return (
    <form action={action} className="stack content-brief">
      <label className="field">
        Objective
        <textarea
          name="objective"
          rows={2}
          maxLength={1000}
          placeholder="Use the latest milestone to invite more people into the town."
        />
      </label>
      <button type="submit" disabled={pending}>
        {pending ? "Planning..." : "Create three concepts"}
      </button>
      {result !== null && (
        <p className={`notice${result.ok ? "" : " notice--error"}`}>
          {result.message}
        </p>
      )}
    </form>
  );
}

export function SelectConceptForm(props: {
  packetId: string;
  conceptId: string;
  expectedVersion: number;
}) {
  const [result, action, pending] = useActionState<ActionState | null, FormData>(
    selectContentConceptAction,
    null,
  );
  return (
    <form action={action} className="stack">
      <input type="hidden" name="packetId" value={props.packetId} />
      <input type="hidden" name="conceptId" value={props.conceptId} />
      <input
        type="hidden"
        name="expectedVersion"
        value={props.expectedVersion}
      />
      <button type="submit" disabled={pending}>
        {pending ? "Selecting..." : "Select and queue private preview"}
      </button>
      {result !== null && (
        <p className={`notice${result.ok ? "" : " notice--error"}`}>
          {result.message}
        </p>
      )}
    </form>
  );
}
