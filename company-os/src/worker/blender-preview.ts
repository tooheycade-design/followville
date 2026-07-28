import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, realpath, stat } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import type { Worktree } from "./worktree.js";

const exec = promisify(execFile);
const RESULT_PREFIX = "COMPANY_OS_BLENDER_RESULT=";
const SUPPORTED_INPUTS = new Set([".glb", ".gltf"]);
const SAFE_RUN_ID = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$/;

export interface BlenderPreviewCommand {
  executable: string;
  args: readonly string[];
  cwd: string;
  timeoutMs: number;
  signal: AbortSignal;
  env: NodeJS.ProcessEnv;
}

export interface BlenderPreviewCommandResult {
  exitCode: number;
  stdout: string;
  stderr: string;
  timedOut?: boolean;
}

export type BlenderPreviewCommandRunner = (
  command: BlenderPreviewCommand,
) => Promise<BlenderPreviewCommandResult>;

export interface BlenderPreviewResult {
  passed: boolean;
  output: string;
  artifactFiles: readonly string[];
}

export interface BlenderPreviewRunner {
  checkAvailability(input: {
    worktreePath: string;
    signal: AbortSignal;
  }): Promise<{ available: boolean; detail: string }>;
  run(input: {
    worktree: Worktree;
    inputFile: string;
    runId: string;
    signal: AbortSignal;
  }): Promise<BlenderPreviewResult>;
}

interface BlenderScriptResult {
  passed?: boolean;
  message?: unknown;
  artifacts?: unknown;
  metrics?: unknown;
}

export interface BlenderPreviewRunnerOptions {
  timeoutMs?: number;
  commandRunner?: BlenderPreviewCommandRunner;
  environment?: NodeJS.ProcessEnv;
  platform?: NodeJS.Platform;
  homeDirectory?: string;
}

function isInside(parent: string, child: string): boolean {
  const relative = path.relative(parent, child);
  return (
    relative.length > 0 &&
    relative !== ".." &&
    !relative.startsWith(`..${path.sep}`) &&
    !path.isAbsolute(relative)
  );
}

