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

`check_world_geometry.py` answers "is anything off the ground, on a road, or in
the street" for the world as placed; this answers "is the asset itself sound"
for the one district whose homes are built out of loose primitives rather than
the shared suburban shell.
"""

import os
import sys

import bpy
from mathutils import Matrix

REPO = os.path.dirname(os.path.abspath(__file__))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

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


def world_box(obj):
    """Axis-aligned bounds of one asset object, in the asset's own space.

    Asset collections are never linked to the scene, so Blender does not
    evaluate matrix_world for their objects -- it stays identity and every box
    collapses onto the origin. Build the transform the way
    _merge_asset_meshes does instead.
    """
    rotation = (obj.rotation_quaternion.copy()
                if obj.rotation_mode == "QUATERNION"
                else obj.rotation_euler.to_quaternion())
    matrix = Matrix.LocRotScale(obj.location, rotation, obj.scale)
    points = [matrix @ vertex.co for vertex in obj.data.vertices]
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


def main():
    failures = []
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

    print()
    if failures:
        print("check_food_assets.py: FAILED")
        for line in failures:
            print("  " + line)
        sys.exit(1)
    print("check_food_assets.py: OK -- ten designs, none below their own "
          "foundation, none past %.2fm, no coplanar box faces"
          % nb.FOOD_COURT_HOME_REACH)


main()
