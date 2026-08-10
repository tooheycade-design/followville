# Codex handoff -- current through Day 39

Updated 2026-08-10 for Cade and Zach's next Claude/Codex session. Newest session
first; the 2026-08-06 section below it is still current except where this one
supersedes it.

## Read this first -- 2026-08-10 session (Cade, via Windows Claude)

The Food Court's nineteen homes were rebuilt and its connector re-routed. Six
things here will bite you if you assume the old behaviour.

1. **Importing `neighborhood_blender` in a background Blender session RUNS A
   GROWTH.** The module ends in `if bpy.app.background: main()` -- that line is
   the entire difference between "load the generator" and "grow the city". Set
   `os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"` **before** the import if you
   only want the functions; nothing in the growth path sets it, so the launchers
   and the GUI panel are unchanged. `check_food_assets.py` is the worked example.

   This is first because of what it cost. A checker of mine imported the
   module with `NEIGHBORHOOD_STATE_DIR` pointed at the repo and silently
   advanced the world to day 40, appending five Northgate houses.
   `git checkout -- world_state.json` was the whole repair -- but in the
   meantime `town_manifest.json` disagreed with `world_state.json`,
   `validateTownManifest()` threw, and the browser **quietly dropped out of
   district streaming into the full-GLB fallback**. That fallback never assigns
   `localWalkSurfaces`, so the walk-surface manifest went empty and a Playwright
   test failed 400m away from anything that had changed. **A state/manifest
   mismatch does not announce itself.** If a walk-surface or streaming test
   starts failing for no reason, compare `world_state.json`'s day / pop /
   building-count against `town_manifest.json`'s `state` block first.

2. **Food house assets face local -Y, like every other house in town, and the
   Food Court's stored `rot` values were 90 degrees out.** `food_court_lots()`
   returned `a + pi`, which points the authored front along the ring *tangent*,
   so all nineteen showed the plaza a side wall. It is `a - pi/2`, and the 19
   stored values were rewritten to match (positions untouched). The ring
   constants in that function also said 46x38 when the day-37 run wrote its
   addresses from **40x33** -- if you re-derive a Food Court lot, use the
   function, not any figure you remember.

3. **`check_food_assets.py` is new, and it needs Blender.** It builds the ten
   food house designs before the per-house merge collapses them and requires:
   nothing below its own foundation, nothing past `FOOD_COURT_HOME_REACH`
   (4.80m), and no two axis-aligned boxes sharing a face plane over an
   overlapping area. It then measures all nineteen standing homes against both
   district roads using each design's **convex hull**. Use the hull, not a
   bounding box: a box round a 14-gon plinth with a doorstep has corners 6.45m
   from the anchor and reports homes as standing in roads they clear.

   ```text
   & "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" ^
       --background --factory-startup --python check_food_assets.py
   ```

4. **The river connector is a 3.0m lane where it passes the homes, and that is
   deliberate.** A 6m carriageway cannot exist there: nineteen homes evenly
   spaced leave no gap for a road, so it has to thread two of them, and those
   two stand 11.98m apart and take 8.18m of that between them. Do not "fix" the
   narrow neck by widening it. `food_court_connector()` derives its centreline
   from `food_court_lots()` and sites it on the line that balances the two
   homes' verges; it is sited from two measured reaches in
   `FOOD_COURT_GAP_REACH`, and `check_food_assets.py` re-measures those every
   run and fails with the real figure if they drift. Two ways this went wrong
   before it was right, both worth knowing: taking a home's *foundation* reach
   when its roof **overhangs** further put the lane inside the home it was moved
   to miss, and a pinch at a single point is not enough when a home presents a
   **flat side** to the lane, because then the clearance barely grows as the
   lane moves away.

   Also corrected: `world_layout.LANDMARK_FOOTPRINTS`' comment calls this "a road
   through one of its homes" and that is **right** -- measured properly it was
   one home by 2.51m, and the other cleared by 0.30m. An earlier commit message
   and TEAM_LOG entry of mine said two homes by 2.13m and 1.02m; that came from
   sampling one worst-case envelope for all nineteen designs and is wrong.

5. **`HOME_MATERIAL_ROLES` in `town.html` is not just a palette table -- it is
   what `isHome` is decided from.** `townMapItem()` reads it, and anything that
   is neither a home nor a landmark hits `if (!isHome && !landmark) return null`
   and vanishes from the town map. `foodhouse` had no entry, so all nineteen
   Food Court homes and their street were missing from the map for three days
   while being **claimable and synced to Supabase as claimable** -- an owner had
   no way to find their own house, no `/house/:id` teleport and no Homeowner
   Mode. **If you add a claimable house type, add it to that table in the same
   commit** or it is unreachable. Its palette roles point at the foundation, the
   trim and the door on purpose, so nobody can recolour a burger's bun.

   Worth generalising, and the reason this sat unnoticed: the walking test
   failed on `data-hill-clearance` eight assertions earlier and never reached
   the map. **One red assertion hides every assertion behind it.** When you fix
   a long-standing test failure, expect the next one rather than assuming green.

