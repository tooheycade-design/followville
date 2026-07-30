# Followville river chapter: population 501–750

Status: implemented as a deterministic, unreleased Day 28 plan. The canonical
Day 27 `world_state.json`, Blend, GLBs, claims, and Supabase rows remain
unchanged until the guarded Day 28 growth is intentionally run.

## Day 28 boundary

- Current population: 500.
- Day 28 target: 528.
- Existing reserve addresses 357–366 finish Summit Court in North Ridge.
- New addresses 367–384 are the first eighteen Rivergate homes on Crossing
  Way, east of the river.
- The full approved reserve is addresses 367–616: 250 homes that take the city
  from population 500 to population 750.
- Ordinary growth never falls back to the legacy lot scanner before address
  616.

## Permanent geography

The river follows a broad north/south line beyond the completed Day 27 eastern
edge. Its visible channel is approximately 28 metres wide, with a protected
30-metre riparian housing setback. The terrain is physically carved into one
continuous river valley; the water is not a flat decal laid over grass.

The original eastern skyline mountains remain unchanged beneath every existing
building through x=320, then feather into the river valley. Replacement eastern
peaks move beyond the new neighborhoods, expanding the regional terrain without
moving any existing address or building.

Founders Crossing is the first permanent crossing. It begins at completed
Summit Court, descends at less than a ten-percent grade, clears the river by
more than seven metres, and lands directly at Crossing Way. It includes:

- a continuous solid deck and road surface;
- two continuous guard rails plus repeated vertical posts;
- three structural piers;
- an east-bank Rivergate gateway;
- exact browser walk-surface heights;
- water collision that remains active everywhere except on the raised bridge.

The river, bridge, banks, riverwalks, and riparian planting appear only when
address 367 exists. They add no population, claimable row, or fake building
record.

## Planned districts

| Plan IDs | District | Streets | Homes |
|---|---|---|---:|
| 367–414 | Rivergate | Crossing Way, Rivergate Drive | 48 |
| 415–472 | Cedarbank | Cedarbank Lane, Alder Court | 58 |
| 473–526 | Timber Bend | Timber Bend Road, Lodgepole Loop | 54 |
| 527–584 | Eastbank Village | Millstone Way, Ferry Street | 58 |
| 585–616 | River Meadows | Marshlight Lane, Heron Reach | 32 |

The sequence deliberately moves from the bridge landing north through the
wooded bank, then into a modest village center, before finishing in the
lower-density southern meadows. This keeps daily growth visually contiguous
instead of scattering houses across the entire eastern reserve.

## River-house architecture

All population 501–750 homes use an eight-design river-house library rather
than the existing suburban library. They remain ordinary claimable `house`
records so ownership, stable URLs, claims, customization, map search, and
Supabase behavior do not fork into a second housing system.

The shared visual language is:

- timber/log wall bands that project physically from the wall;
- steep dark roofs;
- stone bases and chimneys;
- deep covered decks with timber posts and beams;
- large front and rear river-facing glazing;
- compact evergreens and natural-color palettes.

The assets keep the existing suburban lot envelope and material prefixes, so
homeowner wall/roof/door customization and browser hitboxes continue to work.
The complete 250-home reserve has a larger minimum spacing than the earlier
plan and passes oriented-footprint checks with no collisions.

## Reveal and reusable cameras

`--cam day28reveal` is a prepared 20-second portrait sequence:

1. the ten Summit Court homes rise and complete the original 500-home plan;
2. the river valley, water, riverwalks, planting, and bridge rise;
3. Crossing Way forms as the camera crosses toward Rivergate;
4. the eighteen timber homes rise along the new road;
5. the final drone composition holds old city, river, bridge, and new district.

Two finished-scene audit/showcase cameras are reusable:

- `--cam riverdrone` — twelve-second aerial river and crossing showcase.
- `--cam riverbridge` — twelve-second first-person-height bridge approach.

`--cam newstreet` automatically selects Crossing Way on Day 28 because it is
the latest day's largest street group.

## Required release checks

Before production growth or deployment:

1. Run `python3 neighborhood_plan.py`.
2. Run `python3 check_downtown_visuals.py`.
3. Simulate `+28` against a temporary copy of `world_state.json`.
4. Render and inspect Day 28 final drone, bridge-height, and `newstreet` views.
5. Run a replay/export against temporary output and validate full/streamed GLBs.
6. Run the browser suite, including bridge walking, water blocking, maps, home
   hitboxes, claims, and mobile controls.
7. Refresh the embedded generator in the authoritative Blend only through the
   guarded workflow.
8. Run the production `+28` from clean, synchronized `main`, then verify the
   exact 28 insert-only Supabase rows and unchanged pre-existing claims.
