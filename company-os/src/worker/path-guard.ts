import type { AgentProfile, Capability, Task } from "../domain/schemas.js";
import { authorize, type PolicyDecision } from "../policy/policy-engine.js";

export interface PathGuard {
  /** Authorizes one concrete repository path for one capability. */
  check(capability: Capability, relativePath: string): PolicyDecision;
  /** Throws unless the path is permitted. */
  assert(capability: Capability, relativePath: string): void;
}

/**
 * Repository access is authorized per path, never in the abstract.
 *
 * The policy engine deliberately refuses a bare "may this agent read the
 * repository" question, because the answer depends entirely on which path is
 * being touched. An executor therefore receives this guard and must ask about
 * each concrete path, which is also what makes traversal attempts fail closed.
 */
export function createPathGuard(
  agent: AgentProfile,
  task: Task,
  repository: string,
  repositoryRoot: string,
  environment: "local" | "preview" | "staging" | "production" = "local",
): PathGuard {
  const check = (capability: Capability, relativePath: string): PolicyDecision =>
    authorize({
      agent,
      task,
      capability,
      repository,
      relativePath,
      repositoryRoot,
      environment,
      estimatedCostUsdMicros: 0,
      agentDailySpendUsdMicros: 0,
    });

  return {
    check,
    assert(capability, relativePath) {
      const decision = check(capability, relativePath);
      if (decision.outcome !== "allowed") {
        throw new Error(
          `Policy refused ${capability} on "${relativePath}": ${decision.reason}`,
        );
      }
    },
  };
}

/**
 * Coarse pre-flight gate run before any work begins.
 *
 * This checks only what can be known without a target: that the agent is
 * active, is the assigned worker, and that both the agent and the task grant
 * each capability. Path-level authorization still happens at access time
 * through the guard, so passing this is necessary but not sufficient.
 */
export function preflightCapabilities(
  agent: AgentProfile,
  task: Task,
): PolicyDecision {
  if (!agent.active) {
    return { outcome: "denied", reason: "The agent profile is inactive." };
  }
  if (agent.organizationId !== task.organizationId) {
    return {
      outcome: "denied",
      reason: "The agent and task belong to different organizations.",
    };
  }
  if (task.assignedAgentId !== agent.id) {
    return {
      outcome: "denied",
      reason: "The agent is not the assigned worker for this task.",
    };
  }
  for (const capability of task.allowedCapabilities) {
    if (agent.prohibitedCapabilities.includes(capability)) {
      return {
        outcome: "denied",
        reason: `Capability ${capability} is explicitly prohibited for this agent.`,
      };
    }
    if (!agent.capabilities.includes(capability)) {
      return {
        outcome: "denied",
        reason: `The agent has not been granted ${capability}.`,
      };
    }
  }
  return {
    outcome: "allowed",
    reason: "The agent may attempt this task, subject to per-path checks.",
  };
}
