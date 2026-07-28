# Staged Roadmap

The end state: a small AI company that runs Followville. Agents hold persistent
roles, wake on schedules, message each other directly, do real work on real
repositories and real Blender scenes, review each other, and present finished
results to Cade and Zach for approval. Different providers fill different
seats. Cade and Zach stop relaying messages between chat windows.

This document tracks what is done, what is next, and what is honestly hard.

## Current correction

Phases 1 and 2 have advanced beyond the original text below. Shared Supabase
state, owner authentication, the factory dashboard, leases, isolated
worktrees, model execution, review, scheduling, durable checkpoints, owner
feedback, and truthful run records are implemented in development.

The trusted verification-command registry, private dashboard, historical task
cleanup, GitHub App draft review, and private multi-machine artifact storage
are now implemented and live in development. Model prose is not test evidence;
fixed repository-owned commands produce the pass/fail record, and reviewer
rejections automatically queue another attempt. Controlled browser previews
now capture desktop/mobile/town screenshots and traces, fail on console or real
network/HTTP errors, and persist evidence privately. Registered worker health
and agent/capability-compatible dispatch are also live. Next: restored
two-model review and Zach's worker.
See `../VERIFIED_CURRENT_STATE.md`.

## Phase 0 — Architecture and deterministic foundation (done)

Constitution, PRD, architecture, data model, security plan, decision records;
strict domain schemas; fail-closed policy engine; task transition and loop
guards; deterministic goal-to-approval simulation; seed agent profiles; tests.

Proved the hard part: a task cannot spend, use a capability, approve itself, or
reach production because a model asked.

## Phase 1 — Owner dashboard and shared control plane (in progress)

Done:

- Private Next.js dashboard: goals, approvals, agents, audit, build status.
- Owner decision kernel: digest-pinned, role-checked, expiry-checked.
- Development Supabase project and migrations 0001-0019 applied and verified.
- Supabase-backed shared state, owner authentication, owner membership, held
  work decisions, finished-work approvals, and owner-requested revisions.
- A factory view showing work moving through the lifecycle.

Completed:

- Private production deployment at `https://followville-company-os.vercel.app`
  so Cade and Zach reach the same shared state.
- Historical packet-less approval tasks were canceled with immutable audit
  events.

Exit: both owners see identical company state, and every action is
reconstructable from the audit trail.

## Phase 2 — The worker runtime (the real unlock)

This phase is in progress. The queue, leases, heartbeats, isolated worktrees,
Codex and Claude adapters, durable checkpoint branches, evidence review, CEO
gate, revision loop, local scheduler, and run/usage ledger exist.

Remaining work broadens the proven worker:

1. Assemble a context package: constitution, agent profile, task, retrieved
   memory, relevant files. Not the whole company history.
2. Extend trusted verification to Blender and generator changes.
Exact-checkpoint draft pull requests, private multi-machine evidence, and
controlled browser previews are implemented and proven. Worker processes now
register their machine, provider, executable capabilities, current assignment,
and heartbeat; incompatible workers cannot lease a task.

Exit: an owner approves or rejects a complete draft PR package that no human
assembled.

## Phase 3 — Provider adapters and the model roster

One interface, several backends. Which seat an agent sits in should be
configuration, not code.

| Provider | Automation path | Cost model |
| --- | --- | --- |
| Claude | Claude Code headless / Agent SDK | Existing subscription |
| OpenAI | Codex CLI headless; Codex cloud tasks | Existing subscription |
| Google | Gemini CLI | Existing subscription |
| xAI (Grok) | API only | Paid per token |
| Any | Direct API | Paid per token |

Honest constraints:

- Consumer subscriptions are not API keys. Subscription-backed work runs
  through each vendor's local coding CLI on a real machine, under that
  vendor's terms. Do not automate consumer web interfaces.
- Antigravity is IDE-shaped and is not a reliable headless worker. Prefer the
  Gemini CLI for scheduled Google work.
- A Grok CEO seat requires xAI API credits. It is the one named role that
  cannot run on an existing subscription.
- Cheap, frequent work (classification, queue checks, routing) should use the
  cheapest capable model. Reserve strong models for architecture, hard
  debugging, and critical review.

## Phase 4 — Autonomy: schedules, messages, and the CEO

- **Scheduled wake-ups.** Hourly queue check, daily executive report, daily cost
  audit, stale-task sweep, memory maintenance. Cheapest capable model by
  default.
- **Event triggers.** Task created, task unblocked, PR opened, test failed,
  budget threshold crossed, agent blocked, owner left feedback.
- **The message loop.** Agents read their inbox, act, and reply with structured
  messages. This is what replaces Cade and Zach copying text between models.
  The schema exists; the loop does not yet.
- **The CEO agent.** Interprets owner goals, sets priorities, delegates to
  specialists, resolves low-risk disagreements, escalates everything else. It
  has no authority over Cade or Zach and no production capability.
- **Two machines, one company.** Cade's PC and Zach's Mac both run workers
  against the same queue. Leases and heartbeats prevent duplicate work.

Exit: an owner sets a goal in the morning and finds reviewed work waiting,
without prompting anyone.

## Phase 5 — Followville senses and hands

The specialist roles, roughly in order of feasibility:

- **World QA agent.** Walks the live town with Playwright, captures screenshots,
  and files tasks with visual evidence: a broken road seam, a misplaced sign, a
  sky that regressed, a house clipping a hill. The browser harness already
  exists, which makes this the best first specialist.
- **Blender/render agent.** Wraps the existing guarded growth and render
  scripts. Renders and previews are safe; canonical world growth stays an
  owner-approved action and never runs unattended.
- **Website agent.** Prepares site changes as draft PRs with before/after
  screenshots. Deployment stays owner-approved.
- **Design director.** Reviews UI and world visuals against the Followville
  identity and rejects generic output.
- **Social agent.** Drafts Instagram concepts and captions for approval, and
  ties follower milestones to town events. Never publishes.
- **Growth and monetization agents.** Read-only analytics first, proposals
  second.
- **Community and moderation agent.** Chat safety tooling and abuse detection.

Instagram is the weakest link and should be planned honestly: the platform's
API is restrictive and scraping violates its terms. Start with owner-entered
metrics and screenshots; pursue official API access separately.

## Phase 6 — Scale and resilience

Worker pools, stronger file-area ownership, Temporal if workflows outgrow
serverless limits, dedicated secrets and evidence infrastructure, disaster
recovery, formal privacy and moderation reviews.

## What "24/7" actually means

An agent on a personal computer sleeps when that computer sleeps. Genuine
round-the-clock operation requires either a machine left running or a small
always-on cloud worker. Cloud workers need API credentials, which cost money
per token. The recommended path while revenue is zero: subscription-backed
workers on both owners' machines for the heavy work, plus optionally one cheap
always-on cloud agent for coordination and reporting. Set an explicit monthly
cap with warning and hard-stop levels before enabling any paid provider.

## Sequencing summary

| Stage | Unlocks | Blocked on |
| --- | --- | --- |
| Finish Phase 1 | Shared state for both owners | Owner pastes dev Supabase keys locally |
| Phase 2 | Agents actually do work | Phase 1 persistence |
| Phase 3 | Multiple providers in seats | Phase 2 runtime |
| Phase 4 | The company runs itself | Phases 2-3; paid credits for a Grok seat |
| Phase 5 | Followville-specific work | Phase 4 scheduling |

## First useful feature

Phase 0's local goal-to-approval simulator. It deliberately does not pretend to
run an AI team. Real providers arrive only after the deterministic controls pass
owner review.
