import { execFile } from "node:child_process";
import { lstat, mkdir, realpath, symlink } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import type { Task } from "../domain/schemas.js";
import {
  PlaywrightBrowserPreviewRunner,
  type BrowserPreviewRunner,
} from "./browser-preview.js";
import type { Worktree } from "./worktree.js";

const exec = promisify(execFile);
const MAX_OUTPUT_CHARS = 6_000;

export interface VerificationCommand {
  id: string;
  label: string;
  executable: string;
  args: readonly string[];
  cwd: string;
  timeoutMs: number;
}

export interface VerificationCheck {
  id: string;
  label: string;
  passed: boolean;
  durationMs: number;
  output: string;
}

export interface VerificationResult {
  passed: boolean;
  checks: readonly VerificationCheck[];
  unverifiedPaths: readonly string[];
  artifactFiles: readonly string[];
}

export interface WorkVerifier {
  verify(input: {
    task: Task;
    worktree: Worktree;
    filesChanged: readonly string[];
    runId?: string;
    signal: AbortSignal;
  }): Promise<VerificationResult>;
}

export type VerificationCommandRunner = (
  command: VerificationCommand,
  signal: AbortSignal,
) => Promise<{ exitCode: number; output: string }>;

function cleanOutput(output: string): string {
  const normalized = output.replace(/\u0000/g, "").trim();
  return normalized.length > MAX_OUTPUT_CHARS
    ? `${normalized.slice(0, MAX_OUTPUT_CHARS)}\n[output truncated]`
    : normalized;
}

export const runVerificationCommand: VerificationCommandRunner = async (
  command,
  signal,
) => {
  try {
    const { stdout, stderr } = await exec(command.executable, [...command.args], {
      cwd: command.cwd,
      timeout: command.timeoutMs,
      signal,
      windowsHide: true,
      maxBuffer: 8_000_000,
      env: process.env,
    });
    return { exitCode: 0, output: cleanOutput(`${stdout}\n${stderr}`) };
  } catch (error) {
    const failure = error as Error & {
      code?: string | number;
      stdout?: string;
      stderr?: string;
      killed?: boolean;
    };
    const reason = failure.killed
      ? `Timed out after ${command.timeoutMs}ms.`
      : failure.message;
    return {
      exitCode:
        typeof failure.code === "number" && Number.isInteger(failure.code)
          ? failure.code
          : 1,
      output: cleanOutput(
        [failure.stdout, failure.stderr, reason].filter(Boolean).join("\n"),
      ),
    };
  }
};

type CheckKind =
  | "diff-check"
  | "core-typecheck"
  | "core-tests"
  | "dashboard-typecheck"
  | "dashboard-tests"
  | "dashboard-build"
  | "town-browser-tests";

const COMPANY_CODE = /^(?:company-os\/(?:src|db)\/|company-os\/(?:package|tsconfig))/;
const DASHBOARD_CODE =
  /^apps\/company-dashboard\/(?:src\/|package|tsconfig|next\.config)/;
const TOWN_WEB =
  /^(?:index\.html|town\.html|admin\.html|vercel\.json|playwright\.config\.mjs|tests\/|assets\/)/;
const WORKSPACE_DEPENDENCIES = /^(?:package\.json|pnpm-lock\.yaml|pnpm-workspace\.yaml)$/;
const NON_CODE = /(?:^|\/)(?:docs?\/|README(?:\.[^/]*)?$)|\.(?:md|txt)$/i;

/** Fixed check selection. No task or model text is ever interpreted as a command. */
export function verificationKinds(filesChanged: readonly string[]): {
  kinds: readonly CheckKind[];
  unverifiedPaths: readonly string[];
} {
  if (filesChanged.length === 0) {
    return { kinds: [], unverifiedPaths: [] };
  }

  const kinds = new Set<CheckKind>(["diff-check"]);
  const unverifiedPaths: string[] = [];
  for (const file of filesChanged) {
    if (WORKSPACE_DEPENDENCIES.test(file)) {
      kinds.add("core-typecheck");
      kinds.add("core-tests");
      kinds.add("dashboard-typecheck");
      kinds.add("dashboard-tests");
      kinds.add("dashboard-build");
      kinds.add("town-browser-tests");
    } else if (COMPANY_CODE.test(file)) {
      kinds.add("core-typecheck");
      kinds.add("core-tests");
    } else if (DASHBOARD_CODE.test(file)) {
      kinds.add("dashboard-typecheck");
      kinds.add("dashboard-tests");
      kinds.add("dashboard-build");
    } else if (TOWN_WEB.test(file)) {
      kinds.add("town-browser-tests");
    } else if (!NON_CODE.test(file)) {
      unverifiedPaths.push(file);
    }
  }
  return { kinds: [...kinds], unverifiedPaths };
}

