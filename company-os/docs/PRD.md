# Product Requirements: Followville Company OS

Status: Proposed for owner review
Version: 0.1.0
Owners: Cade and Zach
Last updated: 2026-07-26

## Product in One Paragraph

Followville Company OS is a private operations workspace where Cade and Zach
create high-level goals and a controlled set of AI agents plans, executes,
reviews, and reports the work. It is not a group chat and it is not an
autonomous production bot. Durable tasks, messages, evidence, budgets,
permissions, model usage, Git activity, reviews, and human decisions are stored
outside model context. Agents work in scoped sandboxes and review branches.
Only Cade or Zach can authorize production-affecting outcomes.

## Confirmed Current State

- Followville is a persistent town where one follower represents one resident
  and one home.
- The canonical world is controlled by `world_state.json`, the guarded Blender
  workflow, generated GLBs, and Git.
- The public product is a static Vercel site with a Three.js town, Supabase
  accounts/claims/customization, multiplayer presence, chat, and an admin page.
- Cade and Zach already coordinate multiple coding agents through Git history,
  `AGENTS.md`, `CLAUDE.md`, handoff files, and team logs.
- Production growth has strong preflight protections, but agent work is not
  represented as structured goals, tasks, runs, approvals, budgets, or audits.
- Existing consumer AI subscriptions are not equivalent to API credentials.

Evidence: repository files and commit history on 2026-07-26.

## Gap Analysis

| Capability | Today | Required |
| --- | --- | --- |
| Shared memory | Markdown and Git | Typed, versioned, attributable memory |
| Work assignment | Human messages | Goals, initiatives, tasks, dependencies |
| Agent identity | Chat/session identity | Persistent profile and prompt version |
| Permissions | Tool/session defaults | Per-agent capabilities and path scopes |
| Isolation | Varies by coding tool | One branch/worktree or sandbox per task |
| Review | Human and ad hoc AI review | Independent reviewer plus evidence |
| Approval | Conversation | Durable owner approval queue |
| Cost | Provider UI/manual | Per-call, run, task, agent, project budgets |
| Scheduling | Manual | Durable events and bounded schedules |
| Audit | Git plus logs | Append-only business and tool event trail |
| Loop control | Human intervention | Counters, fingerprints, pause thresholds |
| Provider routing | Chosen manually | Policy-driven, replaceable adapters |
| Executive view | Handoff documents | Focused owner attention queue and report |

## Users

### Owners

Cade and Zach create goals, set policy, inspect evidence, approve decisions,
and retain final authority. Either owner may pause the system. Company-policy
changes, production releases, monetization, public communication, and
irreversible actions always require an owner.

### AI Workers

AI workers are capable but unreliable contractors. They receive a defined
objective, relevant context, an explicit capability set, a budget, a workspace,
acceptance criteria, and a reviewer. They cannot widen their own authority.

### Reviewers

Reviewers independently inspect requirements, diffs, test results, visual
evidence, security impact, and budget. A worker cannot approve its own task.

## Core Workflow

1. An owner creates a goal.
2. A manager proposes tasks, dependencies, budgets, and acceptance criteria.
3. Policy checks determine whether planning or work requires owner approval.
4. A dispatcher assigns an approved task to an eligible available agent.
5. The agent receives a minimal context package and isolated workspace.
6. Every run and tool request is validated against capabilities and budget.
7. The agent submits output with evidence and a concise reasoning summary.
8. A different reviewer runs independent checks.
9. Passed work enters the owner attention queue.
10. An owner approves, rejects, requests changes, pauses, or cancels.
11. A separately authorized release workflow may merge or deploy.

## MVP Requirements

### Required

- Owner-only authenticated dashboard.
- Goal intake with risk, budget, and repository scope.
- Structured manager plan and task graph.
- Persistent agent profiles and prompt versions.
- Typed messages, tasks, runs, approvals, memory, and audit events.
- Capability-based policy checks before every side effect.
- Dry-run mode for all high-risk actions.
- Per-run and per-task budget reservation before model calls.
- Append-only usage and audit ledgers.
- Isolated Git branch/worktree assignment.
- Independent review before owner approval.
- Human attention queue.
- Owner decision records with actor, time, rationale, and evidence.
- Idempotent event processing and bounded retries.
- Clear implemented/planned/blocked labels throughout the UI.

### Non-Goals for MVP

- Unattended production merging or deployment.
- Instagram publishing.
- Payments or pricing changes.
- Direct production database migrations.
- Arbitrary access to Cade's or Zach's computers.
- A large cast of conversational personas.
- Automatic use of consumer chat subscriptions.
- Semantic/vector memory before structured retrieval proves insufficient.
- Supporting hundreds of simultaneous agent workers.

## Acceptance Criteria

The MVP is acceptable when a seeded local scenario and a staging environment
can demonstrate:

1. An owner goal becomes a task graph with measurable acceptance criteria.
2. A task cannot start without an eligible agent and sufficient budget.
3. A forbidden capability is denied and audited.
4. A production-affecting action becomes an approval request, not an action.
5. A separate reviewer can pass or reject submitted evidence.
6. A task cannot reach `approved` without an owner decision.
7. Duplicate events and duplicate approvals are idempotent.
8. A run pauses after retry or loop thresholds.
9. Usage totals reconcile from immutable ledger entries.
10. The dashboard can reconstruct who did what and why without chain of thought.

## Product Metrics

### Reliability

- Task completion and review-pass rates.
- Retry, loop-pause, regression, revert, and incident rates.
- Median time from goal creation to owner-ready result.

### Cost

- Cost per accepted task and per approved initiative.
- Budget denial and budget-overrun counts.
- Cached-token and low-cost routing utilization.

### Owner Leverage

- Owner attention items per completed task.
- Minutes of owner review per accepted deliverable.
- Percentage of reports requiring no clarification.

### Followville Outcomes

The Company OS may ingest follower growth, bio clicks, registrations, claims,
active players, retention, moderation, and revenue metrics later. Those product
metrics inform work; they do not grant agents production authority.

## Open Owner Decisions

- Whether this private system uses the existing Supabase project or a separate
  project with a stricter blast radius.
- Whether both owners can individually approve all actions or selected actions
  require two-owner approval.
- Initial monthly API budget, default proposed as USD 0 until credentials are
  intentionally connected.
- Whether the Phase 1 durable workflow pilot uses Inngest Cloud or a local-only
  worker first.
- Which repository and directory scopes the first coding worker may modify.
