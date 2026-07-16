# AI OPERATOR MANUAL — Follower Neighborhood

You are operating Cade's growing 3D city. Every Instagram follower = one house in a
persistent low-poly Blender town. Your entire job is to translate his daily follower
update into ONE shell command, run it, and report the result.

## Current town (Day 14, 2026-07-15)

Population is 244 with 247 buildings. Day 14 added 18 ordinary suburban houses
at plan IDs 93-110: three completed Foxglove Court and 15 began Overlook Circle.
Its future turnaround is still hidden. Use `--cam newgrowthoverhead` for the one
top-down video where today's houses rise and `--cam newstreet` for a
completed-state glide along today's busiest street. `--cam football` is a
temporary Day 14 fan-video mode and must never be used for the permanent GLB.
Nature scatter automatically clears from road/cul-de-sac geometry and occupied
planned lots as development reveals them; do not remove that clearance logic.
The Day 14 GLB and all 18 new Supabase rows were validated. On Windows, running
`grow_windows.ps1` from the authoritative repo intentionally skips the old
iCloud `wip` auto-share hook so the clone stays on `main` after growth.

## Website landing experience (2026-07-15)

`index.html` and the `town.html` loading/start screen use the same optimized
12-second `assets/town-loop.mp4`: a current Day 14 Overlook Circle house seen
from the sidewalk while two cars pass at separate times. The static companion
poster is the fallback for reduced-motion, data-saver, blocked autoplay, and
initial loading. Generate a replacement with `--cam housefront`; that camera
and its traffic are render-only and must not alter `world_state.json`, the
permanent blend, GLB, population, buildings, or claims.

The homepage overlays that loop with an organized destination dashboard rather
than stacked buttons. Desktop shows Walk/Claim cards beside a large live town
preview; mobile keeps the preview and both actions compact above the fold. The
preview redraws from the same `world_state.json` request as the counters and
must remain self-updating rather than becoming a screenshot or second data file.
`vercel.json` redirects bare `/` to `/index.html` and applies `no-store` to both
homepage routes, while the homepage's `pageshow` handler reloads only
back/forward-cache restorations. Preserve all three: they prevent different CDN
route caches or an already-open computer browser from intermittently reviving
an older deployed homepage.

## Live town map (2026-07-15)

The homepage, start screen, in-town map button, and desktop `M` all reach the
same responsive isometric 3D map. It uses a small instanced scene rather than
loading a second full town GLB, supports rotate/pan/zoom, and keeps a flat
fallback for unavailable WebGL. Search supports house number, live claimed handle,
street/district, newest homes, the school, claimed homes, and the signed-in
user's homes; Visit teleports the player outside the selected location. The
map is intentionally self-updating: it rebuilds from `world_state.json` and
`public_claims`, including the established Founder Park rings and only roads
implied by already built planned houses. Do not add manual map coordinates, a
second source of truth, or a second copy of the full town GLB.

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

## Homeowner Mode (2026-07-15)

Claimed-house owners can customize exterior, roof/accent, and door colors. The
data model still retains the previously offered yard choice, but **yard rendering
and its chooser are temporarily paused by Cade:** keep
`YARD_DECORATIONS_ENABLED = false` until a new design is approved. Existing yard
values remain stored but invisible; do not erase or migrate them. `town.html` reads the
existing `claims.customization` JSONB through `public_claims`; the normal
`claims` Realtime channel applies saves to every visitor. Saves must continue
to use `update_my_customization(bigint,jsonb)`, which requires an explicit
house ID owned by `auth.uid()` and accepts only the hard-coded palette IDs.
Never grant direct
client UPDATE on `claims`. The browser clones materials per claimed house before
recoloring, preserving shared GLB batching and preventing neighboring houses
  from changing. Yard pieces must remain in the measured strip between the
  home's real GLB façade and the curb. Use the actual root facing, preserve the
  corner-lot road guard, and preserve the side-lawn/door/garage avoidance.
  Clearance must use `decorationObstacleFootprint()` (the complete exported
  roof/door/garage silhouette), not the ground-level collision footprint. It
  must measure accepted material groups/triangles inside optimized multi-material
  meshes; accepting a whole mesh because one material matches also accepts its
  driveway and mailbox. Founder house #29 proves both distinctions matter.
  Benches must face the street, flags must stay curbward of porch covers, and
  tight lots may compress front-to-back but must not shrink the whole piece or
  move it behind the house. Web collisions use oriented boxes for
  houses/cars and measured trunk cylinders for trees; never restore one large
  circular hitbox per GLB root. House #29 is the one Blender-authored exception:
  its structure is set back 1.3m while its drive/walk remain curb-connected, and
  its open-side lawn socket fits pieces between the path and mailbox. Never
  rewrite building seeds or world state to accomplish a visual correction.

Trusted `profiles.is_admin` accounts (`cade.toohey` and `stellar.kehler`) may
own two homes; all normal users remain limited to one. The limit is enforced by
`claim_house()` plus `claims_enforce_owner_limit`, not by UI state. Multi-home
actions must keep passing a specific house ID so one home cannot overwrite or
unclaim the other.

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
