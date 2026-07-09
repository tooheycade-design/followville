# FOLLOWER NEIGHBORHOOD — project memory (read me first)

Cade's Instagram project: a persistent 3D low-poly town in Blender. Every follower = a house.
Daily reels show the town growing. THE CITY'S MEMORY IS world_state.json — NEVER edit/delete
it casually; back it up before risky operations. **As of 2026-07-09, on Windows this file (and
town.glb) live in the git repo clone (`C:\Users\cadet\followville_repo`), NOT in this iCloud
folder, by default — see "Where world_state.json + town.glb actually live now" below before
you go looking for it here.**

## Current canon (update this section each day!)
- Day 7, population 29, 30 buildings (grown 2026-07-08 via Windows Claude: +3 houses + 1 pond).
  New pond+ducks feature: a "pond" building (SIZE 1, `build_pond`/`ASSET_VARIANTS["pond"]`)
  clusters with new houses in a shared free 2x2 patch via `--pond` (see main()'s `pond_extras`
  block); ducks are NOT saved to world_state (spawned fresh each run by `animate_ducks`,
  analogous to `animate_traffic`, using each pond building's own seed). Rendered hero shot
  (`replay --hero --render --tag hero`) + overhead/drone shot (`replay --cam overhead --render
  --tag overhead`), then deployed live. Live site initially showed the pond+3 new houses
  pancaked flat — root-caused and fixed same day (export_web.py now calls
  `obj.animation_data_clear()` before realizing instances; see the Web viewer section's
  2026-07-08 PITFALL note below for the full story), re-exported, redeployed, confirmed live.
  Sunset fireworks marked the founder era complete (day 4).
- Web viewer shipped day 4 (index.html + town.glb, see Web viewer section).
- FOUNDERS (first 10 residents, custom houses, all built):
  1 mushroom  2 casino  3 cat  4 castle  5 Eiffel home  6 hydrangea flower
  7 Burj Khalifa  8 giant toilet (next to Burj, faces east)  9 beach house  10 cottage
- Founder district = blocks around the center. Regular houses NEVER build in blocks
  containing custom houses (enforced in code).

## Daily workflow (Terminal, no Blender GUI needed)
  cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/neighborhood
  ./grow.sh +N --render              # N followers gained -> N houses + video
  ./grow.sh -N | "=TOTAL" | replay   # losses / set total / re-animate
Flags: --special TYPEhouse[@gx,gy] --followers N --hero --celebrate
       --cam overhead|street --tag NAME --time day|sunset|night --season X --still
       (--cam street: added 2026-07-07 — eye-level flythrough down the town's oldest
       street past the founder blocks, instead of the default overhead orbit; runs at
       least 12s so it reads as "slow". See build_stage() in neighborhood_blender.py.)
Videos auto-copy to Desktop. Multi-shot days: hero shot (replay --hero --render --tag hero)
+ overhead/final (+0 --cam overhead --render --tag overhead).

## House-facing rules
- Houses auto-face their nearest road. Override: set "face": "s|e|n|w" on the building
  in world_state.json (camera looks from the SOUTH-EAST: s and e faces are visible).

## Adding custom house models (Fable-level work)
Edit neighborhood_blender.py: write build_X_house() using add_box/add_ngon_cone/
add_prism_roof + mat(), register in SIZE and ASSET_VARIANTS, then
--special xhouse[@gx,gy]. Match the cute pastel style. After script changes run:
  /Applications/Blender.app/Contents/MacOS/Blender --background neighborhood.blend --python _refresh_text.py

## Cost discipline
- ONE preview still per day max (--still), then render.
- Renders take 10-15 min each: run via nohup job writing render_log.txt (ends "ALL_DONE"),
  and hand the log-watching to a HAIKU subagent. Never poll with the expensive model.
- Routine +N days need no preview at all.

## Web viewer (index.html + town.glb)
A first-person browser version of the town lives in index.html, next to world_state.json.
Real geometry, not a hand-ported copy: grow.sh now runs export_web.py (a second headless
Blender pass) after every build, which bakes the actual "WORLD" collection Blender just
built to town.glb (realizes collection-instances to real meshes via duplicates_make_real,
then exports GLB, Y-up, no animation/camera/lights). index.html loads town.glb with
Three.js's GLTFLoader — pixel-for-pixel the same model Blender rendered, no drift, no
manually-ported shapes to keep in sync, and any brand-new custom house type in
neighborhood_blender.py "just works" on the web the next time grow.sh runs, zero web-code
changes needed. world_state.json is still fetched separately, just for the day/population
HUD text. Collision colliders are computed automatically from each top-level object's
bounding box in the loaded GLB — no per-house-type radius to maintain either.

Fallback: if town.glb is missing (e.g. before the first export ever ran), index.html falls
back to an OLDER procedural JS approximation (the BUILDERS map, ~line 160-500) that
hand-rebuilds simplified house shapes from world_state.json alone, no Blender needed. This
is a safety net only — it's visually approximate and NOT kept in sync with new Blender
house types. Prefer fixing/regenerating town.glb over touching the JS builders.

Serve via a local server (`python3 -m http.server` in this folder — fetch() needs http://,
not file://) to preview locally. For the actual live site, see "Deploying the live site"
below — growing the town does NOT push those changes live by itself.
It always shows the CURRENT town only (no time-travel yet). Usernames on houses are a
planned feature, not wired up — needs a `username` field added to buildings in
world_state.json first.

## Deploying the live site (GitHub + Vercel) — READ THIS, it's the thing that got missed
Live URL: `https://followville-kappa.vercel.app`. Repo:
`https://github.com/tooheycade-design/followville`. Vercel auto-redeploys on every push
to `main` — but nothing pushes automatically on its own.

**Growing the town (`grow.sh` / `grow_windows.bat`) does NOT push to GitHub or update the
live site.** Neither script contains a single git command — they only ever touch files in
this local iCloud folder. Deploying is a separate, manual step, and it's easy to forget:
on 2026-07-07 the live site was still showing "day 5" a full day after the local town had
already grown to day 6, because nobody had pushed in between. **After growing the town,
always also check/push the live site — don't assume it updates itself.**
- **Windows:** `deploy_website.bat` (built 2026-07-07) does this in one click — copies the
  current tracked files (index.html, town.html, town.glb, world_state.json,
  neighborhood_blender.py, grow.sh, export_web.py, the .md docs, etc.) into a local git
  clone at `C:\Users\cadet\followville_repo`, commits, and pushes. Progress + a final
  `ALL_DONE`/`ALL_FAILED` land in `deploy_log.txt`. See the "Third AI" section below for
  the full setup story (installing git, cloning, one-time GitHub sign-in, etc.).
- **Mac:** no equivalent script was found in this folder as of 2026-07-07 — the repo
  already had prior commits (e.g. "Day 5: population 22, 22 buildings") before any AI
  touched git here, so it looks like Cade has just been running `git add / commit / push`
  by hand from a Mac terminal after growing. **If you're Zach's Claude reading this:**
  check with Cade whether he already has a routine for this before assuming there isn't
  one — and if there really isn't one, consider offering to build a `deploy_website.sh`
  mirroring this same idea (copy tracked files, commit, push, log ALL_DONE) so this stops
  getting missed.

## Where world_state.json + town.glb actually live now (2026-07-09)
This section supersedes most of the "combined restore + launch script" workaround described
in the iCloud race-condition gotcha further down (that workaround still applies to plain docs
like this one, which haven't moved — see below). The race itself was: `world_state.json`'s
plain filename in this iCloud folder kept getting silently renamed to a numbered conflict copy
between separate command launches, because it's a file that gets read-modified-written every
single growth day, and that's exactly the wrong kind of file to leave in an iCloud/Dropbox-style
sync path. The actual fix isn't a smarter workaround, it's removing the file from iCloud's sync
path entirely and using git instead — a `git pull` either gets you the latest committed state or
fails loudly; it never silently hands you an empty file the way iCloud's conflict-copy renaming did.

**How it works now (Windows):**
- `neighborhood_blender.py`'s `state_path()` and `export_web.py`'s town.glb output path both
  check an environment variable, `NEIGHBORHOOD_STATE_DIR`. If set, `world_state.json`/`town.glb`
  are read/written there instead of "next to the .blend" (the old default). Unset = old
  behavior, unchanged — this is fully backward compatible.
- `grow_windows.ps1` sets `NEIGHBORHOOD_STATE_DIR` to `C:\Users\cadet\followville_repo` (the git
  clone) before every Blender invocation. Before that, it does `git pull origin main` in the
  clone — if the pull fails, the whole run aborts loudly rather than growing on top of state we
  might not have the latest copy of. After Blender succeeds, it `git add`s `world_state.json` +
  `town.glb`, commits (message: `Grow: <change> (auto-committed by grow_windows.ps1 <timestamp>)`),
  and pushes to `origin/main` automatically — growing the town and publishing its new state are
  now ONE step, not two. (This also closes the *other* recurring problem, "forgot to deploy,
  live site stuck a day behind" — see the old note below.)
- Pass `--no-git` to `grow_windows.bat`/`.ps1` to fall back to the pre-2026-07-09 behavior
  (state next to the `.blend`, in this iCloud folder, no git pull/push) if this ever needs
  troubleshooting.
- `deploy_website.bat` no longer copies `world_state.json`/`town.glb` from this iCloud folder —
  doing so would silently overwrite the fresher git-committed copies with a stale iCloud copy.
  It still handles every OTHER tracked file (docs, code, the HTML). Growing (`grow_windows.bat`)
  publishes state; `deploy_website.bat` publishes everything else (docs/code changes made
  directly in this iCloud folder, outside of a growth run).
- `preview_website.ps1` (local preview server) was updated to serve `world_state.json`/`town.glb`
  from the repo clone if present there, and everything else from this iCloud folder as before —
  so local preview still shows the real current state after a `grow_windows.bat` run.
- **Mac (`grow.sh`):** the equivalent opt-in exists — set `NEIGHBORHOOD_REPO_DIR` (e.g.
  `export NEIGHBORHOOD_REPO_DIR="$HOME/Documents/GitHub/followville"`) before running `grow.sh`,
  and it mirrors the same pull/env-var/commit-push pattern. **This was written from the Windows
  session and has NOT been tested on an actual Mac** — Cade's and Zach's Mac repo clone paths
  weren't known/verifiable from here. Leave `NEIGHBORHOOD_REPO_DIR` unset and `grow.sh` behaves
  exactly as before (fully backward compatible); whoever's on a Mac should verify this once
  before relying on it, and update this note with what was actually found.
- **Docs (this file, TEAM_LOG.md, etc.) have NOT moved** — they're far less frequently
  read-modified-written than `world_state.json` was, but they DO still occasionally get hit by
  the same iCloud race (it happened again mid-edit while writing this very section, 2026-07-09 —
  see the recovery pattern in the gotcha note below). If this becomes a recurring problem for
  docs too, the same fix applies: move their canonical copy into the git repo clone as well.

**Also added 2026-07-08/09, closing the OTHER half of the pancaked-houses problem (that it shipped
silently for a full day before anyone noticed):** `export_web.py` now has an in-Blender check
right after `duplicates_make_real()` — if ANY realized object has a near-zero scale on any axis,
it raises and fails the whole Blender process, which `grow_windows.ps1`/`grow.sh` already treat as
fatal (`ALL_FAILED`). A second, independent copy of the same check lives in a standalone script,
`check_town_glb.py` (needs only `pip install pygltflib`, no Blender required), wired into a
GitHub Action (`.github/workflows/check_town_glb.yml`) that runs on every push to `main` — so
even a bad export that somehow bypassed the in-Blender check (a hand-edited file, a future
refactor that drops it, etc.) can't reach the live site without GitHub itself flagging the push
red. Verify it's working by checking the Actions tab on the GitHub repo after any push.

## Claimable homes (accounts) — built 2026-07-09, see CLAIMING_SETUP.md
Followers can sign up on the site, verify their Instagram handle (DM-code, manually
approved by Cade until Meta app review), and claim exactly ONE house. Backend:
Supabase (Postgres+Auth+Realtime) — schema in `supabase_schema.sql`, run once in the
Supabase SQL editor. One-house-per-account and one-account-per-house are enforced by
DB unique constraints via the `claim_house()` RPC (first commit wins, loser gets a
clean error, Realtime updates every open browser). `town.html` has the whole
account/claim UI; it stays 100% dormant until `SUPABASE_URL`/`SUPABASE_ANON_KEY` are
pasted in near the top of its script. **Pipeline integration (don't lose this):**
`grow_windows.ps1` (Sync-Houses function) and `grow.sh` (sync_houses.py call) now
sync new world_state.json buildings into the Supabase `houses` table after each
growth — insert-only/idempotent, needs `supabase_sync.env` (SECRET, gitignored,
NOT in the deploy whitelist) next to the scripts. Log lines: HOUSES_SYNC_OK /
HOUSES_SYNC_FAILED / HOUSES_SYNC_SKIPPED in grow_log.txt. Everything is claimable
incl. founder houses (Cade's call, 2026-07-09) except ponds/parks/plazas.
Admin (verify/reject/revoke) = the "Admin" button on the LIVE homepage (visible
only to accounts with profiles.is_admin = true — currently cade.toohey and
stellarkehler; every action is re-checked server-side inside the SQL functions,
so the page itself is safe to be public). admin.bat still works locally too
(same admin.html, service key from supabase_sync.env). See CLAIMING_SETUP.md §3.
Setup status: LIVE as of 2026-07-09. Supabase project "followville"
(ref bposhxtidoyulallvhdp, in Cade's "The Human Archive" org) created, schema run,
email-confirmation OFF, legacy anon key pasted into town.html (deployed, commit
c180164), service-role key in supabase_sync.env (local only), all 30 buildings
backfilled into `houses`. Verified end to end: anon REST reads houses (30 rows),
public_claims readable, profiles hidden from anon. Still TODO someday: enable
CAPTCHA (Auth -> Attack Protection, needs a Cloudflare Turnstile account) and the
automated Instagram DM webhook (CLAIMING_SETUP.md §4). To approve verifications:
CLAIMING_SETUP.md §3 (SQL editor, `select admin_verify('handle');`).

## Milestones (auto-built when population crosses)
500 fountain plaza | 2,000 skyscraper | 10,000 stadium

## Web viewer (Followville)
index.html = the landing/home page (logo, tagline, live day/population stats, "Walk the
town" button). town.html = the actual first-person walkable town (Three.js GLTFLoader);
town.glb = exported geometry. Landing page stats are pulled straight from world_state.json's
own `day`/`pop` fields on a ~45s poll — no calendar/date math anywhere, since day/pop should
ONLY change when the town is actually regrown via grow.sh, never on a timer. Population is
intentionally NOT derived from building count (a future apartment building could hold many
followers in one building) — always read `state.pop` directly, never `buildings.length`.
Logo image expected at logo.png next to index.html (falls back to an emoji if missing).

grow.sh auto-exports town.glb after every growth — generator and export_web.py MUST run in
the SAME blender invocation (--python a.py --python b.py). PITFALL (fixed, don't reintroduce):
the GUI City-panel Grow button saves the .blend including built objects; a separate export
launch would read that stale scene. Blend was purged + resaved clean on day 4.

PITFALL (fixed, don't reintroduce): export_web.py must jump to the animation's final frame
(scene.frame_set(scene.frame_end)) before realizing/exporting, or newly-risen houses can get
baked mid-rise ("pancaked" flat to the ground) — the daily rise animation scales buildings
from scale.z≈0.001 up to 1 over the clip, and export_apply=True bakes whatever frame is current.

PITFALL (fixed 2026-07-08, don't reintroduce — this is the REAL fix for the "pancaked houses"
bug, the frame_end jump above was necessary but not sufficient): the frame_end jump only sets
which frame the SCENE is on: it does nothing to remove the actual keyframe animation still
attached to that day's new buildings. `duplicates_make_real()` forces Blender to re-evaluate
the depsgraph, and if an object still carries a live Action with scale keyframes (which every
NEW building does — that's exactly what `animate_rise()` just gave it), that re-evaluation
reasserts the F-curve's value and silently overwrites a plain `obj.scale = (1,1,1)` Python
assignment right back to whatever the curve says. Confirmed directly in the deployed day-7
town.glb via pygltflib: the pond and all 3 new houses (this run's only animated objects) came
out with every mesh part at scale `(1, 0.001, 1)` — the exact frame-1 "not risen yet" value —
baked as orphaned top-level nodes with no parent, while every older building (which has NO
animation data in a later day's Blender session, since `animate_rise()` is only ever called
on the day a building is born) exported fine. That's why it only ever hits the NEWEST batch
and looked so mysterious — it's invisible until the next growth day adds something new.
The fix, in export_web.py's WORLD-collection loop, right before `duplicates_make_real()`:
call `obj.animation_data_clear()` on every object (in addition to, not instead of, the
existing scale-reset and frame_end jump — keep all three). Clearing animation_data removes
the Action outright, so there is no F-curve left that could ever reassert a stale value,
regardless of depsgraph evaluation order. Verified fixed by re-running export_web.py and
checking town.glb with pygltflib: 37 squashed (scale≈0.001) nodes before the fix, 0 after.

## Collaboration (Cade + Zach)
This whole folder lives in an iCloud Drive synced folder, shared between Cade and Zach —
each has it synced locally via iCloud Drive, and each points their own
Cowork/Claude session at their own local copy. They take turns (never edit at the same
time); check that iCloud Drive shows fully synced to the other's machine automatically,
so it's just there next time either person (or their AI) opens the folder — no git pull
needed for this part. GitHub + Vercel (see "Deploying the live site" section below) are
separate and only used for deploying the live website; Zach doesn't need GitHub/Vercel
access unless he wants to deploy himself.

Whoever's AI makes a change should add ONE line to TEAM_LOG.md before handing off (plain-
English, not technical) — that's the whole "who changed what" tracking mechanism. Check
TEAM_LOG.md at the start of a session to see what happened on the other person's last turn,
and check that Google Drive shows fully synced before starting your own turn.

### Third AI: "Cade Claude on Windows" (Cowork)
As of 2026-07-07, Cade also works this project from a Windows PC, via Claude in Cowork mode.
That session is a THIRD AI with access to this same folder — alongside Cade's Mac Claude and
Zach's Mac Claude. It reaches the project through the same iCloud Drive sync (folder path on
this machine: `C:\Users\cadet\iCloudDrive\neighborhood`), so the same rules apply: take turns,
check iCloud is fully synced before starting, add a TEAM_LOG.md line before handing off (sign
it "Cade (via Windows Claude)" so it's clear which AI/machine made the change).

**What's different about the Windows session — corrected 2026-07-07:** its file/bash tools
run inside a sandboxed Linux shell that only sees this mounted folder (no Blender there,
no path to launch one) — but this machine ALSO has a separate screen-control tool
(computer-use) that, once Cade grants access, can see the real Windows desktop and drive
it with actual clicks/keystrokes. **Blender 5.1 is installed on this PC.** Verified
2026-07-07: with that access granted, this session opened `neighborhood.blend` in the real
Blender GUI, used the Scripting tab to inspect the embedded generator script, and closed
back out without saving. So:
- It CAN open Blender and click around the GUI (File > Open Recent, Scripting tab, etc.) —
  useful for inspection/diagnosis. This is something the Mac Claude sessions have never
  done, since they only ever drive Blender headlessly via `grow.sh`.
- It should NOT drive the GUI City panel to run growth days. Simulated clicks are fragile —
  one stray keypress during testing briefly flagged the file as having unsaved changes with
  no visible edit. For a file where `world_state.json`/the `.blend` is the city's only
  memory, that risk isn't worth it.
- **`grow_windows.bat` + `grow_windows.ps1` now exist** (built 2026-07-07) — a proper headless
  Windows equivalent of `grow.sh`: same `+N`/`-N`/`=N`/`replay` syntax and extras, runs
  `blender.exe --background` (no GUI, nothing to click), writes progress + the final
  RESULT/STILL/VIDEO lines to `grow_log.txt` ending `ALL_DONE`/`ALL_FAILED`. Best launched via
  Win+R (typing works there) with something like
  `"C:\Users\cadet\iCloudDrive\neighborhood\grow_windows.bat" +5 --render` — typing directly
  into a visible Command Prompt/Terminal window is blocked for this session, so that's the
  practical way to pass arguments without a human at the keyboard. **Verified working
  2026-07-07** with a real `replay` run (safe — never touches `world_state.json`/the
  `.blend` by design): got `ALL_DONE`, `town.glb` refreshed, state file untouched (checked
  by hash). Still get Cade's go-ahead before the first real `+N`/`-N`/`=N` growth day from
  here. Two gotchas already hit and fixed: (1) keep both files plain ASCII — Windows
  PowerShell 5.1 misreads em-dashes/curly quotes in a BOM-less `.ps1` and can crash
  mid-string; (2) `$ErrorActionPreference = "Stop"` plus `2>&1` on the Blender call turns
  even harmless stderr output (e.g. a Python `DeprecationWarning`) into a fatal PowerShell
  error — the script now relaxes that just around the Blender invocation.
- **`preview_website.bat` + `preview_website.ps1` also exist** (built 2026-07-07) — a tiny
  PowerShell-only local HTTP server (no Python/Node dependency) for previewing
  `index.html`/`town.html` on this machine, since their `fetch()` calls don't work over
  `file://`. Auto-opens the default browser to `http://localhost:8000/`; auto-stops after
  20 minutes. Verified working: landing page and `town.html` both correctly showed live
  "day 5 / population 22" from `world_state.json`, and `town.glb` loaded over the wire
  (200 OK) — confirms the Blender-to-website pipeline is intact from Windows.
- It CAN safely do everything else: edit/read docs (README, CLAUDE.md, AI_HANDOFF.md,
  TEAM_LOG.md, WEB_VIEWER_CHANGELOG.md), tweak the web viewer (`index.html`, `town.html`),
  inspect `world_state.json` and `town.glb` (read-only unless Cade explicitly asks for a
  hand-edit — see the "never edit/delete casually" rule at the top of this file), open
  Blender read-only for diagnosis (always "Ignore"/"Don't Save" on any prompt), and general
  planning/writing tasks.
- If asked to "grow the town" or render a video, it should say so and offer either: point
  Cade to running `grow.sh` on a Mac, or offer to build the headless `.bat` wrapper above —
  rather than attempting the GUI-clicking approach for a real growth day.
- **Deploying to the live site** (see "Deploying the live site" section above for why this
  matters — growing the town alone does NOT push). **`deploy_website.bat` now exists**
  (built 2026-07-07) — a one-click push script that copies this iCloud folder's
  known-tracked files (index.html, town.html, town.glb, world_state.json,
  neighborhood_blender.py, grow.sh, export_web.py, the .md docs, etc. — NOT renders/,
  debug logs, or one-off scripts) into a local git clone at
  `C:\Users\cadet\followville_repo`, commits, and pushes to `origin/main`. Progress + a
  final `ALL_DONE`/`ALL_FAILED` go to `deploy_log.txt`. Git itself wasn't installed on
  this PC before — added via `winget install --id Git.Git -e --source winget`; the clone
  was made with `git clone https://github.com/tooheycade-design/followville
  C:\Users\cadet\followville_repo`. First real push (2026-07-07, the day 6 + street-cam
  update) needed a one-time `git config --global user.name/user.email` (now set) and one
  interactive GitHub sign-in via the browser (Git Credential Manager popped up a normal
  github.com login page for Cade to complete himself — this session never sees or handles
  the credentials). Later pushes should be silent unless that browser login expires.
  Verified working end to end: pushed day 6/pop 26 + the new street-cam feature, confirmed
  live on `followville-kappa.vercel.app` within about a minute (stats and `town.glb` both
  updated).
  - **Gotcha:** run Windows commands here as a `.bat` file (write it, then launch via
    Win+R), never as one long `cmd /c "...with nested quotes..."` string typed directly
    into Win+R — a complex one-liner with nested `"` silently mis-parses and the command
    chain just stops partway with no visible error, which looked exactly like a hung
    `git clone` the first time this was tried (it wasn't hung; the quoting broke).
  - **Bigger gotcha, hit hard on 2026-07-08 (day 7 pond growth day) — READ THIS:**
    `world_state.json`'s plain filename is NOT stable between two separate Win+R-launched
    `.bat` invocations, even seconds apart, even with no other person actively editing
    anything. The pattern: run #1 (`grow_windows.bat +3 --pond`) correctly grows and saves
    the town (day 7 confirmed in `grow_log.txt`'s RESULT line) — then run #2 (a `replay`
    call to render a shot) comes back with `"day": 0, "population": 0, "buildings": 0`,
    i.e. `load_state()` found nothing and fell back to the empty default. Checked via
    Notepad's File > Open dialog (the most authoritative "does Windows itself see this
    file" test — more reliable than File Explorer's status icons, which kept showing a
    stuck blue "syncing" bar on a file that Notepad said flatly did not exist): the plain
    `world_state.json` really was gone, and iCloud had spun up a numbered conflict copy
    (`world_state 3.json`, `world_state 4.json`, ...) holding the correct day-7 content
    instead. This happened repeatedly, not once — restoring the plain filename (Write tool,
    or a `copy` command) and then waiting even ~30-45s before the next Blender launch was
    NOT enough; iCloud renamed it away again in that gap every time. The same thing then hit
    THIS FILE (`CLAUDE.md`) mid-edit while writing up this very lesson — and it hit again on
    2026-07-08 during the pancaked-houses fix, mid-edit for the SAME `CLAUDE.md` file for the
    exact same reason (an Edit call landed on `CLAUDE 4.md` instead of the plain filename;
    recovered by reading the fully-edited conflict copy and Write-ing it straight to the
    canonical path, per the fix below — no data was lost, just an extra round-trip).
    **The fix that actually worked:** stop doing "restore the file" and "launch Blender" as
    two separate tool calls with a gap between them. Instead write ONE `.bat` that does the
    `copy /y "world_state N.json" "world_state.json"` restore AND the
    `call grow_windows.bat replay ...` (or `call deploy_website.bat`) launch back-to-back,
    then run that single combined `.bat` via one Win+R. With no round-trip back through
    Claude's tools in between, the race window closes and Blender reliably sees the correct
    file. Used this pattern for both shot renders and the deploy step on day 7 — all three
    worked first time once combined this way. For a plain doc edit (no Blender involved,
    like this file), there's no combined-script equivalent — when an Edit call reports the
    canonical path doesn't exist, just find whichever `CLAUDE N.md` conflict copy has the
    edit, finish editing THAT copy, then `Write` its full final content straight back to the
    canonical path in one shot (not another `Edit`) to close out the recovery in a single
    tool call. If this happens again: find whichever `world_state N.json` / `CLAUDE N.md`
    conflict copy has the freshest/correct content (check timestamps + open a few to
    compare), then always pair its restore with the next action in one script (for
    Blender/deploy work) or do a single `Write` of the finished content (for doc edits).
  - **Another gotcha, same day:** `grow_log.txt` (and possibly other plain-named files read
    via the Linux-sandbox bash mount) can appear STALE/frozen mid-write from that mount's
    point of view — `tail`/`wc -l` kept returning the exact same byte count across several
    checks 15-25s apart even while the underlying Blender process was still actively running
    and had in fact already finished. Bash's `ls`/`stat` metadata for this same mount was ALSO
    seen showing a day-old mtime for `town.glb` even once its actual just-written content was
    already fresh and correct. **Lesson: for this iCloud-synced folder, don't trust bash's
    view of file freshness (`ls`, `stat`, `tail`, `wc -l`) as proof that a write hasn't
    happened yet.** If a Windows-side process should have finished, verify by reading the
    file's actual CONTENT through a tool that does a real fresh read (the Read tool, or a
    Python script that opens and parses the file, e.g. `pygltflib` on `town.glb`) rather than
    concluding from a stale directory-listing/log-tail that the process is still running or
    stuck.

## Files
neighborhood.blend (scene; GUI panel: N key -> City tab) | neighborhood_blender.py (generator)
grow.sh (CLI) | world_state.json (THE CITY) | renders/ (videos) | AI_HANDOFF.md (cheap-model manual)
TEAM_LOG.md (plain-English "who changed what" between Cade & Zach, see Collaboration section)
world_state_*_backup.json = old test states, ignorable.

Windows-only tooling (permanent, keep): grow_windows.bat/.ps1, preview_website.bat/.ps1,
deploy_website.bat — see "Third AI" section above for what each does.

check_town_glb.py (permanent, keep, cross-platform — no Blender needed, just
`pip install pygltflib`): standalone sanity check for town.glb (catches pancaked/squashed-scale
exports and world_state.json/town.glb mismatches). Runs as part of export_web.py automatically,
and again independently via the `.github/workflows/check_town_glb.yml` GitHub Action on every
push to main. See "Where world_state.json + town.glb actually live now" above.

Windows-only scratch files (safe to ignore, not tracked by git, not part of the deploy
whitelist — leftover from building/debugging the above on 2026-07-07): clone_repo.bat,
cleanup_procs.bat, check_repo.bat, inspect_repo.bat, inspect_repo2.bat, git_config.bat, and
their matching .txt log outputs, plus deploy_check.txt, git_install.txt, proc_check.txt,
proc_check2.txt, grow_log.txt, grow_step1_growth.txt, grow_step2_hero.txt,
grow_step3_overhead.txt, grow_street.txt. Also from 2026-07-08 (day 7 pond growth day, see
the `world_state.json` race gotcha above): fix_and_hero.bat, fix_and_overhead.bat,
fix_and_deploy.bat (the combined restore-copy + launch scripts that fixed the race),
check_push_status.bat/.txt, restore_canonical.bat/.txt, pull_and_check.bat/.txt,
check_remote.bat/.txt, list_folder.bat, fix_reexport.bat (re-exports town.glb after the
2026-07-08 pancaked-houses fix; safe replay-mode, no world_state.json/blend changes),
install_ci_check.bat/.txt (one-off script from 2026-07-09 that copied check_town_glb.py +
check_town_glb.yml into the git repo clone and pushed them — already ran, safe to ignore/delete
once confirmed the GitHub Action shows up on the repo's Actions tab), check_town_glb.yml (the
GitHub Action source file, kept here for reference — the live copy that matters is the one
already pushed to `.github/workflows/check_town_glb.yml` inside the git repo clone),
check_town_glb_setup_note.txt (Fable-written setup note for the above, safe to ignore once read).
Nobody has deleted these per the "never delete without approval" rule at the top of this
file — ask Cade before cleaning them up.

Numbered/parenthesized conflict copies (`world_state 2.json`, `CLAUDE(1).md`, etc.) are
iCloud sync artifacts, not intentional files — see the race-condition gotcha in the Third AI
section for why they keep appearing and how to recover from them. Don't delete these either
without checking their content first (one of them may hold the only copy of the current
canonical state, as happened on day 7).
