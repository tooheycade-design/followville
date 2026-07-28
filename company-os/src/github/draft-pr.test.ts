import assert from "node:assert/strict";
import test from "node:test";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  TaskSchema,
  type ApprovalDecision,
  type ApprovalRequest,
  type Task,
} from "../domain/schemas.js";
import { ORGANIZATION_ID, PROJECT_ID, SEED_AGENTS } from "../config/seed-agents.js";
import {
  publishDraftPullRequest,
  type DraftPullRequestPublicationRequest,
  type DraftPullRequestPublicationResult,
  type GitHubAppAuth,
  type GitHubAppAuthResult,
  type CreatePullRequestInput,
  type EnsureBranchInput,
  type GitHubDraftPullRequest,
  type GitHubPullRequestClient,
} from "./draft-pr.js";

const NOW = "2026-07-27T12:00:00.000Z";
const TASK_ID = "97000000-0000-4000-8000-000000000001";
const OWNER_ID = "97000000-0000-4000-8000-000000000002";
const APPROVAL_ID = "97000000-0000-4000-8000-000000000003";
const DECISION_ID = "97000000-0000-4000-8000-000000000004";
const CHECKPOINT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const SCOPE_DIGEST = "scope-digest-pr-1234567890";
const IDEMPOTENCY_KEY = "github-draft-pr-task-97000000";

function task(overrides: Partial<Task> = {}): Task {
  return TaskSchema.parse({
    id: TASK_ID,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: "97000000-0000-4000-8000-000000000005",
    parentTaskId: null,
    title: "Build GitHub draft PR integration",
    objective: "Publish an approved task branch as a draft pull request.",
    reason: "Owners need a safe handoff path.",
    status: "approved",
    priority: 70,
    riskLevel: "medium",
    assignedAgentId: SEED_AGENTS.engineer.id,
    reviewerAgentId: SEED_AGENTS.reviewer.id,
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: "97000000-0000-4000-8000-000000000006",
        description: "Draft PR publication is safe and idempotent.",
        verificationMethod: "Unit tests",
        required: true,
      },
    ],
    allowedCapabilities: [
      "repository_read",
      "repository_write",
      "git_push_review_branch",
      "pull_request_create",
    ],
    repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 0,
    branchName: "agent/task-1b5dacc3edfa",
    expectedOutputs: ["Draft pull request"],
    testRequirements: ["unit tests"],
    approvalRequired: true,
    version: 1,
    createdAt: NOW,
    updatedAt: NOW,
    ...overrides,
  });
}

function approval(overrides: Partial<ApprovalRequest> = {}): ApprovalRequest {
  return ApprovalRequestSchema.parse({
    id: APPROVAL_ID,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: TASK_ID,
    runId: null,
    requestedByType: "agent",
    requestedById: SEED_AGENTS.manager.id,
    action: "pull_request_create",
    summary: "Open a draft PR for the approved checkpoint.",
    reason: "The owner approved safe review publication.",
    scopeDigest: SCOPE_DIGEST,
    commitSha: CHECKPOINT,
    evidenceArtifactIds: [],
    testsCompleted: ["npm test"],
    riskLevel: "medium",
    reversible: true,
    rollbackPlan: "Close the draft PR and delete the review branch.",
    estimatedCostUsdMicros: 0,
    recommendation: "approve",
    alternatives: ["Keep the branch local"],
    requiredApprovals: 1,
    requiredRole: "owner",
    status: "approved",
    idempotencyKey: "approval-idempotency-key-97000000",
    createdAt: NOW,
    expiresAt: "2026-07-28T12:00:00.000Z",
    ...overrides,
  });
}

function decision(
  request: ApprovalRequest,
  overrides: Partial<ApprovalDecision> = {},
): ApprovalDecision {
  return ApprovalDecisionSchema.parse({
    id: DECISION_ID,
    approvalRequestId: request.id,
    decidedByUserId: OWNER_ID,
    decision: "approve",
    comment: "Approved the exact draft PR publication.",
    requestScopeDigest: request.scopeDigest,
    decidedAt: NOW,
    ...overrides,
  });
}

function request(
  overrides: Partial<DraftPullRequestPublicationRequest> = {},
): DraftPullRequestPublicationRequest {
  const approvalRequest = approval();
  return {
    task: task(),
    repository: { owner: "followville", name: "followville", baseBranch: "main" },
    sourceBranch: "agent/task-1b5dacc3edfa",
    checkpointCommitSha: CHECKPOINT,
    scopeDigest: SCOPE_DIGEST,
    evidence: ["checkpoint commit recorded", "review branch clean"],
    testResults: ["npm test passed"],
    reviewer: {
      verdict: "approved_for_owner",
      summary: "Independent review passed.",
    },
    ceo: {
      accepted: true,
      notes: "CEO gate accepted the work.",
    },
    ownerApproval: {
      request: approvalRequest,
      decisions: [decision(approvalRequest)],
      authorizedOwnerUserIds: new Set([OWNER_ID]),
    },
    idempotencyKey: IDEMPOTENCY_KEY,
    now: NOW,
    ...overrides,
  };
}

function fakeAuth(ok = true): GitHubAppAuth & { readonly calls: number } {
  let calls = 0;
  const auth = {
    get calls() {
      return calls;
    },
    async getInstallationToken(): Promise<GitHubAppAuthResult> {
      calls += 1;
      return ok
        ? {
            ok: true,
            token: {
              token: "test-installation-token",
              expiresAt: "2026-07-27T13:00:00.000Z",
            },
          }
        : { ok: false, reason: "missing installation credentials" };
    },
  };
  return auth;
}

