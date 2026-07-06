"""One-time setup: run by Claude via blender --background --python this_file.
Creates neighborhood.blend with the generator script loaded, does a test
build (day 1, 5 houses), renders a preview PNG, then resets the state so
the user starts fresh at day 0."""
import bpy, os, traceback

PROJ = os.path.expanduser("~/Documents/neighborhood")
SCRIPT = os.path.join(PROJ, "neighborhood_blender.py")

# clean default scene (cube, light, camera)
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

# save blend FIRST so the generator writes world_state.json next to it
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJ, "neighborhood.blend"))

# load generator into the Scripting editor
txt = bpy.data.texts.load(SCRIPT)
txt.name = "neighborhood_blender.py"

# test run: executes the generator (default config = day 1, 5 houses)
try:
    exec(compile(txt.as_string(), "neighborhood_blender.py", "exec"), {})
    print("SETUP: generator ran OK")
except Exception:
    traceback.print_exc()
    print("SETUP: GENERATOR FAILED")
    raise SystemExit(1)

# render one preview frame near the end of the animation
sc = bpy.context.scene
sc.frame_set(max(sc.frame_start, sc.frame_end - 40))
try:
    sc.render.image_settings.media_type = "IMAGE"
except Exception:
    pass
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(PROJ, "test_preview.png")
try:
    bpy.ops.render.render(write_still=True)
    print("SETUP: preview rendered")
except Exception:
    traceback.print_exc()
    print("SETUP: EEVEE preview failed, trying WORKBENCH")
    try:
        sc.render.engine = "BLENDER_WORKBENCH"
        bpy.ops.render.render(write_still=True)
        print("SETUP: workbench preview rendered")
    except Exception:
        traceback.print_exc()

# reset so the user starts fresh at day 0 (test city stays visible in blend)
sp = os.path.join(PROJ, "world_state.json")
if os.path.exists(sp):
    os.remove(sp)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(PROJ, "neighborhood.blend"))
print("SETUP: DONE")
