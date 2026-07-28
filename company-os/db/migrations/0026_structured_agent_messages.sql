-- Durable, bounded agent-to-agent communication.
--
-- Messages carry context and requests, never authority. They cannot grant a
-- capability, approve an action, or move a task. The database validates both
-- participants, task/goal scope, evidence scope, expiry, and deduplication.

begin;

alter table company_ops.messages
  add column goal_id uuid,
  add column deadline_at timestamptz,
  add column confidence text not null default 'uncertain',
  add column updated_at timestamptz not null default clock_timestamp();

update company_ops.messages message
   set goal_id = task.goal_id
  from company_ops.tasks task
 where message.task_id = task.id
   and message.organization_id = task.organization_id
   and message.project_id = task.project_id
   and message.goal_id is null;

alter table company_ops.messages
  add constraint messages_goal_scope_fk
  foreign key (organization_id, project_id, goal_id)
  references company_ops.goals (organization_id, project_id, id)
  on delete restrict,
  add constraint messages_confidence_check
  check (confidence in (
    'confirmed', 'likely', 'uncertain', 'requires_human_verification'
  )),
  add constraint messages_message_type_check
  check (message_type in (
    'task_request', 'task_assignment', 'clarification_request',
    'status_update', 'blocker', 'evidence', 'recommendation',
    'review_request', 'changes_requested', 'approval_request',
    'budget_request', 'incident', 'task_complete', 'task_failed',
    'handoff', 'escalation', 'decision_needed'
  )),
  add constraint messages_fingerprint_check
  check (fingerprint ~ '^[0-9a-f]{64}$'),
  add constraint messages_payload_contract_check
  check (
    jsonb_typeof(payload->'contextSummary') = 'string'
    and length(payload->>'contextSummary') between 1 and 8000
    and (
      not (payload ? 'requestedAction')
      or payload->'requestedAction' = 'null'::jsonb
      or (
        jsonb_typeof(payload->'requestedAction') = 'string'
        and length(payload->>'requestedAction') between 1 and 2000
      )
    )
    and jsonb_typeof(payload->'evidenceArtifactIds') = 'array'
    and jsonb_array_length(payload->'evidenceArtifactIds') <= 25
    and (
      not (payload ? 'expectedOutput')
      or payload->'expectedOutput' = 'null'::jsonb
      or (
        jsonb_typeof(payload->'expectedOutput') = 'string'
        and length(payload->>'expectedOutput') between 1 and 2000
      )
    )
    and jsonb_typeof(payload->'relatedFiles') = 'array'
    and jsonb_array_length(payload->'relatedFiles') <= 50
    and jsonb_typeof(payload->'relatedCommits') = 'array'
    and jsonb_array_length(payload->'relatedCommits') <= 25
    and pg_column_size(payload) <= 32768
  ),
  add constraint messages_expiry_check
  check (
    expires_at is not null
    and expires_at > created_at
    and expires_at <= created_at + interval '30 days'
    and (deadline_at is null or deadline_at <= expires_at)
  ),
  add constraint messages_distinct_participants_check
  check (
    sender_type <> recipient_type
    or sender_id <> recipient_id
  );

create index messages_scope_created_idx
  on company_ops.messages (
    organization_id, project_id, goal_id, task_id, created_at desc
  );

create or replace function company_ops.validate_structured_message()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  evidence_id uuid;
begin
  if new.sender_type = 'agent' then
    if not exists (
      select 1
        from company_ops.agent_profiles agent
       where agent.id = new.sender_id
         and agent.organization_id = new.organization_id
         and agent.active
         and 'message_send'::company_ops.capability = any(agent.capabilities)
    ) then
      raise exception 'message sender is not an active agent with message_send';
    end if;
  elsif new.sender_type = 'human' then
    if not exists (
      select 1
        from company_ops.organization_members member
       where member.user_id = new.sender_id
         and member.organization_id = new.organization_id
         and member.active
    ) then
      raise exception 'message sender is not an active organization member';
    end if;
  else
    raise exception 'system actors cannot originate structured messages';
  end if;

  if new.recipient_type = 'agent' then
    if not exists (
      select 1
        from company_ops.agent_profiles agent
       where agent.id = new.recipient_id
         and agent.organization_id = new.organization_id
         and agent.active
    ) then
      raise exception 'message recipient is not an active organization agent';
    end if;
  elsif new.recipient_type = 'human' then
    if not exists (
      select 1
        from company_ops.organization_members member
       where member.user_id = new.recipient_id
         and member.organization_id = new.organization_id
         and member.active
    ) then
      raise exception 'message recipient is not an active organization member';
    end if;
  else
    raise exception 'system actors cannot receive structured messages';
  end if;

  if new.task_id is not null and not exists (
    select 1
      from company_ops.tasks task
     where task.id = new.task_id
       and task.organization_id = new.organization_id
       and task.project_id = new.project_id
       and (new.goal_id is null or task.goal_id = new.goal_id)
  ) then
    raise exception 'message task does not belong to its project and goal scope';
  end if;

  for evidence_id in
    select value::text::uuid
      from jsonb_array_elements_text(new.payload->'evidenceArtifactIds') value
  loop
    if not exists (
      select 1
        from company_ops.evidence_artifacts artifact
       where artifact.id = evidence_id
         and artifact.organization_id = new.organization_id
         and artifact.project_id = new.project_id
         and (new.goal_id is null or artifact.goal_id = new.goal_id)
         and (new.task_id is null or artifact.task_id = new.task_id)
    ) then
      raise exception 'message evidence does not belong to its scope';
    end if;
  end loop;

  new.updated_at := clock_timestamp();
  return new;
