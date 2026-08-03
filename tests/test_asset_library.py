import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_asset_library", REPO / "scripts" / "build_asset_library.py"
)
asset_library = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(asset_library)


class AssetLibraryTests(unittest.TestCase):
    def test_snake_case_is_stable_for_pack_names(self):
        self.assertEqual(asset_library.snake_case("kitchenFridgeBuiltIn"), "kitchen_fridge_built_in")
        self.assertEqual(asset_library.snake_case("TV-Stand 02"), "tv_stand_02")

    def test_current_registry_and_manifest_verify(self):
        registry = asset_library.load_registry()
        manifest = asset_library.verify_manifest(registry)
        self.assertGreaterEqual(manifest["totals"]["models"], 200)
        self.assertTrue(all(source["web_safe"] for source in manifest["sources"]))

    def test_non_cc0_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            path.write_text(json.dumps({
                "version": 1,
                "sources": [{
                    "id": "unsafe",
                    "title": "Unsafe",
                    "creator": "Unknown",
                    "source_urls": ["https://example.invalid"],
                    "license": "Royalty-Free",
                    "license_url": "https://example.invalid/license",
                    "web_safe": True,
                }],
            }), encoding="utf-8")
            with self.assertRaises(asset_library.AssetLibraryError):
                asset_library.load_registry(path)


if __name__ == "__main__":
    unittest.main()
