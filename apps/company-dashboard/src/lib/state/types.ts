import { z } from "zod";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  AuditEventSchema,
  GoalSchema,
  MemoryRecordSchema,
  EvidenceArtifactSchema,
  RunSchema,
  StructuredMessageSchema,
  TaskSchema,
  WorkerNodeSchema,
  type ApprovalDecision,
  type ApprovalRequest,
  type AuditEvent,
  type EvidenceArtifact,
  type Goal,
  type MemoryRecord,
  type Run,
  type StructuredMessage,
  type Task,
  type WorkerNode,
} from "@followville/company-os-core";

export const HostedControlTickSchema = z
  .object({
    id: z.string().uuid(),
    organizationId: z.string().uuid(),
    projectId: z.string().uuid(),
    tickType: z.enum(["queue_health", "daily_report"]),
    timeBucket: z.string().datetime({ offset: true }),
    metrics: z
      .object({
        reclaimedLeaseCount: z.number().int().nonnegative(),
        expiredMessageCount: z.number().int().nonnegative(),
        onlineWorkers: z.number().int().nonnegative(),
        unavailableWorkers: z.number().int().nonnegative(),
        queuedTasks: z.number().int().nonnegative(),
        incompatibleTasks: z.number().int().nonnegative(),
        pendingApprovals: z.number().int().nonnegative(),
        heldTasks: z.number().int().nonnegative(),
      })
      .strict(),
    createdAt: z.string().datetime({ offset: true }),
  })
  .strict();

export const OwnerNotificationSchema = z
  .object({
    id: z.string().uuid(),
    organizationId: z.string().uuid(),
    projectId: z.string().uuid(),
    notificationType: z.enum([
      "approval_reminder",
      "held_work_reminder",
      "queue_unavailable",
      "worker_unavailable",
    ]),
    targetType: z.enum(["approval_request", "task", "project", "worker"]),
    targetId: z.string().min(1),
    title: z.string().min(1),
    detail: z.string().min(1),
    severity: z.enum(["info", "warning", "urgent"]),
    deliveryDay: z.string(),
    status: z.enum(["pending", "read", "resolved", "expired"]),
    createdAt: z.string().datetime({ offset: true }),
    updatedAt: z.string().datetime({ offset: true }),
  })
  .strict();

export type HostedControlTick = z.infer<typeof HostedControlTickSchema>;
export type OwnerNotification = z.infer<typeof OwnerNotificationSchema>;

const OperationalMetricValueSchema = z.union([
  z.string(),
  z.number(),
  z.boolean(),
  z.null(),
]);

export const IntegrationSourceSchema = z
  .object({
    id: z.string().uuid(),
    organizationId: z.string().uuid(),
    projectId: z.string().uuid(),
    sourceKey: z.string().min(3),
    displayName: z.string().min(1),
    sourceType: z.enum([
      "public_town",
      "website",
      "instagram",
      "analytics",
      "application_database",
      "payments",
      "moderation",
    ]),
    accessMode: z.enum([
      "public_read",
      "configured_read_only",
      "setup_required",
    ]),
    status: z.enum([
      "active",
      "setup_required",
      "degraded",
      "error",
      "disabled",
    ]),
    setupRequirement: z.string().nullable(),
    configuration: z.record(z.string(), z.unknown()),
    lastCheckedAt: z.string().datetime({ offset: true }).nullable(),
    lastSuccessAt: z.string().datetime({ offset: true }).nullable(),
    lastErrorCode: z.string().nullable(),
    createdAt: z.string().datetime({ offset: true }),
    updatedAt: z.string().datetime({ offset: true }),
  })
  .strict();

export const OperationalSnapshotSchema = z
  .object({
    id: z.string().uuid(),
    organizationId: z.string().uuid(),
    projectId: z.string().uuid(),
    sourceId: z.string().uuid(),
    capturedAt: z.string().datetime({ offset: true }),
    metrics: z.record(z.string(), OperationalMetricValueSchema),
    evidenceReference: z.string().min(1),
    sourceDigest: z.string().regex(/^[0-9a-f]{64}$/),
    idempotencyKey: z.string().min(16),
    confidence: z.enum([
      "confirmed",
      "likely",
      "uncertain",
      "requires_human_verification",
    ]),
    freshnessUntil: z.string().datetime({ offset: true }),
    createdByType: z.enum(["human", "agent", "service", "system"]),
    createdById: z.string().uuid(),
    createdAt: z.string().datetime({ offset: true }),
  })
  .strict();

export type IntegrationSource = z.infer<typeof IntegrationSourceSchema>;
export type OperationalSnapshot = z.infer<typeof OperationalSnapshotSchema>;

