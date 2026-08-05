"""Deterministic render-time layout transforms for the experimental city.

The authoritative Day-15 state keeps its original IDs, claims, addresses and
stored coordinates.  This module moves complete districts as rigid groups so
the expanded downtown cannot overlap their roads.  Every consumer (Blender,
the local browser and QA) uses the same offsets.
"""


DISTRICT_OFFSETS = {
    "Creekside Bend": (0.0, 58.0),
    "Willow Hills": (-48.0, 48.0),
    "Twin Oaks": (-62.0, 0.0),
    "Meadow Run": (-48.0, -48.0),
    "Pine Hollow": (0.0, -62.0),
    "North Ridge": (48.0, -48.0),
}

FOUNDER_PARK_OFFSET = (35.0, 0.0)
STORYBOOK_OFFSET = (35.0, 0.0)
STORYBOOK_LAYOUT_CENTER = (305.0, 60.0)

# The Salmon Pro Shop's approach, leaving Pebble Court's terminus at (78,232)
# and running east into the store's lot. The whole run sits between z=6.07 and
# z=6.14, so it is level enough to need no grading at all -- which is why the
# store went where it did.
# The store faces east into the city, so its lot faces the city too and the
# drive comes off the Meadow Run connector on the city side rather than
# doubling back round the building.
#
# It arrives the long way on purpose. The site falls 3.8m west to east, the
# pad is level at the high end, and the lot is therefore about 3.9m above the
# ground on the side the drive comes from. A short entrance would have been a
# 28% ramp; this sweep spreads the same climb over roughly 60m, which is
# inside the ~13% the rest of the town's streets hold to.
#
# It also stays clear of the pad until the kerb gap: an earlier line cut the
# corner, and a raytrace came back with the pad slab 26cm ABOVE the asphalt --
# the road was running underneath its own car park.
SALMON_SHOP_APPROACH = [(-101.0, -88.0), (-99.0, -78.0), (-102.0, -70.0),
                        (-107.0, -63.0), (-113.0, -56.0)]
# Where the drive stops being a road and becomes the lot, in world metres. The
# last stretch ramps from the ground up onto the store's pad so the asphalt
# meets the lot surface flush instead of stepping into its edge.
SALMON_SHOP_ENTRY_RAMP = 30.0

# Authored roads that are not in the suburban plan. They live here so that
# check_world_geometry.py can see every road in the town; a checker that only
# knows about half the roads will happily approve a building sitting on one of
# the others, which is how City Hall came to swallow the Pine Hollow terminus.
#
# The City Hall approach keeps its junction on the x=-3 grid intersection and
# bends east to the portico, because the campus moved 13m east on 2026-07-31
# and a straight road would have left a T-junction mid-block.
CITY_HALL_APPROACH = [(-3.0, -93.0), (-3.0, -101.0), (0.5, -108.0),
                      (6.0, -113.5), (10.0, -118.0), (10.0, -121.0)]
# The Kaleidoscope Crest approach: established asphalt at the grid, then a
# climb up the hill shoulder onto the plateau. The z values are authored, not
# terrain-derived -- that is the whole point, the road is on the hill.
STORYBOOK_ACCESS = [(87.0, 33.0, 0.0), (112.0, 56.0, .02), (149.0, 72.0, .02),
                    (198.0, 74.0, .03), (236.0, 72.0, .05), (240.0, 71.0, .28),
                    (243.0, 70.0, .80), (246.0, 69.0, 1.55), (248.0, 68.0, 2.30),
                    (250.0, 68.0, 2.62), (254.0, 67.0, 2.74),
                    (264.0, 65.0, 2.74), (274.0, 60.0, 2.74)]

