-- ============================================================================
-- FOLLOWVILLE — claimable homes schema (Supabase / Postgres)
-- Run this ONCE in the Supabase SQL Editor of the Followville project.
-- Safe to re-run: everything is IF NOT EXISTS / CREATE OR REPLACE.
--
-- Design notes (see CLAIMING_SETUP.md for the full guide):
-- * houses.id  = the building's `seed` from world_state.json (already a
--   globally-unique, monotonically-increasing integer — no new id scheme).
-- * One house per account AND one account per house are enforced by the
--   PRIMARY KEY on claims.house_id + UNIQUE on claims.user_id — at the
--   database level, so concurrent claims can never double-assign.
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
  constraint handle_format check (instagram_handle ~ '^[a-z0-9._]{1,30}$')
);

create table if not exists public.claims (
  house_id      bigint primary key references public.houses(id),
  user_id       uuid not null unique references public.profiles(user_id) on delete cascade,
  claimed_at    timestamptz not null default now(),
  customization jsonb                         -- future use (house color etc.); null for now
);

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

grant select on public.public_claims to anon, authenticated;

-- No insert/update/delete policies anywhere: all writes go through the
-- SECURITY DEFINER functions below (or the service-role key, which bypasses RLS).

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

-- THE claim. Concurrency safety comes from the unique constraints: whichever
-- transaction commits first wins; the loser's INSERT fails atomically.
create or replace function public.claim_house(p_house_id bigint)
returns json
language plpgsql security definer set search_path = public
as $$
declare
  v_uid  uuid := auth.uid();
  v_row  public.claims;
begin
  if v_uid is null then
    raise exception 'not_authenticated';
  end if;
  if not exists (select 1 from public.profiles
                 where user_id = v_uid and verification_status = 'verified') then
    raise exception 'not_verified';
  end if;
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
    if exists (select 1 from public.claims where user_id = v_uid) then
      raise exception 'already_have_house';
    else
      raise exception 'house_taken';
    end if;
end $$;

-- Give up your own house (added 2026-07-10). Frees the row for anyone (including
-- the caller) to claim again; the same claims.user_id UNIQUE constraint that
-- enforces one-house-per-account keeps enforcing it afterward -- this is just
-- the reverse of claim_house(), nothing new to enforce.
create or replace function public.unclaim_house()
returns void
language plpgsql security definer set search_path = public
as $$
declare
  v_uid uuid := auth.uid();
begin
  if v_uid is null then
    raise exception 'not_authenticated';
  end if;
  delete from public.claims where user_id = v_uid;
  if not found then
    raise exception 'no_claim';
  end if;
end $$;

-- Own-status readback for the UI (avoids exposing profiles more broadly).
create or replace function public.my_status()
returns json
language sql security definer set search_path = public stable
as $$
  select json_build_object(
    'profile', (select row_to_json(p) from public.profiles p where p.user_id = auth.uid()),
    'claim',   (select row_to_json(c) from public.claims   c where c.user_id = auth.uid())
  );
$$;

grant execute on function public.setup_profile(text)  to authenticated;
grant execute on function public.claim_house(bigint)  to authenticated;
grant execute on function public.unclaim_house()      to authenticated;
grant execute on function public.my_status()          to authenticated;
revoke execute on function public.setup_profile(text), public.claim_house(bigint), public.unclaim_house(), public.my_status() from anon;

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
where instagram_handle in ('cade.toohey', 'stellarkehler');

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
  public.setup_profile(text), public.claim_house(bigint), public.unclaim_house(), public.my_status()
from public, anon, authenticated;

grant execute on function
  public.admin_verify(text, text), public.admin_reject(text),
  public.admin_revoke_claim(bigint), public.caller_is_admin(),
  public.admin_list_pending(), public.admin_list_claims(),
  public.admin_list_verified_unclaimed(),
  public.setup_profile(text), public.claim_house(bigint), public.unclaim_house(), public.my_status()
to authenticated, service_role;

-- ───────────────────────────── NOTES ─────────────────────────────
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
