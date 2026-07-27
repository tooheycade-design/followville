/**
 * The worker process.
 *
 * Leases queued tasks from the shared database, runs them with the configured
 * provider inside an isolated worktree, and hands results to review. Run one
 * of these on each owner's machine; leasing keeps them from colliding.
 *
 *   pnpm --dir apps/company-dashboard worker            # one pass, then exit
 *   pnpm --dir apps/company-dashboard worker -- --watch # keep polling
 *   pnpm --dir apps/company-dashboard worker -- --check # report readiness only
 */
import { randomUUID } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { hostname } from "node:os";
import path from "node:path";

import {
  AgentTaskExecutor,
  ClaudeCodeProvider,
  CodexProvider,
  RepositoryReportExecutor,
  SEED_AGENTS,
  WorktreeManager,
  runWorker,
  type ModelProvider,
  type TaskExecutor,
} from "@followville/company-os-core";

import {
  SupabaseReviewQueue,
  SupabaseWorkQueue,
} from "../lib/state/supabase-queue";
import { companyRepository } from "../lib/state";
import {
  DEFAULT_SCHEDULE,
  EvidenceReviewer,
  assertIndependentReviewer,
  dueJobs,
  recordRun,
  reviewAuditEvent,
  type ScheduleState,
} from "@followville/company-os-core";

const args = new Set(process.argv.slice(2));
const watch = args.has("--watch");
const checkOnly = args.has("--check");
const deterministic = args.has("--deterministic");
const pollMs = 15_000;

const repositoryRoot = path.resolve(process.cwd(), "..", "..");
const workerId = `${hostname()}-${process.pid}`;

function log(message: string): void {
  console.log(`[${new Date().toISOString()}] ${message}`);
}

const queue = SupabaseWorkQueue.fromEnvironment();
if (queue === null) {
  console.error(
    "No database configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY in .env.local.",
  );
  process.exit(1);
}

/**
 * Providers are tried in order and the first available one is used.
 *
 * Both run on an existing subscription, so the choice is about which account
 * is signed in on this machine rather than cost. Every candidate is probed and
 * reported even after one is chosen, so an unavailable provider is visible
 * rather than silently skipped.
 */
async function selectProvider(): Promise<ModelProvider | null> {
  const candidates: ModelProvider[] = [];
  const codexPath = CodexProvider.defaultExecutablePath();
  if (codexPath !== null) {
    candidates.push(new CodexProvider(codexPath));
  }
  const claudePath = ClaudeCodeProvider.defaultExecutablePath();
  if (claudePath !== null) {
    candidates.push(new ClaudeCodeProvider(claudePath));
  }
  if (candidates.length === 0) {
    log("no model CLI found; set CODEX_CLI_PATH or CLAUDE_CODE_PATH");
    return null;
  }

  let chosen: ModelProvider | null = null;
  for (const candidate of candidates) {
    const availability = await candidate.checkAvailability();
    log(
      availability.available
        ? `provider ${candidate.name}: ready (${availability.detail})`
        : `provider ${candidate.name}: unavailable (${availability.reason}) - ${availability.detail}`,
    );
    if (availability.available && chosen === null) {
      chosen = candidate;
    }
  }
  return chosen;
}

const provider = await selectProvider();

if (checkOnly) {
  const reclaimed = await queue.reclaimExpiredLeases();
  log(`worker ${workerId} ready. reclaimed ${reclaimed} expired lease(s).`);
  process.exit(0);
}

const executor: TaskExecutor =
  deterministic || provider === null
    ? new RepositoryReportExecutor(repositoryRoot)
    : new AgentTaskExecutor({
        agent: SEED_AGENTS.engineer,
        provider,
        worktrees: new WorktreeManager(
          repositoryRoot,
          path.join(repositoryRoot, ".worktrees", "agents"),
        ),
        repository: "followville_repo",
        invocationTimeoutMs: 15 * 60_000,
        maxSubscriptionRunsPerTask: 1,
      });

log(`worker ${workerId} starting with executor ${executor.name}`);

const reviewQueue = SupabaseReviewQueue.fromEnvironment();
const reviewer = new EvidenceReviewer();

/**
 * Reviews work the worker finished.
 *
 * Evidence and the worker's summary are read back from the audit trail rather
 * than passed along in memory, so the reviewer judges what was actually
 * recorded rather than what the worker said in passing.
 */
