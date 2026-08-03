# FOLLOWVILLE — how to work on this project

Cade's Instagram project: a persistent 3D low-poly town in Blender. Every
follower is a house. Daily reels show the town growing.

**`world_state.json` is the city's only memory.** Never edit or delete it
casually; back it up before anything risky. It lives in the Git repo
(`C:\Users\cadet\followville_repo`), not in iCloud.

**For the current day, population and building count, read `world_state.json`.**
Never a document — the hand-maintained canon that used to live here had drifted
out of order and was missing the newest day entirely.

This file is instructions only. The day-by-day canon, the incident narratives
and the reasoning behind every rule below are in **`HISTORY.md`**, verbatim and
complete. If a rule here looks arbitrary, its story is in there. For what
changed most recently and who changed it, read `TEAM_LOG.md` — that is the
changelog, and this file is not.

---

## Authoritative workflow

- **Git is the only executable source** for code, `world_state.json`, web
  assets and current docs. On Windows: `C:\Users\cadet\followville_repo`.
- The **shared authoritative scene** is
  `C:\Users\cadet\iCloudDrive\neighborhood\neighborhood.blend`. The repo copy
  is a synchronized safety copy and the two must hash-match.
- Growth launchers run the generator and exporter **from Git** against the
  Blend **from iCloud**, in one Blender session. They fail before Blender
  starts unless the repo is on clean `main`, matches `origin/main`, and both
  Blend copies agree.
- **Retired, not fallbacks:** `--no-git`, iCloud-only state, unguarded Blender
  growth, an unset Mac repo path, and automatic `wip` sharing. Direct Blender
  GUI growth is locked unless its embedded generator hash matches the repo.
  After generator changes, refresh embedded text only through the guarded repo
  `_refresh_text.py` with `FOLLOWVILLE_REPO_DIR`/`NEIGHBORHOOD_STATE_DIR` set.
  Never load a numbered iCloud generator copy.
- **Numbered/parenthesized files** (`world_state 3.json`, `CLAUDE(1).md`) are
  iCloud sync artefacts, never source. Don't delete them without checking their
  contents — one has held the only copy of canonical state before. Don't trust
  bash's `ls`/`stat`/`tail` for freshness on iCloud paths; read the content.
- The old `deploy_website.*` and `share_progress.*` scripts are legacy recovery
  tools. Don't use them for routine work, and never let one switch the
  authoritative clone to `wip`.

### Daily growth

```text
cd C:\Users\cadet\followville_repo
grow_windows.bat --preflight-only
grow_windows.bat +N --render
```

Mac: set `FOLLOWVILLE_REPO_DIR` to the local clone, then run the guarded
`grow.sh`. Run `--preflight-only` first after any workflow change.

`+N` / `-N` / `=N` / `replay`. `replay` never touches `world_state.json` or the
Blend, so it is the safe way to re-export.

Logs end `ALL_DONE` or `ALL_FAILED`. **`ALL_FAILED` is real — read the log.**
Don't re-run and hope. If you open the Blend read-only to inspect something,
always answer "Ignore" / "Don't Save" on any prompt.

Flags: `--special TYPEhouse[@gx,gy] --followers N --hero --celebrate --parkring
--cam NAME --tag NAME --time day|sunset|night --season X --still --scatter`.
Videos auto-copy to Desktop.

Cameras: `overhead street park housefront newgrowth newstreet newgrowthoverhead
wholeoverhead storybookstreet cinematic dronezoom dronehover day25reveal
day29reveal`. `--cam housefront` and `--godzilla` are **render-only** and never
change state, GLBs or the Blend.

### Deploying

Live at `https://followville-kappa.vercel.app`; Vercel deploys every push to
`main`. Guarded production growth commits and pushes only `world_state.json`,
`town.glb`, `town_manifest.json` and `town_chunks/`. Everything else needs an
intentional reviewed commit.

### Cost discipline

- One preview still per day maximum (`--still`), then render. Routine `+N` days
  need no preview at all.
