import { createClient } from "@supabase/supabase-js";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  AuditEventSchema,
  GoalSchema,
  RunSchema,
  TaskSchema,
  type ApprovalRequest,
  type AuditEvent,
} from "@followville/company-os-core";

import {
  emptyState,
  type ApprovalDecisionRecord,
  type CompanyRepository,
  type CompanyState,
  type GoalSimulationRecord,
} from "./types";

const SCHEMA = "company_ops";

/**
 * The client is schema-parameterized, so the private schema produces a
 * different type than the default public one.
 */
function createCompanyOpsClient(url: string, secretKey: string) {
  return createClient(url, secretKey, {
    db: { schema: SCHEMA },
    auth: { persistSession: false, autoRefreshToken: false },
  });
}

type CompanyOpsClient = ReturnType<typeof createCompanyOpsClient>;

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

function auditToRow(event: AuditEvent): Row {
  return {
    id: event.id,
    organization_id: event.organizationId,
    project_id: event.projectId,
    task_id: event.taskId,
    run_id: event.runId,
    actor_type: event.actorType,
    actor_id: event.actorId,
    action: event.action,
    target_type: event.targetType,
    target_id: event.targetId,
    outcome: event.outcome,
    reason: event.reason,
    correlation_id: event.correlationId,
    idempotency_key: event.idempotencyKey,
    request_digest: event.requestDigest,
    result_digest: event.resultDigest,
    evidence_artifact_ids: event.evidenceArtifactIds,
    created_at: event.createdAt,
  };
}

/**
 * Shared-state backend for the Company OS control plane.
 *
 * The database owns the invariants. `approval_requests` may only be inserted
 * as pending and cannot be updated, so approval status is read from the
 * `approval_request_states` view and a decision is recorded solely by
 * inserting an `approval_decisions` row. A database trigger independently
 * re-checks the pending state, expiry, scope digest, prior terminal decisions,
 * and the decider's active membership in the required role — so the policy
 * kernel's answer is verified rather than trusted. Task updates pass a second
 * trigger that validates the transition and, for approved or merged, requires
 * a genuinely approved request.
 */
export class SupabaseCompanyRepository implements CompanyRepository {
  readonly backend = "supabase" as const;

