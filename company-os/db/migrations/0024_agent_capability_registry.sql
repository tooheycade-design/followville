-- Normalizes executable agent capabilities for worker compatibility checks.
--
-- Agent profile JSON remains descriptive. This enum array is the database
-- authority used by the worker registry, so a service worker cannot advertise
-- a capability its assigned agent does not hold.

begin;

alter table company_ops.agent_profiles
  add column capabilities company_ops.capability[] not null default '{}';

alter table company_ops.agent_profiles
  add constraint agent_profiles_capabilities_check
  check (
    cardinality(capabilities) <= 64
    and array_position(capabilities, null) is null
  );

update company_ops.agent_profiles
   set capabilities = case id
     when '40000000-0000-4000-8000-000000000001'::uuid then
       array[
         'repository_read', 'memory_write', 'message_send'
       ]::company_ops.capability[]
     when '40000000-0000-4000-8000-000000000002'::uuid then
       array[
         'repository_read', 'repository_write', 'git_branch_create',
         'git_checkpoint', 'git_commit', 'git_push_review_branch',
         'pull_request_create', 'test_execute', 'browser_preview',
         'blender_preview', 'memory_write', 'message_send'
       ]::company_ops.capability[]
     when '40000000-0000-4000-8000-000000000003'::uuid then
       array[
         'repository_read', 'test_execute', 'message_send'
       ]::company_ops.capability[]
     when '40000000-0000-4000-8000-000000000004'::uuid then
       array[
         'repository_read', 'message_send'
       ]::company_ops.capability[]
     when '40000000-0000-4000-8000-000000000005'::uuid then
       array[
         'repository_read', 'message_send'
       ]::company_ops.capability[]
     when '40000000-0000-4000-8000-000000000006'::uuid then
       array[
         'repository_read', 'memory_write', 'message_send'
       ]::company_ops.capability[]
     else '{}'::company_ops.capability[]
   end;

commit;