function previewEnvironment(source: NodeJS.ProcessEnv): NodeJS.ProcessEnv {
  const allowed = [
    "ComSpec",
    "HOME",
    "LANG",
    "LC_ALL",
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
  const environment = Object.create(null) as NodeJS.ProcessEnv;
  for (const name of allowed) {
    if (source[name] !== undefined) environment[name] = source[name];
  }
  environment["TEMP"] ??= tmpdir();
  environment["TMP"] ??= tmpdir();
  return environment;
}

function commonBlenderCandidates(
  environment: NodeJS.ProcessEnv,
  platform: NodeJS.Platform,
  homeDirectory: string,
): readonly string[] {
  const configured = [
    environment["FOLLOWVILLE_BLENDER_PATH"],
    environment["BLENDER_PATH"],
  ];
  const common =
    platform === "win32"
      ? [
          "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe",
          "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe",
          "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe",
          "C:\\Program Files\\Blender Foundation\\Blender 4.4\\blender.exe",
          "C:\\Program Files\\Blender Foundation\\Blender 4.3\\blender.exe",
          "C:\\Program Files\\Blender Foundation\\Blender 4.2\\blender.exe",
          "C:\\Program Files\\Blender Foundation\\Blender 4.1\\blender.exe",
          "C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",
        ]
      : platform === "darwin"
        ? [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            path.join(
              homeDirectory,
              "Applications",
              "Blender.app",
              "Contents",
              "MacOS",
              "Blender",
            ),
            "/opt/homebrew/bin/blender",
            "/usr/local/bin/blender",
          ]
        : ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"];
  return [...configured, ...common, "blender"].filter(
    (candidate): candidate is string =>
      typeof candidate === "string" && candidate.trim().length > 0,
  );
}

async function validateExternalGltfUris(
  gltfPath: string,
  worktreeRoot: string,
): Promise<void> {
  let document: unknown;
  try {
    document = JSON.parse(await readFile(gltfPath, "utf8")) as unknown;
  } catch {
    throw new Error("The .gltf input must contain valid JSON.");
  }
  if (typeof document !== "object" || document === null) {
    throw new Error("The .gltf input must contain a JSON object.");
  }
  const uris: string[] = [];
  const visit = (value: unknown): void => {
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (typeof value !== "object" || value === null) return;
    for (const [key, child] of Object.entries(value)) {
      if (key === "uri" && typeof child === "string") uris.push(child);
      visit(child);
    }
  };
  visit(document);
  for (const uri of uris) {
    if (uri.startsWith("data:")) continue;
    if (/^[a-zA-Z][a-zA-Z\d+.-]*:/.test(uri)) {
      throw new Error("External .gltf URIs must be local worktree files.");
    }
    let decodedPath: string;
    try {
      decodedPath = decodeURIComponent(uri.split(/[?#]/, 1)[0] ?? "");
    } catch {
      throw new Error("External .gltf URI contains invalid encoding.");
    }
    if (
      decodedPath.length === 0 ||
      path.isAbsolute(decodedPath) ||
      decodedPath.includes("\\")
    ) {
      throw new Error("External .gltf URIs must be relative file paths.");
    }
    const resolvedResource = await realpath(
      path.resolve(path.dirname(gltfPath), decodedPath),
    ).catch(() => {
      throw new Error(`External .gltf resource does not exist: ${uri}`);
    });
    if (!isInside(worktreeRoot, resolvedResource)) {
      throw new Error(
        "External .gltf resources must resolve inside the worktree.",
      );
    }
    if (!(await stat(resolvedResource)).isFile()) {
      throw new Error("External .gltf resources must be regular files.");
    }
  }
}

export const runBlenderPreviewCommand: BlenderPreviewCommandRunner = async (
  command,
) => {
  try {
    const { stdout, stderr } = await exec(
      command.executable,
      [...command.args],
      {
        cwd: command.cwd,
        timeout: command.timeoutMs,
        signal: command.signal,
        windowsHide: true,
        maxBuffer: 4_000_000,
        env: command.env,
      },
    );
    return { exitCode: 0, stdout, stderr };
  } catch (error) {
    const failure = error as Error & {
      code?: number | string;
      stdout?: string;
      stderr?: string;
      killed?: boolean;
    };
    return {
      exitCode:
        typeof failure.code === "number" && Number.isInteger(failure.code)
          ? failure.code
          : 1,
      stdout: failure.stdout ?? "",
      stderr: [failure.stderr, failure.message].filter(Boolean).join("\n"),
      timedOut: failure.killed === true,
    };
  }
};

function parseScriptResult(stdout: string): BlenderScriptResult {
  const marker = stdout
    .split(/\r?\n/)
    .reverse()
    .find((line) => line.startsWith(RESULT_PREFIX));
  if (!marker) throw new Error("Blender did not emit a preview result.");
  return JSON.parse(marker.slice(RESULT_PREFIX.length)) as BlenderScriptResult;
}

/** Runs trusted, non-autoexec Blender preview code against one isolated input. */
export class HeadlessBlenderPreviewRunner implements BlenderPreviewRunner {
  readonly #timeoutMs: number;
  readonly #commandRunner: BlenderPreviewCommandRunner;
  readonly #environment: NodeJS.ProcessEnv;
  readonly #platform: NodeJS.Platform;
  readonly #homeDirectory: string;

  constructor(
    private readonly trustedRepositoryRoot: string,
    options: BlenderPreviewRunnerOptions = {},
  ) {
    this.#timeoutMs = options.timeoutMs ?? 180_000;
    this.#commandRunner = options.commandRunner ?? runBlenderPreviewCommand;
    this.#environment = options.environment ?? process.env;
    this.#platform = options.platform ?? process.platform;
    this.#homeDirectory = options.homeDirectory ?? homedir();
  }

  async checkAvailability(input: {
    worktreePath: string;
    signal: AbortSignal;
  }): Promise<{ available: boolean; detail: string }> {
    try {
      const executable = await this.#discoverBlender(
        input.worktreePath,
        input.signal,
        previewEnvironment(this.#environment),
      );
      return { available: true, detail: executable };
    } catch (error) {
      return {
        available: false,
        detail: error instanceof Error ? error.message : String(error),
      };
    }
  }

  async #discoverBlender(
    cwd: string,
    signal: AbortSignal,
    environment: NodeJS.ProcessEnv,
  ): Promise<string> {
    for (const candidate of commonBlenderCandidates(
      this.#environment,
      this.#platform,
      this.#homeDirectory,
    )) {
      const probe = await this.#commandRunner({
        executable: candidate,
        args: ["--version"],
        cwd,
        timeoutMs: 10_000,
        signal,
        env: environment,
      });
      if (probe.exitCode === 0 && /\bBlender\b/i.test(probe.stdout)) {
        return candidate;
      }
      if (signal.aborted) throw new Error("Blender preview was aborted.");
    }
    throw new Error(
      "Blender was not found. Set FOLLOWVILLE_BLENDER_PATH or install Blender in a standard location.",
    );
  }

  async run(input: {
    worktree: Worktree;
    inputFile: string;
    runId: string;
    signal: AbortSignal;
  }): Promise<BlenderPreviewResult> {
    try {
      if (!SAFE_RUN_ID.test(input.runId)) {
        throw new Error("Run ID is not safe for an evidence directory.");
      }
      const extension = path.extname(input.inputFile).toLowerCase();
      if (!SUPPORTED_INPUTS.has(extension)) {
        throw new Error("Blender preview input must be .glb or .gltf.");
      }

      const worktreeRoot = await realpath(input.worktree.path);
      const requestedPath = path.isAbsolute(input.inputFile)
        ? input.inputFile
        : path.resolve(worktreeRoot, input.inputFile);
      const resolvedInput = await realpath(requestedPath);
      if (!isInside(worktreeRoot, resolvedInput)) {
        throw new Error("Blender preview input must resolve inside the worktree.");
      }
      const inputStat = await stat(resolvedInput);
      if (!inputStat.isFile()) {
        throw new Error("Blender preview input must be a regular file.");
      }
      if (extension === ".gltf") {
        await validateExternalGltfUris(resolvedInput, worktreeRoot);
      }

      const relativeOutput = path.join(
        ".company-os",
        "evidence",
        input.runId,
        "blender",
        createHash("sha256")
          .update(path.relative(worktreeRoot, resolvedInput))
          .digest("hex")
          .slice(0, 12),
      );
      const outputDirectory = path.resolve(worktreeRoot, relativeOutput);
      if (!isInside(worktreeRoot, outputDirectory)) {
        throw new Error("Blender evidence directory must be inside the worktree.");
      }

      const environment = previewEnvironment(this.#environment);
      const executable = await this.#discoverBlender(
        worktreeRoot,
        input.signal,
        environment,
      );
      const trustedScript = path.resolve(
        this.trustedRepositoryRoot,
        "company-os",
        "scripts",
        "blender-preview.py",
      );
      const result = await this.#commandRunner({
        executable,
        args: [
          "--factory-startup",
          "--background",
          "--disable-autoexec",
          "--python",
          trustedScript,
          "--",
          "--input",
          resolvedInput,
          "--output",
          outputDirectory,
        ],
        cwd: worktreeRoot,
        timeoutMs: this.#timeoutMs,
        signal: input.signal,
        env: environment,
      });

      let parsed: BlenderScriptResult;
      try {
        parsed = parseScriptResult(result.stdout);
      } catch (error) {
        const timeout = result.timedOut
          ? `Blender preview timed out after ${this.#timeoutMs}ms.`
          : undefined;
        throw new Error(
          [timeout, result.stderr.trim(), (error as Error).message]
            .filter(Boolean)
            .join("\n"),
        );
      }

      const artifacts = Array.isArray(parsed.artifacts)
        ? parsed.artifacts.filter(
            (artifact): artifact is string =>
              typeof artifact === "string" &&
              artifact.length > 0 &&
              !path.isAbsolute(artifact) &&
              !artifact.split(/[\\/]/).includes(".."),
          )
        : [];
      const artifactFiles = artifacts.map((artifact) =>
        path
          .relative(worktreeRoot, path.resolve(outputDirectory, artifact))
          .split(path.sep)
          .join("/"),
      );
      const passed = result.exitCode === 0 && parsed.passed === true;
      const message =
        typeof parsed.message === "string"
          ? parsed.message
          : passed
            ? "Blender preview rendered."
            : "Blender preview failed.";
      return {
        passed,
        output: parsed.metrics
          ? `${message}\n${JSON.stringify(parsed.metrics)}`
          : message,
        artifactFiles,
      };
    } catch (error) {
      return {
        passed: false,
        output: error instanceof Error ? error.message : String(error),
        artifactFiles: [],
      };
    }
  }
}
