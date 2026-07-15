import bpy

for i in range(15):
    col = bpy.data.collections.get("AST_suburban_%02d" % i)
    if not col:
        print("ASSET_MISSING", i)
        continue
    meshes = [o for o in col.objects if o.type == "MESH"]
    if not meshes:
        print("ASSET_EMPTY", i)
        continue
    obj = meshes[0]
    xs = [v.co.x for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    zs = [v.co.z for v in obj.data.vertices]
    used = sorted(set(p.material_index for p in obj.data.polygons))
    print("ASSET", i, "objects", len(meshes), "verts", len(obj.data.vertices),
          "polys", len(obj.data.polygons), "mats", len(obj.data.materials),
          "used", used, "bounds", (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)),
          "names", [m.name if m else None for m in obj.data.materials])
