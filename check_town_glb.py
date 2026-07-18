#!/usr/bin/env python3
"""
FOLLOWER NEIGHBORHOOD -- town.glb sanity check
===============================================
Standalone, no-Blender-needed check for the full GLB, stream manifest/chunks,
and the exact regression class behind the
2026-07-08 "pancaked houses" incident (pond + 3 new houses shipped to the live
site with every mesh part squashed to scale ~0.001, baked in by a stale
keyframe animation surviving into duplicates_make_real() -- see CLAUDE.md's
Web viewer section for the full story).

export_web.py now has its OWN in-Blender copy of this exact check (it raises
and fails the Blender process if it finds anything squashed), so under the
normal local pipeline this should never trigger. This script exists as a
SECOND, independent line of defense that doesn't need Blender at all -- it's
meant to run in CI (see the GitHub Action workflow) against whatever town.glb
is actually sitting in the repo, so a bad export can never reach the live
site even if it somehow got committed without going through export_web.py's
own check (e.g. a hand-edited/replaced file, a future refactor that drops the
in-Blender check, etc.).

Usage:
    python3 check_town_glb.py [path/to/town.glb] [path/to/world_state.json]

Both arguments are optional -- defaults to town.glb / world_state.json next
to this script. Exits 0 if everything looks fine, exits 1 (with a clear
message on stdout) if it finds a problem. Requires: pip install pygltflib
"""

import sys
import os
import json
import math
import hashlib

from neighborhood_plan import PLAN as SUBURBAN_PLAN
from world_layout import walk_surface_manifest

try:
    from pygltflib import GLTF2
except ImportError:
    print("check_town_glb.py: pygltflib is required -- pip install pygltflib")
    sys.exit(1)

SQUASH_THRESHOLD = 0.05  # anything with |scale| below this on any axis is "pancaked"
FEATURE_ROAD_MATERIALS = {"NB_road", "NB_story_transition", "NB_story_road"}


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_asset_record(root, record, label, minimum_roots=1):
    problems = []
    if not isinstance(record, dict) or not record.get("file"):
        return ["%s has no asset record" % label]
    path = os.path.normpath(os.path.join(root, record["file"]))
    if os.path.commonpath([root, path]) != root:
        return ["%s points outside the repository: %s" % (label, record["file"])]
    if not os.path.exists(path):
        return ["%s is missing: %s" % (label, path)]
    size = os.path.getsize(path)
    if size != record.get("bytes"):
        problems.append("%s byte count is stale (%r in manifest, %d on disk)" %
                        (label, record.get("bytes"), size))
    digest = file_sha256(path)
    if digest != record.get("sha256"):
        problems.append("%s SHA-256 is stale or incorrect" % label)
    gltf = GLTF2().load(path)
    if not gltf.nodes:
        problems.append("%s has zero nodes" % label)
        return problems
    scene = gltf.scenes[gltf.scene] if gltf.scene is not None else gltf.scenes[0]
    if len(scene.nodes or []) < minimum_roots:
        problems.append("%s has %d scene root(s), expected at least %d" %
                        (label, len(scene.nodes or []), minimum_roots))
    squashed = find_squashed_nodes(gltf)
    if squashed:
        problems.append("%s contains %d squashed node(s): %s" %
                        (label, len(squashed), ", ".join(squashed[:10])))
    return problems


