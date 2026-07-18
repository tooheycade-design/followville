"""Export curated Quaternius CC0 complete-character looks for Followville.

Sources stay in Codex's integration cache. Outputs are isolated web GLBs under
avatar_assets/avatar_v1/look and never touch the canonical town Blender file.
"""

from pathlib import Path
import hashlib
import json
import re
import bpy


REPO = Path(__file__).resolve().parents[1]
SOURCE = Path(
    r"C:\Users\cadet\.codex\integrations\quaternius-ultimate-animated-characters\Blends"
)
OUTPUT = REPO / "avatar_assets" / "avatar_v1" / "look"
MANIFEST = REPO / "avatar_assets" / "avatar_v1" / "look-manifest.json"

LOOKS = {
    "casual_day_f": "Casual_Female",
    "casual_day_m": "Casual_Male",
    "casual_sky_f": "Casual2_Female",
    "casual_sky_m": "Casual2_Male",
    "casual_lilac_f": "Casual3_Female",
    "casual_lilac_m": "Casual3_Male",
    "casual_bald": "Casual_Bald",
    "suit_f": "Suit_Female",
    "suit_m": "Suit_Male",
    "classy_f": "OldClassy_Female",
    "classy_m": "OldClassy_Male",
    "chef_f": "Chef_Female",
    "chef_m": "Chef_Male",
    "doctor_young_f": "Doctor_Female_Young",
    "doctor_young_m": "Doctor_Male_Young",
    "doctor_senior_f": "Doctor_Female_Old",
    "doctor_senior_m": "Doctor_Male_Old",
    "worker_f": "Worker_Female",
    "worker_m": "Worker_Male",
    "cowboy_f": "Cowboy_Female",
    "cowboy_m": "Cowboy_Male",
    "kimono_f": "Kimono_Female",
    "kimono_m": "Kimono_Male",
    "pirate_f": "Pirate_Female",
    "pirate_m": "Pirate_Male",
    "viking_f": "Viking_Female",
    "viking_m": "Viking_Male",
    "ninja_f": "Ninja_Female",
    "ninja_m": "Ninja_Male",
    "sand_ninja_f": "Ninja_Sand_Female",
    "sand_ninja_m": "Ninja_Sand",
    "gold_knight_f": "Knight_Golden_Female",
    "gold_knight_m": "Knight_Golden_Male",
    "knight_m": "Knight_Male",
    "elf": "Elf",
    "witch": "Witch",
    "wizard": "Wizard",
}


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for collection in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials):
        for datablock in list(collection):
            if datablock.users == 0:
                collection.remove(datablock)


def append_source(path):
    with bpy.data.libraries.load(str(path), link=False) as (available, loaded):
        loaded.objects = available.objects
    objects = []
    for obj in loaded.objects:
        if obj is None or obj.type not in {"MESH", "ARMATURE"}:
            continue
        bpy.context.scene.collection.objects.link(obj)
        if obj.type == "ARMATURE":
            # The Quaternius files open on their authored Idle pose. Preserve
            # that friendly stance as the static bind presentation instead of
            # forcing the source rig back into a wide T-pose.
            obj.data.pose_position = "POSE"
        if obj.type == "MESH":
            for polygon in obj.data.polygons:
                polygon.use_smooth = True
        objects.append(obj)
    return objects


def prepare_materials(objects, look_id):
    seen = set()
    for obj in objects:
        if obj.type != "MESH":
            continue
        for material in obj.data.materials:
            if material is None or material in seen:
                continue
            seen.add(material)
            source_name = material.name.lower()
            safe = re.sub(r"[^a-z0-9]+", "_", source_name).strip("_")
            if "skin" in source_name:
                material.name = f"FV_MAT_SKIN_LOOK_{look_id}"
            elif "hair" in source_name:
                material.name = f"FV_MAT_HAIR_LOOK_{look_id}"
            else:
                material.name = f"FV_MAT_LOOK_{look_id}_{safe}"
            material.roughness = 0.78


def bake_idle_pose(objects):
    """Make the authored frame-zero Idle stance the exported rest pose."""
    armature = next(obj for obj in objects if obj.type == "ARMATURE")
    meshes = [obj for obj in objects if obj.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    bpy.context.scene.frame_set(0)
    bpy.context.view_layer.update()

    # Freeze the evaluated Idle deformation into the mesh before redefining
    # the skeleton's rest pose. This avoids glTF reopening the skinned mesh in
    # its original T-pose while retaining the rig for browser locomotion.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for mesh in meshes:
        evaluated = mesh.evaluated_get(depsgraph)
        baked = bpy.data.meshes.new_from_object(
            evaluated,
            preserve_all_data_layers=True,
            depsgraph=depsgraph,
        )
        mesh.data = baked
        for modifier in list(mesh.modifiers):
            mesh.modifiers.remove(modifier)

    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    armature.animation_data_clear()
    for mesh in meshes:
        modifier = mesh.modifiers.new(name="Followville avatar rig", type="ARMATURE")
        modifier.object = armature


def export_look(look_id, source_name):
    clear_scene()
    source = SOURCE / f"{source_name}.blend"
    if not source.exists():
        raise RuntimeError(f"Missing Quaternius source: {source}")
    objects = append_source(source)
    if not any(obj.type == "ARMATURE" for obj in objects):
        raise RuntimeError(f"No rig found in {source}")
    bake_idle_pose(objects)
    prepare_materials(objects, look_id)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next(obj for obj in objects if obj.type == "ARMATURE")
    path = OUTPUT / f"{look_id}.glb"
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
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
        "path": path.relative_to(REPO / "avatar_assets").as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_model": source_name,
    }


def main():
    manifest = {
        "version": 1,
        "license": "Quaternius Ultimate Animated Character Pack (CC0 1.0)",
        "source": "https://quaternius.com/packs/ultimatedanimatedcharacter.html",
        "looks": {},
    }
    for look_id, source_name in LOOKS.items():
        manifest["looks"][look_id] = export_look(look_id, source_name)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    total = sum(item["bytes"] for item in manifest["looks"].values())
    print(f"FOLLOWVILLE_LOOK_COUNT={len(LOOKS)}")
    print(f"FOLLOWVILLE_LOOK_LIBRARY_BYTES={total}")
    print(f"FOLLOWVILLE_LOOK_MANIFEST={MANIFEST}")


if __name__ == "__main__":
    main()
