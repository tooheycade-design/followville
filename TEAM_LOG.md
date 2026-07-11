# Team log — Followville

Plain-English log of who added/changed what, in order. Not a technical changelog
(see WEB_VIEWER_CHANGELOG.md for that) — just enough so Cade and Zach (and whichever
AI is helping each of them) can see what the other did on their turn.

## How to use this
- Whoever finishes a turn (Cade or Zach) adds ONE line before handing off, in this format:
  `YYYY-MM-DD — Name — [TAG] what changed (one line)`
- **Start every entry with a tag — added 2026-07-10:** `[WORLD]` (changed Blender-authoritative
  stuff: world_state.json, neighborhood_blender.py, anything that should look the same in the
  rendered videos and on the website), `[WEB]` (website-only presentation -- UI, controls,
  decorative additions made straight in index.html/town.html that were never added to Blender),
  or `[BOTH]`. This exists because a `[WEB]`-only change (backdrop mountains/clouds, added
  2026-07-09) shipped with no way for the next AI to know it wasn't also in Blender -- see
  CLAUDE.md's Collaboration section for the full reasoning.
- If an AI made the change, say so, e.g. "via his Claude" or "via Cade's Claude" —
  that's the whole "tracking" mechanism, no git needed.
- Newest entries at the top.
- Take turns — don't both have neighborhood.blend open / Google Drive syncing changes
  from both sides at the same time. Check Drive's synced before you start your turn.

## Log

2026-07-11 - Cade (via Codex) - [WORLD] Grew Followville from 134 to 155 followers with 21 new Creekside Bend houses and only their required winding road/cul-de-sac pieces, rendered a house-loading video plus a finished overhead video, validated the web model, and synced all new homes to claiming.

2026-07-11 - Cade (via Codex) - [WORLD] Planned and built the hidden next-366-house suburban reserve: six terrain-shaped neighborhoods, winding staged roads, and 18 cul-de-sacs; terrain is visible now, while each future road segment and ordinary house appears only when its growth address is reached, without moving anything already built.

2026-07-10 — Cade (via Windows Claude Cowork) — [BOTH] Added the ability for a
  follower to give up (unclaim) their house, at Cade's request ("people need the
  option to unclaim, one house per user still"). New `unclaim_house()` Postgres
  RPC in supabase_schema.sql -- deletes the caller's own `claims` row, which
  frees the house for anyone (including them) to claim again; the existing
  `claims.user_id` UNIQUE constraint that already enforces one-house-per-account
  keeps enforcing it afterward, so no new concurrency logic was needed, this is
  just claim_house() in reverse. town.html: the account panel (click your
  `@handle ✓` button once you have a house) now shows an "unclaim this house"
  option behind a one-step "are you sure" confirm card (new `attemptUnclaim()`,
  `confirmingUnclaim` state, wired into the existing `renderAuthCard()` flow --
  no new top-level UI, reuses the existing modal). Also documented in
  CLAIMING_SETUP.md (a migration note: existing installs just need to re-run
  the whole `supabase_schema.sql` in the Supabase SQL Editor once, safe since
  everything in it is `IF NOT EXISTS`/`CREATE OR REPLACE`). **Cade: one thing
  still needed from you** -- this session can't reach the Supabase SQL Editor
  itself, so `unclaim_house()` exists in the pushed schema file but hasn't
  actually been created in the live database yet. Paste all of
  `supabase_schema.sql` into the SQL Editor and hit Run (same one-time step as
  the original setup, safe to re-run) before the button will work live.

