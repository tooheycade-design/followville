import { createClient } from "@supabase/supabase-js";

import {
  TaskSchema,
  WorkerNodeSchema,
  type AuditEvent,
  type Capability,
  type LeasedTask,
  type StructuredMessage,
  type Task,
  type WorkQueue,
  type WorkerNode,
  type WorkerNodeStatus,
  type WorkerRunFinish,
  type WorkerRunStart,
} from "@followville/company-os-core";
import type { CompletedWorkRecord } from "./types";

type Row = Record<string, unknown>;

export interface WorkerRegistration {
  workerId: string;
  organizationId: string;
  projectId: string;
  agentId: string;
  displayName: string;
  machineName: string;
  platform: string;
  provider: string;
  modelId: string | null;
  softwareVersion: string;
  capabilities: readonly Capability[];
  status: WorkerNodeStatus;
  currentTaskId?: string | null;
  currentRunId?: string | null;
  metadata: Readonly<Record<string, unknown>>;
}

function toNumber(value: unknown): number {
  return typeof value === "string" ? Number(value) : (value as number);
}

function taskFromRow(row: Row): Task {
  return TaskSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    goalId: row.goal_id,
    parentTaskId: row.parent_task_id,
    title: row.title,
    objective: row.objective,
    reason: row.reason,
    status: row.status,
    priority: toNumber(row.priority),
    riskLevel: row.risk_level,
    assignedAgentId: row.assigned_agent_id,
    reviewerAgentId: row.reviewer_agent_id,
    dependencyIds: row.dependency_ids,
    acceptanceCriteria: row.acceptance_criteria,
    allowedCapabilities: row.allowed_capabilities,
    repositoryScopes: row.repository_scopes,
    budgetUsdMicros: toNumber(row.budget_usd_micros),
    estimatedCostUsdMicros: toNumber(row.estimated_cost_usd_micros),
    actualCostUsdMicros: toNumber(row.actual_cost_usd_micros),
    retryCount: toNumber(row.retry_count),
    reviewCycleCount: toNumber(row.review_cycle_count),
    branchName: row.branch_name,
    expectedOutputs: row.expected_outputs,
    testRequirements: row.test_requirements,
    approvalRequired: row.approval_required,
    version: toNumber(row.version),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  });
}

function createControlPlaneClient(url: string, secretKey: string) {
  return createClient(url, secretKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

/**
 * Retries a control-plane call through transient network failures.
 *
 * A brief connectivity blip while appending an audit event previously threw
 * out of the worker mid-task, abandoning a leased task and a finished model
 * run. The control plane is remote, so treating every call as reliable is the
 * wrong default; a few seconds of retry costs nothing and saves the work.
 *
 * Only network-shaped failures are retried. A rejected write is a decision,
 * not a blip, and repeating it would hide the reason rather than fix it.
 */
export async function withRetry<T>(
  label: string,
  attempt: () => Promise<T>,
  attempts = 4,
): Promise<T> {
  let lastError: unknown;
  for (let tries = 0; tries < attempts; tries += 1) {
    try {
      return await attempt();
    } catch (error) {
      lastError = error;
      const message = (error as Error).message;
      if (
        !/fetch failed|ECONNRESET|ETIMEDOUT|socket hang up|network|EAI_AGAIN/i.test(
          message,
        )
      ) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, 500 * 2 ** tries));
    }
  }
  throw new Error(
    `${label} failed after ${attempts} attempts: ${(lastError as Error).message}`,
  );
}

/**
 * Database-backed work queue.
 *
 * Claiming uses `SELECT ... FOR UPDATE SKIP LOCKED` inside the leasing
 * function, so workers on different machines never receive the same task.
 * Every transition is conditional on still holding an unexpired lease, which
 * is what stops a worker that stalled and lost its task from later writing a
 * stale result over fresher work.
 */
export class SupabaseWorkQueue implements WorkQueue {
  constructor(
    private readonly client: ReturnType<typeof createControlPlaneClient>,
  ) {}

  static fromEnvironment(): SupabaseWorkQueue | null {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SECRET_KEY;
    if (!url || !key) {
      return null;
    }
    return new SupabaseWorkQueue(createControlPlaneClient(url, key));
  }

  async upsertWorker(worker: WorkerRegistration): Promise<WorkerNode> {
    const { data, error } = await this.client.rpc("company_os_upsert_worker", {
      payload: worker,
    });
    if (error !== null) {
      throw new Error(`worker registry update failed: ${error.message}`);
    }
    const row = data as Row;
    return WorkerNodeSchema.parse({
      workerId: row.worker_id,
      organizationId: row.organization_id,
      projectId: row.project_id,
      agentId: row.agent_id,
      displayName: row.display_name,
      machineName: row.machine_name,
      platform: row.platform,
      provider: row.provider,
      modelId: row.model_id,
      softwareVersion: row.software_version,
      capabilities: row.capabilities,
      status: row.status,
      currentTaskId: row.current_task_id,
      currentRunId: row.current_run_id,
      metadata: row.metadata,
      startedAt: row.started_at,
      lastSeenAt: row.last_seen_at,
    });
  }

