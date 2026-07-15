"""Isolated high-detail suburban house study for Followville.

This file does not participate in the live neighborhood generator. Run it in a
fresh Blender background session to render and export the prototype set.
"""

import math
import os
import bpy
from mathutils import Vector


OUT_DIR = os.path.join(os.path.dirname(__file__), "suburban_prototypes")


def material(name, color, roughness=0.78, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
    return mat


M = {
    "grass": material("Proto_Grass", (0.30, 0.51, 0.22)),
    "concrete": material("Proto_Concrete", (0.64, 0.63, 0.59)),
    "foundation": material("Proto_Foundation", (0.53, 0.54, 0.52)),
    "trim": material("Proto_Trim", (0.94, 0.92, 0.84)),
    "glass": material("Proto_Glass", (0.24, 0.48, 0.65), 0.28),
    "glass_dark": material("Proto_GlassDark", (0.08, 0.16, 0.23), 0.24),
    "door_blue": material("Proto_DoorBlue", (0.16, 0.34, 0.47)),
    "door_red": material("Proto_DoorRed", (0.52, 0.15, 0.12)),
    "door_green": material("Proto_DoorGreen", (0.18, 0.37, 0.24)),
    "garage": material("Proto_Garage", (0.84, 0.83, 0.76)),
    "roof_charcoal": material("Proto_RoofCharcoal", (0.20, 0.22, 0.24)),
    "roof_brown": material("Proto_RoofBrown", (0.33, 0.23, 0.18)),
    "roof_blue": material("Proto_RoofBlue", (0.22, 0.31, 0.38)),
    "brick": material("Proto_Brick", (0.49, 0.20, 0.14)),
    "stone": material("Proto_Stone", (0.45, 0.43, 0.38)),
    "wall_cream": material("Proto_WallCream", (0.88, 0.80, 0.66)),
    "wall_blue": material("Proto_WallBlue", (0.47, 0.64, 0.71)),
    "wall_green": material("Proto_WallGreen", (0.58, 0.68, 0.55)),
    "wall_peach": material("Proto_WallPeach", (0.83, 0.61, 0.49)),
    "wood": material("Proto_Wood", (0.38, 0.24, 0.14)),
    "metal": material("Proto_Metal", (0.15, 0.16, 0.17), 0.38, 0.18),
    "leaf": material("Proto_Leaf", (0.20, 0.43, 0.18)),
    "leaf2": material("Proto_Leaf2", (0.35, 0.55, 0.20)),
    "flower": material("Proto_Flower", (0.78, 0.25, 0.35)),
    "path": material("Proto_Path", (0.72, 0.67, 0.58)),
}


def box(col, name, size, loc, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = (size[0] / 2, size[1] / 2, size[2] / 2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)
    obj.data.materials.append(mat)
    if bevel:
        mod = obj.modifiers.new("Soft block edges", "BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def prism_roof(col, name, w, d, h, loc, mat, ridge="x"):
    hw, hd = w / 2, d / 2
    if ridge == "x":
        verts = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
                 (-hw, 0, h), (hw, 0, h)]
        faces = [(0, 1, 2, 3), (0, 4, 5, 1), (2, 5, 4, 3), (0, 3, 4), (1, 5, 2)]
    else:
        verts = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
                 (0, -hd, h), (0, hd, h)]
        faces = [(0, 1, 2, 3), (0, 4, 5, 3), (1, 2, 5, 4), (0, 1, 4), (3, 5, 2)]
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    col.objects.link(obj)
    return obj


def cylinder(col, name, radius, depth, loc, mat, vertices=8):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=loc)
    obj = bpy.context.object
    obj.name = name
    for old in list(obj.users_collection):
        old.objects.unlink(obj)
    col.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def window_front(col, name, x, y, z, width=1.2, height=1.25, shutters=False):
    # Fronts face -Y. Layering keeps frames readable in both Blender and GLB.
    box(col, name + "_recess", (width + .26, .10, height + .26), (x, y, z), M["trim"])
    box(col, name + "_glass", (width, .08, height), (x, y - .075, z), M["glass_dark"])
    box(col, name + "_mullion_v", (.07, .065, height), (x, y - .125, z), M["trim"])
    box(col, name + "_mullion_h", (width, .065, .07), (x, y - .13, z), M["trim"])
    box(col, name + "_sill", (width + .35, .28, .11), (x, y - .08, z - height / 2 - .10), M["trim"])
    if shutters:
        for sx in (-1, 1):
            xx = x + sx * (width / 2 + .22)
            box(col, name + ("_shutter_l" if sx < 0 else "_shutter_r"), (.25, .12, height + .14),
                (xx, y - .08, z), M["door_blue"])
            for dz in (-.36, 0, .36):
                box(col, name + "_slat", (.18, .07, .035), (xx, y - .155, z + dz), M["trim"])


