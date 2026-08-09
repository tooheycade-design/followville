# Followville deterministic neighborhood reserve

The original 366-address reserve was implemented 2026-07-11. The approved
river chapter extends the same deterministic system by 250 addresses,
367-616, carrying population 500 to 750. See `RIVER_EXPANSION_PLAN.md`.
Chapter three adds addresses 617-1126 on a gridded quarter north of the
town -- see "Chapter three" below, and note that ten of those addresses are
deliberately not houses.

Current progress: addresses 1-576 are built through Day 34 (population 720).
The permanent Followville First Alert Weather station is a separate civic
landmark record and does not consume an address or change population; address
577 remains next.
Day 15 added addresses 111-115 plus ten separate Kaleidoscope Crest
`storybookhouse` feature homes; those feature homes do not consume ordinary
reserve addresses. Day 16 consumed addresses 116-128, completing Willow Hills
and beginning Twin Oaks. Day 17 consumed addresses 129-157, continuing Twin
Oaks Drive and opening Acorn Court. Day 18 consumed addresses 158-177,
finishing Acorn Court and opening Lantern Court. Day 19 consumed addresses
178-187, finishing Lantern Court and Twin Oaks before opening Meadow Run.
Days 20-27 consumed addresses 188-356, completing Meadow Run, Pine Hollow,
and the first 38 North Ridge homes. Day 28 consumed addresses 357-384,
finishing North Ridge and opening Rivergate across Founders Crossing. Day 29
consumed addresses 385-415, finishing Rivergate and opening Cedarbank Lane.
Day 30 consumed addresses 416-461, finishing Cedarbank Lane and building the
first 17 Alder Court homes. Day 31 consumed addresses 462-481, finishing the
eleven remaining Alder Court homes and opening Timber Bend Road with nine
homes. Day 32 consumed addresses 482-512: nineteen finished Timber Bend Road
and twelve opened Lodgepole Loop. Day 33 consumed addresses 513-545: fourteen
finished Lodgepole Loop and nineteen opened Eastbank Village's Millstone Way.
Day 34 consumed addresses 546-576: eleven finished Millstone Way and twenty
opened Ferry Street. Address 577 is next.

## Behavior

- `neighborhood_plan.py` owns every exact address, street assignment, rotation,
  road dependency, district count, and visible terrain feature. Read the total
  from `HOUSE_CAPACITY`, which is derived from `STREETS`, not from any number
  written in prose here: how many addresses a street can seat depends on how
  much room its specials take, and a hand-kept figure goes stale the moment a
  clearance changes.
- Future plan data creates no Blender object by itself.
- Ordinary `+N` growth consumes the next N addresses in sequence.
- A short road segment appears only when its dependent house exists.
- Cul-de-sac bulbs appear only when the final connecting road segment exists.
- Every planned house is checked against all 28 streets and turnarounds, faces
  its own road, and keeps a safe setback from every other road.
- Each visible street is generated as one continuous shared-vertex road ribbon,
  so bends and T-junctions cannot develop gaps between separate road pieces.
- New-neighborhood roads use the established town's width, asphalt material,
  height, and eight-metre yellow center-dash rhythm.
- Regional terrain remains continuous. River water, banks, bridge, riverwalks,
  and riparian planting reveal with address 367.
- Existing houses, founder buildings, the Day-7 pond, the Day-8 circular park,
  and every existing grid road remain fixed.
- The old population-500 plaza is suppressed when this reserve completes;
  Cade specified that the 366 additions are houses only.
- Ordinary growth stays deterministic through address 616. It must not fall
  back to the legacy lot system before population 750.

## District sequence

| Sequence | District | Houses |
|---|---|---:|
| 1-54 | Creekside Bend | 54 (complete) |
| 55-116 | Willow Hills | 62 (complete) |
| 117-184 | Twin Oaks | 68 (complete) |
| 185-260 | Meadow Run | 76 (complete) |
| 261-318 | Pine Hollow | 58 (complete) |
| 319-366 | North Ridge | 48 (complete) |
| 367-414 | Rivergate | 48 (complete) |
| 415-472 | Cedarbank | 58 (complete) |
| 473-526 | Timber Bend | 54 (complete) |
| 527-584 | Eastbank Village | 58 (50 built; 8 remain) |
| 585-616 | River Meadows | 32 (not started) |

