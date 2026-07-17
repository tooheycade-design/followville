# AI OPERATOR MANUAL — Follower Neighborhood

You are operating Cade's growing 3D city. Every Instagram follower = one house in a
persistent low-poly Blender town. Your entire job is to translate his daily follower
update into ONE shell command, run it, and report the result.

## Current town (Day 15, 2026-07-16)

Population is 259 with 262 buildings. Day 15 added 15 claimable homes: ten
original `storybookhouse` seeds 248-257 around Wanderlight Loop in the new
Kaleidoscope Crest feature district, plus five ordinary seeds 258-262 at
Overlook Circle plan IDs 111-115 in Willow Hills. The Kaleidoscope Crest hill,
garden, lamps, flowers, loop, and access road are permanent Blender/GLB content
and reveal only with their homes. The access starts as ordinary asphalt at the
old grid, widens through a muted transition, then becomes bright pink; its
center markings follow the road's 3D climb. `town.html` mirrors the hill/ramp
height for local and multiplayer walkers. Keep the
`data-storybook-walkable="pass"` browser check whenever raised terrain changes.
The approved Day 15 delivery is three separate MP4s: `--cam wholeoverhead` for
the whole-town/all-15 rise, `--cam newgrowth --focus-type storybookhouse` for
the close ten-home rise, and `--cam storybookstreet --focus-type finished` for
the completed road-level tour. Do not stitch these into one long video. Aerial
cameras must keep their 10m near clip; that prevents moving roads and ponds
from flashing due to depth-precision loss. All three clips passed visual QA and
were emailed as distinct attachments to Cade and Zach. All 15 Day 15 Supabase
rows were validated. Repo-based Windows growth still skips the legacy iCloud
`wip` auto-share hook so the authoritative clone remains on `main`.

Kaleidoscope Crest's merged house assets need material-based collision bounds:
`town.html` intentionally uses only `NB_story_wall*` vertices at player height,
never the full merged mesh, because that mesh also contains each lawn, path,
flowers, fence, and mailbox. Its steep access-road dashes are custom surface
meshes sampled from the sloped road centerline. Each center lamp is now one
continuous curved shared-ring tube with an overlapping globe, base, and two
attached banner brackets. The former island tree is now a polished Cat in the
Hat statue with connected limbs, tail, fingers, face/bow layers, a single
shared-ring six-band hat, an interlocking pedestal, and a 2.18m base collider.
Keep the browser audits
`data-storybook-hitboxes="pass"` and `data-kaleidoscope-statue="pass"`.

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

The landing composition intentionally avoids generic generated-dashboard
styling: the map is framed like a flat paper plan, navigation uses simple ruled
text rows, stats are unboxed, corners are nearly square, and blur/pill/icon-card
treatments are minimal. Preserve this restraint in future homepage changes.
The Walk destination intentionally links to `town.html#walk`, which removes the
route hash and enters the rendered neighborhood without exposing the older
in-town start screen. Desktop users can click the town canvas to capture
mouse-look; mobile begins with the existing touch controls. Once walking on
desktop, Escape opens a real pause menu while preserving the camera position.
`resume` continues from that same spot; only the explicit
`leave town` action returns to the homepage. Escape still closes map/chat
overlays in place. Claimed homeowners can reach the safe confirmed per-house
unclaim action through `manage my home(s) / unclaim` on the town/start screen
and through the pause menu.

The low-poly backdrop mountains are website atmosphere, not Blender terrain.
Their distance is calculated against every current building on each load; a
hill stays on its authored bearing but moves outward until its enclosing base
has 18m of town clearance. Do not return `FV_distant_hills` to a fixed-radius
ring: Day 14 Overlook Circle reached the old ring and Houses #230-247 intersected
two hills. The walking browser regression requires
`body[data-hill-clearance="pass"]`.

## Live town map (updated 2026-07-16)

The homepage, start screen, in-town map button, and desktop `M` all reach the
same responsive isometric 3D map. It uses a small instanced scene rather than
loading a second full town GLB, supports rotate/pan/zoom, and keeps a flat
fallback for unavailable WebGL. Search supports house number, live claimed handle,
street/district, newest homes, the school, claimed homes, and the signed-in
user's homes; Visit teleports the player outside the selected location. The
normal sidebar is now eight compact street groups, not one large house list.
Clicking a street focuses its homes in the existing 3D scene; clicking a 3D house
teleports directly. Search accepts explicit `@owner` handles (including partial
handles), ranks exact owners first, and returns individual house cards with
Visit/Share. Newest and claimed filters group their results by street. The
map is intentionally self-updating: it rebuilds from `world_state.json` and
`public_claims`, including the established Founder Park rings and only roads
implied by already built planned houses. Do not add manual map coordinates, a
second source of truth, or a second copy of the full town GLB.

## Public places and Today activity (2026-07-16)

The homepage's `Today in Followville` row is dynamic: it finds the newest day
in `world_state.json`, counts that day's homes, names their current district and
streets, and links to `/today`. That clean route opens the same live 3D map with
the newest-home filter, update summary, highlighted roofs, and a selected place
ready to visit. It must roll forward automatically on future growth days.

Each home has a permanent `/house/<seed>` address and a Share control in the map
selection. The route uses the existing seed, building data, and `public_claims`;
do not create a second place table or duplicate coordinates. These permanent
place identities and reusable activities are the intended foundation for later
roleplay systems such as interiors, jobs, events, and location actions. Vercel
rewrites `/today` and `/house/:id` to `town.html`; keep the document's root
`<base>` so `town.glb`, state, video, and other assets still load beneath clean
nested URLs. Run `pnpm install` once, then `pnpm test:e2e` after navigation or
map changes. The five-test Playwright suite also runs in GitHub Actions.

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
