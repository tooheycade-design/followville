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
import json
import math
import os
import random
import sys

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
# When any CLI args are given, the CONFIG constants above are ignored.

def _cli():
    if "--" not in sys.argv:
        return {}
    args = sys.argv[sys.argv.index("--") + 1:]
    flags = {"--render": "render", "--still": "still", "--replay": "replay",
             "--hero": "hero", "--celebrate": "celebrate", "--pond": "pond",
             "--parkring": "parkring"}
    keys = {"--pop": "pop", "--gained": "gained", "--lost": "lost",
            "--followers": "followers", "--houses": "gained",
            "--apartments": "apartments", "--parks": "parks", "--trees": "trees",
            "--mushrooms": "mushrooms"}
    skeys = {"--time": "time", "--season": "season", "--cam": "cam", "--tag": "tag"}
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

LOT      = 10                    # lot size (m)
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

def mat(name, rgb, rough=0.85):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return m

def std_mats():
    return {
        "grass":  mat("NB_grass",  (0.42, 0.60, 0.33), 1.0),
        "lawn":   mat("NB_lawn",   (0.40, 0.66, 0.30), 1.0),
        "road":   mat("NB_road",   (0.30, 0.31, 0.33), 0.9),
        "dash":   mat("NB_dash",   (0.85, 0.80, 0.40), 0.9),
        "trunk":  mat("NB_trunk",  (0.44, 0.31, 0.21), 1.0),
        "door":   mat("NB_door",   (0.36, 0.24, 0.17), 0.8),
        "window": mat("NB_window", (0.95, 0.90, 0.70), 0.2),
        "windark": mat("NB_windark", (0.16, 0.22, 0.30), 0.2),
        "water":  mat("NB_water",  (0.30, 0.58, 0.78), 0.1),
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

def build_house(col, seed):
    rng = random.Random(seed)
    m = std_mats()
    wall = mat("NB_wall%d" % seed, WALLS[rng.randrange(len(WALLS))])
    roof = mat("NB_roof%d" % seed, ROOFS[rng.randrange(len(ROOFS))])
    w = 5.5 + rng.random() * 1.5
    d = 5.0 + rng.random() * 1.2
    h = 3.4 + rng.random() * 1.2
    add_box(col, "base", w, d, h, 0, 0, 0, wall)
    add_prism_roof(col, "roof", w + 0.7, d + 0.7, 1.9 + rng.random(), 0, 0, h, roof)
    add_box(col, "door", 1.1, 0.25, 1.9, (rng.random() - 0.5) * w * 0.35, -d / 2 - 0.1, 0, m["door"])
    add_box(col, "winL", 1.0, 0.2, 0.9, -w * 0.28, -d / 2 - 0.08, 1.6, m["window"])
    add_box(col, "winR", 1.0, 0.2, 0.9,  w * 0.28, -d / 2 - 0.08, 1.6, m["window"])
    if rng.random() < 0.6:   # chimney
        add_box(col, "chim", 0.7, 0.7, 1.3, w * 0.25, d * 0.15, h + 0.8, m["cap"])
    if rng.random() < 0.65:  # yard tree
        build_tree(col, rng, 0.6 + rng.random() * 0.4,
                   (1 if rng.random() < 0.5 else -1) * (w / 2 + 1.5),
                   (rng.random() - 0.5) * 3)

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
    add_box(col, "body", 3.6, 1.7, 0.85, 0, 0, 0.35, body)
    add_box(col, "cab", 1.9, 1.5, 0.7, -0.2, 0, 1.2, m["windark"])
    for dx in (-1.15, 1.15):
        for dy in (-0.85, 0.85):
            # upright stubby cylinders read as wheels at this scale
            add_ngon_cone(col, "wheel", 0.36, 0.36, 0.3, 10, dx, dy, 0.0, m["metal"])


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

ASSET_VARIANTS = {
    "house":       [("AST_house_%d" % i, lambda c, i=i: build_house(c, 100 + i)) for i in range(6)],
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
    "duck":        [("AST_duck_%d" % i, lambda c, i=i: build_duck(c, 2200 + i)) for i in range(3)],
    "ringhouse":   [("AST_ring_%d" % i, lambda c, i=i: build_ring_house(c, 2300 + i)) for i in range(10)],
    "parkdistrict": [("AST_parkdist_0", lambda c: build_park_district(c, 2400))],
}

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
        return b["px"], b["py"]
    return lot_to_world(b["gx"], b["gy"])

# building footprint in lots (per side); milestone buildings can span a whole block
SIZE = {"house": 1, "tree": 1, "shop": 1, "streetlight": 1, "car": 1, "bush": 1, "rock": 1,
        "mushroomhouse": 1, "casinohouse": 1, "cathouse": 1, "castlehouse": 1,
        "eiffelhouse": 1, "flowerhouse": 1, "burjhouse": 1, "toilethouse": 1, "beachhouse": 1,
        "cottagehouse": 1, "pond": 1, "ringhouse": 1, "parkdistrict": 1,
        "apartment": 2, "park": 2, "plaza": 2, "skyscraper": 2, "stadium": 3}

# unlocked automatically the day population crosses the threshold
MILESTONES = [(500, "plaza"), (2000, "skyscraper"), (10000, "stadium")]

def footprint(b):
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
    rng = random.Random(1234)
    lots = []
    for gx in range(-radius, radius + 1):
        for gy in range(-radius, radius + 1):
            x, y = lot_to_world(gx, gy)
            lots.append((math.hypot(x, y) + rng.random() * 22, gx, gy))
    lots.sort()
    return lots

def find_free_lots(count, size, occupied, blocked_blocks=None):
    # start near the city's current edge so huge cities don't rescan from zero
    radius = max(3, int(math.sqrt(len(occupied) + count * size * size)))
    while radius < 400:  # ~640k lots — enough for hundreds of thousands
        found = []
        taken = set(occupied)
        for _, gx, gy in sorted_lots(radius):
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
    variants = ASSET_VARIANTS[b["type"]]
    vname, builder = variants[b["seed"] % len(variants)]
    asset = get_asset(vname, builder)
    empty = bpy.data.objects.new(name, None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = asset
    x, y = build_pos(b)
    s = SIZE.get(b["type"], 1)
    if "px" in b:  # exact world placement (park district / ring houses)
        empty.location = (x, y, 0.1 if b["type"] == "ringhouse" else 0)
    else:
        empty.location = (x + (s - 1) * LOT / 2, y + (s - 1) * LOT / 2, 0)
    rng = random.Random(b["seed"])
    if b.get("rot") is not None:  # exact facing (ring houses face their park)
        empty.rotation_euler = (0, 0, b["rot"])
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
    world_col.objects.link(empty)
    return empty

# ═══════════════════════════════ ROADS & DRESSING ═══════════════════════════════

def block_extent(buildings):
    """The town always has at least a 3x3-block starter road grid, so day 0
    shows the exact streets that houses will later appear on. Off-grid park
    districts (and their ring houses) don't extend the grid."""
    buildings = [b for b in buildings if b["type"] not in ("parkdistrict", "ringhouse")]
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
        x = x0 + 4
        while x < x1 - 4:
            add_box(world_col, "dash", 2.6, 0.45, 0.05, x, y, 0.17, m["dash"])
            x += 8
    # streetlights + parked cars at intersections/edges (deterministic)
    rng = random.Random(9000 + (max_bx - min_bx) * 31 + (max_by - min_by))
    for bx in range(min_bx, max_bx + 2):
        for by in range(min_by, max_by + 2):
            ix, iy = bx * PITCH - ROAD / 2, by * PITCH - ROAD / 2
            if rng.random() < 0.65:
                b = {"type": "streetlight", "gx": 0, "gy": 0, "seed": 0}
                e = place_instance(world_col, b, "light")
                e.location = (ix + ROAD / 2 + 0.6, iy + ROAD / 2 + 0.6, 0)
                e.rotation_euler = (0, 0, rng.random() * math.tau)
            if rng.random() < 0.4:
                b = {"type": "car", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
                e = place_instance(world_col, b, "car")
                horiz = rng.random() < 0.5
                off = (rng.random() - 0.5) * PITCH * 0.7
                if horiz:
                    e.location = (ix + off, iy + (1.5 if rng.random() < 0.5 else -1.5), 0.05)
                    e.rotation_euler = (0, 0, 0 if rng.random() < 0.5 else math.pi)
                else:
                    e.location = (ix + (1.5 if rng.random() < 0.5 else -1.5), iy + off, 0.05)
                    e.rotation_euler = (0, 0, math.pi / 2 * (1 if rng.random() < 0.5 else -1))

def build_district_roads(world_col, buildings, m):
    """Straight connector from each park district's entrance (the house gap
    on its west side) to the town's easternmost grid road."""
    districts = [b for b in buildings if b["type"] == "parkdistrict"]
    if not districts:
        return
    min_bx, max_bx, min_by, max_by = block_extent(buildings)
    x_road = (max_bx + 1) * PITCH - ROAD / 2
    for d in districts:
        cx, cy = d["px"], d["py"]
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

def animate_ring_traffic(world_col, buildings, frame_end):
    """A couple of cars slowly loop each park district's ring roads."""
    for d in [b for b in buildings if b["type"] == "parkdistrict"]:
        rng = random.Random(6000 + d["seed"])
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
                e.location = (d["px"] + r * math.cos(a), d["py"] + r * math.sin(a), 0.17)
                e.rotation_euler = (0, 0, a + spin * math.pi / 2)
                e.keyframe_insert("location", frame=fr)
                e.keyframe_insert("rotation_euler", frame=fr)
            for fc in obj_fcurves(e):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

def scatter_nature(world_col, occupied, buildings):
    """Trees, bushes and rocks on empty lots + a wild ring around town.
    Seeded per lot, so the scenery is identical between videos until
    someone builds on that lot."""
    min_bx, max_bx, min_by, max_by = block_extent(buildings)
    for gx in range((min_bx - 1) * BLOCK_N, (max_bx + 2) * BLOCK_N):
        for gy in range((min_by - 1) * BLOCK_N, (max_by + 2) * BLOCK_N):
            if (gx, gy) in occupied:
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
    "day":    dict(sun_e=2.6, sun_c=(1.00, 0.95, 0.86), sun_rot=(50, 0, 120),
                   sky=(0.62, 0.80, 0.92), sky_s=1.3, win=0.0, lamp=0.0),
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
    # invisible until its turn — no flattened houses lying on the ground
    _keyframe_hidden(empty, 1, True)
    _keyframe_hidden(empty, f_start, False)
    empty.scale = (1, 1, 0.001)
    empty.keyframe_insert("scale", frame=f_start)
    empty.scale = (1, 1, 1)
    empty.keyframe_insert("scale", frame=f_start + dur)
    _ease_scale(empty, "EASE_OUT")

def animate_sink(empty, f_start, dur=20):
    """Follower lost: the house sinks back into the ground, then vanishes."""
    _keyframe_hidden(empty, 1, False)
    _keyframe_hidden(empty, f_start + dur, True)
    empty.scale = (1, 1, 1)
    empty.keyframe_insert("scale", frame=f_start)
    empty.scale = (1, 1, 0.001)
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
    if hero:  # close-up on a special building / batch
        cx, cy, hdist = hero
        dist, pol_deg, fstop = hdist, 64, 2.0
        orbit_deg = 9

    # ground
    add_box(world_col, "ground", 4000, 4000, 0.1, cx, cy, -0.1, m["grass"])

    if cam == "street":
        # eye-level flythrough down the town's oldest street (the by=0 road,
        # which runs past whichever buildings sit at gy 0-2 -- the founder
        # blocks from day 1) instead of orbiting a fixed point overhead.
        min_bx, max_bx, min_by, max_by = block_extent(buildings)
        x0, x1 = min_bx * PITCH - ROAD, (max_bx + 1) * PITCH
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
        cam_data.dof.use_dof = True
        cam_data.dof.focus_object = rig
        cam_data.dof.aperture_fstop = fstop
        cam_obj = bpy.data.objects.new("Camera", cam_data)
        cam_obj.parent = rig
        az, pol = math.radians(38), math.radians(pol_deg)
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
    for vt in ("Standard", "Filmic", "AgX"):  # Standard keeps pastels vivid
        try:
            sc.view_settings.view_transform = vt
            break
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
    for coll in (bpy.data.meshes, bpy.data.actions, bpy.data.lights, bpy.data.cameras):
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
            (px, py), = find_free_lots(1, 2, occupied)
            cluster_cells = [(px, py), (px + 1, py), (px, py + 1), (px + 1, py + 1)]
            pond_extras.append(("pond", 1, cluster_cells[0]))
            house_cells = cluster_cells[1:1 + min(gained, 3)]
            for cell in house_cells:
                pond_extras.append(("house", 1, cell))
            house_gained = gained - len(house_cells)

        parkring_n = 0
        if cfg.get("parkring") and gained > 0:
            parkring_n, house_gained = gained, 0

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
                # regular houses stay out of blocks that hold custom homes
                custom_blocks = set()
                for b in state["buildings"]:
                    if b["type"].endswith("house") and b["type"] != "house":
                        for cgx, cgy in footprint(b):
                            custom_blocks.add((cgx // BLOCK_N, cgy // BLOCK_N))
                lots = find_free_lots(n, size, occupied, custom_blocks)
            else:
                lots = find_free_lots(n, size, occupied)
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
    new_ids = {id(b) for b in new_batch}
    rem_ids = {id(b) for b in removed}
    rise, sink = [], []
    for b in state["buildings"]:
        e = place_instance(world_col, b, "%s_d%d" % (b["type"], b.get("day", 0)))
        if id(b) in new_ids:
            rise.append(e)
        elif id(b) in rem_ids:
            sink.append(e)
    keep = [b for b in state["buildings"] if id(b) not in rem_ids]
    build_roads(world_col, keep or state["buildings"], m)
    build_district_roads(world_col, keep or state["buildings"], m)
    scatter_nature(world_col, occupied, keep or state["buildings"])

    # animation timing: sinks first, then rises
    n_anim = len(rise) + len(sink)
    prehold = int(1.5 * FPS)
    stagger = max(2, min(6, 240 // max(n_anim, 1)))
    posthold = int(2.5 * FPS)
    frame_end = prehold + max(n_anim - 1, 0) * stagger + 22 + posthold
    if cfg.get("cam") in ("street", "park", "overhead"):
        frame_end = max(frame_end, FPS * 12)  # give slow showcase cams time to breathe
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
    if cfg.get("hero") and new_batch:
        pts = []
        for b in new_batch:
            x, y = build_pos(b)
            s = SIZE.get(b["type"], 1)
            r = b.get("r", 0)
            if r:
                pts += [(x - r, y - r), (x + r, y + r)]
            else:
                pts.append((x + (s - 1) * LOT / 2, y + (s - 1) * LOT / 2))
        hx = sum(p[0] for p in pts) / len(pts)
        hy = sum(p[1] for p in pts) / len(pts)
        span = max(max(p[0] for p in pts) - min(p[0] for p in pts),
                   max(p[1] for p in pts) - min(p[1] for p in pts))
        hero = (hx, hy, max(42.0, span * 2.1 + 44))
    build_stage(world_col, state["buildings"], frame_end, m, tod, hero, cfg.get("cam"))
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
