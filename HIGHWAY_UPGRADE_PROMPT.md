# Prompt: the Followville highway system

Hand this whole file to the AI taking the job. It is written to be pasted as a
prompt, not skimmed as background.

---

## The job

Followville has a town's worth of streets and one lonely elevated expressway
that starts nowhere and stops nowhere. **Design and then build a real highway
system**: upgrade the Crown Expressway that already exists, extend it, and add
to it until the city is served the way a working city is served. Put vehicles
on it and light it.

Cade's words, so you have them unfiltered:

> upgrade the roads and highway system in the world. No animation needed but
> will add vehicles to the highway and lights and build like as if a city
> planner a full highway system. High quality low poly. It should plan it out
> to make sure it's like how a real life highway system would work. And make
> sure it's all connected to what's built in the world so far and send me
> screenshots of the roads as it works on them so I can watch its progress. It
> should upgrade the highway that's already there and add on.
>
> It can be a big highway
>
> It can build it after planning and send me photos of the fully built system
> and how it connects to the already built world and it should know and see
> what is planned in the world but not in the website yet. So the skyscrapers
> that aren't officially in yet but planned it can see and adds to that plan.
> So when I look in the morning when I wake up I see the fully built system and
> can say to push or not
>
> Plan and then build so it's thought out like a city planner

Four things follow from that, and they are the shape of the whole job:

1. **Plan first, in writing.** Not a sketch in your head — a document, the way
   `NORTH_REACH_PLAN.md` is a document. Then build to it.
2. **You do not need approval between the two.** Plan, then build, in one go.
3. **Design for the city that is planned, not the city that is built.** See
   below; this is the requirement most likely to be skipped and it is the one
   that makes the difference between a highway and highway-shaped scenery.
4. **Do not push.** Cade wakes up, looks at the photos, and decides. See
   "Leave it for the morning".