2026-07-10 — Cade (via Windows Claude Cowork) — [BOTH] Confirmed day 9 (pop 134, 136
  buildings) live on followville-kappa.vercel.app, matching world_state.json exactly. At
  Cade's request, diagnosed the recurring "AI builds on a stale/backup copy" problem and
  wrote up a fix plan in a new file, SYNC_AND_ZONING_PLAN.md (root cause: the iCloud folder
  is used as a live shared working directory for files multiple machines/AI sessions edit
  concurrently; iCloud resolves collisions by silently renaming the loser to a numbered
  copy instead of merging or erroring, so the next session has to guess which copy is
  real -- a wrong guess is exactly "building on a backup"). Corrected a misunderstanding on
  my part along the way: Cade uses Claude (Cowork, Windows); Zach (Mac) uses Claude too
  (Sonnet/Opus/Fable) AND sometimes OpenAI's Codex/GPT models. Also clarified: the day-9
  "curving lane" attempt with the overlapping roads (world_state 5.json/grow_day9_growth.txt,
  never shipped) was Cade using Claude Fable directly to preview that day's growth, not a
  separate AI experimenting on its own -- Fable's road math was just wrong.
  Then found and fixed what this sandboxed session actually could reach: this iCloud
  folder's own `.git` was completely broken (`HEAD`/`config`/`refs/heads/main` had all been
  renamed away by the same race, plus a stale `index.lock`) -- restored those, which is a
  DIFFERENT git-internal-file instance of the race than the `refs/remotes/origin/main`
  duplicate Zach's session found and fixed the same day (see both writeups in CLAUDE.md's
  Day 9 canon / Collaboration section). Could not get `git fetch`/`push` fully working from
  inside that sandbox (a couple of objects read as corrupt -- looks like a sandbox-only
  limitation, not real data loss), so used computer-use (Win+R -> a `.bat` script) to push
  through the real `C:\Users\cadet\followville_repo` clone instead once Cade said "you have
  access to the terminal and whatever you need" -- confirmed pushed to `main`. Along the
  way, nearly clobbered Zach's much-more-current CLAUDE.md/TEAM_LOG.md with a stale local
  copy (the push script's file-copy step happened to fail first, by luck, catching it) --
  refreshed from the real repo before finishing. Added the `[WORLD]`/`[WEB]`/`[BOTH]` TEAM_LOG
  tag convention above and in CLAUDE.md, plus Cade's clarification there that "same world"
  means same geometry, not same visual quality -- the Blender videos are supposed to keep
  looking better than the website; only what's built and where has to match via town.glb.

2026-07-10 — Zach (via Claude) — fixed a typo'd Supabase account handle at Zach's request:
  instagram_handle was "stellarkehler", corrected to "stellar.kehler". The normal signup
  RPC refuses handle changes once an account is verified, so this went straight to the
  profiles table with the service-role key (fix_stellarkehler_handle.command, kept for
  reference). Only instagram_handle changed — verification_status, is_admin, and the
  claimed house are untouched. Confirmed live via public_claims (what the floating name
  tag actually reads). Worth flagging: this account's claimed house (house_id 2) is the
  Burj Khalifa founder house, not an actual "skyscraper" building — the skyscraper
  milestone building doesn't exist in the town yet (unlocks at 2,000 population; we're at
  134). If a real skyscraper is wanted sooner, that'd need a deliberate special-placement
  decision from Cade, not something to do quietly as a side effect of a handle fix.

2026-07-10 — Zach (via Claude) — made the day-9 layout condense automatic going forward,
  per Zach's request ("make the condensed automatic unless otherwise specified"). Until
  today, dense block-filling only happened via the one-off condense_day9.py script (see
  the entry right below this one) — regular growth still used the old pure-radial lot
  order, which scatters new buildings across many blocks instead of filling any one
  solid, and would have gone back to looking sparse again after a few more growth days.
  Promoted that script's block-filling logic into neighborhood_blender.py itself as a new
  sorted_lots_filling() function, and made find_free_lots() use it by default for every
  building type (houses, apartments, parks, pond clusters, all of it) — no code
  invocation is required anymore, it just happens. Kept the old scattered look available
  on purpose, opt-in only: pass --scatter on the CLI for a specific run if that messier
  spread-out look is ever wanted again. Verified the new lot-picker's behavior directly
  against the real world_state.json (pure Python, no Blender needed): simulated adding 40
  houses to the current town landed them in 6 blocks under the new default vs. 13 blocks
  under the old scatter order for the exact same input, with zero collisions, zero
  dead-center placements, and custom/founder blocks still correctly avoided. Not yet
  exercised on a real growth day (that needs Blender, which only runs via a real machine)
  — next real +N day is the live test; if anything looks off compared to how day 9 turned
  out, --scatter is the immediate fallback while it gets sorted out. Pushed to main
  (docs) — condense_day9.py itself is now mostly historical/reference, no longer needed
  for routine growth.

