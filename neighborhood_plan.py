"""Deterministic neighborhood reserve for Followville populations 135..750.

This module contains geometry only; importing it creates no Blender objects and
never edits world_state.json.  The generator consumes the next address(es) when
ordinary houses are added.  Future roads remain data until a house assigned to
that portion of road exists.
"""

import math

from world_layout import DISTRICT_OFFSETS

BASE_POPULATION = 134
LEGACY_RESERVE_CAPACITY = 366
RIVER_RESERVE_CAPACITY = 616
# HOUSE_CAPACITY is derived from STREETS further down -- see the note there.
ROAD_HALF_WIDTH = 3.0
HOUSE_SETBACK = 8.5
HOUSE_ROAD_CLEARANCE = 6.75
CULDESAC_CLEARANCE = 12.0

# ── how much room an address actually needs ─────────────────────────────────
#
# Until 2026-08-09 placement enforced one flat gap between address POINTS,
# whatever stood on them. That is right for a ~9m house and meaningless for a
# fire station, which is 36m across: chapter three gave slots a `type` but left
# them the house's clearance AND the house's setback, so houses sat 7.35m from
# the centre of a building six times that wide, and six of the ten reserved
# specials had a road centreline running straight through their own footprint.
#
# These are the authored GROUND extents, read out of neighborhood_blender's
# builders in local coordinates with the front on local -Y. They are measured,
# not derived from SIZE*LOT: the filling station's forecourt is 17m and the
# diner's lawn 15.4m, both wider than the SIZE-1 lot a *_LOT_ box would give
# them, so a SIZE-derived envelope would under-cover the two most common
# specials in the reserve.
TYPE_FOOTPRINT = {
    #                     x0      x1      y0      y1
    "house":            (-4.59,  4.59,  -4.90,  3.80),
    "gasstation":       (-8.50,  8.50,  -8.50,  6.50),
    "restaurant":       (-7.70,  7.70,  -7.50,  6.30),
    "pond":             (-6.20,  6.20,  -6.20,  6.20),
    "park":            (-12.25, 12.25, -12.25, 12.25),
    "elementaryschool": (-14.20, 14.20, -14.20, 14.20),
    "followmart":      (-17.00, 17.00, -17.00, 17.00),
    "firestation":     (-18.00, 18.00, -18.00, 18.00),
}
# place_instance scales a planned HOUSE into its lot; nothing else is scaled.
HOUSE_LOT_SCALE = 0.78
# Lots at branch merges and adjacent cul-de-sac arcs are intentionally tighter
# than the main road frontage, and their houses are built smaller to match.
# The set was audited against the original 366 reserved addresses with oriented
# boxes. It lives here rather than in the generator because the plan's own
# overlap checks need it: measuring these addresses at the standard .78 lot
# overstates them by 42% and reports 53 pairs of BUILT houses as overlapping.
SUBURBAN_TIGHT_PLAN_IDS = {
    7, 19, 39, 40, 61, 62, 63, 93, 94, 95, 115, 116, 124, 125, 126, 128,
    134, 135, 136, 158, 160, 162, 163, 164, 165, 180, 182, 193, 194, 195,
    196, 197, 205, 206, 207, 208, 211, 212, 255, 256, 257, 258, 259, 260,
    271, 280, 291, 292, 293, 294, 295, 296, 297, 298, 308, 310, 312, 313,
    314, 315, 316, 317, 318, 326, 327, 349, 350,
}
TIGHT_LOT_SCALE = 0.55
# Where a special's front edge stands, measured from its road centreline.
#
# A planned house at .78 scale carries its own front edge 4.68m out, and
# matching that was the first thing tried -- it is what makes a filling station
# read as fronting the same street as its neighbours. It is 0.32m too close.
# Once a type is declared in LANDMARK_FOOTPRINTS, check_world_geometry holds it
# to ROAD_CLEARANCE (2.0m) beyond the road's 3.0m half-width, so a landmark's
# footprint has to start at least 5.0m from the centreline. At 4.68 every one
# of the ten specials would have failed the audit the day it was built.
FRONT_MARGIN = 5.20
# A special's footprint must keep this clear of any OTHER road centreline --
# the cross street beside it as much as its own frontage. It is set from
# check_world_geometry's rule, not chosen: that audit requires ROAD_CLEARANCE
# (2.0m) beyond the road's 3.0m half-width, so 5.0m, plus a little margin
# because the audit walks a densified outline and can sample a corner this one
# does not. At the suburban 3.75m the pond stood 3.97m off Maple Cross and
# would have failed the audit the day it was built.
SPECIAL_ROAD_CLEARANCE = 5.10
# Visible ground between a SPECIAL's footprint and its neighbour's. Two houses
# are held to a plainer rule -- they must not overlap -- because that is the
# actual requirement and because a margin on top of it would condemn addresses
# that are already built: #379 on Crossing Way and #585 on Marshlight Lane
# stand 7.67m apart at their streets' junction, with 0.25-0.50m between their
# lot envelopes, and neither may move.
SPECIAL_NEIGHBOUR_CLEARANCE = 1.50
HOUSE_NEIGHBOUR_CLEARANCE = 0.0
# A civic deck is a flat box laid on the terrain, so the fall across its
# footprint is exactly how proud it stands at its low corner. world_layout's
# DEFAULT_MAX_PAD_STAND is 1.60m; validate_plan() holds specials to it.
MAX_SPECIAL_PAD_FALL = 1.60