  async leaseNextTask(
    workerId: string,
    leaseSeconds: number,
  ): Promise<LeasedTask | null> {
    const { data, error } = await this.client.rpc(
      "company_os_lease_next_compatible_task",
      {
        worker_id: workerId,
        lease_seconds: leaseSeconds,
      },
    );
    if (error !== null) {
      throw new Error(`lease failed: ${error.message}`);
    }
    if (data === null) {
      return null;
    }
    const row = data as Row;
    return {
      task: taskFromRow(row),
      leaseEpoch: toNumber(row.lease_epoch),
      leaseExpiresAt: String(row.lease_expires_at),
    };
  }

  async heartbeat(
    taskId: string,
    workerId: string,
    leaseSeconds: number,
  ): Promise<boolean> {
    const { data, error } = await this.client.rpc("company_os_heartbeat_task", {
      task_id: taskId,
      worker_id: workerId,
      lease_seconds: leaseSeconds,
    });
    if (error !== null) {
      throw new Error(`heartbeat failed: ${error.message}`);
    }
    return data === true;
  }

  async transition(
    taskId: string,
    workerId: string,
    nextStatus: Task["status"],
    releaseLease: boolean,
  ): Promise<boolean> {
    const { data, error } = await this.client.rpc(
      "company_os_transition_leased_task",
      {
        task_id: taskId,
        worker_id: workerId,
        next_status: nextStatus,
        release_lease: releaseLease,
      },
    );
    if (error !== null) {
      throw new Error(`transition failed: ${error.message}`);
    }
    return data === true;
  }

  async appendAuditEvent(event: AuditEvent): Promise<void> {
    await withRetry("audit append", async () => {
      const { error } = await this.client.rpc("company_os_append_audit_events", {
        events: [event],
      });
      if (error !== null) {
        throw new Error(`audit append failed: ${error.message}`);
      }
    });
  }

  async sendMessage(message: StructuredMessage): Promise<void> {
    await withRetry("structured message", async () => {
      const { error } = await this.client.rpc("company_os_send_message", {
        payload: message,
      });
      if (error !== null) {
        throw new Error(`structured message failed: ${error.message}`);
      }
    });
  }

  async startRun(run: WorkerRunStart): Promise<boolean> {
    const { data, error } = await this.client.rpc("company_os_start_worker_run", {
      payload: run,
    });
    if (error !== null) {
      throw new Error(`run start failed: ${error.message}`);
    }
    return data === true;
  }

  async finishRun(run: WorkerRunFinish): Promise<boolean> {
    const { data, error } = await this.client.rpc("company_os_finish_worker_run", {
      payload: run,
    });
    if (error !== null) {
      throw new Error(`run finish failed: ${error.message}`);
    }
    return data === true;
  }

  /** Requeues tasks whose worker stopped reporting. */
  async reclaimExpiredLeases(): Promise<number> {
    const { data, error } = await this.client.rpc(
      "company_os_reclaim_expired_leases",
    );
    if (error !== null) {
      throw new Error(`reclaim failed: ${error.message}`);
    }
    return Array.isArray(data) ? data.length : 0;
  }
}

export interface ReviewLease {
  task: Task;
  workerEvidence: readonly string[];
  workerSummary: string;
  filesChanged: readonly string[];
}

/**
 * Review-side queue operations.
 *
 * Kept on the same class so a single worker process can do both roles against
 * one connection. Independence is preserved by the database, which only hands
 * out review work whose assigned agent differs from the reviewer.
 */
export class SupabaseReviewQueue {
  constructor(
    private readonly client: ReturnType<typeof createControlPlaneClient>,
  ) {}

  static fromEnvironment(): SupabaseReviewQueue | null {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SECRET_KEY;
    if (!url || !key) {
      return null;
    }
    return new SupabaseReviewQueue(createControlPlaneClient(url, key));
  }

  async leaseNextReview(
    workerId: string,
    reviewerAgentId: string,
    leaseSeconds: number,
  ): Promise<Task | null> {
    const { data, error } = await this.client.rpc("company_os_lease_next_review", {
      p_worker_id: workerId,
      p_reviewer_agent_id: reviewerAgentId,
      p_lease_seconds: leaseSeconds,
    });
    if (error !== null) {
      throw new Error(`review lease failed: ${error.message}`);
    }
    return data === null ? null : taskFromRow(data as Row);
  }

  async recordReview(payload: {
    taskId: string;
    workerId: string;
    verdict: "approved_for_owner" | "changes_requested" | "deferred";
    auditEvents: readonly unknown[];
    completedWork?: CompletedWorkRecord;
    retryAfterSeconds?: number;
  }): Promise<boolean> {
    const { data, error } = await this.client.rpc("company_os_record_review", {
      payload,
    });
    if (error !== null) {
      throw new Error(`record review failed: ${error.message}`);
    }
    return data === true;
  }

  async retryFailedReview(payload: {
    taskId: string;
    expectedRunId: string;
    auditEvent: unknown;
  }): Promise<boolean> {
    const { data, error } = await this.client.rpc(
      "company_os_retry_failed_review",
      { payload },
    );
    if (error !== null) {
      throw new Error(`retry failed review failed: ${error.message}`);
    }
    return data === true;
  }
}
