"""Render-only mayor address and Followville Point Station reveal.

Uses the production Followville website avatar library. It never saves either
authoritative Blend, exports town geometry, or changes world_state.json.
"""

import math
import os
import random
import sys
from pathlib import Path

import bpy

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"
import neighborhood_blender as nb  # noqa: E402
os.environ.pop("FOLLOWVILLE_IMPORT_ONLY", None)

OUT = Path(os.environ.get("MAYOR_REEL_OUT", str(REPO / "renders" / "mayor_station_reel")))
OUT.mkdir(parents=True, exist_ok=True)
FPS, END = 30, 600
HX, HY = nb.CITY_HALL_X, nb.CITY_HALL_Y
PX, PY = 446.0, 556.0

nb.main({"replay": True, "time": "sunset", "focus_type": "finished"})
scene = bpy.context.scene
scene.frame_set(scene.frame_end)
for obj in bpy.data.objects:
    if obj.animation_data:
        loc, rot, scale = tuple(obj.location), tuple(obj.rotation_euler), tuple(obj.scale)
        obj.animation_data_clear()
        obj.location, obj.rotation_euler, obj.scale = loc, rot, scale


def tag_render_only(obj):
    obj["nb_render_only"] = True
    return obj


def import_avatar(look, collection_name):
    """Import only the production skinned character from a website GLB."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(REPO / "avatar_assets" / "avatar_v1" / "look" / (look + ".glb")))
    imported = list(set(bpy.data.objects) - before)
    arm = next(o for o in imported if o.type == "ARMATURE")
    keep = {arm} | set(arm.children_recursive)
    for obj in imported:
        if obj not in keep:
            bpy.data.objects.remove(obj, do_unlink=True)
    col = bpy.data.collections.new(collection_name)
    scene.collection.children.link(col)
    for obj in keep:
        for old in list(obj.users_collection):
            old.objects.unlink(obj)
        col.objects.link(obj)
        tag_render_only(obj)
    return col, arm


avatar_looks = ("casual_day_f", "casual_day_m", "casual_lilac_f", "casual_sky_m",
                "classy_f", "classy_m", "worker_f", "worker_m")
crowd_sources = []
for index, look in enumerate(avatar_looks):
    col, _arm = import_avatar(look, "MR_AVATAR_%02d_%s" % (index, look))
    # Keep source collections out of the scene tree; collection instances below
    # can still reference and render them without eight avatars at the origin.
    scene.collection.children.unlink(col)
    crowd_sources.append(col)

mayor_col, mayor_arm = import_avatar("suit_m", "MR_MAYOR_SOURCE")
mayor_root = tag_render_only(bpy.data.objects.new("BPS_OUT_mayor", None))
scene.collection.objects.link(mayor_root)
for obj in list(mayor_col.objects):
    if obj.parent is None:
        obj.parent = mayor_root

ground = nb.terrain_height(HX, HY + 18.0)
mayor_root.location = (HX, HY + 18.0, ground)
mayor_root.rotation_euler.z = math.pi       # face the crowd to the north
mayor_root.scale = (.62, .62, .62)          # ~2.0m, not a civic-scale giant

# Animate the real rig: measured head turns and restrained public-speaking
# gestures. The source GLB has no facial blendshapes, so a tiny rounded mouth
# surface is attached to the actual Head bone and opens during speech.
head_bone = mayor_arm.pose.bones["Head"]
head_bone.rotation_mode = "XYZ"
for frame, degrees in ((1, -3), (60, -3), (120, 5), (180, -4), (240, 6),
                       (300, -5), (360, 3), (390, 0), (600, 0)):
    head_bone.rotation_euler.z = math.radians(degrees)
    head_bone.rotation_euler.x = math.radians(1.2 * math.sin(frame * .07))
    head_bone.keyframe_insert("rotation_euler", frame=frame)

for side, phase in (("L", 0.0), ("R", math.pi)):
    bone = mayor_arm.pose.bones["UpperArm." + side]
    bone.rotation_mode = "XYZ"
    for frame in (1, 60, 120, 180, 240, 300, 360, 390, 600):
        talk = 0.0 if frame < 60 or frame > 390 else math.sin(frame * .055 + phase)
        bone.rotation_euler.y = math.radians((7.0 + 7.0 * talk) * (1 if side == "L" else -1))
        bone.rotation_euler.x = math.radians(3.0 * talk)
        bone.keyframe_insert("rotation_euler", frame=frame)

mouth_mat = nb.mat("MR_avatar_mouth", (.20, .018, .025), .38)
bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=1,
                                    location=(0, -.625, 2.36))
mouth = bpy.context.object
mouth.name = "BPS_OUT_speaking_mouth"
mouth.scale = (.10, .016, .024)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
mouth.data.materials.append(mouth_mat)
tag_render_only(mouth)
mouth.parent = mayor_root
for frame in range(60, 391, 4):
    openness = .65 + 1.75 * abs(math.sin(frame * .29) * math.sin(frame * .071 + .8))
    mouth.scale.z = openness
    mouth.keyframe_insert("scale", frame=frame)

# Real website avatars form the crowd. Instances keep their full modeled
# faces, hair, clothing and proportions without multiplying mesh memory.
rng = random.Random(1701)
crowd_instances = []
for row in range(7):
    count = 9 + row * 2
    y = HY + 23.0 + row * 2.75
    width = 11.0 + row * 2.5
    for i in range(count):
        x = HX - width / 2 + width * (i + .5) / count + rng.uniform(-.25, .25)
        obj = tag_render_only(bpy.data.objects.new("crowd_avatar_%02d_%02d" % (row, i), None))
        scene.collection.objects.link(obj)
        obj.instance_type = "COLLECTION"
        obj.instance_collection = rng.choice(crowd_sources)
        obj.location = (x, y, nb.terrain_height(x, y))
        scale = rng.uniform(.50, .59)  # source looks normalize near 3.28m high
        obj.scale = (scale, scale, scale)
        obj.rotation_euler.z = rng.uniform(-.12, .12)  # source faces -Y: toward mayor
        phase = rng.uniform(0, math.tau)
        base_z = obj.location.z
        for frame in (1, 90, 180, 270, 360, 450, 600):
            obj.location.z = base_z + .018 * math.sin(frame * .065 + phase)
            obj.rotation_euler.z += math.radians(1.1 * math.sin(frame * .04 + phase))
            obj.keyframe_insert("location", frame=frame)
            obj.keyframe_insert("rotation_euler", frame=frame)
        crowd_instances.append(obj)

# A properly volumetric liquid-glass nameplate: thick beveled geometry,
# transmission, IOR, low roughness, subtle tint and separate reflection streaks.
def glass_material():
    mat = bpy.data.materials.new("MR_liquid_glass")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (.10, .35, .58, 1.0)
    bsdf.inputs["Metallic"].default_value = .05
    bsdf.inputs["Roughness"].default_value = .075
    bsdf.inputs["IOR"].default_value = 1.45
    if bsdf.inputs.get("Transmission Weight"):
        bsdf.inputs["Transmission Weight"].default_value = .82
    if bsdf.inputs.get("Coat Weight"):
        bsdf.inputs["Coat Weight"].default_value = .42
    bsdf.inputs["Alpha"].default_value = .54
    mat.diffuse_color = (.12, .42, .68, .54)
    try:
        mat.surface_render_method = "DITHERED"
    except (AttributeError, TypeError):
        pass
    return mat


def rounded_box(name, dimensions, material, parent, loc=(0, 0, 0), bevel=.12):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mod = obj.modifiers.new("liquid_rounding", "BEVEL")
    mod.width, mod.segments = bevel, 10
    obj.data.materials.append(material)
    obj.parent = parent
    tag_render_only(obj)
    return obj


tag = tag_render_only(bpy.data.objects.new("BPS_OUT_liquid_glass_tag", None))
scene.collection.objects.link(tag)
tag.location = (HX, HY + 18.0, ground + 2.42)
plate = rounded_box("BPS_OUT_glass_capsule", (1.18, .13, .30), glass_material(), tag, bevel=.14)
highlight_mat = nb.mat_emissive("MR_glass_highlight", (.72, .94, 1.0), .08, 2.2)
rounded_box("BPS_OUT_glass_top_glint", (.76, .020, .022), highlight_mat, tag,
            loc=(-.05, -.088, .102), bevel=.010)
rounded_box("BPS_OUT_glass_edge_glint", (.022, .020, .14), highlight_mat, tag,
            loc=(-.45, -.088, -.01), bevel=.010)
text_mat = nb.mat_emissive("MR_name_text", (.94, .985, 1.0), .18, 2.4)
font = bpy.data.curves.new("BPS_OUT_font", "FONT")
font.body, font.align_x, font.align_y = "BPS_OUT", "CENTER", "CENTER"
font.size, font.extrude, font.bevel_depth = .155, .010, .005
text = tag_render_only(bpy.data.objects.new("BPS_OUT_text", font))
scene.collection.objects.link(text)
text.data.materials.append(text_mat)
text.parent = tag
text.location = (0, -.088, -.003)
text.rotation_euler.x = math.radians(90)

# Camera path: two-second aerial dive, ten-second address, then transfer to the
# live station. Ground framing keeps the mayor human-sized, with shoulders and
# face readable while retaining crowd and City Hall context.
cam_data = bpy.data.cameras.new("MayorStationCamera")
cam_data.lens, cam_data.clip_start, cam_data.clip_end = 48, .15, 12000.0
cam = bpy.data.objects.new("MayorStationCamera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
aim = bpy.data.objects.new("MayorStationAim", None)
scene.collection.objects.link(aim)
track = cam.constraints.new("TRACK_TO")
track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
tag_track = tag.constraints.new("TRACK_TO")
tag_track.target, tag_track.track_axis, tag_track.up_axis = cam, "TRACK_NEGATIVE_Y", "UP_Z"

beats = (
    (1, (HX + 38, HY + 68, 138), (HX, HY + 15, ground + 1)),
    (60, (HX + 1.5, HY + 22.6, ground + 2.65), (HX, HY + 18.0, ground + 1.64)),
    (150, (HX + 1.15, HY + 22.1, ground + 2.55), (HX, HY + 18.0, ground + 1.68)),
    (270, (HX - .95, HY + 21.7, ground + 2.48), (HX, HY + 18.0, ground + 1.70)),
    (360, (HX + .85, HY + 22.0, ground + 2.55), (HX, HY + 18.0, ground + 1.68)),
    (420, (HX + 30, HY + 72, 66), (HX + 8, HY + 25, 7)),
    (480, (185, 180, 175), (305, 395, 18)),
    (540, (PX + 130, PY - 150, 118), (PX, PY, 21)),
    (600, (PX + 82, PY - 100, 82), (PX, PY, 19)),
)
for frame, position, target in beats:
    cam.location, aim.location = position, target
    cam.keyframe_insert("location", frame=frame)
    aim.keyframe_insert("location", frame=frame)
for obj in (cam, aim):
    for fc in nb.obj_fcurves(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

# The live Point Station appears from its existing root; this scene-only scale
# animation vanishes when Blender closes.
station_roots = [o for o in bpy.data.objects if o.get("nb_world_type") == "nuclearplant"]
if not station_roots:
    raise RuntimeError("Could not locate Followville Point Station")
for obj in station_roots:
    final = tuple(obj.scale)
    obj.scale = (final[0], final[1], .012)
    obj.keyframe_insert("scale", frame=430)
    obj.keyframe_insert("scale", frame=455)
    obj.scale = final
    obj.keyframe_insert("scale", frame=565)
    obj.keyframe_insert("scale", frame=600)
    for fc in nb.obj_fcurves(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"

scene.frame_start, scene.frame_end, scene.render.fps = 1, END, FPS
scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
scene.render.resolution_percentage = int(os.environ.get("MAYOR_REEL_PERCENT", "100"))
scene.render.filepath = str(OUT / "mayor_station_")

work_blend = os.environ.get("MAYOR_REEL_WORK_BLEND", "").strip()
if work_blend:
    bpy.ops.wm.save_as_mainfile(filepath=work_blend, copy=True)
    print("MAYOR_REEL_WORK_BLEND " + work_blend)

preview = [int(v) for v in os.environ.get("MAYOR_REEL_FRAMES", "").split(",") if v.strip()]
if preview:
    try:
        scene.render.image_settings.media_type = "IMAGE"
    except (AttributeError, TypeError):
        pass
    scene.render.image_settings.file_format = "PNG"
    for frame in preview:
        scene.frame_set(frame)
        scene.render.filepath = str(OUT / ("avatar_preview_%04d" % frame))
        bpy.ops.render.render(write_still=True)
        print("MAYOR_REEL_FRAME " + scene.render.filepath)
    print("MAYOR_REEL_PREVIEW_DONE")
else:
    try:
        scene.render.image_settings.media_type = "VIDEO"
    except (AttributeError, TypeError):
        pass
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "HIGH"
    scene.render.filepath = str(OUT / "followville_mayor_station.mp4")
    bpy.ops.render.render(animation=True)
    print("MAYOR_REEL_DONE " + scene.render.filepath)
