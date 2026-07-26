# Company OS setup runbook

Steps only an owner can perform, in order. Everything else is automated.

Development Supabase project: `followville-company-os-dev`, ref
`yutscolndfhscxfoavdp`. This is **not** the live town project
(`followville`, ref `bposhxtidoyulallvhdp`) — never run these against that one.

## Status

| Step | State |
| --- | --- |
| 1. Dev project created | Done |
| 2. Migration 0001 applied and verified | Done |
| 3. Dashboard credentials in `.env.local` | Done |
| 4. Migration 0002 applied | Done, verified |
| 5. Seed applied | Done, verified |
| 6. Owner accounts created | Done |
| 7. Owner membership rows | Done, both owners active |
| 8. Migration 0003 applied | Done |
| 9. Live end-to-end loop verified | Done |

Verified after step 5: `company_os_load()` returns all seven collections; the
`company_ops` schema remains unreachable through PostgREST; and a goal write
correctly fails on `goals_created_by_user_id_fkey` and rolls back completely,
leaving zero rows. That failure is step 6 not being done yet, and it also
demonstrates that partial writes cannot occur.

## Step 4 and 5 — apply the SQL

The SQL editor is at:
`https://supabase.com/dashboard/project/yutscolndfhscxfoavdp/sql/new`

If it hangs on a loading spinner, close the tab and open a fresh one. It is a
dashboard bug, not a database problem.

Copy each file to the clipboard, paste into the editor, press Ctrl+Enter, and
confirm the result says success. Run them in this order.

```bash
cat "C:/Users/cadet/followville_repo/.worktrees/company-os-phase1/company-os/db/migrations/0002_control_plane_api.sql" | clip.exe
```

```bash
cat "C:/Users/cadet/followville_repo/.worktrees/company-os-phase1/company-os/db/seed/0001_company_seed.sql" | clip.exe
```

If Supabase warns about Row Level Security, choose **Run without RLS**. These
objects live in the private `company_ops` schema, which no browser role can
reach; see `db/README.md` for the recorded reasoning.

## Step 6 — create the two owner accounts

Do this yourself. Passwords and account creation stay with the humans who own
them.

1. Open
   `https://supabase.com/dashboard/project/yutscolndfhscxfoavdp/auth/users`.
2. **Add user → Create new user**. Enter Cade's email and a password.
3. Repeat for Zach, or use **Send invitation** so he sets his own password.

## Step 7 — grant owner membership

Until this runs, the `approval_decisions` trigger refuses every decision,
because no account is a registered owner yet. That refusal is the system
working correctly.

Run once per owner in the SQL editor, substituting the real address:

```sql
insert into company_ops.organization_members (organization_id, user_id, role)
select '10000000-0000-4000-8000-000000000001', id, 'owner'
  from auth.users where email = 'REPLACE@example.com'
on conflict (organization_id, user_id)
  do update set role = 'owner', active = true;
```

Confirm both landed:

```sql
select u.email, m.role, m.active
  from company_ops.organization_members m
  join auth.users u on u.id = m.user_id;
```

## After that

Tell Claude the steps are done. Remaining automated work: point the Supabase
adapter at the migration 0002 functions, verify the whole goal-to-approval loop
against the live database, then build the worker runtime.
