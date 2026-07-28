import {
  GoalSchema,
  TaskSchema,
  type Capability,
  type Goal,
  type RiskLevel,
  type Task,
} from "../domain/schemas.js";
import {
  ORGANIZATION_ID,
  OWNER_USER_ID,
  PROJECT_ID,
  SEED_AGENTS,
} from "../config/seed-agents.js";

/**
 * Capabilities the CEO may put on a task without an owner saying so first.
 *
 * The CEO decides what should happen, never what an agent is permitted to do.
 * Anything absent from this set has to be granted deliberately by an owner,
 * which is why the list contains no production, publishing, or spending
 * capability. Widening it is a policy change, not a planning decision.
 */
const CEO_GRANTABLE: readonly Capability[] = [
  "repository_read",
  "repository_write",
  "git_branch_create",
  // Attached automatically alongside repository_write rather than chosen; see
  // where tasks are built below. Listed here so an explicit request for it is
  // not reported as a refusal.
  "git_checkpoint",
  "test_execute",
  "browser_preview",
  "blender_preview",
  "database_read_development",
  "memory_write",
  "message_send",
];

/** Intent an owner expressed, before it is anything the company can act on. */
export interface OwnerIntent {
  title: string;
  detail: string;
  createdByUserId?: string;
}

export interface ProposedTask {
  title: string;
  objective: string;
  reason: string;
  acceptanceCriteria: readonly string[];
  requestedCapabilities: readonly Capability[];
  priority: number;
  riskLevel: RiskLevel;
}

export interface Initiative {
  goal: Goal;
  tasks: readonly Task[];
  /** Decisions the CEO refuses to make on the owners' behalf. */
  escalations: readonly string[];
  /** Capabilities that were asked for and removed, with the reason. */
  clampedCapabilities: readonly { task: string; removed: Capability[] }[];
}

export interface Planner {
  readonly name: string;
  propose(intent: OwnerIntent): Promise<readonly ProposedTask[]>;
}

/** Subjects the CEO must not decide alone, matched against owner intent. */
const ESCALATION_TRIGGERS: readonly { pattern: RegExp; reason: string }[] = [
  {
    pattern: /\b(price|pricing|charge|paid|monetiz\w*|subscription|revenue)\b/gi,
    reason: "Monetization and pricing are owner decisions.",
  },
  {
    pattern: /\b(deploy\w*|release|ship it|go live|production)\b/gi,
    reason: "Releasing to production requires an owner approval.",
  },
  {
    pattern: /\b(post|publish\w*|instagram|tweet|announce)\b/gi,
    reason: "Anything public requires an owner approval.",
  },
  {
    pattern: /\b(brand|logo|rename|identity)\b/gi,
    reason: "Brand and identity are owner decisions.",
  },
  {
    pattern: /\b(delete|wipe|drop|purge|reset)\b/gi,
    reason: "Destructive changes require an owner decision.",
  },
  {
    pattern: /\b(world_state|town\.glb|neighborhood\.blend|grow the town)\b/gi,
    reason: "The canonical town is owner-controlled and never changed by an agent.",
  },
];

/**
 * Whether a sensitive subject is being prohibited rather than requested.
 *
 * This is deliberately small and inspectable. It handles directive negation
 * near the matched phrase, while leaving contrastive wording such as
 * "not only deploy, but publish" positive. A positive mention elsewhere in
 * the same intent still escalates.
 */
