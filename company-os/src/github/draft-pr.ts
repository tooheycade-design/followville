import type {
  ApprovalDecision,
  ApprovalRequest,
  Task,
} from "../domain/schemas.js";
import { verifyApproval } from "../policy/approval-verifier.js";

export interface GitHubRepository {
  owner: string;
  name: string;
  baseBranch: "main";
}

export interface GitHubInstallationToken {
  token: string;
  expiresAt: string;
}

export type GitHubAppAuthResult =
  | { ok: true; token: GitHubInstallationToken }
  | { ok: false; reason: string };

export interface GitHubAppAuth {
  getInstallationToken(repository: GitHubRepository): Promise<GitHubAppAuthResult>;
}

export interface GitHubDraftPullRequest {
  number: number;
  url: string;
  headBranch: string;
  baseBranch: string;
  headSha: string;
  draft: boolean;
}

export interface EnsureBranchInput {
  repository: GitHubRepository;
  token: GitHubInstallationToken;
  branchName: string;
  commitSha: string;
}

export interface FindPullRequestInput {
  repository: GitHubRepository;
  token: GitHubInstallationToken;
  headBranch: string;
  baseBranch: string;
  checkpointCommitSha: string;
  idempotencyKey: string;
}

export interface CreatePullRequestInput extends FindPullRequestInput {
  title: string;
  body: string;
  draft: true;
}

export interface GitHubPullRequestClient {
  ensureBranch(input: EnsureBranchInput): Promise<void>;
  findDraftPullRequest(
    input: FindPullRequestInput,
  ): Promise<GitHubDraftPullRequest | null>;
  createDraftPullRequest(
    input: CreatePullRequestInput,
  ): Promise<GitHubDraftPullRequest>;
}

export interface ReviewerVerdictEvidence {
  verdict: "approved_for_owner" | "changes_requested";
  summary: string;
}

export interface CeoVerdictEvidence {
  accepted: boolean;
  notes: string;
}

export interface OwnerApprovalEvidence {
  request: ApprovalRequest;
  decisions: readonly ApprovalDecision[];
  authorizedOwnerUserIds: ReadonlySet<string>;
}

export interface DraftPullRequestPublicationRequest {
  task: Task;
  repository: GitHubRepository;
  sourceBranch: string;
  checkpointCommitSha: string;
  scopeDigest: string;
  evidence: readonly string[];
  testResults: readonly string[];
  reviewer: ReviewerVerdictEvidence;
  ceo: CeoVerdictEvidence;
  ownerApproval: OwnerApprovalEvidence | null;
  idempotencyKey: string;
  now: string;
}

export type DraftPullRequestPublicationResult =
  | {
      outcome: "created" | "existing";
      pullRequest: GitHubDraftPullRequest;
    }
  | { outcome: "denied"; reason: string };

const AGENT_TASK_BRANCH = /^agent\/task-[a-z0-9][a-z0-9-]*$/;
const FULL_SHA = /^[0-9a-f]{40}$/;

function deny(reason: string): DraftPullRequestPublicationResult {
  return { outcome: "denied", reason };
}