- Renders take 10–15 min: run as a background job writing `render_log.txt`
  (ends `ALL_DONE`), and hand log-watching to a **Haiku subagent**. Never poll
  with the expensive model.

### Environment (Windows)

**First thing in a new session, before any work:**

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_toolchain.py
```

It probes what this session can actually do — interpreter, repo modules, state,
pygltflib, git, node, Playwright, Chromium, the preview port, Blender, both
Blend copies — and prints the exact fix for anything missing, grouped by whether
it blocks inspecting, verifying or changing the world. It installs nothing and
writes nothing. Findings below are the ones it cannot probe for you.

- Python: `"C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe"`.
  The `python` on PATH is a Microsoft Store stub.
- **Windows PowerShell 5.1 has no `&&`.** It is a parser error, not a fallback.
  Run commands on separate lines, or use `;` if you don't need short-circuiting.
- `check_town_glb.py` needs `pygltflib`. Installing it lands in a per-user
  directory, because pip cannot write into `Program Files` without admin — so
  another shell or an elevated one may not see it and will report it missing.
  If the import fails, just install it again for whatever context you are in:

  ```
  & "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" -m pip install pygltflib
  ```
- Playwright from PowerShell needs `$env:PATH = "C:\Program Files\nodejs;$env:PATH"`
  or its web server dies with `'node' is not recognized`.
- Serve locally with `node tests/serve.mjs` (port 8765); `fetch()` needs
  `http://`, not `file://`. Check for a stale listener before trusting a 404.

---

## Looking at the world, and checking it

**Defects get reported as coordinates** — three.js world space: x right, y up,
z depth, and `three z = -blender y`.

**To go and look** (needs `?local=1`; use Playwright, not the in-app Browser
pane, whose WebGL dies after a few 3D loads):

```text
town.html?local=1&view=free&at=311.7,-7&look=322,1,10       walker's eye at x,z
town.html?local=1&view=free&eye=300,150,-25&look=305,0,-5   fixed camera
```

`at=` stands a walker there (`&dist=8` for third person); `eye=` parks a fixed
camera. `window.__followvilleTerrainQA.probe(x, z)` returns what a downward ray
actually strikes, by GLB node name — the only way to see geometry hidden *under*
other geometry.

**Before committing anything that moves a landmark or a road:**