6. **Read CI's two jobs separately, and do not trust a red `browser`.** `check`
   (the Python audits) is meaningful on its own and has been green since
   `35accbb`. `browser` (Playwright) has been red on nearly every run for months
   because GitHub's two shared software-rendered cores time out on the heavy 3D
   tests -- **the failing set changes run to run on identical code** (6 failed
   at `96fbb2b`, 3 at `63a34fb`, 5 at `434dd06`, with tests appearing and
   disappearing), and the suite takes 32-45 minutes there against ~15 locally.
   Get your signal from `pnpm test:e2e` locally; use CI's `browser` only to
   compare *named* failing tests against the previous run.

   Corrected while checking this: the 2026-08-09 entry below says
   `check_town_glb.py` "already fails on pristine main ... CI has been red since
   `7de0a92`". That was true when written and is **not true now** -- the day-39
   growth re-exported everything and `check` has been green ever since. I
   repeated the stale claim before verifying it; don't inherit it a third time.

   The repo is **public**, so you need no `gh` login and no token to look:

   ```bash
   curl -s "https://api.github.com/repos/tooheycade-design/followville/actions/runs?branch=main&per_page=3" | jq -r '.workflow_runs[] | "\(.head_sha[0:9]) \(.status) \(.conclusion)"'
   ```

## Read this first -- 2026-08-06 session (Cade, via Windows Claude)

Five things changed that will bite you if you assume the old behaviour.

0. **No real names on the public website.** Cade and Zach are anonymous to
   visitors. `index.html`, `town.html`, `vote.html` and `admin.html` must not
   carry either name in visible copy -- `/vote` shipped saying "accounts Cade
   has approved" until it was caught. Inside the repo (this file, TEAM_LOG,
   HISTORY, code comments) names are fine and are staying.

1. **Phone play is no longer landscape-only.** The "turn your phone sideways"
   gate is gone and must not come back: most visitors arrive from Instagram,
   whose in-app browser can refuse to rotate, so it blocked play outright.
   Portrait has its own layout under
   `@media (any-pointer:coarse) and (orientation:portrait)`. Touch has no
   Escape key, so `#menuBtn` is the ONLY route to the pause menu -- keep it
   reachable. `data-mobile-orientation` is now `portrait|landscape|desktop`
   (the old `portrait-blocked` / `portrait-bypassed` values are gone).

2. **The walk-surface manifest is the contract for raised decks.**
   `walkSurfaceHeight()` used to filter `walk_surfaces.pads` to a hard-coded
   list of four dock types, silently discarding any other pad the generator
   exported -- which is why the weather station's parking lot was a hole you
   fell through. It now honours every pad. **To make a new landmark walkable,
   declare a pad in `world_layout.walk_surface_manifest()`; no browser change
   is needed.** `data-manifest-pads-walkable` fails if anyone puts an
   allow-list back in front of it.

3. **A level pad may no longer perch itself.** `RETAINED_PADS` says what holds
   a deck up; new `MAX_PAD_STAND` says how proud it may stand (1.60m default).
   A new landmark on a sloping site now FAILS `check_world_geometry.py` rather
   than shipping behind a long ramp. `--self-test` covers 8 regressions now.

4. **Landmark hitboxes are still a hard-coded list.** `addLandmarkColliders()`
   in `town.html` gates on an explicit type array. A landmark not in it gets
   **no colliders at all** -- that is how the Salmon Pro Shop ended up
   walk-through. Add new landmark types there.

### Known debt: the Salmon Pro Shop site (needs Cade's decision)

Its site falls **4.05m across the pad**, so the level deck stands 4.21m proud
at its low corner and needs a 60m sweeping approach to reach its own car park.
This is not a retaining-wall problem and the pad cannot simply be lowered: the
terrain mesh is generated from `terrain_height()`, so a lower pad has the
meadow rising through the asphalt.

**A terrain shelf is not available here.** Measured: the gentlest shelf that
covers the pad moves 20 already-built houses by up to 2m vertically, and
existing geometry never moves. Fixing it properly means relocating the shop to
flatter ground (the meadow is at grade 0 east of about x=-100) or terracing the
pad in steps. Do not "fix" it by raising its `MAX_PAD_STAND` entry.

### Timber Bend Crossing (built 2026-08-06)

A second river bridge, from Timber Bend Road at (502.9, 125.9) west to the
Kaleidoscope Crest access road at (236, 72). 292m, arched 64m deck, standard
3.25m half-width. `world_layout.timber_crossing_points()` is the single
description; the Blender geometry, the browser walk surface and
`check_world_geometry.py` all read it, so there are no copies to drift.

**Correction to an earlier note in this file:** it previously said the northern
east-bank districts had "no route to town". That was wrong, and the mistake is
worth knowing about. A graph that joins roads only where segments share an
endpoint reports the east bank as many separate islands. Roads are 6.5m wide,
so testing by *surface* — segments joined when their centrelines pass within
the sum of their half-widths — shows the whole east bank, Eastbank Village
included, as one continuous network, with Timber Bend 538m from the North
Ridge connector against 512m straight-line (a x1.05 detour). **Test road
connectivity by surface, not by endpoints.** The new crossing is a shortcut,
not a repair.

