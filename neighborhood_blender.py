"""
FOLLOWER NEIGHBORHOOD — Blender world generator
================================================
Run this inside Blender (Scripting tab > Open > Run Script).

Every run:
  1. Loads the saved world from world_state.json (next to your .blend file)
  2. Adds EXACTLY the counts you set in CONFIG below
  3. Rebuilds the whole city, animates only today's new buildings rising
  4. Sets up a 9:16 vertical camera + render settings for reels

Day 1: save your .blend in a folder first (so the state file has a home),
set the counts, hit Run. Then press Ctrl+F12 to render the video.

Works on Blender 3.6 – 4.x.
"""

import bpy
import hashlib
import json
import math
import os
import random
import sys
from mathutils import Matrix, Vector

# Pure-data reserve for populations 135..500.  Importing this module creates
# nothing; future houses/roads remain invisible until main() consumes them.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
if _SCRIPT_DIR and _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from neighborhood_plan import PLAN as SUBURBAN_PLAN, HOUSE_CAPACITY as SUBURBAN_CAPACITY
from downtown_visuals import build_downtown_visuals, terrain_height
from world_layout import (DISTRICT_CONNECTORS, STORYBOOK_LAYOUT_CENTER,
                          transform_building_point, transform_point)


EMBEDDED_GENERATOR_HASH_PROPERTY = "followville_generator_sha256"


def _normalized_source(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _source_hash(text):
    return hashlib.sha256(_normalized_source(text).encode("utf-8")).hexdigest()


def _configured_repo_dir():
    configured = (os.environ.get("FOLLOWVILLE_REPO_DIR")
                  or os.environ.get("NEIGHBORHOOD_STATE_DIR")
                  or os.environ.get("NEIGHBORHOOD_REPO_DIR"))
    return os.path.abspath(os.path.expanduser(configured)) if configured else ""


def _assert_gui_generator_current(scene):
    """Refuse direct GUI growth unless the embedded and Git sources agree."""
    repo = _configured_repo_dir()
    if not repo:
        raise RuntimeError(
            "Growth is locked because the Followville repository is not configured. "
            "Use grow_windows.bat/grow.sh instead of growing from a directly opened Blend."
        )
    if not os.path.isdir(os.path.join(repo, ".git")):
        raise RuntimeError("Configured Followville repository is not a Git clone: %s" % repo)

    generator_path = os.path.join(repo, "neighborhood_blender.py")
    state_file = os.path.join(repo, "world_state.json")
    if not os.path.isfile(generator_path) or not os.path.isfile(state_file):
        raise RuntimeError("Configured Followville repository is missing its generator or state")

    with open(generator_path, "r", encoding="utf-8-sig", newline=None) as handle:
        repository_hash = _source_hash(handle.read())
    embedded = bpy.data.texts.get("neighborhood_blender.py")
    if embedded is None:
        raise RuntimeError("The Blend has no embedded Followville generator; run _refresh_text.py")
    embedded_hash = _source_hash(embedded.as_string())
    recorded_hash = scene.get(EMBEDDED_GENERATOR_HASH_PROPERTY, "")
    if not recorded_hash or recorded_hash != repository_hash or embedded_hash != repository_hash:
        raise RuntimeError(
            "The Blend's embedded generator is stale. Run the guarded _refresh_text.py "
            "from the current Git repository before using the Blender Grow button."
        )

# ═══════════════════════════ CONFIG — EDIT THIS DAILY ═══════════════════════════

FOLLOWERS_GAINED = 5     # today's follower gain (drives population counter)

NEW_HOUSES       = 5     # exactly this many houses appear today
NEW_APARTMENTS   = 0     # big buildings for big days (2k followers -> 1 apartment)
NEW_PARKS        = 0     # community milestones
NEW_TREES        = 0     # decoration

REPLAY_LAST_DAY  = False # True = don't add anything, just re-animate yesterday's batch

TIME_OF_DAY      = "auto"  # auto | day | sunset | night  (auto cycles across days)
SEASON           = "auto"  # auto | spring | summer | fall | winter (auto = real date)

AUTO_RENDER      = False # True = render the video immediately after building
FPS              = 30
RES_X, RES_Y     = 1080, 1920   # 9:16 vertical for reels

# ═══════════════ COMMAND-LINE MODE (for automation / AI operators) ══════════════
# blender --background neighborhood.blend --python neighborhood_blender.py -- [args]
#   --pop N          set TOTAL population; houses are added/removed to match
#   --gained N       add exactly N houses (+N population)
#   --lost N         remove exactly N houses (-N population, newest go first)
#   --followers N    override the population change (e.g. apartment days)
#   --apartments N   --parks N   --trees N
#   --render         render the day's video after building
#   --still          render one preview PNG after building
#   --replay         re-animate the last day, change nothing
#   --cam newgrowth  frame the largest cluster of today's rising houses
#   --cam newgrowthoverhead  top-down view of today's rising houses
#   --cam wholeoverhead  whole-town sky view; all of today's houses rise
#   --cam newstreet  finished eye-level glide through today's busiest street
#   --cam storybookstreet  finished road-level tour of Kaleidoscope Crest
#   --cam housefront  sidewalk view of a current house with passing cars
#   --cam football   temporary England v Argentina supporter vignette
#   --scatter        use the old pure-radial lot order instead of the
#                     default block-fill order (2026-07-10) -- scatters new
#                     buildings across many blocks instead of filling one
#                     solid before starting the next
# When any CLI args are given, the CONFIG constants above are ignored.

def _cli():
    if "--" not in sys.argv:
        return {}
    args = sys.argv[sys.argv.index("--") + 1:]
    flags = {"--render": "render", "--still": "still", "--replay": "replay",
             "--hero": "hero", "--celebrate": "celebrate", "--pond": "pond",
             "--parkring": "parkring", "--scatter": "scatter"}
    keys = {"--pop": "pop", "--gained": "gained", "--lost": "lost",
            "--followers": "followers", "--houses": "gained",
            "--apartments": "apartments", "--parks": "parks", "--trees": "trees",
            "--mushrooms": "mushrooms", "--storybook-houses": "storybook_houses"}
    skeys = {"--time": "time", "--season": "season", "--cam": "cam", "--tag": "tag",
             "--focus-type": "focus_type"}
    out, i = {}, 0
    while i < len(args):
        a = args[i]
        if a == "--special" and i + 1 < len(args):
            out.setdefault("special", []).append(args[i + 1])
            i += 2
        elif a in flags:
            out[flags[a]] = True
            i += 1
        elif a in keys and i + 1 < len(args):
            out[keys[a]] = int(args[i + 1])
            i += 2
        elif a in skeys and i + 1 < len(args):
            out[skeys[a]] = args[i + 1]
            i += 2
        else:
            i += 1
    return out

CLI = _cli()

# ═════════════════════════════ WORLD LAYOUT CONSTANTS ═══════════════════════════

LOT      = 13                    # expanded downtown lot spacing (m)
BLOCK_N  = 3                     # lots per block side
ROAD     = 6                     # road width (m)
PITCH    = BLOCK_N * LOT + ROAD  # block repeat distance

WALLS = [(0.96, 0.90, 0.81), (0.91, 0.84, 0.77), (0.97, 0.82, 0.79),
         (0.85, 0.89, 0.87), (0.90, 0.89, 0.94), (0.98, 0.93, 0.82),
         (0.86, 0.91, 0.96)]
ROOFS = [(0.75, 0.34, 0.31), (0.54, 0.60, 0.36), (0.36, 0.49, 0.60),
         (0.71, 0.52, 0.42), (0.49, 0.42, 0.57), (0.66, 0.37, 0.43)]
GREENS = [(0.31, 0.54, 0.31), (0.36, 0.61, 0.33), (0.25, 0.49, 0.27)]
# bolder pastels for the day-8 park-ring homes (mint/peach/lilac/butter/sky)
RING_WALLS = WALLS + [(0.78, 0.91, 0.82), (0.99, 0.86, 0.72), (0.84, 0.80, 0.94),
                      (0.99, 0.94, 0.70), (0.74, 0.87, 0.95), (0.97, 0.78, 0.84)]

# Day-15 feature neighborhood. The ten houses remain original Followville
# designs. Cade later requested a clearly recognizable Cat in the Hat public
# art statue for the center island; keep it separate from the claimable homes.
# The houses sit on the flat crown of a permanent landscaped hill and face the
# revealed loop.
STORYBOOK_CENTER = (270.0, 60.0)
STORYBOOK_GROUND_Z = 2.82
STORYBOOK_DISTRICT = "Kaleidoscope Crest"
STORYBOOK_STREET = "Wanderlight Loop"
STORYBOOK_FEATURE_ID = "kaleidoscope_crest_day15"


def _storybook_slots():
    slots = []
    # Keep a generous west-side opening for the winding access road.
    gap = .92
    start = math.pi + gap / 2
    span = math.tau - gap
    for index in range(10):
        angle = start + span * (index + .5) / 10
        slots.append({
            "x": round(STORYBOOK_CENTER[0] + 43.0 * math.cos(angle), 3),
            "y": round(STORYBOOK_CENTER[1] + 33.0 * math.sin(angle), 3),
            "z": STORYBOOK_GROUND_Z,
            "rot": round(angle - math.pi / 2, 5),
            "index": index,
        })
    return slots


STORYBOOK_SLOTS = _storybook_slots()

# ═══════════════════════════════ STATE PERSISTENCE ══════════════════════════════

def state_path():
    # NEIGHBORHOOD_STATE_DIR lets the caller redirect world_state.json somewhere
    # other than "next to the .blend" -- specifically, grow_windows.ps1/grow.sh
    # can point this at a git repo clone instead of the iCloud-synced folder,
    # so the one file that gets read-modified-written every growth day never
    # sits inside iCloud's sync path (see CLAUDE.md's iCloud race-condition
    # writeup, 2026-07-08, for why that matters). Unset = old behavior,
    # unchanged, so this is a no-op for anyone who hasn't opted in.
    override = os.environ.get("NEIGHBORHOOD_STATE_DIR")
    if override:
        return os.path.join(override, "world_state.json")
    if bpy.data.filepath:
        return os.path.join(os.path.dirname(bpy.data.filepath), "world_state.json")
    return os.path.join(os.path.expanduser("~"), "neighborhood_world_state.json")

def load_state():
    p = state_path()
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"day": 0, "pop": 0, "seed_counter": 1, "buildings": []}

def save_state(state):
    with open(state_path(), "w") as f:
        json.dump(state, f, indent=1)

# ══════════════════════════════════ MATERIALS ═══════════════════════════════════

def mat(name, rgb, rough=0.85, metallic=0.0, alpha=1.0,
        transmission=0.0, coat=0.0):
    m = bpy.data.materials.get(name)
    if not m:
        m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Alpha"].default_value = alpha
    transmission_input = (bsdf.inputs.get("Transmission Weight")
                          or bsdf.inputs.get("Transmission"))
    if transmission_input:
        transmission_input.default_value = transmission
    coat_input = bsdf.inputs.get("Coat Weight") or bsdf.inputs.get("Clearcoat")
    if coat_input:
        coat_input.default_value = coat
    m.diffuse_color = (*rgb, alpha)
    if alpha < .999:
        m.surface_render_method = "DITHERED"
        m.use_transparency_overlap = False
    return m

def std_mats():
    return {
        "grass":  mat("NB_grass",  (0.42, 0.60, 0.33), 1.0),
        "lawn":   mat("NB_lawn",   (0.40, 0.66, 0.30), 1.0),
        "road":   mat("NB_road",   (0.30, 0.31, 0.33), 0.9),
        "dash":   mat("NB_dash",   (0.85, 0.80, 0.40), 0.9),
        "trunk":  mat("NB_trunk",  (0.44, 0.31, 0.21), 1.0),
        "door":   mat("NB_door",   (0.36, 0.24, 0.17), 0.8),
        "window": mat("NB_window", (0.95, 0.90, 0.70), .16, .04, 1.0, 0.0, .42),
        "windark": mat("NB_windark", (0.10, 0.19, 0.28), .14, .12, 1.0, 0.0, .62),
        "water":  mat("NB_water",  (0.24, 0.52, 0.72), .08, .05, .90, .32, .72),
        "metal":  mat("NB_metal",  (0.25, 0.27, 0.30), 0.5),
        "cap":    mat("NB_cap",    (0.32, 0.34, 0.38), 0.8),
        "bulb":   mat("NB_bulb",   (1.0, 0.95, 0.75), 0.2),
    }

# ═══════════════════════════ LOW-LEVEL MESH HELPERS ═════════════════════════════
# (no bpy.ops — fast and reliable; z-up, objects sit on z=0)

def _link_only(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)

