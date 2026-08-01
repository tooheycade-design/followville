# Followville deterministic neighborhood reserve: houses 135-750

The original 366-address reserve was implemented 2026-07-11. The approved
river chapter extends the same deterministic system by 250 addresses,
367-616, carrying population 500 to 750. See `RIVER_EXPANSION_PLAN.md`.

Current progress: addresses 1-481 are built through Day 31 (population 625).
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
homes. Address 482 is next.

## Behavior

- `neighborhood_plan.py` owns all 616 exact addresses, street assignments,
  rotations, road dependencies, district counts, and visible terrain features.
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
| 473-526 | Timber Bend | 54 (9 built; 45 remain) |
| 527-584 | Eastbank Village | 58 (not started) |
| 585-616 | River Meadows | 32 (not started) |

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

Run `python neighborhood_plan.py`. It verifies continuous IDs, the exact
616-house total, district totals, minimum spacing, road setbacks, cul-de-sac
clearance, and that every front door faces its assigned street.
The GitHub Action runs the same validation on pushes to `main`.

`check_town_glb.py` also verifies that every built planned house still matches
its validated address and rotation, preventing state drift after future edits.

Before changing the plan, also simulate small, boundary, and complete batches
(for example +10, +28, +48, +250) against a copy of `world_state.json`.
Never test a future batch against the canonical state file.
