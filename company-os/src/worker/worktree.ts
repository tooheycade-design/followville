import { execFile } from "node:child_process";
import { rm } from "node:fs/promises";
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

    // A previous attempt that was killed or lost its lease leaves its worktree
    // behind, and `git worktree add` refuses an existing path. Since tasks are
    // requeued after failure, a retry would otherwise fail forever on debris
    // from the very failure it is retrying.
    await this.#git(["worktree", "prune"]).catch(() => undefined);
    await this.#git(["worktree", "remove", "--force", target]).catch(
      () => undefined,
    );
    await rm(target, { recursive: true, force: true }).catch(() => undefined);

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

  /**
   * The change the agent made, as a diff against the commit it started from.
   *
   * New files are the normal case here — most tasks write a file that did not
   * exist before — and `git diff` ignores untracked paths, so a plain diff of
   * an agent's work is usually empty. Recording an intent to add first makes
   * them appear as additions. That touches only the index of a worktree which
   * is about to be thrown away.
   */
  async diff(worktree: Worktree, files: readonly string[] = []): Promise<string> {
    const named = files.slice(0, 200);
    if (named.length > 0) {
      await this.#git(
        ["add", "--intent-to-add", "--", ...named],
        worktree.path,
      ).catch(() => undefined);
    }
    return this.#git(["diff", worktree.baseCommit, "--"], worktree.path);
  }

  /**
   * Commits what the agent produced onto its own review branch.
   *
   * Removing a worktree discards everything uncommitted inside it, and the
   * engineer never commits for itself — `git_commit` is one of the
   * capabilities it may only exercise with human approval. So until this
   * existed, finished work was destroyed the moment its task ended, and an
   * owner was asked to approve a file that no longer existed anywhere. The
   * branch was retained, but it still pointed at the base commit.
   *
   * This is the runtime preserving a result, not the agent exercising
   * `git_commit`. The distinction is kept honest by construction rather than
   * by intent: it writes only to the isolated `agent/task-*` branch the
   * runtime created, refuses any other ref, and never pushes. Nothing here
   * moves work toward production, which is what that approval gate protects.
   *
   * Returns the commit, or null when the agent changed nothing.
   */
  async preserve(
    worktree: Worktree,
    files: readonly string[],
    message: string,
  ): Promise<string | null> {
    if (!/^agent\/task-[A-Za-z0-9]+$/.test(worktree.branch)) {
      throw new Error(
        `Refusing to commit to "${worktree.branch}": only an isolated agent branch may be written.`,
      );
    }
    if (files.length === 0) {
      return null;
    }

    await this.#git(["add", "--", ...files.slice(0, 200)], worktree.path);
    const staged = await this.#git(
      ["diff", "--cached", "--name-only"],
      worktree.path,
    );
    if (staged.length === 0) {
      return null;
    }

    // An identity is supplied explicitly so preservation does not depend on
    // whichever machine happens to be running the worker having git configured.
    await this.#git(
      [
        "-c",
        "user.name=Followville Company OS",
        "-c",
        "user.email=company-os@followville.invalid",
        "commit",
        "-m",
        message,
      ],
      worktree.path,
    );
    return this.#git(["rev-parse", "HEAD"], worktree.path);
  }

  /**
   * Removes the worktree. Retains the branch, which now carries the preserved
   * commit, so the result outlives the disposable checkout it was made in.
   */
  async remove(worktree: Worktree): Promise<void> {
    await this.#git(["worktree", "remove", "--force", worktree.path]);
  }

  async prune(): Promise<void> {
    await this.#git(["worktree", "prune"]);
  }
}
