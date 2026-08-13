# Followville Point Station

Added 2026-08-12. Read this before changing the station, its roads, the
temporary interior set, or the story video.

## What exists

| Thing | Where | Permanent? |
| --- | --- | --- |
| `build_nuclear_plant()` | `neighborhood_blender.py` | yes — a normal landmark |
| `build_reactor_hall_interior()` | `neighborhood_blender.py` | **NO — temporary set** |
| Point Road, Station Trail | `world_layout.py` | yes |
| `scripts/render_nuclear_plant.py` | asset review, blank plane | tool |
| `scripts/render_reactor_interior.py` | interior review | tool |
| `scripts/render_nuclear_in_world.py` | station in context | tool |
| `scripts/render_nuclear_story.py` | the story video | tool |

Placed with `--nuclearplant`. It is a landmark, not a house: it consumes no
follower and does not move population.

## Siting — measured, not chosen

The whole river corridor was scored against the criteria that actually decide
such a siting: cooling water, a buffer from housing, flat ground above the
water, and reach to a road that already goes somewhere. The results forced the
answer:

* The reach **south of the Timber Bend Crossing is floodplain** — the east
  bank sits 0.5–1.3m *below* the river surface, because that is where the
  river runs perched above its own meadow.
* The bank **beside the log houses is taken** — Eastbank Village's reserve
  puts addresses 3–70m away.
* **No point on this river is 150m from a home.** Both banks are lined by the
  reserve. That is the geography, not a failure of searching.

So it sits at **(446, 556)** on the east bank north of Eastbank Village:
~150m of buffer, flat, ~100m from the water, past the last neighbourhood —
which is where such a plant goes. Its pad is pinned above the site's highest
corner (`nuclear_plant_base_height()`), like the Salmon Pro Shop's, because the
terrain mesh comes from `terrain_height()` and a lower pad has the ground
rising through the switchyard.

## The roads

**Point Road** leaves Ferry Street *where that street is still running* — not
at its cul-de-sac bulb, where a junction reads as an afterthought — and carries
on **north past the plant** to a river overlook. That is what stops it being a
private driveway: it is a road to somewhere and the station happens to be on
it. **Station Trail** is the dirt track for the last 30m to the gate: narrower,
no shoulder, no markings.

Both centrelines live in `world_layout` because the generator, the browser's
walk surface and `check_world_geometry` all need the same line and copies
drift. Both are declared in `LANDMARK_APPROACHES` so the audit lets them touch
the station.

## Two modelling rules this build learned the hard way

**1. Signage on a curved wall must be wrapped, not mounted flat.** A flat disc
tangent to a round tower sinks into it away from the tangent point — a 3.4m
disc on an 11.5m tower buries its edges 0.51m inside the shell, which is what
"phasing through the building" looks like. Standing it off far enough turns it
into a floating billboard, and the required standoff grows with the *square* of
the sign's size. `add_wrapped_sector()` lays the sign out flat and maps every
vertex back onto the surface at `radius_at(z) + standoff`, so it follows the
taper too. That is why the trefoils can be 10m across.

**2. `add_box` cannot cut a hole.** Anything "sunk into" something else is
sealed inside an opaque solid. The refuelling pool was built as a pit under an
unbroken floor slab (invisible, and the room went dark because the pool is what
lights it), then rebuilt as a raised basin with the water sunk into *that*
(invisible again). Water sits **on** the basin, biting 2cm in so the tops are
not coplanar.

**3. Emissives saturate to white before they saturate to their hue.** Driving a
light green hard gives a white rectangle. The colour must come from a deep base
and only the lift from the strength. This bit the trefoils and the pool.

## The temporary interior set

`build_reactor_hall_interior()` is a **stage, not a building**. It is never
placed by growth, never exported to a GLB, never referenced by
`world_state.json`, and nothing in the town depends on it. The story script
builds it 400m underground directly beneath the station — a sealed box, so
nothing leaks either way and the cut reads as going *inside* rather than
cutting somewhere else.

Everything a shot might move is a separately named object — `rh_crane_bridge`,
`rh_crane_trolley`, `rh_crane_hook`, the beacon domes, `rh_pool_water` —
because animating a merged mesh animates the room with it.

**Delete it when the video work is finished.**

## The story video

`scripts/render_nuclear_story.py`, 720 frames at 30fps, 1080×1920, sunset.

The **first and last frames are identical by construction** — same camera pose,
and every animated value returned to exactly where it started. That is only
possible because the story *resolves*: the alarm rises and then clears, so the
closing frame is the opening frame and the whole thing loops.

1. bookend — the station, still
2. overview — the city, slow push
3. approach — up Point Road to the gate
4. interior — the hall working, crane travelling
5. emergency — beacons, camera shake, the pool surging
6. exterior — the alarm from outside
7. bookend — back to frame one, exactly

`NUCLEAR_STORY_FRAMES=1,120,250` renders just those frames as stills; checking
framing by rendering the whole thing costs twenty minutes a try.

**The video must show only what is live.** It is rendered from an isolated copy
of the canonical state (day 42, population 1560) with the station added and
**no growth**. An early cut was built with `--gained 1500`, which put Crown
Quarter's skyscrapers and 798 unbuilt houses on screen as though they were
real. Do not do that.

## Known weaknesses, for whoever picks this up

* The terrain is a finite mesh and any shot with the far horizon in frame
  catches its edge as a black band. Aerials must look steeply down; ground
  shots must sit low and close. This is a framing constraint, not a bug to fix
  in the world.
* The screen house and pipe saddles on the intake read as loose boxes in a
  field from directly above.
* The switchyard is a thicket at distance.
* The control-room consoles face the wall display, so from the mezzanine camera
  you see their backs.
* The dirt trail reads pale grey rather than brown under sunset exposure.
* With three trefoils at 120°, one will sometimes straddle the tower's edge and
  show a sliver of green wrapping round the limb. Geometrically correct; drop
  to two aimed at the shots actually used if it bothers a specific frame.
