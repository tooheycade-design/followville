-- Source-backed, versioned, role-retrieved Followville memory.

begin;

alter table company_ops.memories
  add column category text not null,
  add column audience_roles text[] not null default array['owner'],
  add column supersedes_id uuid,
  add column correction_reason text;

alter table company_ops.memories
  add constraint memories_category_check check (category in (
    'current_state', 'identity', 'house_numbering', 'town_layout',
    'neighborhoods', 'roads', 'landmarks', 'founder_homes',
    'generation_rules', 'visual_style', 'brand_rules', 'asset_library',
    'website_architecture', 'multiplayer', 'authentication', 'claiming',
    'customization', 'limitations', 'known_bugs', 'content_history',
    'idea_history', 'milestones', 'monetization', 'priorities', 'roadmap',
    'technical_debt', 'incident'
  )),
  add constraint memories_source_digest_check
    check (source_digest ~ '^[0-9a-f]{64}$'),
  add constraint memories_audience_roles_check check (
    cardinality(audience_roles) between 1 and 12
    and array_position(audience_roles, null) is null
    and audience_roles <@ array[
      'owner', 'ceo', 'engineer', 'reviewer', 'researcher',
      'finance', 'growth', 'content'
    ]
  ),
  add constraint memories_supersedes_fk
    foreign key (organization_id, supersedes_id)
    references company_ops.memories(organization_id, id) on delete restrict,
  add constraint memories_correction_reason_check check (
    correction_reason is null or length(correction_reason) between 1 and 2000
  );

create unique index memories_one_active_subject_idx
  on company_ops.memories (
    organization_id,
    coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid),
    category, lower(subject)
  ) where status = 'active';

create index memories_role_tags_idx
  on company_ops.memories using gin (audience_roles, tags);

create or replace function company_ops.protect_memory_update()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if old.status = 'superseded'
     and new.status = 'superseded'
     and old.superseded_by_id is null
     and new.superseded_by_id is not null
     and new.id = old.id
     and new.organization_id = old.organization_id
     and new.project_id is not distinct from old.project_id
     and new.memory_type = old.memory_type
     and new.category = old.category
     and new.subject = old.subject
     and new.body = old.body
     and new.source_type = old.source_type
     and new.source_reference = old.source_reference
     and new.source_digest = old.source_digest
     and new.confidence = old.confidence
     and new.version = old.version
     and new.tags = old.tags
     and new.audience_roles = old.audience_roles
     and new.created_by_type = old.created_by_type
     and new.created_by_id = old.created_by_id
     and new.created_at = old.created_at
     and new.expires_at is not distinct from old.expires_at
     and new.supersedes_id is not distinct from old.supersedes_id
     and new.correction_reason is not distinct from old.correction_reason then
    return new;
  end if;

  if new.id <> old.id
     or new.organization_id <> old.organization_id
     or new.project_id is distinct from old.project_id
     or new.memory_type <> old.memory_type
     or new.category <> old.category
     or new.subject <> old.subject
     or new.body <> old.body
     or new.source_type <> old.source_type
     or new.source_reference <> old.source_reference
     or new.source_digest <> old.source_digest
     or new.confidence <> old.confidence
     or new.version <> old.version
     or new.tags <> old.tags
     or new.audience_roles <> old.audience_roles
     or new.created_by_type <> old.created_by_type
     or new.created_by_id <> old.created_by_id
     or new.created_at <> old.created_at
     or new.expires_at is distinct from old.expires_at
     or new.supersedes_id is distinct from old.supersedes_id
     or new.correction_reason is distinct from old.correction_reason then
    raise exception 'memory content and provenance are immutable';
  end if;
  if old.status <> 'active'
     or new.status not in ('superseded', 'deprecated', 'incorrect', 'archived') then
    raise exception 'invalid memory lifecycle transition';
  end if;
  return new;
end;
$$;

create trigger memories_protect_update
before update on company_ops.memories
for each row execute function company_ops.protect_memory_update();

create or replace function company_ops.reject_memory_removal()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  raise exception 'memory records are append-only and cannot be removed';
end;
$$;

create trigger memories_reject_delete
before delete on company_ops.memories
for each statement execute function company_ops.reject_memory_removal();

create trigger memories_reject_truncate
before truncate on company_ops.memories
for each statement execute function company_ops.reject_memory_removal();

create or replace function public.company_os_retrieve_memories(
  p_role text,
  p_query text default null,
  p_tags text[] default '{}',
  p_limit integer default 12
)
returns jsonb
language sql
security definer
set search_path = ''
as $$
  select coalesce(jsonb_agg(to_jsonb(ranked) - 'rank' order by ranked.rank desc), '[]'::jsonb)
  from (
    select memory.*,
      (
        case memory.confidence
          when 'confirmed' then 40
          when 'likely' then 25
          when 'uncertain' then 10
          else 0
        end
        + 8 * (
            select count(*)::integer
              from unnest(memory.tags) tag
             where tag = any(coalesce(p_tags, '{}'::text[]))
          )
        + case
            when nullif(btrim(p_query), '') is null then 0
            when to_tsvector('english', memory.subject || ' ' || memory.body)
              @@ websearch_to_tsquery('english', p_query) then 30
            else 0
          end
      ) as rank
    from company_ops.memories memory
    where memory.status = 'active'
      and (memory.expires_at is null or memory.expires_at > clock_timestamp())
      and p_role = any(memory.audience_roles)
    order by rank desc, memory.created_at desc
    limit greatest(1, least(p_limit, 25))
  ) ranked;
