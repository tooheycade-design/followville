"""Read-only audit for Followville's saved Blender scene and embedded source."""

import bpy
import hashlib
import json
import os
import struct


def add_text(hasher, value):
    data = str(value).encode("utf-8", "surrogatepass")
    hasher.update(struct.pack("<Q", len(data)))
    hasher.update(data)


def add_float(hasher, value):
    hasher.update(struct.pack("<d", float(value)))


def object_fcurves(obj):
    animation = obj.animation_data
    if not animation or not animation.action:
        return []
    action = animation.action
    try:
        curves = list(action.fcurves)
        if curves:
            return curves
    except AttributeError:
        pass
    curves = []
    try:
        for layer in action.layers:
            for strip in layer.strips:
                bag = None
                try:
                    bag = strip.channelbag(animation.action_slot)
                except Exception:
                    pass
                if bag is not None:
                    curves.extend(bag.fcurves)
                else:
                    for other in getattr(strip, "channelbags", []):
                        curves.extend(other.fcurves)
    except Exception:
        pass
    return curves


def geometry_signature():
    digest = hashlib.sha256()
    for scene in sorted(bpy.data.scenes, key=lambda item: item.name):
        add_text(digest, ("SCENE", scene.name, scene.frame_start, scene.frame_end,
                          scene.render.engine, scene.render.resolution_x,
                          scene.render.resolution_y, scene.render.resolution_percentage,
                          scene.camera.name if scene.camera else ""))

    for collection in sorted(bpy.data.collections, key=lambda item: item.name):
        add_text(digest, ("COLLECTION", collection.name,
                          tuple(sorted(obj.name for obj in collection.objects)),
                          tuple(sorted(child.name for child in collection.children))))

    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        add_text(digest, ("OBJECT", obj.name, obj.type,
                          obj.parent.name if obj.parent else "",
                          obj.instance_collection.name if obj.instance_collection else ""))
        for value in obj.matrix_world:
            for component in value:
                add_float(digest, component)
        add_text(digest, tuple(slot.material.name if slot.material else ""
                               for slot in obj.material_slots))
        action = obj.animation_data.action if obj.animation_data else None
        if action:
            add_text(digest, ("ACTION", action.name))
            for curve in sorted(object_fcurves(obj),
                                key=lambda item: (item.data_path, item.array_index)):
                add_text(digest, (curve.data_path, curve.array_index))
                for point in curve.keyframe_points:
                    add_float(digest, point.co.x)
                    add_float(digest, point.co.y)
                    add_text(digest, point.interpolation)

    for mesh in sorted(bpy.data.meshes, key=lambda item: item.name):
        add_text(digest, ("MESH", mesh.name, len(mesh.vertices), len(mesh.edges),
                          len(mesh.polygons), tuple(mat.name if mat else ""
                                                     for mat in mesh.materials)))
        for vertex in mesh.vertices:
            for component in vertex.co:
                add_float(digest, component)
        for polygon in mesh.polygons:
            add_text(digest, (tuple(polygon.vertices), polygon.material_index))

    for curve in sorted(bpy.data.curves, key=lambda item: item.name):
        add_text(digest, ("CURVE", curve.name, curve.dimensions,
                          curve.resolution_u, curve.render_resolution_u,
                          curve.bevel_depth, curve.bevel_resolution,
                          curve.fill_mode, getattr(curve, "body", "")))
        for spline in curve.splines:
            add_text(digest, (spline.type, spline.use_cyclic_u,
                              spline.order_u, spline.resolution_u))
            for point in spline.points:
                for component in point.co:
                    add_float(digest, component)
                add_float(digest, point.radius)
                add_float(digest, point.tilt)
            for point in spline.bezier_points:
                for vector in (point.co, point.handle_left, point.handle_right):
                    for component in vector:
                        add_float(digest, component)
                add_text(digest, (point.handle_left_type, point.handle_right_type))
                add_float(digest, point.radius)
                add_float(digest, point.tilt)

    for material in sorted(bpy.data.materials, key=lambda item: item.name):
        add_text(digest, ("MATERIAL", material.name, material.diffuse_color[:],
                          material.metallic, material.roughness,
                          bool(material.node_tree)))
    return digest.hexdigest()


embedded = bpy.data.texts.get("neighborhood_blender.py")
embedded_source = embedded.as_string() if embedded else ""
embedded_source = embedded_source.replace("\r\n", "\n").replace("\r", "\n")
repo = (os.environ.get("FOLLOWVILLE_REPO_DIR")
        or os.environ.get("NEIGHBORHOOD_STATE_DIR")
        or os.environ.get("NEIGHBORHOOD_REPO_DIR") or "")
repo_source_hash = ""
if repo:
    repo_generator = os.path.join(os.path.abspath(os.path.expanduser(repo)),
                                  "neighborhood_blender.py")
    if os.path.isfile(repo_generator):
        with open(repo_generator, "r", encoding="utf-8-sig", newline=None) as handle:
            repo_source = handle.read().replace("\r\n", "\n").replace("\r", "\n")
        repo_source_hash = hashlib.sha256(repo_source.encode("utf-8")).hexdigest()
embedded_hash = hashlib.sha256(embedded_source.encode("utf-8")).hexdigest() if embedded else ""
recorded_hash = bpy.context.scene.get("followville_generator_sha256", "")
result = {
    "blend": bpy.data.filepath,
    "objects": len(bpy.data.objects),
    "collections": len(bpy.data.collections),
    "meshes": len(bpy.data.meshes),
    "curves": len(bpy.data.curves),
    "materials": len(bpy.data.materials),
    "geometry_sha256": geometry_signature(),
    "embedded_lines": len(embedded_source.splitlines()) if embedded else 0,
    "embedded_sha256": embedded_hash,
    "recorded_sha256": recorded_hash,
    "recorded_commit": bpy.context.scene.get("followville_generator_commit", ""),
    "repo_sha256": repo_source_hash,
    "source_match": bool(repo_source_hash and embedded_hash == repo_source_hash
                         and recorded_hash == repo_source_hash),
}
print("FOLLOWVILLE_BLEND_AUDIT " + json.dumps(result, sort_keys=True))
