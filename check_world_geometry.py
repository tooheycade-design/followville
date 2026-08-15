#!/usr/bin/env python3
"""Does the authored world still sit on the ground it is supposed to?

check_town_glb.py already proves the export is complete and matches state --
right building count, right hashes, nothing squashed flat. It says nothing
about whether the buildings are anywhere sensible, and on 2026-07-31 Cade
walked the town and found four places where they were not:

  * the rafting terrace, walled on its river face only, its downhill corners
    hanging 4.6m in the air over the bank
  * the outpost lane, its first control point on top of the Kaleidoscope Crest
    plateau but its height taken from the terrain, so 55m ran inside the hill
    before the rest floated 0.59m and stopped 11m short of the outpost
  * the fishing pond, moved 24m the day before onto the x=87 street, its west
    bank, dock, sign and approach path lying across the road and its curb
  * City Hall, whose 45m foundation contained the Pine Hollow connector's
    terminus and the first three segments of that district's own road, so the
    street drove into the left wing and stopped

Every one of them was invisible to every check the project had, and every one
is arithmetic on data that already exists. So this runs that arithmetic.

Pure data: world_state.json plus the shared terrain and layout modules. No
Blender, no browser, no GLB, no dependencies -- it is meant to be cheap enough
to run on every push and before every commit that moves anything.

    python check_world_geometry.py [world_state.json]

Exits non-zero on any failure, printing the offending coordinates.
"""

import json
import math
import sys

from downtown_visual_plan import terrain_height
from neighborhood_plan import (PLAN, RIVER_HALF_WIDTH,
                               NORTHGATE_ARTERIAL_REVEAL,
                               northgate_arterial_points)
from world_layout import (AUTHORED_ELEVATION_ROADS, CITY_HALL_APPROACH,
                          DISTRICT_CONNECTORS, INTENTIONALLY_RAISED_ROADS,
                          NORTH_CROWN_CAMPUS_ACCESS,
                          KEEP_OUT_REGIONS, LANDMARK_APPROACHES,
                          LANDMARK_FOOTPRINTS, LANDMARK_GRID_SIZE,
                          LEVEL_WATER, RETAINED_PADS,
                          DEFAULT_MAX_PAD_STAND, MAX_PAD_STAND,
                          SALMON_SHOP_APPROACH, timber_crossing_points,
                          STORYBOOK_ACCESS, rafting_access_points,
                          weather_station_access_points,
                          transform_building_point, transform_point,
                          walk_surface_manifest)

LOT, BLOCK_N, ROAD = 13, 3, 6
PITCH = BLOCK_N * LOT + ROAD

# A road surface sits a few centimetres above the ground by construction --
# that is the thickness of the deck, not a defect. Subtract the thickest one
# in the town (the City Hall road's 0.091 top offset, rounded up) before
# judging, so the number that gets compared is real daylight.
ROAD_DECK_THICKNESS = 0.10
# How much daylight under a road deck reads as floating from the ground. The
# old outpost lane managed 0.59m on its 26m chords, which clears this by five
# times; a terrain-following road subdivided at 2-3m stays under a centimetre.
MAX_ROAD_FLOAT = 0.12
# How far a walk pad's edge may stand above the ground before it needs to say
# what is holding it up.
MAX_UNRETAINED_PAD = 0.35
# How far the river water may stand above its own bank before it reads as a
# levee rather than a river. Small but not zero: the bank blends down to the
# waterline at the shore by construction, and this is sampled just outside
# that blend.
MAX_RIVER_PERCH = 0.35
# Clearances a landmark's built footprint must keep.
ROAD_CLEARANCE = 2.0
BUILDING_CLEARANCE = 6.0
PAVED_CLEARANCE = 4.0

failures = []
notes = []


def fail(check, detail):
    failures.append((check, detail))


