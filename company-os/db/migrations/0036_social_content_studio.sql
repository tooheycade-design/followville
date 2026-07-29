-- Adds a source-backed, owner-selected social-content workflow.
-- It deliberately provides no publishing function or publisher credential.

begin;

insert into company_ops.agent_profiles (
  id, organization_id, slug, name, role, profile, prompt_version, capabilities
) values (
  '40000000-0000-4000-8000-000000000008',
  '10000000-0000-4000-8000-000000000001',
  'content-strategist',
  'Content Strategist',
  'Social content planning',
  '{"draftOnly":true,"engagementClaimsRequireEvidence":true,"finalAuthority":"owners"}'::jsonb,
  'content-strategist-v1',
  array['repository_read', 'memory_write', 'message_send']::company_ops.capability[]
)
on conflict (id) do update set
  slug = excluded.slug,
  name = excluded.name,
  role = excluded.role,
  profile = excluded.profile,
  prompt_version = excluded.prompt_version,
  capabilities = excluded.capabilities,
  active = true;

create table company_ops.content_packets (
  id uuid primary key,
  organization_id uuid not null,
  project_id uuid not null,
  created_by_user_id uuid not null references auth.users(id) on delete restrict,
  created_by_agent_id uuid not null,
  status text not null check (status in (
    'draft', 'concept_selected', 'production_in_progress', 'ready_for_owner',
    'approved', 'rejected', 'published'
  )),
  objective text not null check (length(objective) between 1 and 1000),
  recommendation text not null check (length(recommendation) between 1 and 1000),
  milestone jsonb not null check (jsonb_typeof(milestone) = 'object'),
  source_snapshot_ids uuid[] not null check (cardinality(source_snapshot_ids) between 1 and 12),
  source_digest text not null check (source_digest ~ '^[0-9a-f]{64}$'),
  engagement_data_status text not null check (
    engagement_data_status in ('available', 'setup_required', 'stale')
  ),
  data_gaps jsonb not null check (jsonb_typeof(data_gaps) = 'array'),
  prior_content_notes jsonb not null check (jsonb_typeof(prior_content_notes) = 'array'),
  concepts jsonb not null check (
    jsonb_typeof(concepts) = 'array' and jsonb_array_length(concepts) = 3
  ),
  selected_concept_id uuid,
  production_goal_id uuid references company_ops.goals(id) on delete restrict,
  production_task_id uuid references company_ops.tasks(id) on delete restrict,
  publish_approval_request_id uuid references company_ops.approval_requests(id) on delete restrict,
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null,
  updated_at timestamptz not null,
  unique (organization_id, project_id, id),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, created_by_agent_id)
    references company_ops.agent_profiles (organization_id, id) on delete restrict,
  check (
    status <> 'draft' or (
      selected_concept_id is null and production_goal_id is null
      and production_task_id is null and publish_approval_request_id is null
    )
  )
);

create table company_ops.content_concept_decisions (
  id bigint generated always as identity primary key,
  packet_id uuid not null references company_ops.content_packets(id) on delete restrict,
  selected_concept_id uuid not null,
  selected_concept_digest text not null check (selected_concept_digest ~ '^[0-9a-f]{64}$'),
  decided_by_user_id uuid not null references auth.users(id) on delete restrict,
  packet_version integer not null check (packet_version > 0),
  created_at timestamptz not null default now(),
  unique (packet_id, packet_version)
);

alter table company_ops.content_packets enable row level security;
alter table company_ops.content_concept_decisions enable row level security;

create or replace function company_ops.reject_content_decision_mutation()
returns trigger language plpgsql set search_path = '' as $$
begin
  raise exception 'content concept decisions are append-only';
end;
$$;

create trigger content_decisions_append_only
before update or delete on company_ops.content_concept_decisions
for each row execute function company_ops.reject_content_decision_mutation();

revoke all on company_ops.content_packets from public, anon, authenticated, service_role;
revoke all on company_ops.content_concept_decisions from public, anon, authenticated, service_role;

