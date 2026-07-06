# reload the generator script inside neighborhood.blend and mark it to
# auto-register on file load (Blender will ask once to "Allow Execution")
import bpy, os
proj = os.path.expanduser("~/Documents/neighborhood")
for t in list(bpy.data.texts):
    if t.name.startswith("neighborhood_blender"):
        bpy.data.texts.remove(t)
txt = bpy.data.texts.load(os.path.join(proj, "neighborhood_blender.py"))
txt.name = "neighborhood_blender.py"
txt.use_module = True
bpy.ops.wm.save_mainfile()
print("TEXT REFRESHED")