# ── the Northgate arterial ──────────────────────────────────────────────────
#
# The road that connects the chapter-three quarter to downtown. It lives here
# rather than only in the generator because build_plan() has to know about it:
# a reserved address that lands on the arterial is a house in the middle of the
# only road into the quarter, and nothing else would notice.
#
# The line is measured, not chosen. x=-93 is the downtown grid's westernmost
# vertical street, so the south end is a real crossroads with the y=87 street
# rather than a stub in a meadow, and the north end lands on the Northgate
# Avenue centreline 27m clear of Kiln Cross. Between them it runs up the gap
# between Creekside Bend (whose west edge is x=-52..-64) and Willow Hills
# (whose east edge is x=-123): the nearest of the 844 standing buildings is
# 29.4m away, and the steepest terrain grade along it is 0.090, well inside
# the .16 a road may climb.
#
# The reverted 2026-08-09 highway ran east-west along y=272 instead. That line
# is 4m from Pebble Court, whose houses stand at y=276.9-283.3 once Creekside
# Bend's +58 district offset is applied -- it was cleared against the reserve's
# RAW coordinates, where the same houses look 58m further south than they are.
NORTHGATE_ARTERIAL = ((-93.0, 86.0), (-93.0, 306.0))
ARTERIAL_HALF_WIDTH = 4.0
# Centreline to the centre of a reserved address. HOUSE_ROAD_CLEARANCE holds a
# house 6.75m off a suburban centreline, which is 3.75m beyond that road's 3.0m
# half-width; this is the same 3.75m beyond the arterial's wider 4.0m. Do not
# reduce it to the suburban figure: a planned house is 3.58m wide at .78 scale,
# so at 7.50m its own footprint would lie 8cm inside the asphalt.
ARTERIAL_CLEARANCE = ARTERIAL_HALF_WIDTH + 3.75
# It appears with the quarter it serves, so it is never a road to nowhere.
NORTHGATE_ARTERIAL_REVEAL = RIVER_RESERVE_CAPACITY + 1


def northgate_arterial_points(step=3.0):
    """The arterial's centreline, sampled closely enough to stay on the ground.

    Three metres, for the reason recorded against every other authored road
    here: _add_road_strip subdivides to two internally but the browser's walk
    surface uses these points as given, so coarser points drift the surface the
    player stands on away from the asphalt they can see.
    """
    points = []
    for a, b in zip(NORTHGATE_ARTERIAL, NORTHGATE_ARTERIAL[1:]):
        count = max(1, int(math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / step)))
        for index in range(count):
            t = index / count
            points.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    points.append(NORTHGATE_ARTERIAL[-1])
    return points

# Permanent river-chapter geography. The centerline runs north-to-south beyond
# the Day-27 city edge. Water is 24-30 m wide; a broader riparian reserve keeps
# houses, roads, and tree belts from crowding the banks. The first crossing is
# deliberately aligned with completed Summit Court and Day 28 Crossing Way.
RIVER_CENTERLINE = (
    # Continue past Northgate and Crown Quarter so the enlarged terrain does
    # not reveal a dry carved channel beyond the old y=520 endpoint.
    (365.0, 900.0), (348.0, 790.0), (360.0, 700.0), (346.0, 610.0),
    (352.0, 520.0), (365.0, 430.0), (350.0, 340.0),
    (368.0, 250.0), (356.0, 160.0), (372.0, 70.0),
    (360.0, -20.0), (378.0, -110.0), (362.0, -200.0),
    (374.0, -285.0), (388.0, -330.0),
)
RIVER_HALF_WIDTH = 14.0
RIVER_RIPARIAN_CLEARANCE = 30.0
RIVER_BRIDGE = {
    "name": "Founders Crossing",
    "approach": ((276.0, -217.0), (312.0, -216.0), (332.0, -214.0)),
    "deck": ((332.0, -214.0), (396.0, -215.0)),
    "landing": ((396.0, -215.0), (400.0, -215.0)),
    "reveal_at": LEGACY_RESERVE_CAPACITY + 1,
}

# Chapter three adds two dense gridded quarters on open ground north of
# everything built so far. Deliberately NOT more curved cul-de-sac suburbs --
# the existing long radial streets are the ones Cade wants to become main
# downtown arterials later, so these are laid out as short blocks on a
# rectilinear grid that a downtown can actually grow into.
#
# DISTRICTS and HOUSE_CAPACITY are both derived from STREETS below rather than
# written out by hand. Widening a special's clearance changes how many
# addresses a street can seat, and a hand-kept total silently disagrees with
# the plan the moment that happens.

# Addresses inside chapter three that are NOT ordinary houses. The key is a
# fraction of the way ALONG the street, not an address index: how many
# addresses a street can seat depends on how much room its specials take, so an
# index-keyed special moves every time the count is re-solved, and one declared
# past the end of a shortened street used to vanish without a word.
# build_plan() turns the fraction into an address index, so a special still
# keeps both a fixed growth number and a chosen position on the street.
#
# Everything here is an existing generator type; nothing needs a new asset to
# be reserved. The terrace datum and box live in
# downtown_visual_plan.terrain_height, which is the single shared walk surface;
# they are not duplicated here.