2026-07-10 — Zach (via Claude) — finished and shipped day 9 (population 134, 136
  buildings), picking up from the in-progress entry below. Three real code fixes, all
  permanent (full writeup in CLAUDE.md's Day 9 canon entry and the "House-facing rules"
  section — read those before touching growth/camera code again):
  (1) fixed a real bug where every block's dead-center lot (no road frontage on any side)
  was still being handed to regular houses, stranding them — Cade's screenshots of a
  "house in the middle of the square" were this bug, not a one-off. find_free_lots() now
  skips that lot for good.
  (2) retuned the render cameras (default/overhead orbit, the --hero close-up, and --cam
  street) for a more cinematic look per Zach's feedback — these are the new defaults, no
  need to touch them again unless something looks off compared to today's videos.
  (3) condensed day 9's 64 new houses only (never touching founders, claimed houses, or
  anything from an earlier day — Zach's explicit call) into the sparse/half-empty blocks
  left over from earlier growth days, via a one-off script (condense_day9.py, kept in the
  folder for reference). This was a ONE-TIME cleanup, not automatic — day 10 will scatter
  again over time unless find_free_lots() itself gets the same block-filling logic later.
  Rendered and Zach-approved three final videos with fireworks left out on purpose:
  day_009_hero_fixed, day_009_street_walkin, day_009_overhead_condensed (this last one
  uses +0 instead of replay so the houses-rising animation doesn't play — Zach's cutting
  it into a longer video). Deployed live via deploy_website.command (commit c2ab97e on
  main) and confirmed the live site's world_state.json shows day 9/pop 134/136 buildings.
  **Heads up for Cade before his next growth day:** the town looking dense right now is
  from the one-time condense script, not a permanent behavior — if blocks start looking
  sparse again after a few more growth days, that's expected until someone gives
  find_free_lots() the same block-fill-first ordering permanently.

2026-07-10 — Cade (via Codex) — made a standalone transparent 70-to-134 follower counter animation and matching 134 hold image for the next reel.

