-- ============================================================================
-- FOLLOWVILLE — claimable homes schema (Supabase / Postgres)
-- Run this ONCE in the Supabase SQL Editor of the Followville project.
-- Safe to re-run: everything is IF NOT EXISTS / CREATE OR REPLACE.
--
-- Design notes (see CLAIMING_SETUP.md for the full guide):
-- * houses.id  = the building's `seed` from world_state.json (already a
--   globally-unique, monotonically-increasing integer — no new id scheme).
-- * One account per house is enforced by claims.house_id. Per-owner limits
--   are enforced by a locking trigger: one home normally, two for admins.
-- * All writes go through SECURITY DEFINER functions (RPCs). Clients have
--   read-only access; there are deliberately NO insert/update RLS policies.
-- * verification_status is generic (pending/verified/rejected) so manual
--   admin approval works today and the Instagram DM webhook can be swapped
--   in later with zero schema changes.
-- ============================================================================

-- ───────────────────────────── TABLES ─────────────────────────────

create table if not exists public.houses (
  id            bigint primary key,          -- = building seed in world_state.json
  gx            int not null,
  gy            int not null,
  building_type text not null,               -- matches world_state.json "type"
  day_built     int not null,
  claimable     boolean not null default true,
  created_at    timestamptz not null default now()
);

create table if not exists public.profiles (
  user_id             uuid primary key references auth.users(id) on delete cascade,
  instagram_handle    text not null unique,
  instagram_user_id   text,                  -- filled once verified via IG API (stable id; handles can change)
  verification_status text not null default 'pending'
                      check (verification_status in ('pending','verified','rejected')),
  verification_code   text not null,
  verified_at         timestamptz,
  created_at          timestamptz not null default now(),
  is_admin             boolean not null default false,
  avatar               jsonb not null default
                       '{"version":1,"skin":"peach","height":"adult","face":"classic","hair":"swept","outfit":"tailored","hat":"none","look":"custom"}'::jsonb,
  constraint handle_format check (instagram_handle ~ '^[a-z0-9._]{1,30}$')
);

-- Keeps the file re-runnable against installations created before is_admin.
alter table public.profiles add column if not exists is_admin boolean not null default false;
alter table public.profiles add column if not exists avatar jsonb not null default
  '{"version":1,"skin":"peach","height":"adult","face":"classic","hair":"swept","outfit":"tailored","hat":"none","look":"custom"}'::jsonb;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.profiles'::regclass and conname = 'profiles_avatar_valid'
  ) then
    alter table public.profiles add constraint profiles_avatar_valid check (
      jsonb_typeof(avatar) = 'object'
      and octet_length(avatar::text) <= 512
      and avatar ?& array['version','skin','height','face','hair','outfit','hat','look']
      and avatar - array['version','skin','height','face','hair','outfit','hat','look'] = '{}'::jsonb
      and avatar->>'version' = '1'
      and avatar->>'skin' in ('porcelain','fair','peach','warm','honey','amber','bronze','cocoa','deep','espresso')
      and avatar->>'height' in ('kid','tween','teen','adult','tall')
      and avatar->>'face' in ('classic','round','oval','narrow','heart','square','soft','defined')
      and avatar->>'hair' in ('none','close_crop','tousled','swept','afro','long')
      and avatar->>'outfit' in ('tailored','striped','tee','field_jacket','weekend','active')
      and avatar->>'hat' in ('none','ranger_hood')
      and avatar->>'look' in ('custom','casual_day_f','casual_day_m','casual_sky_f','casual_sky_m','casual_lilac_f','casual_lilac_m','casual_bald','suit_f','suit_m','classy_f','classy_m','chef_f','chef_m','doctor_young_f','doctor_young_m','doctor_senior_f','doctor_senior_m','worker_f','worker_m','cowboy_f','cowboy_m','kimono_f','kimono_m','pirate_f','pirate_m','viking_f','viking_m','ninja_f','ninja_m','sand_ninja_f','sand_ninja_m','gold_knight_f','gold_knight_m','knight_m','elf','witch','wizard')
    );
  end if;
end $$;

create table if not exists public.claims (
  house_id      bigint primary key references public.houses(id),
  user_id       uuid not null references public.profiles(user_id) on delete cascade,
  claimed_at    timestamptz not null default now(),
  customization jsonb
);

-- Normal accounts may own one house; trusted admins may own two. Older
-- installs enforced exactly one with the default claims_user_id_key name.
alter table public.claims drop constraint if exists claims_user_id_key;
create index if not exists claims_user_id_idx on public.claims (user_id);

create or replace function public.enforce_claim_limit()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
  v_limit integer;
  v_count integer;
begin
  -- Serializes claims for one owner so concurrent requests cannot both see
  -- the same open slot and exceed that owner's allowance.
  perform 1 from public.profiles where user_id = new.user_id for update;
  if not found then raise exception 'profile_missing'; end if;

  select case when is_admin then 2 else 1 end into v_limit
    from public.profiles where user_id = new.user_id;
  if tg_op = 'INSERT' then
    select count(*) into v_count from public.claims where user_id = new.user_id;
  else
    select count(*) into v_count from public.claims
      where user_id = new.user_id and house_id <> old.house_id;
  end if;
  if v_count >= v_limit then raise exception 'claim_limit_reached'; end if;
  return new;
end $$;

drop trigger if exists claims_enforce_owner_limit on public.claims;
create trigger claims_enforce_owner_limit
before insert or update of user_id on public.claims
for each row execute function public.enforce_claim_limit();

-- ─────────────────────── PUBLIC READ VIEW (name tags) ───────────────────────
-- What the town page shows on claimed houses. Exposes ONLY house_id + handle
-- (+ customization), never emails or auth ids.

create or replace view public.public_claims
with (security_invoker = off) as
  select c.house_id, p.instagram_handle, c.claimed_at, c.customization
  from public.claims c
  join public.profiles p on p.user_id = c.user_id;

-- ───────────────────────────── RLS ─────────────────────────────

alter table public.houses   enable row level security;
alter table public.profiles enable row level security;
alter table public.claims   enable row level security;

drop policy if exists houses_public_read on public.houses;
create policy houses_public_read on public.houses
  for select to anon, authenticated using (true);

-- claims are publicly readable so Realtime change events reach every visitor
-- (row contents: house_id/user_id/claimed_at — no personal data beyond that)
drop policy if exists claims_public_read on public.claims;
create policy claims_public_read on public.claims
  for select to anon, authenticated using (true);

