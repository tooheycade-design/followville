"""Render static QA views after neighborhood_blender.py rebuilds the scene."""

import json
import math
import os
import random
import bpy
from mathutils import Vector


BASE = os.environ.get("NEIGHBORHOOD_STATE_DIR") or os.path.dirname(bpy.data.filepath)
OUT = os.path.join(BASE, "work", "suburban_qa")
os.makedirs(OUT, exist_ok=True)


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_view(scene, cam, name, target, offset, lens=55):
    cam.location = (target[0] + offset[0], target[1] + offset[1], target[2] + offset[2])
    cam.data.lens = lens
    look_at(cam, target)
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("QA_RENDER", scene.render.filepath)


def lot_to_world(gx, gy):
    bx, ix = divmod(gx, 3)
    by, iy = divmod(gy, 3)
    return bx * 36 + ix * 10 + 5, by * 36 + iy * 10 + 5


scene = bpy.context.scene
scene.frame_set(scene.frame_end)
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
try:
    scene.render.image_settings.media_type = "IMAGE"
except Exception:
    pass
scene.render.image_settings.file_format = "PNG"

cam_data = bpy.data.cameras.new("Suburban_QA_Camera")
cam = bpy.data.objects.new("Suburban_QA_Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

with open(os.path.join(BASE, "world_state.json"), encoding="utf-8") as f:
    state = json.load(f)

groups = {"grid": [], "planned": [], "ring": []}
for b in state["buildings"]:
    if b["type"] == "ringhouse":
        groups["ring"].append((b["px"], b["py"]))
    elif b["type"] == "house" and "px" in b:
        groups["planned"].append((b["px"], b["py"]))
    elif b["type"] == "house":
        groups["grid"].append(lot_to_world(b["gx"], b["gy"]))


def center(points):
    return (sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points), 2.8)


render_view(scene, cam, "grid_houses", center(groups["grid"]), (29, -34, 20), 58)
render_view(scene, cam, "park_ring_houses", center(groups["ring"]), (37, -42, 25), 60)
render_view(scene, cam, "planned_houses", center(groups["planned"]), (34, -38, 23), 60)


def building_pos(b):
    return (b["px"], b["py"]) if "px" in b else lot_to_world(b["gx"], b["gy"])


def building_rotation(b):
    if "rot" in b and b["rot"] is not None:
        return b["rot"]
    if b.get("face"):
        return {"s": 0.0, "e": math.pi / 2, "n": math.pi, "w": -math.pi / 2}[b["face"]]
    ix, iy = b["gx"] % 3, b["gy"] % 3
    dists = {0.0: iy, math.pi: 2 - iy, math.pi / 2: 2 - ix, -math.pi / 2: ix}
    best = min(dists.values())
    opts = sorted(k for k, value in dists.items() if value == best)
    return opts[random.Random(b["seed"]).randrange(len(opts))]


# Real-world front-door views for every two-story design plus representative
# one-story/dormer designs. This catches partial silhouettes or export loss.
for style in (0, 3, 4, 5, 7, 8, 9, 10, 12, 14):
    b = next(bb for bb in state["buildings"]
             if bb["type"] in ("house", "ringhouse") and bb["seed"] % 15 == style)
    x, y = building_pos(b)
    rot = building_rotation(b)
    front = (math.sin(rot), -math.cos(rot))
    right = (math.cos(rot), math.sin(rot))
    offset = (front[0] * 21 + right[0] * 7.0,
              front[1] * 21 + right[1] * 7.0, 10.0)
    render_view(scene, cam, "real_front_style_%02d" % style,
                (x, y, 2.9), offset, 54)

# Isolated one-color lineup makes geometry/intersection problems obvious.
qa = bpy.data.collections.new("QA_HOUSE_LINEUP")
scene.collection.children.link(qa)

ground_mat = bpy.data.materials.get("NB_grass")
verts = [(-31, -20, 0), (31, -20, 0), (31, 20, 0), (-31, 20, 0),
         (-31, -20, -.15), (31, -20, -.15), (31, 20, -.15), (-31, 20, -.15)]
faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
         (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
mesh = bpy.data.meshes.new("QA_ground_mesh")
mesh.from_pydata(verts, [], faces)
ground = bpy.data.objects.new("QA_ground", mesh)
ground.location.x = 1000
if ground_mat:
    mesh.materials.append(ground_mat)
qa.objects.link(ground)

for i in range(15):
    asset = bpy.data.collections.get("AST_suburban_%02d" % i)
    if not asset:
        raise RuntimeError("Missing suburban QA asset %02d" % i)
    inst = bpy.data.objects.new("QA_style_%02d" % i, None)
    inst.instance_type = "COLLECTION"
    inst.instance_collection = asset
    col, row = i % 5, i // 5
    inst.location = (1000 + (col - 2) * 12.0, (1 - row) * 12.0, .04)
    qa.objects.link(inst)

render_view(scene, cam, "all_15_styles", (1000, 0, 2.8), (58, -72, 52), 57)
render_view(scene, cam, "all_15_styles_left", (1000, 0, 2.8), (-58, -72, 50), 57)

print("QA_DONE", OUT)
