# Master prompt: Followville accounts + home claiming

> **Historical implementation brief.** The claiming system is already live.
> Use `CLAIMING_SETUP.md`, `supabase_schema.sql`, and current handoff files for
> operations; do not rebuild or migrate from this original starting spec.

Paste this whole document as the first message in a new Claude (Fable) chat to start
building this feature. It's self-contained — read `CLAUDE.md` in this project folder
first for full context on what Followville already is before writing any code.

## What Followville is (read CLAUDE.md for the full picture)

Followville is Cade's Instagram growth project: a persistent 3D low-poly town built in
Blender, where every follower gained = a new house. `neighborhood_blender.py` (headless
Blender, run via `grow_windows.bat`/`grow.sh`) grows the town and writes the current state
to `world_state.json`, then `export_web.py` bakes the real geometry to `town.glb`. The
site is currently static: `index.html` (landing/stats page) + `town.html` (a Three.js
first-person walkable version of the town, GLTFLoader-based) + `town.glb` +
`world_state.json`, hosted on Vercel, deployed via a GitHub repo
(`github.com/tooheycade-design/followville`) that auto-redeploys on push to `main`.
There is currently **no backend, no accounts, no database** — it's pure static files.

## The feature: claimable homes with accounts

Goal: let real Instagram followers create an account on the website, verify who they are,
and claim exactly one existing house in the town as "theirs." Read the full requirements
below — they were worked out with Cade before this prompt was written, including the two
decisions he already made (verification approach and backend stack), so don't re-litigate
those; build them.

### Core rules
- One account per person, enforced via a **verified Instagram handle** (see verification
  below) — not just an email, since the whole point is tying a house to a real follower.
- One house per account, and one account per house — both directions must be enforced
  atomically at the database level, not just in application code, because this needs to
  survive concurrent claim attempts without ever double-assigning a house.
- Claims must **live-update** across all connected users: if two people are looking at the
  same open house, whoever's claim transaction commits first wins, and the other person's
  view must reflect "taken" immediately (or their own claim attempt must fail cleanly and
  tell them so).
