import { createClient } from "@supabase/supabase-js";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  AuditEventSchema,
  GoalSchema,
  MemoryRecordSchema,
  EvidenceArtifactSchema,
  RunSchema,
  SocialContentPacketSchema,
  StructuredMessageSchema,
  TaskSchema,
  WorkerNodeSchema,
  type ApprovalRequest,
  type AuditEvent,
  type Goal,
  type Task,
  type SocialContentPacket,
} from "@followville/company-os-core";

import {
  emptyState,
  type ApprovalDecisionRecord,
  type CompanyRepository,
  type CompanyState,
  type GoalSimulationRecord,
  type HeldTaskDecision,
  HostedControlTickSchema,
  IntegrationSourceSchema,
  OperationalAlertSchema,
  OperationalSnapshotSchema,
  OwnerNotificationSchema,
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

export function runFromRow(row: Row) {
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

export function artifactFromRow(row: Row) {
  return EvidenceArtifactSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    goalId: row.goal_id,
    taskId: row.task_id,
    runId: row.run_id,
    kind: row.kind,
    label: row.label,
    mediaType: row.media_type,
    sizeBytes: toNumber(row.size_bytes),
    sha256: row.sha256,
    location: row.location,
    visibility: row.visibility,
    containsSensitiveData: row.contains_sensitive_data,
    safeToDisplay: row.safe_to_display,
    retentionPolicy: row.retention_policy,
    createdByAgentId: row.created_by_agent_id,
    createdAt: row.created_at,
    expiresAt: row.expires_at,
  });
}

export function messageFromRow(row: Row) {
  const payload = (row.payload ?? {}) as Row;
  return StructuredMessageSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    goalId: row.goal_id,
    taskId: row.task_id,
    threadId: row.thread_id,
    senderType: row.sender_type,
    senderId: row.sender_id,
    recipientType: row.recipient_type,
    recipientId: row.recipient_id,
    type: row.message_type,
    priority: row.priority,
    requestedAction: payload.requestedAction ?? null,
    contextSummary: payload.contextSummary,
    evidenceArtifactIds: payload.evidenceArtifactIds ?? [],
    expectedOutput: payload.expectedOutput ?? null,
    deadlineAt: row.deadline_at,
    confidence: row.confidence,
    estimatedCostUsdMicros: 0,
    relatedFiles: payload.relatedFiles ?? [],
    relatedCommits: payload.relatedCommits ?? [],
    status:
      row.expires_at !== null &&
      Date.parse(String(row.expires_at)) <= Date.now() &&
      row.status !== "resolved"
        ? "expired"
        : row.status,
    fingerprint: row.fingerprint,
    createdAt: row.created_at,
    expiresAt: row.expires_at,
  });
}

export function workerFromRow(row: Row) {
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

export function contentPacketFromRow(row: Row): SocialContentPacket {
  return SocialContentPacketSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    createdByUserId: row.created_by_user_id,
    createdByAgentId: row.created_by_agent_id,
    status: row.status,
    objective: row.objective,
    recommendation: row.recommendation,
    milestone: row.milestone,
    sourceSnapshotIds: row.source_snapshot_ids,
    sourceDigest: row.source_digest,
    engagementDataStatus: row.engagement_data_status,
    dataGaps: row.data_gaps,
    priorContentNotes: row.prior_content_notes,
    concepts: row.concepts,
    selectedConceptId: row.selected_concept_id,
    productionGoalId: row.production_goal_id,
    productionTaskId: row.production_task_id,
    publishApprovalRequestId: row.publish_approval_request_id,
    version: toNumber(row.version),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
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

function controlTickFromRow(row: Row) {
  return HostedControlTickSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    tickType: row.tick_type,
    timeBucket: row.time_bucket,
    metrics: row.metrics,
    createdAt: row.created_at,
  });
}

function notificationFromRow(row: Row) {
  return OwnerNotificationSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    notificationType: row.notification_type,
    targetType: row.target_type,
    targetId: row.target_id,
    title: row.title,
    detail: row.detail,
    severity: row.severity,
    deliveryDay: row.delivery_day,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  });
}

export function integrationSourceFromRow(row: Row) {
  return IntegrationSourceSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    sourceKey: row.source_key,
    displayName: row.display_name,
    sourceType: row.source_type,
    accessMode: row.access_mode,
    status: row.status,
    setupRequirement: row.setup_requirement,
    configuration: row.configuration,
    lastCheckedAt: row.last_checked_at,
    lastSuccessAt: row.last_success_at,
    lastErrorCode: row.last_error_code,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  });
}

export function operationalSnapshotFromRow(row: Row) {
  return OperationalSnapshotSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    sourceId: row.source_id,
    capturedAt: row.captured_at,
    metrics: row.metrics,
    evidenceReference: row.evidence_reference,
    sourceDigest: row.source_digest,
    idempotencyKey: row.idempotency_key,
    confidence: row.confidence,
    freshnessUntil: row.freshness_until,
    createdByType: row.created_by_type,
    createdById: row.created_by_id,
    createdAt: row.created_at,
  });
}

