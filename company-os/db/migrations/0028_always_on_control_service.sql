-- Always-on, authority-free control service.
--
-- Postgres schedules small idempotent housekeeping ticks. Heavy/model work
-- remains on registered workers. This service can reclaim dead leases, expire
-- messages, measure queue compatibility, and create in-app owner reminders;
-- it cannot execute tasks or approve, merge, deploy, publish, spend, or grow.

begin;

create extension if not exists pg_cron;

create table company_ops.control_ticks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null
    references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  tick_type text not null check (tick_type in ('queue_health', 'daily_report')),
  time_bucket timestamptz not null,
  metrics jsonb not null check (
    jsonb_typeof(metrics) = 'object'
    and pg_column_size(metrics) <= 16384
  ),
  created_at timestamptz not null default clock_timestamp(),
  unique (organization_id, project_id, tick_type, time_bucket),
  foreign key (organization_id, project_id)
    references company_ops.projects(organization_id, id) on delete restrict
);

create index control_ticks_recent_idx
  on company_ops.control_ticks (
    organization_id, project_id, tick_type, created_at desc
  );

create table company_ops.owner_notifications (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null
    references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  notification_type text not null check (
    notification_type in (
      'approval_reminder', 'held_work_reminder', 'queue_unavailable',
      'worker_unavailable'
    )
  ),
  target_type text not null check (
    target_type in ('approval_request', 'task', 'project', 'worker')
  ),
  target_id text not null check (length(target_id) between 1 and 200),
  title text not null check (length(title) between 1 and 180),
  detail text not null check (length(detail) between 1 and 2000),
  severity text not null check (severity in ('info', 'warning', 'urgent')),
  delivery_day date not null,
  status text not null default 'pending'
    check (status in ('pending', 'read', 'resolved', 'expired')),
  created_at timestamptz not null default clock_timestamp(),
  updated_at timestamptz not null default clock_timestamp(),
  unique (
    organization_id, project_id, notification_type,
    target_type, target_id, delivery_day
  ),
  foreign key (organization_id, project_id)
    references company_ops.projects(organization_id, id) on delete restrict
);

create index owner_notifications_pending_idx
  on company_ops.owner_notifications (
    organization_id, project_id, severity, created_at desc
  ) where status = 'pending';

