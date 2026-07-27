# Company OS setup and operation

Development Supabase project: `followville-company-os-dev`, ref
`yutscolndfhscxfoavdp`. This is **not** the live town project
(`followville`, ref `bposhxtidoyulallvhdp`). Never run these against that one.

## Status

| Step | State |
| --- | --- |
| Dev project created | Done |
| Migrations 0001-0010 applied | Done |
| Dashboard credentials in `.env.local` | Done |
| Owner accounts and membership | Done, both owners active |
| Shared-database loop verified live | Done |
| Worker runtime verified live | Done |
| Independent review verified live | Done |
| Chief Executive verified live | Done |
| Scheduled wake-ups verified live | Done |
| Real model execution (Codex) | Done, running |
| Real model execution (Claude) | Optional, one owner step below |

## Models

The worker probes every installed CLI, reports each, and uses the first
available one. Both run on an existing subscription rather than paid API
credits.

| Provider | State | Signed in as |
| --- | --- | --- |
| `codex` | Ready | ChatGPT plan |
| `claude-code` | Not signed in | — |

To add Claude alongside Codex, run once in a terminal:

```
"C:\Users\cadet\AppData\Roaming\Claude\claude-code\2.1.219\claude.exe" auth login
```

Authentication is deliberately not something an agent performs. Confirm with:

```
pnpm --dir apps/company-dashboard worker -- --check
```

If no provider is signed in, the worker falls back to a deterministic executor
that calls no model and spends nothing, rather than failing.

### How a model run is bounded

- It runs inside a disposable git worktree, never the operator's checkout.
- It is started in the narrowest directory containing its allowed paths, so it
  does not scan the Blender scenes and exported geometry it cannot touch. On
  this repository that is the difference between 43 MB and a few hundred KB,
  and between a run that times out and one that finishes.
- Codex adds its own `workspace-write` sandbox inside that worktree. The
  dangerous bypass flag is never used.
- Every file the agent touched is re-checked against the policy engine
  afterwards. Editing `world_state.json`, or writing `../` out of scope, fails
  the task before it reaches review.
- A failed attempt leaves its worktree behind; the next attempt clears it
  rather than failing on the debris.

## Directing the company

Open the **CEO** page in the dashboard and say what you want in plain language.
The Chief Executive turns it into bounded tasks and queues them for the
workers.

It decides what should happen, never what an agent is allowed to do. Whatever
it proposes, capabilities are intersected with a fixed grantable set, so a plan
asking for `production_deploy` or `payment_charge` simply does not get it and
the refusal is shown to you.

It holds anything that is your call rather than deciding it: monetization and
pricing, releasing to production, anything public, brand and identity,
destructive changes, and the canonical town. Those arrive as proposed work
waiting for you, with the reason named.

## Running the company

Start the dashboard:

```
pnpm --dir apps/company-dashboard dev
```

Then open `http://localhost:4100`. The header shows which backend is live and
what the ledger has metered.

That figure is **metered API spend**, and it is currently zero because both
providers run on existing subscriptions this ledger does not measure. It does
not mean the work is free. Read it as "no incremental API charges", not "no
cost" — a cost ledger that quietly counts subscription work as $0 gives a
comfortable and wrong picture the moment either provider is used heavily.

Run a worker. Do this on each owner's machine; leasing keeps them from
colliding:

```
pnpm --dir apps/company-dashboard worker              # one pass, then exit
pnpm --dir apps/company-dashboard worker -- --watch   # scheduled, keeps running
pnpm --dir apps/company-dashboard worker -- --check   # readiness only
pnpm --dir apps/company-dashboard worker -- --deterministic  # no model
```

In `--watch` mode the scheduler runs the queue every two minutes, reclaims
stalled leases every five, and produces a daily report and cost audit. Schedule
state is kept on disk, so restarting does not replay every daily job.

Scheduling is interval-based rather than cron on purpose. These machines sleep,
and a wall-clock cron would silently skip everything due while a laptop was
closed. A machine coming back online notices it is overdue and catches up once.

## What the machine will and will not do

It will: interpret your intent, plan bounded tasks, lease work without
colliding with another machine, run it under policy in a disposable worktree,
refuse work that strays outside its approved paths, require evidence before
accepting success, have a second agent check the result, and put the outcome in
front of you.

It will not: merge, deploy, publish, spend, or touch the canonical town files.
Those need an owner decision, and the database enforces that independently of
the application.

## Migrations

Applied in order. They are immutable once applied; corrections ship as a new
numbered migration.

| File | Purpose |
| --- | --- |
| 0001 | Private `company_ops` schema, approval and audit integrity |
| 0002 | Transactional control-plane API in `public` |
| 0003 | Grant the audit-append function to `service_role` |
| 0004 | Task leasing for multi-machine workers |
| 0005 | Record a planned goal as queued work |
| 0006 | Review leasing |
| 0007 | Fix an ambiguous parameter in 0006 |
| 0008 | Permit review bookkeeping on a reviewed task |
| 0009 | Register the Chief Executive agent |
| 0010 | Record a CEO initiative atomically |

To apply a new one, copy it to the clipboard and paste into the SQL editor at
`https://supabase.com/dashboard/project/yutscolndfhscxfoavdp/sql/new`:

```bash
cat "company-os/db/migrations/NAME.sql" | clip.exe
```

If the editor hangs on a spinner, close the tab and open a fresh one. That is a
dashboard bug, not a database problem.

## Owner membership

Both owners are registered. To add another person later:

```sql
insert into company_ops.organization_members (organization_id, user_id, role)
select '10000000-0000-4000-8000-000000000001', id, 'owner'
  from auth.users where email = 'REPLACE@example.com'
on conflict (organization_id, user_id)
  do update set role = 'owner', active = true;
```

Until a person has an owner row, the database refuses their approval decisions.
That refusal is the system working.

## Next

A GitHub App so completed work arrives as a draft pull request, a model-backed
planner behind the same CEO clamping, and the Followville specialists described
in `docs/ROADMAP.md`.
