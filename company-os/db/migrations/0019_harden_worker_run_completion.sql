-- Tighten the worker-run completion contract after live verification.
--
-- A provider can fail before it reports a model name. That is still an
-- invocation and belongs in the usage ledger, recorded as model "unknown".
-- The function also rejects contradictory task/run status pairs instead of
-- relying on a trusted caller to construct them correctly.

begin;

create or replace function public.company_os_finish_worker_run(payload jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_run company_ops.runs%rowtype;
  v_task_status text := nullif(payload->>'taskStatus', '');
  v_run_status text := payload->>'runStatus';
  v_updated integer;
  v_provider text := nullif(payload->>'modelProvider', '');
  v_model text :=
    case when nullif(payload->>'modelProvider', '') is null
      then null
      else coalesce(nullif(payload->>'modelId', ''), 'unknown')
    end;
  v_cost bigint := (payload->>'costUsdMicros')::bigint;
begin
  if v_run_status not in ('awaiting_review', 'failed', 'canceled') then
    raise exception 'invalid terminal worker run status: %', v_run_status;
  end if;
  if (v_task_status is null and v_run_status <> 'canceled')
     or (v_task_status = 'awaiting_review' and v_run_status <> 'awaiting_review')
     or (v_task_status in ('blocked', 'failed') and v_run_status <> 'failed') then
    raise exception 'worker run status % contradicts task status %',
      v_run_status, coalesce(v_task_status, 'unchanged');
  end if;

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
     set status = v_run_status,
         model_provider = v_provider,
         model_id = v_model,
         actual_cost_usd_micros = v_cost,
         completed_at = (payload->>'completedAt')::timestamptz
   where id = v_run.id;

  if v_provider is not null then
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

revoke all on function public.company_os_finish_worker_run(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_finish_worker_run(jsonb)
  to service_role;

commit;
