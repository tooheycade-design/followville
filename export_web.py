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
    bpy.ops.object.select_all(action="DESELECT")
    for obj in col.objects:
        obj.hide_select = False
        obj.hide_viewport = False
        obj.scale = (1.0, 1.0, 1.0)  # belt-and-braces against any residual mid-animation scale
        obj.select_set(True)
    bpy.context.view_layer.objects.active = col.objects[0] if col.objects else None

    # Bake every collection-instance empty into real, exportable mesh data.
    # (glTF export of raw collection-instancer empties is unreliable across
    # Blender versions, so we realize them first — this only touches the
    # in-memory scene of this throwaway process, never the saved .blend.)
    bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)

    # Re-select the whole WORLD collection (now full of real meshes) for export.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in col.objects:
        obj.select_set(True)

    base = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~")
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