-- users can read ONLY their own profile (to see their code + status)
drop policy if exists profiles_own_read on public.profiles;
create policy profiles_own_read on public.profiles
  for select to authenticated using (user_id = auth.uid());

-- Players may update only the avatar column on their own profile. All other
-- profile fields remain server-controlled, and profiles_avatar_valid rejects
-- arbitrary JSON even when a client writes the column directly.
drop policy if exists profiles_own_avatar_update on public.profiles;
create policy profiles_own_avatar_update on public.profiles
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);
revoke update on public.profiles from public, anon, authenticated;
grant update (avatar) on public.profiles to authenticated;

grant select on public.public_claims to anon, authenticated;

-- Claims and identity fields still have no client write policies. The one
-- profile UPDATE policy above is paired with avatar-only column privileges;
-- every other write goes through the narrow functions below (or service role).

-- ───────────────────────────── RPCs ─────────────────────────────

-- Called once after signup (and re-callable while still pending, e.g. to fix
-- a typo'd handle). Generates the verification code server-side.
create or replace function public.setup_profile(p_handle text)
returns public.profiles
language plpgsql security definer set search_path = public
as $$
declare
  v_uid    uuid := auth.uid();
  v_handle text := lower(trim(both '@' from trim(p_handle)));
  v_row    public.profiles;
begin
  if v_uid is null then
    raise exception 'not_authenticated';
  end if;
  if v_handle !~ '^[a-z0-9._]{1,30}$' then
    raise exception 'bad_handle';
  end if;

  select * into v_row from public.profiles where user_id = v_uid;

  if found then
    if v_row.verification_status = 'verified' then
      raise exception 'already_verified';   -- verified handles are locked
    end if;
    update public.profiles
       set instagram_handle = v_handle, verification_status = 'pending'
     where user_id = v_uid
     returning * into v_row;
  else
    insert into public.profiles (user_id, instagram_handle, verification_code)
    values (v_uid, v_handle,
            'FV-' || upper(substr(md5(gen_random_uuid()::text), 1, 6)))
    returning * into v_row;
  end if;

  return v_row;
exception
  when unique_violation then
    raise exception 'handle_taken';
end $$;

-- THE claim. The profile-row lock serializes claims by the same owner, while
-- claims.house_id guarantees two people can never own the same house.
create or replace function public.claim_house(p_house_id bigint)
returns json
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid  uuid := auth.uid();
  v_verified boolean;
  v_limit integer;
  v_count integer;
  v_row  public.claims;
begin
  if v_uid is null then
    raise exception 'not_authenticated';
  end if;
  select verification_status = 'verified', case when is_admin then 2 else 1 end
    into v_verified, v_limit
    from public.profiles where user_id = v_uid for update;
  if not found or not coalesce(v_verified, false) then
    raise exception 'not_verified';
  end if;
  select count(*) into v_count from public.claims where user_id = v_uid;
  if v_count >= v_limit then raise exception 'claim_limit_reached'; end if;
  if not exists (select 1 from public.houses
                 where id = p_house_id and claimable) then
    raise exception 'not_claimable';
  end if;

  insert into public.claims (house_id, user_id)
  values (p_house_id, v_uid)
  returning * into v_row;

  return row_to_json(v_row);
exception
  when unique_violation then
    raise exception 'house_taken';
end $$;

-- Backward-compatible no-argument unclaim for one-home accounts. Two-home
-- admins must use the house-specific overload below so only one row is removed.
create or replace function public.unclaim_house()
returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_count integer;
begin
  if v_uid is null then
    raise exception 'not_authenticated';
  end if;
  select count(*) into v_count from public.claims where user_id = v_uid;
  if v_count > 1 then raise exception 'choose_house'; end if;
  delete from public.claims where user_id = v_uid;
  if not found then
    raise exception 'no_claim';
  end if;
end $$;

-- House-specific unclaim prevents a two-home admin from deleting both homes.
create or replace function public.unclaim_house(p_house_id bigint)
returns void
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;
  delete from public.claims where user_id = v_uid and house_id = p_house_id;
  if not found then raise exception 'not_your_house'; end if;
end $$;

-- Own-status readback for the UI (avoids exposing profiles more broadly).
create or replace function public.my_status()
returns json
language sql security definer set search_path = '' stable
as $$
  select json_build_object(
    'profile', (select row_to_json(p) from public.profiles p where p.user_id = auth.uid()),
    'claim',   (select row_to_json(c) from public.claims c where c.user_id = auth.uid()
                order by c.claimed_at, c.house_id limit 1),
    'claims',  coalesce((select json_agg(row_to_json(c) order by c.claimed_at, c.house_id)
                         from public.claims c where c.user_id = auth.uid()), '[]'::json),
    'claim_limit', case when coalesce((select p.is_admin from public.profiles p
                                       where p.user_id = auth.uid()), false) then 2 else 1 end
  );
$$;

-- Avatar System v1: signed-in players save one complete catalog selection on
-- their profile. Column-level grants prevent updates to identity/admin fields;
-- this security-invoker RPC normalizes IDs and returns only the caller's row.
create or replace function public.update_my_avatar(p_avatar jsonb)
returns json
language plpgsql security invoker set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_input jsonb := coalesce(p_avatar, '{}'::jsonb);
  v_avatar jsonb;
  v_row public.profiles;
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;
  if jsonb_typeof(v_input) <> 'object' or octet_length(v_input::text) > 512 then
    raise exception 'bad_avatar';
  end if;
  if exists (
    select 1 from jsonb_object_keys(v_input) as k(key)
    where k.key not in ('version','skin','height','face','hair','outfit','hat','look')
  ) then raise exception 'bad_avatar'; end if;
  if coalesce(v_input->>'version','1') <> '1'
     or coalesce(v_input->>'skin','peach') not in
       ('porcelain','fair','peach','warm','honey','amber','bronze','cocoa','deep','espresso')
     or coalesce(v_input->>'height','adult') not in ('kid','tween','teen','adult','tall')
     or coalesce(v_input->>'face','classic') not in
       ('classic','round','oval','narrow','heart','square','soft','defined')
     or coalesce(v_input->>'hair','swept') not in
       ('none','close_crop','tousled','swept','afro','long')
     or coalesce(v_input->>'outfit','tailored') not in
       ('tailored','striped','tee','field_jacket','weekend','active')
     or coalesce(v_input->>'hat','none') not in
       ('none','ranger_hood')
     or coalesce(v_input->>'look','custom') not in
       ('custom','casual_day_f','casual_day_m','casual_sky_f','casual_sky_m','casual_lilac_f','casual_lilac_m','casual_bald','suit_f','suit_m','classy_f','classy_m','chef_f','chef_m','doctor_young_f','doctor_young_m','doctor_senior_f','doctor_senior_m','worker_f','worker_m','cowboy_f','cowboy_m','kimono_f','kimono_m','pirate_f','pirate_m','viking_f','viking_m','ninja_f','ninja_m','sand_ninja_f','sand_ninja_m','gold_knight_f','gold_knight_m','knight_m','elf','witch','wizard') then
    raise exception 'bad_avatar';
  end if;
  v_avatar := jsonb_build_object(
    'version',1,
    'skin',coalesce(v_input->>'skin','peach'),
    'height',coalesce(v_input->>'height','adult'),
    'face',coalesce(v_input->>'face','classic'),
    'hair',coalesce(v_input->>'hair','swept'),
    'outfit',coalesce(v_input->>'outfit','tailored'),
    'hat',coalesce(v_input->>'hat','none'),
    'look',coalesce(v_input->>'look','custom')
  );
  update public.profiles set avatar = v_avatar where user_id = v_uid returning * into v_row;
  if not found then raise exception 'profile_missing'; end if;
  return row_to_json(v_row);
end $$;

-- Homeowner Mode: the signed-in owner may change only the approved visual
-- options on their own claim.  Keeping this behind a narrow RPC means the
-- browser never receives UPDATE permission on claims, and the normalized
-- palette IDs keep arbitrary JSON/CSS values out of the public town view.
drop function if exists public.update_my_customization(jsonb);
create or replace function public.update_my_customization(p_house_id bigint, p_customization jsonb)
returns json
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid uuid := auth.uid();
  v_input jsonb := coalesce(p_customization, '{}'::jsonb);
  v_existing jsonb;
  v_interior jsonb;
  v_customization jsonb;
  v_row public.claims;
begin
  if v_uid is null then
    raise exception 'not_authenticated';
  end if;
  select customization into v_existing
    from public.claims
   where user_id = v_uid and house_id = p_house_id;
  if not found then
    raise exception 'not_your_house';
  end if;
  if jsonb_typeof(v_input) <> 'object' or octet_length(v_input::text) > 8192 then
    raise exception 'bad_customization';
  end if;
  if exists (
    select 1 from jsonb_object_keys(v_input) as k(key)
    where k.key not in ('version', 'wall', 'roof', 'door', 'yard', 'interior')
  ) then
    raise exception 'bad_customization';
  end if;
  if coalesce(v_input->>'version', '1') not in ('1', '2')
     or coalesce(v_input->>'wall', 'original') not in
        ('original', 'butter', 'sage', 'sky', 'blush', 'lavender', 'cream')
     or coalesce(v_input->>'roof', 'original') not in
        ('original', 'charcoal', 'cedar', 'slate', 'forest', 'plum')
     or coalesce(v_input->>'door', 'original') not in
        ('original', 'red', 'navy', 'teal', 'yellow', 'white')
     or coalesce(v_input->>'yard', 'none') not in
        ('none', 'flowers', 'tree', 'bench', 'flag') then
    raise exception 'bad_customization';
  end if;

  if v_input ? 'interior' then
    if jsonb_typeof(v_input->'interior') <> 'array'
       or jsonb_array_length(v_input->'interior') > 48
       or exists (
         select 1 from jsonb_array_elements(v_input->'interior') as item(value)
         where jsonb_typeof(item.value) <> 'object'
       )
       or exists (
         select 1
           from jsonb_array_elements(v_input->'interior') as item(value),
                lateral jsonb_object_keys(case when jsonb_typeof(item.value) = 'object'
                  then item.value else '{}'::jsonb end) as k(key)
          where k.key not in ('item', 'x', 'z', 'r')
       )
       or exists (
         select 1 from jsonb_array_elements(v_input->'interior') as item(value)
          where not (item.value ?& array['item','x','z','r'])
             or jsonb_typeof(item.value->'item') <> 'string'
             or jsonb_typeof(item.value->'x') <> 'number'
             or jsonb_typeof(item.value->'z') <> 'number'
             or jsonb_typeof(item.value->'r') <> 'number'
             or item.value->>'item' not in (
               'couch_l','couch_large','fireplace','shelf_large','rug','light_floor',
               'table_round_large','chair','stool','kitchen_sink','fridge','oven','drawer',
               'bed_king','bed_single','nightstand','table_lamp','bathroom_sink','toilet',
               'bathtub','washing_machine','houseplant','curtains_double','light_ceiling','door_double'
             )
             or abs((item.value->>'x')::numeric) > 8.55
             or abs((item.value->>'z')::numeric) > 6.55
             or (item.value->>'r')::numeric <> trunc((item.value->>'r')::numeric)
             or (item.value->>'r')::int not between 0 and 3
       ) then
      raise exception 'bad_customization';
    end if;

    select coalesce(jsonb_agg(jsonb_build_object(
      'item', item.value->>'item',
      'x', round((item.value->>'x')::numeric * 4) / 4,
      'z', round((item.value->>'z')::numeric * 4) / 4,
      'r', (item.value->>'r')::int
    ) order by item.ordinality), '[]'::jsonb)
      into v_interior
      from jsonb_array_elements(v_input->'interior') with ordinality as item(value, ordinality);
  elsif jsonb_typeof(v_existing->'interior') = 'array' then
    v_interior := v_existing->'interior';
  end if;

  v_customization := jsonb_build_object(
    'version', 2,
    'wall', coalesce(v_input->>'wall', 'original'),
    'roof', coalesce(v_input->>'roof', 'original'),
    'door', coalesce(v_input->>'door', 'original'),
    'yard', coalesce(v_input->>'yard', 'none')
  ) || case when v_interior is null then '{}'::jsonb
            else jsonb_build_object('interior', v_interior) end;

  update public.claims
     set customization = v_customization
   where user_id = v_uid and house_id = p_house_id
   returning * into v_row;
  return row_to_json(v_row);
end $$;

grant execute on function public.setup_profile(text)  to authenticated;
grant execute on function public.claim_house(bigint)  to authenticated;
grant execute on function public.unclaim_house()      to authenticated;
grant execute on function public.unclaim_house(bigint) to authenticated;
grant execute on function public.my_status()          to authenticated;
grant execute on function public.update_my_avatar(jsonb) to authenticated;
grant execute on function public.update_my_customization(bigint, jsonb) to authenticated;
revoke execute on function public.enforce_claim_limit(), public.setup_profile(text), public.claim_house(bigint),
  public.unclaim_house(), public.unclaim_house(bigint), public.my_status(),
  public.update_my_customization(bigint, jsonb), public.update_my_avatar(jsonb) from public, anon;

-- ───────────────────────────── REALTIME ─────────────────────────────
-- Broadcast claim inserts/deletes to every connected town.html.

do $$
begin
  alter publication supabase_realtime add table public.claims;
exception when duplicate_object then null;
end $$;

-- ───────────────────────────── ADMIN HELPERS ─────────────────────────────
-- Run these by hand in the SQL Editor (they are NOT exposed to clients).
-- This is the manual-approval stand-in while Meta app review is pending;
-- the future DM webhook will do exactly what admin_verify does, plus fill
-- instagram_user_id from the webhook payload.

create or replace function public.admin_verify(p_handle text, p_instagram_user_id text default null)
returns public.profiles
language plpgsql security definer set search_path = public
as $$
declare v_row public.profiles;
begin
  update public.profiles
     set verification_status = 'verified',
         verified_at = now(),
         instagram_user_id = coalesce(p_instagram_user_id, instagram_user_id)
   where instagram_handle = lower(trim(both '@' from p_handle))
   returning * into v_row;
  if not found then raise exception 'no such handle'; end if;
  return v_row;
end $$;

create or replace function public.admin_reject(p_handle text)
returns void
language sql security definer set search_path = public
as $$
  update public.profiles set verification_status = 'rejected'
  where instagram_handle = lower(trim(both '@' from p_handle));
$$;

-- Revoke a fraudulent claim: frees the house AND blocks the account.
create or replace function public.admin_revoke_claim(p_house_id bigint)
returns void
language plpgsql security definer set search_path = public
as $$
declare v_uid uuid;
begin
  delete from public.claims where house_id = p_house_id returning user_id into v_uid;
  if v_uid is not null then
    update public.profiles set verification_status = 'rejected' where user_id = v_uid;
  end if;
end $$;

-- keep admin helpers away from clients entirely
revoke execute on function public.admin_verify(text, text), public.admin_reject(text), public.admin_revoke_claim(bigint) from anon, authenticated;

-- ──────────────── WEB ADMIN ACCESS (added 2026-07-09, run after the above) ────────────────
-- Lets specific logged-in accounts (profiles.is_admin = true) use the admin
-- page on the LIVE site. Every admin action below is guarded inside the
-- function itself, so the database refuses non-admin callers no matter what
-- the page does. The service-role key (local admin.bat / future DM webhook)
-- keeps working — auth.role() = 'service_role' bypasses the is_admin check.
-- ALSO fixes a privilege gap in the original version of this file: functions
-- get EXECUTE granted to PUBLIC by default, and the original only revoked
-- from anon/authenticated — leaving admin_verify callable via the PUBLIC
-- grant. Everything is revoked from PUBLIC explicitly now.

alter table public.profiles add column if not exists is_admin boolean not null default false;

update public.profiles set is_admin = true
where instagram_handle in ('cade.toohey', 'stellar.kehler');

create or replace function public.caller_is_admin()
returns boolean language sql stable security definer set search_path = public
as $$
  select coalesce((select is_admin from public.profiles where user_id = auth.uid()), false);
$$;

-- guarded versions of the admin actions (CREATE OR REPLACE overwrites the originals)
create or replace function public.admin_verify(p_handle text, p_instagram_user_id text default null)
returns public.profiles language plpgsql security definer set search_path = public
as $$
declare v_row public.profiles;
begin
  if auth.role() <> 'service_role' and not caller_is_admin() then
    raise exception 'not_admin';
  end if;
  update public.profiles
     set verification_status = 'verified', verified_at = now(),
         instagram_user_id = coalesce(p_instagram_user_id, instagram_user_id)
   where instagram_handle = lower(trim(both '@' from p_handle))
   returning * into v_row;
  if not found then raise exception 'no such handle'; end if;
  return v_row;
end $$;

create or replace function public.admin_reject(p_handle text)
returns void language plpgsql security definer set search_path = public
as $$
begin
  if auth.role() <> 'service_role' and not caller_is_admin() then
    raise exception 'not_admin';
  end if;
  update public.profiles set verification_status = 'rejected'
  where instagram_handle = lower(trim(both '@' from p_handle));
end $$;

create or replace function public.admin_revoke_claim(p_house_id bigint)
returns void language plpgsql security definer set search_path = public
as $$
declare v_uid uuid;
begin
  if auth.role() <> 'service_role' and not caller_is_admin() then
    raise exception 'not_admin';
  end if;
  delete from public.claims where house_id = p_house_id returning user_id into v_uid;
  if v_uid is not null then
    update public.profiles set verification_status = 'rejected' where user_id = v_uid;
  end if;
end $$;

-- read RPCs for the admin page (same guard)
create or replace function public.admin_list_pending()
returns json language plpgsql stable security definer set search_path = public
as $$
begin
  if auth.role() <> 'service_role' and not caller_is_admin() then
    raise exception 'not_admin';
  end if;
  return coalesce((select json_agg(json_build_object(
      'instagram_handle', instagram_handle,
      'verification_code', verification_code,
      'created_at', created_at) order by created_at asc)
    from public.profiles where verification_status = 'pending'), '[]'::json);
end $$;

create or replace function public.admin_list_claims()
returns json language plpgsql stable security definer set search_path = public
as $$
begin
  if auth.role() <> 'service_role' and not caller_is_admin() then
    raise exception 'not_admin';
  end if;
  return coalesce((select json_agg(json_build_object(
      'house_id', c.house_id,
      'claimed_at', c.claimed_at,
      'instagram_handle', p.instagram_handle,
      'building_type', h.building_type) order by c.claimed_at desc)
    from public.claims c
    join public.profiles p on p.user_id = c.user_id
    join public.houses h on h.id = c.house_id), '[]'::json);
end $$;

create or replace function public.admin_list_verified_unclaimed()
returns json language plpgsql stable security definer set search_path = public
as $$
begin
  if auth.role() <> 'service_role' and not caller_is_admin() then
    raise exception 'not_admin';
  end if;
  return coalesce((select json_agg(json_build_object(
      'instagram_handle', p.instagram_handle,
      'verified_at', p.verified_at) order by p.verified_at desc)
    from public.profiles p
    where p.verification_status = 'verified'
      and not exists (select 1 from public.claims c where c.user_id = p.user_id)), '[]'::json);
end $$;

-- privileges: nothing via PUBLIC, nothing for anon; authenticated may CALL the
-- admin functions but the in-function guard rejects non-admins.
revoke execute on function
  public.admin_verify(text, text), public.admin_reject(text),
  public.admin_revoke_claim(bigint), public.caller_is_admin(),
  public.admin_list_pending(), public.admin_list_claims(),
  public.admin_list_verified_unclaimed(),
  public.enforce_claim_limit(), public.setup_profile(text), public.claim_house(bigint),
  public.unclaim_house(), public.unclaim_house(bigint), public.my_status(),
  public.update_my_customization(bigint, jsonb), public.update_my_avatar(jsonb)
from public, anon, authenticated;

grant execute on function
  public.admin_verify(text, text), public.admin_reject(text),
  public.admin_revoke_claim(bigint), public.caller_is_admin(),
  public.admin_list_pending(), public.admin_list_claims(),
  public.admin_list_verified_unclaimed(),
  public.setup_profile(text), public.claim_house(bigint), public.unclaim_house(),
  public.unclaim_house(bigint), public.my_status(),
  public.update_my_customization(bigint, jsonb), public.update_my_avatar(jsonb)
to authenticated, service_role;

-- ───────────────────────────── NOTES ─────────────────────────────
-- MULTIPLAYER (added 2026-07-13)
-- Live position data stays in Realtime Broadcast/Presence and is never written
-- to Postgres. Only authenticated chat and authenticated visit durations are
-- persisted. Guests may appear in Presence as anonymous visitors.

create table if not exists public.player_sessions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles(user_id) on delete cascade,
  client_id       uuid not null,
  handle_snapshot text not null,
  started_at      timestamptz not null default now(),
  last_seen_at    timestamptz not null default now(),
  ended_at        timestamptz,
  constraint player_session_handle_format
    check (handle_snapshot ~ '^[a-z0-9._]{1,30}$'),
  constraint player_session_time_order
    check (ended_at is null or ended_at >= started_at)
);