function isNegatedMention(text: string, index: number, length: number): boolean {
  const clauseStart = Math.max(
    text.lastIndexOf(".", index - 1),
    text.lastIndexOf("!", index - 1),
    text.lastIndexOf("?", index - 1),
    text.lastIndexOf(";", index - 1),
    text.lastIndexOf(",", index - 1),
    text.lastIndexOf("\n", index - 1),
  );
  const prefix = text
    .slice(clauseStart + 1, index)
    .toLowerCase()
    .replaceAll("don't", "do not")
    .replaceAll("doesn't", "does not")
    .replaceAll("can't", "can not")
    .replaceAll("won't", "will not")
    .replaceAll("shouldn't", "should not")
    .replaceAll("mustn't", "must not");
  const suffix = text.slice(index + length).toLowerCase();

  const directive =
    /(?:\b(?:do|does|did|must|should|can|could|will|would|may)\s+not|\bnever|\bwithout)\s+(?:[\w-]+\s+){0,4}$/;
  const noIntent =
    /\bno\s+(?:(?:need|plan|intention|permission)\s+)?(?:to\s+)?(?:[\w-]+\s+){0,2}$/;
  const prohibitedState =
    /^\s+(?:[\w-]+\s+){0,2}(?:(?:is|are|must be|should be|will be)\s+(?:not\s+(?:allowed|permitted|required)|forbidden|blocked|disabled)|(?:must|should|will)\s+not\s+(?:happen|occur|change|run))\b/;

  return directive.test(prefix) || noIntent.test(prefix) || prohibitedState.test(suffix);
}

function detectEscalations(intent: OwnerIntent): string[] {
  const haystack = `${intent.title} ${intent.detail}`;
  const found: string[] = [];
  for (const trigger of ESCALATION_TRIGGERS) {
    for (const match of haystack.matchAll(trigger.pattern)) {
      if (
        match.index !== undefined &&
        !isNegatedMention(haystack, match.index, match[0].length) &&
        !found.includes(trigger.reason)
      ) {
        found.push(trigger.reason);
        break;
      }
    }
  }
  return found;
}

/**
 * A planner that splits intent into an investigation and an implementation.
 *
 * It calls no model, so the CEO role works before any provider is connected
 * and its behaviour is inspectable. A model-backed planner can replace it
 * without changing anything else, because the clamping below applies to any
 * planner's output.
 */
export class HeuristicPlanner implements Planner {
  readonly name = "heuristic";

  async propose(intent: OwnerIntent): Promise<readonly ProposedTask[]> {
    const investigation: ProposedTask = {
      title: `Investigate: ${intent.title}`,
      objective:
        `Establish what the current state is and what would have to change to achieve: ${intent.detail}. ` +
        "Report findings with evidence. Change nothing.",
      reason: "Understanding the current state before changing it.",
      acceptanceCriteria: [
        "The current behaviour is described with evidence from the repository.",
        "The specific changes required are named.",
        "Anything that needs an owner decision is called out.",
      ],
      requestedCapabilities: ["repository_read"],
      priority: 60,
      riskLevel: "low",
    };

    const implementation: ProposedTask = {
      title: `Implement: ${intent.title}`,
      objective: `${intent.detail} Make the change in an isolated branch with tests where they apply.`,
      reason: "Delivering the change the owner asked for.",
      acceptanceCriteria: [
        "The requested behaviour exists and is demonstrated.",
        "Existing behaviour is not broken.",
        "Evidence is recorded for an independent reviewer.",
      ],
      requestedCapabilities: [
        "repository_read",
        "repository_write",
        "git_branch_create",
        "test_execute",
      ],
      priority: 50,
      riskLevel: "medium",
    };

    return [investigation, implementation];
  }
}

export interface PlanOptions {
  intent: OwnerIntent;
  planner: Planner;
  idFactory: () => string;
  now?: string;
  /** Capabilities an owner explicitly granted beyond the default set. */
  ownerGrantedCapabilities?: readonly Capability[];
}

/**
 * Turns owner intent into an initiative the company can execute.
 *
 * Whatever a planner proposes, capabilities are intersected with what the CEO
 * may grant plus anything an owner explicitly added. A planner that asks for
 * `production_deploy` does not get it; the request is stripped and recorded,
 * so an attempt to widen permissions is visible rather than silent.
 */
