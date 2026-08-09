"""Deterministic neighborhood reserve for Followville populations 135..750.

This module contains geometry only; importing it creates no Blender objects and
never edits world_state.json.  The generator consumes the next address(es) when
ordinary houses are added.  Future roads remain data until a house assigned to
that portion of road exists.
"""

import math

BASE_POPULATION = 134
LEGACY_RESERVE_CAPACITY = 366
RIVER_RESERVE_CAPACITY = 616
HOUSE_CAPACITY = 1126
ROAD_HALF_WIDTH = 3.0
HOUSE_SETBACK = 8.5
HOUSE_ROAD_CLEARANCE = 6.75
CULDESAC_CLEARANCE = 12.0

# Permanent river-chapter geography. The centerline runs north-to-south beyond
# the Day-27 city edge. Water is 24-30 m wide; a broader riparian reserve keeps
# houses, roads, and tree belts from crowding the banks. The first crossing is
# deliberately aligned with completed Summit Court and Day 28 Crossing Way.
RIVER_CENTERLINE = (
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

DISTRICTS = (
    ("Creekside Bend", 54),
    ("Willow Hills", 62),
    ("Twin Oaks", 68),
    ("Meadow Run", 76),
    ("Pine Hollow", 58),
    ("North Ridge", 48),
    ("Rivergate", 48),
    ("Cedarbank", 58),
    ("Timber Bend", 54),
    ("Eastbank Village", 58),
    ("River Meadows", 32),
    # Chapter three: two dense gridded quarters on open ground north and south
    # of everything built so far. Deliberately NOT more curved cul-de-sac
    # suburbs -- the existing long radial streets are the ones Cade wants to
    # become main downtown arterials later, so these are laid out as short
    # blocks on a rectilinear grid that a downtown can actually grow into.
    ("Northgate", 314),
    ("Southline", 196),
)

# Address numbers inside chapter three that are NOT ordinary houses. The key is
# the address's index along its own street, so a special keeps both its place in
# the growth numbering AND a sensible corner or mid-block position. Everything
# here is an existing generator type; nothing needs a new asset to be reserved.
# The terrace datum and box live in downtown_visual_plan.terrain_height, which
# is the single shared walk surface; they are not duplicated here.

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
    dict(district="Northgate", name="Northgate Avenue", count=71, culdesac=False,
         specials={8: "gasstation", 44: "restaurant"},
         points=[(-190, 306), (-60, 306), (60, 306), (210, 306)]),
    dict(district="Northgate", name="Foundry Street", count=71, culdesac=False,
         specials={22: "followmart", 58: "park"},
         points=[(-190, 342), (-60, 342), (60, 342), (210, 342)]),
    dict(district="Northgate", name="Lantern Row", count=72, culdesac=False,
         specials={12: "pond", 40: "elementaryschool"},
         points=[(-190, 378), (-60, 378), (60, 378), (210, 378)]),
    dict(district="Northgate", name="Kiln Cross", count=20, culdesac=False,
         points=[(-120, 306), (-120, 396), (-120, 486)]),
    dict(district="Northgate", name="Maple Cross", count=20, culdesac=False,
         points=[(-50, 306), (-50, 396), (-50, 486)]),
    dict(district="Northgate", name="Cedar Cross", count=20, culdesac=False,
         points=[(20, 306), (20, 396), (20, 486)]),
    dict(district="Northgate", name="Quarry Cross", count=20, culdesac=False,
         points=[(90, 306), (90, 396), (90, 486)]),
    dict(district="Northgate", name="Anvil Cross", count=20, culdesac=False,
         points=[(160, 306), (160, 396), (160, 486)]),

    # Southline -- the three northern avenues on the same grid, so the two
    # districts read as one quarter rather than two subdivisions.
    dict(district="Southline", name="Southline Avenue", count=62, culdesac=False,
         specials={30: "firestation"},
         points=[(-190, 414), (-60, 414), (60, 414), (210, 414)]),
    dict(district="Southline", name="Millrace Street", count=62, culdesac=False,
         specials={18: "park", 52: "restaurant"},
         points=[(-190, 450), (-60, 450), (60, 450), (210, 450)]),
    dict(district="Southline", name="Kettle Row", count=72, culdesac=False,
         specials={26: "gasstation"},
         points=[(-190, 486), (-60, 486), (60, 486), (210, 486)]),
)

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

    for street_index, street in enumerate(STREETS):
        path = street_paths[street_index]
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
            for fraction in candidates:
                cx, cy, angle = _point_at(path, max(.04, min(.96, fraction)))
                nx, ny = -math.sin(angle), math.cos(angle)
                for side in (preferred_side, -preferred_side):
                    hx, hy = cx + nx * HOUSE_SETBACK * side, cy + ny * HOUSE_SETBACK * side
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
                    chosen = (hx, hy, angle, side)
                    break
                if chosen is not None:
                    break
            if chosen is None:
                continue
            hx, hy, angle, side = chosen
            houses.append(dict(
                plan_id=sequence, district=street["district"], street=street["name"],
                # Ordinary unless this street reserved the address for something
                # else. Keyed on the address's index along its own street, so a
                # special holds a chosen position AND a fixed growth number.
                type=street.get("specials", {}).get(address_index, "house"),
                x=round(hx, 3), y=round(hy, 3),
                # House assets face local -Y. Rotate that front toward the
                # sampled road centerline, never sideways along the street.
                rot=round(angle if side > 0 else angle + math.pi, 5),
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
    assert len(houses) == HOUSE_CAPACITY
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
        if abs(nearest - HOUSE_SETBACK) > 0.15:
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
    return errors


if __name__ == "__main__":
    problems = validate_plan()
    if problems:
        raise SystemExit("\n".join(problems))
    for name, count in DISTRICTS:
        print("%-18s %3d" % (name, count))
    print("TOTAL              %3d" % len(PLAN["houses"]))
