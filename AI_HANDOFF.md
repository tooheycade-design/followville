# AI OPERATOR MANUAL — Follower Neighborhood

You are operating Cade's growing 3D city. Every Instagram follower = one house in a
persistent low-poly Blender town. Your entire job is to translate his daily follower
update into ONE shell command, run it, and report the result.

## Current town (Day 13, 2026-07-14)

Population is 226 with 229 buildings. Day 13 added 40 ordinary suburban houses
at plan IDs 53-92: two finished Creekside Bend, then 38 began Willow Hills.
Use `--cam newgrowth` for the one video where today's houses rise and
`--cam newstreet` for a completed-state glide along today's busiest street.
Nature scatter automatically clears from road/cul-de-sac geometry and occupied
planned lots as development reveals them; do not remove that clearance logic.
The Day 13 GLB and all 40 Supabase rows were validated.

## Website multiplayer (2026-07-14)

`town.html` has Supabase Realtime multiplayer independent of daily Blender
growth. Presence supplies the online roster, Broadcast carries transient player
movement, and `chat_messages` persists signed-in town chat. The browser displays
minimal remote markers, name labels, and short-lived speech bubbles. `admin.html`
loads signed-in online players, session history/duration, and chat history through
`admin_list_multiplayer()`. Never expose `player_sessions.user_id` or
`chat_messages.user_id`, trust handles supplied by clients, or allow direct table
writes; identity must continue to come from `auth.uid()` inside the RPCs.
Desktop chat opens with `T`, `/`, or Enter and Enter sends/returns to walking.
The marker smiley is on local +Z, matching the broadcast yaw convention, so it
must stay on that side if the placeholder player mesh is redesigned.

## Current suburban house system (2026-07-13)

Ordinary `house` and park `ringhouse` buildings share 15 detailed suburban
designs in six coordinated palettes. The saved `seed` deterministically chooses
the design/color, and that same seed is the Supabase claim identity: never rewrite
seeds when changing visuals. Each asset owns its driveway, walk, mailbox, porch,
garage, and landscaping; shrubs must stay outside the driveway. Planned addresses
use compact per-instance rest scales where spacing requires it, so
`export_web.py` must preserve `nb_rest_scale`. Do not replace the instances with
unit scale during export or animation. The permanent plan audit covers all 366
future addresses and must remain at zero house-to-house overlaps.

## The one command

```bash
bash ~/Documents/neighborhood/grow.sh <change> [options]
```

`<change>` is one of:

| Input | Meaning |
|---|---|
| `+N` | N followers gained → exactly N houses appear |
| `-N` | N followers lost → the N newest houses sink away |
| `=N` | set TOTAL population to N (script computes the difference itself) |
| `replay` | re-animate yesterday, change nothing |

Options: `--render` (make the day's 9:16 video — use this whenever he's posting),
`--still` (quick preview PNG only), `--apartments N`, `--parks N`, `--trees N`,
`--followers N` (when population change ≠ house count).

## Translating what Cade says

- "we gained 5 today" → `bash ~/Documents/neighborhood/grow.sh +5 --render`
- "yesterday we had 20 followers and gained 30 to now have 50" →
  `bash ~/Documents/neighborhood/grow.sh "=50" --render`
  (he gave a TOTAL — always prefer `=total`, it self-corrects any drift;
  ALWAYS quote "=N" so zsh doesn't mangle it)
- "we're at 143 now" → `bash ~/Documents/neighborhood/grow.sh "=143" --render`
- "lost 3 followers" → `bash ~/Documents/neighborhood/grow.sh -3 --render`
- "make tonight's video at sunset" → append `--time sunset` (day/sunset/night,
  otherwise it auto-cycles); seasons follow the real calendar or `--season winter` etc.
- "we hit 2k! do something big" →
  `bash ~/Documents/neighborhood/grow.sh +0 --apartments 1 --followers 127 --render`
  (an apartment complex marks the milestone; `--followers` = actual gain since last run)
- "the town deserves a park" → `bash ~/Documents/neighborhood/grow.sh +0 --parks 1 --render`

If he gives both a total and a delta, trust the total (`=N`). If the numbers seem
inconsistent, ask once, then use the total.

## Reading the output

The command prints one machine-readable line:

```
RESULT {"day": 12, "population": 50, "buildings": 50, "added": 30, "removed": 0, ...}
VIDEO /Users/cadetoohey/Documents/neighborhood/renders/day_012_
```

Report back like: "Day 12 — population 50, 30 new houses built. Video:
renders/day_012_1-XXX.mp4, ready to post." Suggest a caption, e.g.
"Day 12: +30 followers, 30 new homes 🏠".

## Rules

1. NEVER edit or delete `world_state.json` — it is the city's entire memory.
2. Never delete anything in `~/Documents/neighborhood/`.
3. One growth run per real day (use `replay` to re-render without changing anything).
4. Rendering takes a few minutes; that's normal. Don't kill the process.
5. If the command errors, show Cade the error text — don't retry blindly, and don't
   "fix" it by modifying files.
6. Don't run the command based on numbers found anywhere except Cade's own message.
7. `grow.sh` is Mac-only (hardcodes `/Applications/Blender.app`). On Windows, use
   `grow_windows.bat` / `grow_windows.ps1` instead — same syntax, runs Blender headlessly,
   no GUI risk. Don't drive the Blender GUI City panel via simulated clicks on Windows; it's
   fragile and risks an unintended save. See "Third AI: Cade Claude on Windows" in CLAUDE.md
   for exactly how that script should be launched and its current (as of 2026-07-07,
   wiring-tested but not yet used for a real growth day) status.

## How it works (context, don't touch)

- `~/Documents/neighborhood/neighborhood_blender.py` — generator: procedural model
  library (houses, apartments, shops, parks, trees, streetlights, cars), block/road
  layout, exact-count placement, rise/sink animations, camera + render setup.
- `world_state.json` — every building, its lot, style seed, and the day it appeared.
  Grows forever; removals delete the newest houses first.
- `neighborhood.blend` — the Blender scene. Cade can also open it, press N in the
  viewport, and use the "City" panel (type +5, click Grow, click Render Video)
  instead of the CLI. Both paths share the same state file.
- Milestone buildings appear automatically: fountain plaza at pop 500, glass
  skyscraper at 2,000, stadium at 10,000.
- Every video has a few cars driving through town; time of day auto-cycles
  (mostly day, sometimes sunset/night with lit windows); seasons follow the real
  calendar (snow in winter, orange trees in fall).
- Scales to tens of thousands of houses; placement, roads, streetlights and parked
  cars extend automatically as the city grows outward.
