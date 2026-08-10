-- Followville Inventory System v1 — fish only.
--
-- Web/backend only. Adds one validated, owner-only, ADD-ONLY inventory column
-- on profiles. It does not touch houses, claims, ownership, verification,
-- admin status, world state, population, or town geometry. No existing row is
-- rewritten: the column arrives with a default and every prior profile is
-- valid on arrival.
--
-- Why profiles and not claims: an inventory belongs to a player, not to a
-- house. Guests keep theirs in localStorage; anyone who signs in gets one,
-- whether or not they are verified and whether or not they own a home.
--
-- Why add-only: there is deliberately no RPC that lowers or clears a count. A
-- client bug, a double-fire, or a hostile caller can inflate a stack but can
-- never destroy a player's catches. Follow Bucks will eventually need a spend
-- path; that is a later migration with its own audit trail, not this one.

begin;

alter table public.profiles add column if not exists inventory jsonb not null default
  '{"version":1,"fish":{}}'::jsonb;

-- CHECK constraints cannot contain subqueries, and validating "every key of a
-- nested object is in an allowlist" needs one. An immutable helper is the
-- supported way to get there, and it keeps the allowlist in exactly one place
-- shared by the constraint and the RPC below.
create or replace function public.followville_inventory_is_valid(p jsonb)
returns boolean
language sql immutable parallel safe set search_path = ''
as $$
  select jsonb_typeof(p) = 'object'
     and octet_length(p::text) <= 1024
     and p ?& array['version','fish']
     and p - array['version','fish'] = '{}'::jsonb
     and p->>'version' = '1'
     and jsonb_typeof(p->'fish') = 'object'
     and not exists (
       select 1 from jsonb_each(p->'fish') as e(key, value)
       where e.key not in (
               'pond_perch','meadow_minnow','dock_sunfish',
               'rusty_carp','willow_bass','speckled_trout',
               'bluebell_pike','glass_eel','moonlit_catfish',
               'golden_sturgeon','founders_koi',
               'kaleidoscope_koi','followville_phantom')
          -- integer 1..999, expressed as a regex so no cast can throw
          or jsonb_typeof(e.value) <> 'number'
          or (e.value #>> '{}') !~ '^[1-9][0-9]{0,2}$'
     );
$$;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.profiles'::regclass and conname = 'profiles_inventory_valid'
  ) then
    alter table public.profiles add constraint profiles_inventory_valid
      check (public.followville_inventory_is_valid(inventory));
  end if;
end $$;

-- The existing profiles_own_avatar_update policy already restricts UPDATE to
-- the caller's own row for authenticated users. Row scope is the same here, so
-- it is reused rather than duplicated; the column-level grant below is what
-- keeps identity, admin and verification fields server-controlled.
--
-- Re-granting avatar alongside inventory is deliberate: the revoke is
-- table-wide, so omitting avatar here would silently break avatar saving.
revoke update on public.profiles from public, anon, authenticated;
grant update (avatar, inventory) on public.profiles to authenticated;

-- Add-only, allowlisted, bounded. The client can never SET a count, only ask
-- for an increment, so the worst a forged call achieves is a larger stack.
create or replace function public.add_to_my_inventory(p_items jsonb)
returns json
language plpgsql security invoker set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_input jsonb := coalesce(p_items, '{}'::jsonb);
  v_current jsonb;
  v_next jsonb;
  v_total integer := 0;
  v_key text;
  v_add integer;
  v_row public.profiles;
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;
  if jsonb_typeof(v_input) <> 'object' or octet_length(v_input::text) > 1024 then
    raise exception 'bad_inventory';
  end if;

  -- Reuse the catalog allowlist by validating the increment as if it were a
  -- whole inventory. Keeps one list, not two that can drift apart.
  if not public.followville_inventory_is_valid(
       jsonb_build_object('version','1','fish',v_input)) then
    raise exception 'bad_inventory';
  end if;

  select coalesce(sum((value #>> '{}')::integer), 0) into v_total
    from jsonb_each(v_input);
  if v_total < 1 or v_total > 200 then raise exception 'bad_inventory'; end if;

  select coalesce(inventory, '{"version":1,"fish":{}}'::jsonb) into v_current
    from public.profiles where user_id = v_uid;
  if v_current is null then raise exception 'profile_missing'; end if;

  v_next := coalesce(v_current->'fish', '{}'::jsonb);
  for v_key, v_add in
    select key, (value #>> '{}')::integer from jsonb_each(v_input)
  loop
    v_next := jsonb_set(
      v_next, array[v_key],
      to_jsonb(least(999, coalesce((v_next->>v_key)::integer, 0) + v_add)),
      true);
  end loop;

  update public.profiles
     set inventory = jsonb_build_object('version', 1, 'fish', v_next)
   where user_id = v_uid
   returning * into v_row;
  if not found then raise exception 'profile_missing'; end if;
  return row_to_json(v_row);
end $$;

revoke execute on function public.add_to_my_inventory(jsonb) from public, anon, authenticated;
grant execute on function public.add_to_my_inventory(jsonb) to authenticated, service_role;

commit;
