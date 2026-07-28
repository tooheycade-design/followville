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
import { arch, hostname, platform } from "node:os";
import path from "node:path";

import {
  AgentTaskExecutor,
  ClaudeCodeProvider,
  CodexProvider,
  GitHubAppInstallationAuth,
  GitHubRestPullRequestClient,
  RepositoryReportExecutor,
  RepositoryVerificationRunner,
  ORGANIZATION_ID,
  PROJECT_ID,
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
  CeoGate,
  DEFAULT_SCHEDULE,
  EvidenceReviewer,
  assertIndependentReviewer,
  artifactFromReport,
  completedWorkApproval,
  decodeWorkerReport,
  gateAuditEvent,
  handoffBriefing,
  priorRejectionsFrom,
  reworkBriefing,
  resumableSessionFromReports,
  dueJobs,
  recordRun,
  reviewAuditEvent,
  reviewReworkBriefing,
  type ScheduleState,
} from "@followville/company-os-core";
import type { CompletedWorkRecord } from "../lib/state/types";
import { OWNER_REGISTRY } from "../lib/config";
import { SupabaseArtifactStore } from "../lib/artifact-storage";
import { runPublicationPass } from "./publication";

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
async function availableProviders(): Promise<ModelProvider[]> {
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
    return [];
  }

  const ready: ModelProvider[] = [];
  for (const candidate of candidates) {
    const availability = await candidate.checkAvailability();
    log(
      availability.available
        ? `provider ${candidate.name}: ready (${availability.detail})`
        : `provider ${candidate.name}: unavailable (${availability.reason}) - ${availability.detail}`,
    );
    if (availability.available) {
      ready.push(candidate);
    }
  }
  return ready;
}

const ready = await availableProviders();
const artifactStore = SupabaseArtifactStore.fromEnvironment();
log(
  artifactStore === null
    ? "shared artifact storage unavailable; evidence remains checkpoint-linked"
    : "shared artifact storage ready in the private Company OS evidence bucket",
);

/**
 * Work and judgement go to different models when two are signed in.
 *
 * A model reviewing its own output shares its blind spots, so the point of an
 * independent reviewer is largely lost. With one model available both roles
 * still run — a single-model check is worth more than none — but the log says
 * so plainly rather than implying independence that does not exist.
 */
const provider = ready[0] ?? null;
const judgeProvider = ready[1] ?? ready[0] ?? null;
const githubPublicationAvailable = [
  process.env.COMPANY_OS_GITHUB_BASE_BRANCH,
  process.env.COMPANY_OS_GITHUB_APP_ID,
  process.env.COMPANY_OS_GITHUB_INSTALLATION_ID,
  process.env.COMPANY_OS_GITHUB_PRIVATE_KEY_BASE64,
].every((value) => value !== undefined && value.trim().length > 0);
if (ready.length >= 2) {
  log(`roles: ${provider?.name} implements, ${judgeProvider?.name} judges`);
} else if (ready.length === 1) {
  log(`roles: ${provider?.name} both implements and judges (only one model signed in)`);
}

const workerCapabilities =
  deterministic || provider === null
    ? (["repository_read"] as const)
    : SEED_AGENTS.engineer.capabilities.filter((capability) => {
        if (
          capability === "blender_preview" ||
          capability === "git_commit" ||
          capability === "memory_write" ||
          capability === "message_send"
        ) {
          return false;
        }
        if (capability === "browser_preview" && artifactStore === null) {
          return false;
        }
        if (
          (capability === "git_push_review_branch" ||
            capability === "pull_request_create") &&
          !githubPublicationAvailable
        ) {
          return false;
        }
        return true;
      });

const workerRegistration = {
  workerId,
  organizationId: ORGANIZATION_ID,
  projectId: PROJECT_ID,
  agentId: SEED_AGENTS.engineer.id,
  displayName: `${hostname()} worker`,
  machineName: hostname(),
  platform: `${platform()}-${arch()}`,
  provider: deterministic ? "deterministic" : (provider?.name ?? "unavailable"),
  modelId: null,
  softwareVersion:
    process.env.COMPANY_OS_WORKER_VERSION?.trim() || "company-os-0.1.0",
  capabilities: workerCapabilities,
  metadata: {
    reviewerProvider: judgeProvider?.name ?? null,
    sharedArtifactStorage: artifactStore !== null,
  },
} as const;
const continuityKey =
  provider === null ? null : `${hostname()}:${provider.name}`;

async function resumableSessionFor(task: {
  id: string;
  retryCount: number;
  reviewCycleCount: number;
}): Promise<string | null> {
  if (
    provider === null ||
    continuityKey === null ||
    (task.retryCount === 0 && task.reviewCycleCount === 0)
  ) {
    return null;
  }
  const state = await companyRepository().load();
  const completions = state.auditEvents
    .filter(
      (event) =>
        event.taskId === task.id && event.action === "worker.completed",
    )
    .reverse();
  return resumableSessionFromReports(
    completions.map((event) => event.reason),
    provider.name,
    continuityKey,
  );
}

