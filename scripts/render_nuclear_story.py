"""FOLLOWVILLE STORIES #002 -- "The Night The Lights Came On".

Produced to FOLLOWVILLE_STORIES.md. Run against an isolated state containing a
`nuclearplant` record. Rebuilds in replay mode, so it never advances the world,
never writes world_state.json, never touches either authoritative Blend and
never exports a GLB.

    set NEIGHBORHOOD_STATE_DIR=<isolated dir>
    blender --background <isolated blend> --python scripts/render_nuclear_story.py

STORYBOARD -- hook, setup, escalation, payoff (§6)
--------------------------------------------------
The event is the hook: the story opens ON the switch-on, not on a building.
Everything is told with lights, because §2 forbids people and §4 says design
for what Blender reliably does -- and lights turning on and off across a whole
city is both the most reliable thing here and the most legible.

  1  0.0-2.3s  HOOK        tight on the station, dark -- then every light on
                           the site snaps on at once
  2  2.3-6.3s  SETUP       the city from above: windows come up in a wave
                           spreading out from the plant. Followville is on it
  3  6.3-11.3s ESCALATION  inside the reactor hall: the pool surges, beacons
                           start, the camera shakes, the crane swings
  4 11.3-14.3s TURN        same city view -- every light in town dies, block
                           by block, until only the green trefoil is lit
  5 14.3-16.7s PAYOFF      the dark city holds, then everything snaps back
                           brighter than before
  6 16.7-18.7s TAIL        back at the station, steady, green

18.7 seconds, inside the 10-20s target. Shot 4 reuses shot 2's camera exactly
so the blackout lands as a match cut on a frame the viewer already knows.

Sound, for the edit: a breaker-clunk on the snap at shot 1, rising hum through
shot 2, alarm klaxon and a low groan under shot 3, then the hum falling away to
silence through shot 4 -- the silence IS the blackout -- and one big clunk plus
a swell as the lights return.

Caption: "Followville switched on its first nuclear plant. It went about as
well as you'd expect." CTA: "Claim your Followville home."

WHY DUSK AND NOT SUNSET: the whole story is told with lights, and at sunset the
sky is still bright enough that windows coming on read as nothing at all. Dusk
is the first preset where the city's own light is the brightest thing in frame.
"""

import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ["FOLLOWVILLE_IMPORT_ONLY"] = "1"
import neighborhood_blender as nb  # noqa: E402
os.environ.pop("FOLLOWVILLE_IMPORT_ONLY", None)

OUT = Path(os.environ.get("NUCLEAR_STORY_OUT",
                          str(REPO / "renders" / "nuclear_story")))
OUT.mkdir(parents=True, exist_ok=True)
TOD = os.environ.get("NUCLEAR_STORY_TOD", "night")
PX, PY = 446.0, 556.0
INTERIOR_Z = -400.0

# focus_type matching no building type empties the rise batch, so the town is
# already standing instead of popping up mid-shot (FOLLOWVILLE_STORIES §13).
nb.main({"replay": True, "time": TOD, "focus_type": "finished"})
scene = bpy.context.scene

# The replay still carries the house-rise animation. Move everything to its
# final pose and drop the actions, or the town grows again behind the story.
# Frame is set FIRST: after frame_set the transforms hold the evaluated values.
scene.frame_set(scene.frame_end)
for obj in bpy.data.objects:
    if obj.animation_data:
        loc, rot, scale = (tuple(obj.location), tuple(obj.rotation_euler),
                           tuple(obj.scale))
        obj.animation_data_clear()
        obj.location, obj.rotation_euler, obj.scale = loc, rot, scale


def render_only(collection):
    """Tag everything so export_web would delete it (STORIES §13).

    This script never runs export_web, but the tag is the only thing standing
    between a temporary prop and geometry welded to the public site forever, and
    the habit is the point.
    """
    for obj in collection.objects:
        obj["nb_render_only"] = True


interior = bpy.data.collections.new("STORY_INTERIOR")
scene.collection.children.link(interior)
nb.build_reactor_hall_interior(interior, 8500)
for obj in interior.objects:
    obj.location = (obj.location.x + PX, obj.location.y + PY,
                    obj.location.z + INTERIOR_Z)
