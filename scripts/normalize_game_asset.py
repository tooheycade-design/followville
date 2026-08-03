"""Normalize one isolated source model into a web-ready GLB and review render.

Run with Blender, never with ordinary Python::

    blender --background --python-exit-code 1 --python scripts/normalize_game_asset.py -- \
      --input raw.glb --output work/normalized.glb --preview work/normalized.png

The script refuses canonical town outputs. It is an intake tool, not a town
generator or exporter.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


REPO = Path(__file__).resolve().parents[1]
BLOCKED_OUTPUTS = {
    (REPO / "town.glb").resolve(),
    (REPO / "neighborhood.blend").resolve(),
    Path(r"C:\Users\cadet\iCloudDrive\neighborhood\neighborhood.blend").resolve(),
}


def parse_args() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--target-height", type=float)
    parser.add_argument("--target-max-dimension", type=float)
    parser.add_argument("--yaw", type=float, default=0.0, help="clockwise degrees around Blender Z before normalization")
    parser.add_argument("--report", type=Path)
    return parser.parse_args(arguments)


def validate_paths(args: argparse.Namespace) -> tuple[Path, Path, Path | None, Path | None]:
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    preview = args.preview.expanduser().resolve() if args.preview else None
    report = args.report.expanduser().resolve() if args.report else output.with_suffix(".json")
    if not source.is_file():
        raise RuntimeError(f"input does not exist: {source}")
    if source.suffix.lower() not in {".glb", ".gltf", ".fbx", ".obj"}:
        raise RuntimeError("input must be GLB, glTF, FBX or OBJ")
    if output.suffix.lower() != ".glb":
        raise RuntimeError("output must be a .glb file")
    if output in BLOCKED_OUTPUTS or "town_chunks" in {part.lower() for part in output.parts}:
        raise RuntimeError(f"refusing canonical town output: {output}")
    if preview and preview.suffix.lower() != ".png":
        raise RuntimeError("preview must be PNG")
    for path in (output, preview, report):
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
    return source, output, preview, report


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.images,
                       bpy.data.cameras, bpy.data.lights):
        for block in list(collection):
            if block.users == 0:
                collection.remove(block)


def import_model(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    elif suffix == ".obj":
        if hasattr(bpy.ops.wm, "obj_import"):
            bpy.ops.wm.obj_import(filepath=str(path))
        else:
            bpy.ops.import_scene.obj(filepath=str(path))


def mesh_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    if not corners:
        raise RuntimeError("the imported file contains no mesh geometry")
    minimum = Vector((min(point.x for point in corners), min(point.y for point in corners), min(point.z for point in corners)))
    maximum = Vector((max(point.x for point in corners), max(point.y for point in corners), max(point.z for point in corners)))
    return minimum, maximum


def normalize(objects: list[bpy.types.Object], target_height: float | None,
              target_max_dimension: float | None, yaw_degrees: float) -> tuple[Vector, Vector, float]:
    imported = set(objects)
    roots = [obj for obj in objects if obj.parent not in imported]
    if yaw_degrees:
        rotation = Matrix.Rotation(math.radians(-yaw_degrees), 4, "Z")
        for root in roots:
            root.matrix_world = rotation @ root.matrix_world

    meshes = [obj for obj in objects if obj.type == "MESH"]
    minimum, maximum = mesh_bounds(meshes)
    dimensions = maximum - minimum
    scale = 1.0
    if target_height:
        if dimensions.z <= 0:
            raise RuntimeError("cannot scale a zero-height asset")
        scale = target_height / dimensions.z
    elif target_max_dimension:
        largest = max(dimensions)
        if largest <= 0:
            raise RuntimeError("cannot scale a zero-size asset")
        scale = target_max_dimension / largest

    center_x = (minimum.x + maximum.x) * 0.5
    center_y = (minimum.y + maximum.y) * 0.5
    transform = Matrix.Scale(scale, 4) @ Matrix.Translation((-center_x, -center_y, -minimum.z))
    for root in roots:
        root.matrix_world = transform @ root.matrix_world

    for obj in meshes:
        for material in obj.data.materials:
            if material:
                material.use_backface_culling = True
                if hasattr(material, "surface_render_method") and material.surface_render_method == "DITHERED":
                    material.surface_render_method = "DITHERED"
    bpy.context.view_layer.update()
    final_minimum, final_maximum = mesh_bounds(meshes)
    return final_minimum, final_maximum, scale


def export_glb(output: Path, objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        if obj.name in bpy.context.view_layer.objects:
            obj.select_set(True)
    bpy.context.view_layer.objects.active = next(obj for obj in objects if obj.type == "MESH")
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_animations=False,
        export_cameras=False,
        export_lights=False,
        export_yup=True,
    )


def look_at(obj: bpy.types.Object, point: Vector) -> None:
    obj.rotation_euler = (point - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_preview(path: Path, minimum: Vector, maximum: Vector) -> None:
    scene = bpy.context.scene
    # Blender 5.1 exposes Eevee as BLENDER_EEVEE; 4.x used the transitional
    # BLENDER_EEVEE_NEXT identifier. Choose from the running build's enum so
    # the intake tool remains usable across both supported generations.
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = str(path)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.018, 0.024, 0.032, 1.0)
    background.inputs["Strength"].default_value = 0.24

    center = (minimum + maximum) * 0.5
    dimensions = maximum - minimum
    radius = max(dimensions) * 0.72
    camera_data = bpy.data.cameras.new("asset_review_camera")
    camera = bpy.data.objects.new("asset_review_camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((radius * 1.55, -radius * 1.85, radius * 1.25))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(dimensions.x, dimensions.y, dimensions.z) * 1.55
    look_at(camera, center)
    scene.camera = camera

    for name, energy, location, size in (
        ("asset_key", 260.0, center + Vector((-radius, -radius * 1.3, radius * 2.0)), radius * 1.5),
        ("asset_fill", 110.0, center + Vector((radius * 1.5, radius, radius)), radius * 1.25),
    ):
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = max(1.0, size)
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = location
        look_at(light, center)

    plane_size = max(dimensions.x, dimensions.y) * 3.0
    bpy.ops.mesh.primitive_plane_add(size=max(2.0, plane_size), location=(0, 0, minimum.z - 0.01))
    plane = bpy.context.object
    plane.name = "asset_review_floor"
    floor_material = bpy.data.materials.new("asset_review_floor")
    floor_material.use_nodes = True
    floor_shader = floor_material.node_tree.nodes.get("Principled BSDF")
    floor_shader.inputs["Base Color"].default_value = (0.055, 0.07, 0.085, 1.0)
    floor_shader.inputs["Roughness"].default_value = 0.92
    plane.data.materials.append(floor_material)
    bpy.ops.render.render(write_still=True)


def main() -> int:
    args = parse_args()
    source, output, preview, report = validate_paths(args)
    clear_scene()
    import_model(source)
    imported = [obj for obj in bpy.context.scene.objects if obj.type not in {"CAMERA", "LIGHT"}]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    if not meshes:
        raise RuntimeError("the imported file contains no mesh objects")
    minimum, maximum, scale = normalize(
        imported, args.target_height, args.target_max_dimension, args.yaw
    )
    export_glb(output, imported)
    if preview:
        render_preview(preview, minimum, maximum)

    for obj in meshes:
        obj.data.calc_loop_triangles()
    triangles = sum(len(obj.data.loop_triangles) for obj in meshes)
    result = {
        "input": str(source),
        "output": str(output),
        "preview": str(preview) if preview else None,
        "objects": len(imported),
        "meshes": len(meshes),
        "materials": len({material.name for obj in meshes for material in obj.data.materials if material}),
        "vertices": sum(len(obj.data.vertices) for obj in meshes),
        "triangles": triangles,
        "scale_applied": round(scale, 8),
        "bounds": {
            "min": [round(value, 6) for value in minimum],
            "max": [round(value, 6) for value in maximum],
        },
    }
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("ASSET_NORMALIZE_OK " + json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
