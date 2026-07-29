select
  to_regclass('company_ops.content_packets') is not null as packet_table,
  (select relrowsecurity
    from pg_class
    where oid = 'company_ops.content_packets'::regclass) as packet_rls,
  (select count(*)
    from company_ops.agent_profiles
    where id = '40000000-0000-4000-8000-000000000008'
      and active
      and capabilities::text[] =
        array['repository_read', 'memory_write', 'message_send']) as strategist,
  has_function_privilege(
    'authenticated',
    'public.company_os_select_content_concept(jsonb)',
    'execute'
  ) as owner_select,
  not has_function_privilege(
    'anon',
    'public.company_os_select_content_concept(jsonb)',
    'execute'
  ) as anon_blocked,
  not has_function_privilege(
    'authenticated',
    'public.company_os_record_content_packet(jsonb)',
    'execute'
  ) as client_record_blocked,
  not has_table_privilege(
    'authenticated',
    'company_ops.content_packets',
    'select'
  ) as direct_read_blocked,
  not exists (
    select 1 from pg_proc where proname like 'company_os%publish%'
  ) as no_publisher;
