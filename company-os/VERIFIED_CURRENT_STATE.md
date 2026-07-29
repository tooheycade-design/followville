# Verified Current State

Last verified: 2026-07-29, development project
`yutscolndfhscxfoavdp`.

## Live and proven

- Supabase is the shared authority for goals, tasks, runs, approvals, evidence,
  audit events, release grants, and owner identity.
- Migrations 0011-0037 are applied. The owner revision flow, reviewer revision
  flow, and worker run
  lifecycle both passed rollback-only live database transactions.
- A request-changes decision preserves the authenticated owner's comment,
  increments the review cycle, and queues a new attempt atomically.
- Every new executor attempt opens a durable run before work begins. Finishing
  updates the task and run in one transaction, with lease-worker and lease-epoch
  checks preventing stale writes.
- Worker, reviewer, CEO, artifacts, and owner approval packets share the same
  run ID.
- Provider usage records input, output, and cached tokens. Metered API providers
  record actual cost; subscription providers record zero spend and are bounded
  by durable run counts plus wall-clock limits.
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
- The Content Studio pins draft concepts to confirmed town snapshots, records
  owner concept selection as an append-only digest-pinned decision, and queues
  only private, review-gated production work. It has no publisher or Instagram
  credential and does not claim to render the canonical town automatically.
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
- Every worker attempt now records a versioned, machine-readable handoff in
  the audit report. It pins the task version, branch, base and checkpoint,
  changed files, checks and failures, evidence IDs, blockers, provider,
  stable worker identity, remaining work, and recommended next action. A later
  worker receives that record as context while current task scope and policy
  remain authoritative.
- Candidate `.glb` and `.gltf` models under `company-os/candidates/` now have
  a fixed headless Blender verifier. It uses factory startup with auto-execute
  disabled, a scrubbed environment, bounded subprocess time, neutral lighting
  and camera framing, private run-scoped PNG evidence, and JSON geometry
  metrics. External glTF URIs must resolve to real files inside the isolated
  worktree.
- Workers advertise `blender_preview` only when Blender is actually executable
  and the private artifact store is available. Cade's installed Blender 5.1.2
  passed a real GLB import and render.
- One task may consume at most three subscription-backed implementation
  attempts across retries and review cycles. The fourth attempt is blocked
  before either model CLI starts. Claude Code's API-equivalent estimate is not
  mislabeled as money charged to the subscription account.
- The dashboard now has a live operating report derived directly from goals,
  tasks, runs, approvals, workers, and immutable audit events. It separates
  the last 24 hours from the seven-day review and surfaces owner attention,
  failures, held work, draft PRs, worker capacity, subscription run counts,
  and metered API spend.

## Verification

- Company OS core: 246 tests pass; one Windows symlink-escape fixture is
  skipped because this account cannot create symlinks. The same escape is
  enforced by canonical-path checks and covered where symlinks are permitted.
- Dashboard: 59 tests pass.
- Strict TypeScript passes in both packages.
- The optimized Next.js production build passes with the Content Studio route.
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
- The durable handoff survives the worker report encode/decode path and is
  included in the next revision briefing without granting it authority.
- A real 27 KB Draco-compressed avatar GLB rendered to a nonblank 960x960 PNG.
  Blender reported two renderable meshes, 2,620 polygons/triangles, four
  materials, and no external textures.

## Honest limits

- Canonical Blender scenes, generator code, and other non-web code areas do not
  yet have registered verification commands. Candidate interchange models are
  deliberately limited to GLB/glTF; untrusted `.blend` files remain fail-closed
  until an operating-system sandbox can constrain linked external data.
- GitHub draft review is live on Cade's worker. Zach's launchd provisioner is
  ready, but his Mac still needs its local env file and provider sign-in before
  it can register.
- The scheduler is a Windows logon task on Cade's PC, not a cloud worker.

## Next milestone

Register guarded generator workflows, then provision Zach's worker and expand
the specialist workflow catalog.
