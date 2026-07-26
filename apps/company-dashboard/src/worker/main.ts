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
import { hostname } from "node:os";
import path from "node:path";

import {
  AgentTaskExecutor,
  ClaudeCodeProvider,
  RepositoryReportExecutor,
  SEED_AGENTS,
  WorktreeManager,
  runWorker,
  type TaskExecutor,
} from "@followville/company-os-core";

import { SupabaseWorkQueue } from "../lib/state/supabase-queue";

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

const executablePath = ClaudeCodeProvider.defaultExecutablePath();
const provider =
  executablePath === null ? null : new ClaudeCodeProvider(executablePath);

if (provider !== null) {
  const availability = await provider.checkAvailability();
  log(
    availability.available
      ? `provider claude-code: ready (${availability.detail})`
      : `provider claude-code: unavailable (${availability.reason}) - ${availability.detail}`,
  );
} else {
  log("provider claude-code: no executable found; set CLAUDE_CODE_PATH");
}

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

let stopping = false;
process.on("SIGINT", () => {
  stopping = true;
  log("stopping after the current task");
});

do {
  const reclaimed = await queue.reclaimExpiredLeases();
  if (reclaimed > 0) {
    log(`requeued ${reclaimed} task(s) whose worker stopped reporting`);
  }

  const outcomes = await runWorker(
    executor,
    queue,
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
  if (outcomes.length === 0 && watch && !stopping) {
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
} while (watch && !stopping);

log("worker finished");
