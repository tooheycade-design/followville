"""Build and verify Followville's licensed local asset catalog.

This script is intentionally independent from the town generator. It copies
approved source assets into a review library, records their provenance and
hashes, and never edits world_state.json, Blender scenes, or runtime catalogs.

Usage with Blender's bundled Python::

    python scripts/build_asset_library.py sync kenney-furniture-kit
    python scripts/build_asset_library.py verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
REGISTRY_PATH = REPO / "assets" / "asset_sources.json"
MANIFEST_PATH = REPO / "assets" / "asset_library_manifest.json"
GLB_JSON_CHUNK = 0x4E4F534A


class AssetLibraryError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snake_case(value: str) -> str:
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", value)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    value = re.sub(r"[^A-Za-z0-9]+", "_", value)
    return value.strip("_").lower()


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("sources"), list):
        raise AssetLibraryError("asset_sources.json must contain version 1 and a sources array")
    seen: set[str] = set()
    for source in data["sources"]:
        required = {"id", "title", "creator", "source_urls", "license", "license_url", "web_safe"}
        missing = required.difference(source)
        if missing:
            raise AssetLibraryError(f"{source.get('id', '<unknown>')} is missing {sorted(missing)}")
        if source["id"] in seen:
            raise AssetLibraryError(f"duplicate source id {source['id']}")
        if source["license"] != "CC0-1.0" or source["web_safe"] is not True:
            raise AssetLibraryError(
                f"{source['id']} is not approved for the browser-safe library; only verified CC0-1.0 sources qualify"
            )
        seen.add(source["id"])
    return data


def source_by_id(registry: dict, source_id: str) -> dict:
    for source in registry["sources"]:
        if source["id"] == source_id:
            return source
    raise AssetLibraryError(f"unknown asset source {source_id}")


def external_source_path(import_spec: dict) -> Path:
    configured = os.environ.get(import_spec["environment_variable"])
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / import_spec["default_source"]).resolve()


def safe_repo_path(relative: str) -> Path:
    candidate = (REPO / relative).resolve()
    if REPO != candidate and REPO not in candidate.parents:
        raise AssetLibraryError(f"path leaves repository: {relative}")
    return candidate


def copy_if_changed(source: Path, destination: Path) -> bool:
    if destination.exists() and destination.stat().st_size == source.stat().st_size:
        if sha256(destination) == sha256(source):
            return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def sync_catalog(source: dict) -> tuple[int, int]:
    spec = source.get("catalog_import")
    if not spec:
        raise AssetLibraryError(f"{source['id']} has no catalog_import recipe")
    root = external_source_path(spec)
    models = root / spec["model_directory"]
    previews = root / spec["preview_directory"]
    license_file = root / spec["license_file"]
    if not models.is_dir() or not previews.is_dir() or not license_file.is_file():
        raise AssetLibraryError(f"source cache is incomplete at {root}")
    license_text = license_file.read_text(encoding="utf-8", errors="replace").lower()
    if "creative commons zero" not in license_text and "cc0" not in license_text:
        raise AssetLibraryError(f"source license does not identify CC0: {license_file}")

    target = safe_repo_path(spec["target_directory"])
    model_files = sorted(models.glob("*.glb"), key=lambda path: path.name.lower())
    if not model_files:
        raise AssetLibraryError(f"no GLB models found in {models}")
    changed = 0
    expected: set[str] = set()
    for model in model_files:
        asset_id = snake_case(model.stem)
        preview = previews / f"{model.stem}.png"
        if not preview.is_file():
            raise AssetLibraryError(f"missing preview for {model.name}")
        model_target = target / f"{asset_id}.glb"
        preview_target = target / f"{asset_id}.png"
        changed += int(copy_if_changed(model, model_target))
        changed += int(copy_if_changed(preview, preview_target))
        expected.update({model_target.name, preview_target.name})

    extras = sorted(
        path.name for path in target.iterdir()
        if path.is_file() and path.suffix.lower() in {".glb", ".png"} and path.name not in expected
    )
    if extras:
        raise AssetLibraryError(
            "catalog contains files no longer supplied by the source; review manually instead of auto-deleting: "
            + ", ".join(extras)
        )
    return len(model_files), changed


def glb_metadata(path: Path) -> dict:
    with path.open("rb") as stream:
        header = stream.read(12)
        if len(header) != 12:
            raise AssetLibraryError(f"truncated GLB: {path}")
        magic, version, total_length = struct.unpack("<III", header)
        if magic != 0x46546C67 or version != 2 or total_length != path.stat().st_size:
            raise AssetLibraryError(f"invalid GLB 2 header: {path}")
        document = None
        while stream.tell() < total_length:
            chunk_header = stream.read(8)
            if len(chunk_header) != 8:
                raise AssetLibraryError(f"truncated GLB chunk: {path}")
            length, chunk_type = struct.unpack("<II", chunk_header)
            payload = stream.read(length)
            if len(payload) != length:
                raise AssetLibraryError(f"truncated GLB payload: {path}")
            if chunk_type == GLB_JSON_CHUNK:
                document = json.loads(payload.rstrip(b" \t\r\n\0").decode("utf-8"))
        if document is None:
            raise AssetLibraryError(f"GLB has no JSON chunk: {path}")

    accessors = document.get("accessors", [])
    vertex_count = 0
    triangle_count = 0
    primitive_count = 0
    bounds_min = [float("inf")] * 3
    bounds_max = [float("-inf")] * 3
    has_bounds = False
    for mesh in document.get("meshes", []):
        for primitive in mesh.get("primitives", []):
            primitive_count += 1
            position_index = primitive.get("attributes", {}).get("POSITION")
            if isinstance(position_index, int) and 0 <= position_index < len(accessors):
                accessor = accessors[position_index]
                vertex_count += int(accessor.get("count", 0))
                if len(accessor.get("min", [])) >= 3 and len(accessor.get("max", [])) >= 3:
                    has_bounds = True
                    for axis in range(3):
                        bounds_min[axis] = min(bounds_min[axis], float(accessor["min"][axis]))
                        bounds_max[axis] = max(bounds_max[axis], float(accessor["max"][axis]))
            index = primitive.get("indices")
            if isinstance(index, int) and 0 <= index < len(accessors):
                triangle_count += int(accessors[index].get("count", 0)) // 3
            elif isinstance(position_index, int) and 0 <= position_index < len(accessors):
                triangle_count += int(accessors[position_index].get("count", 0)) // 3
    result = {
        "meshes": len(document.get("meshes", [])),
        "primitives": primitive_count,
        "vertices": vertex_count,
        "triangles": triangle_count,
    }
    if has_bounds:
        result["accessor_bounds"] = {
            "min": [round(value, 5) for value in bounds_min],
            "max": [round(value, 5) for value in bounds_max],
        }
    return result


def png_dimensions(path: Path) -> list[int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssetLibraryError(f"invalid PNG: {path}")
    return list(struct.unpack(">II", header[16:24]))


def matching_files(pattern: str) -> list[Path]:
    return sorted((path for path in REPO.glob(pattern) if path.is_file()), key=lambda path: path.as_posix())


def build_manifest(registry: dict) -> dict:
    assets: list[dict] = []
    owners: dict[str, str] = {}
    for source in registry["sources"]:
        files: list[Path] = []
        for pattern in source.get("managed_globs", []):
            matched = matching_files(pattern)
            if not matched:
                raise AssetLibraryError(f"{source['id']} pattern matched no files: {pattern}")
            files.extend(matched)
        for path in sorted(set(files), key=lambda item: item.as_posix()):
            relative = path.relative_to(REPO).as_posix()
            previous = owners.get(relative)
            if previous:
                raise AssetLibraryError(f"{relative} belongs to both {previous} and {source['id']}")
            owners[relative] = source["id"]
            record = {
                "path": relative,
                "source": source["id"],
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            if path.suffix.lower() == ".glb":
                record["model"] = glb_metadata(path)
            elif path.suffix.lower() == ".png":
                record["image"] = {"dimensions": png_dimensions(path)}
            assets.append(record)
    assets.sort(key=lambda item: item["path"])
    return {
        "version": 1,
        "policy": "Only locally hosted, provenance-recorded CC0-1.0 assets are admitted to this browser-safe library.",
        "sources": [
            {
                key: source[key]
                for key in ("id", "title", "creator", "source_urls", "license", "license_url", "retrieved", "web_safe")
                if key in source
            }
            for source in registry["sources"]
        ],
        "totals": {
            "files": len(assets),
            "bytes": sum(asset["bytes"] for asset in assets),
            "models": sum(asset["path"].endswith(".glb") for asset in assets),
        },
        "assets": assets,
    }


def write_manifest(manifest: dict, path: Path = MANIFEST_PATH) -> None:
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return
    path.write_text(rendered, encoding="utf-8", newline="\n")


def verify_manifest(registry: dict, path: Path = MANIFEST_PATH) -> dict:
    if not path.is_file():
        raise AssetLibraryError(f"missing generated manifest {path.relative_to(REPO)}")
    recorded = json.loads(path.read_text(encoding="utf-8"))
    current = build_manifest(registry)
    if recorded != current:
        raise AssetLibraryError("asset library manifest is stale; run the manifest command")
    return current


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="copy one approved external catalog into the repo")
    sync_parser.add_argument("source_id")
    subparsers.add_parser("manifest", help="regenerate hashes and structural metadata")
    subparsers.add_parser("verify", help="verify registry, files, GLBs, images and hashes")
    args = parser.parse_args(argv)

    try:
        registry = load_registry()
        if args.command == "sync":
            source = source_by_id(registry, args.source_id)
            count, changed = sync_catalog(source)
            manifest = build_manifest(registry)
            write_manifest(manifest)
            print(f"ASSET_LIBRARY_SYNC_OK source={args.source_id} models={count} changed_files={changed}")
        elif args.command == "manifest":
            manifest = build_manifest(registry)
            write_manifest(manifest)
            print(
                f"ASSET_LIBRARY_MANIFEST_OK files={manifest['totals']['files']} "
                f"models={manifest['totals']['models']} bytes={manifest['totals']['bytes']}"
            )
        else:
            manifest = verify_manifest(registry)
            print(
                f"ASSET_LIBRARY_VERIFY_OK files={manifest['totals']['files']} "
                f"models={manifest['totals']['models']} bytes={manifest['totals']['bytes']}"
            )
        return 0
    except (AssetLibraryError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ASSET_LIBRARY_FAILED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
