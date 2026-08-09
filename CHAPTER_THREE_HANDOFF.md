# Followville — master prompt for the next AI

Paste this whole file as your first message. It is written to be self-contained
about *this* piece of work; everything else about the project is in the files it
points you at.

---

You are picking up Followville, Cade's persistent 3D low-poly town in Blender
where every Instagram follower is a house. Work on Windows in
`C:\Users\cadet\followville_repo`.

## Read first, in this order

1. `CLAUDE.md` — the operating manual. Follow it exactly. It overrides habit.
2. `TEAM_LOG.md` — newest entries at the top. The 2026-08-09 entry is the work
   you are continuing.
3. `world_state.json` — the only memory of the city. Day, population and
   building count come from here and never from a document.

Run the toolchain probe before anything else:

```
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_toolchain.py
```

## Where things stand

Day 38, population 849, 844 buildings. All 616 addresses of the first two
reserve chapters are built and consumed.

Two pieces of work landed on 2026-08-08/09:

- **`--cam day38foodtour`** — a 20-second Day 38 reel of Zach's Food Court.
  Shipped and approved. Do not "improve" its descent; Cade looked at it and
  said it was fine.
- **Chapter three of `neighborhood_plan.py`** — addresses **617–1126**: 500
  houses and 10 reserved non-house addresses, on a gridded quarter north of the
  city, sitting on a new level terrace at 5.00m in
  `downtown_visual_plan.terrain_height` (ported to `town.html`'s
  `regionalTerrainHeight` in the same commit, as that pair requires).

## Your job: three defects Cade found by looking at a render

### 1. Houses are placed inside the reserved specials — 58 of them

This is the big one and it blocks the reserve from being usable past address
624.

`build_plan()` enforces a flat 7.35m gap between address **points**, whatever
those points are. That is correct for a ~9m house and meaningless for a fire
station, which is `SIZE 3` — roughly **39m across**. Chapter three attached a
`type` to slots but never widened their clearance, so houses sit as close as
7.35m to the centre of a building six times that wide.

Measured overlaps:

| Address | Type | Houses inside | Worst |
| --- | --- | --- | --- |
| #961 | firestation | 14 | 16.68m |
| #710 | followmart | 12 | 16.62m |
| #799 | elementaryschool | 13 | 16.43m |
| #1011 | park | 6 | 10.18m |
| #746 | park | 3 | 7.88m |
| #771 | pond | 2 | 5.93m |
| #1081, #625 | gasstation | 2 each | ~5.7m |
| #1045, #661 | restaurant | 2 each | ~4.8m |

**The fix.** In `build_plan()`'s placement loop, replace the flat spacing with
a type-aware one: required gap = `radius(new) + radius(existing)`, radii derived
from `SIZE` (a `SIZE` of *n* is *n* × `LOT`(13m) across, so radius ≈ `n*13/2`)
with houses at ~4.6m. Keep the existing 5.5 / 7.35 floors so **addresses 1–616
do not move** — that is the hard constraint, see "Traps" below.

Then **re-solve the counts**: widening clearance means the streets can no longer
seat their current counts. Capacity is *not* a per-street property — addresses
are spaced as fractions of their street, so changing one count moves all of that
street's houses and changes what is blocked for every street placed after it.
A greedy search from a working vector, re-running the real placement after every
single removal, is what got it to exactly 510 last time. Budget ~20 minutes of
compute and run it in the background.

### 2. The highway was wrong and has been reverted

`build_northgate_highway()` was added and then reverted (commit `8689593`).
Do not simply restore it. It failed two ways:

- It connected to **nothing**. Its west end died 61m short of Overlook Circle,
  its east end 160m from Ferry Street, with no junction at either.
- It ran through built neighbourhoods. The check that cleared it only tested
  the spine against the 510 *reserved* addresses and found zero conflicts; it
  never tested against the 844 buildings already standing, which is exactly
  what Cade was looking at.

**The fix.** Route it with real junctions at both ends, and test it against
`world_state.json` buildings *and* the reserve *and* `PLAN["roads"]`.

### 3. The new quarter has no road to downtown

Cade's requirement, in his words: "this new area must be connected by road to
downtown." Right now the quarter's only access was via the reverted highway's
ramps, so it is reachable only across open meadow. This is part of the same
piece of work as #2 — the arterial has to come south into the existing street
network and reach downtown, not stop at the edge of the grid.

