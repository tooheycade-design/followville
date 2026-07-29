-- Fixes the owner-selection digest check to hash UTF-8 bytes explicitly.

begin;

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
  if encode(extensions.digest(convert_to(
    packet.id::text || ':' || packet.version::text || ':' ||
    (payload->>'conceptId') || ':' || packet.source_digest,
    'UTF8'
  ), 'sha256'), 'hex') <> payload->>'decisionDigest'
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

revoke all on function public.company_os_select_content_concept(jsonb)
  from public, anon, service_role;
grant execute on function public.company_os_select_content_concept(jsonb)
  to authenticated;

commit;
