# Followville highway system — plan

Written 2026-08-20 against Day 49 / population 2,512 / 2,500 buildings /
plan_id 2301, before any geometry existed, and revised after building it. Every
figure was measured from `world_state.json`, `neighborhood_plan.PLAN`,
`metropolitan_plan.py` and `downtown_visual_plan.TERRAIN_BOUNDS`, not copied
from prose. Where building the thing changed the design, the change is recorded
here rather than left as a document describing a city that was not built —
§9 lists every one.

This covers the **freeway and collector tiers only**. It changes no house, no
local street, no landmark and no terrain. `world_state.json` is untouched: day,
population and building count are identical before and after.

The data lives in `highway_plan.py`; `neighborhood_blender.build_highway_system`
turns it into geometry, `world_layout` walks it, and `check_world_geometry`
audits it. Nothing in the generator decides where a road goes.

The route map that goes with this document is `highway_plan_routemap.png`,
drawn from `world_state.json` and the reserve rather than traced by hand. It is
not committed — the repo gitignores `*.png` to stay light for GitHub Pages — so
it travels with the plan rather than in it.

---

## 1. What was there, measured

The Crown Expressway was a 24m six-lane elevated deck at x=222.0, z=14.0,
running y=250 → 858, with one diamond interchange at Crown Boulevard (y=654)
and four ramps. It reveals with the first Crown Quarter tower, of which exactly
one is built (metro_id 1, 11 residents).

Seven defects, all measured:

1. **Both ends stopped in mid-air.** `METROPOLITAN_EXPANSION_PLAN.md` says the
   road "continues beyond the district in both directions visually; it does not
   terminate at the towers." It terminated. The northern cut end at (222, 858)
   is 34m from Crown Fields' southern edge and was becoming visible from the
   Day 49 North Reach; Day 49's camera was framed to keep it off screen, which
   is a workaround, not a fix.
2. **Six built streets dead-ended under the viaduct.** Northgate Avenue
   (y=306), Foundry Street (342), Lantern Row (378), Southline Avenue (414),
   Millrace Street (450) and Kettle Row (486) all stop at x=210.0. The
   viaduct's structure edge is at x=209.1, so each of those six ends is 0.9m
   *inside* the structure's footprint, with no junction and nothing beyond.
3. **The four ramps were named for the opposite direction to their geometry.**
   `ramp_plan()`'s "southbound-off" occupies the south-west quadrant and runs
   from the deck at y=586 up to the terminal at y=654 — that is the southbound
   *entrance*. All four names were inverted. The diamond itself was correctly
   shaped; only the labels lied, and they would have sent every vehicle placed
   by name the wrong way.
4. **The ramps left from mid-carriageway**, diverging at x=215.5 and x=228.5.
   The carriageways run x 209.95→222.0 and 222.0→234.05 with edge lines at
   x=211 and x=233. A ramp should leave from the outside shoulder.
5. **The outside barriers ran unbroken for all 608m**, including across the
   four ramp gores, so the ramps passed beneath a barrier with no opening.
6. **No tapers.** Each ramp met the deck at a point — no acceleration or
   deceleration lane, no gore striping. The four existing ramps drop 8.8m in
   74m, an 11.9% grade.
7. **The deck lighting was invisible to the night presets.**
   `_build_video_practicals()` selects fixtures whose object name contains
   `suburban_light` or `metro_streetlight`, or whose collection contains
   `ast_light`. The viaduct's lights were raw boxes named
   `metro_expressway_light*`, matching none of them. The emissive material
   `FV_expressway_light_warm` *is* handled in `apply_mood()`, so the lamp heads
   glowed but cast no pool — the viaduct looked unlit at night with no obvious
   cause.

And one system-level defect: **one interchange** served a city heading for
2,512 residents plus 1,900 tower residents plus 870 planned houses.

---

## 2. The city this is designed for

Not today's 2,512. The deterministic reserve, read from source:

| Reserve | Where | Size |
| --- | --- | --- |
| 19 unbuilt Crown Quarter towers | x −158..125, y 553..755 | 1,900 residents |
| Crown Fields (ch. 5) | x −174..182, y 834..1189 | 487 addresses |
| Kestrel Downs (ch. 5) | x −772..−531, y 820..1153 | 255 addresses |
| Gatehouse Green (ch. 5) | x −516..−212, y 820..926 | 128 addresses |
| Unbuilt road segments | x −750..160, y 810..1170 | 1,560 segments |

