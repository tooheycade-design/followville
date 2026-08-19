"""Is every Day 49 home actually on screen at the frame it stands up?

Run INSIDE the same Blender session as the generator, exactly like export_web.py
does, so the camera it measures is the evaluated rig and not a re-derivation of
the beats:

    blender --background neighborhood.blend ^
        --python neighborhood_blender.py ^
        --python verify_day49_camera.py -- +152 --cam day49northreach --time sunset

with NEIGHBORHOOD_STATE_DIR pointed at a scratch copy of world_state.json, so a
verification run never advances the real city.

This is the check day 47 and day 48 were each held to and it is the one that
matters: a home whose rise happens two degrees outside a 9:16 frame is invisible
in the finished film and there is no way to tell from the source. It reads the
rise frame out of each root's own animation data rather than recomputing it from
DAY49_WAVE_LEAD, so a wave table that disagrees with the wave that was actually
installed is caught rather than confirmed.

Writes nothing. Renders nothing.
"""

import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

MARGIN = 0.012          # ~1.2% of frame; a home dead on the edge is not "on screen"
SAMPLE_HEIGHT = 4.1     # mid-height of an 8.2m suburban house


def obj_fcurves(obj):
    """All fcurves of an object's action.

    Blender 5.x actions are layered/slotted and no longer expose a flat
    .fcurves, so this is the same two-path walk the generator's own
    obj_fcurves() does. Reading the curves is the whole point of this check --
    the rise frames have to come from the animation that was actually
    installed, not from re-running the formula that was supposed to install it.
    """
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
                    cb = strip.channelbag(ad.action_slot)
                except Exception:
                    cb = None
                if cb:
                    fcs.extend(cb.fcurves)
    except Exception:
        pass
    return fcs


def rise_window(obj):
    """(first, last) frame of this object's scale rise, or None if it never rises."""
    frames = []
    for fc in obj_fcurves(obj):
        if fc.data_path == "scale":
            frames.extend(kp.co[0] for kp in fc.keyframe_points)
    if not frames:
        return None
    return int(round(min(frames))), int(round(max(frames)))


def main():
    scene = bpy.context.scene
    cam = scene.camera
    if cam is None or "Day49NorthReach" not in cam.name:
        raise SystemExit("verify_day49_camera: scene camera is %r, not the Day 49 rig. "
                         "Pass --cam day49northreach." % (cam.name if cam else None))

    homes = [o for o in bpy.data.objects
             if o.name.startswith("house_d") and rise_window(o)]
    print("\n" + "=" * 78)
    print("DAY 49 CAMERA CHECK  --  %s, frames %d-%d, %dx%d"
          % (cam.name, scene.frame_start, scene.frame_end,
             scene.render.resolution_x, scene.render.resolution_y))
    print("=" * 78)
    print("rising homes found: %d" % len(homes))
    if len(homes) != 152:
        print("!! expected 152")

    # The camera path itself, so the beats can be read back as evaluated numbers.
    print("\ncamera path (evaluated):")
    print("  %-6s %-28s %-28s %s" % ("frame", "position", "aim-at (matrix -Z)", "lens"))
    for f in (1, 80, 200, 260, 400, 545, 600, 650, 720):
        scene.frame_set(f)
        loc = cam.matrix_world.translation
        fwd = cam.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
        print("  %-6d (%8.1f,%8.1f,%7.1f)   (%6.2f,%6.2f,%6.2f)        %.1fmm"
              % (f, loc.x, loc.y, loc.z, fwd.x, fwd.y, fwd.z, cam.data.lens))

    failures, edge, ok = [], [], 0
    per_frame = {}
    for obj in homes:
        first, last = rise_window(obj)
        per_frame.setdefault(first, []).append(obj)

    # Walk frames in order so frame_set is monotonic and cheap.
    results = []
    for frame in sorted(per_frame):
        scene.frame_set(frame)
        for obj in per_frame[frame]:
            p = obj.matrix_world.translation.copy()
            p.z += SAMPLE_HEIGHT
            uv = world_to_camera_view(scene, cam, p)
            results.append((obj, frame, uv))

    for obj, frame, uv in results:
        inside = (MARGIN <= uv.x <= 1.0 - MARGIN
                  and MARGIN <= uv.y <= 1.0 - MARGIN
                  and uv.z > 0.0)
        loc = obj.matrix_world.translation
        row = (obj.name, loc.x, loc.y, frame, uv.x, uv.y, uv.z)
        if not inside:
            failures.append(row)
        else:
            ok += 1
            if not (0.06 <= uv.x <= 0.94):
                edge.append(row)

    print("\nwave span: frames %d - %d (%.1fs - %.1fs)"
          % (min(per_frame), max(per_frame),
             min(per_frame) / 30.0, max(per_frame) / 30.0))

    print("\nrise frames by ribbon:")
    ribbons = {}
    for obj, frame, uv in results:
        cx = round((obj.matrix_world.translation.x + 50.0) / 70.0) * 70.0 - 50.0
        ribbons.setdefault(cx, []).append(frame)
    for cx in sorted(ribbons):
        fr = ribbons[cx]
        print("  x=%-7.1f  %3d homes   frames %3d - %3d"
              % (cx, len(fr), min(fr), max(fr)))

    if edge:
        print("\nON SCREEN but within 6%% of a vertical edge (%d):" % len(edge))
        for name, x, y, f, u, v, d in sorted(edge, key=lambda r: r[3])[:20]:
            print("  f%-4d (%8.1f,%8.1f)  u=%.3f v=%.3f  %.0fm out"
                  % (f, x, y, u, v, d))

    print("\n" + "-" * 78)
    if failures:
        print("OFF SCREEN AT THEIR OWN RISE FRAME: %d of %d" % (len(failures), len(results)))
        for name, x, y, f, u, v, d in sorted(failures, key=lambda r: r[3]):
            why = []
            if not (MARGIN <= u <= 1 - MARGIN):
                why.append("u=%.3f" % u)
            if not (MARGIN <= v <= 1 - MARGIN):
                why.append("v=%.3f" % v)
            if d <= 0:
                why.append("behind camera")
            print("  f%-4d (%8.1f,%8.1f)  %s" % (f, x, y, ", ".join(why)))
        print("verify_day49_camera: FAILED -- %d homes rise off screen" % len(failures))
        sys.stdout.flush()
        raise SystemExit(1)

    print("verify_day49_camera: OK -- %d/%d homes are on screen at their own "
          "rise frame" % (ok, len(results)))
    sys.stdout.flush()


main()