create index if not exists player_sessions_user_started_idx
  on public.player_sessions (user_id, started_at desc);
create index if not exists player_sessions_online_idx
  on public.player_sessions (last_seen_at desc) where ended_at is null;

create table if not exists public.active_player_identities (
  client_id        uuid primary key,
  instagram_handle text not null,
  last_seen_at     timestamptz not null default now(),
  constraint active_player_handle_format
    check (instagram_handle ~ '^[a-z0-9._]{1,30}$')
);

create table if not exists public.chat_messages (
  id            bigint generated always as identity primary key,
  user_id       uuid not null references public.profiles(user_id) on delete cascade,
  sender_handle text not null,
  client_id     uuid not null,
  body          text not null,
  created_at    timestamptz not null default now(),
  constraint chat_sender_handle_format
    check (sender_handle ~ '^[a-z0-9._]{1,30}$'),
  constraint chat_body_length
    check (char_length(body) between 1 and 240)
);

create index if not exists chat_messages_created_idx
  on public.chat_messages (created_at desc);
create index if not exists chat_messages_user_created_idx
  on public.chat_messages (user_id, created_at desc);

alter table public.player_sessions enable row level security;
alter table public.active_player_identities enable row level security;
alter table public.chat_messages enable row level security;

drop policy if exists player_sessions_own_read on public.player_sessions;
create policy player_sessions_own_read on public.player_sessions
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists active_player_identities_public_read on public.active_player_identities;
create policy active_player_identities_public_read on public.active_player_identities
  for select to anon, authenticated using (true);

