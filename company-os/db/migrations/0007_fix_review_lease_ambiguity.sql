-- Fixes an ambiguous reference in 0006.
--
-- The parameter was named `reviewer_agent_id`, which is also a column on
-- company_ops.tasks, so Postgres could not tell which one the WHERE clause
-- meant. Parameters are now prefixed, and the column is qualified, so the
-- comparison is unambiguous regardless of naming.
--
-- Renaming a parameter requires dropping the function first; CREATE OR REPLACE
-- cannot change parameter names.

begin;

drop function if exists public.company_os_lease_next_review(text, uuid, integer);

create function public.company_os_lease_next_review(
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

revoke all on function public.company_os_lease_next_review(text, uuid, integer)
  from public, anon, authenticated;
grant execute on function public.company_os_lease_next_review(text, uuid, integer)
  to service_role;

commit;