# The lane from Kaleidoscope Crest down to the rafting outpost. It lives here
# because the geometry and the browser's walk surface both need it and they
# used to hold separate copies.
#
# The old line ran (274,60) -> (324,-18) with its first point on top of the
# Crest plateau but its height taken from the terrain, so 55m of it was buried
# under the hill, and it stopped 11m short of the outpost. This one leaves the
# Crest's approach where that road is still at grade, keeps outside the
# plateau's outer ring the whole way round the south of the hill, climbs the
# outpost's bank at no more than 11%, and finishes on the terrace forecourt.
RAFTING_ACCESS_SPINE = [
    (236.0, 72.0), (238.0, 54.0), (241.0, 36.0), (247.0, 22.0), (256.0, 10.0),
    (268.0, 0.0), (282.0, -8.0), (296.0, -14.0), (308.0, -19.0),
    (318.0, -22.5), (323.0, -23.5),
]

# Followville First Alert Weather sits on a retained terrace immediately north
# of the legacy grid. Its diagonal drive climbs from the north edge street
# without extending the flat downtown road grid into the surrounding hillside.
WEATHER_STATION_CENTER = (29.5, 106.0)
WEATHER_STATION_HALF_EXTENTS = (15.5, 13.5)


def weather_station_base_height():
    """Level weather-campus datum, pinned above its highest terrain corner."""
    from downtown_visual_plan import terrain_height
    cx, cy = WEATHER_STATION_CENTER
    hx, hy = WEATHER_STATION_HALF_EXTENTS
    return max(terrain_height(cx + dx, cy + dy)
               for dx in (-hx, 0.0, hx)
               for dy in (-hy, 0.0, hy)) + .12


def weather_station_access_points(step=2.5):
    """Closely sampled authored ramp from the grid road to the terrace."""
    import math
    from downtown_visual_plan import terrain_height
    cx, cy = WEATHER_STATION_CENTER
    base = weather_station_base_height() + .18
    # A straight, perpendicular driveway reads as a real entrance and aligns
    # with the west parking aisle. The former diagonal route made the raised
    # deck look like a loose wedge laid over the street.
    spine = [(cx - 10.0, 87.0), (cx - 10.0, cy - 9.5)]
    lengths = [math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(spine, spine[1:])]
    total = sum(lengths)
    # The driveway surface uses an 8cm top offset in Blender. Starting at
    # +9cm makes its top exactly meet the downtown road's 17cm asphalt top.
    start_z = terrain_height(*spine[0]) + .09
    points = []
    travelled = 0.0
    for (a, b), length in zip(zip(spine, spine[1:]), lengths):
        count = max(1, int(math.ceil(length / step)))
        for index in range(count):
            local = index / count
            distance = travelled + length * local
            t = distance / total if total else 1.0
            points.append((
                a[0] + (b[0] - a[0]) * local,
                a[1] + (b[1] - a[1]) * local,
                start_z + (base - start_z) * t,
            ))
        travelled += length
    points.append((spine[-1][0], spine[-1][1], base))
    return points


# --- what check_world_geometry.py audits against -------------------------
#
# Every entry below is a claim about the world that a person made on purpose.
# The checker's job is to notice when the world stops matching them. All four
# defects Cade found by walking on 2026-07-31 are expressible here, and none
# of them were expressible anywhere before.

# Off-grid landmarks, as the rectangle their built geometry actually occupies
# in local coordinates, before the record's px/py is added. "rural" means the
# landmark belongs outside the paved downtown envelope -- the fishing pond was
# moved onto the x=87 street precisely because nothing said so.
#
# A type missing from here is reported as unaudited rather than failing, so
# adding a landmark never breaks the build. Adding its footprint is what makes
# the checker able to defend it.
#
# Approach paths are deliberately left out: the pond's sidewalk starts on the
# town's kerb because that is what it is for, and including it would make the
# pond look like it was standing in the street again.
LANDMARK_FOOTPRINTS = {
    #                     x0      x1      y0      y1   rural
    "cityhall":        (-22.5,   22.5,  -11.0,   20.0, False),
    "civicsquare":     (-23.0,   17.0,  -16.0,   16.0, False),
    "fishingpond":     (-26.0,   23.0,  -17.0,   16.0, True),
    "raftingstation":   (-9.0,   33.0,   -8.0,   12.0, True),
    # Turned a quarter turn to face the city, so the pad is 56 wide by 50 deep.
    "salmonproshop":   (-28.0,   28.0,  -25.0,   25.0, True),
    "weatherstation":  (-15.5,   15.5,  -13.5,   13.5, False),
}

