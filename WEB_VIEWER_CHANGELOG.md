# Web viewer — change log

Running log of every change made while building the Followville web viewer, in order.
Kept here (rather than just in chat) so it survives across sessions.

## Day 17 growth + entire-town aerial framing (2026-07-18)
- Grew once from Day 16 / 272 to Day 17 / 301 with 29 ordinary claimable homes
  at Twin Oaks plan IDs 129-157, producing 304 canonical buildings.
- Regenerated the complete GLB fallback, base, manifest, and all six district
  chunks together; focused source, downtown, hash, state, and 304-building
  coverage checks passed.
- Increased the `wholeoverhead` portrait camera margin after visual review
  showed that the expanded Day 17 footprint clipped Twin Oaks on one side and
  crowded Kaleidoscope Crest on the other. The corrected opening and ending
  keep every developed district visible.
- Produced three separate 12-second daytime portrait videos: completed whole
  town, completed moving downtown showcase, then the only growth-animation
  clip with all 29 Day 17 homes appearing.
- Inserted all 29 new Supabase house rows without changing the exact existing
  claim snapshot: 31 claims across 30 accounts with identical ownership,
  timestamps, and customizations.

## Camera, reversible streaming, roof labels, storefronts, and chat (2026-07-18)
- Expanded third-person pitch to near-vertical up/down views and excluded
  walkable ground/roads from the obstruction ray. The collision-safe camera
  now shortens toward the avatar along the ground instead of becoming stuck.
- Added reversible district detail streaming: 70m loads full geometry, 112m
  unloads and disposes it, and the existing lightweight silhouettes return.
  Map/home teleports still await their required district, and unloaded chunks
  can be reloaded normally.
- Replaced type-based claim-label placement with actual loaded GLB roof bounds
  plus 1.25m clearance. This covers tall founder buildings and Kaleidoscope
  Crest storybook homes; fallback/full-town QA asserts the clearance.
- Moved ground-floor downtown glazing and decorative podium glazing inward so
  the exterior glass face is flush with the building facade.
- Kept recent persistent town chat visible as a compact translucent top-left
  walking feed; opening it reveals the existing composer, times, and history.
- Rebuilt the complete GLB, streamed base, affected original-town chunk, and
  manifest in replay mode. Day 16 / 272 / 275, `world_state.json`, addresses,
  claims, owners, and Supabase data are unchanged.

## Downtown terrain + balanced streaming presentation (2026-07-17)
- Integrated the approved thirteen-metre downtown layout and rebuilt full plus
  six-district streamed GLBs from the current Day 16 authoritative scene.
- Added authored downtown sidewalks, curbs, crossings, storefronts, furniture,
  skyline massing, regional terrain, terrain-following suburban roads, house
  pads, and Kaleidoscope access-road alignment without changing city canon.
- Added deterministic walk-surface segments/bulbs to `town_manifest.json` so
  streamed, full-fallback, map, collision, and player terrain logic share the
  same layout source; the GLB validator now checks this payload.
- Kept the real Blender geometry as the public default while moving expensive
  browser-generated facade overlays, procedural shaders, and dynamic shadows
  to maintainer-only `?graphics=ultra`. Software renderers select the
  compatible path automatically, and static town matrices are frozen without
  freezing animated avatars.
- Fixed the offline review server's CSP so its local Draco WebAssembly decoder
  can run; this allowance exists only on the local preview server.
- Preserved Day 16 / population 272 / 275 buildings, addresses 1-128, claims,
  owners, Supabase, and `world_state.json`.

## Avatar family and player-camera correction (2026-07-17)
- Made the 37 compact animated complete characters the only public character
  family. The taller modular face/hair/outfit/hat system is no longer shown or
  loaded, and saved legacy `custom` selections normalize to the animated
  default without a database rewrite.
- Fixed streamed startup so the camera rig attaches immediately and follows the
  player continuously. Corrected camera-relative A/D directions.
