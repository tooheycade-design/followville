-- Visual production needs room to respond to pixel-backed feedback.
--
-- Ordinary work keeps the three-cycle stop. Tasks that explicitly carry a
-- preview capability may use at most five review cycles, which remains bounded
-- while allowing a composition revision after technical and visual checks.

begin;

create or replace function company_ops.cap_automatic_revision_loop()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_limit integer := case
    when 'browser_preview'::company_ops.capability = any(old.allowed_capabilities)
      or 'blender_preview'::company_ops.capability = any(old.allowed_capabilities)
      then 5
    else 3
  end;
begin
  if old.status = 'changes_requested'
     and new.status = 'queued'
     and old.review_cycle_count >= v_limit then
    new.status := 'failed';
  end if;
  return new;
end;
$$;

-- Resume a previously capped visual revision only when the latest independent
-- visual event contains substantive feedback. This cannot approve, publish,
-- alter capabilities, or bypass the five-cycle cap.
create or replace function public.company_os_resume_bounded_visual_revision(
  payload jsonb
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task_id uuid := (payload->>'taskId')::uuid;
  v_task company_ops.tasks%rowtype;
  v_latest_visual company_ops.audit_events%rowtype;
  v_audit jsonb := payload->'auditEvent';
begin
  select t.* into v_task
    from company_ops.tasks t
   where t.id = v_task_id
     for update;

  if not found
     or v_task.status <> 'failed'
     or v_task.review_cycle_count >= 5
     or not (
       'browser_preview'::company_ops.capability = any(v_task.allowed_capabilities)
       or 'blender_preview'::company_ops.capability = any(v_task.allowed_capabilities)
     )
     or not exists (
       select 1
         from company_ops.content_packets packet
        where packet.production_task_id = v_task.id
     ) then
    return false;
  end if;

  select event.* into v_latest_visual
    from company_ops.audit_events event
   where event.task_id = v_task.id
     and event.action like 'visual_review.%'
   order by event.sequence desc
   limit 1;

  if not found
     or v_latest_visual.action <> 'visual_review.changes_requested'
     or v_latest_visual.reason like 'The independent visual review failed:%'
     or v_audit->>'action' <> 'review.visual_revision_requeued'
     or (v_audit->>'taskId')::uuid <> v_task.id then
    return false;
  end if;

  update company_ops.tasks
     set status = 'queued',
         lease_worker_id = null,
         lease_expires_at = null
   where id = v_task.id;

  perform public.company_os_append_audit_events(jsonb_build_array(v_audit));
  return true;
end;
$$;

revoke all on function public.company_os_resume_bounded_visual_revision(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_resume_bounded_visual_revision(jsonb)
  to service_role;

commit;
