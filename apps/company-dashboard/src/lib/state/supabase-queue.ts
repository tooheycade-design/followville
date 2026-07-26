import { createClient } from "@supabase/supabase-js";

import {
  TaskSchema,
  type AuditEvent,
  type LeasedTask,
  type Task,
  type WorkQueue,
} from "@followville/company-os-core";

type Row = Record<string, unknown>;

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

  async leaseNextTask(
    workerId: string,
    leaseSeconds: number,
  ): Promise<LeasedTask | null> {
    const { data, error } = await this.client.rpc("company_os_lease_next_task", {
      worker_id: workerId,
      lease_seconds: leaseSeconds,
    });
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
    const { error } = await this.client.rpc("company_os_append_audit_events", {
      events: [event],
    });
    if (error !== null) {
      throw new Error(`audit append failed: ${error.message}`);
    }
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