- Replaced always-on desktop mouse-look with cursor-locked right-button drag
  orbit; the cursor returns immediately on release. The orbit path no longer
  depends on Windows-style held-button state and accepts Mac Control-click drag
  as a fallback. Mouse wheel and trackpad scrolling now enter true eye-height,
  cursor-locked first-person mouse-look; zooming out restores third person and
  the cursor. Mobile
  drag and pinch use only camera-area touches, so one thumb can steer while the
  other orbits.
- Removed the obsolete white-dot center crosshair from gameplay.
- Added a short grounded player jump on desktop Space and a dedicated mobile
  JUMP button beside RUN. The follow camera rises with the local avatar,
  airborne re-jumps are blocked, and multiplayer visitors receive jump height.
- Bare `/town.html` now redirects old bookmarks to the current dashboard with
  the live map preview and Today in Followville. Explicit walk/map/house routes
  are unchanged.
- No town state, population, GLB, Blender scene, claim, owner, or Supabase row
  changed.

## Third-person Avatar System v1 (released 2026-07-17)
- Added a full-screen editorial Neighborhood Tailor opened from the start
  screen, pause menu, in-town button, or desktop `V`.
- Added a rigged modular avatar with 10 skin tones, five proportions, eight
  face silhouettes, six modeled hairstyles, six modeled outfits, and two hat
  states, plus 37 lazy-loaded complete character looks.
- Replaced text-only selection UI with 60 real preview JPGs captured from the
  exact selectable 3D models. Complete looks are grouped as Everyday, Town
  roles, and Adventure.
- Added third-person locomotion, live rotate/zoom preview, local guest storage,
  stable catalog IDs, and owner-only Supabase profile persistence.
- Default avatar geometry is 512,832 bytes; complete looks load individually
  and are not part of town startup. Avatar assets are isolated from every town
  GLB, `world_state.json`, and the canonical Blender scene.
- Applied `20260717_avatar_system_v1.sql`, verified authenticated saves and
  rejected unauthorized/malformed writes, then released the web build. Day 16 /
  272 population / 275 buildings and all 30 claims are unchanged. See
  `AVATAR_SYSTEM.md` for the asset, rebuild, license, rollback, and QA plan.

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

## 27. Prevent stale homepage restoration

- Added `vercel.json` response headers for `/` and `/index.html` with
  `no-store`, `no-cache`, `must-revalidate`, and immediate expiration. Matching
  HTML cache directives provide the same intent to browsers before all response
  metadata is processed.
- Bare `/` and `/index.html` were observed serving different deployment HTML
  from separate CDN cache keys. Bare `/` now uses a temporary redirect to the
  canonical, uncached `/index.html` route so only one homepage representation
  can reach visitors.
- Added a narrowly scoped `pageshow` safeguard: when a browser restores the
  homepage from its in-memory back/forward cache, the page reloads once from the
  current deployment. Normal page loads and navigation are not reloaded.
- This is web/deployment-only. The dashboard layout, map behavior, Blender,
  GLB, state, population, buildings, seeds, and claims did not change.

## 28. Restrained editorial homepage styling

- Removed the visual patterns that made the destination dashboard feel
  generated: large rounded cards, pill-shaped map badges, boxed stat widgets,
  icon tiles, heavy shadows, and widespread glass blur.
- Reworked the same structure into a flatter, more authored composition with a
  serif neighborhood statement, simple ruled Walk/Claim links, unboxed stats,
  minimal corner rounding, and a cream paper-plan frame around the live map.
  Copy is shorter and more literal throughout.
- The phone layout keeps the map above two compact text destinations without
  reverting to a long stack. Functionality is unchanged: live map rendering,
  routes, session-aware home/admin behavior, cache safeguards, video fallback,
  and all world data remain intact.

## 29. Homepage map return-path fix

