-- Lets an owner release work the Chief Executive held for their decision.
--
-- The CEO parks escalated intent as a `proposed` task and tells the owner it
-- is waiting for them. Nothing could then act on it: the approval tables map
-- an approval onto task status `approved`, and `proposed -> approved` is not a
-- legal transition. So the company could stop unsafe work but never resume it
-- once a human agreed. Six tasks were stranded that way.
--
-- A release is its own immutable authorization record rather than a reuse of
-- `approval_requests`, because it authorizes something different: not "this
-- finished work may go to production" but "this proposed work may begin, with
-- exactly these capabilities".
--
-- Two properties make an authorization non-transferable:
--
--   * It pins an authorization digest computed over the task as the owner saw
--     it. If the objective, capabilities, scopes, or risk change afterwards,
--     the digest no longer matches and the authorization does not apply.
--   * Granted capabilities must be a subset of what was proposed. An owner may
--     narrow the grant; nothing can widen it. This is what stops an approval
--     being silently reused for a broader task.
--
-- Releasing walks the task through its legal chain, proposed -> planned ->
-- approved_for_work -> queued, so the existing transition trigger validates
-- every step rather than being bypassed.

begin;

create table company_ops.task_release_authorizations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null
    references company_ops.organizations(id) on delete restrict,
  task_id uuid not null references company_ops.tasks(id) on delete restrict,
  decision text not null check (decision in ('release', 'reject')),
  -- What the owner was looking at. Recomputed and compared on every use.
  authorization_digest text not null,
  -- The capabilities actually authorized, which may be narrower than proposed.
  granted_capabilities company_ops.capability[] not null default '{}',
  proposed_capabilities company_ops.capability[] not null default '{}',
  decided_by_user_id uuid not null references auth.users(id) on delete restrict,
  comment text not null check (length(comment) between 1 and 4000),
  decided_at timestamptz not null default now()
);

create index task_release_authorizations_task_idx
  on company_ops.task_release_authorizations (task_id, decided_at desc);

-- Append-only, like every other decision record in this schema. An
-- authorization that can be edited afterwards is not evidence of anything.
create or replace function company_ops.block_release_authorization_change()
returns trigger
language plpgsql
as $$
begin
  raise exception 'task release authorizations are append-only';
end;
$$;

create trigger task_release_authorizations_immutable
  before update or delete on company_ops.task_release_authorizations
  for each row execute function company_ops.block_release_authorization_change();

alter table company_ops.task_release_authorizations enable row level security;

create or replace function public.company_os_decide_held_task(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  task_record company_ops.tasks;
  v_task_id uuid := (payload->>'taskId')::uuid;
  v_decision text := payload->>'decision';
  v_user uuid := (payload->>'decidedByUserId')::uuid;
  v_digest text := payload->>'authorizationDigest';
  v_comment text := payload->>'comment';
  v_granted company_ops.capability[];
  v_authorization uuid;
begin
  if v_decision not in ('release', 'reject') then
    raise exception 'unknown decision: %', v_decision;
  end if;

  -- Lock the task so two owners cannot release the same work concurrently.
  select * into task_record
    from company_ops.tasks
    where id = v_task_id
    for update;
  if not found then
    raise exception 'task % does not exist', v_task_id;
  end if;
  if task_record.status <> 'proposed' then
    raise exception 'task % is %, not proposed', v_task_id, task_record.status;
  end if;

  if not exists (
    select 1
      from company_ops.organization_members
      where organization_id = task_record.organization_id
        and user_id = v_user
        and role = 'owner'
        and active
  ) then
    raise exception 'user is not an active owner';
  end if;

  -- The owner decided about a specific task. If it changed since they looked,
  -- their decision is about something that no longer exists.
  --
  -- Checked against the task's own version rather than by recomputing a hash
  -- here: a digest agreed between application and database has to be produced
  -- byte-identically in two languages, and the day that drifts this check
  -- starts passing or failing for reasons unrelated to the task. `version` is
  -- incremented by every write, so it answers the actual question. The digest
  -- the application computed is still stored, as the durable record of what
  -- was put in front of the owner.
  if task_record.version is distinct from (payload->>'expectedVersion')::integer then
    raise exception 'the task changed after it was reviewed; re-read it before deciding';
  end if;

  v_granted := coalesce(
    (select array_agg(value::company_ops.capability)
       from jsonb_array_elements_text(payload->'grantedCapabilities') as value),
    '{}'::company_ops.capability[]
  );

  if v_decision = 'release' then
    -- An owner may narrow a grant. Nothing may widen it, which is what keeps
    -- one authorization from covering a broader task than the one reviewed.
    if exists (
      select 1 from unnest(v_granted) as granted
      where granted <> all (task_record.allowed_capabilities)
    ) then
      raise exception 'a release cannot grant capabilities the task did not propose';
    end if;
    if array_length(v_granted, 1) is null then
      raise exception 'a release must grant at least one capability';
    end if;
  end if;

  insert into company_ops.task_release_authorizations (
    organization_id, task_id, decision, authorization_digest,
    granted_capabilities, proposed_capabilities, decided_by_user_id, comment
  ) values (
    task_record.organization_id, v_task_id, v_decision, v_digest,
    case when v_decision = 'release' then v_granted else '{}'::company_ops.capability[] end,
    task_record.allowed_capabilities, v_user, v_comment
  )
  returning id into v_authorization;

  if v_decision = 'reject' then
    update company_ops.tasks
       set status = 'rejected', version = version + 1, updated_at = now()
     where id = v_task_id;
  else
    -- Walk the legal chain so the transition trigger checks each step rather
    -- than being stepped around.
    update company_ops.tasks
       set status = 'planned', allowed_capabilities = v_granted,
           version = version + 1, updated_at = now()
     where id = v_task_id;
    update company_ops.tasks
       set status = 'approved_for_work', version = version + 1, updated_at = now()
     where id = v_task_id;
    update company_ops.tasks
       set status = 'queued', version = version + 1, updated_at = now()
     where id = v_task_id;
  end if;

  return jsonb_build_object(
    'authorizationId', v_authorization,
    'taskId', v_task_id,
    'status', case when v_decision = 'reject' then 'rejected' else 'queued' end
  );
end;
$$;

revoke all on function public.company_os_decide_held_task(jsonb)
  from public, anon, authenticated;
grant execute on function public.company_os_decide_held_task(jsonb) to service_role;

commit;
