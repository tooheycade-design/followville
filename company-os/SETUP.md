# Company OS setup and operation

Development Supabase project: `followville-company-os-dev`, ref
`yutscolndfhscxfoavdp`. This is **not** the live town project
(`followville`, ref `bposhxtidoyulallvhdp`). Never run these against that one.

## Status

| Step | State |
| --- | --- |
| Dev project created | Done |
| Migrations 0001-0008 applied | Done |
| Dashboard credentials in `.env.local` | Done |
| Owner accounts and membership | Done, both owners active |
| Shared-database loop verified live | Done |
| Worker runtime verified live | Done |
| Independent review verified live | Done |
| **Real model execution** | **Blocked on one owner step, below** |

## The one step still needed: sign the CLI in

The worker can run a real Claude model on Cade's existing subscription, but
the CLI has its own sign-in and authentication is not something an agent
should perform. Run this once, in a terminal:

```
"C:\Users\cadet\AppData\Roaming\Claude\claude-code\2.1.219\claude.exe" auth login
```

Confirm it worked:

```
pnpm --dir apps/company-dashboard worker -- --check
```

It currently reports `not_authenticated`; after signing in it reports `ready`.
Until then the worker falls back to the deterministic executor, which is real
but calls no model.

## Running the company

Start the dashboard:

```
pnpm --dir apps/company-dashboard dev
```

Then open `http://localhost:4100`. The header shows which backend is live and
that the budget is zero.

Run a worker. Do this on each owner's machine; leasing keeps them from
colliding:

```
pnpm --dir apps/company-dashboard worker              # one pass, then exit
pnpm --dir apps/company-dashboard worker -- --watch   # keep polling
pnpm --dir apps/company-dashboard worker -- --check   # readiness only
pnpm --dir apps/company-dashboard worker -- --deterministic  # no model
```

The worker leases queued tasks, runs them in a disposable git worktree,
reviews finished work with a different agent, and leaves results in the
owner approval queue.

## What the machine will and will not do

It will: plan a goal into a task, lease it without colliding with another
machine, run it under policy, refuse work that strays outside its approved
paths, require evidence before accepting success, have a second agent check
the result, and put the outcome in front of an owner.

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

To apply a new one, copy it to the clipboard and paste into the SQL editor at
`https://supabase.com/dashboard/project/yutscolndfhscxfoavdp/sql/new`:

```bash
cat "company-os/db/migrations/NAME.sql" | clip.exe
```

If the editor hangs on a spinner, close the tab and open a fresh one. That is
a dashboard bug, not a database problem.

## Owner membership

Both owners are registered. To add another person later:

```sql
insert into company_ops.organization_members (organization_id, user_id, role)
select '10000000-0000-4000-8000-000000000001', id, 'owner'
  from auth.users where email = 'REPLACE@example.com'
on conflict (organization_id, user_id)
  do update set role = 'owner', active = true;
```

Until a person has an owner row, the database refuses their approval
decisions. That refusal is the system working.

## Next

Scheduled wake-ups so workers run without being started by hand, a GitHub App
so completed work arrives as a draft pull request, and the Followville
specialists described in `docs/ROADMAP.md`.