Two commands, deliberately not chained — PowerShell 5.1 has no `&&`:

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py --self-test
```

It answers "is anything off the ground, on a road, or in the street" — the
class of defect `check_town_glb.py` is blind to. It audits against declarations
in `world_layout.py`: `LANDMARK_FOOTPRINTS`, `KEEP_OUT_REGIONS`,
`RETAINED_PADS`, `INTENTIONALLY_RAISED_ROADS`, `LEVEL_WATER`,
`LANDMARK_APPROACHES`, `AUTHORED_ELEVATION_ROADS`. **Adding a landmark or an
authored road means adding it there too** — an undeclared landmark is reported
as *unaudited*, not failed, so silence is not proof. `--self-test` re-creates
five known regressions and requires each to be caught; the count is whatever
`self_test()` declares, so read the output rather than trusting this sentence.

`check_town_glb.py` enforces hashes, state metadata, root integrity and exact
one-to-one coverage of every building ID. Both run in CI on every push to
`main` — check the Actions tab after any push.

`pnpm test:e2e` runs the Playwright suite. Run it after any public navigation
work. Runtime state is exposed as `data-*` attributes on `<body>`, so
assertions read those rather than poking at `THREE`.

---

## Geometry rules

**Visible-surface depth rule (mandatory).**
- Never place two independently rendered visible faces on the same plane —
  tops, bottoms, front/back, sides, corner trim, glazing, markings, paving,
  foundations, signs, transparent layers.
- A permanent fix physically separates the geometry. Browser `polygonOffset` is
  a temporary compatibility fallback, never a substitute for corrected source.
- Facade details sitting on a supporting wall use `mounted_face_center` or an
  audited equivalent, with at least `MIN_VISIBLE_SURFACE_CLEARANCE` (5cm) of
  visible clearance; the hidden side may stay embedded.
- Horizontal hardscape layers need distinct elevations and no overlapping
  vertical side walls. Coplanar surfaces must fail a standalone geometry check
  before any render, export or deploy.
- Review every new repeated asset head-on **and from both oblique sides** — a
  front-only screenshot hides shared corner planes.

**Ground and elevation.**
- Any level deck on a slope uses `_add_retaining_skirt()`, which samples terrain
  at every perimeter vertex. A wall on one face only holds up on level ground.
- `terrain_height()` in `downtown_visual_plan.py` is the single walk surface
  shared by Blender, roads, houses and the browser. `town.html`'s
  `regionalTerrainHeight` is a faithful port — change both together. It carries
  deliberate level shelves for downtown, the ring district, Kaleidoscope Crest
  and the fishing pond. **Level water needs level ground**: the meadow outside
  the paved grid climbs at a steady 9%, so no relocation fixes a perched pond —
  only a shelf does.
- Aerial cameras use a 10m near clip so thin roads and ponds don't flash from
  lost depth precision. Do not restore Blender's 0.1m default for aerial modes.
- Roads: terrain-following strips need control points every ~3m.
  `_add_road_strip` subdivides to 2m internally but `walk_surface_manifest`
  uses control points as given, so coarse points drift the walk surface away
  from the visible road.

**House placement.**
- Houses auto-face their nearest road. Override with `"face": "s|e|n|w"` on the
  building (the camera looks from the south-east, so `s` and `e` are visible).
- Every 3x3 block's dead-center lot (`ix==1, iy==1`) has no road frontage and is
  never buildable. `find_free_lots()` skips it; don't hand-place one there via
  `--special TYPE@gx,gy` either.
- Staged suburban streets build as continuous mitered meshes, sharing the width,
  material and centre-dash rhythm of the established town roads. A cul-de-sac
  bulb waits until its connecting road is complete.
- Regular houses never build in blocks containing custom founder houses.
- Block-fill is the default lot order (`sorted_lots_filling()`); `--scatter`
  opts into the old scattered look for one run.
- Nature scatter clears automatically from revealed roads, cul-de-sacs,
  occupied planned lots, and the authored landmark approaches.

**Preserve these regressions** when touching their systems:
`data-storybook-walkable`, `data-hill-clearance`, `data-claim-tag-roof-clearance`,
`data-fishing-pond-datum`, `data-rafting-station-walkable`,
`data-fishing-dock-walkable`, and the streaming hysteresis — whose distances are
**manifest-driven**, so read `town_manifest.json`'s `streaming` block for the
current values rather than any number written in prose. What must be preserved
is that load and unload distances differ, not what they happen to be.

**Lighting** final numbers: sun 1.0x at 4.5°, fill 0.07x, sky 1.0x. Don't
re-boost without comparing a frame against `day_007_hero` on the same machine.
Camera framing defaults were tuned on day 9 — compare against
`day_009_hero_fixed`/`day_009_overhead_condensed`, not day 7/8.

---

## Adding to the world

**A custom house model**: write `build_X_house()` in `neighborhood_blender.py`
using `add_box`/`add_ngon_cone`/`add_prism_roof` + `mat()`, register in `SIZE`
and `ASSET_VARIANTS`, then `--special xhouse[@gx,gy]`. Match the pastel style.

**Ordinary houses** draw from one library of 15 suburban designs across six
palettes (90 stable variants), each batched to a single mesh.

**Off-grid buildings** carry exact `px`/`py`/`rot` in `world_state.json` (see
`build_pos()`); `footprint()` reserves the grid lots underneath. District
positions are rigid render-time offsets in `world_layout.DISTRICT_OFFSETS` —
stored coordinates never move.

**`neighborhood_plan.py`** deterministically reserves the next 366 ordinary
houses across six curved-road districts with 18 cul-de-sacs. Planned roads and
houses create no object until `+N` growth consumes their exact addresses, and
existing geometry never moves. See `NEIGHBORHOOD_EXPANSION_PLAN.md`.

Milestones auto-build at population 500 (fountain plaza — suppressed while the
houses-only reserve runs), 2,000 (skyscraper), 10,000 (stadium).

---

## Web viewer

`index.html` is the landing dashboard; `town.html` is the walkable town;
`town.glb` plus `town_chunks/` and `town_manifest.json` are the geometry.

- Geometry is **real Blender output**, not a hand-ported copy: `export_web.py`
  runs in the **same Blender invocation** as the generator and bakes the WORLD
  collection. A new house type therefore "just works" on the web with zero
  web-code changes.
- District streaming sits in front of the complete GLB. Keep the manifest,
  chunks and full GLB together. Map and owned-home teleports must await
  `ensureTownChunkForBuilding()`. `?assets=full` is a maintainer diagnostic, not
  the public default; `?graphics=ultra` gates costly facade overlays, procedural
  shaders and dynamic shadows.
- Always read `state.pop` directly. **Never derive population from
  `buildings.length`** — one building may later hold many followers. No
  calendar maths anywhere; day and pop change only on an actual growth run,
  never on a timer.
- Collision colliders are computed automatically from loaded structural
  geometry as oriented footprints. Cars and tree trunks keep purpose-built
  accurate shapes — trunk cylinders only, never foliage.
- **Never create or maintain a separate map data file**, and never build
  parallel location tables or hard-coded coordinates. The map, `/today` and
  `/house/:id` all derive from `world_state.json` plus the live claims feed.
- The homepage `Walk` action must target `town.html#walk`. Preserve every
  `vercel.json` cache safeguard. The visual style is deliberately restrained and
  editorial — no oversized pills or icon-card dashboards.