# Each street is intentionally independent and develops from its first point
# toward a cul-de-sac at its last point. Counts total 616. The original 366
# addresses remain unchanged; addresses 367-616 form the river chapter.
STREETS = (
    # Creekside Bend -- north of the current town
    dict(district="Creekside Bend", name="Creekside Lane", count=18,
         points=[(-35, 69), (-52, 100), (-58, 128), (-45, 154), (-20, 174), (8, 184)]),
    dict(district="Creekside Bend", name="Heron Court", count=18,
         points=[(-46, 109), (-20, 112), (8, 104), (32, 115), (48, 139), (45, 164)]),
    dict(district="Creekside Bend", name="Pebble Court", count=18,
         points=[(-15, 174), (-4, 201), (20, 218), (48, 216), (70, 198), (78, 174)]),

    # Willow Hills -- north-west high ground
    dict(district="Willow Hills", name="Willow Rise", count=20,
         points=[(-75, 64), (-105, 78), (-128, 101), (-142, 131), (-135, 162), (-112, 188)]),
    dict(district="Willow Hills", name="Foxglove Court", count=21,
         points=[(-124, 105), (-151, 93), (-181, 98), (-205, 119), (-213, 149), (-201, 176)]),
    dict(district="Willow Hills", name="Overlook Circle", count=21,
         points=[(-112, 188), (-135, 207), (-166, 218), (-198, 211), (-218, 191), (-220, 163)]),

    # Twin Oaks -- west of the existing grid
    dict(district="Twin Oaks", name="Twin Oaks Drive", count=22,
         points=[(-75, 20), (-106, 18), (-132, 3), (-145, -23), (-139, -52), (-119, -74)]),
    dict(district="Twin Oaks", name="Acorn Court", count=23,
         points=[(-132, 3), (-157, 18), (-187, 20), (-216, 7), (-229, -18), (-225, -44)]),
    dict(district="Twin Oaks", name="Lantern Court", count=23,
         points=[(-140, -50), (-154, -78), (-179, -94), (-208, -92), (-232, -73), (-238, -48)]),

    # Meadow Run -- south-west around an open meadow
    dict(district="Meadow Run", name="Meadow Run", count=25,
         points=[(-75, -75), (-103, -105), (-111, -135), (-101, -165), (-77, -187), (-47, -195)]),
    dict(district="Meadow Run", name="Larkspur Loop", count=25,
         points=[(-110, -132), (-139, -119), (-170, -121), (-198, -139), (-211, -168), (-205, -197)]),
    dict(district="Meadow Run", name="Sunset Court", count=26,
         points=[(-204, -196), (-180, -216), (-149, -226), (-116, -221), (-88, -205), (-65, -181)]),

    # Pine Hollow -- south, with wooded buffers
    dict(district="Pine Hollow", name="Pine Hollow Road", count=19,
         points=[(-24, -75), (-18, -109), (-2, -134), (22, -151), (51, -153), (75, -139)]),
    dict(district="Pine Hollow", name="Juniper Court", count=19,
         points=[(18, -149), (11, -177), (20, -205), (43, -225), (72, -229), (97, -215)]),
    dict(district="Pine Hollow", name="Hemlock Court", count=20,
         points=[(73, -139), (94, -157), (105, -184), (99, -211), (79, -230), (51, -235)]),

    # North Ridge -- south-east; "north" refers to the district's ridge road
    dict(district="North Ridge", name="Ridgeview Drive", count=16,
         points=[(85, -75), (111, -99), (136, -119), (148, -145), (144, -171), (128, -192)]),
    dict(district="North Ridge", name="Bluebird Court", count=16,
         points=[(136, -119), (164, -111), (192, -116), (215, -135), (226, -160), (222, -184)]),
    dict(district="North Ridge", name="Summit Court", count=16,
         points=[(128, -191), (151, -211), (181, -221), (210, -214), (228, -194), (228, -169)]),

    # River chapter -- east of the permanent river. Crossing Way's first
    # eighteen lots are Day 28 addresses 367-384. The bridge is a district
    # connector, keeping every home safely beyond the water rather than
    # placing frontage on the crossing itself.
    dict(district="Rivergate", name="Crossing Way", count=18,
         points=[(400, -215), (425, -218), (455, -210), (485, -195), (510, -175)]),
    dict(district="Rivergate", name="Rivergate Drive", count=30,
         points=[(455, -210), (450, -175), (442, -140), (448, -100), (465, -65), (490, -40)]),

    # Cedarbank rises gradually north from Rivergate behind a wooded bank.
    dict(district="Cedarbank", name="Cedarbank Lane", count=30,
         points=[(490, -40), (515, -20), (535, 15), (540, 55), (528, 92), (506, 120)]),
    dict(district="Cedarbank", name="Alder Court", count=28,
         points=[(535, 15), (565, 2), (595, 8), (618, 32), (625, 65), (615, 92)]),

    # Timber Bend is the cabin-forward woodland neighborhood closest to the
    # East Woods creek and riparian tree belt.
    dict(district="Timber Bend", name="Timber Bend Road", count=28,
         points=[(506, 120), (490, 150), (488, 185), (505, 216), (530, 238), (560, 248)]),
    dict(district="Timber Bend", name="Lodgepole Loop", count=26,
         points=[(505, 216), (535, 205), (566, 215), (586, 242), (588, 275), (570, 302)]),

    # Eastbank Village gives the chapter a denser, walkable northern center.
    dict(district="Eastbank Village", name="Millstone Way", count=30,
         points=[(488, 185), (458, 202), (435, 226), (428, 260), (440, 292), (465, 315)]),
    dict(district="Eastbank Village", name="Ferry Street", count=28,
         points=[(440, 292), (415, 312), (404, 344), (414, 375), (440, 395), (470, 400)]),

    # Lower-density southern edge with long views back toward the bridge.
    dict(district="River Meadows", name="Marshlight Lane", count=16,
         points=[(485, -195), (510, -225), (535, -252), (565, -263), (595, -255)]),
    dict(district="River Meadows", name="Heron Reach", count=16,
         points=[(535, -252), (545, -285), (568, -310), (600, -318), (630, -305)]),

    # ---------------------------------------------------------------- chapter
    # three. Addresses 617-1126: 500 houses and ten reserved non-house
    # addresses, on a rectilinear grid rather than more radial cul-de-sacs.
    #
    # Both quarters sit on ground that is genuinely empty: an occupancy sweep of
    # the built world plus the whole 616-address reserve found the city solid
    # from about y=-320 to y=280, so these go north of 300 and south of -340.
    # Three long avenues carry the addresses, five short cross streets tie them
    # into blocks, and `culdesac=False` keeps a grid a grid -- a bulb on the end
    # of a street that runs into another street would be a roundabout in the
    # middle of a junction.
    #
    # Address spacing is deliberately tighter than the river chapter's. Adjacent
    # addresses alternate sides of the street, so a 6.5m step along the frontage
    # is a 13m gap between neighbours on the same side: dense enough to read as
    # a town rather than a subdivision, still clear of the 7.35m minimum.

    # The quarter is sited on the broad flat bowl the terrain already has here.
    # Profiling the ground at 40m across y=280..520 found it between 3.3 and
    # 6.5m for x in [-170,170], climbing hard to 20m by x=-320 and 13m by
    # x=280. Building across that climb would have meant either a terrace edge
    # steeper than a road can climb, or a feather long enough to reach back and
    # move Pebble Court. So the grid stops at the edge of the flat ground.

    # Northgate -- the three southern avenues plus every cross street.
    #
    # Which avenue carries which special is a fit, not a preference. The
    # avenues are 36m apart, so the deepest thing that can stand between two of
    # them is about 14m half-depth once both kerbs are respected. That takes
    # the filling station (8.5), the diner (7.5), the pond (6.2) and the park
    # (12.25), and rejects the school (14.2), Follow Mart (17.0) and the fire
    # station (18.0) outright -- at ANY setback, because 36m of building does
    # not fit in a 36m block. Those three go on the two OUTER faces, where the
    # ground is open: the fire station on Northgate Avenue's town side, Follow
    # Mart and the school on Kettle Row's northern edge.
    dict(district="Northgate", name="Northgate Avenue", count=75, culdesac=False,
         specials={.06: "restaurant", .32: "firestation", .80: "gasstation"},
         points=[(-190, 306), (-60, 306), (60, 306), (210, 306)]),
    dict(district="Northgate", name="Foundry Street", count=78, culdesac=False,
         specials={.82: "park"},
         points=[(-190, 342), (-60, 342), (60, 342), (210, 342)]),
    dict(district="Northgate", name="Lantern Row", count=78, culdesac=False,
         specials={.30: "pond"},
         points=[(-190, 378), (-60, 378), (60, 378), (210, 378)]),
    dict(district="Northgate", name="Kiln Cross", count=16, culdesac=False,
         points=[(-120, 306), (-120, 396), (-120, 486)]),
    dict(district="Northgate", name="Maple Cross", count=19, culdesac=False,
         points=[(-50, 306), (-50, 396), (-50, 486)]),
    dict(district="Northgate", name="Cedar Cross", count=16, culdesac=False,
         points=[(20, 306), (20, 396), (20, 486)]),
    dict(district="Northgate", name="Quarry Cross", count=16, culdesac=False,
         points=[(90, 306), (90, 396), (90, 486)]),
    dict(district="Northgate", name="Anvil Cross", count=13, culdesac=False,
         points=[(160, 306), (160, 396), (160, 486)]),

    # Southline -- the three northern avenues on the same grid, so the two
    # districts read as one quarter rather than two subdivisions.
    dict(district="Southline", name="Southline Avenue", count=62, culdesac=False,
         specials={.55: "restaurant"},
         points=[(-190, 414), (-60, 414), (60, 414), (210, 414)]),
    dict(district="Southline", name="Millrace Street", count=62, culdesac=False,
         specials={.25: "park", .78: "gasstation"},
         points=[(-190, 450), (-60, 450), (60, 450), (210, 450)]),
    # Follow Mart and the school stand on the northern edge, where there is
    # open ground behind them: they are 34m and 28.4m deep and would cover the
    # next avenue if they stood inside the grid.
    dict(district="Southline", name="Kettle Row", count=75, culdesac=False,
         specials={.28: "followmart", .70: "elementaryschool"},
         points=[(-190, 486), (-60, 486), (60, 486), (210, 486)]),
)