async function reportWorker(
  status: "online" | "draining" | "offline" | "error",
): Promise<void> {
  await queue!.upsertWorker({ ...workerRegistration, status });
}

await reportWorker("online");

if (checkOnly) {
  const reclaimed = await queue.reclaimExpiredLeases();
  log(`worker ${workerId} ready. reclaimed ${reclaimed} expired lease(s).`);
  await reportWorker("offline");
} else {
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
        ...(continuityKey === null ? {} : { continuityKey }),
        resumeSessionId: resumableSessionFor,
        verifier: new RepositoryVerificationRunner(repositoryRoot),
        ...(artifactStore === null ? {} : { artifactStore }),
        reworkBriefing: async (task) => {
          const state = await companyRepository().load();
          const taskRequestIds = new Set(
            state.approvalRequests
              .filter((request) => request.taskId === task.id)
              .map((request) => request.id),
          );
          const ownerFeedback = state.approvalDecisions
            .filter(
              (decision) =>
                taskRequestIds.has(decision.approvalRequestId) &&
                decision.decision === "request_changes",
            )
            .slice(-3)
            .map((decision) => decision.comment.trim().slice(0, 1_000))
            .filter((comment) => comment.length > 0);
          const gateFeedback = reworkBriefing(
            priorRejectionsFrom(
              state.auditEvents.filter((event) => event.taskId === task.id),
            ),
          );
          const reviewerFeedback = reviewReworkBriefing(
            state.auditEvents.filter((event) => event.taskId === task.id),
          );
          const latestCompletion = state.auditEvents
            .filter(
              (event) =>
                event.taskId === task.id &&
                event.action === "worker.completed",
            )
            .at(-1);
          const priorHandoff =
            latestCompletion === undefined
              ? ""
              : handoffBriefing(decodeWorkerReport(latestCompletion.reason));
          const ownerBriefing =
            ownerFeedback.length === 0
              ? ""
              : [
                  "",
                  "This task was sent back by an authenticated owner.",
                  "Owner revision feedback:",
                  ...ownerFeedback.map((comment) => `- ${comment}`),
                  "Preserve the prior checkpoint. Address this feedback in a new revision.",
                ].join("\n");
          return [priorHandoff, gateFeedback, reviewerFeedback, ownerBriefing]
            .filter((section) => section.length > 0)
            .join("\n");
        },
      });

log(`worker ${workerId} starting with executor ${executor.name}`);
const registryHeartbeat = setInterval(() => {
  void reportWorker("online").catch((error) => {
    log(`worker registry heartbeat failed: ${(error as Error).message}`);
  });
}, 30_000);

const reviewQueue = SupabaseReviewQueue.fromEnvironment();
const reviewer = new EvidenceReviewer();
const githubRepository = {
  owner: process.env.COMPANY_OS_GITHUB_OWNER?.trim() || "tooheycade-design",
  name: process.env.COMPANY_OS_GITHUB_REPOSITORY?.trim() || "followville",
  baseBranch: process.env.COMPANY_OS_GITHUB_BASE_BRANCH?.trim() || "",
};
const githubConfigured = githubPublicationAvailable;
log(
  githubConfigured
    ? `github draft publication ready for ${githubRepository.owner}/${githubRepository.name} -> ${githubRepository.baseBranch}`
    : "github draft publication disabled until the GitHub App credentials are configured",
);

