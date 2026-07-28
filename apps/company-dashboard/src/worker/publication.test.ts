import assert from "node:assert/strict";
import test from "node:test";

import {
  ApprovalDecisionSchema,
  ApprovalRequestSchema,
  AuditEventSchema,
  ORGANIZATION_ID,
  PROJECT_ID,
  TaskSchema,
  encodeWorkerReport,
  type AuditEvent,
  type GitHubAppAuth,
  type GitHubPullRequestClient,
} from "@followville/company-os-core";

import { runPublicationPass } from "./publication";

const TASK_ID = "99000000-0000-4000-8000-000000000001";
const REQUEST_ID = "99000000-0000-4000-8000-000000000002";
const OWNER_ID = "99000000-0000-4000-8000-000000000003";
const COMMIT = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const NOW = "2026-07-27T16:00:00.000Z";
let sequence = 0;

function id(): string {
  sequence += 1;
  return `99000000-0000-4000-8000-${String(sequence).padStart(12, "0")}`;
}

function event(action: string, reason: string): AuditEvent {
  return AuditEventSchema.parse({
    id: id(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: TASK_ID,
    runId: null,
    actorType: "agent",
    actorId: "40000000-0000-4000-8000-000000000003",
    action,
    targetType: "task",
    targetId: TASK_ID,
    outcome: "succeeded",
    reason,
    correlationId: id(),
    idempotencyKey: `event-${action}-${id()}`,
    requestDigest: `request-${action}-1234567890`,
    resultDigest: `result-${action}-1234567890`,
    evidenceArtifactIds: [],
    createdAt: NOW,
  });
}

function fixture() {
  const task = TaskSchema.parse({
    id: TASK_ID,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    goalId: "99000000-0000-4000-8000-000000000010",
    parentTaskId: null,
    title: "Publish reviewed work",
    objective: "Open a draft PR.",
    reason: "Owners need a handoff.",
    status: "approved",
    priority: 50,
    riskLevel: "medium",
    assignedAgentId: "40000000-0000-4000-8000-000000000002",
    reviewerAgentId: "40000000-0000-4000-8000-000000000003",
    dependencyIds: [],
    acceptanceCriteria: [
      {
        id: "99000000-0000-4000-8000-000000000011",
        description: "The reviewed checkpoint is available in a draft PR.",
        verificationMethod: "Inspect the recorded GitHub URL.",
        required: true,
      },
    ],
    allowedCapabilities: [
      "repository_read",
      "repository_write",
      "git_push_review_branch",
      "pull_request_create",
    ],
    repositoryScopes: [
      {
        repository: "followville_repo",
        allowedPathPrefixes: ["company-os"],
        deniedPathPrefixes: ["world_state.json"],
        environments: ["local", "preview"],
      },
    ],
    budgetUsdMicros: 0,
    estimatedCostUsdMicros: 0,
    actualCostUsdMicros: 0,
    retryCount: 0,
    reviewCycleCount: 1,
    branchName: null,
    expectedOutputs: ["Draft PR"],
    testRequirements: [],
    approvalRequired: true,
    version: 2,
    createdAt: NOW,
    updatedAt: NOW,
  });
  const request = ApprovalRequestSchema.parse({
    id: REQUEST_ID,
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    taskId: TASK_ID,
    runId: null,
    requestedByType: "agent",
    requestedById: "40000000-0000-4000-8000-000000000006",
    action: "pull_request_create",
    summary: task.title,
    reason: "Reviewed work.",
    scopeDigest: "scope-digest-publication-123456",
    commitSha: COMMIT,
    evidenceArtifactIds: [],
    testsCompleted: ["core tests passed"],
    riskLevel: "medium",
    reversible: true,
    rollbackPlan: "Close the draft PR and delete the branch.",
    estimatedCostUsdMicros: 0,
    recommendation: "approve",
    alternatives: [],
    requiredApprovals: 1,
    requiredRole: "owner",
    status: "approved",
    idempotencyKey: "approval-publication-1234567890",
    createdAt: NOW,
    expiresAt: "2026-07-28T16:00:00.000Z",
  });
  const decision = ApprovalDecisionSchema.parse({
    id: id(),
    approvalRequestId: REQUEST_ID,
    decidedByUserId: OWNER_ID,
    decision: "approve",
    comment: "Publish this checkpoint for review.",
    requestScopeDigest: request.scopeDigest,
    decidedAt: NOW,
  });
  return {
    tasks: [task],
    approvalRequests: [request],
    approvalDecisions: [decision],
    auditEvents: [
      event(
        "worker.completed",
        encodeWorkerReport({
          summary: "Implemented.",
          evidence: [
            "branch=agent/task-990000000000",
            `commit=${COMMIT}`,
          ],
          testsCompleted: ["core tests passed"],
          testsFailed: [],
          filesChanged: ["company-os/example.ts"],
          diff: "diff --git a/company-os/example.ts b/company-os/example.ts",
          artifacts: [],
        }),
      ),
      event("review.approved_for_owner", "Independent review passed."),
      event("ceo.accepted", "CEO accepted the evidence."),
    ],
  };
}

function dependencies(recorded: AuditEvent[]) {
  const auth: GitHubAppAuth = {
    async getInstallationToken() {
      return {
        ok: true,
        token: { token: "test", expiresAt: "2026-07-27T17:00:00.000Z" },
      };
    },
  };
  const client: GitHubPullRequestClient = {
    async ensureBranch() {},
    async findDraftPullRequest() {
      return null;
    },
    async createDraftPullRequest(input) {
      return {
        number: 42,
        url: "https://github.test/followville/pull/42",
        headBranch: input.headBranch,
        baseBranch: input.baseBranch,
        headSha: input.checkpointCommitSha,
        draft: true,
      };
    },
  };
  return {
    auth,
    client,
    recorder: {
      async appendAuditEvent(audit: AuditEvent) {
        recorded.push(audit);
      },
    },
    authorizedOwnerUserIds: new Set([OWNER_ID]),
    repository: {
      owner: "tooheycade-design",
      name: "followville",
      baseBranch: "main" as const,
    },
    idFactory: id,
    now: () => NOW,
  };
}

test("an approved checkpoint becomes one recorded draft PR", async () => {
  const recorded: AuditEvent[] = [];
  const result = await runPublicationPass(fixture(), dependencies(recorded));

  assert.equal(result[0]?.outcome, "created");
  assert.equal(recorded.length, 1);
  assert.equal(recorded[0]?.action, "github.draft_pr_published");
  assert.match(recorded[0]?.reason ?? "", /pull\/42/);
});

test("a recorded publication is not repeated", async () => {
  const state = fixture();
  const recorded: AuditEvent[] = [];
  await runPublicationPass(state, dependencies(recorded));

  const second = await runPublicationPass(
    { ...state, auditEvents: [...state.auditEvents, ...recorded] },
    dependencies([]),
  );
  assert.equal(second[0]?.outcome, "skipped");
});

test("missing branch evidence fails before GitHub is contacted", async () => {
  const state = fixture();
  state.auditEvents[0] = event(
    "worker.completed",
    encodeWorkerReport({
      summary: "Implemented.",
      evidence: [`commit=${COMMIT}`],
      testsCompleted: ["core tests passed"],
      testsFailed: [],
      filesChanged: ["company-os/example.ts"],
      diff: "diff",
      artifacts: [],
    }),
  );
  let authCalls = 0;
  const deps = dependencies([]);
  deps.auth = {
    async getInstallationToken() {
      authCalls += 1;
      return { ok: false, reason: "should not run" };
    },
  };

  const result = await runPublicationPass(state, deps);
  assert.equal(result[0]?.outcome, "denied");
  assert.equal(authCalls, 0);
});
