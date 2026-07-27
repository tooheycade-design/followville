import { createClient } from "@supabase/supabase-js";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  AuditEventSchema,
  GoalSchema,
  EvidenceArtifactSchema,
  RunSchema,
  TaskSchema,
  type ApprovalRequest,
  type AuditEvent,
  type Goal,
  type Task,
} from "@followville/company-os-core";

import {
  emptyState,
  type ApprovalDecisionRecord,
  type CompanyRepository,
  type CompanyState,
  type CompletedWorkRecord,
  type GoalSimulationRecord,
  type HeldTaskDecision,
} from "./types";

/**
 * The client targets the default `public` schema, where the control-plane
 * functions live. The `company_ops` tables are deliberately not exposed to the
 * Data API and cannot be addressed directly.
 */
function createControlPlaneClient(url: string, secretKey: string) {
  return createClient(url, secretKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

type ControlPlaneClient = ReturnType<typeof createControlPlaneClient>;

type Row = Record<string, unknown>;

function toNumber(value: unknown): number {
  return typeof value === "string" ? Number(value) : (value as number);
}

function failOn(context: string, error: { message: string } | null): void {
  if (error !== null) {
    throw new Error(`Supabase ${context} failed: ${error.message}`);
  }
}

function goalFromRow(row: Row) {
  return GoalSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    createdByUserId: row.created_by_user_id,
    title: row.title,
    objective: row.objective,
    successDefinition: row.success_definition,
    constraints: row.constraints,
    riskLevel: row.risk_level,
    budgetUsdMicros: toNumber(row.budget_usd_micros),
    status: row.status,
    createdAt: row.created_at,
  });
}

function taskFromRow(row: Row) {
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

function runFromRow(row: Row) {
  return RunSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    taskId: row.task_id,
    agentId: row.agent_id,
    reviewerAgentId: row.reviewer_agent_id,
    trigger: row.trigger,
    mode: row.mode,
    status: row.status,
    modelProvider: row.model_provider,
    modelId: row.model_id,
    promptVersion: row.prompt_version,
    contextManifestDigest: row.context_manifest_digest,
    workspaceId: row.workspace_id,
    budgetReservationUsdMicros: toNumber(row.budget_reservation_usd_micros),
    actualCostUsdMicros: toNumber(row.actual_cost_usd_micros),
    retryCount: toNumber(row.retry_count),
    startedAt: row.started_at,
    completedAt: row.completed_at,
  });
}

function approvalRequestFromRow(row: Row, derivedStatus: string): ApprovalRequest {
  return ApprovalRequestSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    taskId: row.task_id,
    runId: row.run_id,
    requestedByType: row.requested_by_type,
    requestedById: row.requested_by_id,
    action: row.action,
    summary: row.summary,
    reason: row.reason,
    scopeDigest: row.scope_digest,
    commitSha: row.commit_sha,
    evidenceArtifactIds: row.evidence_artifact_ids,
    testsCompleted: row.tests_completed,
    riskLevel: row.risk_level,
    reversible: row.reversible,
    rollbackPlan: row.rollback_plan,
    estimatedCostUsdMicros: toNumber(row.estimated_cost_usd_micros),
    recommendation: row.recommendation,
    alternatives: row.alternatives,
    requiredApprovals: toNumber(row.required_approvals),
    requiredRole: row.required_role,
    status: derivedStatus,
    idempotencyKey: row.idempotency_key,
    createdAt: row.created_at,
    expiresAt: row.expires_at,
  });
}

function decisionFromRow(row: Row) {
  return ApprovalDecisionSchema.parse({
    id: row.id,
    approvalRequestId: row.approval_request_id,
    decidedByUserId: row.decided_by_user_id,
    decision: row.decision,
    comment: row.comment,
    requestScopeDigest: row.request_scope_digest,
    decidedAt: row.decided_at,
  });
}

function artifactFromRow(row: Row) {
  return EvidenceArtifactSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    taskId: row.task_id,
    runId: row.run_id,
    kind: row.kind,
    label: row.label,
    mediaType: row.media_type,
    sizeBytes: toNumber(row.size_bytes),
    sha256: row.sha256,
    location: row.location,
    createdByAgentId: row.created_by_agent_id,
    createdAt: row.created_at,
    expiresAt: row.expires_at,
  });
}

function auditFromRow(row: Row) {
  return AuditEventSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    taskId: row.task_id,
    runId: row.run_id,
    actorType: row.actor_type,
    actorId: row.actor_id,
    action: row.action,
    targetType: row.target_type,
    targetId: row.target_id,
    outcome: row.outcome,
    reason: row.reason,
    correlationId: row.correlation_id,
    idempotencyKey: row.idempotency_key,
    requestDigest: row.request_digest,
    resultDigest: row.result_digest,
    evidenceArtifactIds: row.evidence_artifact_ids,
    createdAt: row.created_at,
  });
}


