import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { test } from "node:test";

import { TaskSchema, type Task } from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import type {
  ModelProvider,
  ProviderAvailability,
  ProviderRequest,
  ProviderResponse,
} from "../providers/types.js";
import {
  AgentTaskExecutor,
  narrowestScopeDirectory,
  taskInvocationTimeoutMs,
} from "./agent-executor.js";
import { WorktreeManager } from "./worktree.js";
import type { WorkVerifier } from "./verification.js";

const NOW = "2026-07-26T19:00:00.000Z";
let counter = 0;
const nextId = (): string =>
  `92000000-0000-4000-8000-${(counter += 1).toString().padStart(12, "0")}`;

/** A throwaway git repository shaped like the real one. */
function makeRepository(): { root: string; worktreeRoot: string } {
  const root = mkdtempSync(path.join(tmpdir(), "fv-repo-"));
  const git = (...args: string[]): void => {
    execFileSync("git", args, { cwd: root, stdio: "pipe" });
  };
  git("init", "--initial-branch=main");
  git("config", "user.email", "test@example.com");
  git("config", "user.name", "Test");
  mkdirSync(path.join(root, "company-os"), { recursive: true });
  writeFileSync(path.join(root, "company-os", "README.md"), "# scoped\n");
  writeFileSync(path.join(root, "world_state.json"), '{"day":24}\n');
  git("add", "-A");
  git("commit", "-m", "initial");
  return { root, worktreeRoot: path.join(root, ".worktrees") };
}

function makeTask(): Task {
  return TaskSchema.parse({
    id: nextId(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: nextId(),
    parentTaskId: null,
    title: "Scoped change",
    objective: "Edit only what is permitted.",
    reason: "An owner asked.",
    status: "assigned",
    priority: 50,
    riskLevel: "low",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: nextId(),
        description: "Only approved paths change.",
        verificationMethod: "Reviewer checks the diff.",
        required: true,
      },
    ],
    allowedCapabilities: ["repository_read", "repository_write", "git_checkpoint"],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: null,
    expectedOutputs: ["A scoped edit"],
    testRequirements: [],
    approvalRequired: true,
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
  });
}

/** A provider that writes chosen files instead of calling a model. */
class ScriptedProvider implements ModelProvider {
  readonly name = "scripted";
  readonly billingMode = "subscription" as const;
  lastPrompt = "";
  lastResumeSessionId: string | null = null;
  lastTimeoutMs: number | null = null;
  invokeCount = 0;

  constructor(
    private readonly writes: readonly string[],
    private readonly availability: ProviderAvailability = {
      available: true,
      detail: "test",
    },
    private readonly ok = true,
  ) {}

  async checkAvailability(): Promise<ProviderAvailability> {
    return this.availability;
  }

  async invoke(request: ProviderRequest): Promise<ProviderResponse> {
    this.invokeCount += 1;
    this.lastPrompt = request.prompt;
    this.lastResumeSessionId = request.resumeSessionId ?? null;
    this.lastTimeoutMs = request.timeoutMs;
    for (const relative of this.writes) {
      const target = path.join(request.workingDirectory, relative);
      mkdirSync(path.dirname(target), { recursive: true });
      writeFileSync(target, "changed by agent\n");
    }
    return {
      ok: this.ok,
      text: this.ok ? "Did the work." : "",
      usage: {
        inputTokens: 120,
        outputTokens: 45,
        cachedInputTokens: 0,
        costUsdMicros: 0,
      },
      model: "test-model",
      sessionId: "session-1",
      failureReason: this.ok ? null : "provider refused",
    };
  }
}

function executorFor(
  provider: ModelProvider,
  repo: ReturnType<typeof makeRepository>,
  verifier?: WorkVerifier,
) {
  return new AgentTaskExecutor({
    agent: SEED_AGENTS.engineer,
    provider,
    worktrees: new WorktreeManager(repo.root, repo.worktreeRoot),
    repository: "followville_repo",
    invocationTimeoutMs: 30_000,
    maxSubscriptionRunsPerTask: 1,
    ...(verifier === undefined ? {} : { verifier }),
  });
}

test("an in-scope edit completes and reports evidence", async () => {
  const repo = makeRepository();
  const result = await executorFor(
    new ScriptedProvider(["notes.md"]),
    repo,
  ).execute(makeTask(), new AbortController().signal);

  assert.equal(result.outcome, "completed");
  assert.deepEqual(result.filesChanged, ["company-os/notes.md"]);
  assert.ok(result.evidence.some((line) => line.startsWith("branch=agent/task-")));
  assert.ok(result.evidence.some((line) => line.includes("tokens_in=120")));
});

