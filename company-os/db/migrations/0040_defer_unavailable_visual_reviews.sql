-- Reviewer outages are not worker revisions.
--
-- A timed-out Design Director used to become changes_requested, consume an
-- automatic revision, and eventually fail a completed task. Defer transient
-- review failures in awaiting_review without incrementing the review cycle.
-- The active lease becomes a short cooldown, so the worker loop cannot spin.

begin;

create or replace function public.company_os_lease_next_review(
  p_worker_id text,
  p_reviewer_agent_id uuid,
  p_lease_seconds integer default 300
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  claimed company_ops.tasks%rowtype;
begin
  if p_worker_id is null or length(trim(p_worker_id)) = 0 then
    raise exception 'p_worker_id is required';
  end if;
  if p_lease_seconds < 30 or p_lease_seconds > 3600 then
    raise exception 'p_lease_seconds must be between 30 and 3600';
  end if;

  select t.* into claimed
    from company_ops.tasks t
   where t.status = 'awaiting_review'
     and t.assigned_agent_id is distinct from p_reviewer_agent_id
     and (t.lease_expires_at is null or t.lease_expires_at <= now())
   order by t.priority desc, t.updated_at
     for update skip locked
   limit 1;

  if not found then
    return null;
  end if;

  update company_ops.tasks t
     set lease_worker_id = p_worker_id,
         lease_expires_at = now() + make_interval(secs => p_lease_seconds),
         lease_heartbeat_at = now(),
         lease_epoch = claimed.lease_epoch + 1
   where t.id = claimed.id
   returning t.* into claimed;

  return to_jsonb(claimed);
end;
$$;

create or replace function public.company_os_record_review(payload jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task_id uuid := (payload->>'taskId')::uuid;
  v_worker_id text := payload->>'workerId';
  v_verdict text := payload->>'verdict';
  v_next_status company_ops.task_status;
  v_task company_ops.tasks%rowtype;
  v_request jsonb := payload->'completedWork'->'approvalRequest';
  v_retry_after integer := coalesce((payload->>'retryAfterSeconds')::integer, 300);
begin
  if v_verdict not in ('approved_for_owner', 'changes_requested', 'deferred') then
    raise exception 'unknown review verdict: %', v_verdict;
  end if;
  if v_verdict = 'approved_for_owner' and v_request is null then
    raise exception 'approved review requires completed work';
  end if;
  if v_verdict in ('changes_requested', 'deferred')
     and payload ? 'completedWork' then
    raise exception 'non-approved review cannot create an approval packet';
  end if;
  if v_verdict = 'deferred'
     and (v_retry_after < 60 or v_retry_after > 1800) then
    raise exception 'review retry must be between 60 and 1800 seconds';
  end if;

  select t.* into v_task
    from company_ops.tasks t
   where t.id = v_task_id
     for update;
  if not found then
    return false;
  end if;

  if v_verdict = 'deferred'
     and v_task.status = 'awaiting_review'
     and exists (
       select 1
         from company_ops.audit_events stored
         join lateral jsonb_array_elements(
           coalesce(payload->'auditEvents', '[]'::jsonb)
         ) submitted on (submitted->>'id')::uuid = stored.id
        where stored.task_id = v_task.id
          and stored.action = 'visual_review.unavailable'
     ) then
    return true;
  end if;

  if v_task.status = 'queued'
     and v_verdict = 'changes_requested'
     and exists (
       select 1
         from company_ops.audit_events stored
         join lateral jsonb_array_elements(
           coalesce(payload->'auditEvents', '[]'::jsonb)
         ) submitted on (submitted->>'id')::uuid = stored.id
        where stored.task_id = v_task.id
          and stored.action = 'review.changes_requested'
     ) then
    return true;
  end if;

  if v_task.status = 'awaiting_human_approval'
     and v_verdict = 'approved_for_owner'
     and exists (
       select 1
         from company_ops.approval_requests request
        where request.idempotency_key = v_request->>'idempotencyKey'
          and request.task_id = v_task.id
          and request.organization_id = v_task.organization_id
          and request.project_id = v_task.project_id
     ) then
    return true;
  end if;

  if v_task.status <> 'awaiting_review'
     or v_task.lease_worker_id is distinct from v_worker_id
     or v_task.lease_expires_at is null
     or v_task.lease_expires_at <= now() then
    return false;
  end if;

  if v_verdict = 'deferred' then
    update company_ops.tasks
       set lease_expires_at = now() + make_interval(secs => v_retry_after),
           lease_heartbeat_at = now()
     where id = v_task.id;
    perform public.company_os_append_audit_events(
      coalesce(payload->'auditEvents', '[]'::jsonb)
    );
    return true;
  end if;

  v_next_status := case v_verdict
    when 'approved_for_owner' then 'awaiting_human_approval'
    else 'changes_requested'
  end::company_ops.task_status;

  if v_verdict = 'approved_for_owner' then
    perform public.company_os_record_completed_work(payload->'completedWork');
  end if;

  update company_ops.tasks
     set status = v_next_status,
         review_cycle_count = review_cycle_count + 1,
         lease_worker_id = null,
         lease_expires_at = null
   where id = v_task.id;

  if v_verdict = 'changes_requested' then
    update company_ops.tasks
       set status = 'queued'
     where id = v_task.id
       and status = 'changes_requested';
  end if;

  perform public.company_os_append_audit_events(
    coalesce(payload->'auditEvents', '[]'::jsonb)
  );
  return true;
end;
$$;

-- Recovers a task that the old reviewer-outage behavior failed. The service
-- must pin the exact completed run, and the database independently checks the
-- latest mechanical approval and outage-shaped visual event before walking the
-- existing legal transition chain back to awaiting_review.
create or replace function public.company_os_retry_failed_review(payload jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task_id uuid := (payload->>'taskId')::uuid;
  v_expected_run_id uuid := (payload->>'expectedRunId')::uuid;
  v_task company_ops.tasks%rowtype;
  v_latest_visual company_ops.audit_events%rowtype;
  v_audit jsonb := payload->'auditEvent';
begin
  select t.* into v_task
    from company_ops.tasks t
   where t.id = v_task_id
     for update;
  if not found or v_task.status <> 'failed' then
    return false;
  end if;

  select e.* into v_latest_visual
    from company_ops.audit_events e
   where e.task_id = v_task.id
     and e.action like 'visual_review.%'
   order by e.sequence desc
   limit 1;

  if not found
     or v_latest_visual.action <> 'visual_review.changes_requested'
     or v_latest_visual.run_id is distinct from v_expected_run_id
     or v_latest_visual.reason not like 'The independent visual review failed:%'
     or not exists (
       select 1
         from company_ops.audit_events e
        where e.task_id = v_task.id
          and e.run_id = v_expected_run_id
          and e.action = 'worker.completed'
     )
     or not exists (
       select 1
         from company_ops.audit_events e
        where e.task_id = v_task.id
          and e.run_id = v_expected_run_id
          and e.action = 'review.approved_for_owner'
     )
     or v_audit->>'action' <> 'review.retry_scheduled'
     or (v_audit->>'taskId')::uuid <> v_task.id
     or nullif(v_audit->>'runId', '')::uuid is distinct from v_expected_run_id then
    return false;
  end if;

  update company_ops.tasks
     set status = 'queued',
         review_cycle_count = greatest(review_cycle_count - 1, 0),
         lease_worker_id = null,
         lease_expires_at = null
   where id = v_task.id;
  update company_ops.tasks set status = 'assigned' where id = v_task.id;
  update company_ops.tasks set status = 'in_progress' where id = v_task.id;
  update company_ops.tasks set status = 'awaiting_review' where id = v_task.id;

  perform public.company_os_append_audit_events(jsonb_build_array(v_audit));
  return true;
end;
$$;

revoke all on function public.company_os_lease_next_review(text, uuid, integer)
  from public, anon, authenticated;
revoke all on function public.company_os_record_review(jsonb)
  from public, anon, authenticated;
revoke all on function public.company_os_retry_failed_review(jsonb)
  from public, anon, authenticated;

grant execute on function public.company_os_lease_next_review(text, uuid, integer)
  to service_role;
grant execute on function public.company_os_record_review(jsonb)
  to service_role;
grant execute on function public.company_os_retry_failed_review(jsonb)
  to service_role;

commit;
