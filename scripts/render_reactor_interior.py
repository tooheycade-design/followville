"""Render review views of the TEMPORARY reactor hall interior set.

The set is a stage for one sequence of the nuclear station video. It is never
placed by growth, never exported, and nothing in the town depends on it.

    blender --background --factory-startup --python scripts/render_reactor_interior.py

Set REACTOR_OUT to choose where the PNGs land.
"""

import math
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

OUT = Path(os.environ.get("REACTOR_OUT", str(REPO / "renders" / "reactor_hall")))
OUT.mkdir(parents=True, exist_ok=True)

for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)

scene = bpy.context.scene
col = bpy.data.collections.new("REACTOR_REVIEW")
scene.collection.children.link(col)
nb.build_reactor_hall_interior(col, 8500)

# The room is meant to be lit by what is inside it -- the pool and the screens
# are emissive -- so the only added light is a weak fill standing in for the
# hall's own high bays. A key light here would flatten exactly the thing the
# set is built to show.
fill_data = bpy.data.lights.new("fill", type="AREA")
fill_data.energy = 900.0
fill_data.size = 22.0
fill_data.color = (.80, .86, .96)
fill = bpy.data.objects.new("fill", fill_data)
fill.location = (0.0, 0.0, 16.0)
fill.rotation_euler = (0.0, 0.0, 0.0)
scene.collection.objects.link(fill)

world = bpy.data.worlds.new("interior")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs[0].default_value = (.04, .05, .07, 1)
world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
scene.world = world

for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.image_settings.file_format = "PNG"
try:
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = .10
except TypeError:
    pass
if hasattr(scene, "eevee"):
    for attr, value in (("use_bloom", True), ("bloom_intensity", .06),
                        ("use_gtao", True)):
        try:
            setattr(scene.eevee, attr, value)
        except (AttributeError, TypeError):
            pass


def render_view(name, location, target, lens):
    data = bpy.data.cameras.new("cam_%s" % name)
    data.lens = lens
    data.clip_start = 0.10
    data.clip_end = 500.0
    camera = bpy.data.objects.new("cam_%s" % name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (
        Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.filepath = str(OUT / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    print("REACTOR_SCREENSHOT " + scene.render.filepath)


# Wide, from the south-east corner looking back across pool, vessel and
# mezzanine, so one frame carries the whole set.
render_view("01_hall", (19.0, -13.6, 11.0), (-6.0, 1.0, 3.5), 22)
# The pool, low and close, so the green does the lighting.
render_view("02_pool", (17.0, -10.0, 3.4), (10.0, 2.0, 1.0), 34)
# The control mezzanine and its screens.
render_view("03_control", (2.0, -6.0, 8.2), (-14.0, -11.5, 5.6), 32)
# Reactor vessel, looking up.
render_view("04_vessel", (2.0, -7.0, 2.2), (-9.0, 2.0, 8.0), 30)
print("REACTOR_DONE")
