import { execFile } from "node:child_process";
import { promisify } from "node:util";

import type { Task } from "../domain/schemas.js";
import type { TaskExecutor, WorkResult } from "./types.js";

const run = promisify(execFile);

/**
 * A deterministic executor that calls no model and spends nothing.
 *
 * It exists to prove the runtime end to end — leasing, heartbeats, policy
 * re-checks, evidence, and the handoff to review — before a real model is
 * connected. Reading repository facts is genuinely useful work for a reporter
 * agent, and it is safe because the executor only reads.
 */
export class RepositoryReportExecutor implements TaskExecutor {
  readonly name = "repository-report";

  constructor(private readonly repositoryRoot: string) {}

  async execute(task: Task, signal: AbortSignal): Promise<WorkResult> {
    if (!task.allowedCapabilities.includes("repository_read")) {
      return {
        outcome: "blocked",
        summary: "The task does not permit reading the repository.",
        evidence: [],
        filesChanged: [],
        diff: null,
        artifacts: [],
        modelProvider: null,
        modelId: null,
        inputTokens: 0,
        outputTokens: 0,
        costUsdMicros: 0,
      };
    }

    const git = async (...args: string[]): Promise<string> => {
      const { stdout } = await run("git", args, {
        cwd: this.repositoryRoot,
        signal,
        maxBuffer: 4_000_000,
      });
      return stdout.trim();
    };

    const [branch, head, changed, commitCount] = await Promise.all([
      git("rev-parse", "--abbrev-ref", "HEAD"),
      git("rev-parse", "--short", "HEAD"),
      git("status", "--porcelain"),
      git("rev-list", "--count", "HEAD"),
    ]);

    const dirtyFiles = changed
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0);

    return {
      outcome: "completed",
      summary:
        `Branch ${branch} at ${head}, ${commitCount} commits, ` +
        `${dirtyFiles.length} uncommitted path(s).`,
      evidence: [
        `git rev-parse --abbrev-ref HEAD -> ${branch}`,
        `git rev-parse --short HEAD -> ${head}`,
        `git rev-list --count HEAD -> ${commitCount}`,
        `git status --porcelain -> ${dirtyFiles.length} entries`,
      ],
      filesChanged: [],
      // This executor inspects the repository and changes nothing, so there is
      // no diff to show rather than one that failed to be captured.
      diff: null,
      artifacts: [],
      modelProvider: null,
      modelId: null,
      inputTokens: 0,
      outputTokens: 0,
      costUsdMicros: 0,
    };
  }
}