## Traps that already caught me — do not repeat them

- **"Verified" must name what was verified.** I verified address spacing,
  terrain flatness and that the 616 built addresses did not move, then called
  the reserve "verified". It had never been checked for footprint overlap, which
  is the defect Cade found in thirty seconds by looking at a picture. Say what
  you checked and what you did not.
- **Look at renders before claiming quality.** Every one of Cade's three
  findings was visible in a picture and invisible to the numeric checks.
- **Adding streets to `STREETS` can move existing addresses.** `all_segments`
  and `all_bulbs` are computed across *all* streets before placement begins, so
  a new street can block an old one's slot. Always re-run the check that every
  built `plan_id` in `world_state.json` still matches `PLAN` to within 1e-3.
- **Terrain changes must move nothing already built.** The bar is 1cm across all
  844 buildings, and `terrain_height` and `town.html`'s `regionalTerrainHeight`
  change together or not at all. The chapter-three terrace needed a feather that
  is *anisotropic in three directions* (141m west into open hillside, 76m east
  where the Food Court plateau starts, 65m south where the nearest Food Court
  home is 57m away) — a single circular feather moved that home 10cm.
- **`render_log.txt` is a tracked file.** Using it as `--log` dirties the tree
  and the launcher's own clean-`main` gate then fails the run before Blender
  starts. Use any other `*_log.txt`; `.gitignore` already covers them.
- **Renders land in `iCloudDrive\neighborhood\renders`, not `repo\renders`**, so
  `grow_windows.ps1` copies the wrong (stale) file to the Desktop. Copy by hand.
- **`setup_render()` leaves `image_settings.media_type` in VIDEO.** While it is
  there, `"PNG"` is not a member of the `file_format` enum. Set IMAGE first.
- **PowerShell 5.1**: no `&&`, and `Set-Content -Encoding utf8` writes a BOM that
  breaks `compile()` on a `.py`. Use `[System.IO.File]::WriteAllText` with
  `UTF8Encoding($false)`, or write files with the editor tool.

## How to look at the quarter without touching anything

Build all 510 addresses in a scratch copy — this never writes the real state:

```
$sc = "<scratch>\preview"
Copy-Item world_state.json "$sc\world_state.json"
Copy-Item "C:\Users\cadet\iCloudDrive\neighborhood\neighborhood.blend" "$sc\preview.blend"
$env:NEIGHBORHOOD_STATE_DIR = $sc
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background "$sc\preview.blend" `
  --python neighborhood_blender.py --python <your inspect script> -- --gained 510
```

Pass a second `--python` that places cameras and renders stills. Do not run
`export_web.py` in a preview — you do not want the GLBs regenerated.

## Also still open

- `town.html`'s terrace port is line-checked but **never sampled against the
  Python in a browser**. The project's standard is sampling both models and
  confirming they agree to 0.0000m.
- Zach's Food Court, shipped 2026-08-08, has two defects neither of us fixed:
  the Rivergate connector road cuts **2.48m into food house #2** (the fries
  carton at 296.6, 184.0), and the FOOD COURT sign stands **in the roadway**
  (2.5–2.6m from a centreline with a 3m half-width). Both are invisible to
  `check_world_geometry.py` because `foodcourt` declares no footprint in
  `world_layout.py` — it reports "not audited", which is not the same as clean.
- The Food Court's 20 records are stamped **day 37 in a day-38 world**, because
  the `--foodcourt` block appends before `state["day"] += 1`. Replay now falls
  back to the newest day that exists, so renders work, but the stamp is still
  wrong. Fixing it means editing `world_state.json` and the `day_built` already
  synced to Supabase — **ask Cade first**.

## Working agreements

- Add one line to `TEAM_LOG.md` before handing off, newest at top, tagged
  `[WORLD]` / `[WEB]` / `[BOTH]`, signed with who and which AI.
- Zach works this repo too, sometimes at the same time. `git fetch` and read
  incoming commits before committing; re-read shared files immediately before
  editing them.
- Growth runs through the guarded launcher only. `replay` never touches
  `world_state.json` or the Blend and is the safe way to re-export.