# ---------------------------------------------------------------- chapter four
#
# The West Quarter: 1,000 more homes and 22 reserved parcels, continuing the
# same 70 x 36m block westward off the built edge.  It is declared in its own
# module because it is a complete piece of town planning with its own
# reasoning, and appended here because that is what makes it real: build_plan()
# below places it, validate_plan() measures it, the generator consumes it and
# the browser's walk surface carries its roads, with no new machinery anywhere.
#
# It is appended, never inserted.  Chapters one to three keep plan_ids 1..1126
# and every one of their addresses stays exactly where it is.
from west_quarter_plan import STREETS as WEST_QUARTER_STREETS

STREETS = STREETS + tuple(dict(street) for street in WEST_QUARTER_STREETS)

# The first plan_id chapter four owns. Everything below it is built or already
# reserved and may not move, which is what gates the Crown Quarter road
# clearance in build_plan() to this chapter alone.
WEST_QUARTER_FIRST_ID = (sum(street["count"] for street in STREETS)
                         - sum(street["count"] for street in WEST_QUARTER_STREETS)
                         + 1)

def _districts_from_streets():
    """(name, address count) per district, in the order the streets build."""
    order, totals = [], {}
    for street in STREETS:
        if street["district"] not in totals:
            order.append(street["district"])
            totals[street["district"]] = 0
        totals[street["district"]] += street["count"]
    return tuple((name, totals[name]) for name in order)


DISTRICTS = _districts_from_streets()
HOUSE_CAPACITY = sum(street["count"] for street in STREETS)

TERRAIN = (
    dict(kind="pond", name="Creekside Pond", x=-73, y=158, sx=17, sy=12, z=0.04),
    dict(kind="pond", name="Meadow Pond", x=-154, y=-171, sx=20, sy=13, z=0.04),
    dict(kind="hill", name="Willow Hill", x=-168, y=180, sx=18, sy=14, height=7.0),
    dict(kind="hill", name="North Ridge", x=182, y=-177, sx=25, sy=18, height=8.0),
    dict(kind="hill", name="Pine Knoll", x=54, y=-188, sx=15, sy=13, height=4.8),
    dict(kind="meadow", name="Meadow Run Green", x=-157, y=-169, sx=39, sy=32, height=0.20),
    dict(kind="meadow", name="River Meadows Green", x=565, y=-270, sx=58, sy=42, height=0.16),
    dict(kind="hill", name="Cedarbank Rise", x=585, y=74, sx=34, sy=28, height=4.2),
    dict(kind="hill", name="Timber Bend Rise", x=545, y=250, sx=38, sy=30, height=5.0),
)


def _smooth(points, rounds=2):
    """Chaikin smoothing: deterministic curves without Blender dependencies."""
    pts = [tuple(map(float, p)) for p in points]
    for _ in range(rounds):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            out.append((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25))
            out.append((a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75))
        out.append(pts[-1])
        pts = out
    return pts


