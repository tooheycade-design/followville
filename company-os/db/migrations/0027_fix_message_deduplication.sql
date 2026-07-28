-- Qualify the function argument in the deduplication lookup. The messages
-- table also has a payload column, so an unqualified PL/pgSQL name is
-- ambiguous only when the insert reaches its duplicate fallback.

begin;

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

revoke all on function public.company_os_send_message(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_send_message(jsonb)
  to service_role;

commit;
