-- Read-only verification for migrations 0011 through 0014.
-- Run only in followville-company-os-dev (yutscolndfhscxfoavdp).

select 'project database' as check_name,
       'inspect-project-name' as result,
       current_database() as detail;

select 'git_checkpoint enum' as check_name,
       case when exists (
         select 1
           from pg_enum e
           join pg_type t on t.oid = e.enumtypid
           join pg_namespace n on n.oid = t.typnamespace
          where n.nspname = 'company_ops'
            and t.typname = 'capability'
            and e.enumlabel = 'git_checkpoint'
       ) then 'pass' else 'missing' end as result;

select 'held authorization table' as check_name,
       case when to_regclass('company_ops.task_release_authorizations') is not null
            then 'pass' else 'missing' end as result;

select 'evidence artifact table' as check_name,
       case when to_regclass('company_ops.evidence_artifacts') is not null
            then 'pass' else 'missing' end as result;

select 'held decision function' as check_name,
       case when to_regprocedure('public.company_os_decide_held_task(jsonb)') is not null
            then 'pass' else 'missing' end as result;

select 'atomic review function' as check_name,
       case
         when pg_get_functiondef(
           to_regprocedure('public.company_os_record_review(jsonb)')
         ) like '%company_os_record_completed_work%'
          and pg_get_functiondef(
           to_regprocedure('public.company_os_record_review(jsonb)')
         ) like '%lease_expires_at <= now()%'
         then 'pass'
         else 'missing-or-stale'
       end as result;

select 'acceptance transition separated' as check_name,
       case
         when pg_get_functiondef(
           to_regprocedure('company_ops.validate_task_update()')
         ) like '%current approved result request%'
          and pg_get_functiondef(
           to_regprocedure('company_ops.validate_task_update()')
         ) like '%current approved merge request%'
         then 'pass'
         else 'missing-or-stale'
       end as result;

select 'browser schema access revoked' as check_name,
       case
         when not has_schema_privilege('anon', 'company_ops', 'USAGE')
          and not has_schema_privilege('authenticated', 'company_ops', 'USAGE')
         then 'pass'
         else 'exposed'
       end as result;

select 'browser review execution revoked' as check_name,
       case
         when not has_function_privilege(
           'anon', 'public.company_os_record_review(jsonb)', 'EXECUTE'
         )
          and not has_function_privilege(
           'authenticated', 'public.company_os_record_review(jsonb)', 'EXECUTE'
         )
         then 'pass'
         else 'exposed'
       end as result;

select 'completed-work helper is private' as check_name,
       case
         when to_regprocedure(
           'public.company_os_record_completed_work(jsonb)'
         ) is not null
          and not has_function_privilege(
            'service_role',
            'public.company_os_record_completed_work(jsonb)',
            'EXECUTE'
          )
         then 'pass'
         else 'missing-or-callable'
       end as result;
