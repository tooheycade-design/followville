# Verified Current State

Last verified: 2026-07-28, development project
`yutscolndfhscxfoavdp`.

## Live and proven

- Supabase is the shared authority for goals, tasks, runs, approvals, evidence,
  audit events, release grants, and owner identity.
- Migrations 0011-0025 are applied. The owner revision flow, reviewer revision
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
- Public-town changes require the `browser_preview` capability after the fixed
  Playwright suite passes. The runtime captures desktop home, loaded desktop
  town, and mobile home screenshots plus Playwright traces and a structured
  report.
- Browser evidence records console errors, failed requests, and HTTP error
  responses. Deliberate Chromium `ERR_ABORTED` cancellations are retained as
  ignored diagnostics instead of being mislabeled as network failures.
- Runtime evidence is never described as a Git checkpoint file. It requires a
  run ID and private object storage, then follows the same immutable,
  owner-only artifact path as other approval evidence.
- The preview server serves only real paths inside the isolated worktree and
  rejects symlink escapes.
- Worker nodes register machine, provider, software version, executable
  capabilities, health, and current assignment. Leasing requires a fresh
  online worker whose project, assigned agent, and capabilities match the task.
- Agent capability grants are normalized in the database, so a worker cannot
  advertise a capability outside its assigned profile.
- Cade's worker now uses Codex for implementation and an authenticated Claude
  Code subscription for model judgement. A direct headless Claude invocation
  returned the exact requested sentinel with a durable provider session ID.
- The repository includes an owner-safe macOS launchd provisioner for Zach's
  worker. It validates private env-file permissions, pinned tooling, provider
  authentication, and `worker --check` before installing an always-on service;
  generated service files contain no secrets.
- Explicit worker states now win over heartbeat freshness in the dashboard, so
  a graceful stop is shown as offline immediately while stale heartbeats still
  detect crashed processes.
- Revision worktrees now start from the task's prior checkpoint instead of
  resetting the task branch to the operator checkout. Same-machine revisions
  also resume and fork the prior provider conversation; provider and stable
  machine identity must both match, so sessions are never assumed portable.

## Verification

- Company OS core: 214 tests pass.
- Dashboard: 39 tests pass.
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
- A real three-viewport browser preview passed: all pages rendered, the town
  loading overlay cleared, no console errors or real HTTP/network failures
  occurred, and three screenshots, three traces, and one report were produced.
- Migrations 0023-0025 live test: worker registration and heartbeat, permission
  isolation, dependency/capability-compatible leasing, stale/offline refusal,
  task-heartbeat propagation, and rollback all passed.
- Cade's current worker registered live with the Codex provider, Claude Code
  reviewer metadata, and its executable capability set. Its heartbeat advanced
  across multiple reads, the shared state loader returned it, and the
  previously backed-off queue pass recovered to success with zero failures.
- A real two-turn headless Claude run resumed its recorded session, recalled
  the first turn's sentinel, and returned a different forked session ID.

## Honest limits

- Blender/generator and other non-web code areas do not yet have registered
  verification commands. Changes there fail closed rather than claiming safety.
- GitHub draft review is live on Cade's worker. Zach's launchd provisioner is
  ready, but his Mac still needs its local env file and provider sign-in before
  it can register.
- The scheduler is a Windows logon task on Cade's PC, not a cloud worker.

## Next milestone

Provision Zach's worker, then register trusted Blender/generator previews and
the bounded context package used for specialist work.
