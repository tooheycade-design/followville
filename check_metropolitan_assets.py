"""Build and audit all twenty Crown Quarter tower assets in isolation.

Run with Blender, not the Python executable::

    blender --background --factory-startup --python check_metropolitan_assets.py

The guard below is mandatory: importing ``neighborhood_blender`` in a
background Blender session otherwise runs a real growth.
"""

import math
import os
import sys

import bpy
from mathutils import Matrix

REPO = os.path.dirname(os.path.abspath(__file__))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"

import neighborhood_blender as nb
from metropolitan_plan import (TOWER_COUNT, TOWER_PLAN, NORTH_SOUTH_X,
                               EAST_WEST_Y, LOCAL_ROAD_WIDTH,
                               BOULEVARD_WIDTH)

# Preserve the authored primitives so the audit can measure each one.
nb._merge_asset_meshes = lambda col, name: None

EPS = 1e-4


def points(obj):
    rotation = (obj.rotation_quaternion.copy()
                if obj.rotation_mode == "QUATERNION"
                else obj.rotation_euler.to_quaternion())
    matrix = Matrix.LocRotScale(obj.location, rotation, obj.scale)
    return [matrix @ vertex.co for vertex in obj.data.vertices]


def bounds(meshes):
    vertices = [point for obj in meshes for point in points(obj)]
    return (min(p.x for p in vertices), max(p.x for p in vertices),
            min(p.y for p in vertices), max(p.y for p in vertices),
            min(p.z for p in vertices), max(p.z for p in vertices))


def main():
    failures = []
    signatures = set()
    for variant, slot in enumerate(TOWER_PLAN):
        col = bpy.data.collections.new("METROCHECK_%02d" % variant)
        nb.build_metro_tower(col, variant)
        meshes = [obj for obj in col.objects if obj.type == "MESH"]
        if not meshes:
            failures.append("tower %d built no meshes" % (variant + 1))
            continue
        box = bounds(meshes)
        signatures.add((round(box[1]-box[0], 2), round(box[3]-box[2], 2),
                        round(box[5], 2), variant % 5, variant % 4))
        print("  tower %02d  parts %3d  x %6.2f..%6.2f  y %6.2f..%6.2f  "
              "z %5.2f..%6.2f" % ((variant + 1, len(meshes)) + box))
        if box[0] < -19.01 or box[1] > 19.01:
            failures.append("tower %d exceeds its 38m parcel width" % (variant + 1))
        if box[2] < -20.01 or box[3] > 20.01:
            failures.append("tower %d exceeds its 40m parcel depth" % (variant + 1))
        if box[4] < -EPS:
            failures.append("tower %d has geometry below its ground plane" %
                            (variant + 1))
        expected = float(slot["height"]) + 6.54
        if not expected <= box[5] <= expected + 13.0:
            failures.append("tower %d roof height %.2f is inconsistent with "
                            "its %.2f authored shaft" %
                            (variant + 1, box[5], slot["height"]))
        if any(min(obj.scale) <= EPS for obj in meshes):
            failures.append("tower %d contains a near-zero scale" % (variant + 1))
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(col)

    if len(signatures) != TOWER_COUNT:
        failures.append("the twenty addresses do not have twenty distinct "
                        "massing signatures")

    # Each parcel envelope must clear all four road edges around its block.
    for slot in TOWER_PLAN:
        col, row = int(slot["column"]), int(slot["row"])
        road_gaps = (
            slot["x"]-19.0-NORTH_SOUTH_X[col]-LOCAL_ROAD_WIDTH/2,
            NORTH_SOUTH_X[col+1]-slot["x"]-19.0-LOCAL_ROAD_WIDTH/2,
            slot["y"]-20.0-EAST_WEST_Y[row]-
            (BOULEVARD_WIDTH if EAST_WEST_Y[row] in (588.0, 654.0)
             else LOCAL_ROAD_WIDTH)/2,
            EAST_WEST_Y[row+1]-slot["y"]-20.0-
            (BOULEVARD_WIDTH if EAST_WEST_Y[row+1] in (588.0, 654.0)
             else LOCAL_ROAD_WIDTH)/2,
        )
        if min(road_gaps) < 2.0-EPS:
            failures.append("tower %d keeps only %.2fm from a carriageway" %
                            (slot["metro_id"], min(road_gaps)))

    if failures:
        print()
        for failure in failures:
            print("FAIL:", failure)
        raise SystemExit(1)
    print()
    print("check_metropolitan_assets.py: OK -- 20 distinct tower assets stay "
          "inside their parcels and clear every road")


if __name__ == "__main__":
    main()
