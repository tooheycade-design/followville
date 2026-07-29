\set ON_ERROR_STOP on

begin;

do $$
declare
  v_first jsonb;
  v_second jsonb;
  v_source_id uuid;
begin
  if not exists (
    select 1
      from company_ops.memories
     where category = 'current_state'
       and status = 'active'
       and version = 2
       and body like 'Followville is at Day 27%'
  ) then
    raise exception 'Day 27 memory correction is not active';
  end if;

  if (
    select count(*)
      from company_ops.integration_sources
  ) <> 7 then
    raise exception 'expected seven declared operational sources';
  end if;

  if (
    select count(*)
      from company_ops.integration_sources
     where status = 'setup_required'
  ) <> 5 then
    raise exception 'unconfigured integrations must remain setup_required';
  end if;

  select id into v_source_id
    from company_ops.integration_sources
   where source_key = 'public_town_state';

  v_first := public.company_os_record_operational_snapshot(jsonb_build_object(
    'sourceKey', 'public_town_state',
    'capturedAt', '2026-07-29T18:00:00.000Z',
    'metrics', jsonb_build_object(
      'day', 27, 'population', 500, 'buildingCount', 560, 'seedCounter', 561
    ),
    'evidenceReference', 'verify/0032_0033',
    'sourceDigest', repeat('d', 64),
    'idempotencyKey', 'verify:public-town:2026-07-29T18:00Z',
    'confidence', 'confirmed',
    'freshnessMinutes', 30
  ));
  v_second := public.company_os_record_operational_snapshot(jsonb_build_object(
    'sourceKey', 'public_town_state',
    'capturedAt', '2026-07-29T18:00:00.000Z',
    'metrics', jsonb_build_object(
      'day', 27, 'population', 500, 'buildingCount', 560, 'seedCounter', 561
    ),
    'evidenceReference', 'verify/0032_0033',
    'sourceDigest', repeat('d', 64),
    'idempotencyKey', 'verify:public-town:2026-07-29T18:00Z',
    'confidence', 'confirmed',
    'freshnessMinutes', 30
  ));

  if v_first->>'id' is distinct from v_second->>'id' then
    raise exception 'operational snapshot retry was not idempotent';
  end if;

  begin
    update company_ops.operational_snapshots
       set metrics = '{}'::jsonb
     where id = (v_first->>'id')::uuid;
    raise exception 'snapshot mutation was accepted';
  exception
    when raise_exception then
      if sqlerrm = 'snapshot mutation was accepted' then
        raise;
      end if;
  end;

  if v_source_id is null then
    raise exception 'public town source is missing';
  end if;
end;
$$;

rollback;

select '0032-0033 operational integration verification passed' as result;