test("the provider invocation timeout may be selected from the task", async () => {
  const repo = makeRepository();
  const provider = new ScriptedProvider(["notes.md"]);
  const executor = new AgentTaskExecutor({
    agent: SEED_AGENTS.engineer,
    provider,
    worktrees: new WorktreeManager(repo.root, repo.worktreeRoot),
    repository: "followville_repo",
    invocationTimeoutMs: (task) =>
      task.title === "Scoped change" ? 25_000 : 15_000,
    maxSubscriptionRunsPerTask: 1,
  });
  const task = makeTask();

  await executor.execute(task, new AbortController().signal);

  assert.equal(provider.lastTimeoutMs, 25_000);
});

test("preview tasks receive a larger bounded provider window", () => {
  const regular = makeTask();
  const preview = TaskSchema.parse({
    ...makeTask(),
    allowedCapabilities: [...regular.allowedCapabilities, "blender_preview"],
  });

  assert.equal(taskInvocationTimeoutMs(regular), 15 * 60_000);
  assert.equal(taskInvocationTimeoutMs(preview), 25 * 60_000);
});

test("private social content uses the trusted runtime without spending a model run", async () => {
  const repo = makeRepository();
  const provider = new ScriptedProvider([], {
    available: false,
    reason: "unknown",
    detail: "subscription quota exhausted",
  });
  const packetId = "8c7fd5ae-5247-4ab2-b117-2e03191cdcda";
  const base = makeTask();
  const task = TaskSchema.parse({
    ...base,
    title: "Produce private preview: 500 Residents, One Living Town",
    objective: [
      `Content packet ${packetId}`,
      "Milestone: Day 27 / 500 residents / 560 buildings",
      '0-2s: Open on town. Text: "Every follow built this." VO: "Start."',
    ].join("\n"),
    allowedCapabilities: [
      "repository_read",
      "repository_write",
      "git_checkpoint",
      "test_execute",
      "blender_preview",
      "message_send",
    ],
    repositoryScopes: [
      {
        repository: "followville_repo",
        allowedPathPrefixes: [
          "company-os/content",
          "company-os/candidates/cinematic",
        ],
        deniedPathPrefixes: [
          "world_state.json",
          "town.glb",
          "town_chunks",
          "neighborhood.blend",
        ],
        environments: ["local", "preview"],
      },
    ],
  });
  let verifiedFiles: readonly string[] = [];
  const verifier: WorkVerifier = {
    async verify(input) {
      verifiedFiles = input.filesChanged;
      return {
        passed: true,
        checks: [
          {
            id: "blender-preview:trusted-town",
            label: "Trusted read-only Followville evidence",
            passed: true,
            durationMs: 12,
            output: "rendered",
          },
        ],
        unverifiedPaths: [],
        artifactFiles: [],
      };
    },
  };
  const executor = new AgentTaskExecutor({
    agent: SEED_AGENTS.engineer,
    provider,
    worktrees: new WorktreeManager(repo.root, repo.worktreeRoot),
    repository: "followville_repo",
    invocationTimeoutMs: 30_000,
    maxSubscriptionRunsPerTask: 1,
    verifier,
    artifactStore: {
      async store(input) {
        return {
          kind: "object",
          provider: "supabase_storage",
          bucket: "company-os-evidence",
          objectPath: `${input.runId}/${input.artifactId}`,
        };
      },
    },
  });

  const result = await executor.execute(
    task,
    new AbortController().signal,
    { runId: "81000000-0000-4000-8000-000000000099" },
  );

  assert.equal(result.outcome, "completed");
  assert.equal(provider.invokeCount, 0);
  assert.deepEqual(verifiedFiles, [
    `company-os/content/${packetId}/production-request.json`,
  ]);
  assert.ok(result.evidence.includes("provider=trusted-runtime"));
  assert.equal(result.modelProvider, "trusted-runtime");
  assert.equal(result.inputTokens, 0);
});

test("finished work survives on its branch after the worktree is gone", async () => {
  // The failure this guards: `git worktree remove --force` discarded
  // everything the agent produced, so an owner was asked to approve a file
  // that existed nowhere. Two tasks reached awaiting_human_approval that way.
  const repo = makeRepository();
  const task = makeTask();
  const result = await executorFor(new ScriptedProvider(["notes.md"]), repo).execute(
    task,
    new AbortController().signal,
  );
  assert.equal(result.outcome, "completed");

  const branch = `agent/task-${task.id.replace(/[^a-zA-Z0-9]/g, "").slice(0, 12)}`;
  const tracked = execFileSync(
    "git",
    ["ls-tree", "-r", "--name-only", branch, "--", "company-os/notes.md"],
    { cwd: repo.root, encoding: "utf8" },
  );
  assert.equal(tracked.trim(), "company-os/notes.md", "the work must be recoverable");

  const content = execFileSync("git", ["show", `${branch}:company-os/notes.md`], {
    cwd: repo.root,
    encoding: "utf8",
  });
  assert.match(content, /changed by agent/);
});

