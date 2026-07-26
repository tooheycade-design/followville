-- Allows the review counter to change on a reviewed task.
--
-- `validate_task_update` treats any non-status change to a task in a reviewed
-- state as tampering, which is what protects an approved scope from being
-- rewritten after the fact. Incrementing `review_cycle_count` is bookkeeping
-- about the review itself rather than a change to what was reviewed, so it
-- belongs in the ignored set alongside the lease columns.
--
-- Everything that defines the work — objective, capabilities, scopes,
-- acceptance criteria, budget — remains immutable once reviewed.

begin;

create or replace function company_ops.validate_task_update()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  transition_allowed boolean;
  ignored text[] := array[
    'status', 'updated_at', 'version', 'actual_cost_usd_micros',
    'lease_worker_id', 'lease_expires_at', 'lease_heartbeat_at', 'lease_epoch',
    'review_cycle_count', 'retry_count'
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
    when 'changes_requested' then new.status in ('in_progress', 'canceled', 'failed', 'queued')
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

commit;
