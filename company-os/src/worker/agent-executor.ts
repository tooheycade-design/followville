import type { AgentProfile, Task } from "../domain/schemas.js";
import type { ModelProvider } from "../providers/types.js";
import { createPathGuard } from "./path-guard.js";
import type { TaskExecutor, WorkResult } from "./types.js";
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

export interface AgentExecutorOptions {
  agent: AgentProfile;
  /**
   * Why this task was previously sent back, if it was. A retry told nothing
   * about its last failure usually reproduces it and burns another run.
   */
  reworkBriefing?: string;
  provider: ModelProvider;
  worktrees: WorktreeManager;
  repository: string;
  /** Wall-clock ceiling for one provider invocation. */
  invocationTimeoutMs: number;
  /**
   * Subscription providers report zero dollars, so a dollar budget can never
   * bound them. This caps how long one task may occupy the subscription.
   */
  maxSubscriptionRunsPerTask: number;
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

  async execute(task: Task, signal: AbortSignal): Promise<WorkResult> {
    const availability = await this.options.provider.checkAvailability();
    if (!availability.available) {
      return {
        outcome: "blocked",
        summary: `Provider unavailable (${availability.reason}): ${availability.detail}`,
        evidence: [],
        filesChanged: [],
        diff: null,
        modelProvider: this.options.provider.name,
        modelId: null,
        inputTokens: 0,
        outputTokens: 0,
        costUsdMicros: 0,
      };
    }

    let worktree: Worktree | null = null;
    try {
      worktree = await this.options.worktrees.create(task.id);
      const scopeDirectory = narrowestScopeDirectory(task);
      const workingDirectory =
        scopeDirectory === null
          ? worktree.path
          : `${worktree.path}/${scopeDirectory}`;
      const response = await this.options.provider.invoke({
        workingDirectory,
        prompt:
          buildPrompt(task, workingDirectory) +
          (this.options.reworkBriefing ?? ""),
        timeoutMs: this.options.invocationTimeoutMs,
        signal,
      });

      const changes = await this.options.worktrees.changes(worktree);
      const filesChanged = changes.map((change) => change.file);

      // Capture the change itself, not just the agent's account of it. Codex
      // happens to paste a diff into its prose and Claude does not; evidence a
      // judge needs cannot depend on which model did the work. Best effort —
      // failing to read a diff must not fail a task that otherwise succeeded.
      const diff = await this.options.worktrees
        .diff(worktree, filesChanged)
        .catch(() => null);

      if (!response.ok) {
        return {
          outcome: "failed",
          summary: response.failureReason ?? "The provider failed.",
          evidence: [],
          filesChanged,
          diff,
          modelProvider: this.options.provider.name,
          modelId: response.model,
          inputTokens: response.usage.inputTokens,
          outputTokens: response.usage.outputTokens,
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
          modelProvider: this.options.provider.name,
          modelId: response.model,
          inputTokens: response.usage.inputTokens,
          outputTokens: response.usage.outputTokens,
          costUsdMicros: response.usage.costUsdMicros,
        };
      }

      const evidence = [
        `provider=${this.options.provider.name}`,
        `branch=${worktree.branch}`,
        `base=${worktree.baseCommit.slice(0, 12)}`,
        `files_changed=${filesChanged.length}`,
        `tokens_in=${response.usage.inputTokens} tokens_out=${response.usage.outputTokens}`,
      ];
      if (response.sessionId !== null) {
        evidence.push(`session=${response.sessionId}`);
      }
      // The file list is no longer folded into this line. It is a section of
      // the report in its own right, so it is neither capped at twenty nor
      // recovered by splitting a sentence apart.

      const text = response.text.trim();
      return {
        outcome: "completed",
        summary:
          (text.length > MAX_SUMMARY_CHARS
            ? `${text.slice(0, MAX_SUMMARY_CHARS)}\n[summary truncated at ${MAX_SUMMARY_CHARS} characters]`
            : text) || "The agent reported no summary.",
        evidence,
        filesChanged,
        diff,
        modelProvider: this.options.provider.name,
        modelId: response.model,
        inputTokens: response.usage.inputTokens,
        outputTokens: response.usage.outputTokens,
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
