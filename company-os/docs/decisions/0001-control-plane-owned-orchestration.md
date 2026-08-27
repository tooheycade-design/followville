# ADR 0001: Followville Owns the Agent Control Plane

Date: 2026-07-26
Status: Proposed
Decision owners: Cade and Zach

## Context

Followville needs multi-provider agents, durable work, Git isolation, budgets,
review, and owner approval. Agent frameworks provide useful model loops, tools,
handoffs, memory, and traces, but their abstractions and provider state cannot
be the source of company authority.

## Decision

Build a small provider-neutral control plane in strict TypeScript. It owns:

- domain schemas and state transitions;
- capabilities and path/environment scope;
- budgets and reservations;
- approval requirements;
- audit and usage records;
- context manifests;
- retry and loop limits.

Use provider SDKs behind adapters for bounded execution. Pilot Inngest as the
durable workflow adapter after Phase 0. Store durable company truth in
Postgres. Do not put broad agent autonomy or policy in prompts.

## Consequences

Positive:

- authority remains testable and provider independent;
- switching models or workflow vendors does not rewrite company policy;
- deterministic checks can block work before token spend or side effects;
- the dashboard can reconstruct state without provider traces.

Negative:

- more application code than adopting one opinionated agent framework;
- state transitions and policy require careful maintenance;
- provider-specific features need adapter work.

## Alternatives

- OpenAI Agents SDK as the whole platform: rejected as source of truth, retained
  as an execution adapter.
- LangGraph as the whole platform: deferred; persistence is strong but the
  control plane still needs separate permissions, budget, and approval truth.
- CrewAI or AutoGen team runtime: rejected for MVP because roles/conversations
  are not the primary hard problem.
- Temporal immediately: rejected due operational complexity at current scale.
- Plain cron and database polling: rejected beyond local simulation because
  approvals and retries require durable waits and observability.

## Review Trigger

Revisit when the MVP supports ten or more concurrent workers, workflows last
weeks, Inngest constraints materially shape product behavior, or provider
portability tests fail.