Two hard constraints, both measured, that will bite anyone moving this:

- **The latitude is forced.** South of y~140 the river runs PERCHED above its
  own meadow (up to 2.7m at y=60-100), so a bridge there spans water standing
  higher than the land. North of y~150 the west bank is a bluff: 36% at y=150,
  61% at y=170, 113% at y=270. y=143 is the only place the river is in its
  valley and both banks are gentle.
- **The deck must be arched.** The river's carve pulls the ground to the
  channel bed for 34m either side, so both abutments sit LOWER than the water
  between them; a straight chord ran 0.44m under the surface. The arch is sized
  from the worst shortfall over the water only — applying it near an abutment,
  where the arch shape is ~0, divides by almost nothing and lifts the deck 7m
  into the air.

### The river's bank (fixed 2026-08-06)

The river used to run **above its own meadow** between y=0 and y=120.
`river_water_height()` is a pure function of latitude and knows nothing about
the land, and the Crest plateau mask reaches ~55m past the plateau, across the
water, zeroing the ground there. `terrain_height()` now lifts the corridor to a
bank wherever a mask has dropped it below the waterline.

Three things to know before touching it:

- It **only raises** ground already below the water, and only near the channel.
  Everywhere the valley floor is already above the water it is a no-op, which is
  why the rafting outpost, Founders Crossing and the pond are unaffected.
- **Only the east bank was wrong.** On the west, the Crest's authored plateau
  already carries the ground at 2.80-2.94m over 2.50m water. A first attempt
  that lifted both banks moved all ten claimed founder houses by up to 3.08m;
  the plateau's keep-out ellipse now gates the lift out. **Re-run a
  before/after terrain sweep over every building in `world_state.json` if you
  change any of these numbers** -- that is what caught it.
- `town.html`'s `regionalTerrainHeight` carries the same code. They were
  verified equal at 1,144 points to 0.0000m. Change both or neither.

Still unchecked: nothing audits the river the way `LEVEL_WATER` audits the
pond, so a future edit to `river_water_height()` could re-perch it silently.

## Open the authoritative project

The executable project is `C:\Users\cadet\followville_repo`: code, canonical
`world_state.json`, complete/streamed web assets, and current documentation come
from Git. Start by reading `AGENTS.md`, `CLAUDE.md`, and the newest entries in
`TEAM_LOG.md` there, then compare local `main` with `origin/main`.

The shared authoritative Blender scene is
`C:\Users\cadet\iCloudDrive\neighborhood\neighborhood.blend`; the repo Blend is
a synchronized safety copy. Growth uses the generator/exporter from Git and
that iCloud scene in one guarded Blender session. Never execute a numbered
iCloud conflict copy, use iCloud-only state, or run the retired `--no-git`
workflow.

## Current canon

- Day 34 is live at population 720 with 782 total records and 34 streamed
  chunks. One guarded +31 growth consumed plan IDs 546-576 / seeds 752-782:
  eleven homes finished Millstone Way and twenty opened Ferry Street in
  Eastbank Village. Address 577 is next. The insert-only Supabase sync added
  all 31 claimable rows while the exact 41 existing claims remained unchanged.
  The reviewed delivery is `day_034_day34_fire_response_0001-0480.mp4`, an
  exact 16-second 1080x1920/30fps portrait film: a five-second angled downtown
  skyline with an unclaimed building fire and responding engine, a fast river
  transfer, and all 31 homes rising in one held composition. Fire, smoke,
  engine, hose, lights, and water are render-only and excluded from state and
  web exports. The MP4 is in shared iCloud renders and on Cade's Desktop.

- Day 33 is live at population 689 with 751 total records and 34 streamed
  chunks. One guarded +33 growth consumed plan IDs 513-545 / seeds 719-751:
  fourteen homes finished Timber Bend's Lodgepole Loop and nineteen opened
  Eastbank Village's Millstone Way. Address 546 is next. Permanent seed 718 is
  now published as the non-claimable Followville First Alert Weather station;
  it consumes no address or population. The insert-only Supabase sync added the
  previously local station plus all 33 homes. A read-only audit confirms the
  station is non-claimable, every new home is claimable, none of the new rows is
  claimed, and the current 41 claims across 40 accounts are preserved.

- The corrected, reviewed Day 33 delivery is
  `day_033_storm_weather_station_v2_0001-0600.mp4`, a 20-second 1080x1920 MP4 using
  `--cam day33storm --time storm`: full-town establish, Lodgepole and Millstone
  home-rise waves held together in one wide composition, a cross-town flight,
  seamless tiled rain, two lightning beats, and a final weather-station rise.
  Rain, lightning and the station's repeat rise are render-only and excluded
  from GLBs. This v2 supersedes the original closer render; it is in the shared
  iCloud `renders` folder and on Cade's Desktop.

