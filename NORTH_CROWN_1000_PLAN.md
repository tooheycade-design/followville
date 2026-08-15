# North Crown — 1,000-home planning proposal

Status: **review proposal only**. This file does not add an address, road,
terrain shelf, object, or follower to the authoritative city. It is the plan to
approve or revise before implementation.

## Planning decision

North Crown is the next northern layer of the same city. Its first property
line starts at `y=826`, exactly where the West Quarter terrace and Crown
Quarter streets finish. It does not begin after an empty buffer.

- overall envelope: `x=-766..190`, `y=826..1,404`;
- Crown Quarter immediately south-east: `x=-260..278`, `y=486..824`;
- West Quarter immediately south-west: `x=-766..-180`, `y=404..826`;
- Crown Expressway continues north on its existing `x=222` alignment;
- the river stays east of the expressway and outside the neighborhoods.

## Regional and main roads

### Crown Expressway extension and North Crown exit

- Continue the six-lane elevated expressway from `y=858` to `y=1,465`.
- Add a second grade-separated diamond interchange centered at `y=930`.
- This keeps 276 m between the Crown Boulevard and North Crown interchanges.
- The expressway continues beyond the district; it does not terminate here.

### North Crown Parkway

- centerline: `(-766,930)` to `(278,930)`;
- 16 m paved width: two 3.25 m lanes each way and a 3.0 m planted median;
- 3.2 m sidewalks, street trees, bus bays, and protected turn pockets;
- no house driveway opens directly onto the parkway;
- signals at `x=-680, -540, -400, -260, -120, 20, 160`;
- `x=-260` continues Forge Avenue; `x=-120,20,160` continue Crown streets;
- west of `x=-680`, it becomes a two-lane landscaped collector and bends into
  the existing outer network instead of ending as unexplained asphalt.

## Local street structure and capacity

Seven parkway junctions divide the district into short neighborhoods. Public
roads use 8 m collectors and 6 m local streets with continuous sidewalks.
Curved loops and offset T-junctions prevent an uninterrupted grid.

| Neighborhood | Envelope (metres) | Homes | Street character |
| --- | --- | ---: | --- |
| Harrow North | `x=-766..-548`, `y=826..1,404` | 206 | West Quarter avenues continue into two loops and short closes. |
| Forge Park | `x=-548..-258`, `y=826..1,404`, less campus | 214 | Dense seam blocks, crescents, central park, apartment edge. |
| Crown Gardens | `x=-258..-48`, `y=826..1,404` | 224 | Short urban blocks nearest downtown, then paired loops. |
| Maple North | `x=-48..92`, `y=826..1,404` | 186 | Offset T-streets around a school/park reserve. |
| Anvil Meadows | `x=92..190`, `y=826..1,404` | 170 | Compact neighborhood between downtown and expressway greenway. |
| **Total** |  | **1,000** |  |

These district totals are fixed. Implementation must calibrate individual
street seats through the real placer until it produces exactly 1,000 valid
homes with full footprints and intersection clearances.

## North Crown Residences — gated apartment campus

- envelope: `x=-468..-268`, `y=952..1,210`;
- staffed main gate: `(-368,952)`, directly north of the parkway;
- emergency/service gate near `(-468,1,092)`;
- low masonry wall, open metal fence, hedges, and pedestrian gates;
- private 6 m loop, raised crossings, sidewalks, visitor bays, bike parking,
  service courts, carports, and a leasing building;
- 20 buildings: five of each of four reviewed types;
- four landscape courts rather than a parking-dominated superblock;
- pool court centered near `(-368,1,045)`, behind the south-central building
  when entering through the main gate;
- real basin, separated water, coping, deck, shade, loungers, fence, pool
  house, and planted buffer;
- six storeys on the parkway edge stepping to four beside houses.

The campus is across the parkway from Crown Quarter and touches Forge Park and
Crown Gardens. It is the density transition between downtown and houses.

## Four apartment types for review

1. **Parkline** — four-storey pastel bar, recessed center, balconies, lantern.
2. **Gable Court** — four-storey twin-gable building with residential roofline.
3. **Terrace House** — six-storey boulevard building stepping to four storeys.
4. **Corner Lodge** — five-storey L-shaped building with a glazed lobby.

The isolated pack comes from
`scripts/build_north_crown_apartment_prototypes.py`. It never opens or saves
`neighborhood.blend` and refuses canonical output paths.

## Terrain and grading

- Extend the current terrain beyond its `y=920` edge before roads or lots.
- Continue the 5.00 m engineered Crown/West datum through the dense seam.
- Begin a gentle rise only beyond about `y=1,080`, capped at driveable grade.
- Cut/fill blocks continuously; never put individual houses on blocks/stilts.
- Level only the campus, pool, and declared civic pads; use full retaining
  skirts sampled around every level perimeter.
- Change Blender terrain and its browser port together, and prove existing
  geometry did not move beyond project tolerance.

## Road-quality requirements

- Centerline controls about every 3 m for visible/walk-surface agreement.
- Continuous mitered parkway; median openings only at signed intersections.
- Mast-arm signals, opposing heads, stop bars, crossings, curb ramps, lane
  arrows, refuge areas, and physically separated markings.
- Houses face local roads and do not front the parkway.
- Paired bus stops at the campus, Crown Gardens, Forge Park, and Harrow North.
- Declare the expressway, ramps, parkway, campus, and approaches in
  `world_layout.py` during canonical integration.

## Approval gates

1. Approve/revise the site, roads, campus, and four apartment types.
2. Calibrate all 1,000 exact address points in a pure-data plan.
3. Simulate the full chapter against copies of state and Blend only.
4. Audit visible surfaces and inspect every repeated type front and obliques.
5. Implement in milestones, running world geometry and self-tests after road
   and terrain changes, then GLB/browser verification before any push.

