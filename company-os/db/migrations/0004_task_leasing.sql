-- Task leasing for the worker runtime.
--
-- Cade's PC and Zach's Mac run workers against the same queue. A lease is what
-- stops both from picking up the same task: claiming uses SELECT ... FOR UPDATE
-- SKIP LOCKED, so concurrent workers step over each other's rows instead of
-- blocking or colliding.
--
-- Leases expire. A worker whose machine sleeps, crashes, or loses its network
-- stops sending heartbeats, and the task becomes claimable again rather than
-- being stranded forever. Reclaiming an expired lease is recorded, because a
-- task silently changing hands is the kind of thing an owner needs to see.

begin;

alter table company_ops.tasks
  add column if not exists lease_worker_id text,
  add column if not exists lease_expires_at timestamptz,
  add column if not exists lease_heartbeat_at timestamptz,
  add column if not exists lease_epoch integer not null default 0;

create index if not exists tasks_claimable_idx
  on company_ops.tasks (status, priority desc, created_at)
  where status = 'queued';

-- The task update trigger treats any non-status column change on a reviewed
-- task as tampering. Lease bookkeeping is not part of a reviewed task's scope,
-- so exclude those columns from that comparison.
create or replace function company_ops.validate_task_update()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  transition_allowed boolean;
  ignored text[] := array[
    'status', 'updated_at', 'version', 'actual_cost_usd_micros',
    'lease_worker_id', 'lease_expires_at', 'lease_heartbeat_at', 'lease_epoch'
  ];
begin
  if old.status in (
    'awaiting_review', 'awaiting_human_approval', 'approved', 'merged',
    'deployed', 'rejected', 'canceled'
  ) and (to_jsonb(new) - ignored) is distinct from (to_jsonb(old) - ignored) then
    raise exception 'reviewed task scope is immutable';
  end if;

  if new.status = old.status then
    return new;
  end if;

  transition_allowed := case old.status
    when 'proposed' then new.status in ('planned', 'canceled', 'rejected')
    when 'planned' then new.status in ('approved_for_work', 'canceled', 'rejected')
    when 'approved_for_work' then new.status in ('queued', 'canceled')
    when 'queued' then new.status in ('assigned', 'blocked', 'canceled', 'failed')
    when 'assigned' then new.status in ('in_progress', 'blocked', 'canceled', 'failed', 'queued')
    when 'in_progress' then new.status in ('blocked', 'awaiting_review', 'canceled', 'failed', 'queued')
    when 'blocked' then new.status in ('in_progress', 'canceled', 'failed')
    when 'awaiting_review' then new.status in ('changes_requested', 'awaiting_human_approval', 'failed')
    when 'changes_requested' then new.status in ('in_progress', 'canceled', 'failed')
    when 'awaiting_human_approval' then new.status in ('approved', 'rejected', 'changes_requested', 'canceled')
    when 'approved' then new.status in ('merged', 'canceled')
    when 'failed' then new.status in ('queued', 'canceled')
    when 'merged' then new.status = 'deployed'
    else false
  end;

  if not transition_allowed then
    raise exception 'invalid task transition: % -> %', old.status, new.status;
  end if;
  if new.status in ('approved', 'merged') and not exists (
    select 1
      from company_ops.approval_requests request
      join company_ops.approval_request_states state
        on state.approval_request_id = request.id
      where request.organization_id = new.organization_id
        and request.project_id = new.project_id
        and request.task_id = new.id
        and request.action = 'production_merge'
        and state.status = 'approved'
  ) then
    raise exception 'task does not have a current approved merge request';
  end if;
  if new.status = 'deployed' and not exists (
    select 1
      from company_ops.approval_requests request
      join company_ops.approval_request_states state
        on state.approval_request_id = request.id
      where request.organization_id = new.organization_id
        and request.project_id = new.project_id
        and request.task_id = new.id
        and request.action = 'production_deploy'
        and state.status = 'approved'
  ) then
    raise exception 'task does not have a current approved deployment request';
  end if;
  new.version := old.version + 1;
  new.updated_at := now();
  return new;
end;
$$;

create or replace function public.company_os_lease_next_task(
  worker_id text,
  lease_seconds integer default 300
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  claimed company_ops.tasks%rowtype;
begin
  if worker_id is null or length(trim(worker_id)) = 0 then
    raise exception 'worker_id is required';
  end if;
  if lease_seconds < 30 or lease_seconds > 3600 then
    raise exception 'lease_seconds must be between 30 and 3600';
  end if;

  select * into claimed
    from company_ops.tasks
   where status = 'queued'
   order by priority desc, created_at
     for update skip locked
   limit 1;

  if not found then
    return null;
  end if;

  update company_ops.tasks
     set status = 'assigned',
         lease_worker_id = worker_id,
         lease_expires_at = now() + make_interval(secs => lease_seconds),
         lease_heartbeat_at = now(),
         lease_epoch = claimed.lease_epoch + 1
   where id = claimed.id
   returning * into claimed;

  return to_jsonb(claimed);
end;
$$;

create or replace function public.company_os_heartbeat_task(
  task_id uuid,
  worker_id text,
  lease_seconds integer default 300
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  updated integer;
begin
  update company_ops.tasks
     set lease_heartbeat_at = now(),
         lease_expires_at = now() + make_interval(secs => lease_seconds)
   where id = task_id
     and lease_worker_id = worker_id
     and status in ('assigned', 'in_progress');
  get diagnostics updated = row_count;
  return updated = 1;
end;
$$;

-- Only the holding worker may move its task on. A worker whose lease expired
-- and was taken by someone else must not be able to write a stale result.
create or replace function public.company_os_transition_leased_task(
  task_id uuid,
  worker_id text,
  next_status text,
  release_lease boolean default false
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  updated integer;
begin
  update company_ops.tasks
     set status = next_status::company_ops.task_status,
         lease_worker_id = case when release_lease then null else lease_worker_id end,
         lease_expires_at = case when release_lease then null else lease_expires_at end
   where id = task_id
     and lease_worker_id = worker_id
     and (lease_expires_at is null or lease_expires_at > now());
  get diagnostics updated = row_count;
  return updated = 1;
end;
$$;

-- Returns tasks whose worker stopped reporting, so they can be requeued.
create or replace function public.company_os_reclaim_expired_leases()
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  reclaimed jsonb;
begin
  with expired as (
    update company_ops.tasks
       set status = 'queued',
           lease_worker_id = null,
           lease_expires_at = null
     where status in ('assigned', 'in_progress')
       and lease_expires_at is not null
       and lease_expires_at <= now()
    returning id, lease_epoch
  )
  select coalesce(jsonb_agg(to_jsonb(expired)), '[]'::jsonb) into reclaimed from expired;
  return reclaimed;
end;
$$;

revoke all on function public.company_os_lease_next_task(text, integer) from public, anon, authenticated;
revoke all on function public.company_os_heartbeat_task(uuid, text, integer) from public, anon, authenticated;
revoke all on function public.company_os_transition_leased_task(uuid, text, text, boolean) from public, anon, authenticated;
revoke all on function public.company_os_reclaim_expired_leases() from public, anon, authenticated;

grant execute on function public.company_os_lease_next_task(text, integer) to service_role;
grant execute on function public.company_os_heartbeat_task(uuid, text, integer) to service_role;
grant execute on function public.company_os_transition_leased_task(uuid, text, text, boolean) to service_role;
grant execute on function public.company_os_reclaim_expired_leases() to service_role;

commit;
