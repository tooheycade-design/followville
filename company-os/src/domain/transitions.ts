import type { TaskStatus } from "./schemas.js";

const TASK_TRANSITIONS: Readonly<Record<TaskStatus, readonly TaskStatus[]>> = {
  proposed: ["planned", "canceled", "rejected"],
  planned: ["approved_for_work", "canceled", "rejected"],
  approved_for_work: ["queued", "canceled"],
  queued: ["assigned", "blocked", "canceled", "failed"],
  assigned: ["in_progress", "blocked", "canceled", "failed"],
  in_progress: ["blocked", "awaiting_review", "canceled", "failed"],
  blocked: ["in_progress", "canceled", "failed"],
  awaiting_review: ["changes_requested", "awaiting_human_approval", "failed"],
  changes_requested: ["in_progress", "canceled", "failed"],
  awaiting_human_approval: ["approved", "rejected", "changes_requested", "canceled"],
  approved: ["merged", "canceled"],
  rejected: [],
  merged: ["deployed"],
  deployed: [],
  canceled: [],
  failed: ["queued", "canceled"],
};

export function canTransitionTask(
  from: TaskStatus,
  to: TaskStatus,
): boolean {
  return TASK_TRANSITIONS[from].includes(to);
}

export function assertTaskTransition(
  from: TaskStatus,
  to: TaskStatus,
): void {
  if (!canTransitionTask(from, to)) {
    throw new Error(`Invalid task transition: ${from} -> ${to}`);
  }
}

export function allowedTaskTransitions(
  status: TaskStatus,
): readonly TaskStatus[] {
  return TASK_TRANSITIONS[status];
}
