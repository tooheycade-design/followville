"""Refresh Followville's embedded Blender generator from the Git repository.

Run with Blender's auto-execution disabled. The repository must be supplied by
FOLLOWVILLE_REPO_DIR, NEIGHBORHOOD_STATE_DIR, or NEIGHBORHOOD_REPO_DIR. This
script intentionally never guesses a numbered iCloud conflict-copy filename.
"""

import bpy
import hashlib
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime


GENERATOR_NAME = "neighborhood_blender.py"
HASH_PROPERTY = "followville_generator_sha256"
COMMIT_PROPERTY = "followville_generator_commit"


def normalized_source(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def source_hash(text):
    return hashlib.sha256(normalized_source(text).encode("utf-8")).hexdigest()


def resolve_repo():
    configured = (
        os.environ.get("FOLLOWVILLE_REPO_DIR")
        or os.environ.get("NEIGHBORHOOD_STATE_DIR")
        or os.environ.get("NEIGHBORHOOD_REPO_DIR")
    )
    if not configured:
        raise RuntimeError(
            "Repository path is not configured. Set FOLLOWVILLE_REPO_DIR or "
            "NEIGHBORHOOD_STATE_DIR before refreshing the Blend."
        )
    repo = os.path.abspath(os.path.expanduser(configured))
    if not os.path.isdir(os.path.join(repo, ".git")):
        raise RuntimeError("Configured repository is not a Git clone: %s" % repo)
    return repo


def git_revision(repo):
    try:
        revision = subprocess.check_output(
            ["git", "-C", repo, "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        generator_status = subprocess.check_output(
            ["git", "-C", repo, "status", "--porcelain", "--", GENERATOR_NAME],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        return revision + ("-dirty" if generator_status else "")
    except Exception as exc:
        raise RuntimeError("Could not read the repository revision: %s" % exc) from exc


def backup_blend(repo):
    blend_path = os.path.abspath(bpy.data.filepath)
    if not blend_path or not os.path.isfile(blend_path):
        raise RuntimeError("Open the authoritative neighborhood.blend before refreshing")
    backup_dir = os.path.join(repo, "state_backups")
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = os.path.join(
        backup_dir, "neighborhood-pre-generator-refresh-%s.blend1" % stamp
    )
    shutil.copy2(blend_path, backup_path)
    return backup_path


def main():
    repo = resolve_repo()
    generator_path = os.path.join(repo, GENERATOR_NAME)
    if not os.path.isfile(generator_path):
        raise RuntimeError("Canonical generator is missing: %s" % generator_path)

    with open(generator_path, "r", encoding="utf-8-sig", newline=None) as handle:
        source = normalized_source(handle.read())
    if not source.strip():
        raise RuntimeError("Canonical generator is empty: %s" % generator_path)

    digest = source_hash(source)
    revision = git_revision(repo)
    backup_path = backup_blend(repo)

    # Validate and back up everything before replacing the embedded text.
    for text in list(bpy.data.texts):
        if text.name.startswith("neighborhood_blender"):
            bpy.data.texts.remove(text)

    embedded = bpy.data.texts.new(GENERATOR_NAME)
    embedded.write(source)
    embedded.use_module = True
    bpy.context.scene[HASH_PROPERTY] = digest
    bpy.context.scene[COMMIT_PROPERTY] = revision
    bpy.ops.wm.save_mainfile()

    print("FOLLOWVILLE_TEXT_REFRESHED")
    print("SOURCE %s" % generator_path)
    print("SHA256 %s" % digest)
    print("COMMIT %s" % revision)
    print("BACKUP %s" % backup_path)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        print("FOLLOWVILLE_TEXT_REFRESH_FAILED")
        sys.exit(2)