create or replace function public.company_os_record_content_packet(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  written company_ops.content_packets%rowtype;
begin
  if payload->>'status' <> 'draft'
    or (payload->>'createdByAgentId')::uuid <> '40000000-0000-4000-8000-000000000008'
    or jsonb_array_length(payload->'concepts') <> 3
    or payload->>'sourceDigest' !~ '^[0-9a-f]{64}$'
    or not exists (
      select 1 from company_ops.organization_members member
      where member.organization_id = (payload->>'organizationId')::uuid
        and member.user_id = (payload->>'createdByUserId')::uuid
        and member.role = 'owner' and member.active
    )
  then
    raise exception 'invalid content packet';
  end if;

  insert into company_ops.content_packets (
    id, organization_id, project_id, created_by_user_id, created_by_agent_id,
    status, objective, recommendation, milestone, source_snapshot_ids,
    source_digest, engagement_data_status, data_gaps, prior_content_notes,
    concepts, selected_concept_id, production_goal_id, production_task_id,
    publish_approval_request_id, version, created_at, updated_at
  ) values (
    (payload->>'id')::uuid, (payload->>'organizationId')::uuid,
    (payload->>'projectId')::uuid, (payload->>'createdByUserId')::uuid,
    (payload->>'createdByAgentId')::uuid, payload->>'status',
    payload->>'objective', payload->>'recommendation', payload->'milestone',
    array(select jsonb_array_elements_text(payload->'sourceSnapshotIds'))::uuid[],
    payload->>'sourceDigest', payload->>'engagementDataStatus',
    payload->'dataGaps', payload->'priorContentNotes', payload->'concepts',
    null, null, null, null, (payload->>'version')::integer,
    (payload->>'createdAt')::timestamptz, (payload->>'updatedAt')::timestamptz
  ) returning * into written;
  return to_jsonb(written);
end;
$$;

create or replace function public.company_os_load_content()
returns jsonb
language sql
security definer
set search_path = ''
stable
as $$
  select jsonb_build_object(
    'content_packets',
    coalesce((
      select jsonb_agg(to_jsonb(packet) order by packet.created_at desc)
      from (
        select * from company_ops.content_packets
        order by created_at desc limit 100
      ) packet
    ), '[]'::jsonb)
  );
$$;

create or replace function public.company_os_select_content_concept(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  owner_id uuid := auth.uid();
  packet company_ops.content_packets%rowtype;
  chosen jsonb;
  goal_payload jsonb := payload->'goal';
  task_payload jsonb := payload->'task';
  expected_caps company_ops.capability[] := array[
    'repository_read', 'repository_write', 'git_checkpoint', 'test_execute',
    'blender_preview', 'message_send'
  ]::company_ops.capability[];
  supplied_caps company_ops.capability[];
begin
  if owner_id is null then raise exception 'authentication required'; end if;
  select * into packet from company_ops.content_packets
    where id = (payload->>'packetId')::uuid for update;
  if not found then raise exception 'content packet not found'; end if;
  if not exists (
    select 1 from company_ops.organization_members member
    where member.organization_id = packet.organization_id
      and member.user_id = owner_id and member.role = 'owner' and member.active
  ) then raise exception 'active owner required'; end if;
  if packet.status <> 'draft' or packet.version <> (payload->>'expectedVersion')::integer
  then raise exception 'stale content packet'; end if;

  select value into chosen from jsonb_array_elements(packet.concepts)
    where value->>'id' = payload->>'conceptId';
  if chosen is null then raise exception 'concept does not belong to packet'; end if;
  if encode(digest(
    packet.id::text || ':' || packet.version::text || ':' ||
    (payload->>'conceptId') || ':' || packet.source_digest,
    'sha256'
  ), 'hex') <> payload->>'decisionDigest'
  then raise exception 'concept digest mismatch'; end if;

  supplied_caps := array(
    select value::company_ops.capability
    from jsonb_array_elements_text(task_payload->'allowedCapabilities') value
  );
  if supplied_caps <> expected_caps
    or task_payload->>'assignedAgentId' <> '40000000-0000-4000-8000-000000000002'
    or task_payload->>'reviewerAgentId' <> '40000000-0000-4000-8000-000000000003'
    or task_payload->>'status' <> 'queued'
    or (task_payload->>'approvalRequired')::boolean is not true
    or task_payload->'repositoryScopes'->0->'allowedPathPrefixes'
       <> '["company-os/content","company-os/candidates/cinematic"]'::jsonb
    or goal_payload->>'createdByUserId' <> owner_id::text
    or goal_payload->>'id' <> task_payload->>'goalId'
  then raise exception 'unsafe content production task'; end if;

  perform public.company_os_record_initiative(
    jsonb_build_object('goal', goal_payload, 'tasks', jsonb_build_array(task_payload))
  );
  update company_ops.content_packets set
    status = 'production_in_progress',
    selected_concept_id = (payload->>'conceptId')::uuid,
    production_goal_id = (goal_payload->>'id')::uuid,
    production_task_id = (task_payload->>'id')::uuid,
    version = version + 1,
    updated_at = now()
  where id = packet.id;
  insert into company_ops.content_concept_decisions (
    packet_id, selected_concept_id, selected_concept_digest,
    decided_by_user_id, packet_version
  ) values (
    packet.id, (payload->>'conceptId')::uuid, payload->>'decisionDigest',
    owner_id, packet.version
  );
  return jsonb_build_object(
    'packetId', packet.id, 'goalId', goal_payload->>'id',
    'taskId', task_payload->>'id'
  );
end;
$$;

revoke all on function public.company_os_record_content_packet(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_record_content_packet(jsonb)
  to service_role;
revoke all on function public.company_os_load_content()
  from public, anon, authenticated;
grant execute on function public.company_os_load_content()
  to service_role;
revoke all on function public.company_os_select_content_concept(jsonb)
  from public, anon, service_role;
grant execute on function public.company_os_select_content_concept(jsonb)
  to authenticated;

commit;
