import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import type {
  ModelProvider,
  ProviderAvailability,
  ProviderRequest,
  ProviderResponse,
} from "./types.js";
import { providerEnvironment } from "./environment.js";

const run = promisify(execFile);

export function claudeExecutableCandidates(
  environment: NodeJS.ProcessEnv = process.env,
  homeDirectory = homedir(),
): string[] {
  const pathEntries = (environment["PATH"] ?? "")
    .split(path.delimiter)
    .filter((entry) => entry.length > 0);
  const appData = environment["APPDATA"];
  const candidates = [
    environment["CLAUDE_CODE_PATH"],
    appData === undefined
      ? undefined
      : path.join(
          appData,
          "npm",
          "node_modules",
          "@anthropic-ai",
          "claude-code",
          "bin",
          "claude.exe",
        ),
    path.join(homeDirectory, ".local", "bin", "claude"),
    path.join(homeDirectory, ".local", "bin", "claude.exe"),
    path.join(homeDirectory, ".claude", "local", "claude"),
    path.join(homeDirectory, ".claude", "local", "claude.exe"),
    "/opt/homebrew/bin/claude",
    "/usr/local/bin/claude",
    ...pathEntries.flatMap((directory) => [
      path.join(directory, "claude"),
      path.join(directory, "claude.exe"),
      path.join(directory, "claude.cmd"),
    ]),
  ].filter((candidate): candidate is string => typeof candidate === "string");

  return [...new Set(candidates)];
}

export function claudeInvocationArgs(
  request: Pick<ProviderRequest, "prompt" | "resumeSessionId">,
  model?: string,
): string[] {
  const args = ["-p", request.prompt, "--output-format", "json"];
  if (request.resumeSessionId !== undefined) {
    args.push("--resume", request.resumeSessionId, "--fork-session");
  }
  if (model !== undefined) {
    args.push("--model", model);
  }
  return args;
}

interface ClaudeJsonResult {
  is_error?: boolean;
  result?: string;
  total_cost_usd?: number;
  session_id?: string;
  usage?: {
    input_tokens?: number;
    output_tokens?: number;
    cache_read_input_tokens?: number;
    cache_creation_input_tokens?: number;
  };
  modelUsage?: Record<string, unknown>;
}

export function claudeSubscriptionUsage(
  parsed: Pick<ClaudeJsonResult, "usage" | "total_cost_usd">,
) {
  return {
    inputTokens: parsed.usage?.input_tokens ?? 0,
    outputTokens: parsed.usage?.output_tokens ?? 0,
    cachedInputTokens: parsed.usage?.cache_read_input_tokens ?? 0,
    // Claude Code exposes an API-equivalent estimate even when the operator
    // is authenticated through a flat subscription. Recording that estimate
    // as actual spend makes the cost ledger false.
    costUsdMicros: 0,
  };
}

function emptyUsage() {
  return {
    inputTokens: 0,
    outputTokens: 0,
    cachedInputTokens: 0,
    costUsdMicros: 0,
  };
}

/**
 * Drives the Claude Code CLI headlessly.
 *
 * Runs on the operator's existing subscription rather than an API key, which
 * is why `billingMode` is `subscription`: the run reports zero dollars, and
 * bounding it is the runtime's job through durations and run counts, not a
 * dollar budget that will always read zero.
 *
 * The CLI is invoked with an explicit working directory and a bounded timeout.
 * It is never given credentials by this class; authentication is the
 * operator's, established once with `claude auth login`.
 */
export class ClaudeCodeProvider implements ModelProvider {
  readonly name = "claude-code";
  readonly billingMode = "subscription" as const;

  constructor(
    private readonly executablePath: string,
    private readonly model?: string,
  ) {}

  static defaultExecutablePath(): string | null {
    return claudeExecutableCandidates().find((candidate) => existsSync(candidate)) ?? null;
  }

  async checkAvailability(): Promise<ProviderAvailability> {
    if (!existsSync(this.executablePath)) {
      return {
        available: false,
        reason: "not_installed",
        detail: `No Claude Code executable at ${this.executablePath}.`,
      };
    }
    // `claude auth status` prints JSON such as {"loggedIn":false,...}. It may
    // also exit non-zero while still producing that JSON, so the payload is
    // read from either path before falling back to prose matching.
    let output: string;
    try {
      const { stdout } = await run(this.executablePath, ["auth", "status"], {
        timeout: 30_000,
        maxBuffer: 1_000_000,
        env: providerEnvironment(),
      });
      output = stdout;
    } catch (error) {
      const withOutput = error as Error & { stdout?: string };
      output = withOutput.stdout ?? withOutput.message;
    }

    const notAuthenticated = {
      available: false as const,
      reason: "not_authenticated" as const,
      detail:
        "The Claude Code CLI is installed but not signed in. " +
        "Run once in a terminal: claude auth login",
    };

    try {
      const status = JSON.parse(output.trim()) as {
        loggedIn?: boolean;
        authMethod?: string;
      };
      if (status.loggedIn === true) {
        return {
          available: true,
          detail: `signed in via ${status.authMethod ?? "unknown method"}`,
        };
      }
      return notAuthenticated;
    } catch {
      if (/not logged in|please run|loggedIn"?\s*:\s*false/i.test(output)) {
        return notAuthenticated;
      }
      return { available: false, reason: "unknown", detail: output.trim().slice(0, 200) };
    }
  }

  async invoke(request: ProviderRequest): Promise<ProviderResponse> {
    const args = claudeInvocationArgs(request, this.model);

    let stdout: string;
    try {
      const result = await run(this.executablePath, args, {
        cwd: request.workingDirectory,
        timeout: request.timeoutMs,
        signal: request.signal,
        maxBuffer: 16_000_000,
        env: providerEnvironment(),
      });
      stdout = result.stdout;
    } catch (error) {
      // The CLI exits non-zero for refusals and errors but still emits JSON.
      const withOutput = error as Error & { stdout?: string };
      if (typeof withOutput.stdout === "string" && withOutput.stdout.length > 0) {
        stdout = withOutput.stdout;
      } else {
        return {
          ok: false,
          text: "",
          usage: emptyUsage(),
          model: this.model ?? null,
          sessionId: null,
          failureReason: withOutput.message,
        };
      }
    }

    let parsed: ClaudeJsonResult;
    try {
      parsed = JSON.parse(stdout) as ClaudeJsonResult;
    } catch {
      return {
        ok: false,
        text: "",
        usage: emptyUsage(),
        model: this.model ?? null,
        sessionId: null,
        failureReason: "The CLI returned output that was not valid JSON.",
      };
    }

    const usage = claudeSubscriptionUsage(parsed);

    const failed = parsed.is_error === true;
    return {
      ok: !failed,
      text: parsed.result ?? "",
      usage,
      model: this.model ?? null,
      sessionId: parsed.session_id ?? null,
      failureReason: failed ? (parsed.result ?? "The provider reported an error.") : null,
    };
  }
}
