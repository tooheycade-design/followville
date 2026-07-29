import { createHash, randomUUID } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import type { AgentProfile, Task } from "../domain/schemas.js";
import type { ModelProvider } from "../providers/types.js";
import type { ProviderResponse } from "../providers/types.js";
import { collectArtifacts, type ArtifactStore } from "./artifacts.js";
import { createHandoffArtifact } from "./handoff.js";
import { createPathGuard } from "./path-guard.js";
import type {
  TaskExecutionContext,
  TaskExecutor,
  WorkResult,
} from "./types.js";
import type { WorkVerifier } from "./verification.js";
import { WorktreeManager, type Worktree } from "./worktree.js";

/**
 * How much of the agent's own narrative is kept.
 *
 * The previous ceiling of 2,000 cut real reports mid-sentence — one ended
 * "The system of record is Supabas" — and what it cut was the part explaining
 * how the work met its criteria. The diff is captured separately now, so this
 * only has to hold prose, but it has to hold all of it.
 */
const MAX_SUMMARY_CHARS = 6_000;
const PRIVATE_CONTENT_TASK = /^Produce private preview: /;
const CONTENT_PACKET_ID =
  /^Content packet ([0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})$/im;
const TRUSTED_CONTENT_CAPABILITIES = [
  "blender_preview",
  "git_checkpoint",
  "repository_read",
  "repository_write",
  "test_execute",
] as const;

function trustedContentPacketId(task: Task): string | null {
  const packetId = task.objective.match(CONTENT_PACKET_ID)?.[1] ?? null;
  if (
    packetId === null ||
    !PRIVATE_CONTENT_TASK.test(task.title) ||
    task.allowedCapabilities.length !== TRUSTED_CONTENT_CAPABILITIES.length ||
    !TRUSTED_CONTENT_CAPABILITIES.every((capability) =>
      task.allowedCapabilities.includes(capability),
    ) ||
    task.repositoryScopes.length !== 1 ||
    !task.repositoryScopes.some(
      (scope) =>
        scope.repository === "followville_repo" &&
        scope.allowedPathPrefixes.length === 2 &&
        scope.allowedPathPrefixes.includes("company-os/content") &&
        scope.allowedPathPrefixes.includes("company-os/candidates/cinematic") &&
        scope.deniedPathPrefixes.length === 4 &&
        scope.deniedPathPrefixes.includes("world_state.json") &&
        scope.deniedPathPrefixes.includes("town.glb") &&
        scope.deniedPathPrefixes.includes("town_chunks") &&
        scope.deniedPathPrefixes.includes("neighborhood.blend"),
    )
  ) {
    return null;
  }
  return packetId;
}

