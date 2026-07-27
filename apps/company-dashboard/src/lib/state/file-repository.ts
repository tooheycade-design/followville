import { mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import path from "node:path";

import type { Goal, Task } from "@followville/company-os-core";

import {
  CompanyStateSchema,
  emptyState,
  type ApprovalDecisionRecord,
  type CompanyRepository,
  type CompanyState,
  type GoalSimulationRecord,
} from "./types";

export function defaultStatePath(): string {
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

/**
 * Single-process JSON persistence. Server actions run in one Node process, so
 * the chain serializes read-modify-write cycles and two concurrent form posts
 * cannot interleave. This is Phase 1 local development only; it does not
 * survive multiple machines, which is why the Supabase backend exists.
 */
export class FileCompanyRepository implements CompanyRepository {
  readonly backend = "file" as const;
  #chain: Promise<unknown> = Promise.resolve();

  constructor(private readonly statePath: string = defaultStatePath()) {}

  /**
   * Reads without entering the mutation chain, so rendering a page never
   * rewrites the state file. Queued after any in-flight mutation so a read
   * cannot observe a half-written document.
   */
  load(): Promise<CompanyState> {
    const next = this.#chain.then(() => readState(this.statePath));
    this.#chain = next.catch(() => undefined);
    return next;
  }

  appendGoalSimulation(record: GoalSimulationRecord): Promise<void> {
    return this.#mutate((state) => {
      state.goals.push(record.goal);
      state.tasks.push(record.task);
      state.runs.push(record.run);
      state.approvalRequests.push(record.approvalRequest);
      state.auditEvents.push(...record.auditEvents);
    });
  }

  appendApprovalDecision(record: ApprovalDecisionRecord): Promise<void> {
    return this.#mutate((state) => {
      const requestIndex = state.approvalRequests.findIndex(
        (request) => request.id === record.resolvedRequest.id,
      );
      if (requestIndex >= 0) {
        state.approvalRequests[requestIndex] = record.resolvedRequest;
      }
      state.approvalDecisions.push(record.decision);
      if (record.updatedTask !== null) {
        const taskIndex = state.tasks.findIndex(
          (task) => task.id === record.updatedTask?.id,
        );
        if (taskIndex >= 0) {
          state.tasks[taskIndex] = record.updatedTask;
        }
      }
      state.auditEvents.push(record.auditEvent);
    });
  }

  appendInitiative(goal: Goal, tasks: readonly Task[]): Promise<void> {
    return this.#mutate((state) => {
      state.goals.push(goal);
      state.tasks.push(...tasks);
    });
  }

  appendAuditEvent(event: CompanyState["auditEvents"][number]): Promise<void> {
    return this.#mutate((state) => {
      state.auditEvents.push(event);
    });
  }

  #mutate<T>(mutator: (state: CompanyState) => T): Promise<T> {
    const next = this.#chain.then(() => {
      const state = readState(this.statePath);
      const result = mutator(state);
      writeState(state, this.statePath);
      return result;
    });
    this.#chain = next.catch(() => undefined);
    return next;
  }
}
