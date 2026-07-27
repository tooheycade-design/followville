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
  v_existing uuid;
begin
  -- Idempotent: a worker that recorded the packet and then lost its lease
  -- must not create a second request for the same review cycle.
  select id into v_existing
    from company_ops.approval_requests
    where idempotency_key = v_request->>'idempotencyKey';
  if found then
    return jsonb_build_object('approvalRequestId', v_existing, 'created', false);
  end if;

  for v_artifact in select * from jsonb_array_elements(payload->'artifacts')
  loop
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
    )
    on conflict (id) do nothing;
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
  from public, anon, authenticated;
grant execute on function public.company_os_record_completed_work(jsonb) to service_role;

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