Built extents today: x −758.5..631.2, y −323.9..1156.0.
Modelled world (`TERRAIN_BOUNDS`): **x −960..800, y −360..1280.** That is the
map edge, and it is where "off the map" means. Beyond it the terrain mesh
closes with a vertical skirt down to the background slabs at z=−0.10.

The demand that shapes this plan: the tower field at x −158..125, y 553..755 is
the future downtown core — 2,000 residents in twenty towers — and it sits
immediately west of the expressway. Meanwhile Kestrel Downs and Gatehouse
Green, 383 planned homes, were 1,000m from any highway.

---

## 3. The routes

Two routes: a north–south spine through the city, and a ring around the outside
of it. Between them they touch every district that exists or is reserved, and
they leave the modelled world at two map edges.

### F-1 — Crown Expressway (north–south spine), 1,168m, 560m of it new

| Section | Extent | Form |
| --- | --- | --- |
| Crown Approach (new) | (112, 56) → (222, 250) | at grade rising to the deck, 14m opening to 24m |
| Existing viaduct (upgraded) | y 250 → 858 at x=222 | elevated deck z=14.0, 24m |
| North extension (new) | y 858 → (300, 1176) | descends at 5.0%, at grade from y=1082, bending east to x=300 |

**Southern terminus: a T-junction with the Kaleidoscope Crest access road at
(112, 56)**, which runs west to downtown at (87, 33) and east onto the Crest.
The approach is a cubic with both tangents fixed: it leaves the junction at 80°
against a road running at 32°, so the two cross at 48° instead of running
alongside each other, and it arrives at (222, 250) pointing due north, tangent
to the viaduct it becomes. Constant 6.04% grade over 230m; the tightest radius
is 106m, which is a transition-section number, not a mainline one.

**The expressway cannot be extended south past y≈250, and this is measured,
not assumed.** The Food Court stands 38m south-south-east of the old cut end:
its nearest home is at (232.1, 212.7), 10.1m off the x=222 centreline, where
the viaduct's structure alone is 12.9m half-width. Clearing it westward from a
terminus fixed at (222, 250) needs a horizontal radius of **73m** — a 30 km/h
curve. Eastward is worse: the Food Court is 68m wide (x 238..306) and the next
clear band is x 318..414, a 108m shift in 70m. There is no southern freeway
alignment out of that terminus at any grade.

So the mainline does what a real freeway does when it runs out of room: it
comes down. It holds the 14m arterial width past the Food Court and the East
Woods reserve — 9.07m of edge clearance at the closer of the two — and only
flares to the full 24m deck at y=228, north of everything it has to thread.

**Northern terminus: the IC-4 trumpet, where F-1 ends at the Ring Freeway.**
The extension bends 78m east above IC-3, on a 340m radius. That bend is not
decoration: at x=222 the two south-western quadrants of the ring junction are
40m from Crown Fields' reserve and every ramp that needs them runs through
reserved addresses. At x=300 the nearest reserved address is 131m away and all
four quadrants are open meadow.

F-1 could not both cross the ring and reach the map edge. It is on the ground
after its 5% descent and has 66m left before y=1280, which is nowhere near
enough to climb over a freeway and come back down; the alternative — leaving
the modelled world 7m in the air on a stub — is the same defect this job exists
to fix. Ending at a system interchange is a real terminus, and the ring carries
the regional connection out of the world instead, twice.

### F-2 — Followville Ring Freeway, 3,229m, at grade

| Leg | Extent | Terrain |
| --- | --- | --- |
| North | (800, 1214) → (16, 1214) → (−240, 1252) → NW corner | z 3.2..5.3 |
| West | (−830, 1212) → (−830, −360) | z 0.0..5.3 |

**Eastern terminus: the map edge at x=800. Southern terminus: the map edge at
y=−360.** Both at grade.

