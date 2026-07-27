import type { AuditEvent, Task } from "../domain/schemas.js";

export interface LeasedTask {
  task: Task;
  leaseEpoch: number;
  leaseExpiresAt: string;
}

/** What a worker produced. Evidence is required; a claim alone is not a result. */
export interface WorkResult {
  outcome: "completed" | "blocked" | "failed";
  summary: string;
  evidence: readonly string[];
  filesChanged: readonly string[];
  /**
   * The change itself, or null when the executor cannot produce one.
   *
   * Required rather than optional on purpose: an executor that has no diff has
   * to say so. The failure this whole path exists to prevent is evidence going
   * missing quietly, and an optional field is precisely how that happens again.
   */
  diff: string | null;
  modelProvider: string | null;
  modelId: string | null;
  inputTokens: number;
  outputTokens: number;
  costUsdMicros: number;
}

/**
 * Performs the actual work for a task. Implementations range from a
 * deterministic no-model executor to a real coding agent. The runtime treats
 * every executor the same: bounded, observed, and required to produce evidence.
 */
export interface TaskExecutor {
  readonly name: string;
  execute(task: Task, signal: AbortSignal): Promise<WorkResult>;
}

/** The runtime's view of the queue. Backed by the database in production. */
export interface WorkQueue {
  leaseNextTask(workerId: string, leaseSeconds: number): Promise<LeasedTask | null>;
  heartbeat(taskId: string, workerId: string, leaseSeconds: number): Promise<boolean>;
  transition(
    taskId: string,
    workerId: string,
    nextStatus: Task["status"],
    releaseLease: boolean,
  ): Promise<boolean>;
  appendAuditEvent(event: AuditEvent): Promise<void>;
}

export interface WorkerOptions {
  workerId: string;
  leaseSeconds: number;
  heartbeatIntervalMs: number;
  maxTaskDurationMs: number;
  /** Stop after this many tasks. Used by tests and one-shot runs. */
  maxTasks?: number;
}
