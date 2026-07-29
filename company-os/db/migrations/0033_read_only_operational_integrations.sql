-- Read-only product observations. External data informs work but grants no authority.

begin;

create table company_ops.integration_sources (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  source_key text not null check (source_key ~ '^[a-z][a-z0-9_]{2,63}$'),
  display_name text not null check (length(display_name) between 1 and 160),
  source_type text not null check (source_type in (
    'public_town', 'website', 'instagram', 'analytics',
    'application_database', 'payments', 'moderation'
  )),
  access_mode text not null check (access_mode in (
    'public_read', 'configured_read_only', 'setup_required'
  )),
  status text not null check (status in (
    'active', 'setup_required', 'degraded', 'error', 'disabled'
  )),
  setup_requirement text,
  configuration jsonb not null default '{}'::jsonb check (
    jsonb_typeof(configuration) = 'object'
    and pg_column_size(configuration) <= 8192
  ),
  last_checked_at timestamptz,
  last_success_at timestamptz,
  last_error_code text,
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  unique (organization_id, project_id, source_key),
  unique (organization_id, id),
  foreign key (organization_id, project_id)
    references company_ops.projects(organization_id, id) on delete restrict
);

create table company_ops.operational_snapshots (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null,
  project_id uuid not null,
  source_id uuid not null,
  captured_at timestamptz not null,
  metrics jsonb not null check (
    jsonb_typeof(metrics) = 'object'
    and pg_column_size(metrics) <= 32768
  ),
  evidence_reference text not null check (
    length(evidence_reference) between 1 and 2000
  ),
  source_digest text not null check (source_digest ~ '^[0-9a-f]{64}$'),
  idempotency_key text not null check (
    length(idempotency_key) between 16 and 200
  ),
  confidence text not null check (
    confidence in ('confirmed', 'likely', 'uncertain', 'requires_human_verification')
  ),
  freshness_until timestamptz not null,
  created_by_type company_ops.actor_type not null,
  created_by_id uuid not null,
  created_at timestamptz not null default clock_timestamp(),
  unique (organization_id, idempotency_key),
  foreign key (organization_id, project_id)
    references company_ops.projects(organization_id, id) on delete restrict,
  foreign key (organization_id, source_id)
    references company_ops.integration_sources(organization_id, id) on delete restrict,
  check (freshness_until > captured_at)
);

create index integration_sources_status_idx
  on company_ops.integration_sources (
    organization_id, project_id, status, source_type
  );

create index operational_snapshots_latest_idx
  on company_ops.operational_snapshots (
    organization_id, project_id, source_id, captured_at desc
  );

create function company_ops.reject_operational_snapshot_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'operational snapshots are append-only';
end;
$$;

create trigger operational_snapshots_reject_update
before update on company_ops.operational_snapshots
for each statement execute function company_ops.reject_operational_snapshot_mutation();

create trigger operational_snapshots_reject_delete
before delete on company_ops.operational_snapshots
for each statement execute function company_ops.reject_operational_snapshot_mutation();

create trigger operational_snapshots_reject_truncate
before truncate on company_ops.operational_snapshots
for each statement execute function company_ops.reject_operational_snapshot_mutation();

with target_projects as (
  select project.organization_id, project.id as project_id
    from company_ops.projects project
   where lower(project.name) like '%followville%'
      or lower(project.slug) like '%followville%'
), sources (
  source_key, display_name, source_type, access_mode, status,
  setup_requirement, configuration
) as (
  values
  (
    'public_town_state', 'Public town state', 'public_town',
    'public_read', 'active', null,
    '{"endpoint":"https://followville-kappa.vercel.app/world_state.json","refreshMinutes":15}'::jsonb
  ),
  (
    'public_website_health', 'Public website health', 'website',
    'public_read', 'active', null,
    '{"endpoint":"https://followville-kappa.vercel.app/","refreshMinutes":15}'::jsonb
  ),
  (
    'instagram_metrics', 'Instagram metrics', 'instagram',
    'setup_required', 'setup_required',
    'Official Meta API access and a read-only token are not configured.',
    '{"provider":"meta_graph_api"}'::jsonb
  ),
  (
    'website_analytics', 'Website analytics', 'analytics',
    'setup_required', 'setup_required',
    'A read-only Vercel Analytics export or approved analytics provider is not configured.',
    '{"provider":"vercel_analytics"}'::jsonb
  ),
  (
    'application_database', 'Followville application data', 'application_database',
    'setup_required', 'setup_required',
    'A dedicated read-only production database integration is not configured.',
    '{"provider":"supabase"}'::jsonb
  ),
  (
    'payment_summaries', 'Payment summaries', 'payments',
    'setup_required', 'setup_required',
    'No payment provider or read-only reporting integration has been selected.',
    '{}'::jsonb
  ),
  (
    'moderation_reports', 'Moderation reports', 'moderation',
    'setup_required', 'setup_required',
    'The moderation reporting system has not been built.',
    '{}'::jsonb
  )
)
insert into company_ops.integration_sources (
  organization_id, project_id, source_key, display_name, source_type,
  access_mode, status, setup_requirement, configuration
)
select
  target.organization_id, target.project_id, source.source_key,
  source.display_name, source.source_type, source.access_mode, source.status,
  source.setup_requirement, source.configuration
