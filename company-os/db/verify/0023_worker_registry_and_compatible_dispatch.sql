-- Rollback-only verification for migration 0023.
-- Run after applying 0023 to the Company OS development database.

begin;

do $verify$
declare
  v_organization_id uuid;
  v_project_id uuid;
  v_agent_id uuid;
  v_goal_id uuid;
  v_user_id uuid;
  v_dependency_id uuid := gen_random_uuid();
  v_incompatible_id uuid := gen_random_uuid();
  v_blocked_id uuid := gen_random_uuid();
  v_compatible_id uuid := gen_random_uuid();
  v_worker_id text := 'verify-worker-' || gen_random_uuid()::text;
  v_stale_worker_id text := 'verify-stale-worker-' || gen_random_uuid()::text;
  v_worker jsonb;
  v_lease jsonb;
  v_started_at timestamptz;
  v_last_seen_at timestamptz;
  v_loaded jsonb;
  v_refused boolean;
begin
  if to_regclass('company_ops.worker_nodes') is null then
    raise exception 'worker_nodes table is missing';
  end if;
  if to_regprocedure('public.company_os_upsert_worker(jsonb)') is null then
    raise exception 'company_os_upsert_worker(jsonb) is missing';
  end if;
  if to_regprocedure(
    'public.company_os_lease_next_compatible_task(text,integer)'
  ) is null then
    raise exception 'company_os_lease_next_compatible_task(text, integer) is missing';
  end if;

  if has_function_privilege(
    'anon', 'public.company_os_upsert_worker(jsonb)', 'EXECUTE'
  ) or has_function_privilege(
    'authenticated', 'public.company_os_upsert_worker(jsonb)', 'EXECUTE'
  ) or has_function_privilege(
    'anon',
    'public.company_os_lease_next_compatible_task(text,integer)',
    'EXECUTE'
  ) or has_function_privilege(
    'authenticated',
    'public.company_os_lease_next_compatible_task(text,integer)',
    'EXECUTE'
  ) then
    raise exception 'browser role can execute a worker RPC';
  end if;
  if not has_function_privilege(
    'service_role', 'public.company_os_upsert_worker(jsonb)', 'EXECUTE'
  ) or not has_function_privilege(
    'service_role',
    'public.company_os_lease_next_compatible_task(text,integer)',
    'EXECUTE'
  ) then
    raise exception 'service_role cannot execute a worker RPC';
  end if;
  if has_table_privilege(
    'service_role', 'company_ops.worker_nodes', 'SELECT'
  ) or has_table_privilege(
    'service_role', 'company_ops.worker_nodes', 'INSERT'
  ) or has_table_privilege(
    'service_role', 'company_ops.worker_nodes', 'UPDATE'
  ) then
    raise exception 'service_role has direct worker_nodes table access';
  end if;

  select project.organization_id, project.id
    into v_organization_id, v_project_id
    from company_ops.projects project
   order by project.created_at
   limit 1;
  if not found then
    raise exception 'verification requires an existing Company OS project';
  end if;

  select agent.id into v_agent_id
    from company_ops.agent_profiles agent
   where agent.organization_id = v_organization_id
     and agent.active
   order by agent.created_at
   limit 1;
  if not found then
    raise exception 'verification requires an active agent in the project organization';
  end if;

  select member.user_id into v_user_id
    from company_ops.organization_members member
   where member.organization_id = v_organization_id
     and member.active
   order by member.created_at
   limit 1;
  if not found then
    raise exception 'verification requires an active organization member';
  end if;

  v_goal_id := gen_random_uuid();
  insert into company_ops.goals (
    id, organization_id, project_id, created_by_user_id, title, objective,
    success_definition, constraints, risk_level, status
  ) values (
    v_goal_id, v_organization_id, v_project_id, v_user_id,
    '0023 rollback verification', 'Verify compatible dispatch',
    'All checks pass and the transaction rolls back', '[]'::jsonb,
    'low', 'active'
  );

  insert into company_ops.tasks (
    id, organization_id, project_id, goal_id, title, objective, reason,
    status, priority, risk_level, assigned_agent_id, dependency_ids,
    acceptance_criteria, allowed_capabilities, repository_scopes,
    expected_outputs
  ) values
  (
    v_dependency_id, v_organization_id, v_project_id, v_goal_id,
    'Completed dependency', 'Provide prerequisite', 'Verification fixture',
    'approved', 100, 'low', v_agent_id, '{}'::uuid[], '[]'::jsonb,
    array['repository_read']::company_ops.capability[], '[]'::jsonb,
    '[]'::jsonb
  ),
  (
    v_incompatible_id, v_organization_id, v_project_id, v_goal_id,
    'Incompatible task', 'Require unsupported write', 'Verification fixture',
    'queued', 99, 'low', v_agent_id, '{}'::uuid[], '[]'::jsonb,
    array['repository_write']::company_ops.capability[], '[]'::jsonb,
    '[]'::jsonb
  ),
  (
    v_blocked_id, v_organization_id, v_project_id, v_goal_id,
    'Dependency blocked task', 'Wait for incompatible task', 'Verification fixture',
    'queued', 98, 'low', v_agent_id, array[v_incompatible_id], '[]'::jsonb,
    array['repository_read']::company_ops.capability[], '[]'::jsonb,
    '[]'::jsonb
  ),
  (
    v_compatible_id, v_organization_id, v_project_id, v_goal_id,
    'Compatible task', 'Lease to matching worker', 'Verification fixture',
    'queued', 97, 'low', v_agent_id, array[v_dependency_id], '[]'::jsonb,
    array['repository_read']::company_ops.capability[], '[]'::jsonb,
    '[]'::jsonb
  );

  v_worker := public.company_os_upsert_worker(jsonb_build_object(
    'workerId', v_worker_id,
    'organizationId', v_organization_id,
    'projectId', v_project_id,
    'agentId', v_agent_id,
    'displayName', '0023 verification worker',
    'machineName', 'rollback-only',
    'platform', 'other',
    'provider', 'verification',
    'modelId', 'none',
    'softwareVersion', '0023-test',
    'capabilities', jsonb_build_array('repository_read'),
    'status', 'online',
    'currentTaskId', null,
    'currentRunId', null,
    'metadata', jsonb_build_object('rollbackOnly', true)
  ));

  if v_worker->>'worker_id' <> v_worker_id
     or v_worker->>'status' <> 'online'
     or v_worker->'capabilities' <> '["repository_read"]'::jsonb then
    raise exception 'worker registration returned an unexpected row: %', v_worker;
  end if;
  select started_at into v_started_at
    from company_ops.worker_nodes
   where worker_id = v_worker_id;

  perform pg_sleep(0.01);
  v_worker := public.company_os_upsert_worker(jsonb_build_object(
    'workerId', v_worker_id,
    'organizationId', v_organization_id,
    'projectId', v_project_id,
    'agentId', v_agent_id,
    'displayName', '0023 verification worker heartbeat',
    'machineName', 'rollback-only',
    'platform', 'other',
    'provider', 'verification',
    'modelId', 'none',
    'softwareVersion', '0023-test',
    'capabilities', jsonb_build_array('repository_read'),
    'status', 'online',
    'currentTaskId', null,
    'currentRunId', null,
    'metadata', jsonb_build_object('heartbeat', true)
  ));
  if (v_worker->>'started_at')::timestamptz <> v_started_at
     or (v_worker->>'last_seen_at')::timestamptz <= v_started_at then
    raise exception 'heartbeat changed started_at or failed to advance last_seen_at';
  end if;

  v_lease := public.company_os_lease_next_compatible_task(v_worker_id, 300);
  if (v_lease->>'id')::uuid <> v_compatible_id then
    raise exception
      'compatible dispatch leased %, expected %; capability/dependency filter failed',
      v_lease->>'id', v_compatible_id;
  end if;
  if exists (
    select 1
      from company_ops.tasks task
     where task.id in (v_incompatible_id, v_blocked_id)
       and task.status <> 'queued'
  ) then
    raise exception 'incompatible or dependency-blocked task was leased';
  end if;
  if not exists (
    select 1
      from company_ops.worker_nodes worker
     where worker.worker_id = v_worker_id
       and worker.current_task_id = v_compatible_id
  ) then
    raise exception 'lease did not update worker current_task_id';
  end if;

  select last_seen_at into v_last_seen_at
    from company_ops.worker_nodes
   where worker_id = v_worker_id;
  perform pg_sleep(0.01);
  if not public.company_os_heartbeat_task(v_compatible_id, v_worker_id, 300) then
    raise exception 'normal task heartbeat was refused';
  end if;
  if not exists (
    select 1
      from company_ops.worker_nodes worker
     where worker.worker_id = v_worker_id
       and worker.current_task_id = v_compatible_id
       and worker.last_seen_at > v_last_seen_at
  ) then
    raise exception 'task heartbeat did not refresh worker last_seen_at';
  end if;

  update company_ops.tasks
     set status = 'queued',
         lease_worker_id = null,
         lease_expires_at = null,
         lease_heartbeat_at = null
   where id = v_compatible_id;

  update company_ops.worker_nodes
     set status = 'offline',
         current_task_id = null
   where worker_id = v_worker_id;
  v_refused := false;
  begin
    perform public.company_os_lease_next_compatible_task(v_worker_id, 300);
  exception
    when others then
      v_refused := sqlerrm like '%not online%';
  end;
  if not v_refused then
    raise exception 'offline worker was not refused';
  end if;

  insert into company_ops.worker_nodes (
    worker_id, organization_id, project_id, agent_id, display_name,
    machine_name, platform, provider, model_id, software_version,
    capabilities, status, started_at, last_seen_at, metadata
  ) values (
    v_stale_worker_id, v_organization_id, v_project_id, v_agent_id,
    '0023 stale verification worker', 'rollback-only', 'other',
    'verification', 'none', '0023-test',
    array['repository_read']::company_ops.capability[], 'online',
    clock_timestamp() - interval '2 minutes',
    clock_timestamp() - interval '2 minutes',
    jsonb_build_object('rollbackOnly', true)
  );
  v_refused := false;
  begin
    perform public.company_os_lease_next_compatible_task(v_stale_worker_id, 300);
  exception
    when others then
      v_refused := sqlerrm like '%heartbeat is stale%';
  end;
  if not v_refused then
    raise exception 'stale worker was not refused';
  end if;

  v_loaded := public.company_os_load();
  if not (
    v_loaded ?& array[
      'goals', 'tasks', 'runs', 'approval_requests', 'approval_states',
      'approval_decisions', 'evidence_artifacts', 'audit_events',
      'worker_nodes'
    ]
  ) then
    raise exception 'company_os_load omitted an existing key or worker_nodes';
  end if;
end;
$verify$;

select
  '0023 worker registry and compatible dispatch' as verification,
  'pass (transaction will now roll back)' as result;

rollback;
