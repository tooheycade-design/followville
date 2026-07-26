-- PROPOSAL ONLY. Do not apply without explicit owner approval.
-- Private source-of-truth tables for the Followville Company OS control plane.

begin;

create schema if not exists company_ops;
revoke all on schema company_ops from public, anon, authenticated;

create type company_ops.actor_type as enum ('human', 'agent', 'system');
create type company_ops.task_status as enum (
  'proposed',
  'planned',
  'approved_for_work',
  'queued',
  'assigned',
  'in_progress',
  'blocked',
  'awaiting_review',
  'changes_requested',
  'awaiting_human_approval',
  'approved',
  'rejected',
  'merged',
  'deployed',
  'canceled',
  'failed'
);
create type company_ops.risk_level as enum ('low', 'medium', 'high', 'critical');
create type company_ops.approval_status as enum (
  'pending',
  'approved',
  'rejected',
  'changes_requested',
  'expired',
  'canceled'
);
create type company_ops.capability as enum (
  'repository_read',
  'repository_write',
  'git_branch_create',
  'git_commit',
  'git_push_review_branch',
  'pull_request_create',
  'test_execute',
  'browser_preview',
  'blender_preview',
  'database_read_development',
  'database_migration_prepare',
  'model_invoke',
  'memory_write',
  'message_send',
  'production_merge',
  'production_deploy',
  'production_database_write',
  'canonical_world_growth',
  'public_communication',
  'social_publish',
  'payment_charge',
  'price_change',
  'destructive_delete'
);

create table company_ops.organizations (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  name text not null check (length(name) between 1 and 120),
  constitution_version text not null,
  constitution_ratified_at timestamptz,
  created_at timestamptz not null default now()
);

create table company_ops.organization_members (
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  role text not null check (role in ('owner', 'operator', 'auditor', 'viewer')),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  primary key (organization_id, user_id)
);

create table company_ops.projects (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  slug text not null,
  name text not null,
  repository text not null,
  production_locked boolean not null default true,
  created_at timestamptz not null default now(),
  unique (organization_id, slug),
  unique (organization_id, id)
);

create table company_ops.agent_profiles (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  slug text not null,
  name text not null,
  role text not null,
  profile jsonb not null check (jsonb_typeof(profile) = 'object'),
  prompt_version text not null,
  active boolean not null default true,
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, slug, version),
  unique (organization_id, id)
);

create table company_ops.goals (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  created_by_user_id uuid not null references auth.users(id) on delete restrict,
  title text not null check (length(title) between 1 and 180),
  objective text not null,
  success_definition text not null,
  constraints jsonb not null default '[]'::jsonb check (jsonb_typeof(constraints) = 'array'),
  risk_level company_ops.risk_level not null,
  budget_usd_micros bigint not null default 0 check (budget_usd_micros >= 0),
  status text not null check (
    status in ('draft', 'planning', 'active', 'awaiting_approval', 'completed', 'rejected', 'canceled')
  ),
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, project_id, id),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict
);

create table company_ops.tasks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  goal_id uuid not null,
  parent_task_id uuid,
  title text not null check (length(title) between 1 and 180),
  objective text not null,
  reason text not null,
  status company_ops.task_status not null default 'proposed',
  priority smallint not null default 50 check (priority between 0 and 100),
  risk_level company_ops.risk_level not null,
  assigned_agent_id uuid,
  reviewer_agent_id uuid,
  dependency_ids uuid[] not null default '{}',
  acceptance_criteria jsonb not null check (jsonb_typeof(acceptance_criteria) = 'array'),
  allowed_capabilities company_ops.capability[] not null default '{}',
  repository_scopes jsonb not null default '[]'::jsonb check (jsonb_typeof(repository_scopes) = 'array'),
  budget_usd_micros bigint not null default 0 check (budget_usd_micros >= 0),
  estimated_cost_usd_micros bigint not null default 0 check (estimated_cost_usd_micros >= 0),
  actual_cost_usd_micros bigint not null default 0 check (actual_cost_usd_micros >= 0),
  retry_count smallint not null default 0 check (retry_count >= 0),
  review_cycle_count smallint not null default 0 check (review_cycle_count >= 0),
  branch_name text,
  expected_outputs jsonb not null check (jsonb_typeof(expected_outputs) = 'array'),
  test_requirements jsonb not null default '[]'::jsonb check (jsonb_typeof(test_requirements) = 'array'),
  approval_required boolean not null default true,
  version integer not null default 1 check (version > 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (assigned_agent_id is null or assigned_agent_id is distinct from reviewer_agent_id),
  unique (organization_id, id),
  unique (organization_id, project_id, id),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, goal_id)
    references company_ops.goals (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, project_id, parent_task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, assigned_agent_id)
    references company_ops.agent_profiles (organization_id, id) on delete restrict,
  foreign key (organization_id, reviewer_agent_id)
    references company_ops.agent_profiles (organization_id, id) on delete restrict
);

