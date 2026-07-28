import { z } from "zod";

export const IdentifierSchema = z.string().uuid();
export const SlugSchema = z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
export const IsoDateTimeSchema = z.string().datetime({ offset: true });
export const UsdMicrosSchema = z.number().int().nonnegative().safe();

export const ActorTypeSchema = z.enum(["human", "agent", "system"]);
export const ConfidenceSchema = z.enum([
  "confirmed",
  "likely",
  "uncertain",
  "requires_human_verification",
]);
export const RiskLevelSchema = z.enum(["low", "medium", "high", "critical"]);
export const EnvironmentSchema = z.enum([
  "local",
  "preview",
  "staging",
  "production",
]);
export const ModelClassSchema = z.enum([
  "deterministic",
  "economy",
  "standard",
  "advanced",
  "independent_review",
]);

export const CapabilitySchema = z.enum([
  "repository_read",
  "repository_write",
  "git_branch_create",
  // A recoverable local commit the runtime makes on a task's own review
  // branch, so finished work outlives the disposable worktree it was made in.
  // Separate from `git_commit` because they carry different risk: this one
  // cannot leave the machine, while an agent choosing to commit is a step on
  // the path to publication. Naming both `git_commit` made the policy read as
  // a contradiction — a safe retention action gated like a dangerous one.
  "git_checkpoint",
  "git_commit",
  "git_push_review_branch",
  "pull_request_create",
  "test_execute",
  "browser_preview",
  "blender_preview",
  "database_read_development",
  "database_migration_prepare",
  "model_invoke",
  "memory_write",
  "message_send",
  "production_merge",
  "production_deploy",
  "production_database_write",
  "canonical_world_growth",
  "public_communication",
  "social_publish",
  "payment_charge",
  "price_change",
  "destructive_delete",
]);

export const RepositoryScopeSchema = z
  .object({
    repository: z.string().min(1),
    allowedPathPrefixes: z.array(z.string().min(1)).min(1),
    deniedPathPrefixes: z.array(z.string().min(1)).default([]),
    environments: z.array(EnvironmentSchema).min(1),
  })
  .strict();

export const AgentProfileSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    slug: SlugSchema,
    name: z.string().min(1).max(100),
    role: z.string().min(1).max(100),
    description: z.string().min(1),
    responsibilities: z.array(z.string().min(1)).min(1),
    capabilities: z.array(CapabilitySchema),
    prohibitedCapabilities: z.array(CapabilitySchema),
    repositoryScopes: z.array(RepositoryScopeSchema),
    preferredModelClass: ModelClassSchema,
    fallbackModelClass: ModelClassSchema,
    maxTaskCostUsdMicros: UsdMicrosSchema,
    maxDailyCostUsdMicros: UsdMicrosSchema,
    maxRunDurationSeconds: z.number().int().positive().max(86_400),
    maxRetries: z.number().int().nonnegative().max(10),
    maxConcurrentRuns: z.number().int().positive().max(20),
    requiresHumanApprovalFor: z.array(CapabilitySchema),
    escalationRules: z.array(z.string().min(1)),
    promptVersion: z.string().min(1),
    active: z.boolean(),
  })
  .strict()
  .superRefine((profile, context) => {
    const capabilities = new Set(profile.capabilities);
    for (const prohibited of profile.prohibitedCapabilities) {
      if (capabilities.has(prohibited)) {
        context.addIssue({
          code: "custom",
          message: `Capability ${prohibited} cannot be both allowed and prohibited`,
          path: ["prohibitedCapabilities"],
        });
      }
    }
  });

export const WorkerNodeStatusSchema = z.enum([
  "online",
  "draining",
  "offline",
  "error",
]);

export const WorkerNodeSchema = z
  .object({
    workerId: z.string().min(1).max(160),
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    agentId: IdentifierSchema,
    displayName: z.string().min(1).max(120),
    machineName: z.string().min(1).max(120),
    platform: z.string().min(1).max(120),
    provider: z.string().min(1).max(80),
    modelId: z.string().min(1).max(160).nullable(),
    softwareVersion: z.string().min(1).max(80),
    capabilities: z.array(CapabilitySchema),
    status: WorkerNodeStatusSchema,
    currentTaskId: IdentifierSchema.nullable(),
    currentRunId: IdentifierSchema.nullable(),
    metadata: z.record(z.string(), z.unknown()),
    startedAt: IsoDateTimeSchema,
    lastSeenAt: IsoDateTimeSchema,
  })
  .strict();

