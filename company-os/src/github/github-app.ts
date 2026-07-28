import { createPrivateKey, sign } from "node:crypto";
import { spawn } from "node:child_process";

import type {
  CreatePullRequestInput,
  EnsureBranchInput,
  FindPullRequestInput,
  GitHubAppAuth,
  GitHubAppAuthResult,
  GitHubDraftPullRequest,
  GitHubInstallationToken,
  GitHubPullRequestClient,
  GitHubRepository,
} from "./draft-pr.js";

type Fetch = typeof fetch;

export interface ProcessResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

export type ProcessRunner = (
  command: string,
  args: readonly string[],
  options: { cwd: string; env: NodeJS.ProcessEnv },
) => Promise<ProcessResult>;

interface GitHubAppConfiguration {
  appId: string;
  installationId: string;
  privateKey: string;
}

const BRANCH = /^agent\/task-[a-z0-9][a-z0-9-]*$/;
const SHA = /^[0-9a-f]{40}$/;

function base64Url(value: string | Buffer): string {
  return Buffer.from(value).toString("base64url");
}

function envConfiguration(
  env: NodeJS.ProcessEnv,
): { ok: true; value: GitHubAppConfiguration } | { ok: false; reason: string } {
  const appId = env["COMPANY_OS_GITHUB_APP_ID"]?.trim();
  const installationId = env["COMPANY_OS_GITHUB_INSTALLATION_ID"]?.trim();
  const encodedKey = env["COMPANY_OS_GITHUB_PRIVATE_KEY_BASE64"]?.trim();
  if (!appId || !installationId || !encodedKey) {
    return {
      ok: false,
      reason:
        "COMPANY_OS_GITHUB_APP_ID, COMPANY_OS_GITHUB_INSTALLATION_ID, and " +
        "COMPANY_OS_GITHUB_PRIVATE_KEY_BASE64 are required.",
    };
  }
  if (!/^[0-9]+$/.test(appId) || !/^[0-9]+$/.test(installationId)) {
    return { ok: false, reason: "GitHub App and installation IDs must be numeric." };
  }
  let privateKey: string;
  try {
    privateKey = Buffer.from(encodedKey, "base64").toString("utf8");
    createPrivateKey(privateKey);
  } catch {
    return { ok: false, reason: "The GitHub App private key is not a valid PEM key." };
  }
  return {
    ok: true,
    value: { appId, installationId, privateKey },
  };
}

function appJwt(configuration: GitHubAppConfiguration, nowMs: number): string {
  const now = Math.floor(nowMs / 1000);
  const header = base64Url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = base64Url(
    JSON.stringify({
      iat: now - 60,
      exp: now + 9 * 60,
      iss: configuration.appId,
    }),
  );
  const unsigned = `${header}.${payload}`;
  return `${unsigned}.${sign("RSA-SHA256", Buffer.from(unsigned), configuration.privateKey).toString("base64url")}`;
}

async function jsonResponse(response: Response): Promise<Record<string, unknown>> {
  const body = (await response.json().catch(() => null)) as unknown;
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    throw new Error(`GitHub returned an invalid JSON response (${response.status}).`);
  }
  return body as Record<string, unknown>;
}

export class GitHubAppInstallationAuth implements GitHubAppAuth {
  constructor(
    private readonly env: NodeJS.ProcessEnv = process.env,
    private readonly fetchImpl: Fetch = fetch,
    private readonly now: () => number = Date.now,
  ) {}

  async getInstallationToken(
    repository: GitHubRepository,
  ): Promise<GitHubAppAuthResult> {
    const configured = envConfiguration(this.env);
    if (!configured.ok) {
      return configured;
    }
    const configuration = configured.value;
    let response: Response;
    try {
      response = await this.fetchImpl(
        `https://api.github.com/app/installations/${configuration.installationId}/access_tokens`,
        {
          method: "POST",
          headers: {
            Accept: "application/vnd.github+json",
            Authorization: `Bearer ${appJwt(configuration, this.now())}`,
            "X-GitHub-Api-Version": "2022-11-28",
          },
          body: JSON.stringify({
            repositories: [repository.name],
            permissions: {
              contents: "write",
              metadata: "read",
              pull_requests: "write",
            },
          }),
        },
      );
    } catch {
      return { ok: false, reason: "GitHub App token exchange could not be reached." };
    }
    if (!response.ok) {
      return {
        ok: false,
        reason: `GitHub App token exchange was refused (${response.status}).`,
      };
    }
    try {
      const body = await jsonResponse(response);
      if (
        typeof body["token"] !== "string" ||
        typeof body["expires_at"] !== "string"
      ) {
        return { ok: false, reason: "GitHub returned an incomplete installation token." };
      }
      return {
        ok: true,
        token: { token: body["token"], expiresAt: body["expires_at"] },
      };
    } catch (error) {
      return { ok: false, reason: (error as Error).message };
    }
  }
}