function validateRequest(
  input: DraftPullRequestPublicationRequest,
): DraftPullRequestPublicationResult | null {
  const ownerApproval = input.ownerApproval;
  if (ownerApproval === null || input.task.id !== ownerApproval.request.taskId) {
    return deny("Owner approval is missing or belongs to a different task.");
  }
  if (
    input.task.organizationId !== ownerApproval.request.organizationId ||
    input.task.projectId !== ownerApproval.request.projectId
  ) {
    return deny("Owner approval belongs to a different organization or project.");
  }
  if (input.task.status !== "approved") {
    return deny("The task is not approved.");
  }
  if (input.task.branchName !== input.sourceBranch) {
    return deny("The task branch does not match the requested source branch.");
  }
  if (!AGENT_TASK_BRANCH.test(input.sourceBranch)) {
    return deny("Only agent/task-* source branches can be published.");
  }
  if (!FULL_SHA.test(input.checkpointCommitSha)) {
    return deny("The checkpoint commit SHA is invalid.");
  }
  if (input.evidence.length === 0) {
    return deny("Publication requires recorded evidence.");
  }
  if (input.testResults.length === 0) {
    return deny("Publication requires recorded test results.");
  }
  if (input.scopeDigest !== ownerApproval.request.scopeDigest) {
    return deny("The current scope digest differs from the owner approval.");
  }
  if (ownerApproval.request.commitSha !== input.checkpointCommitSha) {
    return deny("The checkpoint commit differs from the owner approval.");
  }
  if (input.reviewer.verdict !== "approved_for_owner") {
    return deny("The independent reviewer did not approve this work for owner review.");
  }
  if (input.ceo.accepted !== true) {
    return deny("The CEO gate has not accepted this work.");
  }

  const approval = verifyApproval({
    request: ownerApproval.request,
    decisions: ownerApproval.decisions,
    action: "pull_request_create",
    scopeDigest: input.scopeDigest,
    commitSha: input.checkpointCommitSha,
    authorizedApproverUserIds: ownerApproval.authorizedOwnerUserIds,
    now: input.now,
  });
  if (approval.outcome !== "allowed") {
    return deny(`Owner approval is not valid: ${approval.reason}`);
  }

  return null;
}

function prTitle(task: Task): string {
  return `Draft: ${task.title}`;
}

function lines(items: readonly string[]): string {
  return items.map((item) => `- ${item}`).join("\n");
}

export function buildDraftPullRequestBody(
  input: DraftPullRequestPublicationRequest,
): string {
  const approval = input.ownerApproval?.request;
  return [
    "<!-- company-os:draft-pr -->",
    `Idempotency-Key: ${input.idempotencyKey}`,
    `Task-ID: ${input.task.id}`,
    `Checkpoint-Commit: ${input.checkpointCommitSha}`,
    `Scope-Digest: ${input.scopeDigest}`,
    "",
    "## Objective",
    input.task.objective,
    "",
    "## Evidence",
    lines(input.evidence),
    "",
    "## Test Results",
    lines(input.testResults),
    "",
    "## Reviewer Verdict",
    `${input.reviewer.verdict}: ${input.reviewer.summary}`,
    "",
    "## CEO Verdict",
    `accepted: ${input.ceo.notes}`,
    "",
    "## Owner Approval",
    approval === undefined
      ? "missing"
      : [
          `approval_request_id: ${approval.id}`,
          `status: ${approval.status}`,
          `action: ${approval.action}`,
          `required_role: ${approval.requiredRole}`,
        ].join("\n"),
  ].join("\n");
}

export async function publishDraftPullRequest(
  input: DraftPullRequestPublicationRequest,
  dependencies: {
    auth: GitHubAppAuth;
    client: GitHubPullRequestClient;
  },
): Promise<DraftPullRequestPublicationResult> {
  const invalid = validateRequest(input);
  if (invalid !== null) {
    return invalid;
  }

  const token = await dependencies.auth.getInstallationToken(input.repository);
  if (!token.ok) {
    return deny(`GitHub App credentials are unavailable: ${token.reason}`);
  }

  await dependencies.client.ensureBranch({
    repository: input.repository,
    token: token.token,
    branchName: input.sourceBranch,
    commitSha: input.checkpointCommitSha,
  });

  const lookup: FindPullRequestInput = {
    repository: input.repository,
    token: token.token,
    headBranch: input.sourceBranch,
    baseBranch: input.repository.baseBranch,
    checkpointCommitSha: input.checkpointCommitSha,
    idempotencyKey: input.idempotencyKey,
  };
  const existing = await dependencies.client.findDraftPullRequest(lookup);
  if (existing !== null) {
    return { outcome: "existing", pullRequest: existing };
  }

  const created = await dependencies.client.createDraftPullRequest({
    ...lookup,
    title: prTitle(input.task),
    body: buildDraftPullRequestBody(input),
    draft: true,
  });
  return { outcome: "created", pullRequest: created };
}
