# Followville river chapter: population 501–750

Status: Day 30 released at population 605 through plan ID/address 461. The
deterministic reserve continues through population 750; address 462 is next.

## Day 30 boundary and Cedarbank progress

- Day 30 grew from population 559 to 605 with exactly 46 ordinary claimable
  homes, taking total world records from 620 to 666 without adding a landmark.
- Plan IDs 416-444 added the remaining 29 Cedarbank Lane homes, completing its
  30-home run when combined with Day 29's plan ID 415.
- Plan IDs 445-461 opened Alder Court with 17 of its 28 homes. Plan IDs
  462-472 are the eleven Cedarbank homes still reserved before Timber Bend.
- Seeds 621-666 belong to the Day 30 homes. `--cam day30reveal` is the prepared
  18-second low-downtown flight into all 46 Cedarbank home rises.

## Day 29 boundary and rafting destination

- Day 29 target is population 559: exactly 31 new ordinary claimable homes.
- Plan IDs 385-414 place 30 homes on Rivergate Drive; plan ID 415 opens
  Cedarbank Lane with one home.
- The non-population River Run Outfitters landmark sits on the west/city bank
  at Blender `(330,-30)`, clear of every existing and reserved home.
- A terrain-following access road joins Kaleidoscope Crest to its retained
  terrace. A descending boardwalk reaches a T-shaped dock with a launch raft;
  a stored raft, visible life jackets/paddles, and authored rapids establish
  the destination from first-person and drone views.
- `--cam day29reveal` is an 18-second portrait flight: approximately three
  seconds orbiting the full city/downtown, a transfer to all 31 home rises,
  then the rafting outpost appears last.

## Day 28 boundary

- Starting population: 500.
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

| Plan IDs | District | Streets | Homes | Built through Day 30 |
|---|---|---|---:|---:|
| 367–414 | Rivergate | Crossing Way, Rivergate Drive | 48 | 48 |
| 415–472 | Cedarbank | Cedarbank Lane, Alder Court | 58 | 47 |
| 473–526 | Timber Bend | Timber Bend Road, Lodgepole Loop | 54 | 0 |
| 527–584 | Eastbank Village | Millstone Way, Ferry Street | 58 | 0 |
| 585–616 | River Meadows | Marshlight Lane, Heron Reach | 32 | 0 |

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

The current growth-reveal camera is `--cam day30reveal`: an eighteen-second
low-downtown approach followed by the 46 Cedarbank home rises and an Alder
Court finishing hold.

`--cam newstreet` automatically selects Crossing Way on Day 28 because it is
the latest day's largest street group.

## Required checks for future river-district growth

Before production growth or deployment:

1. Run `python3 neighborhood_plan.py`.
2. Run `python3 check_downtown_visuals.py`.
3. Simulate the requested growth against a temporary copy of
   `world_state.json`.
4. Render and inspect the requested reveal plus river, bridge-height, and
   `newstreet` views as applicable.
5. Run a replay/export against temporary output and validate full/streamed GLBs.
6. Run the browser suite, including bridge walking, water blocking, maps, home
   hitboxes, claims, and mobile controls.
7. Refresh the embedded generator in the authoritative Blend only through the
   guarded workflow.
8. Run the production growth from clean, synchronized `main`, then verify the
   exact insert-only Supabase rows and unchanged pre-existing claims.