-- Guests and signed-in players may read only the safe chat fields. The auth
-- user UUID remains private even though the chat stream is public in-game.
drop policy if exists chat_public_read on public.chat_messages;
create policy chat_public_read on public.chat_messages
  for select to anon, authenticated using (true);

revoke all on table public.player_sessions from public, anon, authenticated;
revoke all on table public.active_player_identities from public, anon, authenticated;
revoke all on table public.chat_messages from public, anon, authenticated;
grant select (client_id, instagram_handle, last_seen_at)
  on public.active_player_identities to anon, authenticated;
grant select (id, sender_handle, client_id, body, created_at)
  on public.chat_messages to anon, authenticated;

create or replace function public.start_player_session(p_client_id uuid)
returns uuid
language plpgsql security definer set search_path = public, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_handle text;
  v_id uuid;
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;
  select instagram_handle into v_handle
    from public.profiles where user_id = v_uid;
  if v_handle is null then raise exception 'profile_missing'; end if;

  -- A reload reuses the tab client id. Close its prior record cleanly before
  -- starting a new one instead of leaving two apparently-online sessions.
  update public.player_sessions
     set last_seen_at = now(), ended_at = now()
   where user_id = v_uid and client_id = p_client_id and ended_at is null;

  insert into public.player_sessions (user_id, client_id, handle_snapshot)
  values (v_uid, p_client_id, v_handle)
  returning id into v_id;
  insert into public.active_player_identities (client_id, instagram_handle, last_seen_at)
  values (p_client_id, v_handle, now())
  on conflict (client_id) do update
    set instagram_handle = excluded.instagram_handle,
        last_seen_at = excluded.last_seen_at;
  return v_id;
