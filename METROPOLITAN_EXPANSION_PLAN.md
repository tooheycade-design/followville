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

The expressway is a 24m-wide, six-lane elevated regional road centered at
x=222m. It runs from y=250 through y=858 and continues beyond the district in
both directions visually; it does not terminate at the towers.

- Paired concrete piers at roughly 38m spacing.
- Three lanes each direction, median barrier, outside barriers and shoulders.
- A grade-separated diamond interchange at Crown Boulevard, y=654m.
- Four authored, grade-limited ramps.
- Crown Boulevard passes under the viaduct with useful clearance and continues
  to both ramp terminals.
- Overhead gantries and signs establish regional scale.

The expressway, ramps and local streets are included in the browser walk
surface manifest and world-geometry audit. Raised road regions and authored
elevations are declared in `world_layout.py`.

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
