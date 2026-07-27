-- Puts finished work in front of an owner, with its evidence attached.
--
-- Two gaps closed together, because neither is useful alone.
--
-- First: a task that passed review and the Chief Executive's gate moved to
-- `awaiting_human_approval` and stopped there. The approvals page lists
-- `approval_requests`, and the worker flow never created one, so completed
-- work was invisible. Five tasks reached that state on 2026-07-27 and an owner
-- had no way to see or act on any of them. The task transition trigger also
-- refuses `approved` without an approved decision, so the status could not
-- have been advanced even by hand.
--
-- Second: `evidence_artifact_ids` has been on runs, approvals, and audit
-- events since 0001 and was always empty, because artifacts had no table. An
-- approval packet could describe a screenshot and reference nothing.
--
-- Artifacts hold a reference rather than bytes. The runtime records finished
-- work on the task's own `agent/task-*` branch, so the content is already
-- durable and retrievable with `git show <commit>:<path>`. `location` is jsonb
-- so an object-store backed artifact can be added without a schema change.

begin;

create table company_ops.evidence_artifacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null
    references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  task_id uuid not null references company_ops.tasks(id) on delete restrict,
  run_id uuid,
  kind text not null check (
    kind in ('screenshot', 'render', 'recording', 'log', 'patch', 'report')
  ),
  label text not null check (length(label) between 1 and 200),
  media_type text not null check (length(media_type) between 1 and 120),
  size_bytes bigint not null check (size_bytes >= 0),
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  location jsonb not null,
  created_by_agent_id uuid not null,
  created_at timestamptz not null default now(),
  -- Null means keep it as long as its task exists. An approval whose evidence
  -- expired cannot be audited afterwards.
  expires_at timestamptz
);

create index evidence_artifacts_task_idx
  on company_ops.evidence_artifacts (task_id, created_at);

alter table company_ops.evidence_artifacts enable row level security;

-- Evidence is a record of what happened. Editing it after the fact would make
-- every approval that cited it unverifiable.
create or replace function company_ops.block_artifact_change()
returns trigger
language plpgsql
as $$
begin
  raise exception 'evidence artifacts are append-only';
end;
$$;

create trigger evidence_artifacts_immutable
  before update or delete on company_ops.evidence_artifacts
  for each row execute function company_ops.block_artifact_change();

/*
 * Records finished work: its artifacts and the approval request that cites
 * them, in one transaction.
 *
 * Written together on purpose. An approval request referencing artifact rows
 * that failed to insert would be a packet pointing at nothing, which is the
 * failure this migration exists to end.
 */