test("a revision starts from and extends the prior task checkpoint", async () => {
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const taskId = nextId();
  const first = await manager.create(taskId);
  writeFileSync(path.join(first.path, "company-os", "first.md"), "first attempt\n");
  const firstCommit = await manager.preserve(
    first,
    ["company-os/first.md"],
    "first checkpoint",
  );
  assert.ok(firstCommit);
  await manager.remove(first);

  const revision = await manager.create(taskId);
  assert.equal(
    revision.baseCommit,
    firstCommit,
    "a revision must continue from the checkpoint it is correcting",
  );
  const inherited = execFileSync(
    "git",
    ["show", `${revision.baseCommit}:company-os/first.md`],
    { cwd: repo.root, encoding: "utf8" },
  );
  assert.equal(inherited, "first attempt\n");

  writeFileSync(path.join(revision.path, "company-os", "second.md"), "revision\n");
  const revisionCommit = await manager.preserve(
    revision,
    ["company-os/second.md"],
    "revision checkpoint",
  );
  assert.ok(revisionCommit);
  const tracked = execFileSync(
    "git",
    [
      "ls-tree",
      "-r",
      "--name-only",
      revisionCommit!,
      "--",
      "company-os/first.md",
      "company-os/second.md",
    ],
    { cwd: repo.root, encoding: "utf8" },
  );
  assert.deepEqual(tracked.trim().split("\n").sort(), [
    "company-os/first.md",
    "company-os/second.md",
  ]);
});

test("the preserved commit is named in the evidence", async () => {
  const repo = makeRepository();
  const result = await executorFor(
    new ScriptedProvider(["notes.md"]),
    repo,
  ).execute(makeTask(), new AbortController().signal);

  const commit = result.evidence.find((line) => line.startsWith("commit="));
  assert.ok(commit, "an owner needs to know where the work is");
  assert.match(commit, /^commit=[0-9a-f]{40}$/);
});

test("runtime-owned passing checks reach the completed-work evidence", async () => {
  const repo = makeRepository();
  const verifier: WorkVerifier = {
    async verify() {
      return {
          passed: true,
          unverifiedPaths: [],
          artifactFiles: [],
          checks: [
          {
            id: "core-tests",
            label: "Company OS test suite",
            passed: true,
            durationMs: 42,
            output: "all pass",
          },
        ],
      };
    },
  };
  const result = await executorFor(
    new ScriptedProvider(["notes.md"]),
    repo,
    verifier,
  ).execute(makeTask(), new AbortController().signal);

  assert.equal(result.outcome, "completed");
  assert.deepEqual(result.testsCompleted, ["Company OS test suite"]);
  assert.ok(result.evidence.includes("check=core-tests passed 42ms"));
});

test("a failed trusted check reaches review with diagnostics for revision", async () => {
  const repo = makeRepository();
  const verifier: WorkVerifier = {
    async verify() {
      return {
          passed: false,
          unverifiedPaths: [],
          artifactFiles: [],
          checks: [
          {
            id: "core-typecheck",
            label: "Company OS strict TypeScript",
            passed: false,
            durationMs: 18,
            output: "src/example.ts(1,1): error TS1005",
          },
        ],
      };
    },
  };
  const result = await executorFor(
    new ScriptedProvider(["notes.md"]),
    repo,
    verifier,
  ).execute(makeTask(), new AbortController().signal);

  assert.equal(result.outcome, "completed");
  assert.match(result.summary, /Runtime verification failed/);
  assert.ok(result.evidence.includes("check=core-typecheck failed 18ms"));
  assert.ok(result.evidence.some((line) => line.includes("error TS1005")));
  assert.deepEqual(result.testsCompleted, []);
  assert.deepEqual(result.testsFailed, ["Company OS strict TypeScript"]);
  assert.ok(result.evidence.some((line) => line.startsWith("commit=")));
});