create or replace function company_ops.run_control_tick(p_tick_type text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_org uuid := '10000000-0000-4000-8000-000000000001';
  v_project uuid := '20000000-0000-4000-8000-000000000001';
  v_bucket timestamptz;
  v_reclaimed jsonb := '[]'::jsonb;
  v_expired_messages integer := 0;
  v_online_workers integer := 0;
  v_stale_workers integer := 0;
  v_queued_tasks integer := 0;
  v_incompatible_tasks integer := 0;
  v_pending_approvals integer := 0;
  v_held_tasks integer := 0;
  v_metrics jsonb;
begin
  if p_tick_type not in ('queue_health', 'daily_report') then
    raise exception 'unsupported control tick type';
  end if;

  if not pg_try_advisory_xact_lock(hashtextextended(
    'company-os-control:' || p_tick_type, 0
  )) then
    return jsonb_build_object('outcome', 'already_running');
  end if;

  v_bucket := case p_tick_type
    when 'queue_health' then
      date_trunc('hour', clock_timestamp())
        + floor(extract(minute from clock_timestamp()) / 5)
          * interval '5 minutes'
    else date_trunc('day', clock_timestamp())
  end;

  if exists (
    select 1 from company_ops.control_ticks tick
     where tick.organization_id = v_org
       and tick.project_id = v_project
       and tick.tick_type = p_tick_type
       and tick.time_bucket = v_bucket
  ) then
    return jsonb_build_object('outcome', 'already_recorded');
  end if;

  if p_tick_type = 'queue_health' then
    v_reclaimed := public.company_os_reclaim_expired_leases();

    update company_ops.messages message
       set status = 'expired'
     where message.organization_id = v_org
       and message.project_id = v_project
       and message.status in ('created', 'delivered', 'read')
       and message.expires_at <= clock_timestamp();
    get diagnostics v_expired_messages = row_count;
  end if;

  select count(*) filter (
           where worker.status = 'online'
             and worker.last_seen_at >= clock_timestamp() - interval '90 seconds'
         ),
         count(*) filter (
           where worker.status <> 'online'
              or worker.last_seen_at < clock_timestamp() - interval '90 seconds'
         )
    into v_online_workers, v_stale_workers
    from company_ops.worker_nodes worker
   where worker.organization_id = v_org
     and worker.project_id = v_project;

  select count(*),
         count(*) filter (where not exists (
           select 1
             from company_ops.worker_nodes worker
            where worker.organization_id = task.organization_id
              and worker.project_id = task.project_id
              and worker.agent_id = task.assigned_agent_id
              and worker.status = 'online'
              and worker.last_seen_at >= clock_timestamp() - interval '90 seconds'
              and task.allowed_capabilities <@ worker.capabilities
         ))
    into v_queued_tasks, v_incompatible_tasks
    from company_ops.tasks task
   where task.organization_id = v_org
     and task.project_id = v_project
     and task.status = 'queued';

  select count(*)
    into v_pending_approvals
    from company_ops.approval_requests request
    join company_ops.approval_request_states state
      on state.approval_request_id = request.id
   where request.organization_id = v_org
     and request.project_id = v_project
     and state.status = 'pending';

  select count(*) into v_held_tasks
    from company_ops.tasks task
   where task.organization_id = v_org
     and task.project_id = v_project
     and task.status = 'proposed';

  if p_tick_type = 'daily_report' then
    insert into company_ops.owner_notifications (
      organization_id, project_id, notification_type, target_type, target_id,
      title, detail, severity, delivery_day
    )
    select
      request.organization_id, request.project_id, 'approval_reminder',
      'approval_request', request.id::text, 'Owner decision waiting',
      request.summary,
      case when request.risk_level in ('high', 'critical')
        then 'urgent' else 'warning' end,
      current_date
    from company_ops.approval_requests request
    join company_ops.approval_request_states state
      on state.approval_request_id = request.id
   where request.organization_id = v_org
     and request.project_id = v_project
     and state.status = 'pending'
     and request.created_at < clock_timestamp() - interval '12 hours'
    on conflict do nothing;

    insert into company_ops.owner_notifications (
      organization_id, project_id, notification_type, target_type, target_id,
      title, detail, severity, delivery_day
    )
    select
      task.organization_id, task.project_id, 'held_work_reminder',
      'task', task.id::text, 'Held work needs an owner',
      task.title, 'warning', current_date
    from company_ops.tasks task
   where task.organization_id = v_org
     and task.project_id = v_project
     and task.status = 'proposed'
     and task.created_at < clock_timestamp() - interval '12 hours'
    on conflict do nothing;
  end if;

  if v_incompatible_tasks > 0 then
    insert into company_ops.owner_notifications (
      organization_id, project_id, notification_type, target_type, target_id,
      title, detail, severity, delivery_day
    ) values (
      v_org, v_project, 'queue_unavailable', 'project', v_project::text,
      'Queued work has no compatible worker',
      v_incompatible_tasks || ' queued task(s) have no fresh worker with the required agent and capabilities.',
      'urgent', current_date
    ) on conflict do nothing;
  end if;

  v_metrics := jsonb_build_object(
    'reclaimedLeaseCount', jsonb_array_length(v_reclaimed),
    'expiredMessageCount', v_expired_messages,
    'onlineWorkers', v_online_workers,
    'unavailableWorkers', v_stale_workers,
    'queuedTasks', v_queued_tasks,
    'incompatibleTasks', v_incompatible_tasks,
    'pendingApprovals', v_pending_approvals,
    'heldTasks', v_held_tasks
  );

  insert into company_ops.control_ticks (
    organization_id, project_id, tick_type, time_bucket, metrics
  ) values (v_org, v_project, p_tick_type, v_bucket, v_metrics);

  return jsonb_build_object('outcome', 'recorded', 'metrics', v_metrics);
end;
$$;

create or replace function public.company_os_run_control_tick(tick_type text)
returns jsonb
language sql
security definer
set search_path = ''
as $$
  select company_ops.run_control_tick(tick_type);
$$;

create or replace function public.company_os_load()
returns jsonb
language sql
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'goals', coalesce((select jsonb_agg(to_jsonb(g) order by g.created_at)
      from company_ops.goals g), '[]'::jsonb),
    'tasks', coalesce((select jsonb_agg(to_jsonb(t) order by t.created_at)
      from company_ops.tasks t), '[]'::jsonb),
    'runs', coalesce((select jsonb_agg(to_jsonb(r) order by r.created_at)
      from company_ops.runs r), '[]'::jsonb),
    'messages', coalesce((select jsonb_agg(to_jsonb(m) order by m.created_at)
      from company_ops.messages m), '[]'::jsonb),
    'approval_requests', coalesce((select jsonb_agg(to_jsonb(a) order by a.created_at)
      from company_ops.approval_requests a), '[]'::jsonb),
    'approval_states', coalesce((select jsonb_agg(to_jsonb(s))
      from company_ops.approval_request_states s), '[]'::jsonb),
    'approval_decisions', coalesce((select jsonb_agg(to_jsonb(d) order by d.decided_at)
      from company_ops.approval_decisions d), '[]'::jsonb),
    'evidence_artifacts', coalesce((select jsonb_agg(to_jsonb(e) order by e.created_at)
      from company_ops.evidence_artifacts e), '[]'::jsonb),
    'worker_nodes', coalesce((select jsonb_agg(to_jsonb(w) order by w.started_at)
      from company_ops.worker_nodes w), '[]'::jsonb),
    'control_ticks', coalesce((select jsonb_agg(to_jsonb(c) order by c.created_at)
      from (
        select * from company_ops.control_ticks
        order by created_at desc limit 500
      ) c), '[]'::jsonb),
    'owner_notifications', coalesce((select jsonb_agg(to_jsonb(n) order by n.created_at)
      from (
        select * from company_ops.owner_notifications
        order by created_at desc limit 500
      ) n), '[]'::jsonb),
    'audit_events', coalesce((select jsonb_agg(to_jsonb(e) order by e.sequence)
      from company_ops.audit_events e), '[]'::jsonb)
  );
