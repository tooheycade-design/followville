# Security and Operations

Status: Proposed controls for owner review

## Trust Boundaries

1. Public Followville browser: untrusted.
2. Owner browser: authenticated but still an untrusted client.
3. Company OS server: trusted command boundary.
4. Workflow provider: coordination dependency, no unilateral authority.
5. Agent/model provider: untrusted contractor producing proposed actions.
6. Sandbox/worktree: disposable, scoped execution boundary.
7. GitHub/Supabase/Vercel: production systems reached only by narrow adapters.

Prompt text, repository files, web pages, tool output, model output, and
attachments are all untrusted data. None may alter policy.

## Authentication and Authorization

- Reuse Supabase Auth only after an owner decision.
- Authorize against an explicit `organization_members` row, not merely
  `profiles.is_admin`.
- Require server-side user validation for every command.
- Use short sessions, reauthentication for high-risk approvals, and MFA for
  owner accounts before production tools are connected.
- Approval authorization is area, environment, risk, and action specific.
- Agent capability checks are deterministic and occur before every tool call.

## Secrets

- Store secrets in provider-managed encrypted environment storage or a
  dedicated secret manager.
- Browser-exposed variables are never secret.
- Workers receive scoped short-lived tokens when possible.
- GitHub App installation tokens replace personal access tokens.
- The service-role/secret Supabase key remains server-only.
- Log secret identifiers and access outcome, never values.
- Rotate after exposure, personnel/device loss, or privilege changes.

## Git and Workspace Safety

- One task, one branch/worktree, one workspace lease.
- Protected branches reject direct agent pushes.
- Base commit, path scope, file hashes, and dirty state are recorded at start.
- Overlapping write scopes block dispatch or require an explicit coordination
  decision.
- Sandboxes deny host home directories, unrelated repositories, and production
  credentials.
- The policy engine resolves the repository root and target parent with the
  operating system's `realpath`; it rejects targets outside that root,
  including symlink and Windows reparse-point escapes.
- Generated patches and commits are reviewed independently.

## Side-Effect Classification

| Class | Examples | Default |
| --- | --- | --- |
| Read | inspect repo, docs, staging logs | Allowed in scope |
| Local reversible | edit isolated worktree, run tests | Allowed in scope |
| Shared reversible | push review branch, open draft PR | Approval configurable |
| Production | merge, deploy, send communication, apply migration | Owner approval |
| Irreversible/high impact | delete data, charge, publish, grow canonical world | Explicit owner approval, often two-person |

## Failure and Retry

- Transient provider/network failures: exponential backoff with jitter.
- Validation, permission, policy, or budget failures: no automatic retry.
- Tool side effects require idempotency keys and result reconciliation.
- Default maximum: two retries after the first attempt; lower for expensive or
  risky work.
- Retry exhaustion creates one attention item and pauses the run.
- Resuming uses durable step results rather than repeating successful work.

## Loop Detection

Pause when any configured threshold is reached:

- repeated equivalent message fingerprint;
- same tool and normalized arguments;
- same failing test/error signature;
- same task transition cycle;
- repeated model escalation;
- repeated diff reversion;
- review cycle count;
- cost or runtime slope without new evidence.

The local foundation uses transition and message fingerprints. Production
thresholds belong in versioned policy, not model prompts.

## Event Architecture

Every inbound event has source, type, schema version, occurred time, received
time, payload digest, idempotency key, and status. Webhooks are signature
verified. Processing uses an inbox record plus durable workflow invocation.
Duplicate delivery returns the existing result.

Schedules create events; they do not directly run broad agent exploration.
Every scheduled trigger names a project, task template, budget, capability
scope, and expiration.

## Observability

- Correlation IDs connect goal, task, run, tool call, workflow, commit, review,
  approval, and release.
- Structured logs contain event names and IDs, not secrets or chain of thought.
- Metrics cover queue age, run duration, retries, tool denials, budget use,
  provider errors, review outcomes, owner decisions, and incidents.
- Provider traces are supplemental and may omit sensitive content.
- Audit and usage ledgers reconcile independently.

## Incident Response

1. Fail closed and pause affected dispatch.
2. Preserve audit evidence.
3. Revoke or rotate affected credentials.
4. Notify Cade and Zach through the attention queue and an out-of-band path.
5. Identify scope, user/data impact, and production state.
6. Restore or roll back using recorded versions.
7. Record an incident review and corrective action.

## Moderation and Minors

Before agents operate on public chat at scale, implement:

- community guidelines and age-appropriate defaults;
- report, block, mute, rate-limit, and appeal workflows;
- automated triage with confidence and human escalation;
- retention/deletion rules and restricted evidence access;
- no autonomous permanent ban based solely on model output;
- threat/self-harm escalation procedures reviewed by qualified humans;
- clear separation between moderation evidence and general model memory.

## Deployment Strategy

Phase 0 is local only. Later environments are:

- local: seeded data and simulated providers;
- preview: isolated database/project and draft integrations;
- staging: realistic auth, workflow, GitHub test repository, no production keys;
- production: owner-approved configuration and protected release.

Every deployment references an immutable commit, migration set, policy version,
configuration digest, tests, and rollback target.

## Security Review Gates

Mandatory review before:

- connecting any model or GitHub credential;
- using existing Followville Supabase;
- exposing Company OS routes;
- enabling schedules;
- adding a write-capable tool;
- storing user/community data;
- enabling production merge/deploy;
- changing owner or approval policy.