2026-07-10 — Zach (via Claude) — grew the town to day 9, population 134 (+64 houses), per
  Cade's go-ahead to build from the day-8/pop-70 state rather than a broken concurrent
  day-9 attempt on Cade's end (he'd added a road that looked terrible and told Zach to
  ignore it — a one-time call, not a standing policy). Filled the empty grid, kept every
  founder/claimed house untouched, and mixed in random house variety (skyscraper/castle/
  toilet excluded from the random pool per Cade's request). While pushing this to `wip`,
  found and fixed a real bug in the new conflict-aware sync scripts themselves (see the
  two entries below dated 2026-07-10) that had briefly reverted several tracked docs/
  scripts — restored them from `main` before re-sharing. Video renders: hero shot
  succeeded; the overhead shot failed and needs a re-render — in progress.

2026-07-10 — Zach (via Claude) — found and fixed the actual cause of Cade's profile-picture
  feature vanishing: share_progress/deploy_website were blindly overwriting whole tracked
  files with whatever was in the iCloud folder, with zero awareness of whether the OTHER
  side had changed that file since last sync. Confirmed via full git history search that
  the feature was never committed anywhere — it was local-only on Cade's end and got
  clobbered before it was ever captured. Rewrote the copy step (sync_lib.sh on Mac,
  sync_push.ps1 on Windows) to do a real 3-way merge per file, same idea as `git merge`:
  auto-combine non-overlapping changes from both sides, and refuse to guess (leave the file
  out, flag it loudly) when both sides changed the same spot. Also found and fixed a fresh
  case of the numbered-conflict-copy bug, this time inside `.git` itself
  (`refs/remotes/origin/main 2`). Windows side is unverified on a real PC — treat next use
  as a test, and if Cade's profile-picture code is still sitting in `.pull_backups/` on his
  machine, it should be recoverable from there.

2026-07-10 — Zach (via Claude) — the merge-detection fix above had its own bug, caught the
  same night before it did lasting damage: the "prior known state" used for the 3-way
  comparison was captured right after cloning, which lands on the repo's default branch
  (main) rather than whichever branch was actually being pushed (wip) — so the first real
  run compared local files against the wrong branch's history and concluded upstream had
  changed things it hadn't, silently reverting grow.sh, deploy_website.bat/.command,
  .gitignore, CLAUDE.md, and TEAM_LOG.md back to older content. Fixed by capturing that
  reference point from the branch actually being worked on, after fetching but before
  checking it out. Restored all the reverted files from main (which was never touched by
  the bug). Also gave deploy_website.command the same explicit "checkout main first" safety
  net deploy_website.bat already had.

2026-07-10 — Zach (via Claude) — fixed a road gap in the park district Zach spotted in the
  web preview ("a road belongs there to get into the circle"): build_district_roads() in
  neighborhood_blender.py builds a connector from the grid to the OUTER ring road, and
  separately a spur from the INNER ring to the gazebo's walking loop, but nothing ever
  bridged the outer ring to the inner ring themselves — a bare ~14-unit strip of grass
  between the two concentric rings with no way to drive/walk from one to the other. Added
  one more road segment that starts exactly where the connector ends and hands off exactly
  where the spur begins, closing the gap with no seam. Verified by querying the actual
  object positions in the open Blender session: connector [69,95] + new "radial" [95,112]
  + spur [112,124] now form one continuous stretch. Re-exported town.glb with the fix —
  reload the local preview to see it. Not yet committed/pushed (still sitting as an
  uncommitted change on top of the `wip` branch already on GitHub).

2026-07-09 — Zach (via Claude) — fixed two real bugs and started moving collaboration off
  iCloud sync onto git, at Zach's request ("work off each other's stuff, not copies").
  Bugs fixed in neighborhood_blender.py/export_web.py (both now the canonical files):
  (1) Cade's three rounds of fireworks/park-camera fixes from earlier today had landed in
  numbered iCloud conflict copies (neighborhood_blender 5/6/7.py) instead of the real
  neighborhood_blender.py, so the live script still had the original buggy version —
  promoted file 7 (a clean superset, verified via diff) to canonical, old version backed
  up as neighborhood_blender_prefix_backup_20260709.py. (2) Found why fireworks looked
  like permanent floating debris on the website: export_web.py's pancaked-houses fix
  force-resets EVERY object in the WORLD collection to scale (1,1,1) before baking
  town.glb, which also permanently un-shrinks the "fw"-named firework burst particles at
  their fully-exploded positions (fireworks are meant to be invisible except for a few
  animated frames, video-only). Fix: export_web.py now deletes all "fw"/"fw.NNN" objects
  before the scale-reset/export step. Verified with --celebrate on: 0 firework objects
  survive into the export now (was previously baking dozens in). Neither fix touched
  world_state.json — day 8/pop 70 unchanged.
  Collaboration change (in progress, not finished — see below): the plan is to stop
  relying on iCloud's file sync to hand work between Cade and Zach (it's the root cause
  of the conflict-copy bug above and others documented in this file) and use git instead —
  pull before starting a session, push when done, same pattern grow_windows.ps1 already
  uses for world_state.json/town.glb, just extended to the code/docs too. Work that isn't
  approved to deploy yet (like today's park district + graphics upgrade) goes to a `wip`
  branch instead of `main`, so it can be pulled and built on without going live; `main`
  stays "what's actually deployed." Created the `wip` branch locally and staged .gitignore
  additions to stop the numbered conflict copies from cluttering `git status` going
  forward, but could NOT commit/push from this AI session — this iCloud folder's own
  `.git` has a stale `.git/index.lock` (dated 2026-07-07) that the sandboxed AI session
  can't delete (permission denied at the OS level, likely specific to how this session's
  sandbox mounts the iCloud folder, not a real problem on an actual Mac). **Whoever picks
  this up next (Zach, in Terminal, has real filesystem permissions):**
  ```
  cd "~/Library/Mobile Documents/com~apple~CloudDocs/neighborhood"
  rm -f .git/index.lock   # only if the next command complains it exists
  git checkout wip 2>/dev/null || git checkout -b wip
  git add -u
  git add AGENTS.md CLAIMING_SETUP.md FOLLOWVILLE_ACCOUNTS_MASTER_PROMPT.md MASTER_PROMPT_ZACH.md admin.html check_town_glb.py check_town_glb.yml deploy_website.command supabase_schema.sql sync_houses.py grow_windows.bat grow_windows.ps1 preview_website.bat preview_website.ps1 deploy_website.bat .gitignore
  git commit -m "WIP: day 8 park district + graphics upgrade + fireworks/version-drift fixes"
  git push -u origin wip
  ```
  After that, tell Cade (via TEAM_LOG) to `git fetch && git checkout wip` on his end
  instead of trusting iCloud to hand him these files.

2026-07-09 — Zach (via Codex) — added a local scalable building-detail pass to the website: clearer facade and roof edges, window mullions, brass door hardware, siding/shingle/wood patterns, and occasional flower boxes; previewed successfully and not deployed.

2026-07-09 — Zach (via Codex) — strengthened the local website graphics after review: richer color and shadows, visible curb/sidewalk finishing, distant low-poly hills and clouds, and scalable instanced street detail; previewed successfully and not deployed.

2026-07-09 — Zach (via Codex) — made a local same-camera before/after comparison of the original and upgraded website graphics so the material and sky changes can be reviewed clearly; nothing deployed.

2026-07-09 — Zach (via Codex) — locally upgraded the walkable website's materials, lighting, and sky for a richer painted low-poly look, plus added a founder-district screenshot view; previewed successfully and did not deploy anything.