export function operationalAlertFromRow(row: Row) {
  return OperationalAlertSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    sourceId: row.source_id,
    snapshotId: row.snapshot_id,
    alertKind: row.alert_kind,
    severity: row.severity,
    title: row.title,
    detail: row.detail,
    recommendedAction: row.recommended_action,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  });
}

export function memoryFromRow(row: Row) {
  return MemoryRecordSchema.parse({
    id: row.id,
    organizationId: row.organization_id,
    projectId: row.project_id,
    type: row.memory_type,
    category: row.category,
    subject: row.subject,
    body: row.body,
    sourceType: row.source_type,
    sourceReference: row.source_reference,
    sourceDigest: row.source_digest,
    confidence: row.confidence,
    status: row.status,
    version: toNumber(row.version),
    tags: row.tags,
    audienceRoles: row.audience_roles,
    createdByType: row.created_by_type,
    createdById: row.created_by_id,
    createdAt: row.created_at,
    expiresAt: row.expires_at,
    supersededById: row.superseded_by_id,
    supersedesId: row.supersedes_id,
    correctionReason: row.correction_reason,
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
    const [
      { data, error },
      { data: operationsData, error: operationsError },
      { data: contentData, error: contentError },
    ] = await Promise.all([
      this.client.rpc("company_os_load"),
      this.client.rpc("company_os_load_operations"),
      this.client.rpc("company_os_load_content"),
    ]);
    failOn("company_os_load", error);
    failOn("company_os_load_operations", operationsError);
    failOn("company_os_load_content", contentError);

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
    state.messages = rows("messages").map(messageFromRow);
    state.memories = rows("memories").map(memoryFromRow);
    state.controlTicks = rows("control_ticks").map(controlTickFromRow);
    state.ownerNotifications = rows("owner_notifications").map(
      notificationFromRow,
    );
    const operations = (operationsData ?? {}) as Record<string, Row[]>;
    state.integrationSources = (operations.sources ?? []).map(
      integrationSourceFromRow,
    );
    state.operationalSnapshots = (operations.snapshots ?? []).map(
      operationalSnapshotFromRow,
    );
    state.operationalAlerts = (operations.alerts ?? []).map(
      operationalAlertFromRow,
    );
    const content = (contentData ?? {}) as Record<string, Row[]>;
    state.contentPackets = (content.content_packets ?? []).map(
      contentPacketFromRow,
    );
    state.workers = rows("worker_nodes").map(workerFromRow);
    state.approvalRequests = rows("approval_requests").map((row) =>
      approvalRequestFromRow(row, derived.get(String(row.id)) ?? "pending"),
    );
    state.approvalDecisions = rows("approval_decisions").map(decisionFromRow);
    state.evidenceArtifacts = rows("evidence_artifacts").map(artifactFromRow);
    state.auditEvents = rows("audit_events").map(auditFromRow);
    return state;
  }

  async recordOperationalSnapshot(
    input: Parameters<CompanyRepository["recordOperationalSnapshot"]>[0],
  ) {
    const { data, error } = await this.client.rpc(
      "company_os_record_operational_snapshot",
      { payload: input },
    );
    failOn("company_os_record_operational_snapshot", error);
    return operationalSnapshotFromRow(data as Row);
  }

  async recordOperationalFailure(
    sourceKey: string,
    errorCode: string,
  ): Promise<void> {
    const { error } = await this.client.rpc(
      "company_os_record_operational_failure",
      { p_source_key: sourceKey, p_error_code: errorCode },
    );
    failOn("company_os_record_operational_failure", error);
  }

  async recordContentPacket(
    packet: SocialContentPacket,
  ): Promise<SocialContentPacket> {
    const { data, error } = await this.client.rpc(
      "company_os_record_content_packet",
      { payload: packet },
    );
    failOn("company_os_record_content_packet", error);
    return contentPacketFromRow(data as Row);
  }

  async retrieveMemories(
    role: Parameters<CompanyRepository["retrieveMemories"]>[0],
    query: string,
    tags: readonly string[] = [],
    limit = 8,
  ) {
    const { data, error } = await this.client.rpc("company_os_retrieve_memories", {
      p_role: role,
      p_query: query,
      p_tags: tags,
      p_limit: limit,
    });
    failOn("company_os_retrieve_memories", error);
    return ((data ?? []) as Row[]).map(memoryFromRow);
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

  async decideHeldTask(decision: HeldTaskDecision): Promise<string> {
    const { data, error } = await this.client.rpc("company_os_decide_held_task", {
      payload: decision,
    });
    failOn("company_os_decide_held_task", error);
    return String((data as { status?: string } | null)?.status ?? "unknown");
  }
}
