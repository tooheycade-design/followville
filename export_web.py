"""
FOLLOWER NEIGHBORHOOD — glTF export for the web viewer
=======================================================
Exports the CURRENT built world (the "WORLD" collection that
neighborhood_blender.py just rebuilt) as a complete town.glb fallback plus a
hashed, Draco-compressed base/district stream manifest next to
world_state.json. The browser receives the exact same geometry Blender just
rendered with no hand-ported house shapes or world drift.

Run this AFTER neighborhood_blender.py has rebuilt the world in the same
Blender session (same --python invocation, or immediately after in the GUI).
It does NOT save the .blend file, so it's always safe to run — any changes
it makes (realizing instances into real meshes) only exist in this throwaway
Blender process and vanish when it exits.

Command-line usage (bolt this onto the end of your existing grow.sh call):
  blender --background neighborhood.blend \\
      --python neighborhood_blender.py -- +5 --render \\
      --python export_web.py

Or standalone, to just re-export the current .blend's world without regrowing:
  blender --background neighborhood.blend --python export_web.py
"""

import bpy
import hashlib
import json
import math
import os

from world_layout import transform_building_point, walk_surface_manifest

LOT = 13
BLOCK_N = 3
ROAD = 6
PITCH = BLOCK_N * LOT + ROAD


def _chunk_id_for_building(building):
    district = str(building.get("district") or "").strip().lower()
    if district:
        slug = "".join(ch if ch.isalnum() else "-" for ch in district)
        return "-".join(part for part in slug.split("-") if part)
    if building.get("type") in ("ringhouse", "parkdistrict"):
        return "founder-park"
    return "original-town"


def _building_xz(building):
    if "px" in building:
        x, y = transform_building_point(building)
    else:
        gx, gy = int(building["gx"]), int(building["gy"])
        bx, ix = divmod(gx, BLOCK_N)
        by, iy = divmod(gy, BLOCK_N)
        x = bx * PITCH + ix * LOT + LOT / 2
        y = by * PITCH + iy * LOT + LOT / 2
        size = 3 if building.get("type") in ("elementaryschool", "followmart") else 1
        x += (size - 1) * LOT / 2
        y += (size - 1) * LOT / 2
    return x, -y  # Three.js glTF coordinates: Blender +Y becomes Three -Z.


def _descendants(root):
    found, stack = [], list(root.children)
    while stack:
        child = stack.pop()
        found.append(child)
        stack.extend(child.children)
    return found


def _select(objects):
    bpy.ops.object.select_all(action="DESELECT")
    selected = [obj for obj in objects if obj and obj.name in bpy.context.view_layer.objects]
    for obj in selected:
        obj.hide_select = False
        obj.hide_viewport = False
        obj.select_set(True)
    bpy.context.view_layer.objects.active = selected[0] if selected else None
    return selected


def _export_glb(path, objects, draco=False):
    selected = _select(objects)
    if not selected:
        raise RuntimeError("STREAM_EXPORT_FAILED: no objects selected for %s" % path)
    options = dict(
        filepath=path,
        export_format="GLB",
        use_selection=True,
        export_apply=True,
        export_yup=True,
        export_lights=False,
        export_cameras=False,
        export_animations=False,
        export_materials="EXPORT",
        export_extras=True,
    )
    if draco:
        options.update(
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
        )
    bpy.ops.export_scene.gltf(**options)
    print("export_web.py: wrote", path)


def _asset_record(base, path, compression=None):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    record = {
        "file": os.path.relpath(path, base).replace(os.sep, "/"),
        "bytes": os.path.getsize(path),
        "sha256": digest.hexdigest(),
    }
    if compression:
        record["compression"] = compression
    return record


def _chunk_bounds(buildings):
    points = [_building_xz(building) for building in buildings]
    center_x = sum(point[0] for point in points) / len(points)
    center_z = sum(point[1] for point in points) / len(points)
    radius = max(math.hypot(x - center_x, z - center_z) for x, z in points) + 18
    return {"center": [round(center_x, 3), round(center_z, 3)], "radius": round(radius, 3)}