async function prepareTrustedContentRequest(input: {
  task: Task;
  worktreePath: string;
  packetId: string;
}): Promise<ProviderResponse> {
  const relativeFile = path.join(
    "company-os",
    "content",
    input.packetId,
    "production-request.json",
  );
  const absoluteFile = path.join(input.worktreePath, relativeFile);
  await mkdir(path.dirname(absoluteFile), { recursive: true });
  await writeFile(
    absoluteFile,
    `${JSON.stringify(
      {
        schemaVersion: 1,
        taskId: input.task.id,
        packetId: input.packetId,
        title: input.task.title,
        objectiveSha256: createHash("sha256")
          .update(input.task.objective, "utf8")
          .digest("hex"),
        source: "trusted-read-only:town.glb",
        runtimeAsset: false,
        publishAuthorized: false,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );
  return {
    ok: true,
    text:
      "Prepared a source-pinned private render request for the trusted " +
      "canonical Followville town. No model-created proxy, canonical mutation, " +
      "or publishing action was used.",
    usage: {
      inputTokens: 0,
      outputTokens: 0,
      cachedInputTokens: 0,
      costUsdMicros: 0,
    },
    model: "trusted-content-renderer-v1",
    sessionId: null,
    failureReason: null,
  };
}

export interface AgentExecutorOptions {
  agent: AgentProfile;
  /**
   * Why this task was previously sent back, if it was. A retry told nothing
   * about its last failure usually reproduces it and burns another run.
   */
  reworkBriefing?:
    | string
    | ((task: Task) => string | Promise<string>);
  /**
   * Stable only within the provider's local session store, for example
   * `machine-name:codex`. It prevents a worker on another machine from trying
   * to resume a session ID whose files exist only on the original host.
   */
  continuityKey?: string;
  resumeSessionId?:
    | string
    | null
    | ((task: Task) => string | null | Promise<string | null>);
  provider: ModelProvider;
  worktrees: WorktreeManager;
  repository: string;
  /** Wall-clock ceiling for one provider invocation, optionally task-aware. */
  invocationTimeoutMs: number | ((task: Task) => number);
  /**
   * Subscription providers report zero dollars, so a dollar budget can never
   * bound them. This caps provider calls across every attempt of one task.
   */
  maxSubscriptionRunsPerTask: number;
  /** Counts prior subscription-backed runs from the durable run ledger. */
  subscriptionRunsForTask?:
    | number
    | ((task: Task) => number | Promise<number>);
  /** Trusted repository-owned checks, selected independently of model output. */
  verifier?: WorkVerifier;
  /** Private shared evidence storage, supplied by the worker host. */
  artifactStore?: ArtifactStore;
}

export function taskInvocationTimeoutMs(task: Task): number {
  return task.allowedCapabilities.some(
    (capability) =>
      capability === "browser_preview" || capability === "blender_preview",
  )
    ? 25 * 60_000
    : 15 * 60_000;
}

/**
 * The narrowest directory that contains everything the task may touch.
 *
 * Pointing the provider at the repository root makes it scan tens of
 * megabytes of Blender scenes and exported geometry it is not allowed to touch
 * anyway, which wastes most of a run before any work starts. When every
 * allowed prefix shares one top-level directory, the agent is started there
 * instead. This narrows attention, not permission: the policy check after the
 * run still evaluates every changed path against the full scope.
 */
export function narrowestScopeDirectory(task: Task): string | null {
  const prefixes = task.repositoryScopes.flatMap((scope) =>
    scope.allowedPathPrefixes.map((prefix) => prefix.replace(/^\/+|\/+$/g, "")),
  );
  if (prefixes.length === 0 || prefixes.some((prefix) => prefix.length === 0)) {
    return null;
  }
  const tops = new Set(prefixes.map((prefix) => prefix.split("/")[0]));
  if (tops.size !== 1) {
    return null;
  }
  const [only] = [...tops];
  return only ?? null;
}

function buildPrompt(task: Task, worktreePath: string): string {
  const criteria = task.acceptanceCriteria
    .map((criterion, index) => `${index + 1}. ${criterion.description}`)
    .join("\n");
  const scopes = task.repositoryScopes
    .map(
      (scope) =>
        `- allowed: ${scope.allowedPathPrefixes.join(", ")}` +
        (scope.deniedPathPrefixes.length > 0
          ? `\n- never touch: ${scope.deniedPathPrefixes.join(", ")}`
          : ""),
    )
    .join("\n");

  return [
    "You are an agent working for the Followville Company OS.",
    "",
    "Rules you must follow:",
    "- Work only inside this working directory: " + worktreePath,
    "- Stay strictly within the allowed paths below. Never modify denied paths.",
    "- Do not run git commit, git push, or any deployment command.",
    "- Do not modify the canonical town files (world_state.json, town.glb, neighborhood.blend).",
    "- If the task cannot be completed safely, say so plainly instead of guessing.",
    "",
    "Repository scope:",
    scopes,
    "",
    `Task: ${task.title}`,
    `Objective: ${task.objective}`,
    "",
    "Acceptance criteria:",
    criteria,
    "",
    "When finished, summarize in plain prose what you changed and what evidence",
    "supports that it works. If you changed nothing, say so and explain why.",
  ].join("\n");
}

/**
 * Runs a task with a real model inside a disposable worktree.
 *
 * The worktree is the containment boundary: the provider is pointed at it and
 * nowhere else, so an agent that ignores its instructions still cannot reach
 * the operator's checkout. Every file it touched is then re-checked against
 * the policy engine, because a prompt is guidance, not enforcement — an agent
 * that wandered outside its scope fails the task rather than reaching review.
 */
export class AgentTaskExecutor implements TaskExecutor {
  readonly name: string;

  constructor(private readonly options: AgentExecutorOptions) {
    this.name = `agent:${options.provider.name}`;
  }

  async execute(
    task: Task,
    signal: AbortSignal,
    context?: TaskExecutionContext,
  ): Promise<WorkResult> {
    const contentPacketId = trustedContentPacketId(task);
    if (contentPacketId === null) {
      const availability = await this.options.provider.checkAvailability();
      if (!availability.available) {
        return {
          outcome: "blocked",
          summary: `Provider unavailable (${availability.reason}): ${availability.detail}`,
          evidence: [],
          filesChanged: [],
          diff: null,
          artifacts: [],
          testsCompleted: [],
          testsFailed: [],
          modelProvider: null,
          modelId: null,
          inputTokens: 0,
          outputTokens: 0,
          cachedInputTokens: 0,
          costUsdMicros: 0,
        };
      }
    }
    if (
      (task.allowedCapabilities.includes("browser_preview") ||
        task.allowedCapabilities.includes("blender_preview")) &&
      this.options.artifactStore === undefined
    ) {
      return {
        outcome: "blocked",
        summary:
          "Preview work requires private shared artifact storage on this worker.",
        evidence: [],
        filesChanged: [],
        diff: null,
        artifacts: [],
        testsCompleted: [],
        testsFailed: [],
        modelProvider: null,
        modelId: null,
        inputTokens: 0,
        outputTokens: 0,
        cachedInputTokens: 0,
        costUsdMicros: 0,
      };
    }
    if (
      contentPacketId === null &&
      this.options.provider.billingMode === "subscription"
    ) {
      const priorRuns =
        typeof this.options.subscriptionRunsForTask === "function"
          ? await this.options.subscriptionRunsForTask(task)
          : (this.options.subscriptionRunsForTask ?? 0);
      if (
        !Number.isInteger(priorRuns) ||
        priorRuns < 0 ||
        !Number.isInteger(this.options.maxSubscriptionRunsPerTask) ||
        this.options.maxSubscriptionRunsPerTask < 1
      ) {
        return {
          outcome: "blocked",
          summary:
            "Subscription run accounting is invalid; the provider was not invoked.",
          evidence: [],
          filesChanged: [],
          diff: null,
          artifacts: [],
          testsCompleted: [],
          testsFailed: [],
          modelProvider: null,
          modelId: null,
          inputTokens: 0,
          outputTokens: 0,
          cachedInputTokens: 0,
          costUsdMicros: 0,
        };
      }
      if (priorRuns >= this.options.maxSubscriptionRunsPerTask) {
        return {
          outcome: "blocked",
          summary:
            `Subscription run limit reached (${priorRuns}/${this.options.maxSubscriptionRunsPerTask}). ` +
            "Create a narrower owner-reviewed task before using another model run.",
          evidence: [
            `subscription-runs=${priorRuns}/${this.options.maxSubscriptionRunsPerTask}`,
          ],
          filesChanged: [],
          diff: null,
          artifacts: [],
          testsCompleted: [],
          testsFailed: [],
          modelProvider: null,
          modelId: null,
          inputTokens: 0,
          outputTokens: 0,
          cachedInputTokens: 0,
          costUsdMicros: 0,
        };
      }
    }

    let worktree: Worktree | null = null;
    try {
      worktree = await this.options.worktrees.create(task.id);
      const scopeDirectory = narrowestScopeDirectory(task);
      const workingDirectory =
        scopeDirectory === null
          ? worktree.path
          : `${worktree.path}/${scopeDirectory}`;
      const reworkBriefing =
        typeof this.options.reworkBriefing === "function"
          ? await this.options.reworkBriefing(task)
          : (this.options.reworkBriefing ?? "");
      const resumeSessionId =
        typeof this.options.resumeSessionId === "function"
          ? await this.options.resumeSessionId(task)
          : (this.options.resumeSessionId ?? null);
      const invocationTimeoutMs =
        typeof this.options.invocationTimeoutMs === "function"
          ? this.options.invocationTimeoutMs(task)
          : this.options.invocationTimeoutMs;
      const response =
        contentPacketId === null
          ? await this.options.provider.invoke({
              workingDirectory,
              prompt: buildPrompt(task, workingDirectory) + reworkBriefing,
              ...(resumeSessionId === null ? {} : { resumeSessionId }),
              timeoutMs: invocationTimeoutMs,
              signal,
            })
          : await prepareTrustedContentRequest({
              task,
              worktreePath: worktree.path,
              packetId: contentPacketId,
            });
      const executionProvider =
        contentPacketId === null ? this.options.provider.name : "trusted-runtime";

      const changes = await this.options.worktrees.changes(worktree);
      const filesChanged = changes.map((change) => change.file);

      // Capture the change itself, not just the agent's account of it. Codex
      // happens to paste a diff into its prose and Claude does not; evidence a
      // judge needs cannot depend on which model did the work. Best effort —
      // failing to read a diff must not fail a task that otherwise succeeded.
      const diff = await this.options.worktrees
        .diff(worktree, filesChanged)
        .catch(() => null);

      // Record the result on its review branch before the worktree goes away,
      // so an approval packet refers to something that still exists. The
      // trailers tie the commit to the task and the base it was made from, so
      // a branch found later can be matched to its evidence packet.
      //
      // Best effort for the same reason as the diff: losing the record is bad,
      // but failing a finished task because git declined to record it is
      // worse. A refusal from `preserve` is a real signal, so it is reported
      // in the evidence rather than swallowed.
      let commit: string | null = null;
      let checkpointRefusal: string | null = null;
      if (!task.allowedCapabilities.includes("git_checkpoint")) {
        checkpointRefusal = "the task does not permit git_checkpoint";
      } else {
        try {
          commit = await this.options.worktrees.preserve(
            worktree,
            filesChanged,
            [
              `Agent work for task ${task.id.slice(0, 8)}`,
              "",
              `Unreviewed output of ${executionProvider}, kept so an owner`,
              "can inspect it. This branch is never pushed and never merged.",
              "",
              `Task: ${task.id}`,
              `Base: ${worktree.baseCommit}`,
              `Provider: ${executionProvider}`,
            ].join("\n"),
          );
        } catch (error) {
          checkpointRefusal = (error as Error).message;
        }
      }

      if (!response.ok) {
        return {
          outcome: "failed",
          summary: response.failureReason ?? "The provider failed.",
          evidence: [],
          filesChanged,
          diff,
          artifacts: [],
          testsCompleted: [],
          testsFailed: [],
        modelProvider: executionProvider,
          modelId: response.model,
          inputTokens: response.usage.inputTokens,
          outputTokens: response.usage.outputTokens,
          cachedInputTokens: response.usage.cachedInputTokens,
          costUsdMicros: response.usage.costUsdMicros,
        };
      }

      // A prompt is not a permission system. Verify every touched path.
      const guard = createPathGuard(
        this.options.agent,
        task,
        this.options.repository,
        worktree.path,
      );
      const violations = filesChanged.filter(
        (file) => guard.check("repository_write", file).outcome !== "allowed",
      );
      if (violations.length > 0) {
        return {
          outcome: "failed",
          summary:
            `The agent modified ${violations.length} path(s) outside its approved scope: ` +
            violations.slice(0, 5).join(", "),
          evidence: [],
          filesChanged,
          diff,
          artifacts: [],
          testsCompleted: [],
          testsFailed: [],
          modelProvider: executionProvider,
          modelId: response.model,
          inputTokens: response.usage.inputTokens,
          outputTokens: response.usage.outputTokens,
          cachedInputTokens: response.usage.cachedInputTokens,
          costUsdMicros: response.usage.costUsdMicros,
        };
      }

      const evidence = [
        `provider=${executionProvider}`,
        ...(this.options.continuityKey === undefined
          ? []
          : [`continuity=${this.options.continuityKey}`]),
        `branch=${worktree.branch}`,
        `base=${worktree.baseCommit.slice(0, 12)}`,
        `files_changed=${filesChanged.length}`,
        `tokens_in=${response.usage.inputTokens} tokens_out=${response.usage.outputTokens}`,
      ];
      if (response.sessionId !== null) {
        evidence.push(`session=${response.sessionId}`);
      }
      // Where the work actually is. Without this an owner could read a summary
      // and a diff but had nothing to check out. When no checkpoint was made,
      // the reason is stated: "not recorded" and "recorded elsewhere" must not
      // look the same to whoever reads this next.
      evidence.push(
        commit !== null
          ? `commit=${commit}`
          : `commit=none (${checkpointRefusal ?? "nothing to record"})`,
      );
      // The file list is no longer folded into this line. It is a section of
      // the report in its own right, so it is neither capped at twenty nor
      // recovered by splitting a sentence apart.

      const verification =
        this.options.verifier === undefined
          ? {
              passed: true,
              checks: [],
              unverifiedPaths: [],
              artifactFiles: [],
            }
          : await this.options.verifier.verify({
              task,
              worktree,
              filesChanged,
              ...(context?.runId === undefined ? {} : { runId: context.runId }),
              signal,
            });
      for (const check of verification.checks) {
        evidence.push(
          `check=${check.id} ${check.passed ? "passed" : "failed"} ${check.durationMs}ms`,
        );
        if (!check.passed && check.output.length > 0) {
          evidence.push(
            `check_output=${check.output.replace(/\s+/g, " ").slice(0, 800)}`,
          );
        }
      }
      for (const unverified of verification.unverifiedPaths) {
        evidence.push(`unverified=${unverified}`);
      }
      const testsCompleted = verification.checks
        .filter((check) => check.passed)
        .map((check) => check.label);
      const testsFailed = [
        ...verification.checks
          .filter((check) => !check.passed)
          .map((check) => check.label),
        ...verification.unverifiedPaths,
      ];
      const text = response.text.trim();
      const modelSummary =
        (text.length > MAX_SUMMARY_CHARS
          ? `${text.slice(0, MAX_SUMMARY_CHARS)}\n[summary truncated at ${MAX_SUMMARY_CHARS} characters]`
          : text) || "The agent reported no summary.";
      const summary = verification.passed
        ? modelSummary
        : `${modelSummary}\n\nRuntime verification failed: ${
            testsFailed.join(", ") || "unknown check"
          }`;

      // Collected while the worktree still exists; afterwards these files are
      // only reachable through the checkpoint commit.
      const artifacts = await collectArtifacts({
        task,
        worktreePath: worktree.path,
        filesChanged,
        evidenceFiles: verification.artifactFiles ?? [],
        commitSha: commit,
        diff,
        runId: context?.runId ?? null,
        ...(this.options.artifactStore === undefined
          ? {}
          : { artifactStore: this.options.artifactStore }),
        createdByAgentId: this.options.agent.id,
        idFactory: randomUUID,
      });
      const remainingWork = verification.passed
        ? [
            "Independent review",
            "Chief Executive quality gate",
            "Authenticated owner decision",
          ]
        : testsFailed.map((failure) => `Correct failed verification: ${failure}`);
      const handoff = createHandoffArtifact({
        id: randomUUID(),
        task,
        runId: context?.runId ?? null,
        agentId: this.options.agent.id,
        branch: worktree.branch,
        baseCommit: worktree.baseCommit,
        checkpointCommit: commit,
        workCompleted: summary,
        remainingWork,
        filesChanged,
        testsRun: testsCompleted,
        testFailures: testsFailed,
        artifactIds: artifacts.map((artifact) => artifact.id),
        blockers: verification.unverifiedPaths,
          modelProvider: executionProvider,
        modelId: response.model,
        workerContinuityKey:
          this.options.continuityKey ??
          `unknown-host:${executionProvider}`,
        recommendedNextAction: verification.passed
          ? "Have the independent reviewer inspect the checkpoint and recorded evidence."
          : "Start a revision from this checkpoint and address every failed trusted check.",
      });
      artifacts.push(handoff);
      const visual = artifacts.filter(
        (artifact) => artifact.kind !== "patch" && artifact.kind !== "log",
      );
      if (artifacts.length > 0) {
        evidence.push(
          `artifacts=${artifacts.length}` +
            (visual.length > 0 ? ` (${visual.length} visual)` : ""),
        );
      }

      return {
        outcome: "completed",
        summary,
        evidence,
        filesChanged,
        diff,
        artifacts,
        testsCompleted,
        testsFailed,
        modelProvider: executionProvider,
        modelId: response.model,
        inputTokens: response.usage.inputTokens,
        outputTokens: response.usage.outputTokens,
        cachedInputTokens: response.usage.cachedInputTokens,
        costUsdMicros: response.usage.costUsdMicros,
      };
    } finally {
      if (worktree !== null) {
        // Best effort: a leaked worktree is noise, not a correctness problem,
        // and must not mask the real result.
        await this.options.worktrees.remove(worktree).catch(() => undefined);
      }
    }
  }
}
