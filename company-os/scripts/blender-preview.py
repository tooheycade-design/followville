"""Trusted headless renderer for isolated Company OS model previews."""

import argparse
import json
import math
import os
import sys
import traceback

import bpy
from mathutils import Vector


RESULT_PREFIX = "COMPANY_OS_BLENDER_RESULT="


def emit(payload):
    print(RESULT_PREFIX + json.dumps(payload, separators=(",", ":")), flush=True)


def arguments():
    forwarded = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--profile",
        choices=("candidate", "canonical-content"),
        default="candidate",
    )
    parser.add_argument("--overlay", action="append", default=[])
    return parser.parse_args(forwarded)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def load_input(input_path):
    extension = os.path.splitext(input_path)[1].lower()
    if extension in {".glb", ".gltf"}:
        clear_scene()
        bpy.ops.import_scene.gltf(filepath=input_path)
    else:
        raise ValueError("Unsupported preview input.")


def renderable_meshes():
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and not obj.hide_render and len(obj.data.vertices) > 0
    ]


def content_focus_meshes(objects):
    excluded_prefixes = (
        "regional_walkable_terrain",
        "ground",
    )
    focused = [
        obj
        for obj in objects
        if not obj.name.lower().startswith(excluded_prefixes)
    ]
    return focused or objects


def scene_bounds(objects):
    corners = [
        obj.matrix_world @ Vector(corner)
        for obj in objects
        for corner in obj.bound_box
    ]
    if not corners:
        raise ValueError("The input contains no renderable mesh geometry.")
    minimum = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    maximum = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return minimum, maximum