end $$;

create or replace function public.heartbeat_player_session(p_session_id uuid)
returns void
language plpgsql security definer set search_path = public, pg_temp
as $$
declare v_client_id uuid; v_handle text;
begin
  if auth.uid() is null then raise exception 'not_authenticated'; end if;
  update public.player_sessions set last_seen_at = now()
   where id = p_session_id and user_id = auth.uid() and ended_at is null
  returning client_id, handle_snapshot into v_client_id, v_handle;
  if not found then raise exception 'session_not_found'; end if;
  insert into public.active_player_identities (client_id, instagram_handle, last_seen_at)
  values (v_client_id, v_handle, now())
  on conflict (client_id) do update
    set instagram_handle = excluded.instagram_handle,
        last_seen_at = excluded.last_seen_at;
end $$;

create or replace function public.end_player_session(p_session_id uuid)
returns void
language plpgsql security definer set search_path = public, pg_temp
as $$
declare v_client_id uuid;
begin
  if auth.uid() is null then raise exception 'not_authenticated'; end if;
  update public.player_sessions
     set last_seen_at = now(), ended_at = now()
   where id = p_session_id and user_id = auth.uid() and ended_at is null
   returning client_id into v_client_id;
  if v_client_id is not null then
    delete from public.active_player_identities where client_id = v_client_id;
  end if;
end $$;