The north leg does not run straight. **The North Crown Campus** stands at
(−370, 1088) with a declared 200 × 280m footprint, so its northern edge is at
y=1228 — fourteen metres north of where the ring wanted to be. The campus is
built and cannot move, so the freeway does: it holds y=1252 from the north-west
corner across to x=−240, clearing the campus by 12m at the deck edge, then eases
back to y=1214 over a 200m transition and runs straight to the eastern map
edge. It clears the northernmost planned address — the Crown Fields elementary
school at (−22.9, 1189.4) — by 16.9m, and the westernmost — a Kestrel Downs
Followmart at (−772.2, 961.1) — by 44.9m.

The ring is at grade throughout because it runs entirely through open meadow
and the terrain along both legs is gentle. Elevating it would be a 3.2km
viaduct with nothing underneath it. It carries structure in exactly two places:
the IC-4 overpass, and a **level causeway from x=330 to x=400** across the
river channel's northern remnant, a 1.2m swale whose sides pitch at 8%. The
causeway sits at the height of its own two shoulders, so its profile meets the
terrain exactly at both ends and has no kink at all.

---

## 4. Interchanges

Six, plus the southern terminal junction. Every one lands on a road that is
**built today** — none tie into the reserve's unbuilt streets.

| # | Name | On | At | Type | Serves |
| --- | --- | --- | --- | --- | --- |
| IC-1 | Northgate | F-1 | y=396 | diamond | Northgate + Southline, via East Line Road |
| IC-2 | Crown Boulevard | F-1 | y=654 | diamond (existing, rebuilt) | Crown Quarter, 20 towers |
| IC-3 | Crown Fields | F-1 | y=920 | diamond | Crown Fields, via East Line Road North |
| IC-4 | Ring | F-1 × F-2 | (300, 1214) | trumpet | freeway to freeway |
| IC-5 | Orchard | F-2 | y=810 | diamond | West Quarter + Gatehouse Green |
| IC-6 | West Line | F-2 | y=500 | diamond | Harrow Green + cross-town Kettle Row |
| — | Crest junction | F-1 south end | (112, 56) | at-grade T | downtown, Kaleidoscope Crest |

24 ramps. Every exit leaves and every entrance joins at the outside shoulder —
x=211 southbound, x=233 northbound — never mid-carriageway. Ramps are sized
from the height they have to lose rather than drawn as diagonals: the fit grows
the gore's distance from the cross road until the curve is long enough. Worst
ramp grade in the system is **7.40%**, against the 11.9% of the four it
replaces.

Spacing on F-1: 396 → 654 → 920 → 1214, i.e. 258m, 266m, 294m. On a world whose
blocks are 70m and whose whole city is 1.6km tall, that is the local equivalent
of 2–3km spacing.

**IC-1 and IC-3** carry a short cross road east under the viaduct to a terminal
in open meadow, exactly the way Crown Boulevard already does at IC-2 by running
on to x=278. Deck-to-ground clearance is 7.8m at IC-1 and 8.2m at IC-3. IC-1's
western terminal is the East Line Road junction, because the Southline homes at
x=183..190 leave no room further west.

**IC-2** keeps its existing diamond shape and its terminals at x=186 and x=258.
What changed is the ramps themselves: shoulder gores, real tapers, gore
striping, and barrier openings.

**IC-5 and IC-6** are on the ring's west leg, which runs north–south exactly as
F-1 does, so they are ordinary diamonds with one difference: the ring is on the
ground, so the link road bridges over it and the ramps climb to reach the link.
The bridge approaches are deliberately unequal — 110m and 6.0% to the west,
where there is open meadow to the map edge; 80m and 8.2% to the east, because
the link has to be back on the ground by x=−750 where it meets a built
junction. Both links had to dodge the column of homes at x=−758.5 that fronts
West Line Road from the west for 680m: IC-5 lands at (−750, 810), the Orchard
Street junction, 19.6m from the nearest of them; IC-6 lands at (−750, 500), in
the 45m break between the homes at y=478.98 and y=524.07, 14m north of Kettle
Row West's western end.

**IC-4 is a trumpet.** A freeway meeting another freeway at a T has one
unavoidable problem: traffic off the stem has to reach both carriageways of the
through road, so something must cross something. Trumpets solve it with a loop
and one bridge — and here the bridge already exists, because the ring carries
its own overpass across the junction. The two loops pass beneath its crown at
x=308 and x=332 with 5.2m of clearance, and the interchange needs no structure
of its own. Nothing in it crosses F-1: everything that changes sides does it
north of y=1176, where the expressway no longer exists.

