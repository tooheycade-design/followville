import type { ModelProvider } from "../providers/types.js";
import type { Capability, RiskLevel } from "../domain/schemas.js";
import type { OwnerIntent, Planner, ProposedTask } from "./ceo.js";

const GRANTABLE_HINT = [
  "repository_read",
  "repository_write",
  "git_branch_create",
  "test_execute",
  "browser_preview",
  "blender_preview",
  "database_read_development",
  "memory_write",
  "message_send",
].join(", ");

function buildPlanningPrompt(intent: OwnerIntent, context: string): string {
  return [
    "You are the Chief Executive of a small AI company that maintains Followville,",
    "a persistent 3D town rendered in Blender and walkable on a website.",
    "",
    context,
    "",
    "An owner has asked for this:",
    `Title: ${intent.title}`,
    `Detail: ${intent.detail}`,
    "",
    "Break this into 1 to 4 concrete tasks that engineers could actually pick up.",
    "Each task must be independently checkable and small enough to review.",
    "",
    `Capabilities you may request: ${GRANTABLE_HINT}.`,
    "Never request production, deployment, publishing, payment, or world-growth",
    "capabilities. Those belong to the human owners alone.",
    "",
    "Reply with ONLY a JSON array, no prose and no code fence. Each element:",
    "{",
    '  "title": string,',
    '  "objective": string,',
    '  "reason": string,',
    '  "acceptanceCriteria": [string, ...],',
    '  "requestedCapabilities": [string, ...],',
    '  "priority": number between 0 and 100,',
    '  "riskLevel": "low" | "medium" | "high"',
    "}",
  ].join("\n");
}

/**
 * Extracts the JSON array from a model's reply.
 *
 * Models wrap JSON in prose or fences even when told not to, and a planner
 * that throws on the wrapper would discard sound plans over formatting. The
 * first balanced top-level array is taken instead.
 */
export function extractJsonArray(text: string): unknown[] | null {
  const start = text.indexOf("[");
  if (start < 0) {
    return null;
  }
  let depth = 0;
  let inString = false;
  let escaped = false;
  for (let index = start; index < text.length; index += 1) {
    const character = text[index];
    if (inString) {
      if (escaped) {
        escaped = false;
      } else if (character === "\\") {
        escaped = true;
      } else if (character === '"') {
        inString = false;
      }
      continue;
    }
    if (character === '"') {
      inString = true;
    } else if (character === "[") {
      depth += 1;
    } else if (character === "]") {
      depth -= 1;
      if (depth === 0) {
        try {
          const parsed: unknown = JSON.parse(text.slice(start, index + 1));
          return Array.isArray(parsed) ? parsed : null;
        } catch {
          return null;
        }
      }
    }
  }
  return null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function asRisk(value: unknown): RiskLevel {
  return value === "high" || value === "medium" || value === "low"
    ? value
    : "medium";
}

/** Turns whatever the model returned into proposals, discarding malformed ones. */
export function coerceProposals(raw: unknown[]): ProposedTask[] {
  const proposals: ProposedTask[] = [];
  for (const entry of raw) {
    if (typeof entry !== "object" || entry === null) {
      continue;
    }
    const record = entry as Record<string, unknown>;
    const title = typeof record["title"] === "string" ? record["title"].trim() : "";
    const objective =
      typeof record["objective"] === "string" ? record["objective"].trim() : "";
    if (title.length === 0 || objective.length === 0) {
      continue;
    }
    const criteria = asStringArray(record["acceptanceCriteria"]);
    const priority = Number(record["priority"]);
    proposals.push({
      title: title.slice(0, 180),
      objective,
      reason:
        typeof record["reason"] === "string" && record["reason"].trim().length > 0
          ? record["reason"].trim()
          : "Proposed by the Chief Executive.",
      acceptanceCriteria:
        criteria.length > 0
          ? criteria
          : ["The stated objective is achieved and evidenced."],
      // Requested capabilities are only a request. planInitiative intersects
      // them with what the CEO may grant, so an invented or forbidden
      // capability is stripped and reported rather than honoured.
      requestedCapabilities: asStringArray(
        record["requestedCapabilities"],
      ) as Capability[],
      priority: Number.isFinite(priority) ? priority : 50,
      riskLevel: asRisk(record["riskLevel"]),
    });
  }
  return proposals.slice(0, 4);
}

export interface ModelPlannerOptions {
  provider: ModelProvider;
  workingDirectory: string;
  timeoutMs: number;
  /** Repository facts given to the model so it plans about the real project. */
  context?: string;
  /** Used when the model is unavailable or returns nothing usable. */
  fallback: Planner;
}

/**
 * A planner that asks a real model to decompose owner intent.
 *
 * It always falls back to the heuristic planner rather than failing: an owner
 * who states a goal should get a plan even when a provider is signed out,
 * rate limited, or returns something unparseable. The model changes the
 * quality of the decomposition, never the permissions — every proposal still
 * passes through the same capability clamping and escalation checks.
 */
export class ModelPlanner implements Planner {
  readonly name = "model";

  constructor(private readonly options: ModelPlannerOptions) {}

  async propose(intent: OwnerIntent): Promise<readonly ProposedTask[]> {
    const availability = await this.options.provider.checkAvailability();
    if (!availability.available) {
      return this.options.fallback.propose(intent);
    }

    const controller = new AbortController();
    const response = await this.options.provider.invoke({
      workingDirectory: this.options.workingDirectory,
      prompt: buildPlanningPrompt(
        intent,
        this.options.context ??
          "You have read access to the company-os directory of the repository.",
      ),
      timeoutMs: this.options.timeoutMs,
      signal: controller.signal,
    });

    if (!response.ok) {
      return this.options.fallback.propose(intent);
    }
    const raw = extractJsonArray(response.text);
    if (raw === null) {
      return this.options.fallback.propose(intent);
    }
    const proposals = coerceProposals(raw);
    return proposals.length > 0
      ? proposals
      : this.options.fallback.propose(intent);
  }
}