- The local project now has a safe CC0 asset intake shelf documented in
  `ASSET_PIPELINE.md`: a provenance registry, deterministic hash/model manifest,
  searchable internal `asset-library.html`, 140-model Kenney Furniture Kit
  review library, isolated Blender normalizer, and focused tests. Nothing on the
  shelf is automatically exposed to players; promotion into interiors, avatars,
  or town geometry still requires explicit visual/performance review and the
  relevant client/server allowlist changes. Blender MCP was repaired to version
  1.8.0 and passed a local Blender 5.1 socket/scene probe with auto-connect off
  and telemetry disabled. Restart Codex to refresh its MCP tool registry.

- The web-only high-quality interior and homeowner furnishing release shipped
  from `codex/interior-builder-polish`. It replaces the visible primitive room
  with an enclosed, warmly lit four-zone home and a lazy-loaded 25-item local
  CC0 catalog. Verified owners can place, rotate, delete, undo, reset, and save
  up to 48 bounded quarter-grid pieces on desktop or landscape phone; visitors
  receive the saved layout through the existing claim Realtime path. The
  hardened version-2 `update_my_customization` migration is applied live and
  preserved the exact 40-claim / 39-account snapshot and digest
  `754ed801b3514af5f546255efc54f53a`; no claim row changed. Read
  `INTERIOR_SYSTEM.md` before changing it. The post-release alignment fix turns
  the kitchen fronts into the room, places kitchen/bath fixtures flush to their
  walls, restores the bathtub's correct full-size long axis, and removes
  furniture gameplay hitboxes while retaining shell collision and build-mode
  overlap checks. The follow-up room review also removed the default curtains,
  corrected the fireplace front/wall alignment, and fixed `town.html` ownership
  matching for the claim-record array so verified owners actually see
  **Furnish my home** after entering their claimed house.

- Day 32 was population 656 with 717 total records before the separate local
  weather-station record. One guarded +31 growth
  consumed plan IDs 482-512 / seeds 687-717: nineteen homes finished Timber
  Bend Road and twelve opened Lodgepole Loop. Address 513 is next. The
  insert-only houses sync added all 31 new rows without changing existing
  claims or ownership. Full fallback plus 32 streamed chunks represent the
  exact state. Suburban road bends no longer receive repeated raised cover
  discs; true junctions and cul-de-sac bulbs remain. The reviewed delivery is
  one 20-second daytime portrait MP4 with the whole town, all 31 home rises,
  the `VOTE MR MAYOR` / `VOTE BSB_DOMWILLIS` billboard, and the moving
  `VOTE XAD_INSTA` semi. Campaign props are render-only and excluded from GLBs.

- Day 26 is population 464 with 524 total building records. One guarded +25
  growth consumed addresses 296-320 (Juniper Court, Hemlock Court, then the
  first two Ridgeview Drive lots). Seed 523 added permanent East Woods at
  Blender `(170,180)`, using the regional elevation for its forest floor,
  142 mixed trees, understory, terrain ribbon trail, rocks, fallen log, and
  overlook. Seed 172 remains the non-claimable elementary school. New
  non-claimable seed 524 is the construction vote site at grid `(-6,3)`, where
  it suppresses the anonymous tower around website `(-83,-56)`. Central civic
  junctions have finished mast/lens/pedestrian signals and outer approaches
  have stop signs/bars. The exact
  claim snapshot remained 34 claims / 33 accounts with identical SHA-256
  `ec58555325ae4e0228a013be895cc5a0e212b92dc896430aaf761d67e006c294`.
  The full fallback and 28 preload-all chunks validate exactly. Fourteen local
  browser stories and two live smoke tests passed. The reviewed delivery is
  one 18.000-second 1080x1920 golden-hour portrait MP4 moving from the full
  city through all 25 home rises to the construction-site rise.

- Day 25 is population 439 with 497 total building records. The guarded +39
  growth consumed addresses 257-295 and added one permanent non-claimable
  Followville Fishing Pond near Fire Station 1. Its terrain-following sidewalk
  and dock are walkable, and the website offers a deliberately session-only
  timing/bite/rapid-reel fishing loop with five rarity tiers; money, selling,
  and inventory remain future work. Civic Square stays, its fountain now has
  clear authored water, and the temporary Day 24 election/400/fireworks layer
  is retired. The Day 25 delivery is one reviewed 18-second daytime portrait
  drone film moving from the city through all 39 home rises to the pond.

- Day 19 is population 331 with 334 total buildings. Zach's guarded Mac +10
  growth consumed plan IDs 178-187: seeds 325-331 completed Lantern Court and
  Twin Oaks, while seeds 332-334 opened Meadow Run. The insert-only houses sync
  added all 10 claimable rows. Full and seven-district assets report exact Day
  19 / 331 / 334 state and coverage, including the new `meadow-run.glb` chunk;
  address 188 is next. The reviewed delivery is two separate daytime portrait
  MP4s: all 10 split-district homes rising and a completed 12-second hovering
  drone crescent across downtown and the neighborhoods. `--cam newgrowthall`
  frames every home on split-district growth days; `--cam dronehover` is a
  reusable completed-town replay camera.