$$;

select cron.schedule(
  'followville-company-os-queue-health',
  '*/5 * * * *',
  $cron$select company_ops.run_control_tick('queue_health');$cron$
);

select cron.schedule(
  'followville-company-os-daily-report',
  '17 12 * * *',
  $cron$select company_ops.run_control_tick('daily_report');$cron$
);

select cron.schedule(
  'followville-company-os-control-retention',
  '43 12 * * *',
  $cron$
    delete from company_ops.control_ticks
      where created_at < clock_timestamp() - interval '90 days';
    update company_ops.owner_notifications
       set status = 'expired', updated_at = clock_timestamp()
     where status = 'pending'
       and created_at < clock_timestamp() - interval '30 days';
  $cron$
);

revoke all on company_ops.control_ticks
  from public, anon, authenticated, service_role;
revoke all on company_ops.owner_notifications
  from public, anon, authenticated, service_role;
revoke all on function company_ops.run_control_tick(text)
  from public, anon, authenticated, service_role;
revoke all on function public.company_os_run_control_tick(text)
  from public, anon, authenticated;
revoke all on function public.company_os_load()
  from public, anon, authenticated;
grant execute on function public.company_os_run_control_tick(text)
  to service_role;
grant execute on function public.company_os_load()
  to service_role;

commit;