def export_web_glb():
    col = bpy.data.collections.get("WORLD")
    if col is None:
        print("export_web.py: no WORLD collection found — run neighborhood_blender.py first.")
        return None

    # 2026-07-10: exclude one-off celebration fireworks from the website export.
    # build_fireworks() (neighborhood_blender.py) adds short-lived animated burst
    # particles named "fw"/"fw.001"/... to the WORLD collection for --celebrate
    # videos only -- they're meant to be invisible (scale ~0) except during their
    # few-frame burst window. The scale-reset loop below (needed to fix pancaked
    # houses, see the 2026-07-08 PITFALL note) forces EVERY WORLD object to scale
    # (1,1,1), which also permanently un-shrinks these firework particles at
    # their fully-exploded positions -- without this, they get baked into
    # town.glb and show up on the live website as a frozen cluster of debris
    # floating in the sky forever. Fireworks are a video-only effect; delete
    # them before anything below touches scale or exports.
    fw_objs = [obj for obj in list(col.objects)
               if obj.name == "fw" or obj.name.startswith("fw.")]
    for obj in fw_objs:
        bpy.data.objects.remove(obj, do_unlink=True)
    if fw_objs:
        print("export_web.py: excluded %d firework particle(s) from the website export" % len(fw_objs))

    # Jump to the LAST frame of the daily rise/sink animation before touching
    # anything. New buildings animate up from flattened (scale.z ~0.001) to
    # full height over the clip, and whatever frame the scene happens to be
    # sitting on when this loads gets baked into the export. Without this,
    # the newest houses can export "pancaked" mid-rise. frame_end is already
    # set correctly by setup_render() in the just-saved .blend, so this alone
    # guarantees every object is captured in its fully-grown resting pose.
    scene = bpy.context.scene
    scene.frame_set(scene.frame_end)

    # Select everything in WORLD (this includes the collection-instance empties
    # for every building/tree/car/etc AND the plain road/ground meshes).
    #
    # PITFALL (fixed 2026-07-08, don't reintroduce): frame_set() above is NOT
    # enough by itself for objects that were just animated with animate_rise()
    # THIS SAME run (i.e. today's newest buildings). Those objects still carry
    # a live Action with scale keyframes. duplicates_make_real() below forces a
    # depsgraph re-evaluation, and if any animation data is still attached to
    # an object, that re-evaluation reasserts the F-curve's value and silently
    # overwrites a plain `obj.scale = (1,1,1)` Python assignment right back to
    # whatever frame the curve lands on -- in the day-7 pond+houses incident,
    # every mesh part of the newest batch came out of the export at scale
    # (1, 0.001, 1), the exact frame-1 "not risen yet" value, even though this
    # scale reset AND the frame_end jump above both ran. Older buildings never
    # showed this because in later runs they're placed with no animate_rise()
    # call at all (only THIS run's new_batch gets animated), so they have no
    # Action to reassert anything from. The fix: strip the animation data
    # outright with animation_data_clear() so there is no F-curve left that
    # could ever override the manual reset, regardless of evaluation order.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in col.objects:
        obj.hide_select = False
        obj.hide_viewport = False
        obj.animation_data_clear()   # remove any Action so nothing can reassert scale/visibility
        # Most objects rest at unit scale. Planned suburban lots may carry a
        # deliberate compact footprint in nb_rest_scale; preserve it while
        # still defeating any residual mid-rise animation scale.
        obj.scale = tuple(obj.get("nb_rest_scale", (1.0, 1.0, 1.0)))
        obj.select_set(True)
    bpy.context.view_layer.objects.active = col.objects[0] if col.objects else None

    # Bake every collection-instance empty into real, exportable mesh data.
    # (glTF export of raw collection-instancer empties is unreliable across
    # Blender versions, so we realize them first — this only touches the
    # in-memory scene of this throwaway process, never the saved .blend.)
    bpy.ops.object.duplicates_make_real(use_base_parent=True, use_hierarchy=True)

    # SANITY CHECK (added 2026-07-08, after the pancaked-houses incident): don't
    # just trust the fixes above -- verify. Any realized object with a
    # near-zero scale on ANY axis is exactly what a pancaked/mid-rise export
    # looks like, and the day-7 pond+houses bug shipped silently for a full day
    # before anyone noticed on the live site. Fail loudly here instead: raise,
    # so Blender exits non-zero, so grow_windows.ps1/grow.sh's existing
    # "non-zero exit = ALL_FAILED" handling catches it automatically, before
    # anything gets deployed.
    THRESH = 0.05
    squashed = [obj.name for obj in col.objects
                if any(abs(v) < THRESH for v in obj.scale)]
    if squashed:
        msg = ("SANITY_CHECK_FAILED: %d object(s) exported with a near-zero "
               "scale (pancaked): %s" % (len(squashed), ", ".join(squashed[:10])))
        print(msg)
        raise RuntimeError(msg)

    # Re-select the whole WORLD collection (now full of real meshes) for export.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in col.objects:
        obj.select_set(True)

    # The Kaleidoscope access road is authored in the feature asset's local
    # 0..3m vertical frame, then parented at its world position. Applying the
    # regional terrain function to those local coordinates creates a huge
    # floating ribbon after the parent transform. Refuse to export that exact
    # regression class; this runs on every normal Blender-to-web export.
    feature_road_materials = {"NB_road", "NB_story_transition", "NB_story_road"}
    feature_meshes = []
    feature_outliers = []
    for obj in col.objects:
        if obj.type != "MESH":
            continue
        material_names = {slot.material.name for slot in obj.material_slots if slot.material}
        if "NB_story_transition" not in material_names:
            continue
        feature_meshes.append(obj.name)
        for polygon in obj.data.polygons:
            if polygon.material_index >= len(obj.material_slots):
                continue
            material = obj.material_slots[polygon.material_index].material
            if not material or material.name not in feature_road_materials:
                continue
            for vertex_index in polygon.vertices:
                z = obj.data.vertices[vertex_index].co.z
                if z < -.05 or z > 3.25:
                    feature_outliers.append((obj.name, material.name, z))
                    break
    if not feature_meshes:
        raise RuntimeError("FEATURE_ROAD_CHECK_FAILED: Kaleidoscope access mesh missing")
    if feature_outliers:
        sample = ", ".join("%s/%s z=%.3f" % item for item in feature_outliers[:8])
        raise RuntimeError("FEATURE_ROAD_CHECK_FAILED: authored elevation escaped: " + sample)

    # Same NEIGHBORHOOD_STATE_DIR override as neighborhood_blender.py's
    # state_path() -- if set, town.glb is written straight into the git repo
    # clone alongside world_state.json instead of next to the .blend, so the
    # git commit/push step (see grow_windows.ps1) has both files ready with no
    # separate copy step. Unset = old behavior, unchanged.
    base = (os.environ.get("NEIGHBORHOOD_STATE_DIR")
            or (os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~")))
    out_path = os.path.join(base, "town.glb")

    # Keep the monolithic GLB as a production fallback.  Chunk streaming is an
    # optimization layer, never the only copy of the town.
    all_objects = list(col.objects)
    _export_glb(out_path, all_objects)

    state_path = os.path.join(base, "world_state.json")
    with open(state_path, "r", encoding="utf-8") as handle:
        state = json.load(handle)
    buildings = list(state.get("buildings") or [])
    canonical_ids = {int(building["seed"]) for building in buildings}

    # Realized building roots retain the export tags written by
    # neighborhood_blender.py.  Their complete descendant trees become the
    # district assets; everything else (terrain, all revealed roads, nature,
    # traffic, lamps, and public feature dressing) stays in the base asset.
    tagged_roots = [obj for obj in col.objects
                    if obj.get("nb_world_seed") is not None and obj.get("nb_web_chunk")]
    root_by_seed = {}
    for root in tagged_roots:
        seed = int(root.get("nb_world_seed"))
        if seed in canonical_ids and seed not in root_by_seed:
            root_by_seed[seed] = root
    missing = sorted(canonical_ids - set(root_by_seed))
    if missing:
        raise RuntimeError(
            "STREAM_EXPORT_FAILED: %d canonical building root(s) missing export tags: %s" %
            (len(missing), ", ".join(str(seed) for seed in missing[:12])))

    tagged_objects = set()
    for root in tagged_roots:
        tagged_objects.add(root)
        tagged_objects.update(_descendants(root))
    base_objects = [obj for obj in col.objects if obj not in tagged_objects]

    chunk_dir = os.path.join(base, "town_chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    base_path = os.path.join(chunk_dir, "base.glb")
    _export_glb(base_path, base_objects, draco=True)

    grouped = {}
    for building in buildings:
        grouped.setdefault(_chunk_id_for_building(building), []).append(building)

    chunk_records = []
    # Original town frames the first view, Creekside borders the player spawn,
    # and Kaleidoscope is a current hero district with runtime geometry audits.
    # Await all three so the loading screen never reveals a nearby proxy pop.
    initial_ids = {"original-town", "creekside-bend", "kaleidoscope-crest"}
    for chunk_id in sorted(grouped):
        chunk_buildings = grouped[chunk_id]
        chunk_objects = []
        for building in chunk_buildings:
            root = root_by_seed[int(building["seed"])]
            chunk_objects.append(root)
            chunk_objects.extend(_descendants(root))
        chunk_path = os.path.join(chunk_dir, chunk_id + ".glb")
        _export_glb(chunk_path, chunk_objects, draco=True)
        districts = sorted({str(building.get("district")) for building in chunk_buildings
                            if building.get("district")})
        label = ("Founder Park" if chunk_id == "founder-park" else
                 "Original town" if chunk_id == "original-town" else
                 (districts[0] if len(districts) == 1 else chunk_id.replace("-", " ").title()))
        building_ids = sorted(int(building["seed"]) for building in chunk_buildings)
        house_ids = sorted(int(building["seed"]) for building in chunk_buildings
                           if str(building.get("type", "")).endswith("house"))
        chunk_records.append({
            "id": chunk_id,
            "label": label,
            "initial": chunk_id in initial_ids,
            "bounds": _chunk_bounds(chunk_buildings),
            "building_ids": building_ids,
            "house_ids": house_ids,
            "asset": _asset_record(base, chunk_path, compression="draco"),
        })

    # Keep the generated directory canonical. A renamed/removed district must
    # not leave an orphaned GLB that future deployments carry forever.
    expected_chunk_files = {"base.glb"}
    expected_chunk_files.update(record["asset"]["file"].split("/")[-1]
                                for record in chunk_records)
    for filename in os.listdir(chunk_dir):
        path = os.path.join(chunk_dir, filename)
        if filename.lower().endswith(".glb") and filename not in expected_chunk_files:
            os.remove(path)

    manifest = {
        "version": 1,
        "state": {
            "day": state.get("day"),
            "population": state.get("pop"),
            "building_count": len(buildings),
            "seed_counter": state.get("seed_counter"),
        },
        "base": _asset_record(base, base_path, compression="draco"),
        "chunks": chunk_records,
        "streaming": {
            "detail_load_distance": 70,
            "detail_unload_distance": 112,
            "lod": "simple-houses",
        },
        "walk_surfaces": walk_surface_manifest(state),
        "fallback": _asset_record(base, out_path),
    }
    manifest_path = os.path.join(base, "town_manifest.json")
    temporary_path = manifest_path + ".tmp"
    with open(temporary_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary_path, manifest_path)
    print("export_web.py: wrote", manifest_path)
    print("export_web.py: stream manifest covers %d buildings across %d chunks" %
          (len(canonical_ids), len(chunk_records)))
    return out_path

if __name__ == "__main__":
    export_web_glb()
