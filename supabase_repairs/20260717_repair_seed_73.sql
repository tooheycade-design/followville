-- Followville one-row data repair: abandoned Day 9 lanestreet metadata.
-- Approved scope: public.houses id 73 only. No claim/profile writes.
-- Run only after comparing the live row and public claim snapshot.
-- This is a reviewed one-off data repair, not a schema migration.
-- Applied 2026-07-17 through the equivalent exact-filter single-row PostgREST
-- update after snapshot verification; retained as the audited SQL/rollback.

begin;

do $$
declare
  v_claims integer;
  v_updated integer;
begin
  perform 1 from public.houses where id = 73 for update;
  if not found then
    raise exception 'seed_73_missing';
  end if;

  select count(*) into v_claims
  from public.claims
  where house_id = 73;
  if v_claims <> 0 then
    raise exception 'seed_73_has_claims';
  end if;

  update public.houses
  set gx = -3,
      gy = -3,
      building_type = 'house',
      claimable = true
  where id = 73
    and gx = 5
    and gy = -9
    and building_type = 'lanestreet'
    and day_built = 9
    and claimable = false;

  get diagnostics v_updated = row_count;
  if v_updated <> 1 then
    raise exception 'seed_73_precondition_changed';
  end if;
end
$$;

select id, gx, gy, building_type, day_built, claimable
from public.houses
where id = 73;

commit;

-- Guarded rollback, only if seed 73 still has no claim:
--
-- begin;
-- do $$
-- declare v_claims integer; v_updated integer;
-- begin
--   select count(*) into v_claims from public.claims where house_id = 73;
--   if v_claims <> 0 then raise exception 'seed_73_has_claims_preserve_owner'; end if;
--   update public.houses
--   set gx = 5, gy = -9, building_type = 'lanestreet', claimable = false
--   where id = 73 and gx = -3 and gy = -3
--     and building_type = 'house' and day_built = 9 and claimable = true;
--   get diagnostics v_updated = row_count;
--   if v_updated <> 1 then raise exception 'seed_73_rollback_precondition_changed'; end if;
-- end
-- $$;
-- commit;
