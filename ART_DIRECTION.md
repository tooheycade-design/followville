# Followville art direction

Friendly low-poly Instagram town. Readable on a phone. Colorful, clean, walkable.

## Rules (non-negotiable)

1. **No buildings on roads.** Civic pads stay inside their block with curb margin.
2. **No floating roads.** Downtown grid asphalt sits on the flat platform (~z 0.02).
3. **Burj (seed 2)** stays in the **middle** founder grid; tall but **lot-sized footprint**.
4. **School (seed 172)** SW civic anchor at lots `(-6,-6)` block `(-2,-2)`.
5. **Follow Mart (seed 335)** sits at the **opposite corner of the middle grid** from the school:
   - School SW → Mart **NE** at lots `(3,3)` block `(1,1)` (flat downtown platform).
6. **Castle (seed 5)** and all claimable homes stay unless Zach/Cade explicitly say otherwise.
7. **Procedural massing towers** only on truly empty blocks; placing Mart removes that block’s tower.
8. **Forest** = edge district only (`North Woods`), not random street trees.

## Scale

| Element | Footprint |
|---------|-----------|
| House | 1 lot |
| School / Follow Mart | 1 full block (SIZE 3) |
| Burj | 1 lot footprint, tall skyline |

## Palette cues

- Mart: blue body, yellow trim, white/yellow **FOLLOW MART** lettering, dark asphalt parking
- Roads: dark asphalt, lighter sidewalks/curbs
- Grass: soft meadow under pad, never over asphalt

## QA before ship

```bash
export FOLLOWVILLE_REPO_DIR=~/followville_repo
export NEIGHBORHOOD_STATE_DIR=~/followville_repo
bash ~/AgentWorkspace/blender-tools/followville_qa_all.sh
```

Inspect street + overhead stills. Fail if roads float or Mart sits on a hill (terrain_height ≫ 0).
