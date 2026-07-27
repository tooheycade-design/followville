-- Migration 0002 revoked every control-plane function from the browser roles
-- but granted execute on only three of the four. The control plane also
-- appends a standalone audit event when it refuses a decision, so recording a
-- refusal failed with "permission denied for function".
--
-- Recording that an action was refused is exactly the kind of event the audit
-- trail must not lose, so the grant belongs here rather than dropping the
-- write.

begin;

grant execute on function public.company_os_append_audit_events(jsonb)
  to service_role;

commit;
