# Web viewer — change log

Running log of every change made while building the Followville web viewer, in order.
Kept here (rather than just in chat) so it survives across sessions.

## 1. Built the first version of index.html (JS-procedural)
- Created `index.html`: a Three.js first-person walker, `PointerLockControls`,
  WASD/arrow movement, click-to-lock start screen, HUD (day/pop/building count).
- Ported neighborhood_blender.py's shape logic into JS by hand: `addBox`/`addCone`/
  `addPrismRoof` helpers, all 10 founder house builders, a generic `house` builder,
  road/grid layout math (`lotToWorld`, `blockExtent`), collision via simple
  circle push-out per building.
- Loads `world_state.json` directly via `fetch()` to know what to build and where.

## 2. Fixed a systemic rotation-axis bug
- Root cause: Blender is Z-up, Three.js is Y-up. Every hand-ported `.rotation_euler`
  value needed axis+sign conversion (Blender Z→Three Y, Blender X→Three -X,
  Blender Y→Three -Z), and the first pass got this wrong everywhere at once.
- Fixed in: mushroom/flower window rotation, casino sign+dice rotation, cat
  ear+nose rotation, Eiffel Tower leg rotation, beach house palm+surfboard
  rotation, and the building `face` (n/s/e/w) placement angles.

## 3. Detail passes (things skipped in the first draft, not bugs)
- Casino: added dice pips.
- Mushroom house: rounder cap (more cone sides).
- Cat house: added whiskers.
- Beach house: added porch rails + side window.
- Roads: added the missing yellow lane-dash markings.
- Added generic streetlight/car/bush/rock builders + scattered them
  procedurally around the grid (seeded per-tile so they stay put as the town
  grows, matching neighborhood_blender.py's `scatter_nature`/intersection logic).

## 4. Lighting + material pass
- Switched materials from `MeshLambertMaterial` to `MeshStandardMaterial`.
- Added real shadows: `renderer.shadowMap`, sun `castShadow`, shadow-camera
  frustum sized to the current town extent (recomputed every load, so it
  stays sharp as the town grows).
- Added a fill light, tone mapping, adjusted hemisphere/sun balance.

## 5. Switched to real Blender geometry (the big one)
- Added `export_web.py`: a headless Blender script that takes whatever
  `neighborhood_blender.py` just built (the "WORLD" collection), realizes
  every collection-instance into actual mesh data (`duplicates_make_real`),
  and exports it to `town.glb` (GLB, Y-up, no animation/camera/lights).
- Added a second Blender invocation to the end of `grow.sh`, so `town.glb`
  regenerates automatically after every `./grow.sh` run — no manual step.
- Rewrote `index.html`'s loading logic: it now tries `GLTFLoader.loadAsync
  ("town.glb")` first (the literal Blender geometry, no hand-ported JS
  shapes, no drift) and only falls back to the old JS-procedural builders if
  `town.glb` doesn't exist yet.
- Collision colliders and shadow-frustum sizing are now computed automatically
  from the loaded GLB's bounding boxes — no per-house-type radius to maintain.

## 6. Bug: spawned outside the town in an open field
- Cause: the spawn point was computed from the *entire* GLB's bounding box,
  which also contains a giant 4000×4000 ground plane Blender always adds
  (`build_stage`'s "ground" object) — that plane's bounds dominated the
  calculation and put the spawn point way outside the actual town.
- Fix: exclude any object with bounding radius > 200 from the framing/spawn
  calculation.

## 7. Bug: still spawned just outside town, blocked by scattered nature
- Cause: even after excluding the ground plane, the spawn point (derived from
  the GLB's bounding box) landed in the ring of scattered trees/bushes/rocks
  that sits just outside the actual building blocks, not on a road.
- Fix: stopped deriving spawn position from the GLB entirely. Now computed
  from the same grid math the town is laid out from (`blockExtent`/`PITCH`/
  `ROAD`, applied to `world_state.json`'s building list) — guarantees the
  spawn point is always exactly on a real road regardless of what the GLB's
  bounding box looks like.

## 8. Bug: invisible wall blocking movement inside the town
- Cause: found by directly parsing `town.glb`'s binary structure (no Blender
  needed — GLB is just a JSON chunk + binary buffers). The `roadH` (horizontal
  road) objects are thin (6 units) but very long (~78+ units); the collider
  code used `radius = max(width, length) / 2`, which treated each long thin
  road strip as a giant ~39-radius circular obstacle — nearly blocking the
  whole town.
- Fix: only give an object a collider if it's actually tall (`size.y > 1.0`).
  Roads/lane-dashes/the ground plane are all under 1 unit tall; every real
  building/tree/car stands well above that. This is a general fix, not a
  per-object special case.

## 9. Unresolved: `town.glb` / the .blend itself contains far more houses than world_state.json
- Directly parsed `town.glb`'s binary structure: found 20 objects named
  `house_d4`-family, even though `world_state.json` lists only 3 buildings of
  type `house` dated day 4 (15 buildings total, matching "Day 4, pop 14").
- Ruled out (via headless diagnostics, see `diag_investigate.py`):
  - Not stray/leftover objects: a direct dump of every `house_d4*` object in
    the saved `.blend`'s `WORLD` collection shows all 20 are legitimate
    `EMPTY` objects with `instance_type=COLLECTION`, each referencing a real
    `AST_house_N` asset collection, each at a distinct, sensible, grid-aligned
    `location` (multiples of 10, matching `LOT=10`). Not ghosts/duplicates at
    the same spot — genuinely different, valid placements.
  - Not orphaned data: 0 objects with zero collection links in the whole file.
  - Not a stray second "WORLD" collection: only one collection named
    `WORLD`/`WORLD.*` exists.
  - Not caused by `export_web.py`: confirmed the bloat is already present in
    the *saved* `.blend` file itself, before the export script ever runs.
  - Not explained by the external `neighborhood_blender.py`'s logic: hand-
    traced `main()` — with `--gained 0` every addition count is 0, so the
    "add new buildings" loop appends nothing; the placement loop
    (`for b in state["buildings"]: place_instance(...)`) only iterates the
    exact list loaded from `world_state.json`, which independently verified
    (via `diag_investigate.py`, a standalone script, no shared state with
    `neighborhood_blender.py`) has exactly 15 buildings / 3 house-day-4.
  - Attempted fix (hardened `clear_world()` — sweeps stray WORLD-named
    collections, purges zero-user objects, runs a full Blender orphan-purge)
    made **no difference at all**: re-running `./grow.sh +0` produced a
    byte-for-byte identical `town.glb` (same 20 `house_d4` objects). This
    means the bloat isn't a cleanup/leftover-data problem.
- **Leading hypothesis, unconfirmed:** `neighborhood.blend` prints
  `scripts disabled for ".../neighborhood.blend", skipping 'neighborhood_blender.py'`
  on every load — meaning the `.blend` file has its **own embedded copy** of
  `neighborhood_blender.py` saved inside it as a Text datablock (consistent
  with the GUI "N key → City tab" workflow described in this project's
  CLAUDE.md). That embedded copy is separate from the external
  `neighborhood_blender.py` file on disk that `grow.sh` explicitly runs via
  `--python`, and may still hold old hardcoded CONFIG values (e.g. an old
  `NEW_HOUSES`/`FOLLOWERS_GAINED` default) from earlier testing. Something —
  possibly a registered load-time handler/operator tied to that embedded
  script/panel — may be running a second, uncontrolled rebuild pass using its
  own stale defaults, on top of (or instead of) the correct external-script
  rebuild.
- **UPDATE 2026-07-07 (via Windows Claude, Cowork computer-use):** verified this
  directly — Blender 5.1 turns out to be installed on Cade's Windows PC, so this
  session could actually open the GUI and click around (screenshots + mouse/
  keyboard control), unlike the Mac sessions which only ever drove Blender
  headlessly through `grow.sh`. Opened `neighborhood.blend`, clicked "Ignore" on
  the script-execution prompt (so nothing could auto-run), went to the
  Scripting tab, and read the embedded `neighborhood_blender.py` Text datablock
  end to end.
  - **Hypothesis REFUTED:** the embedded copy already has the same
    `if bpy.app.background: main() else: _register_ui()` guard as the external
    file (confirmed at its own final ~6 lines) — in GUI mode it only registers
    the City panel and does NOT call `main()`. Opening/allowing the file does
    not silently rebuild the world or add houses. CONFIG defaults at the top
    (`FOLLOWERS_GAINED = 5`, `NEW_HOUSES = 5`, etc.) also match the external
    file. So an auto-run-on-open pass using stale embedded defaults is ruled
    out as the cause of the 20-vs-3 `house_d4` mismatch.
  - Side note: the embedded Text datablock's on-disk path (shown in Blender's
    status bar) is still `/Users/cadetoohey/Documents/neighborhood/
    neighborhood_blender.py` — the project's very first location, before the
    move to iCloud Drive. Harmless (Blender just remembers where a Text
    datablock was last loaded from), but confirms the datablock hasn't been
    reloaded/refreshed from an external path since that early move.
  - The 20-vs-3 `house_d4` bug itself is **still unexplained** — this only
    closes off one candidate cause. `diag_investigate.py` remains the right
    tool to re-check current state.
  - Caution for future GUI sessions: even just clicking around (no typing) can
    trigger unexpected Blender UI state — a stray keypress here briefly
    flagged the file as having unsaved changes with no scene edit visible.
    Always choose "Don't Save" / "Ignore" rather than risk saving an
    unintended change to the shared `.blend`.
- `diag_investigate.py` (in this folder) is a safe, read-only diagnostic
  script (does not modify/save the `.blend`) that dumps: world_state.json
  building counts, every `house_d4*` object's position/instance data, all
  WORLD-like collections in the file, and orphan-object counts. Re-run it
  anytime for a fresh read of the actual state.

## 10. Split into a real landing page + the walkable town
- Renamed the old single-page experience to `town.html` (same content, added
  a small "← Followville" link back to the homepage).
- Wrote a new `index.html`: a proper home page — logo (circular, expects
  `logo.png` next to it, falls back to an emoji if missing), title, tagline,
  a "Day / Population" stat pair, and a "Walk the town →" button linking to
  `town.html`.
- Live stats: polls `world_state.json` every 45s and updates the displayed
  numbers if they changed (small pulse animation on change). Deliberately
  does **no calendar/date math at all** — day and population only change
  when `grow.sh` actually regrows the town, never automatically with the
  passage of real time, so simply re-reading the same JSON file is the
  entire "live update" mechanism.
- Population is read from `state.pop` directly (already decoupled from
  building count in `world_state.json` — this was already true before this
  session, not a new fix), so a future apartment/milestone building that
  holds many followers in one building won't throw off the displayed count.
- **Still needed:** the actual logo image file (`logo.png`) — I can see the
  attached profile picture in chat but have no way to save its raw bytes to
  disk from here; needs to be added to the project folder directly.
- **Still needed:** a public hosting decision (GitHub Pages vs. Netlify
  Drop vs. other) before this can actually go in the Instagram bio — this
  folder is only running on a local server (`python3 -m http.server`) so far.

## 11. Bug: deployed houses appeared "pancaked" to the ground
- Cause: `export_web.py` exported whatever animation frame the Blender scene
  happened to be on. `neighborhood_blender.py`'s daily rise animation scales
  new buildings from flat (`scale.z ≈ 0.001`) up to full height over the
  clip — if the scene wasn't sitting on the final frame when the export ran,
  `export_apply=True` baked that flattened mid-rise pose straight into the GLB.
- Fix: `export_web_glb()` now calls `scene.frame_set(scene.frame_end)` first
  thing (frame_end is already set correctly by `setup_render()` in the saved
  `.blend`), plus forces every WORLD object's `scale` back to `(1,1,1)` as a
  belt-and-braces guard, before realizing instances / exporting.
- Landing page (`index.html`) text also simplified: tagline is now just
  "Walk it yourself, right in your browser." and the founders-note paragraph
  about population vs. house count was removed entirely.
- **Still needed:** re-run `./grow.sh` (or otherwise regenerate `town.glb`)
  with this fix in place, then push so Vercel redeploys, then confirm no
  more pancaked houses.

## 12. Mobile support — touch controls for town.html, responsive landing page
- `town.html` had no touch input at all before this: movement was keyboard-only
  and looking around required `PointerLockControls` (a real mouse pointer lock,
  which touchscreens don't support), so the walkable town was effectively
  desktop-only.
- Added a touch-device code path (detected via `"ontouchstart" in window ||
  navigator.maxTouchPoints > 0`) that skips pointer-lock entirely:
  - On-screen virtual joystick (bottom-left) for movement — analog, drives the
    same `move.x`/`move.z` values keyboard WASD now also writes into (movement
    was refactored from 4 booleans to 2 analog axes so both input methods feed
    the same code path).
  - Drag-to-look anywhere else on screen, manually driving `camera.rotation`
    (yaw/pitch, clamped so you can't flip upside-down) since `PointerLockControls`
    can't supply this on touch.
  - A "RUN" toggle button (bottom-right) replaces the desktop shift-key sprint.
  - Start screen swaps its copy/button for touch ("tap to enter", updated hint
    text) and skips `controls.lock()`, going straight into a shared
    `gameRunning` flag that both input paths check.
- Added `touch-action:none` / `overscroll-behavior:none` and a locked viewport
  (`user-scalable=no`) so touch drags move the camera instead of scrolling or
  pinch-zooming the page.
- `index.html` (landing page): added a `viewport-fit=cover` viewport tag, a
  short-viewport media query so the logo/stats don't get pushed off-screen on
  small phone screens in landscape or with a keyboard/browser-chrome eating
  vertical space, and updated the hint line to mention touch controls.
- Verified both files' inline `<script>` blocks still parse cleanly
  (`node --check`) after these changes.

## 13. Suburban library replacement and compact planned lots

- Replaced the normal/ring-house GLB visuals with 15 suburban designs across
  six deterministic color palettes while keeping `building.seed` unchanged,
  so the website's Supabase claim mapping remains stable.
- Batches every reusable house variant into one material-aware mesh. The final
  `town.glb` is about 6.0 MB and passes `check_town_glb.py`.
- `export_web.py` now preserves each instance's `nb_rest_scale`; this keeps
  compact lots clear at tight curves and cul-de-sacs instead of resetting them
  to full size during GLB export.
- Raised `house` and `ringhouse` name-tag heights to 9.2 so labels remain
  above the new two-story roofs.
- Corrected `side_garage_two`, whose full-width windows/foundation had been
  paired with an offset partial-width wall and roof. Its three upper windows
  now sit on a complete two-story facade in Blender and the exported GLB.

## 14. Live multiplayer, town chat, and admin activity logs

- Added Supabase Realtime Presence for the online roster and Broadcast for
  low-latency visitor movement. The town renders minimal remote player markers
  with name labels and interpolates their movement between updates.
- Added town chat: everyone can read recent messages; signed-in followers can
  send. Messages persist in Postgres and briefly appear as speech bubbles over
  the sender's marker.
- Added authenticated session tracking and a safe active-identity registry.
  Identity comes from `auth.uid()` inside database RPCs, not client-supplied
  handles. RLS and column-level grants keep account UUIDs private and block
  anonymous/direct writes.
- Added admin panels for currently online signed-in players, join/end/duration
  history, and persistent chat history through the guarded
  `admin_list_multiplayer()` RPC.
- Multiplayer is website/backend-only. It does not alter Blender geometry,
  `world_state.json`, `town.glb`, population, or existing house claims.

## 15. Multiplayer chat controls, directional faces, and admin layout

- Desktop `T`, `/`, and Enter open town chat without showing the start screen.
  Movement input clears while typing; Enter sends and restores pointer lock in
  the same user action, so walking resumes without another click.
- Added a light circular face panel, large dark eyes, and a thick smile to the
  forward side of every placeholder player marker, making each remote player's
  facing direction obvious at normal gameplay distance.
- Split the admin page into Accounts/Claims and Multiplayer/Chat tabs. Related
  datasets sit in responsive card grids with bounded scrolling instead of one
  continuously growing page.

## 16. Day 13 staged growth and corrected suburban scenery

- Grew the canonical state from 186 to 226 followers with planned suburban
  addresses 53-92, then rebuilt `town.glb` from the corrected completed scene.
- Added `newgrowth` framing for the largest district in the latest batch and a
  `newstreet` camera that follows the latest day's busiest revealed street.
  The street camera keys every road sample and looks along the local tangent,
  preventing interpolation chords and wide-angle roof clipping on tight bends.
- Updated procedural nature scattering so trees, bushes, and rocks clear from
  active suburban roads, cul-de-sac bulbs, and occupied planned-house lots as
  each section develops. Unrevealed future areas remain untouched.
- `check_town_glb.py` confirms the final model is not squashed and still matches
  `world_state.json` at Day 13 / population 226 / 229 buildings.

## 17. Homeowner Mode: realtime claimed-house customization

- Added a responsive claimed-owner picker for exterior, roof/accent, and door
  colors plus one yard piece. Owners can preview before saving and reset to the
  original house look.
- Added the strictly validated `update_my_customization(jsonb)` Supabase RPC.
  It derives the target from `auth.uid()`, accepts only approved palette IDs,
  and leaves direct claims-table writes blocked. Existing claims are untouched.
- `public_claims.customization` now drives the current claim Realtime stream,
  so every open town applies saved changes without a refresh.
- Recolors clone materials per individual home before editing them; shared GLB
  materials and the optimized 15-house library remain batched for uncustomized
  homes. Founder landmarks receive matching wall/roof-accent/door material roles.
- Yard choices are tiny Three.js primitives (flowers, tree, bench, or flag),
  avoiding extra downloads and keeping the static site smooth.
- Verified the module parses, the local town loads without browser errors, all
  226 home visuals map, the picker works at desktop/mobile sizes, and anonymous
  RPC execution is rejected. Blender, `world_state.json`, and `town.glb` did not
  change.

## 18. Two-home admins and road-safe yard placement

- Replaced the old unique-user claim constraint with a concurrency-safe owner
  limit: normal accounts remain capped at one house and trusted admins may own
  two. Both `claim_house()` and a defensive claims trigger lock/count by owner.
- `my_status()` now returns the complete ordered claims list plus `claim_limit`,
  while retaining the first `claim` field for older clients.
- Added house-specific `unclaim_house(bigint)` and
  `update_my_customization(bigint,jsonb)` RPCs. Both require the requested house
  to belong to `auth.uid()`, so one admin home cannot modify the other by
  accident and a two-home unclaim removes only the selected row.
- The account modal shows 1/2 or 2/2 for admins, offers `claim second home`, and
  gives each home independent go/customize/unclaim actions. Normal follower UX
  is unchanged.
- Yard placement now averages every road-facing lot direction and offsets the
  decoration inward. Single-road lots retain a deterministic sideways offset;
  corner lots move diagonally inward. This fixes landmark pieces such as the
  Burj yard decoration appearing on the street.
- Applied the live `allow_admins_two_homes` migration, aligned the targeted
  customization validator with the canonical palette, and rollback-tested second
  admin claims, rejected third/normal-second claims, targeted customization and
  unclaim, trigger enforcement, and RPC privileges. All 27 existing claims
  remained unchanged. Browser verification passed the 1/2 and 2/2 panels, a
  second-home customization selection, and the rendered Burj yard placement.
  Blender, population, world state, and GLB were not changed.

## 19. Front-yard fitting and shape-accurate collisions

- Replaced the fixed backyard/inward yard-piece offset with geometry-aware
  front-yard fitting. The viewer reads each exported home's actual facing,
  projects its structural façade toward the road, measures the curb setback,
  and centers the piece in the remaining strip.
- Decorations scale down only when a founder lot is too tight. Corner lots drop
  the sideways planting offset so a piece cannot enter their second road.
- Replaced the former one-circle-per-top-level-object collision pass with
  oriented boxes for all 226 house bodies and all 16 complete car bodies. The
  school uses three separate wing boxes so its courtyard stays walkable.
- Tree collisions now come only from the 77 exported trunk meshes; foliage,
  bushes, yards, and roads are walkable. Customized yard trees dynamically add
  and remove their own scaled trunk collider.
- Verified all four decoration choices against every mapped home (904 cases):
  zero façade overlaps and zero curb crossings. Runtime mapping reported 245
  box footprints and 77 base trunk cylinders, with no page errors. Module parse,
  GLB sanity, and the 366-address suburban collision audit all passed. This was
  web-only; Blender, `world_state.json`, and `town.glb` did not change.

## 20. Door-safe, visually complete yard pieces

- Moved pieces off the front-door centerline into a side-lawn planting zone.
  Normal suburban styles choose the side opposite their garage; founder homes
  inspect their exported door meshes; corner lots override either choice when
  needed to point away from their second road.
- Rotated benches so the seat faces the street instead of the house. Flags move
  toward the curb side of the safe strip, keeping their poles out from under
  entry canopies and porch covers.
- Tight yards now scale only the piece's front-to-back depth. Width and height
  remain intact, preventing miniature benches and flags or tiny collapsed trees.
- Rendered and reviewed bench, flag, and tree placements at Cade's claimed
  castle. Re-ran the 904-case placement audit: every decoration retained positive
  façade and curb clearance, including all corner/founder homes. Module parse,
  GLB sanity, and the full 366-address audit still pass. Web-only; no state,
  Blender, GLB, population, building, or claim changes.

## 21. House #29 full-silhouette placement fix

- Reproduced the report at house #29 (`double_garage`, seed/house ID 29). Its
  exported door/porch projects about 1.6m farther toward the curb than the
  nominal body used for player collision, so mathematically road-safe pieces
  were still visibly inside the awning and entrance.
- Added a dedicated decoration obstacle footprint from the full-height exported
  wall, roof, door, garage, glass, trim, and shutter materials. Player hitboxes
  remain ground-level and are intentionally independent.
- Optimized suburban door materials now participate in the side choice just as
  founder door meshes do. An off-center entrance takes priority over the garage
  heuristic; corner-road safety remains the final override.
- Rendered #29's saved tree plus bench and flag previews from its street side.
  All clear the actual porch, doorway, and curb. Re-audited all four choices on
  all 226 homes against the new full structural footprint: 904/904 have positive
  house and curb clearance. Module parse, GLB check, and 366-address audit pass.
  Web-only; no Blender, GLB, world-state, population, building, or claim changes.

## 22. House #29 structural lot and multi-material clearance fix

- Replaced the failed depth-compression workaround with a real lot correction:
  founder house/seed 29's structure is authored 1.3m farther from the curb,
  while its driveway and front walk extend back to the relocated facade and
  remain connected to the street.
- Found the underlying web-measurement bug in optimized houses. Each house is
  one merged mesh with multiple material groups, so accepting a mesh because it
  contained a wall material also accepted its driveway and mailbox. Clearance
  now iterates only vertices from structural wall/roof/door/garage/glass/trim/
  shutter material groups. Mailbox flags use their own non-structural material.
- House #29 uses its open side lawn beyond the entrance. Its saved bench is a
  proportional 1.5m two-person bench at full depth between the entry path and
  mailbox, not across the garage/driveway. Custom trees use identical X/Z scale,
  so tight front yards produce upright round evergreens instead of flat slices.
- Rebuilt and saved `neighborhood.blend`, exported `town.glb`, and reviewed
  street-level bench and tree shots. Runtime mapped all 226 homes and reported
  245 rectangular colliders plus 77 trunk cylinders with no page errors. All
  904 home/decoration combinations cleared house, curb, and side-lot limits;
  GLB integrity and current/full-366 suburban collision audits passed. Day 13,
  population 226, 229 buildings, world state, seeds, and claims are unchanged.

## 23. Yard decorations temporarily disabled

- Added the `YARD_DECORATIONS_ENABLED` feature gate and set it to false at
  Cade's request. Saved flowers, trees, benches, and flags no longer render,
  including previously saved homeowner pieces.
- Removed the yard-piece section from Homeowner Mode and updated its copy to
  describe color customization only. Exterior, roof/accent, and door previews
  and saves are unchanged.
- Kept the normalized `yard` field and approved values in the data model/RPC.
  Existing Supabase choices are preserved for a future redesign rather than
  destructively clearing claim data. No Blender, GLB, world-state, population,
  building, seed, or claim changes.

## 24. Street-level video landing and start experience

- Replaced the plain landing background with a compact 12-second portrait loop
  of a current Day 14 Overlook Circle house viewed from the sidewalk. Two cars
  cross the foreground at separate times; the camera makes only a very slow
  lateral move, keeping the screen calm and readable.
- Reused the loop on the in-town loading/start screen and moved its glass start
  card into the open sky so the house and road remain visible. The video pauses
  as soon as walking begins and whenever its page is hidden.
- Added a compressed poster fallback for initial loading, blocked autoplay,
  reduced-motion preferences, and data-saver connections. Both pages remain
  usable if video playback is unavailable.
- Added reusable Blender camera mode `--cam housefront`. Its camera and two
  traffic cars exist only for the render; `world_state.json`, the permanent
  blend, GLB, population, buildings, seeds, and claims remain unchanged.

## 25. Self-updating town map and house finder

- Added `Explore the map` to the homepage and matching access from the town
  start screen, the in-town map control, and desktop `M` key.
- Built a responsive isometric 3D map with drag-to-rotate, pan, wheel/pinch
  zoom, fit-to-town, lit terrain zones, raised colored homes, established grid
  and Founder Park roads, currently revealed planned-road centerlines,
  landmarks, selection rings, and a live player marker. Houses are instanced
  in a small dedicated scene instead of duplicating the full town GLB; the
  original flat canvas renderer remains as a WebGL fallback.
- Added search by exact house number, claimed Instagram handle, street,
  district, and building type. Quick filters cover the newest daily homes,
  school, claimed homes, and the signed-in visitor's owned home(s).
- Selecting a result centers and highlights it; Visit moves the player to the
  correct frontage and enters walking mode. Direct `town.html#map` links open
  the map after the real GLB/state load completes.
- The map rebuilds from `world_state.json` and the existing `public_claims`
  feed. It has no separate source of truth: future houses, landmarks, and road
  extensions appear through the normal growth pipeline, while unbuilt future
  roads remain absent. Current QA mapped 244 homes, three landmarks, 18 Day 14
  homes, and 15 built Overlook Circle homes. Web-only; no Blender, GLB, state,
  population, building, seed, or claim changes.

## 26. Organized homepage with live map preview

- Replaced the narrow vertical homepage button stack with a responsive
  destination dashboard. Desktop uses the screen horizontally: Walk and Claim
  are grouped in one navigation panel while the live map receives the larger
  visual panel. Mobile places the preview first and keeps both action cards in
  one compact row so the main choices remain above the fold.
- Added a lightweight isometric canvas preview that draws the current 244 homes,
  landmarks, established grid and Founder Park roads, and only the currently
  revealed portions of planned streets. It uses the existing
  `world_state.json` request and redraws on both live-stat refresh and resize,
  so normal town growth updates the homepage without a screenshot, new asset,
  or second map source of truth.
- Preserved session-aware Go to my home, admin visibility, reduced-motion and
  data-saver behavior, the 12-second background loop, and all Walk/Map/Claim
  destinations. Verified at desktop, laptop, tablet, and phone sizes with no
  browser errors. Web-only; Blender, GLB, state, population, buildings, seeds,
  and claims did not change.

## Files touched
- `index.html` — the web viewer itself
- `export_web.py` — new; Blender→glTF export script
- `grow.sh` — added the export step
- `neighborhood_blender.py` — hardened `clear_world()`
- `CLAUDE.md` — updated "Web viewer" section to describe the glTF pipeline
- `town.html` — added touch/joystick/drag-look controls for mobile
- `index.html` — responsive tweaks for small/short mobile viewports
