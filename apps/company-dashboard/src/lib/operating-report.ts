import type { CompanyState } from "./state/types";
import { workerHealth } from "./worker-health";

const DAY_MS = 24 * 60 * 60 * 1_000;
const FINISHED = new Set([
  "approved",
  "merged",
  "deployed",
  "rejected",
  "canceled",
]);

export interface AttentionItem {
  id: string;
  kind: "approval" | "held" | "failed";
  title: string;
  detail: string;
  href: "/approvals" | "/held" | "/audit";
  createdAt: string;
}

export interface OperatingReport {
  generatedAt: string;
  day: PeriodSummary;
  week: PeriodSummary;
  runningTasks: number;
  blockedTasks: number;
  heldTasks: number;
  pendingApprovals: number;
  subscriptionRuns: number;
  meteredSpendUsdMicros: number;
  onlineWorkers: number;
  unavailableWorkers: number;
  attention: readonly AttentionItem[];
  risks: readonly string[];
}

export interface PeriodSummary {
  goalsCreated: number;
  workCompleted: number;
  failures: number;
  ownerDecisions: number;
  draftPullRequests: number;
}

function since(iso: string, threshold: number): boolean {
  const value = Date.parse(iso);
  return Number.isFinite(value) && value >= threshold;
}

export function buildOperatingReport(
  state: CompanyState,
  now = new Date(),
): OperatingReport {
  const nowMs = now.getTime();
  const summarize = (threshold: number): PeriodSummary => {
    const events = state.auditEvents.filter((event) =>
      since(event.createdAt, threshold),
    );
    return {
      goalsCreated: events.filter((event) => event.action === "goal.created")
        .length,
      workCompleted: events.filter(
        (event) => event.action === "worker.completed",
      ).length,
      failures: events.filter(
        (event) =>
          event.outcome === "failed" ||
          event.action === "worker.failed" ||
          event.action === "review.rejected",
      ).length,
      ownerDecisions: events.filter(
        (event) =>
          event.action.startsWith("approval.") ||
          event.action.startsWith("held_task."),
      ).length,
      draftPullRequests: events.filter(
        (event) => event.action === "github.draft_pr_published",
      ).length,
    };
  };

  const pending = state.approvalRequests.filter(
    (request) => request.status === "pending",
  );
  const held = state.tasks.filter((task) => task.status === "proposed");
  const failed = state.tasks.filter(
    (task) => task.status === "failed" || task.status === "blocked",
  );
  const attention: AttentionItem[] = [
    ...pending.map((request) => ({
      id: request.id,
      kind: "approval" as const,
      title: request.summary,
      detail: `${request.action} - ${request.riskLevel} risk`,
      href: "/approvals" as const,
      createdAt: request.createdAt,
    })),
    ...held.map((task) => ({
      id: task.id,
      kind: "held" as const,
      title: task.title,
      detail: task.reason,
      href: "/held" as const,
      createdAt: task.updatedAt,
    })),
    ...failed.map((task) => ({
      id: task.id,
      kind: "failed" as const,
      title: task.title,
      detail: `${task.status}: ${task.reason}`,
      href: "/audit" as const,
      createdAt: task.updatedAt,
    })),
  ].sort((left, right) => right.createdAt.localeCompare(left.createdAt));

  const health = state.workers.map((worker) => workerHealth(worker, nowMs));
  const onlineWorkers = health.filter((item) => item.label === "online").length;
  const unavailableWorkers = health.length - onlineWorkers;
  const subscriptionRuns = state.runs.filter(
    (run) =>
      run.modelProvider === "codex" || run.modelProvider === "claude-code",
  ).length;
  const meteredSpendUsdMicros = state.runs.reduce(
    (sum, run) => sum + run.actualCostUsdMicros,
    0,
  );
  const runningTasks = state.tasks.filter(
    (task) =>
      !FINISHED.has(task.status) &&
      !["proposed", "failed", "blocked", "awaiting_human_approval"].includes(
        task.status,
      ),
  ).length;

  const risks: string[] = [];
  if (unavailableWorkers > 0) {
    risks.push(
      `${unavailableWorkers} registered worker${unavailableWorkers === 1 ? " is" : "s are"} delayed, offline, draining, or in error.`,
    );
  }
  if (failed.length > 0) {
    risks.push(
      `${failed.length} task${failed.length === 1 ? " is" : "s are"} blocked or failed and may need a narrower revision.`,
    );
  }
  if (pending.length > 0) {
    risks.push(
      `${pending.length} owner decision${pending.length === 1 ? " is" : "s are"} waiting; production authority remains unchanged until decided.`,
    );
  }
  if (risks.length === 0) {
    risks.push("No current operating risk needs owner attention.");
  }

  return {
    generatedAt: now.toISOString(),
    day: summarize(nowMs - DAY_MS),
    week: summarize(nowMs - 7 * DAY_MS),
    runningTasks,
    blockedTasks: failed.length,
    heldTasks: held.length,
    pendingApprovals: pending.length,
    subscriptionRuns,
    meteredSpendUsdMicros,
    onlineWorkers,
    unavailableWorkers,
    attention,
    risks,
  };
}