# Authored ground that stands above the terrain. A road whose deck is taken
# from the terrain must not pass through one of these, or it runs underneath
# the hill: 55m of the outpost lane did exactly that, invisible to every
# height query because the terrain under the plateau really is at zero.
# Ellipses, as (name, cx, cy, rx, ry).
KEEP_OUT_REGIONS = [
    ("Kaleidoscope Crest plateau", 305.0, 60.0, 61.0, 48.0),
]

# Walk pads whose deck deliberately stands clear of the ground, each with the
# structure that holds it up. A pad standing proud with nothing named here is
# a pad hanging in the air -- which is what the rafting terrace was doing on
# three of its four sides until its plinth was closed all the way round.
RETAINED_PADS = {
    "rafting-terrace": "continuous stone plinth, _add_retaining_skirt()",
    "salmon-pro-shop": "fieldstone skirt round the whole pad, "
                       "_add_retaining_skirt()",
    "rafting-dock": "timber piles driven to the riverbed",
    "rafting-forecourt": "retaining skirt on its three downhill edges",
    "fishing-dock": "steel piles in the pond",
    "weather-station-campus": "continuous concrete retaining wall",
}

# Road decks that are meant to be off the ground, and why. Rectangles in world
# coordinates, as (name, x0, x1, y0, y1).
INTENTIONALLY_RAISED_ROADS = [
    ("Founders Crossing bridge deck", 275.0, 415.0, -230.0, -195.0),
    ("rafting launch boardwalk", 332.0, 360.0, -34.0, -26.0),
    ("First Alert Weather access ramp", 16.5, 22.5, 84.0, 108.0),
]

# Water surfaces that must be level, with how far their rim may fall across
# the whole body before the water starts standing proud of its own bank.
LEVEL_WATER = {"fishingpond": 0.12}

# The road that serves each landmark is allowed to touch it -- that is what a
# road to somewhere does. Every other road must keep its distance.
LANDMARK_APPROACHES = {
    "cityhall": {"City Hall approach"},
    "civicsquare": {"City Hall approach"},
    "raftingstation": {"rafting outpost lane"},
    "salmonproshop": {"Salmon Pro Shop approach"},
    "weatherstation": {"First Alert Weather access"},
}

# Roads that carry their own authored heights rather than following the
# terrain. These are allowed inside KEEP_OUT_REGIONS, because climbing onto
# the raised ground is the whole point of them.
AUTHORED_ELEVATION_ROADS = {"Kaleidoscope Crest access"}


def rafting_access_points(step=3.0):
    """The lane's centreline, sampled closely enough to stay on the ground.

    A road strip keeps whichever is higher, its authored height or the terrain
    under it, so control points 26m apart let the straight line between two
    samples ride up to 0.6m above a concave grade -- which is exactly what
    lifted the last stretch of the old lane off the meadow.

    Six metres held the rendered road to 15mm, because _add_road_strip
    subdivides to two internally. The walk surface does not -- it uses these
    points as given -- so the surface the player stands on drifted further
    from the road they can see than either did from the ground. Three metres
    keeps the two within about a centimetre of each other.
    """
    import math

    points = []
    for a, b in zip(RAFTING_ACCESS_SPINE, RAFTING_ACCESS_SPINE[1:]):
        count = max(1, int(math.ceil(math.hypot(b[0]-a[0], b[1]-a[1])/step)))
        for index in range(count):
            t = index/count
            points.append((a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t))
    points.append(RAFTING_ACCESS_SPINE[-1])
    return points

