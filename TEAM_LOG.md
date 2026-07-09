# Team log — Followville

Plain-English log of who added/changed what, in order. Not a technical changelog
(see WEB_VIEWER_CHANGELOG.md for that) — just enough so Cade and Zach (and whichever
AI is helping each of them) can see what the other did on their turn.

## How to use this
- Whoever finishes a turn (Cade or Zach) adds ONE line before handing off, in this format:
  `YYYY-MM-DD — Name — what changed (one line)`
- If an AI made the change, say so, e.g. "via his Claude" or "via Cade's Claude" —
  that's the whole "tracking" mechanism, no git needed.
- Newest entries at the top.
- Take turns — don't both have neighborhood.blend open / Google Drive syncing changes
  from both sides at the same time. Check Drive's synced before you start your turn.

## Log

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
