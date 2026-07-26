# Staged Roadmap

The end state: a small AI company that runs Followville. Agents hold persistent
roles, wake on schedules, message each other directly, do real work on real
repositories and real Blender scenes, review each other, and present finished
results to Cade and Zach for approval. Different providers fill different
seats. Cade and Zach stop relaying messages between chat windows.

This document tracks what is done, what is next, and what is honestly hard.

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
- Development Supabase project created and migration 0001 applied and verified
  (`company-os/db/README.md`).

Remaining:

- Supabase adapter replacing the local JSON store, so state is shared.
- Supabase Auth with owner membership, replacing the local owner picker.
- Private deployment so Cade and Zach reach the same dashboard from anywhere.

Exit: both owners see identical company state, and every action is
reconstructable from the audit trail.

## Phase 2 — The worker runtime (the real unlock)

Nothing before this makes an agent do work. This phase builds the loop that
turns a queued task into a reviewed draft pull request:

1. Lease a task from the queue, with a heartbeat so two machines never take the
   same one.
2. Create an isolated git worktree for that task alone.
3. Assemble a context package: constitution, agent profile, task, retrieved
   memory, relevant files. Not the whole company history.
4. Invoke the assigned model through a provider adapter.
5. Record tokens, cost, tool calls, and files touched.
6. Run tests, capture evidence, commit, open a draft pull request.
7. Hand the task to a *different* agent for independent review.
8. Post the result to the human attention queue.

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
