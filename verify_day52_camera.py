"""Blender-native animation/framing check for ``day52nightreveal``.

Run after ``neighborhood_blender.py`` in the same background invocation on
the exact Day 52 +2 state (or an isolated copy grown to that state).
"""

import math

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from downtown_visual_plan import terrain_height


scene = bpy.context.scene
camera = scene.camera
failures = []
if camera is None or camera.name != "Day52NightRevealCamera":
    raise RuntimeError("day52nightreveal camera is not active")
if scene.frame_start != 1 or scene.frame_end != 720:
    raise RuntimeError("day52nightreveal must be exactly 720 frames")

homes = {int(obj.get("nb_world_plan_id", 0)): obj for obj in bpy.data.objects
         if int(obj.get("nb_world_plan_id", 0)) in (2354, 2355)}
if sorted(homes) != [2354, 2355]:
    raise RuntimeError("expected Day 52 plan_ids 2354/2355, got %r" % sorted(homes))
scene.frame_set(720)
rest_z = {plan_id: float(root.location.z) for plan_id, root in homes.items()}
rest_scale = {plan_id: tuple(float(value) for value in root.scale)
              for plan_id, root in homes.items()}


def require_state(plan_id, frame, hidden, z_offset):
    root = homes[plan_id]
    scene.frame_set(frame)
    if bool(root.hide_render) != hidden:
        raise RuntimeError("plan_id %d hidden=%r at frame %d; expected %r"
                           % (plan_id, root.hide_render, frame, hidden))
    if abs(root.location.z - (rest_z[plan_id] + z_offset)) > .03:
        raise RuntimeError("plan_id %d z=%.3f at frame %d; expected %.3f"
                           % (plan_id, root.location.z, frame,
                              rest_z[plan_id] + z_offset))


# Empty opening, then two clean rigid rises with no scale distortion.
require_state(2354, 85, True, -9.0)
require_state(2354, 86, False, -9.0)
require_state(2354, 140, False, 0.0)
require_state(2355, 189, True, -9.0)
require_state(2355, 190, False, -9.0)
require_state(2355, 244, False, 0.0)
for plan_id, root in homes.items():
    if any(abs(value - expected) > .001
           for value, expected in zip(root.scale, rest_scale[plan_id])):
        raise RuntimeError("Day 52 house scale was distorted: %s %r"
                           % (root.name, tuple(root.scale)))


def projection(frame, point):
    scene.frame_set(frame)
    ndc = world_to_camera_view(scene, camera, Vector(point))
    return float(ndc.x), float(ndc.y), float(ndc.z)


def require_visible(label, frame, points, margin=.025):
    projected = [projection(frame, point) for point in points]
    misses = [coords for coords in projected
              if coords[2] <= 0.0
              or not margin <= coords[0] <= 1.0 - margin
              or not margin <= coords[1] <= 1.0 - margin]
    if misses:
        failures.append("%s is not safely framed at %d: %r"
                        % (label, frame, projected))
    print("CAMERA_QA %s frame=%d projected=%r" % (label, frame, projected))


home_points = {}
for plan_id, (x, y) in {2354: (-96.169, 854.5),
                        2355: (-89.195, 837.5)}.items():
    z = terrain_height(x, y)
    home_points[plan_id] = ((x - 3.5, y - 4.5, z + .2),
                            (x + 3.5, y + 4.5, z + 7.5))
require_visible("first-empty-frontage", 78, home_points[2354], margin=.018)
require_visible("first-finished-home", 140, home_points[2354], margin=.018)
require_visible("second-empty-frontage", 184, home_points[2355], margin=.018)
require_visible("second-finished-home", 250, home_points[2355], margin=.018)

# The opening camera is genuinely in Gateway Row at a natural eye height.
scene.frame_set(1)
opening = camera.matrix_world.translation
road_ground = terrain_height(opening.x, opening.y)
if abs(opening.y - 846.0) > 4.5 or not 1.7 <= opening.z - road_ground <= 2.8:
    failures.append("opening camera is not road-level in Gateway Row: %r, ground %.3f"
                    % (tuple(opening), road_ground))

# After the homes finish, the move only travels outward/upward. This catches
# an accidental camera reversal or a second story beat during the pullback.
distances = []
reveal_centre = Vector((-93.0, 846.0, 4.0))
for frame in range(250, 721, 15):
    scene.frame_set(frame)
    distances.append((frame, (camera.matrix_world.translation - reveal_centre).length))
for (fa, da), (fb, db) in zip(distances, distances[1:]):
    if db + .25 < da:
        failures.append("pullback reverses between %d and %d: %.2f -> %.2f"
                        % (fa, fb, da, db))

# Every persistent building origin must land inside the final portrait. The
# small margin keeps the developed city legible rather than merely unclipped.
scene.frame_set(720)
city_points = []
for obj in bpy.data.objects:
    if obj.get("nb_world_type") and not obj.get("nb_render_only"):
        loc = obj.matrix_world.translation
        city_points.append((loc.x, loc.y, loc.z + 2.0))
projected = [projection(720, point) for point in city_points]
misses = [coords for coords in projected
          if coords[2] <= 0.0 or not .015 <= coords[0] <= .985
          or not .025 <= coords[1] <= .975]
if misses:
    failures.append("final whole-city frame misses %d/%d building origins; "
                    "bounds x %.3f..%.3f y %.3f..%.3f"
                    % (len(misses), len(projected),
                       min(p[0] for p in projected), max(p[0] for p in projected),
                       min(p[1] for p in projected), max(p[1] for p in projected)))
print("CAMERA_QA whole-city frame=720 buildings=%d bounds=x %.3f..%.3f y %.3f..%.3f"
      % (len(projected), min(p[0] for p in projected), max(p[0] for p in projected),
         min(p[1] for p in projected), max(p[1] for p in projected)))

warm_pools = [obj for obj in bpy.data.objects if obj.name.startswith("Day52WarmPool_")]
if len(warm_pools) != 2:
    raise RuntimeError("expected two Day 52 warm pools, got %d" % len(warm_pools))
for lamp in warm_pools:
    if lamp.data.type != "SPOT" or lamp.data.color.r < .95 or lamp.data.color.b > .3:
        raise RuntimeError("Day 52 pool is not the authored warm spot: %s" % lamp.name)

if failures:
    raise RuntimeError("day52 camera verification failed:\n- " + "\n- ".join(failures))

print("verify_day52_camera.py: OK -- two road-level night reveals and one whole-city pullback")