- Day 18 is population 321 with 324 total buildings. Zach's guarded Mac +20
  growth consumed Twin Oaks plan IDs 158-177: seeds 305-308 finished Acorn
  Court and seeds 309-324 opened Lantern Court. The insert-only houses sync
  added all 20 claimable rows. Full and six-district web assets report exact
  Day 18 / 321 / 324 state and coverage; address 178 is next. The reviewed
  delivery is five separate 12-second daytime portrait MP4s: all 20 homes
  appearing, a finished downtown-forward helicopter reveal, its frame-matched
  temporary Godzilla destruction version with breath/explosion/smoke/debris
  effects, a finished whole-city sky view, and a fast dive/sweep/pullback
  drone shot. `--cam cinematic`, `--cam dronezoom`, and `--godzilla` are
  replay/render tools; the destruction layer never changes saved town state,
  exported assets, or the Blend.

- Day 17 is population 301 with 304 total buildings. The single +29 growth
  consumed Twin Oaks plan IDs 129-157: seeds 276-285 continued Twin Oaks Drive
  at addresses 129-138, and seeds 286-304 opened Acorn Court at addresses
  139-157. All 29 new Supabase rows are claimable. The exact claim snapshot is
  unchanged at 31 claims across 30 accounts, including owners, timestamps, and
  customizations. Full and six-district streamed GLBs passed source, downtown,
  hash, state, and exact 304-building coverage checks. The reviewed delivery is
  three separate daytime portrait MP4s: finished entire-town overhead, finished
  moving downtown showcase, then the only animated clip--an entire-town replay
  where all 29 Day 17 homes appear. The standard overhead camera clipped the
  expanded city; `wholeoverhead` was widened and previewed so Twin Oaks and
  Kaleidoscope Crest remain in frame throughout. The generator refresh was
  backed up and synchronized into both authoritative Blend copies.

- The latest finish pass corrects five connected play-quality issues without
  changing canon. Third-person pitch reaches near-vertical views and ground no
  longer traps the follow camera. Loaded district detail uses 70m/112m
  load/unload hysteresis and returns to lightweight silhouettes when distant.
  Claimed-home and active-claim labels measure the real GLB roof, including
  tall founder and Kaleidoscope Crest homes. Ground-floor downtown storefront
  glass is flush with its facade. Recent persistent chat remains visible as a
  compact top-left walking feed, while the existing composer opens on demand.
  The rebuilt full GLB, base, affected original-town chunk, and manifest passed
  state/hash/coverage validation; focused camera, fallback, and remote-district
  browser flows passed. Day 16 / 272 / 275, addresses, all claims/owners,
  `world_state.json`, and Supabase are unchanged.

- Phone play inside the 3D town works in **both orientations** as of
  2026-08-06. The landscape-only rotate prompt was removed by owner
  instruction — most visitors come from Instagram, whose in-app browser can
  refuse to rotate, so it blocked play outright. **Do not reintroduce it.**
  Portrait has a dedicated control layout, and `#menuBtn` is the only way to
  reach the pause menu on touch (there is no Escape key). The "open in browser"
  escape for in-app browsers now lives inside that pause menu. The landscape
  passive chat feed is compact; tapping it expands the existing composer.

- Zach's downtown/terrain design package is integrated on Day 16 without a
  growth run. Downtown lots are thirteen metres wide and now have authored
  sidewalks, curbs, crossings, storefronts, public furniture, stronger
  massing, regional terrain, terrain-following suburban roads, and foundation
  pads. The full GLB and all six district chunks were regenerated from the
  authoritative iCloud Blend; the stream manifest includes canonical browser
  walk surfaces. Balanced browser graphics keep the actual Blender geometry
  while reserving browser-generated shader/edge/shadow extras for
  `?graphics=ultra`. Day 16 / 272 / 275, addresses 1-128, claims, ownership,
  Supabase, and `world_state.json` remain unchanged. See
  `DOWNTOWN_TERRAIN_HANDOFF.md` for provenance, merge decisions, and QA.

- Avatar System v1 uses only the 37 compact animated complete characters in
  the public Tailor, plus body color and height. The taller modular system is
  retired from the UI/runtime and legacy custom profiles normalize safely.
  Desktop right-drag locks the cursor and orbits, including Mac-safe secondary/Control-click drag. Wheel/trackpad zoom enters true eye-height, cursor-locked first-person mouse-look; mobile
  can drag the camera while moving and pinch zoom, A/D are correct, and the
  follow rig initializes in streamed and full-GLB paths. Space or the mobile
  JUMP button performs a small grounded hop that is mirrored in multiplayer. Bare `town.html`
  bookmarks return to the current map-preview homepage. Owner/guest persistence
  remains intact. Start with `AVATAR_SYSTEM.md` before changing it.

- Day 16 is population 272 with 275 total buildings. The +13 ordinary-home
  batch used planned addresses 116-128: seed 263 completed Overlook Circle and
  Willow Hills at address 116; seeds 264-275 opened Twin Oaks Drive at
  addresses 117-128. All 13 Supabase house rows are present and claimable;
  all 30 existing claims across 29 accounts remain unchanged. Export now has
  six district chunks, including `twin-oaks.glb`, plus the complete fallback.
  The reviewed delivery is two separate portrait MP4s: a completed-town
  overhead with no rise animation and a whole-town overhead replay where all
  13 new homes appear. Full/streamed validation passed, the live site reports
  Day 16 / 272 / 275, and all eight Playwright stories passed (the two longest
  local stories used a successful 180-second rerun).

