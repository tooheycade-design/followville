# Followville — Claimable Homes: setup + admin guide

Real followers create an account on the site, verify their Instagram handle,
and normally claim one house in the town. Trusted admin accounts may claim two.
Built 2026-07-09 (Cade's Windows Claude, Fable).

**Stack:** Supabase (Postgres + Auth + Realtime) as the backend; the site stays
static on Vercel. New files: `supabase_schema.sql` (run once in Supabase),
`sync_houses.py` (Mac/manual sync), a PowerShell sync step inside
`grow_windows.ps1` (Windows, automatic), and account/claim UI inside `town.html`.

**Hard rules enforced at the DATABASE level** (survive concurrent claims):
one account per house (`claims.house_id` primary key); one house per normal
account; and two per trusted `profiles.is_admin` account. `claim_house()` locks
the caller's profile row before counting, and `claims_enforce_owner_limit`
defends direct/service writes too. A simultaneous house collision gets a clean
`house_taken` error, and Realtime pushes the winner to every open browser.

**Unclaiming (added 2026-07-10, multi-home overload 2026-07-15):** followers
can give up an owned house with `unclaim_house(bigint)`. The explicit house ID
ensures a two-home admin removes only the selected row. The no-argument overload
remains for backward compatibility but refuses an ambiguous two-home request.

**Current migration state:** `allow_admins_two_homes` was applied to the live
Supabase project on 2026-07-15. It dropped the old per-user unique constraint,
added the locking limit trigger and targeted RPC overloads, and preserved all
27 claim rows present at that time. The public database has 30 claims across 29
handles as of the latest 2026-07-17 maintenance audit. `supabase_schema.sql` remains
the re-runnable canonical schema.

**Day 16 sync (2026-07-17):** the guarded growth pipeline inserted house rows
263-275 after canonical growth to population 272. All 13 are ordinary Day 16
claimable houses. The `claims` table remains at 30 rows across 29 accounts;
growth did not modify any owner or customization.

**Avatar persistence (applied 2026-07-17):**
`supabase_migrations/20260717_avatar_system_v1.sql`. It adds only a validated
`profiles.avatar` JSON object, an own-row update policy, column-level avatar
update permission, and a security-invoker save RPC. The live rollout preserved
55 profiles, 30 claims across 29 accounts, all 275 house rows, and the exact
claim snapshot. Authenticated own-profile saves passed; cross-profile updates,
anonymous execution, extra keys, and non-avatar column updates were rejected.
It did not touch claims, ownership, handles, verification, admin status, or
houses. Follow the isolated rollback procedure in `AVATAR_SYSTEM.md`.

**Seed 73 maintenance (applied 2026-07-17):** Git history and canonical state
identify seed 73 as a Day 9 `house` at grid `(-3,-3)`. A discarded concurrent
Day 9 road experiment had left only its Supabase row at `(5,-9)`, typed
`lanestreet`, and nonclaimable. The guarded repair changed only that row's
position/type/claimability and the public API now returns the canonical house
as claimable. The complete claims snapshot remained byte-for-byte identical:
30 claims across 29 accounts, with no owner or customization change. The
audited SQL and claim-safe rollback are retained in
`supabase_repairs/20260717_repair_seed_73.sql`.

**Multiplayer (added 2026-07-14):** the same Supabase project now backs website
Presence/movement, persistent town chat, and admin activity logs. Signed-in
sessions are stored in `player_sessions`; safe public handle/client mappings in
`active_player_identities`; chat in `chat_messages`. Clients write only through
`start_player_session`, `heartbeat_player_session`, `end_player_session`, and
`send_chat_message`. These functions derive identity from `auth.uid()`, while
RLS and column grants keep account UUIDs private. `admin_list_multiplayer()`
checks the existing admin flag before returning online/session/chat logs.

**Homeowner Mode (added 2026-07-15):** once a follower has a claim, the account
panel and start screen expose `customize my home`. Owners can preview and save
approved exterior, roof/accent, and door colors. The data model also retains the
previously offered yard choice in the existing `claims.customization` JSONB
column. Browser code never gets
direct UPDATE access: `update_my_customization(bigint,jsonb)` requires a house
ID owned by `auth.uid()`, rejects unknown values, normalizes the payload, and
updates only that row. Yard pieces are placed inward from every road-facing lot
edge (diagonally inward on corner lots). The existing `claims` Realtime
subscription makes saved looks appear for every open visitor.

**Temporary yard pause (2026-07-15):** Cade disabled the yard-piece presentation
pending a better redesign. `YARD_DECORATIONS_ENABLED` is false in `town.html`,
so saved pieces do not render and the chooser is hidden. Existing normalized
`customization.yard` values remain stored; do not delete them or run a database
migration. Exterior, roof/accent, and door customization remains live.

---

## 1. One-time setup (~15 minutes, Cade)

1. **Create the project:** [supabase.com](https://supabase.com) → New project →
   name it `followville` (free tier is plenty; it comfortably handles thousands
   of signups/claims per day — Instagram's API limits are the real ceiling, not this).
2. **Run the schema:** Dashboard → SQL Editor → paste ALL of
   `supabase_schema.sql` → Run. Safe to re-run anytime.
3. **Auth settings** (Dashboard → Authentication):
   - *Sign In / Up → Email*: **turn OFF "Confirm email"** for the smoothest flow
     (signup drops users straight into verification). Leaving it ON also works —
     the UI tells users to click the email link first.
   - *Bot and Abuse Protection*: **enable CAPTCHA** (Cloudflare Turnstile) —
     this plus Supabase's built-in per-IP rate limits is the signup abuse net.
4. **Get your keys:** Dashboard → Settings → API. You need:
   - Project URL (like `https://abcd1234.supabase.co`)
   - `anon public` key — safe to publish
   - `service_role` key — **SECRET**, server-side only
5. **Wire the frontend:** in `town.html`, near the top of the script, paste the
   URL and anon key into `SUPABASE_URL` / `SUPABASE_ANON_KEY`. (Until you do,
   the site behaves exactly as before — the feature is invisible.)
6. **Wire the sync:** create `supabase_sync.env` next to this file (it's
   gitignored and NOT in the deploy whitelist — it must never reach GitHub/Vercel):
   ```
   SUPABASE_URL=https://abcd1234.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=eyJ...the-service-role-key...
   ```
7. **Backfill the existing town:** run the sync once so all current buildings
   get `houses` rows — either `python3 sync_houses.py` (Mac/anywhere with
   Python), or on this PC just run any `grow_windows.bat replay` — the sync now
   runs automatically at the end and logs `HOUSES_SYNC_OK` in `grow_log.txt`.
8. **Deploy the site:** `deploy_website.bat` as usual (pushes the updated
   `town.html`/`index.html`). Done — the "Claim your home" button is live.

## 2. Daily operation (nothing new to remember)

Growing the town (`grow_windows.bat +N` / `grow.sh +N`) now automatically
inserts the new buildings into the `houses` table after the git push. Check
`grow_log.txt` for `HOUSES_SYNC_OK`; if you ever see `HOUSES_SYNC_FAILED`, the
town itself is fine but new houses won't be claimable until you re-run a sync
(step 7 above). The sync is insert-only and idempotent — re-running never hurts
and never overwrites manual edits.

## 3. Verifying followers (manual, until Meta app review)

**The easy way (built 2026-07-09): the Admin button on the live site.** Log in
as @cade.toohey or @stellar.kehler on followville-kappa.vercel.app and an
"Admin →" button appears on the home page → one-click approve/reject for
everyone waiting, plus revoke on every claim. This is safe to have live
because the page holds no secrets: every admin action is a Postgres function
that checks `profiles.is_admin` server-side, so non-admins (or anyone with the
URL) get "No access" and the database refuses them. Manage who's admin with:
`update profiles set is_admin = true where instagram_handle = 'handle';`
`admin.bat` still works too (same page served locally, uses supabase_sync.env,
no login needed).

The manual SQL way (works from any machine with dashboard access):

True "does this person follow me?" checking is impossible via Instagram's API —
what verification proves is that the person **controls the handle** they typed
(stops one person claiming 50 houses under handles they don't own). Users get a
one-time code like `FV-3A7K2C` and are told to DM it to @followville (or put it
in their bio). While Meta app review is pending, YOU are the webhook:

- **See who's waiting** (SQL Editor):
  ```sql
  select instagram_handle, verification_code, created_at
  from profiles where verification_status = 'pending' order by created_at;
  ```
- **Check your Instagram DMs** for the code, then approve:
  ```sql
  select admin_verify('theirhandle');
  ```
- **Reject** a bogus one: `select admin_reject('theirhandle');`
- **Revoke a fraudulent claim** (frees the house AND blocks the account):
  ```sql
  select admin_revoke_claim(<house id>);
  ```

House ids = the building's `seed` in world_state.json. To make any building
unclaimable (or claimable): `update houses set claimable = false where id = <seed>;`

**Claimability defaults** (set at sync time, per Cade 2026-07-09): everything is
claimable — including the 10 founder houses and future milestone buildings —
EXCEPT non-dwellings (`pond`, `park`, `plaza`), which default to false. Flip any
row with the SQL above. The type list lives in `sync_houses.py`
(`NON_CLAIMABLE_TYPES`) and duplicated in `grow_windows.ps1` (`$NonClaimable`) —
change both if you change the rule.

## 4. Automating verification later (the Instagram DM webhook)

Decided approach: **DM-code is the primary path** (researched 2026-07-09):
bio-checking via the `business_discovery` API only works when the *follower's*
account is Business/Creator — most followers are Personal, so bios are
unreadable. DM webhooks work regardless of the sender's account type.

When ready:
1. Make @followville a Business/Creator account (probably already is).
2. Create a Meta Developer App, add Instagram Messaging, subscribe to `messages`
   webhooks. During development this works for up to **25 test users without
   app review** — enough to pilot.
3. Apply for `instagram_business_manage_messages` in Meta App Review (lead time:
   weeks, entirely outside our control — which is why launch doesn't wait for it).
4. Host the webhook as a **Supabase Edge Function**: on each incoming DM, look
   up the code in `profiles.verification_code` where status is `pending`, then
   do exactly what `admin_verify()` does — plus save the sender's
   Instagram-scoped user id into `instagram_user_id` (stable even if the handle
   changes later). **Zero schema changes needed** — that was the point of the
   generic pending/verified/rejected design.

Sources from the research: [Meta webhook docs](https://developers.facebook.com/docs/instagram-platform/webhooks),
[Messaging API](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/),
[business_discovery limits](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery/),
[app-review reality check](https://developers.chatwoot.com/self-hosted/instagram-app-review).

## 5. House customization (shipped 2026-07-15)

`claims.customization` stores only normalized palette IDs in this shape:

```json
{"version":1,"wall":"sage","roof":"charcoal","door":"red","yard":"flowers"}
```

Allowed values are defined in both `supabase_schema.sql` (the authoritative
security validation) and `town.html` (the picker/render palette). Keep those two
lists synchronized when adding an option. Never accept arbitrary CSS colors or
arbitrary decoration/model URLs from a client.
`update_my_customization(bigint,jsonb)` is intentionally executable only by
`authenticated` and updates the requested row only when it matches
`auth.uid()`; `anon` and `PUBLIC` have no execute grant. Re-running the complete
schema safely creates/replaces the RPC without changing existing claim rows.

Yard pieces are browser-only and are placed from the exported home's actual
root rotation, its full-height structural silhouette, and the distance to the
curb. They must stay between the façade and curb; tight founder lots scale the
front-to-back depth instead of shrinking the whole piece. Trees preserve equal
horizontal X/Z scale so they cannot become flat. Placement uses a
side-lawn zone: normal houses avoid their garage side, founder homes avoid their
actual door mesh, and corner lots choose the side away from their second road.
The placement boundary is `decorationObstacleFootprint()`, built from the full
exported wall/roof/door/garage/glass/trim geometry at every height. Optimized
houses are merged multi-material meshes, so this helper must inspect accepted
material groups/triangles rather than accepting the entire mesh; otherwise its
driveway/mailbox incorrectly becomes part of the facade. Do not use the player
collision footprint here. Founder house #29 is also authored 1.3m farther back
while its driveway/walk stay curb-connected, and its decorations use the open
side lawn between entry path and mailbox. Off-center suburban door materials
override the garage preference so the entrance always remains open.
Benches face the street and flags sit curbward so their poles clear porch roofs.
Do not restore the old fixed centerline/inward/backyard offset. The same
footprint helpers drive player collision:
homes and cars use oriented boxes, while trees collide only at their trunks.

## 6. How the pieces fit (for future AI sessions)

```
grow_windows.bat +N
  └─ Blender grows town → world_state.json + town.glb (git repo clone)
  └─ git commit + push  → Vercel redeploys world/GLB
  └─ Sync-Houses (NEW)  → inserts new buildings into Supabase `houses`
town.html (static, on Vercel)
  └─ world_state.json + town.glb → the 3D town (unchanged)
  └─ supabase-js (CDN) → auth, claim_house RPC, Realtime on `claims`,
                          name-tag sprites over claimed houses
Supabase
  └─ auth.users + profiles (verification/admin allowance) + houses + claims
     (house PK + per-owner limit trigger)
```

Claim UX in town.html: sign up (email+password+handle) → DM the code → admin
verifies → "claim a home" button → walk up to an open house → press E (or tap)
→ `claim_house` RPC → name tag appears for everyone in real time. `Go to my
home` spawns you at your own house. Not signed in = exact old free-roam.
Once you have a house, the account panel (click your `@handle ✓` button) shows
per-home visit, customize, and unclaim controls behind a one-step confirmation.
Admins see their 1/2 or 2/2 allowance plus `claim second home`; normal accounts
still see only one home. Every multi-home action passes the selected house ID.
