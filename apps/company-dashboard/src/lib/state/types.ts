import { z } from "zod";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  AuditEventSchema,
  GoalSchema,
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

export const CompanyStateSchema = z
  .object({
    goals: z.array(GoalSchema),
    tasks: z.array(TaskSchema),
    runs: z.array(RunSchema),
    messages: z.array(StructuredMessageSchema).default([]),
    controlTicks: z.array(HostedControlTickSchema).default([]),
    ownerNotifications: z.array(OwnerNotificationSchema).default([]),
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
  controlTicks: HostedControlTick[];
  ownerNotifications: OwnerNotification[];
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
    controlTicks: [],
    ownerNotifications: [],
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
  /** Releases or rejects held work. Returns the task's resulting status. */
  decideHeldTask(decision: HeldTaskDecision): Promise<string>;
  appendGoalSimulation(record: GoalSimulationRecord): Promise<void>;
  appendApprovalDecision(record: ApprovalDecisionRecord): Promise<void>;
  /** Records a planned initiative: one goal and its tasks, written together. */
  appendInitiative(goal: Goal, tasks: readonly Task[]): Promise<void>;
  /** Records a refused or failed attempt, which produces no state change. */
  appendAuditEvent(event: AuditEvent): Promise<void>;
}