create index tasks_project_status_priority_idx
  on company_ops.tasks (project_id, status, priority desc, created_at);
create index tasks_assigned_agent_status_idx
  on company_ops.tasks (assigned_agent_id, status)
  where assigned_agent_id is not null;

create table company_ops.runs (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  task_id uuid not null,
  agent_id uuid not null,
  reviewer_agent_id uuid,
  trigger text not null check (trigger in ('human', 'event', 'schedule', 'retry', 'message')),
  mode text not null check (mode in ('simulation', 'execute')),
  status text not null check (
    status in ('created', 'policy_check', 'budget_reserved', 'running', 'paused',
      'awaiting_review', 'completed', 'failed', 'canceled')
  ),
  model_provider text,
  model_id text,
  prompt_version text not null,
  context_manifest_digest text not null,
  workspace_id uuid,
  budget_reservation_usd_micros bigint not null default 0 check (budget_reservation_usd_micros >= 0),
  actual_cost_usd_micros bigint not null default 0 check (actual_cost_usd_micros >= 0),
  retry_count smallint not null default 0 check (retry_count >= 0),
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null default now(),
  unique (organization_id, id),
  unique (organization_id, project_id, id),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, agent_id)
    references company_ops.agent_profiles (organization_id, id) on delete restrict,
  foreign key (organization_id, reviewer_agent_id)
    references company_ops.agent_profiles (organization_id, id) on delete restrict
);

create index runs_task_created_idx on company_ops.runs (task_id, created_at desc);
create index runs_active_idx on company_ops.runs (status, created_at)
  where status in ('created', 'policy_check', 'budget_reserved', 'running', 'paused', 'awaiting_review');

create table company_ops.messages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  task_id uuid,
  thread_id uuid not null,
  sender_type company_ops.actor_type not null,
  sender_id uuid not null,
  recipient_type company_ops.actor_type not null,
  recipient_id uuid not null,
  message_type text not null,
  priority text not null check (priority in ('low', 'normal', 'high', 'urgent')),
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  fingerprint text not null,
  status text not null check (status in ('created', 'delivered', 'read', 'resolved', 'expired')),
  created_at timestamptz not null default now(),
  expires_at timestamptz,
  unique (thread_id, fingerprint),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict
);

create index messages_recipient_status_idx
  on company_ops.messages (recipient_type, recipient_id, status, created_at);

create table company_ops.artifacts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  task_id uuid,
  run_id uuid,
  artifact_type text not null,
  storage_reference text not null,
  content_digest text not null,
  media_type text not null,
  metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now(),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, project_id, run_id)
    references company_ops.runs (organization_id, project_id, id) on delete restrict
);