2026-07-09 -- Zach (via Claude) -- grew the town to day 8, population 70 (+41 houses).
  Built a whole new circular park district east of town: central park with a gazebo,
  ring roads, and the 41 new houses arranged in two rings around it, every door facing
  the park -- with more variety than the grid houses (two-story homes, townhouses, new
  pastel colors). Rendered three videos with celebration fireworks (houses+park rising,
  a higher/wider overhead drone of the whole town, and an in-park showcase orbit), all
  auto-copied to the Desktop. After Zach's review: re-shot the overhead + in-park videos
  as calm 12-second showcases of the finished town (only the hero shows houses rising)
  and turned the new lighting's brightness back down (it was washing things out). Also upgraded the lighting for all future videos (softer
  shadows, sky fill light). Note: this Mac's iCloud copy had fallen behind again --
  reconciled world_state.json/generator/docs from GitHub (day 7) before growing, and
  backed up the day-7 state first. Website NOT pushed yet -- waiting for Zach to confirm
  the videos look right, then deploying.

2026-07-09 — Cade (via Windows Claude) — set Cade's new building-icon image as the site
  logo (landing page profile photo): downscaled to 512px as logo.png (old one kept as
  logo_previous.png, original upload kept as logo_candidate.png). Found why the live site
  had been showing the emoji fallback instead of any logo: deploy_website.bat copied the
  file to UPPERCASE "LOGO.png" while index.html requests lowercase "logo.png", and Vercel
  is case-sensitive — fixed the deploy script to use the lowercase name (the stale
  LOGO.png in the repo is harmless, left in place per the no-deletions rule).
  ── STATE OF THE PROJECT after today (handoff summary for the next AI) ──
  Everything about claimable homes is LIVE and verified end to end. The complete picture:
  * Live site followville-kappa.vercel.app: index.html (landing; session-aware buttons,
    admin button for admins, logo), town.html (walkable town + full account/claim UI),
    admin.html (admin moderation page, server-side gated), town.glb + world_state.json
    (from the git repo clone, pushed automatically by growth runs).
  * Backend: Supabase project "followville" (ref bposhxtidoyulallvhdp, org "The Human
    Archive"). Canonical schema = supabase_schema.sql (both original section and the
    "WEB ADMIN ACCESS" migration have been run). Keys: legacy anon key is public (in
    town.html/index.html/admin.html); legacy service-role key ONLY in supabase_sync.env
    (iCloud folder, gitignored, never deploy).
  * Residents so far: @cade.toohey (admin, owns house #5 the castle), @stellarkehler
    (admin, verified, no house yet). Verification is manual until Meta app review
    (CLAIMING_SETUP.md §4 has the webhook plan).
  * Daily ops: grow_windows.bat +N grows the town AND git-pushes state AND syncs new
    buildings into Supabase houses (HOUSES_SYNC_OK in grow_log.txt); deploy_website.bat
    pushes doc/code/HTML changes; admin approvals happen on the live Admin page (or
    admin.bat locally). Docs: CLAIMING_SETUP.md is the feature manual, CLAUDE.md's
    "Claimable homes" section is the summary. Known quirks worth reading before working
    here: the iCloud conflict-copy race (CLAUDE.md Third AI section — hit 5+ times today,
    recovery pattern documented) and the Blender-glTF axis flip (blender +y = three -z,
    documented in town.html's claims module).

2026-07-09 — Cade (via Windows Claude) — took the admin page live, properly gated: added an
  is_admin flag (currently @cade.toohey and @stellarkehler), rebuilt every admin action as a
  database function that checks that flag server-side (so only admin accounts can approve/
  reject/revoke — anyone else who finds admin.html gets "No access" and the database refuses
  them), and put an "Admin" button on the homepage that only admins see. Along the way found
  and fixed a real security gap from the original schema: Postgres grants function-execute
  to PUBLIC by default and the original only revoked anon/authenticated, which had left
  admin_verify callable with just the public site key — everything is now revoked from
  PUBLIC explicitly (verified: anon key gets "permission denied"). admin.bat/local mode
  still works unchanged. Also updated deploy_website.bat's whitelist (admin.html now
  deploys; admin.bat and supabase_sync.env stay local).

2026-07-09 — Cade (via Windows Claude) — polished the claiming experience after Cade's first
  real playtest, and approved the first two residents (@cade.toohey → the castle, and new
  user @stellarkehler, verified via DM code). Fixes: name tags were floating over the street
  (Blender's GLB export mirrors the north-south axis — verified against town.glb itself and
  corrected), tags are now smaller, sit just above each house's actual roof, and only appear
  when you're near; the claim prompt now only shows when you're right at a house's front
  door AND looking at it, with a floating "[E] claim this house" tag over that exact house;
  the landing page is session-aware (shows "Go to my home" + "logged in as @handle · log
  out" when appropriate); "go to my home" spawns you facing your own front door. Also built
  admin.bat/admin.html — a LOCAL-ONLY one-click admin page (approve/reject verifications,
  revoke claims) that reads the secret key from supabase_sync.env at runtime, so it can
  never work on the live site; never add it to deploy_website.bat's whitelist.

2026-07-09 — Cade (via Windows Claude) — took claimable homes LIVE: created the Supabase
  project (followville, in "The Human Archive" org) through Cade's browser, ran the schema,
  turned off email-confirmation for smooth signups, wired the anon key into town.html and
  the service-role key into supabase_sync.env (secret, local only), backfilled all 30
  buildings into the houses table, deployed, and verified the live site + database end to
  end. Followers can now sign up and claim houses at followville-kappa.vercel.app — Cade
  approves each Instagram verification by hand for now (CLAIMING_SETUP.md §3: check DMs for
  the code, then `select admin_verify('handle');` in the Supabase SQL editor). Also fixed
  the "website won't load" confusion (double-clicking town.html can't fetch data over
  file:// — use preview_website.bat) and added the new files to deploy_website.bat's
  whitelist.

2026-07-09 — Cade (via Windows Claude) — built the "claimable homes" feature: followers can
  now create an account on the site, verify their Instagram handle with a one-time DM code
  (manually approved by Cade until Meta's app review goes through), and claim exactly one
  house in the town — first come first served, enforced by the database so two people can
  never grab the same house, with live updates in every open browser. New files:
  supabase_schema.sql (run once in Supabase), sync_houses.py + a sync step inside
  grow_windows.ps1/grow.sh (new buildings automatically become claimable after each growth
  day), and CLAIMING_SETUP.md (the full setup + admin guide). town.html got the whole
  account/claim UI (sign up, verification code screen, walk-up-and-press-E claiming, name
  tags floating over claimed houses, "go to my home" spawn); index.html got a "Claim your
  home" button. NOT live yet — Cade still needs to create the Supabase project and paste
  in the keys (15-minute checklist in CLAIMING_SETUP.md §1). Until then the site behaves
  exactly as before. Also: TEAM_LOG.md's plain filename had been eaten by the iCloud race
  again — restored from the freshest conflict copy (TEAM_LOG 7.md) while writing this.

2026-07-09 — Cade (via Windows Claude) — installed Blender's official MCP add-on (from
  blender.org/lab/mcp-server) into the Windows Blender 5.1 install, enabled "Allow Online
  Access" in Blender's System preferences (required for the add-on's local server to run),
  and started the MCP bridge on localhost:9876. This lets this session (and future ones)
  inspect the live Blender scene directly (materials, object hierarchy, scale, etc.) instead
  of only driving Blender headlessly via grow_windows.bat or round-tripping through
  town.glb + pygltflib. Heads up for whoever opens neighborhood.blend next: the add-on's own
  security notice says it lets any connected AI run unsandboxed Python inside Blender with no
  guardrails against data loss/exfiltration -- Cade explicitly approved installing it anyway
  on this everyday PC (not a VM), so if that tradeoff ever needs revisiting, disable/remove
  the "MCP" add-on in Edit > Preferences > Add-ons.
  Also confirmed something worth knowing: neighborhood.blend's saved scene is stale (still
  shows roughly the day-4 state, missing the day 5-7 houses and the pond) because growth has
  been headless-only since day 4 and nothing has re-saved the .blend since. This does NOT
  affect world_state.json, town.glb, or the live site (those are correct/current, built fresh
  by the headless pipeline each run) -- it only matters if someone opens the .blend in the
  GUI expecting to see the current town.

2026-07-09 — Cade (via Windows Claude) — verified the new git-backed grow pipeline end to end
  (test_git_pipeline3.txt): git pull succeeded, Blender read/wrote world_state.json + town.glb
  from C:\Users\cadet\followville_repo via NEIGHBORHOOD_STATE_DIR (state_file in the RESULT line
  confirms it), the sanity check passed (no SANITY_CHECK_FAILED), and git add/commit/push ran
  automatically, correctly reporting NOCHANGES since this was a no-op replay of the already-
  committed day 7 state. Log ended in ALL_DONE. Hit the iCloud race one more time on the way in
  (neighborhood_blender.py's plain filename had been renamed to a numbered conflict copy again --
  restored from the freshest copy) and again on TEAM_LOG.md itself while writing this entry --
  another data point for why the git-backed approach above is the right fix, not a patch.

2026-07-09 — Cade (via Windows Claude) — root-caused the recurring iCloud sync race for real
  this time, instead of just working around it. world_state.json/town.glb now live
  authoritatively in the git repo clone (C:\Users\cadet\followville_repo), not in this iCloud
  folder: neighborhood_blender.py/export_web.py gained a NEIGHBORHOOD_STATE_DIR env-var
  override (unset = old behavior, fully backward compatible), and grow_windows.ps1 now does
  git pull -> point Blender at the repo clone -> git add/commit/push automatically after every
  growth run. Growing the town and publishing its state are one step now instead of two --
  this also kills the "forgot to deploy, site stuck a day behind" failure mode from 2026-07-07.
  Updated deploy_website.bat to stop copying world_state.json/town.glb (it would've stomped
  the fresher git-committed copies) and preview_website.ps1 to serve those two files from the
  repo clone so local preview still works. Added the same opt-in pattern to grow.sh via
  NEIGHBORHOOD_REPO_DIR for Mac -- untested from here, needs a Mac session to verify before
  relying on it. Also built check_town_glb.py (standalone, no-Blender pygltflib check for the
  exact pancaked-scale bug from yesterday) and wired it in twice: once inside export_web.py
  itself (fails the Blender run outright if it finds anything squashed) and once as a GitHub
  Action (.github/workflows/check_town_glb.yml, had a Fable subagent draft the workflow YAML)
  that runs on every push to main -- so a bad export can't reach the live site undetected even
  if the in-Blender check somehow gets bypassed later. Full writeup in CLAUDE.md under "Where
  world_state.json + town.glb actually live now."

2026-07-08 — Cade (via Windows Claude) — found and fixed the real cause of the "pancaked
  houses" bug Cade reported on the live day-7 site (pond + 3 new houses showing up flat,
  as if caught mid-rise). It wasn't the frame_end jump (that fix from 2026-07-05 was still
  needed but not enough) — it was that export_web.py's scale reset only overrides the
  Python-side value; the new buildings still had live rise-animation keyframes attached,
  and Blender's duplicates_make_real() re-applies that animation during export, silently
  baking the mid-rise scale back in. Confirmed directly in the deployed town.glb with
  pygltflib (37 mesh parts squashed to scale 0.001). Fix: export_web.py now also calls
  obj.animation_data_clear() before realizing instances, so there's no animation left to
  reassert anything. Re-exported town.glb (verified 0 squashed nodes, was 37), redeployed
  via deploy_website.bat, confirmed the push landed on origin/main (commit 630e634). Full
  writeup in CLAUDE.md's Web viewer section (new 2026-07-08 PITFALL note) in case this
  pattern ever resurfaces.

