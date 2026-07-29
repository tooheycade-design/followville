# Database

## Applied environments

| Environment | Supabase project | Migration 0001 | Applied |
| --- | --- | --- | --- |
| Development | `followville-company-os-dev` (ref `yutscolndfhscxfoavdp`) | Applied | 2026-07-26, by Cade's explicit approval |
| Staging | none | Not applied | — |
| Production | none | Not applied | — |

The live public town project (`followville`, ref `bposhxtidoyulallvhdp`) is a
separate Supabase project and was **not** touched. It holds `houses`, `claims`,
`profiles`, and the rest of the public game data. Never apply Company OS
migrations there.

Migrations are immutable once applied. Corrections ship as a new numbered
migration, never as an edit to an applied file.

## Applied verification (development, 2026-07-26)

Run inside the development project's SQL editor immediately after applying
`0001_company_os_foundation.sql`:

| Check | Result |
| --- | --- |
| Tables and views in `company_ops` | 15 tables, 1 view |
| Triggers | 8 |
| Functions | 3 |
| Table grants to `anon`, `authenticated`, or `public` | 0 |
| `has_schema_privilege('anon','company_ops','USAGE')` | `false` |

The development project was additionally created with **Automatically expose
new tables** disabled.

Migrations through `0037_harden_social_content_history.sql` are applied in
development as of 2026-07-29. The content tables have RLS enabled and no direct
client grants; live verification confirmed owner-only concept selection,
blocked anonymous access, blocked direct reads, and no social publisher.

## Connecting the dashboard (owner steps)

1. In the development project, open **Project Settings → API** and copy the
   project URL, the publishable key, and the secret key.
2. Create `company-os/.env.local` (gitignored) from `.env.example` and paste
   them in. Never commit real values.
3. Run `db/seed/0001_company_seed.sql` in that project's SQL editor. It creates
   the organization, project, and five agent profiles using the same fixed
   identifiers the application uses.
4. Have Cade and Zach each create an account in the development project, then
   run the owner-membership statement recorded at the bottom of the seed file
   once per owner.

Until step 4 is complete, the `approval_decisions` trigger refuses every
decision, because no account is yet a registered owner. That refusal is the
system working, not a bug.

The dashboard picks its backend from the environment: with `SUPABASE_URL` and
`SUPABASE_SECRET_KEY` present it uses the database, otherwise it falls back to
the local JSON store. The active backend is displayed in the dashboard header
so the difference is never silent.

## Security posture

The tables live in the private `company_ops` schema, not `public`. Browser
roles receive no schema or table privileges, and default privileges are revoked
so future tables inherit the same posture. `company_ops` is not in the Data
API's exposed-schema list, so PostgREST cannot see it.

Row Level Security is intentionally **not** enabled on these tables. RLS governs
access for roles that can already reach a table; here `anon` and `authenticated`
cannot reach the schema at all, and the server-side control plane connects with
a secret credential that bypasses RLS regardless. Supabase's SQL editor shows a
generic RLS warning for any table created outside its default pattern; that
warning was reviewed and does not apply to this schema. Revisit this decision if
any `company_ops` table is ever exposed through the Data API.

## Before applying a migration to any new environment

1. Ratify the constitution and owner roles.
2. Review the migration against a disposable project or branch first.
3. Add integration tests for every server endpoint that touches it.
4. Confirm backup and rollback procedures.
5. Obtain explicit approval from Cade or Zach.