create or replace function public.send_chat_message(p_body text, p_client_id uuid)
returns json
language plpgsql security definer set search_path = public, pg_temp
as $$
declare
  v_uid uuid := auth.uid();
  v_handle text;
  v_body text := trim(coalesce(p_body, ''));
  v_row public.chat_messages;
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;
  if char_length(v_body) < 1 or char_length(v_body) > 240 then
    raise exception 'bad_chat_length';
  end if;
  select instagram_handle into v_handle
    from public.profiles where user_id = v_uid;
  if v_handle is null then raise exception 'profile_missing'; end if;
  if exists (select 1 from public.chat_messages
             where user_id = v_uid and created_at > now() - interval '1 second') then
    raise exception 'chat_rate_limited';
  end if;
  insert into public.chat_messages (user_id, sender_handle, client_id, body)
  values (v_uid, v_handle, p_client_id, v_body)
  returning * into v_row;
  return json_build_object(
    'id', v_row.id, 'sender_handle', v_row.sender_handle,
    'client_id', v_row.client_id, 'body', v_row.body,
    'created_at', v_row.created_at);
end $$;

create or replace function public.admin_list_multiplayer(p_limit integer default 200)
returns json
language plpgsql stable security definer set search_path = public, pg_temp
as $$
declare v_limit integer := greatest(1, least(coalesce(p_limit, 200), 500));
begin
  if coalesce(auth.jwt()->>'role', '') <> 'service_role'
     and not public.caller_is_admin() then
    raise exception 'not_admin';
  end if;
  return json_build_object(
    'online', coalesce((select json_agg(row_to_json(x)) from (
      select id, handle_snapshot as instagram_handle, started_at, last_seen_at,
             greatest(0, extract(epoch from (now() - started_at))::integer) as duration_seconds
      from public.player_sessions
      where ended_at is null and last_seen_at > now() - interval '90 seconds'
      order by started_at desc
    ) x), '[]'::json),
    'sessions', coalesce((select json_agg(row_to_json(x)) from (
      select id, handle_snapshot as instagram_handle, started_at, last_seen_at,
             case when ended_at is null and last_seen_at > now() - interval '90 seconds'
                  then null else coalesce(ended_at, last_seen_at) end as ended_at,
             (ended_at is null and last_seen_at > now() - interval '90 seconds') as is_online,
             greatest(0, extract(epoch from
               (case when ended_at is null and last_seen_at > now() - interval '90 seconds'
                     then now() else coalesce(ended_at, last_seen_at) end - started_at))::integer)
               as duration_seconds
      from public.player_sessions order by started_at desc limit v_limit
    ) x), '[]'::json),
    'chat', coalesce((select json_agg(row_to_json(x)) from (
      select id, sender_handle as instagram_handle, body, created_at
      from public.chat_messages order by created_at desc limit v_limit
    ) x), '[]'::json)
  );
end $$;

revoke execute on function
  public.start_player_session(uuid), public.heartbeat_player_session(uuid),
  public.end_player_session(uuid), public.send_chat_message(text, uuid),
  public.admin_list_multiplayer(integer)
from public, anon, authenticated;

grant execute on function
  public.start_player_session(uuid), public.heartbeat_player_session(uuid),
  public.end_player_session(uuid), public.send_chat_message(text, uuid)
to authenticated;
grant execute on function public.admin_list_multiplayer(integer)
to authenticated, service_role;
drop function if exists public.active_player_identities();

do $$
begin
  alter publication supabase_realtime add table public.chat_messages;
exception when duplicate_object then null;
end $$;

