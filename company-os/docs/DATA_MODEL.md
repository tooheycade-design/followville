# Data Model and Contracts

Status: Proposed database design; TypeScript contracts implemented in Phase 0.

## Design Rules

- UUID primary keys for distributed creation.
- `timestamptz` for all instants.
- Append-only audit and usage ledgers.
- Explicit organization/project membership on every private record path.
- Optimistic version numbers for mutable records.
- Idempotency keys on events, commands, tool calls, and approvals.
- JSON only for provider-specific metadata and immutable snapshots, not core
  relations or authorization.
- Company tables live in a private, non-Data-API schema.
- Dashboard writes pass through server-side commands, not broad table grants.

## Major Tables

### Identity and Governance

| Table | Purpose |
| --- | --- |
| `organizations` | Followville company boundary |
| `organization_members` | Cade/Zach owner membership and future operators |
| `constitution_versions` | Immutable proposed/ratified/superseded policy |
| `agent_profiles` | Persistent role, limits, permissions, model preferences |
| `agent_prompt_versions` | Immutable system prompt history |
| `capability_grants` | Agent/tool/repository/path/environment allow rules |
| `model_catalog` | Dated provider/model capabilities and prices |

### Work

| Table | Purpose |
| --- | --- |
| `projects` | Followville product or internal work boundary |
| `goals` | Owner-level desired outcomes |
| `initiatives` | Manager-created delivery groups |
| `tasks` | Atomic assignments and state machine |
| `task_dependencies` | Directed dependency edges |
| `task_acceptance_criteria` | Individually verifiable completion conditions |
| `task_file_scopes` | Allowed repositories and path patterns |
| `task_transitions` | Append-only task status history |
| `messages` | Structured agent/owner communication |
| `message_attachments` | Evidence and file references |

### Execution and Review

| Table | Purpose |
| --- | --- |
| `runs` | One bounded agent execution |
| `run_attempts` | Retry-specific lifecycle and errors |
| `tool_calls` | Requested capability, input digest, decision, result digest |
| `artifacts` | Private evidence metadata and content hash |
| `reviews` | Independent review outcome and evidence |
| `approval_requests` | Human decision package |
| `approval_decisions` | Immutable owner action |
| `workspace_leases` | Branch/worktree/container and file-area lease |

### Memory, Events, and Cost

| Table | Purpose |
| --- | --- |
| `memory_records` | Versioned sourced memory with confidence/status/expiry |
| `memory_relations` | Supersedes, contradicts, duplicates, supports |
| `events` | Idempotent event inbox |
| `event_deliveries` | Workflow delivery attempts |
| `schedules` | Bounded recurring triggers |
| `budget_policies` | Task/agent/project/provider/time-window limits |
| `budget_reservations` | Pre-call estimated spend held for a run |
| `usage_ledger` | Immutable tokens, provider usage, and cost |
| `audit_events` | Append-only business/security action trail |
| `incidents` | Security, production, cost, or automation incidents |

## Agent Profile Contract

An agent profile includes:

- stable ID, slug, name, role, description, responsibilities;
- active prompt version;
- preferred and fallback capability classes;
- tools and explicit prohibited capabilities;
- allowed repositories, path globs, and environments;
- maximum task cost, daily cost, run duration, retries, and concurrency;
- approval requirements and escalation rules;
- availability and performance evidence references.

Profiles never contain credentials. A profile points to secret capability names
that the runtime may resolve only after policy authorization.

## Task Contract

Tasks include objective, reason, parent goal/initiative/task, dependencies,
assignee, reviewer, priority, status, risk, context package references, allowed
capabilities and file scopes, budget, expected outputs, acceptance criteria,
test requirements, approval requirements, retry/loop counters, branch/PR,
estimates, actuals, final result, and human decision.

The task status set and transitions are defined in TypeScript and mirrored by a
database constraint. Invalid transitions fail closed.

## Message Contract

Messages contain sender/recipient, project/task/thread, type, priority,
requested action, context summary, evidence references, expected output,
deadline, confidence, cost estimate, related files/commits, status, and
expiration. Free-form prose is payload, not state.

## Run Contract

Runs capture agent, task, profile/prompt/model versions, trigger, mode,
workspace, context manifest, budget reservation, start/end, status, retry
fingerprints, usage, result summary, error category, and evidence.

## Approval Contract

An approval request identifies exact action, scope, commit/migration/deployment
reference, requester, reason, evidence, tests, risk, reversibility, cost,
recommendation, alternatives, required approvers and role, expiration, and
idempotency key. Decisions are separate immutable rows.

The proposed SQL stores requests and decisions as immutable records. Current
request state is derived from those decisions and expiration rather than
trusted as a mutable flag. Project-scoped composite foreign keys prevent a
record from being attached to another repository project in the same company.

Approval is invalid after scope, commit, policy version, cost ceiling, or
expiration changes.

## Memory Contract

Memory types are `company`, `project`, `decision`, `task`, `agent`, and
`temporary`. Each record has source, source digest, author, confidence, status,
version, effective time, expiration, superseding record, and retrieval tags.

The initial retrieval strategy is relational and tagged. Vector search is
deferred until measured retrieval failures justify its privacy and complexity.

## Audit Contract

Audit events store actor type/ID, action, target, project/task/run, policy
decision, request and result digests, evidence IDs, IP/session metadata where
appropriate, timestamp, and correlation/idempotency keys.

Audit records exclude secrets, raw private prompts where avoidable, hidden
chain of thought, and unredacted personal data.

## Database Migration

`db/migrations/0001_company_os_foundation.sql` is a proposed, unapplied
reference migration. It creates a private `company_ops` schema and core MVP
tables. It intentionally grants no client role broad table access.

Before any application:

1. Decide existing versus separate Supabase project.
2. Generate a canonical migration using the selected Supabase CLI workflow.
3. Run local migrations and database tests.
4. Review RLS/grants and database advisors.
5. Obtain owner approval for the exact migration hash.

Relevant current guidance:

- RLS: https://supabase.com/docs/guides/database/postgres/row-level-security
- API security: https://supabase.com/docs/guides/api/securing-your-api
- Supabase Queues: https://supabase.com/docs/guides/queues

Supabase's 2026 Data API changes make explicit API exposure/grants especially
important. Private Company OS tables should remain unexposed.
