# Followville metropolitan expansion — Crown Quarter

Status: implemented as a dormant deterministic reserve on 2026-08-11.

Nothing in this plan changes the canonical Day 41 state, either authoritative
Blend, the current GLBs, the live website, claims, or Supabase. The source is
ready for the first guarded growth that exhausts the ordinary address reserve.

## Planning intent

Crown Quarter is not a second city and not a detached tower development. It is
the next northern layer of Followville's existing urban structure:

- The original downtown grid remains the historic center.
- Northgate and Southline form the transition from houses to urban blocks.
- Six Crown Quarter north/south streets continue the established grid lines.
- Kettle Row is the shared seam, not an edge road separating two settlements.
- Tower height and density increase away from the historic center, producing a
  graduated skyline rather than twenty isolated objects.
- A regional expressway runs along the east edge, where it serves the center
  without dividing its walkable blocks.

The site is intentionally graded to the same 5.00m datum as Northgate and
Southline. Its southern core overlaps the existing engineered terrace, so no
standing house moves. The west and north edges feather into open terrain. The
short east feather ends before the river.

## Population and claiming model

- The remaining ordinary `neighborhood_plan.py` house addresses are consumed
  first. At Day 41 there are 109 ordinary house slots remaining; three of the
  final 112 plan IDs are reserved civic addresses.
- Every follower beyond those 109 occupies Crown Quarter.
- One `metrotower` holds up to 100 followers.
- A partial group earns a tower immediately. Example: 291 overflow followers
  produce tower occupancies 100, 100 and 91.
- The next growth fills the last partial tower before earning another.
- Twenty tower addresses reserve exactly 2,000 followers.
- Each tower is one claimable `houses` row today. Records carry `metro_id`,
  `resident_capacity` and `residents`, leaving a stable path for future
  apartment-level ownership without changing the building address.

No built or claimed house is demolished. The approved replacement/claim
migration option remains unnecessary because the additive site fits cleanly.

## Street and block plan

The pure-data source is `metropolitan_plan.py`.

- North/south grid lines: x = -190, -120, -50, 20, 90 and 160m.
- East/west streets: y = 522, 588, 654, 720 and 786m.
- Twenty parcels: five columns by four rows.
- Local streets are 8m wide.
- Founders Boulevard and Crown Boulevard are 14m wide urban arterials.
- Every block has 3.2m sidewalks, physical kerbs, curb ramps and crossings.
- Crown Boulevard has a planted median and is the interchange street.
- Four sheltered bus stops serve the two boulevards.

The ground floor is deliberately busier than the tower massing. Every earned
tower receives glazed storefront bays and awnings; a café terrace with fully
modeled chairs, tables and umbrella; entrance bollards; racks with complete
bicycles; layered mixed-foliage planters; a hydrant and news/parcel box; and a
working paved service edge with a ribbed wheeled dumpster, loading hatch,
drain, safety guards, utility cabinet and delivery crates. Curbside cars,
loading marks, detailed corner kiosks and a windowed, doored Followville city
bus populate the shared streets. Eight additional cars travel deterministic
local-street and expressway routes during videos, so Crown Quarter has activity
at pedestrian, neighborhood and regional scales without blocking crosswalks or
claimable entrances. Maintained close-review shots live in
`scripts/render_crown_quarter_details.py`; they rebuild only against an isolated
all-tower state and never advance the canonical city.
- Streetlights, trees, bins, benches, planters and wayfinding use Followville's
  existing low-poly material language.

Unbuilt parcels are active interim city land rather than blank slabs. They
cycle deterministically among pocket parks, surface parking and fenced prepared
construction sites. When a tower is earned, its interim use disappears and its
paved podium forecourt replaces it.

## Crown Expressway

**Superseded 2026-08-20. The expressway is now one route in a city-wide
highway system; `HIGHWAY_PLAN.md` is the authority and `highway_plan.py` is the
data. What follows describes what is actually built.**

The section this chapter created is unchanged in position and height: a
24m-wide, six-lane elevated deck centered at x=222m, z=14.0, from y=250 to
y=858, on paired concrete piers, with three lanes each direction, a median
barrier, outside barriers and shoulders, overhead gantries, and a
grade-separated diamond interchange at Crown Boulevard (y=654) whose terminals
are still at x=186 and x=258 with the boulevard running on to x=278 to reach
them.