create table company_ops.approval_requests (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  task_id uuid not null,
  run_id uuid,
  requested_by_type company_ops.actor_type not null,
  requested_by_id uuid not null,
  action company_ops.capability not null,
  summary text not null,
  reason text not null,
  scope_digest text not null,
  commit_sha text,
  evidence_artifact_ids uuid[] not null default '{}',
  tests_completed jsonb not null default '[]'::jsonb check (jsonb_typeof(tests_completed) = 'array'),
  risk_level company_ops.risk_level not null,
  reversible boolean not null,
  rollback_plan text not null,
  estimated_cost_usd_micros bigint not null default 0 check (estimated_cost_usd_micros >= 0),
  recommendation text not null check (recommendation in ('approve', 'reject', 'request_changes')),
  alternatives jsonb not null default '[]'::jsonb check (jsonb_typeof(alternatives) = 'array'),
  required_approvals smallint not null default 1 check (required_approvals between 1 and 2),
  required_role text not null default 'owner' check (required_role in ('owner', 'operator')),
  status company_ops.approval_status not null default 'pending'
    check (status = 'pending'),
  idempotency_key text not null unique,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  check (
    action not in ('production_merge', 'production_deploy')
    or commit_sha ~ '^(?:[0-9a-f]{40}|[0-9a-f]{64})$'
  ),
  check (
    action not in (
      'production_merge',
      'production_deploy',
      'production_database_write',
      'canonical_world_growth',
      'public_communication',
      'social_publish',
      'payment_charge',
      'price_change',
      'destructive_delete'
    )
    or required_role = 'owner'
  ),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, project_id, run_id)
    references company_ops.runs (organization_id, project_id, id) on delete restrict
);

create index approval_requests_pending_idx
  on company_ops.approval_requests (organization_id, created_at)
  where status = 'pending';

create table company_ops.approval_decisions (
  id uuid primary key default gen_random_uuid(),
  approval_request_id uuid not null references company_ops.approval_requests(id) on delete restrict,
  decided_by_user_id uuid not null references auth.users(id) on delete restrict,
  decision text not null check (decision in ('approve', 'reject', 'request_changes')),
  comment text not null,
  request_scope_digest text not null,
  decided_at timestamptz not null default now(),
  unique (approval_request_id, decided_by_user_id)
);

create function company_ops.validate_approval_decision()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  request_record company_ops.approval_requests%rowtype;
begin
  select *
    into request_record
    from company_ops.approval_requests
    where id = new.approval_request_id
    for update;

  if not found then
    raise exception 'approval request does not exist';
  end if;
  if request_record.status <> 'pending' then
    raise exception 'approval request is not pending';
  end if;
  if request_record.expires_at <= now() then
    raise exception 'approval request has expired';
  end if;
  if new.request_scope_digest <> request_record.scope_digest then
    raise exception 'approval scope digest does not match';
  end if;
  if exists (
    select 1
      from company_ops.approval_decisions
      where approval_request_id = request_record.id
        and decision in ('reject', 'request_changes')
  ) then
    raise exception 'approval request already has a terminal decision';
  end if;
  if (
    select count(*) >= request_record.required_approvals
      from company_ops.approval_decisions
      where approval_request_id = request_record.id
        and decision = 'approve'
  ) then
    raise exception 'approval request already has enough approvals';
  end if;
  if not exists (
    select 1
      from company_ops.organization_members
      where organization_id = request_record.organization_id
        and user_id = new.decided_by_user_id
        and role = request_record.required_role
        and active
  ) then
    raise exception 'user is not an active authorized approver';
  end if;
  new.decided_at := now();
  return new;
end;
$$;

create trigger approval_decisions_validate
before insert on company_ops.approval_decisions
for each row execute function company_ops.validate_approval_decision();

create view company_ops.approval_request_states as
select
  request.id as approval_request_id,
  case
    when request.expires_at <= now() then 'expired'::company_ops.approval_status
    when exists (
      select 1
        from company_ops.approval_decisions decision
        where decision.approval_request_id = request.id
          and decision.decision = 'reject'
    ) then 'rejected'::company_ops.approval_status
    when exists (
      select 1
        from company_ops.approval_decisions decision
        where decision.approval_request_id = request.id
          and decision.decision = 'request_changes'
    ) then 'changes_requested'::company_ops.approval_status
    when (
      select count(distinct decision.decided_by_user_id)
        from company_ops.approval_decisions decision
        where decision.approval_request_id = request.id
          and decision.decision = 'approve'
    ) >= request.required_approvals then 'approved'::company_ops.approval_status
    else 'pending'::company_ops.approval_status
  end as status
from company_ops.approval_requests request;

