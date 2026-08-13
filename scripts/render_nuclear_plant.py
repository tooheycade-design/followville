"""Render review views of the nuclear station asset on its own.

Builds only the asset, on a plain ground plane, so the model can be judged
before it is placed in the world.  Writes nothing to world_state.json, neither
Blend, nor any GLB.

    blender --background --factory-startup --python scripts/render_nuclear_plant.py

Set NUCLEAR_OUT to choose where the PNGs land.
"""

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
# Importing the generator runs a growth unless this is set.
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"
import neighborhood_blender as nb  # noqa: E402
os.environ.pop("FOLLOWVILLE_IMPORT_ONLY", None)

OUT = Path(os.environ.get("NUCLEAR_OUT", str(REPO / "renders" / "nuclear_plant")))
OUT.mkdir(parents=True, exist_ok=True)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

scene = bpy.context.scene
col = bpy.data.collections.new("PLANT_REVIEW")
scene.collection.children.link(col)
nb.build_nuclear_plant(col, 8400)

ground = bpy.data.meshes.new("ground")
ground.from_pydata([(-400, -400, 0), (400, -400, 0), (400, 400, 0),
                    (-400, 400, 0)], [], [(0, 1, 2, 3)])
ground.update()
ground_obj = bpy.data.objects.new("ground", ground)
ground_obj.data.materials.append(
    nb.mat("NB_np_review_ground", (.55, .63, .45), .97))
col.objects.link(ground_obj)

# Lit from the generator's own "sunset" row in TODS, so this review matches
# what the video will actually look like rather than an invented key. Taken
# from the preset rather than imported, because apply_mood() expects a built
# town scene and this script deliberately has nothing but the asset. Any drift
# between these numbers and TODS["sunset"] is a bug in this script.
sunset = nb.TODS["sunset"]
sun_data = bpy.data.lights.new("sun", type="SUN")
sun_data.energy = sunset["sun_e"] * 2.3
sun_data.angle = math.radians(sunset["sun_angle"])
sun_data.color = sunset["sun_c"]
sun = bpy.data.objects.new("sun", sun_data)
sun.rotation_euler = tuple(math.radians(v) for v in sunset["sun_rot"])
scene.collection.objects.link(sun)
world = bpy.data.worlds.new("review")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (
    sunset["sky"][0], sunset["sky"][1], sunset["sky"][2], 1.0)
world.node_tree.nodes["Background"].inputs[1].default_value = sunset["sky_s"]
scene.world = world

# Blender renamed EEVEE between versions; take whichever this build offers.
for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = sunset["exposure"]
except TypeError:
    pass


def render_view(name, location, target, lens):
    data = bpy.data.cameras.new("cam_%s" % name)
    data.lens = lens
    data.clip_start = 0.5
    data.clip_end = 5000.0
    camera = bpy.data.objects.new("cam_%s" % name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (
        Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.filepath = str(OUT / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    print("NUCLEAR_SCREENSHOT " + scene.render.filepath)


render_view("01_hero", (86.0, -104.0, 46.0), (-4.0, 6.0, 15.0), 40)
render_view("02_gate", (6.0, -84.0, 12.0), (-6.0, 0.0, 12.0), 45)
render_view("03_tower", (-64.0, -46.0, 22.0), (-19.0, 13.0, 22.0), 48)
render_view("04_overhead", (10.0, -58.0, 120.0), (-2.0, 6.0, 6.0), 40)
render_view("05_river_side", (-116.0, 22.0, 30.0), (-10.0, 8.0, 16.0), 42)
print("NUCLEAR_DONE")