export type WorkerNodeStatus = z.infer<typeof WorkerNodeStatusSchema>;
export type WorkerNode = z.infer<typeof WorkerNodeSchema>;

export const TaskStatusSchema = z.enum([
  "proposed",
  "planned",
  "approved_for_work",
  "queued",
  "assigned",
  "in_progress",
  "blocked",
  "awaiting_review",
  "changes_requested",
  "awaiting_human_approval",
  "approved",
  "rejected",
  "merged",
  "deployed",
  "canceled",
  "failed",
]);

export const AcceptanceCriterionSchema = z
  .object({
    id: IdentifierSchema,
    description: z.string().min(1),
    verificationMethod: z.string().min(1),
    required: z.boolean(),
  })
  .strict();

export const TaskSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    goalId: IdentifierSchema,
    parentTaskId: IdentifierSchema.nullable(),
    title: z.string().min(1).max(180),
    objective: z.string().min(1),
    reason: z.string().min(1),
    status: TaskStatusSchema,
    priority: z.number().int().min(0).max(100),
    riskLevel: RiskLevelSchema,
    assignedAgentId: IdentifierSchema.nullable(),
    reviewerAgentId: IdentifierSchema.nullable(),
    dependencyIds: z.array(IdentifierSchema),
    acceptanceCriteria: z.array(AcceptanceCriterionSchema).min(1),
    allowedCapabilities: z.array(CapabilitySchema),
    repositoryScopes: z.array(RepositoryScopeSchema),
    budgetUsdMicros: UsdMicrosSchema,
    estimatedCostUsdMicros: UsdMicrosSchema,
    actualCostUsdMicros: UsdMicrosSchema,
    retryCount: z.number().int().nonnegative(),
    reviewCycleCount: z.number().int().nonnegative(),
    branchName: z.string().nullable(),
    expectedOutputs: z.array(z.string().min(1)).min(1),
    testRequirements: z.array(z.string().min(1)),
    approvalRequired: z.boolean(),
    version: z.number().int().positive(),
    createdAt: IsoDateTimeSchema,
    updatedAt: IsoDateTimeSchema,
  })
  .strict()
  .superRefine((task, context) => {
    if (
      task.assignedAgentId !== null &&
      task.assignedAgentId === task.reviewerAgentId
    ) {
      context.addIssue({
        code: "custom",
        message: "Assigned agent and reviewer must be different",
        path: ["reviewerAgentId"],
      });
    }
  });

export const GoalSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    createdByUserId: IdentifierSchema,
    title: z.string().min(1).max(180),
    objective: z.string().min(1),
    successDefinition: z.string().min(1),
    constraints: z.array(z.string().min(1)),
    riskLevel: RiskLevelSchema,
    budgetUsdMicros: UsdMicrosSchema,
    status: z.enum([
      "draft",
      "planning",
      "active",
      "awaiting_approval",
      "completed",
      "rejected",
      "canceled",
    ]),
    createdAt: IsoDateTimeSchema,
  })
  .strict();

export const MessageTypeSchema = z.enum([
  "task_request",
  "task_assignment",
  "clarification_request",
  "status_update",
  "blocker",
  "evidence",
  "recommendation",
  "review_request",
  "changes_requested",
  "approval_request",
  "budget_request",
  "incident",
  "task_complete",
  "task_failed",
  "handoff",
  "escalation",
  "decision_needed",
]);