`CLAUDE.md` is the operating manual and overrides anything here. Read it first,
then `METROPOLITAN_EXPANSION_PLAN.md` (the expressway's original spec),
`NORTH_REACH_PLAN.md`, and `world_layout.py`'s declaration blocks.

## Read the numbers from source, not from this file

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_toolchain.py
```

As of writing, `world_state.json` is **day 49, population 2,512, 2,500
buildings**, with **3,691 of 5,251 planned road segments revealed**. Verify
before doing anything.

---

## Design for the city that is planned, not the city that is built

This is Cade's "it should know and see what is planned in the world but not in
the website yet". A highway built only for today's 2,512 people would be
obsolete on the day it opened, and real planners size for the horizon. All of
this already exists as data, deterministically placed, waiting for followers:

| Reserve | Where | Size |
| --- | --- | --- |
| **19 unbuilt towers** | x −158..125, y 553..755 | 1,900 more residents |
| Crown Fields (ch. 5) | north of y=824 | 487 addresses |
| Kestrel Downs (ch. 5) | x −750..−540 | 255 addresses |
| Gatehouse Green (ch. 5) | x −540..−190 | 128 addresses |
| Unbuilt roads | x −750..160, y 810..1170 | 1,560 segments |

Read them yourself — `metropolitan_plan.TOWER_PLAN` (20 towers at
`TOWER_RESIDENT_CAPACITY` 100 each, exactly **one** built and holding 11),
`neighborhood_plan.PLAN["houses"]` past the highest built `plan_id` (2301), and
`PLAN["roads"]` with `reveal_at` past it. Milestones also auto-build at
population 2,000 (skyscraper) and 10,000 (stadium).

**The single most important fact in this table**: the tower field at
x −158..125, y 553..755 is the future downtown core — 2,000 residents in twenty
towers — and it sits immediately **west of the expressway** at x=222. That is
the demand the highway exists to serve, and today it is served by one
interchange. Meanwhile **Kestrel Downs and Gatehouse Green, 383 planned homes
out west, have no highway access at all.**

Plan the alignment and the interchanges around the full build-out. Build the
geometry now. Nothing here requires the future houses to exist yet — planned
roads and houses create no object until growth consumes their addresses, and
**existing geometry never moves**, so a highway laid out for the finished city
is safe to build against today's.

---

## Phase 1 — plan it, and write it down

Produce **`HIGHWAY_PLAN.md`**, in the style of `NORTH_REACH_PLAN.md`: measured,
specific, and honest about what it does not solve. It must answer:

- **Where do the two ends of the expressway go?** Today it runs y=250 to y=858
  and simply stops at both ends. The world's built extents are **x −758..631,
  y −324..1156** — so the highway covers 608m of a 1,480m-tall world, stopping
  312m short of the northern edge and 566m short of the southern one. Real
  highways leave town. The obvious answer is that it runs off the map at both
  ends; say where the map edge is and how the road meets it.
- **How many interchanges, and where, and what does each one serve?** There is
  currently one, a diamond at Crown Boulevard (y=654). One interchange for a
  city heading to 2,000 tower residents plus 3,171 houses is not a system.
- **Is there an east–west route?** A lone north–south corridor is not a system
  either, and the whole west side has no access. If you propose a crossing
  route it needs a real junction with the expressway, not a crossroads.
- **The hierarchy**, and which existing roads become what. Followville has
  locals, one boulevard grid, and a freeway — the **collector tier is missing**,
  and that is why the current expressway feels bolted on.
- **Staging.** Which parts serve today's 2,512 and which are sized for the
  build-out. A planner would draw both.
- **What it costs**: new authored roads, new `world_layout.py` declarations,
  and whether any terrain shelf is needed (try hard to need none).

Include a route map — an overhead screenshot of the world with the alignments
drawn on it. Cade thinks visually and reads on his phone.

## Phase 2 — build it

Build to the plan. If building teaches you the plan was wrong, change the plan
document too; do not leave a document that describes a city you didn't build.

---

## What is already there, measured

### The Crown Expressway

Spec in `METROPOLITAN_EXPANSION_PLAN.md`, constants in `metropolitan_plan.py`:

| | |
| --- | --- |
| `EXPRESSWAY_X` | 222.0 |
| `EXPRESSWAY_Y0` / `Y1` | 250.0 → 858.0 |
| `EXPRESSWAY_DECK_Z` | 14.0 (elevated) |
| `EXPRESSWAY_WIDTH` | 24.0, six lanes |
| `INTERCHANGE_Y` | 654.0, diamond |
| `RAMPS` | four, from `ramp_plan()` |
| `EXPRESSWAY_REVEAL_TOWER` | 1 — it appears with the first tower |

Piers at ~38m, median and outside barriers, shoulders, overhead gantries.

**The spec and the world disagree, and this is your first fix.** The plan says
the expressway "continues beyond the district in both directions visually; it
does not terminate at the towers." It does terminate. It stops dead at y=858,
which used to be empty meadow and is now beside the day-49 North Reach, so the
cut end is becoming visible from the new quarter. Day 49's camera was
deliberately framed to keep it off screen. That was a workaround, not a fix.

### The other road systems it has to connect to

- **Local streets** — `ROAD = 6`m, built from `neighborhood_plan.PLAN["roads"]`
  as `{a, b, reveal_at, street, district}` segments.
- **The Northgate arterial** — `northgate_arterial_points()`,
  `ARTERIAL_HALF_WIDTH`, `NORTHGATE_ARTERIAL_REVEAL`.
- **The metropolitan grid** — `metropolitan_plan.STREETS`, `BOULEVARD_WIDTH` 14,
  `LOCAL_ROAD_WIDTH` 8, `SIDEWALK_WIDTH` 3.2, six north–south lines and five
  east–west.
- **The North Reach** (day 49) — five ribbons at x=−190/−120/−50/20/90 running
  north to y=1170 **and stopping in meadow**, because their cross streets do
  not reveal until plan_id 2345. You are connecting to five loose ends up
  there, not to a grid.
- **Bridges** — Founders Crossing, Timber Bend Crossing, both declared raised
  regions. Read them before authoring another bridge.
- **Landmark approaches** — Station Trail and Point Road (nuclear plant),
  rafting outpost lane, City Hall approach, and the rest of
  `LANDMARK_APPROACHES`.

---

## What "like a real life highway system" actually demands

The test is whether a traffic engineer would nod at it:

- **Hierarchy**: freeway → arterial → collector → local, with the missing
  collector tier supplied.
- **Access control.** Nothing fronts a freeway — no driveway, no house, no
  direct local-street connection. Access happens only at interchanges. Check
  every alignment against `HOUSE_ROAD_CLEARANCE` and the standing houses;
  **the road yields, not the houses.**
- **Ramps that work**: acceleration and deceleration lanes with real tapers,
  grade limits (the four existing ramps are grade-limited — match them), and
  enough weaving distance between successive ramps.
- **Termini that are not cut ends.** Every end of every road is an interchange,
  a surface intersection, a turnaround, or an exit off the map. "It fades into
  the meadow" is the defect you were hired to fix; don't add four more.
- **Continuity of crossing streets.** Where the freeway crosses a street, that
  street passes under with clearance, passes over, or is properly terminated.
  It may not stop at the embankment.
- **Markings, barriers, shoulders, signs**: lane and edge lines, gore striping
  at ramps, median barrier, gantries at decision points.

**High quality low poly** is the house style, not an excuse for crude work.
Match the pastel palette and the way `build_metro_tower()` and the suburban
shells are built: flat colours, clean silhouettes, no textures, real geometry
rather than painted-on detail.

## Vehicles

`build_car(col, seed)` exists; cars are placed as
`{"type": "car", "gx": 0, "gy": 0, "seed": ...}` through `place_instance`.
Reuse it; add types if the highway wants trucks.

No animation, so these are static — and static vehicles are ruthless about
revealing mistakes:

- **Direction of travel.** On a divided six-lane road every vehicle on one
  carriageway faces one way and the other carriageway faces the other. One car
  facing the wrong way ruins the shot and is the likeliest error you will make.
- **Lane discipline**: centred in a lane, following the road's curvature.
- **They sit on the deck, not the ground.** The deck is at z=14. A vehicle
  placed at `terrain_height()` under the viaduct is a car buried in a field.
  Place off the surface you built and verify with
  `__followvilleTerrainQA.probe(x, z)`.
- **Spacing and variety**: vary `seed` so the same car doesn't repeat, and vary
  the gaps — evenly spaced cars read as a toy train.
- Colliders are computed automatically from structural geometry, but **cars
  keep purpose-built accurate shapes**. Don't break that.

## Lights

`build_streetlight(col, _seed=0)` exists, placed as `{"type": "streetlight"}`
records, e.g. `place_instance(world_col, lamp_data, "metro_streetlight")`.

**Naming matters more than you would expect.** The render-only light pools the
sunset/night presets add attach to objects whose names contain `suburban_light`
or `metro_streetlight`. Name new highway lighting so it is picked up, or it
looks unlit at night with no obvious cause.

Freeway lighting is not street lighting: high-mast at interchanges, regular
spacing along the mainline, and the deck lit from its own poles rather than
from the ground 14m below.

---

## Photographs

Cade asked for progress shots while you work **and** photos of the finished
system showing how it connects to the built world. Both, not one.

**Use Playwright, not the in-app Browser pane** — the pane's WebGL context dies
after a few 3D loads.

```text
$env:PATH = "C:\Program Files\nodejs;$env:PATH"
node tests/serve.mjs                       # port 8765
```

Cameras (`?local=1` is required; **three z = −blender y**):

```text
town.html?local=1&view=free&eye=300,150,-25&look=305,0,-5    fixed camera
town.html?local=1&view=free&at=311.7,-7&look=322,1,10        walker's eye
```

`window.__followvilleTerrainQA.probe(x, z)` returns what a downward ray
actually strikes, by GLB node name — the only way to see geometry hidden
*under* other geometry, which is exactly the failure mode of an elevated deck.

How to do it well:

- **Fix a camera set at the start and reuse it every time**, so Cade compares
  like with like instead of a slideshow of unrelated angles: one overhead of
  the whole corridor, one per interchange, one per terminus, one at deck level,
  and one at each junction with the existing town.
- The finishing set must **show the connections** — the highway meeting the
  Northgate arterial, the metropolitan grid, the west side, and the North
  Reach. That is what Cade asked to see.
- Send them with **SendUserFile as you finish each milestone**, not batched at
  the end. Caption what changed: "interchange at y=654, southbound ramps
  rebuilt with taper" beats "screenshot 4".
- He reads on a phone. A few clear images beat many.

---

## Leave it for the morning — do not push

*"So when I look in the morning when I wake up I see the fully built system and
can say to push or not."*

**This job never pushes to `main`.** That has a sharp consequence you must plan
around:

> **The guarded launcher cannot be used for this job.** `grow_windows.ps1`
> hardcodes `git push origin main` after it commits, and its preflight only
> runs on a clean `main` matching `origin/main`. Running it would push the
> thing Cade wants to review first.

So do this instead:

1. Branch: `git checkout -b highway-system` off current `main`.
2. Make the generator and plan changes there.
3. Regenerate the assets by invoking Blender **directly**, in one session, the
   same way the launcher does — generator, then `export_web.py`, then
   `save_canonical_blend.py`:

   ```text
   blender --background neighborhood.blend --python neighborhood_blender.py ^
       --python export_web.py --python save_canonical_blend.py -- --replay
   ```

   One invocation matters: a separate export reads a stale saved scene.
4. Commit `town.glb`, `town_manifest.json`, `town_chunks/` and
   `neighborhood.blend` **to the branch**. Push the *branch* if you like so
   Cade can see it from anywhere — never `main`.
5. Tell him plainly, in your final message, exactly what merging would deploy.

**`--replay` never changes `world_state.json`.** Day and population must not
move. If you find yourself typing `+N`, stop — you have misunderstood the job.
Run `grow_windows.bat --preflight-only` for its validation if you want it, but
not the launcher itself.

While iterating, keep the repo clean: point `NEIGHBORHOOD_STATE_DIR` at a
scratch copy of `world_state.json` and run Blender directly, exactly as day
49's camera work did. Set `FOLLOWVILLE_IMPORT_ONLY` before importing the
generator for any other reason — **importing `neighborhood_blender` in a
background Blender session runs a growth** and has silently advanced the world
before.

**No renders are needed.** Cade said no animation, which removes the 10–15
minute render from every loop. Your feedback loop is the browser.

---

## Rules that will bite you

- **Control points every ~3m on terrain-following roads.** `_add_road_strip`
  subdivides to 2m internally, but `walk_surface_manifest` uses the control
  points *as given*, so coarse points drift the walkable surface away from the
  visible road.
- **Declare everything.** A road with authored heights goes in
  `AUTHORED_ELEVATION_ROADS`; its footprint in `INTENTIONALLY_RAISED_ROADS`; a
  new landmark in `LANDMARK_FOOTPRINTS`. An undeclared landmark is reported as
  *unaudited*, not failed — **silence is not proof.**
- **The visible-surface depth rule is mandatory.** Never two independently
  rendered visible faces on one plane: markings against deck, deck against
  shoulder, barrier against edge, sign against gantry. Separate the geometry;
  browser `polygonOffset` is a fallback, never a fix. Review every repeated
  asset head-on **and from both oblique sides**.
- **Level decks on slopes need `_add_retaining_skirt()`**, which samples
  terrain at every perimeter vertex. A wall on one face only holds on level
  ground.
- **Try not to touch terrain at all.** If you must, `terrain_height()` in
  `downtown_visual_plan.py` and `regionalTerrainHeight` in `town.html` are the
  same surface and **change together**.
- **Aerial cameras use a 10m near clip** so thin roads don't flash.
- Windows PowerShell 5.1 has **no `&&`** — a parser error, not a fallback.
- Python is Blender's bundled interpreter; the `python` on PATH is a Store stub.
- `pnpm` is **not** on PATH — run `.\node_modules\.bin\playwright.cmd`.

## Checking your work

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py --self-test
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_town_glb.py
```

`check_world_geometry.py` answers "is anything off the ground, on a road, or in
the street" — the class of defect this job can most easily introduce. Read the
self-test's own output for the count rather than trusting prose.

Then the Playwright suite locally. Expect two tests to be **already red for
reasons that predate you**: the map street count (the map counts the Crown
Quarter tower as a home — red since day 48) and the Day 28 river centreline
(11 vs 15 — red since 2026-08-12). Don't chase those. Do take seriously any
*new* failure, especially the Timber Bend crossing test: it went red once
because a state/manifest mismatch had emptied the walk-surface manifest 400m
away.

## Definition of done

- `HIGHWAY_PLAN.md` written before the build, and still true after it.
- The Crown Expressway upgraded and no longer terminating in mid-air at either
  end, with `METROPOLITAN_EXPANSION_PLAN.md` updated to describe what is
  actually built.
- A highway **system**: interchanges, the missing collector tier, west-side
  access, every alignment tied into the existing network — nothing ending in a
  field — and laid out for the planned build-out, not just today's 2,512.
- Vehicles on the mainline, facing the right way, sitting on the deck.
- Lighting named so the sunset and night presets pick it up.
- Both audits green; `world_state.json` **unchanged** — same day, same
  population, same building count.
- Photos delivered through the build, plus a finishing set showing the
  connections to the built world.
- One line in `TEAM_LOG.md`, newest at top, tagged `[WORLD]`, signed with who
  and which AI.
- **Everything on a branch. `main` untouched.** The last thing you say to Cade
  is what merging would deploy.

## Absolute rules

- **Never edit `world_state.json`.** This job does not change it at all. Back
  it up before anything risky anyway.
- **Existing geometry never moves.** The road yields to the houses.
- **Never push to `main`**, and never let the guarded launcher do it for you.
- `git fetch` and re-read shared files immediately before editing — Codex and
  Claude run on this repo concurrently, and the conflict will be in whatever
  file you were both told to change.

## One loose end you inherit

The North Reach's five streets run north to y=1170 and stop, because their
cross streets don't reveal until plan_id 2345. That is correct behaviour for a
growing town and **not yours to fix** — but if your highway reaches north, do
not imply those stubs are finished roads. Ask Cade before tying anything
permanent into them.
