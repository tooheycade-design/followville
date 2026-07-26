import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";
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

const CompanyStateSchema = z
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

function defaultStatePath(): string {
  return path.join(
    process.env.COMPANY_OS_DATA_DIR ?? path.join(process.cwd(), ".data"),
    "company-state.json",
  );
}

export function readState(statePath = defaultStatePath()): CompanyState {
  let raw: string;
  try {
    raw = readFileSync(statePath, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return emptyState();
    }
    throw error;
  }
  return CompanyStateSchema.parse(JSON.parse(raw));
}

export function writeState(
  state: CompanyState,
  statePath = defaultStatePath(),
): void {
  const validated = CompanyStateSchema.parse(state);
  mkdirSync(path.dirname(statePath), { recursive: true });
  const temporaryPath = `${statePath}.tmp`;
  writeFileSync(temporaryPath, JSON.stringify(validated, null, 2), "utf8");
  renameSync(temporaryPath, statePath);
}

// Server actions run in one Node process during Phase 1; the chain serializes
// read-modify-write cycles so two concurrent form posts cannot interleave.
let mutationChain: Promise<unknown> = Promise.resolve();

export function mutateState<T>(
  mutator: (state: CompanyState) => T,
  statePath = defaultStatePath(),
): Promise<T> {
  const next = mutationChain.then(() => {
    const state = readState(statePath);
    const result = mutator(state);
    writeState(state, statePath);
    return result;
  });
  mutationChain = next.catch(() => undefined);
  return next;
}