create or replace function public.company_os_record_completed_work(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_request jsonb := payload->'approvalRequest';
  v_artifact jsonb;
  v_task company_ops.tasks%rowtype;
  v_artifact_ids uuid[];
  v_evidence_ids uuid[];
begin
  select t.* into v_task
    from company_ops.tasks t
   where t.id = (v_request->>'taskId')::uuid
     for update;
  if not found or v_task.status <> 'awaiting_review' then
    raise exception 'completed work requires a task awaiting review';
  end if;
  if (v_request->>'organizationId')::uuid <> v_task.organization_id
     or (v_request->>'projectId')::uuid <> v_task.project_id then
    raise exception 'approval request does not belong to its task';
  end if;
  if not ((v_request->>'action')::company_ops.capability =
          any(v_task.allowed_capabilities)) then
    raise exception 'approval action is outside the task capability grant';
  end if;

  select coalesce(array_agg((item->>'id')::uuid order by item->>'id'), '{}'::uuid[])
    into v_artifact_ids
    from jsonb_array_elements(coalesce(payload->'artifacts', '[]'::jsonb)) item;
  select coalesce(array_agg(value::uuid order by value), '{}'::uuid[])
    into v_evidence_ids
    from jsonb_array_elements_text(
      coalesce(v_request->'evidenceArtifactIds', '[]'::jsonb)
    ) value;
  if v_artifact_ids <> v_evidence_ids then
    raise exception 'approval evidence must exactly match the submitted artifacts';
  end if;

  for v_artifact in select * from jsonb_array_elements(payload->'artifacts')
  loop
    if (v_artifact->>'organizationId')::uuid <> v_task.organization_id
       or (v_artifact->>'projectId')::uuid <> v_task.project_id
       or (v_artifact->>'taskId')::uuid <> v_task.id then
      raise exception 'artifact does not belong to its task';
    end if;
    if v_task.assigned_agent_id is not null
       and (v_artifact->>'createdByAgentId')::uuid <> v_task.assigned_agent_id then
      raise exception 'artifact creator is not the assigned worker';
    end if;
    if v_artifact->'location'->>'kind' = 'git'
       and (
         nullif(v_request->>'commitSha', '') is null
         or v_artifact->'location'->>'commitSha' <> v_request->>'commitSha'
       ) then
      raise exception 'git artifact is not pinned to the approved checkpoint';
    end if;
    insert into company_ops.evidence_artifacts (
      id, organization_id, project_id, task_id, run_id, kind, label,
      media_type, size_bytes, sha256, location, created_by_agent_id,
      created_at, expires_at
    ) values (
      (v_artifact->>'id')::uuid,
      (v_artifact->>'organizationId')::uuid,
      (v_artifact->>'projectId')::uuid,
      (v_artifact->>'taskId')::uuid,
      nullif(v_artifact->>'runId', '')::uuid,
      v_artifact->>'kind',
      v_artifact->>'label',
      v_artifact->>'mediaType',
      (v_artifact->>'sizeBytes')::bigint,
      v_artifact->>'sha256',
      v_artifact->'location',
      (v_artifact->>'createdByAgentId')::uuid,
      (v_artifact->>'createdAt')::timestamptz,
      nullif(v_artifact->>'expiresAt', '')::timestamptz
    );
  end loop;

  insert into company_ops.approval_requests (
    id, organization_id, project_id, task_id, run_id, requested_by_type,
    requested_by_id, action, summary, reason, scope_digest, commit_sha,
    evidence_artifact_ids, tests_completed, risk_level, reversible,
    rollback_plan, estimated_cost_usd_micros, recommendation, alternatives,
    required_approvals, required_role, idempotency_key, created_at, expires_at
  ) values (
    (v_request->>'id')::uuid,
    (v_request->>'organizationId')::uuid,
    (v_request->>'projectId')::uuid,
    (v_request->>'taskId')::uuid,
    nullif(v_request->>'runId', '')::uuid,
    (v_request->>'requestedByType')::company_ops.actor_type,
    (v_request->>'requestedById')::uuid,
    (v_request->>'action')::company_ops.capability,
    v_request->>'summary',
    v_request->>'reason',
    v_request->>'scopeDigest',
    nullif(v_request->>'commitSha', ''),
    coalesce(
      (select array_agg(value::text::uuid)
         from jsonb_array_elements_text(v_request->'evidenceArtifactIds') as value),
      '{}'::uuid[]
    ),
    coalesce(v_request->'testsCompleted', '[]'::jsonb),
    (v_request->>'riskLevel')::company_ops.risk_level,
    (v_request->>'reversible')::boolean,
    v_request->>'rollbackPlan',
    (v_request->>'estimatedCostUsdMicros')::bigint,
    v_request->>'recommendation',
    coalesce(v_request->'alternatives', '[]'::jsonb),
    (v_request->>'requiredApprovals')::smallint,
    v_request->>'requiredRole',
    v_request->>'idempotencyKey',
    (v_request->>'createdAt')::timestamptz,
    (v_request->>'expiresAt')::timestamptz
  );

  return jsonb_build_object('approvalRequestId', v_request->>'id', 'created', true);
end;
$$;

revoke all on function public.company_os_record_completed_work(jsonb)
  from public, anon, authenticated, service_role;

/*
 * The verdict, its audit rows, artifacts, approval request, and task transition
 * are one transaction. A lost review lease can therefore leave none of them
 * behind, and a packet failure cannot produce invisible approved work.
 */
create or replace function public.company_os_record_review(payload jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_task_id uuid := (payload->>'taskId')::uuid;
  v_worker_id text := payload->>'workerId';
  v_verdict text := payload->>'verdict';
  v_next_status company_ops.task_status;
  v_task company_ops.tasks%rowtype;
  v_request jsonb := payload->'completedWork'->'approvalRequest';
begin
  if v_verdict not in ('approved_for_owner', 'changes_requested') then
    raise exception 'unknown review verdict: %', v_verdict;
  end if;
  if v_verdict = 'approved_for_owner' and v_request is null then
    raise exception 'approved review requires completed work';
  end if;
  if v_verdict = 'changes_requested' and payload ? 'completedWork' then
    raise exception 'changes-requested review cannot create an approval packet';
  end if;

  select t.* into v_task
    from company_ops.tasks t
   where t.id = v_task_id
     for update;
  if not found then
    return false;
  end if;

  -- A network retry after a committed transaction is a successful retry, not
  -- a second review. The idempotency key must still point at this same task.
  if v_task.status = 'awaiting_human_approval'
     and v_verdict = 'approved_for_owner'
     and exists (
       select 1
         from company_ops.approval_requests request
        where request.idempotency_key = v_request->>'idempotencyKey'
          and request.task_id = v_task.id
          and request.organization_id = v_task.organization_id
          and request.project_id = v_task.project_id
     ) then
    return true;
  end if;

  if v_task.status <> 'awaiting_review'
     or v_task.lease_worker_id is distinct from v_worker_id
     or v_task.lease_expires_at is null
     or v_task.lease_expires_at <= now() then
    return false;
  end if;

  v_next_status := case v_verdict
    when 'approved_for_owner' then 'awaiting_human_approval'
    else 'changes_requested'
  end::company_ops.task_status;

  if v_verdict = 'approved_for_owner' then
    perform public.company_os_record_completed_work(payload->'completedWork');
  end if;

  update company_ops.tasks
     set status = v_next_status,
         review_cycle_count = review_cycle_count + 1,
         lease_worker_id = null,
         lease_expires_at = null
   where id = v_task.id;

  perform public.company_os_append_audit_events(
    coalesce(payload->'auditEvents', '[]'::jsonb)
  );
  return true;
end;
$$;

revoke all on function public.company_os_record_review(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_record_review(jsonb) to service_role;

-- Artifacts join the state the dashboard loads.
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
    'audit_events', coalesce((select jsonb_agg(to_jsonb(e) order by e.sequence)
      from company_ops.audit_events e), '[]'::jsonb)
  );
$$;

revoke all on function public.company_os_load() from public, anon, authenticated;
grant execute on function public.company_os_load() to service_role;

commit;
