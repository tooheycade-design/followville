-- Gives the dashboard a narrow authenticated identity check.
--
-- The previous web UI trusted a user-selectable cookie and an environment
-- registry. This function derives the user from the validated Supabase Auth
-- JWT and returns only that user's active Company OS membership. It accepts no
-- user-id argument, so one account cannot ask about or impersonate another.

begin;

create or replace function public.company_os_my_membership()
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'userId', member.user_id,
    'organizationId', member.organization_id,
    'role', member.role
  )
  from company_ops.organization_members member
  where member.user_id = (select auth.uid())
    and member.active
  limit 1;
$$;

revoke all on function public.company_os_my_membership()
  from public, anon, service_role;
grant execute on function public.company_os_my_membership() to authenticated;

commit;