- `YARD_DECORATIONS_ENABLED` in `town.html` is the single intentional feature
  gate for the paused yard decorations; saved values stay in Supabase.
- A procedural JS `BUILDERS` fallback exists if the GLB fails entirely. It is a
  safety net only, visually approximate and not kept in sync. Prefer
  regenerating `town.glb`.

### Export pitfalls (fixed — do not reintroduce)

All three are needed together in `export_web.py`:

1. Generator and exporter must run in **one Blender invocation**
   (`--python a.py --python b.py`), or the export reads a stale saved scene.
2. Jump to `scene.frame_set(scene.frame_end)` before realizing, or new houses
   bake mid-rise.
3. Call `obj.animation_data_clear()` on every object **before**
   `duplicates_make_real()`. That call re-evaluates the depsgraph, and a live
   Action's F-curve silently overwrites a plain `obj.scale = (1,1,1)`. This is
   the real fix for pancaked houses; the frame jump alone is not sufficient.

`export_web.py` fails the whole Blender process if any realized object has a
near-zero scale, and `check_town_glb.py` repeats that check independently.

---

## Claimable homes (see `CLAIMING_SETUP.md`)

Followers sign up, verify their Instagram handle (DM code, manually approved by
Cade), and claim one house. Backend is Supabase; schema in
`supabase_schema.sql`. One-house-per-account and one-account-per-house are
enforced by DB constraints via the `claim_house()` RPC.

- **Pipeline integration, don't lose this:** `grow_windows.ps1` (`Sync-Houses`)
  and `grow.sh` (`sync_houses.py`) sync new buildings into the Supabase
  `houses` table after each growth — insert-only and idempotent, needing
  `supabase_sync.env` (SECRET, gitignored, never deployed). Watch for
  `HOUSES_SYNC_OK` / `_FAILED` / `_SKIPPED` in `grow_log.txt`.
- Everything is claimable including founder houses, except ponds, parks,
  plazas, schools and other civic landmarks.
