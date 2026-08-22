"""Blender-native framing and animation check for ``highschoolreveal``.

Run after ``neighborhood_blender.py`` in the same background invocation:

    blender --background neighborhood.blend \
      --python neighborhood_blender.py \
      --python verify_high_school_camera.py -- \
      --replay --cam highschoolreveal --time dusk
"""

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


scene = bpy.context.scene
camera = scene.camera
if camera is None or camera.name != "HighSchoolRevealCamera":
    raise RuntimeError("highschoolreveal camera is not active")
if scene.frame_start != 1 or scene.frame_end != 720:
    raise RuntimeError("highschoolreveal must be exactly 720 frames")

school_roots = [obj for obj in bpy.data.objects
                if obj.get("nb_world_type") == "highschool"]
if len(school_roots) != 1:
    raise RuntimeError("expected one high-school root, got %d" % len(school_roots))
school = school_roots[0]

scene.frame_set(1)
if not school.hide_render:
    raise RuntimeError("school must be absent in the downtown opening")
scene.frame_set(175)
if not school.hide_render:
    raise RuntimeError("school appeared before the reveal beat")
scene.frame_set(176)
if school.hide_render or abs(school.location.z + 20.0) > .001:
    raise RuntimeError("school reveal does not begin underground at frame 176")
scene.frame_set(240)
if school.hide_render or abs(school.location.z) > .001:
    raise RuntimeError("school has not completed its rise by frame 240")
if any(abs(value - 1.0) > .001 for value in school.scale):
    raise RuntimeError("school reveal distorted the campus scale")


def projection(frame, point):
    scene.frame_set(frame)
    ndc = world_to_camera_view(scene, camera, Vector(point))
    return (float(ndc.x), float(ndc.y), float(ndc.z))


def require_visible(label, frame, points, margin_x=.025, margin_y=.025):
    projected = [projection(frame, point) for point in points]
    misses = [coords for coords in projected
              if coords[2] <= 0.0
              or not margin_x <= coords[0] <= 1.0 - margin_x
              or not margin_y <= coords[1] <= 1.0 - margin_y]
    if misses:
        raise RuntimeError("%s is not safely framed at %d: %r" %
                           (label, frame, projected))
    print("CAMERA_QA %s frame=%d projected=%r" % (label, frame, projected))


# The old-town anchor, the empty destination, and the precise campus-facing
# side of the monument sign must each read at their intended beat.
require_visible("burj-old-downtown", 1, ((6.5, 19.5, 20.0),))
require_visible("empty-campus", 145, ((-69.0, -156.0, .2),))
require_visible("monument-sign", 270,
                ((-94.7, -103.07, 1.05), (-87.3, -103.07, 1.05),
                 (-94.7, -103.07, 3.55), (-87.3, -103.07, 3.55)),
                margin_x=.015, margin_y=.015)

# Projection alone cannot detect a building standing between the camera and
# a target. Ray to the centre of the street-facing sign and require the first
# actual surface to be one of the authored hs_sign_* objects.
scene.frame_set(270)
depsgraph = bpy.context.evaluated_depsgraph_get()
origin = camera.evaluated_get(depsgraph).matrix_world.translation
sign_centre = Vector((-91.0, -103.07, 2.25))
direction = sign_centre - origin
hit, _, _, _, hit_object, _ = scene.ray_cast(
    depsgraph, origin, direction.normalized(), distance=direction.length + .25)
if not hit or hit_object is None or "hs_sign" not in hit_object.name.lower():
    raise RuntimeError("monument sign is projected but occluded by %s" %
                       (hit_object.name if hit_object else "nothing"))
print("CAMERA_QA monument-occlusion first-hit=%s" % hit_object.name)

# All three building entrances share at least one complete orbit frame.
facades = ((-89.0, -131.0, 4.8), (-67.0, -131.0, 4.8),
           (-47.5, -131.0, 4.8))
facade_frames = []
for frame in (330, 365, 400):
    coords = [projection(frame, point) for point in facades]
    if all(p[2] > 0 and .02 <= p[0] <= .98 and .03 <= p[1] <= .97
           for p in coords):
        facade_frames.append((frame, coords))
if not facade_frames:
    raise RuntimeError("no orbit frame holds all three school buildings")
print("CAMERA_QA three-buildings frame=%d projected=%r" % facade_frames[0])

# The final climb-out must preserve the football field and the recognizable
# outer width of the track, rather than ending on an abstract patch of turf.
require_visible("stadium", 720,
                ((-95.0, -211.0, .3), (-37.0, -211.0, .3),
                 (-95.0, -137.0, .3), (-37.0, -137.0, .3)),
                margin_x=.01, margin_y=.01)

# Conservative no-cut rule: whenever the camera is below rooftop height it
# must be outside the campus rectangle plus a two-metre safety margin. This is
# sampled throughout the continuous curve, not only at the authored keyframes.
for frame in range(1, 721, 3):
    scene.frame_set(frame)
    position = camera.matrix_world.translation
    inside_xy = (-103.0 <= position.x <= -35.0 and
                 -214.0 <= position.y <= -98.0)
    if inside_xy and position.z < 22.0:
        raise RuntimeError(
            "camera enters the campus/building envelope at frame %d: %r" %
            (frame, tuple(round(value, 3) for value in position)))
print("CAMERA_QA exterior-orbit clear at 240 sampled frames")

print("verify_high_school_camera.py: OK -- one continuous 24s school-only "
      "reveal; downtown, empty pad, sign, three buildings, and stadium framed")