/**
 * Shared-state backend for the Company OS control plane.
 *
 * All access goes through transactional `SECURITY DEFINER` functions in
 * `public`. The `company_ops` tables are not exposed to the Data API and
 * cannot be reached directly, and PostgREST has no cross-request transaction,
 * so a multi-table write such as a goal simulation must happen inside one
 * function call or it could leave a partial record.
 *
 * The database owns its invariants. `approval_requests` may only be inserted
 * as pending and cannot be updated, so status is read from the
 * `approval_request_states` view and a decision is recorded solely by
 * inserting a decision row. A trigger independently re-checks pending state,
 * expiry, scope digest, prior terminal decisions, and the decider's active
 * membership in the required role, so the policy kernel's answer is verified
 * rather than trusted.
 */
export class SupabaseCompanyRepository implements CompanyRepository {
  readonly backend = "supabase" as const;

  constructor(private readonly client: ControlPlaneClient) {}

  static fromEnvironment(): SupabaseCompanyRepository | null {
    const url = process.env.SUPABASE_URL;
    const key = process.env.SUPABASE_SECRET_KEY;
    if (
      url === undefined ||
      key === undefined ||
      url.length === 0 ||
      key.length === 0
    ) {
      return null;
    }
    return new SupabaseCompanyRepository(createControlPlaneClient(url, key));
  }

  async load(): Promise<CompanyState> {
    const { data, error } = await this.client.rpc("company_os_load");
    failOn("company_os_load", error);

    const payload = (data ?? {}) as Record<string, Row[]>;
    const rows = (key: string): Row[] => payload[key] ?? [];

    const derived = new Map<string, string>(
      rows("approval_states").map((row) => [
        String(row.approval_request_id),
        String(row.status),
      ]),
    );

    const state = emptyState();
    state.goals = rows("goals").map(goalFromRow);
    state.tasks = rows("tasks").map(taskFromRow);
    state.runs = rows("runs").map(runFromRow);
    state.approvalRequests = rows("approval_requests").map((row) =>
      approvalRequestFromRow(row, derived.get(String(row.id)) ?? "pending"),
    );
    state.approvalDecisions = rows("approval_decisions").map(decisionFromRow);
    state.evidenceArtifacts = rows("evidence_artifacts").map(artifactFromRow);
    state.auditEvents = rows("audit_events").map(auditFromRow);
    return state;
  }

  async appendGoalSimulation(record: GoalSimulationRecord): Promise<void> {
    const { error } = await this.client.rpc("company_os_record_goal_simulation", {
      payload: {
        goal: record.goal,
        task: record.task,
        run: record.run,
        approvalRequest: record.approvalRequest,
        auditEvents: record.auditEvents,
      },
    });
    failOn("company_os_record_goal_simulation", error);
  }

  async appendApprovalDecision(record: ApprovalDecisionRecord): Promise<void> {
    const { error } = await this.client.rpc(
      "company_os_record_approval_decision",
      {
        payload: {
          decision: record.decision,
          updatedTask: record.updatedTask,
          auditEvent: record.auditEvent,
        },
      },
    );
    failOn("company_os_record_approval_decision", error);
  }

  async appendInitiative(goal: Goal, tasks: readonly Task[]): Promise<void> {
    const { error } = await this.client.rpc("company_os_record_initiative", {
      payload: { goal, tasks },
    });
    failOn("company_os_record_initiative", error);
  }

  async appendAuditEvent(event: AuditEvent): Promise<void> {
    const { error } = await this.client.rpc("company_os_append_audit_events", {
      events: [event],
    });
    failOn("company_os_append_audit_events", error);
  }

  async appendCompletedWork(record: CompletedWorkRecord): Promise<boolean> {
    const { data, error } = await this.client.rpc(
      "company_os_record_completed_work",
      {
        payload: {
          approvalRequest: record.approvalRequest,
          artifacts: record.artifacts,
        },
      },
    );
    failOn("company_os_record_completed_work", error);
    return Boolean((data as { created?: boolean } | null)?.created);
  }

  async decideHeldTask(decision: HeldTaskDecision): Promise<string> {
    const { data, error } = await this.client.rpc("company_os_decide_held_task", {
      payload: decision,
    });
    failOn("company_os_decide_held_task", error);
    return String((data as { status?: string } | null)?.status ?? "unknown");
  }
}
