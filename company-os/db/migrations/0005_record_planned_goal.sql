-- Records an owner goal as queued work.
--
-- `company_os_record_goal_simulation` writes a goal that has already been
-- walked to a pending approval, so it requires a run and an approval request.
-- Planned work has neither yet: it is a goal and one task waiting for a worker
-- to lease it. Both rows are written in one transaction so a task can never
-- exist without its goal.

begin;

create or replace function public.company_os_record_planned_goal(payload jsonb)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  g jsonb := payload->'goal';
  t jsonb := payload->'task';
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
    (g->>'budgetUsdMicros')::bigint, g->>'status',
    (g->>'createdAt')::timestamptz
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

  perform public.company_os_append_audit_events(
    coalesce(payload->'auditEvents', '[]'::jsonb)
  );
end;
$$;

revoke all on function public.company_os_record_planned_goal(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_record_planned_goal(jsonb)
  to service_role;

commit;