export const StructuredMessageSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    taskId: IdentifierSchema.nullable(),
    threadId: IdentifierSchema,
    senderType: ActorTypeSchema,
    senderId: IdentifierSchema,
    recipientType: ActorTypeSchema,
    recipientId: IdentifierSchema,
    type: MessageTypeSchema,
    priority: z.enum(["low", "normal", "high", "urgent"]),
    requestedAction: z.string().nullable(),
    contextSummary: z.string().min(1),
    evidenceArtifactIds: z.array(IdentifierSchema),
    expectedOutput: z.string().nullable(),
    deadlineAt: IsoDateTimeSchema.nullable(),
    confidence: ConfidenceSchema,
    estimatedCostUsdMicros: UsdMicrosSchema,
    relatedFiles: z.array(z.string()),
    relatedCommits: z.array(z.string()),
    status: z.enum(["created", "delivered", "read", "resolved", "expired"]),
    fingerprint: z.string().min(16),
    createdAt: IsoDateTimeSchema,
    expiresAt: IsoDateTimeSchema.nullable(),
  })
  .strict();

/**
 * Something an agent produced that a human may want to look at.
 *
 * `evidenceArtifactIds` existed on runs, approvals, and audit events from the
 * start and was always empty, because there was nowhere to put an artifact.
 * An approval packet could say a screenshot had been taken and point at
 * nothing.
 *
 * Artifacts live in the task's own checkpoint commit rather than in a separate
 * object store. The runtime already records finished work on an `agent/task-*`
 * branch, so a screenshot committed alongside the change is durable, shared
 * through the same remote as everything else, and retrievable with
 * `git show <commit>:<path>`. `location` is a union so a future object store
 * can be added without rewriting what already exists.
 */
export const ArtifactKindSchema = z.enum([
  "screenshot",
  "render",
  "recording",
  "log",
  "patch",
  "report",
  "trace",
  "model",
  "performance",
]);

const StorageBucketSchema = z.string().regex(/^[a-z0-9][a-z0-9._-]{1,62}$/);
const StorageObjectPathSchema = z
  .string()
  .min(1)
  .max(1_024)
  .refine(
    (value) =>
      !value.startsWith("/") &&
      !value.includes("\\") &&
      !value.split("/").some((part) => part === "" || part === ".."),
    "Storage object paths must be relative, normalized, and traversal-free",
  );

export const ArtifactLocationSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("git"),
      commitSha: z.string().regex(/^[0-9a-f]{7,64}$/),
      repositoryPath: z.string().min(1),
    })
    .strict(),
  z
    .object({
      kind: z.literal("inline"),
      /** Small text held directly, such as a diff. */
      text: z.string(),
    })
    .strict(),
  z
    .object({
      kind: z.literal("object"),
      provider: z.literal("supabase_storage"),
      bucket: StorageBucketSchema,
      objectPath: StorageObjectPathSchema,
    })
    .strict(),
]);

export const ArtifactVisibilitySchema = z.enum([
  "owner_only",
  "company_internal",
  "public",
]);
export const ArtifactRetentionPolicySchema = z.enum([
  "approval_record",
  "temporary_preview",
  "permanent",
]);

export const EvidenceArtifactSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    goalId: IdentifierSchema,
    taskId: IdentifierSchema,
    runId: IdentifierSchema.nullable(),
    kind: ArtifactKindSchema,
    /** What a human should call this when deciding. */
    label: z.string().min(1).max(200),
    mediaType: z.string().min(1).max(120),
    sizeBytes: z.number().int().nonnegative(),
    sha256: z.string().regex(/^[0-9a-f]{64}$/),
    location: ArtifactLocationSchema,
    visibility: ArtifactVisibilitySchema,
    containsSensitiveData: z.boolean(),
    safeToDisplay: z.boolean(),
    retentionPolicy: ArtifactRetentionPolicySchema,
    createdByAgentId: IdentifierSchema,
    createdAt: IsoDateTimeSchema,
    /**
     * When this may be discarded. Null means keep it as long as its task
     * exists — an approval's evidence should not expire before the decision
     * it supports can be audited.
     */
    expiresAt: IsoDateTimeSchema.nullable(),
  })
  .strict()
  .superRefine((artifact, context) => {
    if (artifact.containsSensitiveData && artifact.safeToDisplay) {
      context.addIssue({
        code: "custom",
        message: "Sensitive artifacts cannot be marked safe for inline display",
        path: ["safeToDisplay"],
      });
    }
    if (artifact.location.kind === "object" && artifact.runId === null) {
      context.addIssue({
        code: "custom",
        message: "Object-backed artifacts must be pinned to a run",
        path: ["runId"],
      });
    }
  });

