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
grant execute on function public.my_status()          to authenticated;
revoke execute on function public.setup_profile(text), public.claim_house(bigint), public.my_status() from anon;

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