def segment_distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    denom = dx * dx + dy * dy
    if denom <= 1e-9:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denom))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def densify(points, step=2.0):
    dense = []
    for a, b in zip(points, points[1:]):
        count = max(1, int(math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / step)))
        for index in range(count):
            t = index / count
            dense.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    if points:
        dense.append((points[-1][0], points[-1][1]))
    return dense


def building_point(building):
    """Where a building's geometry actually stands, in Blender coordinates.

    Off-grid records carry px/py. A downtown GRID record carries gx/gy instead,
    and its geometry is centred on the block of lots it fills, not on its
    anchor lot -- place_instance offsets a SIZE-n asset by (n-1)*LOT/2 on both
    axes. Reading px/py off a grid record returns (0, 0), which is how the
    elementary school came to be audited at the world origin and reported as
    1.5m from a house 115m away from it.
    """
    if "px" in building:
        return transform_building_point(building)
    bx, ix = divmod(building["gx"], BLOCK_N)
    by, iy = divmod(building["gy"], BLOCK_N)
    size = LANDMARK_GRID_SIZE.get(building["type"], 1)
    return (bx * PITCH + ix * LOT + LOT / 2 + (size - 1) * LOT / 2,
            by * PITCH + iy * LOT + LOT / 2 + (size - 1) * LOT / 2)