from target_projects target
cross join sources source
on conflict (organization_id, project_id, source_key) do nothing;

create function public.company_os_record_operational_snapshot(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_source company_ops.integration_sources%rowtype;
  v_snapshot company_ops.operational_snapshots%rowtype;
  v_metrics jsonb := payload->'metrics';
  v_captured_at timestamptz := coalesce(
    nullif(payload->>'capturedAt', '')::timestamptz,
    clock_timestamp()
  );
  v_freshness_minutes integer := coalesce(
    nullif(payload->>'freshnessMinutes', '')::integer,
    30
  );
begin
  select source.* into v_source
    from company_ops.integration_sources source
   where source.source_key = payload->>'sourceKey'
     and source.status in ('active', 'degraded', 'error')
   order by source.created_at
   limit 1
   for update;
  if not found then
    raise exception 'active operational source does not exist';
  end if;
  if jsonb_typeof(v_metrics) <> 'object'
     or pg_column_size(v_metrics) > 32768 then
    raise exception 'operational metrics must be a bounded object';
  end if;
  if (payload->>'sourceDigest') !~ '^[0-9a-f]{64}$' then
    raise exception 'operational source digest must be lowercase SHA-256';
  end if;
  if v_freshness_minutes not between 1 and 10080 then
    raise exception 'operational freshness must be between one minute and seven days';
  end if;

  insert into company_ops.operational_snapshots (
    organization_id, project_id, source_id, captured_at, metrics,
    evidence_reference, source_digest, idempotency_key, confidence, freshness_until,
    created_by_type, created_by_id
  ) values (
    v_source.organization_id, v_source.project_id, v_source.id, v_captured_at,
    v_metrics, payload->>'evidenceReference', payload->>'sourceDigest',
    payload->>'idempotencyKey',
    coalesce(nullif(payload->>'confidence', ''), 'confirmed'),
    v_captured_at + make_interval(mins => v_freshness_minutes),
    'system', coalesce(
      nullif(payload->>'createdById', '')::uuid,
      '00000000-0000-4000-8000-000000000033'::uuid
    )
  )
  on conflict (organization_id, idempotency_key) do nothing
  returning * into v_snapshot;

  if v_snapshot.id is null then
    select snapshot.* into v_snapshot
      from company_ops.operational_snapshots snapshot
     where snapshot.organization_id = v_source.organization_id
       and snapshot.idempotency_key = payload->>'idempotencyKey';
  end if;

  update company_ops.integration_sources
     set status = 'active',
         last_checked_at = clock_timestamp(),
         last_success_at = clock_timestamp(),
         last_error_code = null,
         updated_at = clock_timestamp()
   where id = v_source.id;

  return to_jsonb(v_snapshot);
end;
$$;

create function public.company_os_record_operational_failure(
  p_source_key text,
  p_error_code text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_source company_ops.integration_sources%rowtype;
begin
  if p_error_code !~ '^[a-z][a-z0-9_]{2,79}$' then
    raise exception 'operational error code is invalid';
  end if;
  update company_ops.integration_sources
     set status = 'error',
         last_checked_at = clock_timestamp(),
         last_error_code = p_error_code,
         updated_at = clock_timestamp()
   where source_key = p_source_key
     and status <> 'setup_required'
  returning * into v_source;
  if not found then
    raise exception 'operational source does not exist or requires setup';
  end if;
  return to_jsonb(v_source);
end;
$$;

create function public.company_os_load_operations()
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
    ), '[]'::jsonb)
  );
$$;

revoke all on company_ops.integration_sources from public, anon, authenticated, service_role;
revoke all on company_ops.operational_snapshots from public, anon, authenticated, service_role;
revoke all on function company_ops.reject_operational_snapshot_mutation()
  from public, anon, authenticated, service_role;
revoke all on function public.company_os_record_operational_snapshot(jsonb)
  from public, anon, authenticated;
revoke all on function public.company_os_record_operational_failure(text, text)
  from public, anon, authenticated;
revoke all on function public.company_os_load_operations()
  from public, anon, authenticated;

grant execute on function public.company_os_record_operational_snapshot(jsonb)
  to service_role;
grant execute on function public.company_os_record_operational_failure(text, text)
  to service_role;
grant execute on function public.company_os_load_operations()
  to service_role;

commit;