## Chapter three: the Northgate quarter (addresses 617 onward)

A rectilinear grid on open ground north of everything built, sitting on a level
terrace at 5.00m in `downtown_visual_plan.terrain_height`. Six avenues 36m
apart (y=306 to y=486) crossed by five short streets 70m apart (x=-120 to
x=160). `culdesac=False` on all thirteen: a grid street ends on another street,
and a turning circle there would be a roundabout dropped in a junction.

**Ten of these addresses are not houses.** They are consumed in the same order
as everything else, so `+60 followers` still means "the next sixty addresses
appear" -- one of them just happens to be a filling station. The reserved types
are 2 filling stations, 2 diners, the grocery, the school, the fire station,
2 parks and a pond.

Specials are declared by a fraction ALONG their street, not by address index.
An index-keyed special moves every time the counts are re-solved, and one
declared past the end of a shortened street used to disappear without a word.

**Size decides which street a special can stand on.** Avenues are 36m apart, so
the deepest thing that fits between two of them is about 14m half-depth once
both kerbs are respected. That takes the filling station, the diner, the pond
and the park. It rejects the school (28.4m), Follow Mart (34m) and the fire
station (36m) at ANY setback -- 36m of building does not fit in a 36m block --
so those three stand on the two OUTER faces, where the ground is open: the fire
station on Northgate Avenue's town side, Follow Mart and the school along
Kettle Row's northern edge.

Each address is set back so its own front edge lands 5.20m from its road
centreline, whatever its size. That figure is not free: once a type is declared
in `world_layout.LANDMARK_FOOTPRINTS`, `check_world_geometry` holds it to 2.0m
beyond the road's 3.0m half-width.

### The Northgate arterial

The quarter's road connection to downtown, revealed with address 617. It leaves
the downtown grid at the crossroads of the x=-93 and y=87 streets and runs
220m north onto the Northgate Avenue centreline -- real junctions at both ends.
Its centreline is declared once, in `neighborhood_plan.NORTHGATE_ARTERIAL`, and
read by the generator, the browser walk surface and `check_world_geometry`, so
there are no copies to drift.

Do not restore the 2026-08-09 east-west highway along y=272 (commit `8689593`).
It connected to nothing at either end, and it ran through Willow Hills and
Creekside Bend: it had been cleared against the reserve's RAW coordinates,
where Creekside Bend's houses look 58m further south than they actually stand.
`build_plan()` now compares chapter three in WORLD metres for that reason.

## Safe daily operation

Use the normal growth command. There is no special suburban flag:

```text
grow_windows.bat +N --render
./grow.sh +N --render
```

The state records only addresses that have actually appeared. Planned future
houses and roads never enter `world_state.json`, `town.glb`, Blender renders,
or the website.

## Validation

Run `python neighborhood_plan.py`. It verifies continuous IDs, district totals,
minimum spacing, road setbacks, cul-de-sac clearance, and that every front door
faces its assigned street.

It also runs `_validate_footprints()`, which measures the ground each address
actually covers rather than the distance between address POINTS. That
distinction is the whole of the 2026-08-09 defect: every point-based check
passed while fourteen houses stood inside the fire station and six of the ten
specials had a road running through them. It checks footprint overlap between
any pair involving a special, every special against every road centreline,
every chapter-three address against the arterial, and that a civic pad's ground
does not fall more than `MAX_SPECIAL_PAD_FALL` across its own footprint.

Houses in DIFFERENT districts are compared in world metres, not raw plan
coordinates. Districts are rigid render-time offsets, so two addresses can be
58m apart in the raw numbers and standing on each other in the town.

The GitHub Action runs the same validation on pushes to `main`.

`check_town_glb.py` also verifies that every built planned house still matches
its validated address and rotation, preventing state drift after future edits.

Before changing the plan, also simulate small, boundary, and complete batches
(for example +10, +28, +48, +250) against a copy of `world_state.json`.
Never test a future batch against the canonical state file.
