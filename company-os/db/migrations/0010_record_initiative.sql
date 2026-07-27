-- Records a CEO initiative: one goal and every task it produced.
--
-- `company_os_record_planned_goal` writes exactly one goal and one task, so an
-- initiative with several tasks would need several calls and could half-apply.
-- This writes the whole plan in one transaction, so an initiative is never
-- partially present.

begin;

create or replace function public.company_os_record_initiative(payload jsonb)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  g jsonb := payload->'goal';
  t jsonb;
  written integer := 0;
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

  for t in select * from jsonb_array_elements(payload->'tasks')
  loop
    insert into company_ops.tasks (
      id, organization_id, project_id, goal_id, parent_task_id, title,
      objective, reason, status, priority, risk_level, assigned_agent_id,
      reviewer_agent_id, dependency_ids, acceptance_criteria,
      allowed_capabilities, repository_scopes, budget_usd_micros,
      estimated_cost_usd_micros, actual_cost_usd_micros, retry_count,
      review_cycle_count, branch_name, expected_outputs, test_requirements,
      approval_required, version, created_at, updated_at
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
    written := written + 1;
  end loop;

  perform public.company_os_append_audit_events(
    coalesce(payload->'auditEvents', '[]'::jsonb)
  );
  return written;
end;
$$;

revoke all on function public.company_os_record_initiative(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_record_initiative(jsonb)
  to service_role;

commit;