// The CEO judges with a model when one is available. Without a provider it
// still applies its mechanical bar, so an unavailable model makes the gate
// stricter rather than opening it.
const gate = new CeoGate({
  ...(judgeProvider === null ? {} : { provider: judgeProvider }),
  workingDirectory: repositoryRoot,
  timeoutMs: 3 * 60_000,
});

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
    // The most recent completion, not the first. A task sent back and retried
    // has several, and judging the newest attempt against the oldest attempt's
    // evidence is how a fixed task gets rejected for the fault it just fixed.
    const completion = events
      .filter((event) => event.action === "worker.completed")
      .at(-1);

    // Recovered with the same encoder the worker wrote it with, so the summary,
    // the evidence, the full file list and the diff all arrive intact. Reading
    // this back by hand is what lost everything but the first line, and left
    // the Chief Executive rejecting sound work for missing_evidence.
    const report = decodeWorkerReport(completion?.reason ?? "");
    const completedRunId = completion?.runId ?? null;

    const result = await reviewer.review({
      task,
      workerEvidence: report.evidence,
      workerSummary: report.summary,
      filesChanged: report.filesChanged,
      runId: completedRunId,
      testsCompleted: report.testsCompleted,
      testsFailed: report.testsFailed,
    });

    // The reviewer checks that evidence exists; the CEO decides whether the
    // work is good. Both must pass before an owner is asked to look, which is
    // what makes the approval queue finished work rather than a triage pile.
    let verdict = result.verdict;
    let completedWork: CompletedWorkRecord | undefined;
    const auditEvents: unknown[] = [
      reviewAuditEvent(
        task,
        result,
        SEED_AGENTS.reviewer.id,
        randomUUID,
        new Date().toISOString(),
        completedRunId,
      ),
    ];

    if (verdict === "approved_for_owner") {
      const gateResult = await gate.judge({
        task,
        workerSummary: report.summary,
        workerEvidence: report.evidence,
        filesChanged: report.filesChanged,
        diff: report.diff,
        diffTruncated: report.diffTruncated,
        artifacts: report.artifacts,
        priorRejections: priorRejectionsFrom(
          state.auditEvents.filter((event) => event.taskId === task.id),
        ),
      });
      auditEvents.push(
        gateAuditEvent(
          task,
          gateResult,
          randomUUID,
          new Date().toISOString(),
          completedRunId,
        ),
      );
      if (!gateResult.accepted) {
        verdict = "changes_requested";
        log(
          `ceo ${task.id.slice(0, 8)} -> sent back: ${gateResult.reasons.join(", ")}`,
        );
      } else {
        // Put it in front of an owner. Work used to stop at
        // awaiting_human_approval with nothing to act on: the approvals page
        // lists approval requests and this flow never made one, so finished
        // work was invisible and the task trigger would refuse `approved`
        // without a decision anyway.
        const commit = report.evidence
          .find((item) => item.startsWith("commit="))
          ?.slice("commit=".length);
        const artifacts = report.artifacts.map((reported) =>
          artifactFromReport(
            reported,
            task,
            SEED_AGENTS.engineer.id,
            completion?.createdAt ?? new Date().toISOString(),
            completedRunId,
          ),
        );
        const request = completedWorkApproval({
          task,
          runId: completedRunId!,
          summary: report.summary,
          evidence: report.evidence,
          testsCompleted: report.testsCompleted,
          filesChanged: report.filesChanged,
          artifacts,
          commitSha:
            commit === undefined || commit.startsWith("none") ? null : commit,
          gateNotes: gateResult.notes,
          idFactory: randomUUID,
        });
        completedWork = { approvalRequest: request, artifacts };
      }
    }

    const recorded = await reviewQueue.recordReview({
      taskId: task.id,
      workerId,
      verdict,
      auditEvents,
      ...(completedWork === undefined ? {} : { completedWork }),
    });
    log(
      recorded
        ? `review ${task.id.slice(0, 8)} -> ${verdict}: ${result.summary}`
        : `review ${task.id.slice(0, 8)} -> lease lost, verdict discarded`,
    );
    if (recorded && completedWork !== undefined) {
      log(`owner ${task.id.slice(0, 8)} -> awaiting your decision`);
    }
    count += 1;
  }
}

async function runDraftPublicationPass(): Promise<number> {
  if (!githubConfigured) {
    return 0;
  }
  const repository = companyRepository();
  const state = await repository.load();
  const results = await runPublicationPass(state, {
    auth: new GitHubAppInstallationAuth(),
    client: new GitHubRestPullRequestClient(repositoryRoot),
    recorder: repository,
    authorizedOwnerUserIds: new Set(OWNER_REGISTRY.ownerUserIds),
    repository: githubRepository,
    idFactory: randomUUID,
    now: () => new Date().toISOString(),
  });
  for (const result of results) {
    if (result.outcome !== "skipped") {
      log(
        `github ${result.taskId.slice(0, 8)} -> ${result.outcome}: ${result.detail}`,
      );
    }
  }
  return results.filter(
    (result) => result.outcome === "created" || result.outcome === "existing",
  ).length;
}

let stopping = false;
process.on("SIGINT", () => {
  stopping = true;
  log("stopping after the current task");
});
process.on("SIGTERM", () => {
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
  const published = await runDraftPublicationPass();
  if (published > 0) {
    log(`published ${published} approved checkpoint(s) for draft review`);
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
    // Named precisely: this is metered API spend, and both providers currently
    // run on subscriptions the ledger does not measure. Reporting it as total
    // model spend would understate the real cost of the work indefinitely.
    log(
      `cost audit: $${(spent / 1_000_000).toFixed(2)} metered API spend; ` +
        `subscription usage is not measured by this ledger`,
    );
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

clearInterval(registryHeartbeat);
await reportWorker("offline").catch((error) => {
  log(`could not mark worker offline: ${(error as Error).message}`);
});
log("worker finished");
}