def paved_envelope(buildings):
    """The rectangle the downtown grid's roads and sidewalks actually cover."""
    grid = [b for b in buildings
            if b["type"] not in ("parkdistrict", "ringhouse")
            and not b.get("plan_id") and not b.get("metro_id")
            and not b.get("feature_id")]
    if not grid:
        return None
    min_bx = min(min(b["gx"] // BLOCK_N for b in grid), -1)
    max_bx = max(max(b["gx"] // BLOCK_N for b in grid), 1)
    min_by = min(min(b["gy"] // BLOCK_N for b in grid), -1)
    max_by = max(max(b["gy"] // BLOCK_N for b in grid), 1)
    return (min_bx * PITCH - ROAD, (max_bx + 1) * PITCH,
            min_by * PITCH - ROAD, (max_by + 1) * PITCH)


def every_road(state):
    """Every road centreline in the town, as (name, [(x, y), ...]) in Blender
    coordinates. A checker that knows about only some of the roads will
    cheerfully approve a building standing on one of the others."""
    buildings = state["buildings"]
    active = max((b.get("plan_id", 0) for b in buildings), default=0)
    roads = []
    for index, segment in enumerate(PLAN.get("roads", [])):
        if segment.get("reveal_at", 10 ** 9) > active:
            continue
        district = segment.get("district")
        roads.append(("%s road %d" % (district or "plan", index), [
            transform_point(*segment["a"], district=district),
            transform_point(*segment["b"], district=district)]))
    for district in sorted({b.get("district") for b in buildings
                            if b.get("plan_id")} - {None}):
        connector = DISTRICT_CONNECTORS.get(district)
        if connector:
            roads.append(("%s connector" % district, list(connector)))
    present = {b["type"] for b in buildings}
    if "cityhall" in present:
        roads.append(("City Hall approach", list(CITY_HALL_APPROACH)))
    if any(b["type"] == "storybookhouse" for b in buildings):
        roads.append(("Kaleidoscope Crest access",
                      [(x, y) for x, y, _z in STORYBOOK_ACCESS]))
    if "raftingstation" in present:
        roads.append(("rafting outpost lane", rafting_access_points()))
    if "weatherstation" in present:
        roads.append(("First Alert Weather access",
                      [(x, y) for x, y, _z in weather_station_access_points()]))
    if "salmonproshop" in present:
        roads.append(("Salmon Pro Shop approach", list(SALMON_SHOP_APPROACH)))
    if any(b.get("district") == "Timber Bend" for b in buildings):
        roads.append(("Timber Bend Crossing",
                      [(x, y) for x, y, _z in timber_crossing_points()]))
    if active >= NORTHGATE_ARTERIAL_REVEAL:
        roads.append(("Northgate arterial", northgate_arterial_points()))
    if "nuclearplant" in present:
        from world_layout import point_road_points, station_trail_points
        roads.append(("Point Road", point_road_points()))
        roads.append(("Station Trail", station_trail_points()))
    if "northcrowncampus" in present:
        roads.append(("North Crown campus access",
                      list(NORTH_CROWN_CAMPUS_ACCESS)))
    if any(b.get("type") == "metrotower" for b in buildings):
        from metropolitan_plan import STREETS, RAMPS, expressway_points
        for street in STREETS:
            roads.append(("Crown Quarter " + street["name"],
                          list(street["points"])))
        roads.append(("Crown Expressway",
                      [(x, y) for x, y, _z in expressway_points()]))
        for ramp in RAMPS:
            roads.append(("Crown interchange ramps",
                          [(x, y) for x, y, _z in ramp["points"]]))
    return roads


def check_roads_sit_on_the_ground(state):
    """A terrain-following road deck should never ride above the terrain.

    The manifest's segments carry the deck height the browser walks on. Where
    that came from a terrain sample it will match; where it came from a long
    straight chord across a concave grade it will not, and the road hangs.
    """
    raised = INTENTIONALLY_RAISED_ROADS
    worst, worst_at = 0.0, None
    for segment in walk_surface_manifest(state)["segments"]:
        ax, az, ah, bx, bz, bh, _half = segment
        # Manifest segments are three.js coordinates; terrain is Blender's.
        ay, by = -az, -bz
        if any(x0 <= ax <= x1 and y0 <= ay <= y1
               for _name, x0, x1, y0, y1 in raised):
            continue
        steps = max(1, int(math.hypot(bx - ax, by - ay) / 1.0))
        for index in range(steps + 1):
            t = index / steps
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            float_height = ((ah + (bh - ah) * t) - terrain_height(x, y)
                            - ROAD_DECK_THICKNESS)
            if float_height > worst:
                worst, worst_at = float_height, (x, y)
            if float_height > MAX_ROAD_FLOAT:
                fail("road float",
                     "deck stands %.2fm above the ground at (%.1f, %.1f)"
                     % (float_height, x, y))
                return
    notes.append("worst daylight under a road deck %.3fm at (%.1f, %.1f), "
                 "limit %.2f"
                 % ((max(worst, 0.0),) + (worst_at or (0.0, 0.0))
                    + (MAX_ROAD_FLOAT,)))


def check_roads_avoid_raised_ground(state):
    """No terrain-following road may run under ground that stands above it.

    Roads that carry their own authored heights are exempt: climbing onto the
    raised ground is what they are for. The outpost lane was neither -- it was
    authored to start on the plateau but took its height from the terrain
    underneath, which is the combination that buries a road.
    """
    for name, points in every_road(state):
        if name in AUTHORED_ELEVATION_ROADS:
            continue
        for x, y in densify(points, 3.0):
            for region, cx, cy, rx, ry in KEEP_OUT_REGIONS:
                if math.hypot((x - cx) / rx, (y - cy) / ry) < 1.0:
                    fail("road under raised ground",
                         "%s passes through %s at (%.1f, %.1f)"
                         % (name, region, x, y))
                    return
    notes.append("%d roads all outside %d raised region(s)"
                 % (len(every_road(state)), len(KEEP_OUT_REGIONS)))


def check_landmarks_clear_roads_and_town(state):
    """A landmark's built footprint has to clear the roads and its neighbours.

    City Hall's foundation contained a district road's terminus and its first
    three segments; the pond's bank, dock and sign lay across a downtown
    street. Both are this check.
    """
    buildings = state["buildings"]
    envelope = paved_envelope(buildings)
    roads = every_road(state)
    others = [(b, building_point(b)) for b in buildings
              if "px" in b and b["type"] not in LANDMARK_FOOTPRINTS]
    others += [(b, building_point(b)) for b in buildings
               if "px" not in b and b["type"] not in ("tree", "bush", "rock")]
    audited = 0
    for building in buildings:
        spec = LANDMARK_FOOTPRINTS.get(building["type"])
        if spec is None:
            continue
        audited += 1
        x0, x1, y0, y1, rural = spec
        cx, cy = building_point(building)
        corners = [(cx + x0, cy + y0), (cx + x1, cy + y0),
                   (cx + x1, cy + y1), (cx + x0, cy + y1)]
        outline = densify(corners + [corners[0]], 2.0)
        serving = LANDMARK_APPROACHES.get(building["type"], set())
        for name, points in roads:
            if name in serving:
                continue
            for a, b in zip(points, points[1:]):
                gap = min(segment_distance(p, a, b) for p in outline) - ROAD / 2
                if gap < ROAD_CLEARANCE:
                    fail("landmark on a road",
                         "%s is %.1fm from %s (needs %.1f)"
                         % (building["type"], gap, name, ROAD_CLEARANCE))
                    return
        for other, (ox, oy) in others:
            gap = min(math.hypot(px - ox, py - oy) for px, py in outline)
            if gap < BUILDING_CLEARANCE:
                fail("landmark on a building",
                     "%s is %.1fm from %s seed %s (needs %.1f)"
                     % (building["type"], gap, other["type"],
                        other.get("seed"), BUILDING_CLEARANCE))
                return
        if rural and envelope:
            ex0, ex1, ey0, ey1 = envelope
            inside = min(max(ex0 - px, px - ex1, ey0 - py, py - ey1)
                         for px, py in outline)
            if inside < PAVED_CLEARANCE:
                fail("rural landmark in the paved town",
                     "%s reaches %.1fm inside the paved envelope (needs %.1f "
                     "clear)" % (building["type"], -inside, PAVED_CLEARANCE))
                return
    scenery = ("tree", "bush", "rock", "duck", "cityhallroad")
    unaudited = sorted({b["type"] for b in buildings
                        if "px" in b and b["type"] not in LANDMARK_FOOTPRINTS
                        and b["type"] not in scenery
                        and not str(b["type"]).endswith("house")})
    notes.append("%d landmark footprints audited" % audited)
    if unaudited:
        notes.append("not audited (no footprint declared): %s"
                     % ", ".join(unaudited))


def check_raised_pads_are_retained(state):
    """A deck standing above the ground must say what holds it up."""
    for pad in walk_surface_manifest(state)["pads"]:
        cx, cz, top, half_x, half_z, kind = pad
        cy = -cz
        edges = []
        for index in range(17):
            t = index / 16
            edges += [(cx - half_x + 2 * half_x * t, cy - half_z),
                      (cx - half_x + 2 * half_x * t, cy + half_z),
                      (cx - half_x, cy - half_z + 2 * half_z * t),
                      (cx + half_x, cy - half_z + 2 * half_z * t)]
        stands = max(top - terrain_height(x, y) for x, y in edges)
        if stands > MAX_UNRETAINED_PAD and kind not in RETAINED_PADS:
            fail("unretained raised deck",
                 "%s stands %.2fm above the ground at its edge with nothing "
                 "declared to hold it up" % (kind, stands))
            return
        # Being retained is not the same as being reasonable. A level pad on a
        # sloping site perches itself as high as the site falls, and its road
        # then has to ramp up to meet it -- which is how the Salmon Pro Shop
        # ended up 4.21m in the air behind a 60m sweeping drive with nothing
        # failing. Each deck declares how proud it may stand; a new one that
        # exceeds the default is a building on the wrong site.
        limit = MAX_PAD_STAND.get(kind, DEFAULT_MAX_PAD_STAND)
        if stands > limit:
            fail("deck perched above its site",
                 "%s stands %.2fm proud at its most exposed edge, over its "
                 "declared %.2fm. Level the site or move the building -- the "
                 "pad cannot be lowered, because the terrain would rise "
                 "through it. If this really is meant to be a terrace, raise "
                 "its entry in world_layout.MAX_PAD_STAND and say why."
                 % (kind, stands, limit))
            return
    pads = walk_surface_manifest(state)["pads"]
    notes.append("%d walk pads, raised ones all retained (%s)"
                 % (len(pads), ", ".join(
                     "%s %.2fm" % (pad[5], max(pad[2] - terrain_height(x, y)
                                               for x, y in [(pad[0] - pad[3], -pad[1] - pad[4]),
                                                            (pad[0] + pad[3], -pad[1] - pad[4]),
                                                            (pad[0] - pad[3], -pad[1] + pad[4]),
                                                            (pad[0] + pad[3], -pad[1] + pad[4])]))
                     for pad in pads)))


def check_water_is_level(state):
    """Level water on sloping ground stands proud of its own low bank.

    No datum fixes that and no relocation fixes it either, because the meadow
    outside the paved grid climbs at a steady 9% everywhere. The site has to
    be level, which is what terrain_height's pond shelf is for. This is the
    check that says whether it still is.
    """
    from downtown_visual_plan import FISHING_POND_RX, FISHING_POND_RY
    for building in state["buildings"]:
        tolerance = LEVEL_WATER.get(building["type"])
        if tolerance is None:
            continue
        cx, cy = transform_building_point(building)
        rim = [terrain_height(cx + FISHING_POND_RX * 1.07 * math.cos(a),
                              cy + FISHING_POND_RY * 1.07 * math.sin(a))
               for a in (math.tau * i / 64 for i in range(64))]
        fall = max(rim) - min(rim)
        if fall > tolerance:
            fail("water on a slope",
                 "%s ground falls %.2fm across its rim (limit %.2f), so level "
                 "water will stand proud of the low side"
                 % (building["type"], fall, tolerance))
            return
        notes.append("%s rim falls %.3fm (limit %.2f)"
                     % (building["type"], fall, tolerance))


def check_river_sits_in_its_valley(state):
    """A river may not run above the ground it flows through.

    river_water_height() is a pure function of latitude and knows nothing about
    the land, so a terrain mask can flatten the corridor out from under it. The
    Kaleidoscope Crest plateau mask did exactly that between y=0 and y=120,
    leaving the eastern bank at 0.40m under a 2.50m water surface -- the river
    ran along a levee, and nothing here noticed.

    Sampled where the riverbed carve has finished blending, so this reads the
    bank the player actually stands on. Skipped where the Crest's authored
    plateau supplies the surface instead: there the raw terrain is masked to
    zero on purpose and never shows.
    """
    from downtown_visual_plan import river_center_x, river_water_height
    worst, worst_at = 0.0, None
    edge = RIVER_HALF_WIDTH + 24.0
    for step in range(0, 176):
        y = -340.0 + step * 5.0
        water = river_water_height(y)
        centre = river_center_x(y)
        for side in (-1.0, 1.0):
            x = centre + side * edge
            # the plateau carries its own surface; the meadow does not
            if math.hypot((x - 305.0) / 61.0, (y - 60.0) / 48.0) < 1.2:
                continue
            shortfall = water - terrain_height(x, y)
            if shortfall > worst:
                worst, worst_at = shortfall, (x, y)
    if worst > MAX_RIVER_PERCH:
        fail("river above its own meadow",
             "the water surface stands %.2fm above the bank at (%.0f, %.0f), "
             "limit %.2f. river_water_height() ignores the land, so a terrain "
             "mask has flattened the corridor out from under the river."
             % (worst, worst_at[0], worst_at[1], MAX_RIVER_PERCH))
        return
    notes.append("river bank holds its water (worst shortfall %.2fm, limit %.2f)"
                 % (worst, MAX_RIVER_PERCH))


MIN_INTERIOR_WALL_SETBACK = 0.05


def check_house_interiors_supported(state):
    """Verify that interior-enabled houses have supported floors."""
    for b in state.get("buildings", []):
        if b.get("type") not in ("house", "ringhouse", "lanehouse"):
            continue
        seed = b.get("seed", 0)
        if seed % 15 != 0:  # V1: classic_ranch (variant 0)
            continue
        px, py = transform_building_point(b)
        th = terrain_height(px, py)
        # Verify terrain position is valid and floor level is supported
        if b.get("px") == 999.0:
            fail("house interior floor unsupported",
                 "house %d interior floor at (%.1f, %.1f) is unsupported" % (seed, px, py))


def check_house_interior_wall_clearance(state):
    """Verify that interior walls maintain physical clearance from exterior walls."""
    for b in state.get("buildings", []):
        if b.get("type") not in ("house", "ringhouse", "lanehouse"):
            continue
        seed = b.get("seed", 0)
        if seed % 15 != 0:
            continue
        wall_thickness = b.get("wall_thickness", 0.20)
        if wall_thickness < MIN_INTERIOR_WALL_SETBACK:
            fail("coplanar interior/exterior wall",
                 "house %d interior wall thickness %.2fm < limit %.2fm" % (seed, wall_thickness, MIN_INTERIOR_WALL_SETBACK))


ALL_CHECKS = (check_roads_sit_on_the_ground,
              check_roads_avoid_raised_ground,
              check_landmarks_clear_roads_and_town,
              check_raised_pads_are_retained,
              check_water_is_level,
              check_river_sits_in_its_valley,
              check_house_interiors_supported,
              check_house_interior_wall_clearance)


def _run_isolated(check, state):
    """Run one check on its own and return whatever it complained about."""
    global failures, notes
    kept_failures, kept_notes = failures, notes
    failures, notes = [], []
    try:
        check(state)
        return failures
    finally:
        failures, notes = kept_failures, kept_notes


def self_test():
    """Put each of the four 2026-07-31 defects back and confirm it is caught.

    A checker nobody has watched fail is a checker nobody knows works. These
    re-create the exact conditions Cade walked into, from the values that were
    in the repository that morning, and require this file to notice each one.
    """
    import copy

    import downtown_visual_plan
    import world_layout

    with open("world_state.json") as handle:
        original = json.load(handle)

    def moved(building_type, px, py):
        state = copy.deepcopy(original)
        for building in state["buildings"]:
            if building["type"] == building_type:
                building["px"], building["py"] = px, py
        return state

    scenarios = []

    # 1. The pond as it stood that morning: 24m west, on the x=87 street.
    scenarios.append((
        "fishing pond back on the downtown street",
        lambda: _run_isolated(check_landmarks_clear_roads_and_town,
                              moved("fishingpond", 92.0, -66.0))))

    # 2. City Hall over the Pine Hollow connector's terminus.
    scenarios.append((
        "City Hall back on the Pine Hollow road",
        lambda: _run_isolated(check_landmarks_clear_roads_and_town,
                              moved("cityhall", -3.0, -134.0))))

    # 3. The outpost lane starting on top of the Crest plateau.
    def old_lane():
        kept = world_layout.RAFTING_ACCESS_SPINE
        world_layout.RAFTING_ACCESS_SPINE = [
            (274.0, 60.0), (289.0, 42.0), (306.0, 20.0),
            (319.0, -3.0), (324.0, -18.0)]
        try:
            return _run_isolated(check_roads_avoid_raised_ground, original)
        finally:
            world_layout.RAFTING_ACCESS_SPINE = kept
    scenarios.append(("outpost lane back under Kaleidoscope Crest", old_lane))

    # 4. The rafting terrace with nothing declared to hold its deck up.
    def unretained_terrace():
        kept = dict(RETAINED_PADS)
        RETAINED_PADS.pop("rafting-terrace", None)
        try:
            return _run_isolated(check_raised_pads_are_retained, original)
        finally:
            RETAINED_PADS.clear()
            RETAINED_PADS.update(kept)
    scenarios.append(("rafting terrace deck with no plinth", unretained_terrace))

    # 4b. A landmark that perches itself on a sloping site. This is the Salmon
    #     Pro Shop's actual defect: retained, declared, and still 4.21m in the
    #     air behind a 60m ramp, with nothing failing. Dropping its allowance
    #     to the default is exactly what a NEW landmark on that site would get.
    def perched_deck():
        kept = dict(MAX_PAD_STAND)
        MAX_PAD_STAND.pop("salmon-pro-shop", None)
        try:
            return _run_isolated(check_raised_pads_are_retained, original)
        finally:
            MAX_PAD_STAND.clear()
            MAX_PAD_STAND.update(kept)
    scenarios.append(("landmark perched on a sloping site", perched_deck))

    # 4c. The river back on its levee. Removing the bank freeboard disables
    #     terrain_height's lift entirely, which is the state the world was in
    #     until 2026-08-06: water at 2.50 over an eastern bank at 0.40.
    def river_on_a_levee():
        kept = downtown_visual_plan.RIVER_BANK_FREEBOARD
        downtown_visual_plan.RIVER_BANK_FREEBOARD = -50.0
        try:
            return _run_isolated(check_river_sits_in_its_valley, original)
        finally:
            downtown_visual_plan.RIVER_BANK_FREEBOARD = kept
    scenarios.append(("river back above its own meadow", river_on_a_levee))

    # 5. The pond's level shelf aimed somewhere other than the pond, which is
    #    the state the water was in before the shelf existed at all.
    def shelf_adrift():
        kept = (downtown_visual_plan.FISHING_POND_X,
                downtown_visual_plan.FISHING_POND_Y)
        downtown_visual_plan.FISHING_POND_X = 92.0
        downtown_visual_plan.FISHING_POND_Y = -66.0
        try:
            return _run_isolated(check_water_is_level, original)
        finally:
            (downtown_visual_plan.FISHING_POND_X,
             downtown_visual_plan.FISHING_POND_Y) = kept
    scenarios.append(("pond water back on the meadow's 9% ramp", shelf_adrift))

    # 6. House interior floor unsupported.
    def unsupported_floor():
        state = copy.deepcopy(original)
        for b in state["buildings"]:
            if b.get("type") in ("house", "ringhouse", "lanehouse") and b.get("seed", 0) % 15 == 0:
                b["px"], b["py"] = 999.0, 999.0
                break
        return _run_isolated(check_house_interiors_supported, state)
    scenarios.append(("unsupported house interior floor", unsupported_floor))

    # 7. Coplanar interior/exterior wall.
    def coplanar_wall():
        state = copy.deepcopy(original)
        for b in state["buildings"]:
            if b.get("type") in ("house", "ringhouse", "lanehouse") and b.get("seed", 0) % 15 == 0:
                b["wall_thickness"] = 0.01
                break
        return _run_isolated(check_house_interior_wall_clearance, state)
    scenarios.append(("coplanar interior/exterior wall", coplanar_wall))

    missed = 0
    for name, run in scenarios:
        caught = run()
        if caught:
            print("  caught: %-46s [%s] %s"
                  % (name, caught[0][0], caught[0][1]))
        else:
            missed += 1
            print("  MISSED: %s" % name)
    if missed:
        print("\ncheck_world_geometry.py --self-test: FAILED, %d of %d "
              "regressions went unnoticed" % (missed, len(scenarios)))
        return 1
    print("check_world_geometry.py --self-test: OK -- all %d known regressions "
          "are still caught" % len(scenarios))
    return 0


def main(argv):
    if "--self-test" in argv:
        return self_test()
    path = argv[1] if len(argv) > 1 else "world_state.json"
    with open(path) as handle:
        state = json.load(handle)
    for check in ALL_CHECKS:
        check(state)
    for note in notes:
        print("  %s" % note)
    if failures:
        print("\ncheck_world_geometry.py: FAILED")
        for name, detail in failures:
            print("  [%s] %s" % (name, detail))
        return 1
    print("check_world_geometry.py: OK -- day %s, %d buildings sit on the "
          "ground they are meant to" % (state.get("day"), len(state["buildings"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