  constructor(private readonly client: CompanyOpsClient) {}

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
    return new SupabaseCompanyRepository(createCompanyOpsClient(url, key));
  }

  async load(): Promise<CompanyState> {
    const state = emptyState();
    const from = (table: string) => this.client.from(table).select("*");

    const [goals, tasks, runs, requests, states, decisions, audits] =
      await Promise.all([
        from("goals").order("created_at"),
        from("tasks").order("created_at"),
        from("runs").order("created_at"),
        from("approval_requests").order("created_at"),
        from("approval_request_states"),
        from("approval_decisions").order("decided_at"),
        from("audit_events").order("sequence"),
      ]);

    failOn("goals read", goals.error);
    failOn("tasks read", tasks.error);
    failOn("runs read", runs.error);
    failOn("approval_requests read", requests.error);
    failOn("approval_request_states read", states.error);
    failOn("approval_decisions read", decisions.error);
    failOn("audit_events read", audits.error);

    const derived = new Map<string, string>(
      (states.data ?? []).map((row) => [
        String((row as Row).approval_request_id),
        String((row as Row).status),
      ]),
    );

    state.goals = (goals.data ?? []).map((row) => goalFromRow(row as Row));
    state.tasks = (tasks.data ?? []).map((row) => taskFromRow(row as Row));
    state.runs = (runs.data ?? []).map((row) => runFromRow(row as Row));
    state.approvalRequests = (requests.data ?? []).map((row) =>
      approvalRequestFromRow(
        row as Row,
        derived.get(String((row as Row).id)) ?? "pending",
      ),
    );
    state.approvalDecisions = (decisions.data ?? []).map((row) =>
      decisionFromRow(row as Row),
    );
    state.auditEvents = (audits.data ?? []).map((row) =>
      auditFromRow(row as Row),
    );
    return state;
  }

  async appendGoalSimulation(record: GoalSimulationRecord): Promise<void> {
    const { goal, task, run, approvalRequest } = record;

    failOn(
      "goal insert",
      (
        await this.client.from("goals").insert({
          id: goal.id,
          organization_id: goal.organizationId,
          project_id: goal.projectId,
          created_by_user_id: goal.createdByUserId,
          title: goal.title,
          objective: goal.objective,
          success_definition: goal.successDefinition,
          constraints: goal.constraints,
          risk_level: goal.riskLevel,
          budget_usd_micros: goal.budgetUsdMicros,
          status: goal.status,
          created_at: goal.createdAt,
        })
      ).error,
    );

    failOn(
      "task insert",
      (
        await this.client.from("tasks").insert({
          id: task.id,
          organization_id: task.organizationId,
          project_id: task.projectId,
          goal_id: task.goalId,
          parent_task_id: task.parentTaskId,
          title: task.title,
          objective: task.objective,
          reason: task.reason,
          status: task.status,
          priority: task.priority,
          risk_level: task.riskLevel,
          assigned_agent_id: task.assignedAgentId,
          reviewer_agent_id: task.reviewerAgentId,
          dependency_ids: task.dependencyIds,
          acceptance_criteria: task.acceptanceCriteria,
          allowed_capabilities: task.allowedCapabilities,
          repository_scopes: task.repositoryScopes,
          budget_usd_micros: task.budgetUsdMicros,
          estimated_cost_usd_micros: task.estimatedCostUsdMicros,
          actual_cost_usd_micros: task.actualCostUsdMicros,
          retry_count: task.retryCount,
          review_cycle_count: task.reviewCycleCount,
          branch_name: task.branchName,
          expected_outputs: task.expectedOutputs,
          test_requirements: task.testRequirements,
          approval_required: task.approvalRequired,
          version: task.version,
          created_at: task.createdAt,
          updated_at: task.updatedAt,
        })
      ).error,
    );

    failOn(
      "run insert",
      (
        await this.client.from("runs").insert({
          id: run.id,
          organization_id: run.organizationId,
          project_id: run.projectId,
          task_id: run.taskId,
          agent_id: run.agentId,
          reviewer_agent_id: run.reviewerAgentId,
          trigger: run.trigger,
          mode: run.mode,
          status: run.status,
          model_provider: run.modelProvider,
          model_id: run.modelId,
          prompt_version: run.promptVersion,
          context_manifest_digest: run.contextManifestDigest,
          workspace_id: run.workspaceId,
          budget_reservation_usd_micros: run.budgetReservationUsdMicros,
          actual_cost_usd_micros: run.actualCostUsdMicros,
          retry_count: run.retryCount,
          started_at: run.startedAt,
          completed_at: run.completedAt,
        })
      ).error,
    );

    failOn(
      "approval_request insert",
      (
        await this.client.from("approval_requests").insert({
          id: approvalRequest.id,
          organization_id: approvalRequest.organizationId,
          project_id: approvalRequest.projectId,
          task_id: approvalRequest.taskId,
          run_id: approvalRequest.runId,
          requested_by_type: approvalRequest.requestedByType,
          requested_by_id: approvalRequest.requestedById,
          action: approvalRequest.action,
          summary: approvalRequest.summary,
          reason: approvalRequest.reason,
          scope_digest: approvalRequest.scopeDigest,
          commit_sha: approvalRequest.commitSha,
          evidence_artifact_ids: approvalRequest.evidenceArtifactIds,
          tests_completed: approvalRequest.testsCompleted,
          risk_level: approvalRequest.riskLevel,
          reversible: approvalRequest.reversible,
          rollback_plan: approvalRequest.rollbackPlan,
          estimated_cost_usd_micros: approvalRequest.estimatedCostUsdMicros,
          recommendation: approvalRequest.recommendation,
          alternatives: approvalRequest.alternatives,
          required_approvals: approvalRequest.requiredApprovals,
          required_role: approvalRequest.requiredRole,
          idempotency_key: approvalRequest.idempotencyKey,
          created_at: approvalRequest.createdAt,
          expires_at: approvalRequest.expiresAt,
        })
      ).error,
    );

    await this.#insertAudits(record.auditEvents);
  }

  async appendApprovalDecision(record: ApprovalDecisionRecord): Promise<void> {
    const { decision, updatedTask } = record;

    failOn(
      "approval_decision insert",
      (
        await this.client.from("approval_decisions").insert({
          id: decision.id,
          approval_request_id: decision.approvalRequestId,
          decided_by_user_id: decision.decidedByUserId,
          decision: decision.decision,
          comment: decision.comment,
          request_scope_digest: decision.requestScopeDigest,
        })
      ).error,
    );

    if (updatedTask !== null) {
      failOn(
        "task status update",
        (
          await this.client
            .from("tasks")
            .update({ status: updatedTask.status })
            .eq("id", updatedTask.id)
        ).error,
      );
    }

    await this.#insertAudits([record.auditEvent]);
  }

  async appendAuditEvent(event: AuditEvent): Promise<void> {
    await this.#insertAudits([event]);
  }

  async #insertAudits(events: readonly AuditEvent[]): Promise<void> {
    if (events.length === 0) {
      return;
    }
    failOn(
      "audit_events insert",
      (await this.client.from("audit_events").insert(events.map(auditToRow)))
        .error,
    );
  }
}
