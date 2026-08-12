"""Render the four maintained Crown Quarter street-detail review views.

Run against an isolated all-tower state by setting NEIGHBORHOOD_STATE_DIR.
The script rebuilds the scene in replay mode, so it never advances that state.
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


OUT = REPO / "renders" / "crown_quarter_street_life"
OUT.mkdir(parents=True, exist_ok=True)
ONLY = {name.strip() for name in os.environ.get(
    "CROWN_DETAIL_ONLY", "").split(",") if name.strip()}

# Replay reconstructs the complete city but performs no state, Blend or web
# export write. The supplied isolated state contains all twenty towers.
nb.main({"replay": True, "cam": "metroreveal", "time": "day"})

scene = bpy.context.scene
scene.frame_end = 1300
scene.frame_set(1300)
scene.render.resolution_x = 960
scene.render.resolution_y = 1280
scene.render.resolution_percentage = 100
try:
    scene.render.image_settings.media_type = "IMAGE"
except (AttributeError, TypeError):
    pass
scene.render.image_settings.file_format = "PNG"


def render_view(name, location, target, lens):
    if ONLY and name not in ONLY:
        return
    data = bpy.data.cameras.new("CrownDetail_%s" % name)
    data.lens = lens
    data.clip_start = 1.0
    data.clip_end = 10000.0
    camera = bpy.data.objects.new("CrownDetail_%s" % name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (
        Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.filepath = str(OUT / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    print("CROWN_DETAIL_SCREENSHOT " + scene.render.filepath)


render_view("01_cafe_and_entry", (-125.0, 599.0, 8.5),
            (-103.0, 619.0, 3.2), 38)
render_view("02_transit_boulevard", (-48.0, 566.0, 9.5),
            (-12.0, 589.0, 3.3), 37)
render_view("03_service_and_bikes", (15.0, 664.0, 9.0),
            (7.0, 674.0, 6.25), 48)
render_view("04_active_corner", (-116.0, 594.0, 8.8),
            (-107.0, 602.0, 6.55), 50)
render_view("05_service_lane", (15.0, 683.0, 9.4),
            (7.0, 699.0, 6.35), 45)
