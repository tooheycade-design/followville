import { z } from "zod";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  AuditEventSchema,
  GoalSchema,
  RunSchema,
  TaskSchema,
  type ApprovalDecision,
  type ApprovalRequest,
  type AuditEvent,
  type Goal,
  type Run,
  type Task,
} from "@followville/company-os-core";

export const CompanyStateSchema = z
  .object({
    goals: z.array(GoalSchema),
    tasks: z.array(TaskSchema),
    runs: z.array(RunSchema),
    approvalRequests: z.array(ApprovalRequestSchema),
    approvalDecisions: z.array(ApprovalDecisionSchema),
    auditEvents: z.array(AuditEventSchema),
  })
  .strict();

export interface CompanyState {
  goals: Goal[];
  tasks: Task[];
  runs: Run[];
  approvalRequests: ApprovalRequest[];
  approvalDecisions: ApprovalDecision[];
  auditEvents: AuditEvent[];
}

export function emptyState(): CompanyState {
  return {
    goals: [],
    tasks: [],
    runs: [],
    approvalRequests: [],
    approvalDecisions: [],
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

export interface CompanyRepository {
  readonly backend: "file" | "supabase";
  load(): Promise<CompanyState>;
  appendGoalSimulation(record: GoalSimulationRecord): Promise<void>;
  appendApprovalDecision(record: ApprovalDecisionRecord): Promise<void>;
  /** Records a refused or failed attempt, which produces no state change. */
  appendAuditEvent(event: AuditEvent): Promise<void>;
}
