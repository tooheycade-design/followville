"""Render isolated Followville Arcade day, night, aerial, and interior reviews.

This script never reads or writes world_state.json or neighborhood.blend.  It
builds the reusable generator asset directly, making it safe to run before the
canonical seed-129 replacement is integrated.
"""

import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"

import neighborhood_blender as nb  # noqa: E402


OUTPUT = ROOT / "renders" / "arcade_review"


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for col in list(bpy.data.collections):
        if col != bpy.context.scene.collection:
            bpy.data.collections.remove(col)


def aim_camera(name, location, target, lens=48):
    data = bpy.data.cameras.new(name)
    data.lens = lens
    data.sensor_width = 36
    data.clip_start = .08
    data.clip_end = 400
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = obj
    return obj


def setup_context():
    col = bpy.data.collections.new("ARCADE_REVIEW")
    bpy.context.scene.collection.children.link(col)
    nb.build_followville_arcade(col, 129)

    asphalt = nb.mat("ARCADE_REVIEW_asphalt", (.13, .14, .16), .96)
    sidewalk = nb.mat("ARCADE_REVIEW_sidewalk", (.48, .47, .44), .98)
    grass = nb.mat("ARCADE_REVIEW_grass", (.25, .43, .20), 1.0)
    line = nb.mat("ARCADE_REVIEW_line", (.85, .70, .22), .86)
    nb.add_box(col, "review_ground", 52, 50, .16, 0, 2, -.18, grass)
    nb.add_box(col, "review_sidewalk", 24, 7.4, .20, 0, -7.5, -.02, sidewalk)
    nb.add_box(col, "review_road", 52, 13, .13, 0, -17.7, -.15, asphalt)
    nb.add_box(col, "review_centerline", 16, .16, .025, -13, -17.7, -.02, line)
    nb.add_box(col, "review_centerline", 16, .16, .025, 13, -17.7, -.02, line)

    # Minimal neighbouring massing tests whether the one-lot silhouette holds
    # in an urban row without competing with real downtown properties.
    neighbour = nb.mat("ARCADE_REVIEW_neighbour", (.29, .25, .22), .90)
    roof = nb.mat("ARCADE_REVIEW_neighbour_roof", (.06, .065, .075), .82)
    for x, height in ((-12.2, 11.2), (12.2, 9.4)):
        nb.add_box(col, "review_neighbour", 9.1, 9.2, height, x, .25, 0, neighbour)
        nb.add_box(col, "review_neighbour_roof", 9.5, 9.6, .42, x, .25,
                   height, roof)
    return col


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_percentage = 100
    scene.render.use_file_extension = True
    scene.render.filepath = str(OUTPUT / "review.png")
    scene.render.image_settings.color_depth = "8"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_percentage = 100
    scene.render.fps = 30
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = .25
    scene.render.image_settings.color_mode = "RGBA"
    scene.world = bpy.data.worlds.new("ARCADE_REVIEW_WORLD")
    scene.world.use_nodes = True



def clear_lights():
    # Keep the four asset practicals; replace only review-rig lights.
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT" and obj.name.startswith("REVIEW_"):
            bpy.data.objects.remove(obj, do_unlink=True)


