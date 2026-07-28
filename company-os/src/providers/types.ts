/**
 * How a provider is paid for.
 *
 * `subscription` runs consume an included monthly allowance rather than
 * per-token dollars. They are not free: the limit is quota and rate, not
 * spend, so a dollar budget alone will never stop them. Subscription providers
 * must therefore be bounded by run counts and durations instead.
 *
 * `api` runs bill per token and are governed by the dollar budgets in the
 * policy engine.
 */
export type BillingMode = "subscription" | "api";

export interface ModelUsage {
  inputTokens: number;
  outputTokens: number;
  cachedInputTokens: number;
  /** Reported by the provider when it bills per token; zero on subscriptions. */
  costUsdMicros: number;
}

export interface ProviderRequest {
  /** Working directory the provider may operate in. */
  workingDirectory: string;
  prompt: string;
  /**
   * A prior local provider session for this same task and continuity key.
   * Providers must start a fresh child/fork so the prior audit record remains
   * immutable.
   */
  resumeSessionId?: string;
  /** Hard ceiling on wall-clock time. */
  timeoutMs: number;
  signal: AbortSignal;
}

export interface ProviderResponse {
  ok: boolean;
  text: string;
  usage: ModelUsage;
  model: string | null;
  sessionId: string | null;
  /** Set when the provider itself refused or could not run. */
  failureReason: string | null;
}

export type ProviderAvailability =
  | { available: true; detail: string }
  | { available: false; reason: "not_installed" | "not_authenticated" | "unknown"; detail: string };

/**
 * A model backend the runtime can invoke.
 *
 * Deliberately narrow: the control plane owns policy, budgets, and state, and
 * a provider only turns a prompt into text plus usage. Swapping Claude for
 * Codex or Gemini must never change who may do what.
 */
export interface ModelProvider {
  readonly name: string;
  readonly billingMode: BillingMode;
  /** Checks the backend can actually run, without spending anything. */
  checkAvailability(): Promise<ProviderAvailability>;
  invoke(request: ProviderRequest): Promise<ProviderResponse>;
}