# Curved transition roads begin on an outer downtown street and terminate at
# each shifted district's original entrance. They reveal only when that
# district has at least one house, preserving staged-road behavior.
DISTRICT_CONNECTORS = {
    "Creekside Bend": [(-35.0, 87.0), (-41.0, 99.0), (-39.0, 114.0), (-35.0, 127.0)],
    "Willow Hills": [(-93.0, 70.0), (-101.0, 82.0), (-112.0, 96.0), (-123.0, 112.0)],
    "Twin Oaks": [(-93.0, 20.0), (-108.0, 17.0), (-123.0, 18.0), (-137.0, 20.0)],
    "Meadow Run": [(-93.0, -70.0), (-101.0, -88.0), (-112.0, -107.0), (-123.0, -123.0)],
    "Pine Hollow": [(-24.0, -93.0), (-29.0, -108.0), (-27.0, -123.0), (-24.0, -137.0)],
    "North Ridge": [(70.0, -93.0), (91.0, -99.0), (114.0, -111.0), (133.0, -123.0)],
}


def offset_for(district=None, building_type=None, feature_id=None):
    if district in DISTRICT_OFFSETS:
        return DISTRICT_OFFSETS[district]
    if building_type in ("parkdistrict", "ringhouse"):
        return FOUNDER_PARK_OFFSET
    if building_type == "storybookhouse" or feature_id == "kaleidoscope_crest_day15":
        return STORYBOOK_OFFSET
    return (0.0, 0.0)


def transform_point(x, y, district=None, building_type=None, feature_id=None):
    dx, dy = offset_for(district, building_type, feature_id)
    return float(x) + dx, float(y) + dy


def transform_building_point(building):
    return transform_point(
        building.get("px", 0.0), building.get("py", 0.0),
        district=building.get("district"),
        building_type=building.get("type"),
        feature_id=building.get("feature_id"),
    )