export async function provisionTrustedDirectory(
  target: string,
  link: string,
): Promise<void> {
  let exists = true;
  try {
    await lstat(link);
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
      throw error;
    }
    exists = false;
  }
  if (exists) {
    const [actual, expected] = await Promise.all([realpath(link), realpath(target)]);
    if (path.normalize(actual) !== path.normalize(expected)) {
      throw new Error(
        `Refusing untrusted dependency path ${link}; expected ${expected}, found ${actual}.`,
      );
    }
    return;
  }
  await mkdir(path.dirname(link), { recursive: true });
  await symlink(target, link, process.platform === "win32" ? "junction" : "dir");
}

export class RepositoryVerificationRunner implements WorkVerifier {
  private readonly provisionDependencies: boolean;

  constructor(
    private readonly trustedRepositoryRoot: string,
    private readonly commandRunner: VerificationCommandRunner =
      runVerificationCommand,
    private readonly browserPreview: BrowserPreviewRunner =
      new PlaywrightBrowserPreviewRunner(trustedRepositoryRoot),
  ) {
    this.provisionDependencies = commandRunner === runVerificationCommand;
  }

  private command(kind: CheckKind, worktree: Worktree): VerificationCommand {
    const node = process.execPath;
    const core = path.join(worktree.path, "company-os");
    const dashboard = path.join(worktree.path, "apps", "company-dashboard");
    const trustedCore = path.join(this.trustedRepositoryRoot, "company-os");
    const trustedDashboard = path.join(
      this.trustedRepositoryRoot,
      "apps",
      "company-dashboard",
    );

    switch (kind) {
      case "diff-check":
        return {
          id: kind,
          label: "Git whitespace and patch integrity",
          executable: "git",
          args: ["diff", "--check", worktree.baseCommit, "--"],
          cwd: worktree.path,
          timeoutMs: 30_000,
        };
      case "core-typecheck":
        return {
          id: kind,
          label: "Company OS strict TypeScript",
          executable: node,
          args: [
            path.join(trustedCore, "node_modules", "typescript", "bin", "tsc"),
            "--noEmit",
          ],
          cwd: core,
          timeoutMs: 90_000,
        };
      case "core-tests":
        return {
          id: kind,
          label: "Company OS test suite",
          executable: node,
          args: [
            path.join(trustedCore, "node_modules", "tsx", "dist", "cli.mjs"),
            "--test",
            "src/**/*.test.ts",
          ],
          cwd: core,
          timeoutMs: 180_000,
        };
      case "dashboard-typecheck":
        return {
          id: kind,
          label: "Dashboard strict TypeScript",
          executable: node,
          args: [
            path.join(
              trustedDashboard,
              "node_modules",
              "typescript",
              "bin",
              "tsc",
            ),
            "--noEmit",
          ],
          cwd: dashboard,
          timeoutMs: 90_000,
        };
      case "dashboard-tests":
        return {
          id: kind,
          label: "Dashboard test suite",
          executable: node,
          args: [
            path.join(
              trustedDashboard,
              "node_modules",
              "tsx",
              "dist",
              "cli.mjs",
            ),
            "--test",
            "src/lib/state/file-repository.test.ts",
            "src/lib/state/file-repository.readonly.test.ts",
            "src/lib/state/supabase-repository.test.ts",
            "src/lib/state/supabase-queue.test.ts",
            "src/lib/state/retry.test.ts",
            "src/lib/commands.test.ts",
            "src/lib/auth-policy.test.ts",
          ],
          cwd: dashboard,
          timeoutMs: 120_000,
        };
      case "dashboard-build":
        return {
          id: kind,
          label: "Dashboard production build",
          executable: node,
          args: [
            path.join(
              trustedDashboard,
              "node_modules",
              "next",
              "dist",
              "bin",
              "next",
            ),
            "build",
          ],
          cwd: dashboard,
          timeoutMs: 180_000,
        };
      case "town-browser-tests":
        return {
          id: kind,
          label: "Followville browser regression suite",
          executable: node,
          args: [
            path.join(
              this.trustedRepositoryRoot,
              "node_modules",
              "@playwright",
              "test",
              "cli.js",
            ),
            "test",
          ],
          cwd: worktree.path,
          timeoutMs: 240_000,
        };
    }
  }

