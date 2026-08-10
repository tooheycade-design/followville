"""Are the ten Food Court home designs well-formed?

    & "C:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe" ^
        --background --factory-startup --python check_food_assets.py

This needs Blender, because the only honest answer comes from building the
assets. It builds each of the ten designs on its own, before the per-house merge
collapses them, and requires of every one:

  * nothing hangs deeper than the foundation's own bite into the ground. The
    burger used to be a 4.45m sphere centred 3.3m up, so 1.15m of it was below
    the world and its sesame seeds were sealed inside it.
  * nothing reaches past FOOD_COURT_HOME_REACH toward the plaza. The loop road's
    kerb is 5.0m from a home's anchor, and the old homes ran a 4m front path
    straight out from the lot envelope.
  * no two axis-aligned boxes share a face plane over an overlapping area --
    the coplanar-surface fault CLAUDE.md's depth rule forbids, and the one the
    old stack of resting slabs was full of.

It then measures every one of the nineteen standing homes against both of the
district's roads, using each home's real footprint rather than a nominal
envelope. This is the part that would have caught the district's oldest defect:
the connector out to the river ran 1.77m inside the fries carton's foundation
from the day the Food Court shipped, and `check_world_geometry.py` could not see
it, because that checker matches roads against *declared landmark* footprints
and a food home is a house.

`check_world_geometry.py` answers "is anything off the ground, on a road, or in
the street" for the world as placed; this answers "is the asset itself sound,
and does it clear its own streets" for the one district whose homes are built
out of loose primitives rather than the shared suburban shell.
"""

import json
import math
import os
import sys

import bpy
from mathutils import Matrix

REPO = os.path.dirname(os.path.abspath(__file__))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

# neighborhood_blender runs a growth on import in a background Blender session
# -- that is how the generator is launched. This must be set BEFORE the import
# or reading the module changes the city: it did exactly that once, advancing the
# world to day 40 and appending five houses, which left town_manifest.json
# disagreeing with world_state.json and dropped the browser out of streaming.
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"

import neighborhood_blender as nb

# The coplanar check has to see the individual primitives, so stop the per-house
# merge from collapsing them into one mesh first.
nb._merge_asset_meshes = lambda col, name: None

EPS = 1e-4
FACE_TOLERANCE = .004          # planes closer than this count as coincident
OVERLAP_TOLERANCE = .02        # ignore hairline overlaps at shared corners
DEEPEST_SINK = .22             # _food_plinth's step, the lowest thing authored

# _sub_door stacks its door panels 2.5mm inside the slab and _sub_window puts
# both mullions on one plane so they can cross. Those are the shared helpers
# every house in Followville uses, not anything the food homes introduce, so
# changing them is an ~800-house decision and out of this audit's scope.
SHARED_HELPER_PAIRS = (
    ("food_entry_slab", "food_entry_panel"),
    ("food_window_mv", "food_window_mh"),
)


def world_points(obj):
    """One asset object's vertices in the asset's own space.

    Asset collections are never linked to the scene, so Blender does not
    evaluate matrix_world for their objects -- it stays identity and every box
    collapses onto the origin. Build the transform the way
    _merge_asset_meshes does instead.
    """
    rotation = (obj.rotation_quaternion.copy()
                if obj.rotation_mode == "QUATERNION"
                else obj.rotation_euler.to_quaternion())
    matrix = Matrix.LocRotScale(obj.location, rotation, obj.scale)
    return [matrix @ vertex.co for vertex in obj.data.vertices]


def world_box(obj):
    points = world_points(obj)
    return (min(p.x for p in points), max(p.x for p in points),
            min(p.y for p in points), max(p.y for p in points),
            min(p.z for p in points), max(p.z for p in points))


def is_axis_aligned_box(obj):
    if len(obj.data.vertices) != 8 or len(obj.data.polygons) != 6:
        return False
    rotation = obj.rotation_euler
    return (abs(rotation.x) < EPS and abs(rotation.y) < EPS
            and abs(rotation.z) < EPS)


