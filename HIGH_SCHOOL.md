# Followville High School

Three buildings, a running track with a football field inside it, and the
campus around them, on the block immediately south of Followville Elementary.

Added 2026-08-21 on Cade's brief: *"a track with the football field in the
middle, three buildings or something, it should say FOLLOWVILLE HIGH SCHOOL
outside of it, near the elementary school, connected to that old part of the
city — add a block right there and flatten the terrain if you need to."*

This file is the record of **why it is where it is and what size it is**. The
short version: the site was not chosen, it was the only one, and the campus was
sized to fit it rather than the other way round.

---

## Where

One record, `highschool`, anchored at **(-69, -156)** with `px`/`py`, no grid
lot. The declared footprint in `world_layout.LANDMARK_FOOTPRINTS` is
**x ±32, y ±56** — 64m across, 112m deep — which is world
**x[-101, -37], y[-212, -100]**.

The elementary school stands on the downtown block directly north, across the
town's own y=-93 street. The two are 15m apart at their closest.

### Why not somewhere bigger

The whole town was swept for a clear rectangle before this was drawn, at the
clearances `check_world_geometry` actually enforces (6.0m to any building,
2.0m plus half a carriageway to any road):

| minimum width | longest clear rectangle | nearest such site to the elementary school |
| --- | --- | --- |
| 60m | 138m | 89m |
| 72m | 116m | 98m |
| 80m | 100m | 102m |
| 92m |  66m | 111m |

Nothing anywhere in Followville seats a full-size 400m track (89 x 173m) within
**270m** of the elementary school; the nearest rectangle that would is at
(-294, 80), the far side of Twin Oaks and Willow Hills. Meadow Run closes this
pocket on the west, Pine Hollow on the east, and the downtown grid on the
north. So the campus is 64 x 112 and the track is scaled to fit, which is the
trade Cade's "near the elementary school, like, right there" asks for.

## The platform

`downtown_visual_plan.HIGH_SCHOOL_PAD` cuts the campus rectangle level at the
downtown datum, and `town.html`'s `regionalTerrainHeight` carries the identical
cut — change one and you must change the other.

The natural ground falls **7.3m** across the site, from 0.00 at the north edge
to 7.33 at the south-west corner, because the platform's own 9% edge ramp gives
out at y=-113 and the slope up to the (-235, -155) landform takes over. North of
y=-113 the cut removes nothing at all, which is why the campus meets the town's
street with no step.

The cut is a `min()` cap, like the downtown platform's own edge, **not** a lerp
toward a datum like the Food Court's or the West Quarter's. That is the safety
property: a cap can only ever lower ground, so no feather of it can push the
meadow up through a standing house.

`HIGH_SCHOOL_BANK_RUN` is **3.5m of run per metre of rise — a 28.6% grass
bank**, and it is the steepest the site allows in both directions:

* **Shallower moves the world.** Meadow Run road 363 sits 5.28m up and 20.8m
  out from the core's south-west corner and needs 3.94 or steeper before its
  ground starts to drop; house 202 at (-135.2, -213.7) needs 4.14. Existing
  geometry never moves.
* **Steeper buys nothing.** Nothing outside the core is closer than that.

Verified after the change: the largest ground movement under any of the 2,550
standing buildings is **0.000m**, over every revealed road centreline
**0.000m**, over the whole paved downtown envelope **0.000m**, and over all
3,171 planned-but-unbuilt addresses **0.000m**.

The campus holds that bank back on its west edge with a fieldstone retaining
wall and piers, because the cut is 6m deep there and a hillside would otherwise
spill onto the running track.

## The site plan

Local coordinates, north (+Y) toward the town, front doors on -Y like every
other civic asset:

| band | y | what |
| --- | --- | --- |
| arrival | +42.2 … +56 | drive loop, bus lay-by, staff car park, monument sign, flagpole |
| buildings | +25 … +45 | Founders Hall, the science & arts wing, the gymnasium |
| quad | +19.4 … +25 | one slab of paving in front of all three |
| stadium | -55 … +19 | the running track, the field, the home stand, the field house |

That is the entire 112m. There is no forecourt per building because three
slabs at one level would meet along shared faces, and staggering them would put
steps across the front of the school.

### The track

An obround with its straights along Y: inner kerb radius **20.3**, half-straight
**11.0**, a six-lane band **5.7m** wide. Outer 52 x 74. The infield is
40.6 x 62.6 and holds a **23 x 50** football field with five-metre end zones.

The proportions are a real 400m track brought down to the scale this town is
built at, and that is the part worth keeping. **Fitting the widest oval the
site allows gives a round one, and a round oval can only hold a square field**
— an early draft at 60 x 78 could only seat a field 1.5:1 instead of a real
field's 2.25:1, because the field's corners have to sit inside the bends. The
check re-measures that corner clearance on every run; it currently has 2.18m to
spare.

### The name

Cade asked for it to say FOLLOWVILLE HIGH SCHOOL outside, so it says it twice:

* a **double-sided monument sign** at the campus entrance, read from the town
  street on its north face and from the campus on its south — which is also
  the side every town camera looks at;
* **extruded letters on Founders Hall's south facade**, over the main entrance,
  on a navy band.

The scoreboard and the press box both carry FOLLOWVILLE HIGH as well.

## Checks

```
blender --background --factory-startup --python check_high_school_assets.py
```

`check_high_school_assets.py` is the standalone geometry check CLAUDE.md's
visible-surface depth rule asks for. Neither `check_town_glb.py` nor
`check_world_geometry.py` can see coplanar faces — they measure where things
stand, not whether two faces are fighting for the same depth — and this campus
is almost entirely stacked flat slabs: paving, a drive, a car park, a running
track and a painted field, any pair of which shimmers in the browser if they
share a plane.

It reports a pair only when the shared face is actually **seen**: it samples
just outside the face and asks whether any other solid encloses that point, so
a slab resting on a slab, a window frame anchored in a wall and a cornice under
a roof are all correctly ignored. It also only compares bounding planes that a
real polygon lies in, so a roof prism's ridge — a line, not a face — is not
reported against the vent cap beside it.

It found nine defects the eye had passed, including every paved surface in the
arrival area sharing one top, the six bleacher tiers finishing on one plane at
each end, and every entrance's steps landing exactly level with the quad.

The usual two also apply, and both pass with the campus in place:

```
blender's python check_world_geometry.py
blender's python check_town_glb.py
```

## Things that are not obvious

* The campus deck is a **walk pad**, not a road. The drop-off loop is declared
  in `world_layout.HIGH_SCHOOL_APPROACH` so the geometry audit can see it and
  so `LANDMARK_APPROACHES` can tell it apart from a street the campus is
  standing on — but it is deliberately **not** in the walk-surface manifest as
  a road. Its asphalt is 31cm up on the campus deck, and a road deck that far
  above the terrain is exactly what `check_roads_sit_on_the_ground` exists to
  catch. The `high-school-campus` pad covers the whole platform, loop included.
* `HS_LAWN_TOP` is 0.22 for that reason: it puts the lawn, the paving, the
  drive and the running track all within 6cm of one deck height, so a single
  0.28m pad serves the campus without the player sinking into the paving or
  hovering over the grass.
* Two kerb-cut ramps take the 14cm between the town's asphalt and the campus
  deck over twelve metres. They are the only geometry that reaches outside the
  declared footprint, and the asset check exempts them by name.
* `footprint()` reserves every grid lot the campus covers. Downtown block-fill
  would otherwise have reached these lots within a few days' growth, and the
  nature scatter works from the same occupied set — without it a tree could be
  planted on the running track.
