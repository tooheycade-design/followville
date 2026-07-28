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
| Real model execution (Claude) | Done, judging |
| Migrations 0011-0021 applied | Done in development; 0017-0021 live-verified with rollback-only transactions |
| Owner revision loop | Done; feedback queues a new revision and reaches the worker |
| Truthful worker run ledger | Done; real attempts, usage, audit, and owner packets share a run ID |
| Runtime-owned test evidence | Done for Company OS, dashboard, and public-town browser changes |
| Reviewer revision loop | Done; failed checks and review feedback automatically requeue |
| Factory dashboard deployment | Done at `https://followville-company-os.vercel.app` |
| Historical packet-less task cleanup | Done; 11 canceled with immutable audit events |
| Draft GitHub PR runtime | Implemented and tested; GitHub App owner setup remains |

## Models

The worker probes every installed CLI, reports each, and uses the first
available one. Both run on an existing subscription rather than paid API
credits.

| Provider | State | Signed in as |
| --- | --- | --- |
| `codex` | Ready | ChatGPT plan |
| `claude-code` | Re-authentication may be required | claude.ai |

When both are signed in, Codex implements and Claude judges. If only one is
available both roles still run, and the log says so plainly rather than
implying an independence that does not exist.

To re-authenticate Claude if that lapses:

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

### Releasing work it held

Held work appears on the **Held** page. Each task shows what you originally
asked for, why it was held, the capabilities requested, the paths it may and
may not touch, its risk level, its acceptance criteria, and its version.

Releasing it authorizes exactly the capabilities you leave ticked. Unticking
one narrows the grant; nothing can widen it, and the database re-checks that
independently of the dashboard. The decision is recorded against the version
you were shown, so a task edited after you read it is refused rather than
released on the strength of a decision about something else.

Every decision writes an append-only authorization row naming the task, the
capabilities granted, the capabilities proposed, and who decided. A release
walks the task through `proposed → planned → approved_for_work → queued` so
the transition trigger checks each step.

Escalation triggers account for directive polarity. A constraint such as "do
not deploy this" does not claim deployment authority, while an affirmative
request to deploy still gets held for an owner. Mixed instructions remain
conservative: a positive production action elsewhere in the same request is
still escalated.

## Owner authentication

Copy `apps/company-dashboard/.env.example` to an ignored `.env.local` and fill
in the development project's keys. `SUPABASE_PUBLISHABLE_KEY` is used only for
the caller's cookie-backed Auth session. `SUPABASE_SECRET_KEY` remains
server-only and powers the private Company OS repository; never expose it
through a `NEXT_PUBLIC_` variable.

The dashboard has no identity picker. Sign in with an existing Supabase Auth
account whose `organization_members` row is active with role `owner`.
Unauthenticated callers are redirected to `/login`, and signed-in non-owners
are sent to `/unauthorized`. The database derives membership from `auth.uid()`;
the browser cannot provide a user ID to impersonate another owner.

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

## Deciding on finished work

Work that passes review and the Chief Executive's gate arrives on the
**Approvals** page as a request citing its evidence: what the worker said, the
files it changed, and any artifacts it produced — screenshots, renders, logs,
and the diff. Each artifact names how to retrieve it, usually
`git show <commit>:<path>` against the task's own review branch.

Nothing has been pushed, merged, or deployed at that point. Rejecting means
deleting a branch nobody depends on. Approving a write task authorizes the
worker to publish that exact checkpoint to its `agent/task-*` branch and open
one private draft PR. It does not authorize a merge or deployment.

Artifacts are recorded by reference into that checkpoint commit rather than
copied into separate storage, so the bytes travel with the branch. The
`location` field is a union, so object storage can be added later without
changing what already exists.

## GitHub draft review

Review publication uses a GitHub App installation token, never a personal
access token. Create an app owned by `tooheycade-design`, install it only on the
private `followville` repository, and grant exactly:

| Permission | Access |
| --- | --- |
| Metadata | Read |
| Contents | Read and write |
| Pull requests | Read and write |

Do not grant Actions, Administration, Deployments, Environments, Issues,
Packages, Secrets, or Webhooks. The app cannot merge through this runtime:
only an exact local `agent/task-*` checkpoint may be pushed, with
force-with-lease protection, and every created pull request has `draft: true`.

Put these values in the worker machine's ignored
`apps/company-dashboard/.env.local`:

```text
COMPANY_OS_GITHUB_OWNER=tooheycade-design
COMPANY_OS_GITHUB_REPOSITORY=followville
COMPANY_OS_GITHUB_APP_ID=...
COMPANY_OS_GITHUB_INSTALLATION_ID=...
COMPANY_OS_GITHUB_PRIVATE_KEY_BASE64=...
```

Encode the downloaded PEM without printing it:

```powershell
[Convert]::ToBase64String(
  [IO.File]::ReadAllBytes("C:\path\to\the-downloaded-private-key.pem")
)
```

Once all three credentials are present, each worker polling cycle scans for
approved `pull_request_create` packets. It re-verifies the owner decision,
scope digest, checkpoint, reviewer verdict, CEO verdict, local branch, and
remote branch lease before requesting credentials. A successful or reconciled
draft PR is written to the immutable audit ledger and linked from the Factory
page. A retry finds the existing marker instead of opening a duplicate.

## What the machine will and will not do

It will: interpret your intent, plan bounded tasks, lease work without
colliding with another machine, run it under policy in a disposable worktree,
refuse work that strays outside its approved paths, require evidence before
accepting success, have a second agent check the result, and put the outcome in
front of you.

It will publish an owner-approved checkpoint to a private review branch and
draft PR. It will not merge, deploy, publish public content, spend, or touch
the canonical town files. Those remain separate owner decisions, enforced
independently of the application.

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
| 0011 | `git_checkpoint`, separating a local commit from a publication step |
| 0012 | Owner release of held work, with an append-only authorization record |
| 0013 | Evidence artifacts, and finished work reaching the approval queue |
| 0014 | Separate accepting reviewed work from merge/deploy authorization |
| 0015 | Pin append-only trigger helper search paths |
| 0016 | Resolve the signed-in caller's active Company OS membership |
| 0017 | Preserve owner feedback and atomically queue a new revision |
| 0018 | Link real worker attempts, usage, audit, and completion to durable runs |
| 0019 | Reject contradictory run states and retain unknown-model usage |
| 0020 | Atomically requeue reviewer-requested revisions |
| 0021 | Stop automatic revision loops after three review cycles |

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

Run `db/verify/0011_0014.sql` after applying the migration set. Every row must
report `pass`. Do not run any of these files against the live town project.

## Next

Create and install the narrowly scoped GitHub App, add its credentials to each
worker machine, then run one fresh write task through CEO, worker, review,
owner approval, branch publication, and draft PR reconciliation. Restore
Claude authentication for genuinely independent model review.

The trusted verification registry now runs fixed commands selected from changed
paths. Company OS code gets strict TypeScript and the core suite; dashboard code
gets strict TypeScript, tests, and a production build; public-town web changes
get the Playwright suite; every change gets `git diff --check`. Unknown code
areas fail closed until a maintainer adds a repository-owned verifier.

See `VERIFIED_CURRENT_STATE.md` for the evidence-based handoff.