create table company_ops.memories (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid,
  memory_type text not null check (
    memory_type in ('company', 'project', 'decision', 'task', 'agent', 'temporary')
  ),
  subject text not null,
  body text not null,
  source_type text not null,
  source_reference text not null,
  source_digest text not null,
  confidence text not null check (
    confidence in ('confirmed', 'likely', 'uncertain', 'requires_human_verification')
  ),
  status text not null check (status in ('active', 'deprecated', 'superseded', 'incorrect', 'archived')),
  version integer not null check (version > 0),
  tags text[] not null default '{}',
  created_by_type company_ops.actor_type not null,
  created_by_id uuid not null,
  created_at timestamptz not null default now(),
  expires_at timestamptz,
  superseded_by_id uuid,
  unique (organization_id, id),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, superseded_by_id)
    references company_ops.memories (organization_id, id) on delete restrict
);

create index memories_lookup_idx
  on company_ops.memories (organization_id, project_id, memory_type, status, created_at desc);

create table company_ops.budget_policies (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  scope_type text not null check (scope_type in ('organization', 'project', 'agent', 'task', 'provider')),
  scope_id text not null,
  period text not null check (period in ('task', 'day', 'week', 'month')),
  warning_usd_micros bigint not null check (warning_usd_micros >= 0),
  hard_limit_usd_micros bigint not null check (hard_limit_usd_micros >= warning_usd_micros),
  max_calls integer not null check (max_calls >= 0),
  max_concurrent_runs integer not null check (max_concurrent_runs >= 0),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (organization_id, scope_type, scope_id, period)
);

create table company_ops.usage_ledger (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid not null,
  task_id uuid not null,
  run_id uuid not null,
  agent_id uuid not null,
  provider text not null,
  model text not null,
  input_tokens bigint not null check (input_tokens >= 0),
  output_tokens bigint not null check (output_tokens >= 0),
  cached_input_tokens bigint not null default 0 check (cached_input_tokens >= 0),
  estimated_cost_usd_micros bigint not null check (estimated_cost_usd_micros >= 0),
  actual_cost_usd_micros bigint check (actual_cost_usd_micros >= 0),
  provider_request_id text,
  recorded_at timestamptz not null default now(),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, project_id, run_id)
    references company_ops.runs (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, agent_id)
    references company_ops.agent_profiles (organization_id, id) on delete restrict
);

create index usage_ledger_org_recorded_idx
  on company_ops.usage_ledger (organization_id, recorded_at desc);
create index usage_ledger_agent_recorded_idx
  on company_ops.usage_ledger (agent_id, recorded_at desc);

create table company_ops.audit_events (
  sequence bigint generated always as identity primary key,
  id uuid not null unique default gen_random_uuid(),
  organization_id uuid not null references company_ops.organizations(id) on delete restrict,
  project_id uuid,
  task_id uuid,
  run_id uuid,
  actor_type company_ops.actor_type not null,
  actor_id uuid not null,
  action text not null,
  target_type text not null,
  target_id text not null,
  outcome text not null check (
    outcome in ('allowed', 'denied', 'approval_required', 'succeeded', 'failed')
  ),
  reason text not null,
  correlation_id uuid not null,
  idempotency_key text not null unique,
  request_digest text not null,
  result_digest text,
  evidence_artifact_ids uuid[] not null default '{}',
  created_at timestamptz not null default now(),
  foreign key (organization_id, project_id)
    references company_ops.projects (organization_id, id) on delete restrict,
  foreign key (organization_id, project_id, task_id)
    references company_ops.tasks (organization_id, project_id, id) on delete restrict,
  foreign key (organization_id, project_id, run_id)
    references company_ops.runs (organization_id, project_id, id) on delete restrict
);

create index audit_events_correlation_idx
  on company_ops.audit_events (correlation_id, sequence);
create index audit_events_task_idx
  on company_ops.audit_events (task_id, sequence)
  where task_id is not null;

