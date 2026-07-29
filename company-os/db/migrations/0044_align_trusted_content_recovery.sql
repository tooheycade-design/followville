-- Align trusted-content recovery with the exact content task contract:
-- message_send is used for internal handoffs, and failed production packets
-- are lifecycle-synchronized to rejected. No authority is widened.

begin;

create or replace function public.company_os_retry_failed_trusted_content(
  p_task_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task company_ops.tasks%rowtype;
  v_latest_action text;
  v_latest_reason text;
  v_correlation_id uuid := gen_random_uuid();
  v_retry integer;
begin
  select task.* into v_task
    from company_ops.tasks task
   where task.id = p_task_id
   for update;

  if not found
     or v_task.status <> 'failed'
     or v_task.title not like 'Produce private preview: %'
     or cardinality(v_task.allowed_capabilities) <> 6
     or not (
       v_task.allowed_capabilities <@ array[
         'repository_read',
         'repository_write',
         'git_checkpoint',
         'test_execute',
         'blender_preview',
         'message_send'
       ]::company_ops.capability[]
     )
     or jsonb_array_length(v_task.repository_scopes) <> 1
     or not exists (
       select 1
         from jsonb_array_elements(v_task.repository_scopes) scope
        where scope->>'repository' = 'followville_repo'
          and jsonb_array_length(scope->'allowedPathPrefixes') = 2
          and (scope->'allowedPathPrefixes') ? 'company-os/content'
          and (scope->'allowedPathPrefixes') ? 'company-os/candidates/cinematic'
          and jsonb_array_length(scope->'deniedPathPrefixes') = 4
          and (scope->'deniedPathPrefixes') ? 'world_state.json'
          and (scope->'deniedPathPrefixes') ? 'town.glb'
          and (scope->'deniedPathPrefixes') ? 'town_chunks'
          and (scope->'deniedPathPrefixes') ? 'neighborhood.blend'
          and jsonb_array_length(scope->'environments') = 2
          and (scope->'environments') ? 'local'
          and (scope->'environments') ? 'preview'
     )
     or not exists (
       select 1
         from company_ops.content_packets packet
        where packet.production_task_id = v_task.id
          and packet.status = 'rejected'
     ) then
    return false;
  end if;

  select event.action, event.reason
    into v_latest_action, v_latest_reason
    from company_ops.audit_events event
   where event.task_id = v_task.id
   order by event.sequence desc
   limit 1;

  if v_latest_action <> 'worker.failed'
     or v_latest_reason not like '%files: 0%' then
    return false;
  end if;

  v_retry := v_task.retry_count + 1;

  update company_ops.tasks task
     set status = 'queued',
         retry_count = v_retry,
         lease_worker_id = null,
         lease_expires_at = null,
         lease_heartbeat_at = null,
         updated_at = now()
   where task.id = v_task.id;

  update company_ops.worker_nodes worker
     set current_task_id = null,
         current_run_id = null,
         last_seen_at = clock_timestamp()
   where worker.current_task_id = v_task.id;

  insert into company_ops.audit_events (
    organization_id,
    project_id,
    task_id,
    run_id,
    actor_type,
    actor_id,
    action,
    target_type,
    target_id,
    outcome,
    reason,
    correlation_id,
    idempotency_key,
    request_digest,
    result_digest,
    evidence_artifact_ids
  ) values (
    v_task.organization_id,
    v_task.project_id,
    v_task.id,
    null,
    'agent',
    v_task.assigned_agent_id,
    'worker.trusted_content_retry',
    'task',
    v_task.id::text,
    'succeeded',
    'Requeued file-empty private-preview failure for the trusted canonical-town renderer.',
    v_correlation_id,
    'trusted-content-retry:' || v_task.id::text || ':' || v_retry::text,
    encode(
      extensions.digest(
        convert_to(v_task.id::text || ':' || v_retry::text, 'UTF8'),
        'sha256'
      ),
      'hex'
    ),
    null,
    '{}'
  );

  return true;
end;
$$;

revoke all on function public.company_os_retry_failed_trusted_content(uuid)
  from public, anon, authenticated;
grant execute on function public.company_os_retry_failed_trusted_content(uuid)
  to service_role;

commit;