- A Day 15 maintenance pass hardens the shared Blender workflow before any new
  growth: production launchers require clean/current Git, match the repo and
  iCloud Blend mirrors, and execute only the repository generator. A generator
  beside the iCloud Blend is ignored because iCloud may rename it. During the
  maintenance repair, iCloud immediately renamed the restored exact mirror to
  `neighborhood_blender 19.py`; it was preserved as history, and routine growth
  no longer depends on any plain-name iCloud generator.
  Direct GUI growth rejects a stale embedded generator. The current refresh
  tool backs up the Blend and embeds the repo source with its hash/revision.
  No population, building, geometry, state, or generated asset changes belong
  to this maintenance.

- The seed 73 Supabase metadata repair is live. The row now matches canonical
  state (`house`, `-3,-3`, Day 9, claimable) and is visible through the public
  API. Only house row 73 changed; the exact before/after snapshot retained all
  30 claims across 29 accounts with identical owners and customizations.

- The website now streams deterministic Blender districts while keeping the
  complete town as a safety fallback. `town_manifest.json` hashes a compressed
  shared base and five `town_chunks/*.glb` district assets; the browser loads
  2,800,996 bytes of detailed geometry at startup instead of the 7,916,952-byte
  monolith, uses lightweight silhouettes for distant homes, and awaits the
  destination district before map or owned-home teleports. Any manifest or
  initial-chunk failure automatically loads `town.glb`. Future growth must
  commit `world_state.json`, `town.glb`, `town_manifest.json`, and
  `town_chunks/` together (the Windows and Mac scripts now do this). The
  standalone validator checks every hash plus exact one-to-one coverage of all
  262 canonical buildings. Eight Playwright flows include streaming, remote
  teleport, full fallback, and iPhone touch/map recovery. This infrastructure
  did not alter day, population, buildings, addresses, claims, or Blender
  visuals.

- Day 15 is population 259 with 262 total buildings. It added 15 claimable
  homes: ten `storybookhouse` seeds 248-257 on Wanderlight Loop in the new
  Kaleidoscope Crest feature district, plus five ordinary seeds 258-262 at
  Overlook Circle plan IDs 111-115 in Willow Hills. The feature hill, garden,
  road, lamps, and flowers are permanent Blender/GLB content and appear only
  once feature homes exist. The access road now joins the old grid as matching
  asphalt, widens through a muted transition, then becomes pink; its dashes
  conform to the ramp. Website walking mirrors the raised hill/ramp surface
  for local and remote players and is guarded by
  `data-storybook-walkable="pass"`. All 15 database rows are claimable.
  The approved Day 15 delivery is three standalone videos, never one combined
  edit: `--cam wholeoverhead` for the full-town/all-15 rise;
  `--cam newgrowth --focus-type storybookhouse` for the close ten-home feature
  rise; and `--cam storybookstreet --focus-type finished` for the completed
  street-level tour with every home present from frame one. Keep the 10m near
  plane on all aerial cameras: it fixed the prior moving-shot road/pond
  flashing caused by depth-precision loss. All three were visually reviewed
  and emailed as separate MP4 attachments to Cade and Zach.
- Kaleidoscope Crest received a post-delivery finish pass without changing any
  building record or claim. `storybookhouse` collisions are now derived only
  from `NB_story_wall*` material vertices at player height, excluding the
  merged lawn/path/fence/flower/mailbox geometry. The access-ramp dashes are
  shallow surface meshes sampled from both ends of the 3D road centerline.
  All ten crooked lamps are single continuous shared-ring tubes with attached
  globes and banner brackets. A polished Cat in the Hat public-art statue
  replaces the center tree: continuous curved limbs/tail/fingers, embedded
  face and bow layers, one six-band shared-ring hat, an interlocking pedestal,
  and an accurate 2.18m base collider. It remains part of the conditional
  Kaleidoscope street asset. Preserve the Playwright requirements for
  `data-storybook-hitboxes="pass"` and `data-kaleidoscope-statue="pass"`.
- Website backdrop mountains now move outward independently when town growth
  approaches them. The old fixed 282-310m ring intersected Day 14 Overlook
  Circle Houses #230-247; `addTownAtmosphere()` now gives every current building
  at least 18m clearance from each hill's conservative footprint and exposes a
  Playwright-checked runtime audit. This is web scenery only—do not move the
  houses or edit Blender terrain to solve it.
- The public website now has stable roleplay-ready place/activity routes.
  `Today in Followville` is computed from the latest day in
  `world_state.json`; `/today` opens that day's homes in the live map with a
  current district/street summary and visual highlight. Every home can be
  shared at `/house/:id` from its selection card. These routes reuse building
  seeds, world data, and `public_claims`; future interiors/jobs/events should
  attach to those identities instead of creating parallel coordinates or a
  second place table. Vercel rewrites both clean routes to `town.html`, and its
  root `<base>` is required for assets under `/house/:id`. Browser regressions
  live in `tests/` and run in CI; use `pnpm test:e2e` after navigation changes.
