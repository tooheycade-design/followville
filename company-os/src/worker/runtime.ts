import { AuditEventSchema, type AuditEvent, type Task } from "../domain/schemas.js";
import { digest } from "../domain/fingerprints.js";
import { ORGANIZATION_ID, PROJECT_ID } from "../config/seed-agents.js";
import { SEED_AGENTS } from "../config/seed-agents.js";
import { preflightCapabilities } from "./path-guard.js";
import { reportedArtifact } from "./artifacts.js";
import { encodeWorkerReport } from "./report.js";
import type {
  LeasedTask,
  TaskExecutor,
  WorkQueue,
  WorkResult,
  WorkerOptions,
} from "./types.js";

export interface TaskOutcome {
  taskId: string;
  status: "completed" | "blocked" | "failed" | "lost_lease";
  summary: string;
  costUsdMicros: number;
}

function auditEvent(input: {
  id: string;
  correlationId: string;
  taskId: string;
  actorId: string;
  action: string;
  outcome: AuditEvent["outcome"];
  reason: string;
  request: unknown;
  result?: unknown;
  runId?: string | null;
  now: string;
}): AuditEvent {
  return AuditEventSchema.parse({
    id: input.id,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: input.taskId,
    runId: input.runId ?? null,
    actorType: "agent",
    actorId: input.actorId,
    action: input.action,
    targetType: "task",
    targetId: input.taskId,
    outcome: input.outcome,
    reason: input.reason,
    correlationId: input.correlationId,
    idempotencyKey: digest({
      taskId: input.taskId,
      action: input.action,
      correlationId: input.correlationId,
    }),
    requestDigest: digest(input.request),
    resultDigest: input.result === undefined ? null : digest(input.result),
    evidenceArtifactIds: [],
    createdAt: input.now,
  });
}

/**
 * Runs one task end to end under a lease.
 *
 * The lease is the safety mechanism, so the runtime treats losing it as fatal
 * to the attempt: if a heartbeat fails, the work is abandoned rather than
 * written back, because another worker may already have claimed the task and a
 * stale result would silently overwrite fresher work.
 */
