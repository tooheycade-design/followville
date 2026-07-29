\set ON_ERROR_STOP on

begin;

do $$
declare
  v_org uuid;
  v_project uuid;
  v_actor uuid := '00000000-0000-4000-8000-000000000030';
  v_first uuid := '30000000-0000-4000-8000-000000000001';
  v_second uuid := '30000000-0000-4000-8000-000000000002';
  v_payload jsonb;
begin
  select id into v_org from company_ops.organizations order by created_at limit 1;
  select id into v_project
    from company_ops.projects
   where organization_id = v_org
   order by created_at
   limit 1;

  if v_org is null or v_project is null then
    raise exception 'verification needs the seeded organization and project';
  end if;

  insert into company_ops.memories (
    id, organization_id, project_id, memory_type, category, subject, body,
    source_type, source_reference, source_digest, confidence, status, version,
    tags, audience_roles, created_by_type, created_by_id
  ) values (
    v_first, v_org, v_project, 'project', 'current_state',
    'verification fact', 'version one', 'test', 'verify/0030',
    repeat('a', 64), 'confirmed', 'active', 1,
    array['verification'], array['owner', 'engineer'], 'system', v_actor
  );

  begin
    insert into company_ops.memories (
      id, organization_id, project_id, memory_type, category, subject, body,
      source_type, source_reference, source_digest, confidence, status, version,
      tags, audience_roles, created_by_type, created_by_id
    ) values (
      v_second, v_org, v_project, 'project', 'current_state',
      'VERIFICATION FACT', 'contradiction', 'test', 'verify/0030',
      repeat('b', 64), 'confirmed', 'active', 1,
      array['verification'], array['owner'], 'system', v_actor
    );
    raise exception 'active contradiction was accepted';
  exception
    when unique_violation then null;
  end;

  select public.company_os_retrieve_memories(
    'engineer', 'unrelated query', array['verification'], 100
  ) into v_payload;

  if jsonb_array_length(v_payload) > 25
     or v_payload->0->>'subject' <> 'verification fact'
     or not v_payload @> jsonb_build_array(jsonb_build_object('id', v_first)) then
    raise exception 'bounded role retrieval returned the wrong records: %', v_payload;
  end if;

  if public.company_os_retrieve_memories(
    'finance', null, array['verification'], 25
  ) @> jsonb_build_array(jsonb_build_object('id', v_first)) then
    raise exception 'role retrieval disclosed a memory to the wrong audience';
  end if;

  begin
    update company_ops.memories set body = 'rewritten' where id = v_first;
    raise exception 'in-place memory rewrite was accepted';
  exception
    when raise_exception then
      if sqlerrm = 'in-place memory rewrite was accepted' then
        raise;
      end if;
  end;

  begin
    delete from company_ops.memories where id = v_first;
    raise exception 'memory deletion was accepted';
  exception
    when raise_exception then
      if sqlerrm = 'memory deletion was accepted' then
        raise;
      end if;
  end;
end;
$$;

rollback;

select '0030 structured memory verification passed' as result;