-- Abuse safety net (no schema needed):
--  * Enable CAPTCHA (Cloudflare Turnstile) in Supabase Dashboard →
--    Auth → Settings → Bot and Abuse Protection.
--  * Supabase Auth already rate-limits signups/emails per IP by default.
--  * admin_revoke_claim() above is the "revoke a reported fraudulent claim" tool.
--
-- Pending verifications queue (run in SQL Editor to see who's waiting):
--   select instagram_handle, verification_code, created_at
--   from profiles where verification_status = 'pending' order by created_at;
--
-- To make a specific building unclaimable (or claimable) later:
--   update houses set claimable = false where id = <seed>;

-- ════════════════ MAYORAL ELECTION v1 (added 2026-08-05) ════════════════
-- Ships as supabase_migrations/20260805_election_v1.sql, mirrored here so
-- this file stays the single re-runnable canonical schema. A "citizen" is
-- exactly verification_status = 'verified': no new account concept.
-- One vote per citizen is election_votes PRIMARY KEY (election_id, user_id);
-- votes are insert-only, so a cast ballot can never be changed.
-- Full design notes and the rollback live in the migration file.
-- ───────────────────────────── TABLES ─────────────────────────────

create table if not exists public.elections (
  id           bigint generated always as identity primary key,
  title        text not null,
  blurb        text not null default '',
  starts_at    timestamptz,
  ends_at      timestamptz,
  is_published boolean not null default false,
  created_at   timestamptz not null default now(),
  constraint election_title_length check (char_length(title) between 1 and 120),
  constraint election_blurb_length check (char_length(blurb) <= 600),
  constraint election_window_order
    check (starts_at is null or ends_at is null or ends_at > starts_at)
);

create table if not exists public.election_candidates (
  id               bigint generated always as identity primary key,
  election_id      bigint not null references public.elections(id) on delete cascade,
  instagram_handle text not null,
  display_name     text,
  pitch            text not null default '',
  created_at       timestamptz not null default now(),
  -- same handle shape the rest of the site enforces on profiles
  constraint candidate_handle_format check (instagram_handle ~ '^[a-z0-9._]{1,30}$'),
  constraint candidate_pitch_length check (char_length(pitch) <= 280),
  constraint candidate_name_length
    check (display_name is null or char_length(display_name) between 1 and 60),
  constraint candidate_unique_per_election unique (election_id, instagram_handle)
);

-- Lets a vote's composite foreign key prove its candidate belongs to the very
-- election the vote was cast in — a candidate id alone could not.
alter table public.election_candidates
  drop constraint if exists election_candidates_id_election_key;
alter table public.election_candidates
  add constraint election_candidates_id_election_key unique (id, election_id);

create table if not exists public.election_votes (
  election_id  bigint not null references public.elections(id) on delete cascade,
  user_id      uuid not null references public.profiles(user_id) on delete cascade,
  candidate_id bigint not null,
  created_at   timestamptz not null default now(),
  -- THE one-vote-per-citizen rule. Enforced by the database, not the browser.
  primary key (election_id, user_id)
);

alter table public.election_votes
  drop constraint if exists election_votes_candidate_in_election_fk;
alter table public.election_votes
  add constraint election_votes_candidate_in_election_fk
  foreign key (candidate_id, election_id)
  references public.election_candidates (id, election_id) on delete cascade;

create index if not exists election_votes_candidate_idx
  on public.election_votes (candidate_id);
create index if not exists election_candidates_election_idx
  on public.election_candidates (election_id);

-- ───────────────────────────── RLS ─────────────────────────────
-- All three tables are enabled with NO select policy and no grants. Every read
-- goes through election_state() (which decides what a caller is allowed to
-- see) and every write through cast_vote() or a guarded admin function. This
-- is why an unpublished draft ballot cannot leak: there is no direct path.

alter table public.elections           enable row level security;
alter table public.election_candidates enable row level security;
alter table public.election_votes      enable row level security;

revoke all on table public.elections           from public, anon, authenticated;
revoke all on table public.election_candidates from public, anon, authenticated;
revoke all on table public.election_votes      from public, anon, authenticated;

-- ───────────────────────── READ + VOTE RPCs ─────────────────────────

-- The single source of truth for the /vote page. Callable by anyone, but what
-- comes back depends on who is asking:
--   * signed out / pending / rejected  -> election teaser only (title, window,
--     candidate count). No names, no tallies, no ballot.
--   * verified citizen -> the full ballot with live counts and their own vote.
-- Counts are public-to-citizens on purpose: The owner chose a live leaderboard.
create or replace function public.election_state()
returns json
language plpgsql stable security definer set search_path = ''
as $$
declare
  v_uid       uuid := auth.uid();
  v_election  public.elections;
  v_status    text;
  v_citizen   boolean := false;
  v_open      boolean;
  v_total     integer := 0;
  v_my_vote   bigint;
  v_candidates json;
begin
  select * into v_election
    from public.elections
   where is_published
   order by starts_at desc nulls last, id desc
   limit 1;

  if v_uid is not null then
    select verification_status into v_status
      from public.profiles where user_id = v_uid;
    v_citizen := coalesce(v_status, '') = 'verified';
  end if;

  -- Tested on v_election.id, never on FOUND: the profiles lookup just above
  -- resets FOUND, and a signed-in visitor with no profile row would otherwise
  -- be told there is no election at all.
  if v_election.id is null then
    return json_build_object(
      'election', null,
      'signed_in', v_uid is not null,
      'verification_status', v_status,
      'is_citizen', v_citizen);
  end if;

  v_open := v_election.starts_at is not null
        and v_election.ends_at is not null
        and now() >= v_election.starts_at
        and now() <  v_election.ends_at;

  if v_citizen then
    select count(*) into v_total
      from public.election_votes where election_id = v_election.id;
    select candidate_id into v_my_vote
      from public.election_votes
     where election_id = v_election.id and user_id = v_uid;
    -- Returned in a stable alphabetical order. The page sorts its own copy by
    -- votes for the leaderboard, so ballot order never tracks who is winning.
    select coalesce(json_agg(row_to_json(c) order by c.instagram_handle), '[]'::json)
      into v_candidates
      from (
        select k.id, k.instagram_handle, k.display_name, k.pitch,
               (select count(*) from public.election_votes v
                 where v.candidate_id = k.id)::integer as votes
          from public.election_candidates k
         where k.election_id = v_election.id
      ) c;
  end if;

  return json_build_object(
    'election', json_build_object(
      'id', v_election.id,
      'title', v_election.title,
      'blurb', v_election.blurb,
      'starts_at', v_election.starts_at,
      'ends_at', v_election.ends_at,
      'is_open', v_open,
      'has_opened', v_election.starts_at is not null and now() >= v_election.starts_at,
      'has_closed', v_election.ends_at is not null and now() >= v_election.ends_at,
      'server_now', now(),
      'candidate_count', (select count(*) from public.election_candidates
                           where election_id = v_election.id)),
    'signed_in', v_uid is not null,
    'verification_status', v_status,
    'is_citizen', v_citizen,
    'my_vote', v_my_vote,
    'total_votes', case when v_citizen then v_total else null end,
    'candidates', case when v_citizen then v_candidates else null end);
end $$;

-- The vote. Insert-only and final: there is no update path anywhere in this
-- file, so a cast ballot cannot be changed by the voter, and the primary key
-- makes a second one impossible even under a double-click or a race.
create or replace function public.cast_vote(p_candidate_id bigint)
returns json
language plpgsql security definer set search_path = ''
as $$
declare
  v_uid      uuid := auth.uid();
  v_verified boolean;
  v_election public.elections;
begin
  if v_uid is null then raise exception 'not_authenticated'; end if;

  select verification_status = 'verified' into v_verified
    from public.profiles where user_id = v_uid;
  if not found or not coalesce(v_verified, false) then
    raise exception 'not_verified';
  end if;

  select * into v_election
    from public.elections
   where is_published
   order by starts_at desc nulls last, id desc
   limit 1;
  if not found then raise exception 'no_election'; end if;

  if v_election.starts_at is null or v_election.ends_at is null
     or now() < v_election.starts_at then
    raise exception 'polls_not_open';
  end if;
  if now() >= v_election.ends_at then
    raise exception 'polls_closed';
  end if;

  if not exists (select 1 from public.election_candidates
                  where id = p_candidate_id and election_id = v_election.id) then
    raise exception 'unknown_candidate';
  end if;

  insert into public.election_votes (election_id, user_id, candidate_id)
  values (v_election.id, v_uid, p_candidate_id);

  return json_build_object('election_id', v_election.id,
                           'candidate_id', p_candidate_id);
exception
  when unique_violation then
    raise exception 'already_voted';
end $$;

-- ───────────────────────── ADMIN RPCs ─────────────────────────
-- Same guard shape as every other admin function here: the check lives inside
-- the function, so the page enforcing nothing is not a security problem.

create or replace function public.admin_election_save(
  p_id bigint default null,
  p_title text default 'Followville mayoral election',
  p_blurb text default '',
  p_starts_at timestamptz default null,
  p_ends_at timestamptz default null,
  p_is_published boolean default false)
returns json
language plpgsql security definer set search_path = ''
as $$
declare v_row public.elections;
begin
  if coalesce(auth.jwt()->>'role', '') <> 'service_role'
     and not public.caller_is_admin() then
    raise exception 'not_admin';
  end if;

  if p_id is null then
    insert into public.elections (title, blurb, starts_at, ends_at, is_published)
    values (coalesce(nullif(trim(p_title), ''), 'Followville mayoral election'),
            coalesce(p_blurb, ''), p_starts_at, p_ends_at, coalesce(p_is_published, false))
    returning * into v_row;
  else
    update public.elections
       set title = coalesce(nullif(trim(p_title), ''), title),
           blurb = coalesce(p_blurb, blurb),
           starts_at = p_starts_at,
           ends_at = p_ends_at,
           is_published = coalesce(p_is_published, is_published)
     where id = p_id
     returning * into v_row;
    if not found then raise exception 'no_such_election'; end if;
  end if;
  return row_to_json(v_row);
end $$;

-- One button for the thing the owner actually does: start the 48-hour poll now.
create or replace function public.admin_election_open_48h(p_election_id bigint)
returns json
language plpgsql security definer set search_path = ''
as $$
declare v_row public.elections;
begin
  if coalesce(auth.jwt()->>'role', '') <> 'service_role'
     and not public.caller_is_admin() then
    raise exception 'not_admin';
  end if;
  if not exists (select 1 from public.election_candidates
                  where election_id = p_election_id) then
    raise exception 'no_candidates';
  end if;
  update public.elections
     set starts_at = now(), ends_at = now() + interval '48 hours', is_published = true
   where id = p_election_id
   returning * into v_row;
  if not found then raise exception 'no_such_election'; end if;
  return row_to_json(v_row);
end $$;

-- Ends the poll early. Votes already cast are kept and the result stands.
create or replace function public.admin_election_close(p_election_id bigint)
returns json
language plpgsql security definer set search_path = ''
as $$
declare v_row public.elections;
begin
  if coalesce(auth.jwt()->>'role', '') <> 'service_role'
     and not public.caller_is_admin() then
    raise exception 'not_admin';
  end if;
  update public.elections set ends_at = now()
   where id = p_election_id returning * into v_row;
  if not found then raise exception 'no_such_election'; end if;
  return row_to_json(v_row);
end $$;

create or replace function public.admin_candidate_add(
  p_election_id bigint,
  p_handle text,
  p_display_name text default null,
  p_pitch text default '')
returns json
language plpgsql security definer set search_path = ''
as $$
declare
  v_handle text := lower(trim(both '@' from trim(coalesce(p_handle, ''))));
  v_row public.election_candidates;
begin
  if coalesce(auth.jwt()->>'role', '') <> 'service_role'
     and not public.caller_is_admin() then
    raise exception 'not_admin';
  end if;
  if v_handle !~ '^[a-z0-9._]{1,30}$' then raise exception 'bad_handle'; end if;
  if not exists (select 1 from public.elections where id = p_election_id) then
    raise exception 'no_such_election';
  end if;
  -- The ballot is frozen the moment the first citizen votes, so nobody can be
  -- added to a race that is already partly decided.
  if exists (select 1 from public.election_votes where election_id = p_election_id) then
    raise exception 'ballot_locked';
  end if;

  insert into public.election_candidates (election_id, instagram_handle, display_name, pitch)
  values (p_election_id, v_handle,
          nullif(trim(coalesce(p_display_name, '')), ''),
          left(coalesce(p_pitch, ''), 280))
  returning * into v_row;
  return row_to_json(v_row);
exception
  when unique_violation then raise exception 'candidate_exists';
end $$;

create or replace function public.admin_candidate_remove(p_candidate_id bigint)
returns void
language plpgsql security definer set search_path = ''
as $$
declare v_election_id bigint;
begin
  if coalesce(auth.jwt()->>'role', '') <> 'service_role'
     and not public.caller_is_admin() then
    raise exception 'not_admin';
  end if;
  select election_id into v_election_id
    from public.election_candidates where id = p_candidate_id;
  if not found then raise exception 'no_such_candidate'; end if;
  if exists (select 1 from public.election_votes where election_id = v_election_id) then
    raise exception 'ballot_locked';
  end if;
  delete from public.election_candidates where id = p_candidate_id;
end $$;

-- Everything the admin page shows: every election, the live standings of the
-- requested one (default: the newest), and turnout against the citizen roll.
create or replace function public.admin_election_report(p_election_id bigint default null)
returns json
language plpgsql stable security definer set search_path = ''
as $$
declare
  v_election public.elections;
  v_eligible integer;
begin
  if coalesce(auth.jwt()->>'role', '') <> 'service_role'
     and not public.caller_is_admin() then
    raise exception 'not_admin';
  end if;

  if p_election_id is null then
    select * into v_election from public.elections
     order by created_at desc, id desc limit 1;
  else
    select * into v_election from public.elections where id = p_election_id;
  end if;

  select count(*) into v_eligible
    from public.profiles where verification_status = 'verified';

  return json_build_object(
    'elections', coalesce((select json_agg(row_to_json(e) order by e.created_at desc)
                             from public.elections e), '[]'::json),
    'election', case when v_election.id is null then null else row_to_json(v_election) end,
    'eligible_citizens', v_eligible,
    'total_votes', coalesce((select count(*) from public.election_votes
                              where election_id = v_election.id), 0),
    'ballot_locked', exists (select 1 from public.election_votes
                              where election_id = v_election.id),
    'candidates', coalesce((select json_agg(row_to_json(c)
                              order by c.votes desc, c.instagram_handle)
      from (
        select k.id, k.instagram_handle, k.display_name, k.pitch, k.created_at,
               (select count(*) from public.election_votes v
                 where v.candidate_id = k.id)::integer as votes
          from public.election_candidates k
         where k.election_id = v_election.id
      ) c), '[]'::json));
end $$;

-- ───────────────────────── PRIVILEGES ─────────────────────────
-- Functions are granted to PUBLIC by default, so revoke first, then grant
-- narrowly. election_state() is the only one anon may call.

revoke execute on function
  public.election_state(), public.cast_vote(bigint),
  public.admin_election_save(bigint, text, text, timestamptz, timestamptz, boolean),
  public.admin_election_open_48h(bigint), public.admin_election_close(bigint),
  public.admin_candidate_add(bigint, text, text, text),
  public.admin_candidate_remove(bigint), public.admin_election_report(bigint)
from public, anon, authenticated;

grant execute on function public.election_state() to anon, authenticated, service_role;
grant execute on function public.cast_vote(bigint) to authenticated;
grant execute on function
  public.admin_election_save(bigint, text, text, timestamptz, timestamptz, boolean),
  public.admin_election_open_48h(bigint), public.admin_election_close(bigint),
  public.admin_candidate_add(bigint, text, text, text),
  public.admin_candidate_remove(bigint), public.admin_election_report(bigint)
to authenticated, service_role;
