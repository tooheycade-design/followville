import {
  AuditEventSchema,
  SEED_AGENTS,
  decodeWorkerReport,
  digest,
  publishDraftPullRequest,
  type ApprovalDecision,
  type ApprovalRequest,
  type AuditEvent,
  type GitHubAppAuth,
  type GitHubPullRequestClient,
  type Task,
} from "@followville/company-os-core";

interface PublicationState {
  tasks: readonly Task[];
  approvalRequests: readonly ApprovalRequest[];
  approvalDecisions: readonly ApprovalDecision[];
  auditEvents: readonly AuditEvent[];
}

export interface PublicationRecorder {
  appendAuditEvent(event: AuditEvent): Promise<void>;
}

export interface PublicationDependencies {
  auth: GitHubAppAuth;
  client: GitHubPullRequestClient;
  recorder: PublicationRecorder;
  authorizedOwnerUserIds: ReadonlySet<string>;
  repository: {
    owner: string;
    name: string;
    baseBranch: "main";
  };
  idFactory: () => string;
  now: () => string;
}

export interface PublicationPassResult {
  taskId: string;
  outcome: "created" | "existing" | "denied" | "skipped";
  detail: string;
}

function lastEvent(
  events: readonly AuditEvent[],
  taskId: string,
  action: string,
): AuditEvent | undefined {
  return [...events]
    .reverse()
    .find((event) => event.taskId === taskId && event.action === action);
}

function branchFrom(events: readonly AuditEvent[], taskId: string): string | null {
  const completion = lastEvent(events, taskId, "worker.completed");
  if (completion === undefined) {
    return null;
  }
  const branch = decodeWorkerReport(completion.reason).evidence
    .find((item) => item.startsWith("branch="))
    ?.slice("branch=".length);
  return branch !== undefined && /^agent\/task-[a-z0-9-]+$/.test(branch)
    ? branch
    : null;
}

function publicationDigest(
  task: Task,
  request: ApprovalRequest,
  branch: string,
): string {
  return digest({
    purpose: "github-draft-pr",
    taskId: task.id,
    requestId: request.id,
    scopeDigest: request.scopeDigest,
    commitSha: request.commitSha,
    branch,
  });
}

/**
 * Publishes every owner-approved checkpoint that has not already been
 * recorded. Side effects remain behind the draft-PR kernel, and the immutable
 * audit row makes a later scheduler pass a no-op.
 */
export async function runPublicationPass(
  state: PublicationState,
  dependencies: PublicationDependencies,
): Promise<PublicationPassResult[]> {
  const results: PublicationPassResult[] = [];
  const requests = state.approvalRequests.filter(
    (request) =>
      request.status === "approved" &&
      request.action === "pull_request_create" &&
      request.commitSha !== null,
  );

  for (const request of requests) {
    const task = state.tasks.find((candidate) => candidate.id === request.taskId);
    if (task === undefined || task.status !== "approved") {
      results.push({
        taskId: request.taskId,
        outcome: "skipped",
        detail: "The task is not in the approved publication state.",
      });
      continue;
    }

    const branch = branchFrom(state.auditEvents, task.id);
    if (branch === null) {
      results.push({
        taskId: task.id,
        outcome: "denied",
        detail: "No recorded agent/task-* branch matches the completed work.",
      });
      continue;
    }
    const requestDigest = publicationDigest(task, request, branch);
    if (
      state.auditEvents.some(
        (event) =>
          event.taskId === task.id &&
          event.action === "github.draft_pr_published" &&
          event.requestDigest === requestDigest,
      )
    ) {
      results.push({
        taskId: task.id,
        outcome: "skipped",
        detail: "The exact checkpoint already has a recorded draft PR.",
      });
      continue;
    }

    const completion = lastEvent(state.auditEvents, task.id, "worker.completed");
    const reviewer = lastEvent(
      state.auditEvents,
      task.id,
      "review.approved_for_owner",
    );
    const ceo = lastEvent(state.auditEvents, task.id, "ceo.accepted");
    if (completion === undefined || reviewer === undefined || ceo === undefined) {
      results.push({
        taskId: task.id,
        outcome: "denied",
        detail: "Worker, reviewer, or CEO evidence is missing.",
      });
      continue;
    }
    const report = decodeWorkerReport(completion.reason);
    if (!report.evidence.includes(`commit=${request.commitSha}`)) {
      results.push({
        taskId: task.id,
        outcome: "denied",
        detail: "The approval checkpoint is not present in worker evidence.",
      });
      continue;
    }

    let publication;
    try {
      publication = await publishDraftPullRequest(
        {
          task: { ...task, branchName: branch },
          repository: dependencies.repository,
          sourceBranch: branch,
          checkpointCommitSha: request.commitSha!,
          scopeDigest: request.scopeDigest,
          evidence: report.evidence,
          testResults: request.testsCompleted,
          reviewer: {
            verdict: "approved_for_owner",
            summary: reviewer.reason,
          },
          ceo: { accepted: true, notes: ceo.reason },
          ownerApproval: {
            request,
            decisions: state.approvalDecisions.filter(
              (decision) => decision.approvalRequestId === request.id,
            ),
            authorizedOwnerUserIds: dependencies.authorizedOwnerUserIds,
          },
          idempotencyKey: requestDigest,
          now: dependencies.now(),
        },
        { auth: dependencies.auth, client: dependencies.client },
      );
    } catch (error) {
      results.push({
        taskId: task.id,
        outcome: "denied",
        detail: `GitHub publication failed safely: ${(error as Error).message}`,
      });
      continue;
    }

    if (publication.outcome === "denied") {
      results.push({
        taskId: task.id,
        outcome: "denied",
        detail: publication.reason,
      });
      continue;
    }

    const pullRequest = publication.pullRequest;
    await dependencies.recorder.appendAuditEvent(
      AuditEventSchema.parse({
        id: dependencies.idFactory(),
        organizationId: task.organizationId,
        projectId: task.projectId,
        taskId: task.id,
        runId: request.runId,
        actorType: "agent",
        actorId: task.assignedAgentId ?? SEED_AGENTS.engineer.id,
        action: "github.draft_pr_published",
        targetType: "pull_request",
        targetId: String(pullRequest.number),
        outcome: "succeeded",
        reason:
          `Draft PR #${pullRequest.number}: ${pullRequest.url}\n` +
          `Branch ${branch} at ${request.commitSha}.`,
        correlationId: dependencies.idFactory(),
        idempotencyKey: requestDigest,
        requestDigest,
        resultDigest: digest(pullRequest),
        evidenceArtifactIds: request.evidenceArtifactIds,
        createdAt: dependencies.now(),
      }),
    );
    results.push({
      taskId: task.id,
      outcome: publication.outcome,
      detail: pullRequest.url,
    });
  }
  return results;
}
