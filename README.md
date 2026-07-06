# Follower Neighborhood — Blender Setup

The foundation for your growing 3D city (like the Battery Tea video). One script builds the model library, the world, the daily growth, and the animation.

## One-time setup

1. Download Blender (free): https://www.blender.org/download/ — install and open it.
2. Make a folder for the project, e.g. `Documents/neighborhood/`.
3. In Blender: **File > Save As** → save `neighborhood.blend` into that folder. (Important — the world's memory file lives next to it.)
4. Go to the **Scripting** tab (top bar) → **Open** → pick `neighborhood_blender.py` → move it into the same folder when asked or just open it from wherever you saved it.

## Daily routine (1 minute)

**In Blender (easiest):** open `neighborhood.blend` (click "Allow Execution" if asked),
press **N** in the viewport, open the **City** tab, type your change (`+5`, `-3`, `=50`),
click **Grow the City** — watch it build through the camera — then **Render Video**.
The mp4 lands in `renders/` and auto-copies to your Desktop. AirDrop → post.

**Or in Terminal:** `~/Documents/neighborhood/grow.sh +5 --render`
(`-3` removes houses, `"=50"` sets the total — quote the = form.)

Extras on either path: Time (day/sunset/night — auto-cycles by default, night = lit
windows + streetlights) and Season (auto-follows the real calendar; winter = snow,
fall = orange trees). Milestones appear automatically: plaza at 500, skyscraper at
2,000, stadium at 10,000. Cars drive through town in every video.

The script remembers everything in `world_state.json` — old buildings stay exactly where they were, forever. Back that file up; it IS your city.

## What's in the model library

Houses (6 variants: random walls, roofs, chimneys, yard trees), apartment complexes (3), shops (3), parks (3: pond, trees, benches), trees (4), streetlights, cars. Streetlights and parked cars scatter automatically as the road grid grows.

## Extending it

- **Add a model:** copy `build_shop()` in the ASSET LIBRARY section, build your thing out of `add_box` / `add_ngon_cone` / `add_prism_roof` calls, register it in `ASSET_VARIANTS`, add a `NEW_<THING>` config line following the pattern in `main()`.
- **Use downloaded/AI models:** import any model into the .blend, put it in a collection named e.g. `AST_stadium_0`, register that name in `ASSET_VARIANTS` — the script will place it like any other asset.
- **Re-render yesterday:** set `REPLAY_LAST_DAY = True` (adds nothing, re-animates the last batch).
- **Look tweaks:** sun angle/energy and sky color in `build_stage()`, camera lens/DOF there too.

## Tips

- First run: try `NEW_HOUSES = 10` as a test, then `Reset` by deleting `world_state.json` before going live.
- Renders are fast (EEVEE). A 10-second day renders in a couple of minutes on most laptops.
- Want captions burned in? Easier to add text in Instagram/CapCut than in Blender.