function fakeClient(existing: GitHubDraftPullRequest | null = null): GitHubPullRequestClient & {
  readonly ensured: number;
  readonly created: number;
  readonly lastBody: string | null;
} {
  let ensured = 0;
  let created = 0;
  let lastBody: string | null = null;
  const client = {
    get ensured() {
      return ensured;
    },
    get created() {
      return created;
    },
    get lastBody() {
      return lastBody;
    },
    async ensureBranch(input: EnsureBranchInput) {
      ensured += 1;
      assert.equal(input.branchName, "agent/task-1b5dacc3edfa");
      assert.equal(input.commitSha, CHECKPOINT);
    },
    async findDraftPullRequest() {
      return existing;
    },
    async createDraftPullRequest(input: CreatePullRequestInput) {
      created += 1;
      lastBody = input.body;
      return {
        number: 42,
        url: "https://github.test/followville/followville/pull/42",
        headBranch: input.headBranch,
        baseBranch: input.baseBranch,
        headSha: input.checkpointCommitSha,
        draft: input.draft,
      };
    },
  };
  return client;
}

function assertDenied(
  result: DraftPullRequestPublicationResult,
): asserts result is Extract<DraftPullRequestPublicationResult, { outcome: "denied" }> {
  assert.equal(result.outcome, "denied");
}

function assertCreated(
  result: DraftPullRequestPublicationResult,
): asserts result is {
  outcome: "created" | "existing";
  pullRequest: GitHubDraftPullRequest;
} {
  assert.equal(result.outcome, "created");
}

function assertExisting(
  result: DraftPullRequestPublicationResult,
): asserts result is {
  outcome: "created" | "existing";
  pullRequest: GitHubDraftPullRequest;
} {
  assert.equal(result.outcome, "existing");
}

test("valid publication pushes only the approved branch and opens a draft PR", async () => {
  const auth = fakeAuth();
  const client = fakeClient();

  const result = await publishDraftPullRequest(request(), { auth, client });

  assertCreated(result);
  assert.equal(auth.calls, 1);
  assert.equal(client.ensured, 1);
  assert.equal(client.created, 1);
  assert.match(client.lastBody ?? "", /Task-ID: 97000000/);
  assert.match(client.lastBody ?? "", /Checkpoint-Commit: a{40}/);
  assert.match(client.lastBody ?? "", /## Owner Approval/);
});

test("missing owner approval fails closed before credentials are requested", async () => {
  const auth = fakeAuth();
  const client = fakeClient();

  const result = await publishDraftPullRequest(request({ ownerApproval: null }), {
    auth,
    client,
  });

  assertDenied(result);
  assert.match(result.reason, /approval is missing/i);
  assert.equal(auth.calls, 0);
  assert.equal(client.created, 0);
});

test("scope digest mismatch is denied", async () => {
  const auth = fakeAuth();
  const client = fakeClient();

  const result = await publishDraftPullRequest(
    request({ scopeDigest: "different-scope-digest-123456" }),
    { auth, client },
  );

  assertDenied(result);
  assert.match(result.reason, /scope digest/i);
  assert.equal(auth.calls, 0);
});

test("wrong checkpoint commit is denied", async () => {
  const auth = fakeAuth();
  const client = fakeClient();

  const result = await publishDraftPullRequest(
    request({ checkpointCommitSha: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }),
    { auth, client },
  );

  assertDenied(result);
  assert.match(result.reason, /commit differs/i);
  assert.equal(auth.calls, 0);
});

test("unsafe source branch is denied", async () => {
  const auth = fakeAuth();
  const client = fakeClient();

  const result = await publishDraftPullRequest(
    request({
      sourceBranch: "feature/manual",
      task: task({ branchName: "feature/manual" }),
    }),
    { auth, client },
  );

  assertDenied(result);
  assert.match(result.reason, /agent\/task-\*/i);
  assert.equal(auth.calls, 0);
});

test("unsafe review base branch is denied before credentials are requested", async () => {
  const auth = fakeAuth();
  const client = fakeClient();

  const result = await publishDraftPullRequest(
    request({
      repository: {
        owner: "followville",
        name: "followville",
        baseBranch: "agent/task-other",
      },
    }),
    { auth, client },
  );

  assertDenied(result);
  assert.match(result.reason, /base branch is unsafe/i);
  assert.equal(auth.calls, 0);
});

test("a task without publication capabilities is denied", async () => {
  const auth = fakeAuth();
  const client = fakeClient();

  const result = await publishDraftPullRequest(
    request({
      task: task({
        allowedCapabilities: ["repository_read", "repository_write"],
      }),
    }),
    { auth, client },
  );

  assertDenied(result);
  assert.match(result.reason, /publication capabilities/i);
  assert.equal(auth.calls, 0);
});

test("duplicate requests return the existing draft PR instead of creating another", async () => {
  const existing: GitHubDraftPullRequest = {
    number: 7,
    url: "https://github.test/followville/followville/pull/7",
    headBranch: "agent/task-1b5dacc3edfa",
    baseBranch: "main",
    headSha: CHECKPOINT,
    draft: true,
  };
  const auth = fakeAuth();
  const client = fakeClient(existing);

  const result = await publishDraftPullRequest(request(), { auth, client });

  assertExisting(result);
  assert.equal(result.pullRequest.number, 7);
  assert.equal(client.ensured, 1);
  assert.equal(client.created, 0);
});

test("missing GitHub App credentials fail closed", async () => {
  const auth = fakeAuth(false);
  const client = fakeClient();

  const result = await publishDraftPullRequest(request(), { auth, client });

  assertDenied(result);
  assert.match(result.reason, /credentials are unavailable/i);
  assert.equal(client.created, 0);
});