def window_side(col, name, x, y, z, side=1, width=1.1, height=1.2):
    xx = x + side * .01
    box(col, name + "_recess", (.10, width + .26, height + .26), (xx, y, z), M["trim"])
    box(col, name + "_glass", (.08, width, height), (xx + side * .075, y, z), M["glass_dark"])
    box(col, name + "_mullion_v", (.065, .07, height), (xx + side * .125, y, z), M["trim"])
    box(col, name + "_mullion_h", (.065, width, .07), (xx + side * .13, y, z), M["trim"])


def front_door(col, name, x, y, z0, color):
    box(col, name + "_frame", (1.45, .28, 2.45), (x, y, z0 + 1.225), M["trim"])
    box(col, name + "_slab", (1.12, .13, 2.15), (x, y - .17, z0 + 1.075), color)
    for dz in (.44, 1.02, 1.61):
        box(col, name + "_panel", (.72, .06, .36), (x, y - .255, z0 + dz), M["trim"])
    cylinder(col, name + "_knob", .07, .11, (x + .36, y - .26, z0 + 1.03), M["metal"], 10).rotation_euler.x = math.radians(90)
    box(col, name + "_light", (.16, .18, .30), (x + .93, y - .09, z0 + 1.82), M["glass"])


def garage_door(col, name, x, y, z0, width=2.75):
    box(col, name + "_frame", (width + .35, .25, 2.35), (x, y, z0 + 1.175), M["trim"])
    box(col, name + "_door", (width, .12, 2.05), (x, y - .18, z0 + 1.025), M["garage"])
    for dz in (.40, .82, 1.24, 1.66):
        box(col, name + "_seam", (width - .15, .055, .035), (x, y - .26, z0 + dz), M["foundation"])
    for sx in (-.7, 0, .7):
        box(col, name + "_top_window", (.48, .055, .28), (x + sx, y - .27, z0 + 1.72), M["glass_dark"])


def porch(col, name, x, front_y, z0, width=3.4, depth=1.25, columns=2):
    box(col, name + "_deck", (width, depth, .24), (x, front_y - depth / 2, z0), M["wood"], .035)
    # Three broad steps toward the street.
    for i, (sw, sd, sh) in enumerate(((2.25, .42, .18), (1.95, .38, .18), (1.65, .34, .18))):
        box(col, name + f"_step_{i}", (sw, sd, sh), (x, front_y - depth - .15 - i * .29, z0 - .08 - i * .18), M["concrete"])
    post_xs = [x - width / 2 + .28, x + width / 2 - .28] if columns == 2 else [x - width / 2 + .28, x, x + width / 2 - .28]
    for i, px in enumerate(post_xs):
        box(col, name + f"_post_{i}", (.20, .20, 2.25), (px, front_y - depth + .18, z0 + 1.24), M["trim"], .025)
        box(col, name + f"_postbase_{i}", (.34, .34, .22), (px, front_y - depth + .18, z0 + .22), M["trim"])
    box(col, name + "_beam", (width, .24, .25), (x, front_y - depth + .18, z0 + 2.33), M["trim"])
    prism_roof(col, name + "_roof", width + .35, depth + .35, .66,
               (x, front_y - depth / 2, z0 + 2.43), M["roof_charcoal"], "x")


