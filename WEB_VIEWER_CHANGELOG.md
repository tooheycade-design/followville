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
- **Not yet verified** — was about to have the user open the `.blend` in the
  Blender GUI (Scripting tab) to check for an embedded `neighborhood_blender.py`
  Text datablock and read off its CONFIG constants, to confirm or rule this out,
  when the conversation was handed off.
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

## Files touched
- `index.html` — the web viewer itself
- `export_web.py` — new; Blender→glTF export script
- `grow.sh` — added the export step
- `neighborhood_blender.py` — hardened `clear_world()`
- `CLAUDE.md` — updated "Web viewer" section to describe the glTF pipeline
