"""Render a maintainer contact sheet of candidate CC0 Quaternius characters.

This reads copies in Codex's integration cache and writes only a PNG under
test-results. It never opens or modifies Followville's neighborhood.blend.
"""

from pathlib import Path
import math
import bpy
from mathutils import Vector


REPO = Path(__file__).resolve().parents[1]
SOURCE = Path(
    r"C:\Users\cadet\.codex\integrations\quaternius-ultimate-animated-characters\Blends"
)
OUTPUT = REPO / "test-results" / "quaternius-library-contact-sheet.png"

CHARACTERS = [
    "Casual_Female",
    "Casual_Male",
    "Casual2_Female",
    "Casual2_Male",
    "Casual3_Female",
    "Casual3_Male",
    "Suit_Female",
    "Suit_Male",
    "Chef_Female",
    "Doctor_Male_Young",
    "Worker_Female",
    "Cowboy_Male",
    "Kimono_Female",
    "Pirate_Male",
    "Viking_Female",
    "Wizard",
]


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def append_character(name, x, z):
    source = SOURCE / f"{name}.blend"
    with bpy.data.libraries.load(str(source), link=False) as (available, loaded):
        loaded.objects = available.objects
    root = bpy.data.objects.new(f"PREVIEW_{name}", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = (x, 0, z)
    for obj in loaded.objects:
        if obj is None:
            continue
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = root
        if obj.type == "ARMATURE":
            obj.data.pose_position = "REST"
        if obj.type == "MESH":
            for polygon in obj.data.polygons:
                polygon.use_smooth = True


def main():
    clear_scene()
    columns = 8
    for index, name in enumerate(CHARACTERS):
        column = index % columns
        row = index // columns
        append_character(name, (column - 3.5) * 2.25, (0.5 - row) * 3.7)

    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.color = (0.035, 0.045, 0.055)

    ground_mat = bpy.data.materials.new("Preview Ground")
    ground_mat.diffuse_color = (0.07, 0.075, 0.09, 1)
    bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0.55, -1.85))
    ground = bpy.context.object
    ground.rotation_euler.x = math.radians(90)
    ground.data.materials.append(ground_mat)

    bpy.ops.object.light_add(type="AREA", location=(-6, -7, 8))
    key = bpy.context.object
    key.data.energy = 1800
    key.data.shape = "DISK"
    key.data.size = 7
    look_at(key, (0, 0, 0))
    bpy.ops.object.light_add(type="AREA", location=(8, 1, 5))
    fill = bpy.context.object
    fill.data.energy = 950
    fill.data.color = (0.55, 0.72, 1.0)
    fill.data.size = 8
    look_at(fill, (0, 0, 0))

    bpy.ops.object.camera_add(location=(0, -24, 2.05))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 20.0
    look_at(camera, (0, 0, 0.1))
    bpy.context.scene.camera = camera

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT)
    scene.render.film_transparent = False
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    print(f"QUATERNIUS_CONTACT_SHEET={OUTPUT}")


if __name__ == "__main__":
    main()
