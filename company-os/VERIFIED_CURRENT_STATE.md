# Verified Current State

Last verified: 2026-07-27, development project
`yutscolndfhscxfoavdp`.

## Live and proven

- Supabase is the shared authority for goals, tasks, runs, approvals, evidence,
  audit events, release grants, and owner identity.
- Migrations 0011-0019 are applied. The owner revision flow and worker run
  lifecycle both passed rollback-only live database transactions.
- A request-changes decision preserves the authenticated owner's comment,
  increments the review cycle, and queues a new attempt atomically.
- Every new executor attempt opens a durable run before work begins. Finishing
  updates the task and run in one transaction, with lease-worker and lease-epoch
  checks preventing stale writes.
- Worker, reviewer, CEO, artifacts, and owner approval packets share the same
  run ID.
- Provider usage records input, output, cached tokens, and actual cost.
- The factory view, understandable owner approvals, worktree isolation,
  checkpoint preservation, scheduling, and fail-closed policy kernel are
  implemented.

## Verification

- Company OS core: 160 tests pass.
- Dashboard: 26 tests pass.
- Strict TypeScript passes in both packages.
- The optimized Next.js production build passes with all 14 routes.
- `git diff --check` passes.
- Migration 0018 live test: task lease, run start, atomic run/task finish, and
  rollback all passed. The source task and database counts were unchanged.

## Honest limits

- A model cannot certify its own tests. The report format and approval guard now
  accept only runtime-owned `testsCompleted` entries, but the general trusted
  command runner is not built yet. Code tasks requiring checks will return for
  revision until it exists.
- Claude may need re-authentication. With only Codex available, implementation
  and judgement are not genuinely independent even though the role checks run.
- The dashboard is local, not yet a private shared deployment.
- Six historical tasks reached approval-era statuses before durable packets
  existed. They require an explicit repair/archive policy, not a blanket update.
- Evidence references local checkpoint commits. Multi-machine artifact storage
  is not yet present.
- GitHub draft-PR support exists on a separate local branch and has not been
  integrated or credentialed.
- The scheduler is a Windows logon task on Cade's PC, not a cloud worker.

## Next milestone

Add a project-owned verification registry with fixed commands, timeouts,
captured stdout/stderr, and structured pass/fail records. Run commands inside
the task worktree after the provider finishes and before review. A task may
reach an owner only when every required check maps to a passing verifier result.
