\set ON_ERROR_STOP on

begin;

do $$
declare
  v_capabilities company_ops.capability[];
begin
  select capabilities
    into v_capabilities
    from company_ops.agent_profiles
   where id = '40000000-0000-4000-8000-000000000007'
     and slug = 'design-director'
     and active;

  if v_capabilities is null then
    raise exception 'active Design Director profile is missing';
  end if;

  if v_capabilities <> array[
    'repository_read'::company_ops.capability,
    'message_send'::company_ops.capability
  ] then
    raise exception 'Design Director capabilities are not least privilege: %',
      v_capabilities;
  end if;

  if v_capabilities && array[
    'repository_write'::company_ops.capability,
    'git_commit'::company_ops.capability,
    'production_merge'::company_ops.capability,
    'production_deploy'::company_ops.capability,
    'production_database_write'::company_ops.capability,
    'canonical_world_growth'::company_ops.capability,
    'payment_charge'::company_ops.capability
  ] then
    raise exception 'Design Director received a prohibited capability';
  end if;
end;
$$;

rollback;

select '0035 Design Director verification passed' as result;
