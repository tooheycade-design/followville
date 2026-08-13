"""Render the nuclear station IN the world, lit by the real TOD preset.

Run against an isolated state that already contains a `nuclearplant` record.
Rebuilds in replay mode, so it never advances that state, never writes
world_state.json, never touches either authoritative Blend and never exports.

    set NEIGHBORHOOD_STATE_DIR=<isolated dir>
    blender --background <isolated blend> --python scripts/render_nuclear_in_world.py

NUCLEAR_WORLD_OUT chooses the output directory, NUCLEAR_WORLD_TOD the preset.
"""

import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"
import neighborhood_blender as nb  # noqa: E402
os.environ.pop("FOLLOWVILLE_IMPORT_ONLY", None)

OUT = Path(os.environ.get("NUCLEAR_WORLD_OUT",
                          str(REPO / "renders" / "nuclear_in_world")))
OUT.mkdir(parents=True, exist_ok=True)
TOD = os.environ.get("NUCLEAR_WORLD_TOD", "sunset")

nb.main({"replay": True, "time": TOD})

scene = bpy.context.scene
scene.frame_set(scene.frame_end)
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
try:
    scene.render.image_settings.media_type = "IMAGE"
except (AttributeError, TypeError):
    pass
scene.render.image_settings.file_format = "PNG"

PX, PY = 446.0, 556.0


def render_view(name, location, target, lens, clip_start=1.0):
    data = bpy.data.cameras.new("np_world_%s" % name)
    data.lens = lens
    data.clip_start = clip_start
    data.clip_end = 20000.0
    camera = bpy.data.objects.new("np_world_%s" % name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (
        Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.filepath = str(OUT / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    print("NUCLEAR_WORLD_SCREENSHOT " + scene.render.filepath)


# 1. The station in its landscape: river to the west, Eastbank Village and the
#    log houses south of it. This is the shot that has to prove the siting.
render_view("01_in_world", (PX + 300.0, PY - 330.0, 190.0),
            (PX - 30.0, PY + 10.0, 12.0), 40, clip_start=10.0)
# 2. Coming up Point Road from the town side.
render_view("02_approach", (472.0, 452.0, 8.0), (PX + 6.0, PY - 6.0, 16.0), 36)
# 3. The junction: Point Road carries on north, the dirt trail turns off to
#    the gate. This is the shot that shows it is not a private driveway.
render_view("03_junction", (492.0, 478.0, 11.0), (462.0, 512.0, 3.0), 34)
# 4. From across the river, the way the town sees it.
render_view("04_from_river", (300.0, 520.0, 40.0), (PX - 20.0, PY + 6.0, 18.0),
            42, clip_start=10.0)
print("NUCLEAR_WORLD_DONE")
