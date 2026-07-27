# Verified Current State

Last verified: 2026-07-27, development project
`yutscolndfhscxfoavdp`.

## Live and proven

- Supabase is the shared authority for goals, tasks, runs, approvals, evidence,
  audit events, release grants, and owner identity.
- Migrations 0011-0021 are applied. The owner revision flow, reviewer revision
  flow, and worker run
  lifecycle both passed rollback-only live database transactions.
- A request-changes decision preserves the authenticated owner's comment,
  increments the review cycle, and queues a new attempt atomically.
- Every new executor attempt opens a durable run before work begins. Finishing
  updates the task and run in one transaction, with lease-worker and lease-epoch
  checks preventing stale writes.
- Worker, reviewer, CEO, artifacts, and owner approval packets share the same
  run ID.
- Provider usage records input, output, cached tokens, and actual cost.
- Verification commands are selected by repository code, never model text.
  Company OS, dashboard, and public-town browser changes have fixed suites;
  unknown code paths fail closed.
- A failed runtime check reaches review with diagnostics and is automatically
  queued as a new revision after the reviewer sends it back.
- Automatic revisions stop at three review cycles in the database; a fourth
  attempt cannot be leased without owner intervention.
- The factory view, understandable owner approvals, worktree isolation,
  checkpoint preservation, scheduling, and fail-closed policy kernel are
  implemented.

## Verification

- Company OS core: 176 tests pass.
- Dashboard: 26 tests pass.
- Strict TypeScript passes in both packages.
- The optimized Next.js production build passes with all 14 routes.
- `git diff --check` passes.
- Migration 0018 live test: task lease, run start, atomic run/task finish, and
  rollback all passed. The source task and database counts were unchanged.
- Migrations 0020-0021 live tests: reviewer rejection requeued below the cap,
  stopped at the third review cycle, and rolled back without changing the task.
- The real verification process runner passed against this worktree.
- An agent-created dependency directory is rejected instead of being used by
  the verifier.

## Honest limits

- Blender/generator and other non-web code areas do not yet have registered
  verification commands. Changes there fail closed rather than claiming safety.
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

Repair or archive the historical packet-less tasks with an explicit policy,
then deploy the private dashboard for Cade and Zach. After that, integrate the
already-started draft pull-request kernel and durable shared artifact storage.
