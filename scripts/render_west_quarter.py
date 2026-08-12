"""Render the maintained West Quarter review views.

Run against an isolated state whose growth has already consumed chapter four,
by setting NEIGHBORHOOD_STATE_DIR.  The script rebuilds the scene in replay
mode, so it never advances that state, never writes world_state.json, never
touches either authoritative Blend and never exports a GLB.

    set NEIGHBORHOOD_STATE_DIR=<isolated dir>
    blender --background <isolated blend> --python scripts/render_west_quarter.py

Set WEST_QUARTER_OUT to send the PNGs somewhere other than renders/, and
WEST_QUARTER_ONLY to a comma-separated list of view names to render a subset.

These are landscape rather than the 9:16 the Story and daily-growth cameras
use, because they exist to judge PLANNING -- whether the quarter reads as a
continuation of the built grid, whether the density gradient shows, whether
the reserved parcels sit where a planner would put them -- and a tall crop
throws away exactly the width that question depends on.
"""

import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
# Importing the generator runs a growth unless this is set -- the module ends
# in `if bpy.app.background: main()`, which is the whole launch mechanism.
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"
import neighborhood_blender as nb  # noqa: E402
os.environ.pop("FOLLOWVILLE_IMPORT_ONLY", None)


OUT = Path(os.environ.get("WEST_QUARTER_OUT",
                          str(REPO / "renders" / "west_quarter")))
OUT.mkdir(parents=True, exist_ok=True)
ONLY = {name.strip() for name in os.environ.get(
    "WEST_QUARTER_ONLY", "").split(",") if name.strip()}

# Replay reconstructs the complete city and performs no state, Blend or web
# export write.
nb.main({"replay": True, "time": "day"})

scene = bpy.context.scene
# Jump to the scene's OWN last frame, never a hard-coded one. Houses rise on a
# staggered animation, so the frame the batch finishes on scales with how many
# buildings the replay reconstructed. A fixed 1300 was tried and it caught the
# last district still at zero scale: Harrow Green and Bramble Park stood up but
# Ember Ridge, which grows last, rendered as flat pads on empty streets.
scene.frame_set(scene.frame_end)
print("WEST_QUARTER_FRAME %d" % scene.frame_end)
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
try:
    scene.render.image_settings.media_type = "IMAGE"
except (AttributeError, TypeError):
    pass
scene.render.image_settings.file_format = "PNG"


def render_view(name, location, target, lens, clip_start=1.0):
    if ONLY and name not in ONLY:
        return
    data = bpy.data.cameras.new("WestQuarter_%s" % name)
    data.lens = lens
    # Aerial views use a 10m near clip so thin roads and ponds do not flash
    # from lost depth precision; Blender's 0.1m default is only safe on the
    # ground-level shots.
    data.clip_start = clip_start
    data.clip_end = 20000.0
    camera = bpy.data.objects.new("WestQuarter_%s" % name, data)
    scene.collection.objects.link(camera)
    camera.location = location
    camera.rotation_euler = (
        Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.filepath = str(OUT / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    print("WEST_QUARTER_SCREENSHOT " + scene.render.filepath)


# 1. The whole metropolitan area. The question this answers is whether the new
#    quarter reads as part of one city or as a separate settlement.
render_view("01_whole_city", (760.0, -560.0, 900.0), (-190.0, 330.0, 0.0),
            32, clip_start=10.0)

# 2. The seam, from over the built grid looking west. Southline Avenue,
#    Millrace Street and Kettle Row should run straight out of the built
#    blocks into the new ones with no join visible.
render_view("02_the_seam", (240.0, 190.0, 300.0), (-420.0, 520.0, 0.0),
            40, clip_start=10.0)

# 3. The quarter from above, square on -- blocks, parks, ponds and the empty
#    reserved parcels.
render_view("03_quarter_overhead", (-430.0, 240.0, 620.0),
            (-440.0, 615.0, 0.0), 45, clip_start=10.0)

# 4. The density gradient, looking east down Kettle Row West from beyond the
#    western edge: tight lots at the far end against the city, generous ones
#    in the foreground.
render_view("04_density_gradient", (-800.0, 470.0, 120.0),
            (-260.0, 500.0, 0.0), 42, clip_start=10.0)

# 5. Ground level ON Southline Avenue West, looking east back toward the city.
#    The eye height is the 5.00m datum plus 1.8m, and the camera sits on the
#    carriageway rather than beside it: a first attempt stood it 12m south of
#    the centreline, which is somebody's back garden, and the frame was filled
#    by the back wall of one house.
render_view("05_street_level", (-524.0, 415.5, 6.8), (-215.0, 415.5, 6.1), 40)

# 6. The north arm running up the outside of Crown Quarter, so the suburb and
#    the skyline are in one frame.
render_view("06_arm_and_skyline", (-620.0, 300.0, 210.0),
            (-120.0, 700.0, 20.0), 38, clip_start=10.0)

print("WEST_QUARTER_DONE")