---

## 5. The collector tier

Followville had locals (6–8m), a boulevard grid (14m) and a freeway. The tier
between them was missing, which is why the expressway felt bolted on: there was
nothing for it to hand traffic to.

| Name | Extent | Width | Job |
| --- | --- | --- | --- |
| East Line Road | x=204, y 296 → 500 | 10m | Collects the six streets that dead-ended at x=210 and feeds IC-1 |
| East Line Road North | x=196, y 786 → 1180 | 11m | Crown Fields' eastern edge; feeds IC-3; ends in a turnaround |
| Orchard Link | y=810, x −940 → −750 | 11m | IC-5 to the built Orchard Street / West Line Road junction |
| West Line Link | y=500, x −940 → −750 | 11m | IC-6 to built West Line Road |
| Crown Approach | (112, 56) → (222, 250) | 14→24m | F-1's southern touchdown to the Crest junction |

**East Line Road is the single highest-value piece of this plan.** Six built
streets stopped dead inside the viaduct's footprint. It threads a 24m gap — the
Southline homes stand at x=190.2..191.4 and the structure edge is at x=209.1 —
at x=204 and 10m wide, keeping 7.6m from the nearest house, stopping 0.1m short
of the structure, and landing its eastern kerb within a metre of where all six
streets stop.

**East Line Road North deliberately does not touch the North Reach's five stub
ribbons.** West Market, Kiln, Maple, Cedar and Quarry Avenues run north to
y=1170 and stop there because their cross streets do not reveal until plan_id
2345. Tying anything permanent into those ends is Cade's call, not mine. The
collector runs at x=196, 27.5m east of the nearest planned address and 36m east
of Anvil Avenue North's future line, crosses nothing, and ends in a turnaround
at y=1180. When Northmoor Street (y=1170) is built it will pass 10m south of
that turnaround and the connection becomes a 30m stub — a future decision,
flagged, not taken here.

**Five turnarounds**, because the alternative is a cut end in a meadow: the
East Line Road North bulb at (196, 1180), the two interchange cross roads east
of the expressway at (262, 396) and (262, 920), which have nothing to run on to
but open ground out to the river at x=350, and the two ring links at (−940, 810)
and (−940, 500), which have nothing west of them but the map edge. Each bulb is
the point where that road's two ramp terminals meet.

---

## 6. Vehicles and lighting

**292 vehicles.** Static, no animation, so direction of travel is the whole
game. Right-hand traffic, which the existing ramp geometry already assumed even
though its four names said the opposite: the southbound carriageway is west of
the median (x 210→222) and the northbound is east (x 222→234). Lane centres are
2.10m, 6.00m and 9.50m off the median, derived from the viaduct's own markings.
`build_car`'s body is 3.6m along local +X, so southbound is rot=−π/2 and
northbound is rot=+π/2. Every vehicle sits on the deck it is driving on — z =
deck + 0.19 — never on the terrain 14m below. Gaps are varied by three
interleaved cadences so the line does not read as a toy train, and the seed
walks so no two neighbours draw the same body colour.

**50 lighting masts and 13 high-mast towers.** All placed through
`place_instance` under an object name containing `metro_streetlight`, and from
a collection named `ast_light_*`, so `_build_video_practicals()` finds them in
the sunset and night presets. Freeway lighting is not street lighting: 11.5m
masts at 64m centres, mounted on the deck itself rather than on the ground
below it, alternating sides; 20m high-mast towers with eight heads at every
interchange. The old `metro_expressway_light*` boxes are gone.

---

## 7. What it cost

- **New authored roads:** F-1's south approach and north extension, F-2's two
  legs, 24 ramps, four collectors and four interchange cross roads.
- **`world_layout.py`**: `walk_surface_manifest()` gained every new centreline
  at its deck height and all five turnaround bulbs, and the stale
  "Crown interchange ramps" raised rectangle came out.
