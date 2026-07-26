-- Seed for a DEVELOPMENT Company OS database only.
-- Safe to re-run: every statement is idempotent.
--
-- The identifiers below intentionally match src/config/seed-agents.ts so the
-- application and the database agree on organization, project, and agent IDs.

begin;

insert into company_ops.organizations (id, slug, name, constitution_version)
values (
  '10000000-0000-4000-8000-000000000001',
  'followville',
  'Followville',
  'proposed-v0.1.0'
)
on conflict (id) do nothing;

insert into company_ops.projects (id, organization_id, slug, name, repository)
values (
  '20000000-0000-4000-8000-000000000001',
  '10000000-0000-4000-8000-000000000001',
  'followville-town',
  'Followville Town',
  'followville_repo'
)
on conflict (id) do nothing;

insert into company_ops.agent_profiles
  (id, organization_id, slug, name, role, profile, prompt_version)
values
  ('40000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001',
   'company-manager', 'Company Manager', 'Planning and coordination',
   '{}'::jsonb, 'company-manager-v1'),
  ('40000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000001',
   'full-stack-engineer', 'Full-Stack Engineer', 'Implementation',
   '{}'::jsonb, 'full-stack-engineer-v1'),
  ('40000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000001',
   'qa-reviewer', 'QA Reviewer', 'Independent review',
   '{}'::jsonb, 'qa-reviewer-v1'),
  ('40000000-0000-4000-8000-000000000004', '10000000-0000-4000-8000-000000000001',
   'cost-auditor', 'Cost Auditor', 'Budget oversight',
   '{}'::jsonb, 'cost-auditor-v1'),
  ('40000000-0000-4000-8000-000000000005', '10000000-0000-4000-8000-000000000001',
   'executive-reporter', 'Executive Reporter', 'Human-readable reporting',
   '{}'::jsonb, 'executive-reporter-v1')
on conflict (id) do nothing;

commit;

-- Owner membership cannot be seeded with fixed identifiers because
-- organization_members.user_id references auth.users. After Cade and Zach each
-- create an account in this development project, run the statement below once
-- per owner, substituting the real email address:
--
--   insert into company_ops.organization_members (organization_id, user_id, role)
--   select '10000000-0000-4000-8000-000000000001', id, 'owner'
--     from auth.users where email = 'owner@example.com'
--   on conflict (organization_id, user_id) do update set role = 'owner', active = true;
--
-- Until at least one owner row exists, the database trigger on
-- approval_decisions refuses every decision. That refusal is correct: it means
-- an unregistered account cannot approve anything.
