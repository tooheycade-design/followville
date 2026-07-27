-- Make the run ledger describe real worker attempts.
--
-- A task lease and its run are tied together by worker id and lease epoch.
-- Opening a run must happen before executor work. Finishing a run and moving
-- its task happen in one transaction, so the factory cannot show one without
-- the other. A stale worker may close its own run as canceled, but cannot move
-- a task after another worker has acquired it.

begin;

alter table company_ops.runs
  add column if not exists worker_id text,
  add column if not exists lease_epoch integer;

create or replace function public.company_os_start_worker_run(payload jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task company_ops.tasks%rowtype;
begin
  select t.* into v_task
    from company_ops.tasks t
   where t.id = (payload->>'taskId')::uuid
     for update;

  if not found
     or v_task.status <> 'in_progress'
     or v_task.lease_worker_id <> payload->>'workerId'
     or v_task.lease_epoch <> (payload->>'leaseEpoch')::integer
     or v_task.lease_expires_at is null
     or v_task.lease_expires_at <= now() then
    return false;
  end if;
  if v_task.assigned_agent_id is null
     or v_task.assigned_agent_id <> (payload->>'agentId')::uuid then
    raise exception 'worker run agent does not match the leased task';
  end if;

  insert into company_ops.runs (
    id, organization_id, project_id, task_id, agent_id, reviewer_agent_id,
    trigger, mode, status, model_provider, model_id, prompt_version,
    context_manifest_digest, workspace_id, budget_reservation_usd_micros,
    actual_cost_usd_micros, retry_count, started_at, completed_at,
    worker_id, lease_epoch
  ) values (
    (payload->>'id')::uuid,
    v_task.organization_id,
    v_task.project_id,
    v_task.id,
    (payload->>'agentId')::uuid,
    nullif(payload->>'reviewerAgentId', '')::uuid,
    'event',
    'execute',
    'running',
    null,
    null,
    payload->>'promptVersion',
    payload->>'contextManifestDigest',
    null,
    v_task.budget_usd_micros,
    0,
    (payload->>'retryCount')::smallint,
    (payload->>'startedAt')::timestamptz,
    null,
    payload->>'workerId',
    (payload->>'leaseEpoch')::integer
  );

  return true;
end;
$$;

create or replace function public.company_os_finish_worker_run(payload jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_run company_ops.runs%rowtype;
  v_task_status text := nullif(payload->>'taskStatus', '');
  v_updated integer;
  v_provider text := nullif(payload->>'modelProvider', '');
  v_model text := nullif(payload->>'modelId', '');
  v_cost bigint := (payload->>'costUsdMicros')::bigint;
begin
  select r.* into v_run
    from company_ops.runs r
   where r.id = (payload->>'runId')::uuid
     for update;

  if not found
     or v_run.task_id <> (payload->>'taskId')::uuid
     or v_run.worker_id <> payload->>'workerId'
     or v_run.lease_epoch <> (payload->>'leaseEpoch')::integer
     or v_run.status <> 'running' then
    return false;
  end if;

  if v_task_status is not null then
    update company_ops.tasks
       set status = v_task_status::company_ops.task_status,
           actual_cost_usd_micros = actual_cost_usd_micros + v_cost,
           lease_worker_id =
             case when (payload->>'releaseLease')::boolean then null else lease_worker_id end,
           lease_expires_at =
             case when (payload->>'releaseLease')::boolean then null else lease_expires_at end
     where id = v_run.task_id
       and lease_worker_id = v_run.worker_id
       and lease_epoch = v_run.lease_epoch
       and lease_expires_at is not null
       and lease_expires_at > now();
    get diagnostics v_updated = row_count;

    if v_updated <> 1 then
      update company_ops.runs
         set status = 'canceled',
             completed_at = (payload->>'completedAt')::timestamptz
       where id = v_run.id;
      return false;
    end if;
  end if;

  update company_ops.runs
     set status = payload->>'runStatus',
         model_provider = v_provider,
         model_id = v_model,
         actual_cost_usd_micros = v_cost,
         completed_at = (payload->>'completedAt')::timestamptz
   where id = v_run.id;

  if v_provider is not null and v_model is not null then
    insert into company_ops.usage_ledger (
      organization_id, project_id, task_id, run_id, agent_id,
      provider, model, input_tokens, output_tokens, cached_input_tokens,
      estimated_cost_usd_micros, actual_cost_usd_micros
    ) values (
      v_run.organization_id,
      v_run.project_id,
      v_run.task_id,
      v_run.id,
      v_run.agent_id,
      v_provider,
      v_model,
      (payload->>'inputTokens')::bigint,
      (payload->>'outputTokens')::bigint,
      (payload->>'cachedInputTokens')::bigint,
      v_cost,
      v_cost
    );
  end if;

  return true;
end;
$$;

revoke all on function public.company_os_start_worker_run(jsonb)
  from public, anon, authenticated;
revoke all on function public.company_os_finish_worker_run(jsonb)
  from public, anon, authenticated;

grant execute on function public.company_os_start_worker_run(jsonb)
  to service_role;
grant execute on function public.company_os_finish_worker_run(jsonb)
  to service_role;

commit;