def landscaping(col, prefix, house_width, front_y, seed_shift=0.0):
    box(col, prefix + "_walk", (1.15, 3.2, .10), (seed_shift, front_y - 2.30, .06), M["path"])
    for i, x in enumerate((-house_width * .34, -house_width * .21, house_width * .23, house_width * .36)):
        cylinder(col, prefix + f"_shrub_{i}", .38 + .06 * (i % 2), .52, (x, front_y - .35, .30), M["leaf2"], 8)
        cylinder(col, prefix + f"_shrubcap_{i}", .30, .25, (x, front_y - .35, .65), M["leaf"], 8)
    # Mailbox close to the curb.
    box(col, prefix + "_mailpost", (.14, .14, 1.10), (house_width / 2 - .35, front_y - 3.55, .55), M["wood"])
    box(col, prefix + "_mailbox", (.48, .75, .38), (house_width / 2 - .35, front_y - 3.62, 1.18), M["metal"], .06)
    box(col, prefix + "_mailflag", (.06, .07, .55), (house_width / 2 - .05, front_y - 3.62, 1.31), M["door_red"])


def make_lot(name, center_x):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new(name + "_ROOT", None)
    root.empty_display_type = "PLAIN_AXES"
    root.location.x = center_x
    col.objects.link(root)
    for obj in list(col.objects):
        if obj != root:
            obj.parent = root
    return col, root


def parent_new_objects(col, root):
    for obj in col.objects:
        if obj != root and obj.parent is None:
            obj.parent = root


def build_ranch(center_x=-11.0):
    col, root = make_lot("SUBURBAN_RANCH", center_x)
    front = -2.95
    box(col, "Ranch_foundation", (8.6, 6.25, .38), (0, 0, .19), M["foundation"])
    box(col, "Ranch_body", (8.25, 5.9, 3.15), (0, 0, 1.93), M["wall_cream"], .07)
    box(col, "Ranch_brickskirt", (8.30, .16, .70), (0, front - .03, .73), M["brick"])
    prism_roof(col, "Ranch_roof", 8.85, 6.55, 2.0, (0, 0, 3.5), M["roof_brown"], "x")
    box(col, "Ranch_fascia", (8.95, .18, .22), (0, front - .28, 3.48), M["trim"])
    front_door(col, "Ranch_door", -1.05, front - .11, .40, M["door_green"])
    window_front(col, "Ranch_window_left", -3.15, front - .12, 2.05, 1.35, 1.20, True)
    window_front(col, "Ranch_window_mid", .70, front - .12, 2.05, 1.35, 1.20, True)
    garage_door(col, "Ranch_garage", 2.90, front - .12, .40, 2.55)
    porch(col, "Ranch_porch", -1.05, front - .15, .40, 2.25, 1.08)
    window_side(col, "Ranch_side_window", -4.14, .50, 2.0, -1)
    box(col, "Ranch_chimney", (.72, .72, 2.2), (-3.05, .80, 3.8), M["brick"])
    box(col, "Ranch_chimneycap", (.92, .92, .18), (-3.05, .80, 4.96), M["concrete"])
    box(col, "Ranch_driveway", (3.15, 4.0, .09), (2.90, front - 2.0, .05), M["concrete"])
    landscaping(col, "Ranch", 8.25, front, -1.05)
    parent_new_objects(col, root)
    return root


