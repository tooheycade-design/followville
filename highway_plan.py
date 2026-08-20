"""Followville highway system: the freeway and collector tiers, as pure data.

Geometry-free, like ``neighborhood_plan`` and ``metropolitan_plan``. Everything
here is a centreline, a width and an authored height; ``neighborhood_blender``
turns it into meshes, ``world_layout`` declares it to the audits and puts it in
the browser walk-surface manifest, and ``check_world_geometry`` reads the same
centrelines back.

The design and the measurements behind every number are in ``HIGHWAY_PLAN.md``.
The short version:

* **F-1, the Crown Expressway.** The existing 608m viaduct at x=222 keeps its
  alignment and its deck height exactly. It gains a southern approach that
  brings it down to the Kaleidoscope Crest access road instead of stopping in
  mid-air over the Food Court plateau, and a northern extension that descends
  to grade and leaves the modelled world at y=1280.
* **F-2, the Ring Freeway.** At grade for its whole length, from the eastern
  map edge along y=1214, around the north-west corner and south along x=-830 to
  the southern map edge.
* **Six interchanges and four collectors.** Every interchange lands on a road
  that is built today; none of them touch the North Reach's unbuilt streets.

The whole system reveals on the same condition the expressway already used --
the presence of a ``metrotower`` -- so it appears with the road it upgrades.
"""

import math

from downtown_visual_plan import TERRAIN_BOUNDS, terrain_height
from metropolitan_plan import (EXPRESSWAY_DECK_Z, EXPRESSWAY_WIDTH,
                               EXPRESSWAY_X, EXPRESSWAY_Y0, EXPRESSWAY_Y1,
                               TERRACE_DATUM)

MAP_X0, MAP_X1, MAP_Y0, MAP_Y1 = TERRAIN_BOUNDS

# ---------------------------------------------------------------- dimensions

FREEWAY_WIDTH = EXPRESSWAY_WIDTH          # 24m, six lanes, matches the viaduct
STRUCTURE_EXTRA = 1.8                     # the deck's structure oversail
ARTERIAL_WIDTH = 14.0                     # Crown Approach, boulevard-grade
COLLECTOR_WIDTH = 11.0                    # the missing tier
CROSS_ROAD_WIDTH = 11.0                   # interchange cross roads
RAMP_WIDTH = 5.4                          # matches the existing four ramps
SHOULDER_HALF = 11.0                      # outside edge line, from the median
DECK_SURFACE = 0.18                       # deck top above the authored height
ROAD_TOP = 0.19                           # at-grade deck top above terrain
UNDERPASS_CLEARANCE = 5.20                # what a road needs beneath a deck

# Lane centres measured from the median, per carriageway. Derived from the
# viaduct's own markings: median barrier at 0.19, lane lines at 4 and 8,
# outside edge line at 11.
LANE_CENTRES = (2.10, 6.00, 9.50)

# The limits this plan holds itself to. For scale: the four ramps that exist
# today run at 11.9%, so everything here is gentler than what it replaces.
MAX_MAINLINE_GRADE = 0.062
MAX_RAMP_GRADE = 0.075
MAX_ENTRANCE_GRADE = 0.065                # entrances are longer than exits

# ------------------------------------------------------------------- helpers


def _densify(points, step=3.0):
    """Sample a centreline every ``step`` metres, endpoints included."""
    out = []
    for a, b in zip(points, points[1:]):
        count = max(1, int(math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / step)))
        for index in range(count):
            t = index / count
            out.append(tuple(a[i] + (b[i] - a[i]) * t for i in range(len(a))))
    out.append(tuple(points[-1]))
    return out


def _at_grade(points, lift=ROAD_TOP):
    """Give a plan centreline the terrain's own height."""
    return tuple((x, y, terrain_height(x, y) + lift) for x, y in points)


def _length(points):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(points, points[1:]))


def _graded(points, z_start, z_end, floor=None):
    """Interpolate height by distance along the centreline, not by index."""
    total = _length(points)
    out = []
    run = 0.0
    for index, point in enumerate(points):
        if index:
            run += math.hypot(point[0] - points[index - 1][0],
                              point[1] - points[index - 1][1])
        z = z_start + (z_end - z_start) * (run / total if total else 0.0)
        if floor is not None:
            z = max(z, terrain_height(point[0], point[1]) + floor)
        out.append((point[0], point[1], z))
    return tuple(out)


def _limit_grade(points, max_grade):
    """Enforce a maximum gradient by raising points, never by lowering them.

    Two sweeps. The forward one caps how fast the profile may fall, the
    backward one caps how fast it may rise; both only ever push a point up, so
    a profile that started above the ground stays above it. This is what stops
    a ramp whose two ends are level from following every wrinkle of the meadow
    between them at 9%.
    """
    out = [list(point) for point in points]
    for index in range(1, len(out)):
        run = math.hypot(out[index][0] - out[index - 1][0],
                         out[index][1] - out[index - 1][1])
        out[index][2] = max(out[index][2], out[index - 1][2] - max_grade * run)
    for index in range(len(out) - 2, -1, -1):
        run = math.hypot(out[index + 1][0] - out[index][0],
                         out[index + 1][1] - out[index][1])
        out[index][2] = max(out[index][2], out[index + 1][2] - max_grade * run)
    return tuple(tuple(point) for point in out)


def _arc(centre, radius, start_deg, end_deg, step_deg=6.0):
    """A circular fillet, used for the ring's north-west corner."""
    span = end_deg - start_deg
    count = max(2, int(math.ceil(abs(span) / step_deg)))
    return tuple((centre[0] + radius * math.cos(math.radians(start_deg + span * i / count)),
                  centre[1] + radius * math.sin(math.radians(start_deg + span * i / count)))
                 for i in range(count + 1))