render_only(interior)

alarm = bpy.data.collections.new("STORY_ALARM")
scene.collection.children.link(alarm)
alarm_mat = nb.mat_emissive("NB_story_alarm", (.74, .05, .03), .30, 0.0)
site_mat = nb.mat_emissive("NB_story_sitelight", (1.0, .88, .62), .34, 0.0)
for index, (dx, dy, dz) in enumerate(((-2.0, -28.0, 3.9), (26.0, 18.0, 31.0),
                                      (8.0, 15.0, 24.0), (-19.0, 13.0, 41.5),
                                      (-25.0, -19.0, 8.2))):
    nb.add_ngon_cone(alarm, "story_alarm_%d" % index, .85, .60, 1.1, 10,
                     PX + dx, PY + dy, 4.75 + dz, alarm_mat)
# Site floodlights: what actually "switches on" in shot 1.
for index in range(10):
    a = index / 10.0 * math.tau
    nb.add_box(alarm, "story_sitelight_%d" % index, 1.0, 1.0, .6,
               PX + 34.0 * math.cos(a), PY + 2.0 + 30.0 * math.sin(a),
               4.75 + 7.4, site_mat)
render_only(alarm)

CITY_LIGHTS = ("NB_window", "NB_windark", "NB_bulb", "NB_streetlight_glow",
               "NB_sign_glow", "NB_salmon_warm_light", "NB_fire_warm_light",
               "FV_metro_lobby_glow", "FV_metro_shop_light",
               "FV_expressway_light_warm")


def emission_socket(material):
    if not material or not material.node_tree:
        return None
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    return bsdf.inputs.get("Emission Strength") if bsdf else None


def key_emission(material, frames, scale=1.0):
    socket = emission_socket(material)
    if socket is None:
        return
    base = socket.default_value or 1.0
    for frame, value in frames:
        socket.default_value = value * (base if scale is None else scale)
        socket.keyframe_insert("default_value", frame=frame)


# ── the city's lights: the whole story, in one curve ───────────────────────
#
# Dark until the plant comes on, up in a wave, then killed block by block, then
# slammed back brighter than they started.
CITY_CURVE = [(1, 0.0), (78, 0.0), (96, .18), (130, .55), (180, 1.0),
              (390, 1.0), (404, .72), (422, .34), (444, .08), (468, 0.0),
              (574, 0.0), (582, .25), (600, .60), (626, 1.35), (648, 1.12),
              (680, 1.0), (780, 1.0)]
found, missing = [], []
for name in CITY_LIGHTS:
    material = bpy.data.materials.get(name)
    socket = emission_socket(material)
    if socket is None:
        missing.append(name)
        continue
    found.append("%s@%.1f" % (name, socket.default_value or 0.0))
    base = socket.default_value or 3.0
    for frame, value in CITY_CURVE:
        socket.default_value = base * value
        socket.keyframe_insert("default_value", frame=frame)
print("STORY_CITY_MATERIALS found=%s missing=%s" % (",".join(found),
                                                    ",".join(missing)))

# The night preset also puts REAL lights in the scene -- up to sixty practical
# pools under the streetlights -- and those are what actually light the town.
# Animating only the emissive materials left the blackout frame looking
# identical to the lit one. Everything except the sun/moon key follows the same
# curve.
practicals = [obj for obj in bpy.data.objects
              if obj.type == "LIGHT" and obj.data.type != "SUN"]
for obj in practicals:
    base = obj.data.energy
    for frame, value in CITY_CURVE:
        obj.data.energy = base * value
        obj.data.keyframe_insert("energy", frame=frame)
print("STORY_PRACTICAL_LIGHTS %d" % len(practicals))

# The moon/sun key has to fall away too, or the town stays visibly lit from
# above through the blackout. It is dimmed rather than killed: pitch black
# reads as a render failure, a faint moon reads as a power cut.
for obj in bpy.data.objects:
    if obj.type == "LIGHT" and obj.data.type == "SUN":
        base = obj.data.energy
        for frame, value in CITY_CURVE:
            obj.data.energy = base * (1.0 if value >= 1.0
                                      else .34 + .66 * min(1.0, value))
            obj.data.keyframe_insert("energy", frame=frame)

