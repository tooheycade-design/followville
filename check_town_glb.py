#!/usr/bin/env python3
"""
FOLLOWER NEIGHBORHOOD -- town.glb sanity check
===============================================
Standalone, no-Blender-needed check for the exact regression class behind the
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

from neighborhood_plan import PLAN as SUBURBAN_PLAN

try:
    from pygltflib import GLTF2
except ImportError:
    print("check_town_glb.py: pygltflib is required -- pip install pygltflib")
    sys.exit(1)

SQUASH_THRESHOLD = 0.05  # anything with |scale| below this on any axis is "pancaked"


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

    if os.path.exists(state_path):
        with open(state_path) as f:
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
    else:
        problems.append("world_state.json not found at %s (skipping day/pop cross-check)" % state_path)

    return problems


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    glb_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "town.glb")
    state_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "world_state.json")

    problems = check(glb_path, state_path)

    if problems:
        print("check_town_glb.py: FAILED")
        for p in problems:
            print("  - " + p)
        sys.exit(1)

    print("check_town_glb.py: OK -- no squashed nodes, state file consistent")
    sys.exit(0)


if __name__ == "__main__":
    main()