export type ArtifactKind = z.infer<typeof ArtifactKindSchema>;
export type ArtifactLocation = z.infer<typeof ArtifactLocationSchema>;
export type EvidenceArtifact = z.infer<typeof EvidenceArtifactSchema>;

export const RunSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    taskId: IdentifierSchema,
    agentId: IdentifierSchema,
    reviewerAgentId: IdentifierSchema.nullable(),
    trigger: z.enum(["human", "event", "schedule", "retry", "message"]),
    mode: z.enum(["simulation", "execute"]),
    status: z.enum([
      "created",
      "policy_check",
      "budget_reserved",
      "running",
      "paused",
      "awaiting_review",
      "completed",
      "failed",
      "canceled",
    ]),
    modelProvider: z.string().nullable(),
    modelId: z.string().nullable(),
    promptVersion: z.string(),
    contextManifestDigest: z.string().min(16),
    workspaceId: IdentifierSchema.nullable(),
    budgetReservationUsdMicros: UsdMicrosSchema,
    actualCostUsdMicros: UsdMicrosSchema,
    retryCount: z.number().int().nonnegative(),
    startedAt: IsoDateTimeSchema.nullable(),
    completedAt: IsoDateTimeSchema.nullable(),
  })
  .strict();

export const BudgetPolicySchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    scopeType: z.enum(["organization", "project", "agent", "task", "provider"]),
    scopeId: z.string().min(1),
    period: z.enum(["task", "day", "week", "month"]),
    warningUsdMicros: UsdMicrosSchema,
    hardLimitUsdMicros: UsdMicrosSchema,
    maxCalls: z.number().int().nonnegative(),
    maxConcurrentRuns: z.number().int().nonnegative(),
    active: z.boolean(),
  })
  .strict()
  .superRefine((policy, context) => {
    if (policy.warningUsdMicros > policy.hardLimitUsdMicros) {
      context.addIssue({
        code: "custom",
        message: "Warning threshold must not exceed hard limit",
        path: ["warningUsdMicros"],
      });
    }
  });

export const UsageLedgerEntrySchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    taskId: IdentifierSchema,
    runId: IdentifierSchema,
    agentId: IdentifierSchema,
    provider: z.string().min(1),
    model: z.string().min(1),
    inputTokens: z.number().int().nonnegative(),
    outputTokens: z.number().int().nonnegative(),
    cachedInputTokens: z.number().int().nonnegative(),
    estimatedCostUsdMicros: UsdMicrosSchema,
    actualCostUsdMicros: UsdMicrosSchema.nullable(),
    providerRequestId: z.string().nullable(),
    recordedAt: IsoDateTimeSchema,
  })
  .strict();

export const ApprovalRequestSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema,
    taskId: IdentifierSchema,
    runId: IdentifierSchema.nullable(),
    requestedByType: ActorTypeSchema,
    requestedById: IdentifierSchema,
    action: CapabilitySchema,
    summary: z.string().min(1),
    reason: z.string().min(1),
    scopeDigest: z.string().min(16),
    commitSha: z.string().regex(/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/).nullable(),
    evidenceArtifactIds: z.array(IdentifierSchema),
    testsCompleted: z.array(z.string()),
    riskLevel: RiskLevelSchema,
    reversible: z.boolean(),
    rollbackPlan: z.string().min(1),
    estimatedCostUsdMicros: UsdMicrosSchema,
    recommendation: z.enum(["approve", "reject", "request_changes"]),
    alternatives: z.array(z.string().min(1)),
    requiredApprovals: z.number().int().positive().max(2),
    requiredRole: z.enum(["owner", "operator"]),
    status: z.enum([
      "pending",
      "approved",
      "rejected",
      "changes_requested",
      "expired",
      "canceled",
    ]),
    idempotencyKey: z.string().min(16),
    createdAt: IsoDateTimeSchema,
    expiresAt: IsoDateTimeSchema,
  })
  .strict()
  .superRefine((request, context) => {
    if (
      ["production_merge", "production_deploy"].includes(request.action) &&
      request.commitSha === null
    ) {
      context.addIssue({
        code: "custom",
        message: "Code release approvals must be pinned to a commit SHA",
        path: ["commitSha"],
      });
    }
    if (
      ["production_merge", "production_deploy", "production_database_write",
        "canonical_world_growth", "public_communication", "social_publish", "payment_charge",
        "price_change", "destructive_delete"].includes(request.action) &&
      request.requiredRole !== "owner"
    ) {
      context.addIssue({
        code: "custom",
        message: "High-impact approvals require an owner",
        path: ["requiredRole"],
      });
    }
  });

