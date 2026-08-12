"""State-free Blender smoke check for Followville's video lighting presets.

Usage:
  blender --background --factory-startup --python-exit-code 1 \
    --python check_video_lighting.py
"""

import os
import sys
from pathlib import Path

import bpy


os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import neighborhood_blender as nb  # noqa: E402


scene = bpy.context.scene
world_col = bpy.data.collections.new("LIGHTING_CHECK")
scene.collection.children.link(world_col)

# Widely spaced stand-ins exercise the same name/location selection contract as
# collection-instanced streetlights without building or advancing the city.
for index in range(60):
    fixture = bpy.data.objects.new("suburban_light_check_%02d" % index, None)
    fixture.location = ((index % 10) * 70.0, (index // 10) * 70.0, 5.0)
    world_col.objects.link(fixture)

for preset in ("day", "sunset", "dusk", "night", "storm"):
    nb._configure_video_sky(preset)
    nodes = scene.world.node_tree.nodes
    if any(node.bl_idname == "ShaderNodeVolumeScatter" for node in nodes):
        raise RuntimeError("%s preset created forbidden world-volume fog" % preset)
    wants_sky = nb.TODS[preset]["sky_mode"] == "nishita"
    has_sky = any(node.bl_idname == "ShaderNodeTexSky" for node in nodes)
    if has_sky != wants_sky:
        raise RuntimeError("%s procedural-sky mode disagrees with its preset" % preset)
    practicals = nb._build_video_practicals(world_col, preset)
    expected = int(nb.TODS[preset]["practical_count"])
    if len(practicals) != expected:
        raise RuntimeError("%s built %d practicals, expected %d" %
                           (preset, len(practicals), expected))
    for light in practicals:
        if not light.get("nb_render_only"):
            raise RuntimeError("video practical is not excluded from web export")
        bpy.data.objects.remove(light, do_unlink=True)

nb.std_mats()
for preset in ("day", "sunset", "night"):
    nb.apply_mood(preset, "summer")
    bsdf = bpy.data.materials["NB_bulb"].node_tree.nodes["Principled BSDF"]
    strength = bsdf.inputs.get("Emission Strength")
    if strength and abs(strength.default_value - nb.TODS[preset]["lamp"]) > 1e-6:
        raise RuntimeError("%s bulb emission did not apply" % preset)

print("check_video_lighting.py: OK -- day/sunset/night skies, practicals, "
      "emission and no-fog contract verified")
