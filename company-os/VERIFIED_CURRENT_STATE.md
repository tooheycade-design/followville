# Verified Current State

Last verified: 2026-07-28, development project
`yutscolndfhscxfoavdp`.

## Live and proven

- Supabase is the shared authority for goals, tasks, runs, approvals, evidence,
  audit events, release grants, and owner identity.
- Migrations 0011-0022 are applied. The owner revision flow, reviewer revision
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
- The private dashboard is live at
  `https://followville-company-os.vercel.app`.
- Eleven packet-less legacy tasks were canceled with eleven immutable audit
  events; none remain in the owner queue.
- Owner-approved write tasks can be published only as exact-checkpoint
  `agent/task-*` branches and private draft PRs. The adapter uses GitHub App
  tokens, keeps credentials out of command arguments, pushes with
  force-with-lease, reconciles retries, and records the resulting URL.
- GitHub App `Followville Company OS` is installed only on the private
  `tooheycade-design/followville` repository with Metadata read, Contents
  write, and Pull requests write. Draft PR #3 proved the full path. Its base
  was corrected to `codex/company-os-lifecycle-hardening`, leaving exactly
  `company-os/docs/AUTOMATION_SMOKE_TEST.md` in the review diff.
- Publication now requires an explicit review base and verifies that the
  approved checkpoint descends from it before any branch push.
- The private `company-os-evidence` bucket is live with no browser Storage
  policies. Evidence metadata is goal/task/run scoped, append-only including
  truncate protection, and database-validated against the creating run.
- Worker uploads use content-derived immutable paths, refuse overwrite, and
  verify stored bytes by downloading and hashing them. Approval links are
  owner-authenticated, organization-scoped, short-lived, and `no-store`.
- Model provider subprocesses no longer inherit Supabase, GitHub App, paid API,
  or other host secrets.

## Verification

- Company OS core: 198 tests pass.
- Dashboard: 32 tests pass.
- Strict TypeScript passes in both packages.
- The optimized Next.js production build passes with all 15 routes.
- `git diff --check` passes.
- Migration 0018 live test: task lease, run start, atomic run/task finish, and
  rollback all passed. The source task and database counts were unchanged.
- Migrations 0020-0021 live tests: reviewer rejection requeued below the cap,
  stopped at the third review cycle, and rolled back without changing the task.
- Migration 0022 live tests: private bucket configuration, zero browser
  policies, four-row backfill, exact path/agent scope, insert validation, and
  update/delete/truncate refusal all passed. A live upload was downloaded and
  hash-verified; replacement was refused and the test object was removed.
- The real verification process runner passed against this worktree.
- An agent-created dependency directory is rejected instead of being used by
  the verifier.

## Honest limits

- Blender/generator and other non-web code areas do not yet have registered
  verification commands. Changes there fail closed rather than claiming safety.
- Claude may need re-authentication. With only Codex available, implementation
  and judgement are not genuinely independent even though the role checks run.
- GitHub draft review is live on Cade's worker. Zach's machine does not yet
  have its own worker credentials.
- The scheduler is a Windows logon task on Cade's PC, not a cloud worker.

## Next milestone

Run browser previews as a controlled worker capability and attach desktop,
mobile, console, network, trace, and test evidence. Then restore Claude
authentication and provision Zach's worker.