- Fixed a route-state mismatch where opening the full map from the redesigned
  homepage and then closing it exposed the older `town.html` start screen that
  had been initialized underneath the map panel.
- A page initially opened at `town.html#map` now returns to `index.html` when
  the map is closed by its close button, Escape, or backdrop. Choosing Visit on
  a map result still enters the 3D town; maps opened while already walking still
  close back to the same walking session.
- This is navigation-only. World data, homes, claims, accounts, map contents,
  and multiplayer behavior are unchanged.

## 30. Direct Walk route

- Changed the redesigned homepage's Walk destination from plain `town.html` to
  `town.html#walk`, giving it an explicit direct-entry state instead of loading
  the older in-town intro screen.
- Once the world is ready, the route marker is removed and walking begins in
  the rendered neighborhood. Desktop users can click the town canvas to capture
  mouse-look; mobile uses the existing touch look and joystick controls.
- Other town entry states remain intact, including claims, owned-home routing,
  map deep-links, the in-game map, chat, accounts, and multiplayer.

## 31. Escape returns to the redesigned homepage

- Replaced the desktop pointer-lock exit fallback that displayed the legacy
  in-town intro with a return to `index.html`, using history replacement so the
  browser Back button cannot immediately revive that old town state.
- Escape while the town map or chat is open remains scoped to that overlay and
  resumes the rendered town without pointer-lock; clicking the canvas recaptures
  mouse-look. This avoids a browser race caused by requesting pointer-lock from
  inside the same Escape keystroke that just released it.
- This is navigation-only. World state, homes, claims, accounts, multiplayer,
  Blender assets, and map content are unchanged.

## 32. Today activity, permanent house links, and browser regressions

- Added `Today in Followville` to the homepage. It derives the latest home
  count, district, and streets directly from `world_state.json`, subtly marks
  those homes in the preview, and links to `/today`. The clean route opens the
  existing live 3D map filtered to the latest homes with an update summary and
  selected address ready to visit; the next normal growth day updates it with
  no manual copy or second data file.
- Added stable `/house/:id` addresses for every home and a responsive Share
  action in the map selection card. Native Web Share is used where available;
  desktop browsers receive a clipboard fallback and an explicit status. Unknown
  house IDs show a complete, searchable `Address unavailable` state rather than
  a broken page.
- Added same-app Vercel rewrites for both route families and a root document
  base so the static `town.html` app continues to load `town.glb`,
  `world_state.json`, video, and other assets from nested clean URLs. The routes
  inherit the project's no-store deployment safeguards.
- Added exact-version Playwright infrastructure and five browser regressions:
  live homepage values/preview, Today entry/return, house copy/visit, invalid
  address handling, and desktop chat/map/Escape movement recovery. GitHub
  Actions now runs these alongside the existing GLB and 366-address audits.
- Desktop and 390x844 phone layouts were visually reviewed. This is web and CI
  infrastructure only; Blender, GLB, world state, population, building seeds,
  claims, and Supabase schema were not changed.

## 33. Backdrop mountains clear growing suburbs

- Fixed two low-poly website backdrop mountains intersecting Day 14's newest
  Overlook Circle/Foxglove Court homes. The atmosphere had been authored as a
  fixed 282-310m ring while House #247 now reaches roughly 297m from town
  center, so the town had physically grown into the scenery.
- Each hill now preserves its original bearing and preferred distance, but is
  advanced outward in small steps whenever its conservative enclosing
  footprint is within 18m of any current building. Only threatened hills move;
  the rest of the skyline keeps its existing composition. Future normal growth
  re-runs the same clearance automatically.
- Added a runtime hill-clearance result and extended the walking Playwright
  regression to require a pass. All five browser tests passed, and ground-level
  views at Houses #239 and #247 were visually reviewed with clean open lots and
  mountains behind the neighborhood.
- Web-only. No Blender terrain, GLB geometry, house/road position, world state,
  day, population, address, claim, or Supabase data changed.

