import { existsSync, realpathSync } from "node:fs";
import path from "node:path";

import type {
  AgentProfile,
  BudgetPolicy,
  Capability,
  RepositoryScope,
  Task,
} from "../domain/schemas.js";

export type PolicyOutcome = "allowed" | "denied" | "approval_required";

export interface PolicyDecision {
  outcome: PolicyOutcome;
  reason: string;
}

export interface AuthorizationRequest {
  agent: AgentProfile;
  task: Task;
  capability: Capability;
  repository?: string;
  relativePath?: string;
  repositoryRoot?: string;
  environment: "local" | "preview" | "staging" | "production";
  estimatedCostUsdMicros?: number;
  agentDailySpendUsdMicros?: number;
  budgetPolicies?: readonly BudgetPolicy[];
  callsInPeriod?: number;
  concurrentRuns?: number;
}

const PRODUCTION_CAPABILITIES = new Set<Capability>([
  "production_merge",
  "production_deploy",
  "production_database_write",
  "canonical_world_growth",
  "public_communication",
  "social_publish",
  "payment_charge",
  "price_change",
  "destructive_delete",
]);

const REPOSITORY_CAPABILITIES = new Set<Capability>([
  "repository_read",
  "repository_write",
  "git_branch_create",
  "git_checkpoint",
  "git_commit",
  "git_push_review_branch",
  "pull_request_create",
  "test_execute",
  "browser_preview",
  "blender_preview",
]);

const WORKER_ONLY_CAPABILITIES = new Set<Capability>([
  "repository_write",
  "git_branch_create",
  "git_checkpoint",
  "git_commit",
  "git_push_review_branch",
  "pull_request_create",
]);

const ACTIVE_WORK_STATUSES = new Set<Task["status"]>([
  "approved_for_work",
  "queued",
  "assigned",
  "in_progress",
  "changes_requested",
]);

function denied(reason: string): PolicyDecision {
  return { outcome: "denied", reason };
}

function requiresApproval(reason: string): PolicyDecision {
  return { outcome: "approval_required", reason };
}