# Site floodlights snap on at frame 8 -- that snap is the hook.
key_emission(site_mat, [(1, 0.0), (7, 0.0), (8, 6.0), (14, 3.4), (390, 3.4),
                        (410, 0.0), (574, 0.0), (582, 5.0), (626, 3.4),
                        (780, 3.4)], scale=1.0)
# Alarms: silent until the escalation, hard flashing, and they are the ONLY
# thing still lit through the blackout -- that is what makes the dark hold
# read as the plant still being in trouble rather than as an empty frame.
key_emission(alarm_mat, [(1, 0.0), (200, 0.0), (210, 9.0), (224, .6),
                         (238, 9.0), (252, .6), (285, 9.0), (305, .6),
                         (340, 9.0), (364, .8), (400, 7.0), (460, 5.0),
                         (520, 3.5), (570, 2.0), (590, 0.0), (780, 0.0)],
             scale=1.0)

pool = bpy.data.materials.get("NB_rh_pool")
beacon = bpy.data.materials.get("NB_rh_beacon")
key_emission(pool, [(1, 2.4), (200, 2.4), (225, 7.8), (265, 4.2), (305, 9.0),
                    (350, 5.5), (390, 2.4), (780, 2.4)], scale=1.0)
key_emission(beacon, [(1, 2.2), (200, 2.2), (212, 11.0), (226, 1.4),
                      (240, 11.0), (254, 1.4), (290, 11.0), (315, 1.4),
                      (345, 10.0), (390, 2.2), (780, 2.2)], scale=1.0)

for name in ("rh_crane_trolley", "rh_crane_cable", "rh_crane_hook"):
    obj = interior.objects.get(name)
    if obj is None:
        continue
    start = tuple(obj.location)
    for frame, dy in ((1, 0.0), (200, 0.0), (300, -8.0), (390, -12.5),
                      (780, -12.5)):
        obj.location = (start[0], start[1] + dy, start[2])
        obj.keyframe_insert("location", frame=frame)

# ── shots ──────────────────────────────────────────────────────────────────
# Down at skyline height, not 430m up. At altitude a low-poly town's windows
# are a few pixels each and a wave of lights coming on reads as nothing; the
# whole story is told with those windows, so the camera has to be close enough
# for them to be the brightest thing in frame.
CITY_A = (368.0, 30.0, 138.0)
CITY_A_TO = (30.0, 300.0, 14.0)
CITY_B = (300.0, 124.0, 112.0)
CITY_B_TO = (10.0, 332.0, 14.0)
PLANT_AT = (PX + 62.0, PY - 80.0, 16.0)
PLANT_TO = (PX - 4.0, PY + 5.0, 26.0)

CITY_C = (268.0, 162.0, 98.0)

SHOTS = [
    # start, end, from_loc, from_look, to_loc, to_look, lens, shake
    (1, 70, PLANT_AT, PLANT_TO, (PX + 54.0, PY - 70.0, 15.0), PLANT_TO, 44, 0.0),
    (71, 200, CITY_A, CITY_A_TO, CITY_B, CITY_B_TO, 34, 0.0),
    (201, 390, (PX + 17.0, PY - 12.6, INTERIOR_Z + 9.6),
     (PX - 7.0, PY + 1.0, INTERIOR_Z + 4.0),
     (PX + 9.0, PY - 8.0, INTERIOR_Z + 7.4),
     (PX - 8.0, PY + 1.0, INTERIOR_Z + 4.8), 26, 0.60),
    # Shot 4 reuses shot 2's END pose exactly: a match cut onto a frame the
    # viewer already knows, so the blackout is the only thing that changed.
    (391, 490, CITY_B, CITY_B_TO, CITY_B, CITY_B_TO, 34, 0.0),
    # The dark hold. A slow push keeps it alive while nothing is lit but the
    # trefoil and the alarms.
    (491, 560, CITY_B, CITY_B_TO, CITY_C, CITY_B_TO, 36, 0.0),
    (561, 680, CITY_C, CITY_B_TO, (236.0, 196.0, 92.0), (0.0, 340.0, 14.0),
     36, 0.0),
    (681, 780, (PX + 50.0, PY - 66.0, 14.0), (PX - 4.0, PY + 5.0, 27.0),
     (PX + 46.0, PY - 61.0, 13.5), (PX - 4.0, PY + 5.0, 27.0), 40, 0.0),
]