def _resample(points, step=5.0):
    pts = _smooth(points)
    result = [pts[0]]
    carry = 0.0
    for a, b in zip(pts, pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if not length:
            continue
        d = step - carry
        while d < length:
            t = d / length
            result.append((a[0] + dx * t, a[1] + dy * t))
            d += step
        carry = max(0.0, length - (d - step))
    if result[-1] != pts[-1]:
        result.append(pts[-1])
    return result


def _point_at(points, fraction):
    lengths = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])]
    target = max(0.0, min(1.0, fraction)) * sum(lengths)
    walked = 0.0
    for i, length in enumerate(lengths):
        if walked + length >= target or i == len(lengths) - 1:
            t = 0.0 if not length else (target - walked) / length
            a, b = points[i], points[i + 1]
            x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            angle = math.atan2(b[1] - a[1], b[0] - a[0])
            return x, y, angle
        walked += length
    raise AssertionError("unreachable")


def _distance_to_segment(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if not length_sq:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx +
                           (point[1] - a[1]) * dy) / length_sq))
    return math.hypot(point[0] - (a[0] + t * dx),
                      point[1] - (a[1] + t * dy))


def setback_for(kind):
    """How far an address's centre stands from its road centreline.

    A house keeps HOUSE_SETBACK exactly -- every one of the 616 built and
    reserved addresses depends on it. Anything else is set back by its own
    front half-depth so that its front edge lands where a house's front edge
    lands, instead of inheriting a setback sized for a 9m cottage.
    """
    if kind == "house":
        return HOUSE_SETBACK
    return FRONT_MARGIN - TYPE_FOOTPRINT[kind][2]