$$;

create or replace function public.company_os_correct_memory(payload jsonb)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_old company_ops.memories%rowtype;
  v_new company_ops.memories%rowtype;
  v_new_id uuid := coalesce(nullif(payload->>'id', '')::uuid, gen_random_uuid());
begin
  select memory.* into v_old
    from company_ops.memories memory
   where memory.id = (payload->>'memoryId')::uuid
   for update;
  if not found or v_old.status <> 'active' then
    raise exception 'active memory does not exist';
  end if;
  if (payload->>'expectedVersion')::integer <> v_old.version then
    raise exception 'memory changed after it was read';
  end if;
  if not exists (
    select 1 from company_ops.organization_members member
     where member.organization_id = v_old.organization_id
       and member.user_id = v_user
       and member.role = 'owner'
       and member.active
  ) then
    raise exception 'only an active owner may correct memory';
  end if;

  update company_ops.memories
     set status = 'superseded'
   where id = v_old.id;

  insert into company_ops.memories (
    id, organization_id, project_id, memory_type, category, subject, body,
    source_type, source_reference, source_digest, confidence, status, version,
    tags, audience_roles, created_by_type, created_by_id, created_at,
    expires_at, supersedes_id, correction_reason
  ) values (
    v_new_id, v_old.organization_id, v_old.project_id, v_old.memory_type,
    v_old.category, v_old.subject, payload->>'body', 'human',
    'owner-correction:' || v_user::text,
    encode(digest(convert_to(payload->>'body', 'UTF8'), 'sha256'), 'hex'),
    'confirmed', 'active', v_old.version + 1, v_old.tags,
    v_old.audience_roles, 'human', v_user, clock_timestamp(),
    nullif(payload->>'expiresAt', '')::timestamptz, v_old.id,
    payload->>'reason'
  ) returning * into v_new;

  update company_ops.memories
     set superseded_by_id = v_new.id
   where id = v_old.id;
  return to_jsonb(v_new);
end;
$$;

create or replace function public.company_os_load()
returns jsonb
language sql
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'goals', coalesce((select jsonb_agg(to_jsonb(g) order by g.created_at) from company_ops.goals g), '[]'::jsonb),
    'tasks', coalesce((select jsonb_agg(to_jsonb(t) order by t.created_at) from company_ops.tasks t), '[]'::jsonb),
    'runs', coalesce((select jsonb_agg(to_jsonb(r) order by r.created_at) from company_ops.runs r), '[]'::jsonb),
    'messages', coalesce((select jsonb_agg(to_jsonb(m) order by m.created_at) from company_ops.messages m), '[]'::jsonb),
    'memories', coalesce((select jsonb_agg(to_jsonb(m) order by m.created_at) from (
      select * from company_ops.memories order by created_at desc limit 500
    ) m), '[]'::jsonb),
    'approval_requests', coalesce((select jsonb_agg(to_jsonb(a) order by a.created_at) from company_ops.approval_requests a), '[]'::jsonb),
    'approval_states', coalesce((select jsonb_agg(to_jsonb(s)) from company_ops.approval_request_states s), '[]'::jsonb),
    'approval_decisions', coalesce((select jsonb_agg(to_jsonb(d) order by d.decided_at) from company_ops.approval_decisions d), '[]'::jsonb),
    'evidence_artifacts', coalesce((select jsonb_agg(to_jsonb(e) order by e.created_at) from company_ops.evidence_artifacts e), '[]'::jsonb),
    'worker_nodes', coalesce((select jsonb_agg(to_jsonb(w) order by w.started_at) from company_ops.worker_nodes w), '[]'::jsonb),
    'control_ticks', coalesce((select jsonb_agg(to_jsonb(c) order by c.created_at) from (
      select * from company_ops.control_ticks order by created_at desc limit 500
    ) c), '[]'::jsonb),
    'owner_notifications', coalesce((select jsonb_agg(to_jsonb(n) order by n.created_at) from (
      select * from company_ops.owner_notifications order by created_at desc limit 500
    ) n), '[]'::jsonb),
    'audit_events', coalesce((select jsonb_agg(to_jsonb(e) order by e.sequence) from company_ops.audit_events e), '[]'::jsonb)
  );
$$;

revoke all on company_ops.memories from public, anon, authenticated, service_role;
revoke all on function company_ops.protect_memory_update() from public, anon, authenticated, service_role;
revoke all on function company_ops.reject_memory_removal() from public, anon, authenticated, service_role;
revoke all on function public.company_os_retrieve_memories(text, text, text[], integer) from public, anon, authenticated;
revoke all on function public.company_os_correct_memory(jsonb) from public, anon, service_role;
revoke all on function public.company_os_load() from public, anon, authenticated;
grant execute on function public.company_os_retrieve_memories(text, text, text[], integer) to service_role;
grant execute on function public.company_os_correct_memory(jsonb) to authenticated;
grant execute on function public.company_os_load() to service_role;

commit;