  async verify(input: {
    task: Task;
    worktree: Worktree;
    filesChanged: readonly string[];
    runId?: string;
    signal: AbortSignal;
  }): Promise<VerificationResult> {
    const plan = verificationKinds(input.filesChanged);
    if (
      plan.kinds.length > 0 &&
      !input.task.allowedCapabilities.includes("test_execute")
    ) {
      return {
        passed: false,
        checks: [],
        unverifiedPaths: [
          "The task changed files but does not permit the test_execute capability.",
        ],
        artifactFiles: [],
      };
    }

    if (
      this.provisionDependencies &&
      plan.kinds.some((kind) => kind.startsWith("core-"))
    ) {
      await provisionTrustedDirectory(
        path.join(this.trustedRepositoryRoot, "company-os", "node_modules"),
        path.join(input.worktree.path, "company-os", "node_modules"),
      );
    }
    if (
      this.provisionDependencies &&
      plan.kinds.some((kind) => kind.startsWith("dashboard-"))
    ) {
      await provisionTrustedDirectory(
        path.join(
          this.trustedRepositoryRoot,
          "apps",
          "company-dashboard",
          "node_modules",
        ),
        path.join(
          input.worktree.path,
          "apps",
          "company-dashboard",
          "node_modules",
        ),
      );
    }
    if (
      this.provisionDependencies &&
      plan.kinds.includes("town-browser-tests")
    ) {
      await provisionTrustedDirectory(
        path.join(this.trustedRepositoryRoot, "node_modules"),
        path.join(input.worktree.path, "node_modules"),
      );
    }

    const checks: VerificationCheck[] = [];
    for (const kind of plan.kinds) {
      const command = this.command(kind, input.worktree);
      const started = Date.now();
      const result = await this.commandRunner(command, input.signal);
      checks.push({
        id: command.id,
        label: command.label,
        passed: result.exitCode === 0,
        durationMs: Date.now() - started,
        output: result.output,
      });
      if (result.exitCode !== 0) {
        break;
      }
    }

    let artifactFiles: readonly string[] = [];
    if (
      plan.kinds.includes("town-browser-tests") &&
      plan.unverifiedPaths.length === 0 &&
      checks.every((check) => check.passed)
    ) {
      if (!input.task.allowedCapabilities.includes("browser_preview")) {
        return {
          passed: false,
          checks,
          unverifiedPaths: [
            "Public town changes require the browser_preview capability.",
          ],
          artifactFiles: [],
        };
      }
      if (input.runId === undefined) {
        return {
          passed: false,
          checks,
          unverifiedPaths: [
            "A durable run ID is required before browser evidence can be captured.",
          ],
          artifactFiles: [],
        };
      }
      const started = Date.now();
      const preview = await this.browserPreview.run({
        task: input.task,
        worktree: input.worktree,
        runId: input.runId,
        signal: input.signal,
      });
      checks.push({
        id: "browser-preview",
        label: "Desktop and mobile browser evidence",
        passed: preview.passed,
        durationMs: Date.now() - started,
        output: cleanOutput(preview.output),
      });
      artifactFiles = preview.artifactFiles;
    }

    return {
      passed:
        plan.unverifiedPaths.length === 0 &&
        checks.every((check) => check.passed),
      checks,
      unverifiedPaths: plan.unverifiedPaths,
      artifactFiles,
    };
  }
}
