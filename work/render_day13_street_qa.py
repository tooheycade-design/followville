import bpy
import os

scene = bpy.context.scene
scene.render.resolution_percentage = 50
try:
    scene.render.image_settings.media_type = "IMAGE"
except Exception:
    pass
scene.render.image_settings.file_format = "PNG"
out_dir = os.path.join(os.path.dirname(bpy.data.filepath), "work")
for frame in (30, 120, 180, 240, 330):
    scene.frame_set(frame)
    scene.render.filepath = os.path.join(out_dir, "day13_street_qa_%03d.png" % frame)
    bpy.ops.render.render(write_still=True)