async function runReviewPass(): Promise<number> {
  if (reviewQueue === null) {
    return 0;
  }
  let count = 0;
  for (;;) {
    const task = await reviewQueue.leaseNextReview(
      workerId,
      SEED_AGENTS.reviewer.id,
      300,
    );
    if (task === null) {
      return count;
    }
    assertIndependentReviewer(task);

    const state = await companyRepository().load();
    const events = state.auditEvents.filter(
      (event) => event.taskId === task.id && event.action.startsWith("worker."),
    );
    const completion = events.find((event) => event.action === "worker.completed");

    const result = await reviewer.review({
      task,
      workerEvidence: completion === undefined ? [] : [completion.reason],
      workerSummary: completion?.reason ?? "",
      filesChanged: [],
    });

    const recorded = await reviewQueue.recordReview({
      taskId: task.id,
      workerId,
      verdict: result.verdict,
      auditEvents: [
        reviewAuditEvent(task, result, SEED_AGENTS.reviewer.id, randomUUID),
      ],
    });
    log(
      recorded
        ? `review ${task.id.slice(0, 8)} -> ${result.verdict}: ${result.summary}`
        : `review ${task.id.slice(0, 8)} -> lease lost, verdict discarded`,
    );
    count += 1;
  }
}

let stopping = false;
process.on("SIGINT", () => {
  stopping = true;
  log("stopping after the current task");
});

/**
 * Schedule state is kept on disk so a restarted worker does not immediately
 * rerun every daily job. It is local bookkeeping, not company state, which is
 * why it lives beside the process rather than in the shared database.
 */
const scheduleStatePath = path.join(process.cwd(), ".data", "schedule.json");
const scheduleStates = new Map<string, ScheduleState>();
try {
  const raw = JSON.parse(readFileSync(scheduleStatePath, "utf8")) as ScheduleState[];
  for (const entry of raw) {
    scheduleStates.set(entry.name, entry);
  }
} catch {
  // No prior state; every job is simply due.
}

function saveScheduleStates(): void {
  try {
    mkdirSync(path.dirname(scheduleStatePath), { recursive: true });
    writeFileSync(
      scheduleStatePath,
      JSON.stringify([...scheduleStates.values()], null, 2),
      "utf8",
    );
  } catch (error) {
    log(`could not persist schedule state: ${(error as Error).message}`);
  }
}

async function runWorkQueueJob(): Promise<void> {
  const outcomes = await runWorker(
    executor,
    queue!,
    {
      workerId,
      leaseSeconds: 300,
      heartbeatIntervalMs: 60_000,
      maxTaskDurationMs: 20 * 60_000,
      maxTasks: watch ? 1 : undefined,
    },
    randomUUID,
  );
  for (const outcome of outcomes) {
    log(`task ${outcome.taskId.slice(0, 8)} -> ${outcome.status}: ${outcome.summary}`);
  }
  const reviewed = await runReviewPass();
  if (reviewed > 0) {
    log(`reviewed ${reviewed} task(s)`);
  }
}

const JOBS: Record<string, () => Promise<void>> = {
  "work-queue": runWorkQueueJob,
  "reclaim-leases": async () => {
    const reclaimed = await queue!.reclaimExpiredLeases();
    if (reclaimed > 0) {
      log(`requeued ${reclaimed} task(s) whose worker stopped reporting`);
    }
  },
  "daily-report": async () => {
    const state = await companyRepository().load();
    const pending = state.approvalRequests.filter((r) => r.status === "pending");
    const open = state.tasks.filter(
      (t) => !["approved", "rejected", "merged", "deployed", "canceled"].includes(t.status),
    );
    log(
      `daily report: ${state.goals.length} goal(s), ${open.length} open task(s), ` +
        `${pending.length} awaiting an owner, ${state.auditEvents.length} audit event(s)`,
    );
  },
  "cost-audit": async () => {
    const state = await companyRepository().load();
    const spent = state.runs.reduce((sum, run) => sum + run.actualCostUsdMicros, 0);
    log(`cost audit: $${(spent / 1_000_000).toFixed(2)} recorded model spend`);
  },
};

if (!watch) {
  // A single pass runs the work queue directly, ignoring the schedule.
  await JOBS["reclaim-leases"]!();
  await runWorkQueueJob();
} else {
  log(
    `scheduler active: ${DEFAULT_SCHEDULE.map((j) => `${j.name} every ${Math.round(j.intervalMs / 60000)}m`).join(", ")}`,
  );
  while (!stopping) {
    const now = Date.now();
    const due = dueJobs(DEFAULT_SCHEDULE, scheduleStates, now);
    for (const job of due) {
      if (stopping) {
        break;
      }
      const handler = JOBS[job.name];
      if (handler === undefined) {
        continue;
      }
      try {
        await handler();
        scheduleStates.set(
          job.name,
          recordRun(scheduleStates.get(job.name), job.name, "succeeded", new Date().toISOString()),
        );
      } catch (error) {
        log(`job ${job.name} failed: ${(error as Error).message}`);
        scheduleStates.set(
          job.name,
          recordRun(scheduleStates.get(job.name), job.name, "failed", new Date().toISOString()),
        );
      }
      saveScheduleStates();
    }
    if (!stopping) {
      await new Promise((resolve) => setTimeout(resolve, pollMs));
    }
  }
}

log("worker finished");
