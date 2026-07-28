begin;

do $$
declare
  v_org uuid := '10000000-0000-4000-8000-000000000001';
  v_project uuid := '20000000-0000-4000-8000-000000000001';
  v_goal uuid;
  v_task uuid;
  v_sender uuid := '40000000-0000-4000-8000-000000000002';
  v_recipient uuid := '40000000-0000-4000-8000-000000000003';
  v_message uuid := gen_random_uuid();
  v_thread uuid := gen_random_uuid();
  v_result jsonb;
begin
  select id into v_goal
    from company_ops.goals
   where organization_id = v_org and project_id = v_project
   order by created_at desc limit 1;
  select id into v_task
    from company_ops.tasks
   where organization_id = v_org and project_id = v_project
   order by created_at desc limit 1;

  if v_goal is null or v_task is null then
    raise exception 'verification requires one existing goal and task';
  end if;

  v_result := public.company_os_send_message(jsonb_build_object(
    'id', v_message,
    'organizationId', v_org,
    'projectId', v_project,
    'goalId', v_goal,
    'taskId', v_task,
    'threadId', v_thread,
    'senderType', 'agent',
    'senderId', v_sender,
    'recipientType', 'agent',
    'recipientId', v_recipient,
    'type', 'evidence',
    'priority', 'normal',
    'requestedAction', 'Review the evidence and report only concrete defects.',
    'contextSummary', 'A bounded verification message.',
    'evidenceArtifactIds', jsonb_build_array(),
    'expectedOutput', 'A pass or evidence-backed findings.',
    'relatedFiles', jsonb_build_array('company-os/README.md'),
    'relatedCommits', jsonb_build_array(),
    'fingerprint', repeat('a', 64),
    'confidence', 'confirmed',
    'deadlineAt', clock_timestamp() + interval '1 hour',
    'createdAt', clock_timestamp(),
    'expiresAt', clock_timestamp() + interval '1 day'
  ));

  if v_result->>'id' <> v_message::text then
    raise exception 'message insert did not return its durable row';
  end if;

  v_result := public.company_os_send_message(jsonb_build_object(
    'id', gen_random_uuid(),
    'organizationId', v_org,
    'projectId', v_project,
    'goalId', v_goal,
    'taskId', v_task,
    'threadId', v_thread,
    'senderType', 'agent',
    'senderId', v_sender,
    'recipientType', 'agent',
    'recipientId', v_recipient,
    'type', 'evidence',
    'priority', 'normal',
    'requestedAction', 'Review the evidence and report only concrete defects.',
    'contextSummary', 'A bounded verification message.',
    'evidenceArtifactIds', jsonb_build_array(),
    'expectedOutput', 'A pass or evidence-backed findings.',
    'relatedFiles', jsonb_build_array('company-os/README.md'),
    'relatedCommits', jsonb_build_array(),
    'fingerprint', repeat('a', 64),
    'confidence', 'confirmed',
    'deadlineAt', clock_timestamp() + interval '1 hour',
    'createdAt', clock_timestamp(),
    'expiresAt', clock_timestamp() + interval '1 day'
  ));

  if v_result->>'id' <> v_message::text then
    raise exception 'message deduplication returned a different row';
  end if;

  perform public.company_os_transition_message(v_message, 'delivered');
  perform public.company_os_transition_message(v_message, 'read');
  perform public.company_os_transition_message(v_message, 'resolved');

  begin
    perform public.company_os_transition_message(v_message, 'delivered');
    raise exception 'resolved message was allowed to move backward';
  exception
    when others then
      if sqlerrm = 'resolved message was allowed to move backward' then
        raise;
      end if;
  end;

  begin
    update company_ops.messages
       set payload = jsonb_set(payload, '{contextSummary}', '"tampered"')
     where id = v_message;
    raise exception 'message content mutation was allowed';
  exception
    when others then
      if sqlerrm = 'message content mutation was allowed' then
        raise;
      end if;
  end;
end;
$$;

rollback;
