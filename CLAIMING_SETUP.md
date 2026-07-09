# Followville — Claimable Homes: setup + admin guide

Real followers create an account on the site, verify their Instagram handle, and
claim exactly one house in the town. Built 2026-07-09 (Cade's Windows Claude, Fable).

**Stack:** Supabase (Postgres + Auth + Realtime) as the backend; the site stays
static on Vercel. New files: `supabase_schema.sql` (run once in Supabase),
`sync_houses.py` (Mac/manual sync), a PowerShell sync step inside
`grow_windows.ps1` (Windows, automatic), and account/claim UI inside `town.html`.

**Hard rules enforced at the DATABASE level** (survive concurrent claims):
one house per account and one account per house (`claims.house_id` primary key +
`claims.user_id` unique). All claims go through the `claim_house()` Postgres
function — first commit wins, the loser gets a clean "house_taken" error, and
Supabase Realtime pushes the change to every open browser instantly.

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

## 5. Future: house customization

`claims.customization` (jsonb) is already in the schema, null for now. When the
feature ships: add an `update_my_customization()` RPC that only touches the
caller's own claim row, and read the json in `town.html` when building name
tags / recoloring. No migration needed.

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
  └─ auth.users + profiles (verification) + houses + claims (constraints)
```

Claim UX in town.html: sign up (email+password+handle) → DM the code → admin
verifies → "claim a home" button → walk up to an open house → press E (or tap)
→ `claim_house` RPC → name tag appears for everyone in real time. `Go to my
home` spawns you at your own house. Not signed in = exact old free-roam.