data = bpy.data.cameras.new("story002_cam")
data.clip_start = 0.10
data.clip_end = 20000.0
camera = bpy.data.objects.new("story002_cam", data)
scene.collection.objects.link(camera)
scene.camera = camera


def key_camera(frame, location, target, lens, shake, seed):
    rot = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    if shake:
        # Deterministic wobble, so a re-render matches frame for frame.
        rot.x += shake * .011 * math.sin(frame * .77 + seed)
        rot.y += shake * .009 * math.sin(frame * 1.31 + seed * 2.0)
        rot.z += shake * .013 * math.sin(frame * .53 + seed * 3.0)
        location = (location[0] + shake * .10 * math.sin(frame * 1.7 + seed),
                    location[1] + shake * .10 * math.sin(frame * 1.1 + seed),
                    location[2] + shake * .07 * math.sin(frame * 2.3 + seed))
    camera.location = location
    camera.rotation_euler = rot
    camera.keyframe_insert("location", frame=frame)
    camera.keyframe_insert("rotation_euler", frame=frame)
    data.lens = lens
    data.keyframe_insert("lens", frame=frame)


for index, (f0, f1, a, at, b, bt, lens, shake) in enumerate(SHOTS):
    if shake:
        for frame in range(f0, f1 + 1, 2):
            t = (frame - f0) / max(1, f1 - f0)
            key_camera(frame,
                       tuple(a[i] + (b[i] - a[i]) * t for i in range(3)),
                       tuple(at[i] + (bt[i] - at[i]) * t for i in range(3)),
                       lens, shake, index * 7 + 1)
    else:
        key_camera(f0, a, at, lens, 0.0, index)
        key_camera(f1, b, bt, lens, 0.0, index)

# Hard cuts: obj_fcurves() is the generator's accessor -- Blender 5 moved an
# Action's curves behind layers/strips/channelbags.
for fcurve in nb.obj_fcurves(camera):
    for kp in fcurve.keyframe_points:
        kp.interpolation = "BEZIER"
        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
cuts = {f0 - 1 for index, (f0, *_r) in enumerate(SHOTS) if index}
for fcurve in nb.obj_fcurves(camera):
    for kp in fcurve.keyframe_points:
        if any(abs(kp.co.x - cut) < .5 for cut in cuts):
            kp.interpolation = "CONSTANT"

scene.frame_start = 1
scene.frame_end = 780
scene.render.fps = 30
scene.render.resolution_x = 1080
scene.render.resolution_y = 1920
scene.render.resolution_percentage = 100
scene.render.filepath = str(OUT / "followville_story_002_")

preview = [int(v) for v in os.environ.get("NUCLEAR_STORY_FRAMES", "").split(",")
           if v.strip()]
if preview:
    try:
        scene.render.image_settings.media_type = "IMAGE"
    except (AttributeError, TypeError):
        pass
    scene.render.image_settings.file_format = "PNG"
    for frame in preview:
        scene.frame_set(frame)
        scene.render.filepath = str(OUT / ("s2_frame_%04d" % frame))
        bpy.ops.render.render(write_still=True)
        print("NUCLEAR_STORY_FRAME " + scene.render.filepath)
    print("NUCLEAR_STORY_PREVIEW_DONE")
else:
    try:
        scene.render.image_settings.media_type = "VIDEO"
    except (AttributeError, TypeError):
        pass
    try:
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "HIGH"
    except (AttributeError, TypeError):
        scene.render.image_settings.file_format = "PNG"
    print("NUCLEAR_STORY_RENDERING %d frames" % scene.frame_end)
    bpy.ops.render.render(animation=True)
    print("NUCLEAR_STORY_DONE")
