-- Transactional control-plane API for the Company OS.
--
-- Why this exists: `company_ops` is deliberately not exposed to the Data API,
-- so PostgREST cannot address its tables. Exposing the schema would also leave
-- every multi-table write non-atomic, because PostgREST has no cross-request
-- transaction. A goal simulation writes a goal, task, run, approval request,
-- and several audit events; a partial write would produce exactly the
-- inconsistent record this system exists to prevent.
--
-- These functions live in `public` so the client can call them, run as one
-- transaction each, and are revoked from every browser role. `company_ops`
-- itself stays unreachable from the Data API.

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
    'approval_requests', coalesce((select jsonb_agg(to_jsonb(a) order by a.created_at)
      from company_ops.approval_requests a), '[]'::jsonb),
    'approval_states', coalesce((select jsonb_agg(to_jsonb(s))
      from company_ops.approval_request_states s), '[]'::jsonb),
    'approval_decisions', coalesce((select jsonb_agg(to_jsonb(d) order by d.decided_at)
      from company_ops.approval_decisions d), '[]'::jsonb),
    'audit_events', coalesce((select jsonb_agg(to_jsonb(e) order by e.sequence)
      from company_ops.audit_events e), '[]'::jsonb)
  );
$$;

create or replace function public.company_os_append_audit_events(events jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into company_ops.audit_events (
    id, organization_id, project_id, task_id, run_id, actor_type, actor_id,
    action, target_type, target_id, outcome, reason, correlation_id,
    idempotency_key, request_digest, result_digest, evidence_artifact_ids,
    created_at
  )
  select
    (e->>'id')::uuid,
    (e->>'organizationId')::uuid,
    nullif(e->>'projectId', '')::uuid,
    nullif(e->>'taskId', '')::uuid,
    nullif(e->>'runId', '')::uuid,
    (e->>'actorType')::company_ops.actor_type,
    (e->>'actorId')::uuid,
    e->>'action',
    e->>'targetType',
    e->>'targetId',
    e->>'outcome',
    e->>'reason',
    (e->>'correlationId')::uuid,
    e->>'idempotencyKey',
    e->>'requestDigest',
    e->>'resultDigest',
    coalesce(
      (select array_agg(value::text::uuid)
         from jsonb_array_elements_text(e->'evidenceArtifactIds') as value),
      '{}'::uuid[]
    ),
    (e->>'createdAt')::timestamptz
  from jsonb_array_elements(events) as e;
end;
$$;

create or replace function public.company_os_record_goal_simulation(payload jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  g jsonb := payload->'goal';
  t jsonb := payload->'task';
  r jsonb := payload->'run';
  a jsonb := payload->'approvalRequest';
begin
  insert into company_ops.goals (
    id, organization_id, project_id, created_by_user_id, title, objective,
    success_definition, constraints, risk_level, budget_usd_micros, status,
    created_at
  ) values (
    (g->>'id')::uuid, (g->>'organizationId')::uuid, (g->>'projectId')::uuid,
    (g->>'createdByUserId')::uuid, g->>'title', g->>'objective',
    g->>'successDefinition', g->'constraints',
    (g->>'riskLevel')::company_ops.risk_level,
    (g->>'budgetUsdMicros')::bigint, g->>'status', (g->>'createdAt')::timestamptz
  );

  insert into company_ops.tasks (
    id, organization_id, project_id, goal_id, parent_task_id, title, objective,
    reason, status, priority, risk_level, assigned_agent_id, reviewer_agent_id,
    dependency_ids, acceptance_criteria, allowed_capabilities,
    repository_scopes, budget_usd_micros, estimated_cost_usd_micros,
    actual_cost_usd_micros, retry_count, review_cycle_count, branch_name,
    expected_outputs, test_requirements, approval_required, version,
    created_at, updated_at
  ) values (
    (t->>'id')::uuid, (t->>'organizationId')::uuid, (t->>'projectId')::uuid,
    (t->>'goalId')::uuid, nullif(t->>'parentTaskId', '')::uuid,
    t->>'title', t->>'objective', t->>'reason',
    (t->>'status')::company_ops.task_status,
    (t->>'priority')::smallint, (t->>'riskLevel')::company_ops.risk_level,
    nullif(t->>'assignedAgentId', '')::uuid,
    nullif(t->>'reviewerAgentId', '')::uuid,
    coalesce((select array_agg(value::text::uuid)
      from jsonb_array_elements_text(t->'dependencyIds') as value), '{}'::uuid[]),
    t->'acceptanceCriteria',
    coalesce((select array_agg(value::text::company_ops.capability)
      from jsonb_array_elements_text(t->'allowedCapabilities') as value),
      '{}'::company_ops.capability[]),
    t->'repositoryScopes',
    (t->>'budgetUsdMicros')::bigint, (t->>'estimatedCostUsdMicros')::bigint,
    (t->>'actualCostUsdMicros')::bigint, (t->>'retryCount')::smallint,
    (t->>'reviewCycleCount')::smallint, t->>'branchName',
    t->'expectedOutputs', t->'testRequirements',
    (t->>'approvalRequired')::boolean, (t->>'version')::integer,
    (t->>'createdAt')::timestamptz, (t->>'updatedAt')::timestamptz
  );

  insert into company_ops.runs (
    id, organization_id, project_id, task_id, agent_id, reviewer_agent_id,
    trigger, mode, status, model_provider, model_id, prompt_version,
    context_manifest_digest, workspace_id, budget_reservation_usd_micros,
    actual_cost_usd_micros, retry_count, started_at, completed_at
  ) values (
    (r->>'id')::uuid, (r->>'organizationId')::uuid, (r->>'projectId')::uuid,
    (r->>'taskId')::uuid, (r->>'agentId')::uuid,
    nullif(r->>'reviewerAgentId', '')::uuid,
    r->>'trigger', r->>'mode', r->>'status', r->>'modelProvider',
    r->>'modelId', r->>'promptVersion', r->>'contextManifestDigest',
    nullif(r->>'workspaceId', '')::uuid,
    (r->>'budgetReservationUsdMicros')::bigint,
    (r->>'actualCostUsdMicros')::bigint, (r->>'retryCount')::smallint,
    nullif(r->>'startedAt', '')::timestamptz,
    nullif(r->>'completedAt', '')::timestamptz
  );

  insert into company_ops.approval_requests (
    id, organization_id, project_id, task_id, run_id, requested_by_type,
    requested_by_id, action, summary, reason, scope_digest, commit_sha,
    evidence_artifact_ids, tests_completed, risk_level, reversible,
    rollback_plan, estimated_cost_usd_micros, recommendation, alternatives,
    required_approvals, required_role, idempotency_key, created_at, expires_at
  ) values (
    (a->>'id')::uuid, (a->>'organizationId')::uuid, (a->>'projectId')::uuid,
    (a->>'taskId')::uuid, nullif(a->>'runId', '')::uuid,
    (a->>'requestedByType')::company_ops.actor_type,
    (a->>'requestedById')::uuid, (a->>'action')::company_ops.capability,
    a->>'summary', a->>'reason', a->>'scopeDigest', a->>'commitSha',
    coalesce((select array_agg(value::text::uuid)
      from jsonb_array_elements_text(a->'evidenceArtifactIds') as value),
      '{}'::uuid[]),
    a->'testsCompleted', (a->>'riskLevel')::company_ops.risk_level,
    (a->>'reversible')::boolean, a->>'rollbackPlan',
    (a->>'estimatedCostUsdMicros')::bigint, a->>'recommendation',
    a->'alternatives', (a->>'requiredApprovals')::smallint,
    a->>'requiredRole', a->>'idempotencyKey',
    (a->>'createdAt')::timestamptz, (a->>'expiresAt')::timestamptz
  );

  perform public.company_os_append_audit_events(
    coalesce(payload->'auditEvents', '[]'::jsonb)
  );
end;
$$;

create or replace function public.company_os_record_approval_decision(payload jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  d jsonb := payload->'decision';
  t jsonb := payload->'updatedTask';
begin
  -- The approval_decisions trigger independently re-validates pending state,
  -- expiry, scope digest, prior terminal decisions, and that the decider is an
  -- active member holding the required role.
  insert into company_ops.approval_decisions (
    id, approval_request_id, decided_by_user_id, decision, comment,
    request_scope_digest
  ) values (
    (d->>'id')::uuid, (d->>'approvalRequestId')::uuid,
    (d->>'decidedByUserId')::uuid, d->>'decision', d->>'comment',
    d->>'requestScopeDigest'
  );

  if t is not null and jsonb_typeof(t) = 'object' then
    update company_ops.tasks
       set status = (t->>'status')::company_ops.task_status
     where id = (t->>'id')::uuid;
  end if;

  perform public.company_os_append_audit_events(
    jsonb_build_array(payload->'auditEvent')
  );
end;
$$;

revoke all on function public.company_os_load() from public, anon, authenticated;
revoke all on function public.company_os_append_audit_events(jsonb) from public, anon, authenticated;
revoke all on function public.company_os_record_goal_simulation(jsonb) from public, anon, authenticated;
revoke all on function public.company_os_record_approval_decision(jsonb) from public, anon, authenticated;

grant execute on function public.company_os_load() to service_role;
grant execute on function public.company_os_record_goal_simulation(jsonb) to service_role;
grant execute on function public.company_os_record_approval_decision(jsonb) to service_role;

commit;