export async function planInitiative(options: PlanOptions): Promise<Initiative> {
  const now = options.now ?? new Date().toISOString();
  const make = options.idFactory;
  const permitted = new Set<Capability>([
    ...CEO_GRANTABLE,
    ...(options.ownerGrantedCapabilities ?? []),
  ]);

  // A capability the assigned worker does not hold produces a task that is
  // planned, queued, leased, and only then blocked at execution. The CEO must
  // not be able to grant authority the executing agent lacks, so the two lists
  // are intersected at plan time rather than discovered at run time.
  const worker = SEED_AGENTS.engineer;
  const grantable = new Set(
    [...permitted].filter((capability) => worker.capabilities.includes(capability)),
  );

  const escalations = detectEscalations(options.intent);
  const proposals = await options.planner.propose(options.intent);
  if (proposals.length === 0) {
    throw new Error("The planner proposed no tasks.");
  }

  const goal = GoalSchema.parse({
    id: make(),
    organizationId: ORGANIZATION_ID,
    projectId: PROJECT_ID,
    createdByUserId: options.intent.createdByUserId ?? OWNER_USER_ID,
    title: options.intent.title,
    objective: options.intent.detail,
    successDefinition:
      "Every task is completed, independently reviewed, and accepted by an owner.",
    constraints: [
      "No production capability",
      "No public communication",
      "The canonical town is never modified by an agent",
      ...escalations,
    ],
    riskLevel: escalations.length > 0 ? "high" : "medium",
    budgetUsdMicros: 0,
    status: escalations.length > 0 ? "awaiting_approval" : "active",
    createdAt: now,
  });

  const clampedCapabilities: { task: string; removed: Capability[] }[] = [];
  const tasks = proposals.map((proposal) => {
    const granted = proposal.requestedCapabilities.filter((capability) =>
      grantable.has(capability),
    );
    const removed = proposal.requestedCapabilities.filter(
      (capability) => !grantable.has(capability),
    );
    if (removed.length > 0) {
      clampedCapabilities.push({ task: proposal.title, removed });
    }

    // A task that may write files must be able to have those writes recorded,
    // or its result is destroyed with the worktree and an owner is asked to
    // approve something that no longer exists. This is bookkeeping rather than
    // a planning decision, so it is attached rather than requested: leaving it
    // to the planner means tasks silently lose their evidence whenever the
    // model forgets to ask. It cannot push, merge, or reach production.
    if (granted.includes("repository_write") && !granted.includes("git_checkpoint")) {
      granted.push("git_checkpoint");
    }
    if (granted.includes("repository_write")) {
      // Publication is bundled into a write task so the completed-work packet
      // can ask the owner to publish the exact reviewed checkpoint. Policy
      // keeps both capabilities unusable until that approval exists.
      if (!granted.includes("git_push_review_branch")) {
        granted.push("git_push_review_branch");
      }
      if (!granted.includes("pull_request_create")) {
        granted.push("pull_request_create");
      }
    }

    return TaskSchema.parse({
      id: make(),
      organizationId: ORGANIZATION_ID,
      projectId: PROJECT_ID,
      goalId: goal.id,
      parentTaskId: null,
      title: proposal.title,
      objective: proposal.objective,
      reason: proposal.reason,
      // Work waits for an owner when the intent touched something escalated.
      status: escalations.length > 0 ? "proposed" : "queued",
      priority: Math.max(0, Math.min(100, proposal.priority)),
      riskLevel: proposal.riskLevel,
      assignedAgentId: SEED_AGENTS.engineer.id,
      reviewerAgentId: SEED_AGENTS.reviewer.id,
      dependencyIds: [],
      acceptanceCriteria: proposal.acceptanceCriteria.map((description) => ({
        id: make(),
        description,
        verificationMethod: "Independent reviewer inspects the recorded evidence.",
        required: true,
      })),
      allowedCapabilities: granted.length > 0 ? granted : ["repository_read"],
      repositoryScopes: SEED_AGENTS.engineer.repositoryScopes,
      budgetUsdMicros: 0,
      estimatedCostUsdMicros: 0,
      actualCostUsdMicros: 0,
      retryCount: 0,
      reviewCycleCount: 0,
      branchName: null,
      expectedOutputs: ["A reviewed result with evidence"],
      testRequirements: [],
      approvalRequired: true,
      version: 1,
      createdAt: now,
      updatedAt: now,
    });
  });

  return { goal, tasks, escalations, clampedCapabilities };
}
