# Prompt: the Followville highway system

Hand this whole file to the AI taking the job. It is written to be pasted as a
prompt, not skimmed as background.

---

## The job

Followville has a town's worth of streets and one lonely elevated expressway
that starts nowhere and stops nowhere. **Design and build a real highway
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

**"It can be a big highway" is explicit permission to be ambitious.** Do not
deliver a timid two-kilometre stub because it was cheaper. Do not deliver
spaghetti either — the test is whether a traffic engineer would nod at it.

`CLAUDE.md` is the operating manual and overrides anything here. Read it first,
then `METROPOLITAN_EXPANSION_PLAN.md` (the expressway's original spec) and
`world_layout.py`'s declaration blocks.

## Read the numbers from source, not from this file

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_toolchain.py
```

As of writing, `world_state.json` is **day 49, population 2,512, 2,500
buildings**, and the plan holds **5,251 road segments of which 3,691 are
revealed**. Verify before doing anything.

---

## This is a `replay` job, not a growth

Read this twice, because it changes everything about how you work.

**Road geometry is not stored in `world_state.json`.** It is generated at build
time from `neighborhood_plan.PLAN["roads"]`, `metropolitan_plan`, and the
authored point-lists in `world_layout.py`. So upgrading roads means changing
the *generator*, then re-exporting — it does not mean growing the city.

```text
grow_windows.bat --preflight-only
grow_windows.bat replay
```

`replay` **never changes `world_state.json`**. It refreshes the exports and the
repo Blend's saved WORLD snapshot. Day and population must not move. If you
find yourself typing `+N`, stop — you have misunderstood the job.

Two consequences worth internalising:

- **No renders are needed.** Cade said no animation. That removes the 10–15
  minute render from every loop and makes this job far cheaper than a growth
  day. Your feedback loop is the browser, not Blender's renderer.
- **Preview before you touch `main`.** The guarded launcher refuses to start
  unless the repo is clean `main` matching `origin/main`, so iterate against a
  scratch state first: set `NEIGHBORHOOD_STATE_DIR` to a scratch copy of
  `world_state.json` and run Blender directly, exactly as day 49's camera work
  did. Set `FOLLOWVILLE_IMPORT_ONLY` before importing the generator for
  anything else — **importing `neighborhood_blender` in a background Blender
  session runs a growth** and has silently advanced the world before.

---

## STOP — plan before you build, and get it approved

Cade asked for this explicitly: *"It should plan it out to make sure it's like
how a real life highway system would work."*

**Do not start modifying the generator.** First produce a plan and put it in
front of Cade:

1. A route map — an overhead of the existing world with the proposed
   alignments, interchanges and termini drawn on it. Screenshot or diagram,
   not prose.
2. The hierarchy you are proposing, and which existing roads become what.
3. Interchange locations with the reason each one exists (what it serves).
4. Where every end of every new road terminates, and why that is not a cut end.
5. Roughly what it costs — how many new authored roads, how many declarations
   in `world_layout.py`, whether any terrain shelf is needed.

Then wait for his answer. He has been clear that scope calls are his.

### The questions the plan has to answer

- **Where do the two ends of the expressway go?** Today it runs y=250 to
  y=858 and simply stops at both ends. The world's built extents are
  **x −758..631, y −324..1156** — so the highway covers 608m of a 1,480m-tall
  world, stopping 312m short of the northern edge and 566m short of the
  southern one. Real highways leave town. The obvious answer is that it runs
  off the map at both ends; say so and show where the map edge is.
- **How many interchanges, and where?** There is currently **one**, a diamond
  at Crown Boulevard (y=654), for a city of 2,512 across 1.4km. Real urban
  freeways carry an interchange every 1.5–3km, and this world is smaller than
  that spacing — which means the honest number is small but it is not one.
  Whatever you propose, each interchange must serve something real: downtown,
  the Northgate/Southline grid, the West Quarter, the new North Reach.
- **Is there an east–west route?** A single north–south corridor is not a
  "system". The West Quarter (out to x=−750) currently has no highway access
  at all. If you propose a crossing route, it needs its own junction with the
  expressway — a real one, not a crossroads.
- **How much of the ordinary street network is in scope?** "Upgrade the roads"
  could mean the highway and its arterials, or it could mean re-marking 3,691
  local segments. Propose the boundary; don't assume the largest reading.

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
which used to be empty meadow and is now the western edge of the day-49 North
Reach, so the cut end is becoming visible from the new quarter. Day 49's camera
was deliberately framed to keep it off screen. That was a workaround, not a fix.

### The other road systems it has to connect to

- **Local streets** — `ROAD = 6`m, built from `neighborhood_plan.PLAN["roads"]`
  as `{a, b, reveal_at, street, district}` segments. 3,691 revealed today.
- **The Northgate arterial** — `northgate_arterial_points()`,
  `ARTERIAL_HALF_WIDTH`, `NORTHGATE_ARTERIAL_REVEAL`.
- **The metropolitan grid** — `metropolitan_plan.STREETS`, with
  `BOULEVARD_WIDTH` 14, `LOCAL_ROAD_WIDTH` 8, `SIDEWALK_WIDTH` 3.2, six
  north–south lines and five east–west.
- **The North Reach** (day 49) — five ribbons at x=−190/−120/−50/20/90 running
  north to y=1170 **and stopping in meadow**. Their east–west avenues do not
  reveal until plan_id 2345, so there are no cross streets up there yet. If
  your plan reaches north, understand that you are connecting to five loose
  ends, not to a grid.
- **Bridges** — Founders Crossing, Timber Bend Crossing. Both are declared
  raised regions; read them before you author another bridge.
- **Landmark approaches** — Station Trail and Point Road (nuclear plant),
  rafting outpost lane, City Hall approach, and others in
  `LANDMARK_APPROACHES`.

---

## What "like a real life highway system" actually demands

This is the part that separates a highway from a wide grey ribbon. A planner
would insist on all of it:

- **Hierarchy.** Freeway → arterial → collector → local. Followville today has
  locals, one boulevard grid, and a freeway, with nothing in between. Collectors
  are the missing tier and are why the current expressway feels bolted on.
- **Access control.** Nothing fronts a freeway. No driveway, no house, no
  direct local-street connection — access happens only at interchanges. Check
  every new alignment against `HOUSE_ROAD_CLEARANCE` and the existing houses;
  **existing geometry never moves**, so the road yields, not the houses.
- **Ramps that work.** Acceleration and deceleration lanes with real tapers,
  grade limits (the four existing ramps are already grade-limited — match
  them), and enough weaving distance between successive ramps.
- **Termini that are not cut ends.** Every end of every road must be an
  interchange, a surface intersection, a turnaround, or an exit off the map.
  "It fades into the meadow" is the defect you were hired to fix; do not
  introduce four more of them.
- **Continuity of the crossing streets.** Where the freeway crosses an existing
  street, that street either passes under with clearance, passes over, or is
  properly terminated. It may not simply stop at the embankment.
- **Markings, barriers, shoulders, signs.** Lane lines, edge lines, gore
  striping at ramps, median barrier, gantries at decision points.
- **Lighting** — see below.

**High quality low poly** is the house style, not an excuse for crude work.
Match the existing pastel palette and the way `build_metro_tower()` and the
suburban shells are built: flat colours, clean silhouettes, no textures, real
geometry rather than painted-on detail.

---

## Vehicles

`build_car(col, seed)` already exists, and cars are placed as
`{"type": "car", "gx": 0, "gy": 0, "seed": ...}` records through
`place_instance`. Reuse it; add types if the highway needs trucks.

Cade said **no animation**, so these are static. Static vehicles are ruthless
about revealing mistakes — get these right:

- **Direction of travel.** On a divided six-lane road every vehicle on one
  carriageway faces one way and every vehicle on the other faces the opposite
  way. One car facing the wrong way ruins the shot and is the single most
  likely error.
- **Lane discipline.** Vehicles sit centred in a lane, not straddling lines,
  and follow the road's curvature and superelevation.
- **They sit on the deck, not the ground.** The expressway deck is at z=14.
  A vehicle placed at `terrain_height()` under the viaduct is a car buried in a
  field. Place off the road surface you built, and verify with
  `__followvilleTerrainQA.probe(x, z)`.
- **Spacing and variety.** Vary `seed` so the same car does not repeat down the
  lane, and vary gaps — evenly spaced cars read as a toy train.
- Collision colliders are computed automatically from structural geometry, but
  **cars keep purpose-built accurate shapes** — see `CLAUDE.md`. Don't break
  that.

## Lights

`build_streetlight(col, _seed=0)` exists, placed as `{"type": "streetlight"}`
records, e.g. `place_instance(world_col, lamp_data, "metro_streetlight")`.

**Naming matters more than you would expect.** The render-only light pools that
the sunset/night presets add attach to objects whose name contains
`suburban_light` or `metro_streetlight` (`neighborhood_blender.py`, in the
"sparse render-only light pools" pass). Name new highway lighting so it is
picked up, or it will look unlit at night and nobody will know why.

Freeway lighting is not street lighting: high-mast at interchanges, regular
spacing along the mainline, and the deck lit from its own poles rather than
from the ground 14m below.

---

## Send Cade screenshots as you go

He asked for this specifically: *"send me screenshots of the roads as it works
on them so I can watch its progress."* This is a requirement, not a courtesy.

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

- **Fix a set of camera positions at the start and reuse them every time**, so
  Cade is comparing like with like and can see progress rather than a slideshow
  of unrelated angles. An overhead of the whole corridor, one at each
  interchange, one at each terminus, one at deck level.
- Send them with **SendUserFile as you finish each milestone**, not batched at
  the end. He is watching progress, so a before/after pair beats a gallery.
- Caption what changed. "Interchange at y=654, southbound ramps rebuilt with
  taper" is useful; "screenshot 4" is not.
- Cade reads these on his phone. Prefer a few clear images over many.

---

## Rules that will bite you

- **Control points every ~3m on terrain-following roads.** `_add_road_strip`
  subdivides to 2m internally, but `walk_surface_manifest` uses the control
  points *as given*, so coarse points drift the walkable surface away from the
  visible road.
- **Declare everything.** A road with authored heights goes in
  `AUTHORED_ELEVATION_ROADS`; its footprint goes in `INTENTIONALLY_RAISED_ROADS`;
  a new landmark goes in `LANDMARK_FOOTPRINTS`. An undeclared landmark is
  reported as *unaudited*, not failed — **silence is not proof**.
- **The visible-surface depth rule is mandatory.** Never two independently
  rendered visible faces on the same plane: lane markings against the deck,
  the deck against the shoulder, barriers against the edge, signs against
  gantries. Physically separate the geometry; `polygonOffset` in the browser is
  a fallback, never a fix. Review every repeated asset head-on **and from both
  oblique sides**.
- **Level decks on slopes need `_add_retaining_skirt()`**, which samples terrain
  at every perimeter vertex. A wall on one face only holds up on level ground.
- **Try not to touch terrain at all.** If you must, `terrain_height()` in
  `downtown_visual_plan.py` and `regionalTerrainHeight` in `town.html` are the
  same surface and **change together**.
- **Aerial cameras use a 10m near clip** so thin roads don't flash. Don't
  restore Blender's 0.1m default.
- Windows PowerShell 5.1 has **no `&&`** — a parser error, not a fallback.
- Python is Blender's bundled interpreter; the `python` on PATH is a Store stub.
- `pnpm` is **not** on PATH — run `.\node_modules\.bin\playwright.cmd`.

## Checking your work

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py --self-test
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_town_glb.py
```

`check_world_geometry.py` is the one that answers "is anything off the ground,
on a road, or in the street" — the class of defect this job can most easily
introduce. Read the self-test's own output for the count rather than trusting a
number written in prose.

Then `pnpm test:e2e` locally (via the playwright binary above). Expect two
tests to be **already red for reasons that predate you**: the map street count
(the map counts the Crown Quarter tower as a home, red since day 48) and the
Day 28 river centreline (11 vs 15, red since 2026-08-12). Do not "fix" your
work to chase those. Do take seriously any *new* failure, especially the
Timber Bend crossing test — it went red once because a state/manifest mismatch
had emptied the walk-surface manifest 400m away.

In CI, read the **`check`** job. A red **`browser`** job is not evidence of a
defect — it has been red on nearly every run for months on GitHub's shared
runners and the failing set changes run to run on identical code.

## Definition of done

- The Crown Expressway upgraded and no longer terminating in mid-air at either
  end, with the `METROPOLITAN_EXPANSION_PLAN.md` spec updated to describe what
  is actually built.
- A highway *system*: the approved interchanges, the missing collector tier,
  and every new alignment connected to the existing network — nothing ending
  in a field.
- Vehicles on the mainline, facing the right way, sitting on the deck.
- Lighting named so the sunset and night presets pick it up.
- Both audits green, CI `check` green, `world_state.json` **unchanged** (same
  day, same population, same building count).
- Screenshots delivered to Cade throughout, not just at the end.
- One line in `TEAM_LOG.md`, newest at the top, tagged `[WORLD]`, signed with
  who and which AI.

## Absolute rules

- **Never edit `world_state.json`.** This job does not change it at all. Back
  it up before anything risky anyway.
- **Existing geometry never moves.** The road yields to the houses.
- Growth and replay both go through the **guarded launcher**.
- `git fetch` and re-read shared files immediately before editing — Codex and
  Claude run on this repo concurrently, and the conflict will be in whatever
  file you were both told to change.

## One loose end you inherit

The North Reach's five streets run north to y=1170 and stop, because their
cross streets do not reveal until plan_id 2345. That is correct behaviour for a
growing town and **not yours to fix** — but if your highway reaches north, do
not accidentally imply those stubs are finished roads. Ask Cade before tying
anything permanent into them.