def add_box(col, name, w, d, h, x, y, z, material):
    """Box of size w,d,h whose BOTTOM sits at z."""
    verts, faces = [], []
    hw, hd = w / 2, d / 2
    for dz in (0, h):
        verts += [(-hw, -hd, dz), (hw, -hd, dz), (hw, hd, dz), (-hw, hd, dz)]
    faces = [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
             (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = (x, y, z)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj

def add_beam_between(col, name, start, end, thickness, material):
    """Square-section beam whose ends land exactly on start and end."""
    p0, p1 = Vector(start), Vector(end)
    delta = p1 - p0
    if delta.length <= 1e-6:
        raise ValueError("Beam endpoints must be different")
    obj = add_box(col, name, thickness, thickness, delta.length,
                  p0.x, p0.y, p0.z, material)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = delta.to_track_quat("Z", "Y")
    return obj

def add_ngon_cone(col, name, r_bot, r_top, h, sides, x, y, z, material, rot=0.0):
    """Cone/cylinder with n sides. r_top=0 => cone. Bottom at z."""
    verts, faces = [], []
    for i in range(sides):
        a = rot + i / sides * math.tau
        verts.append((r_bot * math.cos(a), r_bot * math.sin(a), 0))
    if r_top > 0:
        for i in range(sides):
            a = rot + i / sides * math.tau
            verts.append((r_top * math.cos(a), r_top * math.sin(a), h))
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((i, j, sides + j, sides + i))
        faces.append(tuple(range(sides - 1, -1, -1)))
        faces.append(tuple(range(sides, 2 * sides)))
    else:
        verts.append((0, 0, h))
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((i, j, sides))
        faces.append(tuple(range(sides - 1, -1, -1)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = (x, y, z)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj


def add_tapered_box(col, name, w0, d0, w1, d1, h, x, y, z,
                    top_dx, top_dy, material):
    """A four-sided story whose upper floor can taper and lean off-center."""
    verts = [(-w0/2, -d0/2, 0), (w0/2, -d0/2, 0),
             (w0/2, d0/2, 0), (-w0/2, d0/2, 0),
             (top_dx-w1/2, top_dy-d1/2, h),
             (top_dx+w1/2, top_dy-d1/2, h),
             (top_dx+w1/2, top_dy+d1/2, h),
             (top_dx-w1/2, top_dy+d1/2, h)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7),
             (0, 1, 5, 4), (1, 2, 6, 5),
             (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x, y, z)
    col.objects.link(obj)
    return obj


def add_offset_pyramid(col, name, w, d, h, x, y, z, apex_dx, apex_dy, material):
    """Asymmetric four-sided roof with a deliberately off-center peak."""
    verts = [(-w/2, -d/2, 0), (w/2, -d/2, 0),
             (w/2, d/2, 0), (-w/2, d/2, 0),
             (apex_dx, apex_dy, h)]
    faces = [(0, 3, 2, 1), (0, 1, 4), (1, 2, 4),
             (2, 3, 4), (3, 0, 4)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x, y, z)
    col.objects.link(obj)
    return obj

def add_prism_roof(col, name, w, d, h, x, y, z, material):
    """Gable roof: triangular prism, ridge along x. Bottom at z."""
    hw, hd = w / 2, d / 2
    verts = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
             (-hw, 0, h), (hw, 0, h)]
    faces = [(0, 1, 2, 3), (0, 4, 5, 1), (2, 5, 4, 3), (0, 3, 4), (1, 5, 2)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = (x, y, z)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj

def add_text(col, name, body, size, depth, x, y, z, material,
             rotation=(math.pi / 2, 0, 0)):
    """Small extruded title card text, facing toward negative Y by default."""
    curve = bpy.data.curves.new(name, type="FONT")
    curve.body = body
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.size = size
    curve.extrude = depth
    curve.bevel_depth = min(0.025, depth * 0.25)
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    obj.location = (x, y, z)
    obj.rotation_euler = rotation
    col.objects.link(obj)
    return obj

def add_uv_sphere(col, name, radius, x, y, z, material, rings=8, segments=12):
    """Low-poly sphere without operators, safe for background rendering."""
    verts = [(0, 0, radius), (0, 0, -radius)]
    for ring in range(1, rings):
        phi = math.pi * ring / rings
        for seg in range(segments):
            theta = math.tau * seg / segments
            verts.append((radius * math.sin(phi) * math.cos(theta),
                          radius * math.sin(phi) * math.sin(theta),
                          radius * math.cos(phi)))
    faces = []
    first_ring = 2
    for seg in range(segments):
        faces.append((0, first_ring + seg,
                      first_ring + (seg + 1) % segments))
    for ring in range(rings - 2):
        a0 = first_ring + ring * segments
        b0 = a0 + segments
        for seg in range(segments):
            nxt = (seg + 1) % segments
            faces.append((a0 + seg, b0 + seg, b0 + nxt, a0 + nxt))
    last_ring = first_ring + (rings - 2) * segments
    for seg in range(segments):
        faces.append((1, last_ring + (seg + 1) % segments, last_ring + seg))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = (x, y, z)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj

# ═══════════════════════════════ ASSET LIBRARY ══════════════════════════════════
# Each asset lives in its own collection (NOT linked to the scene) and is placed
# in the world via collection-instance empties. Edit these builders / add your
# own asset functions to grow the model library.

def get_asset(name, builder):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        builder(col)
    return col

def build_tree(col, rng, scale=1.0, px=0.0, py=0.0):
    s = scale
    m = std_mats()
    add_ngon_cone(col, "trunk", 0.4 * s, 0.3 * s, 2.0 * s, 6, px, py, 0, m["trunk"])
    green = mat("NB_green%d" % rng.randrange(len(GREENS)), GREENS[rng.randrange(len(GREENS))])
    if rng.random() < 0.5:
        add_ngon_cone(col, "pine1", 1.8 * s, 0, 3.0 * s, 7, px, py, 1.8 * s, green)
        add_ngon_cone(col, "pine2", 1.3 * s, 0, 2.3 * s, 7, px, py, 3.6 * s, green)
    else:
        blob = add_ngon_cone(col, "blob", 1.9 * s, 0.7 * s, 2.8 * s, 7, px, py, 1.8 * s, green)
        add_ngon_cone(col, "blobtop", 0.7 * s, 0, 0.9 * s, 7, px, py, 4.6 * s, green)

SUBURBAN_PALETTES = [
    # wall, roof, door, shutter -- restrained colors keep whole streets cohesive
    ((0.88, 0.80, 0.66), (0.32, 0.23, 0.18), (0.18, 0.37, 0.24), (0.22, 0.40, 0.48)),
    ((0.47, 0.64, 0.71), (0.20, 0.22, 0.24), (0.52, 0.15, 0.12), (0.32, 0.49, 0.61)),
    ((0.58, 0.68, 0.55), (0.22, 0.31, 0.38), (0.16, 0.34, 0.47), (0.18, 0.35, 0.25)),
    ((0.83, 0.61, 0.49), (0.37, 0.24, 0.18), (0.24, 0.31, 0.42), (0.49, 0.28, 0.22)),
    ((0.78, 0.79, 0.74), (0.27, 0.29, 0.30), (0.46, 0.22, 0.15), (0.31, 0.42, 0.44)),
    ((0.79, 0.73, 0.82), (0.34, 0.27, 0.38), (0.20, 0.38, 0.35), (0.43, 0.31, 0.48)),
]

# Fifteen normal suburban silhouettes. Every entry fits a single 10m lot and
# faces local -Y. Existing/future building seeds select both style and color,
# so rerenders stay stable and claims never move to a different building ID.
SUBURBAN_STYLES = [
    # name, width, depth, floors, garage side, porch, roof height, feature
    ("classic_ranch",       7.9, 5.7, 1,  1, "small", 1.75, "brick"),
    ("wide_ranch",          8.5, 5.4, 1, -1, "small", 1.55, "stone"),
    ("raised_ranch",        7.7, 5.8, 1,  1, "stoop", 1.85, "raised"),
    ("split_level",         8.3, 5.7, 2,  1, "stoop", 1.55, "split"),
    ("center_colonial",     7.1, 5.7, 2, -1, "portico", 2.05, "colonial"),
    ("garage_colonial",     7.8, 5.8, 2,  1, "portico", 1.90, "belt"),
    ("craftsman",           7.5, 5.9, 1, -1, "wide", 2.20, "craftsman"),
    ("cape_cod",            7.2, 5.5, 1,  1, "small", 2.45, "dormers"),
    ("suburban_farmhouse",  7.4, 5.8, 2, -1, "wide", 2.15, "farmhouse"),
    ("modern_suburban",     7.8, 5.6, 2,  1, "stoop", 1.25, "modern"),
    ("front_gable",         7.0, 5.9, 2, -1, "portico", 2.00, "frontgable"),
    ("l_shaped_ranch",      8.4, 5.8, 1,  1, "small", 1.70, "wing"),
    ("side_garage_two",     8.2, 5.9, 2, -1, "small", 1.85, "sidewing"),
    ("starter_suburban",    6.7, 5.3, 1,  1, "stoop", 1.75, "simplegable"),
    ("double_garage",       8.6, 5.9, 2, -1, "portico", 1.85, "doublegarage"),
]

# Lots at branch merges and adjacent cul-de-sac arcs are intentionally tighter
# than the main road frontage. These plan IDs use the compact lot footprint;
# every other planned address uses the standard .78 footprint. The set was
# audited against all 366 reserved addresses with oriented bounding boxes.
SUBURBAN_TIGHT_PLAN_IDS = {
    7, 19, 39, 40, 61, 62, 63, 93, 94, 95, 115, 116, 124, 125, 126, 128,
    134, 135, 136, 158, 160, 162, 163, 164, 165, 180, 182, 193, 194, 195,
    196, 197, 205, 206, 207, 208, 211, 212, 255, 256, 257, 258, 259, 260,
    271, 280, 291, 292, 293, 294, 295, 296, 297, 298, 308, 310, 312, 313,
    314, 315, 316, 317, 318, 326, 327, 349, 350,
}


def _sub_window(col, name, x, y, z, trim, glass, shutter=None,
                width=1.12, height=1.18):
    """Layered street-facing window with frame, glass, mullions and sill."""
    add_box(col, name + "_frame", width + .24, .12, height + .24,
            x, y, z, trim)
    add_box(col, name + "_glass", width, .08, height,
            x, y - .08, z + .12, glass)
    add_box(col, name + "_mv", .07, .06, height,
            x, y - .14, z + .12, trim)
    add_box(col, name + "_mh", width, .06, .07,
            x, y - .14, z + .12 + height * .49, trim)
    add_box(col, name + "_sill", width + .34, .24, .10,
            x, y - .08, z - .09, trim)
    if shutter:
        for side in (-1, 1):
            sx = x + side * (width / 2 + .18)
            add_box(col, name + "_shutter", .22, .10, height + .10,
                    sx, y - .08, z + .07, shutter)
            for iz in range(3):
                add_box(col, name + "_slat", .15, .05, .035,
                        sx, y - .15, z + .30 + iz * .33, trim)


def _sub_side_window(col, name, x, y, z, side, trim, glass):
    add_box(col, name + "_frame", .12, 1.28, 1.40, x, y, z, trim)
    add_box(col, name + "_glass", .08, 1.06, 1.18,
            x + side * .08, y, z + .11, glass)
    add_box(col, name + "_mullion", .06, .07, 1.18,
            x + side * .14, y, z + .11, trim)
    add_box(col, name + "_cross", .06, 1.06, .07,
            x + side * .14, y, z + .68, trim)


def _sub_door(col, name, x, front_y, z0, trim, door, glass, m):
    add_box(col, name + "_frame", 1.42, .24, 2.42,
            x, front_y - .10, z0, trim)
    add_box(col, name + "_slab", 1.10, .11, 2.14,
            x, front_y - .23, z0 + .13, door)
    for iz in range(3):
        add_box(col, name + "_panel", .70, .055, .35,
                x, front_y - .31, z0 + .34 + iz * .57, trim)
    add_box(col, name + "_knob", .10, .07, .10,
            x + .36, front_y - .36, z0 + 1.00, m["metal"])
    add_box(col, name + "_porchlight", .16, .18, .30,
            x + .90, front_y - .15, z0 + 1.76, glass)


def _sub_garage(col, name, x, front_y, z0, width, trim, garage, glass, m):
    add_box(col, name + "_frame", width + .34, .22, 2.35,
            x, front_y - .10, z0, trim)
    add_box(col, name + "_door", width, .10, 2.05,
            x, front_y - .23, z0 + .14, garage)
    for iz in range(4):
        add_box(col, name + "_seam", width - .15, .05, .035,
                x, front_y - .31, z0 + .43 + iz * .41, m["cap"])
    for ix in (-.72, 0, .72):
        if abs(ix) < width / 2 - .20:
            add_box(col, name + "_topglass", .45, .05, .28,
                    x + ix, front_y - .32, z0 + 1.68, glass)


def _sub_porch(col, name, x, front_y, z0, kind, trim, roof, m):
    widths = {"stoop": 1.75, "small": 2.45, "portico": 2.75, "wide": 3.65}
    width = widths[kind]
    depth = .72 if kind == "stoop" else 1.12
    add_box(col, name + "_deck", width, depth, .22,
            x, front_y - depth / 2, z0 - .03, m["trunk"])
    for iz in range(3):
        sw = 1.75 - iz * .18
        add_box(col, name + "_step", sw, .34, .16,
                x, front_y - depth - .10 - iz * .25, z0 - .10 - iz * .14,
                m["cap"])
    if kind != "stoop":
        for px in (x - width / 2 + .22, x + width / 2 - .22):
            add_box(col, name + "_post", .18, .18, 2.18,
                    px, front_y - depth + .18, z0 + .20, trim)
            add_box(col, name + "_postbase", .31, .31, .20,
                    px, front_y - depth + .18, z0 + .12, trim)
        add_box(col, name + "_beam", width, .22, .24,
                x, front_y - depth + .18, z0 + 2.28, trim)
        add_prism_roof(col, name + "_roof", width + .35, depth + .35, .62,
                       x, front_y - depth / 2, z0 + 2.48, roof)
    else:
        add_box(col, name + "_canopy", width + .20, 1.00, .18,
                x, front_y - .46, z0 + 2.38, roof)


def _sub_shrub(col, name, x, y, green, green2):
    add_ngon_cone(col, name + "_base", .34, .40, .48, 8, x, y, .04, green)
    add_ngon_cone(col, name + "_top", .25, .20, .24, 8, x, y, .52, green2)


def _merge_asset_meshes(col, name):
    """Combine one detailed house into one object while retaining materials.

    One collection instance per house is much cheaper in Three.js than 60-90
    tiny trim/window objects. Material slots still create a handful of draw
    groups, but geometry and transforms remain identical in Blender and GLB.
    """
    objects = [obj for obj in list(col.objects) if obj.type == "MESH"]
    if len(objects) < 2:
        return
    vertices, faces, face_mats, face_smooth, materials = [], [], [], [], []
    mat_index = {}
    for obj in objects:
        # Asset collections are intentionally unlinked from the scene until
        # instanced. Blender does not always evaluate matrix_local for those
        # objects, so build the transform explicitly; otherwise every roof,
        # window and porch collapses toward the collection origin when merged.
        matrix = Matrix.LocRotScale(obj.location, obj.rotation_euler.to_quaternion(), obj.scale)
        base = len(vertices)
        vertices.extend(tuple(matrix @ v.co) for v in obj.data.vertices)
        for poly in obj.data.polygons:
            faces.append(tuple(base + i for i in poly.vertices))
            source_mat = (obj.data.materials[poly.material_index]
                          if len(obj.data.materials) else None)
            if source_mat not in mat_index:
                mat_index[source_mat] = len(materials)
                materials.append(source_mat)
            face_mats.append(mat_index[source_mat])
            face_smooth.append(poly.use_smooth)
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    merged = bpy.data.objects.new(name, mesh)
    col.objects.link(merged)
    for material in materials:
        if material:
            mesh.materials.append(material)
    for poly, index, use_smooth in zip(mesh.polygons, face_mats, face_smooth):
        poly.material_index = index
        poly.use_smooth = use_smooth
    for obj in objects:
        bpy.data.objects.remove(obj, do_unlink=True)


def build_suburban_house(col, variant):
    style_index = variant % len(SUBURBAN_STYLES)
    palette_index = (variant // len(SUBURBAN_STYLES)) % len(SUBURBAN_PALETTES)
    name, w, d, floors, garage_side, porch_kind, roof_h, feature = SUBURBAN_STYLES[style_index]
    # Founder house #29's double-garage facade and portico leave no usable front
    # yard. Set that structure back while leaving its drive, walk, and mailbox
    # at the curb so the lot still connects cleanly to its road.
    structure_setback = 1.30 if variant == 29 else 0.0
    wall_c, roof_c, door_c, shutter_c = SUBURBAN_PALETTES[palette_index]
    rng = random.Random(9100 + variant)
    m = std_mats()
    wall = mat("NB_sub_wall_%d" % palette_index, wall_c, .82)
    roof = mat("NB_sub_roof_%d" % palette_index, roof_c, .88)
    door = mat("NB_sub_door_%d" % palette_index, door_c, .72)
    mail_flag = mat("NB_mail_flag", (0.72, 0.12, 0.11), .65)
    shutter = mat("NB_sub_shutter_%d" % palette_index, shutter_c, .78)
    trim = mat("NB_sub_trim", (.94, .92, .84), .76)
    glass = mat("NB_sub_glass", (.075, .18, .27), .13, .12, 1.0, 0.0, .66)
    garage = mat("NB_sub_garage", (.84, .83, .76), .84)
    brick = mat("NB_sub_brick", (.49, .20, .14), .90)
    stone = mat("NB_sub_stone", (.45, .43, .38), .95)
    green = mat("NB_sub_green", (.25, .48, .21), .95)
    green2 = mat("NB_sub_green_light", (.39, .57, .24), .95)

    foundation_z = .12 if feature != "raised" else .38
    body_h = 3.40 if floors == 1 else 5.85
    if feature == "split":
        # Two offset heights give the actual split-level silhouette.
        add_box(col, "left_body", w * .54, d, 4.90, -w * .23, 0, foundation_z, wall)
        add_box(col, "right_body", w * .48, d, 3.48, w * .27, 0, foundation_z, wall)
        add_prism_roof(col, "left_roof", w * .58, d + .58, roof_h,
                       -w * .23, 0, foundation_z + 4.90, roof)
        add_prism_roof(col, "right_roof", w * .52, d + .58, roof_h * .88,
                       w * .27, 0, foundation_z + 3.48, roof)
    elif feature == "wing":
        add_box(col, "main_body", w * .62, d, body_h, -w * .18, 0, foundation_z, wall)
        add_box(col, "front_wing", w * .40, d * .72, body_h + .35,
                w * .31, -d * .13, foundation_z, wall)
        add_prism_roof(col, "main_roof", w * .68, d + .58, roof_h,
                       -w * .18, 0, foundation_z + body_h, roof)
        wing_roof = add_prism_roof(col, "wing_roof", d * .80, w * .44, roof_h * .88,
                                   w * .31, -d * .13, foundation_z + body_h + .35, roof)
        wing_roof.rotation_euler.z = math.pi / 2
    elif feature == "sidewing":
        # The main two-story volume must span the full facade. The original
        # partial-width/offset body left the third upper window floating over
        # empty space, which looked like half of this house failed to load.
        add_box(col, "main_body", w, d, body_h, 0, 0, foundation_z, wall)
        add_box(col, "garage_wing", w * .34, d * .82, 3.50,
                garage_side * w * .34, -d * .09, foundation_z, wall)
        add_prism_roof(col, "main_roof", w + .62, d + .58, roof_h,
                       0, 0, foundation_z + body_h, roof)
        add_prism_roof(col, "wing_roof", w * .38, d * .88, roof_h * .80,
                       garage_side * w * .34, -d * .09, foundation_z + 3.50, roof)
    else:
        add_box(col, "body", w, d, body_h, 0, 0, foundation_z, wall)
        if feature == "frontgable":
            main_roof = add_prism_roof(col, "roof", d + .65, w + .62, roof_h,
                                       0, 0, foundation_z + body_h, roof)
            main_roof.rotation_euler.z = math.pi / 2
        elif feature == "modern":
            add_box(col, "roof_low", w + .42, d + .42, .34,
                    0, 0, foundation_z + body_h, roof)
            add_box(col, "roof_high", w * .47, d + .62, .42,
                    -w * .23, 0, foundation_z + body_h + .34, roof)
        else:
            add_prism_roof(col, "roof", w + .62, d + .62, roof_h,
                           0, 0, foundation_z + body_h, roof)

    add_box(col, "foundation", w + .22, d + .20, .36, 0, 0, 0, m["cap"])
    front_y = -d / 2 - .08
    garage_w = 4.05 if feature == "doublegarage" else 2.58
    garage_x = garage_side * (w / 2 - garage_w / 2 - .20)
    door_x = -garage_side * (w * .19)
    _sub_garage(col, "garage", garage_x, front_y, foundation_z + .04,
                garage_w, trim, garage, glass, m)
    _sub_door(col, "entry", door_x, front_y, foundation_z + .04,
              trim, door, glass, m)
    _sub_porch(col, "porch", door_x, front_y - .10, foundation_z + .04,
               porch_kind, trim, roof, m)

    # Lower windows always stay out of the garage opening.
    open_side_x = -garage_side * (w * .34)
    _sub_window(col, "lower_outer", open_side_x, front_y - .04,
                foundation_z + 1.40, trim, glass, shutter, 1.12, 1.16)
    if abs(open_side_x - door_x) > 1.65:
        _sub_window(col, "lower_inner", (open_side_x + door_x) / 2,
                    front_y - .04, foundation_z + 1.42, trim, glass,
                    None, .94, 1.12)

    if floors == 2 and feature != "split":
        upper_z = foundation_z + 4.18
        for i, ux in enumerate((-w * .33, 0, w * .33)):
            _sub_window(col, "upper_%d" % i, ux, front_y - .04, upper_z,
                        trim, glass, shutter if i != 1 else None, 1.02, 1.18)
        add_box(col, "story_belt", w + .18, .20, .16,
                0, front_y - .01, foundation_z + 3.18, trim)
    if feature == "split":
        # Keep both upper windows inside the tall half. The earlier generic
        # three-window row overlapped an extra split window and looked broken.
        for i, sx in enumerate((-w * .34, -w * .13)):
            _sub_window(col, "split_upper_%d" % i, sx, front_y - .04,
                        foundation_z + 3.48, trim, glass,
                        shutter if i == 0 else None, 1.08, 1.18)
    if feature == "dormers":
        for dx in (-1.65, 1.65):
            add_box(col, "dormer", 1.28, .78, 1.02,
                    dx, -.88, foundation_z + body_h + 1.88, wall)
            add_prism_roof(col, "dormer_roof", 1.55, 1.12, .62,
                           dx, -.88, foundation_z + body_h + 2.88, roof)
            _sub_window(col, "dormer_window", dx, -1.31,
                        foundation_z + body_h + 2.02, trim, glass, None, .68, .65)
    if feature in ("colonial", "farmhouse", "frontgable"):
        add_box(col, "entry_gable_face", 2.65, .70, .88,
                door_x, front_y - .40, foundation_z + body_h - .20, wall)
        add_prism_roof(col, "entry_gable", 2.95, 1.55, .95,
                       door_x, front_y - .45, foundation_z + body_h + .62, roof)
    if feature in ("brick", "raised", "belt"):
        add_box(col, "brick_skirt", w - .10, .14, .66,
                0, front_y - .01, foundation_z, brick)
    elif feature in ("stone", "craftsman", "split"):
        add_box(col, "stone_skirt", w - .10, .14, .72,
                0, front_y - .01, foundation_z, stone)

    _sub_side_window(col, "side_window", garage_side * (w / 2 + .02), .45,
                     foundation_z + 1.46, garage_side, trim, glass)
    if floors == 2:
        _sub_side_window(col, "side_upper", garage_side * (w / 2 + .02), .45,
                         foundation_z + 4.16, garage_side, trim, glass)

    # Driveway extends toward the street from the garage. Landscaping is
    # deliberately restricted to the opposite planting bed, never this x-zone.
    drive_front = -4.90
    drive_back = front_y + structure_setback - .02
    drive_depth = max(.80, drive_back - drive_front)
    add_box(col, "driveway", garage_w + .48, drive_depth, .09,
            garage_x, (drive_front + drive_back) / 2, .02, m["cap"])
    if structure_setback:
        walk_front, walk_back = -4.82, front_y + structure_setback - .10
        add_box(col, "front_walk", 1.08, walk_back - walk_front, .10,
                door_x, (walk_front + walk_back) / 2, .03, m["cap"])
    else:
        add_box(col, "front_walk", 1.08, max(.65, -4.82 - (front_y - 1.0)), .10,
                door_x, -4.05, .03, m["cap"])
    bed_center = -garage_side * (w * .34)
    for i, bx in enumerate((bed_center - .42, bed_center + .42)):
        # Extra exclusion check is cheap insurance if future style dimensions change.
        if abs(bx - garage_x) > garage_w / 2 + .38:
            _sub_shrub(col, "shrub_%d" % i, bx, front_y - .34, green, green2)
    mailbox_x = -garage_side * (w / 2 - .38)
    add_box(col, "mailpost", .13, .13, 1.02, mailbox_x, -4.62, .02, m["trunk"])
    add_box(col, "mailbox", .42, .66, .34, mailbox_x, -4.66, .98, m["metal"])
    add_box(col, "mailflag", .06, .07, .46,
            mailbox_x + .25, -4.66, 1.08, mail_flag)

    if feature in ("classic_ranch", "colonial", "farmhouse") or rng.random() < .24:
        add_box(col, "chimney", .64, .68, 1.45,
                -garage_side * w * .30, .72, foundation_z + body_h + .72, brick)
        add_box(col, "chimney_cap", .82, .86, .16,
                -garage_side * w * .30, .72, foundation_z + body_h + 2.13, m["cap"])

    if structure_setback:
        curb_anchored = ("driveway", "front_walk", "mailpost", "mailbox", "mailflag")
        for obj in list(col.objects):
            if obj.type == "MESH" and not obj.name.lower().startswith(curb_anchored):
                obj.location.y += structure_setback

    _merge_asset_meshes(col, "suburban_%02d_%s" % (variant, name))


STORYBOOK_PALETTES = [
    ((0.96, .48, .36), (.30, .10, .42), (.08, .51, .58)),
    ((.24, .68, .77), (.94, .31, .45), (.94, .70, .18)),
    ((.92, .70, .22), (.13, .48, .50), (.72, .17, .42)),
    ((.52, .37, .78), (.96, .51, .20), (.18, .61, .40)),
    ((.41, .75, .47), (.39, .14, .56), (.94, .39, .32)),
    ((.96, .57, .68), (.13, .44, .68), (.84, .66, .12)),
    ((.28, .60, .91), (.84, .19, .34), (.95, .59, .19)),
    ((.95, .42, .19), (.18, .55, .48), (.52, .24, .71)),
    ((.72, .77, .25), (.48, .17, .55), (.10, .52, .72)),
    ((.50, .71, .84), (.89, .27, .55), (.91, .61, .12)),
]


def build_storybook_house(col, variant):
    """One of ten original crooked-storybook homes for Wanderlight Loop.

    The silhouettes share a coherent material system but change height,
    tower count, lean, roof language, window rhythm, chimney, garden, and
    trim. Everything is merged to one multi-material mesh so the richer art
    direction does not turn ten homes into hundreds of web draw objects.
    """
    variant %= 10
    rng = random.Random(15150 + variant)
    m = std_mats()
    wall_c, roof_c, door_c = STORYBOOK_PALETTES[variant]
    wall = mat("NB_story_wall_%02d" % variant, wall_c, .80)
    wall2 = mat("NB_story_wall2_%02d" % variant,
                tuple(min(1.0, c * .82 + .18) for c in wall_c), .84)
    roof = mat("NB_story_roof_%02d" % variant, roof_c, .86)
    roof2 = mat("NB_story_roof2_%02d" % variant,
                tuple(min(1.0, c * .72 + .14) for c in roof_c), .88)
    door = mat("NB_story_door_%02d" % variant, door_c, .70)
    trim = mat("NB_story_trim", (.97, .90, .66), .76)
    glass = mat("NB_story_glass", (.065, .20, .32), .13, .10, 1.0, 0.0, .64)
    lawn = mat("NB_story_lawn", (.35, .68, .27), 1.0)
    path = mat("NB_story_path", (.92, .76, .48), .94)
    fence = mat("NB_story_fence", (.89, .77, .56), .88)
    flower_mats = [
        mat("NB_story_flower_pink", (.97, .34, .55), .78),
        mat("NB_story_flower_gold", (.98, .72, .14), .78),
        mat("NB_story_flower_blue", (.27, .61, .92), .78),
    ]

    widths = (7.2, 8.4, 6.8, 6.5, 7.8, 8.8, 7.4, 6.6, 8.6, 6.2)
    depths = (6.1, 5.8, 6.5, 5.9, 6.3, 5.7, 6.4, 5.8, 6.0, 6.2)
    lower_heights = (3.8, 4.0, 4.2, 3.6, 4.1, 3.7, 3.9, 3.8, 3.7, 4.0)
    upper_levels = (1, 0, 1, 2, 1, 0, 1, 2, 0, 2)
    leans = (-.55, .35, .62, -.48, .44, -.30, -.62, .52, .27, -.42)
    w, d, lower_h = widths[variant], depths[variant], lower_heights[variant]
    lean = leans[variant]
    foundation_z = .30

    # Complete authored lot: clipped oval-like lawn, stepping path, planting
    # beds, side fences, and a curb-side mailbox. The front edge stops before
    # the colored asphalt, so these details cannot repeat the old road-overlap
    # failure of the optional homeowner yard pieces.
    add_box(col, "yard", 10.6, 13.0, .14, 0, -.15, 0, lawn)
    add_box(col, "foundation", w + .30, d + .24, .34,
            0, .45, .13, m["cap"])
    add_tapered_box(col, "lower_body", w, d, w * .91, d * .93,
                    lower_h, 0, .45, foundation_z, lean * .30, .10, wall)
    add_box(col, "lower_belt", w * .94, .18, .18,
            lean * .15, -d/2 + .38, foundation_z + lower_h * .58, trim)

    # A broad side wing changes the street silhouette on alternating lots.
    if variant in (1, 2, 4, 5, 6, 8):
        side = -1 if variant in (2, 5, 8) else 1
        wing_w = 3.5 + (variant % 3) * .35
        wing_h = 2.85 + (variant % 2) * .38
        wing_x = side * (w/2 + wing_w/2 - .72)
        add_tapered_box(col, "wing", wing_w, d * .72, wing_w * .88, d * .66,
                        wing_h, wing_x, .28, .25, side * .22, -.10, wall2)
        add_offset_pyramid(col, "wing_roof", wing_w + .75, d * .76 + .72,
                           1.65 + (variant % 3) * .22, wing_x, .20,
                           .25 + wing_h, side * .55, -.12, roof2)
        _sub_window(col, "wing_window", wing_x, -d * .30 - .04,
                    1.15, trim, glass, None, .92, 1.02)

    current_z = foundation_z + lower_h
    current_x = lean * .30
    upper_w = w * (.62 if variant not in (3, 7, 9) else .70)
    upper_d = d * .66
    for level in range(upper_levels[variant]):
        story_h = 2.75 + .25 * ((variant + level) % 3)
        level_lean = lean * (1.0 if level == 0 else -.72)
        add_tapered_box(col, "upper_%d" % level,
                        upper_w, upper_d, upper_w * .84, upper_d * .88,
                        story_h, current_x, .48, current_z,
                        level_lean, -.05 + .08 * level, wall2 if level % 2 == 0 else wall)
        add_box(col, "upper_belt_%d" % level, upper_w * .94, .17, .16,
                current_x + level_lean * .45,
                .48 - upper_d/2 - .06, current_z + story_h * .53, trim)
        # Window rows deliberately vary between one, two, and three openings.
        count = 1 + ((variant + level) % 3)
        spacing = upper_w * .54 / max(count - 1, 1)
        for wi in range(count):
            wx = current_x + level_lean * .35 + (wi - (count - 1)/2) * spacing
            _sub_window(col, "upper_%d_win_%d" % (level, wi), wx,
                        .48 - upper_d/2 - .08, current_z + .82,
                        trim, glass, roof2 if count == 1 else None, .76, .94)
        current_x += level_lean
        current_z += story_h
        upper_w *= .82
        upper_d *= .88

    # The roof language changes across the ten variants: pointed crooked
    # pyramids, flared polygonal caps, and split twin roofs.
    if upper_levels[variant]:
        roof_w = max(3.3, upper_w + 1.55)
        roof_d = max(3.1, upper_d + 1.35)
        if variant in (2, 4, 9):
            cap = add_ngon_cone(col, "tower_cap", 1.0, 0.0,
                                2.7 + .28 * variant, 9,
                                current_x, .48, current_z, roof, .18)
            cap.scale = (roof_w/2, roof_d/2, 1)
        else:
            add_offset_pyramid(col, "crooked_roof", roof_w, roof_d,
                               2.5 + .22 * (variant % 4), current_x, .48,
                               current_z, -lean * 1.4, -.38, roof)
    else:
        add_offset_pyramid(col, "broad_roof", w + 1.30, d + 1.22,
                           2.15 + .24 * variant, lean * .30, .45,
                           current_z, -lean * 1.8, -.42, roof)

    # Twin-turret variants get a second, deliberately mismatched vertical.
    if variant in (1, 4, 6):
        side = -1 if variant != 4 else 1
        tx = side * (w * .34)
        tr = 1.45 + .12 * variant
        th = 4.6 + .35 * (variant % 3)
        turret = add_ngon_cone(col, "turret", tr, tr * .82, th, 10,
                               tx, .72, foundation_z + lower_h * .40, wall2, .12)
        turret.scale.y = .92
        tcap = add_ngon_cone(col, "turret_cap", tr * 1.34, 0, 2.35,
                             9, tx, .72, foundation_z + lower_h * .40 + th,
                             roof2, .18)
        tcap.scale.y = .92
        _sub_window(col, "turret_window", tx, -.72,
                    foundation_z + lower_h * .40 + 1.45,
                    trim, glass, None, .70, .88)

    front_y = -d/2 + .36
    door_x = (-.72, .85, -.62, .74, -.88, .58, -.68, .82, -.56, .62)[variant]
    _sub_door(col, "entry", door_x, front_y, .42, trim, door, glass, m)
    _sub_porch(col, "porch", door_x, front_y - .05, .42,
               "small" if variant % 3 else "stoop", trim, roof2, m)
    for i, wx in enumerate((-w * .28, w * .28)):
        if abs(wx - door_x) > 1.15:
            _sub_window(col, "lower_window_%d" % i, wx, front_y - .08,
                        1.18, trim, glass, roof2 if i == variant % 2 else None,
                        .92 + .08 * (variant % 2), 1.08)

    # A segmented bent chimney makes the facing readable from overhead while
    # keeping every segment fully connected to the next.
    chimney_x = (-1 if variant % 2 else 1) * w * .27
    chimney_base = foundation_z + lower_h + .55
    p0 = (chimney_x, 1.25, chimney_base)
    p1 = (chimney_x + lean * .34, 1.20, chimney_base + 1.20)
    p2 = (chimney_x - lean * .14, 1.18, chimney_base + 2.18)
    add_beam_between(col, "chimney_low", p0, p1, .48, roof2)
    add_beam_between(col, "chimney_high", p1, p2, .43, roof2)
    add_box(col, "chimney_cap", .76, .72, .17, p2[0], p2[1], p2[2], m["cap"])

    # Curved-looking stepping stones and dense but collision-safe flower beds.
    for i in range(5):
        sy = front_y - 1.10 - i * .72
        sx = door_x * max(0, 1 - i/5) + math.sin(i * .85 + variant) * .18
        stone = add_box(col, "stepstone_%d" % i, 1.18, .62, .09,
                        sx, sy, .14, path)
        stone.rotation_euler.z = math.radians((-7, 5, -4, 7, -3)[i])
    for side in (-1, 1):
        bed_x = side * 3.65
        add_box(col, "flowerbed", 1.35, 3.25, .12,
                bed_x, -2.25, .14, m["trunk"])
        for fi in range(5):
            fx = bed_x + (fi % 2 - .5) * .48
            fy = -3.45 + fi * .57
            add_ngon_cone(col, "flower_stem", .055, .045, .30, 6,
                          fx, fy, .26, m["trunk"])
            add_uv_sphere(col, "flower_head", .18, fx, fy, .60,
                          flower_mats[(fi + variant + (0 if side < 0 else 1)) % 3], 5, 7)

    # Side/back picket fencing frames each lot without blocking the entrance.
    for side in (-1, 1):
        fx = side * 5.0
        for fy in (-1.8, .1, 2.0, 3.9, 5.4):
            add_box(col, "fence_post", .18, .18, 1.05, fx, fy, .14, fence)
            add_offset_pyramid(col, "fence_cap", .28, .28, .24,
                               fx, fy, 1.19, 0, 0, roof2)
        for fy in (-.85, 1.05, 2.95, 4.65):
            add_box(col, "fence_rail", .14, 1.78, .15, fx, fy, .55, fence)
            add_box(col, "fence_rail", .14, 1.78, .13, fx, fy, .91, fence)

    mailbox_x = -4.20 if door_x > 0 else 4.20
    add_box(col, "mailpost", .16, .16, 1.08, mailbox_x, -6.05, .14, fence)
    add_tapered_box(col, "mailbox", .54, .72, .48, .62, .42,
                    mailbox_x, -6.05, 1.12, .05, 0, roof2)
    add_offset_pyramid(col, "mailbox_roof", .70, .88, .34,
                       mailbox_x + .03, -6.05, 1.54, .12, -.08, roof)

    _merge_asset_meshes(col, "storybook_%02d" % variant)


def build_house(col, seed):
    # Backward-compatible entry point used by docs/custom callers.
    build_suburban_house(col, seed % (len(SUBURBAN_STYLES) * len(SUBURBAN_PALETTES)))


def build_urban_townhouse(col, variant):
    """Compact claim-preserving city home for the legacy downtown grid."""
    rng = random.Random(41000 + variant)
    palettes = (
        ((.46,.20,.14),(.18,.22,.24),(.72,.42,.20)),
        ((.56,.48,.37),(.15,.23,.28),(.20,.38,.34)),
        ((.30,.34,.37),(.11,.19,.24),(.62,.23,.16)),
        ((.39,.18,.15),(.21,.25,.27),(.72,.58,.33)),
        ((.61,.57,.49),(.16,.20,.22),(.28,.35,.48)),
    )
    wall_c, frame_c, door_c = palettes[variant % len(palettes)]
    wall = mat("FV_townhouse_wall_%d" % (variant % len(palettes)), wall_c, .91)
    frame = mat("FV_townhouse_frame", (.82,.79,.70), .86)
    dark = mat("FV_townhouse_window", frame_c, .12, .12, 1.0, 0.0, .65)
    storefront_glass = mat("FV_townhouse_storefront_glass", (.055,.16,.20),
                           .08,.08,.48,.42,.78)
    interior = mat("FV_townhouse_interior", (.095,.075,.060), .88)
    interior_floor = mat("FV_townhouse_interior_floor", (.24,.15,.085), .72)
    interior_light = mat("FV_townhouse_interior_light", (.92,.63,.30), .34)
    display = mat("FV_townhouse_display", (.48,.31,.18), .74)
    door = mat("FV_townhouse_door_%d" % (variant % len(palettes)), door_c, .72)
    roof = mat("FV_townhouse_roof", (.10,.12,.13), .86)
    metal = mat("FV_townhouse_metal", (.12,.14,.15), .62)
    solar = mat("FV_townhouse_solar", (.055,.13,.19), .18, .22, 1.0, 0.0, .62)
    sign = mat("FV_townhouse_sign_%d" % (variant % len(palettes)), door_c, .62)
    floors = 3 + (1 if variant % 7 == 0 else 0)
    # Buildings retain full urban scale. Breathing room now comes from the
    # expanded thirteen-metre lot grid rather than shrinking architecture.
    width = 7.8 + rng.uniform(-.35,.35)
    depth = 7.9 + rng.uniform(-.30,.40)
    floor_h = 2.85
    height = floors*floor_h
    # Real ground-floor shell: an open room behind the glazing, not a tinted
    # rectangle pasted over a solid wall. The upper floors retain the efficient
    # single mass while the street-facing level gets true depth and contents.
    ground_h=2.92
    add_box(col,"upper_wall",width,depth,height-ground_h,0,.25,ground_h,wall)
    add_box(col,"ground_rear",width,.34,ground_h,0,.25+depth/2-.17,.12,wall)
    add_box(col,"ground_left",.36,depth-.34,ground_h,-width/2+.18,.08,.12,wall)
    add_box(col,"ground_right",.36,depth-.34,ground_h,width/2-.18,.08,.12,wall)
    add_box(col,"interior_floor",width-.72,depth-.52,.16,0,.12,.14,interior_floor)
    add_box(col,"interior_ceiling",width-.72,depth-.52,.14,0,.12,2.87,interior)
    add_box(col,"interior_backdrop",width-.95,.12,2.28,0,depth/2-.12,.38,interior)
    # Storefront structure surrounds two actual openings.
    # All storefront surfaces share one exterior plane.  The earlier version
    # placed glass, door and trim at four different Y offsets, so oblique views
    # made the panes look pasted onto the building.
    # Recess the storefront into the real ground-floor shell plane so the
    # glazing reads as architecture, not a glass box pasted to the facade.
    facade_plane_y=.25-depth/2
    facade_depth=.12
    front_y=facade_plane_y+facade_depth/2
    outer_y=facade_plane_y
    glass_depth=.035
    glass_y=facade_plane_y+glass_depth/2
    add_box(col,"storefront_base",width+.12,facade_depth,.30,0,front_y,.18,frame)
    add_box(col,"storefront_lintel",width+.12,facade_depth,.34,0,front_y,2.62,frame)
    add_box(col,"storefront_left_pier",.46,facade_depth,2.44,-width/2+.23,front_y,.48,frame)
    add_box(col,"storefront_right_pier",.46,facade_depth,2.44,width/2-.23,front_y,.48,frame)
    add_box(col,"storefront_center_pier",.48,facade_depth,2.44,-width*.10,front_y,.48,frame)
    door_x=-width*.28
    # A framed glazed door replaces the old solid door with a glass rectangle
    # hovering in front of it.
    add_box(col,"door_left_stile",.18,facade_depth,2.37,door_x-.50,front_y,.24,door)
    add_box(col,"door_right_stile",.18,facade_depth,2.37,door_x+.50,front_y,.24,door)
    add_box(col,"door_bottom_rail",.82,facade_depth,.24,door_x,front_y,.24,door)
    add_box(col,"door_top_rail",.82,facade_depth,.15,door_x,front_y,2.46,door)
    add_box(col,"door_glass",.82,glass_depth,1.67,door_x,glass_y,.48,storefront_glass)
    add_box(col,"door_transom",.82,glass_depth,.31,door_x,glass_y,2.15,storefront_glass)
    sidelight_left=-width/2+.46
    sidelight_right=door_x-.59
    sidelight_width=max(.24,sidelight_right-sidelight_left)
    add_box(col,"door_sidelight",sidelight_width,glass_depth,2.13,
            (sidelight_left+sidelight_right)/2,glass_y,.48,storefront_glass)
    add_box(col,"entry_canopy",1.65,.42,.12,-width*.28,-depth/2-.30,2.66,metal)
    add_box(col,"door_pull",.07,.055,.48,door_x+.31,outer_y-.028,1.05,metal)
    add_box(col,"door_kickplate",.72,.035,.24,door_x,outer_y-.018,.30,metal)
    shop_left=-width*.10+.24
    shop_right=width/2-.46
    shop_width=shop_right-shop_left
    shop_center=(shop_left+shop_right)/2
    add_box(col,"shop_window",shop_width,glass_depth,2.09,shop_center,glass_y,.52,
            storefront_glass)
    for fraction in (1/3,2/3):
        add_box(col,"shop_mullion",.055,.08,2.09,
                shop_left+shop_width*fraction,front_y,.52,frame)
    add_box(col,"shop_sill",shop_width+.26,.16,.16,shop_center,front_y-.02,.42,frame)
    # Visible interior composition: counter, rear shelves, product blocks and
    # warm ceiling panels. These remain low-poly and merge into the house mesh.
    add_box(col,"display_counter",2.75,.62,.86,width*.18,-1.50,.30,display)
    add_box(col,"counter_top",2.95,.72,.12,width*.18,-1.50,1.16,frame)
    for shelf_z in (.72,1.28,1.84):
        add_box(col,"rear_shelf",3.25,.24,.11,width*.15,depth/2-.32,shelf_z,display)
    for item_index in range(6):
        item_x=width*.15+(item_index%3-1)*.82
        item_z=.83+(item_index//3)*.58
        add_box(col,"display_item",.34,.28,.34,item_x,depth/2-.48,item_z,
                door if item_index%2 else sign)
    for light_x in (-width*.22,width*.22):
        add_box(col,"interior_light",.92,.38,.08,light_x,-.10,2.76,interior_light)
    if variant % 3 != 1:
        add_box(col,"shop_canopy",3.85,.48,.14,width*.18,-depth/2-.32,2.66,door)
        for support_x in (-1.45,1.45):
            add_beam_between(col,"awning_support",
                             (width*.18+support_x,-depth/2-.14,2.66),
                             (width*.18+support_x,-depth/2-.48,2.43),.075,metal)
    for floor in range(1,floors):
        z=.72+floor*floor_h
        for ix in (-.27,0,.27):
            x=ix*width
            add_box(col,"window_frame",1.20,.16,1.58,x,-depth/2-.08,z,frame)
            add_box(col,"window",.94,.08,1.32,x,-depth/2-.19,z+.13,dark)
            add_box(col,"window_mullion",.06,.05,1.32,x,-depth/2-.25,z+.13,frame)
            add_box(col,"window_sill",1.34,.28,.12,x,-depth/2-.12,z-.10,frame)
    # Side windows stop the row from reading like a stage-flat facade.
    for floor in range(1,floors):
        z=.76+floor*floor_h
        for y in (-1.8,1.8):
            for side in (-1,1):
                # Sink the frame into the wall and let only a few centimetres
                # project. The former one-centimetre overlap made these panes
                # visibly detach at oblique street angles.
                # Keep several centimetres embedded in the masonry while the
                # visible face remains outside the wall plane.
                frame_x=side*(width/2+.025)
                for frame_y in (y-.605,y+.605):
                    add_box(col,"side_window_jamb",.14,.16,1.48,
                            frame_x,frame_y,z-.115,frame)
                for frame_z in (z-.695,z+.575):
                    add_box(col,"side_window_rail",.14,1.37,.14,
                            frame_x,y,frame_z,frame)
                add_box(col,"side_window",.10,1.05,1.25,
                        side*(width/2+.015),y,z,dark)
    add_box(col,"cornice",width+.55,depth+.55,.42,0,.25,height+.12,frame)
    add_box(col,"roof",width+.12,depth+.12,.42,0,.25,height+.54,roof)
    add_box(col,"roof_access",2.0,2.2,1.45,.9,.65,height+.96,roof)
    for vent_x in (-width*.22,width*.18):
        add_box(col,"roof_vent",.28,.28,.62,vent_x,1.15,height+.96,metal)
        add_box(col,"roof_vent_cap",.44,.44,.12,vent_x,1.15,height+1.54,metal)
    if variant%4==0:
        for sy in (-.62,.62):
            add_box(col,"solar_panel",2.25,.92,.10,-.95,sy,height+.98,solar)
    elif variant%4==1:
        add_box(col,"mechanical_curb",1.72,1.48,.24,-.82,.52,height+.98,metal)
        add_box(col,"mechanical_unit",1.48,1.24,1.02,-.82,.52,height+1.22,roof)
        for louver_x in (-1.23,-.97,-.71,-.45):
            add_box(col,"mechanical_louver",.12,.06,.62,louver_x,-.13,height+1.40,metal)
        add_box(col,"mechanical_cap",1.66,1.42,.16,-.82,.52,height+2.24,metal)
    for side in (-1,1):
        add_box(col,"parapet",.18,depth+.25,.70,side*(width/2),.25,height+.58,metal)
    _merge_asset_meshes(col,"urban_townhouse_%02d" % variant)

def build_apartment(col, seed):
    rng = random.Random(seed)
    m = std_mats()
    wall = mat("NB_awall%d" % seed, WALLS[rng.randrange(len(WALLS))])
    w, d = 14.0, 12.0
    h = 15.0 + rng.random() * 8.0
    add_box(col, "base", w, d, h, 0, 0, 0, wall)
    add_box(col, "roofcap", w + 0.6, d + 0.6, 0.7, 0, 0, h, m["cap"])
    floors = int(h / 3)
    for f in range(1, floors + 1):
        for i in (-1, 0, 1):
            add_box(col, "win", 2.2, 0.15, 1.3, i * 4, -d / 2 - 0.08, f * 3 - 1.9, m["windark"])
            add_box(col, "win", 2.2, 0.15, 1.3, i * 4,  d / 2 + 0.08 - 0.15, f * 3 - 1.9, m["windark"])
    add_box(col, "entry", 2.6, 0.5, 2.6, 0, -d / 2 - 0.2, 0, m["door"])
    build_tree(col, rng, 0.9, w / 2 + 2.2, d / 2 - 1)

def build_shop(col, seed):
    rng = random.Random(seed)
    m = std_mats()
    wall = mat("NB_swall%d" % seed, WALLS[rng.randrange(len(WALLS))])
    accent = mat("NB_saccent%d" % seed, ROOFS[rng.randrange(len(ROOFS))])
    w, d, h = 7.0, 6.0, 3.6
    add_box(col, "base", w, d, h, 0, 0, 0, wall)
    add_box(col, "roofcap", w + 0.5, d + 0.5, 0.5, 0, 0, h, m["cap"])
    add_box(col, "awning", w * 0.9, 1.2, 0.25, 0, -d / 2 - 0.6, 2.6, accent)
    add_box(col, "glass", w * 0.7, 0.2, 1.7, 0, -d / 2 - 0.08, 0.5, m["windark"])

def build_park(col, seed):
    rng = random.Random(seed)
    m = std_mats()
    size = LOT * 2 - 1.5
    add_box(col, "lawn", size, size, 0.35, 0, 0, 0, m["lawn"])
    add_ngon_cone(col, "pond", 3.2, 3.2, 0.45, 18, 3, 3, 0.02, m["water"])
    for i in range(4 + rng.randrange(3)):
        a = rng.random() * math.tau
        r = 4 + rng.random() * 4.5
        build_tree(col, rng, 0.7 + rng.random() * 0.5,
                   math.cos(a) * r - 2, math.sin(a) * r - 2)
    add_box(col, "bench", 2.2, 0.7, 0.55, -4, 4, 0.35, m["trunk"])
    add_box(col, "bench2", 0.7, 2.2, 0.55, 5, -4, 0.35, m["trunk"])

def build_pond(col, seed):
    """A small neighborhood pond -- ducks live here (see build_duck / animate_ducks)."""
    rng = random.Random(seed)
    m = std_mats()
    grass = mat("NB_pond_bank", (0.44, 0.62, 0.34), 1.0)
    reed_g = mat("NB_pond_reed", (0.42, 0.58, 0.28), 0.9)
    stone = mat("NB_pond_stone", (0.62, 0.61, 0.58), 0.95)
    lily = mat("NB_pond_lily", (0.30, 0.52, 0.28), 0.7)
    add_box(col, "bank", LOT - 0.6, LOT - 0.6, 0.25, 0, 0, 0, grass)
    add_ngon_cone(col, "water", 3.9, 3.9, 0.22, 20, 0, 0, 0.02, m["water"])
    add_ngon_cone(col, "waterlip", 4.15, 4.05, 0.1, 20, 0, 0, 0.25, stone)
    for i in range(5 + rng.randrange(3)):  # reeds around the bank
        a = rng.random() * math.tau
        r = 4.3 + rng.random() * 0.6
        add_ngon_cone(col, "reed", 0.08, 0.03, 1.1 + rng.random() * 0.6, 5,
                      math.cos(a) * r, math.sin(a) * r, 0.25, reed_g)
    for i in range(3 + rng.randrange(2)):  # loose pebbles
        a = rng.random() * math.tau
        r = 4.0 + rng.random() * 0.5
        s = 0.3 + rng.random() * 0.3
        add_ngon_cone(col, "pebble", s, s * 0.6, s * 0.5, 6,
                      math.cos(a) * r, math.sin(a) * r, 0.15, stone)
    for i in range(2 + rng.randrange(2)):  # lily pads
        px, py = rng.uniform(-2.0, 2.0), rng.uniform(-2.0, 2.0)
        add_ngon_cone(col, "lily", 0.5 + rng.random() * 0.3, 0.45, 0.05, 8, px, py, 0.24, lily)

DUCK_COLORS = [(0.94, 0.85, 0.25),   # yellow duckling
               (0.36, 0.30, 0.20),   # brown hen mallard
               (0.18, 0.30, 0.20)]   # dark green-headed drake (simplified, whole-body tint)

def build_duck(col, seed):
    """A small duck that paddles a pond -- see animate_ducks for the swim path."""
    rng = random.Random(seed)
    body_c = mat("NB_duck_body%d" % seed, DUCK_COLORS[seed % len(DUCK_COLORS)], 0.6)
    bill = mat("NB_duck_bill", (0.85, 0.55, 0.12), 0.5)
    eye = mat("NB_duck_eye", (0.08, 0.08, 0.08), 0.3)
    b = add_ngon_cone(col, "body", 0.34, 0.24, 0.30, 10, 0, 0, 0.06, body_c)
    b.scale = (1.0, 1.35, 1.0)
    add_ngon_cone(col, "head", 0.16, 0.13, 0.18, 8, 0, 0.32, 0.30, body_c)
    add_box(col, "bill", 0.10, 0.16, 0.06, 0, 0.42, 0.32, bill)
    for sx in (-1, 1):
        add_ngon_cone(col, "eye", 0.02, 0.02, 0.02, 6, sx * 0.07, 0.36, 0.37, eye)
    add_ngon_cone(col, "tail", 0.09, 0.02, 0.14, 6, 0, -0.32, 0.14, body_c)

def build_lone_tree(col, seed):
    rng = random.Random(seed)
    build_tree(col, rng, 0.8 + rng.random() * 0.7,
               (rng.random() - 0.5) * 4, (rng.random() - 0.5) * 4)

def build_bush(col, seed):
    rng = random.Random(seed)
    green = mat("NB_green%d" % rng.randrange(len(GREENS)), GREENS[rng.randrange(len(GREENS))])
    for _ in range(2 + rng.randrange(2)):
        s = 0.6 + rng.random() * 0.7
        add_ngon_cone(col, "bushblob", s, s * 0.55, s * 1.1, 7,
                      (rng.random() - 0.5) * 3.5, (rng.random() - 0.5) * 3.5, 0, green)
    if rng.random() < 0.5:  # little flowers
        fl = mat("NB_flower_dot", (0.95, 0.70, 0.78), 0.8)
        for _ in range(3):
            add_ngon_cone(col, "dot", 0.14, 0.1, 0.25, 6,
                          (rng.random() - 0.5) * 4, (rng.random() - 0.5) * 4, 0, fl)

def build_rock(col, seed):
    rng = random.Random(seed)
    grey = mat("NB_rock", (0.62, 0.61, 0.60), 1.0)
    for _ in range(1 + rng.randrange(3)):
        s = 0.5 + rng.random() * 0.8
        r = add_ngon_cone(col, "rock", s, s * 0.4, s * 0.8, 6,
                          (rng.random() - 0.5) * 3.5, (rng.random() - 0.5) * 3.5, 0, grey, rot=rng.random())
        r.rotation_euler = (0, 0, rng.random() * math.tau)

def build_mushroom_house(col, seed):
    """A cozy mushroom cottage — special-request house."""
    rng = random.Random(seed)
    m = std_mats()
    cream = mat("NB_mush_stem", (0.97, 0.94, 0.85), 0.9)
    caps = [(0.52, 0.06, 0.05), (0.58, 0.13, 0.04), (0.48, 0.05, 0.10)]
    red = mat("NB_mush_cap%d" % (seed % 3), caps[seed % 3], 0.7)
    white = mat("NB_mush_spot", (0.98, 0.97, 0.93), 0.8)
    # stem = the cottage
    add_ngon_cone(col, "stem", 2.9, 2.35, 3.4, 12, 0, 0, 0, cream)
    add_box(col, "door", 1.15, 0.35, 2.0, 0, -2.7, 0, m["door"])
    add_ngon_cone(col, "knob", 0.09, 0.09, 0.1, 6, 0.35, -2.9, 1.0, m["bulb"])
    for t in (math.radians(210), math.radians(330)):  # round-ish windows
        w = add_box(col, "win", 0.95, 0.5, 0.95, 2.5 * math.cos(t), 2.5 * math.sin(t), 1.5, m["window"])
        w.rotation_euler = (0, 0, t + math.pi / 2)
    # cap with underside rim
    add_ngon_cone(col, "rim", 4.95, 4.55, 0.4, 14, 0, 0, 3.1, cream)
    add_ngon_cone(col, "cap", 4.8, 1.0, 2.8, 14, 0, 0, 3.4, red)
    add_ngon_cone(col, "captip", 1.02, 0.0, 0.6, 14, 0, 0, 6.18, red)
    for _ in range(6 + rng.randrange(3)):  # white spots
        t = rng.random() * math.tau
        r = 1.7 + rng.random() * 2.3
        z = 3.4 + (4.8 - r) / (4.8 - 1.0) * 2.8
        s = 0.32 + rng.random() * 0.38
        add_ngon_cone(col, "spot", s, s * 0.7, 0.5, 10,
                      r * math.cos(t), r * math.sin(t), z - 0.3, white)
    # baby mushroom + greenery in the yard
    add_ngon_cone(col, "b_stem", 0.45, 0.38, 1.0, 8, 3.6, -1.6, 0, cream)
    add_ngon_cone(col, "b_cap", 1.05, 0.15, 0.85, 10, 3.6, -1.6, 0.95, red)
    add_ngon_cone(col, "b_spot", 0.2, 0.14, 0.3, 8, 3.2, -2.0, 1.25, white)
    build_tree(col, rng, 0.75, -3.6, 1.8)

def build_casino_house(col, seed):
    """Founder #2: a tiny Vegas casino cottage."""
    rng = random.Random(seed)
    m = std_mats()
    cream = mat("NB_cas_wall", (0.96, 0.92, 0.82), 0.85)
    gold = mat("NB_cas_gold", (0.78, 0.62, 0.22), 0.4)
    red = mat("NB_cas_red", (0.62, 0.10, 0.12), 0.6)
    add_box(col, "base", 6.4, 5.4, 3.6, 0, 0, 0, cream)
    add_box(col, "cap", 6.9, 5.9, 0.5, 0, 0, 3.6, gold)
    add_box(col, "door", 1.5, 0.3, 2.2, 0.6, -2.75, 0, m["door"])
    add_box(col, "carpet", 1.7, 1.6, 0.06, 0.6, -3.6, 0, red)
    add_box(col, "winL", 1.3, 0.2, 1.1, -1.8, -2.75, 1.4, m["windark"])
    # marquee sign with light bulbs
    sign = add_box(col, "sign", 2.3, 0.4, 3.3, -2.6, -3.1, 0.4, red)
    sign.rotation_euler = (0, 0, math.radians(14))
    for i in range(5):
        add_ngon_cone(col, "bulb", 0.14, 0.1, 0.25, 6,
                      -3.45 + i * 0.47, -3.45 + i * 0.11, 3.9 - i * 0.0, m["bulb"])
    star = add_ngon_cone(col, "star", 0.75, 0.0, 0.9, 5, -2.9, -3.2, 3.95, gold)
    # giant dice on the roof
    die = add_box(col, "die", 1.5, 1.5, 1.5, 1.8, 1.2, 4.1, mat("NB_cas_die", (0.97, 0.97, 0.97), 0.5))
    die.rotation_euler = (0, 0, math.radians(28))
    for dx, dy in ((-0.35, -0.35), (0.35, 0.35), (0, 0)):
        add_ngon_cone(col, "pip", 0.16, 0.16, 0.08, 8, 1.8 + dx, 1.2 + dy, 5.6, m["windark"])
    build_tree(col, rng, 0.7, 3.2, -1.8)

def build_cat_house(col, seed):
    """Founder #3: a house that IS a cat."""
    rng = random.Random(seed)
    m = std_mats()
    fur = mat("NB_cat_fur", (0.78, 0.74, 0.71), 0.95)
    dark = mat("NB_cat_dark", (0.45, 0.42, 0.40), 0.9)
    pink = mat("NB_cat_pink", (0.92, 0.60, 0.62), 0.8)
    add_box(col, "body", 6.0, 5.2, 4.2, 0, 0, 0, fur)
    add_prism_roof(col, "roofcap", 6.3, 5.5, 0.9, 0, 0, 4.2, fur)
    # ears
    for sx in (-1, 1):
        ear = add_ngon_cone(col, "ear", 1.0, 0.0, 1.6, 4, sx * 2.0, -1.4, 4.6, dark)
        ear.rotation_euler = (0, 0, math.radians(45))
    # face: eyes, pupils, nose, whiskers — the door is the mouth
    for sx in (-1, 1):
        add_box(col, "eye", 1.05, 0.18, 1.05, sx * 1.5, -2.68, 2.6, mat("NB_cat_eye", (0.97, 0.97, 0.95), 0.4))
        add_box(col, "pupil", 0.4, 0.12, 0.75, sx * 1.5, -2.78, 2.75, m["windark"])
    nose = add_box(col, "nose", 0.55, 0.2, 0.55, 0, -2.75, 1.95, pink)
    nose.rotation_euler = (math.radians(45), 0, 0)
    for sx in (-1, 1):
        for i, ang in enumerate((-12, 0, 12)):
            wh = add_box(col, "whisker", 1.5, 0.08, 0.08, sx * 2.6, -2.8, 2.0 + i * 0.25, dark)
            wh.rotation_euler = (0, 0, math.radians(ang))
    add_box(col, "mouthdoor", 1.3, 0.3, 1.9, 0, -2.7, 0, m["door"])
    # tail curling up the back corner
    t1 = add_ngon_cone(col, "tail1", 0.3, 0.26, 2.6, 8, 2.6, 2.9, 0, dark)
    t2 = add_ngon_cone(col, "tail2", 0.26, 0.18, 1.6, 8, 2.6, 2.9, 2.4, dark)
    t2.rotation_euler = (math.radians(-40), 0, 0)
    for sx in (-1, 1):  # front paws by the door
        add_box(col, "paw", 1.0, 0.9, 0.5, sx * 1.1, -2.9, 0, fur)
    build_tree(col, rng, 0.65, -3.3, 2.0)

def build_castle_house(col, seed):
    """Founder #4: a tiny medieval keep."""
    rng = random.Random(seed)
    m = std_mats()
    stone = mat("NB_cast_stone", (0.63, 0.63, 0.67), 0.95)
    stone2 = mat("NB_cast_stone2", (0.70, 0.70, 0.73), 0.95)
    blue = mat("NB_cast_blue", (0.25, 0.33, 0.52), 0.7)
    red = mat("NB_cast_red", (0.60, 0.12, 0.12), 0.8)
    add_box(col, "keep", 5.6, 5.6, 4.2, 0, 0, 0, stone)
    # crenellations
    for i in range(-2, 3):
        add_box(col, "cren", 0.7, 0.55, 0.7, i * 1.25, -2.65, 4.2, stone2)
        add_box(col, "cren", 0.7, 0.55, 0.7, i * 1.25, 2.65, 4.2, stone2)
        add_box(col, "cren", 0.55, 0.7, 0.7, -2.65, i * 1.25, 4.2, stone2)
        add_box(col, "cren", 0.55, 0.7, 0.7, 2.65, i * 1.25, 4.2, stone2)
    # corner towers with blue cone roofs
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * 2.8, sy * 2.8
            add_ngon_cone(col, "tower", 1.05, 0.95, 5.4, 10, x, y, 0, stone2)
            add_ngon_cone(col, "troof", 1.35, 0.0, 1.9, 10, x, y, 5.4, blue)
    add_box(col, "gate", 1.6, 0.4, 2.5, 0, -2.85, 0, m["door"])
    add_box(col, "slit", 0.3, 0.2, 0.9, -1.4, -2.85, 2.6, m["windark"])
    add_box(col, "slit", 0.3, 0.2, 0.9, 1.4, -2.85, 2.6, m["windark"])
    add_box(col, "banner", 0.9, 0.1, 1.6, 0, -2.9, 2.3, red)
    # flag on one tower
    add_ngon_cone(col, "pole", 0.07, 0.05, 1.8, 6, 2.8, 2.8, 7.3, m["metal"])
    add_box(col, "flag", 1.0, 0.06, 0.5, 3.35, 2.8, 8.5, red)
    build_tree(col, rng, 0.6, -3.6, -0.5)

def build_eiffel_house(col, seed):
    """Founder #5: livable Vegas-style Eiffel Tower."""
    m = std_mats()
    bronze = mat("NB_eif_bronze", (0.45, 0.32, 0.20), 0.6)
    cream = mat("NB_eif_home", (0.96, 0.92, 0.82), 0.85)
    tilt = math.radians(15)
    for sx in (-1, 1):  # four leaning legs
        for sy in (-1, 1):
            leg = add_box(col, "leg", 0.85, 0.85, 5.2, sx * 2.4, sy * 2.4, 0, bronze)
            leg.rotation_euler = (tilt * sy, -tilt * sx, 0)
    add_box(col, "arch", 4.4, 0.5, 0.7, 0, -2.1, 2.6, bronze)  # front arch beam
    # the home: platform level
    add_box(col, "home", 4.6, 4.6, 2.4, 0, 0, 4.6, cream)
    add_box(col, "homedoor", 1.0, 0.3, 1.7, 0, -2.35, 4.6, m["door"])
    add_box(col, "homewin", 0.9, 0.2, 0.8, -1.5, -2.35, 5.6, m["window"])
    add_box(col, "homewin", 0.9, 0.2, 0.8, 1.5, -2.35, 5.6, m["window"])
    add_box(col, "deck", 5.6, 5.6, 0.4, 0, 0, 6.9, bronze)
    # tapering tower above
    add_ngon_cone(col, "t1", 1.7, 1.0, 3.2, 4, 0, 0, 7.3, bronze, rot=math.pi / 4)
    add_ngon_cone(col, "t2", 1.0, 0.5, 2.8, 4, 0, 0, 10.5, bronze, rot=math.pi / 4)
    add_box(col, "topdeck", 1.6, 1.6, 0.35, 0, 0, 13.3, bronze)
    add_ngon_cone(col, "spire", 0.3, 0.0, 1.8, 6, 0, 0, 13.65, bronze)
    add_ngon_cone(col, "beacon", 0.18, 0.14, 0.3, 6, 0, 0, 15.0, m["bulb"])

def build_flower_house(col, seed):
    """Founder #6: pastel pink hydrangea cottage."""
    rng = random.Random(seed)
    m = std_mats()
    stem_g = mat("NB_flw_stem", (0.55, 0.70, 0.48), 0.9)
    leaf_g = mat("NB_flw_leaf", (0.40, 0.60, 0.36), 0.9)
    pinks = [mat("NB_flw_p0", (0.93, 0.55, 0.68), 0.85),
             mat("NB_flw_p1", (0.97, 0.70, 0.79), 0.85),
             mat("NB_flw_p2", (0.88, 0.45, 0.60), 0.85)]
    add_ngon_cone(col, "base", 2.85, 2.55, 3.2, 12, 0, 0, 0, stem_g)
    add_box(col, "door", 1.1, 0.35, 1.9, 0, -2.6, 0, m["door"])
    for t in (math.radians(215), math.radians(325)):
        w = add_box(col, "win", 0.9, 0.5, 0.9, 2.45 * math.cos(t), 2.45 * math.sin(t), 1.5, m["window"])
        w.rotation_euler = (0, 0, t + math.pi / 2)
    # leaf collar
    for i in range(6):
        a = i / 6 * math.tau + 0.3
        leaf = add_ngon_cone(col, "leaf", 1.25, 0.1, 0.6, 5, 3.0 * math.cos(a), 3.0 * math.sin(a), 2.9, leaf_g)
    # hydrangea blossom dome
    add_ngon_cone(col, "bloom0", 2.9, 1.9, 2.1, 12, 0, 0, 3.2, pinks[1])
    for i in range(14):
        a = rng.random() * math.tau
        r = 0.6 + rng.random() * 2.2
        z = 4.6 + (2.6 - r) * 0.55 + rng.random() * 0.4
        s = 0.55 + rng.random() * 0.55
        add_ngon_cone(col, "blob", s, s * 0.55, s * 1.1, 8,
                      r * math.cos(a), r * math.sin(a), z - s * 0.5, pinks[rng.randrange(3)])
    # stepping-stone path
    for i in range(3):
        add_ngon_cone(col, "step", 0.45, 0.45, 0.08, 8, 0, -3.3 - i * 0.9, 0, pinks[1])

def build_burj_house(col, seed):
    """Founder #7: a livable mini Burj Khalifa."""
    m = std_mats()
    glass = mat("NB_burj_glass", (0.52, 0.63, 0.74), 0.25)
    trim = mat("NB_burj_trim", (0.88, 0.90, 0.93), 0.6)
    tiers = [(2.6, 2.3, 6.0, 0.0), (2.0, 1.75, 5.5, 6.0),
             (1.5, 1.3, 5.0, 11.5), (1.0, 0.85, 4.0, 16.5)]
    for i, (rb, rt, h, z) in enumerate(tiers):
        add_ngon_cone(col, "tier%d" % i, rb, rt, h, 6, 0, 0, z, glass)
        add_ngon_cone(col, "trim%d" % i, rb + 0.12, rb + 0.06, 0.35, 6, 0, 0, z, trim)
    add_ngon_cone(col, "spire", 0.4, 0.0, 4.5, 6, 0, 0, 20.5, trim)
    add_ngon_cone(col, "beacon", 0.14, 0.1, 0.25, 6, 0, 0, 24.2, m["bulb"])
    # street-level entrance
    add_box(col, "lobby", 3.4, 3.4, 1.6, 0, 0, 0, trim)
    add_box(col, "door", 1.2, 0.3, 1.4, 0, -1.75, 0, m["door"])
    add_box(col, "awning", 2.0, 0.9, 0.2, 0, -2.3, 1.6, glass)
    build_tree(col, random.Random(seed), 0.6, 2.9, -2.4)

def build_toilet_house(col, seed):
    """A large livable toilet. The people asked."""
    rng = random.Random(seed)
    m = std_mats()
    porcelain = mat("NB_wc_white", (0.93, 0.94, 0.96), 0.35)
    seatm = mat("NB_wc_seat", (0.97, 0.95, 0.90), 0.5)
    silver = mat("NB_wc_silver", (0.75, 0.77, 0.80), 0.3)
    matp = mat("NB_wc_mat", (0.55, 0.75, 0.85), 0.95)
    # bowl = the living room
    add_ngon_cone(col, "bowl", 3.1, 2.55, 2.6, 14, 0, -0.6, 0, porcelain)
    add_ngon_cone(col, "footring", 3.25, 3.1, 0.35, 14, 0, -0.6, 0, porcelain)
    # seat + raised lid leaning on the tank
    add_ngon_cone(col, "seat", 2.95, 2.75, 0.45, 14, 0, -0.6, 2.6, seatm)
    lid = add_ngon_cone(col, "lid", 2.85, 2.75, 0.3, 14, 0, 1.05, 3.4, seatm)
    lid.rotation_euler = (math.radians(-78), 0, 0)
    # tank = the bedroom upstairs
    add_box(col, "tank", 4.4, 1.9, 3.2, 0, 2.35, 2.2, porcelain)
    add_box(col, "tanklid", 4.7, 2.2, 0.4, 0, 2.35, 5.4, seatm)
    add_box(col, "flush", 0.9, 0.5, 0.25, -1.6, 1.3, 5.5, silver)
    add_box(col, "tankwin", 1.1, 0.15, 0.9, 0, 1.34, 3.2, m["window"])
    # door + porthole in the bowl
    add_box(col, "door", 1.15, 0.3, 1.9, 0, -3.35, 0, m["door"])
    add_box(col, "porthole", 0.8, 0.3, 0.8, -1.9, -2.55, 1.2, m["window"])
    # bath mat doormat + plunger planter
    add_ngon_cone(col, "mat", 1.5, 1.5, 0.07, 12, 0, -4.3, 0, matp)
    add_ngon_cone(col, "plunger", 0.5, 0.35, 0.5, 10, 3.3, -1.8, 0, mat("NB_wc_rub", (0.72, 0.28, 0.24), 0.8))
    add_ngon_cone(col, "stick", 0.08, 0.06, 1.6, 6, 3.3, -1.8, 0.5, m["trunk"])
    build_tree(col, rng, 0.55, -3.4, 1.6)

def build_beach_house(col, seed):
    """Stilted beach cottage with palm, surfboard and a puddle of ocean."""
    rng = random.Random(seed)
    m = std_mats()
    sand = mat("NB_bch_sand", (0.90, 0.83, 0.62), 1.0)
    turq = mat("NB_bch_wall", (0.55, 0.82, 0.80), 0.85)
    white = mat("NB_bch_trim", (0.97, 0.96, 0.93), 0.7)
    thatch = mat("NB_bch_roof", (0.80, 0.68, 0.42), 1.0)
    board = mat("NB_bch_board", (0.95, 0.55, 0.35), 0.5)
    add_box(col, "sandpatch", 8.6, 8.6, 0.18, 0, 0, 0, sand)
    add_ngon_cone(col, "ocean", 2.2, 2.2, 0.12, 14, -3.1, -3.0, 0.14, m["water"])
    # stilts + cottage
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_box(col, "stilt", 0.5, 0.5, 1.4, sx * 2.2, sy * 1.8, 0.15, m["trunk"])
    add_box(col, "cabin", 5.6, 4.6, 2.9, 0, 0.2, 1.5, turq)
    add_prism_roof(col, "roof", 6.3, 5.4, 1.7, 0, 0.2, 4.4, thatch)
    add_box(col, "door", 1.05, 0.25, 1.8, -0.9, -2.15, 1.5, m["door"])
    add_box(col, "win", 1.2, 0.2, 1.0, 1.2, -2.15, 2.3, m["window"])
    add_box(col, "winside", 0.2, 1.2, 1.0, 2.85, 0.6, 2.3, m["window"])
    # deck + steps
    add_box(col, "deck", 5.6, 1.6, 0.25, 0, -2.9, 1.25, white)
    for i in range(3):
        add_box(col, "step", 1.4, 0.55, 0.22, -0.9, -3.9 - i * 0.5, 0.85 - i * 0.35, white)
    for sx in (-2.6, -0.9, 0.9, 2.6):
        add_box(col, "rail", 0.18, 0.18, 0.9, sx, -3.6, 1.5, white)
    add_box(col, "railtop", 5.6, 0.18, 0.16, 0, -3.6, 2.35, white)
    # tilted palm with fronds
    palm = add_ngon_cone(col, "palm", 0.4, 0.25, 4.6, 7, 3.4, 2.6, 0.1, m["trunk"])
    palm.rotation_euler = (math.radians(-10), math.radians(12), 0)
    for i in range(6):
        a = i / 6 * math.tau
        fr = add_ngon_cone(col, "frond", 1.6, 0.12, 0.5, 4,
                           4.05 + 1.1 * math.cos(a), 1.85 + 1.1 * math.sin(a), 4.5,
                           mat("NB_bch_frond", (0.36, 0.62, 0.34), 0.9))
    # surfboard leaning on the cabin
    sb = add_box(col, "surf", 0.85, 0.2, 3.0, 2.6, -1.9, 1.6, board)
    sb.rotation_euler = (math.radians(-14), 0, math.radians(8))
    # beach ball
    add_ngon_cone(col, "ball", 0.5, 0.28, 0.62, 10, -2.6, -1.2, 0.18, board)
    add_ngon_cone(col, "balltop", 0.28, 0.0, 0.3, 10, -2.6, -1.2, 0.8, white)

def build_cottage_house(col, seed):
    """Founder #10: a storybook cottage."""
    rng = random.Random(seed)
    m = std_mats()
    stucco = mat("NB_cot_wall", (0.96, 0.93, 0.84), 0.9)
    timber = mat("NB_cot_beam", (0.38, 0.27, 0.18), 0.9)
    straw = mat("NB_cot_roof", (0.78, 0.64, 0.38), 1.0)
    stone = mat("NB_cot_stone", (0.66, 0.66, 0.68), 0.95)
    puff = mat("NB_cot_puff", (0.96, 0.96, 0.97), 1.0)
    w, d, h = 6.0, 5.0, 3.2
    add_box(col, "base", w, d, h, 0, 0, 0, stucco)
    # timber framing on the facade
    for sx in (-2.6, -0.9, 0.9, 2.6):
        add_box(col, "beam", 0.28, 0.15, h, sx, -d / 2 - 0.02, 0, timber)
    add_box(col, "beamtop", w + 0.2, 0.15, 0.28, 0, -d / 2 - 0.02, h - 0.28, timber)
    # steep thatched roof + dormer
    add_prism_roof(col, "roof", w + 1.0, d + 1.0, 2.9, 0, 0, h, straw)
    add_prism_roof(col, "ridge", w + 1.2, 1.0, 0.5, 0, 0, h + 2.85, straw)
    add_box(col, "dormer", 1.5, 1.2, 1.3, -1.3, -d / 2 + 0.4, h + 0.5, stucco)
    add_prism_roof(col, "dormroof", 1.8, 1.5, 0.8, -1.3, -d / 2 + 0.4, h + 1.8, straw)
    add_box(col, "dormwin", 0.9, 0.2, 0.8, -1.3, -d / 2 - 0.25, h + 0.8, m["window"])
    # round-top door + windows with flower boxes
    add_box(col, "door", 1.15, 0.3, 1.9, 1.3, -d / 2 - 0.08, 0, m["door"])
    add_ngon_cone(col, "doortop", 0.58, 0.55, 0.3, 10, 1.3, -d / 2 - 0.08, 1.9, m["door"])
    for sx in (-1.6, 0.0):
        add_box(col, "win", 1.0, 0.2, 0.95, sx, -d / 2 - 0.06, 1.4, m["window"])
        add_box(col, "fbox", 1.1, 0.35, 0.3, sx, -d / 2 - 0.28, 1.05, timber)
        for i in range(3):
            add_ngon_cone(col, "fdot", 0.12, 0.08, 0.22, 6,
                          sx - 0.35 + i * 0.35, -d / 2 - 0.32, 1.32, mat("NB_flower_dot", (0.95, 0.70, 0.78), 0.8))
    # stone chimney with smoke puffs
    add_box(col, "chimney", 0.95, 0.95, 2.2, 2.0, 1.2, h + 1.2, stone)
    for i, (px, pz, s) in enumerate(((0.1, 0.5, 0.4), (0.45, 1.2, 0.55), (0.9, 2.0, 0.7))):
        add_ngon_cone(col, "puff", s, s * 0.75, s, 8, 2.0 + px, 1.2 + px * 0.4, h + 3.4 + pz, puff)
    # stone path + picket fence
    for i in range(3):
        add_ngon_cone(col, "step", 0.42, 0.42, 0.07, 8, 1.3, -3.2 - i * 0.85, 0, stone)
    for sx in (-2.9, -2.1, -1.3, 2.9):
        add_box(col, "picket", 0.18, 0.18, 0.9, sx, -3.6, 0, stucco)
    add_box(col, "pickrail", 2.0, 0.12, 0.15, -2.1, -3.6, 0.55, stucco)
    build_tree(col, rng, 0.7, -3.3, 1.6)

def build_plaza(col, seed):
    """Milestone: fountain plaza (pop 500)."""
    rng = random.Random(seed)
    m = std_mats()
    stone = mat("NB_stone", (0.80, 0.78, 0.74), 0.9)
    size = LOT * 2 - 1.5
    add_box(col, "base", size, size, 0.4, 0, 0, 0, stone)
    add_ngon_cone(col, "f_rim", 3.4, 3.4, 1.0, 14, 0, 0, 0.4, stone)
    add_ngon_cone(col, "f_water", 3.0, 3.0, 0.9, 14, 0, 0, 0.45, m["water"])
    add_ngon_cone(col, "f_col", 0.7, 0.5, 2.4, 8, 0, 0, 0.4, stone)
    add_ngon_cone(col, "f_top", 1.4, 1.4, 0.35, 10, 0, 0, 2.8, m["water"])
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        t_rng = random.Random(seed * 7 + dx * 3 + dy)
        build_tree(col, t_rng, 0.8, dx * (size / 2 - 2), dy * (size / 2 - 2))
        add_box(col, "bench", 2.0, 0.6, 0.5, dx * 4.5, dy * 1.5, 0.4, m["trunk"])

def build_skyscraper(col, seed):
    """Milestone: glass tower (pop 2,000)."""
    rng = random.Random(seed)
    m = std_mats()
    glass = mat("NB_glass", (0.55, 0.70, 0.82), 0.15)
    frame = mat("NB_frame", (0.90, 0.91, 0.93), 0.6)
    w, d = 12.0, 12.0
    h = 42.0 + rng.random() * 8
    add_box(col, "core", w, d, h, 0, 0, 0, glass)
    for i in (-1, 0, 1):  # vertical mullions
        add_box(col, "mullion", 0.8, d + 0.3, h, i * 4.5, 0, 0, frame)
        add_box(col, "mullion2", w + 0.3, 0.8, h, 0, i * 4.5, 0, frame)
    add_box(col, "cap", w + 0.8, d + 0.8, 1.2, 0, 0, h, m["cap"])
    add_ngon_cone(col, "antenna", 0.25, 0.02, 6.0, 6, 0, 0, h + 1.2, m["metal"])
    add_box(col, "lobby", w + 2.5, d + 2.5, 2.6, 0, 0, 0, frame)

def build_stadium(col, seed):
    """Milestone: stadium, fills a whole block (pop 10,000)."""
    m = std_mats()
    shell = mat("NB_stad", (0.93, 0.93, 0.96), 0.7)
    accent = mat("NB_stad_acc", ROOFS[seed % len(ROOFS)], 0.7)
    pitch = mat("NB_pitch", (0.30, 0.62, 0.28), 1.0)
    R = LOT * 1.42
    add_ngon_cone(col, "bowl", R, R * 0.90, 7.0, 18, 0, 0, 0, shell)
    add_ngon_cone(col, "rim", R * 0.93, R * 0.90, 1.1, 18, 0, 0, 6.9, accent)
    add_ngon_cone(col, "field", R * 0.74, R * 0.74, 0.4, 18, 0, 0, 6.7, pitch)
    add_box(col, "lines", R * 0.9, 0.5, 0.05, 0, 0, 7.1, shell)
    for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        x, y = dx * R * 0.95, dy * R * 0.95
        add_ngon_cone(col, "pole", 0.35, 0.22, 12.0, 6, x, y, 0, m["metal"])
        add_box(col, "flood", 2.2, 0.5, 1.4, x, y, 11.5, m["bulb"])

def build_streetlight(col, _seed=0):
    m = std_mats()
    add_ngon_cone(col, "pole", 0.14, 0.10, 4.6, 6, 0, 0, 0, m["metal"])
    add_box(col, "arm", 1.3, 0.14, 0.14, 0.65, 0, 4.5, m["metal"])
    add_box(col, "lamp", 0.5, 0.4, 0.22, 1.2, 0, 4.35, m["bulb"])

def build_car(col, seed):
    rng = random.Random(seed)
    body = mat("NB_car%d" % seed, ROOFS[rng.randrange(len(ROOFS))], 0.4)
    m = std_mats()
    tire = mat("NB_car_tire", (0.055, 0.065, 0.075), 0.38)
    hub = mat("NB_car_hub", (0.58, 0.62, 0.66), 0.62)
    add_box(col, "body", 3.6, 1.7, 0.85, 0, 0, 0.35, body)
    add_box(col, "cab", 1.9, 1.5, 0.7, -0.2, 0, 1.2, m["windark"])
    for dx in (-1.18, 1.18):
        for side in (-1, 1):
            # add_ngon_cone grows along local +Z.  Start each tire at its OUTER
            # face and rotate it toward the center of the car.  The two sides
            # therefore need opposite X rotations; using one rotation for both
            # sides was what buried a pair of tires inside the body.
            outer_y = side * 1.04
            inward_rot = side * math.pi / 2
            wheel = add_ngon_cone(col, "wheel", .40, .40, .34, 12,
                                  dx, outer_y, .40, tire)
            wheel.rotation_euler.x = inward_rot
            # Thin hubcaps sit on the exposed outer faces, not through the tire.
            cap = add_ngon_cone(col, "wheel_hub", .19, .19, .055, 12,
                                dx, side * 1.055, .40, hub)
            cap.rotation_euler.x = inward_rot


def add_ring(col, name, r_in, r_out, segs, x, y, z, material):
    """Flat annulus (ring road / circular path), top face only, at height z."""
    verts, faces = [], []
    for i in range(segs):
        a = i / segs * math.tau
        verts.append((r_in * math.cos(a), r_in * math.sin(a), 0))
        verts.append((r_out * math.cos(a), r_out * math.sin(a), 0))
    for i in range(segs):
        j = (i + 1) % segs
        faces.append((2 * i, 2 * i + 1, 2 * j + 1, 2 * j))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = (x, y, z)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj

def build_elementary_school(col, seed):
    """Detailed full-block Followville Elementary campus, front facing -Y."""
    rng = random.Random(seed)
    m = std_mats()
    brick = mat("NB_school_brick", (0.68, 0.31, 0.22), .92)
    brick2 = mat("NB_school_brick_accent", (0.78, 0.43, 0.27), .9)
    cream = mat("NB_school_cream", (0.94, 0.88, 0.72), .82)
    navy = mat("NB_school_roof", (0.20, 0.31, 0.42), .78)
    blue = mat("NB_school_blue", (0.26, 0.52, 0.72), .55)
    yellow = mat("NB_school_bus_yellow", (0.95, 0.67, 0.10), .7)
    rubber = mat("NB_school_playground", (0.31, 0.55, 0.63), .95)
    red = mat("NB_school_play_red", (0.83, 0.25, 0.23), .78)
    white = mat("NB_school_white", (0.96, 0.95, 0.90), .75)
    dark = mat("NB_school_dark", (0.12, 0.15, 0.18), .55)

    # Campus ground, front drop-off loop, sidewalks and crosswalk.
    add_box(col, "school_lawn", 28.4, 28.4, .22, 0, 0, 0, m["lawn"])
    add_box(col, "school_bus_loop", 25.5, 4.0, .16, 0, -11.3, .22, m["road"])
    add_box(col, "school_front_walk", 17.0, 3.2, .18, 0, -7.7, .23, cream)
    add_box(col, "school_entry_walk", 4.0, 3.5, .19, 0, -8.4, .24, cream)
    for x in (-1.5, -.75, 0, .75, 1.5):
        add_box(col, "school_crosswalk", .42, 2.9, .025, x, -11.3, .39, white)

    # Symmetrical classroom wings and a taller civic-looking center hall.
    for x in (-7.2, 7.2):
        add_box(col, "school_classroom_wing", 8.8, 12.5, 5.7, x, 1.1, .25, brick)
        add_prism_roof(col, "school_wing_roof", 9.6, 13.3, 2.2, x, 1.1, 5.95, navy)
        add_box(col, "school_wing_belt", 9.0, 12.7, .28, x, 1.1, 3.0, cream)
    add_box(col, "school_center_hall", 6.8, 13.8, 7.3, 0, .45, .25, brick2)
    add_prism_roof(col, "school_center_roof", 7.6, 14.6, 2.7, 0, .45, 7.55, navy)
    add_box(col, "school_center_cornice", 7.15, 14.1, .35, 0, .45, 6.85, cream)

    # Repeated classroom windows with deep frames, mullions and sills.
    for x in (-10.0, -7.2, -4.4, 4.4, 7.2, 10.0):
        add_box(col, "school_window_frame", 2.05, .28, 1.85, x, -5.22, 1.45, cream)
        add_box(col, "school_window", 1.68, .18, 1.48, x, -5.39, 1.63, m["window"])
        add_box(col, "school_window_mullion", .10, .12, 1.48, x, -5.51, 1.63, navy)
        add_box(col, "school_window_sill", 2.15, .42, .18, x, -5.34, 1.35, cream)
    for side in (-1, 1):
        sx = side * 11.64
        for y in (-1.8, 1.0, 3.8, 6.1):
            add_box(col, "school_side_frame", .28, 2.0, 1.8, sx, y, 1.5, cream)
            add_box(col, "school_side_window", .18, 1.62, 1.44,
                    sx + side * .16, y, 1.68, m["window"])

    # Glass entrance pavilion, double doors, canopy, columns and broad steps.
    add_box(col, "school_entry", 5.5, 2.5, 4.35, 0, -7.55, .28, cream)
    add_box(col, "school_entry_glass", 4.75, .18, 3.15, 0, -8.88, 1.05, m["windark"])
    add_box(col, "school_door_left", 1.45, .16, 2.65, -.82, -9.0, .42, blue)
    add_box(col, "school_door_right", 1.45, .16, 2.65, .82, -9.0, .42, blue)
    add_box(col, "school_door_split", .13, .18, 2.75, 0, -9.10, .38, cream)
    for x in (-1.58, 1.58):
        add_ngon_cone(col, "school_canopy_column", .16, .16, 3.25, 10,
                      x, -9.25, .32, cream)
    add_box(col, "school_canopy", 6.4, 2.7, .32, 0, -8.9, 3.55, navy)
    for y, width in ((-9.55, 6.2), (-9.9, 6.8), (-10.2, 7.4)):
        add_box(col, "school_step", width, .48, .16, 0, y, .28, cream)

    # Round clock/emblem above the entrance, with visible hands.
    clock = add_ngon_cone(col, "school_clock", 1.0, 1.0, .18, 24,
                          0, -6.58, 5.35, cream)
    clock.rotation_euler.x = math.pi / 2
    add_box(col, "school_clock_hand_v", .10, .12, .65, 0, -6.79, 5.55, navy)
    hand = add_box(col, "school_clock_hand_h", .55, .12, .10, .18, -6.80, 5.67, navy)
    hand.rotation_euler.z = math.radians(18)

    # Monument sign, flag court, benches, planters and composed landscaping.
    add_box(col, "school_sign_base", 5.2, 1.15, .45, -7.4, -8.15, .30, cream)
    add_box(col, "school_sign_face", 4.55, .65, 1.55, -7.4, -8.15, .72, brick2)
    for i, color in enumerate((blue, yellow, red, cream)):
        add_box(col, "school_sign_mark", .55, .14, .55,
                -8.45 + i * .7, -8.55, 1.2 + (i % 2) * .18, color)
    add_ngon_cone(col, "school_flagpole", .10, .07, 10.5, 10,
                  8.7, -8.3, .30, m["metal"])
    flag_mesh = bpy.data.meshes.new("school_flag_mesh")
    flag_mesh.from_pydata([(8.78, -8.30, 9.0), (12.0, -8.30, 8.35),
                           (8.78, -8.30, 7.75)], [], [(0, 1, 2)])
    flag_mesh.materials.append(blue); flag_mesh.update()
    flag_obj = bpy.data.objects.new("school_flag", flag_mesh); col.objects.link(flag_obj)
    for x in (-10.2, -5.0, 5.0, 10.2):
        add_box(col, "school_bench", 2.0, .55, .48, x, -7.1, .38, m["trunk"])
        for sx in (-.82, .82):
            add_box(col, "school_bench_leg", .16, .42, .55, x + sx, -7.1, .28, dark)
    for x in (-12.0, -9.2, 9.2, 12.0):
        build_tree(col, rng, .72 + rng.random() * .18, x, -3.8)
    for x in (-10.5, -8.7, -6.9, 6.9, 8.7, 10.5):
        add_ngon_cone(col, "school_shrub", .62, .30, .85, 10, x, -5.8, .25, m["lawn"])

    # Rear playground: a broad, fully fenced safety surface with a coherent
    # play structure, a slide that actually joins its deck, swings, climbing
    # bars and painted ground games.  Keep everything beyond the classroom
    # footprint (which ends at y=7.75) so no equipment clips through the school.
    add_box(col, "school_play_border", 25.2, 6.0, .13, 0, 10.75, .23, cream)
    add_box(col, "school_play_mat", 24.4, 5.35, .16, 0, 10.75, .36, rubber)

    # Two connected roofed towers make the equipment read as a real playset.
    for tx in (-7.3, -3.7):
        for px in (tx - 1.0, tx + 1.0):
            for py in (9.6, 11.5):
                add_box(col, "school_play_post", .24, .24, 3.25,
                        px, py, .52, red)
        add_box(col, "school_play_deck", 2.45, 2.35, .28,
                tx, 10.55, 2.45, cream)
        add_ngon_cone(col, "school_play_roof", 2.15, 0, 1.55, 4,
                      tx, 10.55, 3.72, blue, rot=math.pi / 4)
    add_box(col, "school_play_bridge", 2.0, 1.05, .22,
            -5.5, 10.55, 2.48, yellow)
    for by in (10.06, 11.04):
        add_box(col, "school_bridge_rail", 2.0, .10, .75,
                -5.5, by, 2.68, cream)

    # Purpose-built inclined slide mesh: top meets the left tower deck and the
    # run-out finishes just above the safety surface.  Its side rails use exact
    # endpoint beams so they follow the chute instead of rotating around a box
    # corner and floating away from it.
    slide_mesh = bpy.data.meshes.new("school_slide_mesh")
    slide_mesh.from_pydata([
        (-8.05, 11.55, 2.58), (-6.55, 11.55, 2.58),
        (-8.05, 13.22, .68), (-6.55, 13.22, .68),
        (-8.05, 11.55, 2.40), (-6.55, 11.55, 2.40),
        (-8.05, 13.22, .52), (-6.55, 13.22, .52),
    ], [], [(0, 2, 3, 1), (4, 5, 7, 6), (0, 4, 6, 2),
            (1, 3, 7, 5), (0, 1, 5, 4), (2, 6, 7, 3)])
    slide_mesh.materials.append(yellow); slide_mesh.update()
    col.objects.link(bpy.data.objects.new("school_slide", slide_mesh))
    for sx in (-8.12, -6.48):
        add_beam_between(col, "school_slide_rail",
                         (sx, 11.55, 2.88), (sx, 13.22, .98), .12, cream)
    # Short flat exit lip makes the bottom visibly meet the play surface.
    add_box(col, "school_slide_exit", 1.50, .48, .14,
            -7.30, 13.40, .54, yellow)

    # Connected A-frame swing set.  Each leg terminates at the top beam; none
    # of the supports are detached vertical posts beside it.
    beam_z = 4.02
    for x in (1.2, 8.8):
        add_beam_between(col, "school_swing_leg",
                         (x, 9.05, .52), (x, 10.72, beam_z), .25, navy)
        add_beam_between(col, "school_swing_leg",
                         (x, 12.39, .52), (x, 10.72, beam_z), .25, navy)
        add_box(col, "school_swing_foot", .55, .55, .12,
                x, 9.05, .48, cream)
        add_box(col, "school_swing_foot", .55, .55, .12,
                x, 12.39, .48, cream)
    add_box(col, "school_swing_beam", 8.05, .30, .30,
            5.0, 10.72, beam_z - .05, navy)
    for x in (3.25, 6.75):
        for yy in (10.43, 11.01):
            add_beam_between(col, "school_swing_chain",
                             (x, yy, 1.82), (x, yy, beam_z), .065, m["metal"])
        add_box(col, "school_swing_seat", 1.05, .68, .16,
                x, 10.72, 1.68, red)

    # Climbing dome, stepping pods and hopscotch fill the yard without clutter.
    for i in range(8):
        a = i / 8 * math.tau
        add_box(col, "school_climber_bar", .12, .12, 1.65,
                11.0 + math.cos(a) * 1.25, 10.55 + math.sin(a) * 1.25,
                .52, yellow if i % 2 else red)
    add_ngon_cone(col, "school_climber_top", .42, .30, .45, 10,
                  11.0, 10.55, 2.10, blue)
    for i, (px, py) in enumerate(((-1.2, 9.1), (-.2, 9.7), (.8, 9.1))):
        add_ngon_cone(col, "school_step_pod", .34, .30, .26 + i * .12,
                      10, px, py, .52, (yellow, red, cream)[i])
    for i in range(5):
        add_box(col, "school_hopscotch", .62, .62, .025,
                -1.8 + (i % 2) * .68, 11.1 + i * .52, .54,
                (cream, yellow, red)[i % 3])

    # Continuous rear and side fencing, with a clear gate at the left corner.
    for x in range(-13, 14, 2):
        add_box(col, "school_fence_post", .11, .11, 1.45,
                x, 13.78, .38, m["metal"])
    for y in (8.0, 10.0, 12.0):
        for x in (-12.85, 12.85):
            add_box(col, "school_fence_post", .11, .11, 1.45,
                    x, y, .38, m["metal"])
    for z in (.88, 1.55):
        add_box(col, "school_fence_rail", 25.8, .09, .10,
                0, 13.78, z, m["metal"])
        add_box(col, "school_fence_side", .09, 5.85, .10,
                -12.85, 10.85, z, m["metal"])
        add_box(col, "school_fence_side", .09, 5.85, .10,
                12.85, 10.85, z, m["metal"])

    # Finished low-poly school bus at the curb: windows, wheels and stop arm.
    add_box(col, "school_bus_body", 6.8, 2.2, 2.0, 6.8, -11.2, .52, yellow)
    add_box(col, "school_bus_roof", 6.3, 2.25, .35, 6.55, -11.2, 2.50, cream)
    add_box(col, "school_bus_windshield", 1.15, 2.05, .85, 9.72, -11.2, 1.42, m["windark"])
    for x in (4.2, 5.35, 6.5, 7.65, 8.8):
        for y in (-12.33, -10.07):
            add_box(col, "school_bus_window", .82, .10, .70, x, y, 1.65, m["windark"])
    for x in (4.6, 8.9):
        for y in (-12.25, -10.15):
            add_box(col, "school_bus_wheel", .75, .32, .75, x, y, .34, dark)
    add_box(col, "school_bus_stop_arm", .12, .95, .95, 7.7, -12.65, 1.25, red)


def build_ring_house(col, seed):
    """Park-ring homes (day 8+): same cute pastel style, more variety --
    cottages, two-story family homes and skinny townhouses."""
    rng = random.Random(seed)
    m = std_mats()
    wall = mat("NB_rwall%d" % seed, RING_WALLS[rng.randrange(len(RING_WALLS))])
    trim = mat("NB_rtrim", (0.97, 0.96, 0.93), 0.7)
    roof = mat("NB_rroof%d" % seed, ROOFS[rng.randrange(len(ROOFS))])
    style = rng.random()
    if style < 0.38:      # cozy cottage
        w = 5.2 + rng.random() * 1.6
        d = 4.8 + rng.random() * 1.2
        h = 3.2 + rng.random() * 0.8
        add_box(col, "base", w, d, h, 0, 0, 0, wall)
        add_prism_roof(col, "roof", w + 0.8, d + 0.8, 2.0 + rng.random() * 0.8, 0, 0, h, roof)
        add_box(col, "door", 1.1, 0.25, 1.9, (rng.random() - 0.5) * w * 0.3, -d / 2 - 0.1, 0, m["door"])
        for sx in (-1, 1):
            add_box(col, "win", 1.0, 0.2, 0.9, sx * w * 0.28, -d / 2 - 0.08, 1.5, m["window"])
        if rng.random() < 0.7:  # little porch awning over the door
            add_box(col, "awn", 1.7, 0.9, 0.16, (rng.random() - 0.5) * w * 0.3, -d / 2 - 0.55, 2.15, trim)
    elif style < 0.72:    # two-story family home
        w = 5.6 + rng.random() * 1.4
        d = 5.2 + rng.random() * 1.0
        h = 5.6 + rng.random() * 1.0
        add_box(col, "base", w, d, h, 0, 0, 0, wall)
        add_box(col, "belt", w + 0.15, d + 0.15, 0.22, 0, 0, h * 0.5, trim)
        add_prism_roof(col, "roof", w + 0.8, d + 0.8, 1.8 + rng.random() * 0.7, 0, 0, h, roof)
        add_box(col, "door", 1.15, 0.25, 2.0, (rng.random() - 0.5) * w * 0.3, -d / 2 - 0.1, 0, m["door"])
        for z in (1.5, h * 0.5 + 1.3):
            for sx in (-1, 1):
                add_box(col, "win", 1.0, 0.2, 0.95, sx * w * 0.28, -d / 2 - 0.08, z, m["window"])
        if rng.random() < 0.6:
            add_box(col, "chim", 0.7, 0.7, 1.5, w * 0.28, d * 0.2, h + 0.6, m["cap"])
        if rng.random() < 0.5:  # balcony over the door
            add_box(col, "balc", 1.9, 0.8, 0.15, 0, -d / 2 - 0.4, h * 0.5 + 0.3, trim)
            for bx in (-0.85, 0.85):
                add_box(col, "bpost", 0.12, 0.12, 0.8, bx, -d / 2 - 0.72, h * 0.5 + 0.45, trim)
            add_box(col, "brail", 1.9, 0.12, 0.12, 0, -d / 2 - 0.72, h * 0.5 + 1.25, trim)
    else:                 # skinny townhouse
        w = 3.6 + rng.random() * 0.8
        d = 6.0 + rng.random() * 1.0
        h = 6.4 + rng.random() * 1.4
        add_box(col, "base", w, d, h, 0, 0, 0, wall)
        add_box(col, "parapet", w + 0.3, d + 0.3, 0.5, 0, 0, h, roof)
        add_box(col, "stoopA", 1.3, 0.8, 0.55, 0, -d / 2 - 0.4, 0, trim)
        add_box(col, "stoopB", 1.3, 0.5, 0.28, 0, -d / 2 - 0.8, 0, trim)
        add_box(col, "door", 1.05, 0.25, 2.0, 0, -d / 2 - 0.1, 0.55, m["door"])
        zf = 3.3
        while zf < h - 0.9:
            for sx in (-1, 1):
                add_box(col, "win", 0.9, 0.2, 0.95, sx * w * 0.22, -d / 2 - 0.08, zf, m["window"])
            zf += 2.3
        add_box(col, "cornice", w + 0.4, 0.5, 0.25, 0, -d / 2 - 0.15, h - 0.3, trim)
    if rng.random() < 0.55:  # yard tree
        build_tree(col, rng, 0.55 + rng.random() * 0.4,
                   (1 if rng.random() < 0.5 else -1) * (w / 2 + 1.4),
                   (rng.random() - 0.5) * 2.5)
    if rng.random() < 0.45:  # flowers along the front
        fl = mat("NB_flower_dot", (0.95, 0.70, 0.78), 0.8)
        for i in range(3):
            add_ngon_cone(col, "fdot", 0.13, 0.09, 0.24, 6,
                          -1.0 + i * 1.0, -d / 2 - 0.9, 0, fl)

def build_park_district(col, seed):
    """Day-8 circular park district GROUND: central park (gazebo, paths,
    trees, flowers, benches) + two ring roads with dashes + verge lamps.
    The ring houses themselves are separate 'ringhouse' buildings that
    main() lays out on the rings; this asset is everything under them."""
    rng = random.Random(seed)
    m = std_mats()
    stone = mat("NB_stone", (0.80, 0.78, 0.74), 0.9)
    groof = mat("NB_gazebo_roof", (0.75, 0.34, 0.31), 0.8)
    # grass pad under the whole district
    add_ngon_cone(col, "pad", 58.0, 58.0, 0.12, 48, 0, 0, 0, m["grass"])
    # central park
    add_ngon_cone(col, "lawn", 15.0, 15.0, 0.3, 36, 0, 0, 0.02, m["lawn"])
    add_ring(col, "walkloop", 8.2, 10.0, 36, 0, 0, 0.34, stone)
    # gazebo at the heart
    add_ngon_cone(col, "gdeck", 3.4, 3.4, 0.5, 6, 0, 0, 0.3, stone)
    for i in range(6):
        a = i / 6 * math.tau + math.tau / 12
        add_box(col, "gpost", 0.28, 0.28, 2.6, 3.0 * math.cos(a), 3.0 * math.sin(a), 0.8, m["trunk"])
    add_ngon_cone(col, "groof", 4.2, 0.4, 1.9, 6, 0, 0, 3.4, groof)
    add_ngon_cone(col, "gtip", 0.42, 0.0, 0.5, 6, 0, 0, 5.3, groof)
    for k in range(4):  # radial paths gazebo -> walking loop
        a = k / 4 * math.tau + math.tau / 8
        p = add_box(col, "ppath", 4.9, 1.4, 0.06, 5.9 * math.cos(a), 5.9 * math.sin(a), 0.31, stone)
        p.rotation_euler = (0, 0, a)
    for i in range(7):  # park trees
        a = rng.random() * math.tau
        r = 11.2 + rng.random() * 2.6
        build_tree(col, rng, 0.7 + rng.random() * 0.5, math.cos(a) * r, math.sin(a) * r)
    fls = [mat("NB_fl_a", (0.95, 0.62, 0.72), 0.8), mat("NB_fl_b", (0.98, 0.85, 0.45), 0.8),
           mat("NB_fl_c", (0.72, 0.62, 0.92), 0.8)]
    for i in range(16):  # flower beds inside the walking loop
        a = rng.random() * math.tau
        r = 4.5 + rng.random() * 3.2
        add_ngon_cone(col, "flower", 0.16, 0.10, 0.3, 6, math.cos(a) * r, math.sin(a) * r, 0.3, fls[i % 3])
    for k in range(4):  # benches on the loop, facing the gazebo
        a = k / 4 * math.tau
        b = add_box(col, "bench", 2.0, 0.6, 0.55, 9.1 * math.cos(a), 9.1 * math.sin(a), 0.34, m["trunk"])
        b.rotation_euler = (0, 0, a + math.pi / 2)
    # two ring roads with lane dashes
    for r0, r1 in ((17.5, 23.5), (37.5, 43.5)):
        rc = (r0 + r1) / 2
        add_ring(col, "ringroad", r0, r1, 64, 0, 0, 0.16, m["road"])
        nd = int(math.tau * rc / 8)
        for i in range(nd):
            a = i / nd * math.tau
            dsh = add_box(col, "rdash", 2.4, 0.45, 0.02, rc * math.cos(a), rc * math.sin(a), 0.18, m["dash"])
            dsh.rotation_euler = (0, 0, a + math.pi / 2)
    for i in range(10):  # verge street lamps
        a = i / 10 * math.tau + 0.15
        for rr in (25.4, 35.6):
            px, py = rr * math.cos(a), rr * math.sin(a)
            add_ngon_cone(col, "lpole", 0.13, 0.09, 4.2, 6, px, py, 0.1, m["metal"])
            add_box(col, "llamp", 0.45, 0.35, 0.2, px, py, 4.3, m["bulb"])

SUBURBAN_ASSET_VARIANTS = [
    ("AST_suburban_%02d" % i, lambda c, i=i: build_suburban_house(c, i))
    for i in range(len(SUBURBAN_STYLES) * len(SUBURBAN_PALETTES))
]

STORYBOOK_ASSET_VARIANTS = [
    ("AST_storybook_%02d" % i, lambda c, i=i: build_storybook_house(c, i))
    for i in range(10)
]

ASSET_VARIANTS = {
    "house":       SUBURBAN_ASSET_VARIANTS,
    "storybookhouse": STORYBOOK_ASSET_VARIANTS,
    "apartment":   [("AST_apart_%d" % i, lambda c, i=i: build_apartment(c, 200 + i)) for i in range(3)],
    "shop":        [("AST_shop_%d" % i, lambda c, i=i: build_shop(c, 300 + i)) for i in range(3)],
    "park":        [("AST_park_%d" % i, lambda c, i=i: build_park(c, 400 + i)) for i in range(3)],
    "tree":        [("AST_tree_%d" % i, lambda c, i=i: build_lone_tree(c, 500 + i)) for i in range(4)],
    "streetlight": [("AST_light_0", lambda c: build_streetlight(c))],
    "bush":        [("AST_bush_%d" % i, lambda c, i=i: build_bush(c, 1700 + i)) for i in range(4)],
    "rock":        [("AST_rock_%d" % i, lambda c, i=i: build_rock(c, 1800 + i)) for i in range(3)],
    "car":         [("AST_car_%d" % i, lambda c, i=i: build_car(c, 600 + i)) for i in range(4)],
    "mushroomhouse": [("AST_mush_%d" % i, lambda c, i=i: build_mushroom_house(c, 1000 + i)) for i in range(3)],
    "casinohouse":   [("AST_casino_0", lambda c: build_casino_house(c, 1100))],
    "cathouse":      [("AST_cat_0", lambda c: build_cat_house(c, 1200))],
    "castlehouse":   [("AST_castle_0", lambda c: build_castle_house(c, 1300))],
    "eiffelhouse":   [("AST_eiffel_0", lambda c: build_eiffel_house(c, 1400))],
    "flowerhouse":   [("AST_flower_0", lambda c: build_flower_house(c, 1500))],
    "burjhouse":     [("AST_burj_0", lambda c: build_burj_house(c, 1600))],
    "toilethouse":   [("AST_toilet_0", lambda c: build_toilet_house(c, 1900))],
    "beachhouse":    [("AST_beach_0", lambda c: build_beach_house(c, 2000))],
    "cottagehouse":  [("AST_cottage_0", lambda c: build_cottage_house(c, 2100))],
    "plaza":       [("AST_plaza_0", lambda c: build_plaza(c, 700))],
    "skyscraper":  [("AST_sky_%d" % i, lambda c, i=i: build_skyscraper(c, 800 + i)) for i in range(2)],
    "stadium":     [("AST_stadium_0", lambda c: build_stadium(c, 900))],
    "pond":        [("AST_pond_0", lambda c: build_pond(c, 1950))],
    "elementaryschool": [("AST_elementaryschool_0", lambda c: build_elementary_school(c, 2500))],
    "duck":        [("AST_duck_%d" % i, lambda c, i=i: build_duck(c, 2200 + i)) for i in range(3)],
    # Park-ring residents keep their exact seed/claim/position/rotation, but
    # now draw from the same normal suburban library as every other resident.
    "ringhouse":   SUBURBAN_ASSET_VARIANTS,
    "parkdistrict": [("AST_parkdist_0", lambda c: build_park_district(c, 2400))],
}

URBAN_ASSET_VARIANTS = [
    ("AST_urban_%d" % i, lambda c, i=i: build_urban_townhouse(c, i))
    for i in range(15)
]

# ═══════════════════════════════ GRID / PLACEMENT ═══════════════════════════════

def lot_to_world(gx, gy):
    bx, ix = divmod(gx, BLOCK_N)
    by, iy = divmod(gy, BLOCK_N)
    return (bx * PITCH + ix * LOT + LOT / 2,
            by * PITCH + iy * LOT + LOT / 2)

def build_pos(b):
    """World-space anchor: exact px/py if stored (ring houses / park
    district sit off-grid), else the building's grid lot."""
    if "px" in b:
        return transform_building_point(b)
    return lot_to_world(b["gx"], b["gy"])

def web_chunk_id(b):
    """Stable streaming group for one canonical world-state building.

    The value is stored on the Blender instance root before export.  It never
    becomes a second address/source of truth: district and type still come
    from world_state.json, and the exporter only uses this tag to partition
    the exact same realized geometry that also goes into town.glb.
    """
    if b.get("district"):
        value = str(b["district"]).strip().lower()
        slug = "".join(ch if ch.isalnum() else "-" for ch in value)
        return "-".join(part for part in slug.split("-") if part)
    if b.get("type") in ("ringhouse", "parkdistrict"):
        return "founder-park"
    return "original-town"


def hillside_pad_levels(x, y, rotation=0.0, width=8.4, depth=9.0):
    """Level foundation range for a house on continuous sloping terrain."""
    c, s = math.cos(rotation), math.sin(rotation)
    samples = []
    for lx in (-width / 2, 0.0, width / 2):
        for ly in (-depth / 2, 0.0, depth / 2):
            wx = x + lx * c - ly * s
            wy = y + lx * s + ly * c
            samples.append(terrain_height(wx, wy))
    return min(samples), max(samples) + .08

# building footprint in lots (per side); milestone buildings can span a whole block
SIZE = {"house": 1, "tree": 1, "shop": 1, "streetlight": 1, "car": 1, "bush": 1, "rock": 1,
        "storybookhouse": 1,
        "mushroomhouse": 1, "casinohouse": 1, "cathouse": 1, "castlehouse": 1,
        "eiffelhouse": 1, "flowerhouse": 1, "burjhouse": 1, "toilethouse": 1, "beachhouse": 1,
        "cottagehouse": 1, "pond": 1, "ringhouse": 1, "parkdistrict": 1,
        "apartment": 2, "park": 2, "plaza": 2, "skyscraper": 2, "stadium": 3,
        "elementaryschool": 3}

# unlocked automatically the day population crosses the threshold
MILESTONES = [(500, "plaza"), (2000, "skyscraper"), (10000, "stadium")]

def footprint(b):
    # Planned suburban houses use exact world positions on curving roads, not
    # grid lots.  They therefore reserve no legacy 3x3-grid cell.
    if b.get("plan_id") or b.get("feature_id"):
        return []
    if b["type"] == "parkdistrict":
        # reserve every lot whose center falls inside the district circle
        cells, rr = [], b.get("r", 57) + LOT
        for dgx in range(-10, 11):
            for dgy in range(-10, 11):
                x, y = lot_to_world(b["gx"] + dgx, b["gy"] + dgy)
                if math.hypot(x - b.get("px", x), y - b.get("py", y)) <= rr:
                    cells.append((b["gx"] + dgx, b["gy"] + dgy))
        return cells
    s = SIZE.get(b["type"], 1)
    return [(b["gx"] + dx, b["gy"] + dy) for dx in range(s) for dy in range(s)]

def sorted_lots(radius):
    """Pure per-lot radial-distance order (with jitter) -- scatters new
    buildings across many blocks instead of filling any one solid. This was
    the only ordering before 2026-07-10 and is why blocks kept ending up
    sparse (one house + trees) after several growth days. Kept as an
    explicit opt-out: pass --scatter on the CLI (see fill_mode below) if you
    ever want that old scattered look back. sorted_lots_filling() is the
    default now."""
    rng = random.Random(1234)
    lots = []
    for gx in range(-radius, radius + 1):
        for gy in range(-radius, radius + 1):
            x, y = lot_to_world(gx, gy)
            lots.append((math.hypot(x, y) + rng.random() * 22, gx, gy))
    lots.sort()
    return lots

def sorted_lots_filling(radius):
    """Block-fill order (2026-07-10): blocks in spiral order by distance
    from the city center, and within each block, its 9 lots in a fixed
    reading order -- fills one block solid before starting the next,
    instead of scattering new buildings across many blocks at once (the
    dead-center lot of each block gets skipped downstream in
    find_free_lots, same as before, so it doesn't need special-casing
    here). Promoted from the one-off condense_day9.py script (which still
    exists for reference) to the real pipeline as the DEFAULT ordering for
    all new growth, per Zach's request to keep the town looking dense
    without needing a manual condense pass every few days. Pass --scatter
    on the CLI to fall back to the old sorted_lots() ordering instead."""
    block_radius = max(1, radius // BLOCK_N + 1)
    blocks = []
    for bx in range(-block_radius, block_radius + 1):
        for by in range(-block_radius, block_radius + 1):
            cx, cy = bx * PITCH + PITCH / 2, by * PITCH + PITCH / 2
            blocks.append((math.hypot(cx, cy), bx, by))
    blocks.sort()
    lots = []
    priority = 0
    for _, bx, by in blocks:
        for iy in range(BLOCK_N):
            for ix in range(BLOCK_N):
                lots.append((priority, bx * BLOCK_N + ix, by * BLOCK_N + iy))
                priority += 1
    return lots

def find_free_lots(count, size, occupied, blocked_blocks=None, fill_mode="block"):
    # start near the city's current edge so huge cities don't rescan from zero
    radius = max(3, int(math.sqrt(len(occupied) + count * size * size)))
    lot_order_fn = sorted_lots if fill_mode == "scatter" else sorted_lots_filling
    while radius < 400:  # ~640k lots — enough for hundreds of thousands
        found = []
        taken = set(occupied)
        for _, gx, gy in lot_order_fn(radius):
            if blocked_blocks and (gx // BLOCK_N, gy // BLOCK_N) in blocked_blocks:
                continue
            if len(found) >= count:
                return found
            if size > 1:
                if gx % BLOCK_N > BLOCK_N - size or gy % BLOCK_N > BLOCK_N - size:
                    continue
                cells = [(gx + dx, gy + dy) for dx in range(size) for dy in range(size)]
                if any(c in taken for c in cells):
                    continue
                taken.update(cells)
                found.append((gx, gy))
            else:
                if (gx, gy) in taken:
                    continue
                # 2026-07-10: skip the lot dead-center of its 3x3 block --
                # it's fully boxed in by the other 8 lots with no road
                # frontage on any side, so a house placed there is
                # unreachable from the street (Zach spotted several of these
                # "encapsulated" houses in the day-9 video). Leaving it
                # unbuilt turns it into a little green square instead, via
                # the existing scatter_nature() pass over unoccupied lots.
                center = BLOCK_N // 2
                if gx % BLOCK_N == center and gy % BLOCK_N == center:
                    continue
                taken.add((gx, gy))
                found.append((gx, gy))
        if len(found) >= count:
            return found
        radius += max(3, radius // 4)
    raise RuntimeError("Ran out of space")

def place_instance(world_col, b, name):
    variants = (URBAN_ASSET_VARIANTS
                if b["type"] == "house" and not b.get("plan_id") and "px" not in b
                else ASSET_VARIANTS[b["type"]])
    vname, builder = variants[b["seed"] % len(variants)]
    asset = get_asset(vname, builder)
    empty = bpy.data.objects.new(name, None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = asset
    x, y = build_pos(b)
    s = SIZE.get(b["type"], 1)
    if "px" in b:  # exact world placement (district / suburban houses)
        authored_z = b.get("pz")
        if authored_z is None:
            authored_z = (hillside_pad_levels(x, y, b.get("rot", 0.0))[1]
                          if b.get("plan_id") else
                          (0.1 if b["type"] == "ringhouse" else 0))
        empty.location = (x, y, authored_z)
    else:
        empty.location = (x + (s - 1) * LOT / 2, y + (s - 1) * LOT / 2, 0)
    rng = random.Random(b["seed"])
    if b.get("rot") is not None:  # exact facing (ring houses face their park)
        empty.rotation_euler = (0, 0, b["rot"])
    elif b["type"] == "elementaryschool":
        # The campus asset is authored with its main doors facing local -Y;
        # keep that deliberate frontage instead of applying lot-house rotation.
        empty.rotation_euler = (0, 0, 0)
    elif b.get("face"):  # explicit facing override stored in the state file
        empty.rotation_euler = (0, 0, {"s": 0.0, "e": math.pi / 2,
                                       "n": math.pi, "w": -math.pi / 2}[b["face"]])
    elif b["type"] in ("tree", "bush", "rock"):
        empty.rotation_euler = (0, 0, rng.random() * math.tau)
    elif b["type"] not in ("park", "plaza", "stadium", "streetlight", "car", "pond", "duck", "parkdistrict"):
        # face the front door toward the nearest road edge of the block
        bn = BLOCK_N - s
        ix, iy = b["gx"] % BLOCK_N, b["gy"] % BLOCK_N
        dists = {0.0: iy,                 # door faces south (-y)
                 math.pi: bn - iy,        # north
                 math.pi / 2: bn - ix,    # east
                 -math.pi / 2: ix}        # west
        best = min(dists.values())
        opts = sorted(k for k, v in dists.items() if v == best)
        empty.rotation_euler = (0, 0, opts[rng.randrange(len(opts))])
    if b["type"] == "house" and not b.get("plan_id") and "px" not in b:
        # Pull downtown homes into the building line without changing their
        # grid address or identity. Local -Y is the authored front.
        facing = empty.rotation_euler.z
        empty.location.x += -math.sin(facing) * 1.25
        empty.location.y +=  math.cos(facing) * 1.25
    if b["type"] == "house" and b.get("plan_id"):
        lot_scale = .55 if b["plan_id"] in SUBURBAN_TIGHT_PLAN_IDS else .78
        empty.scale = (lot_scale, lot_scale, max(.75, lot_scale + .20))
    # Animation/export must return to this authored scale, not blindly to 1.
    empty["nb_rest_scale"] = tuple(empty.scale)
    world_col.objects.link(empty)
    return empty

# ═══════════════════════════════ ROADS & DRESSING ═══════════════════════════════

def block_extent(buildings):
    """The town always has at least a 3x3-block starter road grid, so day 0
    shows the exact streets that houses will later appear on. Off-grid park
    districts (and their ring houses) don't extend the grid."""
    buildings = [b for b in buildings if b["type"] not in ("parkdistrict", "ringhouse")
                 and not b.get("plan_id") and not b.get("feature_id")]
    if not buildings:
        return -1, 1, -1, 1
    bxs = [b["gx"] // BLOCK_N for b in buildings]
    bys = [b["gy"] // BLOCK_N for b in buildings]
    return (min(min(bxs), -1), max(max(bxs), 1),
            min(min(bys), -1), max(max(bys), 1))

def build_roads(world_col, buildings, m):
    min_bx, max_bx, min_by, max_by = block_extent(buildings)
    x0, x1 = min_bx * PITCH - ROAD, (max_bx + 1) * PITCH
    y0, y1 = min_by * PITCH - ROAD, (max_by + 1) * PITCH
    for bx in range(min_bx, max_bx + 2):
        x = bx * PITCH - ROAD / 2
        add_box(world_col, "roadV", ROAD, y1 - y0, 0.15, x, (y0 + y1) / 2, 0, m["road"])
    for by in range(min_by, max_by + 2):
        y = by * PITCH - ROAD / 2
        add_box(world_col, "roadH", x1 - x0, ROAD, 0.16, (x0 + x1) / 2, y, 0, m["road"])
    # Parked cars belong along block faces, not scattered through junctions.
    # The dedicated public-realm pass owns all downtown streetlights.
    rng = random.Random(9000 + (max_bx - min_bx) * 31 + (max_by - min_by))
    for bx in range(min_bx, max_bx + 1):
        for by in range(min_by, max_by + 1):
            block_x, block_y = bx * PITCH, by * PITCH
            if rng.random() < 0.78:
                b = {"type": "car", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
                e = place_instance(world_col, b, "car")
                e.location = (block_x + LOT*(.65+rng.random()*1.7),
                              block_y - 1.15, .05)
                e.rotation_euler = (0, 0, 0 if rng.random() < .5 else math.pi)
            if rng.random() < 0.48:
                b = {"type": "car", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
                e = place_instance(world_col, b, "car")
                e.location = (block_x - 1.15,
                              block_y + LOT*(.65+rng.random()*1.7), .05)
                e.rotation_euler = (0, 0, math.pi/2 if rng.random() < .5 else -math.pi/2)

def build_district_roads(world_col, buildings, m):
    """Straight connector from each park district's entrance (the house gap
    on its west side) to the town's easternmost grid road."""
    districts = [b for b in buildings if b["type"] == "parkdistrict"]
    if not districts:
        return
    min_bx, max_bx, min_by, max_by = block_extent(buildings)
    x_road = (max_bx + 1) * PITCH - ROAD / 2
    for d in districts:
        cx, cy = transform_building_point(d)
        x_in = cx - (d.get("r", 57) - 18)   # reaches into the outer ring road
        if x_in <= x_road:
            continue
        L = x_in - x_road
        add_box(world_col, "connector", L, ROAD, 0.18, x_road + L / 2, cy, 0, m["road"])
        x = x_road + 5
        while x < x_in - 3:
            add_box(world_col, "cdash", 2.6, 0.45, 0.05, x, cy, 0.19, m["dash"])
            x += 8
        # short spur from the inner ring road to the park's walking loop
        add_box(world_col, "spur", 12.0, 3.4, 0.18, cx - 16.0, cy, 0, m["road"])
        # 2026-07-10: the connector above only reaches the OUTER ring (ends at
        # x_in), and the spur above only reaches from the INNER ring inward to
        # the walking loop (starts at cx-22) -- nothing bridges the two ring
        # roads themselves. That left a bare ~14-unit strip of grass between
        # them with no way to drive/walk from the outer ring to the inner one,
        # even though each individually connects fine to its own ring. Zach
        # spotted this in the web preview ("a road belongs there to get into
        # the circle"). Fix: one more straight segment closing that exact gap,
        # picking up right where the connector ends and handing off right
        # where the spur begins, so the whole path from the grid to the
        # gazebo is continuous.
        radial_w = (cx - 22.0) - x_in
        if radial_w > 0:
            add_box(world_col, "radial", radial_w, ROAD, 0.18, x_in + radial_w / 2, cy, 0, m["road"])


def _add_ellipse_disc(col, name, x, y, sx, sy, z, material, sides=24):
    verts = [(0, 0, 0)]
    for i in range(sides):
        a = math.tau * i / sides
        verts.append((math.cos(a) * sx, math.sin(a) * sy, 0))
    faces = [(0, i + 1, (i + 1) % sides + 1) for i in range(sides)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces); mesh.materials.append(material); mesh.update()
    obj = bpy.data.objects.new(name, mesh); obj.location = (x, y, z); col.objects.link(obj)
    return obj


def _add_ellipse_pad(col, name, x, y, sx, sy, z, height, material, sides=32):
    """A shallow elliptical solid. Unlike a single face, this cannot flicker
    against the ground/road when the camera moves at a shallow angle."""
    obj = add_ngon_cone(col, name, 1.0, 1.0, height, sides, x, y, z, material)
    obj.scale = (sx, sy, 1.0)
    return obj


def _add_mound(col, name, x, y, sx, sy, height, material, sides=20):
    """Broad low-poly mound with a rounded crown, not a sharp cone."""
    verts = []
    rings = ((1.0, 0.0), (.72, height * .55), (.34, height * .90), (0.0, height))
    for radius, z in rings[:-1]:
        for i in range(sides):
            a = math.tau * i / sides
            wobble = 1.0 + .035 * math.sin(i * 2.17 + x * .01)
            verts.append((math.cos(a) * sx * radius * wobble,
                          math.sin(a) * sy * radius * wobble, z))
    verts.append((0, 0, rings[-1][1]))
    top = len(verts) - 1
    faces = []
    for ring in range(2):
        a0, b0 = ring * sides, (ring + 1) * sides
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((a0 + i, a0 + j, b0 + j, b0 + i))
    for i in range(sides):
        faces.append((2 * sides + i, 2 * sides + (i + 1) % sides, top))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces); mesh.materials.append(material); mesh.update()
    obj = bpy.data.objects.new(name, mesh); obj.location = (x, y, 0.02); col.objects.link(obj)
    return obj


def build_suburban_terrain(world_col, m):
    """Visible landform reserve.  Terrain is allowed to precede development;
    future roads/houses are deliberately handled by build_suburban_roads()."""
    if not SUBURBAN_PLAN:
        return
    hill_mat = mat("NB_suburban_hill", (0.37, 0.57, 0.29), 1.0)
    meadow_mat = mat("NB_suburban_meadow", (0.48, 0.66, 0.31), 1.0)
    for feature in SUBURBAN_PLAN["terrain"]:
        if feature["kind"] == "hill":
            _add_mound(world_col, "terrain_" + feature["name"], feature["x"], feature["y"],
                       feature["sx"], feature["sy"], feature["height"], hill_mat)
        elif feature["kind"] == "pond":
            _add_ellipse_pad(world_col, "terrain_" + feature["name"], feature["x"], feature["y"],
                             feature["sx"], feature["sy"], .015, .065, m["water"])
        elif feature["kind"] == "meadow":
            _add_ellipse_disc(world_col, "terrain_" + feature["name"], feature["x"], feature["y"],
                              feature["sx"], feature["sy"], .025, meadow_mat)


def _add_road_strip(world_col, name, points, material, width=ROAD,
                    bottom_offset=.01, top_offset=.19, widths=None,
                    segment_materials=None, terrain_conform=False,
                    terrain_origin=None):
    """One continuous, shallow road mesh with mitered bends.

    The previous implementation rotated a separate rectangle for every five
    metres of curve. Even with cover discs, the exposed rectangle ends could
    read as cracks. A single ribbon has shared vertices and therefore no gaps.
    """
    if len(points) < 2:
        return None
    # Subdivide long authored segments before building the ribbon.  Sampling
    # terrain only at distant control points let a convex hill rise through the
    # chord between them, which made the road disappear underground midway up
    # a grade.
    dense_points = []
    dense_widths = []
    subdivision_counts = []
    source_widths = list(widths) if widths is not None else [width] * len(points)
    for index, (a, b) in enumerate(zip(points, points[1:])):
        length = math.hypot(b[0]-a[0], b[1]-a[1])
        steps = max(1, int(math.ceil(length / 2.0)))
        subdivision_counts.append(steps)
        for step in range(steps):
            t = step / steps
            x = a[0] + (b[0]-a[0])*t
            y = a[1] + (b[1]-a[1])*t
            authored_z = ((a[2] if len(a) > 2 else 0.0) +
                          ((b[2] if len(b) > 2 else 0.0) -
                           (a[2] if len(a) > 2 else 0.0))*t)
            if terrain_origin is not None:
                sample_z = max(authored_z,
                               terrain_height(x+terrain_origin[0],
                                              y+terrain_origin[1]))
            else:
                sample_z = terrain_height(x, y) if terrain_conform else authored_z
            dense_points.append((x, y, sample_z))
            dense_widths.append(source_widths[index] +
                                (source_widths[index+1]-source_widths[index])*t)
    final_authored = points[-1][2] if len(points[-1]) > 2 else 0.0
    if terrain_origin is not None:
        final_z = max(final_authored,
                      terrain_height(points[-1][0]+terrain_origin[0],
                                     points[-1][1]+terrain_origin[1]))
    else:
        final_z = (terrain_height(points[-1][0], points[-1][1])
                   if terrain_conform else final_authored)
    dense_points.append((points[-1][0], points[-1][1], final_z))
    dense_widths.append(source_widths[-1])
    points = dense_points
    point_widths = dense_widths
    if len(point_widths) != len(points):
        raise ValueError("road-strip widths must match the point count")
    if segment_materials is not None:
        # Authored per-segment materials are expanded across subdivisions.
        source_materials = list(segment_materials)
        if len(source_materials) != len(source_widths) - 1:
            raise ValueError("road-strip materials must match the segment count")
        materials_by_segment = []
        for material_index, count in enumerate(subdivision_counts):
            materials_by_segment.extend([source_materials[material_index]] * count)
    else:
        materials_by_segment = [material] * (len(points) - 1)
    edges = []
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < .001:
            edges.append((1.0, 0.0))
        else:
            edges.append((dx / length, dy / length))
    offsets = []
    for i in range(len(points)):
        half = point_widths[i] / 2
        before = edges[max(0, i - 1)]
        after = edges[min(len(edges) - 1, i)]
        n0, n1 = (-before[1], before[0]), (-after[1], after[0])
        mx, my = n0[0] + n1[0], n0[1] + n1[1]
        ml = math.hypot(mx, my)
        if ml < .001:
            mx, my, scale = n1[0], n1[1], half
        else:
            mx, my = mx / ml, my / ml
            scale = min(half * 1.6, half / max(.35, mx * n1[0] + my * n1[1]))
        offsets.append((mx * scale, my * scale))
    verts = []
    for z_offset in (bottom_offset, top_offset):
        for point, offset in zip(points, offsets):
            # Sample both ribbon edges independently.  Sharing the highest
            # cross-road sample kept the asphalt above ground but produced
            # raised slab steps on steep terrain.  A two-metre longitudinal
            # grid plus per-edge heights follows the hillside continuously.
            left_x, left_y = point[0] + offset[0], point[1] + offset[1]
            right_x, right_y = point[0] - offset[0], point[1] - offset[1]
            if terrain_origin is not None:
                left_z = max(point[2], terrain_height(
                    left_x+terrain_origin[0], left_y+terrain_origin[1]))
                right_z = max(point[2], terrain_height(
                    right_x+terrain_origin[0], right_y+terrain_origin[1]))
            else:
                left_z = terrain_height(left_x, left_y) if terrain_conform else point[2]
                right_z = terrain_height(right_x, right_y) if terrain_conform else point[2]
            verts.extend(((left_x, left_y, left_z + z_offset),
                          (right_x, right_y, right_z + z_offset)))
    n = len(points)
    faces = []
    face_materials = []
    for i in range(n - 1):
        # bottom, top, left wall, right wall
        faces.extend(((2*i, 2*i+1, 2*i+3, 2*i+2),
                      (2*n+2*i, 2*n+2*i+2, 2*n+2*i+3, 2*n+2*i+1),
                      (2*i, 2*i+2, 2*n+2*i+2, 2*n+2*i),
                      (2*i+1, 2*n+2*i+1, 2*n+2*i+3, 2*i+3)))
        face_materials.extend([materials_by_segment[i]] * 4)
    faces.extend(((0, 2*n, 2*n+1, 1),
                  (2*n-2, 2*n-1, 4*n-1, 4*n-2)))
    face_materials.extend((materials_by_segment[0], materials_by_segment[-1]))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    material_slots = []
    for face_material in face_materials:
        if face_material not in material_slots:
            material_slots.append(face_material)
    for slot_material in material_slots:
        mesh.materials.append(slot_material)
    for polygon, face_material in zip(mesh.polygons, face_materials):
        polygon.material_index = material_slots.index(face_material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    world_col.objects.link(obj)
    return obj


def _add_terrain_disc_batch(collection, name, centers, radius, z_offset,
                            material, sides=18):
    """Terrain-following junction covers for seamless road connections."""
    unique = sorted({(round(x, 4), round(y, 4)) for x, y in centers})
    if not unique:
        return None
    vertices, faces = [], []
    for cx, cy in unique:
        start = len(vertices)
        vertices.append((cx, cy, terrain_height(cx, cy)+z_offset))
        for index in range(sides):
            angle = math.tau*index/sides
            x, y = cx+radius*math.cos(angle), cy+radius*math.sin(angle)
            vertices.append((x, y, terrain_height(x, y)+z_offset))
        for index in range(sides):
            faces.append((start, start+1+index, start+1+(index+1)%sides))
    mesh = bpy.data.meshes.new(name+"_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def _polyline_sample(points, distance):
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if distance <= length:
            t = distance / max(length, .001)
            return a[0] + dx * t, a[1] + dy * t, math.atan2(dy, dx)
        distance -= length
    a, b = points[-2], points[-1]
    return b[0], b[1], math.atan2(b[1] - a[1], b[0] - a[0])


def _offset_terrain_path(points, offset):
    """Parallel path sampled from local polyline tangents on the terrain."""
    result = []
    for index, point in enumerate(points):
        before = points[max(0, index-1)]
        after = points[min(len(points)-1, index+1)]
        dx, dy = after[0]-before[0], after[1]-before[1]
        length = max(.001, math.hypot(dx, dy))
        nx, ny = -dy/length, dx/length
        x, y = point[0]+nx*offset, point[1]+ny*offset
        result.append((x, y, terrain_height(x, y)))
    return result


def _polyline_surface_sample(points, distance):
    """Position and horizontal tangent on a 3D road centerline."""
    remaining = max(0.0, distance)
    for a, b in zip(points, points[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        if length < .001:
            continue
        if remaining <= length:
            t = remaining / length
            az = a[2] if len(a) > 2 else 0.0
            bz = b[2] if len(b) > 2 else 0.0
            return (a[0] + dx*t, a[1] + dy*t,
                    az + (bz-az)*t, dx/length, dy/length)
        remaining -= length
    a, b = points[-2], points[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = max(.001, math.hypot(dx, dy))
    return b[0], b[1], (b[2] if len(b) > 2 else 0.0), dx/length, dy/length


def _add_road_surface_dash(col, name, points, center_distance, length,
                           width, road_top_offset, height, material):
    """A shallow marking whose four corners follow the sloped road surface.

    Rotating a box around its center left a visible air gap on the steep Day-15
    access ramp. Sampling both ends from the authored centerline makes the
    marking share the road pitch (and any nearby bend) exactly.
    """
    samples = [_polyline_surface_sample(points, center_distance + offset)
               for offset in (-length/2, length/2)]
    bottom, top = [], []
    for x, y, z, tx, ty in samples:
        nx, ny = -ty, tx
        for side in (-1, 1):
            point = (x + nx*width*.5*side,
                     y + ny*width*.5*side,
                     z + road_top_offset)
            bottom.append(point)
            top.append((point[0], point[1], point[2] + height))
    verts = bottom + top
    faces = [(0, 1, 3, 2), (4, 6, 7, 5),
             (0, 4, 5, 1), (1, 5, 7, 3),
             (3, 7, 6, 2), (2, 6, 4, 0)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    return obj


def build_suburban_roads(world_col, buildings, m):
    """Reveal only the road pieces needed by houses already constructed."""
    if not SUBURBAN_PLAN:
        return
    active = max([b.get("plan_id", 0) for b in buildings] or [0])
    if not active:
        return
    active_districts = {b.get("district") for b in buildings if b.get("plan_id")}
    active_house_points = [build_pos(b) for b in buildings
                           if b.get("type") == "house" and b.get("plan_id")]
    shoulder_mat = mat("FV_suburban_road_shoulder", (.24, .27, .25), .99)
    lane_mat = mat("FV_suburban_lane_marking", (.61, .60, .47), 1.0)
    path_mat = mat("FV_suburban_walking_path", (.52, .49, .42), .99)
    junction_points = []
    for district in sorted(active_districts):
        connector = DISTRICT_CONNECTORS.get(district)
        if not connector:
            continue
        points = [(x, y, terrain_height(x, y)) for x, y in connector]
        junction_points.extend((x, y) for x, y, _z in points)
        _add_road_strip(world_col, "district_connector_shoulder_" + district.lower().replace(" ", "_"),
                        points, shoulder_mat, width=7.35, bottom_offset=.005,
                        top_offset=.045, terrain_conform=True)
        _add_road_strip(world_col, "district_connector_" + district.lower().replace(" ", "_"),
                        points, m["road"], bottom_offset=.015,
                        top_offset=.085, terrain_conform=True)
        for side in (-1, 1):
            path = _offset_terrain_path(points, side*4.45)
            _add_road_strip(world_col, "district_path_" + district.lower().replace(" ", "_") + str(side),
                            path, path_mat, width=1.25, bottom_offset=.005,
                            top_offset=.035, terrain_conform=True)
    by_street = {}
    for segment in SUBURBAN_PLAN["roads"]:
        if segment["reveal_at"] <= active:
            by_street.setdefault(segment["street_index"], []).append(segment)
    for street_index, segments in by_street.items():
        district = segments[0].get("district")
        source_points = [segments[0]["a"]] + [segment["b"] for segment in segments]
        flat_points = [transform_point(point[0], point[1], district=district)
                       for point in source_points]
        points = [(point[0], point[1], terrain_height(point[0], point[1]))
                  for point in flat_points]
        junction_points.extend(flat_points)
        _add_road_strip(world_col, "suburban_shoulder_%02d" % street_index, points,
                        shoulder_mat, width=7.35, bottom_offset=.005,
                        top_offset=.045, terrain_conform=True)
        _add_road_strip(world_col, "suburban_road_%02d" % street_index, points,
                        m["road"], bottom_offset=.015,
                        top_offset=.085, terrain_conform=True)
        path = _offset_terrain_path(points, 4.35 if street_index%2==0 else -4.35)
        _add_road_strip(world_col, "suburban_path_%02d" % street_index, path,
                        path_mat, width=1.18, bottom_offset=.005,
                        top_offset=.035, terrain_conform=True)
        # Match the established grid/ring roads: centered pale lane dashes at
        # the same eight-metre rhythm, following the curve tangent.
        total = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                    for a, b in zip(points, points[1:]))
        distance = 5.0
        while distance < total - 2.0:
            x, y, angle = _polyline_sample(points, distance)
            dash = add_box(world_col, "suburban_dash", 1.65, .16, .018,
                           x, y, terrain_height(x, y)+.095, lane_mat)
            dash.rotation_euler.z = angle
            distance += 10.0
        light_distance = 18.0
        light_index = 0
        while light_distance < total-8.0:
            lx, ly, angle = _polyline_sample(points, light_distance)
            side = 1 if (light_index+street_index)%2==0 else -1
            nx, ny = -math.sin(angle)*side, math.cos(angle)*side
            lx, ly = lx+nx*4.55, ly+ny*4.55
            if any(math.hypot(lx-hx, ly-hy) < 5.4 for hx,hy in active_house_points):
                light_distance += 34.0
                light_index += 1
                continue
            lamp_data = {"type":"streetlight","gx":0,"gy":0,
                         "seed":17000+street_index*97+light_index}
            lamp = place_instance(world_col, lamp_data, "suburban_light")
            lamp.location = (lx, ly, terrain_height(lx, ly))
            lamp.rotation_euler = (0, 0, angle)
            light_distance += 34.0
            light_index += 1
    # Rounded, terrain-following covers turn independent road ribbons into one
    # visually continuous network at bends and junctions. The one-centimetre
    # lift over each ribbon prevents depth fighting without a visible step.
    _add_terrain_disc_batch(world_col, "suburban_junction_shoulders",
                            junction_points, 3.72, .052, shoulder_mat, 20)
    _add_terrain_disc_batch(world_col, "suburban_junction_surfaces",
                            junction_points, 3.12, .095, m["road"], 20)
    for bulb in SUBURBAN_PLAN["turnarounds"]:
        if bulb["reveal_at"] <= active:
            # Road boxes top out at z=.19. Put the solid turnaround just above
            # that surface so overlapping faces never depth-fight.
            bulb_x, bulb_y = transform_point(bulb["center"][0], bulb["center"][1],
                                             district=bulb.get("district"))
            bulb_obj = _add_ellipse_pad(world_col, "culdesac", bulb_x, bulb_y,
                                        8.2, 8.2, .012, .083, m["road"], 32)
            bulb_obj.location.z = terrain_height(bulb_x, bulb_y)


def build_hillside_foundations(world_col, buildings):
    """Give every revealed winding-road home a level, retained house pad.

    Buildings remain architecturally level, as real houses do, while the
    stone foundation absorbs the terrain difference instead of leaving the
    downhill edge floating or letting the uphill slope cut through the home.
    """
    wall = mat("FV_hillside_foundation", (.31, .30, .28), .97)
    cap = mat("FV_hillside_pad", (.34, .53, .27), .99)
    wall_boxes, cap_boxes = [], []
    for b in buildings:
        if b.get("type") != "house" or not b.get("plan_id"):
            continue
        x, y = build_pos(b)
        rotation = b.get("rot", 0.0)
        low, top = hillside_pad_levels(x, y, rotation)
        bottom = low - .30
        wall_boxes.append((x,y,bottom,8.65,9.25,top-bottom,rotation))
        # Let the pad overlap the first four centimetres of the house base.
        # Coplanar pad/foundation faces previously competed in the depth buffer
        # and flickered as the player moved.
        cap_boxes.append((x,y,top-.14,8.85,9.45,.18,rotation))
    _add_rotated_box_batch(world_col,"hillside_foundations",wall_boxes,wall)
    _add_rotated_box_batch(world_col,"hillside_pads",cap_boxes,cap)


def _add_rotated_box_batch(collection, name, boxes, material):
    """Export many oriented solids as one mesh without losing placement."""
    if not boxes:
        return None
    vertices,faces=[],[]
    for x,y,z,width,depth,height,rotation in boxes:
        start=len(vertices);hw,hd=width/2,depth/2
        c,s=math.cos(rotation),math.sin(rotation)
        def point(lx,ly,lz):
            return (x+lx*c-ly*s,y+lx*s+ly*c,z+lz)
        vertices.extend((point(-hw,-hd,0),point(hw,-hd,0),point(hw,hd,0),point(-hw,hd,0),
                         point(-hw,-hd,height),point(hw,-hd,height),
                         point(hw,hd,height),point(-hw,hd,height)))
        faces.extend(((start,start+1,start+2,start+3),(start+4,start+7,start+6,start+5),
                      (start,start+4,start+5,start+1),(start+1,start+5,start+6,start+2),
                      (start+2,start+6,start+7,start+3),(start+3,start+7,start+4,start)))
    mesh=bpy.data.meshes.new(name+"_mesh");mesh.from_pydata(vertices,[],faces)
    mesh.materials.append(material);mesh.update()
    obj=bpy.data.objects.new(name,mesh);collection.objects.link(obj)
    return obj


def _add_ellipse_ring_pad(col, name, rx_outer, ry_outer, rx_inner, ry_inner,
                          z, height, material, sides=64):
    """Shallow solid elliptical ring with explicitly separated top quads."""
    verts = []
    for level_z in (0.0, height):
        for rx, ry in ((rx_outer, ry_outer), (rx_inner, ry_inner)):
            for i in range(sides):
                angle = math.tau * i / sides
                verts.append((rx * math.cos(angle), ry * math.sin(angle), level_z))
    ob, ib, ot, it = 0, sides, sides * 2, sides * 3
    faces = []
    for i in range(sides):
        j = (i + 1) % sides
        faces.extend(((ot+i, ot+j, it+j, it+i),       # top
                      (ob+j, ob+i, ib+i, ib+j),       # bottom
                      (ob+i, ob+j, ot+j, ot+i),       # outer wall
                      (ib+j, ib+i, it+i, it+j)))      # inner wall
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location.z = z
    col.objects.link(obj)
    return obj


def _add_storybook_plateau(col, material):
    """Terraced, flat-topped hill sized for all ten lots without clipping."""
    sides = 48
    rings = ((64.0, 50.0, .02), (61.0, 48.0, .72),
             (58.0, 46.0, 1.72), (56.0, 44.0, 2.60))
    verts = []
    for rx, ry, z in rings:
        for i in range(sides):
            angle = math.tau * i / sides
            ripple = 1 + .018 * math.sin(i * 2.31)
            verts.append((rx * ripple * math.cos(angle),
                          ry * ripple * math.sin(angle), z))
    verts.append((0, 0, rings[-1][2]))
    center = len(verts) - 1
    faces = []
    for ring in range(len(rings) - 1):
        a0, b0 = ring * sides, (ring + 1) * sides
        for i in range(sides):
            j = (i + 1) % sides
            faces.append((a0+i, a0+j, b0+j, b0+i))
    for i in range(sides):
        faces.append(((len(rings)-1)*sides+i,
                      (len(rings)-1)*sides+(i+1)%sides, center))
    mesh = bpy.data.meshes.new("storybook_hill_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new("storybook_hill", mesh)
    col.objects.link(obj)
    return obj


def _smooth_object(obj):
    """Mark a modeled prop smooth without affecting its flat end caps."""
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def _add_connected_tube(col, name, points, radii, materials, sides=12):
    """Build one capped, shared-ring tube through an arbitrary 3D path.

    Unlike several rotated cubes or cylinders, adjacent bends share the exact
    same ring of vertices. That prevents daylight gaps and floating-looking
    joints in the web export, even when viewed up close from an oblique angle.
    """
    path = [Vector(point) for point in points]
    if len(path) < 2:
        raise ValueError("A connected tube needs at least two path points")
    if isinstance(radii, (int, float)):
        radius_pairs = [(float(radii), float(radii))] * len(path)
    else:
        radius_pairs = []
        for radius in radii:
            radius_pairs.append((float(radius), float(radius))
                                if isinstance(radius, (int, float))
                                else (float(radius[0]), float(radius[1])))
        if len(radius_pairs) != len(path):
            raise ValueError("Tube radii must match the number of path points")
    tube_materials = list(materials) if isinstance(materials, (tuple, list)) else [materials]
    if not tube_materials:
        raise ValueError("A connected tube needs at least one material")

    tangents = []
    for index in range(len(path)):
        if index == 0:
            tangent = path[1] - path[0]
        elif index == len(path) - 1:
            tangent = path[-1] - path[-2]
        else:
            tangent = path[index + 1] - path[index - 1]
        tangents.append(tangent.normalized())

    # Parallel-transport one radial axis down the path. Computing an unrelated
    # look quaternion at every ring can flip 180 degrees on a gentle bend,
    # cross-stitching the next set of faces into an hourglass. Transport keeps
    # vertex correspondence stable and produces a genuinely continuous tube.
    reference = Vector((1, 0, 0))
    if abs(reference.dot(tangents[0])) > .92:
        reference = Vector((0, 1, 0))
    radial = reference - tangents[0] * reference.dot(tangents[0])
    radial.normalize()

    vertices = []
    for index, (point, radius) in enumerate(zip(path, radius_pairs)):
        tangent = tangents[index]
        if index:
            transported = radial - tangent * radial.dot(tangent)
            if transported.length_squared < 1e-8:
                reference = Vector((0, 1, 0)) if abs(tangent.y) < .92 else Vector((1, 0, 0))
                transported = reference - tangent * reference.dot(tangent)
            radial = transported.normalized()
        binormal = tangent.cross(radial).normalized()
        for side in range(sides):
            angle = math.tau * side / sides
            offset = (radial * (math.cos(angle) * radius[0]) +
                      binormal * (math.sin(angle) * radius[1]))
            vertices.append(tuple(point + offset))

    faces, face_materials, face_smooth = [], [], []
    for segment in range(len(path) - 1):
        material_index = min(segment, len(tube_materials) - 1)
        for side in range(sides):
            next_side = (side + 1) % sides
            faces.append((segment * sides + side,
                          segment * sides + next_side,
                          (segment + 1) * sides + next_side,
                          (segment + 1) * sides + side))
            face_materials.append(material_index)
            face_smooth.append(True)
    faces.append(tuple(reversed(range(sides))))
    face_materials.append(0)
    face_smooth.append(False)
    end_start = (len(path) - 1) * sides
    faces.append(tuple(end_start + side for side in range(sides)))
    face_materials.append(min(len(path) - 2, len(tube_materials) - 1))
    face_smooth.append(False)

    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for material in tube_materials:
        mesh.materials.append(material)
    for polygon, material_index, use_smooth in zip(
            mesh.polygons, face_materials, face_smooth):
        polygon.material_index = material_index
        polygon.use_smooth = use_smooth
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    return obj


def _add_extruded_profile(col, name, xz_points, y_back, y_front, material):
    """Create a solid front-facing silhouette with attached side walls."""
    count = len(xz_points)
    vertices = [(x, y_back, z) for x, z in xz_points]
    vertices += [(x, y_front, z) for x, z in xz_points]
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, count + next_index, count + index))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    return obj


def _build_cat_in_hat_statue_legacy(col, ground_z):
    """Blocky, low-poly Cat in the Hat public-art figure for the center island."""
    black = mat("NB_cat_hat_statue_black", (.035, .045, .055), .72)
    white = mat("NB_cat_hat_statue_white", (.96, .95, .88), .82)
    red = mat("NB_cat_hat_statue_red", (.82, .045, .075), .70)
    eye = mat("NB_cat_hat_statue_eye", (.98, .84, .24), .48)
    stone = mat("NB_cat_hat_statue_stone", (.19, .28, .39), .92)
    stone_top = mat("NB_cat_hat_statue_stone_top", (.32, .45, .56), .86)
    plaque = mat("NB_cat_hat_statue_plaque", (.93, .66, .17), .52)

    # A stepped pedestal gives the figure enough visual weight to read from
    # the road and provides one honest, compact collision footprint.
    add_ngon_cone(col, "cat_statue_lower_plinth", 1.95, 1.78, .28, 12,
                  0, 0, ground_z, stone)
    add_box(col, "cat_statue_pedestal", 2.85, 2.85, .62,
            0, 0, ground_z + .28, stone)
    add_ngon_cone(col, "cat_statue_upper_plinth", 1.62, 1.45, .22, 12,
                  0, 0, ground_z + .90, stone_top)
    add_box(col, "cat_statue_plaque", 1.18, .09, .42,
            0, -1.455, ground_z + .43, plaque)
    body_z = ground_z + 1.12

    # Feet, legs, torso, belly, arms, gloves, and a curled tail create a clear
    # full-body silhouette instead of relying on the hat alone.
    for x in (-.43, .43):
        add_box(col, "cat_statue_leg", .48, .58, 1.15,
                x, 0, body_z, black)
        paw = add_uv_sphere(col, "cat_statue_paw", .46,
                            x, -.18, body_z + .08, white, 6, 9)
        paw.scale = (1.20, 1.50, .58)
    add_ngon_cone(col, "cat_statue_torso", 1.04, .78, 2.20, 10,
                  0, 0, body_z + .78, black, .12)
    belly = add_uv_sphere(col, "cat_statue_belly", .84,
                          0, -.79, body_z + 1.85, white, 7, 10)
    belly.scale = (.72, .24, 1.10)
    add_beam_between(col, "cat_statue_left_arm",
                     (-.62, 0, body_z + 2.45),
                     (-1.48, -.05, body_z + 2.95), .26, black)
    add_beam_between(col, "cat_statue_left_forearm",
                     (-1.48, -.05, body_z + 2.95),
                     (-1.67, -.08, body_z + 3.72), .23, black)
    add_uv_sphere(col, "cat_statue_left_glove", .42,
                  -1.67, -.08, body_z + 3.82, white, 6, 9)
    add_beam_between(col, "cat_statue_right_arm",
                     (.62, 0, body_z + 2.45),
                     (1.48, -.08, body_z + 1.96), .26, black)
    add_uv_sphere(col, "cat_statue_right_glove", .42,
                  1.58, -.10, body_z + 1.90, white, 6, 9)
    tail_points = ((.70, .36, body_z + 1.25),
                   (1.52, .50, body_z + 1.55),
                   (1.92, .52, body_z + 2.25),
                   (1.74, .45, body_z + 2.88))
    for a, b in zip(tail_points, tail_points[1:]):
        add_beam_between(col, "cat_statue_tail", a, b, .22, black)
    add_uv_sphere(col, "cat_statue_tail_tip", .28,
                  *tail_points[-1], white, 5, 8)

    # Head, muzzle, eyes, nose, smile, and whiskers are modeled separately so
    # the face remains readable from the surrounding homes at web resolution.
    head_z = body_z + 3.78
    head = add_uv_sphere(col, "cat_statue_head", 1.02,
                         0, 0, head_z, black, 8, 12)
    head.scale = (1.0, .84, 1.02)
    for x in (-.68, .68):
        ear = add_ngon_cone(col, "cat_statue_ear", .34, 0, .58, 4,
                            x, .04, head_z + .53, black, math.pi/4)
        ear.scale.y = .72
    for x in (-.36, .36):
        muzzle = add_uv_sphere(col, "cat_statue_muzzle", .56,
                               x, -.78, head_z - .24, white, 6, 9)
        muzzle.scale = (.78, .28, .52)
        eye_white = add_uv_sphere(col, "cat_statue_eye_white", .28,
                                  x*.84, -.80, head_z + .28, white, 6, 9)
        eye_white.scale = (.70, .25, 1.00)
        pupil = add_uv_sphere(col, "cat_statue_pupil", .105,
                              x*.84, -.875, head_z + .27, eye, 5, 8)
        pupil.scale.y = .42
    add_uv_sphere(col, "cat_statue_nose", .17,
                  0, -.99, head_z - .13, red, 5, 8)
    add_beam_between(col, "cat_statue_smile_left",
                     (-.48, -.965, head_z - .42),
                     (0, -.995, head_z - .55), .045, black)
    add_beam_between(col, "cat_statue_smile_right",
                     (0, -.995, head_z - .55),
                     (.48, -.965, head_z - .42), .045, black)
    for zoff, spread in ((-.19, 1.34), (-.34, 1.48)):
        add_beam_between(col, "cat_statue_whisker_left",
                         (-.42, -.94, head_z + zoff),
                         (-spread, -.92, head_z + zoff + .10), .035, white)
        add_beam_between(col, "cat_statue_whisker_right",
                         (.42, -.94, head_z + zoff),
                         (spread, -.92, head_z + zoff + .10), .035, white)

    for x in (-.39, .39):
        bow = add_uv_sphere(col, "cat_statue_bow", .48,
                            x, -.73, head_z - .91, red, 6, 9)
        bow.scale = (.96, .28, .56)
    add_uv_sphere(col, "cat_statue_bow_knot", .23,
                  0, -.87, head_z - .91, red, 5, 8)

    # The red-and-white stovepipe hat is deliberately oversized and gently
    # tapered so the character is unmistakable without a high-poly asset.
    hat_z = head_z + .82
    add_ngon_cone(col, "cat_statue_hat_brim", 1.38, 1.30, .20, 14,
                  0, 0, hat_z, red, .11)
    stripe_specs = ((white, .78, .74, .52), (red, .74, .82, .54),
                    (white, .82, .76, .52), (red, .76, .84, .54),
                    (white, .84, .72, .50))
    cursor = hat_z + .20
    for index, (material, radius0, radius1, height) in enumerate(stripe_specs):
        add_ngon_cone(col, "cat_statue_hat_stripe_%d" % index,
                      radius0, radius1, height, 12, 0, 0, cursor, material, .11)
        cursor += height
    add_ngon_cone(col, "cat_statue_hat_top", .72, .68, .18, 12,
                  0, 0, cursor, red, .11)

    # A pair of low topiary mounds fills the former tree bed without crowding
    # the statue or hiding its compact pedestal from walkers.
    topiary = mat("NB_cat_hat_statue_topiary", (.18, .48, .29), 1.0)
    for x in (-4.2, 4.2):
        shrub = add_uv_sphere(col, "cat_statue_topiary", 1.05,
                              x, 1.1, ground_z + .68, topiary, 6, 9)
        shrub.scale = (1.28, .88, .78)


def _build_cat_in_hat_statue(col, ground_z):
    """Connected hero-quality Cat in the Hat sculpture for the center island.

    Major silhouettes use shared-ring meshes and every smaller feature embeds
    into its parent. The result stays physically assembled from every camera
    angle instead of relying on loose primitives that only line up head-on.
    """
    black = mat("NB_cat_hat_statue_black", (.025, .032, .042), .64)
    charcoal = mat("NB_cat_hat_statue_charcoal", (.08, .10, .13), .70)
    white = mat("NB_cat_hat_statue_white", (.97, .955, .88), .76)
    red = mat("NB_cat_hat_statue_red", (.84, .025, .055), .62)
    dark_red = mat("NB_cat_hat_statue_dark_red", (.46, .015, .028), .72)
    gold = mat("NB_cat_hat_statue_gold", (.96, .62, .10), .45)
    iris = mat("NB_cat_hat_statue_iris", (.93, .73, .16), .40)
    stone = mat("NB_cat_hat_statue_stone", (.16, .24, .34), .88)
    stone_top = mat("NB_cat_hat_statue_stone_top", (.31, .43, .53), .80)

    # Overlapping pedestal tiers form one grounded base. The inset gold band
    # and plaque are intentionally embedded rather than hovering on the face.
    add_ngon_cone(col, "cat_statue_base_foot", 2.18, 2.08, .24, 16,
                  0, 0, ground_z, stone)
    add_ngon_cone(col, "cat_statue_base_bevel", 2.08, 1.83, .22, 16,
                  0, 0, ground_z + .20, stone_top)
    add_box(col, "cat_statue_pedestal", 3.12, 3.12, .67,
            0, 0, ground_z + .38, stone)
    add_box(col, "cat_statue_gold_band", 3.20, 3.20, .105,
            0, 0, ground_z + .84, gold)
    add_ngon_cone(col, "cat_statue_cap", 1.82, 1.62, .27, 16,
                  0, 0, ground_z + .98, stone_top)
    add_box(col, "cat_statue_plaque", 1.42, .10, .46,
            0, -1.575, ground_z + .48, gold)
    add_box(col, "cat_statue_plaque_inset", 1.18, .055, .26,
            0, -1.637, ground_z + .58, dark_red)

    figure_z = ground_z + 1.17

    # Curved legs rise into the torso, while the broad paws overlap both the
    # legs and cap. Nothing can separate when exported or viewed from behind.
    for side in (-1, 1):
        x = .42 * side
        _add_connected_tube(
            col, "cat_statue_leg",
            ((x, .03, figure_z), (x + .035 * side, 0, figure_z + .62),
             (x * .82, -.02, figure_z + 1.25)),
            (.31, .29, .34), black, 14)
        paw = _smooth_object(add_uv_sphere(
            col, "cat_statue_paw", .49, x, -.21, figure_z + .08,
            white, 9, 14))
        paw.scale = (1.20, 1.48, .58)
        # Three shallow toe ridges are embedded into the front of each paw.
        for toe in (-.18, 0, .18):
            ridge = _smooth_object(add_uv_sphere(
                col, "cat_statue_toe", .105, x + toe, -.67,
                figure_z + .12, charcoal, 6, 9))
            ridge.scale = (.60, .36, .34)

    torso = _smooth_object(add_uv_sphere(
        col, "cat_statue_torso", 1.14, 0, .02, figure_z + 2.00,
        black, 12, 18))
    torso.scale = (.79, .66, 1.30)
    belly = _smooth_object(add_uv_sphere(
        col, "cat_statue_belly", .89, 0, -.68, figure_z + 1.94,
        white, 11, 16))
    belly.scale = (.66, .27, 1.04)

    # The left arm gestures upward; the right presents the surrounding town.
    # Each limb is one tapered shared-ring tube with its shoulder buried in
    # the body and its cuff buried into both forearm and palm.
    left_arm = ((-.58, -.02, figure_z + 2.46),
                (-1.05, -.10, figure_z + 2.83),
                (-1.42, -.13, figure_z + 3.35),
                (-1.47, -.15, figure_z + 3.83))
    _add_connected_tube(col, "cat_statue_left_arm", left_arm,
                        (.32, .29, .255, .22), black, 14)
    _add_connected_tube(col, "cat_statue_left_cuff",
                        ((-1.47, -.15, figure_z + 3.72),
                         (-1.47, -.17, figure_z + 3.98)),
                        (.32, .29), white, 14)
    left_palm = _smooth_object(add_uv_sphere(
        col, "cat_statue_left_palm", .39, -1.47, -.18,
        figure_z + 4.10, white, 9, 14))
    left_palm.scale = (.82, .64, 1.02)
    for offset, lean in ((-.18, -.18), (0, 0), (.18, .18)):
        finger_start = (-1.47 + offset, -.18, figure_z + 4.22)
        finger_end = (-1.47 + offset + lean, -.18, figure_z + 4.62 - abs(offset) * .30)
        _add_connected_tube(col, "cat_statue_left_finger",
                            (finger_start, finger_end), (.115, .085), white, 9)
        _smooth_object(add_uv_sphere(col, "cat_statue_left_fingertip", .09,
                                     *finger_end, white, 6, 9))
    _add_connected_tube(col, "cat_statue_left_thumb",
                        ((-1.29, -.21, figure_z + 4.08),
                         (-1.07, -.22, figure_z + 4.18)),
                        (.12, .085), white, 9)

    right_arm = ((.59, -.02, figure_z + 2.48),
                 (1.04, -.14, figure_z + 2.27),
                 (1.45, -.22, figure_z + 1.92),
                 (1.72, -.26, figure_z + 1.99))
    _add_connected_tube(col, "cat_statue_right_arm", right_arm,
                        (.32, .29, .255, .22), black, 14)
    _add_connected_tube(col, "cat_statue_right_cuff",
                        ((1.62, -.25, figure_z + 1.97),
                         (1.88, -.30, figure_z + 2.02)),
                        (.32, .29), white, 14)
    right_palm = _smooth_object(add_uv_sphere(
        col, "cat_statue_right_palm", .40, 1.99, -.32,
        figure_z + 2.04, white, 9, 14))
    right_palm.scale = (1.03, .64, .79)
    for zoff, spread in ((.18, .37), (0, .43), (-.18, .34)):
        finger_start = (2.13, -.33, figure_z + 2.04 + zoff)
        finger_end = (2.13 + spread, -.34, figure_z + 2.04 + zoff * 1.45)
        _add_connected_tube(col, "cat_statue_right_finger",
                            (finger_start, finger_end), (.11, .075), white, 9)
        _smooth_object(add_uv_sphere(col, "cat_statue_right_fingertip", .082,
                                     *finger_end, white, 6, 9))
    _add_connected_tube(col, "cat_statue_right_thumb",
                        ((1.91, -.38, figure_z + 1.83),
                         (2.10, -.40, figure_z + 1.67)),
                        (.115, .08), white, 9)

    # One continuous curl, including its white final segment, replaces the
    # old stack of beams and detached tip sphere.
    tail_points = ((.66, .31, figure_z + 1.45),
                   (1.30, .49, figure_z + 1.55),
                   (1.82, .55, figure_z + 2.02),
                   (1.96, .49, figure_z + 2.62),
                   (1.70, .34, figure_z + 3.07),
                   (1.43, .20, figure_z + 3.28))
    _add_connected_tube(col, "cat_statue_tail", tail_points,
                        (.27, .25, .23, .21, .20, .16),
                        (black, black, black, black, white), 14)

    # The head overlaps the torso and all face layers are inset into the head
    # or muzzle. Ears have inner panels that sit inside the black ear profile.
    head_z = figure_z + 3.88
    head = _smooth_object(add_uv_sphere(
        col, "cat_statue_head", 1.06, 0, 0, head_z,
        black, 13, 20))
    head.scale = (1.0, .84, 1.04)
    for side in (-1, 1):
        ear = add_ngon_cone(col, "cat_statue_ear", .39, .04, .68, 5,
                            .68 * side, -.01, head_z + .46, black, math.pi/2)
        ear.scale.y = .68
        inner = add_ngon_cone(col, "cat_statue_inner_ear", .24, .025, .43, 5,
                              .68 * side, -.20, head_z + .55, red, math.pi/2)
        inner.scale.y = .42

    # Connected white brow/mask bridge gives the eyes one coherent expression.
    mask_profile = [(-.63, head_z + .47), (-.50, head_z + .73),
                    (-.13, head_z + .64), (0, head_z + .50),
                    (.13, head_z + .64), (.50, head_z + .73),
                    (.63, head_z + .47), (.47, head_z + .10),
                    (0, head_z + .20), (-.47, head_z + .10)]
    _add_extruded_profile(col, "cat_statue_eye_mask", mask_profile,
                          -.73, -.90, white)
    for side in (-1, 1):
        eye_white = _smooth_object(add_uv_sphere(
            col, "cat_statue_eye_white", .31, .31 * side, -.88,
            head_z + .40, white, 10, 14))
        eye_white.scale = (.72, .24, 1.06)
        eye_iris = _smooth_object(add_uv_sphere(
            col, "cat_statue_iris", .145, .31 * side, -.947,
            head_z + .38, iris, 8, 12))
        eye_iris.scale = (.80, .22, 1.0)
        pupil = _smooth_object(add_uv_sphere(
            col, "cat_statue_pupil", .07, .31 * side, -.982,
            head_z + .38, black, 7, 10))
        pupil.scale = (.72, .20, 1.12)

    muzzle_profile = [(-.79, head_z - .17), (-.62, head_z + .08),
                      (-.25, head_z + .10), (0, head_z - .04),
                      (.25, head_z + .10), (.62, head_z + .08),
                      (.79, head_z - .17), (.56, head_z - .54),
                      (0, head_z - .62), (-.56, head_z - .54)]
    _add_extruded_profile(col, "cat_statue_muzzle_mask", muzzle_profile,
                          -.73, -.93, white)
    for side in (-1, 1):
        muzzle = _smooth_object(add_uv_sphere(
            col, "cat_statue_muzzle", .53, .31 * side, -.86,
            head_z - .25, white, 10, 15))
        muzzle.scale = (.82, .25, .55)
    nose = _smooth_object(add_uv_sphere(
        col, "cat_statue_nose", .18, 0, -1.01,
        head_z - .12, red, 8, 12))
    nose.scale = (1.14, .64, .82)
    _add_connected_tube(col, "cat_statue_smile",
                        ((-.44, -.995, head_z - .43),
                         (0, -1.025, head_z - .57),
                         (.44, -.995, head_z - .43)),
                        (.045, .05, .045), dark_red, 8)
    for side in (-1, 1):
        for index, zoff in enumerate((-.17, -.33, -.48)):
            start = (.40 * side, -.955, head_z + zoff)
            end = ((1.32 + index * .10) * side, -.94,
                   head_z + zoff + (.10 - index * .07))
            _add_connected_tube(col, "cat_statue_whisker",
                                (start, end), (.04, .025), white, 7)

    # The bow is one solid extruded silhouette behind an overlapping knot.
    bow_z = head_z - .92
    bow_profile = [(-.04, bow_z), (-.32, bow_z + .28),
                   (-.82, bow_z + .38), (-.75, bow_z),
                   (-.82, bow_z - .38), (-.32, bow_z - .27),
                   (-.04, bow_z), (.32, bow_z - .27),
                   (.82, bow_z - .38), (.75, bow_z),
                   (.82, bow_z + .38), (.32, bow_z + .28)]
    _add_extruded_profile(col, "cat_statue_bow", bow_profile,
                          -.61, -.91, red)
    knot = _smooth_object(add_uv_sphere(
        col, "cat_statue_bow_knot", .28, 0, -.96, bow_z,
        dark_red, 8, 12))
    knot.scale.y = .62

    # A single shared-ring crooked hat body carries all six alternating bands.
    # Band boundaries reuse identical vertices, eliminating the floating stack
    # effect of the previous separately capped cones.
    hat_base_z = head_z + .84
    brim = add_ngon_cone(col, "cat_statue_hat_brim", 1.43, 1.34, .24, 20,
                         0, 0, hat_base_z, red, math.pi/20)
    brim.scale.y = .82
    hat_points = ((0, 0, hat_base_z + .18),
                  (.02, .01, hat_base_z + .68),
                  (-.05, .015, hat_base_z + 1.19),
                  (.07, .02, hat_base_z + 1.70),
                  (.18, .015, hat_base_z + 2.20),
                  (.32, .00, hat_base_z + 2.67),
                  (.43, -.02, hat_base_z + 3.07))
    hat_radii = ((.84, .69), (.77, .64), (.82, .66), (.75, .62),
                 (.80, .64), (.70, .58), (.61, .51))
    _add_connected_tube(col, "cat_statue_banded_hat", hat_points,
                        hat_radii, (white, red, white, red, white, red), 20)
    _add_connected_tube(col, "cat_statue_hat_rim_band",
                        ((-.76, -.01, hat_base_z + .26),
                         (.76, -.01, hat_base_z + .26)),
                        ((.055, .055), (.055, .055)), dark_red, 8)

    # Low topiary mounds frame the sculpture without obscuring its pedestal.
    topiary = mat("NB_cat_hat_statue_topiary", (.18, .48, .29), 1.0)
    for x in (-4.2, 4.2):
        shrub = _smooth_object(add_uv_sphere(
            col, "cat_statue_topiary", 1.05, x, 1.1,
            ground_z + .68, topiary, 8, 12))
        shrub.scale = (1.28, .88, .78)


def _build_storybook_street_asset(col):
    """Permanent hill, colored road, bespoke lamps, garden, and access road."""
    m = std_mats()
    hill = mat("NB_story_hill", (.31, .54, .28), 1.0)
    hill_top = mat("NB_story_hilltop", (.42, .71, .30), 1.0)
    road = mat("NB_story_road", (.73, .16, .31), .88)
    transition = mat("NB_story_transition", (.46, .24, .31), .91)
    curb = mat("NB_story_curb", (.97, .66, .16), .84)
    dash = mat("NB_story_dash", (1.0, .91, .54), .76)
    pole = mat("NB_story_pole", (.12, .40, .48), .58)
    banner_a = mat("NB_story_banner_a", (.95, .36, .52), .72)
    banner_b = mat("NB_story_banner_b", (.40, .69, .90), .72)
    island = mat("NB_story_island", (.28, .61, .25), 1.0)
    flower_mats = [
        mat("NB_story_public_flower_a", (.96, .30, .54), .78),
        mat("NB_story_public_flower_b", (.99, .76, .15), .78),
        mat("NB_story_public_flower_c", (.48, .35, .88), .78),
    ]
    _add_storybook_plateau(col, hill)
    _add_ellipse_pad(col, "storybook_hilltop", 0, 0, 54.5, 42.3,
                     2.60, .20, hill_top, 48)

    # Wind around the north side of Founder Park, then rise naturally through
    # the hill shoulder. The centerline is fully continuous with shared road
    # vertices, so bends cannot open into gaps.
    cx, cy = STORYBOOK_LAYOUT_CENTER
    absolute_access = [(87, 33, 0.0), (112, 56, .02), (149, 72, .02),
                       (198, 74, .03), (236, 72, .05), (240, 71, .28),
                       (243, 70, .80), (246, 69, 1.55), (248, 68, 2.30),
                       (250, 68, 2.62), (254, 67, 2.74),
                       (264, 65, 2.74), (274, 60, 2.74)]
    access = [(x-cx, y-cy, z) for x, y, z in absolute_access]
    # The access starts as the established asphalt at the existing grid
    # intersection, widens gradually, then transitions into the feature-road
    # color. This avoids laying a bright diagonal slab across the old road.
    access_widths = [6.0, 6.3, 6.7] + [7.0] * (len(access) - 3)
    access_materials = [m["road"], transition] + [road] * (len(access) - 3)
    _add_road_strip(col, "storybook_access", access, road, 7.0, .015, .085,
                    widths=access_widths,
                    segment_materials=access_materials,
                    terrain_origin=(cx, cy))

    # Main road and its raised golden curbs are solid rings at distinct
    # elevations; they remain stable in long-lens aerial renders.
    _add_ellipse_ring_pad(col, "storybook_loop_road",
                          34.5, 25.5, 27.5, 18.5, 2.76, .22, road, 72)
    _add_ellipse_ring_pad(col, "storybook_outer_curb",
                          35.15, 26.15, 34.45, 25.45, 2.96, .18, curb, 72)
    _add_ellipse_ring_pad(col, "storybook_inner_curb",
                          27.55, 18.55, 26.85, 17.85, 2.96, .18, curb, 72)

    for i in range(28):
        angle = math.tau * (i + .5) / 28
        x, y = 31.0 * math.cos(angle), 22.0 * math.sin(angle)
        tangent = math.atan2(22.0 * math.cos(angle), -31.0 * math.sin(angle))
        mark = add_box(col, "storybook_lane_dash", 2.15, .40, .075,
                       x, y, 2.995, dash)
        mark.rotation_euler.z = tangent

    # Access-road center dashes keep one continuous eight-metre rhythm across
    # every control segment. Each mark is a shallow mesh sampled at both ends
    # from the road centerline, so it physically lies on the climb instead of
    # remaining horizontal or hovering above it.
    access_total = sum(math.hypot(b[0]-a[0], b[1]-a[1])
                       for a, b in zip(access, access[1:]))
    dash_distance = 4.0
    while dash_distance < access_total - 2.0:
        remaining = dash_distance
        for segment_index, (a, b) in enumerate(zip(access, access[1:])):
            dx, dy, dz = b[0]-a[0], b[1]-a[1], b[2]-a[2]
            length = math.hypot(dx, dy)
            if remaining > length:
                remaining -= length
                continue
            dash_material = m["dash"] if segment_index == 0 else dash
            _add_road_surface_dash(col, "storybook_access_dash", access,
                                   dash_distance, 2.15, .40, .096, .015,
                                   dash_material)
            break
        dash_distance += 8.0

    # Oval garden in the center makes the turnaround feel authored rather
    # than empty. It is walkable open space, not another building.
    _add_ellipse_pad(col, "storybook_island", 0, 0, 24.8, 15.8,
                     2.81, .13, island, 48)
    for i in range(34):
        angle = math.tau * i / 34
        radius_x = 17.0 + 2.4 * math.sin(i * 1.7)
        radius_y = 9.8 + 1.4 * math.cos(i * 1.3)
        x, y = radius_x * math.cos(angle), radius_y * math.sin(angle)
        add_ngon_cone(col, "public_flower_stem", .06, .045, .34, 6,
                      x, y, 2.94, m["trunk"])
        add_uv_sphere(col, "public_flower", .20, x, y, 3.34,
                      flower_mats[i % len(flower_mats)], 5, 7)
    _build_cat_in_hat_statue(col, 2.94)

    # Crooked teal lamps with alternating fabric banners. Each main post is a
    # single shared-ring tube from its base through its hook, so bends cannot
    # split into disconnected upper/lower pieces in Blender or the web GLB.
    for i in range(10):
        angle = math.tau * (i + .25) / 10
        x, y = 25.8 * math.cos(angle), 17.1 * math.sin(angle)
        base_z = 2.94
        inward = Vector((-math.cos(angle), -math.sin(angle), 0))
        tangent = Vector((-math.sin(angle), math.cos(angle), 0))
        bend = .42 if i % 2 else -.42
        p0 = Vector((x, y, base_z + .05))
        p1 = p0 + tangent * bend + Vector((0, 0, 2.35))
        p2 = p0 - tangent * (bend * .32) + inward * .08 + Vector((0, 0, 4.18))
        p3 = p2 + inward * .52 + Vector((0, 0, .20))
        _add_connected_tube(col, "storybook_lamp_post", (p0, p1, p2, p3),
                            (.22, .195, .17, .145), pole, 14)
        add_ngon_cone(col, "storybook_lamp_base", .29, .23, .22, 8,
                      p0[0], p0[1], base_z, pole)
        add_ngon_cone(col, "storybook_lamp_base_ring", .37, .29, .10, 10,
                      p0[0], p0[1], base_z, pole)
        globe = _smooth_object(add_uv_sphere(
            col, "storybook_lamp_globe", .36, p3[0], p3[1], p3[2] + .08,
            m["bulb"], 9, 14))
        globe.scale = (.90, .90, 1.08)

        # Two metal brackets physically enter both the post and the banner.
        # The banner hangs tangent to the loop and therefore never appears to
        # float beside a post when viewed from the road or nearby houses.
        banner_center = p1 + tangent * (.70 if bend > 0 else -.70)
        banner_sign = 1 if bend > 0 else -1
        banner_bottom = base_z + 2.62
        banner_height = 1.26
        for bracket_z in (banner_bottom + .10, banner_bottom + banner_height - .10):
            post_at_z = Vector((p1.x, p1.y, bracket_z))
            near_edge = Vector((banner_center.x, banner_center.y, bracket_z)) \
                        - tangent * (.49 * banner_sign)
            _add_connected_tube(col, "storybook_banner_bracket",
                                (post_at_z, near_edge), (.065, .055), pole, 8)
        banner = add_box(col, "storybook_banner", 1.02, .10, banner_height,
                         banner_center.x, banner_center.y, banner_bottom,
                         banner_a if i % 2 else banner_b)
        banner.rotation_euler.z = angle + math.pi/2

    _merge_asset_meshes(col, "kaleidoscope_crest_street")


def build_storybook_street(world_col, buildings):
    """Reveal the feature hill/street only once one of its homes exists."""
    if not any(b.get("feature_id") == STORYBOOK_FEATURE_ID for b in buildings):
        return None
    asset = get_asset("AST_kaleidoscope_crest_street", _build_storybook_street_asset)
    empty = bpy.data.objects.new("kaleidoscope_crest_street", None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = asset
    empty.location = (STORYBOOK_LAYOUT_CENTER[0], STORYBOOK_LAYOUT_CENTER[1], 0)
    world_col.objects.link(empty)
    return empty

def animate_ring_traffic(world_col, buildings, frame_end):
    """A couple of cars slowly loop each park district's ring roads."""
    for d in [b for b in buildings if b["type"] == "parkdistrict"]:
        rng = random.Random(6000 + d["seed"])
        district_x, district_y = transform_building_point(d)
        for rr in (20.5, 40.5):
            if rng.random() < 0.2:
                continue
            c = {"type": "car", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
            e = place_instance(world_col, c, "ringtraffic")
            lane = 1.5 * (1 if rng.random() < 0.5 else -1)
            r = rr + lane
            spin = 1 if lane > 0 else -1
            speed = (10.0 + rng.random() * 5.0) / FPS
            arc = speed * frame_end / r
            a0 = rng.random() * math.tau
            wps = max(12, int(arc * 8))
            for wp in range(wps + 1):
                fr = 1 + (frame_end - 1) * wp / wps
                a = a0 + spin * arc * wp / wps
                e.location = (district_x + r * math.cos(a), district_y + r * math.sin(a), 0.17)
                e.rotation_euler = (0, 0, a + spin * math.pi / 2)
                e.keyframe_insert("location", frame=fr)
                e.keyframe_insert("rotation_euler", frame=fr)
            for fc in obj_fcurves(e):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

def scatter_nature(world_col, occupied, buildings):
    """Trees, bushes and rocks on empty lots + a wild ring around town.
    Seeded per lot, so the scenery is identical between videos until
    someone builds on that lot. Nature also clears automatically as planned
    suburban roads and house lots become active."""
    min_bx, max_bx, min_by, max_by = block_extent(buildings)
    active_plan_id = max((b.get("plan_id", 0) for b in buildings), default=0)
    active_segments = [(transform_point(seg["a"][0], seg["a"][1], district=seg.get("district")),
                        transform_point(seg["b"][0], seg["b"][1], district=seg.get("district")))
                       for seg in SUBURBAN_PLAN.get("roads", [])
                       if seg.get("reveal_at", 10**9) <= active_plan_id]
    active_bulbs = [transform_point(bulb["center"][0], bulb["center"][1],
                                    district=bulb.get("district"))
                    for bulb in SUBURBAN_PLAN.get("turnarounds", [])
                    if bulb.get("reveal_at", 10**9) <= active_plan_id]
    active_house_points = [transform_building_point(b) for b in buildings
                           if b.get("plan_id") and "px" in b and "py" in b]
    active_districts = {b.get("district") for b in buildings if b.get("plan_id")}
    active_segments.extend((a, b) for district in active_districts
                           for a, b in zip(DISTRICT_CONNECTORS.get(district, ()),
                                           DISTRICT_CONNECTORS.get(district, ())[1:]))

    def distance_to_segment(point, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        denom = dx * dx + dy * dy
        if denom <= .000001:
            return math.hypot(point[0] - a[0], point[1] - a[1])
        t = max(0.0, min(1.0,
                ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denom))
        return math.hypot(point[0] - (a[0] + t * dx),
                          point[1] - (a[1] + t * dy))

    for gx in range((min_bx - 1) * BLOCK_N, (max_bx + 2) * BLOCK_N):
        for gy in range((min_by - 1) * BLOCK_N, (max_by + 2) * BLOCK_N):
            if (gx, gy) in occupied:
                continue
            point = lot_to_world(gx, gy)
            # The scatter operates on the legacy grid, which can overlap the
            # exact-coordinate suburban reserve. Clear a canopy-sized buffer
            # only when that planned road/lot is actually developed.
            if any(distance_to_segment(point, a, b) < ROAD / 2 + 2.5
                   for a, b in active_segments):
                continue
            if any(math.hypot(point[0] - x, point[1] - y) < 7.5
                   for x, y in active_house_points):
                continue
            if any(math.hypot(point[0] - x, point[1] - y) < 10.5
                   for x, y in active_bulbs):
                continue
            r = random.Random(gx * 7919 + gy * 104729 + 13)
            roll = r.random()
            if roll < 0.22:
                btype = "tree"
            elif roll < 0.36:
                btype = "bush"
            elif roll < 0.42:
                btype = "rock"
            else:
                continue
            b = {"type": btype, "gx": gx, "gy": gy, "seed": r.randrange(99999)}
            place_instance(world_col, b, "nature")
            if r.random() < 0.3:  # occasional companion tree
                b2 = {"type": "tree", "gx": gx, "gy": gy, "seed": r.randrange(99999)}
                e2 = place_instance(world_col, b2, "nature")
                e2.location = (e2.location.x + r.uniform(-3, 3),
                               e2.location.y + r.uniform(-3, 3), 0)

def animate_traffic(world_col, buildings, frame_end, day):
    """A few cars drive through town for the whole clip — makes it feel alive."""
    min_bx, max_bx, min_by, max_by = block_extent(buildings)
    rng = random.Random(7000 + day)
    x0, x1 = min_bx * PITCH - ROAD, (max_bx + 1) * PITCH
    y0, y1 = min_by * PITCH - ROAD, (max_by + 1) * PITCH
    n = max(2, min(8, len(buildings) // 25 + 2))
    for _ in range(n):
        b = {"type": "car", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
        e = place_instance(world_col, b, "traffic")
        speed = (13.0 + rng.random() * 9.0) / FPS  # metres per frame
        lane = 1.5 if rng.random() < 0.5 else -1.5
        drive = speed * frame_end
        if rng.random() < 0.5:  # horizontal road
            y = rng.randint(min_by, max_by + 1) * PITCH - ROAD / 2 + lane
            sgn = 1 if lane > 0 else -1
            sx = x0 if sgn > 0 else x1
            e.rotation_euler = (0, 0, 0 if sgn > 0 else math.pi)
            e.location = (sx, y, 0.05)
            e.keyframe_insert("location", frame=1)
            e.location = (sx + sgn * drive, y, 0.05)
            e.keyframe_insert("location", frame=frame_end)
        else:  # vertical road
            x = rng.randint(min_bx, max_bx + 1) * PITCH - ROAD / 2 + lane
            sgn = 1 if lane < 0 else -1
            sy = y0 if sgn > 0 else y1
            e.rotation_euler = (0, 0, math.pi / 2 if sgn > 0 else -math.pi / 2)
            e.location = (x, sy, 0.05)
            e.keyframe_insert("location", frame=1)
            e.location = (x, sy + sgn * drive, 0.05)
            e.keyframe_insert("location", frame=frame_end)
        for fc in obj_fcurves(e):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

def animate_ducks(world_col, buildings, frame_end):
    """Ducks paddle slow loops around every pond in town -- the water version
    of animate_traffic. Ducks aren't saved to world_state; they're
    re-spawned fresh each run from the pond's own seed."""
    ponds = [b for b in buildings if b["type"] == "pond"]
    for b in ponds:
        cx, cy = lot_to_world(b["gx"], b["gy"])
        rng = random.Random(5000 + b["seed"])
        n = 2 + rng.randrange(3)
        for _ in range(n):
            d = {"type": "duck", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
            e = place_instance(world_col, d, "duck")
            r = 1.6 + rng.random() * 1.6  # swim radius -- stays inside the pond
            a0 = rng.random() * math.tau
            spin = (1 if rng.random() < 0.5 else -1) * (0.5 + rng.random() * 0.4)
            waypoints = 5
            for wp in range(waypoints + 1):
                frame = 1 + (frame_end - 1) * wp / waypoints
                a = a0 + spin * math.tau * wp / waypoints
                e.location = (cx + math.cos(a) * r, cy + math.sin(a) * r, 0.02)
                e.rotation_euler = (0, 0, a + math.pi / 2 * (1 if spin > 0 else -1))
                e.keyframe_insert("location", frame=frame)
                e.keyframe_insert("rotation_euler", frame=frame)
            for fc in obj_fcurves(e):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

def build_fireworks(world_col, cx, cy, frame_end):
    """One-off celebration: firework bursts above an area. Not saved to the
    world state — they exist only in videos rendered with --celebrate."""
    rng = random.Random(4242)
    colors = [(1.0, 0.35, 0.45), (1.0, 0.80, 0.30), (0.40, 0.70, 1.0),
              (0.72, 0.50, 1.0), (0.40, 1.0, 0.60)]
    fmats = []
    for i, c in enumerate(colors):
        fm = mat("NB_fw_%d" % i, c, 0.5)
        bsdf = fm.node_tree.nodes.get("Principled BSDF")
        try:
            bsdf.inputs["Emission Color"].default_value = (*c, 1.0)
            # 2026-07-09: was 9.0 -- readable at sunset but nearly invisible
            # against a bright daytime sky at drone distance; boosted so
            # daylight celebrations actually show up on camera
            bsdf.inputs["Emission Strength"].default_value = 30.0
        except Exception:
            pass
        fmats.append(fm)
    for k in range(6):
        bx = cx + rng.uniform(-26, 26)
        by = cy + rng.uniform(-20, 20)
        bz = 28 + rng.uniform(0, 12)
        t0 = int(25 + (max(frame_end - 100, 30)) * k / 6 + rng.uniform(0, 8))
        fm = fmats[k % len(fmats)]
        for _ in range(12):
            th = rng.uniform(0, math.tau)
            ph = math.acos(rng.uniform(-1, 1))
            dx = math.sin(ph) * math.cos(th)
            dy = math.sin(ph) * math.sin(th)
            dz = math.cos(ph)
            # 2026-07-09: particles enlarged (0.75->1.2) + wider spread so the
            # bursts read at drone distance in daylight, not just at sunset
            p = add_ngon_cone(world_col, "fw", 1.2, 0.8, 1.4, 6, bx, by, bz, fm)
            p.scale = (0.001, 0.001, 0.001)
            p.keyframe_insert("scale", frame=t0)
            p.keyframe_insert("location", frame=t0)
            p.location = (bx + dx * 8.5, by + dy * 8.5, bz + dz * 8.5)
            p.scale = (1, 1, 1)
            p.keyframe_insert("scale", frame=t0 + 7)
            p.keyframe_insert("location", frame=t0 + 7)
            p.location = (bx + dx * 13.0, by + dy * 13.0, bz + dz * 13.0 - 2.0)
            p.scale = (0.001, 0.001, 0.001)
            p.keyframe_insert("scale", frame=t0 + 22)
            p.keyframe_insert("location", frame=t0 + 22)

# ═══════════════════════ TIME OF DAY / SEASONS (mood) ═══════════════════════════

TODS = {
    "day":    dict(sun_e=2.0, sun_c=(1.00, 0.95, 0.86), sun_rot=(50, 0, 120),
                   sky=(0.54, 0.72, 0.86), sky_s=.72, win=0.0, lamp=0.0),
    "sunset": dict(sun_e=2.3, sun_c=(1.00, 0.52, 0.28), sun_rot=(78, 0, 100),
                   sky=(0.93, 0.60, 0.42), sky_s=1.0, win=3.0, lamp=5.0),
    "night":  dict(sun_e=0.30, sun_c=(0.55, 0.65, 1.00), sun_rot=(55, 0, 140),
                   sky=(0.05, 0.07, 0.14), sky_s=0.7, win=9.0, lamp=35.0),
}

SEASONS = {
    "spring": {"NB_grass": (0.44, 0.62, 0.32), "NB_lawn": (0.42, 0.68, 0.30),
               "NB_green0": (0.38, 0.62, 0.36), "NB_green1": (0.46, 0.68, 0.38),
               "NB_green2": (0.32, 0.56, 0.32)},
    "summer": {"NB_grass": (0.42, 0.60, 0.33), "NB_lawn": (0.40, 0.66, 0.30),
               "NB_green0": (0.31, 0.54, 0.31), "NB_green1": (0.36, 0.61, 0.33),
               "NB_green2": (0.25, 0.49, 0.27)},
    "fall":   {"NB_grass": (0.56, 0.49, 0.26), "NB_lawn": (0.58, 0.52, 0.26),
               "NB_green0": (0.74, 0.42, 0.16), "NB_green1": (0.80, 0.56, 0.20),
               "NB_green2": (0.62, 0.30, 0.14)},
    "winter": {"NB_grass": (0.86, 0.88, 0.91), "NB_lawn": (0.83, 0.86, 0.89),
               "NB_green0": (0.28, 0.42, 0.32), "NB_green1": (0.31, 0.46, 0.34),
               "NB_green2": (0.25, 0.39, 0.29)},
}

def auto_time(day):
    r = day % 9
    return "night" if r == 8 else ("sunset" if r == 4 else "day")

def auto_season():
    import datetime
    mth = datetime.date.today().month
    if mth in (12, 1, 2):
        return "winter"
    if mth in (3, 4, 5):
        return "spring"
    if mth in (6, 7, 8):
        return "summer"
    return "fall"

def _set_mat_color(name, rgb):
    m = bpy.data.materials.get(name)
    if m and m.use_nodes:
        b = m.node_tree.nodes.get("Principled BSDF")
        if b:
            b.inputs["Base Color"].default_value = (*rgb, 1.0)

def _set_mat_emission(name, rgb, strength):
    m = bpy.data.materials.get(name)
    if m and m.use_nodes:
        b = m.node_tree.nodes.get("Principled BSDF")
        if b:
            try:
                b.inputs["Emission Color"].default_value = (*rgb, 1.0)
                b.inputs["Emission Strength"].default_value = strength
            except KeyError:
                pass

def apply_mood(tod, season):
    t = TODS.get(tod, TODS["day"])
    _set_mat_emission("NB_window", (1.0, 0.82, 0.50), t["win"])
    _set_mat_emission("NB_bulb", (1.0, 0.90, 0.65), t["lamp"])
    for name, rgb in SEASONS.get(season, SEASONS["summer"]).items():
        _set_mat_color(name, rgb)

# ═══════════════════════════ ANIMATION / CAMERA / STAGE ═════════════════════════

def obj_fcurves(obj):
    """All fcurves of an object's action — works on Blender 3.x/4.x (legacy)
    and 4.4+/5.x layered ('slotted') actions."""
    ad = obj.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        fcs = list(act.fcurves)
        if fcs:
            return fcs
    except AttributeError:
        pass
    fcs = []
    try:
        for layer in act.layers:
            for strip in layer.strips:
                cb = None
                try:
                    cb = strip.channelbag(ad.action_slot)
                except Exception:
                    pass
                if cb is not None:
                    fcs.extend(cb.fcurves)
                else:
                    for cb2 in getattr(strip, "channelbags", []):
                        fcs.extend(cb2.fcurves)
    except Exception:
        pass
    return fcs

def _ease_scale(empty, easing):
    for fc in obj_fcurves(empty):
        if fc.data_path != "scale":
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = "BACK"
            kp.easing = easing

def _keyframe_hidden(empty, frame, hidden):
    empty.hide_viewport = hidden
    empty.hide_render = hidden
    empty.keyframe_insert("hide_viewport", frame=frame)
    empty.keyframe_insert("hide_render", frame=frame)

def animate_rise(empty, f_start, dur=22):
    rest = tuple(empty.get("nb_rest_scale", empty.scale))
    # invisible until its turn — no flattened houses lying on the ground
    _keyframe_hidden(empty, 1, True)
    _keyframe_hidden(empty, f_start, False)
    empty.scale = (rest[0], rest[1], max(.001, rest[2] * .001))
    empty.keyframe_insert("scale", frame=f_start)
    empty.scale = rest
    empty.keyframe_insert("scale", frame=f_start + dur)
    _ease_scale(empty, "EASE_OUT")

def animate_sink(empty, f_start, dur=20):
    """Follower lost: the house sinks back into the ground, then vanishes."""
    rest = tuple(empty.get("nb_rest_scale", empty.scale))
    _keyframe_hidden(empty, 1, False)
    _keyframe_hidden(empty, f_start + dur, True)
    empty.scale = rest
    empty.keyframe_insert("scale", frame=f_start)
    empty.scale = (rest[0], rest[1], max(.001, rest[2] * .001))
    empty.keyframe_insert("scale", frame=f_start + dur)
    _ease_scale(empty, "EASE_IN")

def city_center_and_extent(buildings):
    if not buildings:
        return 15, 15, 105  # frame the empty starter road grid
    xs, ys = [], []
    for b in buildings:
        x, y = build_pos(b)
        r = b.get("r", 0)
        xs += [x - r, x + r]
        ys += [y - r, y + r]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ext = max(max(xs) - min(xs), max(ys) - min(ys), 40)
    return cx, cy, ext

def build_football_vignette(world_col, buildings, frame_end):
    """Temporary fan-prediction set used only by ``--cam football``.

    This deliberately says "TONIGHT" and uses a question mark instead of
    inventing a match result before England v Argentina has been played. The
    #10 memorial is a visual sports metaphor, not a permanent town object.
    """
    m_white = mat("NB_fan_white", (0.96, 0.97, 0.98), 0.8)
    m_red = mat("NB_fan_england_red", (0.78, 0.04, 0.05), 0.72)
    m_sky = mat("NB_fan_argentina_sky", (0.28, 0.68, 0.91), 0.7)
    m_blue = mat("NB_fan_navy", (0.04, 0.10, 0.24), 0.7)
    m_gold = mat("NB_fan_gold", (0.96, 0.68, 0.08), 0.5)
    m_stone = mat("NB_fan_stone", (0.34, 0.36, 0.40), 0.9)
    m_dark = mat("NB_fan_dark", (0.025, 0.035, 0.05), 0.8)
    m_turf = mat("NB_fan_turf", (0.10, 0.42, 0.16), 1.0)
    m_plane = mat("NB_fan_plane", (0.80, 0.84, 0.88), 0.55)

    points = [build_pos(b) for b in buildings]
    xs = [p[0] for p in points] or [0.0]
    ys = [p[1] for p in points] or [0.0]
    cx = (min(xs) + max(xs)) / 2
    # Put the temporary set just south of the developed town. The camera
    # looks north so real Followville houses remain the background.
    sy = min(ys) - 27.0

    # Small football presentation terrace and touchline accents.
    add_box(world_col, "fan_pitch", 31, 23, .35, cx, sy + 3, .02, m_turf)
    add_box(world_col, "fan_touchline_front", 29, .18, .06,
            cx, sy - 7.5, .38, m_white)
    add_box(world_col, "fan_touchline_back", 29, .18, .06,
            cx, sy + 13.5, .38, m_white)
    add_box(world_col, "fan_touchline_left", .18, 21, .06,
            cx - 14.5, sy + 3, .38, m_white)
    add_box(world_col, "fan_touchline_right", .18, 21, .06,
            cx + 14.5, sy + 3, .38, m_white)

    # Match card: no fake score, only the verified semi-final matchup.
    add_box(world_col, "fan_scoreboard", 18, .7, 6.4,
            cx, sy + 11.0, 2.0, m_blue)
    add_box(world_col, "fan_scoreboard_cap", 19, .9, .35,
            cx, sy + 11.0, 8.35, m_gold)
    add_text(world_col, "fan_semifinal_text", "WORLD CUP SEMI-FINAL",
             .75, .055, cx, sy + 10.60, 7.15, m_gold)
    add_text(world_col, "fan_match_text", "ENGLAND  v  ARGENTINA",
             .72, .06, cx, sy + 10.59, 5.25, m_white)
    add_text(world_col, "fan_tonight_text", "TONIGHT",
             .88, .055, cx, sy + 10.58, 3.35, m_red)

    # Symbolic #10 / "GOAT defeated?" football memorial.
    add_box(world_col, "fan_grave_base", 6.4, 3.8, .6,
            cx, sy + 1.8, .35, m_stone)
    stone = add_box(world_col, "fan_number10_stone", 4.8, 1.25, 5.8,
                    cx, sy + 2.1, .9, m_stone)
    bevel = stone.modifiers.new("Rounded stone", "BEVEL")
    bevel.width = .38
    bevel.segments = 3
    add_text(world_col, "fan_goat_text", "THE GOAT?",
             .65, .06, cx, sy + 1.44, 5.35, m_white)
    add_text(world_col, "fan_ten_text", "#10",
             1.5, .09, cx, sy + 1.42, 3.45, m_gold)
    add_text(world_col, "fan_defeated_text", "DEFEATED?",
             .57, .055, cx, sy + 1.40, 1.85, m_red)
    ball = add_uv_sphere(world_col, "fan_football", 1.0,
                         cx + 3.7, sy - .1, 1.3, m_white)
    # Simple dark panels make the ball read immediately at Reel size.
    for a in (0, math.tau / 3, 2 * math.tau / 3):
        add_uv_sphere(world_col, "fan_ball_panel", .23,
                      ball.location.x + .84 * math.cos(a),
                      ball.location.y - .25,
                      ball.location.z + .55 * math.sin(a), m_dark, 5, 8)

    def flag_on_pole(prefix, x, stripe_mats, lowered=False):
        pole_h = 8.0
        add_ngon_cone(world_col, prefix + "_pole", .10, .08, pole_h, 10,
                      x, sy + .2, .4, m_plane)
        top = 6.2 if lowered else 8.0
        flag_h, flag_w = 4.2, 6.3
        stripe_h = flag_h / len(stripe_mats)
        for i, stripe_mat in enumerate(stripe_mats):
            z = top - flag_h + i * stripe_h
            add_box(world_col, prefix + "_stripe", flag_w, .12, stripe_h,
                    x + flag_w / 2, sy + .15, z, stripe_mat)
        return top, flag_w, flag_h

    # Argentina lowered beside #10; England fully raised on the other side.
    flag_on_pole("fan_argentina", cx - 10.7, (m_sky, m_white, m_sky), True)
    top, fw, fh = flag_on_pole("fan_england", cx + 4.3,
                               (m_white,), False)
    add_box(world_col, "fan_england_cross_h", fw, .14, .72,
            cx + 4.3 + fw / 2, sy + .08, top - fh / 2 - .36, m_red)
    add_box(world_col, "fan_england_cross_v", .72, .14, fh,
            cx + 4.3 + fw / 2, sy + .07, top - fh, m_red)

    # Low-poly flyby. All pieces are local to one animated root so the plane
    # and its St George banner cross the town together in the background.
    fly = bpy.data.objects.new("EnglandFlyby", None)
    world_col.objects.link(fly)
    fly_parts = []
    fly_parts.append(add_box(world_col, "fan_plane_fuselage", 8.5, 1.3, 1.25,
                             1.0, 0, 0, m_plane))
    fly_parts.append(add_box(world_col, "fan_plane_wings", 3.6, 9.5, .22,
                             1.1, 0, .48, m_white))
    fly_parts.append(add_box(world_col, "fan_plane_tail", 2.0, 3.7, .18,
                             -3.0, 0, .55, m_red))
    fly_parts.append(add_box(world_col, "fan_plane_fin", 1.4, .2, 2.0,
                             -3.2, 0, .5, m_red))
    fly_parts.append(add_box(world_col, "fan_plane_cockpit", 2.1, 1.0, .5,
                             3.0, -.05, 1.18, m_blue))
    fly_parts.append(add_box(world_col, "fan_fly_flag", 13.0, .12, 5.4,
                             -13.2, 0, -2.2, m_white))
    fly_parts.append(add_box(world_col, "fan_fly_cross_h", 13.0, .15, .78,
                             -13.2, -.08, .1, m_red))
    fly_parts.append(add_box(world_col, "fan_fly_cross_v", .78, .15, 5.4,
                             -13.2, -.09, -2.2, m_red))
    fly_parts.append(add_beam_between(world_col, "fan_tow_top",
                                      (-3.3, 0, .7), (-6.7, 0, 2.9), .08, m_dark))
    fly_parts.append(add_beam_between(world_col, "fan_tow_bottom",
                                      (-3.3, 0, .4), (-6.7, 0, -2.0), .08, m_dark))
    for obj in fly_parts:
        obj.parent = fly
    fly.location = (cx - 92, sy + 36, 26)
    fly.keyframe_insert("location", frame=1)
    fly.location = (cx + 92, sy + 36, 26)
    fly.keyframe_insert("location", frame=frame_end)
    for fc in obj_fcurves(fly):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

    # Dedicated low-angle portrait camera: memorial foreground, real town and
    # passing plane behind. A restrained side-dolly gives the set depth.
    cam_data = bpy.data.cameras.new("FootballCam")
    cam_data.lens = 42
    cam_data.dof.use_dof = False
    cam_obj = bpy.data.objects.new("FootballCamera", cam_data)
    aim = bpy.data.objects.new("FootballAim", None)
    aim.location = (cx, sy + 7.0, 7.2)
    world_col.objects.link(cam_obj)
    world_col.objects.link(aim)
    tr = cam_obj.constraints.new("TRACK_TO")
    tr.target = aim
    tr.track_axis = "TRACK_NEGATIVE_Z"
    tr.up_axis = "UP_Y"
    cam_obj.location = (cx - 4.0, sy - 34.0, 14.5)
    cam_obj.keyframe_insert("location", frame=1)
    cam_obj.location = (cx + 4.0, sy - 31.0, 13.0)
    cam_obj.keyframe_insert("location", frame=frame_end)
    for fc in obj_fcurves(cam_obj):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
    bpy.context.scene.camera = cam_obj

def build_stage(world_col, buildings, frame_end, m, tod="day", hero=None, cam=None):
    t = TODS.get(tod, TODS["day"])
    cx, cy, ext = city_center_and_extent(buildings)
    # 2026-07-10 cinematography pass (day 9, park district pushed the bounding
    # box way out -- ext jumped to ~258 -- and the old padding multipliers
    # were tuned for a much smaller town): both the default/hero shot and the
    # overhead shot were framing with way too much empty grass/sky padding
    # around the actual buildings, and the old 9-degree total orbit sweep
    # read as nearly static across an 11-12s clip -- neither felt "cinematic"
    # per Zach's feedback. Tightened the distance padding so buildings fill
    # more of the portrait frame, and widened the orbit sweep so the shot
    # visibly moves and reveals more of the town (including the park ring)
    # over the course of the clip instead of holding one static-feeling view.
    dist = ext * 1.05 + 45
    pol_deg, fstop = 55, 3.2
    orbit_deg = 46
    if cam == "overhead":
        # was a near-vertical 16-degree top-down angle -- read as flat/
        # orthographic with no sense of depth. 36 degrees still shows the
        # whole grid+park layout from above (the "sees everything" ask) but
        # keeps real perspective/parallax so it looks like a drone shot, not
        # a map.
        pol_deg, dist = 36, ext * 1.15 + 60
        orbit_deg = 55
    elif cam == "wholeoverhead":
        # Day-15 release camera: keep every developed edge inside frame while
        # all new homes rise. The shallower orbit avoids clipping a far suburb
        # during the move and still preserves enough parallax to read as a sky
        # shot rather than a flat map.
        pol_deg, dist, fstop = 28, ext * 1.32 + 100, 7.0
        orbit_deg = 18
    if hero:  # close-up on a special building / batch
        cx, cy, hdist = hero
        dist, pol_deg, fstop = hdist, 64, 2.0
        # 2026-07-10: was a flat 9 degrees regardless of subject size -- fine
        # for a tight 2-3 house close-up, but on a big batch (day 9's +64,
        # tracked across a wide area) it read as nearly static. Scale the
        # sweep with how far back the camera already sits, capped so a small
        # close-up still doesn't swing wildly off its subject.
        orbit_deg = min(38, 9 + hdist / 12)
        if cam == "newgrowthoverhead":
            # Keep the new neighborhood large in frame while clearly reading
            # as a top-down growth shot rather than another oblique reveal.
            pol_deg, fstop = 39, 4.5
            dist *= 1.05
            orbit_deg = min(30, orbit_deg)
        if cam == "school":
            # Higher, front-left campus reveal avoids neighboring rooftops and
            # lets the orbit uncover the playground behind the classroom wings.
            pol_deg, fstop, orbit_deg = 52, 4.0, 34

    # ground
    add_box(world_col, "ground", 4000, 4000, 0.1, cx, cy, -0.1, m["grass"])

    if cam == "downtownstreet":
        # Eye-level audit of the expanded pedestrian realm. This deliberately
        # looks along a full block face so curb height, clear walking width,
        # furniture placement, storefront setback and lighting cadence are
        # all visible in one approval frame.
        aim = bpy.data.objects.new("DowntownStreetAim", None)
        aim.location = (-3.0, 39.0, 3.05)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("DowntownStreetCamera")
        cam_data.lens = 31
        cam_data.dof.use_dof = False
        cam_data.clip_start = .25
        cam_data.clip_end = 1200.0
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        cam_obj.location = (-3.0, 1.5, 2.18)
        cam_obj.keyframe_insert("location", frame=1)
        cam_obj.location = (-3.0, 5.5, 2.18)
        cam_obj.keyframe_insert("location", frame=frame_end)
        bpy.context.scene.camera = cam_obj
    elif cam == "storefront":
        # Approval camera for real first-floor depth: directly faces a legacy
        # downtown home from across the street and keeps door, glazing,
        # displays, ceiling lights, sidewalk and upper façade in one frame.
        aim = bpy.data.objects.new("StorefrontAim", None)
        aim.location = (19.5, -12.5, 1.75)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("StorefrontCamera")
        cam_data.lens = 38
        cam_data.dof.use_dof = False
        cam_data.clip_start = .18
        cam_data.clip_end = 800.0
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        cam_obj.location = (19.5, -5.0, 2.08)
        bpy.context.scene.camera = cam_obj
    elif cam == "downtown":
        # Dedicated approval camera for the experimental city redesign: a
        # close oblique helicopter view that reads building massing, streets,
        # sidewalks, and the first terrain transition in one frame.
        aim = bpy.data.objects.new("DowntownAim", None)
        aim.location = (-3.0, -3.0, 13.0)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("DowntownCamera")
        cam_data.lens = 42
        cam_data.dof.use_dof = False
        cam_data.clip_start = 1.0
        cam_data.clip_end = 2500.0
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        cam_obj.location = (108.0, -128.0, 86.0)
        cam_obj.keyframe_insert("location", frame=1)
        cam_obj.location = (96.0, -116.0, 78.0)
        cam_obj.keyframe_insert("location", frame=frame_end)
        for fc in obj_fcurves(cam_obj):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "housefront":
        # Landing-page loop: stand on the opposite sidewalk and look across
        # the road at a representative house from the newest developed street.
        # Two temporary cars pass between the lens and house; none of this is
        # saved to world_state.
        latest_day = max((b.get("day", 0) for b in buildings
                          if b.get("type") == "house" and b.get("street")), default=0)
        latest_houses = [b for b in buildings
                         if b.get("type") == "house" and b.get("street")
                         and b.get("day", 0) == latest_day]
        street_groups = {}
        for b in latest_houses:
            street_groups.setdefault((b.get("district"), b.get("street")), []).append(b)
        if not street_groups:
            raise RuntimeError("housefront camera needs planned houses with street metadata")
        street_houses = max(street_groups.values(), key=len)
        street_houses.sort(key=lambda b: b.get("plan_id", 0))
        subject = street_houses[len(street_houses) // 2]
        hx, hy = build_pos(subject)
        rot = subject.get("rot", 0.0)
        house_z = hillside_pad_levels(hx, hy, rot)[1]
        # House assets face local -Y; planned-house rot points that front at
        # the road. Local +X therefore supplies the road tangent.
        front = Vector((math.sin(rot), -math.cos(rot), 0))
        tangent = Vector((math.cos(rot), math.sin(rot), 0))

        aim = bpy.data.objects.new("HouseFrontAim", None)
        # Keep the full facade and a strip of road in the portrait frame. A
        # lower aim avoids wasting the upper half of the reel on empty sky.
        aim.location = (hx, hy, house_z + 2.2)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("HouseFrontCam")
        cam_data.lens = 27
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        across_xy = Vector((hx, hy, 0)) + front * 13.0
        across = Vector((across_xy.x, across_xy.y,
                         terrain_height(across_xy.x, across_xy.y) + 1.82))
        cam_obj.location = across - tangent * 0.6
        cam_obj.keyframe_insert("location", frame=1)
        cam_obj.location = across + tangent * 0.6
        cam_obj.keyframe_insert("location", frame=frame_end // 2)
        cam_obj.location = across - tangent * 0.6
        cam_obj.keyframe_insert("location", frame=frame_end)
        for fc in obj_fcurves(cam_obj):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj

        road_xy = Vector((hx, hy, 0)) + front * 8.5
        road_center = Vector((road_xy.x, road_xy.y,
                              terrain_height(road_xy.x, road_xy.y) + .19))
        for i, (direction, lane_offset) in enumerate(((1, -1.25), (-1, -0.45))):
            car_data = {"type": "car", "gx": 0, "gy": 0,
                        "seed": 9100 + subject.get("seed", 0) + i}
            car = place_instance(world_col, car_data, "housefront_traffic")
            # These cars pass close to a portrait lens. Keep their apparent
            # size comfortable and stagger the crossings so the house never
            # vanishes behind two vehicles at once.
            car.scale = (0.58, 0.58, 0.58)
            lane_center = road_center + front * lane_offset
            start = lane_center - tangent * (32.0 * direction)
            finish = lane_center + tangent * (32.0 * direction)
            start.z = terrain_height(start.x, start.y) + .20
            finish.z = terrain_height(finish.x, finish.y) + .20
            car.location = start
            car.rotation_euler = (0, 0, math.atan2(tangent.y, tangent.x) +
                                  (0 if direction > 0 else math.pi))
            start_frame = 1 if i == 0 else frame_end // 3
            end_frame = frame_end * 2 // 3 if i == 0 else frame_end
            car.keyframe_insert("location", frame=start_frame)
            car.location = finish
            car.keyframe_insert("location", frame=end_frame)
            for fc in obj_fcurves(car):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    elif cam == "storybookstreet":
        # Standalone completed-state tour for the Day 15 feature district.
        # The camera stays on the authored access/loop centerline, climbs with
        # the road, then follows the lower oval past the ten preserved homes.
        # Pair with --focus-type finished on replay to keep every house fully
        # built for the entire clip.
        if not any(b.get("feature_id") == STORYBOOK_FEATURE_ID for b in buildings):
            raise RuntimeError("storybookstreet camera needs Kaleidoscope Crest homes")
        route = [(236.0, 72.0, .05), (240.0, 71.0, .28),
                 (246.0, 69.0, 1.55), (250.0, 68.0, 2.62),
                 (264.0, 65.0, 2.74), (274.0, 60.0, 2.98)]
        cx_story, cy_story = STORYBOOK_LAYOUT_CENTER
        for i in range(11):
            angle = math.pi + math.pi * .92 * i / 10.0
            route.append((cx_story + 31.0 * math.cos(angle),
                          cy_story + 22.0 * math.sin(angle), 2.98))

        distances = [0.0]
        for a, b in zip(route, route[1:]):
            distances.append(distances[-1] + math.sqrt(
                (b[0]-a[0])**2 + (b[1]-a[1])**2 + (b[2]-a[2])**2))
        total_distance = max(distances[-1], .001)

        cam_data = bpy.data.cameras.new("StorybookStreetCam")
        cam_data.lens = 25
        cam_data.dof.use_dof = False
        cam_data.clip_start = .15
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        aim = bpy.data.objects.new("StorybookStreetAim", None)
        world_col.objects.link(cam_obj)
        world_col.objects.link(aim)
        bpy.context.scene.camera = cam_obj
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"

        for i, point in enumerate(route):
            frame = 1 + int(round((frame_end - 1) * distances[i] / total_distance))
            if i < len(route) - 1:
                target = route[min(len(route) - 1, i + 2)]
            else:
                previous = route[-2]
                target = (point[0] + (point[0]-previous[0]),
                          point[1] + (point[1]-previous[1]), point[2])
            cam_obj.location = (point[0], point[1], point[2] + 1.68)
            aim.location = (target[0], target[1], target[2] + 2.20)
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    elif cam == "newstreet":
        # Finished street-level showcase of the newest ordinary homes. Pick
        # the latest day's busiest planned street, then animate both camera
        # and look target along its revealed road centerline. This follows
        # winding roads naturally and cannot drift back to the founder grid.
        latest_day = max((b.get("day", 0) for b in buildings
                          if b.get("type") == "house" and b.get("street")), default=0)
        latest_houses = [b for b in buildings
                         if b.get("type") == "house" and b.get("street")
                         and b.get("day", 0) == latest_day]
        street_groups = {}
        for b in latest_houses:
            key = (b.get("district"), b.get("street"))
            street_groups.setdefault(key, []).append(b)
        if not street_groups:
            raise RuntimeError("newstreet camera needs planned houses with street metadata")
        (district_name, street_name), street_houses = max(
            street_groups.items(), key=lambda item: (len(item[1]), item[0][1] or ""))
        built_plan_id = max((b.get("plan_id", 0) for b in buildings), default=0)
        road_segments = [seg for seg in SUBURBAN_PLAN.get("roads", [])
                         if seg.get("district") == district_name
                         and seg.get("street") == street_name
                         and seg.get("reveal_at", 10**9) <= built_plan_id]
        if not road_segments:
            raise RuntimeError("newstreet camera found no revealed road for %s" % street_name)
        source_road_points = [road_segments[0]["a"]] + [seg["b"] for seg in road_segments]
        road_points = [transform_point(x, y, district=district_name)
                       for x, y in source_road_points]
        start_i = 0
        # Stop before the final turnaround. Keeping five road samples ahead
        # gives the portrait camera enough depth to see facades on both sides
        # instead of ending on a close-up of empty asphalt.
        end_i = max(start_i + 1, len(road_points) - 10)
        # Key every road sample. Sparse chords cut across the inside of tight
        # curves and can pass through a house even though both endpoints sit
        # on the road centerline.
        key_count = end_i - start_i + 1

        cam_data = bpy.data.cameras.new("Cam")
        # A moderately wide street lens keeps both rows of houses visible
        # without catching the dark undersides of roofs on the inside of
        # Willow Rise's tighter bends.
        cam_data.lens = 28
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        aim = bpy.data.objects.new("NewStreetAim", None)
        world_col.objects.link(cam_obj)
        world_col.objects.link(aim)
        bpy.context.scene.camera = cam_obj
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"

        for k in range(key_count):
            frac = k / float(key_count - 1)
            idx = int(round(start_i + (end_i - start_i) * frac))
            # Look just far enough ahead to follow the local tangent. A long
            # look-ahead cuts across bends and points the wide frame directly
            # under the nearest inside-corner roof.
            aim_idx = min(len(road_points) - 1, idx + 3)
            frame = 1 + int(round((frame_end - 1) * frac))
            px, py = road_points[idx]
            ax, ay = road_points[aim_idx]
            cam_obj.location = (px, py, terrain_height(px, py) + 1.90)
            aim.location = (ax, ay, terrain_height(ax, ay) + 1.72)
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
    elif cam == "street":
        # eye-level flythrough down the town's oldest street (the by=0 road,
        # which runs past whichever buildings sit at gy 0-2 -- the founder
        # blocks from day 1) instead of orbiting a fixed point overhead.
        #
        # 2026-07-10: was min_bx*PITCH-ROAD to (max_bx+1)*PITCH -- the FULL
        # grid width. That was fine when the town was small, but now (day 9,
        # grid spans x -78..72) covering the whole width in the fixed 12s
        # floor works out to ~12.5 m/s -- more like a car than "walking into
        # town," and most of that distance is plain grid houses, not the
        # founders' custom landmarks Zach actually wants visible. Fixed to a
        # town-size-independent window centered on the founder cluster
        # (measured x -21..25): a little approach room before it, straight
        # through it, a little continuation after -- at a brisk-but-human
        # ~7.5 m/s (a fast walk/light jog, not a crawl and not a drive-by).
        # Clipped to whatever's actually built so this can't run off into
        # blank grass on a tiny town either.
        min_bx, max_bx, min_by, max_by = block_extent(buildings)
        full_x0, full_x1 = min_bx * PITCH - ROAD, (max_bx + 1) * PITCH
        x0 = max(full_x0, -40.0)
        x1 = min(full_x1, 50.0)
        street_y = -ROAD / 2
        street_z = 1.75  # roughly eye/walking height

        cam_data = bpy.data.cameras.new("Cam")
        cam_data.lens = 32  # wider, more human POV than the establishing shots
        cam_data.dof.use_dof = False  # a far-ahead aim target makes DOF unreliable here
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        cam_obj.location = (x0, street_y, street_z)
        world_col.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj

        # aim far down the road (not at a nearby point) so heading stays
        # essentially constant while the camera translates -- like actually
        # walking/driving straight down the street, not swinging to track it
        aim = bpy.data.objects.new("StreetAim", None)
        aim.location = (x1 + 2000, street_y, street_z)
        world_col.objects.link(aim)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"

        cam_obj.location = (x0, street_y, street_z)
        cam_obj.keyframe_insert("location", frame=1)
        cam_obj.location = (x1, street_y, street_z)
        cam_obj.keyframe_insert("location", frame=frame_end)
        for fc in obj_fcurves(cam_obj):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    elif cam == "park":
        # in-park showcase: slow low orbit around the park's gazebo, looking
        # across the lawn at the ring houses sweeping by behind it
        districts = [b for b in buildings if b["type"] == "parkdistrict"]
        pcx, pcy = (districts[-1]["px"], districts[-1]["py"]) if districts else (cx, cy)
        rig = bpy.data.objects.new("CamRig", None)
        rig.location = (pcx, pcy, 2.0)
        world_col.objects.link(rig)
        cam_data = bpy.data.cameras.new("Cam")
        cam_data.lens = 30
        cam_data.dof.use_dof = True
        cam_data.dof.focus_object = rig
        cam_data.dof.aperture_fstop = 5.6
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        cam_obj.parent = rig
        # 2026-07-09 night fix (Cade's PC), take 2: the first cut orbited at
        # r~29.5 THROUGH the inner ring houses; take 1's fix (r=20, h=8.5) was
        # still low enough that park-rim trees (r<=13.8, tops ~7) loomed across
        # the lower half of frame as the camera swept past. Final: r~17.7 at
        # h~11.4 -- comfortably above every tree, looking down at the gazebo
        # with the ring houses behind it, nothing ever crossing the lens.
        pol = math.radians(62)
        pdist = 20.0
        az = math.radians(38)
        cam_obj.location = (pdist * math.sin(pol) * math.cos(az),
                            -pdist * math.sin(pol) * math.sin(az),
                            pdist * math.cos(pol))
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = rig
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        world_col.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj
        rig.rotation_euler = (0, 0, 0)
        rig.keyframe_insert("rotation_euler", frame=1)
        rig.rotation_euler = (0, 0, math.radians(75))
        rig.keyframe_insert("rotation_euler", frame=frame_end)
        for fc in obj_fcurves(rig):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
    else:
        # camera rig: empty at center, camera orbits it
        rig = bpy.data.objects.new("CamRig", None)
        rig.location = (cx, cy, 0)
        world_col.objects.link(rig)

        cam_data = bpy.data.cameras.new("Cam")
        cam_data.lens = 45
        # Thin roads and ponds are only centimetres above the ground. At an
        # aerial distance of 500m+, Blender's default 0.1m near plane spends
        # almost all depth precision beside the lens, making those surfaces
        # alternate between full polygons, wedges, and invisibility as the
        # camera moves. Raising the near plane for sky shots restores stable
        # depth separation without clipping anything near the town.
        if cam in ("overhead", "wholeoverhead", "newgrowthoverhead"):
            cam_data.clip_start = 10.0
            cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = True
        cam_data.dof.focus_object = rig
        cam_data.dof.aperture_fstop = fstop
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        cam_obj.parent = rig
        az = math.radians(135 if cam == "school" else 38)
        pol = math.radians(pol_deg)
        cam_obj.location = (dist * math.sin(pol) * math.cos(az),
                        -dist * math.sin(pol) * math.sin(az),
                        dist * math.cos(pol))
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = rig
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        world_col.objects.link(cam_obj)
        bpy.context.scene.camera = cam_obj

        # orbit across the whole shot -- sweep amount set above per shot type
        # (orbit_deg): wide for the establishing/overhead shots so they
        # visibly reveal the town instead of holding a near-static frame,
        # narrow for hero close-ups where a big sweep would swing off the
        # subject.
        rig.rotation_euler = (0, 0, 0)
        rig.keyframe_insert("rotation_euler", frame=1)
        rig.rotation_euler = (0, 0, math.radians(orbit_deg))
        rig.keyframe_insert("rotation_euler", frame=frame_end)
        for fc in obj_fcurves(rig):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    # sun -- 2026-07-09 lighting upgrade: softer shadow edges, plus a cool
    # shadow-free "skylight" fill from the opposite side so shaded facades
    # read as sky-lit instead of near-black. Same time-of-day moods as before.
    sun_data = bpy.data.lights.new("Sun", type="SUN")
    # 2026-07-09 night (Cade's PC): the "0.95x sun + 6.5deg + 0.15x fill" combo
    # still washed the town out (fainter shadows + flatter color than day 7).
    # Full sun strength + near-original shadow sharpness restore the contrast;
    # the sky fill idea stays but much weaker (a subtle shaded-side lift only).
    sun_data.energy = t["sun_e"]
    sun_data.angle = math.radians(4.5)
    sun_data.color = t["sun_c"]
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = tuple(math.radians(a) for a in t["sun_rot"])
    world_col.objects.link(sun)
    fill_data = bpy.data.lights.new("Fill", type="SUN")
    fill_data.energy = t["sun_e"] * 0.07
    fill_data.angle = math.radians(30)
    fill_data.color = tuple(min(1.0, c * 0.5 + 0.5) for c in t["sky"])
    try:
        fill_data.use_shadow = False
    except Exception:
        pass
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.rotation_euler = (math.radians(55), 0, math.radians(t["sun_rot"][2] + 170))
    world_col.objects.link(fill)

    # sky
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (*t["sky"], 1.0)
        bg.inputs[1].default_value = t["sky_s"]  # 2026-07-09 evening: brightness boost removed

def setup_render(state, frame_end, tag=None):
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):  # 4.2+ / older & 5.x
        try:
            sc.render.engine = eng
            break
        except Exception:
            pass
    sc.render.resolution_x = RES_X
    sc.render.resolution_y = RES_Y
    sc.render.fps = FPS
    sc.frame_start = 1
    sc.frame_end = frame_end
    for attr, val in [("use_gtao", True), ("use_bloom", False),
                      ("use_ssr", False), ("use_raytracing", False),
                      # 2026-07-09 lighting upgrade (each is best-effort
                      # across Blender versions thanks to the try/except):
                      ("shadow_cube_size", "2048"), ("shadow_cascade_size", "2048"),
                      ("use_shadow_high_bitdepth", True), ("use_soft_shadows", True),
                      ("gtao_distance", 8.0), ("taa_render_samples", 96)]:
        try:
            setattr(sc.eevee, attr, val)
        except Exception:
            pass
    for vt in ("AgX", "Filmic", "Standard"):
        try:
            sc.view_settings.view_transform = vt
            break
        except Exception:
            pass
    try:
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    base = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~")
    name = "day_%03d_" % state["day"] + ((tag + "_") if tag else "")
    sc.render.filepath = os.path.join(base, "renders", name)
    try:  # Blender 5.x: video formats live behind media_type
        sc.render.image_settings.media_type = "VIDEO"
    except Exception:
        pass
    try:
        sc.render.image_settings.file_format = "FFMPEG"
        sc.render.ffmpeg.format = "MPEG4"
        sc.render.ffmpeg.codec = "H264"
        sc.render.ffmpeg.constant_rate_factor = "HIGH"
    except Exception:
        # no video output available -> PNG frame sequence instead
        sc.render.image_settings.file_format = "PNG"

# ═══════════════════════════════════ CLEANUP ════════════════════════════════════

def clear_world():
    # Remove EVERY collection named "WORLD" or "WORLD.NNN" — a stray duplicate
    # (e.g. left behind by an interrupted run, or a past testing session) would
    # otherwise sit outside bpy.data.collections.get("WORLD")'s reach forever,
    # quietly accumulating objects across every future rebuild.
    for col in [c for c in list(bpy.data.collections) if c.name == "WORLD" or c.name.startswith("WORLD.")]:
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(col)
    # belt-and-braces: purge any zero-user objects left over from previous
    # runs (covers cases where do_unlink=True above doesn't fully clear a
    # reference, e.g. objects still held by an animation driver/action)
    for obj in list(bpy.data.objects):
        if obj.users == 0:
            bpy.data.objects.remove(obj)
    for coll in (bpy.data.meshes, bpy.data.curves, bpy.data.actions,
                 bpy.data.lights, bpy.data.cameras):
        for blk in list(coll):
            if blk.users == 0:
                coll.remove(blk)
    try:
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    except Exception:
        pass
    col = bpy.data.collections.new("WORLD")
    bpy.context.scene.collection.children.link(col)
    return col

# ═════════════════════════════════════ MAIN ═════════════════════════════════════

def render_still(state, frame_end):
    sc = bpy.context.scene
    sc.frame_set(max(sc.frame_start, frame_end - 10))
    base = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.expanduser("~")
    try:
        sc.render.image_settings.media_type = "IMAGE"
    except Exception:
        pass
    sc.render.image_settings.file_format = "PNG"
    path = os.path.join(base, "renders", "day_%03d_preview.png" % state["day"])
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path

def main(cfg=None):
    state = load_state()

    # effective inputs: cfg (panel) > CLI > CONFIG constants
    if cfg is None:
        cfg = dict(CLI) if CLI else {"gained": NEW_HOUSES, "apartments": NEW_APARTMENTS,
                                     "parks": NEW_PARKS, "trees": NEW_TREES,
                                     "followers": FOLLOWERS_GAINED,
                                     "replay": REPLAY_LAST_DAY, "render": AUTO_RENDER,
                                     "time": None if TIME_OF_DAY == "auto" else TIME_OF_DAY,
                                     "season": None if SEASON == "auto" else SEASON}
    replay = cfg.get("replay", False)
    n_apart = cfg.get("apartments", 0)
    n_parks = cfg.get("parks", 0)
    n_trees = cfg.get("trees", 0)
    n_mush = cfg.get("mushrooms", 0)
    if "pop" in cfg:
        delta = cfg["pop"] - state["pop"]
        gained, lost = max(delta, 0), max(-delta, 0)
    else:
        gained, lost = cfg.get("gained", 0), cfg.get("lost", 0)
    followers = cfg.get("followers")
    if followers is None:
        followers = gained - lost

    occupied = set()
    for b in state["buildings"]:
        occupied.update(footprint(b))

    # 2026-07-10: block-fill lot order is the default for every new growth
    # day now (fills sparse blocks solid instead of scattering across many
    # at once -- see sorted_lots_filling()'s docstring). Pass --scatter to
    # opt back into the old pure-radial scatter order (sorted_lots()) if a
    # future day ever wants that messier look on purpose.
    fill_mode = "scatter" if cfg.get("scatter") else "block"
    planned_before = len([b for b in state["buildings"] if b.get("plan_id")])

    new_batch, removed, unlocked = [], [], []
    if replay:
        new_batch = [b for b in state["buildings"] if b.get("day") == state["day"]]
    else:
        if lost > 0:
            houses = [b for b in state["buildings"] if b["type"] == "house"]
            if len(houses) < lost:
                raise RuntimeError("Cannot remove %d houses; only %d exist"
                                   % (lost, len(houses)))
            removed = houses[-lost:]  # newest residents leave first
        specials = []
        for spec in cfg.get("special", []):
            if "@" in spec:  # e.g. toilethouse@1,1 — place at an exact lot
                t, _, coord = spec.partition("@")
                tgx, tgy = (int(v) for v in coord.split(","))
                specials.append((t, 1, (tgx, tgy)))
            else:
                specials.append((spec, 1, None))

        pond_extras = []
        house_gained = gained
        if cfg.get("pond") and gained > 0:
            # cluster the pond + up to 3 new houses around it in one free 2x2
            # patch, so the growth video reads as "these houses + this pond
            # arrived together" rather than scattering them across town
            (px, py), = find_free_lots(1, 2, occupied, fill_mode=fill_mode)
            cluster_cells = [(px, py), (px + 1, py), (px, py + 1), (px + 1, py + 1)]
            pond_extras.append(("pond", 1, cluster_cells[0]))
            house_cells = cluster_cells[1:1 + min(gained, 3)]
            for cell in house_cells:
                pond_extras.append(("house", 1, cell))
            house_gained = gained - len(house_cells)

        parkring_n = 0
        if cfg.get("parkring") and gained > 0:
            parkring_n, house_gained = gained, 0

        storybook_requested = max(0, cfg.get("storybook_houses", 0))
        existing_storybook = len([b for b in state["buildings"]
                                  if b.get("feature_id") == STORYBOOK_FEATURE_ID])
        storybook_n = min(storybook_requested,
                          max(0, len(STORYBOOK_SLOTS) - existing_storybook))
        if storybook_requested > gained:
            raise RuntimeError("--storybook-houses cannot exceed today's follower gain")
        if storybook_requested != storybook_n:
            raise RuntimeError("Wanderlight Loop has only %d unbuilt feature lots"
                               % (len(STORYBOOK_SLOTS) - existing_storybook))
        house_gained -= storybook_n

        additions = specials + pond_extras + [("house", house_gained, None),
                                ("mushroomhouse", n_mush, None),
                                ("apartment", n_apart, None), ("park", n_parks, None),
                                ("tree", n_trees, None)]
        if gained or lost or n_apart or n_parks or n_trees or n_mush or specials:
            state["day"] += 1
            state["pop"] = max(0, state["pop"] + followers)
            # milestone buildings appear the day a threshold is crossed
            done = state.setdefault("milestones", [])
            for thr, btype in MILESTONES:
                if state["pop"] >= thr and thr not in done:
                    done.append(thr)
                    # Cade's approved 135..500 reserve is ordinary houses
                    # only. Reaching 500 completes that neighborhood plan;
                    # it must not silently insert the legacy plaza.
                    if thr == 500 and planned_before < SUBURBAN_CAPACITY and house_gained > 0:
                        unlocked.append("500-house suburban reserve complete")
                        continue
                    additions.append((btype, 1, None))
                    unlocked.append("%s (pop %d)" % (btype, thr))
        if parkring_n:
            # ── circular park district: park + ring roads at a fixed center
            # east of town, with today's houses arranged on rings around it,
            # every front door facing the park ──
            xs, ys = [], []
            for b in state["buildings"]:
                x, y = build_pos(b)
                xs.append(x); ys.append(y)
            R_D = 57.0
            dcx = (max(xs) if xs else 0) + LOT + R_D + 26
            dcy = ((min(ys) + max(ys)) / 2) if ys else 15.0

            def _near_lot(wx, wy):
                bx = math.floor(wx / PITCH)
                ix = min(max(int((wx - bx * PITCH) // LOT), 0), BLOCK_N - 1)
                by = math.floor(wy / PITCH)
                iy = min(max(int((wy - by * PITCH) // LOT), 0), BLOCK_N - 1)
                return int(bx * BLOCK_N + ix), int(by * BLOCK_N + iy)

            gxc, gyc = _near_lot(dcx, dcy)
            park_b = {"type": "parkdistrict", "gx": gxc, "gy": gyc,
                      "px": round(dcx, 2), "py": round(dcy, 2), "r": R_D,
                      "seed": state["seed_counter"], "day": state["day"]}
            state["seed_counter"] += 1
            state["buildings"].append(park_b)
            occupied.update(footprint(park_b))
            new_batch.append(park_b)
            n1 = min(parkring_n, 17)
            for rr, cnt, gap in ((30.5, n1, 0.30), (50.5, parkring_n - n1, 0.20)):
                if cnt <= 0:
                    continue
                a0, span = math.pi + gap, math.tau - 2 * gap
                for k in range(cnt):
                    a = a0 + span * (k + 0.5) / cnt
                    hx, hy = dcx + rr * math.cos(a), dcy + rr * math.sin(a)
                    hgx, hgy = _near_lot(hx, hy)
                    hb = {"type": "ringhouse", "gx": hgx, "gy": hgy,
                          "px": round(hx, 2), "py": round(hy, 2),
                          "rot": round(a - math.pi / 2, 4),
                          "seed": state["seed_counter"], "day": state["day"]}
                    state["seed_counter"] += 1
                    state["buildings"].append(hb)
                    new_batch.append(hb)
        if storybook_n:
            for slot in STORYBOOK_SLOTS[existing_storybook:existing_storybook + storybook_n]:
                hb = {"type": "storybookhouse", "gx": 0, "gy": 0,
                      "px": slot["x"], "py": slot["y"], "pz": slot["z"],
                      "rot": slot["rot"], "feature_index": slot["index"],
                      "feature_id": STORYBOOK_FEATURE_ID,
                      "district": STORYBOOK_DISTRICT, "street": STORYBOOK_STREET,
                      "seed": state["seed_counter"], "day": state["day"]}
                state["seed_counter"] += 1
                state["buildings"].append(hb)
                new_batch.append(hb)
        for btype, n, target in additions:
            size = SIZE.get(btype, 1)
            if n <= 0:
                continue
            if target is not None:
                cells = [(target[0] + dx, target[1] + dy)
                         for dx in range(size) for dy in range(size)]
                if any(c in occupied for c in cells):
                    raise RuntimeError("Lot %s is already taken" % (target,))
                lots = [target]
            elif btype == "house":
                # Consume exact addresses from the hidden 366-house suburban
                # reserve before falling back to the legacy grid.  The plan
                # lives outside world_state and creates no future objects.
                already = len([b for b in state["buildings"] if b.get("plan_id")])
                take = min(n, max(0, SUBURBAN_CAPACITY - already))
                if take and SUBURBAN_PLAN:
                    for slot in SUBURBAN_PLAN["houses"][already:already + take]:
                        b = {"type": "house", "gx": 0, "gy": 0,
                             "px": slot["x"], "py": slot["y"], "rot": slot["rot"],
                             "plan_id": slot["plan_id"], "district": slot["district"],
                             "street": slot["street"], "seed": state["seed_counter"],
                             "day": state["day"]}
                        state["seed_counter"] += 1
                        state["buildings"].append(b)
                        new_batch.append(b)
                    n -= take
                    if n <= 0:
                        continue
                # regular houses stay out of blocks that hold custom homes
                custom_blocks = set()
                for b in state["buildings"]:
                    if b["type"].endswith("house") and b["type"] != "house":
                        for cgx, cgy in footprint(b):
                            custom_blocks.add((cgx // BLOCK_N, cgy // BLOCK_N))
                lots = find_free_lots(n, size, occupied, custom_blocks, fill_mode=fill_mode)
            else:
                lots = find_free_lots(n, size, occupied, fill_mode=fill_mode)
            for gx, gy in lots:
                b = {"type": btype, "gx": gx, "gy": gy,
                     "seed": state["seed_counter"], "day": state["day"]}
                state["seed_counter"] += 1
                state["buildings"].append(b)
                occupied.update(footprint(b))
                new_batch.append(b)

    # rebuild world (removed houses still placed so they can sink on camera)
    world_col = clear_world()
    m = std_mats()
    focus_type = cfg.get("focus_type")
    animation_batch = ([b for b in new_batch if b["type"] == focus_type]
                       if focus_type else new_batch)
    new_ids = {id(b) for b in animation_batch}
    rem_ids = {id(b) for b in removed}
    rise, sink = [], []
    for b in state["buildings"]:
        e = place_instance(world_col, b, "%s_d%d" % (b["type"], b.get("day", 0)))
        # Export-only identity.  The web chunker partitions these canonical
        # building roots but leaves roads, terrain, nature, traffic, and public
        # feature dressing in the always-loaded base asset.
        e["nb_world_seed"] = int(b["seed"])
        e["nb_world_type"] = str(b["type"])
        e["nb_web_chunk"] = web_chunk_id(b)
        if b.get("district"):
            e["nb_world_district"] = str(b["district"])
        if id(b) in new_ids:
            rise.append(e)
        elif id(b) in rem_ids:
            sink.append(e)
    keep = [b for b in state["buildings"] if id(b) not in rem_ids]
    build_roads(world_col, keep or state["buildings"], m)
    build_district_roads(world_col, keep or state["buildings"], m)
    # The redesign supplies one continuous walkable terrain mesh. The older
    # decorative mound pass is intentionally omitted to avoid intersecting
    # houses and roads with scenery that has no shared elevation model.
    build_suburban_roads(world_col, keep or state["buildings"], m)
    build_hillside_foundations(world_col, keep or state["buildings"])
    build_storybook_street(world_col, keep or state["buildings"])
    # Isolated, state-free public-realm layer. The module owns no houses,
    # roads, claims, addresses, or browser loading behavior, making this hook
    # easy to adapt after the district-streaming exporter lands.
    build_downtown_visuals(
        world_col, keep or state["buildings"], occupied,
        {"block_extent": block_extent(keep or state["buildings"]),
         "block_n": BLOCK_N, "lot": LOT, "road": ROAD, "pitch": PITCH},
        render_mode=cfg.get("cam"))
    scatter_nature(world_col, occupied, keep or state["buildings"])

    # animation timing: sinks first, then rises
    n_anim = len(rise) + len(sink)
    prehold = int(1.5 * FPS)
    stagger = max(2, min(6, 240 // max(n_anim, 1)))
    posthold = int(2.5 * FPS)
    frame_end = prehold + max(n_anim - 1, 0) * stagger + 22 + posthold
    if cfg.get("cam") in ("street", "newstreet", "storybookstreet", "housefront", "park", "overhead", "wholeoverhead", "downtown", "downtownstreet"):
        frame_end = max(frame_end, FPS * 12)  # give slow showcase cams time to breathe
    elif cfg.get("cam") == "football":
        frame_end = max(frame_end, FPS * 10)
    elif cfg.get("cam") == "school":
        frame_end = max(frame_end, FPS * 8)
    f = prehold
    for e in sink:
        animate_sink(e, f)
        f += stagger
    for e in rise:
        animate_rise(e, f)
        f += stagger

    # mood + life
    tod = cfg.get("time") or auto_time(state["day"])
    season = cfg.get("season") or auto_season()
    animate_traffic(world_col, keep or state["buildings"], frame_end, state["day"])
    animate_ducks(world_col, keep or state["buildings"], frame_end)
    animate_ring_traffic(world_col, keep or state["buildings"], frame_end)
    hero = None
    hero_batch = animation_batch if focus_type else new_batch
    if cfg.get("cam") in ("newgrowth", "newgrowthoverhead") and hero_batch:
        # A daily total can finish one cul-de-sac and start a distant district.
        # Frame the largest new district so the rise shot stays close enough to
        # read as houses appearing instead of shrinking the entire town to fit.
        district_groups = {}
        for b in hero_batch:
            district_groups.setdefault(b.get("district") or "", []).append(b)
        hero_batch = max(district_groups.values(), key=len)
    if (cfg.get("hero") or cfg.get("cam") in ("newgrowth", "newgrowthoverhead")) and hero_batch:
        pts = []
        for b in hero_batch:
            x, y = build_pos(b)
            s = SIZE.get(b["type"], 1)
            r = b.get("r", 0)
            if r:
                pts += [(x - r, y - r), (x + r, y + r)]
            elif s > 1:
                center_x = x + (s - 1) * LOT / 2
                center_y = y + (s - 1) * LOT / 2
                half = s * LOT / 2
                pts += [(center_x - half, center_y - half),
                        (center_x + half, center_y + half)]
            else:
                pts.append((x + (s - 1) * LOT / 2, y + (s - 1) * LOT / 2))
        hx = sum(p[0] for p in pts) / len(pts)
        hy = sum(p[1] for p in pts) / len(pts)
        span = max(max(p[0] for p in pts) - min(p[0] for p in pts),
                   max(p[1] for p in pts) - min(p[1] for p in pts))
        # 2026-07-10: was span*2.1+44 -- fine for a small batch (a handful of
        # houses) but on a big growth day (day 9's +64, span~128) that padding
        # put the camera almost as far back as the whole-town shot, same
        # "mostly empty grass/sky" problem as the other two camera modes.
        # Tightened the same way.
        hero = (hx, hy, max(40.0, span * 1.3 + 42))
    build_stage(world_col, state["buildings"], frame_end, m, tod, hero, cfg.get("cam"))
    if cfg.get("cam") == "football":
        build_football_vignette(world_col, state["buildings"], frame_end)
    if cfg.get("celebrate"):
        # fireworks over today's new batch if there is one (e.g. the day-8
        # park district), otherwise over the founders' custom homes
        today = [b for b in state["buildings"] if b.get("day") == state["day"]]
        customs = new_batch or today or [b for b in state["buildings"]
                                if b["type"].endswith("house") and b["type"] != "house"]
        if customs:
            pts = [build_pos(b) for b in customs]
            build_fireworks(world_col,
                            sum(p[0] for p in pts) / len(pts),
                            sum(p[1] for p in pts) / len(pts), frame_end)
    apply_mood(tod, season)
    setup_render(state, frame_end, cfg.get("tag"))

    # removed houses leave the saved city permanently
    if removed:
        state["buildings"] = keep
    if not replay:
        save_state(state)

    summary = {"day": state["day"], "population": state["pop"],
               "buildings": len(state["buildings"]),
               "added": len(new_batch), "removed": len(removed),
               "time": tod, "season": season, "milestones": unlocked,
               "state_file": state_path()}
    print("=" * 50)
    print("DAY %d | population %d | buildings %d | +%d / -%d today"
          % (state["day"], state["pop"], len(state["buildings"]),
             len(new_batch), len(removed)))
    print("Render: Ctrl+F12 (output -> renders/day_%03d_*.mp4)" % state["day"])
    print("=" * 50)
    print("RESULT " + json.dumps(summary))

    if cfg.get("render"):
        bpy.ops.render.render(animation=True)
        print("VIDEO " + bpy.context.scene.render.filepath)
    if cfg.get("still"):
        print("STILL " + render_still(state, frame_end))
    return summary

# ═══════════════════ IN-BLENDER CONTROL PANEL (GUI only) ════════════════════════
# Press N in the 3D viewport -> "City" tab. Type +5 / -3 / =50, click Grow,
# watch it build in the camera view, then click Render Video.

def _parse_change(s):
    s = s.strip().replace(" ", "")
    if not s:
        raise ValueError("Type a change first, e.g. +5")
    if s.lower() == "replay":
        return {"replay": True}
    if s[0] == "+":
        return {"gained": int(s[1:])}
    if s[0] == "-":
        return {"lost": int(s[1:])}
    if s[0] == "=":
        return {"pop": int(s[1:])}
    return {"gained": int(s)}  # bare number = houses gained

def _copy_video_to_desktop(scene, *args):
    import glob
    import shutil
    if not bpy.data.filepath:
        return
    vids = glob.glob(os.path.join(os.path.dirname(bpy.data.filepath), "renders", "*.mp4"))
    if vids:
        newest = max(vids, key=os.path.getmtime)
        try:
            shutil.copy(newest, os.path.expanduser("~/Desktop"))
            print("Copied to Desktop:", os.path.basename(newest))
        except Exception:
            pass

def _register_ui():
    S = bpy.types.Scene
    S.nb_change = bpy.props.StringProperty(
        name="Change", default="+5",
        description="+5 add houses | -3 remove | =50 set total | replay")
    S.nb_time = bpy.props.EnumProperty(
        name="Time", default="auto",
        items=[(k, k.title(), "") for k in ("auto", "day", "sunset", "night")])
    S.nb_season = bpy.props.EnumProperty(
        name="Season", default="auto",
        items=[(k, k.title(), "") for k in ("auto", "spring", "summer", "fall", "winter")])

    class NB_OT_grow(bpy.types.Operator):
        bl_idname = "nb.grow"
        bl_label = "Grow the City"
        bl_description = "Apply the change, then play the growth in the camera view"

        def execute(self, ctx):
            try:
                _assert_gui_generator_current(ctx.scene)
            except Exception as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
            try:
                cfg = _parse_change(ctx.scene.nb_change)
            except ValueError as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
            if ctx.scene.nb_time != "auto":
                cfg["time"] = ctx.scene.nb_time
            if ctx.scene.nb_season != "auto":
                cfg["season"] = ctx.scene.nb_season
            try:
                summary = main(cfg)
            except Exception as e:
                self.report({"ERROR"}, str(e))
                return {"CANCELLED"}
            # watch it through the camera
            for area in ctx.screen.areas:
                if area.type == "VIEW_3D":
                    for space in area.spaces:
                        if space.type == "VIEW_3D":
                            space.shading.type = "MATERIAL"
                            space.region_3d.view_perspective = "CAMERA"
            if ctx.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
            ctx.scene.frame_set(1)
            bpy.ops.screen.animation_play()
            bpy.ops.wm.save_mainfile()
            note = " | ".join(summary["milestones"]) if summary["milestones"] else ""
            self.report({"INFO"}, "Day %d — pop %d %s" %
                        (summary["day"], summary["population"], note))
            return {"FINISHED"}

    class NB_OT_stop(bpy.types.Operator):
        bl_idname = "nb.stop"
        bl_label = "Stop"
        bl_description = "Stop the animation and jump to the finished city"

        def execute(self, ctx):
            if ctx.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
            ctx.scene.frame_set(ctx.scene.frame_end)
            return {"FINISHED"}

    class NB_OT_replay(bpy.types.Operator):
        bl_idname = "nb.replay"
        bl_label = "Replay"
        bl_description = "Play the last day's animation again from the start"

        def execute(self, ctx):
            if ctx.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
            ctx.scene.frame_set(1)
            bpy.ops.screen.animation_play()
            return {"FINISHED"}

    class NB_OT_render(bpy.types.Operator):
        bl_idname = "nb.render"
        bl_label = "Render Video"
        bl_description = "Render the day's 9:16 video (auto-copies to Desktop)"

        def execute(self, ctx):
            if ctx.screen.is_animation_playing:
                bpy.ops.screen.animation_play()
            bpy.ops.render.render("INVOKE_DEFAULT", animation=True)
            self.report({"INFO"}, "Rendering... video lands in renders/ and on your Desktop")
            return {"FINISHED"}

    class NB_PT_panel(bpy.types.Panel):
        bl_label = "Follower Neighborhood"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "City"

        def draw(self, ctx):
            lay = self.layout
            lay.prop(ctx.scene, "nb_change")
            row = lay.row()
            row.prop(ctx.scene, "nb_time")
            row.prop(ctx.scene, "nb_season")
            lay.operator("nb.grow", icon="PLAY")
            row = lay.row()
            row.operator("nb.stop", icon="PAUSE")
            row.operator("nb.replay", icon="FILE_REFRESH")
            lay.operator("nb.render", icon="RENDER_ANIMATION")

    for cls in (NB_OT_grow, NB_OT_stop, NB_OT_replay, NB_OT_render, NB_PT_panel):
        try:
            bpy.utils.unregister_class(getattr(bpy.types, cls.__name__))
        except Exception:
            pass
        bpy.utils.register_class(cls)

    # copy finished videos to the Desktop automatically
    hs = bpy.app.handlers.render_complete
    for h in list(hs):
        if getattr(h, "__name__", "") == "_copy_video_to_desktop":
            hs.remove(h)
    hs.append(_copy_video_to_desktop)

if bpy.app.background:
    main()
else:
    _register_ui()
    print("City panel ready — press N in the 3D viewport and open the 'City' tab.")
