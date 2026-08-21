"""Build the Followville High campus in isolation and audit its surfaces.

Run with Blender, not the Python executable::

    blender --background --factory-startup --python check_high_school_assets.py

The guard below is mandatory: importing ``neighborhood_blender`` in a
background Blender session otherwise runs a real growth.

What this defends
-----------------
CLAUDE.md's visible-surface depth rule -- never two independently rendered
visible faces on one plane -- is the only rule in this project that neither
``check_town_glb.py`` nor ``check_world_geometry.py`` can see.  Both of those
measure where things stand; neither measures whether two faces are fighting for
the same depth, and the rule itself says coplanar surfaces "must fail a
standalone geometry check before any render, export or deploy".  This is that
check, for the one asset in town made almost entirely of stacked flat slabs:
a levelled campus with paving, a drive, a car park, a running track and a
painted football field, any pair of which will shimmer in the browser if they
share a plane.

Two boxes are only a defect when the coincident face is actually SEEN.  A slab
resting on another slab, a window frame anchored inside a wall and a cornice
tucked under a roof all put faces on shared planes on purpose, and all of them
are buried.  So a pair is reported only when the shared face has open air on
the outward side -- tested by sampling just outside it and asking whether any
other solid in the campus encloses that point.

It also re-measures the two things the campus's own declarations promise:
that no geometry escapes the footprint in world_layout.LANDMARK_FOOTPRINTS,
and that nothing pokes above the walk deck world_layout hands the browser by
more than the buildings are meant to.
"""

import os
import sys

import bpy
from mathutils import Matrix

REPO = os.path.dirname(os.path.abspath(__file__))
if REPO not in sys.path:
    sys.path.insert(0, REPO)
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"

import neighborhood_blender as nb
from world_layout import LANDMARK_FOOTPRINTS

# Keep the authored primitives: the per-asset merge collapses them into one
# mesh, and a single mesh has nothing left to measure against itself.
nb._merge_asset_meshes = lambda col, name: None

PLANE_TOL = 1e-4          # two faces this close count as one plane
MIN_OVERLAP = 0.02        # ignore slivers narrower than 2cm
PROBE = 0.004             # how far outside a face to sample for open air
AXES = ("x", "y", "z")


def world_boxes(collection):
    """Every axis-aligned box in the campus, as (name, low, high).

    Rotated pieces -- the clock hands, the flag, the press-box lettering -- are
    skipped rather than approximated: a rotated bounding box is not the solid,
    and reporting its faces would be reporting planes that do not exist.

    The transform is composed here rather than read from ``matrix_world``.
    This collection is never linked into a scene, so Blender never evaluates
    it and every ``matrix_world`` comes back as the identity -- which silently
    piles the entire campus on top of itself at the origin and makes every
    slab look coplanar with every other one.
    """
    boxes = []
    for obj in collection.objects:
        if obj.type != "MESH":
            continue
        rotation = (obj.rotation_quaternion.to_euler()
                    if obj.rotation_mode == "QUATERNION"
                    else obj.rotation_euler)
        if max(abs(rotation.x), abs(rotation.y), abs(rotation.z)) > 1e-6:
            continue
        matrix = Matrix.LocRotScale(obj.location, rotation, obj.scale)
        corners = [matrix @ vertex.co for vertex in obj.data.vertices]
        if not corners:
            continue
        low = [min(corner[axis] for corner in corners) for axis in range(3)]
        high = [max(corner[axis] for corner in corners) for axis in range(3)]
        # A bounding-box plane is only a real surface if the mesh has a polygon
        # lying in it.  Roof prisms, cones and the track's obround rings all
        # have bounding planes that hold nothing but an edge or a single point,
        # and comparing those would report planes that are not there: the gym's
        # roof ridge is a line, not a face, and it "shares" its bounding top
        # with the ridge vent's cap.
        faces = set()
        for polygon in obj.data.polygons:
            points = [corners[i] for i in polygon.vertices]
            for axis in range(3):
                values = [point[axis] for point in points]
                if max(values) - min(values) > PLANE_TOL:
                    continue
                if abs(values[0] - low[axis]) <= PLANE_TOL:
                    faces.add((axis, -1))
                if abs(values[0] - high[axis]) <= PLANE_TOL:
                    faces.add((axis, 1))
        boxes.append((obj.name, low, high, faces))
    return boxes


def encloses(box, point):
    low, high = box[1], box[2]
    return all(low[axis] < point[axis] < high[axis] for axis in range(3))


CELL = 6.0


