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
import { AgentTaskExecutor, narrowestScopeDirectory } from "./agent-executor.js";
import { WorktreeManager } from "./worktree.js";

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
    allowedCapabilities: ["repository_read", "repository_write"],
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

function executorFor(provider: ModelProvider, repo: ReturnType<typeof makeRepository>) {
  return new AgentTaskExecutor({
    agent: SEED_AGENTS.engineer,
    provider,
    worktrees: new WorktreeManager(repo.root, repo.worktreeRoot),
    repository: "followville_repo",
    invocationTimeoutMs: 30_000,
    maxSubscriptionRunsPerTask: 1,
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

test("the preserved commit is named in the evidence", async () => {
  const repo = makeRepository();
  const result = await executorFor(
    new ScriptedProvider(["notes.md"]),
    repo,
  ).execute(makeTask(), new AbortController().signal);

  const commit = result.evidence.find((line) => line.startsWith("commit="));
  assert.ok(commit, "an owner needs to know where the work is");
  assert.match(commit, /^commit=[0-9a-f]{12}$/);
});

test("preserving refuses any branch that is not an isolated agent branch", async () => {
  // The guarantee that keeps this from being a way around git_commit: the
  // runtime may record a result on a throwaway branch and nothing else.
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const worktree = await manager.create(nextId());

  await assert.rejects(
    manager.preserve({ ...worktree, branch: "main" }, ["company-os/README.md"], "no"),
    /only an isolated agent branch/,
  );
});

test("an agent that changed nothing preserves nothing", async () => {
  const repo = makeRepository();
  const manager = new WorktreeManager(repo.root, repo.worktreeRoot);
  const worktree = await manager.create(nextId());
  assert.equal(await manager.preserve(worktree, [], "nothing"), null);
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
