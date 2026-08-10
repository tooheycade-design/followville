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
--cam NAME --tag NAME --time day|sunset|night|storm --season X --still --scatter`.
Videos auto-copy to Desktop.

Cameras: `overhead street park housefront newgrowth newstreet newgrowthoverhead
wholeoverhead storybookstreet cinematic dronezoom dronehover day25reveal
day29reveal day30reveal day31reveal day32campaign day33storm day34fire`.
`--cam housefront`, `--cam day34fire`'s emergency vignette, and `--godzilla`
are **render-only** and never change state, GLBs or the Blend.

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
`main`, in the **`check`** job — check the Actions tab after any push.

**Read the two CI jobs separately.** `check` (the Python audits) and `browser`
(the Playwright suite) fail for completely different reasons, and the run's
overall red tells you nothing about which. `browser` has been red on almost
every run for months on GitHub's two shared, software-rendered cores: the heavy
3D tests time out, **the set that fails changes from run to run on identical
code**, and the whole suite takes 32-45 minutes there against ~15 locally.
`playwright.config.mjs`'s own comment describes the same signature. So a red
`browser` is not evidence of a defect and a green one is not available; get your
signal from `pnpm test:e2e` locally, and use CI's `browser` only to compare the
*named failing tests* against the previous run. `check` is the job that means
something on its own.

The repo is public, so neither needs `gh` or any token:

```bash
curl -s "https://api.github.com/repos/tooheycade-design/followville/actions/runs?branch=main&per_page=3" | jq -r '.workflow_runs[] | "\(.head_sha[0:9]) \(.status) \(.conclusion)"'
```

For which tests failed rather than just that something did, read the run's
annotations — the CI reporter writes a Playwright summary into them:

```bash
curl -s "https://api.github.com/repos/tooheycade-design/followville/commits/main/check-runs" | jq -r '.check_runs[] | "\(.name) \(.conclusion) \(.id)"'
curl -s "https://api.github.com/repos/tooheycade-design/followville/check-runs/<id>/annotations" | jq -r '.[] | select(.annotation_level=="notice") | .message'
```

`check_food_assets.py` needs Blender, because the only honest answer comes from
building the assets. The Food Court's homes are the one district made of loose
primitives rather than the shared suburban shell, so it builds all ten designs
before the per-house merge collapses them and requires nothing below the
foundation, nothing past `FOOD_COURT_HOME_REACH`, and no two axis-aligned boxes
sharing a face plane. It then measures all nineteen standing homes against both
district roads using each design's **convex hull** — a box drawn round a round
plinth reports homes as standing in roads they clear.

**Importing `neighborhood_blender` in a background Blender session runs a
growth.** The module ends in `if bpy.app.background: main()`, which is the whole
launch mechanism, so any tool that imports it to read a function grows the city
as a side effect — one did, silently advancing the world a day and leaving
`town_manifest.json` disagreeing with `world_state.json`, which drops the
browser out of district streaming without saying so. Set
`FOLLOWVILLE_IMPORT_ONLY` before the import; nothing in the growth path sets it.

`pnpm test:e2e` runs the Playwright suite. Run it after any public navigation
work. Runtime state is exposed as `data-*` attributes on `<body>`, so
assertions read those rather than poking at `THREE`. A failure far from what you
touched is worth taking seriously rather than filing as flake: the Timber Bend
crossing test went red because a state/manifest mismatch had emptied the
walk-surface manifest 400m away.

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

**`neighborhood_plan.py`** deterministically reserves every future address:
366 across six curved-road districts, then 250 more in the river chapter, then
the gridded Northgate quarter. **Read the total from `HOUSE_CAPACITY`**, which
is derived from `STREETS` — how many addresses a street seats depends on how
much room its specials take, so any figure written in prose goes stale. A
handful of chapter-three addresses are civic buildings rather than houses, and
are consumed in the same order. Planned roads and houses create no object until
`+N` growth consumes their exact addresses, and existing geometry never moves.
See `NEIGHBORHOOD_EXPANSION_PLAN.md`.

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

The same verified/pending/rejected flag is what the mayoral election calls
"citizenship" — see `ELECTION_SETUP.md`. Approving someone for a house also
lets them vote; there is no second approval and no second account concept.

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

## Followville Stories

A **second** video format alongside Daily Growth, added 2026-08-10 — short
episodes about events happening inside the persistent city, so the world feels
alive between population updates. It changes nothing above. Full direction is
in **`FOLLOWVILLE_STORIES.md`**; read it before producing one.

- **Trigger:** "let's make a Followville Story", "Story video", "make an
  episode". Enter Story mode — **gather context and propose three concepts
  first**, don't start modifying Blender.
- **No people, ever, in a produced Story.** The environment tells the story
  through vehicles, doors, packages, lights, weather, props and hard cuts.
  Website avatars are unaffected — the rule is about rendered video.
- **Shot renders must not advance the world.** Build on `--replay` with a
  Story camera, exactly as `--replay --godzilla` does: temporary set dressing
  that never touches `world_state.json`, the GLBs or the Blend. Name shots
  `--cam story001NAME --tag story_001_shotN`.
- **Anything a Story leaves behind permanently** — a business, landmark,
  branded store, custom property — is a normal `[WORLD]` change and takes the
  full route: addressed build, guarded growth, `world_layout.py` declarations,
  both audits.

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
| `check_food_assets.py` | Are the ten Food Court home designs sound (needs Blender). |
| `assets/asset_sources.json` | Approved third-party asset provenance and licenses. |
| `assets/asset_library_manifest.json` | Generated hashes and geometry stats for the review library. |
| `scripts/build_asset_library.py` | Syncs and verifies approved review assets without promoting them. |
| `scripts/normalize_game_asset.py` | Isolated Blender intake/preview tool; refuses canonical town outputs. |
| `grow_windows.bat/.ps1`, `grow.sh` | Guarded growth launchers. |
| `preview_website.bat/.ps1` | Local HTTP preview, no Python/Node needed. |
| `inventory-system.js` | Fish catalog, stacking rules, guest + account stores. |
| `tests/followville.spec.mjs` | The Playwright suite. |
| `tests/inventory_*_test.mjs` | Fast local inventory checks (`pnpm test:inventory`). |
| `HISTORY.md` | Full historical record — every canon entry and incident. |
| `TEAM_LOG.md` | Who changed what, newest first. |
| `AI_HANDOFF.md` | Cheap-model manual. |

Other docs: `CLAIMING_SETUP.md`, `ELECTION_SETUP.md` (read before touching the
mayoral election, the ballot or `vote.html` — a "citizen" there is exactly a
`verified` profile, not a new account type), `AVATAR_SYSTEM.md` (read before touching the
avatar catalog, rigs, persistence or controls), `INTERIOR_SYSTEM.md` (read
before touching the room, furnishing catalog, persistence or builder),
`INVENTORY_SYSTEM.md` (read before touching the fish catalog, the inventory
panel or `profiles.inventory` — note the fish IDs are permanent and the
`profiles` update grant must re-grant `avatar` alongside `inventory`),
`ASSET_PIPELINE.md` (read before downloading, importing or promoting assets), `DOWNTOWN_TERRAIN_HANDOFF.md`
(read before changing downtown or terrain), `FOLLOWVILLE_STORIES.md` (read
before writing, storyboarding or producing a Story video),
`NEIGHBORHOOD_EXPANSION_PLAN.md`, `WEB_VIEWER_CHANGELOG.md`.

`condense_day9.py`, the `render_day9_*.command` scripts and the assorted
Windows `.bat`/`.txt` scratch files are superseded paper trail. **Nobody
deletes them without asking Cade** — the standing rule at the top of this file.
