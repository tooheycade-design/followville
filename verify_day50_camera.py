"""Verify Day 50's installed rise animation against its evaluated camera.

Run in the same Blender session as ``neighborhood_blender.py`` against a
scratch copy of Day 49 state. This reads each root's actual scale keyframes;
it does not re-run the intended wave formula.
"""

import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

MARGIN = 0.012
SAMPLE_HEIGHT = 4.1


def obj_fcurves(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        fcs = list(act.fcurves)
        if fcs:
            return fcs
    except AttributeError:
        pass
    fcs = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                try:
                    bag = strip.channelbag(ad.action_slot)
                except Exception:
                    bag = None
                if bag:
                    fcs.extend(bag.fcurves)
    except Exception:
        pass
    return fcs


def rise_window(obj):
    frames = []
    for curve in obj_fcurves(obj):
        if curve.data_path == "scale":
            frames.extend(point.co[0] for point in curve.keyframe_points)
    if not frames:
        return None
    return int(round(min(frames))), int(round(max(frames)))


def main():
    scene = bpy.context.scene
    cam = scene.camera
    if cam is None or "Day50Highway" not in cam.name:
        raise SystemExit(
            "verify_day50_camera: scene camera is %r, not Day50Highway. "
            "Pass --cam day50highway." % (cam.name if cam else None))

    rising = [obj for obj in bpy.data.objects if rise_window(obj)]
    homes = [obj for obj in rising if obj.name.startswith("house_d")]
    print("\n" + "=" * 78)
    print("DAY 50 CAMERA CHECK -- %s, frames %d-%d, %dx%d"
          % (cam.name, scene.frame_start, scene.frame_end,
             scene.render.resolution_x, scene.render.resolution_y))
    print("=" * 78)
    print("rising records: %d (homes: %d)" % (len(rising), len(homes)))
    if len(rising) != 50 or len(homes) != 50:
        raise SystemExit(
            "verify_day50_camera: expected 50 rising records / 50 homes")

    print("\ncamera path (evaluated):")
    for frame in (1, 100, 200, 260, 380, 500, 560, 630, 720):
        scene.frame_set(frame)
        loc = cam.matrix_world.translation
        fwd = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        print("  f%-3d (%8.1f,%8.1f,%7.1f) aim=(%5.2f,%5.2f,%5.2f) %.1fmm"
              % (frame, loc.x, loc.y, loc.z, fwd.x, fwd.y, fwd.z,
                 cam.data.lens))

    per_frame = {}
    for obj in rising:
        first, _last = rise_window(obj)
        per_frame.setdefault(first, []).append(obj)

    results = []
    for frame in sorted(per_frame):
        scene.frame_set(frame)
        for obj in per_frame[frame]:
            point = obj.matrix_world.translation.copy()
            point.z += SAMPLE_HEIGHT
            results.append((obj, frame, world_to_camera_view(scene, cam, point)))

    failures = []
    edge = []
    for obj, frame, uv in results:
        inside = (MARGIN <= uv.x <= 1.0 - MARGIN
                  and MARGIN <= uv.y <= 1.0 - MARGIN and uv.z > 0.0)
        row = (obj.name, obj.location.x, obj.location.y, frame,
               uv.x, uv.y, uv.z)
        if not inside:
            failures.append(row)
        elif not (0.06 <= uv.x <= 0.94):
            edge.append(row)

    print("\nwave span: frames %d-%d (%.1fs-%.1fs)"
          % (min(per_frame), max(per_frame),
             min(per_frame) / 30.0, max(per_frame) / 30.0))
    if edge:
        print("on screen but within 6%% of a vertical edge: %d" % len(edge))
        for name, x, y, frame, u, v, depth in edge[:20]:
            print("  f%-3d %-34s (%7.1f,%7.1f) u=%.3f v=%.3f"
                  % (frame, name, x, y, u, v))

    if failures:
        print("\nOFF SCREEN AT OWN RISE FRAME: %d of %d" %
              (len(failures), len(results)))
        for name, x, y, frame, u, v, depth in failures:
            print("  f%-3d %-34s (%7.1f,%7.1f) u=%.3f v=%.3f depth=%.1f"
                  % (frame, name, x, y, u, v, depth))
        raise SystemExit("verify_day50_camera: FAILED")

    print("verify_day50_camera: OK -- all %d records, including all %d homes, "
          "are on screen at their own rise frame" % (len(results), len(homes)))
    sys.stdout.flush()


main()