def walk_surface_manifest(state):
    """Exact revealed suburban road decks for browser walking/collision QA."""
    import math

    from downtown_visual_plan import terrain_height, river_water_height
    from neighborhood_plan import PLAN

    active = max((building.get("plan_id", 0)
                  for building in state.get("buildings", [])), default=0)
    segments = []

    # Blender exports are produced on Windows while CI validates on Linux.
    # Round derived terrain samples to sub-millimetre precision so harmless
    # libm differences cannot make an otherwise identical manifest fail exact
    # JSON comparison across operating systems.
    def stable_height(value):
        return round(float(value), 4)

    def append_road(ax, ay, bx, by, half_width=3.25):
        length = math.hypot(bx - ax, by - ay)
        steps = max(1, int(math.ceil(length / 2.0)))
        samples = []
        for step in range(steps + 1):
            t = step / steps
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            samples.append((x, y, terrain_height(x, y)))
        for a, b in zip(samples, samples[1:]):
            segments.append([stable_height(a[0]), stable_height(-a[1]),
                             stable_height(a[2]), stable_height(b[0]),
                             stable_height(-b[1]), stable_height(b[2]),
                             half_width])

    def append_graded_road(points, half_width):
        for a, b in zip(points, points[1:]):
            segments.append([
                stable_height(a[0]), stable_height(-a[1]), stable_height(a[2]),
                stable_height(b[0]), stable_height(-b[1]), stable_height(b[2]),
                half_width,
            ])

    active_districts = {building.get("district")
                        for building in state.get("buildings", [])
                        if building.get("plan_id")}
    for district in sorted(active_districts):
        connector = DISTRICT_CONNECTORS.get(district, ())
        for (ax, ay), (bx, by) in zip(connector, connector[1:]):
            append_road(ax, ay, bx, by)
    river = PLAN.get("river") or {}
    bridge = river.get("bridge") or {}
    river_active = active >= int(bridge.get("reveal_at", 10**9))
    if river_active:
        start = tuple(bridge["approach"][0])
        end = (410.0, -214.0)
        start_z = terrain_height(*start)+.18
        end_z = terrain_height(*end)+.22
        deck = []
        for index in range(9):
            t = index/8.0
            deck.append((start[0]+(end[0]-start[0])*t,
                         start[1]+(end[1]-start[1])*t,
                         start_z+(end_z-start_z)*t+.14))
        append_graded_road(deck, 3.95)
    for segment in PLAN["roads"]:
        if segment["reveal_at"] > active:
            continue
        ax, ay = transform_point(*segment["a"], district=segment.get("district"))
        bx, by = transform_point(*segment["b"], district=segment.get("district"))
        append_road(ax, ay, bx, by)
    bulbs = []
    for bulb in PLAN["turnarounds"]:
        if bulb["reveal_at"] > active:
            continue
        x, y = transform_point(*bulb["center"], district=bulb.get("district"))
        bulbs.append([stable_height(x), stable_height(-y),
                      stable_height(terrain_height(x, y)), 8.35])
    pads = []
    for building in state.get("buildings", []):
        if building.get("type") != "fishingpond":
            continue
        x, y = transform_building_point(building)
        water_height = max(
            terrain_height(
                x + 18.0 * math.cos(math.tau * index / 48),
                y + 11.3 * math.sin(math.tau * index / 48),
            )
            for index in range(48)
        ) + .14
        # Center/half-extents mirror build_fishing_pond's T-shaped west dock.
        pads.append([
            stable_height(x - 10.8), stable_height(-y + 2.7),
            stable_height(water_height + .28), 5.6, 3.5, "fishing-dock",
        ])
    rafting = next((building for building in state.get("buildings", [])
                    if building.get("type") == "raftingstation"), None)
    if rafting:
        x, y = transform_building_point(rafting)
        base_z = max(
            terrain_height(x + dx, y + dy)
            for dx in (-8.0, 0.0, 8.0)
            for dy in (-6.0, 0.0, 6.0)
        ) + .12
        water_z = river_water_height(y)
        append_graded_road(
            [(ax, ay, terrain_height(ax, ay) + .055)
             for ax, ay in rafting_access_points()],
            2.2)
        launch = [
            (x + 5.8, y, base_z + .16),
            (x + 10.0, y, base_z - .64),
            (x + 14.5, y, base_z - 1.68),
            (x + 19.0, y, water_z + .38),
            (x + 26.0, y, water_z + .38),
        ]
        append_graded_road(launch, 1.28)
        pads.append([
            stable_height(x), stable_height(-y), stable_height(base_z + .10),
            9.0, 7.0, "rafting-terrace",
        ])
        pads.append([
            stable_height(x + 27.5), stable_height(-y),
            stable_height(water_z + .44), 4.25, 2.8, "rafting-dock",
        ])
        # Where the lane ends, below the terrace plinth's stair.
        pads.append([
            stable_height(x - 5.0), stable_height(-y - 9.5),
            stable_height(terrain_height(x - 5.0, y + 7.6) + .24),
            4.0, 2.5, "rafting-forecourt",
        ])
    weather_station = next((building for building in state.get("buildings", [])
                            if building.get("type") == "weatherstation"), None)
    if weather_station:
        x, y = transform_building_point(weather_station)
        access = weather_station_access_points()
        append_graded_road(access, 2.35)
        half_x, half_y = WEATHER_STATION_HALF_EXTENTS
        pads.append([
            stable_height(x), stable_height(-y),
            stable_height(weather_station_base_height() + .18),
            half_x, half_y, "weather-station-campus",
        ])
    river_manifest = None
    if river_active:
        river_manifest = {
            "centerline": [[stable_height(x), stable_height(-y),
                            stable_height(river_water_height(y))]
                           for x, y in river["centerline"]],
            "halfWidth": stable_height(river.get("half_width", 14.0)),
            "bridgeName": bridge.get("name"),
        }
    return {"activePlanId": active, "segments": segments,
            "bulbs": bulbs, "pads": pads, "river": river_manifest}