## 34. Day 15 raised-terrain walking and feature-road integration

- Added `storybookhouse` as a first-class home in the viewer, homepage preview,
  Today route, claiming material roles, and both town maps. Kaleidoscope Crest
  and Wanderlight Loop continue to derive from the canonical Day 15 building
  records rather than a second map/state file.
- Fixed first-person and multiplayer visitors passing underneath the terraced
  hill. A deterministic web walk-surface profile mirrors the Blender plateau,
  garden loop, and climbing access road, and the walking browser regression now
  requires `body[data-storybook-walkable="pass"]`.
- Blended the feature access into the established grid in Blender, the
  homepage preview, the flat map, and the 3D map. The junction begins at the
  old asphalt width/color, expands through a muted transition, and only then
  becomes bright pink; map joints use fitted caps rather than exposed segment
  corners.
- Made the Blender access-road markings follow the full three-dimensional road
  tangent and sample one continuous eight-metre rhythm. This removes both the
  horizontal floating lines on the hill and the dash bunching created by its
  dense ramp control points.
- Updated browser expectations to derive the current day/population/newest
  homes/districts/streets from `world_state.json`, so normal future growth does
  not make the regression suite stale. All five Chromium flows passed after
  the change.

## 35. Kaleidoscope house collisions and center-island finish

- Corrected the ten optimized `storybookhouse` collision footprints. Each
  house is one merged multi-material GLB mesh, so the former mesh-name filter
  included its complete lawn, path, flowers, fence, and mailbox. The viewer now
  measures only `NB_story_wall*` vertices intersecting player height, producing
  an oriented box around the actual structure while leaving the yard walkable.
- Added a runtime comparison against each full lot footprint and made the
  walking Playwright flow require `data-storybook-hitboxes="pass"` for all ten
  feature homes.
- Replaced the steep access road's rotated dash boxes with shallow meshes whose
  two ends are sampled directly from the 3D road centerline. The marks now share
  the ramp pitch and sit one millimetre above its surface instead of hovering or
  projecting horizontally through the climb.
- Closed the diagonal seam between every crooked lamp's lower and upper beams
  with a low-poly joint globe, and added a base collar at the island surface.
- Replaced the center tree with a detailed, performance-conscious Cat in the
  Hat public-art statue: full body, gloves, ears, face, whiskers, red bow tie,
  oversized striped hat, stepped pedestal, plaque, and two low topiaries. The
  merged street asset keeps the web draw count compact; a separate 1.95m
  pedestal collider prevents walking through it. Runtime GLB detection is
  covered by `data-kaleidoscope-statue="pass"`.
- Close Blender proofs covered the statue front, the exact steep ramp section,
  and a lamp joint. `check_town_glb.py`, all five Chromium regressions, and an
  automated browser content/error/route check passed. Day, population, 262
  building records, addresses, claimability, ownership, and Supabase data were
  unchanged.

## 36. Continuous feature props, position-preserving pause, and visible unclaim

- Replaced every Kaleidoscope Crest lamp's two-beam/joint construction with a
  single capped shared-ring tube. A parallel-transport frame keeps each ring's
  vertices aligned through bends, so the post cannot split, pinch, or twist.
  The globe overlaps the hook, the base overlaps the foot, and two metal
  brackets enter both the post and banner.
- Rebuilt the center Cat in the Hat sculpture as a polished hero asset. Curved
  legs, arms, cuffs, fingers, tail, and the six-band crooked hat use continuous
  tube meshes; facial layers, muzzle, bow, paws, and pedestal tiers overlap
  their parents. This removes the former floating primitive stack from front,
  three-quarter, side, and rear views while retaining Followville's blocky feel.
- Preserved smooth shading when the full feature street is merged for GLB
  performance. The web pedestal collider now matches the modeled 2.18m base.