function normalizeRelativePath(candidate: string): string | null {
  const slashPath = candidate.replaceAll("\\", "/");
  if (
    slashPath.length === 0 ||
    slashPath.startsWith("/") ||
    /^[a-zA-Z]:\//.test(slashPath)
  ) {
    return null;
  }

  const normalized = path.posix.normalize(slashPath);
  if (
    normalized === ".." ||
    normalized.startsWith("../") ||
    normalized.includes("/../")
  ) {
    return null;
  }
  return normalized.replace(/^\.\//, "");
}

function containsPath(prefix: string, candidate: string): boolean {
  const normalizedPrefix = normalizeRelativePath(prefix);
  return (
    normalizedPrefix !== null &&
    (candidate === normalizedPrefix ||
      candidate.startsWith(`${normalizedPrefix}/`))
  );
}

function findMatchingScope(
  scopes: readonly RepositoryScope[],
  repository: string,
  environment: AuthorizationRequest["environment"],
  relativePath?: string,
): RepositoryScope | null {
  for (const scope of scopes) {
    if (
      scope.repository !== repository ||
      !scope.environments.includes(environment)
    ) {
      continue;
    }
    if (relativePath === undefined) {
      return scope;
    }

    const normalized = normalizeRelativePath(relativePath);
    if (normalized === null) {
      return null;
    }
    const explicitlyDenied = scope.deniedPathPrefixes.some((prefix) =>
      containsPath(prefix, normalized),
    );
    const explicitlyAllowed = scope.allowedPathPrefixes.some((prefix) =>
      containsPath(prefix, normalized),
    );
    if (explicitlyAllowed && !explicitlyDenied) {
      return scope;
    }
  }
  return null;
}

function checkBudget(request: AuthorizationRequest): PolicyDecision | null {
  const estimate = request.estimatedCostUsdMicros ?? 0;
  const spent = request.agentDailySpendUsdMicros ?? 0;

  if (estimate < 0 || spent < 0) {
    return denied("Cost values must be nonnegative integers.");
  }
  if (!Number.isSafeInteger(estimate) || !Number.isSafeInteger(spent)) {
    return denied("Cost values must be safe integer microdollar amounts.");
  }
  if (
    request.capability === "model_invoke" &&
    (request.estimatedCostUsdMicros === undefined ||
      request.agentDailySpendUsdMicros === undefined ||
      request.budgetPolicies === undefined ||
      request.callsInPeriod === undefined ||
      request.concurrentRuns === undefined)
  ) {
    return denied("Model invocation requires complete budget and concurrency context.");
  }
  if (estimate > request.task.budgetUsdMicros - request.task.actualCostUsdMicros) {
    return denied("The estimate exceeds the task's remaining budget.");
  }
  if (estimate > request.agent.maxTaskCostUsdMicros) {
    return denied("The estimate exceeds the agent's per-task budget.");
  }
  if (spent + estimate > request.agent.maxDailyCostUsdMicros) {
    return denied("The estimate exceeds the agent's daily budget.");
  }

  for (const policy of request.budgetPolicies ?? []) {
    if (!policy.active) {
      continue;
    }
    if (spent + estimate > policy.hardLimitUsdMicros) {
      return denied(`The ${policy.scopeType} budget hard limit would be exceeded.`);
    }
    if ((request.callsInPeriod ?? 0) >= policy.maxCalls) {
      return denied(`The ${policy.scopeType} call limit has been reached.`);
    }
    if ((request.concurrentRuns ?? 0) >= policy.maxConcurrentRuns) {
      return denied(`The ${policy.scopeType} concurrency limit has been reached.`);
    }
  }
  return null;
}

function canonicalizeTarget(root: string, relativePath: string): {
  root: string;
  target: string;
} | null {
  try {
    const canonicalRoot = realpathSync.native(root);
    const declaredTarget = path.resolve(canonicalRoot, relativePath);
    const canonicalTarget = existsSync(declaredTarget)
      ? realpathSync.native(declaredTarget)
      : path.join(
          realpathSync.native(path.dirname(declaredTarget)),
          path.basename(declaredTarget),
        );
    return { root: canonicalRoot, target: canonicalTarget };
  } catch {
    return null;
  }
}

function isContainedResolvedPath(root: string, target: string): boolean {
  const relative = path.relative(root, target);
  return (
    relative.length > 0 &&
    !relative.startsWith("..") &&
    !path.isAbsolute(relative)
  );
}

export function authorize(request: AuthorizationRequest): PolicyDecision {
  if (!request.agent.active) {
    return denied("The agent profile is inactive.");
  }
  if (request.agent.organizationId !== request.task.organizationId) {
    return denied("The agent and task belong to different organizations.");
  }
  const isAssignedWorker = request.task.assignedAgentId === request.agent.id;
  const isAssignedReviewer = request.task.reviewerAgentId === request.agent.id;
  const productionCapability = PRODUCTION_CAPABILITIES.has(request.capability);
  const reviewPublication =
    request.task.status === "approved" &&
    ["git_push_review_branch", "pull_request_create"].includes(
      request.capability,
    );
  const requiredProductionStatus =
    request.capability === "production_deploy" ? "merged" : "approved";
  if (productionCapability && request.task.status !== requiredProductionStatus) {
    return denied(
      `The task must be ${requiredProductionStatus} before this production action is authorized.`,
    );
  }
  const reviewerMayInspect =
    request.task.status === "awaiting_review" &&
    isAssignedReviewer &&
    !WORKER_ONLY_CAPABILITIES.has(request.capability);
  if (
    !productionCapability &&
    !ACTIVE_WORK_STATUSES.has(request.task.status) &&
    !reviewerMayInspect &&
    !reviewPublication
  ) {
    return denied("The task lifecycle does not permit work in its current state.");
  }
  if (WORKER_ONLY_CAPABILITIES.has(request.capability) && !isAssignedWorker) {
    return denied("Only the task's assigned worker may perform this action.");
  }
  if (
    REPOSITORY_CAPABILITIES.has(request.capability) &&
    !isAssignedWorker &&
    !isAssignedReviewer
  ) {
    return denied("The agent is not assigned to this task as worker or reviewer.");
  }
  if (request.agent.prohibitedCapabilities.includes(request.capability)) {
    return denied("The capability is explicitly prohibited for this agent.");
  }
  if (!request.agent.capabilities.includes(request.capability)) {
    return denied("The agent has not been granted this capability.");
  }
  if (!request.task.allowedCapabilities.includes(request.capability)) {
    return denied("The task has not been granted this capability.");
  }

  const budgetDecision = checkBudget(request);
  if (budgetDecision !== null) {
    return budgetDecision;
  }

  if (REPOSITORY_CAPABILITIES.has(request.capability)) {
    if (request.repository === undefined || request.relativePath === undefined) {
      return denied("Repository actions require explicit repository and path context.");
    }
    const canonical =
      request.repositoryRoot === undefined
        ? null
        : canonicalizeTarget(request.repositoryRoot, request.relativePath);
    if (
      canonical === null ||
      !isContainedResolvedPath(canonical.root, canonical.target)
    ) {
      return denied(
        "The OS-canonical target must resolve inside the repository.",
      );
    }
    const agentScope = findMatchingScope(
      request.agent.repositoryScopes,
      request.repository,
      request.environment,
      request.relativePath,
    );
    const taskScope = findMatchingScope(
      request.task.repositoryScopes,
      request.repository,
      request.environment,
      request.relativePath,
    );
    if (agentScope === null || taskScope === null) {
      return denied("The repository, path, or environment is outside the approved scope.");
    }
  } else if (request.repository !== undefined) {
    return denied("Repository context was supplied for a non-repository capability.");
  } else if (request.relativePath !== undefined) {
    return denied("A repository is required when authorizing a path.");
  }

  if (
    request.environment === "production" ||
    productionCapability ||
    request.agent.requiresHumanApprovalFor.includes(request.capability)
  ) {
    return requiresApproval("A human approval is required for this action.");
  }

  return { outcome: "allowed", reason: "The request satisfies current policy." };
}

export function isProductionCapability(capability: Capability): boolean {
  return PRODUCTION_CAPABILITIES.has(capability);
}
