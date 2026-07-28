import assert from "node:assert/strict";
import { generateKeyPairSync, verify } from "node:crypto";
import test from "node:test";

import {
  GitHubAppInstallationAuth,
  GitHubRestPullRequestClient,
  type ProcessResult,
} from "./github-app.js";

const REPOSITORY = { owner: "owner", name: "repo", baseBranch: "main" as const };
const TOKEN = { token: "installation-secret", expiresAt: "2026-07-28T14:00:00Z" };
const COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const BASE_COMMIT = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
const BRANCH = "agent/task-123456789abc";

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("GitHub App auth signs a short-lived JWT and returns an installation token", async () => {
  const { privateKey, publicKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
  });
  let authorization = "";
  const auth = new GitHubAppInstallationAuth(
    {
      COMPANY_OS_GITHUB_APP_ID: "123",
      COMPANY_OS_GITHUB_INSTALLATION_ID: "456",
      COMPANY_OS_GITHUB_PRIVATE_KEY_BASE64: Buffer.from(
        privateKey.export({ type: "pkcs8", format: "pem" }),
      ).toString("base64"),
    },
    async (_url, init) => {
      authorization = String(
        (init?.headers as Record<string, string>)["Authorization"],
      );
      return response({ token: TOKEN.token, expires_at: TOKEN.expiresAt });
    },
    () => Date.parse("2026-07-28T13:00:00Z"),
  );

  const result = await auth.getInstallationToken(REPOSITORY);
  assert.equal(result.ok, true);
  if (!result.ok) return;
  assert.equal(result.token.token, TOKEN.token);
  const jwt = authorization.slice("Bearer ".length);
  const [header, payload, signature] = jwt.split(".");
  assert.ok(header && payload && signature);
  assert.equal(
    verify(
      "RSA-SHA256",
      Buffer.from(`${header}.${payload}`),
      publicKey,
      Buffer.from(signature, "base64url"),
    ),
    true,
  );
  const claims = JSON.parse(Buffer.from(payload, "base64url").toString("utf8"));
  assert.equal(claims.iss, "123");
  assert.ok(claims.exp - claims.iat <= 600);
});

test("missing GitHub App configuration fails before network access", async () => {
  let calls = 0;
  const auth = new GitHubAppInstallationAuth({}, async () => {
    calls += 1;
    return response({});
  });
  const result = await auth.getInstallationToken(REPOSITORY);
  assert.equal(result.ok, false);
  assert.equal(calls, 0);
});

test("ensureBranch pushes only the exact local checkpoint with an environment credential", async () => {
  const calls: { args: readonly string[]; env: NodeJS.ProcessEnv }[] = [];
  const runner = async (
    _command: string,
    args: readonly string[],
    options: { env: NodeJS.ProcessEnv },
  ): Promise<ProcessResult> => {
    calls.push({ args, env: options.env });
    if (args[0] === "rev-parse" && args[2] === `refs/heads/${BRANCH}`) {
      return { exitCode: 0, stdout: `${COMMIT}\n`, stderr: "" };
    }
    if (args[0] === "rev-parse" && args[2] === "refs/heads/main") {
      return { exitCode: 0, stdout: `${BASE_COMMIT}\n`, stderr: "" };
    }
    return { exitCode: 0, stdout: "ok", stderr: "" };
  };
  const client = new GitHubRestPullRequestClient(
    "C:/repo",
    async () => response({ message: "not found" }, 404),
    runner,
  );

  await client.ensureBranch({
    repository: REPOSITORY,
    token: TOKEN,
    branchName: BRANCH,
    commitSha: COMMIT,
  });

  assert.equal(calls.length, 4);
  assert.deepEqual(calls[2]?.args, [
    "merge-base",
    "--is-ancestor",
    BASE_COMMIT,
    COMMIT,
  ]);
  const push = calls[3]!;
  assert.ok(push.args.includes(`${COMMIT}:refs/heads/${BRANCH}`));
  assert.ok(push.args.some((arg) => arg.startsWith("--force-with-lease=")));
  assert.ok(push.args.every((arg) => !arg.includes(TOKEN.token)));
  assert.match(push.env["GIT_CONFIG_VALUE_0"] ?? "", /Authorization: Basic/);
});

test("ensureBranch refuses a checkpoint outside the configured review base", async () => {
  const calls: readonly string[][] = [];
  const recorded = calls as string[][];
  const runner = async (
    _command: string,
    args: readonly string[],
  ): Promise<ProcessResult> => {
    recorded.push([...args]);
    if (args[0] === "rev-parse" && args[2] === `refs/heads/${BRANCH}`) {
      return { exitCode: 0, stdout: `${COMMIT}\n`, stderr: "" };
    }
    if (args[0] === "rev-parse") {
      return { exitCode: 0, stdout: `${BASE_COMMIT}\n`, stderr: "" };
    }
    return { exitCode: 1, stdout: "", stderr: "not an ancestor" };
  };
  const client = new GitHubRestPullRequestClient(
    "C:/repo",
    async () => response({ message: "not found" }, 404),
    runner,
  );

  await assert.rejects(
    client.ensureBranch({
      repository: REPOSITORY,
      token: TOKEN,
      branchName: BRANCH,
      commitSha: COMMIT,
    }),
    /does not descend from the review base/,
  );
  assert.equal(recorded.some((args) => args[0] === "push"), false);
});

test("an existing exact draft PR is reconciled instead of recreated", async () => {
  const client = new GitHubRestPullRequestClient("C:/repo", async () =>
    response([
      {
        number: 7,
        html_url: "https://github.test/owner/repo/pull/7",
        draft: true,
        body: "Idempotency-Key: idem-1234567890",
        head: { ref: BRANCH, sha: COMMIT },
        base: { ref: "main" },
      },
    ]),
  );
  const found = await client.findDraftPullRequest({
    repository: REPOSITORY,
    token: TOKEN,
    headBranch: BRANCH,
    baseBranch: "main",
    checkpointCommitSha: COMMIT,
    idempotencyKey: "idem-1234567890",
  });
  assert.equal(found?.number, 7);
});

test("a marker on a different checkpoint fails closed", async () => {
  const client = new GitHubRestPullRequestClient("C:/repo", async () =>
    response([
      {
        number: 7,
        html_url: "https://github.test/owner/repo/pull/7",
        draft: true,
        body: "Idempotency-Key: idem-1234567890",
        head: { ref: BRANCH, sha: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" },
        base: { ref: "main" },
      },
    ]),
  );
  await assert.rejects(
    client.findDraftPullRequest({
      repository: REPOSITORY,
      token: TOKEN,
      headBranch: BRANCH,
      baseBranch: "main",
      checkpointCommitSha: COMMIT,
      idempotencyKey: "idem-1234567890",
    }),
    /different work/,
  );
});