test("a revision attempt receives the owner's feedback", async () => {
  const repo = makeRepository();
  const provider = new ScriptedProvider(["notes.md"]);
  const executor = new AgentTaskExecutor({
    agent: SEED_AGENTS.engineer,
    provider,
    worktrees: new WorktreeManager(repo.root, repo.worktreeRoot),
    repository: "followville_repo",
    invocationTimeoutMs: 30_000,
    maxSubscriptionRunsPerTask: 1,
    reworkBriefing: async () =>
      "\n\nOwner revision feedback:\n- The mobile layout still overlaps.",
  });

  await executor.execute(makeTask(), new AbortController().signal);

  assert.match(provider.lastPrompt, /Owner revision feedback/);
  assert.match(provider.lastPrompt, /mobile layout still overlaps/);
});

test("a revision resumes only the session selected by the runtime", async () => {
  const repo = makeRepository();
  const provider = new ScriptedProvider(["notes.md"]);
  const executor = new AgentTaskExecutor({
    agent: SEED_AGENTS.engineer,
    provider,
    worktrees: new WorktreeManager(repo.root, repo.worktreeRoot),
    repository: "followville_repo",
    invocationTimeoutMs: 30_000,
    maxSubscriptionRunsPerTask: 1,
    continuityKey: "test-machine:scripted",
    resumeSessionId: async () => "session-from-prior-attempt",
  });

  const result = await executor.execute(makeTask(), new AbortController().signal);

  assert.equal(provider.lastResumeSessionId, "session-from-prior-attempt");
  assert.ok(result.evidence.includes("continuity=test-machine:scripted"));
});

test("a checkpoint preserves every approved path beyond the old 200-file limit", async () => {
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const worktree = await manager.create(nextId());
  const files = Array.from(
    { length: 205 },
    (_, index) => `company-os/bulk/file-${index.toString().padStart(3, "0")}.md`,
  );
  for (const file of files) {
    const target = path.join(worktree.path, file);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, `${file}\n`);
  }

  const diff = await manager.diff(worktree, files);
  const commit = await manager.preserve(worktree, files, "checkpoint all files");

  assert.ok(diff.includes("file-204.md"), "the review diff must include the last file");
  assert.ok(commit);
  const tracked = execFileSync(
    "git",
    ["ls-tree", "-r", "--name-only", commit!, "--", "company-os/bulk"],
    { cwd: repo.root, encoding: "utf8" },
  );
  assert.equal(tracked.trim().split("\n").length, 205);
});

test("a checkpoint refuses any branch that is not an isolated agent branch", async () => {
  // What keeps git_checkpoint from becoming a way around git_commit: the
  // runtime may record a result on a throwaway branch and nothing else.
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const worktree = await manager.create(nextId());

  await assert.rejects(
    manager.preserve({ ...worktree, branch: "main" }, ["company-os/README.md"], "no"),
    /only an isolated agent branch/,
  );
});

test("a checkpoint refuses a worktree whose history moved", async () => {
  // If the agent committed or reset for itself, a checkpoint layered on top
  // would record history nobody checked.
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const worktree = await manager.create(nextId());

  writeFileSync(path.join(worktree.path, "company-os", "own.md"), "agent commit\n");
  execFileSync("git", ["add", "-A"], { cwd: worktree.path, stdio: "pipe" });
  execFileSync("git", ["commit", "-m", "the agent committed for itself"], {
    cwd: worktree.path,
    stdio: "pipe",
  });

  writeFileSync(path.join(worktree.path, "company-os", "later.md"), "more\n");
  await assert.rejects(
    manager.preserve(worktree, ["company-os/later.md"], "no"),
    /moved from/,
  );
});

test("a checkpoint refuses to record a path that was never checked", async () => {
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const worktree = await manager.create(nextId());

  writeFileSync(path.join(worktree.path, "company-os", "checked.md"), "ok\n");
  // Already in the index before the checkpoint runs — the working tree is not
  // what the caller believes it is.
  writeFileSync(path.join(worktree.path, "world_state.json"), '{"day":99}\n');
  execFileSync("git", ["add", "--", "world_state.json"], {
    cwd: worktree.path,
    stdio: "pipe",
  });

  await assert.rejects(
    manager.preserve(worktree, ["company-os/checked.md"], "no"),
    /unchecked path/,
    "a path outside the checked set must stop the checkpoint",
  );
});

test("an agent that changed nothing preserves nothing", async () => {
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const worktree = await manager.create(nextId());
  assert.equal(await manager.preserve(worktree, [], "nothing"), null);
});

test("a task without git_checkpoint records no commit and says why", async () => {
  const repo = makeRepository();
  const task = makeTask();
  const withoutCheckpoint = {
    ...task,
    allowedCapabilities: ["repository_read", "repository_write"],
  } as Task;

  const result = await executorFor(
    new ScriptedProvider(["notes.md"]),
    repo,
  ).execute(withoutCheckpoint, new AbortController().signal);

  const commit = result.evidence.find((line) => line.startsWith("commit="));
  assert.match(commit ?? "", /does not permit git_checkpoint/);
});