exception
  when invalid_text_representation then
    raise exception 'message evidence contains an invalid artifact id';
end;
$$;

create trigger messages_validate_insert
before insert on company_ops.messages
for each row execute function company_ops.validate_structured_message();

create or replace function company_ops.protect_structured_message()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.project_id <> old.project_id
     or new.task_id is distinct from old.task_id
     or new.goal_id is distinct from old.goal_id
     or new.thread_id <> old.thread_id
     or new.sender_type <> old.sender_type
     or new.sender_id <> old.sender_id
     or new.recipient_type <> old.recipient_type
     or new.recipient_id <> old.recipient_id
     or new.message_type <> old.message_type
     or new.priority <> old.priority
     or new.payload <> old.payload
     or new.fingerprint <> old.fingerprint
     or new.deadline_at is distinct from old.deadline_at
     or new.confidence <> old.confidence
     or new.created_at <> old.created_at
     or new.expires_at <> old.expires_at then
    raise exception 'structured message content and scope are immutable';
  end if;

  if not (
    (old.status = 'created' and new.status in ('delivered', 'read', 'resolved', 'expired'))
    or (old.status = 'delivered' and new.status in ('read', 'resolved', 'expired'))
    or (old.status = 'read' and new.status in ('resolved', 'expired'))
    or (old.status = new.status)
  ) then
    raise exception 'invalid structured message status transition';
  end if;

  new.updated_at := clock_timestamp();
  return new;
end;
$$;

create trigger messages_protect_update
before update on company_ops.messages
for each row execute function company_ops.protect_structured_message();

create or replace function company_ops.reject_structured_message_removal()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'structured messages are append-only and cannot be removed';
end;
$$;

create trigger messages_reject_delete
before delete on company_ops.messages
for each statement execute function company_ops.reject_structured_message_removal();

create trigger messages_reject_truncate
before truncate on company_ops.messages
for each statement execute function company_ops.reject_structured_message_removal();

create or replace function public.company_os_send_message(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  message_record company_ops.messages%rowtype;
begin
  if payload is null or jsonb_typeof(payload) <> 'object' then
    raise exception 'message payload must be an object';
  end if;

  insert into company_ops.messages (
    id, organization_id, project_id, goal_id, task_id, thread_id,
    sender_type, sender_id, recipient_type, recipient_id, message_type,
    priority, payload, fingerprint, status, deadline_at, confidence,
    created_at, expires_at
  ) values (
    (payload->>'id')::uuid,
    (payload->>'organizationId')::uuid,
    (payload->>'projectId')::uuid,
    nullif(payload->>'goalId', '')::uuid,
    nullif(payload->>'taskId', '')::uuid,
    (payload->>'threadId')::uuid,
    (payload->>'senderType')::company_ops.actor_type,
    (payload->>'senderId')::uuid,
    (payload->>'recipientType')::company_ops.actor_type,
    (payload->>'recipientId')::uuid,
    payload->>'type',
    payload->>'priority',
    jsonb_build_object(
      'requestedAction', payload->'requestedAction',
      'contextSummary', payload->'contextSummary',
      'evidenceArtifactIds', coalesce(payload->'evidenceArtifactIds', '[]'::jsonb),
      'expectedOutput', payload->'expectedOutput',
      'relatedFiles', coalesce(payload->'relatedFiles', '[]'::jsonb),
      'relatedCommits', coalesce(payload->'relatedCommits', '[]'::jsonb)
    ),
    payload->>'fingerprint',
    'created',
    nullif(payload->>'deadlineAt', '')::timestamptz,
    payload->>'confidence',
    (payload->>'createdAt')::timestamptz,
    (payload->>'expiresAt')::timestamptz
  )
  on conflict (thread_id, fingerprint) do nothing
  returning * into message_record;

  if message_record.id is null then
    select *
     into message_record
      from company_ops.messages message
     where message.thread_id = ($1->>'threadId')::uuid
       and message.fingerprint = $1->>'fingerprint';
  end if;

  return to_jsonb(message_record);
end;
$$;

create or replace function public.company_os_transition_message(
  message_id uuid,
  next_status text
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  message_record company_ops.messages%rowtype;
begin
  if next_status not in ('delivered', 'read', 'resolved', 'expired') then
    raise exception 'unsupported structured message status';
  end if;

  update company_ops.messages
     set status = next_status
   where id = message_id
  returning * into message_record;

  if message_record.id is null then
    raise exception 'structured message does not exist';
  end if;
  return to_jsonb(message_record);
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
    'messages', coalesce((select jsonb_agg(to_jsonb(m) order by m.created_at)
      from company_ops.messages m), '[]'::jsonb),
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

revoke all on company_ops.messages
  from public, anon, authenticated, service_role;
revoke all on function company_ops.validate_structured_message()
  from public, anon, authenticated, service_role;
revoke all on function company_ops.protect_structured_message()
  from public, anon, authenticated, service_role;
revoke all on function company_ops.reject_structured_message_removal()
  from public, anon, authenticated, service_role;
revoke all on function public.company_os_send_message(jsonb)
  from public, anon, authenticated;
revoke all on function public.company_os_transition_message(uuid, text)
  from public, anon, authenticated;
revoke all on function public.company_os_load()
  from public, anon, authenticated;

grant execute on function public.company_os_send_message(jsonb)
  to service_role;
grant execute on function public.company_os_transition_message(uuid, text)
  to service_role;
grant execute on function public.company_os_load()
  to service_role;

commit;
