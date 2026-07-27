import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { promisify } from "node:util";

import type {
  ModelProvider,
  ProviderAvailability,
  ProviderRequest,
  ProviderResponse,
} from "./types.js";

const run = promisify(execFile);

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
    const args = [
      "exec",
      "--sandbox",
      this.sandbox,
      "--skip-git-repo-check",
      "-C",
      request.workingDirectory,
      request.prompt,
    ];

    let stdout: string;
    let failed = false;
    let failureDetail: string | null = null;
    try {
      const result = await run(this.executablePath, args, {
        cwd: request.workingDirectory,
        timeout: request.timeoutMs,
        signal: request.signal,
        maxBuffer: 32_000_000,
      });
      // The transcript is emitted on stderr; the final answer on stdout.
      stdout = `${result.stderr}\n${result.stdout}`;
    } catch (error) {
      const withOutput = error as Error & {
        stdout?: string;
        stderr?: string;
        killed?: boolean;
        signal?: string;
        code?: number | string;
      };
      stdout = `${withOutput.stderr ?? ""}\n${withOutput.stdout ?? ""}`.trim();
      failed = true;
      failureDetail = describeFailure(withOutput, request.timeoutMs);
      if (stdout.length === 0) {
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
    }

    const parsed = parseCodexOutput(stdout, failed);
    return failed && failureDetail !== null
      ? { ...parsed, failureReason: failureDetail }
      : parsed;
  }
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