- Must scale to potentially thousands of new signups/claims **per day** without falling
  over. (Today's actual growth is ~1-5 followers/day — this is explicitly a "build with
  headroom" requirement, not today's real load.)
- Future-proof for house customization (e.g. changing a house's color), restricted to the
  verified owner of that specific house only. Don't build customization now — just don't
  design the schema in a way that makes adding it later painful.

## The hard platform constraint (already researched — don't relitigate)

**Meta's official Instagram API has no endpoint to check whether a specific account
follows another account.** There is no "is this user a follower of me" check available,
full stop — this was confirmed via research before this prompt was written. Any design
that assumes this is possible is wrong. What IS available:
- **Instagram API with Instagram Login** (OAuth): lets a user log in with their own
  Instagram identity, but Meta only permits this for accounts that are themselves
  Business/Creator type — most everyday followers have Personal accounts and would need
  to convert first (free and reversible, but real friction, and not everyone will do it).
- **Instagram Graph API + Messaging API**: available to Followville's own account (which
  can and should be a Business/Creator account), lets Followville programmatically read
  incoming DMs/comments on its own account. This does NOT prove someone follows the
  account — DMs/comments don't require following, depending on privacy settings — but it
  DOES prove the person typing the code actually controls that specific Instagram handle,
  which is the real problem worth solving (stopping one person from claiming 50 houses
  under 50 handles they don't own).

## Decided approach (Cade already chose these — build to this spec)

**Verification: DM/bio-code challenge.**
1. User signs up on the site with email/password (or magic link) via Supabase Auth, and
   types their Instagram handle.
2. The backend generates a one-time verification code tied to their account.
3. UI instructs them to either DM that code to `@followville`'s Instagram account, or add
   it temporarily to their Instagram bio (support whichever is easier to detect via the
   Messaging/Graph API — investigate both during build and pick the more reliable one).
4. A webhook/poll against the Instagram Messaging API (or Graph API for bio-checking)
   detects the code and flips `verification_status` to `verified` for that user, tied to
   their specific Instagram user id (not just the typed string — handles can change).
5. **Real-world caveat to design around**: using the Messaging API at meaningful volume
   requires Followville's Instagram account to be Business/Creator, a registered Meta
   Developer App, and Meta's app review for the messaging permission — which has real
   external lead time (historically days to weeks, entirely outside our control). Build
   the `verification_status` flow generically (pending / verified / rejected) so that
   while the Meta app review is pending, verification can be **manually approved by Cade**
   (an admin action) as a stand-in — then swap in the automated webhook once Meta approves,
   with zero schema changes. Do not block the whole feature launch on Meta's review timeline.
6. Because true cryptographic proof-of-follow isn't possible, add a lightweight abuse
   safety net regardless: rate-limit signups per IP/device, and give Cade a simple way to
   revoke a claim (e.g. an admin table flag) if a fraudulent claim is reported later.

**Backend: Supabase** (Postgres + built-in Auth + built-in Realtime). Keep the frontend on
Vercel — Supabase pairs cleanly with that and needs no custom server infrastructure. This
comfortably handles thousands of daily signups/claims; it is not the bottleneck. The
Instagram Messaging API's rate limits and app-review tier are the actual ceiling at high
volume, not this stack.

## Data model (Postgres via Supabase) — starting point, adjust as needed

```sql
-- One row per claimable building. Synced from world_state.json (see sync section below).
create table houses (
  id           bigint primary key,   -- reuse the building's existing `seed` from
                                      -- world_state.json — it's already a globally unique,
                                      -- monotonically-increasing integer assigned once per
                                      -- building at creation time in neighborhood_blender.py.
                                      -- Don't invent a new id scheme; this one is free.
  gx           int not null,
  gy           int not null,
  building_type text not null,       -- e.g. "house", "apartment" -- matches world_state.json
  day_built    int not null,
  claimable    boolean not null default true,  -- see "assumptions to confirm" below
  created_at   timestamptz not null default now()
);

-- Extends Supabase's built-in auth.users
create table profiles (
  user_id             uuid primary key references auth.users(id),
  instagram_handle    text not null,             -- normalized lowercase
  instagram_user_id   text,                      -- filled in once verified, if obtainable
  verification_status text not null default 'pending', -- pending | verified | rejected
  verification_code   text not null,
  verified_at          timestamptz,
  created_at          timestamptz not null default now(),
  unique (instagram_handle)
);

-- The actual claim. Both unique constraints together are what guarantee
-- "one house per account" AND "one account per house" at the database level.
create table claims (
  house_id     bigint not null references houses(id) unique,
  user_id      uuid not null references profiles(user_id) unique,
  claimed_at   timestamptz not null default now(),
  customization jsonb  -- future use (e.g. house color); null until that feature ships
);
```

Claiming must go through a single Postgres function/RPC call (not a check-then-write from
the client), something like:

```sql
create or replace function claim_house(p_house_id bigint, p_user_id uuid)
returns claims as $$
  -- verify p_user_id's profile has verification_status = 'verified' first,
  -- then INSERT INTO claims — let the unique constraints do the concurrency-safety work.
  -- If either unique constraint fails, the insert fails atomically and the caller
  -- should show "already claimed" / "you already have a house" accordingly.
$$ language plpgsql;
```

Subscribe the frontend to Supabase Realtime on the `claims` table so every connected
client's map of "which houses are taken" updates live the instant any claim commits.

## Syncing the Blender growth pipeline with the `houses` table

This is a new integration point that's easy to forget (this project has already been
bitten twice by "forgot to wire step B into the pipeline" — see CLAUDE.md's deploy and
pancake-bug history — don't repeat that pattern here). Every time `grow_windows.bat`/
`grow.sh` grows the town and adds new buildings to `world_state.json`, those new buildings
must also get inserted as new rows in `houses` (unclaimed, `claimable` set per the type
rule below) before they can show up as claimable on the site. Add this as an explicit step
at the end of the grow pipeline (after the existing git push), e.g. a small script that
reads `world_state.json`, diffs against what's already in the `houses` table by `seed`/id,
and upserts any missing rows via Supabase's REST API with a service-role key.

## Frontend (`town.html`) changes needed

1. **Auth UI**: sign up / log in via Supabase Auth (email+password or magic link). Sign-up
   also collects the Instagram handle and kicks off the verification flow described above.
2. **Landing routing logic**, on page load:
   - Not logged in → default to **Explore Followville** (today's existing free-roam mode,
     unchanged).
   - Logged in, no claim yet → offer **Claim a Home**; clicking it (if not yet verified)
     shows the code + DM/bio instructions, then once verified drops them into the scene
     with a **one-time tutorial overlay**: "walk up to any open house and press [E] to
     claim it."
   - Logged in, already has a claim → **Go to Home** spawns them directly at their house's
     world position (reuse the same `lot_to_world(gx, gy)` grid math already in
     `neighborhood_blender.py` — it's simple arithmetic, port it to JS).
3. **Proximity + interact**: each frame, distance-check the player against unclaimed
   houses' world positions; within range, show a "Press E to claim" prompt; on keypress,
   call the `claim_house` RPC. Handle both outcomes: success (lock the house to them
   visually, e.g. a name tag or marker), and failure (someone else just claimed it —
   refresh state from Realtime and tell them).

## Assumptions to confirm with Cade before/while building (don't silently guess)

- Are the 10 **founder houses** (mushroom, casino, cat, castle, Eiffel, hydrangea, Burj
  Khalifa, toilet, beach house, cottage) and **milestone buildings** (fountain plaza,
  skyscraper, stadium) excluded from the public claim pool (`claimable = false`), since
  they represent specific real people/milestones rather than anonymous new followers? This
  prompt assumes yes — confirm before shipping.
- Confirm with Cade which of DM-code vs bio-code is easier to reliably automate once you've
  looked at the current Instagram Messaging/Graph API docs — pick one as the primary path.
- Confirm the manual-admin-approval fallback (for while Meta's app review is pending) is
  acceptable to Cade as a launch stopgap.

## Where to look first

Read `CLAUDE.md` in this folder in full before writing code — it has the complete history
of this project's pitfalls (iCloud sync races, the pancaked-houses export bug, the
git-backed state migration) and current file layout. Don't touch `world_state.json`,
`neighborhood_blender.py`, or the git-backed grow pipeline destructively — this feature is
additive (a new backend + frontend changes to `town.html`), not a replacement for how the
town itself grows.