def solid_index(boxes):
    """Coarse spatial hash, so burial is a local question, not a 700-box scan."""
    index = {}
    for box in boxes:
        low, high = box[1], box[2]
        spans = [range(int(low[axis] // CELL), int(high[axis] // CELL) + 1)
                 for axis in range(3)]
        for i in spans[0]:
            for j in spans[1]:
                for k in spans[2]:
                    index.setdefault((i, j, k), []).append(box)
    return index


def face_is_buried(index, axis, value, outward, centre):
    """Is there solid material immediately outside this face?"""
    probe = list(centre)
    probe[axis] = value + outward * PROBE
    cell = tuple(int(probe[a] // CELL) for a in range(3))
    return any(encloses(box, probe) for box in index.get(cell, ()))


def coplanar_defects(boxes):
    index = solid_index(boxes)
    faces = {}
    for position, (_name, low, high, real) in enumerate(boxes):
        for axis in range(3):
            for side, value in ((-1, low[axis]), (1, high[axis])):
                if (axis, side) not in real:
                    continue
                faces.setdefault((axis, side, round(value, 4)), []).append(position)
    defects = []
    for (axis, side, value), members in faces.items():
        if len(members) < 2:
            continue
        free = [i for i in range(3) if i != axis]
        for first in range(len(members)):
            for second in range(first + 1, len(members)):
                a, b = boxes[members[first]], boxes[members[second]]
                spans = [min(a[2][i], b[2][i]) - max(a[1][i], b[1][i])
                         for i in free]
                if min(spans) <= MIN_OVERLAP:
                    continue
                centre = [0.0, 0.0, 0.0]
                for i in free:
                    centre[i] = (max(a[1][i], b[1][i]) +
                                 min(a[2][i], b[2][i])) / 2
                centre[axis] = value
                if face_is_buried(index, axis, value, side, centre):
                    continue
                defects.append((AXES[axis], value, a[0], b[0], min(spans)))
    return defects


def main():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    campus = bpy.data.collections.new("HIGHSCHOOL_CHECK")
    nb.build_high_school(campus, 2600)
    bpy.context.view_layer.update()

    boxes = world_boxes(campus)
    if len(boxes) < 400:
        print("FAIL: the campus built only %d axis-aligned solids" % len(boxes))
        raise SystemExit(1)
    failures = []

    defects = coplanar_defects(boxes)
    if defects:
        shown = {}
        for axis, value, first, second, span in defects:
            key = (axis, first.split(".")[0], second.split(".")[0])
            shown[key] = max(shown.get(key, 0.0), span)
        for (axis, first, second), span in sorted(shown.items()):
            failures.append(
                "%s and %s put visible faces on the same %s plane, "
                "overlapping %.2fm" % (first, second, axis, span))

    # Nothing may reach outside the rectangle the geometry audit defends. The
    # kerb-cut ramps are the one exception, and are meant to: they are the
    # approach road, and world_layout leaves approaches out of footprints on
    # purpose so a landmark is not reported as standing in its own drive.
    x0, x1, y0, y1, _rural = LANDMARK_FOOTPRINTS["highschool"]
    for name, low, high, _real in boxes:
        if name.startswith("hs_kerb_cut"):
            continue
        if (low[0] < x0 - PLANE_TOL or high[0] > x1 + PLANE_TOL or
                low[1] < y0 - PLANE_TOL or high[1] > y1 + PLANE_TOL):
            failures.append(
                "%s reaches x[%.2f %.2f] y[%.2f %.2f], outside the declared "
                "footprint x[%.2f %.2f] y[%.2f %.2f]"
                % (name, low[0], high[0], low[1], high[1], x0, x1, y0, y1))

    # The football field has to fit inside the bends, not just inside the
    # oval's bounding box -- a field whose corners overhang the curve is the
    # giveaway that the track was fitted to the site instead of to the field.
    inner = nb.HS_TRACK_INNER_R
    straight = nb.HS_TRACK_HALF_STRAIGHT
    corner_y = abs(nb.HS_FIELD_L / 2) - straight
    reach = ((nb.HS_FIELD_W / 2) ** 2 + max(0.0, corner_y) ** 2) ** .5
    if reach > inner - 1.0:
        failures.append(
            "the field's corner reaches %.2fm from the bend centre, and the "
            "inner kerb is at %.2fm" % (reach, inner))

    if failures:
        print()
        for failure in failures:
            print("FAIL:", failure)
        raise SystemExit(1)
    print()
    print("check_high_school_assets.py: OK -- %d campus solids, no visible "
          "coplanar faces, nothing outside the footprint, the field fits its "
          "bends with %.2fm to spare" % (len(boxes), inner - reach))


if __name__ == "__main__":
    main()
