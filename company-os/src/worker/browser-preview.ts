import { execFile } from "node:child_process";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import type { Task } from "../domain/schemas.js";
import type { Worktree } from "./worktree.js";

const exec = promisify(execFile);

function previewEnvironment(): NodeJS.ProcessEnv {
  const allowed = [
    "ComSpec",
    "HOME",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "SystemDrive",
    "SystemRoot",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
  ];
  const environment: NodeJS.ProcessEnv = {
    NODE_ENV: process.env["NODE_ENV"] ?? "production",
  };
  for (const name of allowed) {
    if (process.env[name] !== undefined) {
      environment[name] = process.env[name];
    }
  }
  environment["TEMP"] ??= tmpdir();
  environment["TMP"] ??= tmpdir();
  return environment;
}

export interface BrowserPreviewResult {
  passed: boolean;
  output: string;
  artifactFiles: readonly string[];
}

export interface BrowserPreviewRunner {
  run(input: {
    task: Task;
    worktree: Worktree;
    runId: string;
    signal: AbortSignal;
  }): Promise<BrowserPreviewResult>;
}

interface PreviewScriptResult {
  passed?: boolean;
  artifacts?: unknown;
  captures?: unknown;
}

/** Runs trusted Playwright capture code against files in the isolated worktree. */
export class PlaywrightBrowserPreviewRunner implements BrowserPreviewRunner {
  constructor(private readonly trustedRepositoryRoot: string) {}

  async run(input: {
    task: Task;
    worktree: Worktree;
    runId: string;
    signal: AbortSignal;
  }): Promise<BrowserPreviewResult> {
    const relativeOutput = path.posix.join(
      ".company-os",
      "evidence",
      input.runId,
      "browser",
    );
    try {
      const { stdout, stderr } = await exec(
        process.execPath,
        [
          path.join(
            this.trustedRepositoryRoot,
            "company-os",
            "scripts",
            "browser-preview.mjs",
          ),
          input.worktree.path,
          relativeOutput,
        ],
        {
          cwd: input.worktree.path,
          timeout: 150_000,
          signal: input.signal,
          windowsHide: true,
          maxBuffer: 4_000_000,
          env: previewEnvironment(),
        },
      );
      const parsed = JSON.parse(stdout) as PreviewScriptResult;
      const artifactFiles = Array.isArray(parsed.artifacts)
        ? parsed.artifacts.filter(
            (item): item is string => typeof item === "string",
          )
        : [];
      return {
        passed: parsed.passed === true,
        output: stderr.trim() || "Desktop, town, and mobile previews captured.",
        artifactFiles,
      };
    } catch (error) {
      const failure = error as Error & { stdout?: string; stderr?: string };
      let artifactFiles: string[] = [];
      let detail = [failure.stderr, failure.message].filter(Boolean).join("\n");
      try {
        const parsed = JSON.parse(failure.stdout ?? "") as PreviewScriptResult;
        artifactFiles = Array.isArray(parsed.artifacts)
          ? parsed.artifacts.filter(
              (item): item is string => typeof item === "string",
            )
          : [];
        detail = JSON.stringify(parsed.captures ?? parsed);
      } catch {
        // Keep the process failure detail.
      }
      return { passed: false, output: detail, artifactFiles };
    }
  }
}
