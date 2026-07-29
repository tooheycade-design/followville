-- Synthetic product health and diagnostic alerts. Alerts carry no authority.

begin;

with target_projects as (
  select project.organization_id, project.id as project_id
    from company_ops.projects project
   where lower(project.name) like '%followville%'
      or lower(project.slug) like '%followville%'
)
insert into company_ops.integration_sources (
  organization_id, project_id, source_key, display_name, source_type,
  access_mode, status, setup_requirement, configuration
)
select
  target.organization_id, target.project_id,
  'browser_product_health', 'Browser product health', 'website',
  'configured_read_only', 'active', null,
  '{"endpoint":"https://followville-kappa.vercel.app/","refreshMinutes":60,"journeys":["homepage","town-walk"]}'::jsonb
from target_projects target
on conflict (organization_id, project_id, source_key) do nothing;

create table company_ops.operational_alerts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  snapshot_id uuid not null,
  alert_kind text not null check (alert_kind in (
    'availability', 'browser_errors', 'request_failures', 'performance'
  )),
  severity text not null check (severity in ('info', 'warning', 'urgent')),
  title text not null check (length(title) between 1 and 200),
  detail text not null check (length(detail) between 1 and 4000),
  recommended_action text not null check (
    length(recommended_action) between 1 and 2000
  ),
  status text not null default 'open' check (
    status in ('open', 'diagnostic_requested', 'resolved', 'expired')
  ),
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  unique (snapshot_id, alert_kind),
  unique (organization_id, id),
  foreign key (organization_id, project_id)
    references company_ops.projects(organization_id, id) on delete restrict,
  foreign key (organization_id, source_id)
    references company_ops.integration_sources(organization_id, id) on delete restrict,
  foreign key (snapshot_id)
    references company_ops.operational_snapshots(id) on delete restrict
);

create index operational_alerts_open_idx
  on company_ops.operational_alerts (
    organization_id, project_id, status, severity, created_at desc
  );

create function company_ops.evaluate_product_health_snapshot()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_source_key text;
  v_home_status integer;
  v_town_status integer;
  v_client_errors integer;
  v_failed_requests integer;
  v_home_dcl integer;
  v_town_ready integer;
begin
  select source.source_key into v_source_key
    from company_ops.integration_sources source
   where source.id = new.source_id;
  if v_source_key <> 'browser_product_health' then
    return new;
  end if;

  v_home_status := coalesce((new.metrics->>'homeStatusCode')::integer, 0);
  v_town_status := coalesce((new.metrics->>'townStatusCode')::integer, 0);
  v_client_errors := coalesce((new.metrics->>'clientErrorCount')::integer, 0);
  v_failed_requests := coalesce((new.metrics->>'failedRequestCount')::integer, 0);
  v_home_dcl := coalesce((new.metrics->>'homeDomContentLoadedMs')::integer, 0);
  v_town_ready := coalesce((new.metrics->>'townReadyMs')::integer, 0);

  if v_home_status <> 200 or v_town_status <> 200
     or coalesce((new.metrics->>'homeReachable')::boolean, false) = false
     or coalesce((new.metrics->>'townReachable')::boolean, false) = false then
    insert into company_ops.operational_alerts (
      organization_id, project_id, source_id, snapshot_id, alert_kind,
      severity, title, detail, recommended_action
    ) values (
      new.organization_id, new.project_id, new.source_id, new.id,
      'availability', 'urgent', 'Public journey is unavailable',
      format(
        'Homepage HTTP %s; town HTTP %s; homepage reachable %s; town reachable %s.',
        v_home_status, v_town_status, new.metrics->>'homeReachable',
        new.metrics->>'townReachable'
      ),
      'Create a read-only diagnostic task to inspect deployment state, routing, and recent runtime errors. Production remediation still requires its own approval.'
    ) on conflict do nothing;
  end if;

  if v_client_errors > 0 then
    insert into company_ops.operational_alerts (
      organization_id, project_id, source_id, snapshot_id, alert_kind,
      severity, title, detail, recommended_action
    ) values (
      new.organization_id, new.project_id, new.source_id, new.id,
      'browser_errors', 'warning', 'Client errors detected',
      format('The synthetic homepage and town journey recorded %s console or page error(s).', v_client_errors),
      'Create a diagnostic task to reproduce the errors with browser traces and identify the responsible commit. Do not deploy automatically.'
    ) on conflict do nothing;
  end if;

  if v_failed_requests > 0 then
    insert into company_ops.operational_alerts (
      organization_id, project_id, source_id, snapshot_id, alert_kind,
      severity, title, detail, recommended_action
    ) values (
      new.organization_id, new.project_id, new.source_id, new.id,
      'request_failures', 'warning', 'Browser requests failed',
      format('The synthetic journey recorded %s failed HTTP or network request(s).', v_failed_requests),
      'Create a diagnostic task to classify failed requests, confirm whether any are intentional cancellations, and attach network evidence.'
    ) on conflict do nothing;
  end if;

  if v_home_dcl > 4000 or v_town_ready > 30000 then
    insert into company_ops.operational_alerts (
      organization_id, project_id, source_id, snapshot_id, alert_kind,
      severity, title, detail, recommended_action
    ) values (
      new.organization_id, new.project_id, new.source_id, new.id,
      'performance', 'warning', 'Public journey is slower than its threshold',
      format(
        'Homepage DOM content loaded in %s ms (threshold 4000); town became ready in %s ms (threshold 30000).',
        v_home_dcl, v_town_ready
      ),
      'Create a performance diagnostic task to compare asset, network, and rendering timings before proposing a scoped optimization.'
    ) on conflict do nothing;
  end if;
  return new;
end;
$$;

create trigger operational_snapshots_evaluate_product_health
after insert on company_ops.operational_snapshots
for each row execute function company_ops.evaluate_product_health_snapshot();

create or replace function public.company_os_load_operations()
returns jsonb
language sql
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'sources', coalesce((
      select jsonb_agg(to_jsonb(source) order by source.display_name)
        from company_ops.integration_sources source
    ), '[]'::jsonb),
    'snapshots', coalesce((
      select jsonb_agg(to_jsonb(snapshot) order by snapshot.captured_at desc)
        from (
          select *
            from company_ops.operational_snapshots
           order by captured_at desc
           limit 500
        ) snapshot
    ), '[]'::jsonb),
    'alerts', coalesce((
      select jsonb_agg(to_jsonb(alert) order by alert.created_at desc)
        from (
          select *
            from company_ops.operational_alerts
           order by created_at desc
           limit 200
        ) alert
    ), '[]'::jsonb)
  );
$$;

revoke all on company_ops.operational_alerts
  from public, anon, authenticated, service_role;
revoke all on function company_ops.evaluate_product_health_snapshot()
  from public, anon, authenticated, service_role;
revoke all on function public.company_os_load_operations()
  from public, anon, authenticated;
grant execute on function public.company_os_load_operations() to service_role;

commit;
