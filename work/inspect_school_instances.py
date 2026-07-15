import bpy

for obj in bpy.data.objects:
    if obj.instance_collection and obj.instance_collection.name.startswith("AST_elementaryschool"):
        print("SCHOOL_INSTANCE", obj.name, tuple(round(v, 2) for v in obj.location), obj.parent.name if obj.parent else "-")