def _bezier(start, end, bulge, step=4.0):
    """A quadratic curve in plan: what turns a straight diagonal into a ramp."""
    mid = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    dx, dy = end[0] - start[0], end[1] - start[1]
    span = math.hypot(dx, dy) or 1.0
    control = (mid[0] - dy / span * bulge, mid[1] + dx / span * bulge)
    count = max(6, int(math.ceil(span / step)))
    return [(( 1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t * t * end[0],
             (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t * t * end[1])
            for t in (i / count for i in range(count + 1))]


# =============================================================== F-1 mainline
#
# The viaduct itself is untouched: same x, same deck, same length. What is new
# is what happens at each end.

# The southern terminus. (112, 56) is a vertex of world_layout.STORYBOOK_ACCESS,
# the built Kaleidoscope Crest access road, which runs west from there to
# downtown at (87, 33) and east onto the Crest. Joining it here rather than at
# (198, 74) buys 50m of length, which is the difference between a 7.6% approach
# and a 6.1% one.
CREST_JUNCTION = (112.0, 56.0)
NORTH_TERMINUS_Y = MAP_Y1                 # 1280, the northern map edge
NORTH_DESCENT_START_Y = 872.0
NORTH_DESCENT_GRADE = 0.050

# A cubic with both tangents fixed: it leaves the Crest road at 80 degrees --
# a 48 degree junction, so the two roads actually cross rather than run
# alongside each other -- and arrives at (222, 250) pointing due north, tangent
# to the viaduct it becomes. The first version of this spine left the junction
# at 47 degrees against a road running at 32, which met it at 15 degrees and
# read as two parallel roads that never touched.
#
# The curve also has to thread the Food Court, whose nearest home stands at
# (232.1, 212.7), and the East Woods reserve at (170, 180). It clears the
# closer of the two by 16.0m of centreline, which is 9.0m of edge at the 14m
# arterial width it still holds there.
CROWN_APPROACH_SPINE = (
    (112.0, 56.0), (118.5, 78.1), (128.8, 97.8), (141.9, 115.6),
    (156.7, 132.4), (172.2, 148.8), (187.3, 165.5), (200.9, 183.3),
    (211.9, 202.8), (219.3, 224.8), (EXPRESSWAY_X, EXPRESSWAY_Y0),
)


def crown_approach_points(step=3.0):
    """Crown Approach: one constant 6.1% climb from the Crest road to the deck.

    A single grade the whole way, so the road has no kink. ``floor`` guarantees
    it can never be authored below the ground it crosses; measured, it never
    needs to be -- the profile clears terrain everywhere by construction.
    """
    plan = _densify(CROWN_APPROACH_SPINE, step)
    return _graded(plan, terrain_height(*CREST_JUNCTION) + ROAD_TOP,
                   EXPRESSWAY_DECK_Z, floor=ROAD_TOP)


APPROACH_FLARE_Y = 228.0


def crown_approach_widths(points):
    """14m arterial for its whole length, flaring to the 24m deck at the end.

    The flare is late on purpose. Opening it out gradually from halfway would
    put a 20m deck 3.0m from the Food Court's nearest home; holding the
    arterial width until y=228 -- north of everything the curve has to pass --
    keeps 9.0m there and puts the whole transition in open meadow.
    """
    widths = []
    for x, y, _z in points:
        t = max(0.0, min(1.0, (y - APPROACH_FLARE_Y)
                         / (EXPRESSWAY_Y0 - APPROACH_FLARE_Y)))
        widths.append(ARTERIAL_WIDTH + (FREEWAY_WIDTH - ARTERIAL_WIDTH) * t)
    return tuple(widths)


# The extension bends 78m east above IC-3, on a 340m radius. That bend is not
# decoration: it is what gives the system interchange with the ring room to
# exist. At x=222 the two south-western quadrants of the junction are 40m from
# Crown Fields' reserve and every ramp that needs them runs through reserved
# addresses. At x=300 the nearest reserved address is 131m away and all four
# quadrants are open meadow.
NORTH_EXTENSION_SPINE = (
    (EXPRESSWAY_X, EXPRESSWAY_Y1), (EXPRESSWAY_X, 950.0), (238.0, 1006.0),
    (264.0, 1068.0), (288.0, 1120.0), (297.0, 1150.0), (300.0, 1176.0),
)
NORTH_JUNCTION_X = 300.0
# Where the mainline ends and its two carriageways become the trumpet's ramps.
NORTH_SPLIT_Y = 1176.0


def north_extension_points(step=3.0):
    """The northern extension: viaduct down to grade, then out of the world.

    Terrain north of y=900 is flat at 3.22m for 380m, which is what makes a
    proper terminus possible here and impossible in the south: the deck comes
    down at 5.0% and the road leaves the modelled world on the ground.
    """
    points = []
    for x, y in _densify(NORTH_EXTENSION_SPINE, step):
        drop = max(0.0, y - NORTH_DESCENT_START_Y) * NORTH_DESCENT_GRADE
        points.append((x, y, max(EXPRESSWAY_DECK_Z - drop,
                                 terrain_height(x, y) + ROAD_TOP)))
    return tuple(points)


def north_extension_touchdown():
    """The y at which the northern extension first sits on the ground."""
    for x, y, z in north_extension_points(step=2.0):
        if z <= terrain_height(x, y) + ROAD_TOP + 1e-6:
            return y
    return NORTH_TERMINUS_Y


def _mainline_profile():
    """F-1 end to end as (y, x, deck z), ascending in y. Cached on the module."""
    global _MAINLINE_CACHE
    if _MAINLINE_CACHE is None:
        profile = [(y, x, z) for x, y, z in crown_approach_points(step=2.0)]
        profile.append((EXPRESSWAY_Y1, EXPRESSWAY_X, EXPRESSWAY_DECK_Z))
        profile.extend((y, x, z) for x, y, z in north_extension_points(step=2.0))
        profile.sort()
        _MAINLINE_CACHE = tuple(profile)
    return _MAINLINE_CACHE


_MAINLINE_CACHE = None


def _mainline_at(y):
    profile = _mainline_profile()
    if y <= profile[0][0]:
        return profile[0][1], profile[0][2]
    if y >= profile[-1][0]:
        return profile[-1][1], profile[-1][2]
    low, high = 0, len(profile) - 1
    while high - low > 1:
        mid = (low + high) // 2
        if profile[mid][0] <= y:
            low = mid
        else:
            high = mid
    span = profile[high][0] - profile[low][0]
    t = (y - profile[low][0]) / span if span else 0.0
    return (profile[low][1] + (profile[high][1] - profile[low][1]) * t,
            profile[low][2] + (profile[high][2] - profile[low][2]) * t)


def mainline_x(y):
    """Centreline x anywhere on F-1."""
    return _mainline_at(y)[0]


def mainline_deck_z(y):
    """Deck height anywhere on F-1, used to sit vehicles and lights on it."""
    return _mainline_at(y)[1]


# =================================================================== F-2 ring

RING_Y = 1214.0
RING_X = -830.0
RING_CORNER_RADIUS = 40.0
RING_EAST_END = MAP_X1                    # 800
RING_SOUTH_END = MAP_Y0                   # -360

# The north leg crosses the river channel's northern remnant: a 1.2m swale
# between x=330 and x=400 whose sides pitch at 8%. The freeway carries a level
# causeway across it at the height of its own shoulders, so the profile meets
# terrain exactly at both ends and has no kink at all.
RING_CAUSEWAY = (330.0, 400.0)
RING_CAUSEWAY_Z = ROAD_TOP + min(terrain_height(RING_CAUSEWAY[0], RING_Y),
                                 terrain_height(RING_CAUSEWAY[1], RING_Y))

# The system interchange with F-1, at (300, 1214). F-2 lifts over F-1 rather
# than the other way round: F-1 is on the ground here after its 5% descent and
# has only 66m left before the map edge, which is nowhere near enough to bring
# a 6.5m overpass back down. Lifting the ring instead leaves the expressway's
# own terminus at grade all the way out of the world.
#
# The overpass carries a flat crown either side of the crossing rather than a
# single peak. That is what lets the fourth ramp pass beneath the ring at
# x=340 instead of needing a second flyover.
RING_OVERPASS_X = NORTH_JUNCTION_X
RING_OVERPASS_CROWN = 45.0
RING_OVERPASS_GRADE = 0.058
RING_OVERPASS_RAMP = 140.0


def _ring_overpass_deck():
    """Set from the highest ground anywhere under the crown, not just the
    crossing: the ground rises 0.5m between x=300 and the crown's east end."""
    highest = max(terrain_height(x, RING_Y)
                  for x in range(int(RING_OVERPASS_X - RING_OVERPASS_CROWN),
                                 int(RING_OVERPASS_X + RING_OVERPASS_CROWN) + 1, 5))
    return highest + ROAD_TOP + UNDERPASS_CLEARANCE + 1.05 + 0.30


RING_OVERPASS_DECK = _ring_overpass_deck()




# The north leg does not run straight. The North Crown Campus stands at
# (-370, 1088) with a declared 200 x 280m footprint, so its northern edge is at
# y=1228 -- fourteen metres north of where the ring wanted to be. The campus is
# built and cannot move, so the freeway does: it holds y=1252 from the
# north-west corner across to x=-240, clearing the campus by 12m at the deck
# edge, then eases back down to y=1214 over a 200m transition and runs straight
# to the eastern map edge. IC-4 is at x=300 and is unaffected.
RING_NORTH_JOG_Y = 1252.0
RING_NORTH_TRANSITION = (
    (-240.0, RING_NORTH_JOG_Y), (-192.0, 1251.2), (-146.0, 1247.4),
    (-104.0, 1240.6), (-66.0, 1231.4), (-34.0, 1221.6), (-8.0, 1215.6),
    (16.0, RING_Y),
)


def ring_corner_points():
    """The north-west fillet, from the north leg onto the west leg."""
    centre = (RING_X + RING_CORNER_RADIUS, RING_NORTH_JOG_Y - RING_CORNER_RADIUS)
    return _arc(centre, RING_CORNER_RADIUS, 90.0, 180.0)


def ring_spine():
    """The whole ring in plan, east terminus to south terminus."""
    corner = ring_corner_points()
    return (((RING_EAST_END, RING_Y),) + RING_NORTH_TRANSITION[::-1]
            + tuple(corner) + ((RING_X, RING_SOUTH_END),))


def ring_height(x, y):
    """The ring's authored height at a point on its centreline.

    The causeway and the overpass approach overlap between x=330 and x=354, so
    they compose: the causeway sets the base the overpass then climbs from.
    Treating them as alternatives put a 1.17m step in the deck at x=354.
    """
    ground = terrain_height(x, y) + ROAD_TOP
    if abs(y - RING_Y) > 1.0:
        return ground
    base = ground
    if RING_CAUSEWAY[0] <= x <= RING_CAUSEWAY[1]:
        base = max(base, RING_CAUSEWAY_Z)
    # The approaches are a fixed gradient down from the deck, not a fraction of
    # the ground beneath them. Scaling by the ground put a 9.2% pitch at x=449,
    # where the meadow rises under a ramp that was already descending.
    reach = abs(x - RING_OVERPASS_X) - RING_OVERPASS_CROWN
    if reach <= RING_OVERPASS_RAMP:
        base = max(base, RING_OVERPASS_DECK
                   - max(0.0, reach) * RING_OVERPASS_GRADE)
    return base


def ring_points(step=3.0):
    """The ring's centreline with heights: at grade but for two structures."""
    return tuple((x, y, ring_height(x, y))
                 for x, y in _densify(ring_spine(), step))


def ring_overpass_bounds():
    """Plan footprint of the raised section, for INTENTIONALLY_RAISED_ROADS."""
    half = FREEWAY_WIDTH / 2.0 + STRUCTURE_EXTRA + 2.0
    reach = RING_OVERPASS_CROWN + RING_OVERPASS_RAMP + 6.0
    return (RING_OVERPASS_X - reach, RING_OVERPASS_X + reach,
            RING_Y - half, RING_Y + half)


# ================================================================ collectors
#
# The tier Followville did not have. Each one exists to give a freeway ramp
# somewhere to land and a set of local streets somewhere to go.

# East Line Road threads a 24m gap: the Southline homes stand at x=190.2..191.4
# and the viaduct's structure edge is at x=209.1. At x=204 and 10m wide it
# keeps 7.6m from the nearest house and stops 0.1m short of the structure, and
# its eastern kerb lands within a metre of where all six streets stop.
EAST_LINE_ROAD_X = 204.0
EAST_LINE_ROAD_WIDTH = 10.0
EAST_LINE_ROAD = ((EAST_LINE_ROAD_X, 296.0), (EAST_LINE_ROAD_X, 500.0))
EAST_LINE_NORTH_X = 196.0
EAST_LINE_ROAD_NORTH = ((EAST_LINE_NORTH_X, 786.0), (EAST_LINE_NORTH_X, 1180.0))
EAST_LINE_NORTH_TURNAROUND = (EAST_LINE_NORTH_X, 1180.0)
TURNAROUND_RADIUS = 9.5

# The two ring links. Both have to reach x=-750, where West Line Road runs and
# the West Quarter's cross streets end -- but a column of homes stands at
# x=-758.5 fronting it from the west, all the way from y=425 to y=1107. The
# links land in the two gaps in that column: y=810, where Orchard Street meets
# West Line Road and the nearest home is 19.6m away, and y=500, in the 45m
# break between the homes at y=478.98 and y=524.07.
# -940 rather than -930 so the western end is back on the ground: the bridge's
# western approach runs 110m out from x=-830, and a turnaround bulb half a
# metre in the air is not a road end, it is a diving board.
ORCHARD_LINK = ((-940.0, 810.0), (-750.0, 810.0))
WEST_LINE_LINK = ((-940.0, 500.0), (-750.0, 500.0))

COLLECTORS = (
    {"name": "East Line Road", "points": EAST_LINE_ROAD,
     "width": EAST_LINE_ROAD_WIDTH, "elevated": False,
     "note": "collects the six streets that dead-end at x=210"},
    {"name": "East Line Road North", "points": EAST_LINE_ROAD_NORTH,
     "width": COLLECTOR_WIDTH, "elevated": False,
     "note": "Crown Fields' eastern edge; ends in a turnaround at y=1180"},
)


def collector_points(collector, step=3.0):
    return _at_grade(_densify(collector["points"], step))


# ============================================================== interchanges


def _fit_ramp(shoulder_x, cross_y, side, terminal, z_deck, z_ground, bulge,
              max_grade):
    """Lay out one ramp long enough to hold its grade, then apply the profile.

    The gore is pushed further from the cross road until the curve is long
    enough for the height it has to lose. That is the whole difference between
    a ramp and a diagonal line: the existing four drop 8.8m in 74m.
    """
    drop = abs(z_deck - z_ground)
    needed = max(drop / max_grade, 70.0)
    along = 45.0
    plan = _bezier((shoulder_x, cross_y + side * along), terminal, bulge)
    for _ in range(80):
        if _length(plan) >= needed:
            break
        along += 5.0
        plan = _bezier((shoulder_x, cross_y + side * along), terminal, bulge)
    return plan


def _diamond(name, cross_y, deck_z, terminal_west, terminal_east,
             centre_x=None, west_bow=1.0):
    """A four-ramp diamond, correctly named for the direction each ramp serves.

    Right-hand traffic. The southbound carriageway is west of the median and
    the northbound is east, which is what the existing ramp geometry already
    assumed even though its four names said the opposite: the ramp called
    "southbound-off" occupies the south-west quadrant, and the south-west
    quadrant ramp of a diamond is the southbound *entrance*.

    Exits leave, and entrances join, at the outside shoulder -- never
    mid-carriageway, which is where all four of the existing ones start.
    """
    cx = EXPRESSWAY_X if centre_x is None else centre_x
    west = cx - SHOULDER_HALF
    east = cx + SHOULDER_HALF
    west_xy, west_z = terminal_west[:2], terminal_west[2]
    east_xy, east_z = terminal_east[:2], terminal_east[2]
    ramps = [
        # North-west quadrant: leave the southbound deck, land west.
        {"name": "%s southbound exit" % name, "carriageway": "southbound",
         "role": "exit",
         "plan": _fit_ramp(west, cross_y, +1, west_xy, deck_z, west_z,
                           -16.0 * west_bow, MAX_RAMP_GRADE),
         "z": (deck_z, west_z)},
        # South-west quadrant: leave the west terminal, join southbound.
        {"name": "%s southbound entrance" % name, "carriageway": "southbound",
         "role": "entrance",
         "plan": _fit_ramp(west, cross_y, -1, west_xy, deck_z, west_z,
                           16.0 * west_bow, MAX_ENTRANCE_GRADE),
         "z": (west_z, deck_z), "reverse": True},
        # South-east quadrant: leave the northbound deck, land east.
        {"name": "%s northbound exit" % name, "carriageway": "northbound",
         "role": "exit",
         "plan": _fit_ramp(east, cross_y, -1, east_xy, deck_z, east_z,
                           16.0, MAX_RAMP_GRADE),
         "z": (deck_z, east_z)},
        # North-east quadrant: leave the east terminal, join northbound.
        {"name": "%s northbound entrance" % name, "carriageway": "northbound",
         "role": "entrance",
         "plan": _fit_ramp(east, cross_y, +1, east_xy, deck_z, east_z,
                           -16.0, MAX_ENTRANCE_GRADE),
         "z": (east_z, deck_z), "reverse": True},
    ]
    return [_finish_ramp(ramp) for ramp in ramps]


def _finish_ramp(ramp):
    plan = list(ramp["plan"])
    if ramp.pop("reverse", False):
        plan.reverse()
    z_start, z_end = ramp.pop("z")
    ramp["points"] = _limit_grade(_graded(plan, z_start, z_end, floor=ROAD_TOP),
                                  MAX_RAMP_GRADE)
    ramp.pop("plan")
    return ramp


IC1_Y = 396.0
IC2_Y = 654.0
IC3_Y = 920.0
IC5_Y = 810.0
IC6_Y = 500.0

_INTERCHANGE_CACHE = None


def interchanges():
    """Every interchange, south to north. Cached: the fits are iterative."""
    global _INTERCHANGE_CACHE
    if _INTERCHANGE_CACHE is not None:
        return _INTERCHANGE_CACHE
    entries = []

    # IC-1 Northgate. The viaduct stands 6.8m clear of the ground here, so the
    # cross road passes under it and reaches an eastern terminal in open
    # meadow, exactly the way Crown Boulevard already does at IC-2. The west
    # terminal is the East Line Road junction, because the Southline houses at
    # x=183..190 leave no room further west.
    ic1_ground = terrain_height(EAST_LINE_ROAD_X, IC1_Y) + ROAD_TOP
    entries.append({
        "id": "IC-1", "name": "Northgate", "route": "F-1", "y": IC1_Y,
        "kind": "diamond",
        "serves": "Northgate and Southline, via East Line Road",
        "cross_road": {
            "name": "Northgate interchange road",
            "points": ((EAST_LINE_ROAD_X, IC1_Y), (262.0, IC1_Y)),
            "width": CROSS_ROAD_WIDTH},
        # west_bow is flipped so the two southbound ramps bow east, away from
        # the Southline homes at x=191.4 rather than towards them.
        "ramps": _diamond("Northgate", IC1_Y, EXPRESSWAY_DECK_Z,
                          (EAST_LINE_ROAD_X, IC1_Y, ic1_ground),
                          (262.0, IC1_Y, terrain_height(262.0, IC1_Y) + ROAD_TOP),
                          west_bow=-1.0),
        "high_mast": ((EXPRESSWAY_X - 21.0, IC1_Y - 30.0),
                      (EXPRESSWAY_X + 21.0, IC1_Y + 30.0))})

    # IC-2 Crown Boulevard. The existing diamond keeps its terminals at x=186
    # and x=258 and its cross road, which already runs east to x=278 to reach
    # them. What changes is the ramps themselves.
    entries.append({
        "id": "IC-2", "name": "Crown Boulevard", "route": "F-1", "y": IC2_Y,
        "kind": "diamond",
        "serves": "Crown Quarter and its twenty towers",
        "cross_road": None,
        "ramps": _diamond("Crown Boulevard", IC2_Y, EXPRESSWAY_DECK_Z,
                          (186.0, IC2_Y, TERRACE_DATUM + 0.18),
                          (258.0, IC2_Y, TERRACE_DATUM + 0.18)),
        "high_mast": ((EXPRESSWAY_X - 23.0, IC2_Y - 32.0),
                      (EXPRESSWAY_X + 23.0, IC2_Y + 32.0))})

    # IC-3 Crown Fields. On the northern descent: the deck is 11.6m over flat
    # ground, so the cross road passes under with room to spare.
    ic3_deck = mainline_deck_z(IC3_Y)
    ic3_ground = terrain_height(EAST_LINE_NORTH_X, IC3_Y) + ROAD_TOP
    entries.append({
        "id": "IC-3", "name": "Crown Fields", "route": "F-1", "y": IC3_Y,
        "kind": "diamond",
        "serves": "Crown Fields, via East Line Road North",
        "cross_road": {
            "name": "Crown Fields interchange road",
            "points": ((EAST_LINE_NORTH_X, IC3_Y), (262.0, IC3_Y)),
            "width": CROSS_ROAD_WIDTH},
        "ramps": _diamond("Crown Fields", IC3_Y, ic3_deck,
                          (EAST_LINE_NORTH_X, IC3_Y, ic3_ground),
                          (262.0, IC3_Y, terrain_height(262.0, IC3_Y) + ROAD_TOP)),
        "high_mast": ((EXPRESSWAY_X - 21.0, IC3_Y - 30.0),
                      (EXPRESSWAY_X + 21.0, IC3_Y + 30.0))})

    # IC-5 Orchard and IC-6 West Line, on the ring's west leg, which runs
    # north-south exactly as F-1 does -- so they are ordinary diamonds, with
    # one difference: the ring is on the ground, so the link road bridges over
    # it and the ramps climb to reach the link instead of descending from it.
    #
    # Both links land where a road is built today, and both had to dodge the
    # column of homes at x=-758.5 that fronts West Line Road from the west for
    # 680m. IC-5 lands at (-750, 810), the Orchard Street junction, 19.6m from
    # the nearest of them. IC-6 lands at (-750, 500), in the 45m break between
    # the homes at y=478.98 and y=524.07, 14m north of Kettle Row West's
    # western end.
    for ident, name, y, link, serves in (
            ("IC-5", "Orchard", IC5_Y, ORCHARD_LINK,
             "the West Quarter and Gatehouse Green"),
            ("IC-6", "West Line", IC6_Y, WEST_LINE_LINK,
             "Harrow Green and cross-town Kettle Row")):
        ground = terrain_height(RING_X, y) + ROAD_TOP
        deck = ground + UNDERPASS_CLEARANCE + 1.05 + 0.30
        # The bridge approaches are deliberately unequal. West of the ring
        # there is open meadow to the map edge, so that side gets 110m and a
        # 6.0% grade; east of it the link has to be back on the ground by
        # x=-750 where it meets a built junction, which leaves 80m and 8.2%.
        bridge = (RING_X, deck, 110.0, 80.0)
        west_terminal = (RING_X - 58.0, y,
                         _overbridge_height(RING_X - 58.0, y, bridge))
        east_terminal = (RING_X + 58.0, y,
                         _overbridge_height(RING_X + 58.0, y, bridge))
        entries.append({
            "id": ident, "name": name, "route": "F-2", "y": y,
            "kind": "diamond", "serves": serves,
            "cross_road": {"name": "%s interchange road" % name,
                           "points": link, "width": CROSS_ROAD_WIDTH,
                           "overbridge": bridge},
            "ramps": _diamond(name, y, ground, west_terminal, east_terminal,
                              centre_x=RING_X),
            "high_mast": ((RING_X - 30.0, y - 24.0), (RING_X + 30.0, y + 24.0))})

    # IC-4, the system interchange, where F-1 ends. See system_ramps().
    entries.append({
        "id": "IC-4", "name": "Ring", "route": "F-1 x F-2", "y": RING_Y,
        "kind": "trumpet", "serves": "freeway to freeway",
        "cross_road": None,
        "ramps": system_ramps(),
        "high_mast": ((NORTH_JUNCTION_X - 54.0, RING_Y - 46.0),
                      (NORTH_JUNCTION_X + 58.0, RING_Y - 40.0),
                      (NORTH_JUNCTION_X + 40.0, RING_Y + 44.0))})
    _INTERCHANGE_CACHE = tuple(entries)
    return _INTERCHANGE_CACHE


def _overbridge_height(x, y, bridge):
    """Height of a link road on its bridge over the ring."""
    bridge_x, deck, west_ramp, east_ramp = bridge
    ground = terrain_height(x, y) + ROAD_TOP
    reach = abs(x - bridge_x)
    ramp = west_ramp if x < bridge_x else east_ramp
    if reach >= ramp:
        return ground
    return ground + (deck - ground) * (1.0 - reach / ramp)


def system_ramps():
    """IC-4: a trumpet, because F-1 ends here rather than crossing.

    A freeway meeting another freeway at a T has one unavoidable problem:
    traffic off the stem has to reach both carriageways of the through road,
    so something must cross something. Trumpets solve it with a loop and one
    bridge. Here the bridge already exists -- the ring is on its own overpass
    across the whole junction -- so the two loops simply pass beneath its crown
    and the interchange needs no structure of its own.

    F-1 could not both cross the ring and reach the map edge: it is on the
    ground after its 5% descent and has 66m left, which is nowhere near enough
    to climb over a freeway and come back down. Ending it here is the honest
    answer, and a system interchange is a real terminus. The ring carries the
    regional connection out of the world instead, twice.

    Nothing in here crosses F-1: everything that has to change sides does it
    north of NORTH_SPLIT_Y, where the expressway no longer exists.
    """
    split = (NORTH_JUNCTION_X, NORTH_SPLIT_Y)
    west = NORTH_JUNCTION_X - SHOULDER_HALF
    east = NORTH_JUNCTION_X + SHOULDER_HALF
    eb_shoulder = RING_Y - SHOULDER_HALF
    wb_shoulder = RING_Y + SHOULDER_HALF
    ramps = []

    def add(name, carriageway, role, plan, z_start, z_end):
        ramps.append({"name": name, "carriageway": carriageway, "role": role,
                      "points": _limit_grade(
                          _graded(plan, z_start, z_end, floor=ROAD_TOP),
                          MAX_RAMP_GRADE)})

    def ground(x, y):
        return terrain_height(x, y) + ROAD_TOP

    # 1. The free right: F-1 northbound swings east onto the ring, entirely in
    #    the south-east quadrant, crossing nothing.
    add("Ring northbound to eastbound", "northbound", "exit",
        _bezier((east, split[1] - 56.0), (470.0, eb_shoulder), 46.0),
        ground(east, split[1] - 56.0), ring_height(470.0, RING_Y))

    # 2. The free right, mirrored: the ring's eastbound carriageway drops south
    #    onto F-1, entirely in the south-west quadrant.
    add("Ring eastbound to southbound", "southbound", "entrance",
        _bezier((200.0, eb_shoulder), (west, split[1] - 46.0), 40.0),
        ring_height(200.0, RING_Y), ground(west, split[1] - 46.0))

    # 3. The loop: F-1 northbound to the ring westbound. East, north under the
    #    ring's crown at x=332, then west along its northern side to a merge
    #    where the ring has come back down to 8.1m.
    add("Ring northbound to westbound", "northbound", "exit",
        [(east, split[1] - 30.0), (334.0, 1168.0), (338.0, 1206.0),
         (330.0, 1242.0), (300.0, 1258.0), (250.0, 1250.0),
         (206.0, wb_shoulder + 4.0), (200.0, wb_shoulder)],
        ground(east, split[1] - 30.0), ring_height(200.0, RING_Y))

    # 4. The other loop: the ring westbound to F-1 southbound. West along the
    #    ring's northern side, under the crown at x=308, then south to the
    #    expressway's western shoulder.
    add("Ring westbound to southbound", "southbound", "entrance",
        [(430.0, wb_shoulder), (386.0, 1252.0), (340.0, 1258.0),
         (312.0, 1238.0), (308.0, 1210.0), (300.0, 1186.0),
         (292.0, 1150.0), (west, split[1] - 76.0)],
        ring_height(430.0, RING_Y), ground(west, split[1] - 76.0))
    return ramps


def cross_road_points(cross, step=3.0):
    """An interchange cross road, lifted over the ring where it has to be."""
    plan = _densify(cross["points"], step)
    bridge = cross.get("overbridge")
    if not bridge:
        return _at_grade(plan)
    points = []
    for x, y in plan:
        ground = terrain_height(x, y) + ROAD_TOP
        lifted = _overbridge_height(x, y, bridge)
        if lifted > ground:
            points.append((x, y, lifted))
        else:
            points.append((x, y, ground))
    return _limit_grade(points, MAX_RAMP_GRADE)


# ================================================================== vehicles
#
# Static, so direction of travel is the whole game. Right-hand traffic: the
# west carriageway runs -Y and the east carriageway runs +Y. build_car's body
# is 3.6m along local +X, so a southbound car is rot=-pi/2 and a northbound one
# is rot=+pi/2. Every vehicle sits on the deck it is driving on, never on the
# terrain underneath it.

SOUTHBOUND_ROT = -math.pi / 2.0
NORTHBOUND_ROT = math.pi / 2.0
EASTBOUND_ROT = 0.0
WESTBOUND_ROT = math.pi
VEHICLE_DECK_LIFT = DECK_SURFACE + 0.01


def _traffic_run(seed0, span, place, height, rot_forward, rot_reverse,
                 spacing=54.0, jitter=23.0):
    """Deterministic vehicles down one road, both carriageways.

    ``place(t, offset)`` returns a world x,y for a position along the road and
    a signed offset from the median; ``height(t)`` returns the deck there.
    Gaps are varied so the line does not read as a toy train, and the seed
    walks so no two neighbours draw the same body colour.
    """
    vehicles = []
    start, end = span
    seed = seed0
    for direction, rot in ((1, rot_forward), (-1, rot_reverse)):
        for lane_index, lane in enumerate(LANE_CENTRES):
            position = start + spacing * (0.31 + 0.27 * lane_index)
            while position < end:
                x, y = place(position, direction * lane)
                vehicles.append({"type": "car", "gx": 0, "gy": 0,
                                 "px": round(x, 3), "py": round(y, 3),
                                 "pz": round(height(position) + VEHICLE_DECK_LIFT, 3),
                                 "rot": rot, "seed": seed})
                seed += 1
                position += spacing + jitter * (0.5 + 0.5 * math.sin(seed * 1.7))
    return vehicles


def mainline_vehicles():
    """Traffic on F-1, from the Crown Approach to the northern terminus."""
    return _traffic_run(
        41000, (CREST_JUNCTION[1] + 60.0, NORTH_TERMINUS_Y - 30.0),
        lambda y, offset: (mainline_x(y) + offset, y),
        lambda y: mainline_deck_z(y) - DECK_SURFACE,
        NORTHBOUND_ROT, SOUTHBOUND_ROT, spacing=58.0)


def ring_north_vehicles():
    """The ring's north leg. Its southern carriageway runs east."""
    return _traffic_run(
        43000, (RING_X + 80.0, RING_EAST_END - 40.0),
        lambda x, offset: (x, RING_Y - offset),
        lambda x: ring_height(x, RING_Y) - DECK_SURFACE,
        EASTBOUND_ROT, WESTBOUND_ROT, spacing=76.0)


def ring_west_vehicles():
    """The ring's west leg. Its western carriageway runs south."""
    return _traffic_run(
        45000, (RING_SOUTH_END + 50.0, RING_Y - 110.0),
        lambda y, offset: (RING_X + offset, y),
        lambda y: ring_height(RING_X, y) - DECK_SURFACE,
        NORTHBOUND_ROT, SOUTHBOUND_ROT, spacing=82.0)


def vehicles():
    return tuple(mainline_vehicles() + ring_north_vehicles() + ring_west_vehicles())


# ================================================================== lighting
#
# Freeway lighting, not street lighting: tall masts on the deck itself rather
# than on the ground below it, and high-mast towers at the interchanges.
# Everything is placed under an object name containing "metro_streetlight" so
# _build_video_practicals() finds it -- the existing viaduct's fixtures were
# named metro_expressway_light* and matched nothing, which is why the deck has
# looked unlit at night.

MAST_SPACING = 64.0
MAST_HEIGHT = 11.5
MAST_OFFSET = SHOULDER_HALF + 0.95
HIGH_MAST_HEIGHT = 20.0


def mainline_masts():
    """(x, y, deck z, arm direction) down F-1, alternating sides."""
    masts = []
    y = CREST_JUNCTION[1] + 70.0
    flip = 0
    while y < NORTH_TERMINUS_Y - 20.0:
        side = -1 if flip % 2 else 1
        masts.append((mainline_x(y) + side * MAST_OFFSET, y,
                      mainline_deck_z(y), -side))
        y += MAST_SPACING
        flip += 1
    return tuple(masts)


def ring_masts():
    masts = []
    flip = 0
    x = RING_X + 70.0
    while x < RING_EAST_END - 20.0:
        side = -1 if flip % 2 else 1
        masts.append((x, RING_Y + side * MAST_OFFSET, ring_height(x, RING_Y),
                      -side))
        x += MAST_SPACING * 1.5
        flip += 1
    y = RING_SOUTH_END + 70.0
    flip = 0
    while y < RING_Y - 110.0:
        side = -1 if flip % 2 else 1
        masts.append((RING_X + side * MAST_OFFSET, y,
                      ring_height(RING_X, y), -side))
        y += MAST_SPACING * 1.5
        flip += 1
    return tuple(masts)


def high_masts():
    towers = []
    for entry in interchanges():
        for x, y in entry["high_mast"]:
            towers.append((x, y, terrain_height(x, y)))
    return tuple(towers)


# ============================================================== declarations
#
# What world_layout has to declare and what check_world_geometry has to audit.
# Kept here so the road data and the paperwork about it cannot drift apart.

def named_roads():
    """(name, points-with-z, half width) for every centreline this creates."""
    roads = [("Crown Approach", crown_approach_points(), ARTERIAL_WIDTH / 2.0),
             ("Crown Expressway North", north_extension_points(),
              FREEWAY_WIDTH / 2.0),
             ("Ring Freeway", ring_points(), FREEWAY_WIDTH / 2.0)]
    for collector in COLLECTORS:
        roads.append((collector["name"], collector_points(collector),
                      collector["width"] / 2.0))
    for entry in interchanges():
        cross = entry.get("cross_road")
        if cross:
            roads.append((cross["name"], cross_road_points(cross),
                          cross["width"] / 2.0))
        for ramp in entry["ramps"]:
            roads.append((ramp["name"], ramp["points"], RAMP_WIDTH / 2.0))
    return tuple(roads)


def authored_elevation_roads():
    """Roads that carry their own heights rather than following the terrain."""
    return frozenset(name for name, _points, _half in named_roads())


# The audit's own tolerance for a road deck riding above the ground. Anything
# over this has to be declared, so the declarations are derived from exactly
# that test rather than from a hand-drawn box that can fall out of step with
# the alignment it is supposed to describe. The first version of this function
# did draw boxes by hand, and the northern viaduct's box was still centred on
# x=222 after the alignment bent east to x=300 -- which the audit caught as a
# 1.86m float at (257.2, 1051.8).
_AUDIT_ROAD_FLOAT = 0.12
_AUDIT_DECK_THICKNESS = 0.10


def raised_road_regions():
    """Rectangles for INTENTIONALLY_RAISED_ROADS: (name, x0, x1, y0, y1)."""
    regions = []
    for name, points, half_width in named_roads():
        pad = half_width + STRUCTURE_EXTRA + 4.0
        run = []
        index = 0
        for point in list(points) + [None]:
            airborne = point is not None and (
                point[2] - terrain_height(point[0], point[1])
                - _AUDIT_DECK_THICKNESS > _AUDIT_ROAD_FLOAT * 0.5)
            if airborne:
                run.append(point)
                continue
            if len(run) > 1:
                xs = [p[0] for p in run]
                ys = [p[1] for p in run]
                regions.append(("%s raised %d" % (name, index),
                                min(xs) - pad, max(xs) + pad,
                                min(ys) - pad, max(ys) + pad))
                index += 1
            run = []
    return tuple(regions)


def audited_roads():
    """(name, [(x, y), ...]) for check_world_geometry.every_road()."""
    return tuple((name, [(x, y) for x, y, _z in points])
                 for name, points, _half in named_roads())


def turnarounds():
    """Every road end that is a turnaround rather than a junction.

    Five of them, and every one exists because the alternative is a cut end in
    a meadow. The two interchange cross roads east of the expressway have
    nothing to run on to -- open ground out to the river at x=350 -- and the
    two ring links have nothing west of them but the map edge. Each one is the
    point where that road's two ramp terminals meet, so a bulb is what a
    driver would actually find there.
    """
    bulbs = [EAST_LINE_NORTH_TURNAROUND]
    for entry in interchanges():
        cross = entry.get("cross_road")
        if not cross:
            continue
        points = cross_road_points(cross)
        far = points[-1] if entry["route"] == "F-1" else points[0]
        bulbs.append((far[0], far[1]))
    return tuple(bulbs)


def is_active(buildings):
    """The highway reveals with the expressway it upgrades."""
    return any(building.get("type") == "metrotower" for building in buildings)


# ================================================================ validation


def _worst_grade(points):
    worst, at = 0.0, None
    for a, b in zip(points, points[1:]):
        run = math.hypot(b[0] - a[0], b[1] - a[1])
        if run < 0.5:
            continue
        grade = abs(b[2] - a[2]) / run
        if grade > worst:
            worst, at = grade, (b[0], b[1])
    return worst, at


def validate_plan():
    """Grades, clearances and terminus honesty, checked from the data itself."""
    errors = []

    for name, points, limit in (
            ("Crown Approach", crown_approach_points(), MAX_MAINLINE_GRADE),
            ("Crown Expressway North", north_extension_points(), MAX_MAINLINE_GRADE),
            ("Ring Freeway", ring_points(), MAX_MAINLINE_GRADE)):
        grade, at = _worst_grade(points)
        if grade > limit + 1e-6:
            errors.append("%s reaches %.1f%% at (%.1f, %.1f), over its %.1f%% limit"
                          % (name, grade * 100, at[0], at[1], limit * 100))

    for entry in interchanges():
        for ramp in entry["ramps"]:
            grade, at = _worst_grade(ramp["points"])
            if grade > MAX_RAMP_GRADE + 1e-6:
                errors.append("%s reaches %.1f%% at (%.1f, %.1f)"
                              % (ramp["name"], grade * 100, at[0], at[1]))

    # Nothing may be authored below the ground it stands on.
    for name, points, _half in named_roads():
        for x, y, z in points:
            if z < terrain_height(x, y) + ROAD_TOP - 1e-6:
                errors.append("%s is under the ground at (%.1f, %.1f)" % (name, x, y))
                break

    # Every road end must be a junction, a map edge or a declared turnaround.
    # F-1's northern end is the trumpet split at IC-4; the ring carries the
    # regional connection off the map from there.
    if abs(north_extension_points()[-1][1] - NORTH_SPLIT_Y) > 0.01:
        errors.append("the northern terminus is not the IC-4 trumpet split")
    ring = ring_points()
    if abs(ring[0][0] - MAP_X1) > 0.01 or abs(ring[-1][1] - MAP_Y0) > 0.01:
        errors.append("a ring terminus is not at the map edge")
    if crown_approach_points()[0][:2] != CREST_JUNCTION:
        errors.append("the southern terminus is not the Crest junction")

    # Every vehicle must sit on a deck, not in a field.
    for vehicle in vehicles():
        if vehicle["pz"] < terrain_height(vehicle["px"], vehicle["py"]) - 0.6:
            errors.append("a vehicle at (%.1f, %.1f) is %.2fm below the ground"
                          % (vehicle["px"], vehicle["py"],
                             terrain_height(vehicle["px"], vehicle["py"]) - vehicle["pz"]))
            break

    # Underpasses have to be tall enough to be underpasses.
    for entry in interchanges():
        cross = entry.get("cross_road")
        if not cross or cross.get("overbridge"):
            continue
        deck = mainline_deck_z(entry["y"])
        ground = terrain_height(EXPRESSWAY_X, entry["y"]) + ROAD_TOP
        if deck - 1.05 - ground < UNDERPASS_CLEARANCE:
            errors.append("%s has only %.2fm under the deck"
                          % (entry["id"], deck - 1.05 - ground))
    return errors


if __name__ == "__main__":
    failures = validate_plan()
    if failures:
        raise SystemExit("\n".join(failures))
    ring_length = _length(ring_points())
    f1 = (_length(crown_approach_points()) + (EXPRESSWAY_Y1 - EXPRESSWAY_Y0)
          + _length(north_extension_points()))
    ramps = sum(len(entry["ramps"]) for entry in interchanges())
    print("Followville highway system")
    print("  F-1 Crown Expressway   %.0fm  (%.0fm of it new)"
          % (f1, f1 - (EXPRESSWAY_Y1 - EXPRESSWAY_Y0)))
    print("  F-2 Ring Freeway       %.0fm" % ring_length)
    print("  interchanges           %d, %d ramps" % (len(interchanges()), ramps))
    print("  collectors             %d, %.0fm"
          % (len(COLLECTORS), sum(_length(c["points"]) for c in COLLECTORS)))
    print("  vehicles               %d" % len(vehicles()))
    print("  lighting               %d masts, %d high-mast towers"
          % (len(mainline_masts()) + len(ring_masts()), len(high_masts())))
    print("  northern touchdown     y=%.0f" % north_extension_touchdown())
    print("  worst mainline grade   %.2f%%"
          % (max(_worst_grade(crown_approach_points())[0],
                 _worst_grade(north_extension_points())[0],
                 _worst_grade(ring_points())[0]) * 100))
    print("  worst ramp grade       %.2f%%"
          % (max(_worst_grade(r["points"])[0]
                 for e in interchanges() for r in e["ramps"]) * 100))
