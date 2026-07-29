import { execFile, spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { promisify } from "node:util";

import type {
  ModelProvider,
  ProviderAvailability,
  ProviderRequest,
  ProviderResponse,
} from "./types.js";
import { providerEnvironment } from "./environment.js";

const run = promisify(execFile);

export function codexInvocationArgs(
  request: Pick<ProviderRequest, "workingDirectory" | "prompt" | "resumeSessionId">,
  sandbox: "read-only" | "workspace-write",
): string[] {
  const args = [
    "exec",
    "--sandbox",
    sandbox,
    "--skip-git-repo-check",
    "-C",
    request.workingDirectory,
  ];
  if (request.resumeSessionId !== undefined) {
    args.push("resume", request.resumeSessionId, request.prompt);
  } else {
    args.push(request.prompt);
  }
  return args;
}

/**
 * Drives the Codex CLI headlessly on the operator's ChatGPT subscription.
 *
 * Sandboxing is delegated to Codex itself. `workspace-write` confines
 * model-generated commands to the working directory, which is a second
 * boundary inside the disposable worktree the runtime already provides. The
 * dangerous bypass flag is deliberately never used: an agent that needs to
 * escape its sandbox is an agent that should stop and ask.
 */
export class CodexProvider implements ModelProvider {
  readonly name = "codex";
  readonly billingMode = "subscription" as const;

  constructor(
    private readonly executablePath: string,
    private readonly sandbox: "read-only" | "workspace-write" = "workspace-write",
  ) {}

  static defaultExecutablePath(): string | null {
    const candidates = [
      process.env["CODEX_CLI_PATH"],
      "C:/Users/cadet/.codex/plugins/.plugin-appserver/codex.exe",
    ].filter((candidate): candidate is string => typeof candidate === "string");
    return candidates.find((candidate) => existsSync(candidate)) ?? null;
  }

  async checkAvailability(): Promise<ProviderAvailability> {
    if (!existsSync(this.executablePath)) {
      return {
        available: false,
        reason: "not_installed",
        detail: `No Codex executable at ${this.executablePath}.`,
      };
    }
    // `codex login status` writes its answer to stderr, not stdout, so both
    // streams are read. Checking only stdout reports a signed-in CLI as
    // unauthenticated and silently falls back to the no-model executor.
    let output: string;
    try {
      const result = await run(this.executablePath, ["login", "status"], {
        timeout: 30_000,
        maxBuffer: 1_000_000,
        env: providerEnvironment(),
      });
      output = `${result.stdout}\n${result.stderr}`;
    } catch (error) {
      const withOutput = error as Error & { stdout?: string; stderr?: string };
      output = `${withOutput.stdout ?? ""}\n${withOutput.stderr ?? ""}\n${withOutput.message}`;
    }

    if (/logged in/i.test(output)) {
      return { available: true, detail: output.trim().split("\n")[0] ?? "logged in" };
    }
    return {
      available: false,
      reason: "not_authenticated",
      detail:
        "The Codex CLI is installed but not signed in. Run once in a terminal: codex login",
    };
  }

  async invoke(request: ProviderRequest): Promise<ProviderResponse> {
    const args = codexInvocationArgs(
      request,
      request.accessMode ?? this.sandbox,
    );

    const result = await spawnCollecting(this.executablePath, args, {
      cwd: request.workingDirectory,
      timeoutMs: request.timeoutMs,
      signal: request.signal,
    });

    // The transcript is emitted on stderr; the final answer on stdout.
    const stdout = `${result.stderr}\n${result.stdout}`.trim();
    const failed = result.failure !== null;
    const failureDetail =
      result.failure === null
        ? null
        : collectedFailureReason(result.failure, stdout);

    if (failed && stdout.length === 0) {
      return {
        ok: false,
        text: "",
        usage: {
          inputTokens: 0,
          outputTokens: 0,
          cachedInputTokens: 0,
          costUsdMicros: 0,
        },
        model: null,
        sessionId: null,
        failureReason: failureDetail,
      };
    }

    const parsed = parseCodexOutput(stdout, failed);
    return failed && failureDetail !== null
      ? { ...parsed, failureReason: failureDetail }
      : parsed;
  }
}

export function collectedFailureReason(
  fallback: string,
  output: string,
): string {
  const actionable = output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .reverse()
    .find(
      (line) =>
        /^ERROR:/i.test(line) &&
        !/failed to initialize MCP client during shutdown/i.test(line),
    );
  if (actionable === undefined) return fallback;
  const detail = actionable.replace(/^ERROR:\s*/i, "").slice(0, 800);
  return `${fallback} ${detail}`;
}

export interface CollectedRun {
  stdout: string;
  stderr: string;
  /** Null when the process exited cleanly. */
  failure: string | null;
}

/**
 * Runs a CLI to completion with stdin closed.
 *
 * `execFile` cannot close the child's stdin, and an agent CLI that finds an
 * open stdin waits for input a headless run will never send. The process then
 * sits at near-zero CPU until its timeout, which looks identical to a slow
 * model and wasted two full runs before it was diagnosed. `spawn` with stdin
 * set to "ignore" is the only way to guarantee the child sees a closed stream.
 */
export function spawnCollecting(
  executable: string,
  args: readonly string[],
  options: { cwd: string; timeoutMs: number; signal?: AbortSignal },
): Promise<CollectedRun> {
  return new Promise((resolve) => {
    const child = spawn(executable, [...args], {
      cwd: options.cwd,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
      env: providerEnvironment(),
    });

    let stdout = "";
    let stderr = "";
    let settled = false;
    const finish = (failure: string | null): void => {
      if (settled) {
        return;
      }
      settled = true;
      clearTimeout(timer);
      options.signal?.removeEventListener("abort", onAbort);
      resolve({ stdout, stderr, failure });
    };

    const timer = setTimeout(() => {
      child.kill();
      finish(
        `The model exceeded its ${Math.round(options.timeoutMs / 60_000)}-minute limit and was stopped.`,
      );
    }, options.timeoutMs);

    const onAbort = (): void => {
      child.kill();
      finish("The run was aborted, usually because the task lease was lost.");
    };
    options.signal?.addEventListener("abort", onAbort, { once: true });

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => finish(`Could not start the CLI: ${error.message}`));
    child.on("close", (code) =>
      finish(code === 0 ? null : `The CLI exited with code ${code ?? "unknown"}.`),
    );
  });
}

