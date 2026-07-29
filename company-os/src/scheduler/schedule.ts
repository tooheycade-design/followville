/**
 * Scheduled wake-ups.
 *
 * Deliberately interval-based rather than cron. The company runs on personal
 * machines that sleep, so a wall-clock cron would silently skip everything
 * that fell due while a laptop was closed. Tracking "when did this last run"
 * instead means a machine coming back online notices it is overdue and
 * catches up once, rather than either missing the work or replaying every
 * missed slot.
 */
export interface ScheduleDefinition {
  name: string;
  /** How often the job should run. */
  intervalMs: number;
  /** Skipped runs are never replayed; only the current state matters. */
  catchUp: boolean;
  description: string;
}

export interface ScheduleState {
  name: string;
  lastRunAt: string | null;
  lastOutcome: "succeeded" | "failed" | null;
  consecutiveFailures: number;
}

export const MINUTE = 60_000;
export const HOUR = 60 * MINUTE;

/**
 * The default company schedule.
 *
 * Frequencies are chosen so an idle company is cheap: the queue check is the
 * only frequent job, and it does nothing when there is no work.
 */
export const DEFAULT_SCHEDULE: readonly ScheduleDefinition[] = [
  {
    name: "work-queue",
    intervalMs: 2 * MINUTE,
    catchUp: false,
    description: "Lease and run any queued work, then review finished work.",
  },
  {
    name: "reclaim-leases",
    intervalMs: 5 * MINUTE,
    catchUp: false,
    description: "Requeue tasks whose worker stopped reporting.",
  },
  {
    name: "operations-refresh",
    intervalMs: 15 * MINUTE,
    catchUp: false,
    description: "Capture approved read-only Followville operating signals.",
  },
  {
    name: "daily-report",
    intervalMs: 24 * HOUR,
    catchUp: true,
    description: "Summarize what happened and what needs an owner.",
  },
  {
    name: "cost-audit",
    intervalMs: 24 * HOUR,
    catchUp: true,
    description: "Check model usage against the configured budget.",
  },
];

export interface DueDecision {
  due: boolean;
  reason: string;
}

/**
 * Decides whether a job should run now.
 *
 * A job that has never run is due immediately. A job whose backoff is active
 * after repeated failures is held off, so a broken job cannot spin: each
 * consecutive failure doubles the wait, up to an hour.
 */
export function isDue(
  definition: ScheduleDefinition,
  state: ScheduleState | undefined,
  now: number,
): DueDecision {
  if (state === undefined || state.lastRunAt === null) {
    return { due: true, reason: "It has never run." };
  }

  const last = Date.parse(state.lastRunAt);
  if (!Number.isFinite(last)) {
    return { due: true, reason: "The last run time is unreadable." };
  }

  const elapsed = now - last;
  if (state.consecutiveFailures > 0) {
    const backoff = Math.min(
      definition.intervalMs * 2 ** state.consecutiveFailures,
      HOUR,
    );
    if (elapsed < backoff) {
      return {
        due: false,
        reason: `Backing off after ${state.consecutiveFailures} failure(s); ${Math.round(
          (backoff - elapsed) / 1000,
        )}s remaining.`,
      };
    }
    return { due: true, reason: "The failure backoff has elapsed." };
  }

  if (elapsed >= definition.intervalMs) {
    return { due: true, reason: `Last ran ${Math.round(elapsed / 1000)}s ago.` };
  }
  return {
    due: false,
    reason: `Next run in ${Math.round((definition.intervalMs - elapsed) / 1000)}s.`,
  };
}

export function recordRun(
  state: ScheduleState | undefined,
  name: string,
  outcome: "succeeded" | "failed",
  now: string,
): ScheduleState {
  const failures =
    outcome === "failed" ? (state?.consecutiveFailures ?? 0) + 1 : 0;
  return {
    name,
    lastRunAt: now,
    lastOutcome: outcome,
    consecutiveFailures: failures,
  };
}

/** Jobs due now, most overdue first. */
export function dueJobs(
  definitions: readonly ScheduleDefinition[],
  states: ReadonlyMap<string, ScheduleState>,
  now: number,
): readonly ScheduleDefinition[] {
  return definitions
    .filter((definition) => isDue(definition, states.get(definition.name), now).due)
    .sort((a, b) => {
      const aLast = Date.parse(states.get(a.name)?.lastRunAt ?? "0") || 0;
      const bLast = Date.parse(states.get(b.name)?.lastRunAt ?? "0") || 0;
      return aLast - bLast;
    });
}
