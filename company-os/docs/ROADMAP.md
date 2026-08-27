# Staged Roadmap

## Phase 0: Architecture and Deterministic Foundation

Objective: agree on authority, contracts, state, and the first safe workflow.

Deliverables:

- PRD, constitution, architecture, data model, security plan, decisions;
- strict domain schemas;
- policy and budget checks;
- task transition and loop guards;
- deterministic goal-to-approval simulation;
- proposed database migration and seed profiles;
- tests and CI-ready commands.

Exit: Cade or Zach approves, rejects, or requests changes. No deployment.

## Phase 1: Owner Dashboard and Persistent Control Plane

Objective: owner creates a goal and observes deterministic workflow state.

- Separate private Next.js app.
- Owner-only Supabase Auth and organization membership.
- Apply reviewed migration to a development project only.
- Goal, task, agent, event, memory, audit, cost, and attention views.
- Server-side command handlers using the Phase 0 policy package.
- Simulation mode as the only execution mode.
- Responsive and accessible operational UI.

Exit: staging demo reconstructs every action from the audit trail.

## Phase 2: One Real Worker, Independent Review

Objective: safely prepare a code change in an isolated test repository.

- GitHub App with metadata/read first, then scoped branch/PR writes.
- Ephemeral worktree/container lease.
- One full-stack worker adapter.
- One separate QA reviewer.
- Patch, tests, screenshots, cost, and review evidence.
- Draft PR only; no merge.

Exit: owner can approve or reject a complete draft PR package.

## Phase 3: Durable Events and Scheduling

Objective: survive restarts and support bounded background work.

- Inngest pilot with event inbox/outbox and idempotent steps.
- Approval waits, retry/failure handlers, concurrency and rate limits.
- Daily reporter, stale-task checker, cost auditor.
- Signed GitHub webhook processing.

Exit: interrupted workflows resume without duplicate side effects.

## Phase 4: Provider and Specialist Expansion

- OpenAI and Anthropic adapters behind one usage contract.
- Model catalog and routing evaluation.
- Architect, Blender, game systems, security, design, and social-draft roles.
- Better context retrieval and memory maintenance.
- Evaluation datasets and per-role performance evidence.

No specialist receives production access by default.

## Phase 5: Followville Operations Integrations

- Read-only product analytics.
- Growth and content planning.
- Moderation attention queue.
- Custom-home intake and asset workflow.
- Owner-approved release automation.

Payments, publishing, canonical town growth, and public moderation actions each
receive dedicated policies and approvals.

## Future Scale

- Worker pools and stronger spatial/file ownership.
- Temporal evaluation if workflows outgrow serverless duration/complexity.
- Dedicated secrets and evidence infrastructure.
- Multi-project organizations.
- Disaster recovery and regional resilience.
- Formal privacy impact and moderation reviews.

## First Useful Feature

The smallest safe feature is the local goal-to-approval simulator implemented
in Phase 0. It proves the hard part: a task cannot spend, use a capability,
approve itself, or cross into production merely because a model requests it.

It deliberately does not pretend to run an AI team. Real providers arrive only
after the deterministic controls pass owner review.
