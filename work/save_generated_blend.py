import bpy

bpy.context.scene.frame_set(bpy.context.scene.frame_end)
bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath)
print("SAVED_BLEND", bpy.data.filepath)