- **`check_world_geometry.py`** merges `highway_plan.raised_road_regions()` and
  `authored_elevation_roads()` into its own declarations. It has to be done
  there rather than in `world_layout`, because `highway_plan` reaches
  `downtown_visual_plan`, which reaches `neighborhood_plan`, which imports
  `DISTRICT_OFFSETS` straight back out of `world_layout`. Both are still
  derived from the alignments themselves — a ramp that moves takes its
  declarations with it — which is what caught the one alignment/declaration
  mismatch this job produced (§9).
- **`town.html`**: one maintainer diagnostic, `?far=`, inside the block that
  already requires `?local=1&view=free`. The walking camera's 500m far clip and
  390m fog are right for a person on a street and make a 1.5km corridor render
  as empty sky. The public viewer cannot reach the line.
- **Terrain: none.** No shelf, no mound, no edit to `terrain_height()` or
  `regionalTerrainHeight`. Every alignment was chosen so that no terrain change
  is needed; that is why F-2 is at grade and why F-1 stops where it does in the
  south.
- **`world_state.json`: unchanged.** No growth, no new building record. The
  highway is world geometry, like the river and the bridges.
- `town.glb` grows from 46.3MB to 52.9MB.

Reveal: the whole system reveals on the condition the expressway already used —
the presence of a `metrotower` — so it appears with the road it upgrades and
disappears in an earlier replay exactly as the expressway does.

---

## 8. What this plan does not solve

- **Neither end of F-1 reaches a map edge.** The south is measured shut in §3;
  the north ends at IC-4 because 66m is not enough to cross a freeway and come
  back down. The ring reaches the map edge twice, so the system does leave
  town — F-1 by itself does not.
- **The North Reach's five stub ribbons stay stubs.** Out of scope by
  instruction; §5 says where the future connection goes. **This is the one
  thing worth a decision from Cade**: a 30m link from the East Line Road North
  turnaround would tie them in the day Northmoor Street reveals.
- **The southern districts** — North Ridge, Twin Oaks, Pine Hollow, Meadow Run,
  Rivergate, River Meadows, roughly 250 built homes with no planned growth —
  get no direct interchange. Their nearest access is the Crest junction. A
  southern ring leg was measured: at y=−340 it crosses the x=−455 landform at
  7.6%, above a freeway standard, to serve a part of the city with no reserve
  behind it. Not built.
- **Crown Quarter's declared collectors** — Kiln, Cedar and Anvil Avenues are
  tagged `kind: "collector"` in `metropolitan_plan.street_plan()` — are still
  built at the 8m local width. Widening them would change built geometry, so
  the collector tier is expressed in new roads instead.
- **The ring's west leg has no interchange between y=500 and y=−360**, 860m of
  access-free rural freeway. That is correct for a road whose job there is the
  regional connection south, but it does mean the southwest quadrant is served
  by the ring only at its two western links.

---

## 9. What building it changed

Four things. Each is in the document above; they are collected here so the
difference between the plan as written and the plan as built is visible rather
than quietly reconciled.

1. **F-1's northern terminus moved from the map edge to IC-4**, and the
   extension bends east to x=300. The first draft ran it dead straight at x=222
   to y=1280 and crossed the ring on the way. Laying out the interchange showed
   both south-western quadrants land inside Crown Fields' reserve, and that
   F-1 had 66m to get back down from an overpass. Bending east solved the first
   and a trumpet solved the second.
2. **The Ring Freeway jogs to y=1252 around the North Crown Campus.** The
   campus is at (−370, 1088) with a 200 × 280m declared footprint reaching
   y=1228; the straight ring at y=1214 ran through it. `check_world_geometry`
   caught it — "northcrowncampus is −1.0m from Ring Freeway (needs 2.0)" —
   which the clearance sweep did not, because that sweep measured to building
   centres and the campus centre is 126m away.
3. **The raised-road declarations became derived rather than drawn.** They
   started as hand-written rectangles, and the northern viaduct's box was still
   centred on x=222 after the alignment bent east. The audit caught that too, as
   a 1.86m float at (257.2, 1051.8). They are now computed from where each road
   actually leaves the ground.
4. **The Crown Approach was re-cut as a tangent-matched cubic.** The first
   spine met the Crest access road at 15° — near enough to parallel that the
   two roads read as never touching — and reached the viaduct with a 38m
   radius. IC-6 moved from y=486 to y=500 in the same pass, out of the Harrow
   Green homes at x=−758.5.
