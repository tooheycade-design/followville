-- Pins the search path on the append-only trigger helpers added in 0012 and
-- 0013. They do not query objects, but an explicit empty path removes ambient
-- role state and satisfies the database security advisor.

begin;

alter function company_ops.block_release_authorization_change()
  set search_path = '';

alter function company_ops.block_artifact_change()
  set search_path = '';

commit;
