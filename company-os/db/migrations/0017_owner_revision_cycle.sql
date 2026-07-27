-- An owner's request for changes is work, not a terminal parking state.
--
-- Preserve the immutable decision and prior checkpoint, then move through the
-- legal changes_requested -> queued transition inside the same transaction.
-- The next worker attempt receives the recorded owner comment as its briefing.

begin;

create or replace function public.company_os_record_approval_decision(payload jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  d jsonb := payload->'decision';
  t jsonb := payload->'updatedTask';
begin
  insert into company_ops.approval_decisions (
    id, approval_request_id, decided_by_user_id, decision, comment,
    request_scope_digest
  ) values (
    (d->>'id')::uuid, (d->>'approvalRequestId')::uuid,
    (d->>'decidedByUserId')::uuid, d->>'decision', d->>'comment',
    d->>'requestScopeDigest'
  );

  if t is not null and jsonb_typeof(t) = 'object' then
    update company_ops.tasks
       set status = (t->>'status')::company_ops.task_status
     where id = (t->>'id')::uuid;

    if d->>'decision' = 'request_changes'
       and t->>'status' = 'changes_requested' then
      update company_ops.tasks
         set status = 'queued',
             review_cycle_count = review_cycle_count + 1,
             lease_worker_id = null,
             lease_expires_at = null,
             lease_heartbeat_at = null
       where id = (t->>'id')::uuid;
    end if;
  end if;

  perform public.company_os_append_audit_events(
    jsonb_build_array(payload->'auditEvent')
  );
end;
$$;

revoke all on function public.company_os_record_approval_decision(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_record_approval_decision(jsonb)
  to service_role;

commit;