export const runProcess: ProcessRunner = (command, args, options) =>
  new Promise((resolve, reject) => {
    const child = spawn(command, [...args], {
      cwd: options.cwd,
      env: options.env,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf8");
    });
    child.once("error", reject);
    child.once("close", (exitCode) => {
      resolve({ exitCode: exitCode ?? -1, stdout, stderr });
    });
  });

function repositoryPath(repository: GitHubRepository): string {
  const name = /^[A-Za-z0-9_.-]+$/;
  if (
    !name.test(repository.owner) ||
    !name.test(repository.name) ||
    repository.owner === "." ||
    repository.owner === ".." ||
    repository.name === "." ||
    repository.name === ".."
  ) {
    throw new Error("The GitHub repository name is invalid.");
  }
  return `/repos/${encodeURIComponent(repository.owner)}/${encodeURIComponent(repository.name)}`;
}

function gitEnvironment(
  extra: Record<string, string | undefined> = {},
): NodeJS.ProcessEnv {
  const inherited = [
    "PATH",
    "SystemRoot",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOME",
  ];
  return {
    NODE_ENV: process.env["NODE_ENV"] ?? "production",
    ...Object.fromEntries(
      inherited
        .map((name) => [name, process.env[name]] as const)
        .filter(
          (entry): entry is readonly [string, string] => entry[1] !== undefined,
        )
        .concat(
          Object.entries(extra).filter(
            (entry): entry is [string, string] => entry[1] !== undefined,
          ),
        ),
    ),
  } as NodeJS.ProcessEnv;
}

