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
