# FOLLOWER NEIGHBORHOOD — project memory (read me first)

Cade's Instagram project: a persistent 3D low-poly town in Blender. Every follower = a house.
Daily reels show the town growing. THE CITY'S MEMORY IS world_state.json — NEVER edit/delete
it casually; back it up before risky operations.

## Current canon (update this section each day!)
- Day 6, population 26, 26 buildings (grown 2026-07-07 via Windows Claude: +4 houses).
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

## Files
neighborhood.blend (scene; GUI panel: N key -> City tab) | neighborhood_blender.py (generator)
grow.sh (CLI) | world_state.json (THE CITY) | renders/ (videos) | AI_HANDOFF.md (cheap-model manual)
TEAM_LOG.md (plain-English "who changed what" between Cade & Zach, see Collaboration section)
world_state_*_backup.json = old test states, ignorable.

Windows-only tooling (permanent, keep): grow_windows.bat/.ps1, preview_website.bat/.ps1,
deploy_website.bat — see "Third AI" section above for what each does.

Windows-only scratch files (safe to ignore, not tracked by git, not part of the deploy
whitelist — leftover from building/debugging the above on 2026-07-07): clone_repo.bat,
cleanup_procs.bat, check_repo.bat, inspect_repo.bat, inspect_repo2.bat, git_config.bat, and
their matching .txt log outputs, plus deploy_check.txt, git_install.txt, proc_check.txt,
proc_check2.txt, grow_log.txt, grow_step1_growth.txt, grow_step2_hero.txt,
grow_step3_overhead.txt, grow_street.txt. Nobody has deleted these per the "never delete
without approval" rule at the top of this file — ask Cade before cleaning them up.
