# Followville asset pipeline

Followville uses a local, reviewable asset library to save modeling time without
giving up licensing certainty, visual consistency, or browser performance. The
library is deliberately separate from `world_state.json`, the authoritative
Blend, town geometry, avatar runtime, and homeowner catalog. Importing a pack
does not make its contents public or selectable automatically.

## Approved sources

`assets/asset_sources.json` is the source-of-truth registry. A source must have
an official page, creator, retrieval date, exact license, and local managed
paths. The browser-safe library currently accepts only verified CC0 1.0 assets.
This conservative rule is intentional: public GLBs can be downloaded from a
website, which can violate otherwise useful marketplace licenses that prohibit
redistributing extractable source models.

The first review library is Kenney's 140-model Furniture Kit. Its complete
source archive stays outside Git under
`%USERPROFILE%\.codex\integrations\kenney-furniture-kit`; Git contains only the
compact GLBs, matching preview cards, provenance, and deterministic hashes.
Quaternius remains the source of the released avatar and interior catalogs.

## Commands

Use Blender's bundled Python from the repository root:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" scripts\build_asset_library.py sync kenney-furniture-kit
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" scripts\build_asset_library.py verify
& "C:\Program Files\Blender Foundation\Blender 5.1\5.1\python\bin\python.exe" -m unittest tests.test_asset_library
```

Set `FOLLOWVILLE_KENNEY_FURNITURE_SOURCE` when the source pack is cached in a
different location. `sync` copies changed files but never automatically deletes
an unfamiliar file. `verify` parses every GLB 2 header/JSON chunk, validates
every PNG, recomputes all hashes and model statistics, and fails if the
generated `assets/asset_library_manifest.json` is stale.

Open `asset-library.html` through the normal local preview server for a searchable
maintainer gallery with real source thumbnails, triangle counts, file sizes,
stable IDs, and direct GLB downloads. It is deliberately not linked from the
public game UI.

Normalize an approved model in an isolated Blender process before promotion:

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe" --background --python-exit-code 1 --python scripts\normalize_game_asset.py -- --input "C:\path\raw.glb" --output "work\asset-review\normalized.glb" --preview "work\asset-review\normalized.png" --target-max-dimension 2.0
```

The normalizer centers the footprint, grounds the model, optionally standardizes
its size, strips source cameras/lights, enables backface culling, exports a
web-ready GLB, renders a neutral review card, and writes mesh/material/triangle
statistics. It refuses `town.glb`, `town_chunks`, and both authoritative Blend
paths so an intake command cannot overwrite the city.

## Promoting an asset into gameplay

The review library is an intake shelf, not a runtime allowlist. Before using an
asset in the town, avatar system, or homeowner builder:

1. Review the real model at intended scale from the front and both oblique
   sides. Check orientation, origin, materials, visible-face separation and
   triangle cost.
2. Normalize it through an isolated Blender authoring scene. Never open or save
   `neighborhood.blend` merely to convert a downloaded model.
3. Copy only the approved optimized result into its runtime directory.
4. Add it to the applicable client allowlist and server allowlist together.
   Homeowner items require a new additive Supabase migration; never rewrite a
   migration already applied to production.
5. Regenerate the asset manifest, run focused browser tests, and visually inspect
   the exact runtime result. Do not hotlink third-party files.

## Blender MCP

Blender MCP is an interactive aid for inspecting, staging and iterating on
individual assets. It is not the canonical generator and must not be used for
daily growth. The maintained local integration lives at
`%USERPROFILE%\.codex\integrations\blender-mcp-6641189`; Codex points to that
checkout with Python 3.11, telemetry disabled, and the server bound locally.
The visible Blender GUI must be open and **Connect to MCP server** must be active.
Restart Codex after changing MCP configuration so its tool registry refreshes.

Finalize useful MCP experiments as deterministic scripts or committed source
assets. That keeps Cade, Zach, Codex and Claude able to reproduce the same
result without depending on one interactive session.
