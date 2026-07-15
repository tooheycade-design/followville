import math
import os

import bpy
from mathutils import Vector


OUT = os.path.join(os.path.dirname(bpy.data.filepath), "work", "fix-qa")
os.makedirs(OUT, exist_ok=True)


def point_camera(camera, target):
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


scene = bpy.context.scene
for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        pass
scene.render.resolution_x = 1000
scene.render.resolution_y = 800
scene.render.resolution_percentage = 100
try:
    scene.render.image_settings.media_type = "IMAGE"
except (AttributeError, TypeError):
    pass
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False

camera_data = bpy.data.cameras.new("QA_Camera")
camera_data.lens = 54
camera = bpy.data.objects.new("QA_Camera", camera_data)
scene.collection.objects.link(camera)
scene.camera = camera

scene.frame_set(scene.frame_end)
school_asset = next(
    col for col in bpy.data.collections if col.name.startswith("AST_elementaryschool")
)
school = bpy.data.objects.new("QA_School", None)
school.instance_type = "COLLECTION"
school.instance_collection = school_asset
school.location = (1000.0, 1000.0, 0.0)
scene.collection.objects.link(school)
school_center = school.location
camera.location = school_center + Vector((0.0, 20.0, 22.0))
point_camera(camera, school_center + Vector((0.0, 10.2, 1.4)))
scene.render.filepath = os.path.join(OUT, "playground_fixed.png")
scene.render.film_transparent = False
bpy.ops.render.render(write_still=True)

camera.location = school_center + Vector((21.0, 24.0, 9.0))
point_camera(camera, school_center + Vector((0.0, 10.6, 2.0)))
scene.render.filepath = os.path.join(OUT, "playground_side_fixed.png")
bpy.ops.render.render(write_still=True)

car_asset = next(col for col in bpy.data.collections if col.name.startswith("AST_car_"))
car = bpy.data.objects.new("QA_Car", None)
car.instance_type = "COLLECTION"
car.instance_collection = car_asset
car.location = (1040.0, 1000.0, 0.0)
scene.collection.objects.link(car)
car_pos = car.location
camera.location = car_pos + Vector((0.0, -5.6, 2.15))
point_camera(camera, car_pos + Vector((0.0, 0.0, .75)))
camera.data.lens = 62
scene.render.filepath = os.path.join(OUT, "car_wheels_near_side.png")
bpy.ops.render.render(write_still=True)

camera.location = car_pos + Vector((0.0, 5.6, 2.15))
point_camera(camera, car_pos + Vector((0.0, 0.0, .75)))
scene.render.filepath = os.path.join(OUT, "car_wheels_far_side.png")
bpy.ops.render.render(write_still=True)

print("QA_PLAYGROUND", os.path.join(OUT, "playground_fixed.png"))
print("QA_PLAYGROUND_SIDE", os.path.join(OUT, "playground_side_fixed.png"))
print("QA_CAR_NEAR", os.path.join(OUT, "car_wheels_near_side.png"))
print("QA_CAR_FAR", os.path.join(OUT, "car_wheels_far_side.png"))