def footprint_corners(x, y, rot, kind, plan_id=None):
    """The address's authored ground footprint as four world-space corners.

    `plan_id` matters only for houses: place_instance builds the ones in
    SUBURBAN_TIGHT_PLAN_IDS at the compact lot scale, and measuring them at
    the standard one invents overlaps that are not there.
    """
    x0, x1, y0, y1 = TYPE_FOOTPRINT[kind]
    if kind == "house":
        scale = (TIGHT_LOT_SCALE if plan_id in SUBURBAN_TIGHT_PLAN_IDS
                 else HOUSE_LOT_SCALE)
        x0, x1, y0, y1 = (v * scale for v in (x0, x1, y0, y1))
    cos_r, sin_r = math.cos(rot), math.sin(rot)
    return [(x + lx * cos_r - ly * sin_r, y + lx * sin_r + ly * cos_r)
            for lx, ly in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


def _polygons_apart(a, b, gap):
    """True when two convex footprints are at least `gap` apart.

    Separating-axis test rather than a circle, because these footprints are
    rectangles up to 36m long: a circumradius would reject perfectly good
    frontage and still under-cover a building's corners.
    """
    for poly in (a, b):
        for i in range(len(poly)):
            px, py = poly[i]
            qx, qy = poly[(i + 1) % len(poly)]
            nx, ny = -(qy - py), qx - px
            length = math.hypot(nx, ny)
            if not length:
                continue
            nx, ny = nx / length, ny / length
            a_lo = min(nx * x + ny * y for x, y in a)
            a_hi = max(nx * x + ny * y for x, y in a)
            b_lo = min(nx * x + ny * y for x, y in b)
            b_hi = max(nx * x + ny * y for x, y in b)
            if b_lo - a_hi >= gap or a_lo - b_hi >= gap:
                return True
    return False


def _polygon_segment_distance(poly, a, b):
    """Closest approach between a footprint and a road centreline segment."""
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        if _segments_cross(p, q, a, b):
            return 0.0
    inside = _point_in_polygon(poly, a)
    if inside:
        return 0.0
    return min([_distance_to_segment(v, a, b) for v in poly] +
               [min(_distance_to_segment(p, poly[i], poly[(i + 1) % len(poly)])
                    for i in range(len(poly))) for p in (a, b)])


def _segments_cross(p1, p2, p3, p4):
    def side(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1, d2 = side(p3, p4, p1), side(p3, p4, p2)
    d3, d4 = side(p1, p2, p3), side(p1, p2, p4)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def _point_in_polygon(poly, point):
    sign = None
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        cross = ((b[0] - a[0]) * (point[1] - a[1]) -
                 (b[1] - a[1]) * (point[0] - a[0]))
        if cross == 0:
            continue
        if sign is None:
            sign = cross > 0
        elif (cross > 0) != sign:
            return False
    return True


def _resolve_specials(street):
    """Turn this street's position fractions into address indices.

    Two specials that round onto the same address, or a type with no declared
    footprint, are errors rather than a quietly-dropped reservation -- the
    reserve is only worth anything if what it says is there is there.
    """
    resolved = {}
    for fraction, kind in sorted(street.get("specials", {}).items()):
        if kind not in TYPE_FOOTPRINT:
            raise ValueError("%s reserves a %s, which has no declared footprint"
                             % (street["name"], kind))
        index = int(round(fraction * (street["count"] - 1)))
        index = max(0, min(street["count"] - 1, index))
        if index in resolved:
            raise ValueError("%s puts %s and %s on the same address"
                             % (street["name"], resolved[index], kind))
        resolved[index] = kind
    return resolved


def neighbour_clearance(kind_a, kind_b):
    """Ground that must separate two addresses' footprints."""
    if kind_a == "house" and kind_b == "house":
        return HOUSE_NEIGHBOUR_CLEARANCE
    return SPECIAL_NEIGHBOUR_CLEARANCE


def _world_footprint(point, rot, kind, district=None, plan_id=None):
    """A placed address as (centre, circumradius, corners, kind, district).

    The centre and radius are only a broad-phase filter -- every test that
    decides anything uses the corners.
    """
    corners = footprint_corners(point[0], point[1], rot, kind, plan_id)
    cx = sum(c[0] for c in corners) / 4.0
    cy = sum(c[1] for c in corners) / 4.0
    radius = max(math.hypot(c[0] - cx, c[1] - cy) for c in corners)
    return ((cx, cy), radius, corners, kind, district)


def _chapter_three_fits(point, rot, kind, street_index, district,
                        world_segments, world_placed):
    """Does this chapter-three address physically fit where it was asked to go?

    Everything here is in world metres. Chapters one and two never reach this
    function, so their 616 addresses cannot move.
    """
    centre, radius, corners, _, _ = _world_footprint(point, rot, kind, district)

    # Nothing may stand on the only road into the quarter.
    (ax, ay), (bx, by) = NORTHGATE_ARTERIAL
    if _distance_to_segment(point, (ax, ay), (bx, by)) < ARTERIAL_CLEARANCE:
        return False
    # Against the arterial's own half-width, not a suburban street's:
    # SPECIAL_ROAD_CLEARANCE is 3.75m, less than the 4.0m of asphalt here, so
    # measuring against it would let a footprint sit inside the road.
    if kind != "house" and _polygon_segment_distance(
            corners, (ax, ay), (bx, by)) < ARTERIAL_HALF_WIDTH + 2.0:
        return False

    # A special is up to 36m across. Its own street is at FRONT_MARGIN by
    # construction; every other centreline -- including the cross street it is
    # sitting beside -- has to stay outside its footprint.
    if kind != "house":
        for a, b, other in world_segments:
            if abs(a[0] - centre[0]) > radius + 60 or abs(a[1] - centre[1]) > radius + 60:
                continue
            if other == street_index and _distance_to_segment(
                    point, a, b) <= setback_for(kind) + .01:
                continue        # the frontage this address is addressed to
            if _polygon_segment_distance(corners, a, b) < SPECIAL_ROAD_CLEARANCE:
                return False

    # Every pair is measured as ground, including house against house. The flat
    # 7.35m spacing floor is NOT enough on its own: it separates address
    # POINTS, so two houses that meet at a right angle -- one fronting an
    # avenue, one fronting the cross street beside it -- present 3.58m of width
    # against 3.82m of frontage, which is 7.40m of building inside a 7.35m gap.
    # #623 and #848 overlapped by 5cm that way.
    for (other_centre, other_radius, other_corners,
         other_kind, other_district) in world_placed:
        gap = neighbour_clearance(kind, other_kind)
        if math.hypot(centre[0] - other_centre[0],
                      centre[1] - other_centre[1]) > radius + other_radius + gap:
            continue
        if not _polygons_apart(corners, other_corners, gap):
            return False
    return True


def build_plan():
    houses, roads, turnarounds = [], [], []
    sequence = 1
    district_paths = {}
    street_paths = []
    # Resolve every path first. House placement must know about later branch
    # roads too, otherwise an early house can land in a future intersection.
    for street_index, street in enumerate(STREETS):
        path = _resample(street["points"])
        # Snap branch entrances onto an already-defined road in the same
        # district. This produces real T-junctions instead of near-miss gaps.
        prior = district_paths.get(street["district"], [])
        if prior:
            nearest = min((p for old_path in prior for p in old_path),
                          key=lambda p: math.hypot(p[0] - path[0][0], p[1] - path[0][1]))
            if math.hypot(nearest[0] - path[0][0], nearest[1] - path[0][1]) <= 24.0:
                path[0] = nearest
        district_paths.setdefault(street["district"], []).append(path)
        street_paths.append(path)

    all_segments = [(a, b, i) for i, path in enumerate(street_paths)
                    for a, b in zip(path, path[1:])]
    # Only streets that actually END in a turning circle reserve one. A grid
    # street runs into another street, so treating its last point as a bulb
    # would blank out twelve metres of frontage around a plain junction.
    all_bulbs = [(path[-1], i) for i, path in enumerate(street_paths)
                 if STREETS[i].get("culdesac", True)]

    # The same road network in WORLD metres. Districts are rigid render-time
    # offsets, so two addresses in different districts can be 58m apart in the
    # raw coordinates above and standing on each other in the town -- which is
    # exactly how the reverted highway got cleared against Pebble Court. Only
    # chapter three uses these; chapters one and two keep the raw comparison
    # they were laid out with, so none of their 616 addresses can move.
    world_segments = []
    for street_index, street in enumerate(STREETS):
        dx, dy = DISTRICT_OFFSETS.get(street["district"], (0.0, 0.0))
        for a, b in zip(street_paths[street_index], street_paths[street_index][1:]):
            world_segments.append(((a[0] + dx, a[1] + dy),
                                   (b[0] + dx, b[1] + dy), street_index))
    world_footprints = []          # (corners, plan_id) for everything placed

    # Crown Quarter's streets, which this module does not own but chapter four
    # stands next to. They matter because metropolitan_plan's east/west streets
    # now run west as far as x=-260 to meet the West Quarter's edge instead of
    # dead-ending in meadow, so a chapter-four address on that edge could
    # otherwise be placed in the middle of a downtown boulevard -- nothing here
    # was looking at those roads at all.
    #
    # Deliberately gated to chapter four and no earlier, because build_plan
    # re-solves a whole street at once: applying this to chapter three would
    # recompute addresses that are already BUILT, and a built house's position
    # lives in world_state.json while its road comes from here -- so the road
    # would move and the house would not, leaving it standing in the street.
    #
    # That gate costs nothing today. Measured against the Day 41 state: zero
    # built plan houses lie within clearance of any Crown Quarter street, and
    # zero lie inside one.
    metro_segments = []
    try:
        from metropolitan_plan import STREETS as METRO_STREETS
    except ImportError:
        METRO_STREETS = ()
    for street in METRO_STREETS:
        points = street["points"]
        for a, b in zip(points, points[1:]):
            metro_segments.append(((float(a[0]), float(a[1])),
                                   (float(b[0]), float(b[1])),
                                   street["width"] / 2.0))

    for street_index, street in enumerate(STREETS):
        path = street_paths[street_index]
        offset = DISTRICT_OFFSETS.get(street["district"], (0.0, 0.0))
        specials = _resolve_specials(street)
        first_sequence = sequence
        # House fractions avoid shared entrances and leave room for the bulb.
        # Candidate oversampling lets junctions shared by two streets remain
        # naturally empty instead of placing two houses on top of each other.
        placed = 0
        for address_index in range(street["count"]):
            base = .06 + .88 * (address_index + .5) / street["count"]
            # Search the whole usable frontage, nearest to the address's ideal
            # fraction first. Branch junction exclusion can require moving a
            # slot farther than a small local retry window.
            samples = street["count"] * 8
            candidates = sorted((.04 + (i + .5) * .92 / samples for i in range(samples)),
                                key=lambda fraction: abs(fraction - base))
            chosen = None
            preferred_side = -1 if address_index % 2 == 0 else 1
            # Ordinary unless this street reserved the address for something
            # else. Keyed on the address's index along its own street, so a
            # special holds a chosen position AND a fixed growth number.
            kind = specials.get(address_index, "house")
            setback = setback_for(kind)
            for fraction in candidates:
                cx, cy, angle = _point_at(path, max(.04, min(.96, fraction)))
                nx, ny = -math.sin(angle), math.cos(angle)
                for side in (preferred_side, -preferred_side):
                    hx, hy = cx + nx * setback * side, cy + ny * setback * side
                    point = (hx, hy)
                    spacing = 7.35 if sequence > LEGACY_RESERVE_CAPACITY else 5.5
                    if any(math.hypot(hx - h["x"], hy - h["y"]) < spacing
                           for h in houses):
                        continue
                    if any(other != street_index and
                           _distance_to_segment(point, a, b) < HOUSE_ROAD_CLEARANCE
                           for a, b, other in all_segments):
                        continue
                    if any(math.hypot(hx - center[0], hy - center[1]) < CULDESAC_CLEARANCE
                           for center, _ in all_bulbs):
                        continue
                    rot = angle if side > 0 else angle + math.pi
                    world = (hx + offset[0], hy + offset[1])
                    # Crown Quarter's roads. Chapter four only -- see the note
                    # where metro_segments is built.
                    if sequence >= WEST_QUARTER_FIRST_ID and metro_segments:
                        corners = footprint_corners(world[0], world[1], rot,
                                                    kind, sequence)
                        if kind == "house":
                            if any(_distance_to_segment(world, a, b)
                                   < half + 3.75
                                   for a, b, half in metro_segments):
                                continue
                        elif any(_polygon_segment_distance(corners, a, b)
                                 < half + 2.0
                                 for a, b, half in metro_segments):
                            continue
                    if sequence > RIVER_RESERVE_CAPACITY and not _chapter_three_fits(
                            world, rot, kind, street_index, street["district"],
                            world_segments, world_footprints):
                        continue
                    chosen = (hx, hy, angle, side, rot, kind, world)
                    break
                if chosen is not None:
                    break
            if chosen is None:
                continue
            hx, hy, angle, side, rot, kind, world = chosen
            world_footprints.append(
                _world_footprint(world, rot, kind, street["district"]))
            houses.append(dict(
                plan_id=sequence, district=street["district"], street=street["name"],
                type=kind,
                x=round(hx, 3), y=round(hy, 3),
                # House assets face local -Y. Rotate that front toward the
                # sampled road centerline, never sideways along the street.
                rot=round(rot, 5),
                street_index=street_index,
            ))
            sequence += 1
            placed += 1
        if placed != street["count"]:
            raise ValueError("not enough collision-free frontage on %s" % street["name"])
        last_sequence = sequence - 1
        # Every small segment unlocks with the nearest next address.  All
        # connector segments before the first address share its reveal id.
        for i, (a, b) in enumerate(zip(path, path[1:])):
            fraction = (i + 1) / max(1, len(path) - 1)
            local = min(street["count"] - 1, max(0, int((fraction - .08) / .84 * street["count"])))
            roads.append(dict(a=a, b=b, reveal_at=first_sequence + local,
                              district=street["district"], street=street["name"],
                              street_index=street_index))
        # The bulb must not appear until the final road segment reaches it.
        # Revealing it early creates a detached gray disc in growth videos.
        # Grid streets end on another street rather than in a turning circle,
        # and a bulb there would be a roundabout dropped in a junction.
        if street.get("culdesac", True):
            turnarounds.append(dict(center=path[-1], reveal_at=last_sequence,
                                    district=street["district"], street=street["name"],
                                    street_index=street_index))
    # Against the streets as declared, not against a module constant: every
    # street above raises if it cannot seat its own count, so this is the last
    # guard that the two agree.
    assert len(houses) == sum(street["count"] for street in STREETS)
    return dict(houses=houses, roads=roads, turnarounds=turnarounds,
                terrain=list(TERRAIN), districts=list(DISTRICTS),
                river={"centerline": list(RIVER_CENTERLINE),
                       "half_width": RIVER_HALF_WIDTH,
                       "riparian_clearance": RIVER_RIPARIAN_CLEARANCE,
                       "bridge": dict(RIVER_BRIDGE)})


PLAN = build_plan()


def validate_plan(min_house_spacing=5.5):
    errors = []
    houses = PLAN["houses"]
    ids = [h["plan_id"] for h in houses]
    if ids != list(range(1, HOUSE_CAPACITY + 1)):
        errors.append("plan ids are not continuous 1..%d" % HOUSE_CAPACITY)
    if sum(c for _, c in DISTRICTS) != HOUSE_CAPACITY:
        errors.append("district counts do not total %d" % HOUSE_CAPACITY)
    for i, a in enumerate(houses):
        for b in houses[i + 1:]:
            required_spacing = (7.35 if
                                max(a["plan_id"], b["plan_id"]) >
                                LEGACY_RESERVE_CAPACITY else min_house_spacing)
            if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < required_spacing:
                errors.append("house spacing collision: %d and %d" % (a["plan_id"], b["plan_id"]))
                if len(errors) > 20:
                    return errors
        own_roads = [r for r in PLAN["roads"] if r["street_index"] == a["street_index"]]
        nearest = min(_distance_to_segment((a["x"], a["y"]), r["a"], r["b"])
                      for r in own_roads)
        if abs(nearest - setback_for(a["type"])) > 0.15:
            errors.append("house %d is not on its street frontage" % a["plan_id"])
        front = (math.sin(a["rot"]), -math.cos(a["rot"]))
        road_vector = min(
            ((r, _distance_to_segment((a["x"], a["y"]), r["a"], r["b"])) for r in own_roads),
            key=lambda item: item[1])[0]
        # Closest point direction is tested against the door's local -Y axis.
        ra, rb = road_vector["a"], road_vector["b"]
        dx, dy = rb[0] - ra[0], rb[1] - ra[1]
        ll = dx * dx + dy * dy
        t = max(0.0, min(1.0, ((a["x"] - ra[0]) * dx + (a["y"] - ra[1]) * dy) / ll))
        toward = (ra[0] + t * dx - a["x"], ra[1] + t * dy - a["y"])
        if front[0] * toward[0] + front[1] * toward[1] <= 0:
            errors.append("house %d does not face its road" % a["plan_id"])
        for r in PLAN["roads"]:
            if r["street_index"] != a["street_index"] and _distance_to_segment(
                    (a["x"], a["y"]), r["a"], r["b"]) < HOUSE_ROAD_CLEARANCE:
                errors.append("house %d overlaps road %s" % (a["plan_id"], r["street"]))
        for bulb in PLAN["turnarounds"]:
            if math.hypot(a["x"] - bulb["center"][0], a["y"] - bulb["center"][1]) < CULDESAC_CLEARANCE:
                errors.append("house %d overlaps cul-de-sac %s" % (a["plan_id"], bulb["street"]))
        if a["plan_id"] > LEGACY_RESERVE_CAPACITY:
            river_distance = min(
                _distance_to_segment((a["x"], a["y"]), p0, p1)
                for p0, p1 in zip(RIVER_CENTERLINE, RIVER_CENTERLINE[1:])
            )
            if river_distance < RIVER_RIPARIAN_CLEARANCE:
                errors.append("river house %d enters the protected riparian corridor" %
                              a["plan_id"])
    errors.extend(_validate_footprints())
    return errors


def _validate_footprints():
    """The checks the address-point tests above cannot express.

    Everything above measures distances between address POINTS, which is why
    the reserve could pass while fourteen houses stood inside the fire station
    and six of the ten specials had a road running through them. These measure
    the ground each address actually covers.
    """
    from downtown_visual_plan import terrain_height

    errors = []
    placed = []
    for house in PLAN["houses"]:
        dx, dy = DISTRICT_OFFSETS.get(house["district"], (0.0, 0.0))
        point = (house["x"] + dx, house["y"] + dy)
        placed.append((house, point,
                       _world_footprint(point, house["rot"], house["type"],
                                        house["district"], house["plan_id"])))

    roads = [(transform_point_pair(r), r["street"]) for r in PLAN["roads"]]
    arterial = list(zip(NORTHGATE_ARTERIAL, NORTHGATE_ARTERIAL[1:]))

    for index, (house, point, shape) in enumerate(placed):
        centre, radius, corners, kind, district = shape
        chapter_three = house["plan_id"] > RIVER_RESERVE_CAPACITY

        if chapter_three:
            for a, b in arterial:
                if _distance_to_segment(point, a, b) < ARTERIAL_CLEARANCE:
                    errors.append("address %d stands on the Northgate arterial"
                                  % house["plan_id"])

        if kind != "house":
            for (a, b), name in roads:
                if _distance_to_segment(point, a, b) <= setback_for(kind) + .01:
                    continue
                gap = _polygon_segment_distance(corners, a, b)
                if gap < SPECIAL_ROAD_CLEARANCE:
                    errors.append("%s %d has %s %.2fm inside its footprint"
                                  % (kind, house["plan_id"], name, gap))
                    break
            for a, b in arterial:
                if _polygon_segment_distance(corners, a,
                                             b) < ARTERIAL_HALF_WIDTH + 2.0:
                    errors.append("%s %d stands on the Northgate arterial"
                                  % (kind, house["plan_id"]))
            # A civic deck is a flat box on the terrain, so the fall across the
            # footprint is how proud it stands at its low corner.
            heights = [terrain_height(x, y) for x, y in corners] + \
                      [terrain_height(centre[0], centre[1])]
            fall = max(heights) - min(heights)
            if fall > MAX_SPECIAL_PAD_FALL:
                errors.append("%s %d sits on ground that falls %.2fm across it"
                              % (kind, house["plan_id"], fall))

        for other, _other_point, other_shape in placed[index + 1:]:
            (other_centre, other_radius, other_corners,
             other_kind, other_district) = other_shape
            if (kind == "house" and other_kind == "house"
                    and house["plan_id"] <= RIVER_RESERVE_CAPACITY
                    and other["plan_id"] <= RIVER_RESERVE_CAPACITY):
                # Chapters one and two are built and cannot move. Eight pairs
                # of them have lot envelopes that touch -- driveway against
                # driveway, not wall against wall -- and reporting those every
                # run would bury the findings that can still be acted on.
                continue
            gap = neighbour_clearance(kind, other_kind)
            if math.hypot(centre[0] - other_centre[0],
                          centre[1] - other_centre[1]) > radius + other_radius + gap:
                continue
            if not _polygons_apart(corners, other_corners, gap):
                errors.append(
                    "%s %d and %s %d are less than %.2fm apart on the ground"
                    % (kind, house["plan_id"], other_kind, other["plan_id"], gap)
                    if gap else
                    "%s %d and %s %d overlap on the ground"
                    % (kind, house["plan_id"], other_kind, other["plan_id"]))
        if len(errors) > 20:
            break
    return errors


def transform_point_pair(road):
    """A plan road segment's two ends in world metres."""
    dx, dy = DISTRICT_OFFSETS.get(road.get("district"), (0.0, 0.0))
    return ((road["a"][0] + dx, road["a"][1] + dy),
            (road["b"][0] + dx, road["b"][1] + dy))


if __name__ == "__main__":
    problems = validate_plan()
    if problems:
        raise SystemExit("\n".join(problems))
    for name, count in DISTRICTS:
        print("%-18s %3d" % (name, count))
    print("TOTAL              %3d" % len(PLAN["houses"]))
