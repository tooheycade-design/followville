"""
One-off diagnostic — does NOT modify or save neighborhood.blend.
Run with:
  /Applications/Blender.app/Contents/MacOS/Blender --background \
    ~/Documents/neighborhood/neighborhood.blend --python diag_investigate.py
"""
import bpy
import sys
import os
import json

DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DIR)

# Load world_state.json exactly the way neighborhood_blender.py does, without
# importing that module (avoids accidentally running its module-level CONFIG code).
with open(os.path.join(DIR, "world_state.json")) as f:
    state = json.load(f)

buildings = state["buildings"]
print("world_state.json building count:", len(buildings))
house_d4 = [b for b in buildings if b["type"] == "house" and b.get("day") == 4]
print("house entries with day==4 in world_state.json:", len(house_d4))
print(house_d4)

col = bpy.data.collections.get("WORLD")
print("\nWORLD collection object count (in saved .blend):", len(col.objects) if col else "NO WORLD COLLECTION")

house_d4_objs = [o for o in col.objects if o.name.startswith("house_d4")] if col else []
print("Objects in WORLD named house_d4*: ", len(house_d4_objs))
for o in house_d4_objs:
    inst_col = o.instance_collection.name if o.instance_type == 'COLLECTION' and o.instance_collection else None
    print(f"  {o.name}  type={o.type}  instance_type={o.instance_type}  instance_collection={inst_col}  location={tuple(o.location)}  users_collection={[c.name for c in o.users_collection]}")

# Also: is there more than one collection anywhere named WORLD or WORLD.NNN?
all_world_like = [c.name for c in bpy.data.collections if c.name == "WORLD" or c.name.startswith("WORLD.")]
print("\nAll WORLD-like collections in this file:", all_world_like)

# Total object count in the whole file, and how many are unlinked from every collection
total_objs = len(bpy.data.objects)
unlinked = [o.name for o in bpy.data.objects if len(o.users_collection) == 0]
print("\nTotal objects in bpy.data.objects:", total_objs)
print("Objects with zero collection links (orphaned):", len(unlinked))
