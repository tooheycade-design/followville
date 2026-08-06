-- ============================================================================
-- FOLLOWVILLE — Mayoral election v1 (2026-08-05)
--
-- Adds a 48-hour town election on top of the EXISTING citizenship system.
-- There is deliberately no new account concept: a "citizen" is exactly a
-- profile with verification_status = 'verified', i.e. someone Cade approved
-- from an Instagram DM code. This migration adds no column to profiles and
-- changes no existing table, function, claim, or house row.
--
-- The guarantees that matter, and where they live:
--   * one vote per citizen per election  -> election_votes PRIMARY KEY
--       (election_id, user_id). Not a UI check; two simultaneous requests
--       from the same account cannot both land.
--   * a vote is final                    -> no update path exists at all.
--       cast_vote() only ever INSERTs, and no client has UPDATE on the table.
--   * candidates may vote (incl. for themselves) -> candidates are handles on
--       a ballot, voters are accounts; nothing links them, so nothing blocks.
--   * the ballot is frozen once voting starts -> admin_candidate_remove()
--       refuses after the first vote is cast.
--   * only citizens see the ballot or the tally -> election_state() returns a
--       bare teaser to everyone else. The three tables have RLS enabled with
--       NO select policy and no grants, so they are unreachable directly.
--
-- Rollback (destroys votes — take a copy first):
--   drop function if exists public.admin_election_report(bigint);
--   drop function if exists public.admin_candidate_remove(bigint);
--   drop function if exists public.admin_candidate_add(bigint,text,text,text);
--   drop function if exists public.admin_election_close(bigint);
--   drop function if exists public.admin_election_open_48h(bigint);
--   drop function if exists public.admin_election_save(bigint,text,text,timestamptz,timestamptz,boolean);
--   drop function if exists public.cast_vote(bigint);
--   drop function if exists public.election_state();
--   drop table if exists public.election_votes;
--   drop table if exists public.election_candidates;
--   drop table if exists public.elections;
-- ============================================================================

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
-- Counts are public-to-citizens on purpose: Cade chose a live leaderboard.
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

-- One button for the thing Cade actually does: start the 48-hour poll now.
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