- Changed desktop Escape from an implicit homepage teleport to a true pause.
  The camera never moves; `resume` continues at the same location,
  while `leave town` is an explicit action. Map and chat keep their local
  Escape behavior. The final pause card contains only those actions (plus map
  and signed-in home management); it intentionally has no state explanation.
- Made home relinquishment discoverable without weakening its safeguards.
  Signed-in owners now see `manage my home(s) / unclaim` on the town/start
  screen and a manage-home action in pause; admins select which of their two
  homes first, and the existing destructive confirmation/RPC remains required.
- Reviewed seven Blender proofs (four statue angles, lamp, ramp, and district),
  passed `check_town_glb.py`, passed all five Chromium flows, and completed an
  annotated browser content/error/UI review. Day 15 state, population, 262
  building records, addresses, claimability, and ownership were unchanged.

## 37. Street-first 3D map navigation

- Preserved the existing responsive isometric 3D town, its instanced geometry,
  built-road rules, camera controls, landmarks, and flat WebGL fallback.
- Replaced the default 259-house sidebar with eight self-updating groups: the
  seven named streets in current state plus one `Original town` group for the
  134 founder-era homes that predate street metadata. No canonical addresses
  were invented for those older homes.
- Clicking a street now focuses that neighborhood in the 3D scene. Clicking a
  rendered 3D house teleports directly into the walkable town; selecting a
  search result still exposes its Visit and permanent Share actions.
- Strengthened search for explicit `@owner` handles, partial handles, exact house
  numbers, and streets. Exact owner/house matches rank first, and broad searches
  show a bounded result set with a refinement hint instead of another huge list.
- Grouped newest-home and claimed-home filters by street while leaving school,
  landmark, and signed-in owned-home results as individual destinations.
- Extended the world-derived Playwright coverage for street counts, street
  search, `#29`, and the renamed house action. All five flows passed, and desktop
  plus 390px mobile browser reviews confirmed the map remains 3D, legible, and
  free of page/console errors. Blender, GLB, state, population, buildings,
  addresses, claims, and ownership were unchanged.

## 38. District-streamed Blender town with full fallback

- Extended the canonical Blender export with stable building metadata and a
  versioned `town_manifest.json`. Every one of the 262 canonical building IDs
  appears exactly once across five deterministic district assets; terrain,
  currently built roads, nature, traffic, and public feature dressing live in
  one shared base asset.
- Draco-compressed the base and district GLBs while preserving the complete,
  uncompressed `town.glb` as a production fallback. Detailed startup transfer
  is 2,800,996 bytes instead of 7,916,952 bytes (about 65% less); all compressed
  stream assets together are 4,398,376 bytes. Asset URLs use manifest SHA-256
  revisions so regenerated districts cannot be mixed with stale caches.
- Added low-detail instanced house silhouettes for unloaded districts. The
  browser loads detailed districts within a manifest-controlled 70m radius and
  removes the proxy atomically when the real geometry is ready. Proxies have no
  collision, so the existing real house/car/trunk hitboxes remain authoritative.
- Made map destinations and signed-in owned-home teleports await the target
  district. Failed destination loads leave the player and map in place with a
  retry message. If the manifest or any initial asset fails, the viewer cleans
  up and loads the full GLB automatically. Maintainers can force the same path
  with `?assets=full` for parity checks.
- Updated Windows and Mac growth automation to stage state, the full GLB,
  manifest, and chunk directory together, fail if required export artifacts are
  missing, and remove obsolete generated district files during export.
  `check_town_glb.py` now verifies manifest state metadata, byte counts,
  SHA-256s, GLB roots/scales, safe load distance, exact home coverage, and exact
  one-to-one building coverage.
- Eight Playwright flows passed: the existing homepage/Today/share/map/chat/
  pause/error behavior plus streamed startup, remote Willow Hills loading
  before teleport, intentional manifest-failure fallback, and iPhone touch/map
  recovery. Desktop streamed/full screenshots matched in the active detailed
  town, with only the intentional distant silhouettes differing. Day 15,
  population 259, 262 buildings, claims, owners, addresses, and visible Blender
  world content were unchanged.