def lighting(mode):
    clear_lights()
    scene = bpy.context.scene
    bg = scene.world.node_tree.nodes.get("Background")
    if mode == "day":
        bg.inputs["Color"].default_value = (.36, .58, .82, 1)
        bg.inputs["Strength"].default_value = .72
        scene.view_settings.exposure = .15
        sun_data = bpy.data.lights.new("REVIEW_day_sun", "SUN")
        sun_data.energy = 2.4
        sun_data.angle = math.radians(6)
        sun_data.color = (1.0, .79, .60)
        sun = bpy.data.objects.new("REVIEW_day_sun", sun_data)
        bpy.context.scene.collection.objects.link(sun)
        sun.rotation_euler = (math.radians(38), 0, math.radians(-32))
        fill_data = bpy.data.lights.new("REVIEW_day_fill", "AREA")
        fill_data.energy = 650
        fill_data.shape = "DISK"
        fill_data.size = 18
        fill_data.color = (.48, .66, 1.0)
        fill = bpy.data.objects.new("REVIEW_day_fill", fill_data)
        bpy.context.scene.collection.objects.link(fill)
        fill.location = (-13, -14, 18)
        fill.rotation_euler = (Vector((0, 0, 7)) - fill.location).to_track_quat("-Z", "Y").to_euler()
    else:
        bg.inputs["Color"].default_value = (.008, .014, .045, 1)
        bg.inputs["Strength"].default_value = .16
        scene.view_settings.exposure = .8
        moon_data = bpy.data.lights.new("REVIEW_night_moon", "SUN")
        moon_data.energy = .65
        moon_data.angle = math.radians(8)
        moon_data.color = (.28, .42, 1.0)
        moon = bpy.data.objects.new("REVIEW_night_moon", moon_data)
        bpy.context.scene.collection.objects.link(moon)
        moon.rotation_euler = (math.radians(52), 0, math.radians(28))
        pool_data = bpy.data.lights.new("REVIEW_night_pool", "AREA")
        pool_data.energy = 520
        pool_data.shape = "RECTANGLE"
        pool_data.size = 8
        pool_data.size_y = 3
        pool_data.color = (1.0, .34, .12)
        pool = bpy.data.objects.new("REVIEW_night_pool", pool_data)
        bpy.context.scene.collection.objects.link(pool)
        pool.location = (0, -10, 7)
        pool.rotation_euler = (Vector((0, -4.5, 3)) - pool.location).to_track_quat("-Z", "Y").to_euler()


def render_view(name, mode, location, target, lens):
    lighting(mode)
    aim_camera("REVIEW_" + name, location, target, lens)
    path = OUTPUT / (name + ".png")
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("ARCADE_REVIEW", path)


def validate_asset(collection):
    meshes = [obj for obj in collection.all_objects if obj.type == "MESH"
              and obj.name == "followville_arcade_batched"]
    if len(meshes) != 1:
        raise RuntimeError("Arcade should batch to one mesh; got %d" % len(meshes))
    mesh = meshes[0]
    corners = [mesh.matrix_world @ Vector(corner) for corner in mesh.bound_box]
    bounds = {
        "min": [min(v[i] for v in corners) for i in range(3)],
        "max": [max(v[i] for v in corners) for i in range(3)],
        "vertices": len(mesh.data.vertices),
        "polygons": len(mesh.data.polygons),
        "materials": len(mesh.data.materials),
        "lights": sum(1 for obj in collection.all_objects if obj.type == "LIGHT"),
    }
    if bounds["min"][0] < -6.19 or bounds["max"][0] > 6.19:
        raise RuntimeError("Arcade exceeds its one-lot X footprint: %r" % bounds)
    if bounds["min"][1] < -6.19 or bounds["max"][1] > 6.19:
        raise RuntimeError("Arcade exceeds its one-lot Y footprint: %r" % bounds)
    if bounds["min"][2] < -.001:
        raise RuntimeError("Arcade geometry falls below its foundation: %r" % bounds)
    return bounds


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    clear_scene()
    collection = setup_context()
    setup_render()
    bounds = validate_asset(collection)
    render_view("day_front", "day", (0, -29, 8.2), (0, -.4, 7.0), 55)
    render_view("day_threequarter", "day", (22, -25, 17), (0, 0, 7.2), 58)
    render_view("day_left_threequarter", "day", (-22, -25, 17),
                (0, 0, 7.2), 58)
    render_view("day_overhead", "day", (20, -21, 36), (0, 0, 5.4), 54)
    render_view("night_front", "night", (0, -28, 8.0), (0, -.6, 7.0), 55)
    render_view("night_threequarter", "night", (21, -24, 16), (0, 0, 7.2), 58)
    render_view("entrance_pushin", "night", (0, -9.2, 2.35), (0, 1.3, 2.0), 38)
    render_view("interior_aisle", "night", (0, -3.75, 2.25),
                (0, 1.85, 1.65), 25)
    render_view("interior_left_row", "night", (.20, -2.55, 2.10),
                (-3.15, .25, 1.30), 34)
    render_view("interior_right_row", "night", (-.20, -2.55, 2.10),
                (3.15, .25, 1.30), 34)
    report = OUTPUT / "asset_report.json"
    report.write_text(json.dumps(bounds, indent=2), encoding="utf-8")
    print("ARCADE_REPORT", report)


if __name__ == "__main__":
    main()