2026-07-08 — Cade (via Windows Claude) — grew the town to day 7, population 29 (30
  buildings): added a brand-new "pond" building type with animated ducks
  (build_pond/build_duck/animate_ducks in neighborhood_blender.py, new --pond flag) and
  clustered the 3 new houses around it in a shared 2x2 patch. Rendered a hero shot of the
  pond+houses appearing (day_007_hero_0001-0160.mp4) and a final overhead/drone shot of
  the whole town (day_007_overhead_0001-0160.mp4), both copied to the Desktop. Deployed
  live via deploy_website.bat, confirmed the push landed on origin/main (commit bcf77d0).
  Hit a nasty iCloud sync issue along the way — world_state.json's plain filename kept
  getting renamed to a numbered conflict copy between separate command launches, causing
  one render to silently run against an empty town. Documented the cause and the fix
  (combine the restore + the next action into one script) in CLAUDE.md's Third AI section
  — worth reading if anything like this happens again.

2026-07-07 — Cade (via Windows Claude) — set up real deploying from Windows: installed
2026-07-07 — Zach (via Claude) — set up a real GitHub Desktop clone at ~/Documents/GitHub/followville
  (Separate from the shared iCloud folder, same idea as Cade's Windows deploy_website.bat setup) to
  Find out whether Cade's collaborator invite gives write access, not just read. This line is the
  Test: if it shows up on GitHub after a push, write access is confirmed.

  Git, cloned the GitHub repo, and built `deploy_website.bat` (one-click push: copies the
  current site files in, commits, pushes -- Vercel redeploys automatically). Used it for
  the first time to push the day 6 growth + the new street-cam feature -- the live site
  (followville-kappa.vercel.app) had been stuck showing day 5 since the last Mac push;
  it's now correctly showing day 6/population 26, confirmed in a real browser. Cade did
  one manual GitHub sign-in in his own browser for the first push (normal one-time step,
  this session never saw the credentials); future pushes should be silent.

2026-07-07 — Cade (via Windows Claude) — added a new street-view camera mode
  (`--cam street`) to neighborhood_blender.py: instead of orbiting overhead, the camera
  now drives straight down the town's oldest street (the road past the founder blocks)
  at eye level, aimed far ahead so the heading stays steady the whole way -- a proper
  "walking/driving down the street" shot rather than an orbit. Made the clip length for
  this mode at least 12 seconds so it actually feels slow. Rendered via grow_windows.bat
  in safe `replay` mode (doesn't touch world_state.json/the .blend) --
  day_006_street_0001-0360.mp4, copied to the Desktop. Cade confirmed it looks good.

2026-07-07 — Cade (via Windows Claude) — grew the town for real from Windows for the
  first time: day 5 -> day 6, population 22 -> 26 (4 new houses), using
  grow_windows.bat. Rendered a hero shot of the 4 new houses rising
  (day_006_hero_0001-0160.mp4) and a final overhead shot of the whole town at its new
  size (day_006_overhead_0001-0142.mp4), both auto-copied to the Desktop -- same
  multi-shot pattern as the Mac workflow (real growth quietly, then replay --hero
  --render for the close-up, then +0 --cam overhead --render for the wide shot). Both
  renders finished in under 90 seconds each (much faster than the 10-15 min the Mac
  docs estimate -- this PC's EEVEE render is quick). world_state.json now correctly
  shows day 6/pop 26/26 buildings.

2026-07-07 — Cade (via Windows Claude) — ran a real (safe) end-to-end test of
  grow_windows.bat: `replay` mode, which never touches world_state.json/the .blend by
  design. First attempt failed for a dumb reason (PowerShell treated a harmless Blender
  DeprecationWarning on stderr as a fatal error) -- fixed and reran, got ALL_DONE, town.glb
  refreshed with a fresh timestamp, world_state.json/.blend untouched (verified by hash/
  timestamp). Then built preview_website.bat + preview_website.ps1 (a tiny PowerShell-only
  local server, no Python/Node needed -- fetch() doesn't work over file://) and confirmed
  in a real browser that index.html and town.html both correctly show "day 5 / population
  22" and that town.glb genuinely loads over the wire (200 OK) -- the Blender-to-website
  pipeline is confirmed working end to end from Windows now.
2026-07-07 — Cade (via Windows Claude) — built grow_windows.bat + grow_windows.ps1: a
  Windows equivalent of grow.sh that runs Blender headlessly (--background, no GUI, no
  clicking) via blender.exe at "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe".
  Same +N/-N/=N/replay syntax and extras as grow.sh. Hit and fixed one real bug along the
  way: Windows PowerShell 5.1 misreads em-dash characters in .ps1 files without a BOM,
  which broke a string and crashed the script — both files are plain ASCII now (see
  WEB_VIEWER_CHANGELOG.md). Verified the wiring works (usage message shows correctly with
  no args) but have NOT yet run it against the real world_state.json — that needs Cade's
  go-ahead first. Meant to be launched via Win+R (types fine there) or double-click, not by
  typing into a Command Prompt window (blocked for this session).
2026-07-07 — Cade (via Windows Claude) — correction to my earlier entry today: Blender
  IS actually installed on this Windows PC, and with screen-control access I can open it
  and click around (unlike the Mac AIs, which only ever ran it headlessly via grow.sh).
  Used that to open neighborhood.blend, check the Scripting tab, and rule out one
  hypothesis for the old "20 vs 3 house_d4" bug from WEB_VIEWER_CHANGELOG.md #9 (the
  embedded script copy already has the safe auto-run guard, so it's not silently
  rebuilding on open). Didn't save any changes to the .blend. Still don't have a safe,
  non-GUI way to run actual growth days from here — see updated CLAUDE.md note.
2026-07-07 — Cade (via Windows Claude) — set up a third AI session on Cade's Windows PC,
  working from the same iCloud-synced folder. Documented in CLAUDE.md that this session
  can edit docs/web viewer but has no Blender, so growth days/renders still run on a Mac.
2026-07-05 — Cade (via Claude) — added mobile touch controls (joystick + drag-to-look)
  to town.html, fixed the "pancaked houses" export bug, simplified landing page text.
  Set up this shared team-log + Google Drive collaboration workflow for Zach.
2026-07-06 -- Cade (via Claude) -- grew the town to day 5, population 22 (22 houses). Rendered a hero shot of the new houses appearing and a final overhead shot, both copied to the Desktop. Caught and fixed an accidental double-run of the render script that briefly corrupted the state to day 6/pop 28; restored from a day-4 backup before redoing it cleanly. Also corrected a 1-off population/house-count mismatch by hand-editing the pop field to match the 22 built houses.
