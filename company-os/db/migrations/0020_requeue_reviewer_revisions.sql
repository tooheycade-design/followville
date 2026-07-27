-- A reviewer rejection is actionable work, not a terminal parking place.
--
-- Earlier review passes moved tasks to changes_requested and released the
-- lease. Workers only lease queued tasks, so seven real tasks stopped forever.
-- Record the review and move through changes_requested to queued in the same
-- transaction. The intermediate state remains real and trigger-validated; the
-- final queued state makes the next attempt automatic.

begin;

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
begin
  if v_verdict not in ('approved_for_owner', 'changes_requested') then
    raise exception 'unknown review verdict: %', v_verdict;
  end if;
  if v_verdict = 'approved_for_owner' and v_request is null then
    raise exception 'approved review requires completed work';
  end if;
  if v_verdict = 'changes_requested' and payload ? 'completedWork' then
    raise exception 'changes-requested review cannot create an approval packet';
  end if;

  select t.* into v_task
    from company_ops.tasks t
   where t.id = v_task_id
     for update;
  if not found then
    return false;
  end if;

  -- A network retry after commit is still success. For a rejected review, the
  -- immutable audit event identifies the exact verdict that already queued the
  -- revision.
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

revoke all on function public.company_os_record_review(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_record_review(jsonb)
  to service_role;

commit;