create function company_ops.validate_task_update()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  transition_allowed boolean;
begin
  if old.status in (
    'awaiting_review',
    'awaiting_human_approval',
    'approved',
    'merged',
    'deployed',
    'rejected',
    'canceled'
  ) and (
    to_jsonb(new) - array['status', 'updated_at', 'version', 'actual_cost_usd_micros']
  ) is distinct from (
    to_jsonb(old) - array['status', 'updated_at', 'version', 'actual_cost_usd_micros']
  ) then
    raise exception 'reviewed task scope is immutable';
  end if;

  if new.status = old.status then
    return new;
  end if;

  transition_allowed := case old.status
    when 'proposed' then new.status in ('planned', 'canceled', 'rejected')
    when 'planned' then new.status in ('approved_for_work', 'canceled', 'rejected')
    when 'approved_for_work' then new.status in ('queued', 'canceled')
    when 'queued' then new.status in ('assigned', 'blocked', 'canceled', 'failed')
    when 'assigned' then new.status in ('in_progress', 'blocked', 'canceled', 'failed')
    when 'in_progress' then new.status in ('blocked', 'awaiting_review', 'canceled', 'failed')
    when 'blocked' then new.status in ('in_progress', 'canceled', 'failed')
    when 'awaiting_review' then new.status in ('changes_requested', 'awaiting_human_approval', 'failed')
    when 'changes_requested' then new.status in ('in_progress', 'canceled', 'failed')
    when 'awaiting_human_approval' then new.status in ('approved', 'rejected', 'changes_requested', 'canceled')
    when 'approved' then new.status in ('merged', 'canceled')
    when 'failed' then new.status in ('queued', 'canceled')
    when 'merged' then new.status = 'deployed'
    else false
  end;

  if not transition_allowed then
    raise exception 'invalid task transition: % -> %', old.status, new.status;
  end if;
  if new.status in ('approved', 'merged') and not exists (
    select 1
      from company_ops.approval_requests request
      join company_ops.approval_request_states state
        on state.approval_request_id = request.id
      where request.organization_id = new.organization_id
        and request.project_id = new.project_id
        and request.task_id = new.id
        and request.action = 'production_merge'
        and state.status = 'approved'
  ) then
    raise exception 'task does not have a current approved merge request';
  end if;
  if new.status = 'deployed' and not exists (
    select 1
      from company_ops.approval_requests request
      join company_ops.approval_request_states state
        on state.approval_request_id = request.id
      where request.organization_id = new.organization_id
        and request.project_id = new.project_id
        and request.task_id = new.id
        and request.action = 'production_deploy'
        and state.status = 'approved'
  ) then
    raise exception 'task does not have a current approved deployment request';
  end if;
  new.version := old.version + 1;
  new.updated_at := now();
  return new;
end;
$$;

create trigger tasks_validate_update
before update on company_ops.tasks
for each row execute function company_ops.validate_task_update();

create function company_ops.reject_immutable_mutation()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'company_ops.% is append-only', tg_table_name;
end;
$$;

create trigger audit_events_append_only
before update or delete on company_ops.audit_events
for each row execute function company_ops.reject_immutable_mutation();

create trigger audit_events_no_truncate
before truncate on company_ops.audit_events
for each statement execute function company_ops.reject_immutable_mutation();

create trigger approval_decisions_append_only
before update or delete on company_ops.approval_decisions
for each row execute function company_ops.reject_immutable_mutation();

create trigger approval_decisions_no_truncate
before truncate on company_ops.approval_decisions
for each statement execute function company_ops.reject_immutable_mutation();

create trigger approval_requests_append_only
before update or delete on company_ops.approval_requests
for each row execute function company_ops.reject_immutable_mutation();

create trigger approval_requests_no_truncate
before truncate on company_ops.approval_requests
for each statement execute function company_ops.reject_immutable_mutation();

revoke all on all tables in schema company_ops from public, anon, authenticated;
revoke all on all sequences in schema company_ops from public, anon, authenticated;
revoke all on all functions in schema company_ops from public, anon, authenticated;
alter default privileges in schema company_ops
  revoke all on tables from public, anon, authenticated;
alter default privileges in schema company_ops
  revoke all on sequences from public, anon, authenticated;
alter default privileges in schema company_ops
  revoke all on functions from public, anon, authenticated;

commit;