Everything else about it changed, because the paragraph this replaces claimed
the road "continues beyond the district in both directions visually; it does
not terminate at the towers", and it did terminate — in mid-air, at both ends.

- **It no longer stops at either end.** South of y=250 the deck comes down at
  6.04% as the Crown Approach and ends at a T-junction with the Kaleidoscope
  Crest access road at (112, 56). North of y=858 it descends at 5.0%, reaches
  the ground at y=1082, bends east to x=300 and ends at a trumpet interchange
  with the Ring Freeway at (300, 1214).
- **Four interchanges, not one:** Northgate (y=396), Crown Boulevard (y=654),
  Crown Fields (y=920) and the Ring system interchange.
- **The four original ramps were rebuilt.** Their names were inverted relative
  to their geometry — the ramp called "southbound-off" sits in the south-west
  quadrant, which is the southbound *entrance* — they diverged from
  mid-carriageway rather than the shoulder, they had no tapers, and they passed
  beneath an outside barrier that ran unbroken for all 608m. All four now leave
  and rejoin at the shoulder with tapers, gore striping and real barrier
  openings, and the worst ramp grade in the whole system is 7.40% against the
  11.9% of the originals.
- **The deck lighting was replaced.** The old `metro_expressway_light*` boxes
  matched none of the names `_build_video_practicals()` looks for, so the
  viaduct cast no light pools at night. Lighting is now placed through
  `place_instance` under names containing `metro_streetlight`.
- **`metropolitan_plan.RAMPS` is no longer built, walked or audited.**
  `ramp_plan()` is retained as the record of the original geometry;
  `highway_plan.interchanges()` supplies the ramps that exist.
- Six built streets (Northgate Avenue, Foundry Street, Lantern Row, Southline
  Avenue, Millrace Street and Kettle Row) dead-ended at x=210, 0.9m inside the
  viaduct's structure. East Line Road, a new 10m collector at x=204, now
  collects all six.

The expressway, its ramps, the rest of the highway network and the local
streets are all in the browser walk surface manifest and the world-geometry
audit. Raised road regions and authored elevations for the highway system are
derived from the alignments in `highway_plan.py` and merged into the
declarations by `check_world_geometry.py`.

## Tower design system

Twenty variants are authored in `build_metro_tower()` and instantiated by
stable `metro_id`, never by random daily selection.

- Five massing families: stepped commercial, offset slab, broad-base setback,
  faceted taper and paired-wing/spine.
- Four crown families: faceted cap, lantern, spire and vertical fins.
- Heights range from roughly 60m to 116m including crowns.
- Ten pastel/contemporary palettes repeat with different massing, keeping the
  skyline recognizably Followville.
- Every tower has a retail/lobby podium, canopy, entrance, planters and a
  complete ground interface.
- Glass bands and fins are physically separated from support faces; no browser
  `polygonOffset` is used as an authored-geometry fix.

The existing population-2,000 generic milestone skyscraper is retired. Leaving
it active would insert an unrelated twenty-first tower into the historic grid.

## Growth and video behavior

Normal guarded `+N` growth needs no special tower flag. When the ordinary
reserve ends, the allocator fills/creates towers automatically.

Use `--cam metroreveal` for the first Crown Quarter day. It is a 26-second
continuous move that:

1. establishes the historic city;
2. follows the existing urban growth north;
3. arcs across the expressway and interchange;
4. holds on the new skyline while earned towers rise; and
5. touches boulevard scale before climbing to a complete final portrait.

On the first tower day, highways and streets build on before towers rise.
Existing infrastructure is never re-hidden or reanimated on later days.

## Validation

Run these before any commit that changes this plan:

```text
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" metropolitan_plan.py
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --factory-startup --python-exit-code 1 --python check_metropolitan_assets.py
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" check_world_geometry.py --self-test
```

Also simulate tomorrow's full gain against copies of the state and Blend. The
2026-08-11 isolated `+400` simulation produced Day 42 / population 1,640 with
109 ordinary homes and three towers occupied by 100, 100 and 91 residents. A
second isolated simulation instantiated all twenty variants and passed the
world geometry audit at population 3,349. Neither simulation touched canonical
state or binaries.
