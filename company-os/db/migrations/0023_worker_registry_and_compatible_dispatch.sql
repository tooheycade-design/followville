-- Private worker registry and capability-compatible task dispatch.
--
-- A worker is a durable machine/runtime identity bound to one organization,
-- project, and agent profile. Browser roles cannot inspect or mutate workers;
-- trusted runtimes register and heartbeat through the public service RPCs.

begin;

create table company_ops.worker_nodes (
  worker_id text primary key
    check (
      length(worker_id) between 1 and 160
      and worker_id = btrim(worker_id)
      and worker_id ~ '^[A-Za-z0-9][A-Za-z0-9._:@/-]*$'
    ),
  organization_id uuid not null,
  project_id uuid not null,
  agent_id uuid not null,
  display_name text not null check (length(display_name) between 1 and 120),
  machine_name text not null check (length(machine_name) between 1 and 255),
  platform text not null check (length(platform) between 1 and 120),
  provider text check (
    provider is null or length(provider) between 1 and 80
  ),
  model_id text check (
    model_id is null or length(model_id) between 1 and 160
  ),
  software_version text not null
    check (length(software_version) between 1 and 80),
  capabilities company_ops.capability[] not null default '{}'
    check (
      cardinality(capabilities) <= 64
      and array_position(capabilities, null) is null
    ),
  status text not null
    check (status in ('online', 'draining', 'offline', 'error')),
  current_task_id uuid,
  current_run_id uuid,
  started_at timestamptz not null default clock_timestamp(),
  last_seen_at timestamptz not null default clock_timestamp(),
  metadata jsonb not null default '{}'::jsonb
    check (
      jsonb_typeof(metadata) = 'object'
      and pg_column_size(metadata) <= 16384
    ),
  unique (organization_id, project_id, worker_id),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, agent_id)
    references company_ops.agent_profiles (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, current_task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, project_id, current_run_id)
    references company_ops.runs (organization_id, project_id, id) on delete restrict,
  check (last_seen_at >= started_at)
);

create index worker_nodes_dispatch_idx
  on company_ops.worker_nodes (
    organization_id, project_id, status, last_seen_at desc
  );

create index worker_nodes_agent_status_idx
  on company_ops.worker_nodes (
    organization_id, project_id, agent_id, status, last_seen_at desc
  );

create index worker_nodes_current_task_idx
  on company_ops.worker_nodes (current_task_id)
  where current_task_id is not null;

create or replace function company_ops.validate_worker_node_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.worker_id <> old.worker_id
     or new.organization_id <> old.organization_id
     or new.project_id <> old.project_id
     or new.agent_id <> old.agent_id
     or new.started_at <> old.started_at then
    raise exception 'worker identity and start time are immutable';
  end if;
  return new;
end;
$$;

create trigger worker_nodes_validate_update
before update on company_ops.worker_nodes
for each row execute function company_ops.validate_worker_node_update();

