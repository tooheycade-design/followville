"""Save the freshly rebuilt Followville scene back to the Git Blend.

The guarded launchers run this after the generator and exporter in the same
Blender process.  It refuses any file outside FOLLOWVILLE_REPO_DIR, backs up the
previous Blend inside the repo, stamps state metadata, and then saves.  This
keeps the tracked scene's WORLD snapshot aligned with world_state.json while
preserving its reusable future asset collections.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime

import bpy


def fail(message):
    raise RuntimeError("CANONICAL_BLEND_SAVE_REFUSED: " + message)


def main():
    repo = os.path.abspath(os.environ.get("FOLLOWVILLE_REPO_DIR", ""))
    if not repo or not os.path.isdir(os.path.join(repo, ".git")):
        fail("FOLLOWVILLE_REPO_DIR is not a Git clone")
    expected = os.path.normcase(os.path.join(repo, "neighborhood.blend"))
    current = os.path.normcase(os.path.abspath(bpy.data.filepath))
    if current != expected:
        fail("open Blend is %s, expected %s" % (current, expected))

    state_path = os.path.join(repo, "world_state.json")
    with open(state_path, "rb") as handle:
        raw_state = handle.read()
    state = json.loads(raw_state.decode("utf-8"))
    world = bpy.data.collections.get("WORLD")
    seeds = [int(obj.get("nb_world_seed")) for obj in world.all_objects
             if obj.get("nb_world_seed") is not None] if world else []
    state_seeds = [int(building["seed"]) for building in state["buildings"]]
    if sorted(seeds) != sorted(state_seeds):
        fail("WORLD/state seed coverage differs (%d scene, %d state)" %
             (len(seeds), len(state_seeds)))

    backup_dir = os.path.join(repo, "state_backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = os.path.join(backup_dir,
                          "neighborhood-pre-world-save-%s.blend1" % stamp)
    shutil.copy2(bpy.data.filepath, backup)

    scene = bpy.context.scene
    generator_path = os.path.join(repo, "neighborhood_blender.py")
    with open(generator_path, "r", encoding="utf-8-sig", newline=None) as handle:
        generator_source = handle.read().replace("\r\n", "\n").replace("\r", "\n")
    generator_hash = hashlib.sha256(generator_source.encode("utf-8")).hexdigest()
    for text in list(bpy.data.texts):
        if text.name.startswith("neighborhood_blender"):
            bpy.data.texts.remove(text)
    embedded = bpy.data.texts.new("neighborhood_blender.py")
    embedded.write(generator_source)
    embedded.use_module = True
    revision = subprocess.check_output(
        ["git", "-C", repo, "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(
        ["git", "-C", repo, "status", "--porcelain", "--",
         "neighborhood_blender.py"], text=True).strip()
    scene["followville_generator_sha256"] = generator_hash
    scene["followville_generator_commit"] = revision + ("-dirty" if dirty else "")
    scene["followville_state_day"] = int(state["day"])
    scene["followville_state_population"] = int(state["pop"])
    scene["followville_state_buildings"] = len(state["buildings"])
    scene["followville_state_sha256"] = hashlib.sha256(raw_state).hexdigest()
    scene.frame_set(scene.frame_end)
    bpy.ops.wm.save_mainfile(filepath=os.path.join(repo, "neighborhood.blend"))
    print("CANONICAL_BLEND_SAVED %s" % bpy.data.filepath)
    print("CANONICAL_BLEND_BACKUP %s" % backup)
    print("CANONICAL_BLEND_STATE day=%d population=%d buildings=%d" %
          (state["day"], state["pop"], len(state["buildings"])))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error))
        sys.exit(2)
