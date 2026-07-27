import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { TaskSchema } from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import {
  RepositoryVerificationRunner,
  provisionTrustedDirectory,
  runVerificationCommand,
  verificationKinds,
  type VerificationCommand,
} from "./verification.js";

const task = TaskSchema.parse({
  id: "81000000-0000-4000-8000-000000000001",
  organizationId: ORGANIZATION_ID,
  projectId: PROJECT_ID,
  goalId: "81000000-0000-4000-8000-000000000002",
  parentTaskId: null,
  title: "Verify",
  objective: "Verify a scoped change.",
  reason: "Safety",
  status: "assigned",
  priority: 50,
  riskLevel: "low",
  assignedAgentId: SEED_AGENTS.engineer.id,
  reviewerAgentId: SEED_AGENTS.reviewer.id,
  dependencyIds: [],
  acceptanceCriteria: [
    {
      id: "81000000-0000-4000-8000-000000000003",
      description: "The fixed checks pass.",
      verificationMethod: "Runtime-owned verifier",
      required: true,
    },
  ],
  allowedCapabilities: ["repository_read", "repository_write", "test_execute"],
  repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
  budgetUsdMicros: 0,
  estimatedCostUsdMicros: 0,
  actualCostUsdMicros: 0,
  retryCount: 0,
  reviewCycleCount: 0,
  branchName: null,
  expectedOutputs: ["Structured verification results"],
  testRequirements: [],
  approvalRequired: true,
  version: 1,
  createdAt: "2026-07-27T17:00:00.000Z",
  updatedAt: "2026-07-27T17:00:00.000Z",
});

test("Company OS code selects the fixed core checks", () => {
  assert.deepEqual(verificationKinds(["company-os/src/worker/runtime.ts"]), {
    kinds: ["diff-check", "core-typecheck", "core-tests"],
    unverifiedPaths: [],
  });
});

test("dashboard code selects typecheck, tests, and a production build", () => {
  assert.deepEqual(
    verificationKinds(["apps/company-dashboard/src/app/factory/page.tsx"]),
    {
      kinds: [
        "diff-check",
        "dashboard-typecheck",
        "dashboard-tests",
        "dashboard-build",
      ],
      unverifiedPaths: [],
    },
  );
});

test("public town code selects the browser suite", () => {
  assert.deepEqual(verificationKinds(["town.html"]), {
    kinds: ["diff-check", "town-browser-tests"],
    unverifiedPaths: [],
  });
});

test("documentation needs only patch integrity", () => {
  assert.deepEqual(verificationKinds(["company-os/docs/ROADMAP.md"]), {
    kinds: ["diff-check"],
    unverifiedPaths: [],
  });
});

test("unknown code paths fail closed", () => {
  assert.deepEqual(verificationKinds(["neighborhood_blender.py"]), {
    kinds: ["diff-check"],
    unverifiedPaths: ["neighborhood_blender.py"],
  });
});

test("workspace dependency changes select every affected suite", () => {
  assert.deepEqual(verificationKinds(["pnpm-lock.yaml"]), {
    kinds: [
      "diff-check",
      "core-typecheck",
      "core-tests",
      "dashboard-typecheck",
      "dashboard-tests",
      "dashboard-build",
      "town-browser-tests",
    ],
    unverifiedPaths: [],
  });
});

test("commands run in fixed order and stop at the first failure", async () => {
  const invoked: VerificationCommand[] = [];
  const runner = new RepositoryVerificationRunner("C:/trusted", async (command) => {
    invoked.push(command);
    return {
      exitCode: command.id === "core-typecheck" ? 1 : 0,
      output: command.id,
    };
  });

  const result = await runner.verify({
    task,
    worktree: {
      path: "C:/worktree",
      branch: "agent/task-test",
      baseCommit: "a".repeat(40),
    },
    filesChanged: ["company-os/src/example.ts"],
    signal: new AbortController().signal,
  });

  assert.equal(result.passed, false);
  assert.deepEqual(
    invoked.map((command) => command.id),
    ["diff-check", "core-typecheck"],
  );
  assert.equal(result.checks.at(-1)?.output, "core-typecheck");
});

test("file changes cannot run checks without test_execute", async () => {
  const runner = new RepositoryVerificationRunner("C:/trusted", async () => {
    throw new Error("must not execute");
  });
  const result = await runner.verify({
    task: { ...task, allowedCapabilities: ["repository_read", "repository_write"] },
    worktree: {
      path: "C:/worktree",
      branch: "agent/task-test",
      baseCommit: "a".repeat(40),
    },
    filesChanged: ["company-os/src/example.ts"],
    signal: new AbortController().signal,
  });

  assert.equal(result.passed, false);
  assert.match(result.unverifiedPaths[0] ?? "", /test_execute/);
});

test("the real command runner captures process output and exit status", async () => {
  const result = await runVerificationCommand(
    {
      id: "self-test",
      label: "Runner self-test",
      executable: process.execPath,
      args: ["-e", "console.log('verified')"],
      cwd: process.cwd(),
      timeoutMs: 10_000,
    },
    new AbortController().signal,
  );

  assert.equal(result.exitCode, 0);
  assert.equal(result.output, "verified");
});

test("an agent-created dependency directory is never trusted", async () => {
  const root = mkdtempSync(path.join(tmpdir(), "fv-verifier-"));
  const trusted = path.join(root, "trusted");
  const poisoned = path.join(root, "worktree", "node_modules");
  mkdirSync(trusted, { recursive: true });
  mkdirSync(poisoned, { recursive: true });

  await assert.rejects(
    provisionTrustedDirectory(trusted, poisoned),
    /Refusing untrusted dependency path/,
  );
});