export const ApprovalDecisionSchema = z
  .object({
    id: IdentifierSchema,
    approvalRequestId: IdentifierSchema,
    decidedByUserId: IdentifierSchema,
    decision: z.enum(["approve", "reject", "request_changes"]),
    comment: z.string().min(1),
    requestScopeDigest: z.string().min(16),
    decidedAt: IsoDateTimeSchema,
  })
  .strict();

export const MemoryRecordSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema.nullable(),
    type: z.enum(["company", "project", "decision", "task", "agent", "temporary"]),
    subject: z.string().min(1),
    body: z.string().min(1),
    sourceType: z.enum([
      "human",
      "repository",
      "test",
      "metric",
      "external_primary_source",
      "agent_summary",
    ]),
    sourceReference: z.string().min(1),
    sourceDigest: z.string().min(16),
    confidence: ConfidenceSchema,
    status: z.enum([
      "active",
      "deprecated",
      "superseded",
      "incorrect",
      "archived",
    ]),
    version: z.number().int().positive(),
    tags: z.array(z.string().min(1)),
    createdByType: ActorTypeSchema,
    createdById: IdentifierSchema,
    createdAt: IsoDateTimeSchema,
    expiresAt: IsoDateTimeSchema.nullable(),
    supersededById: IdentifierSchema.nullable(),
  })
  .strict();

export const AuditEventSchema = z
  .object({
    id: IdentifierSchema,
    organizationId: IdentifierSchema,
    projectId: IdentifierSchema.nullable(),
    taskId: IdentifierSchema.nullable(),
    runId: IdentifierSchema.nullable(),
    actorType: ActorTypeSchema,
    actorId: IdentifierSchema,
    action: z.string().min(1),
    targetType: z.string().min(1),
    targetId: z.string().min(1),
    outcome: z.enum(["allowed", "denied", "approval_required", "succeeded", "failed"]),
    reason: z.string().min(1),
    correlationId: IdentifierSchema,
    idempotencyKey: z.string().min(16),
    requestDigest: z.string().min(16),
    resultDigest: z.string().min(16).nullable(),
    evidenceArtifactIds: z.array(IdentifierSchema),
    createdAt: IsoDateTimeSchema,
  })
  .strict();

export type AgentProfile = z.infer<typeof AgentProfileSchema>;
export type ApprovalDecision = z.infer<typeof ApprovalDecisionSchema>;
export type ApprovalRequest = z.infer<typeof ApprovalRequestSchema>;
export type AuditEvent = z.infer<typeof AuditEventSchema>;
export type BudgetPolicy = z.infer<typeof BudgetPolicySchema>;
export type Capability = z.infer<typeof CapabilitySchema>;
export type Goal = z.infer<typeof GoalSchema>;
export type MemoryRecord = z.infer<typeof MemoryRecordSchema>;
export type RepositoryScope = z.infer<typeof RepositoryScopeSchema>;
export type RiskLevel = z.infer<typeof RiskLevelSchema>;
export type Run = z.infer<typeof RunSchema>;
export type StructuredMessage = z.infer<typeof StructuredMessageSchema>;
export type Task = z.infer<typeof TaskSchema>;
export type TaskStatus = z.infer<typeof TaskStatusSchema>;
export type UsageLedgerEntry = z.infer<typeof UsageLedgerEntrySchema>;
