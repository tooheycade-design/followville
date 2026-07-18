"""Build Followville's modular avatar library from Quaternius' CC0 characters.

The source character, rig, eyes, eyebrows, and hairstyles come from the CC0
Universal Base Characters pack. The complete modular garments come from the
CC0 Modular Character Outfits - Fantasy pack. Followville applies restrained
color grades to the source textures while preserving their modeled detail.

This script creates an isolated avatar scene. It never opens or writes the
canonical neighborhood.blend or any town asset.
"""

from pathlib import Path
import bmesh
import bpy
import hashlib
import json


REPO = Path(__file__).resolve().parents[1]
ASSET_DIR = REPO / "avatar_assets"
OUTPUT_DIR = ASSET_DIR / "avatar_v1"
SOURCE_DIR = ASSET_DIR / "source"
OUTPUT_BLEND = SOURCE_DIR / "followville_avatar_library.blend"

QUATERNIUS_ROOT = Path(
    r"C:\Users\cadet\.codex\integrations\quaternius-universal-base-characters-standard"
) / "Universal Base Characters[Standard]"
BASE_DIR = QUATERNIUS_ROOT / "Base Characters"
HAIR_DIR = QUATERNIUS_ROOT / "Hairstyles" / "Rigged to Head Bone" / "FBX (Unity)"

BODY_FBX = BASE_DIR / "Unity" / "Superhero_Male_FullBody.fbx"
BODY_TEXTURES = BASE_DIR / "Textures"
EYE_TEXTURE = BODY_TEXTURES / "T_Eye_Brown.png"
HAIR_TEXTURE = BODY_TEXTURES / "T_Hair_1_BaseColor.png"

OUTFIT_PACK = Path(
    r"C:\Users\cadet\.codex\integrations\quaternius-modular-character-outfits-fantasy"
) / "Modular Character Outfits - Fantasy[Standard]"
OUTFIT_EXPORTS = OUTFIT_PACK / "Exports" / "FBX (Unity)"
OUTFIT_DIR = OUTFIT_EXPORTS / "Outfits"
OUTFIT_PARTS_DIR = OUTFIT_EXPORTS / "Modular Parts"
OUTFIT_TEXTURES = OUTFIT_PACK / "Textures"
BODY_TEXTURE = BODY_TEXTURES / "T_Superhero_Male_Ligh.png"
PEASANT_TEXTURE = OUTFIT_TEXTURES / "Peasant" / "T_Peasant_BaseColor.png"
PEASANT_TEXTURE_2 = OUTFIT_TEXTURES / "Peasant" / "T_Peasant_2_BaseColor.png"
RANGER_TEXTURE = OUTFIT_TEXTURES / "Ranger" / "T_Ranger_BaseColor.png"
RANGER_TEXTURE_3 = OUTFIT_TEXTURES / "Ranger" / "T_Ranger_3_BaseColor.png"
PEASANT_FBX = OUTFIT_DIR / "Male_Peasant.fbx"
RANGER_FBX = OUTFIT_DIR / "Male_Ranger.fbx"
RANGER_HOOD_FBX = OUTFIT_PARTS_DIR / "Male_Ranger_Head_Hood.fbx"

HAIRS = {
    "close_crop": "Hair_Buzzed.fbx",
    "tousled": "Hair_BuzzedFemale.fbx",
    "swept": "Hair_SimpleParted.fbx",
    "afro": "Hair_Buns.fbx",
    "long": "Hair_Long.fbx",
}

OUTFIT_SOURCES = {
    # Hue uses Blender's 0.5-neutral Hue/Saturation node convention.
    "tailored": (PEASANT_FBX, PEASANT_TEXTURE_2, 0.60, 1.08, 1.10),
    "striped": (PEASANT_FBX, PEASANT_TEXTURE, 0.50, 0.92, 1.02),
    "tee": (PEASANT_FBX, PEASANT_TEXTURE_2, 0.43, 0.96, 1.16),
    "field_jacket": (RANGER_FBX, RANGER_TEXTURE, 0.50, 1.00, 1.04),
    "weekend": (RANGER_FBX, RANGER_TEXTURE_3, 0.50, 0.94, 1.04),
    "active": (RANGER_FBX, RANGER_TEXTURE, 0.64, 1.08, 1.10),
}