def check_stream_manifest(root, state, fallback_path):
    problems = []
    manifest_path = os.path.join(root, "town_manifest.json")
    if not os.path.exists(manifest_path):
        return ["town_manifest.json is missing -- district streaming assets were not exported"]
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("version") != 1:
        problems.append("town_manifest.json has unsupported version %r" % manifest.get("version"))

    buildings = state.get("buildings") or []
    state_ids = {int(building["seed"]) for building in buildings}
    state_house_ids = {int(building["seed"]) for building in buildings
                       if str(building.get("type", "")).endswith("house")}
    meta = manifest.get("state") or {}
    expected_meta = {
        "day": state.get("day"), "population": state.get("pop"),
        "building_count": len(buildings), "seed_counter": state.get("seed_counter")
    }
    for key, value in expected_meta.items():
        if meta.get(key) != value:
            problems.append("manifest state.%s is %r, expected %r" % (key, meta.get(key), value))

    fallback = manifest.get("fallback") or {}
    if os.path.normpath(os.path.join(root, fallback.get("file", ""))) != os.path.normpath(fallback_path):
        problems.append("manifest fallback does not point to the checked town.glb")
    problems.extend(check_asset_record(root, fallback, "fallback town.glb"))
    problems.extend(check_asset_record(root, manifest.get("base"), "stream base"))

    chunks = manifest.get("chunks") or []
    chunk_ids = [chunk.get("id") for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        problems.append("manifest contains duplicate chunk IDs")
    if "original-town" not in chunk_ids:
        problems.append("manifest has no original-town chunk")
    if not any(chunk.get("initial") for chunk in chunks):
        problems.append("manifest has no initial district chunk")
    load_distance = (manifest.get("streaming") or {}).get("detail_load_distance")
    if not isinstance(load_distance, (int, float)) or not 25 <= load_distance <= 250:
        problems.append("manifest streaming.detail_load_distance is missing or unsafe")
    unload_distance = (manifest.get("streaming") or {}).get("detail_unload_distance")
    if (not isinstance(load_distance, (int, float)) or
            not isinstance(unload_distance, (int, float)) or
            not load_distance < unload_distance <= 400):
        problems.append("manifest streaming.detail_unload_distance is missing or unsafe")
    if manifest.get("walk_surfaces") != walk_surface_manifest(state):
        problems.append("manifest walk surfaces are missing or stale for world_state.json")

    seen_ids = []
    seen_house_ids = []
    for chunk in chunks:
        chunk_id = chunk.get("id") or "<unnamed>"
        building_ids = [int(value) for value in chunk.get("building_ids") or []]
        house_ids = [int(value) for value in chunk.get("house_ids") or []]
        seen_ids.extend(building_ids)
        seen_house_ids.extend(house_ids)
        if not set(house_ids).issubset(set(building_ids)):
            problems.append("chunk %s has house IDs outside its building IDs" % chunk_id)
        bounds = chunk.get("bounds") or {}
        if len(bounds.get("center") or []) != 2 or not isinstance(bounds.get("radius"), (int, float)):
            problems.append("chunk %s has invalid bounds" % chunk_id)
        problems.extend(check_asset_record(
            root, chunk.get("asset"), "chunk %s" % chunk_id,
            minimum_roots=max(1, len(building_ids))))

    if len(seen_ids) != len(set(seen_ids)):
        problems.append("one or more building IDs appear in multiple chunks")
    if set(seen_ids) != state_ids:
        missing = sorted(state_ids - set(seen_ids))
        extra = sorted(set(seen_ids) - state_ids)
        problems.append("chunk building coverage mismatch (missing=%s extra=%s)" %
                        (missing[:12], extra[:12]))
    if set(seen_house_ids) != state_house_ids:
        problems.append("chunk house coverage does not match canonical claimable-home geometry")
    return problems


def find_squashed_nodes(gltf):
    """Walk every node in the default scene and flag any whose scale has a
    near-zero component on any axis -- the exact signature of an object
    exported mid-rise-animation instead of at its fully-grown resting pose."""
    squashed = []
    node_list = gltf.nodes

    def walk(idx):
        node = node_list[idx]
        scale = node.scale or [1, 1, 1]
        if any(abs(v) < SQUASH_THRESHOLD for v in scale):
            squashed.append(node.name or ("<unnamed node %d>" % idx))
        for child in (node.children or []):
            walk(child)

    scene = gltf.scenes[gltf.scene] if gltf.scene is not None else gltf.scenes[0]
    for root in scene.nodes:
        walk(root)
    return squashed


def find_feature_road_outliers(gltf):
    """Reject feature-road vertices evaluated in the asset's local XY frame.

    Kaleidoscope Crest is built around local z=0..3 and then instanced at its
    world position. Applying the regional terrain function before that parent
    transform produces the long floating beam captured in Zach's screenshots.
    """
    outliers = []
    seen_materials = set()
    for node in gltf.nodes:
        if not node.name or "kaleidoscope_crest_street" not in node.name:
            continue
        if node.mesh is None:
            continue
        for primitive in gltf.meshes[node.mesh].primitives:
            if primitive.material is None:
                continue
            material_name = gltf.materials[primitive.material].name or ""
            if material_name not in FEATURE_ROAD_MATERIALS:
                continue
            seen_materials.add(material_name)
            accessor = gltf.accessors[primitive.attributes.POSITION]
            minimum, maximum = accessor.min or [], accessor.max or []
            if len(minimum) < 2 or len(maximum) < 2:
                outliers.append("%s has no position bounds" % material_name)
            elif minimum[1] < -0.05 or maximum[1] > 3.25:
                outliers.append("%s local vertical range %.3f..%.3f" %
                                (material_name, minimum[1], maximum[1]))
    missing = FEATURE_ROAD_MATERIALS - seen_materials
    if missing:
        outliers.append("missing feature-road material(s): %s" % ", ".join(sorted(missing)))
    return outliers


def check(glb_path, state_path):
    problems = []

    if not os.path.exists(glb_path):
        problems.append("town.glb not found at %s" % glb_path)
        return problems

    gltf = GLTF2().load(glb_path)

    if not gltf.nodes:
        problems.append("town.glb has zero nodes -- looks like an empty/failed export")
        return problems

    squashed = find_squashed_nodes(gltf)
    if squashed:
        problems.append(
            "%d node(s) exported with a near-zero scale on some axis (pancaked): %s%s"
            % (len(squashed), ", ".join(squashed[:15]),
               " ... (%d more)" % (len(squashed) - 15) if len(squashed) > 15 else "")
        )

    feature_road_outliers = find_feature_road_outliers(gltf)
    if feature_road_outliers:
        problems.append("Kaleidoscope feature road escaped its authored elevation: %s" %
                        "; ".join(feature_road_outliers))

    if os.path.exists(state_path):
        with open(state_path, encoding="utf-8") as f:
            state = json.load(f)
        day = state.get("day")
        pop = state.get("pop")
        buildings = state.get("buildings", [])
        if day is None or day < 0:
            problems.append("world_state.json has a missing/invalid 'day': %r" % day)
        if pop is None or pop < 0:
            problems.append("world_state.json has a missing/invalid 'pop': %r" % pop)
        if buildings and len(gltf.nodes) < len(buildings):
            problems.append(
                "world_state.json lists %d building(s) but town.glb only has %d node(s) "
                "total -- export looks incomplete" % (len(buildings), len(gltf.nodes))
            )
        planned_slots = {slot["plan_id"]: slot for slot in SUBURBAN_PLAN["houses"]}
        for building in buildings:
            plan_id = building.get("plan_id")
            if not plan_id:
                continue
            slot = planned_slots.get(plan_id)
            if slot is None:
                problems.append("building has unknown suburban plan_id %r" % plan_id)
                continue
            if math.hypot(building.get("px", 0) - slot["x"],
                          building.get("py", 0) - slot["y"]) > 0.01:
                problems.append("planned house %d has drifted off its validated frontage" % plan_id)
            angle_delta = (building.get("rot", 0) - slot["rot"] + math.pi) % (2 * math.pi) - math.pi
            if abs(angle_delta) > 0.001:
                problems.append("planned house %d no longer faces its road" % plan_id)
        problems.extend(check_stream_manifest(os.path.dirname(os.path.abspath(glb_path)),
                                              state, os.path.abspath(glb_path)))
    else:
        problems.append("world_state.json not found at %s (skipping day/pop cross-check)" % state_path)

    return problems


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    glb_path = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(here, "town.glb")
    state_path = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(here, "world_state.json")

    problems = check(glb_path, state_path)

    if problems:
        print("check_town_glb.py: FAILED")
        for p in problems:
            print("  - " + p)
        sys.exit(1)

    print("check_town_glb.py: OK -- full GLB + streamed chunks are complete and state-consistent")
    sys.exit(0)


if __name__ == "__main__":
    main()