def build_two_story(center_x=0.0):
    col, root = make_lot("SUBURBAN_TWO_STORY", center_x)
    front = -2.75
    box(col, "Two_foundation", (7.55, 5.75, .42), (0, 0, .21), M["foundation"])
    box(col, "Two_body", (7.20, 5.45, 6.05), (0, 0, 3.43), M["wall_blue"], .07)
    box(col, "Two_belt", (7.35, .22, .18), (0, front - .02, 3.35), M["trim"])
    prism_roof(col, "Two_roof", 7.85, 6.10, 2.35, (0, 0, 6.45), M["roof_charcoal"], "x")
    box(col, "Two_fascia", (7.92, .18, .24), (0, front - .34, 6.40), M["trim"])
    front_door(col, "Two_door", -1.05, front - .12, .43, M["door_red"])
    porch(col, "Two_porch", -1.05, front - .15, .43, 2.55, 1.18)
    garage_door(col, "Two_garage", 2.15, front - .12, .43, 2.65)
    for i, x in enumerate((-2.55, 0.0, 2.55)):
        window_front(col, f"Two_upper_{i}", x, front - .13, 4.75, 1.16, 1.32, i != 1)
    window_front(col, "Two_lower_left", -2.65, front - .13, 2.12, 1.20, 1.28, True)
    window_side(col, "Two_side_low", -3.62, .65, 2.05, -1, 1.15, 1.25)
    window_side(col, "Two_side_high", -3.62, .65, 4.68, -1, 1.15, 1.25)
    # Entry gable makes the front silhouette distinctly suburban.
    prism_roof(col, "Two_entry_gable", 2.95, 2.05, 1.15, (-1.05, front - .58, 5.92), M["roof_charcoal"], "x")
    box(col, "Two_driveway", (3.25, 4.0, .09), (2.15, front - 2.0, .05), M["concrete"])
    landscaping(col, "Two", 7.2, front, -1.05)
    parent_new_objects(col, root)
    return root


def build_split_level(center_x=11.0):
    col, root = make_lot("SUBURBAN_SPLIT_LEVEL", center_x)
    front = -2.85
    box(col, "Split_foundation", (8.55, 5.95, .42), (0, 0, .21), M["foundation"])
    box(col, "Split_left_body", (4.45, 5.65, 4.90), (-2.0, 0, 2.87), M["wall_green"], .07)
    box(col, "Split_right_body", (4.0, 5.65, 3.48), (2.22, 0, 2.16), M["wall_peach"], .07)
    box(col, "Split_stone", (4.05, .18, 1.10), (2.22, front - .02, .97), M["stone"])
    prism_roof(col, "Split_left_roof", 4.95, 6.2, 1.65, (-2.0, 0, 5.32), M["roof_blue"], "x")
    prism_roof(col, "Split_right_roof", 4.5, 6.2, 1.45, (2.22, 0, 3.90), M["roof_blue"], "x")
    front_door(col, "Split_door", -.55, front - .12, .43, M["door_blue"])
    window_front(col, "Split_upper_left", -2.55, front - .13, 3.72, 1.35, 1.25, True)
    window_front(col, "Split_upper_mid", -1.02, front - .13, 3.72, 1.05, 1.25, False)
    window_front(col, "Split_right_window", 1.25, front - .13, 2.42, 1.15, 1.15, True)
    garage_door(col, "Split_garage", 3.03, front - .12, .43, 2.35)
    box(col, "Split_entry_pad", (1.9, 1.05, .22), (-.55, front - .55, .39), M["concrete"])
    for i in range(3):
        box(col, f"Split_step_{i}", (1.55 - .15 * i, .38, .18),
            (-.55, front - 1.05 - .28 * i, .22 - .12 * i), M["concrete"])
    box(col, "Split_entry_canopy", (2.15, 1.25, .18), (-.55, front - .55, 2.86), M["roof_blue"])
    box(col, "Split_canopy_post", (.18, .18, 2.25), (-1.48, front - 1.0, 1.60), M["trim"])
    box(col, "Split_driveway", (2.95, 4.0, .09), (3.0, front - 2.0, .05), M["concrete"])
    landscaping(col, "Split", 8.35, front, -.55)
    parent_new_objects(col, root)
    return root


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def setup_scene():
    # The script is launched without a .blend, so clear only scene objects. A
    # factory reset here would invalidate the module-level material references.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    os.makedirs(OUT_DIR, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("Prototype World")
    scene.world.color = (0.045, 0.065, 0.09)
    scene.view_settings.look = "AgX - Medium High Contrast"

    ground_col = bpy.data.collections.new("DISPLAY_LOTS")
    scene.collection.children.link(ground_col)
    box(ground_col, "Ground", (35, 14, .16), (0, 0, -.10), M["grass"])
    box(ground_col, "Street", (35, 3.2, .12), (0, -7.1, -.03), material("Proto_Road", (.12, .13, .14)))
    for x in (-11, 0, 11):
        box(ground_col, "Curb", (10.2, .25, .18), (x, -5.60, .04), M["concrete"])

    build_ranch(-11)
    build_two_story(0)
    build_split_level(11)

    bpy.ops.object.light_add(type="SUN", location=(0, -3, 14))
    sun = bpy.context.object
    sun.name = "Sun"
    sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(-28))
    sun.data.energy = 2.1
    sun.data.angle = math.radians(18)
    bpy.ops.object.light_add(type="AREA", location=(-7, -11, 13))
    key = bpy.context.object
    key.data.energy = 1700
    key.data.shape = "DISK"
    key.data.size = 9
    look_at(key, (0, 0, 2.5))

    bpy.ops.object.camera_add(location=(22, -31, 18))
    cam = bpy.context.object
    cam.data.lens = 54
    look_at(cam, (0, 0, 2.6))
    scene.camera = cam
    return scene, cam