def require_sources():
    required = [
        BODY_FBX, BODY_TEXTURE, EYE_TEXTURE, HAIR_TEXTURE,
        PEASANT_FBX, RANGER_FBX, RANGER_HOOD_FBX,
        PEASANT_TEXTURE, PEASANT_TEXTURE_2, RANGER_TEXTURE, RANGER_TEXTURE_3,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("Missing Quaternius CC0 source assets: " + ", ".join(missing))


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.materials, bpy.data.images):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def solid_material(name, color, roughness=0.78):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.diffuse_color = (*color, 1.0)
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = 0.0
    return material


def image_material(name, path, roughness=0.68, hue=0.5, saturation=1.0, value=1.0):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Roughness"].default_value = roughness
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(str(path), check_existing=True)
    texture.interpolation = "Linear"
    grade = nodes.new("ShaderNodeHueSaturation")
    grade.inputs["Hue"].default_value = hue
    grade.inputs["Saturation"].default_value = saturation
    grade.inputs["Value"].default_value = value
    links.new(texture.outputs["Color"], grade.inputs["Color"])
    links.new(grade.outputs["Color"], shader.inputs["Base Color"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def replace_material(obj, material):
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for polygon in obj.data.polygons:
        polygon.material_index = 0
        polygon.use_smooth = True


def import_body():
    bpy.ops.import_scene.fbx(filepath=str(BODY_FBX), use_anim=False)
    rig = bpy.data.objects.get("Armature")
    body = bpy.data.objects.get("SuperHero_Male")
    eyes = bpy.data.objects.get("Eyes")
    brows = bpy.data.objects.get("Eyebrows")
    if not all((rig, body, eyes, brows)):
        raise RuntimeError("Quaternius body import did not contain the expected production objects")

    rig.name = "FV_RIG"
    body.name = "FV_BODY"
    eyes.name = "FV_EYES"
    brows.name = "FV_EYEBROWS"

    replace_material(body, image_material("FV_MAT_SKIN", BODY_TEXTURE, 0.74))
    replace_material(eyes, image_material("FV_MAT_EYES", EYE_TEXTURE, 0.42))
    replace_material(brows, solid_material("FV_MAT_BROWS", (0.055, 0.025, 0.014), 0.72))
    return rig, body, eyes, brows


def group_weight(vertex, allowed_indices):
    return sum(group.weight for group in vertex.groups if group.group in allowed_indices)


def extract_weighted_surface(source, name, allowed_bones, material, offset, smooth_steps=0):
    """Create a fitted garment from the authored character surface and skin weights."""
    garment = source.copy()
    garment.data = source.data.copy()
    garment.animation_data_clear()
    garment.name = name
    bpy.context.collection.objects.link(garment)

    allowed_indices = {
        group.index for group in garment.vertex_groups if group.name in allowed_bones
    }
    keep_faces = set()
    for polygon in garment.data.polygons:
        score = sum(group_weight(garment.data.vertices[index], allowed_indices) for index in polygon.vertices)
        score /= max(1, len(polygon.vertices))
        # Boundary faces often blend two neighboring bones (shoulder/neck,
        # waist/torso, wrist/hand). A low inclusion threshold keeps those
        # seams continuous; the small normal offset prevents skin z-fighting.
        if score >= 0.08:
            keep_faces.add(polygon.index)

    mesh = garment.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    remove = [face for face in bm.faces if face.index not in keep_faces]
    bmesh.ops.delete(bm, geom=remove, context="FACES")
    loose = [vertex for vertex in bm.verts if not vertex.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.normal_update()
    for vertex in bm.verts:
        vertex.co += vertex.normal * offset
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    replace_material(garment, material)
    if smooth_steps:
        modifier = garment.modifiers.new("FV garment tailoring", "SMOOTH")
        modifier.factor = 0.34
        modifier.iterations = smooth_steps
        bpy.context.view_layer.objects.active = garment
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    return garment


def bind_rigid_mesh(obj, rig, bone_name):
    for group in list(obj.vertex_groups):
        obj.vertex_groups.remove(group)
    group = obj.vertex_groups.new(name=bone_name)
    group.add(range(len(obj.data.vertices)), 1.0, "REPLACE")
    modifier = obj.modifiers.new("FV armature", "ARMATURE")
    modifier.object = rig
    obj.parent = rig
    return obj


def triangular_prism(name, center_x, material, rig):
    x0 = center_x
    side = -1 if center_x < 0 else 1
    front = -0.173
    depth = 0.010
    points = [
        (x0 - side * 0.060, front, 1.485),
        (x0 + side * 0.045, front, 1.475),
        (x0 + side * 0.030, front - 0.006, 1.385),
    ]
    vertices = points + [(x, y + depth, z) for x, y, z in points]
    faces = [(0, 1, 2), (3, 5, 4), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return bind_rigid_mesh(obj, rig, "spine_03")


def add_buttons(prefix, material, rig):
    buttons = []
    for index, z in enumerate((1.34, 1.22, 1.10)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, location=(0.0, -0.181, z))
        button = bpy.context.object
        button.name = f"{prefix}_BUTTON_{index + 1}"
        button.scale = (0.012, 0.006, 0.012)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        replace_material(button, material)
        bind_rigid_mesh(button, rig, "spine_02" if z < 1.20 else "spine_03")
        buttons.append(button)
    return buttons


def assign_official_outfit_materials(obj, cloth_material, skin_material):
    for index, material in enumerate(list(obj.data.materials)):
        if material and "Regular_Male" in material.name:
            obj.data.materials[index] = skin_material
        else:
            obj.data.materials[index] = cloth_material
    for polygon in obj.data.polygons:
        polygon.use_smooth = True


def create_outfits():
    result = {}
    for outfit_id, (source, texture, hue, saturation, value) in OUTFIT_SOURCES.items():
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.fbx(filepath=str(source), use_anim=False)
        created = [obj for obj in bpy.context.scene.objects if obj not in before]
        rigs = [obj for obj in created if obj.type == "ARMATURE"]
        meshes = [obj for obj in created if obj.type == "MESH"]
        if len(rigs) != 1 or not meshes:
            raise RuntimeError(f"Unexpected Quaternius outfit import for {source}")
        outfit_rig = rigs[0]
        outfit_rig.name = f"FV_OUTFIT_RIG_{outfit_id}"
        cloth = image_material(
            f"FV_MAT_OUTFIT_{outfit_id}", texture, 0.78, hue, saturation, value
        )
        skin = image_material(f"FV_MAT_SKIN_{outfit_id}", BODY_TEXTURE, 0.74)
        objects = []
        for mesh in meshes:
            if "Head_Hood" in mesh.name or "Acc_Pauldron" in mesh.name:
                bpy.data.objects.remove(mesh, do_unlink=True)
                continue
            mesh.name = f"FV_OUTFIT_{outfit_id}_{mesh.name}"
            assign_official_outfit_materials(mesh, cloth, skin)
            objects.append(mesh)
        result[outfit_id] = (outfit_rig, objects)
    return result


def import_hair_modules():
    result = {}
    hair_material = image_material("FV_MAT_HAIR", HAIR_TEXTURE, 0.70)
    for hair_id, filename in HAIRS.items():
        before = set(bpy.context.scene.objects)
        bpy.ops.import_scene.fbx(filepath=str(HAIR_DIR / filename), use_anim=False)
        created = [obj for obj in bpy.context.scene.objects if obj not in before]
        rigs = [obj for obj in created if obj.type == "ARMATURE"]
        meshes = [obj for obj in created if obj.type == "MESH"]
        if len(rigs) != 1 or len(meshes) != 1:
            raise RuntimeError(f"Unexpected Quaternius hair import for {filename}")
        hair_rig, hair = rigs[0], meshes[0]
        hair_rig.name = f"FV_HAIR_RIG_{hair_id}"
        hair.name = f"FV_HAIR_{hair_id}"
        replace_material(hair, hair_material)
        result[hair_id] = (hair_rig, hair)
    return result


def import_official_hood():
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=str(RANGER_HOOD_FBX), use_anim=False)
    created = [obj for obj in bpy.context.scene.objects if obj not in before]
    rigs = [obj for obj in created if obj.type == "ARMATURE"]
    meshes = [obj for obj in created if obj.type == "MESH"]
    if len(rigs) != 1 or len(meshes) != 1:
        raise RuntimeError("Unexpected Quaternius ranger hood import")
    rig, hood = rigs[0], meshes[0]
    rig.name = "FV_HAT_RIG_ranger_hood"
    hood.name = "FV_HAT_ranger_hood"
    replace_material(hood, image_material("FV_MAT_HAT_ranger_hood", RANGER_TEXTURE, 0.76))
    return rig, hood


def export_component(path, rig, objects):
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        export_image_format="WEBP",
        export_image_quality=72,
        export_image_webp_fallback=False,
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_skins=True,
        export_animations=False,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
    )
    return {
        "path": path.relative_to(ASSET_DIR).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main():
    require_sources()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    clear_scene()

    rig, body_source, eyes, brows = import_body()
    body_source.name = "FV_BODY_SOURCE"
    body = extract_weighted_surface(
        body_source,
        "FV_BODY",
        {"Head", "neck_01"},
        image_material("FV_MAT_SKIN_HEAD", BODY_TEXTURE, 0.74),
        0.0,
        0,
    )
    bpy.data.objects.remove(body_source, do_unlink=True)
    outfits = create_outfits()
    hairs = import_hair_modules()
    hood_rig, hood = import_official_hood()
    hats = {"ranger_hood": (hood_rig, [hood])}

    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            for polygon in obj.data.polygons:
                polygon.use_smooth = True

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))

    manifest = {
        "version": 2,
        "license": "Quaternius Universal Base Characters and Modular Character Outfits - Fantasy (CC0 1.0)",
        "source": [
            "https://quaternius.com/packs/universalbasecharacters.html",
            "https://quaternius.com/packs/modularcharacteroutfitsfantasy.html",
        ],
        "core": export_component(OUTPUT_DIR / "core.glb", rig, [body, eyes, brows]),
        "hair": {},
        "outfit": {},
        "hat": {},
    }
    for hair_id, (hair_rig, hair) in hairs.items():
        manifest["hair"][hair_id] = export_component(
            OUTPUT_DIR / "hair" / f"{hair_id}.glb", hair_rig, [hair]
        )
    for outfit_id, (outfit_rig, objects) in outfits.items():
        manifest["outfit"][outfit_id] = export_component(
            OUTPUT_DIR / "outfit" / f"{outfit_id}.glb", outfit_rig, objects
        )
    for hat_id, (hat_rig, objects) in hats.items():
        manifest["hat"][hat_id] = export_component(
            OUTPUT_DIR / "hat" / f"{hat_id}.glb", hat_rig, objects
        )

    manifest_path = OUTPUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    initial = (
        manifest["core"]["bytes"]
        + manifest["hair"]["swept"]["bytes"]
        + manifest["outfit"]["tailored"]["bytes"]
    )
    print(f"FOLLOWVILLE_AVATAR_MANIFEST={manifest_path}")
    print(f"FOLLOWVILLE_AVATAR_CORE_BYTES={manifest['core']['bytes']}")
    print(f"FOLLOWVILLE_AVATAR_INITIAL_DEFAULT_BYTES={initial}")


if __name__ == "__main__":
    main()
