# Followville Company OS

Followville Company OS is a proposed private control plane for Cade and Zach to
assign goals to AI workers, observe their work, enforce budgets and permissions,
and approve or reject results before anything reaches production.

This directory is intentionally separate from the public town runtime. The
public website, canonical `world_state.json`, Blender scene, claims, and live
Supabase schema are not changed by this foundation.

## Phase 0 Status

| Area | Status | Notes |
| --- | --- | --- |
| Product and architecture | Implemented | Reviewable documents in `docs/` |
| Company constitution | Proposed | Requires Cade or Zach approval |
| Domain contracts | Implemented | Strict TypeScript and Zod schemas |
| Policy engine | Implemented | Budgets, capabilities, approval gates |
| Local workflow simulation | Implemented | Deterministic and API-free |
| Database schema | Proposed | Migration is not applied |
| Agent profiles | Implemented | Seed fixtures, no provider calls |
| Owner dashboard | Implemented (local) | `apps/company-dashboard`; goals, approvals, agents, audit, build status. Local JSON store and a dev owner picker until the development Supabase project exists |
| Model providers | Planned | No API package or credential required |
| Durable workflow provider | Planned | Inngest recommended for MVP |
| GitHub App | Planned | Read-only first, then scoped write tools |
| Production deployment | Blocked by policy | Requires owner approval |

## Local Commands

From the repository root:

```text
pnpm company-os:typecheck
pnpm company-os:test
pnpm company-os:simulate
```

The simulator writes nothing, calls no external service, spends no model
budget, and performs no Git, database, deployment, or social-media action.

## Review Order

1. `docs/PRD.md`
2. `docs/CONSTITUTION.md`
3. `docs/ARCHITECTURE.md`
4. `docs/DATA_MODEL.md`
5. `docs/SECURITY_AND_OPERATIONS.md`
6. `docs/ROADMAP.md`
7. `docs/decisions/0001-control-plane-owned-orchestration.md`

Nothing in this folder authorizes autonomous production changes.