def object_metrics(collection_names):
    metrics = {}
    for name in collection_names:
        col = bpy.data.collections[name]
        meshes = [o for o in col.objects if o.type == "MESH"]
        vertices = sum(len(o.data.vertices) for o in meshes)
        polygons = sum(len(o.data.polygons) for o in meshes)
        triangles = 0
        for obj in meshes:
            obj.data.calc_loop_triangles()
            triangles += len(obj.data.loop_triangles)
        metrics[name] = {"mesh_objects": len(meshes), "vertices": vertices,
                         "polygons": polygons, "triangles": triangles}
    return metrics


def export_glb(scene):
    # Export only the three houses, excluding the presentation ground/street.
    prototype_names = {"SUBURBAN_RANCH", "SUBURBAN_TWO_STORY", "SUBURBAN_SPLIT_LEVEL"}
    for obj in scene.objects:
        in_prototype = any(col.name in prototype_names for col in obj.users_collection)
        obj.select_set(obj.type == "MESH" and in_prototype)
    path = os.path.join(OUT_DIR, "suburban_house_prototypes.glb")
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True)
    return path


def main():
    scene, cam = setup_scene()
    front_path = os.path.join(OUT_DIR, "suburban_houses_front.png")
    scene.render.filepath = front_path
    bpy.ops.render.render(write_still=True)

    cam.location = (-22, -29, 15)
    look_at(cam, (0, 0, 2.5))
    rear_path = os.path.join(OUT_DIR, "suburban_houses_front_left.png")
    scene.render.filepath = rear_path
    bpy.ops.render.render(write_still=True)

    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1000
    hero_specs = (
        ("ranch", -11.0, 6.8),
        ("two_story", 0.0, 8.6),
        ("split_level", 11.0, 7.3),
    )
    for slug, x, height in hero_specs:
        cam.location = (x + 10.5, -15.5, height)
        cam.data.lens = 57
        look_at(cam, (x, 0, 2.65))
        hero_path = os.path.join(OUT_DIR, f"suburban_{slug}_closeup.png")
        scene.render.filepath = hero_path
        bpy.ops.render.render(write_still=True)

    glb_path = export_glb(scene)
    metrics = object_metrics(["SUBURBAN_RANCH", "SUBURBAN_TWO_STORY", "SUBURBAN_SPLIT_LEVEL"])
    metrics_path = os.path.join(OUT_DIR, "metrics.txt")
    with open(metrics_path, "w", encoding="utf-8") as f:
        for name, data in metrics.items():
            f.write(f"{name}: {data}\n")
        f.write(f"GLB bytes: {os.path.getsize(glb_path)}\n")
    print("PROTOTYPE_FRONT", front_path)
    print("PROTOTYPE_SECOND", rear_path)
    print("PROTOTYPE_GLB", glb_path, os.path.getsize(glb_path))
    print("PROTOTYPE_METRICS", metrics)


if __name__ == "__main__":
    main()