- Added a hysteretic first-person near-clipping guard for multiplayer markers.
  Visitors still see every forward-facing smiley normally, but two players at
  the shared spawn (or standing nearly inside each other) no longer have an
  avatar fill the camera; it returns after they separate by 1.65m.

## 39. Guarded shared generator and claim-metadata maintenance

- Made the Git clone the only executable source for generator, exporter, state,
  and streamed/full web assets while retaining the shared iCloud
  `neighborhood.blend` as the authoritative Blender scene.
- Added matching Windows/Mac preflights that require clean synchronized `main`,
  exact repository/iCloud Blend hashes, current `origin/main`, and all required
  streamed assets before Blender starts. Both launchers always execute the Git
  generator and ignore generator copies that iCloud may rename. The retired `--no-git`,
  legacy `wip` auto-share, and standalone deploy/share paths now fail or carry
  prominent historical/recovery warnings.
- Hardened Blender text refresh with an explicit Git source, source hashing,
  scene provenance, and a recoverable pre-refresh Blend backup. Direct GUI
  growth now cancels when the embedded generator is not byte-for-byte current.
  The live repair reproduced iCloud renaming the restored exact generator to
  `neighborhood_blender 19.py`; that history copy was preserved, and both
  launchers were made independent of any generator beside the Blend.
- Updated expansion and handoff documentation to Day 15, population 259, 262
  buildings, and consumed planned addresses through 115; address 116 is next.
- Applied the guarded Supabase repair for unclaimed seed 73. Git history and
  canonical state identify it as the Day 9 house at `(-3,-3)`; its live row now
  matches and is publicly claimable. Only house row 73 changed. All 30 claim
  rows across 29 accounts, including owners and customizations, had identical
  before/after hashes. The retained repair SQL contains a claim-safe rollback.
- Temporary-Blend and authoritative-scene QA proved the refresh changed
  generator provenance but not object/collection/mesh/curve/material counts or
  the geometry digest. The refreshed repo/iCloud Blend hashes match. Windows
  and Mac-style preflights passed in isolated clean `main` clones with
  no shared generator present; a deliberately mismatched Blend was rejected.
  No state, GLB, town geometry, population, claim, or owner changed in this
  maintenance pass.

## 40. Day 16 growth and Twin Oaks streaming expansion

- Grew canonical state once from Day 15/population 259 to Day 16/population
  272, adding 13 ordinary planned homes at addresses 116-128. Address 116
  completes Willow Hills on Overlook Circle; addresses 117-128 begin Twin Oaks
  Drive.
- Regenerated the complete `town.glb`, hashed manifest, shared base, and
  district chunks together. The manifest now covers all 275 building IDs
  exactly once across six chunks and adds `town_chunks/twin-oaks.glb`; the full
  GLB remains the automatic fallback.
- Inserted house rows 263-275 through the guarded insert-only Supabase sync.
  All are Day 16 ordinary claimable houses; the 30 existing claims across 29
  accounts were unchanged.
- Confirmed the production site serves Day 16/population 272/275 buildings,
  passed full/streamed asset validation, and completed all eight Playwright
  stories. Six passed in the normal local run; the two 90-second local timeout
  cases passed on isolated 180-second reruns.
- Rendered and frame-reviewed two standalone portrait deliveries: a completed
  town overhead with no rise animation and an all-13 whole-town rise replay.

## Files touched
- `index.html` — the web viewer itself
- `export_web.py` — new; Blender→glTF export script
- `grow.sh` — added the export step
- `neighborhood_blender.py` — hardened `clear_world()`
- `CLAUDE.md` — updated "Web viewer" section to describe the glTF pipeline
- `town.html` — added touch/joystick/drag-look controls for mobile
- `index.html` — responsive tweaks for small/short mobile viewports
