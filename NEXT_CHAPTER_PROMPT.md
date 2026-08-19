# Prompt: plan and build Followville's next 1,000 homes (chapter five)

Hand this whole file to the AI taking the job. It is written to be pasted as a
prompt, not skimmed as background.

---

## The job

Act as a **city planner**, not a level designer. Plan and build the next 1,000
reserved home addresses for Followville, at the same quality as the four
chapters already in the ground: real street hierarchy, blocks that match the
existing fabric, roads that connect to roads that already exist, a density that
makes sense against distance from the centre, and empty parcels held back for
the things a town needs later — groceries, filling stations, schools, a fire
station, parks, stormwater ponds.

It is a **reserve**, not a build. Addresses exist as data; growth turns them
into houses one follower at a time. Nothing you add appears in the world until
a follower earns it.

## Why this is urgent

Read the numbers yourself before trusting this paragraph — but as of writing:

- `world_state.json`: **day 48, population 2360, 2348 buildings**
- `neighborhood_plan.HOUSE_CAPACITY`: **2148**
- **Unbuilt ordinary house addresses: 0.** The reserve is exhausted.
- Overflow has already begun: **one Crown Quarter tower, 11 residents.**

Every new follower now becomes a tower resident at 100 per building instead of
getting a house. Followville's whole identity is "every follower gets a house."
That stops being true the moment the reserve empties, and it already has.

Verify before starting:

```bash
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" -c "import json,neighborhood_plan as NP; s=json.load(open('world_state.json')); built={b['plan_id'] for b in s['buildings'] if b.get('plan_id')}; print('capacity',NP.HOUSE_CAPACITY,'unbuilt',sum(1 for h in NP.PLAN['houses'] if h['type']=='house' and h['plan_id'] not in built))"
```

## Read these first, and read numbers from source

`CLAUDE.md` is the operating manual and overrides anything here.
`WEST_QUARTER_PLAN.md` is chapter four and the closest model for this work.
Then `NEIGHBORHOOD_EXPANSION_PLAN.md` and `METROPOLITAN_EXPANSION_PLAN.md`.

**Never quote a total from prose.** `HOUSE_CAPACITY` is derived from `STREETS`;
how many addresses a street seats depends on how much room its specials take,
so any number written in a document is stale the moment a constant changes.

## The land, measured

Established by survey, not assumption. Re-measure before relying on them, but
do not re-discover them the hard way.

- **South and east are full.** Chapters one and two fill roughly y=-320..280.
- **Northgate/Southline**: x -190..210, y 306..486.
- **Crown Quarter**: x -220..196, y 486..824; its terrace ends at y=824.
- **West Quarter** (chapter four): south arm x -750..-190, y 414..486;
  north arm x -750..-260, y 522..810.
- **Willow Hills is the southern limit of the west.** Its northernmost houses
  stand at **(-241.5, 268.0) on 12.15m ground** and **(-213.3, 272.2) on
  9.08m**. Existing geometry never moves — this is why chapter four starts at
  Southline Avenue instead of carrying Northgate Avenue west.
- **The western ridge** peaks near **31m at (-460, 330)**. Chapter four stops at
  its foot rather than quarrying a mesa out of it.
- **North of about y=880 is flat open prairie**, 3.2–5.3m, from x=-750 east to
  the river. This is the obvious room for chapter five.
- **The river** runs x≈350–372 north of y=250; riparian clearance is 30m.
- **South of the Timber Bend Crossing the east bank is floodplain** — ground
  sits 0.5–1.3m *below* the river surface, because the river runs perched above
  its own meadow there.
- **No point on the river is 150m from a home.** Both banks are lined by the
  reserve. Do not spend hours looking for a site that clears 150m; there isn't
  one.

## Recommended siting, with the reasoning

**North of Crown Quarter and north of the West Quarter's north arm.** The
prairie above y≈880 is flat, empty, needs almost no terracing, and is the only
direction with room for another thousand homes.

Make it **continuous with what exists** — the thing Cade cares about most, and
the thing that got rejected twice before it was right:

- Continue the **70m north/south ladder** (the West Quarter's cross streets) and
  the **36m avenue ladder** straight north. Blocks stay 70 × 36m.
- Carry Crown Quarter's north/south streets north past y=824 so downtown's grid
  runs into the new quarter instead of stopping at a boundary.
- The quarter must meet the existing fabric along a **long edge, not a corner**.
  A detached grid joined by a single road will be rejected — that exact
  mistake was made and thrown away once already.

## The method that worked

1. **Survey before drawing.** Sweep every built building and every reserved
   address for occupancy; profile terrain height and grade across the candidate
   box. Decide from measurements.
2. **Continue the module.** Do not invent a new block size or street spacing.
3. **Roads connect to roads.** Extend existing streets by name where possible,
   and join where the old street is still running — never at a cul-de-sac bulb.
4. **Grade the density.** Chapter four runs 4.30m of frontage per address at the
   city edge, loosening to 7.40m at the far edge. A uniform quarter looks
   printed. Because `build_plan()` spreads a street's addresses evenly, one
   street can only carry ONE density — so cut long avenues into segments on the
   cross-street ladder.
5. **Hold parcels back.** Use existing types in `TYPE_FOOTPRINT` so no new
   assets are needed. Growth steps over them, the ground stays empty, and the
   building appears only when Cade asks.
6. **Deep types need perimeter frontage.** A fire station reaches 41m back from
   its own centreline while the next avenue is 36m away, so a 36m-deep building
   **cannot** sit inside the grid at any setback. Put schools, groceries and the
   fire station on an outer face with open ground behind — and confirm that
   ground is level, because a civic pad's fall across its footprint is capped at
   1.60m.

## Traps that cost real time here — do not re-learn these

- **`build_plan()` raises if a street cannot seat its declared count**, and
  capacity is NOT `length / spacing`.
- **A crossing street costs about 20m of frontage, not the 13.5m**
  `HOUSE_ROAD_CLEARANCE` implies — the crossing's own corner address eats into
  this street's frontage too.
- **Capacity is not monotonic in the requested count.** A street that cannot
  seat N may well seat N at a different total, because the placer walks
  candidate fractions outward from each address's ideal position. A street that
  refused once is worth retrying after other counts change.
- **So measure counts against the placer, then bake them.** Estimate to get the
  shape, then grow or trim each street against `build_plan()` until it seats
  exactly what it declares, and commit the measured table. Sized by arithmetic
  alone, nineteen chapter-four streets asked for more than could be placed —
  one of them by ten.
- **Verify terrain after EVERY change, not once.** A terrace measured clean
  before a re-siting was 0.203m out on Lantern Row afterwards, and the stale
  figure got reported as fact. Check ground movement under every built
  building, every reserved address **and** every existing plan road.
- **A flat surface is not the requirement; a continuous one is.** Chapter four's
  terrace deliberately stops 110m short of the seam and leaves the strip between
  on natural ground, because terracing it moved the built world.
- **`terrain_height()` and `town.html`'s `regionalTerrainHeight` change
  together**, verified by sampling both across the new area and the seam.
- **Gate new placement rules to unbuilt chapters only.** `build_plan()` re-solves
  a whole street at once. A built house's position is frozen in
  `world_state.json` while its road comes from the plan — re-solving an earlier
  chapter moves the road and leaves the house standing in the street.
- **Do not leave an unfinished plan in the working tree.** A growth ran here
  while chapter four was uncommitted and consumed 211 of its addresses into the
  live world before anyone decided to. Commit to a branch and get out of the
  shared tree.

## Verification gate — all of it, before committing

```bash
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" neighborhood_plan.py
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py --self-test
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_town_glb.py
```

`neighborhood_plan.py` is the one that matters — it places every address and
measures spacing, frontage, facing, footprint overlap, roads running through
buildings, and pad fall. Plus, written yourself:

- ground movement under all built buildings, reserved addresses and plan roads
  must be **0.000m**
- Blender vs browser terrain parity across the new area and the seam
- an **isolated full build-out** — copy the state, grow it, render it — so the
  quarter can be seen standing before anyone commits to it

## Absolute rules

- **Existing geometry never moves.** Built and claimed houses least of all.
- **Never edit `world_state.json` casually**; back it up before anything risky.
- **A render of a grown simulation is not the live world.** Never show planned
  content as though it exists — build video worlds from the live state.
- **If a new type is not a home, add it to BOTH non-claimable lists**
  (`NON_CLAIMABLE_TYPES` in `sync_houses.py` and the `$NonClaimable` mirror in
  `grow_windows.ps1`), or the sync offers it as a claimable property. A nuclear
  reactor nearly shipped as a claimable house this way.
- **Growth uses the guarded launcher.** On this machine set
  `FOLLOWVILLE_SHARED_DIR` to the repo — the iCloud path is stale and unused.
- **The Desktop for renders is `C:\Users\cadet\Desktop`**, not
  `[Environment]::GetFolderPath('Desktop')`, which OneDrive has redirected.
- Add one `TEAM_LOG.md` line before handing off. Codex and Claude run
  concurrently — `git fetch` and re-read shared files immediately before editing.

## Definition of done

1,000 new home addresses plus held-back parcels, reserved and validated; the
quarter continuous with the existing city along a long edge; every check above
green; a plan document in the shape of `WEST_QUARTER_PLAN.md` explaining what
was measured and why each boundary sits where it does; and photographs from an
isolated build-out showing it standing.
