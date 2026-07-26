import { execFile } from "node:child_process";
import path from "node:path";
import { promisify } from "node:util";

const run = promisify(execFile);

export interface Worktree {
  path: string;
  branch: string;
  baseCommit: string;
}

export interface WorktreeChange {
  status: string;
  file: string;
}

/** Git quotes paths containing unusual characters. */
function unquote(value: string): string {
  if (value.startsWith('"') && value.endsWith('"') && value.length >= 2) {
    try {
      return JSON.parse(value) as string;
    } catch {
      return value.slice(1, -1);
    }
  }
  return value;
}

/**
 * Gives each task its own git worktree and branch.
 *
 * Two agents working in one checkout would overwrite each other, and a shared
 * checkout also means a failed run can leave debris that the next task
 * inherits. A worktree is cheap, disposable, and cannot reach the operator's
 * working tree, so an agent that misbehaves damages only its own copy.
 */
export class WorktreeManager {
  constructor(
    private readonly repositoryRoot: string,
    private readonly worktreeRoot: string,
  ) {}

  async #git(args: string[], cwd = this.repositoryRoot): Promise<string> {
    return (await this.#gitRaw(args, cwd)).trim();
  }

  /**
   * Untrimmed output. Porcelain status encodes state in the first two columns,
   * and a modified tracked file begins with a space, so trimming the whole
   * output shifts every filename by one character.
   */
  async #gitRaw(args: string[], cwd = this.repositoryRoot): Promise<string> {
    const { stdout } = await run("git", args, { cwd, maxBuffer: 8_000_000 });
    return stdout;
  }

  /** Creates an isolated worktree for a task, branched from `baseRef`. */
  async create(taskId: string, baseRef = "HEAD"): Promise<Worktree> {
    const short = taskId.replace(/[^a-zA-Z0-9]/g, "").slice(0, 12);
    const branch = `agent/task-${short}`;
    const target = path.join(this.worktreeRoot, `task-${short}`);

    await this.#git(["worktree", "add", "--detach", target, baseRef]);
    await this.#git(["checkout", "-B", branch], target);
    const baseCommit = await this.#git(["rev-parse", "HEAD"], target);

    return { path: target, branch, baseCommit };
  }

  /** Files the agent actually touched, including untracked ones. */
  async changes(worktree: Worktree): Promise<readonly WorktreeChange[]> {
    const output = await this.#gitRaw(
      ["status", "--porcelain", "--untracked-files=all"],
      worktree.path,
    );
    return output
      .split("\n")
      .filter((line) => line.length > 3)
      .map((line) => ({
        status: line.slice(0, 2).trim(),
        // Renames report "old -> new"; the destination is what was written.
        file: unquote(line.slice(3).replace(/^.* -> /, "").trimEnd()),
      }))
      .filter((change) => change.file.length > 0);
  }

  async diff(worktree: Worktree): Promise<string> {
    return this.#git(["diff", worktree.baseCommit], worktree.path);
  }

  /**
   * Removes the worktree. Retains the branch so a result can still be
   * inspected after cleanup; an abandoned branch is recoverable, whereas a
   * deleted one is not.
   */
  async remove(worktree: Worktree): Promise<void> {
    await this.#git(["worktree", "remove", "--force", worktree.path]);
  }

  async prune(): Promise<void> {
    await this.#git(["worktree", "prune"]);
  }
}