export const CompanyStateSchema = z
  .object({
    goals: z.array(GoalSchema),
    tasks: z.array(TaskSchema),
    runs: z.array(RunSchema),
    messages: z.array(StructuredMessageSchema).default([]),
    memories: z.array(MemoryRecordSchema).default([]),
    controlTicks: z.array(HostedControlTickSchema).default([]),
    ownerNotifications: z.array(OwnerNotificationSchema).default([]),
    integrationSources: z.array(IntegrationSourceSchema).default([]),
    operationalSnapshots: z.array(OperationalSnapshotSchema).default([]),
    workers: z.array(WorkerNodeSchema).default([]),
    approvalRequests: z.array(ApprovalRequestSchema),
    approvalDecisions: z.array(ApprovalDecisionSchema),
    // Defaulted, not required: a store written before artifacts existed must
    // still load rather than failing a dashboard that was working yesterday.
    evidenceArtifacts: z.array(EvidenceArtifactSchema).default([]),
    auditEvents: z.array(AuditEventSchema),
  })
  .strict();

export interface CompanyState {
  goals: Goal[];
  tasks: Task[];
  runs: Run[];
  messages: StructuredMessage[];
  memories: MemoryRecord[];
  controlTicks: HostedControlTick[];
  ownerNotifications: OwnerNotification[];
  integrationSources: IntegrationSource[];
  operationalSnapshots: OperationalSnapshot[];
  workers: WorkerNode[];
  approvalRequests: ApprovalRequest[];
  approvalDecisions: ApprovalDecision[];
  evidenceArtifacts: EvidenceArtifact[];
  auditEvents: AuditEvent[];
}

export function emptyState(): CompanyState {
  return {
    goals: [],
    tasks: [],
    runs: [],
    messages: [],
    memories: [],
    controlTicks: [],
    ownerNotifications: [],
    integrationSources: [],
    operationalSnapshots: [],
    workers: [],
    approvalRequests: [],
    approvalDecisions: [],
    evidenceArtifacts: [],
    auditEvents: [],
  };
}

/** A completed simulation, written as one unit. */
export interface GoalSimulationRecord {
  goal: Goal;
  task: Task;
  run: Run;
  approvalRequest: ApprovalRequest;
  auditEvents: readonly AuditEvent[];
}

/**
 * A recorded owner decision. `resolvedRequest` and `updatedTask` are the
 * results the decision kernel computed. A backend whose database derives
 * approval status from the decision rows themselves may ignore
 * `resolvedRequest.status` — the decision row remains the source of truth.
 */
export interface ApprovalDecisionRecord {
  decision: ApprovalDecision;
  resolvedRequest: ApprovalRequest;
  updatedTask: Task | null;
  auditEvent: AuditEvent;
}

/**
 * An owner's decision about work the Chief Executive held for them.
 *
 * `grantedCapabilities` may be narrower than the task proposed and can never
 * be wider; the database re-checks that independently. `expectedVersion` is
 * what the owner was looking at, so a task edited since they read it cannot be
 * released on the strength of a decision about something else.
 */
/** Finished work and the request asking an owner to accept it. */
export interface CompletedWorkRecord {
  approvalRequest: ApprovalRequest;
  artifacts: readonly EvidenceArtifact[];
}

export interface HeldTaskDecision {
  taskId: string;
  decision: "release" | "reject";
  decidedByUserId: string;
  comment: string;
  grantedCapabilities: readonly string[];
  authorizationDigest: string;
  expectedVersion: number;
}

export interface CompanyRepository {
  readonly backend: "file" | "supabase";
  load(): Promise<CompanyState>;
  retrieveMemories(
    role: MemoryRecord["audienceRoles"][number],
    query: string,
    tags?: readonly string[],
    limit?: number,
  ): Promise<MemoryRecord[]>;
  recordOperationalSnapshot(input: {
    sourceKey: string;
    capturedAt: string;
    metrics: OperationalSnapshot["metrics"];
    evidenceReference: string;
    sourceDigest: string;
    idempotencyKey: string;
    confidence: OperationalSnapshot["confidence"];
    freshnessMinutes: number;
  }): Promise<OperationalSnapshot>;
  recordOperationalFailure(sourceKey: string, errorCode: string): Promise<void>;
  /** Releases or rejects held work. Returns the task's resulting status. */
  decideHeldTask(decision: HeldTaskDecision): Promise<string>;
  appendGoalSimulation(record: GoalSimulationRecord): Promise<void>;
  appendApprovalDecision(record: ApprovalDecisionRecord): Promise<void>;
  /** Records a planned initiative: one goal and its tasks, written together. */
  appendInitiative(goal: Goal, tasks: readonly Task[]): Promise<void>;
  /** Records a refused or failed attempt, which produces no state change. */
  appendAuditEvent(event: AuditEvent): Promise<void>;
}
