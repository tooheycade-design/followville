\set ON_ERROR_STOP on

begin;

do $$
declare
  v_tasks_before bigint;
  v_approvals_before bigint;
  v_healthy jsonb;
  v_unhealthy jsonb;
begin
  if not exists (
    select 1
      from company_ops.integration_sources
     where source_key = 'browser_product_health'
       and access_mode = 'configured_read_only'
       and status = 'active'
  ) then
    raise exception 'browser product health source is not active';
  end if;

  select count(*) into v_tasks_before from company_ops.tasks;
  select count(*) into v_approvals_before from company_ops.approval_requests;

  v_healthy := public.company_os_record_operational_snapshot(jsonb_build_object(
    'sourceKey', 'browser_product_health',
    'metrics', jsonb_build_object(
      'homeReachable', true, 'homeStatusCode', 200,
      'homeDomContentLoadedMs', 800, 'homeLoadMs', 1000,
      'townReachable', true, 'townStatusCode', 200, 'townReadyMs', 5000,
      'clientErrorCount', 0, 'failedRequestCount', 0,
      'apiRequestCount', 2, 'apiAverageMs', 100, 'apiFailureCount', 0
    ),
    'evidenceReference', 'verify/0034/healthy',
    'sourceDigest', repeat('a', 64),
    'idempotencyKey', 'verify:product-health:healthy:0034',
    'confidence', 'confirmed',
    'freshnessMinutes', 120
  ));

  if exists (
    select 1 from company_ops.operational_alerts
     where snapshot_id = (v_healthy->>'id')::uuid
  ) then
    raise exception 'healthy product snapshot created an alert';
  end if;

  v_unhealthy := public.company_os_record_operational_snapshot(jsonb_build_object(
    'sourceKey', 'browser_product_health',
    'metrics', jsonb_build_object(
      'homeReachable', false, 'homeStatusCode', 503,
      'homeDomContentLoadedMs', 5000, 'homeLoadMs', 6000,
      'townReachable', false, 'townStatusCode', 500, 'townReadyMs', 31000,
      'clientErrorCount', 2, 'failedRequestCount', 3,
      'apiRequestCount', 2, 'apiAverageMs', 900, 'apiFailureCount', 2
    ),
    'evidenceReference', 'verify/0034/unhealthy',
    'sourceDigest', repeat('b', 64),
    'idempotencyKey', 'verify:product-health:unhealthy:0034',
    'confidence', 'confirmed',
    'freshnessMinutes', 120
  ));

  if (
    select count(*)
      from company_ops.operational_alerts
     where snapshot_id = (v_unhealthy->>'id')::uuid
  ) <> 4 then
    raise exception 'unhealthy product snapshot did not create four alerts';
  end if;

  if (select count(*) from company_ops.tasks) <> v_tasks_before
     or (select count(*) from company_ops.approval_requests) <> v_approvals_before then
    raise exception 'alert evaluation changed task or approval authority';
  end if;

  if jsonb_array_length(
    public.company_os_load_operations()->'alerts'
  ) < 4 then
    raise exception 'operations read model does not expose alerts';
  end if;
end;
$$;

rollback;

select '0034 product observability verification passed' as result;
