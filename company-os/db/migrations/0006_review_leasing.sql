-- Leasing for independent review.
--
-- Work that a worker finished sits in `awaiting_review` until a different
-- agent checks it. Reviewers need the same lease protection as workers, so
-- two reviewers never double-review and a stalled reviewer releases the task.
--
-- The reviewer is required to differ from the worker. That separation is the
-- point of having a reviewer at all, so it is enforced here rather than left
-- to the runtime to remember.

begin;

create or replace function public.company_os_lease_next_review(
  worker_id text,
  reviewer_agent_id uuid,
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
   where status = 'awaiting_review'
     and assigned_agent_id is distinct from reviewer_agent_id
   order by priority desc, updated_at
     for update skip locked
   limit 1;

  if not found then
    return null;
  end if;

  update company_ops.tasks
     set lease_worker_id = worker_id,
         lease_expires_at = now() + make_interval(secs => lease_seconds),
         lease_heartbeat_at = now(),
         lease_epoch = claimed.lease_epoch + 1
   where id = claimed.id
   returning * into claimed;

  return to_jsonb(claimed);
end;
$$;

-- Records a review verdict and moves the task accordingly, in one transaction.
create or replace function public.company_os_record_review(payload jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  task_id uuid := (payload->>'taskId')::uuid;
  worker_id text := payload->>'workerId';
  verdict text := payload->>'verdict';
  next_status company_ops.task_status;
  updated integer;
begin
  if verdict not in ('approved_for_owner', 'changes_requested') then
    raise exception 'unknown review verdict: %', verdict;
  end if;
  next_status := case verdict
    when 'approved_for_owner' then 'awaiting_human_approval'
    else 'changes_requested'
  end::company_ops.task_status;

  update company_ops.tasks
     set status = next_status,
         review_cycle_count = review_cycle_count + 1,
         lease_worker_id = null,
         lease_expires_at = null
   where id = task_id
     and lease_worker_id = worker_id
     and (lease_expires_at is null or lease_expires_at > now())
     and status = 'awaiting_review';
  get diagnostics updated = row_count;

  if updated = 1 then
    perform public.company_os_append_audit_events(
      coalesce(payload->'auditEvents', '[]'::jsonb)
    );
  end if;
  return updated = 1;
end;
$$;

revoke all on function public.company_os_lease_next_review(text, uuid, integer) from public, anon, authenticated;
revoke all on function public.company_os_record_review(jsonb) from public, anon, authenticated;
grant execute on function public.company_os_lease_next_review(text, uuid, integer) to service_role;
grant execute on function public.company_os_record_review(jsonb) to service_role;

commit;