/**
 * Turns a spawn failure into something an owner can act on.
 *
 * "The CLI exited with an error" is true of a timeout, an output overflow, and
 * a genuine crash alike, and hides which one happened. Naming the cause is the
 * difference between tuning a limit and hunting a phantom bug.
 */
export function describeFailure(
  error: Error & { killed?: boolean; signal?: string; code?: number | string },
  timeoutMs: number,
): string {
  if (error.killed === true || error.signal === "SIGTERM") {
    return `The model exceeded its ${Math.round(timeoutMs / 60_000)}-minute limit and was stopped. Narrow the task or raise the limit.`;
  }
  if (/maxBuffer/i.test(error.message)) {
    return "The model produced more output than the runtime accepts. Narrow the task.";
  }
  if (error.code === "ABORT_ERR" || /abort/i.test(error.message)) {
    return "The run was aborted, usually because the task lease was lost.";
  }
  return `The Codex CLI failed: ${error.message.split("\n")[0] ?? error.message}`;
}

/**
 * Extracts the final answer and token usage from Codex's transcript output.
 *
 * The CLI prints a human-readable transcript rather than JSON, so the final
 * assistant turn is whatever follows the last `codex` marker, and the total
 * token count appears under `tokens used`. Parsing is tolerant: an
 * unrecognized shape yields the raw tail rather than throwing, because losing
 * a completed model's work to a format change would be worse than a slightly
 * messy summary.
 */
export function parseCodexOutput(
  stdout: string,
  failed: boolean,
): ProviderResponse {
  const lines = stdout.split(/\r?\n/);

  let tokens = 0;
  const tokensIndex = lines.findIndex((line) => /^tokens used/i.test(line.trim()));
  if (tokensIndex >= 0) {
    const raw = lines[tokensIndex + 1]?.replace(/[^0-9]/g, "") ?? "";
    tokens = raw.length > 0 ? Number(raw) : 0;
  }

  const sessionLine = lines.find((line) => /^session id:/i.test(line.trim()));
  const sessionId =
    sessionLine === undefined ? null : sessionLine.split(":").slice(1).join(":").trim();

  // The final assistant turn is the last block introduced by a bare `codex`
  // line, stopping at the usage footer.
  let start = -1;
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    if (lines[index]?.trim() === "codex") {
      start = index + 1;
      break;
    }
  }

  let text: string;
  if (start >= 0) {
    const end = tokensIndex > start ? tokensIndex : lines.length;
    text = lines.slice(start, end).join("\n").trim();
  } else {
    text = lines.slice(-40).join("\n").trim();
  }

  return {
    ok: !failed && text.length > 0,
    text,
    usage: {
      // Codex reports a single total; attributing it to input would overstate
      // output and vice versa, so it is recorded where it can be summed
      // without implying a split the CLI never gave us.
      inputTokens: tokens,
      outputTokens: 0,
      cachedInputTokens: 0,
      costUsdMicros: 0,
    },
    model: "codex-cli",
    sessionId,
    failureReason: failed ? "The Codex CLI exited with an error." : null,
  };
}