- The homepage is an organized destination dashboard: desktop places compact
  Walk/Claim cards beside a large isometric town preview, while mobile keeps
  all three destinations above the fold. That preview redraws from
  `world_state.json` whenever the existing live stats refresh; do not replace
  it with a stale screenshot or separate map file. Its `Explore the map` card
  opens `town.html#map`. `vercel.json` redirects bare `/` to `/index.html`,
  deliberately sends `no-store` on both routes, and `index.html` reloads when
  restored from browser back/forward memory. Preserve all three safeguards so
  deployments do not intermittently show the prior homepage. Homepage styling
  should stay restrained and editorial: a sharp paper map, ruled text links,
  unboxed stats, and almost no glass blur or pill UI. Avoid returning to generic
  rounded icon cards. The same live,
  lightweight isometric 3D map opens from the town start screen, the in-game
  `town map` button, or `M`; it supports rotate, pan, zoom, and fit-to-town.
  The homepage Walk link is `town.html#walk`; this explicitly bypasses the
  legacy in-town start screen and starts in the rendered neighborhood. Desktop
  canvas clicks capture mouse-look, and mobile retains its touch controls.
  Desktop Escape while walking opens a real pause overlay without changing the
  camera position. `resume` restores that exact location, while
  `leave town` explicitly returns to `index.html`. Escape inside map/chat still
  closes that overlay rather than leaving town. Signed-in homeowners have
  visible `manage my home(s) / unclaim` entry points on the town/start screen
  and pause menu; each selected home still uses the existing confirmation step.
  When opened through the homepage's `town.html#map` deep-link, closing it,
  pressing Escape, or clicking its backdrop returns to the redesigned homepage
  instead of exposing the older in-town start screen. Visiting a selected map
  result still enters the town and disables that return-home behavior.
  Its normal sidebar is an eight-row street directory (seven named streets plus
  `Original town`), not a 259-house list. Street rows focus their part of the
  existing 3D scene; clicking a rendered 3D house teleports immediately. Search
  accepts `@owner`, house ID, and street/district, ranks exact and partial owner
  matches well, and keeps individual Visit/Share results. Newest and claimed
  filters group by street; landmarks and signed-in homes remain individual.
  Instanced map geometry must remain derived from the current
  `world_state.json`; planned road lines use only built houses, so future empty
  roads remain hidden, while the already-built Founder Park rings and connector
  are reconstructed from their existing homes. `public_claims` supplies live
  owner names. Do not add a separate map JSON/database table, manual
  coordinates, or a second copy of the full town GLB.
- Day 14 is complete: population/followers 244, 247 buildings, and 18 new
  ordinary homes at plan IDs 93-110. IDs 93-95 completed Foxglove Court;
  IDs 96-110 began Overlook Circle. Its road is revealed only as far as those
  homes and its future turnaround remains hidden. The 18 new claimable rows
  were inserted into Supabase.
- The landing page and in-town loading/start screen use
  `assets/town-loop.mp4`, a 12-second Day 14 sidewalk view of a current
  Overlook Circle house with two staggered passing cars. Its poster is
  `assets/town-loop-poster.jpg`. The source comes from render-only camera mode
  `--cam housefront`; it does not mutate the blend, GLB, state, or claims.
  Reduced-motion/data-saver visitors receive the poster, and the intro video
  pauses during walking and on hidden tabs.
- `--cam newgrowthoverhead` is the preferred tight top-down daily rise shot.
  `--cam football` builds the temporary England v Argentina fan vignette used
  on Day 14. That set must remain render-only: do not export or save it into the
  permanent blend/GLB. The final saved `neighborhood.blend` was rebuilt without
  the set, and the validated `town.glb` contains no fan-scene object names.
- When `grow_windows.ps1` is run from the authoritative repo, it now skips the
  old iCloud-to-`wip` auto-share hook. The hook switched the working clone to
  stale `wip` after the Day 14 `main` push; the state/model push itself was
  unaffected. Keep repo-based daily work on `main`.
- Homeowner yard decorations are temporarily disabled. `town.html` does not
  render flowers/trees/benches/flags and does not show their chooser. Keep
  `YARD_DECORATIONS_ENABLED = false` until Cade approves a redesign. Existing
  stored `customization.yard` values remain normalized and preserved so this
  pause does not destroy homeowner data; exterior/roof/door colors still work.
- Founder house #29's structure is now authored 1.3m farther back, with its
  driveway and walk extended to remain connected to the curb. Yard clearance
  reads the selected structural material triangles inside the merged GLB mesh,
  so curb-anchored driveway/mailbox parts no longer make the house look deeper
  than it is. The saved bench is a full-depth two-person bench fitted on the
  open side lawn between entry path and mailbox; custom trees keep equal X/Z
  scale instead of becoming flat. Blender and GLB changed; world state, Day 13,
  population 226, 229 buildings, seeds, and claims did not.
