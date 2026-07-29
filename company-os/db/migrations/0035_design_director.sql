-- Registers the read-only Design Director used for pixel-backed review.

begin;

insert into company_ops.agent_profiles (
  id, organization_id, slug, name, role, profile, prompt_version, capabilities
) values (
  '40000000-0000-4000-8000-000000000007',
  '10000000-0000-4000-8000-000000000001',
  'design-director',
  'Design Director',
  'Independent visual review',
  '{"evidenceRequired":true,"finalAuthority":"owners"}'::jsonb,
  'design-director-v1',
  array['repository_read', 'message_send']::company_ops.capability[]
)
on conflict (id) do update set
  slug = excluded.slug,
  name = excluded.name,
  role = excluded.role,
  profile = excluded.profile,
  prompt_version = excluded.prompt_version,
  capabilities = excluded.capabilities,
  active = true;

commit;