create or replace function public.company_os_upsert_worker(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_worker_id text := nullif(btrim(payload->>'workerId'), '');
  v_organization_id uuid := nullif(payload->>'organizationId', '')::uuid;
  v_project_id uuid := nullif(payload->>'projectId', '')::uuid;
  v_agent_id uuid := nullif(payload->>'agentId', '')::uuid;
  v_current_task_id uuid := nullif(payload->>'currentTaskId', '')::uuid;
  v_current_run_id uuid := nullif(payload->>'currentRunId', '')::uuid;
  v_capabilities company_ops.capability[];
  v_existing company_ops.worker_nodes%rowtype;
  v_worker company_ops.worker_nodes%rowtype;
begin
  if payload is null or jsonb_typeof(payload) <> 'object' then
    raise exception 'worker payload must be an object';
  end if;
  if v_worker_id is null then
    raise exception 'workerId is required';
  end if;
  if v_organization_id is null or v_project_id is null or v_agent_id is null then
    raise exception 'organizationId, projectId, and agentId are required';
  end if;
  if jsonb_typeof(payload->'capabilities') is distinct from 'array' then
    raise exception 'capabilities must be an array';
  end if;

  begin
    select coalesce(
      array_agg(distinct value::company_ops.capability order by value::company_ops.capability),
      '{}'::company_ops.capability[]
    )
      into v_capabilities
      from jsonb_array_elements_text(payload->'capabilities') item(value);
  exception
    when invalid_text_representation then
      raise exception 'capabilities contains an unknown capability';
  end;

  if not exists (
    select 1
      from company_ops.projects project
     where project.id = v_project_id
       and project.organization_id = v_organization_id
  ) then
    raise exception 'worker project scope does not exist';
  end if;
  if not exists (
    select 1
      from company_ops.agent_profiles agent
     where agent.id = v_agent_id
       and agent.organization_id = v_organization_id
       and agent.active
  ) then
    raise exception 'worker agent is not active in its organization';
  end if;
  if exists (
    select 1
      from unnest(v_capabilities) capability
     where not exists (
       select 1
         from company_ops.agent_profiles agent
        where agent.id = v_agent_id
          and agent.organization_id = v_organization_id
          and capability = any(agent.capabilities)
     )
  ) then
    raise exception 'worker capabilities exceed its agent profile';
  end if;

  select worker.* into v_existing
    from company_ops.worker_nodes worker
   where worker.worker_id = v_worker_id
   for update;
  if found and (
    v_existing.organization_id <> v_organization_id
    or v_existing.project_id <> v_project_id
    or v_existing.agent_id <> v_agent_id
  ) then
    raise exception 'workerId is already bound to another scope or agent';
  end if;

  if v_current_task_id is not null and not exists (
    select 1
      from company_ops.tasks task
     where task.id = v_current_task_id
       and task.organization_id = v_organization_id
       and task.project_id = v_project_id
       and task.assigned_agent_id = v_agent_id
  ) then
    raise exception 'currentTaskId does not belong to the worker agent and scope';
  end if;
  if v_current_run_id is not null and not exists (
    select 1
      from company_ops.runs run
     where run.id = v_current_run_id
       and run.organization_id = v_organization_id
       and run.project_id = v_project_id
       and run.agent_id = v_agent_id
       and (
         v_current_task_id is null
         or run.task_id = v_current_task_id
       )
  ) then
    raise exception 'currentRunId does not belong to the worker agent, task, and scope';
  end if;

  insert into company_ops.worker_nodes (
    worker_id, organization_id, project_id, agent_id, display_name,
    machine_name, platform, provider, model_id, software_version,
    capabilities, status, current_task_id, current_run_id, metadata
  ) values (
    v_worker_id,
    v_organization_id,
    v_project_id,
    v_agent_id,
    payload->>'displayName',
    payload->>'machineName',
    payload->>'platform',
    nullif(payload->>'provider', ''),
    nullif(payload->>'modelId', ''),
    payload->>'softwareVersion',
    v_capabilities,
    payload->>'status',
    v_current_task_id,
    v_current_run_id,
    coalesce(payload->'metadata', '{}'::jsonb)
  )
  on conflict (worker_id) do update
     set display_name = excluded.display_name,
         machine_name = excluded.machine_name,
         platform = excluded.platform,
         provider = excluded.provider,
         model_id = excluded.model_id,
         software_version = excluded.software_version,
         capabilities = excluded.capabilities,
         status = excluded.status,
         current_task_id =
           case when payload ? 'currentTaskId'
             then excluded.current_task_id
             else worker_nodes.current_task_id
           end,
         current_run_id =
           case when payload ? 'currentRunId'
             then excluded.current_run_id
             else worker_nodes.current_run_id
           end,
         last_seen_at = clock_timestamp(),
         metadata = excluded.metadata
  returning * into v_worker;

  if not (payload ? 'currentTaskId')
     and v_worker.current_task_id is not null
     and not exists (
       select 1
         from company_ops.tasks task
        where task.id = v_worker.current_task_id
          and task.lease_worker_id = v_worker.worker_id
          and task.status in ('assigned', 'in_progress')
          and task.lease_expires_at is not null
          and task.lease_expires_at > now()
     ) then
    update company_ops.worker_nodes worker
       set current_task_id = null,
           current_run_id = null
     where worker.worker_id = v_worker.worker_id
     returning * into v_worker;
  end if;

  return to_jsonb(v_worker);
end;
$$;

create or replace function public.company_os_lease_next_compatible_task(
  worker_id text,
  lease_seconds integer default 300
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_worker company_ops.worker_nodes%rowtype;
  v_claimed company_ops.tasks%rowtype;
begin
  if worker_id is null or length(btrim(worker_id)) = 0 then
    raise exception 'worker_id is required';
  end if;
  if lease_seconds < 30 or lease_seconds > 3600 then
    raise exception 'lease_seconds must be between 30 and 3600';
  end if;

  select worker.* into v_worker
    from company_ops.worker_nodes worker
   where worker.worker_id = btrim(company_os_lease_next_compatible_task.worker_id)
   for update;

  if not found then
    raise exception 'worker is not registered';
  end if;
  if v_worker.status <> 'online' then
    raise exception 'worker is not online';
  end if;
  if v_worker.last_seen_at < clock_timestamp() - interval '90 seconds' then
    raise exception 'worker heartbeat is stale';
  end if;
  if v_worker.current_task_id is not null and exists (
    select 1
      from company_ops.tasks active_task
     where active_task.id = v_worker.current_task_id
       and active_task.lease_worker_id = v_worker.worker_id
       and active_task.status in ('assigned', 'in_progress')
       and active_task.lease_expires_at is not null
       and active_task.lease_expires_at > now()
  ) then
    raise exception 'worker already holds an active task lease';
  end if;

  select task.* into v_claimed
    from company_ops.tasks task
   where task.organization_id = v_worker.organization_id
     and task.project_id = v_worker.project_id
     and task.status = 'queued'
     and task.assigned_agent_id = v_worker.agent_id
     and task.allowed_capabilities <@ v_worker.capabilities
     and not exists (
       select 1
         from unnest(task.dependency_ids) dependency(dependency_id)
        where not exists (
          select 1
            from company_ops.tasks completed_dependency
           where completed_dependency.id = dependency.dependency_id
             and completed_dependency.organization_id = task.organization_id
             and completed_dependency.project_id = task.project_id
             and completed_dependency.status in ('approved', 'merged', 'deployed')
        )
     )
   order by task.priority desc, task.created_at
     for update of task skip locked
   limit 1;

  if not found then
    update company_ops.worker_nodes
       set last_seen_at = clock_timestamp()
     where worker_nodes.worker_id = v_worker.worker_id;
    return null;
  end if;

  update company_ops.tasks
     set status = 'assigned',
         lease_worker_id = v_worker.worker_id,
         lease_expires_at = now() + make_interval(secs => lease_seconds),
         lease_heartbeat_at = now(),
         lease_epoch = v_claimed.lease_epoch + 1
   where id = v_claimed.id
   returning * into v_claimed;

  update company_ops.worker_nodes
     set current_task_id = v_claimed.id,
         current_run_id = null,
         last_seen_at = clock_timestamp()
   where worker_nodes.worker_id = v_worker.worker_id;

  return to_jsonb(v_claimed);
end;
$$;

-- A task heartbeat is also proof that its registered worker is alive.
create or replace function public.company_os_heartbeat_task(
  task_id uuid,
  worker_id text,
  lease_seconds integer default 300
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_updated integer;
begin
  if lease_seconds < 30 or lease_seconds > 3600 then
    raise exception 'lease_seconds must be between 30 and 3600';
  end if;

  update company_ops.tasks task
     set lease_heartbeat_at = now(),
         lease_expires_at = now() + make_interval(secs => lease_seconds)
   where task.id = company_os_heartbeat_task.task_id
     and task.lease_worker_id = company_os_heartbeat_task.worker_id
     and task.status in ('assigned', 'in_progress')
     and task.lease_expires_at is not null
     and task.lease_expires_at > now();
  get diagnostics v_updated = row_count;

  if v_updated = 1 then
    update company_ops.worker_nodes worker
       set last_seen_at = clock_timestamp(),
           current_task_id = task_id
     where worker.worker_id = company_os_heartbeat_task.worker_id
       and (
         worker.current_task_id is null
         or worker.current_task_id = company_os_heartbeat_task.task_id
       )
       and exists (
         select 1
           from company_ops.tasks task
          where task.id = company_os_heartbeat_task.task_id
            and task.organization_id = worker.organization_id
            and task.project_id = worker.project_id
            and task.assigned_agent_id = worker.agent_id
       );
  end if;

  return v_updated = 1;
end;
$$;

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
    'audit_events', coalesce((select jsonb_agg(to_jsonb(e) order by e.sequence)
      from company_ops.audit_events e), '[]'::jsonb)
  );
$$;

revoke all on company_ops.worker_nodes
  from public, anon, authenticated, service_role;
revoke all on function company_ops.validate_worker_node_update()
  from public, anon, authenticated, service_role;

revoke all on function public.company_os_upsert_worker(jsonb)
  from public, anon, authenticated;
revoke all on function public.company_os_lease_next_compatible_task(text, integer)
  from public, anon, authenticated;
revoke all on function public.company_os_heartbeat_task(uuid, text, integer)
  from public, anon, authenticated;
revoke all on function public.company_os_load()
  from public, anon, authenticated;

grant execute on function public.company_os_upsert_worker(jsonb)
  to service_role;
grant execute on function public.company_os_lease_next_compatible_task(text, integer)
  to service_role;
grant execute on function public.company_os_heartbeat_task(uuid, text, integer)
  to service_role;
grant execute on function public.company_os_load()
  to service_role;

commit;