def overlaps(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > OVERLAP_TOLERANCE


def from_shared_helper(name_a, name_b):
    pair = (name_a.split(".")[0], name_b.split(".")[0])
    return pair in SHARED_HELPER_PAIRS or pair[::-1] in SHARED_HELPER_PAIRS


def coplanar_pairs(variant, meshes):
    """Every pair of axis-aligned boxes sharing a face plane where they meet."""
    found, seen = [], set()
    aligned = [(obj.name, world_box(obj)) for obj in meshes
               if is_axis_aligned_box(obj)]
    for index, (name_a, a) in enumerate(aligned):
        for name_b, b in aligned[index + 1:]:
            if from_shared_helper(name_a, name_b):
                continue
            for axis, span_a, span_b, first, second in (
                    ("z", (a[4], a[5]), (b[4], b[5]),
                     ((a[0], a[1]), (b[0], b[1])), ((a[2], a[3]), (b[2], b[3]))),
                    ("y", (a[2], a[3]), (b[2], b[3]),
                     ((a[0], a[1]), (b[0], b[1])), ((a[4], a[5]), (b[4], b[5]))),
                    ("x", (a[0], a[1]), (b[0], b[1]),
                     ((a[2], a[3]), (b[2], b[3])), ((a[4], a[5]), (b[4], b[5])))):
                coincident = any(
                    abs(one - other) < FACE_TOLERANCE
                    for one, other in ((span_a[1], span_b[0]),
                                       (span_b[1], span_a[0]),
                                       (span_a[0], span_b[0]),
                                       (span_a[1], span_b[1])))
                if not coincident:
                    continue
                if not (overlaps(first[0][0], first[0][1],
                                 first[1][0], first[1][1])
                        and overlaps(second[0][0], second[0][1],
                                     second[1][0], second[1][1])):
                    continue
                key = (name_a, name_b, axis)
                if key in seen:
                    continue
                seen.add(key)
                found.append("style %d: %s and %s share a %s face plane over an "
                             "overlapping area" % (variant, name_a, name_b, axis))
    return found


MIN_VERGE = .10                # grass a home must keep between it and a kerb


def convex_hull(points):
    """Monotone chain. A home's footprint, not a box drawn round it.

    Boxing the footprint is not good enough here: a 14-gon plinth of radius
    4.44 with a doorstep in front has bounding-box corners 6.45m from its
    anchor, which reports two homes as standing in a road they clear.
    """
    ordered = sorted(set((round(x, 4), round(y, 4)) for x, y in points))
    if len(ordered) < 3:
        return ordered

    def half(sequence):
        chain = []
        for point in sequence:
            while len(chain) >= 2:
                (ax, ay), (bx, by) = chain[-2], chain[-1]
                if ((bx - ax) * (point[1] - ay)
                        - (by - ay) * (point[0] - ax)) <= 0:
                    chain.pop()
                else:
                    break
            chain.append(point)
        return chain

    lower, upper = half(ordered), half(reversed(ordered))
    return lower[:-1] + upper[:-1]


def point_to_segment(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(point[0] - (a[0] + dx * t), point[1] - (a[1] + dy * t))


def worst_verge(footprint, centreline, widths):
    """Least grass between a home's footprint and a road's kerb, in metres.

    Negative means the carriageway is inside the home. Sampled corner-to-segment
    both ways round, because a home's corner can be closest to the middle of a
    road segment and a road's control point closest to the middle of a wall.
    """
    verge = float("inf")
    for index, (a, b) in enumerate(zip(centreline, centreline[1:])):
        half = max(widths[index], widths[index + 1]) / 2
        for corner in footprint:
            verge = min(verge, point_to_segment(corner, a, b) - half)
        for point in (a, b):
            for corner_a, corner_b in zip(footprint,
                                          footprint[1:] + footprint[:1]):
                verge = min(verge,
                            point_to_segment(point, corner_a, corner_b) - half)
    return verge


def home_footprint(hull, x, y, rot):
    """A home's footprint in world metres, placed and turned like the instance."""
    cos_r, sin_r = math.cos(rot), math.sin(rot)
    return [(x + lx * cos_r - ly * sin_r, y + lx * sin_r + ly * cos_r)
            for lx, ly in hull]


def reach_toward(footprint, x, y, target):
    """How far a home's footprint reaches from its anchor toward a point."""
    length = math.hypot(target[0] - x, target[1] - y)
    if length == 0:
        return 0.0
    ux, uy = (target[0] - x) / length, (target[1] - y) / length
    return max((corner[0] - x) * ux + (corner[1] - y) * uy
               for corner in footprint)


def check_roads(hulls):
    """Every standing home against both of the district's roads."""
    # Beside this script by default, like check_world_geometry.py and
    # check_town_glb.py -- neighborhood_blender's state_path() resolves relative
    # to the loaded .blend, and there is no .blend loaded here.
    failures = []
    state_file = os.path.join(os.environ.get("NEIGHBORHOOD_STATE_DIR") or REPO,
                              "world_state.json")
    with open(state_file, encoding="utf-8") as handle:
        state = json.load(handle)
    homes = [b for b in state.get("buildings", [])
             if b.get("type") == "foodhouse"]
    if len(homes) != nb.FOOD_COURT_HOMES:
        # Silence here would be worse than a failure: an empty list used to read
        # as a clean pass, which is the mistake this whole district is a lesson in.
        return ["found %d foodhouse records in %s, expected %d -- the road "
                "clearances were not checked"
                % (len(homes), state_file, nb.FOOD_COURT_HOMES)]

    loop = [(nb.FOOD_COURT_X + 32.0 * math.cos(math.tau * i / 72),
             nb.FOOD_COURT_Y + 25.0 * math.sin(math.tau * i / 72))
            for i in range(73)]
    loop_widths = [nb.ROAD] * len(loop)
    lane_local, lane_widths = nb.food_court_connector()
    lane = [(nb.FOOD_COURT_X + px, nb.FOOD_COURT_Y + py)
            for px, py in lane_local]

    print()
    print("  home  style          loop verge   lane verge")
    footprints = {}
    for index, home in enumerate(homes):
        style = int(home["seed"]) % 10
        footprint = home_footprint(hulls[style], home["px"], home["py"],
                                   home["rot"])
        footprints[index] = (home, footprint)
        loop_verge = worst_verge(footprint, loop, loop_widths)
        lane_verge = worst_verge(footprint, lane, lane_widths)
        flag = "   <-- ON A ROAD" if min(loop_verge, lane_verge) < 0 else ""
        print("  %4d  style %d  %10.2f m %11.2f m%s"
              % (index, style, loop_verge, lane_verge, flag))
        for road, verge in (("loop road", loop_verge), ("river lane", lane_verge)):
            if verge < MIN_VERGE - EPS:
                failures.append(
                    "home %d (style %d) keeps only %.2fm of grass from the %s, "
                    "under the %.2fm minimum"
                    % (index, style, verge, road, MIN_VERGE))

    # food_court_connector() sites the lane from two hand-recorded reaches. They
    # are the one place this district's road geometry is not derived, so measure
    # them off the built designs rather than trusting them.
    print()
    first, second = nb.FOOD_COURT_GAP_INDICES
    for index, partner, declared in ((first, second, nb.FOOD_COURT_GAP_REACH[0]),
                                     (second, first, nb.FOOD_COURT_GAP_REACH[1])):
        home, footprint = footprints[index]
        partner_home, _ = footprints[partner]
        measured = reach_toward(footprint, home["px"], home["py"],
                               (partner_home["px"], partner_home["py"]))
        print("  home %d reaches %.3fm toward home %d; "
              "FOOD_COURT_GAP_REACH declares %.2f"
              % (index, measured, partner, declared))
        # Which stretch of the lane actually comes closest, so a failure says
        # where to change the profile rather than only that it is too tight.
        tight, tight_at = float("inf"), None
        for seg, (a, b) in enumerate(zip(lane, lane[1:])):
            half = max(lane_widths[seg], lane_widths[seg + 1]) / 2
            gap = min(point_to_segment(corner, a, b)
                      for corner in footprint) - half
            if gap < tight:
                tight, tight_at = gap, (seg, half)
        print("     closest at lane segment %d (half-width %.2f): %+.2fm"
              % (tight_at[0], tight_at[1], tight))
        if measured > declared + EPS:
            failures.append(
                "FOOD_COURT_GAP_REACH says home %d reaches %.2fm toward the "
                "lane's gap, but it reaches %.3fm -- the lane is sited from "
                "that number, so correct it and re-check"
                % (index, declared, measured))
    return failures


def state_fingerprint():
    """Day, population and building count, so a checker cannot grow the city."""
    path = os.path.join(os.environ.get("NEIGHBORHOOD_STATE_DIR") or REPO,
                        "world_state.json")
    if not os.path.exists(path):
        return path, None
    with open(path, encoding="utf-8-sig") as handle:
        state = json.load(handle)
    return path, (state.get("day"), state.get("pop"),
                  len(state.get("buildings") or []))


def main():
    failures = []
    hulls = {}
    state_path, before = state_fingerprint()
    print()
    for variant in range(10):
        col = bpy.data.collections.new("FOODCHECK_%02d" % variant)
        nb.build_food_house(col, variant)
        meshes = [obj for obj in col.objects if obj.type == "MESH"]
        boxes = [world_box(obj) for obj in meshes]
        low = min(box[4] for box in boxes)
        high = max(box[5] for box in boxes)
        front = max(-box[2] for box in boxes)
        reach = max(max(abs(box[0]), abs(box[1]), abs(box[2]), abs(box[3]))
                    for box in boxes)
        hulls[variant] = convex_hull(
            [(point.x, point.y) for obj in meshes for point in world_points(obj)])
        print("  style %d  parts %3d  z %6.2f .. %5.2f  front %5.3f  reach %5.3f"
              % (variant, len(meshes), low, high, front, reach))

        if low < -DEEPEST_SINK - EPS:
            failures.append("style %d has geometry at z=%.3f, deeper than the "
                            "foundation's %.2fm bite into the ground"
                            % (variant, low, DEEPEST_SINK))
        if front > nb.FOOD_COURT_HOME_REACH + EPS:
            failures.append("style %d reaches %.3fm toward the loop road, past "
                            "the %.2fm limit"
                            % (variant, front, nb.FOOD_COURT_HOME_REACH))
        failures.extend(coplanar_pairs(variant, meshes))

        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(col)

    failures.extend(check_roads(hulls))

    # A checker must not change the city. This one imports the generator, and the
    # generator's whole launch mechanism is "run on import", so say so out loud
    # rather than trusting the guard to stay in place.
    _, after = state_fingerprint()
    if after != before:
        failures.append("world_state.json changed while checking: %s -> %s. "
                        "Something ran a growth -- see FOLLOWVILLE_IMPORT_ONLY "
                        "at the bottom of neighborhood_blender.py"
                        % (before, after))

    print()
    if failures:
        print("check_food_assets.py: FAILED")
        for line in failures:
            print("  " + line)
        sys.exit(1)
    print("check_food_assets.py: OK -- ten designs sound, and all nineteen "
          "homes keep at least %.2fm of grass from both roads" % MIN_VERGE)


main()