export async function runLeasedTask(
  leased: LeasedTask,
  executor: TaskExecutor,
  queue: WorkQueue,
  options: WorkerOptions,
  idFactory: () => string,
  now: () => string = () => new Date().toISOString(),
): Promise<TaskOutcome> {
  const { task } = leased;
  const correlationId = idFactory();
  const controller = new AbortController();
  let leaseLost = false;
  let runId: string | null = null;

  const record = async (
    action: string,
    outcome: AuditEvent["outcome"],
    reason: string,
    request: unknown,
    result?: unknown,
  ): Promise<void> => {
    await queue.appendAuditEvent(
      auditEvent({
        id: idFactory(),
        correlationId,
        taskId: task.id,
        actorId: task.assignedAgentId ?? SEED_AGENTS.engineer.id,
        action,
        outcome,
        reason,
        request,
        result,
        runId,
        now: now(),
      }),
    );
  };

  // Re-check policy at execution time. The queue is not a trusted authority on
  // what a task may do; the policy engine is.
  const agent = Object.values(SEED_AGENTS).find(
    (candidate) => candidate.id === task.assignedAgentId,
  );
  if (agent === undefined) {
    await record(
      "worker.rejected",
      "denied",
      "The assigned agent profile does not exist.",
      { assignedAgentId: task.assignedAgentId },
    );
    await queue.transition(task.id, options.workerId, "failed", true);
    return {
      taskId: task.id,
      status: "failed",
      summary: "Unknown assigned agent.",
      costUsdMicros: 0,
    };
  }

  // Coarse gate only. Repository capabilities are authorized per path at
  // access time through the guard the executor receives, because the policy
  // engine cannot answer "may this agent read the repository" without knowing
  // which path is involved.
  const preflight = preflightCapabilities(agent, task);
  if (preflight.outcome !== "allowed") {
    await record("worker.rejected", "denied", preflight.reason, {
      allowedCapabilities: task.allowedCapabilities,
    });
    await queue.transition(task.id, options.workerId, "blocked", true);
    return {
      taskId: task.id,
      status: "blocked",
      summary: preflight.reason,
      costUsdMicros: 0,
    };
  }

  const started = await queue.transition(
    task.id,
    options.workerId,
    "in_progress",
    false,
  );
  if (!started) {
    return {
      taskId: task.id,
      status: "lost_lease",
      summary: "The lease was lost before work began.",
      costUsdMicros: 0,
    };
  }

  runId = idFactory();
  const runStarted = await queue.startRun({
    id: runId,
    taskId: task.id,
    agentId: agent.id,
    reviewerAgentId: task.reviewerAgentId,
    workerId: options.workerId,
    leaseEpoch: leased.leaseEpoch,
    promptVersion: `worker-v1:${executor.name}`,
    contextManifestDigest: digest({
      taskId: task.id,
      version: task.version,
      objective: task.objective,
      criteria: task.acceptanceCriteria,
      scopes: task.repositoryScopes,
    }),
    retryCount: task.retryCount,
    startedAt: now(),
  });
  if (!runStarted) {
    await queue.transition(task.id, options.workerId, "failed", true);
    return {
      taskId: task.id,
      status: "lost_lease",
      summary: "The run ledger could not be opened before work began.",
      costUsdMicros: 0,
    };
  }

  const finishRun = async (
    runStatus: "awaiting_review" | "failed" | "canceled",
    taskStatus: Task["status"] | null,
    releaseLease: boolean,
    result?: WorkResult,
  ): Promise<boolean> =>
    queue.finishRun({
      runId: runId!,
      taskId: task.id,
      workerId: options.workerId,
      leaseEpoch: leased.leaseEpoch,
      runStatus,
      taskStatus,
      releaseLease,
      modelProvider: result?.modelProvider ?? null,
      modelId: result?.modelId ?? null,
      inputTokens: result?.inputTokens ?? 0,
      outputTokens: result?.outputTokens ?? 0,
      cachedInputTokens: result?.cachedInputTokens ?? 0,
      costUsdMicros: result?.costUsdMicros ?? 0,
      completedAt: now(),
    });

  await record("worker.started", "succeeded", `Executor ${executor.name} began work.`, {
    executor: executor.name,
  });

  const heartbeat = setInterval(() => {
    void queue
      .heartbeat(task.id, options.workerId, options.leaseSeconds)
      .then((held) => {
        if (!held) {
          leaseLost = true;
          controller.abort();
        }
      })
      .catch(() => {
        leaseLost = true;
        controller.abort();
      });
  }, options.heartbeatIntervalMs);

  const timeout = setTimeout(() => controller.abort(), options.maxTaskDurationMs);

  let result: WorkResult;
  try {
    result = await executor.execute(task, controller.signal);
  } catch (error) {
    clearInterval(heartbeat);
    clearTimeout(timeout);
    const reason = leaseLost
      ? "The lease was lost during execution; the result was discarded."
      : `Execution failed: ${(error as Error).message}`;
    if (leaseLost) {
      await record("worker.lease_lost", "failed", reason, { taskId: task.id });
      await finishRun("canceled", null, false);
      return {
        taskId: task.id,
        status: "lost_lease",
        summary: reason,
        costUsdMicros: 0,
      };
    }
    await record("worker.failed", "failed", reason, { taskId: task.id });
    const finished = await finishRun("failed", "failed", true);
    if (!finished) {
      return {
        taskId: task.id,
        status: "lost_lease",
        summary: "The lease expired before the failure could be recorded.",
        costUsdMicros: 0,
      };
    }
    return { taskId: task.id, status: "failed", summary: reason, costUsdMicros: 0 };
  }
  clearInterval(heartbeat);
  clearTimeout(timeout);

  if (leaseLost) {
    const reason = "The lease was lost during execution; the result was discarded.";
    await record("worker.lease_lost", "failed", reason, { taskId: task.id });
    await finishRun("canceled", null, false, result);
    return { taskId: task.id, status: "lost_lease", summary: reason, costUsdMicros: 0 };
  }

  if (result.outcome === "completed" && result.evidence.length === 0) {
    const reason = "The executor reported success without evidence.";
    await record("worker.rejected", "denied", reason, { summary: result.summary });
    const finished = await finishRun("failed", "failed", true, result);
    if (!finished) {
      return {
        taskId: task.id,
        status: "lost_lease",
        summary: "The lease expired before the rejected result could be recorded.",
        costUsdMicros: result.costUsdMicros,
      };
    }
    return { taskId: task.id, status: "failed", summary: reason, costUsdMicros: result.costUsdMicros };
  }

  const nextStatus: Task["status"] =
    result.outcome === "completed"
      ? "awaiting_review"
      : result.outcome === "blocked"
        ? "blocked"
        : "failed";

  // The evidence is written into the audit reason, not just hashed into the
  // result digest. A reviewer reads what was recorded rather than what the
  // worker said in passing, so anything it must judge on has to survive in
  // readable form; a digest proves nothing was altered but cannot be read.
  //
  // The encoding is shared with the reader rather than reproduced there. When
  // the two were written separately they drifted, and the reader kept only the
  // first line of a report the writer had emitted in full.
  const recordedReason = encodeWorkerReport({
    summary: result.summary,
    evidence: result.evidence,
    testsCompleted: result.testsCompleted,
    testsFailed: result.testsFailed,
    filesChanged: result.filesChanged,
    diff: result.diff,
    artifacts: result.artifacts.map(reportedArtifact),
  });

  await record(
    `worker.${result.outcome}`,
    result.outcome === "completed" ? "succeeded" : "failed",
    recordedReason,
    { executor: executor.name },
    {
      evidence: result.evidence,
      filesChanged: result.filesChanged,
      costUsdMicros: result.costUsdMicros,
      testsCompleted: result.testsCompleted,
      testsFailed: result.testsFailed,
    },
  );

  const moved = await finishRun(
    result.outcome === "completed" ? "awaiting_review" : "failed",
    nextStatus,
    true,
    result,
  );
  if (!moved) {
    return {
      taskId: task.id,
      status: "lost_lease",
      summary: "The lease expired before the result could be written.",
      costUsdMicros: result.costUsdMicros,
    };
  }

  return {
    taskId: task.id,
    status: result.outcome,
    summary: result.summary,
    costUsdMicros: result.costUsdMicros,
  };
}

/** Drains the queue until it is empty or `maxTasks` is reached. */
export async function runWorker(
  executor: TaskExecutor,
  queue: WorkQueue,
  options: WorkerOptions,
  idFactory: () => string,
): Promise<readonly TaskOutcome[]> {
  const outcomes: TaskOutcome[] = [];
  const limit = options.maxTasks ?? Number.POSITIVE_INFINITY;

  while (outcomes.length < limit) {
    const leased = await queue.leaseNextTask(
      options.workerId,
      options.leaseSeconds,
    );
    if (leased === null) {
      break;
    }
    outcomes.push(
      await runLeasedTask(leased, executor, queue, options, idFactory),
    );
  }
  return outcomes;
}
