# Followville suburban reserve: houses 135-500

Implemented 2026-07-11 for Cade. This is a permanent deterministic plan for
the next 366 ordinary houses. It changes no existing building or road.

## Behavior

- `neighborhood_plan.py` owns all 366 exact addresses, street assignments,
  rotations, road dependencies, district counts, and visible terrain features.
- Future plan data creates no Blender object by itself.
- Ordinary `+N` growth consumes the next N addresses in sequence.
- A short road segment appears only when its dependent house exists.
- Cul-de-sac bulbs appear only near the end of their street's buildout.
- Terrain is visible immediately. It consists of undeveloped hills, meadows,
  and ponds outside the Day-9 footprint.
- Existing houses, founder buildings, the Day-7 pond, the Day-8 circular park,
  and every existing grid road remain fixed.
- The old population-500 plaza is suppressed when this reserve completes;
  Cade specified that the 366 additions are houses only.
- After address 366, ordinary growth falls back to the legacy lot system unless
  a new reserve is approved and added.

## District sequence

| Sequence | District | Houses |
|---|---|---:|
| 1-54 | Creekside Bend | 54 |
| 55-116 | Willow Hills | 62 |
| 117-184 | Twin Oaks | 68 |
| 185-260 | Meadow Run | 76 |
| 261-318 | Pine Hollow | 58 |
| 319-366 | North Ridge | 48 |

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
366-house total, district totals, and minimum spacing between planned houses.
The GitHub Action runs the same validation on pushes to `main`.

Before changing the plan, also simulate small, boundary, and complete batches
(for example +10, +54, +60, and +366) against a copy of `world_state.json`.
Never test a future batch against the canonical state file.