test("an agent that edits the canonical world file fails instead of reaching review", async () => {
  const repo = makeRepository();
  const result = await executorFor(
    new ScriptedProvider(["../world_state.json"]),
    repo,
  ).execute(makeTask(), new AbortController().signal);

  assert.equal(result.outcome, "failed");
  assert.match(result.summary, /outside its approved scope/);
  assert.ok(result.filesChanged.includes("world_state.json"));
});

test("an agent that edits an unrelated path fails", async () => {
  const repo = makeRepository();
  const result = await executorFor(
    new ScriptedProvider(["../secrets.env"]),
    repo,
  ).execute(makeTask(), new AbortController().signal);
  assert.equal(result.outcome, "failed");
  assert.match(result.summary, /outside its approved scope/);
});

test("an unauthenticated provider blocks the task rather than failing it", async () => {
  const repo = makeRepository();
  const result = await executorFor(
    new ScriptedProvider([], {
      available: false,
      reason: "not_authenticated",
      detail: "Run: claude auth login",
    }),
    repo,
  ).execute(makeTask(), new AbortController().signal);

  assert.equal(result.outcome, "blocked");
  assert.match(result.summary, /not_authenticated/);
  assert.match(result.summary, /claude auth login/);
});

test("the durable subscription run cap blocks another model call", async () => {
  const repo = makeRepository();
  const provider = new ScriptedProvider(["notes.md"]);
  const executor = new AgentTaskExecutor({
    agent: SEED_AGENTS.engineer,
    provider,
    worktrees: new WorktreeManager(repo.root, repo.worktreeRoot),
    repository: "followville_repo",
    invocationTimeoutMs: 30_000,
    maxSubscriptionRunsPerTask: 3,
    subscriptionRunsForTask: async () => 3,
  });

  const result = await executor.execute(
    makeTask(),
    new AbortController().signal,
  );

  assert.equal(result.outcome, "blocked");
  assert.match(result.summary, /limit reached \(3\/3\)/);
  assert.equal(provider.invokeCount, 0);
});

test("a provider failure is reported as failed with usage retained", async () => {
  const repo = makeRepository();
  const result = await executorFor(
    new ScriptedProvider([], { available: true, detail: "ok" }, false),
    repo,
  ).execute(makeTask(), new AbortController().signal);

  assert.equal(result.outcome, "failed");
  assert.equal(result.summary, "provider refused");
  assert.equal(result.inputTokens, 120);
});

test("the operator's checkout is never touched", async () => {
  const repo = makeRepository();
  await executorFor(new ScriptedProvider(["notes.md"]), repo).execute(
    makeTask(),
    new AbortController().signal,
  );
  const status = execFileSync("git", ["status", "--porcelain"], {
    cwd: repo.root,
    encoding: "utf8",
  });
  assert.equal(status.trim(), "");
});

test("the agent is started in the narrowest directory containing its scope", () => {
  // The engineer's scope is confined to company-os, so the provider should be
  // pointed there rather than at 43 MB of Blender scenes it cannot touch.
  assert.equal(narrowestScopeDirectory(makeTask()), "company-os");
});

test("a scope spanning several top-level directories keeps the repository root", () => {
  const task = makeTask();
  const widened = {
    ...task,
    repositoryScopes: [
      {
        ...task.repositoryScopes[0]!,
        allowedPathPrefixes: ["company-os/", "apps/"],
      },
    ],
  } as Task;
  assert.equal(narrowestScopeDirectory(widened), null);
});

test("an unbounded scope keeps the repository root", () => {
  const task = makeTask();
  const unbounded = {
    ...task,
    repositoryScopes: [
      { ...task.repositoryScopes[0]!, allowedPathPrefixes: [""] },
    ],
  } as Task;
  assert.equal(narrowestScopeDirectory(unbounded), null);
});

test("a retry succeeds when a previous attempt left its worktree behind", async () => {
  const repo = makeRepository();
  const task = makeTask();
  const executor = executorFor(new ScriptedProvider(["notes.md"]), repo);

  const first = await executor.execute(task, new AbortController().signal);
  assert.equal(first.outcome, "completed");

  // Simulate debris from a killed run: recreate the worktree and leave it.
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  await manager.create(task.id);

  const retry = await executor.execute(task, new AbortController().signal);
  assert.equal(retry.outcome, "completed", "the retry must not fail on debris");
});
