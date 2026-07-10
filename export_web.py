"""
FOLLOWER NEIGHBORHOOD — glTF export for the web viewer
=======================================================
Exports the CURRENT built world (the "WORLD" collection that
neighborhood_blender.py just rebuilt) to town.glb, next to world_state.json,
so index.html can load the exact same geometry Blender just rendered —
no hand-ported JS shapes, no drift.

Run this AFTER neighborhood_blender.py has rebuilt the world in the same
Blender session (same --python invocation, or immediately after in the GUI).
It does NOT save the .blend file, so it's always safe to run — any changes
it makes (realizing instances into real meshes) only exist in this throwaway
Blender process and vanish when it exits.

Command-line usage (bolt this onto the end of your existing grow.sh call):
  blender --background neighborhood.blend \\
      --python neighborhood_blender.py -- +5 --render \\
      --python export_web.py

Or standalone, to just re-export the current .blend's world without regrowing:
  blender --background neighborhood.blend --python export_web.py
"""

import bpy
import os

def export_web_glb():
    col = bpy.data.collections.get("WORLD")
    if col is None:
        print("export_web.py: no WORLD collection found — run neighborhood_blender.py first.")
        return None

    # 2026-07-10: exclude one-off celebration fireworks from the website export.
    # build_fireworks() (neighborhood_blender.py) adds short-lived animated burst
    # particles named "fw"/"fw.001"/... to the WORLD collection for --celebrate
    # videos only -- they're meant to be invisible (scale ~0) except during their
    # few-frame burst window. The scale-reset loop below (needed to fix pancaked
    # houses, see the 2026-07-08 PITFALL note) forces EVERY WORLD object to scale
    # (1,1,1), which also permanently un-shrinks these firework particles at
    # their fully-exploded positions -- without this, they get baked into
    # town.glb and show up on the live website as a frozen cluster of debris
    # floating in the sky forever. Fireworks are a video-only effect; delete
    # them before anything below touches scale or exports.
    fw_objs = [obj for obj in list(col.objects)
               if obj.name == "fw" or obj.name.startswith("fw.")]
    for obj in fw_objs:
        bpy.data.objects.remove(obj, do_unlink=True)
    if fw_objs:
        print("export_web.py: excluded %d firework particle(s) from the website export" % len(fw_objs))

    # Jump to the LAST frame of the daily rise/sink animation before touching
    # anything. New buildings animate up from flattened (scale.z ~0.001) to
    # full height over the clip, and whatever frame the scene happens to be
    # sitting on when this loads gets baked into the export. Without this,
    # the newest houses can export "pancaked" mid-rise. frame_end is already
    # set correctly by setup_render() in the just-saved .blend, so this alone
    # guarantees every object is captured in its fully-grown resting pose.
    scene = bpy.context.scene
    scene.frame_set(scene.frame_end)

    # Select everything in WORLD (this includes the collection-instance empties
    # for every building/tree/car/etc AND the plain road/ground meshes).
    #
    # PITFALL (fixed 2026-07-08, don't reintroduce): frame_set() above is NOT
    # enough by itself for objects that were just animated with animate_rise()
    # THIS SAME run (i.e. today's newest buildings). Those objects still carry
    # a live Action with scale keyframes. duplicates_make_real() below forces a
    # depsgraph re-evaluation, and if any animation data is still attached to
    # an object, that re-evaluation reasserts the F-curve's value and silently
    # overwrites a plain `obj.scale = (1,1,1)` Python assignment right back to
    # whatever frame the curve lands on -- in the day-7 pond+houses incident,
    # every mesh part of the newest batch came out of the export at scale
    # (1, 0.001, 1), the exact frame-1 "not risen yet" value, even though this
    # scale reset AND the frame_end jump above both ran. Older buildings never
    # showed this because in later runs they're placed with no animate_rise()
    # call at all (only THIS run's new_batch gets animated), so they have no
    # Action to reassert anything from. The fix: strip the animation data
    # outright with animation_data_clear() so there is no F-curve left that
    # could ever override the manual reset, regardless of evaluation order.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in col.objects:
        obj.hide_select = False
        obj.hide_viewport = False
        obj.animation_data_clear()   # remove any Action so nothing can reassert scale/visibility
        obj.scale = (1.0, 1.0, 1.0)  # belt-and-braces against any residual mid-animation scale
        obj.select_set(True)
    bpy.context.view_layer.objects.active = col.objects[0] if col.objects else None

    # Bake every collection-instance empty into real, exportable mesh data.
    # (glTF export of raw collection-instancer empties is unreliable across
    # Blender versions, so we realize them first — this only touches the
    # in-memory scene of this throwaway process, never the saved .blend.)
    bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)

    # SANITY CHECK (added 2026-07-08, after the pancaked-houses incident): don't
    # just trust the fixes above -- verify. Any realized object with a
    # near-zero scale on ANY axis is exactly what a pancaked/mid-rise export
    # looks like, and the day-7 pond+houses bug shipped silently for a full day
    # before anyone noticed on the live site. Fail loudly here instead: raise,
    # so Blender exits non-zero, so grow_windows.ps1/grow.sh's existing
    # "non-zero exit = ALL_FAILED" handling catches it automatically, before
    # anything gets deployed.
    THRESH = 0.05
    squashed = [obj.name for obj in col.objects
                if any(abs(v) < THRESH for v in obj.scale)]
    if squashed:
        msg = ("SANITY_CHECK_FAILED: %d object(s) exported with a near-zero "
               "scale (pancaked): %s" % (len(squashed), ", ".join(squashed[:10])))
        print(msg)
        raise RuntimeError(msg)

    # Re-select the whole WORLD collection (now full of real meshes) for export.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in col.objects:
        obj.select_set(True)

    # Same NEIGHBORHOOD_STATE_DIR override as neighborhood_blender.py's
    # state_path() -- if set, town.glb is written straight into the git repo
    # clone alongside world_state.json instead of next to the .blend, so the
    # git commit/push step (see grow_windows.ps1) has both files ready with no
    # separate copy step. Unset = old behavior, unchanged.
    base = (os.environ.get("NEIGHBORHOOD_STATE_DIR")
            or (os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~")))
    out_path = os.path.join(base, "town.glb")

    bpy.ops.export_scene.gltf(
        filepath=out_path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,          # bake modifiers/transforms
        export_yup=True,            # glTF convention: Y-up (matches Three.js directly)
        export_lights=False,
        export_cameras=False,
        export_animations=False,    # web viewer doesn't need the daily rise/sink animation
        export_materials="EXPORT",
    )
    print("export_web.py: wrote", out_path)
    return out_path

if __name__ == "__main__":
    export_web_glb()