- Admin accounts now have a database-enforced two-home allowance; normal
  accounts still have one. The live handles are `cade.toohey` and
  `stellar.kehler`. `town.html` lists both homes and targets visit, customize,
  and unclaim actions by house ID. Existing claims were not reassigned.
- Web yard decorations now occupy the real front-yard strip: `town.html` reads
  the GLB root's actual facing, measures the complete exported structural
  silhouette (including roofs, doors, garages, glass, and trim) and curb setback,
  then uses a side-lawn planting zone rather than the doorway centerline.
  Standard homes use their door material and founder homes use their door meshes
  to choose the side opposite the entrance; corner lots still prioritize the
  side away from the second road.
  Benches face the street, flags sit curbward to clear porch covers, and tight
  lots compress only front-to-back rather than shrinking the whole decoration.
- Web collisions are shape-aware. All 226 homes and 16 cars have oriented box
  footprints, the school has three independent wing boxes, and each tree blocks
  only at its measured trunk (77 existing GLB trunks plus homeowner yard trees),
  not at the canopy. The collision system itself remains browser-side.
- Day 13 is complete: population/followers 226, 229 buildings, with 40 new
  ordinary houses at suburban plan IDs 53-92. The batch finished Creekside
  Bend (2 Pebble Court homes) and started Willow Hills (20 Willow Rise and 18
  Foxglove Court homes). Supabase has all 229 rows and the 40 Day 13 IDs match.
- Homeowner Mode is live in the code/database as of 2026-07-15: every claimed
  owner can preview and save an exterior, roof/accent, and door color plus one
  yard piece. Saved palette IDs use the existing `claims.customization` field
  and flow to all open visitors over the current claim Realtime subscription.
  The owner-only RPC validates every option and cannot target another claim.
  All 27 pre-existing claims remain attached and unchanged; Blender/state/GLB
  were not modified.
- `--cam newgrowth` frames the newest day's largest district for rise videos;
  `--cam newstreet` follows the newest day's busiest curved street. The street
  path keys every road sample, uses local tangent aiming, and avoids roof/house
  clipping on bends.
- Procedural nature now clears from active suburban road ribbons, cul-de-sac
  bulbs, and occupied planned lots, preventing trees or rocks from remaining
  in newly developed roads. Future unrevealed areas keep their terrain/nature.
- Website multiplayer is implemented: Supabase Realtime Presence tracks online
  visitors, Broadcast carries movement, and the town renders lightweight remote
  markers/name labels. Signed-in users can send persistent chat; guests can read
  it. Admins have online-player, session-duration, and chat-history logs.
- Desktop chat opens with `T`, `/`, or Enter while keeping the town visible;
  Enter sends and restores pointer-lock walking. Remote markers use a 3D smiley
  to show facing direction. Admin data is split into two tabs with bounded,
  scrollable sections rather than one long page.
- Multiplayer database writes go only through authenticated, identity-derived
  RPCs. RLS and column grants expose only safe public identity/chat fields.
  Guests cannot create sessions, identities, or messages. Blender state and
  existing claims are not modified by multiplayer.
- Day 12 finished at population/followers 186 and 189 buildings.
- All 176 ordinary and park-ring homes now use a deterministic optimized
  library of 15 suburban designs and six coordinated palettes. Existing seeds,
  positions, claims, day, and population are unchanged. Each lot includes a
  clear driveway, walk, mailbox, porch/stoop, garage, and safe landscaping.
- Planned-house compact scales are preserved by `nb_rest_scale`; the oriented
  collision audit passes all current homes and all 366 reserved addresses.
- The `side_garage_two` partial-body bug is fixed: all three upstairs windows
  now sit on a complete full-width two-story facade and roof.
- Day 12 added 17 ordinary Creekside Bend houses at plan IDs 36-52 and one
  non-population, non-claimable Followville Elementary School.
- The hidden 366-house suburban reserve remains deterministic and staged;
  roads appear only as their associated houses appear.
- The school has classroom wings, glass entrance, bus loop/bus, landscaping,
  clock, flag court, and a finished fenced playground.
- Final playground correction: connected A-frame swing supports, chains and
  seats; slide chute, rails, and ground exit share exact endpoints.
- Final car correction: four upright tires per car at the front/rear axles,
  with opposite inward rotations on the two sides so every tire protrudes
  outside the body. Both car sides were rendered in isolation and checked.
- `neighborhood.blend` and `town.glb` were regenerated and validated.
- Supabase contains all 189 world records; the school is non-claimable.
- The live Vercel model was hash-checked against the local corrected GLB.

## Latest delivery

Day 15's approved delivery is three separate reviewed MP4s: whole-town/all-15
rise, Kaleidoscope ten-home rise, and finished storybook-street tour. Do not
replace them with the older combined Day 14 reel pattern. The newest production
code delivery is district streaming plus the avatar camera guard and the CI
timeout follow-up; it did not change town content.

## Git checkpoints

- `7446a16` -- production district streaming and streamed/full validation.
- `40421eb` -- nearby multiplayer avatars no longer clip the camera.
- `fbdef0e` -- CI allowance for the eight streamed Three.js regressions.

Read newer commits if present; `origin/main` remains authoritative.
