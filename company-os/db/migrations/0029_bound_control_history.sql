-- Bound the shared dashboard payload and hosted-control history.

begin;

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

revoke all on function public.company_os_load()
  from public, anon, authenticated;
grant execute on function public.company_os_load()
  to service_role;

commit;
