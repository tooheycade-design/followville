-- Private, durable evidence for browser, Blender, test, and review outputs.
--
-- The object bucket holds bytes. `evidence_artifacts` remains the immutable
-- authority for who produced them, which run they belong to, their digest,
-- their visibility, and whether the dashboard may render them inline.

begin;

alter table company_ops.evidence_artifacts
  add column goal_id uuid,
  add column visibility text not null default 'owner_only',
  add column contains_sensitive_data boolean not null default false,
  add column safe_to_display boolean not null default false,
  add column retention_policy text not null default 'approval_record';

alter table company_ops.evidence_artifacts
  disable trigger evidence_artifacts_immutable;

update company_ops.evidence_artifacts artifact
   set goal_id = task.goal_id
  from company_ops.tasks task
 where task.id = artifact.task_id
   and task.organization_id = artifact.organization_id
   and task.project_id = artifact.project_id;

alter table company_ops.evidence_artifacts
  enable trigger evidence_artifacts_immutable;

alter table company_ops.evidence_artifacts
  alter column goal_id set not null,
  add constraint evidence_artifacts_visibility_check
    check (visibility in ('owner_only', 'company_internal', 'public')),
  add constraint evidence_artifacts_retention_check
    check (retention_policy in ('approval_record', 'temporary_preview', 'permanent')),
  add constraint evidence_artifacts_sensitive_display_check
    check (not contains_sensitive_data or not safe_to_display),
  add constraint evidence_artifacts_goal_fk
    foreign key (organization_id, project_id, goal_id)
    references company_ops.goals (organization_id, project_id, id)
    on delete restrict;

alter table company_ops.evidence_artifacts
  drop constraint evidence_artifacts_kind_check,
  add constraint evidence_artifacts_kind_check check (
    kind in (
      'screenshot', 'render', 'recording', 'log', 'patch', 'report',
      'trace', 'model', 'performance'
    )
  ),
  add constraint evidence_artifacts_location_check check (
    jsonb_typeof(location) = 'object'
    and (
      (
        location->>'kind' = 'git'
        and location - 'kind' - 'commitSha' - 'repositoryPath' = '{}'::jsonb
        and location->>'commitSha' ~ '^[0-9a-f]{7,64}$'
        and length(location->>'repositoryPath') between 1 and 1024
      )
      or (
        location->>'kind' = 'inline'
        and location - 'kind' - 'text' = '{}'::jsonb
        and jsonb_typeof(location->'text') = 'string'
      )
      or (
        location->>'kind' = 'object'
        and location - 'kind' - 'provider' - 'bucket' - 'objectPath' = '{}'::jsonb
        and location->>'provider' = 'supabase_storage'
        and location->>'bucket' = 'company-os-evidence'
        and length(location->>'objectPath') between 1 and 1024
        and location->>'objectPath' !~ '(^/|\\\\|(^|/)\.\.(/|$)|//)'
      )
    )
  );

create unique index runs_task_identity_idx
  on company_ops.runs (organization_id, project_id, task_id, id);

alter table company_ops.evidence_artifacts
  add constraint evidence_artifacts_run_task_fk
    foreign key (organization_id, project_id, task_id, run_id)
    references company_ops.runs (organization_id, project_id, task_id, id)
    on delete restrict;

create or replace function company_ops.validate_evidence_artifact()
returns trigger
language plpgsql
set search_path = ''
as $$
declare
  v_task company_ops.tasks%rowtype;
  v_run company_ops.runs%rowtype;
  v_expected_path text;
begin
  select task.* into v_task
    from company_ops.tasks task
   where task.id = new.task_id
     and task.organization_id = new.organization_id
     and task.project_id = new.project_id;
  if not found then
    raise exception 'artifact task scope does not exist';
  end if;

  if new.goal_id is null then
    new.goal_id := v_task.goal_id;
  elsif new.goal_id <> v_task.goal_id then
    raise exception 'artifact goal does not match its task';
  end if;

  if new.run_id is not null then
    select run.* into v_run
      from company_ops.runs run
     where run.id = new.run_id
       and run.organization_id = new.organization_id
       and run.project_id = new.project_id
       and run.task_id = new.task_id;
    if not found then
      raise exception 'artifact run does not belong to its task';
    end if;
    if v_run.agent_id <> new.created_by_agent_id then
      raise exception 'artifact creator does not own its run';
    end if;
  end if;

  new.created_at := now();
  new.visibility := 'owner_only';
  new.retention_policy := 'approval_record';
  new.contains_sensitive_data := new.kind in ('log', 'patch', 'report', 'trace');
  new.safe_to_display :=
    new.kind in ('screenshot', 'render', 'recording')
    and new.media_type in (
      'image/png', 'image/jpeg', 'image/webp', 'image/gif',
      'video/mp4', 'video/webm'
    );

  if new.location->>'kind' = 'object' then
    if new.run_id is null then
      raise exception 'object artifact requires a durable run';
    end if;
    v_expected_path := concat(
      'organizations/', new.organization_id,
      '/projects/', new.project_id,
      '/goals/', new.goal_id,
      '/tasks/', new.task_id,
      '/runs/', new.run_id,
      '/artifacts/', new.id,
      '/', new.sha256
    );
    if new.location->>'objectPath' <> v_expected_path then
      raise exception 'artifact object path does not match its database scope';
    end if;
  end if;
  return new;
end;
$$;

create trigger evidence_artifacts_validate
  before insert on company_ops.evidence_artifacts
  for each row execute function company_ops.validate_evidence_artifact();

create trigger evidence_artifacts_no_truncate
  before truncate on company_ops.evidence_artifacts
  for each statement execute function company_ops.block_artifact_change();

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
) values (
  'company-os-evidence',
  'company-os-evidence',
  false,
  104857600,
  array[
    'image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/svg+xml',
    'video/mp4', 'video/webm', 'text/plain', 'text/html',
    'application/json', 'application/xml', 'application/zip',
    'model/gltf-binary', 'model/gltf+json'
  ]::text[]
)
on conflict (id) do update
  set public = false,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

-- No anon/authenticated Storage policies are created. Only trusted server
-- code may upload or sign reads; the browser sees a short-lived owner link.

commit;