- Admins (`profiles.is_admin`) may own two houses; everyone else one. Live
  admins: `cade.toohey`, `stellar.kehler`. Admin actions are re-checked
  server-side inside the SQL functions.
- Homeowner Mode stores approved palette IDs in `claims.customization`. Web
  materials are cloned per house before recoloring so shared Blender materials
  cannot recolor neighbours.
- Multiplayer identity, session and chat writes are authenticated RPCs with RLS
  and narrow public-read columns. Guests cannot forge them.

---

## Collaboration

Cade and Zach both work this project, each with an AI (Claude and/or Codex, on
Windows and Mac). **GitHub is the sync mechanism, not file sync.**

- **Codex and Claude sometimes run on the same task at the same time.** Before
  committing, `git fetch` and read any incoming commits; expect the conflict to
  be in whatever file both were told to fix. Re-read any shared file
  immediately before editing it — a copy taken even a few minutes earlier may
  already be stale.
- Add **one line to `TEAM_LOG.md`** before handing off, newest at the top,
  starting with a tag: `[WORLD]` (Blender-authoritative — should look identical
  in renders and on the web), `[WEB]` (website-only presentation that was never
  added to Blender), or `[BOTH]`. Sign it with who and which AI.
- New scenery or geography goes into **Blender**, so `export_web.py` carries it
  over automatically. Reserve `[WEB]`-only changes for things that could never
  appear in a render — name tags, claim UI, touch controls.
- **"Same world" means same geometry, not same visual quality.** Renders are
  expected to look better than the browser: real lighting, shadows, AO, depth of
  field. What must match is which buildings exist, where, and what shape. Don't
  chase "make the website look like the video"; chase "same buildings in the
  same places".

---

## Files

| File | What it is |
| --- | --- |
| `world_state.json` | **The city.** Day, population, every building record. |
| `neighborhood.blend` | The scene (GUI panel: N key → City tab). |
| `neighborhood_blender.py` | The generator. |
| `export_web.py` | Bakes the WORLD collection to full + district GLBs. |
| `neighborhood_plan.py` | The 366-house structural reserve. |
| `world_layout.py` | District offsets, authored roads, audit declarations. |
| `downtown_visual_plan.py` | `terrain_height` and the shared terrain model. |
| `check_town_glb.py` | Export completeness and state consistency. |
| `check_world_geometry.py` | Is anything off the ground, on a road, in the street. |
| `assets/asset_sources.json` | Approved third-party asset provenance and licenses. |
| `assets/asset_library_manifest.json` | Generated hashes and geometry stats for the review library. |
| `scripts/build_asset_library.py` | Syncs and verifies approved review assets without promoting them. |
| `scripts/normalize_game_asset.py` | Isolated Blender intake/preview tool; refuses canonical town outputs. |
| `grow_windows.bat/.ps1`, `grow.sh` | Guarded growth launchers. |
| `preview_website.bat/.ps1` | Local HTTP preview, no Python/Node needed. |
| `tests/followville.spec.mjs` | The Playwright suite. |
| `HISTORY.md` | Full historical record — every canon entry and incident. |
| `TEAM_LOG.md` | Who changed what, newest first. |
| `AI_HANDOFF.md` | Cheap-model manual. |

Other docs: `CLAIMING_SETUP.md`, `AVATAR_SYSTEM.md` (read before touching the
avatar catalog, rigs, persistence or controls), `INTERIOR_SYSTEM.md` (read
before touching the room, furnishing catalog, persistence or builder),
`ASSET_PIPELINE.md` (read before downloading, importing or promoting assets), `DOWNTOWN_TERRAIN_HANDOFF.md`
(read before changing downtown or terrain), `NEIGHBORHOOD_EXPANSION_PLAN.md`,
`WEB_VIEWER_CHANGELOG.md`.

`condense_day9.py`, the `render_day9_*.command` scripts and the assorted
Windows `.bat`/`.txt` scratch files are superseded paper trail. **Nobody
deletes them without asking Cade** — the standing rule at the top of this file.