def point_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def install_neutral_stage(minimum, maximum, profile):
    scene = bpy.context.scene
    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)

    center = (minimum + maximum) * 0.5
    size = maximum - minimum
    radius = max(size.length * 0.5, 0.5)

    camera_data = bpy.data.cameras.new("CompanyOS_Preview_Camera")
    camera = bpy.data.objects.new("CompanyOS_Preview_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + Vector((radius * 1.45, -radius * 1.75, radius * 1.2))
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(size.length * 1.15, 1.0)
    camera_data.clip_start = max(radius / 10000.0, 0.001)
    camera_data.clip_end = max(radius * 20.0, 1000.0)
    point_at(camera, center)
    scene.camera = camera

    for name, energy, size_factor, offset in (
        ("CompanyOS_Key", 1100.0, 1.4, (1.5, -1.8, 2.2)),
        ("CompanyOS_Fill", 700.0, 1.8, (-1.8, -0.5, 1.2)),
        ("CompanyOS_Rim", 900.0, 1.2, (0.4, 1.8, 1.7)),
    ):
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = max(radius * size_factor, 1.0)
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = center + Vector(offset) * radius
        point_at(light, center)

    world = bpy.data.worlds.new("CompanyOS_Neutral_World")
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    if profile == "canonical-content":
        background.inputs["Color"].default_value = (0.35, 0.55, 0.8, 1.0)
        background.inputs["Strength"].default_value = 0.8
    else:
        background.inputs["Color"].default_value = (0.055, 0.065, 0.08, 1.0)
        background.inputs["Strength"].default_value = 0.45
    scene.world = world


def collect_metrics(objects):
    vertices = 0
    polygons = 0
    triangles = 0
    material_names = set()
    textures = []
    missing_assets = []
    for obj in objects:
        mesh = obj.data
        vertices += len(mesh.vertices)
        polygons += len(mesh.polygons)
        mesh.calc_loop_triangles()
        triangles += len(mesh.loop_triangles)
        material_names.update(slot.material.name for slot in obj.material_slots if slot.material)
    for image in bpy.data.images:
        if image.source == "VIEWER" or not (image.filepath or image.packed_file):
            continue
        width, height = image.size[:]
        byte_size = 0
        if image.packed_file:
            byte_size = image.packed_file.size
        elif image.filepath:
            resolved = bpy.path.abspath(image.filepath)
            if os.path.isfile(resolved):
                byte_size = os.path.getsize(resolved)
            else:
                missing_assets.append(image.filepath)
        textures.append(
            {
                "name": image.name,
                "width": width,
                "height": height,
                "bytes": byte_size,
            }
        )
    actions = list(bpy.data.actions)
    return {
        "objects": len(bpy.context.scene.objects),
        "renderableObjects": len(objects),
        "meshes": len({obj.data.name for obj in objects}),
        "vertices": vertices,
        "polygons": polygons,
        "triangles": triangles,
        "materials": len(material_names),
        "textures": len(textures),
        "textureBytes": sum(texture["bytes"] for texture in textures),
        "maxTextureDimension": max(
            (max(texture["width"], texture["height"]) for texture in textures),
            default=0,
        ),
        "animations": len(actions),
        "animationFrameStart": int(bpy.context.scene.frame_start),
        "animationFrameEnd": int(bpy.context.scene.frame_end),
        "missingAssets": sorted(set(missing_assets)),
    }


def configure_render(profile):
    scene = bpy.context.scene
    engines = {
        item.identifier
        for item in scene.render.bl_rna.properties["engine"].enum_items
    }
    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if engine in engines:
            scene.render.engine = engine
            break
    else:
        raise RuntimeError("No supported Blender preview render engine is available.")
    if profile == "canonical-content":
        scene.render.resolution_x = 720
        scene.render.resolution_y = 1280
    else:
        scene.render.resolution_x = 960
        scene.render.resolution_y = 960
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.use_file_extension = True


def add_camera_text(camera, value, position):
    font = bpy.data.curves.new("CompanyOS_Overlay_Font", "FONT")
    font.body = value
    font.align_x = "CENTER"
    font.align_y = "CENTER"
    font.size = 0.12
    font.extrude = 0.006
    material = bpy.data.materials.get("CompanyOS_Overlay_Material")
    if material is None:
        material = bpy.data.materials.new("CompanyOS_Overlay_Material")
        material.diffuse_color = (1.0, 1.0, 1.0, 1.0)
        material.use_nodes = True
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bsdf.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bsdf.inputs["Emission Strength"].default_value = 1.0
        bsdf.inputs["Roughness"].default_value = 1.0
    font.materials.append(material)
    text = bpy.data.objects.new("CompanyOS_Overlay", font)
    bpy.context.scene.collection.objects.link(text)
    text.parent = camera
    text.location = Vector((0.0, position, -5.0))
    text.rotation_euler = (0.0, 0.0, 0.0)
    return text


def hierarchy_meshes(root):
    return [
        obj
        for obj in (root, *root.children_recursive)
        if obj.type == "MESH" and not obj.hide_render and len(obj.data.vertices) > 0
    ]


def named_root(prefix):
    return next(
        (
            obj
            for obj in bpy.context.scene.objects
            if obj.name.lower().startswith(prefix)
        ),
        None,
    )


def frame_story_camera(camera, label, center, radius):
    if label == "portrait-street":
        anchor = named_root("mushroomhouse_d1")
        anchor_meshes = hierarchy_meshes(anchor) if anchor is not None else []
        if anchor_meshes:
            minimum, maximum = scene_bounds(anchor_meshes)
            size = maximum - minimum
            target = (minimum + maximum) * 0.5
            target.z = minimum.z + size.z * 0.48
            distance = max(size.x, size.y, size.z) * 1.8
            camera.data.lens = 48
            camera.location = target + Vector(
                (distance * 0.65, -distance * 1.4, distance * 0.28)
            )
            point_at(camera, target)
            return

    if label == "portrait-downtown":
        prefixes = (
            "mushroomhouse_",
            "burjhouse_",
            "casinohouse_",
            "cathouse_",
            "castlehouse_",
            "eiffelhouse_",
            "flowerhouse_",
            "toilethouse_",
            "beachhouse_",
            "cottagehouse_",
        )
        downtown_meshes = [
            mesh
            for prefix in prefixes
            for root in [named_root(prefix)]
            if root is not None
            for mesh in hierarchy_meshes(root)
        ]
        if downtown_meshes:
            minimum, maximum = scene_bounds(downtown_meshes)
            size = maximum - minimum
            horizontal = max(size.x, size.y, 40.0)
            target = (minimum + maximum) * 0.5
            target.z = minimum.z + min(size.z * 0.18, 12.0)
            camera.data.lens = 52
            camera.location = target + Vector(
                (horizontal * 0.68, -horizontal * 1.08, horizontal * 0.62)
            )
            point_at(camera, target)
            return

    camera.data.lens = 52
    camera.location = center + Vector((0.9, -1.12, 1.45)) * radius
    point_at(camera, center)


def render_angles(output_directory, camera, center, radius, profile, overlays):
    artifacts = []
    if profile == "canonical-content":
        camera.data.type = "PERSP"
        camera.data.lens = 52
        camera.data.sensor_fit = "VERTICAL"
        angles = (
            ("portrait-street", None),
            ("portrait-town", None),
            ("portrait-downtown", None),
        )
    else:
        angles = (
            ("front", (1.45, -1.75, 1.2)),
            ("side", (1.9, 0.25, 1.05)),
            ("rear", (-1.45, 1.75, 1.2)),
        )
    for index, (label, offset) in enumerate(angles):
        if profile == "canonical-content":
            frame_story_camera(camera, label, center, radius)
        else:
            camera.location = center + Vector(offset) * radius
            point_at(camera, center)
        overlay = None
        if profile == "canonical-content" and overlays:
            overlay = add_camera_text(
                camera,
                overlays[min(index, len(overlays) - 1)],
                (0.42, 0.5, 0.46)[index],
            )
        filename = "preview-" + label + ".png"
        bpy.context.scene.render.filepath = os.path.join(output_directory, filename)
        bpy.ops.render.render(write_still=True)
        artifacts.append(filename)
        if overlay is not None:
            bpy.data.objects.remove(overlay, do_unlink=True)
    return artifacts


def render_animation_preview(output_directory, metrics):
    if metrics["animations"] == 0:
        return None
    scene = bpy.context.scene
    original = (
        scene.render.resolution_x,
        scene.render.resolution_y,
        scene.frame_step,
    )
    span = max(scene.frame_end - scene.frame_start + 1, 1)
    scene.frame_step = max(math.ceil(span / 24), 1)
    scene.render.resolution_x = 480
    scene.render.resolution_y = 480
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = os.path.join(output_directory, "animation-preview.mp4")
    try:
        bpy.ops.render.render(animation=True)
    finally:
        (
            scene.render.resolution_x,
            scene.render.resolution_y,
            scene.frame_step,
        ) = original
        scene.render.image_settings.file_format = "PNG"
    return "animation-preview.mp4"


def runtime_assessment(metrics, profile):
    limits = {
        "triangles": 250000,
        "materials": 64,
        "textures": 64,
        "maxTextureDimension": 4096,
    }
    failures = []
    if metrics["missingAssets"]:
        failures.append("missing external assets")
    if profile == "runtime":
        for name, maximum in limits.items():
            if metrics[name] > maximum:
                failures.append("{} exceeds {}".format(name, maximum))
    return {
        "profile": profile,
        "suitable": not failures,
        "failures": failures,
        "limits": limits if profile == "runtime" else None,
    }


def main():
    args = arguments()
    input_path = os.path.realpath(args.input)
    output_directory = os.path.realpath(args.output)
    os.makedirs(output_directory, exist_ok=True)
    report_path = os.path.join(output_directory, "technical-report.json")
    validated_glb_path = os.path.join(output_directory, "validated.glb")

    load_input(input_path)
    meshes = renderable_meshes()
    framing_meshes = (
        content_focus_meshes(meshes)
        if args.profile == "canonical-content"
        else meshes
    )
    minimum, maximum = scene_bounds(framing_meshes)
    metrics = collect_metrics(meshes)
    normalized_input = input_path.replace("\\", "/").lower()
    profile = (
        "cinematic"
        if args.profile == "canonical-content" or "/cinematic/" in normalized_input
        else "runtime"
    )
    assessment = runtime_assessment(metrics, profile)
    if args.profile != "canonical-content":
        bpy.ops.export_scene.gltf(
            filepath=validated_glb_path,
            export_format="GLB",
            use_visible=True,
        )
    center = (minimum + maximum) * 0.5
    radius = max((maximum - minimum).length * 0.5, 0.5)
    install_neutral_stage(minimum, maximum, args.profile)
    camera = bpy.context.scene.camera
    configure_render(args.profile)
    preview_artifacts = render_angles(
        output_directory,
        camera,
        center,
        radius,
        args.profile,
        args.overlay[:3],
    )
    animation_artifact = (
        None
        if args.profile == "canonical-content"
        else render_animation_preview(output_directory, metrics)
    )
    if animation_artifact:
        preview_artifacts.append(animation_artifact)
    report = {"metrics": metrics, "assessment": assessment}
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    emit(
        {
            "passed": assessment["suitable"],
            "message": (
                (
                    "Rendered trusted read-only canonical town evidence."
                    if args.profile == "canonical-content"
                    else "Rendered and validated isolated Blender candidate."
                )
                if assessment["suitable"]
                else "Candidate failed its Blender suitability assessment."
            ),
            "artifacts": preview_artifacts
            + ["technical-report.json"]
            + ([] if args.profile == "canonical-content" else ["validated.glb"]),
            "metrics": report,
        }
    )


try:
    main()
except Exception as error:
    traceback.print_exc(file=sys.stderr)
    emit(
        {
            "passed": False,
            "message": str(error),
            "artifacts": [],
        }
    )
    raise SystemExit(1)