function apiHeaders(token: GitHubInstallationToken): Record<string, string> {
  return {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token.token}`,
    "Content-Type": "application/json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
}

function pullRequest(
  row: Record<string, unknown>,
): GitHubDraftPullRequest | null {
  const head =
    row["head"] !== null && typeof row["head"] === "object"
      ? (row["head"] as Record<string, unknown>)
      : null;
  const base =
    row["base"] !== null && typeof row["base"] === "object"
      ? (row["base"] as Record<string, unknown>)
      : null;
  if (
    typeof row["number"] !== "number" ||
    typeof row["html_url"] !== "string" ||
    typeof row["draft"] !== "boolean" ||
    head === null ||
    base === null ||
    typeof head["ref"] !== "string" ||
    typeof head["sha"] !== "string" ||
    typeof base["ref"] !== "string"
  ) {
    return null;
  }
  return {
    number: row["number"],
    url: row["html_url"],
    headBranch: head["ref"],
    baseBranch: base["ref"],
    headSha: head["sha"],
    draft: row["draft"],
  };
}

export class GitHubRestPullRequestClient implements GitHubPullRequestClient {
  constructor(
    private readonly repositoryRoot: string,
    private readonly fetchImpl: Fetch = fetch,
    private readonly processRunner: ProcessRunner = runProcess,
    private readonly apiBaseUrl = "https://api.github.com",
    private readonly gitExecutable = "git",
  ) {}

  private async request(
    repository: GitHubRepository,
    token: GitHubInstallationToken,
    path: string,
    init: RequestInit = {},
  ): Promise<Response> {
    return this.fetchImpl(
      `${this.apiBaseUrl.replace(/\/+$/, "")}${repositoryPath(repository)}${path}`,
      {
        ...init,
        headers: { ...apiHeaders(token), ...(init.headers ?? {}) },
      },
    );
  }

  async ensureBranch(input: EnsureBranchInput): Promise<void> {
    if (!BRANCH.test(input.branchName) || !SHA.test(input.commitSha)) {
      throw new Error("Refusing to publish an invalid review branch or checkpoint.");
    }
    const local = await this.processRunner(
      this.gitExecutable,
      ["rev-parse", "--verify", `refs/heads/${input.branchName}`],
      {
        cwd: this.repositoryRoot,
        env: gitEnvironment({ GIT_TERMINAL_PROMPT: "0" }),
      },
    );
    if (local.exitCode !== 0 || local.stdout.trim() !== input.commitSha) {
      throw new Error("The local review branch does not point at the approved checkpoint.");
    }

    const refPath = `/git/ref/heads/${input.branchName
      .split("/")
      .map(encodeURIComponent)
      .join("/")}`;
    const remote = await this.request(input.repository, input.token, refPath);
    let expected = "";
    if (remote.ok) {
      const body = await jsonResponse(remote);
      const object =
        body["object"] !== null && typeof body["object"] === "object"
          ? (body["object"] as Record<string, unknown>)
          : null;
      if (
        object === null ||
        typeof object["sha"] !== "string" ||
        !SHA.test(object["sha"])
      ) {
        throw new Error("GitHub returned an invalid review branch reference.");
      }
      expected = object["sha"];
      if (expected === input.commitSha) {
        return;
      }
    } else if (remote.status !== 404) {
      throw new Error(`GitHub branch lookup failed (${remote.status}).`);
    }

    const basic = Buffer.from(`x-access-token:${input.token.token}`).toString("base64");
    const result = await this.processRunner(
      this.gitExecutable,
      [
        "push",
        "--porcelain",
        `--force-with-lease=refs/heads/${input.branchName}:${expected}`,
        `https://github.com/${input.repository.owner}/${input.repository.name}.git`,
        `${input.commitSha}:refs/heads/${input.branchName}`,
      ],
      {
        cwd: this.repositoryRoot,
        env: gitEnvironment({
          GIT_TERMINAL_PROMPT: "0",
          GIT_CONFIG_COUNT: "1",
          GIT_CONFIG_KEY_0: "http.https://github.com/.extraheader",
          GIT_CONFIG_VALUE_0: `Authorization: Basic ${basic}`,
        }),
      },
    );
    if (result.exitCode !== 0) {
      throw new Error("Git refused to publish the approved review branch.");
    }
  }

  async findDraftPullRequest(
    input: FindPullRequestInput,
  ): Promise<GitHubDraftPullRequest | null> {
    const query = new URLSearchParams({
      state: "open",
      head: `${input.repository.owner}:${input.headBranch}`,
      base: input.baseBranch,
      per_page: "20",
    });
    const response = await this.request(
      input.repository,
      input.token,
      `/pulls?${query.toString()}`,
    );
    if (!response.ok) {
      throw new Error(`GitHub draft PR lookup failed (${response.status}).`);
    }
    const rows = (await response.json()) as unknown;
    if (!Array.isArray(rows)) {
      throw new Error("GitHub returned an invalid pull request list.");
    }
    for (const value of rows) {
      if (value === null || typeof value !== "object" || Array.isArray(value)) {
        continue;
      }
      const row = value as Record<string, unknown>;
      const body = typeof row["body"] === "string" ? row["body"] : "";
      if (!body.includes(`Idempotency-Key: ${input.idempotencyKey}`)) {
        continue;
      }
      const parsed = pullRequest(row);
      if (
        parsed === null ||
        !parsed.draft ||
        parsed.headSha !== input.checkpointCommitSha
      ) {
        throw new Error("An existing publication marker points at different work.");
      }
      return parsed;
    }
    return null;
  }

  async createDraftPullRequest(
    input: CreatePullRequestInput,
  ): Promise<GitHubDraftPullRequest> {
    const response = await this.request(input.repository, input.token, "/pulls", {
      method: "POST",
      body: JSON.stringify({
        title: input.title,
        body: input.body,
        head: input.headBranch,
        base: input.baseBranch,
        draft: true,
      }),
    });
    if (!response.ok) {
      throw new Error(`GitHub draft PR creation failed (${response.status}).`);
    }
    const parsed = pullRequest(await jsonResponse(response));
    if (
      parsed === null ||
      !parsed.draft ||
      parsed.headBranch !== input.headBranch ||
      parsed.baseBranch !== input.baseBranch ||
      parsed.headSha !== input.checkpointCommitSha
    ) {
      throw new Error("GitHub created a pull request that does not match the checkpoint.");
    }
    return parsed;
  }
}
