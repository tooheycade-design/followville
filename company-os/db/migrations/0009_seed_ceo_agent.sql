-- Registers the Chief Executive agent.
--
-- The CEO interprets owner intent and sets priority. It holds no write, no
-- production, and no publishing capability, because deciding what should
-- happen is a different job from being allowed to do it.
--
-- Idempotent, so it is safe to re-run.

begin;

insert into company_ops.agent_profiles
  (id, organization_id, slug, name, role, profile, prompt_version)
values (
  '40000000-0000-4000-8000-000000000006',
  '10000000-0000-4000-8000-000000000001',
  'chief-executive',
  'Chief Executive',
  'Interpretation and prioritization',
  '{}'::jsonb,
  'chief-executive-v1'
)
on conflict (id) do nothing;

commit;
