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

# Pure-data reserve for populations 135..750. Importing this module creates
# nothing; future houses/roads remain invisible until main() consumes them.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else ""
if _SCRIPT_DIR and _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from neighborhood_plan import (PLAN as SUBURBAN_PLAN,
                               HOUSE_CAPACITY as SUBURBAN_CAPACITY,
                               ARTERIAL_HALF_WIDTH,
                               NORTHGATE_ARTERIAL_REVEAL,
                               SUBURBAN_TIGHT_PLAN_IDS,
                               northgate_arterial_points)
from metropolitan_plan import (TOWER_PLAN as METRO_TOWER_PLAN,
                               TOWER_COUNT as METRO_TOWER_COUNT,
                               TOWER_RESIDENT_CAPACITY,
                               DISTRICT as METRO_DISTRICT,
                               STREETS as METRO_STREETS,
                               RAMPS as METRO_RAMPS,
                               NORTH_SOUTH_X as METRO_NS_X,
                               EAST_WEST_Y as METRO_EW_Y,
                               EXPRESSWAY_X, EXPRESSWAY_Y0, EXPRESSWAY_Y1,
                               EXPRESSWAY_DECK_Z, EXPRESSWAY_WIDTH,
                               INTERCHANGE_Y as METRO_INTERCHANGE_Y,
                               TERRACE_DATUM as METRO_TERRACE_DATUM,
                               expressway_points)
import highway_plan as HP
from downtown_visual_plan import TERRAIN_BOUNDS, mounted_face_center
from downtown_visuals import build_downtown_visuals, terrain_height
from downtown_visual_plan import (FISHING_POND_X, FISHING_POND_Y,
                                  FISHING_POND_RX, FISHING_POND_RY)
from downtown_visual_plan import river_center_x, river_distance, river_water_height
from world_layout import (rafting_access_points, CITY_HALL_APPROACH,
                          LANDMARK_GRID_SIZE,
                          STORYBOOK_ACCESS, SALMON_SHOP_APPROACH,
                          SALMON_SHOP_ENTRY_RAMP,
                          DISTRICT_CONNECTORS, STORYBOOK_LAYOUT_CENTER,
                          WEATHER_STATION_CENTER,
                          WEATHER_STATION_HALF_EXTENTS,
                          NORTH_CROWN_CAMPUS_ACCESS,
                          weather_station_access_points,
                          weather_station_base_height,
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
#   --cam newgrowthall  frame every house in today's rising batch
#   --cam newgrowthoverhead  top-down view of today's rising houses
#   --cam wholeoverhead  whole-town sky view; all of today's houses rise
#   --cam newstreet  finished eye-level glide through today's busiest street
#   --cam storybookstreet  finished road-level tour of Kaleidoscope Crest
#   --cam housefront  sidewalk view of a current house with passing cars
#   --cam football   temporary England v Argentina supporter vignette
#   --cam cinematic  elevated whole-city skyline reveal
#   --cam dronezoom  fast whole-city dive and pullback
#   --cam dronehover  smooth high-altitude crescent hover across the city
#   --cam day21growth  coffee-truck reveal followed by the five new homes
#   --cam day21drone  eight-second neighborhood-to-downtown drone glide
#   --cam day21skyline  eight-second angled skyline push
#   --cam day22reveal  14-second skyline, ten-home, and fire-station reveal
#   --cam day23reveal  16-second skyline, homes, civic road, and City Hall reveal
#   --cam day24reveal  20-second dusk milestone flight through homes and Civic Square
#   --cam day25reveal  18-second skyline-to-homes-to-fishing-pond flight
#   --cam day26reveal  18-second city-to-homes-to-construction-zone flight
#   --cam day27reveal  20-second city-to-36-homes-to-movie-theater flight
#   --cam day28reveal  20-second old-plan finish, river/road, river-home reveal
#   --cam day29reveal  18-second city arc, 31 river homes, rafting-outpost finale
#   --cam day30reveal  18-second low downtown angle into 46 Cedarbank home rises
#   --cam day31reveal  20-second whole-town, 20-home, and City Hall drone reveal
#   --cam day32campaign 20-second town, 31-home, billboard, and campaign-semi reveal
#   --cam day33storm  20-second storm flight through 33 homes to the weather station
#   --cam day34fire    16-second skyline fire response into 31 Eastbank home rises
#   --cam day35store  24-second continuous town/homes/Salmon Pro Shop reveal
#   --cam day36reveal 16-second held skyline, fast transfer, 13 Heron Reach rises
#   --salmonproshop  add the permanent Salmon Pro Shop west of downtown
#   --highschool     add Followville High -- three buildings and the stadium,
#                     on the block south of the elementary school
#   --commons        add Followville Commons, the permanent apartment complex
#   --northcrowncampus add North Crown's permanent planned apartment campus
#                     with four finished blocks and sixteen grass parcels
#   --foodcourt      add the Food Court ring of food-shaped homes
#   --cam day38reveal 16-second skyline, run east, Food Court rise
#   --cam day38foodtour 20-second city drone -> Food Court rise -> street level
#   --cam day37reveal 24-second orbit, Commons rise, and the mayor's plinth
#   --cam day42reveal 16-second Founder skyline, FPV transfer, West Quarter wave
#   --cam day43fpv   16-second skyline, low construction wave, Point Station reveal
#   --cam day43pov   16-second street POV, close overhead wave, alternate station reveal
#   --cam day44approach  city overview diving into the Day 44 house wave
#   --cam day44street    grounded street view; houses rise toward the viewer
#   --cam day44drone     low drone companion flight with the construction wave
#   --cam day44field     fixed grass-field viewpoint with an optical zoom
#   --cam day44overhead  completed-city sunset overhead
#   --cam day44downtown  completed-city low downtown street flight
#   --cam day44allapproach full-growth overview descending into the house wave
#   --cam day44alldrone   wide drone flight carrying the complete growth front
#   --cam day44allfield   fixed distant field zoom framing the full growth area
#   --cam day44fullarc    full-city overhead -> growth wave -> full-city overhead
#   --cam day44southfpv   16-second south skyline FPV construction chase
#   --cam day44swrooftop 16-second south-west skyline rooftop/street run
#   --cam day44westbank  16-second west skyline bank and diagonal dive
#   --cam day44sereverse 16-second south-east skyline reverse-wave flight
#   --cam day46sunsetdrone 16-second skyline, low 47-home wave, city pullback
#   --cam day47reveal 24-second sunset street flight down the Ember Ridge
#                     centreline, 37 homes rising one by one past the lens,
#                     then a low climb-out over the original city.
#                     Authored for --time sunset.
#   --cam day48crown 24-second sunset descent onto the Wheelwright Street
#                     centreline, 81 homes rising across three Ember Ridge
#                     streets, then a climbing turn south-east that lands on
#                     Crown Quarter's first tower as it rises.
#                     Authored for --time sunset.
#   --cam day49northreach 24-second sunset approach across the y=824 seam and
#                     north up the Maple Avenue North centreline, 152 homes
#                     rising on five Crown Fields streets, then a climbing
#                     bank that looks back south-west down all five.
#                     Authored for --time sunset.
#   --cam day50highway 24-second sunset construction chase through the 50 new
#                     Crown Fields addresses, ending on the rebuilt Crown
#                     Expressway / Ring Freeway interchange.
#                     Authored for --time sunset.
#   --cam day41reveal 30-second town overhead, arc to the new quarter, roads
#                     draw themselves on, 300 homes rise, low run home
#   --cam metroreveal 26-second historic-core to expressway to skyline reveal
#   --cam day40reveal 27-second city overhead, one eastward drone run through
#                     58 new homes, then the filling station in its own shot
#   --gasstation     claim the reserve's next filling-station address
#   --cam story001pricesign  Followville Stories #001, shots 1-4 (11.0s, --time day)
#   --cam story001dusk       Followville Stories #001, shot 5 (4.2s, --time dusk)
#                     Both are render-only overlays on the filling station and
#                     need --replay --focus-type finished. See FOLLOWVILLE_STORIES.md.
#   --cam riverdrone    reusable finished river/bridge aerial
#   --cam riverbridge   reusable first-person-height bridge crossing
#   --cityhall       add the permanent City Hall and its terrain-following road
#   --civicsquare    add the permanent terrain-following square beside City Hall
#   --fishingpond    add the permanent off-grid fishing pond north of the grid
#   --constructionzone add the cleared downtown vote site at block (-2, 1)
#   --movietheater  replace the canonical vote site with Followville Cinema
#   --arcade       replace verified-unclaimed downtown seed 129 with the arcade
#   --eastwoods      add the permanent raised East Woods reserve
#   --raftingstation add the permanent west-bank rafting outpost and launch
#   --godzilla       temporary city-destruction layer for cinematic replays
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
             "--hero": "hero", "--pond": "pond",
             "--parkring": "parkring", "--scatter": "scatter",
             "--godzilla": "godzilla", "--forest": "forest",
             "--cityhall": "cityhall", "--civicsquare": "civicsquare",
             "--fishingpond": "fishingpond",
             "--constructionzone": "constructionzone",
             "--movietheater": "movietheater",
             "--arcade": "arcade",
             "--eastwoods": "eastwoods",
             "--raftingstation": "raftingstation",
             "--salmonproshop": "salmonproshop",
             "--highschool": "highschool",
             "--commons": "apartmentcomplex",
             "--northcrowncampus": "northcrowncampus",
             "--gasstation": "gasstation",
             "--nuclearplant": "nuclearplant",
             "--foodcourt": "foodcourt"}
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

EAST_WOODS_X = 170.0
EAST_WOODS_Y = 180.0
EAST_WOODS_RADIUS = 58.0
RAFTING_STATION_X = 330.0
RAFTING_STATION_Y = -30.0

# Salmon Pro Shop, on the western edge of town about 130m out from downtown
# centre -- as close as a 50x56m pad fits, because everything inside that is
# either paved grid or suburb. Sited by measurement: 18m clear of the nearest
# building, no building anywhere inside the pad, and a drive off the Twin Oaks
# connector. The ground falls 3.78m west to east across it, so the pad is a
# genuinely retained platform rather than a slab resting on a slope.
SALMON_SHOP_X = -128.0
SALMON_SHOP_Y = -36.0

# Followville High. The block immediately south of the elementary school,
# across the town's own y=-93 street. The anchor is the centre of the campus
# rectangle declared in world_layout.LANDMARK_FOOTPRINTS["highschool"] and cut
# level by downtown_visual_plan.HIGH_SCHOOL_PAD; all three must agree.
HIGH_SCHOOL_X = -69.0
HIGH_SCHOOL_Y = -156.0

# Followville Commons. Sited by scanning the meadow for the largest clear,
# level ground within reach of the civic district: 60m clear in every
# direction, and the connector to Meadow Run runs at 1.4-2.1% grade.
# Food Court. Sited by scanning the meadow east of Kaleidoscope Crest with
# check_world_geometry's own transform: 82m clear radius, 1.21m fall across
# the ring, and an 89m connector to Rivergate at 0.1-1.8% grade.
FOOD_COURT_X = 272.0
FOOD_COURT_Y = 210.0
FOOD_COURT_HOMES = 19
# The ring the nineteen homes actually stand on. These were 46/38 until
# 2026-08-09, which is not what built the district: the day-37 growth run wrote
# its addresses from 40/33, so the constants here described a ring 6m wider than
# the one in world_state.json. Nothing moved when they were corrected -- every
# address is already stored -- but anyone re-deriving a lot from this function
# got a position no house has ever occupied. 40/33 is also the only pair that
# fits: it leaves each home exactly 8m from the loop road's centre line.
FOOD_COURT_RING_RX = 40.0
FOOD_COURT_RING_RY = 33.0
# Every home's own geometry -- body, plinth, entrance steps, paving -- stays
# inside this radius of its anchor. The loop road's centre line is 8m away and
# it is ROAD (6m) wide, so its kerb is at 5.0m: a home that reaches further
# than this paves over the street it is meant to face.
FOOD_COURT_HOME_REACH = 4.80


def food_court_lots():
    """The ring of homes, evenly spaced and every one facing the loop road."""
    lots = []
    for index in range(FOOD_COURT_HOMES):
        a = math.tau * index / FOOD_COURT_HOMES - math.pi / 2
        # Food house assets are authored with their front on local -Y, like
        # every other house in town, and place_instance() turns that front by
        # `rot`. Rotating by `a + pi` -- what this returned until 2026-08-09 --
        # leaves the front pointing along the ring tangent, so all nineteen
        # homes showed the plaza a side wall and walked their front paths out
        # across the grass. -Y lands on the inward radius at `a - pi/2`.
        lots.append((FOOD_COURT_X + FOOD_COURT_RING_RX * math.cos(a),
                     FOOD_COURT_Y + FOOD_COURT_RING_RY * math.sin(a),
                     a - math.pi / 2))       # face inward, toward the road
    return lots


# Which two homes the connector threads, and how far each reaches toward the
# gap between them. Nineteen homes evenly spaced on the ring leave no gap for a
# road, so the connector has to pass between two of them; index 2 is the fries
# carton and index 3 the sushi roll, and the ring has been complete since day
# 37, so neither ever changes.
#
# These are measured, not estimated: 3.81m is the fries carton's overhanging
# lip, not its foundation, and taking the foundation's 3.08m instead put the
# lane 1.40m inside the home it was being moved to miss. check_food_assets.py
# re-measures both off the built designs every run and fails with the real
# figure, which is how that was caught.
FOOD_COURT_GAP_INDICES = (2, 3)
FOOD_COURT_GAP_REACH = (3.81, 4.37)
# The lane's width along its own centreline, as (metres from the pinch, width).
# It cannot be ROAD where it passes the homes: they stand 11.98m apart and take
# 8.18m of that between them, leaving 3.80m of ground for a carriageway and two
# verges.
#
# The narrow section runs the whole way from the loop junction to well clear of
# the ring, rather than pinching at a point. A short pinch is not enough: the
# fries carton presents a flat side to the lane, so the clearance hardly grows
# as the lane moves away from it, and a stretch tapering back up to ROAD only
# three metres inside the ring lay 1.02m inside that home's own footprint. Only
# widen once both homes are behind it.
FOOD_COURT_LANE_PROFILE = ((-6.4, 3.0), (6.0, 3.0), (10.0, 4.6), (14.0, ROAD))
# The rest of the run out to the bridge, unchanged, local to the district.
FOOD_COURT_LANE_TAIL = ((45.0, -42.0), (55.0, -54.0), (62.5, -63.5))


def food_court_connector():
    """The lane out to the river bridge, and its width at each control point.

    Until 2026-08-09 this ran straight out on its own bearing at full ROAD
    width and lay 1.77m inside the fries carton's foundation -- the incident
    world_layout.LANDMARK_FOOTPRINTS' comment records, and the reason those ten
    civic footprints were declared in the first place. Two things were wrong
    with it: it took the bearing it happened to have rather than the line
    through the gap, and it stayed six metres wide the whole way.

    So it now leaves on the line that balances the two homes' verges -- the
    middle of the gap is not the middle of the free ground, because the two
    homes reach different distances into it -- and narrows to a single track
    where it threads them, widening back to ROAD once it is clear of the ring.

    The centreline is derived from food_court_lots(), so it cannot drift away
    from the homes it has to miss. Local to the district instance, like
    everything else in build_food_court(). Returns (points, widths).
    """
    lots = food_court_lots()
    first, second = (lots[index] for index in FOOD_COURT_GAP_INDICES)
    ax, ay = first[0] - FOOD_COURT_X, first[1] - FOOD_COURT_Y
    bx, by = second[0] - FOOD_COURT_X, second[1] - FOOD_COURT_Y
    span = math.hypot(bx - ax, by - ay)
    along = span / 2 + (FOOD_COURT_GAP_REACH[0] - FOOD_COURT_GAP_REACH[1]) / 2
    pinch_x = ax + (bx - ax) * along / span
    pinch_y = ay + (by - ay) * along / span
    # Perpendicular to the gap, so the pinch really is the closest the lane ever
    # comes to either home, and pointing away from the plaza.
    out_x, out_y = (by - ay) / span, -(bx - ax) / span
    if pinch_x * out_x + pinch_y * out_y < 0:
        out_x, out_y = -out_x, -out_y
    points = [(pinch_x + step * out_x, pinch_y + step * out_y)
              for step, _ in FOOD_COURT_LANE_PROFILE]
    widths = [lane_width for _, lane_width in FOOD_COURT_LANE_PROFILE]
    points.extend(FOOD_COURT_LANE_TAIL)
    widths.extend([ROAD] * len(FOOD_COURT_LANE_TAIL))
    return points, widths


APARTMENTS_X = -50.0
APARTMENTS_Y = -300.0
# Re-sited 2026-08-07. The first site was chosen against stored coordinates
# and landed 0.9m from house seed 485 once district render offsets were
# applied -- the complex grew through a claimed house. This one was scanned
# with check_world_geometry's own transform and clears every building by 30m.
# Terrain falls 1.41m across the podium; the deck sits just over the high
# corner and stands 1.47m proud at the low one, inside DEFAULT_MAX_PAD_STAND.
APARTMENTS_PAD_Z = 1.84

# Permanent planned campus immediately north of the Day 45 Ember Ridge front.
# The shared terrain is level to less than a millimetre across the enclosure,
# so buildings and parking sit directly on grade rather than on raised blocks.
NORTH_CROWN_CAMPUS_X = -370.0
NORTH_CROWN_CAMPUS_Y = 1088.0
NORTH_CROWN_CAMPUS_Z = 5.332

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
    # NEIGHBORHOOD_STATE_DIR lets guarded launchers use the authoritative Git
    # repository and lets audits use disposable test-state folders. Unset keeps
    # the local .blend-adjacent behavior for direct development sessions.
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


def image_mat(name, relative_path, rough=.58):
    """Packed image material for a permanent branded sign in the Blend/GLB."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    path = os.path.join(_SCRIPT_DIR, relative_path)
    if not os.path.isfile(path):
        raise RuntimeError("Missing branded image asset: %s" % path)
    image = bpy.data.images.load(path, check_existing=True)
    if not image.packed_file:
        image.pack()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.interpolation = "Linear"
    bsdf.inputs["Roughness"].default_value = rough
    m.node_tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    m.node_tree.links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
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

def mat_emissive(name, rgb, rough=.34, strength=1.0):
    """A flat colour that also emits.

    mat() has no emission argument and widening it would touch every material
    in the town, so the Principled node is reached directly here. The input is
    called "Emission Color" on current Blender and "Emission" on older builds,
    hence the lookup rather than a fixed key.
    """
    m = mat(name, rgb, rough)
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        for key in ("Emission Color", "Emission"):
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
                break
        if "Emission Strength" in bsdf.inputs:
            bsdf.inputs["Emission Strength"].default_value = strength
    return m


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


def add_image_panel(col, name, w, h, x, y, z, material):
    """Single UV-mapped facade panel facing local -Y."""
    hw = w / 2
    verts = [(-hw, 0, 0), (hw, 0, 0), (hw, 0, h), (-hw, 0, h)]
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], [(0, 1, 2, 3)])
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name="UVMap")
    for loop, coordinate in zip(mesh.polygons[0].loop_indices,
                                ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[loop].uv = coordinate
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x, y, z)
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

def add_ring_sector(col, name, r_inner, r_outer, a0, a1, thickness,
                    x, y, z, material, facing=None, segments=8):
    """A flat annular sector lying in local XY, extruded by `thickness`.

    Built for signage: a radiation trefoil is three of these plus a disc, and
    nothing else in the toolkit can cut a wedge out of a ring.

    `facing` is a horizontal angle in radians. Given one, the sector is turned
    so its face points that way -- Blender's XYZ euler applies Rz*Ry, and
    Ry(90 deg) already maps local +Z onto +X, so (0, pi/2, facing) aims the
    face along (cos facing, sin facing, 0). That is what lets a sign stand
    proud of a curved wall instead of lying on the ground.
    """
    verts, faces = [], []
    for i in range(segments + 1):
        a = a0 + (a1 - a0) * i / segments
        ca, sa = math.cos(a), math.sin(a)
        verts += [(r_inner * ca, r_inner * sa, 0.0),
                  (r_outer * ca, r_outer * sa, 0.0),
                  (r_inner * ca, r_inner * sa, thickness),
                  (r_outer * ca, r_outer * sa, thickness)]
    for i in range(segments):
        b, n = 4 * i, 4 * (i + 1)
        faces += [(b, b + 1, n + 1, n),                 # underside
                  (b + 2, n + 2, n + 3, b + 3),         # face
                  (b + 1, b + 3, n + 3, n + 1),         # outer rim
                  (b, n, n + 2, b + 2)]                 # inner rim
    last = 4 * segments
    faces += [(0, 2, 3, 1), (last, last + 1, last + 3, last + 2)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    obj.location = (x, y, z)
    if facing is not None:
        obj.rotation_euler = (0.0, math.pi / 2, facing)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj


def add_wrapped_sector(col, name, cx, cy, theta0, z0, r_inner, r_outer,
                       a0, a1, standoff, thickness, radius_at, material,
                       segments=10):
    """An annular sector WRAPPED onto a vertical surface of revolution.

    Signage on a round tower cannot be a flat plate. A flat disc tangent to a
    curved wall sinks into it away from the tangent point -- for a 3.4m disc on
    an 11.5m tower the edges are 0.51m inside the shell, which is exactly the
    "phasing through the building" it looks like. Standing the plate far enough
    off to clear the curve turns it into a billboard hanging in the air, and
    the standoff grows with the square of the sign's size, so it gets worse the
    bigger the sign.

    So the sign is built in the wall's own geometry instead. The sector is laid
    out in unwrapped coordinates -- u along the surface, v up it -- and every
    vertex is mapped back onto the surface at ``radius_at(z) + standoff``.
    ``radius_at`` is a callable so the sign follows a taper: a cooling tower
    loses 0.2m of radius per metre of height, so a ten-metre sign at constant
    radius would still bury its lower edge.
    """
    verts, faces = [], []
    for i in range(segments + 1):
        a = a0 + (a1 - a0) * i / segments
        ca, sa = math.cos(a), math.sin(a)
        for r in (r_inner, r_outer):
            u, v = r * ca, r * sa
            z = z0 + v
            base = radius_at(z) + standoff
            for depth in (0.0, thickness):
                angle = theta0 + u / max(.001, base)
                rad = base + depth
                verts.append((cx + rad * math.cos(angle),
                              cy + rad * math.sin(angle), z))
    for i in range(segments):
        b, n = 4 * i, 4 * (i + 1)
        faces += [(b, b + 2, n + 2, n),                 # inner rim
                  (b + 1, n + 1, n + 3, b + 3),         # outer rim
                  (b + 2, b + 3, n + 3, n + 2),         # face
                  (b, n, n + 1, b + 1)]                 # back
    last = 4 * segments
    faces += [(0, 1, 3, 2), (last, last + 2, last + 3, last + 1)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
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


def add_torus(col, name, major_radius, minor_radius, x, y, z, material,
              major_segments=16, minor_segments=6, rotation=(0.0, 0.0, 0.0)):
    """Operator-free torus centered at x/y/z, with its ring in local XY."""
    verts, faces = [], []
    for major_index in range(major_segments):
        theta = math.tau * major_index / major_segments
        ct, st = math.cos(theta), math.sin(theta)
        for minor_index in range(minor_segments):
            phi = math.tau * minor_index / minor_segments
            radius = major_radius + minor_radius * math.cos(phi)
            verts.append((radius * ct, radius * st,
                          minor_radius * math.sin(phi)))
    for major_index in range(major_segments):
        next_major = (major_index + 1) % major_segments
        for minor_index in range(minor_segments):
            next_minor = (minor_index + 1) % minor_segments
            a = major_index * minor_segments + minor_index
            b = next_major * minor_segments + minor_index
            c = next_major * minor_segments + next_minor
            d = major_index * minor_segments + next_minor
            faces.append((a, b, c, d))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (x, y, z)
    obj.rotation_euler = rotation
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

def build_birch_tree(col, rng, scale=1.0, px=0.0, py=0.0):
    s = scale
    birch_bark = mat("NB_birch_bark", (0.92, 0.92, 0.90), 0.9)
    birch_leaf = mat("NB_birch_leaf%d" % rng.randrange(3),
                     [(0.45, 0.72, 0.35), (0.55, 0.78, 0.30), (0.62, 0.82, 0.28)][rng.randrange(3)])
    add_ngon_cone(col, "birch_trunk", 0.28 * s, 0.20 * s, 3.2 * s, 6, px, py, 0, birch_bark)
    add_ngon_cone(col, "birch_crown1", 1.4 * s, 0.4 * s, 2.2 * s, 6, px + 0.1 * s, py - 0.1 * s, 2.2 * s, birch_leaf)
    add_ngon_cone(col, "birch_crown2", 1.1 * s, 0.2 * s, 1.8 * s, 6, px - 0.2 * s, py + 0.1 * s, 3.5 * s, birch_leaf)
    add_ngon_cone(col, "birch_crown3", 0.6 * s, 0.0, 1.1 * s, 5, px, py, 4.8 * s, birch_leaf)


def build_autumn_tree(col, rng, scale=1.0, px=0.0, py=0.0):
    s = scale
    m = std_mats()
    autumn_colors = [(0.92, 0.45, 0.15), (0.95, 0.72, 0.18), (0.78, 0.22, 0.14), (0.88, 0.58, 0.12)]
    leaf_mat = mat("NB_autumn_leaf%d" % rng.randrange(len(autumn_colors)),
                   autumn_colors[rng.randrange(len(autumn_colors))])
    add_ngon_cone(col, "autumn_trunk", 0.35 * s, 0.25 * s, 2.4 * s, 6, px, py, 0, m["trunk"])
    add_ngon_cone(col, "autumn_crown1", 1.8 * s, 0.6 * s, 2.6 * s, 7, px, py, 1.8 * s, leaf_mat)
    add_ngon_cone(col, "autumn_crown2", 1.2 * s, 0.2 * s, 2.0 * s, 7, px, py, 3.4 * s, leaf_mat)


def build_rock_boulder(col, rng, scale=1.0, px=0.0, py=0.0, pz=0.0):
    s = scale
    rock_mat = mat("NB_boulder_stone", (0.42, 0.44, 0.45), 0.92)
    rot = rng.random() * math.tau
    add_ngon_cone(col, "boulder_rock", 0.95 * s, 0.65 * s, 0.85 * s, 6, px, py, pz, rock_mat, rot=rot)


def build_flower_clump(col, rng, px=0.0, py=0.0, pz=0.0):
    green_mat = mat("NB_flower_leaf", (0.28, 0.52, 0.24), 0.95)
    flower_colors = [(0.95, 0.42, 0.65), (0.98, 0.85, 0.25), (0.72, 0.55, 0.92), (0.95, 0.95, 0.95)]
    f_mat = mat("NB_flower_petals%d" % rng.randrange(len(flower_colors)),
                flower_colors[rng.randrange(len(flower_colors))])
    add_ngon_cone(col, "flower_base", 0.45, 0.25, 0.25, 6, px, py, pz, green_mat)
    for i in range(3):
        ang = i * (math.tau / 3) + rng.uniform(-0.2, 0.2)
        r = 0.18
        fx = px + r * math.cos(ang)
        fy = py + r * math.sin(ang)
        add_ngon_cone(col, "flower_head", 0.12, 0.0, 0.18, 5, fx, fy, pz + 0.22, f_mat)


def build_lowpoly_car(col, style="sedan", color=(0.25, 0.52, 0.82), px=0.0, py=0.0, pz=0.0, rot=0.0):
    body_m = mat("NB_car_body_%s" % str(color), color, rough=0.35, metallic=0.15)
    glass_m = mat("NB_car_glass", (0.75, 0.88, 0.95), rough=0.1, alpha=0.6, transmission=0.4)
    tire_m = mat("NB_car_tire", (0.12, 0.12, 0.13), rough=0.9)
    light_m = mat("NB_car_headlight", (1.0, 0.96, 0.75), rough=0.2)
    tail_m = mat("NB_car_taillight", (0.85, 0.12, 0.12), rough=0.2)

    length, width, height = 4.2, 1.8, 1.4
    if style == "pickup":
        length, width, height = 4.8, 1.9, 1.6
    elif style == "hatchback":
        length, width, height = 3.6, 1.7, 1.35

    add_box(col, "car_chassis", length, width, height * 0.45, px, py, pz + height * 0.25, body_m)
    cabin_w = width * 0.88
    cabin_l = length * 0.50 if style != "pickup" else length * 0.38
    cabin_x = px - (length * 0.08 if style == "pickup" else 0.0)
    add_box(col, "car_cabin", cabin_l, cabin_w, height * 0.42, cabin_x, py, pz + height * 0.65, glass_m)
    add_box(col, "car_roof", cabin_l * 0.9, cabin_w * 0.9, 0.06, cabin_x, py, pz + height * 0.87, body_m)

    r_wheel = 0.32
    w_width = 0.22
    for wx_sign in (-1, 1):
        for wy_sign in (-1, 1):
            wx = px + wx_sign * (length * 0.32)
            wy = py + wy_sign * (width * 0.48)
            add_ngon_cone(col, "car_wheel", r_wheel, r_wheel, w_width, 8, wx, wy, pz + r_wheel * 0.6, tire_m, rot=math.pi/2)

    for y_sign in (-1, 1):
        add_box(col, "car_headlight", 0.08, 0.3, 0.18, px + length * 0.50, py + y_sign * width * 0.35, pz + height * 0.38, light_m)
        add_box(col, "car_taillight", 0.08, 0.3, 0.18, px - length * 0.50, py + y_sign * width * 0.35, pz + height * 0.38, tail_m)


def build_tree(col, rng, scale=1.0, px=0.0, py=0.0):
    s = scale
    m = std_mats()
    tree_type_roll = rng.random()
    if tree_type_roll < 0.25:
        build_birch_tree(col, rng, scale, px, py)
    elif tree_type_roll < 0.50:
        build_autumn_tree(col, rng, scale, px, py)
    else:
        add_ngon_cone(col, "trunk", 0.4 * s, 0.3 * s, 2.0 * s, 6, px, py, 0, m["trunk"])
        green = mat("NB_green%d" % rng.randrange(len(GREENS)), GREENS[rng.randrange(len(GREENS))])
        if rng.random() < 0.5:
            add_ngon_cone(col, "pine1", 1.8 * s, 0, 3.0 * s, 7, px, py, 1.8 * s, green)
            add_ngon_cone(col, "pine2", 1.3 * s, 0, 2.3 * s, 7, px, py, 3.6 * s, green)
        else:
            blob = add_ngon_cone(col, "blob", 1.9 * s, 0.7 * s, 2.8 * s, 7, px, py, 1.8 * s, green)
            add_ngon_cone(col, "blobtop", 0.7 * s, 0, 0.9 * s, 7, px, py, 4.6 * s, green)


def _forest_floor_mesh(col, material):
    """Terrain-conforming irregular forest floor centered on East Woods."""
    rings, segments = 5, 32
    vertices = [(0.0, 0.0,
                 terrain_height(EAST_WOODS_X, EAST_WOODS_Y)
                 - terrain_height(EAST_WOODS_X, EAST_WOODS_Y) + .055)]
    for ring in range(1, rings + 1):
        fraction = ring / rings
        for segment in range(segments):
            a = segment / segments * math.tau
            wobble = 1.0 + .08 * math.sin(a * 3 + .8) + .05 * math.sin(a * 7)
            radius = EAST_WOODS_RADIUS * fraction * wobble
            lx = math.cos(a) * radius
            ly = math.sin(a) * radius * .82
            lz = (terrain_height(EAST_WOODS_X + lx, EAST_WOODS_Y + ly)
                  - terrain_height(EAST_WOODS_X, EAST_WOODS_Y) + .055)
            vertices.append((lx, ly, lz))
    faces = []
    first = 1
    for segment in range(segments):
        faces.append((0, first + segment, first + (segment + 1) % segments))
    for ring in range(1, rings):
        inner = 1 + (ring - 1) * segments
        outer = inner + segments
        for segment in range(segments):
            nxt = (segment + 1) % segments
            faces.append((inner + segment, outer + segment,
                          outer + nxt, inner + nxt))
    mesh = bpy.data.meshes.new("east_woods_floor_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new("east_woods_floor", mesh)
    col.objects.link(obj)


def build_east_woods(col, seed):
    """Dense mixed low-poly woodland with a trail and overlook clearing."""
    rng = random.Random(seed)
    m = std_mats()
    forest_floor = mat("NB_east_woods_floor", (.19, .31, .16), .98)
    trail = mat("NB_east_woods_trail", (.38, .29, .19), .98)
    fern = mat("NB_east_woods_fern", (.20, .42, .18), 1.0)
    bark = mat("NB_east_woods_bark", (.25, .15, .085), 1.0)
    stone = mat("NB_east_woods_stone", (.34, .36, .34), .96)
    _forest_floor_mesh(col, forest_floor)
    base_height = terrain_height(EAST_WOODS_X, EAST_WOODS_Y)

    # A narrow curved trail gives the biome a legible human-scale entrance.
    trail_points = [(-52, -27), (-42, -23), (-31, -17), (-20, -12),
                    (-9, -6), (2, 1), (13, 8), (24, 14), (35, 19),
                    (46, 22), (52, 20)]
    for index, ((ax, ay), (bx, by)) in enumerate(zip(trail_points, trail_points[1:])):
        az = terrain_height(EAST_WOODS_X + ax, EAST_WOODS_Y + ay) - base_height + .08
        bz = terrain_height(EAST_WOODS_X + bx, EAST_WOODS_Y + by) - base_height + .08
        length = math.hypot(bx - ax, by - ay)
        ribbon = add_box(col, "east_woods_trail_%02d" % index,
                         length + .18, 2.35, .12,
                         (ax + bx) / 2, (ay + by) / 2,
                         (az + bz) / 2 - .035, trail)
        ribbon.rotation_euler.z = math.atan2(by - ay, bx - ax)

    tree_points = []
    attempts = 0
    while len(tree_points) < 142 and attempts < 6500:
        attempts += 1
        x = rng.uniform(-EAST_WOODS_RADIUS, EAST_WOODS_RADIUS)
        y = rng.uniform(-EAST_WOODS_RADIUS * .82, EAST_WOODS_RADIUS * .82)
        if (x / EAST_WOODS_RADIUS) ** 2 + (y / (EAST_WOODS_RADIUS * .82)) ** 2 > 1:
            continue
        # Preserve the trail and a small overlook clearing at its high end.
        if min(math.hypot(x - px, y - py) for px, py in trail_points) < 3.4:
            continue
        if math.hypot(x - 35, y - 19) < 8.6:
            continue
        if any(math.hypot(x - px, y - py) < 2.4 for px, py in tree_points):
            continue
        tree_points.append((x, y))

    for index, (x, y) in enumerate(tree_points):
        z = terrain_height(EAST_WOODS_X + x, EAST_WOODS_Y + y) - base_height
        scale = rng.uniform(.82, 1.42) * (1.12 if index % 9 == 0 else 1.0)
        build_tree(col, rng, scale, x, y)
        # Shift every object created at this tree's local x/y to the sampled terrain.
        for obj in list(col.objects):
            if obj.name.startswith(("trunk", "pine", "blob")) and abs(obj.location.x-x) < .01 and abs(obj.location.y-y) < .01:
                obj.location.z += z

    # Understory, rocks, a fallen log and a simple overlook bench.
    for index in range(86):
        a = rng.random() * math.tau
        r = rng.uniform(8, EAST_WOODS_RADIUS - 3)
        x, y = math.cos(a) * r, math.sin(a) * r * .82
        if min(math.hypot(x-px, y-py) for px, py in trail_points) < 2.3:
            continue
        z = terrain_height(EAST_WOODS_X+x, EAST_WOODS_Y+y) - base_height + .05
        add_ngon_cone(col, "east_woods_fern", rng.uniform(.28, .48), .06,
                      rng.uniform(.35, .72), 7, x, y, z, fern,
                      rot=rng.random()*math.tau)
    for index, (x, y, radius) in enumerate(((-38, 15, 1.2), (43, -15, .9),
                                            (11, -30, 1.35), (39, 29, .75),
                                            (-8, 34, 1.05), (-45, -20, .82))):
        z = terrain_height(EAST_WOODS_X+x, EAST_WOODS_Y+y)-base_height+.03
        add_ngon_cone(col, "east_woods_boulder", radius, radius*.72,
                      radius*.82, 7, x, y, z, stone, rot=index*.41)
    log_z = terrain_height(EAST_WOODS_X-4, EAST_WOODS_Y+29)-base_height+.25
    log = add_ngon_cone(col, "east_woods_fallen_log", .42, .38, 8.5, 9,
                        -4, 29, log_z, bark)
    log.rotation_euler = (0, math.pi/2, math.radians(18))
    bench_z = terrain_height(EAST_WOODS_X+35, EAST_WOODS_Y+19)-base_height+.1
    add_box(col, "east_woods_bench_seat", 3.3, .62, .22, 35, 19, bench_z+.55, bark)
    add_box(col, "east_woods_bench_back", 3.3, .18, 1.05, 35, 19.3, bench_z+.72, bark)
    for x in (33.7, 36.3):
        add_box(col, "east_woods_bench_leg", .18, .48, .58, x, 19, bench_z, m["metal"])
    _merge_asset_meshes(col, "east_woods_batched")


def build_construction_zone(col, seed):
    """Full-block public vote site for a cleared downtown redevelopment block."""
    rng = random.Random(seed)
    m = std_mats()
    gravel = mat("NB_construction_gravel", (.34, .32, .28), .99)
    soil = mat("NB_construction_soil", (.30, .18, .09), 1.0)
    concrete = mat("NB_construction_concrete", (.52, .51, .47), .96)
    orange = mat("NB_construction_orange", (.94, .34, .045), .72)
    yellow = mat("NB_construction_yellow", (.95, .61, .06), .7)
    dark = mat("NB_construction_dark", (.09, .10, .10), .64, .25)
    safety = mat("NB_construction_safety", (1.0, .72, .08), .68)
    add_box(col, "construction_pad", 33.8, 33.8, .22, 0, 0, 0, gravel)
    add_box(col, "construction_excavation", 17.0, 13.0, .42, 2.0, 3.5, .22, soil)
    # Foundation forms and rebar establish that this is an active build site.
    for x in (-5.8, 9.8):
        add_box(col, "construction_footing", .72, 13.4, .55, x, 3.5, .42, concrete)
    for y in (-2.7, 9.7):
        add_box(col, "construction_footing", 16.2, .72, .55, 2.0, y, .42, concrete)
    for x in (-5.2, -1.6, 2.0, 5.6, 9.2):
        for y in (-2.1, 9.1):
            add_ngon_cone(col, "construction_rebar", .055, .055, 2.1, 8,
                          x, y, .95, m["metal"])
    # Tower crane.
    add_box(col, "construction_crane_base", 3.2, 3.2, .55, -10.5, 8.5, .25, concrete)
    for z in range(1, 17, 2):
        add_box(col, "construction_crane_mast", 1.05, 1.05, 1.78,
                -10.5, 8.5, z, yellow)
    add_box(col, "construction_crane_jib", 22.0, .55, .58, -1.0, 8.5, 17.2, yellow)
    add_box(col, "construction_crane_counter", 3.0, 1.5, 1.2, -11.8, 8.5, 16.7, dark)
    add_box(col, "construction_crane_cable", .07, .07, 8.0, 5.8, 8.5, 9.2, dark)
    add_box(col, "construction_crane_hook", .32, .18, .65, 5.8, 8.5, 8.6, orange)
    # Excavator with articulated boom and bucket.
    add_box(col, "construction_excavator_tracks", 5.8, 3.4, .72, 8.7, -7.4, .25, dark)
    add_box(col, "construction_excavator_body", 4.2, 3.0, 1.8, 8.2, -7.4, .92, yellow)
    add_box(col, "construction_excavator_cab", 2.0, 2.55, 2.35, 7.2, -7.4, 2.45, m["windark"])
    add_beam_between(col, "construction_excavator_boom",
                     (9.5, -7.4, 3.6), (13.4, -7.4, 6.8), .62, yellow)
    add_beam_between(col, "construction_excavator_stick",
                     (13.4, -7.4, 6.8), (15.2, -7.4, 2.1), .52, yellow)
    add_ngon_cone(col, "construction_excavator_bucket", 1.15, .55, 1.3, 6,
                  15.2, -7.4, .85, dark, rot=math.pi/6)
    # Perimeter fence, orange barriers and cones leave a clear south gate.
    for x in range(-16, 17, 4):
        if abs(x) > 4:
            add_box(col, "construction_fence_post", .13, .13, 2.0, x, -16.2, .22, m["metal"])
        add_box(col, "construction_fence_post", .13, .13, 2.0, x, 16.2, .22, m["metal"])
    for y in range(-16, 17, 4):
        for x in (-16.2, 16.2):
            add_box(col, "construction_fence_post", .13, .13, 2.0, x, y, .22, m["metal"])
    for y in (-16.2, 16.2):
        for x in range(-14, 15, 4):
            if y > 0 or abs(x) > 4:
                add_box(col, "construction_fence_panel", 3.75, .08, 1.35, x, y, .48, orange)
    for x in (-16.2, 16.2):
        for y in range(-14, 15, 4):
            add_box(col, "construction_fence_panel", .08, 3.75, 1.35, x, y, .48, orange)
    for x in (-5.2, -2.6, 2.6, 5.2):
        add_ngon_cone(col, "construction_cone", .34, .06, .82, 8,
                      x, -15.0, .22, safety)
    # Front-facing vote board is the human-readable purpose of the site.
    add_box(col, "construction_vote_board", 10.5, .48, 4.2, 0, -12.3, .38, dark)
    add_box(col, "construction_vote_face", 9.7, .12, 3.45, 0, -12.58, .72, orange)
    add_text(col, "construction_vote_title", "YOU DECIDE", .82, .045,
             0, -12.72, 3.18, safety)
    add_text(col, "construction_vote_subtitle", "WHAT RISES NEXT?", .42, .035,
             0, -12.72, 2.0, safety)
    _merge_asset_meshes(col, "construction_zone_batched")


def build_movie_theater(col, seed):
    """Followville Cinema: a full-block, front-readable Art Deco movie palace.

    The building faces local -Y.  Its public forecourt shares one 0.22m top
    plane so the browser can treat the whole civic pad as a walk surface.
    """
    rng = random.Random(seed)
    burgundy = mat("NB_cinema_burgundy", (.31, .045, .075), .72)
    burgundy_hi = mat("NB_cinema_burgundy_hi", (.50, .075, .105), .62)
    midnight = mat("NB_cinema_midnight", (.035, .055, .095), .62, .08)
    charcoal = mat("NB_cinema_charcoal", (.075, .075, .085), .76)
    cream = mat("NB_cinema_cream", (.88, .80, .66), .82)
    stone = mat("NB_cinema_stone", (.54, .51, .47), .94)
    brass = mat("NB_cinema_brass", (.72, .47, .13), .34, .68)
    gold = mat("NB_cinema_gold", (1.0, .65, .13), .32, .28)
    glass = mat("NB_cinema_glass", (.10, .30, .44), .12, .12, .88, .08, .66)
    glass_dark = mat("NB_cinema_glass_dark", (.025, .095, .15), .10, .18, .94, .12, .72)
    warm = mat("NB_cinema_warm_light", (1.0, .72, .30), .22)
    red = mat("NB_cinema_velvet", (.48, .025, .045), .78)
    poster_mats = [
        mat("NB_cinema_poster_teal", (.06, .47, .54), .56),
        mat("NB_cinema_poster_coral", (.82, .20, .14), .58),
        mat("NB_cinema_poster_violet", (.31, .12, .55), .54),
        mat("NB_cinema_poster_gold", (.93, .55, .08), .58),
    ]

    WALK_TOP = .22
    # Paved forecourt and side service apron; all top faces are separated.
    add_box(col, "cinema_block_pad", 33.8, 33.8, WALK_TOP, 0, 0, 0, stone)
    add_box(col, "cinema_forecourt", 28.8, 8.2, .035, 0, -12.4,
            WALK_TOP, cream)
    for x in (-10.8, -7.2, -3.6, 0, 3.6, 7.2, 10.8):
        add_box(col, "cinema_forecourt_inlay", .10, 7.6, .018, x, -12.4,
                WALK_TOP + .035, brass)
    add_box(col, "cinema_entry_carpet", 6.8, 6.1, .025, 0, -11.5,
            WALK_TOP + .055, red)

    # Auditorium masses step upward toward the rear for a convincing drone
    # silhouette.  The central lobby tower gives the front a strong landmark.
    add_box(col, "cinema_auditorium_left", 11.8, 19.0, 9.8, -8.0, 3.6,
            WALK_TOP, burgundy)
    add_box(col, "cinema_auditorium_right", 11.8, 19.0, 9.8, 8.0, 3.6,
            WALK_TOP, burgundy)
    add_box(col, "cinema_rear_flytower", 25.0, 6.8, 13.5, 0, 9.8,
            WALK_TOP, midnight)
    # Rear articulation matters in downtown drone passes: relief frames,
    # service doors and vents prevent the flytower reading as an empty cube.
    for x in (-9.8, -6.5, -3.25, 0, 3.25, 6.5, 9.8):
        add_box(col, "cinema_rear_rib", .34, .38, 11.6, x, 13.34,
                WALK_TOP + .8, brass if x in (-9.8, 9.8) else stone)
    for x in (-6.2, 6.2):
        add_box(col, "cinema_rear_exit", 2.25, .30, 3.2, x, 13.42,
                WALK_TOP + .12, burgundy_hi)
        add_box(col, "cinema_rear_exit_bar", 1.5, .12, .13, x, 13.61,
                WALK_TOP + 1.55, brass)
    for x in (-3.0, 0, 3.0):
        add_box(col, "cinema_rear_vent", 1.9, .24, 1.15, x, 13.48,
                WALK_TOP + 7.8, charcoal)
        for z in (8.05, 8.35, 8.65):
            add_box(col, "cinema_rear_vent_louver", 1.55, .10, .08, x, 13.63,
                    WALK_TOP + z, stone)
    add_box(col, "cinema_lobby_core", 11.6, 12.8, 13.9, 0, -1.0,
            WALK_TOP, cream)
    add_box(col, "cinema_lobby_crown", 9.2, 10.8, 3.0, 0, .1,
            WALK_TOP + 13.9, burgundy_hi)
    add_box(col, "cinema_crown_cap", 9.9, 11.4, .42, 0, .1,
            WALK_TOP + 16.9, brass)

    # Art Deco stepping, pilasters, and vertical fins hold up at street and
    # aerial distance without becoming surface noise.
    for x in (-13.1, -10.7, -5.8, 5.8, 10.7, 13.1):
        height = 10.8 if abs(x) < 7 else 9.2
        add_box(col, "cinema_front_pilaster", .55, .70, height, x, -6.25,
                WALK_TOP, cream)
        add_box(col, "cinema_pilaster_cap", .85, .92, .34, x, -6.37,
                WALK_TOP + height, brass)
    for x, height in ((-3.8, 14.8), (-2.45, 16.0), (0, 17.8),
                      (2.45, 16.0), (3.8, 14.8)):
        add_box(col, "cinema_deco_fin", .48, .62, height, x, -7.18,
                WALK_TOP + 1.0, brass)

    # Two-storey glazed lobby with visible warm interior bands.
    add_box(col, "cinema_lobby_glass", 10.4, .28, 10.1, 0, -7.48,
            WALK_TOP + 1.0, glass)
    add_box(col, "cinema_lobby_glow", 9.8, .18, 3.8, 0, -7.22,
            WALK_TOP + 1.2, warm)
    for x in (-5.0, -2.5, 0, 2.5, 5.0):
        add_box(col, "cinema_lobby_mullion", .16, .36, 10.2, x, -7.58,
                WALK_TOP + .95, brass)
    for z in (4.6, 8.0, 11.2):
        add_box(col, "cinema_lobby_transom", 10.6, .38, .17, 0, -7.60,
                WALK_TOP + z, brass)
    # Four real entrance doors and handles.
    for x in (-3.75, -1.25, 1.25, 3.75):
        add_box(col, "cinema_entry_door", 2.05, .22, 3.3, x, -7.72,
                WALK_TOP + .10, glass_dark)
        add_box(col, "cinema_door_handle", .07, .16, .75,
                x + (-.42 if x < 0 else .42), -7.88, WALK_TOP + 1.35, brass)

    # Deep cantilevered marquee is the visual anchor of the final shot.
    add_box(col, "cinema_marquee", 24.0, 5.3, .66, 0, -9.7,
            WALK_TOP + 6.1, midnight)
    add_box(col, "cinema_marquee_face", 23.6, .42, 2.25, 0, -12.20,
            WALK_TOP + 5.25, burgundy_hi)
    add_box(col, "cinema_marquee_top_trim", 24.4, .48, .22, 0, -12.28,
            WALK_TOP + 7.35, brass)
    add_box(col, "cinema_marquee_bottom_trim", 24.4, .48, .22, 0, -12.28,
            WALK_TOP + 5.10, brass)
    for x in [(-10.7 + i * 1.07) for i in range(21)]:
        add_ngon_cone(col, "cinema_marquee_bulb", .10, .10, .10, 10,
                      x, -12.55, WALK_TOP + 5.36, warm)
    _add_followmart_text(col, "NOW SHOWING", 1.18, 0, -12.56,
                         WALK_TOP + 6.2, cream, extrude=.10, bevel=.014)

    # Tower sign and medallion establish a unique civic identity.
    add_box(col, "cinema_tower_sign", 8.6, .52, 3.8, 0, -7.63,
            WALK_TOP + 11.15, midnight)
    _add_followmart_text(col, "FOLLOWVILLE", 1.0, 0, -7.98,
                         WALK_TOP + 13.45, gold, extrude=.12, bevel=.018)
    _add_followmart_text(col, "CINEMA", 1.62, 0, -8.01,
                         WALK_TOP + 11.70, cream, extrude=.13, bevel=.020)
    add_ngon_cone(col, "cinema_crown_medallion", 1.22, 1.22, .28, 20,
                  0, -7.82, WALK_TOP + 16.0, brass, rot=math.pi/20)

    # Ticket windows and four illuminated poster cases flank the entry.
    for side in (-1, 1):
        tx = side * 7.2
        add_box(col, "cinema_ticket_frame", 3.15, .48, 3.0, tx, -7.52,
                WALK_TOP + .75, brass)
        add_box(col, "cinema_ticket_glass", 2.62, .20, 2.42, tx, -7.82,
                WALK_TOP + 1.02, glass_dark)
        add_box(col, "cinema_ticket_counter", 3.35, .72, .25, tx, -8.02,
                WALK_TOP + 1.15, cream)
    for index, x in enumerate((-12.2, -9.7, 9.7, 12.2)):
        add_box(col, "cinema_poster_case", 2.05, .44, 3.35, x, -6.62,
                WALK_TOP + 1.0, brass)
        add_box(col, "cinema_poster", 1.65, .18, 2.92, x, -6.89,
                WALK_TOP + 1.22, poster_mats[index])
        add_box(col, "cinema_poster_title", 1.25, .08, .14, x, -7.00,
                WALK_TOP + 3.35, cream)

    # Street furniture gives the facade believable pedestrian scale.
    for x in (-11.8, -8.4, 8.4, 11.8):
        add_ngon_cone(col, "cinema_bollard", .16, .13, .95, 10, x, -10.8,
                      WALK_TOP + .06, brass)
    for x in (-13.0, 13.0):
        add_box(col, "cinema_bench_seat", 2.8, .62, .18, x, -13.4,
                WALK_TOP + .48, cream)
        add_box(col, "cinema_bench_back", 2.8, .16, .85, x, -13.1,
                WALK_TOP + .58, midnight)
        for lx in (x - 1.05, x + 1.05):
            add_box(col, "cinema_bench_leg", .15, .45, .48, lx, -13.4,
                    WALK_TOP + .06, brass)

    # Roofline detail keeps the building authored from the drone perspective.
    for x, y, w, d in ((-7.0, 5.8, 3.4, 2.2), (7.0, 5.8, 3.4, 2.2)):
        add_box(col, "cinema_roof_screen", w + .5, d + .5, 1.15, x, y,
                WALK_TOP + 10.0, midnight)
        add_box(col, "cinema_hvac", w, d, .85, x, y,
                WALK_TOP + 10.15, charcoal)
    # Flytower roof equipment sits above its actual 13.72m roof instead of
    # disappearing inside it, and a parapet gives the top a finished edge.
    add_box(col, "cinema_flytower_parapet_front", 25.5, .42, .85, 0, 6.45,
            WALK_TOP + 13.5, burgundy_hi)
    add_box(col, "cinema_flytower_parapet_rear", 25.5, .42, .85, 0, 13.15,
            WALK_TOP + 13.5, burgundy_hi)
    for x in (-11.9, 11.9):
        add_box(col, "cinema_flytower_parapet_side", .42, 6.4, .85, x, 9.8,
                WALK_TOP + 13.5, burgundy_hi)
    for x in (-6.2, 0, 6.2):
        add_box(col, "cinema_roof_screen", 3.8, 2.7, 1.35, x, 9.8,
                WALK_TOP + 13.5, stone)
        add_box(col, "cinema_hvac", 3.15, 2.15, .85, x, 9.8,
                WALK_TOP + 13.75, charcoal)
        add_box(col, "cinema_hvac_fan", 1.25, 1.25, .12, x, 9.8,
                WALK_TOP + 14.62, brass)
    for y in (-2.0, 3.0, 8.0):
        add_box(col, "cinema_side_belt_l", .22, 3.4, .28, -14.02, y,
                WALK_TOP + 6.6, brass)
        add_box(col, "cinema_side_belt_r", .22, 3.4, .28, 14.02, y,
                WALK_TOP + 6.6, brass)
    _merge_asset_meshes(col, "movie_theater_batched")


def build_followville_arcade(col, seed):
    """Three-level urban arcade for the unclaimed seed-129 downtown parcel.

    The public frontage faces local -Y.  The shell is deliberately open behind
    the glazing, so the cabinet floor is real visible geometry rather than a
    picture pasted onto an opaque facade.  All facade layers have at least 5cm
    of physical separation from their support planes.
    """
    rng = random.Random(seed)
    navy = mat("NB_arcade_navy", (.035, .065, .13), .62)
    navy_hi = mat("NB_arcade_navy_hi", (.07, .13, .23), .52)
    brick = mat("NB_arcade_brick", (.31, .105, .095), .86)
    cream = mat("NB_arcade_cream", (.82, .73, .57), .82)
    charcoal = mat("NB_arcade_charcoal", (.055, .06, .075), .68)
    brass = mat("NB_arcade_brass", (.72, .43, .12), .34, .62)
    pavement = mat("NB_arcade_pavement", (.48, .47, .44), .96)
    floor = mat("NB_arcade_floor", (.075, .085, .11), .48)
    glass = mat("NB_arcade_glass", (.045, .22, .31), .10, .08, .42, .48, .72)
    glass_dark = mat("NB_arcade_glass_dark", (.018, .075, .12), .12, .12,
                     .58, .34, .70)
    magenta = mat_emissive("NB_arcade_magenta", (.95, .055, .42), .26, 5.0)
    cyan = mat_emissive("NB_arcade_cyan", (.02, .78, .92), .24, 4.6)
    gold = mat_emissive("NB_arcade_gold", (1.0, .55, .08), .30, 3.8)
    warm = mat_emissive("NB_arcade_warm", (1.0, .58, .22), .30, 2.8)
    screen_mats = (
        mat_emissive("NB_arcade_screen_cyan", (.025, .58, .78), .20, 2.8),
        mat_emissive("NB_arcade_screen_pink", (.88, .035, .32), .20, 2.8),
        mat_emissive("NB_arcade_screen_gold", (.95, .48, .035), .20, 2.6),
        mat_emissive("NB_arcade_screen_green", (.08, .72, .38), .20, 2.5),
    )
    foliage = mat("NB_arcade_foliage", (.18, .42, .22), .96)
    soil = mat("NB_arcade_soil", (.18, .10, .055), 1.0)

    PAD_TOP = .18
    SHELL_FRONT = -4.78
    # One-lot civic-quality ground interface, with a distinct flush approach.
    add_box(col, "arcade_lot_pad", 12.35, 12.35, PAD_TOP, 0, 0, 0, pavement)
    add_box(col, "arcade_entry_inlay", 5.6, 1.62, .025, 0, -5.28,
            PAD_TOP, navy)
    for x in (-2.35, -1.18, 0, 1.18, 2.35):
        add_box(col, "arcade_entry_inlay_bar", .055, 1.46, .018, x, -5.28,
                PAD_TOP + .025, brass)

    # Real ground-floor room.  Nothing opaque sits behind the storefront.
    add_box(col, "arcade_ground_floor", 9.55, 9.35, .16, 0, -.12,
            PAD_TOP, floor)
    add_box(col, "arcade_ground_rear", 10.15, .46, 4.05, 0, 4.34,
            PAD_TOP + .16, brick)
    add_box(col, "arcade_ground_left", .50, 9.05, 4.05, -4.83, -.12,
            PAD_TOP + .16, brick)
    add_box(col, "arcade_ground_right", .50, 9.05, 4.05, 4.83, -.12,
            PAD_TOP + .16, brick)
    add_box(col, "arcade_ground_ceiling", 9.65, 8.95, .22, 0, -.05,
            PAD_TOP + 4.21, charcoal)

    # Upper stories step backward and sideways instead of forming a plain box.
    add_box(col, "arcade_upper_main", 9.75, 8.65, 7.15, -.12, .18,
            PAD_TOP + 4.43, navy)
    add_box(col, "arcade_upper_step", 6.65, 7.65, 2.25, -1.45, .52,
            PAD_TOP + 11.58, navy_hi)
    add_box(col, "arcade_sign_tower", 3.15, 6.9, 4.75, -2.42, .38,
            PAD_TOP + 10.62, brick)
    add_box(col, "arcade_tower_cap", 3.72, 7.25, .38, -2.42, .38,
            PAD_TOP + 15.37, brass)
    add_box(col, "arcade_roof_crown", 5.20, 2.30, 1.15, .85, .60,
            PAD_TOP + 13.83, charcoal)
    # Offset fins make a skyline-readable controller / equalizer crown.
    for index, (x, h, material) in enumerate((
            (-1.35, 2.00, magenta), (-.55, 2.85, cyan),
            (.30, 3.65, gold), (1.15, 2.65, cyan), (2.0, 1.80, magenta))):
        add_box(col, "arcade_crown_fin_%d" % index, .30, .44, h, x, -.42,
                PAD_TOP + 14.40, material)
    add_box(col, "arcade_crown_beam", 4.10, .48, .28, .32, -.43,
            PAD_TOP + 14.15, brass)

    # Two-storey front composition: recessed portal plus large reveal windows.
    add_box(col, "arcade_front_left_pier", 1.28, .56, 4.08, -4.23,
            SHELL_FRONT, PAD_TOP + .16, brick)
    add_box(col, "arcade_front_right_pier", 1.28, .56, 4.08, 4.23,
            SHELL_FRONT, PAD_TOP + .16, brick)
    add_box(col, "arcade_front_lintel", 7.40, .56, .48, 0, SHELL_FRONT,
            PAD_TOP + 3.76, cream)
    add_box(col, "arcade_storefront_glass", 7.15, .12, 3.43, 0,
            SHELL_FRONT - .35, PAD_TOP + .28, glass)
    for x in (-3.55, -1.72, 0, 1.72, 3.55):
        add_box(col, "arcade_storefront_mullion", .13, .20, 3.56, x,
                SHELL_FRONT - .44, PAD_TOP + .22, brass)
    add_box(col, "arcade_storefront_transom", 7.20, .20, .13, 0,
            SHELL_FRONT - .44, PAD_TOP + 2.92, brass)

    # Deep entrance portal and actual paired glazed doors.
    add_box(col, "arcade_portal_left", .48, 1.15, 3.62, -1.42, -5.03,
            PAD_TOP + .20, cream)
    add_box(col, "arcade_portal_right", .48, 1.15, 3.62, 1.42, -5.03,
            PAD_TOP + .20, cream)
    add_box(col, "arcade_portal_head", 3.32, 1.15, .48, 0, -5.03,
            PAD_TOP + 3.34, cream)
    for x in (-.68, .68):
        add_box(col, "arcade_entry_door", 1.16, .12, 3.05, x, -5.39,
                PAD_TOP + .24, glass_dark)
        add_box(col, "arcade_door_handle", .065, .17, .78,
                x + (-.28 if x < 0 else .28), -5.50, PAD_TOP + 1.25, brass)

    # Angled marquee projects far enough to own entrance push-in shots.
    add_tapered_box(col, "arcade_marquee", 8.65, 1.95, 7.65, 1.18,
                    .62, 0, -5.20, PAD_TOP + 3.92, 0, -.16, navy_hi)
    add_box(col, "arcade_marquee_edge", 8.10, .18, .44, 0, -6.02,
            PAD_TOP + 4.12, magenta)
    for x in (-3.35, -2.25, -1.15, 0, 1.15, 2.25, 3.35):
        add_ngon_cone(col, "arcade_marquee_bulb", .09, .09, .10, 8, x,
                      -6.09, PAD_TOP + 4.25, warm)

    # Exact, restrained branding integrated into the architecture.
    add_box(col, "arcade_main_sign_back", 8.72, .30, 2.28, .35, -4.83,
            PAD_TOP + 7.98, charcoal)
    add_text(col, "arcade_followville_text", "FOLLOWVILLE", .72, .055,
             .35, -5.03, PAD_TOP + 9.48, gold)
    add_text(col, "arcade_arcade_text", "ARCADE", 1.42, .075,
             .35, -5.05, PAD_TOP + 8.42, cyan)
    # Side blade reads on the long east approach without duplicating branding.
    add_box(col, "arcade_blade_back", .42, 2.55, 5.10, 5.18, -2.15,
            PAD_TOP + 6.25, charcoal)
    add_text(col, "arcade_blade_text", "ARCADE", .62, .055, 5.42, -2.15,
             PAD_TOP + 8.80, magenta, rotation=(math.pi / 2, 0, math.pi / 2))

    # Upper glazing and fins supply parallax from both oblique sides.
    for floor_z in (5.10, 8.05):
        for x in (-3.18, -.94, 1.30, 3.54):
            add_box(col, "arcade_upper_window_frame", 1.68, .28, 2.18, x,
                    -4.23, PAD_TOP + floor_z, cream)
            add_box(col, "arcade_upper_window", 1.36, .12, 1.84, x,
                    -4.42, PAD_TOP + floor_z + .18, glass_dark)
    for x in (-4.65, 4.52):
        add_box(col, "arcade_vertical_light", .16, .23, 6.85, x, -4.56,
                PAD_TOP + 4.62, magenta if x < 0 else cyan)
    for y in (-2.55, .10, 2.75):
        add_box(col, "arcade_side_window_frame", .30, 1.72, 1.95, 4.82, y,
                PAD_TOP + 5.35, cream)
        add_box(col, "arcade_side_window", .14, 1.40, 1.62, 5.02, y,
                PAD_TOP + 5.52, glass_dark)

    # Detailed visible interior: varied machine families still leave a 2.6m
    # camera aisle. Helpers rotate every component as one authored machine.
    def machine_box(name, w, d, h, x, y, z, material, rot=0.0,
                    local_x=0.0, local_y=0.0):
        wx = x + local_x * math.cos(rot) - local_y * math.sin(rot)
        wy = y + local_x * math.sin(rot) + local_y * math.cos(rot)
        obj = add_box(col, name, w, d, h, wx, wy, z, material)
        obj.rotation_euler[2] = rot
        return obj

    def upright_cabinet(index, x, y, rot):
        body_mat = (navy_hi, brick, charcoal)[index % 3]
        machine_box("arcade_cabinet_body", .88, .92, 1.52, x, y,
                    PAD_TOP + .20, body_mat, rot)
        hood = add_tapered_box(col, "arcade_cabinet_hood", .92, .82, .86, .58,
                               .82, x, y, PAD_TOP + 1.72, 0, -.10, body_mat)
        hood.rotation_euler[2] = rot
        # Screen and controls sit 6cm proud of the cabinet face.
        machine_box("arcade_cabinet_screen", .62, .08, .60, x, y,
                    PAD_TOP + 2.08, screen_mats[index % 4], rot,
                    local_y=-.47)
        machine_box("arcade_cabinet_controls", .76, .36, .13, x, y,
                    PAD_TOP + 1.58, brass, rot, local_y=-.40)
        for local_x, material in ((-.18, magenta), (.18, cyan)):
            machine_box("arcade_cabinet_button", .12, .12, .07, x, y,
                        PAD_TOP + 1.71, material, rot, local_x, -.53)

    def claw_machine(index, x, y, rot):
        body_mat = (navy_hi, brick)[index % 2]
        machine_box("arcade_claw_base", .96, .88, .72, x, y,
                    PAD_TOP + .20, body_mat, rot)
        machine_box("arcade_claw_glass", .88, .76, 1.22, x, y,
                    PAD_TOP + .92, glass, rot)
        machine_box("arcade_claw_header", 1.00, .88, .28, x, y,
                    PAD_TOP + 2.14, screen_mats[index % 4], rot)
        machine_box("arcade_claw_control", .74, .28, .15, x, y,
                    PAD_TOP + .78, brass, rot, local_y=-.48)
        # A real hanging claw and a small pile of distinct prizes.
        machine_box("arcade_claw_rail", .62, .08, .08, x, y,
                    PAD_TOP + 1.95, charcoal, rot)
        machine_box("arcade_claw_cable", .035, .035, .42, x, y,
                    PAD_TOP + 1.55, brass, rot, local_x=.12)
        for prize_index, (local_x, local_y, material) in enumerate((
                (-.24, -.12, magenta), (.08, .04, cyan),
                (.27, -.18, gold), (-.05, .22, warm))):
            machine_box("arcade_claw_prize_%d" % prize_index, .22, .20,
                        .18 + .04 * (prize_index % 2), x, y, PAD_TOP + .98,
                        material, rot, local_x, local_y)

    def pinball_machine(index, x, y, rot):
        body_mat = (brick, navy_hi)[index % 2]
        machine_box("arcade_pinball_pedestal", .58, .58, .72, x, y,
                    PAD_TOP + .20, body_mat, rot, local_y=.18)
        table = machine_box("arcade_pinball_table", .82, 1.18, .18, x, y,
                            PAD_TOP + .94, charcoal, rot, local_y=-.12)
        table.rotation_euler[0] = math.radians(-7)
        machine_box("arcade_pinball_playfield", .66, .88, .08, x, y,
                    PAD_TOP + 1.10, screen_mats[index % 4], rot,
                    local_y=-.23)
        machine_box("arcade_pinball_backbox", .80, .22, .72, x, y,
                    PAD_TOP + 1.18, body_mat, rot, local_y=.48)
        machine_box("arcade_pinball_score", .60, .08, .38, x, y,
                    PAD_TOP + 1.42, screen_mats[(index + 1) % 4], rot,
                    local_y=.62)
        for local_x in (-.22, .22):
            machine_box("arcade_pinball_leg", .07, .07, .82, x, y,
                        PAD_TOP + .20, brass, rot, local_x, -.38)

    def racing_machine(index, x, y, rot):
        body_mat = (charcoal, navy_hi)[index % 2]
        machine_box("arcade_racer_console", .96, .78, 1.42, x, y,
                    PAD_TOP + .20, body_mat, rot, local_y=-.16)
        machine_box("arcade_racer_screen", .72, .08, .62, x, y,
                    PAD_TOP + 1.36, screen_mats[index % 4], rot,
                    local_y=-.58)
        # Low-poly steering wheel, column, pedals and bucket seat.
        wheel = add_ngon_cone(col, "arcade_racer_wheel", .25, .25, .08, 10,
                              x + math.sin(rot) * .67,
                              y - math.cos(rot) * .67,
                              PAD_TOP + 1.06, brass)
        wheel.rotation_euler = (math.pi / 2, 0, rot)
        machine_box("arcade_racer_column", .09, .36, .09, x, y,
                    PAD_TOP + .91, brass, rot, local_y=-.54)
        machine_box("arcade_racer_seat", .72, .62, .62, x, y,
                    PAD_TOP + .20, brick, rot, local_y=.72)
        machine_box("arcade_racer_seat_back", .72, .18, 1.02, x, y,
                    PAD_TOP + .38, brick, rot, local_y=1.00)
        for local_x in (-.20, .20):
            machine_box("arcade_racer_pedal", .15, .25, .05, x, y,
                        PAD_TOP + .25, brass, rot, local_x, -.62)

    def rhythm_machine(index, x, y, rot):
        body_mat = (navy_hi, brick)[index % 2]
        machine_box("arcade_rhythm_tower", .92, .72, 1.82, x, y,
                    PAD_TOP + .20, body_mat, rot, local_y=.12)
        machine_box("arcade_rhythm_screen", .68, .08, .70, x, y,
                    PAD_TOP + 1.10, screen_mats[index % 4], rot,
                    local_y=-.28)
        machine_box("arcade_rhythm_marquee", .98, .18, .30, x, y,
                    PAD_TOP + 2.02, magenta, rot, local_y=.02)
        # Two speaker discs and a four-zone illuminated dance pad.
        for local_x in (-.25, .25):
            speaker = add_ngon_cone(
                col, "arcade_rhythm_speaker", .14, .14, .07, 10,
                x + local_x * math.cos(rot) + math.sin(rot) * .30,
                y + local_x * math.sin(rot) - math.cos(rot) * .30,
                PAD_TOP + .72, charcoal)
            speaker.rotation_euler = (math.pi / 2, 0, rot)
        machine_box("arcade_rhythm_pad_base", 1.08, .92, .10, x, y,
                    PAD_TOP + .20, charcoal, rot, local_y=-.76)
        for local_x, local_y, material in ((-.27, -.98, cyan),
                                             (.27, -.98, magenta),
                                             (-.27, -.57, gold),
                                             (.27, -.57, cyan)):
            machine_box("arcade_rhythm_pad", .42, .34, .035, x, y,
                        PAD_TOP + .30, material, rot, local_x, local_y)
        for local_x in (-.45, .45):
            machine_box("arcade_rhythm_rail", .08, .08, 1.05, x, y,
                        PAD_TOP + .30, brass, rot, local_x, -.24)
        machine_box("arcade_rhythm_rail_top", .98, .08, .08, x, y,
                    PAD_TOP + 1.28, brass, rot, local_y=-.24)

    def machine(index, x, y, rot, kind="upright"):
        if kind == "claw":
            claw_machine(index, x, y, rot)
        elif kind == "pinball":
            pinball_machine(index, x, y, rot)
        elif kind == "racer":
            racing_machine(index, x, y, rot)
        elif kind == "rhythm":
            rhythm_machine(index, x, y, rot)
        else:
            upright_cabinet(index, x, y, rot)

    left_kinds = ("upright", "claw", "rhythm", "pinball", "upright")
    right_kinds = ("racer", "upright", "claw", "rhythm", "pinball")
    for index, y in enumerate((-2.65, -1.15, .35, 1.85, 3.32)):
        machine(index, -3.12, y, math.pi / 2, left_kinds[index])
        machine(index + 5, 3.12, y, -math.pi / 2, right_kinds[index])

    # Custom redemption table replaces the old flat back-wall display. Every
    # prize is modeled in 3D and readable from the entrance camera path.
    add_box(col, "arcade_prize_table_top", 5.45, 1.02, .20, 0, 3.45,
            PAD_TOP + 1.02, cream)
    add_box(col, "arcade_prize_table_apron", 5.10, .20, .42, 0, 2.99,
            PAD_TOP + .74, navy_hi)
    add_box(col, "arcade_prize_table_shelf", 4.78, .76, .14, 0, 3.48,
            PAD_TOP + .42, brick)
    for x in (-2.22, 2.22):
        for y in (3.12, 3.78):
            add_box(col, "arcade_prize_table_leg", .18, .18, .88, x, y,
                    PAD_TOP + .14, brass)
    add_box(col, "arcade_prize_header", 5.60, .18, .86, 0, 4.06,
            PAD_TOP + 2.92, charcoal)
    add_text(col, "arcade_prize_vault_text", "PRIZE VAULT", .38, .035,
             0, 3.93, PAD_TOP + 3.36, gold)

    prize_z = PAD_TOP + 1.24
    # Faceted ball.
    add_uv_sphere(col, "arcade_prize_ball", .34, -2.02, 3.36,
                  prize_z + .34, magenta, rings=6, segments=8)
    # Trophy with stepped base, stem, open-looking cup and handles.
    add_box(col, "arcade_prize_trophy_base", .52, .38, .16, -1.10, 3.36,
            prize_z, brass)
    add_ngon_cone(col, "arcade_prize_trophy_stem", .10, .10, .34, 8,
                  -1.10, 3.36, prize_z + .16, gold)
    add_ngon_cone(col, "arcade_prize_trophy_cup", .18, .38, .42, 8,
                  -1.10, 3.36, prize_z + .50, gold)
    for x in (-1.48, -.72):
        add_box(col, "arcade_prize_trophy_handle", .18, .10, .20, x, 3.36,
                prize_z + .60, brass)
    # Rocket with contrasting nose and fins.
    add_ngon_cone(col, "arcade_prize_rocket_body", .20, .18, .68, 8,
                  -.20, 3.36, prize_z, cyan)
    add_ngon_cone(col, "arcade_prize_rocket_nose", .20, 0, .30, 8,
                  -.20, 3.36, prize_z + .68, magenta)
    for x in (-.42, .02):
        add_box(col, "arcade_prize_rocket_fin", .18, .10, .26, x, 3.36,
                prize_z, gold)
    # Toy car with a raised cabin and four low-poly wheels.
    add_box(col, "arcade_prize_car_body", .78, .42, .24, .78, 3.36,
            prize_z + .12, brick)
    add_tapered_box(col, "arcade_prize_car_cabin", .42, .34, .30, .28, .24,
                    .78, 3.36, prize_z + .36, 0, 0, glass_dark)
    for x in (.48, 1.08):
        for y in (3.12, 3.60):
            wheel = add_ngon_cone(col, "arcade_prize_car_wheel", .12, .12,
                                  .10, 8, x, y, prize_z + .10, charcoal)
            wheel.rotation_euler[0] = math.pi / 2
    # Small robot/plush prize with a distinct face, antenna and blocky feet.
    add_box(col, "arcade_prize_robot_body", .48, .34, .48, 1.75, 3.36,
            prize_z + .12, navy_hi)
    add_box(col, "arcade_prize_robot_head", .60, .42, .46, 1.75, 3.36,
            prize_z + .60, cream)
    for x in (1.60, 1.90):
        add_box(col, "arcade_prize_robot_eye", .10, .08, .10, x, 3.05,
                prize_z + .80, cyan)
    add_box(col, "arcade_prize_robot_mouth", .25, .07, .06, 1.75, 3.05,
            prize_z + .68, magenta)
    add_box(col, "arcade_prize_robot_antenna", .05, .05, .30, 1.75, 3.36,
            prize_z + 1.06, brass)
    add_uv_sphere(col, "arcade_prize_robot_tip", .09, 1.75, 3.36,
                  prize_z + 1.40, gold, rings=5, segments=8)
    for x in (1.58, 1.92):
        add_box(col, "arcade_prize_robot_foot", .22, .38, .14, x, 3.36,
                prize_z, brick)
    for x, material in ((-.72, cyan), (0, gold), (.72, magenta)):
        add_box(col, "arcade_aisle_strip", .10, 5.35, .018, x, -.38,
                PAD_TOP + .17, material)
    # Change kiosk, ticket checker and low-poly wall graphics make the room
    # operational rather than a row of props.
    add_box(col, "arcade_change_kiosk", .72, .54, 1.42, -4.18, -3.10,
            PAD_TOP + .20, cream)
    add_box(col, "arcade_change_screen", .50, .08, .42, -4.18, -3.42,
            PAD_TOP + 1.12, cyan)
    add_box(col, "arcade_change_slot", .28, .08, .07, -4.18, -3.43,
            PAD_TOP + .72, charcoal)
    add_box(col, "arcade_ticket_checker", .48, .44, 1.02, 4.25, -3.30,
            PAD_TOP + .20, navy_hi)
    add_box(col, "arcade_ticket_glow", .34, .08, .24, 4.25, -3.56,
            PAD_TOP + .85, magenta)
    for side in (-1, 1):
        wall_x = side * 4.54
        for index, (wall_y, z, material) in enumerate((
                (-1.55, 2.72, cyan), (-.88, 2.18, magenta),
                (-.20, 2.84, gold), (.48, 2.30, cyan), (1.16, 2.72, magenta))):
            add_box(col, "arcade_wall_pixel_%d" % index, .08, .46, .42,
                    wall_x, wall_y, PAD_TOP + z, material)
    # Ceiling baffles and light bars give the room a finished acoustic grid.
    for x in (-3.55, -2.40, 2.40, 3.55):
        add_box(col, "arcade_ceiling_baffle", .18, 7.15, .28, x, .18,
                PAD_TOP + 3.78, navy_hi)
    for y in (-2.45, -.55, 1.35, 3.18):
        add_box(col, "arcade_ceiling_light", 2.25, .16, .075, 0, y,
                PAD_TOP + 4.02, cyan if int((y + 3) * 10) % 2 else magenta)

    # Street-scale details stay inside the parcel and preserve the clear portal.
    for x in (-4.75, 4.75):
        add_box(col, "arcade_planter", 1.35, .95, .58, x, -5.30,
                PAD_TOP + .02, navy_hi)
        add_box(col, "arcade_planter_soil", 1.15, .75, .12, x, -5.30,
                PAD_TOP + .58, soil)
        for offset in (-.34, 0, .34):
            add_ngon_cone(col, "arcade_planter_leaf", .30, .10,
                          .72 + rng.uniform(-.08, .10), 7, x + offset,
                          -5.30 + rng.uniform(-.14, .14), PAD_TOP + .68, foliage,
                          rot=rng.random() * math.tau)
    # Bike hoops and a short bench occupy the quieter east edge.
    for y in (-4.30, -3.45):
        for x in (4.92, 5.62):
            add_box(col, "arcade_bike_rack_post", .10, .10, .82, x, y,
                    PAD_TOP + .04, brass)
        add_box(col, "arcade_bike_rack_top", .80, .10, .10, 5.27, y,
                PAD_TOP + .81, brass)
    add_box(col, "arcade_bench_seat", 2.20, .58, .17, -4.62, -3.78,
            PAD_TOP + .46, cream)
    add_box(col, "arcade_bench_back", 2.20, .16, .82, -4.62, -3.50,
            PAD_TOP + .53, navy)
    for x in (-5.40, -3.84):
        add_box(col, "arcade_bench_leg", .14, .42, .48, x, -3.78,
                PAD_TOP + .04, brass)

    # Screened roof plant gives overhead views an authored, believable finish.
    add_box(col, "arcade_roof_screen_front", 4.25, .20, 1.20, 1.75, 2.12,
            PAD_TOP + 11.58, navy_hi)
    add_box(col, "arcade_roof_screen_rear", 4.25, .20, 1.20, 1.75, 4.05,
            PAD_TOP + 11.58, navy_hi)
    for x in (-.27, 3.77):
        add_box(col, "arcade_roof_screen_side", .20, 1.72, 1.20, x, 3.08,
                PAD_TOP + 11.58, navy_hi)
    for x in (.70, 2.80):
        add_box(col, "arcade_hvac", 1.35, 1.28, .72, x, 3.05,
                PAD_TOP + 11.60, charcoal)
        add_ngon_cone(col, "arcade_hvac_fan", .42, .42, .08, 10, x, 3.05,
                      PAD_TOP + 12.33, brass)

    # Four practicals are enough for the entrance and interior, and remain
    # cheap compared with the town's capped render-only streetlight pools.
    for index, (x, y, z, energy, color) in enumerate((
            (-2.0, -1.0, 3.55, 95, (1.0, .18, .46)),
            (2.0, 1.65, 3.55, 95, (.08, .70, 1.0)),
            (-3.55, -5.18, 3.30, 70, (1.0, .44, .12)),
            (3.55, -5.18, 3.30, 70, (.10, .65, 1.0)))):
        data = bpy.data.lights.new("arcade_practical_%d" % index, type="POINT")
        data.energy = energy
        data.color = color
        data.shadow_soft_size = 1.10
        obj = bpy.data.objects.new("arcade_practical_%d" % index, data)
        obj.location = (x, y, PAD_TOP + z)
        col.objects.link(obj)

    _merge_asset_meshes(col, "followville_arcade_batched")

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

# Which addresses use the compact lot footprint now lives in
# neighborhood_plan, next to the footprints it changes the size of: the plan's
# own overlap checks need it, and they cannot import this module because this
# module needs bpy. Treating every planned house as the standard .78 lot
# reported 53 pairs of BUILT houses as overlapping when they do not.


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
        rotation = (obj.rotation_quaternion.copy()
                    if obj.rotation_mode == "QUATERNION"
                    else obj.rotation_euler.to_quaternion())
        matrix = Matrix.LocRotScale(obj.location, rotation, obj.scale)
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
        if style_index == 0:
            # V1 Walkable Interior for classic_ranch (variant 0):
            # Outer walls with physical 0.20m wall thickness and front doorway opening
            t = 0.20
            door_w = 1.20
            door_h = 2.10
            door_x = -garage_side * (w * .19)
            # Back wall
            add_box(col, "wall_back", w, t, body_h, 0, d/2 - t/2, foundation_z, wall)
            # Left wall
            add_box(col, "wall_left", t, d - 2*t, body_h, -w/2 + t/2, 0, foundation_z, wall)
            # Right wall
            add_box(col, "wall_right", t, d - 2*t, body_h, w/2 - t/2, 0, foundation_z, wall)
            # Front wall left segment
            front_left_w = (w / 2 + door_x - door_w / 2)
            front_left_cx = -w/2 + front_left_w/2
            add_box(col, "wall_front_l", front_left_w, t, body_h, front_left_cx, -d/2 + t/2, foundation_z, wall)
            # Front wall right segment
            front_right_w = (w / 2 - door_x - door_w / 2)
            front_right_cx = w/2 - front_right_w/2
            add_box(col, "wall_front_r", front_right_w, t, body_h, front_right_cx, -d/2 + t/2, foundation_z, wall)
            # Lintel above door
            add_box(col, "wall_front_lintel", door_w, t, body_h - door_h, door_x, -d/2 + t/2, foundation_z + door_h, wall)
            # Interior floor slab
            add_box(col, "interior_floor", w - 2*t, d - 2*t, 0.08, 0, 0, foundation_z, m["cap"])
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


RIVER_HOUSE_PALETTES = [
    ((.40, .23, .12), (.13, .20, .17), (.68, .27, .12)),
    ((.53, .34, .17), (.18, .23, .22), (.17, .33, .27)),
    ((.34, .29, .23), (.12, .18, .20), (.56, .22, .14)),
    ((.47, .39, .25), (.17, .24, .18), (.23, .38, .42)),
]


def build_river_house(col, variant):
    """Distinctive timber-and-stone homes for the population 501-750 chapter.

    The eight silhouettes share the existing safe suburban lot envelope and
    customization material roles, but read immediately as cabins/lodges from
    street and drone height: steep roofs, exposed timber bands, stone bases,
    broad river-facing glass, and deep covered porches.
    """
    style = variant % 8
    wall_c, roof_c, door_c = RIVER_HOUSE_PALETTES[variant % len(RIVER_HOUSE_PALETTES)]
    m = std_mats()
    wall = mat("NB_sub_wall_river_%d" % (variant % 4), wall_c, .90)
    roof = mat("NB_sub_roof_river_%d" % (variant % 4), roof_c, .92)
    door = mat("NB_sub_door_river_%d" % (variant % 4), door_c, .78)
    trim = mat("NB_sub_trim_river", (.76, .67, .51), .88)
    glass = mat("NB_sub_glass_river", (.08, .20, .24), .10, .12, 1.0, 0.0, .68)
    stone = mat("NB_sub_stone_river", (.31, .32, .29), .97)
    timber = mat("NB_sub_timber_river", (.24, .14, .075), .94)
    metal = mat("NB_sub_metal_river", (.10, .13, .13), .82)
    green = mat("NB_sub_green_river", (.18, .34, .19), .97)

    widths = (7.4, 7.8, 8.3, 7.9, 7.1, 8.5, 7.6, 8.2)
    depths = (5.8, 6.0, 5.9, 6.2, 5.7, 6.1, 6.0, 5.8)
    width, depth = widths[style], depths[style]
    two_story = style in (2, 3, 5, 7)
    body_h = 5.45 if two_story else 3.45
    base_z = .34 if style in (3, 4, 7) else .18

    add_box(col, "river_stone_foundation", width + .22, depth + .18, base_z + .34,
            0, 0, 0, stone)
    if style == 1:
        # A-frame center with short side shoulders.
        add_box(col, "river_wall_main", width, depth, 3.25, 0, 0, base_z, wall)
        add_prism_roof(col, "river_roof_aframe", width + .66, depth + .72, 4.15,
                       0, 0, base_z + 2.70, roof)
    elif style == 3:
        add_box(col, "river_wall_main", width * .68, depth, body_h,
                -width * .15, 0, base_z, wall)
        add_box(col, "river_wall_wing", width * .38, depth * .78, 3.25,
                width * .31, -.25, base_z, wall)
        add_prism_roof(col, "river_roof_main", width * .75, depth + .62, 2.05,
                       -width * .15, 0, base_z + body_h, roof)
        wing_roof = add_prism_roof(col, "river_roof_wing", depth * .86,
                                   width * .43, 1.55, width * .31, -.25,
                                   base_z + 3.25, roof)
        wing_roof.rotation_euler.z = math.pi / 2
    elif style == 5:
        # Broad modern lodge: traditional timber massing with a glass center.
        add_box(col, "river_wall_left", width * .39, depth, body_h,
                -width * .305, 0, base_z, wall)
        add_box(col, "river_wall_right", width * .39, depth, body_h,
                width * .305, 0, base_z, wall)
        add_box(col, "river_wall_center", width * .22, depth, body_h,
                0, 0, base_z, wall)
        add_prism_roof(col, "river_roof_lodge", width + .72, depth + .72, 2.35,
                       0, 0, base_z + body_h, roof)
    else:
        add_box(col, "river_wall_main", width, depth, body_h, 0, 0, base_z, wall)
        roof_height = 2.65 if style in (0, 6) else (2.15 if two_story else 2.35)
        add_prism_roof(col, "river_roof_main", width + .68, depth + .70,
                       roof_height, 0, 0, base_z + body_h, roof)

    front_y = -depth / 2
    # Real projecting log bands. Each band overlaps the wall by 3 cm and owns
    # its visible face by 7 cm, satisfying the project's depth rule.
    #
    # The bands and posts must trace the massing this style actually built,
    # not the lot envelope. Styles 1 and 3 are not a single full-height box:
    # style 3 sets a low wing beside a tall main mass, and running the timber
    # straight across left bands and a corner post standing in open air above
    # that wing -- no wall behind them, no roof over them, so the right-hand
    # third of the house read as a roofless open crate (reported 2026-08-06).
    # Each mass is (center x, center y, width, depth, wall top, post sides).
    if style == 3:
        masses = ((-width * .15, 0.0, width * .68, depth,
                   base_z + body_h, (-1,)),
                  (width * .31, -.25, width * .38, depth * .78,
                   base_z + 3.25, (1,)))
    elif style == 1:
        masses = ((0.0, 0.0, width, depth, base_z + 3.25, (-1, 1)),)
    else:
        masses = ((0.0, 0.0, width, depth, base_z + body_h, (-1, 1)),)
    for mass_index, (mx, my, m_w, m_d, wall_top, post_sides) in enumerate(masses):
        index, z = 0, base_z + .48
        # Stop a course short of the eave so no band crosses the roofline.
        while z <= wall_top - .34:
            add_box(col, "river_log_band_%d_%02d" % (mass_index, index),
                    m_w + .08, .10, .105, mx, my - m_d / 2 - .02, z, timber)
            add_box(col, "river_rear_log_band_%d_%02d" % (mass_index, index),
                    m_w + .08, .10, .105, mx, my + m_d / 2 + .02, z, timber)
            index += 1
            z += .46
        for side in post_sides:
            add_box(col, "river_corner_post", .12, m_d + .08,
                    wall_top - base_z + .08, mx + side * (m_w / 2 + .02), my,
                    base_z, timber)

    door_x = -width * .22 if style % 2 else width * .20
    _sub_door(col, "river_entry", door_x, front_y - .08, base_z + .04,
              trim, door, glass, m)
    window_x = -door_x * .95
    _sub_window(col, "river_picture_window", window_x, front_y - .10,
                base_z + 1.32, trim, glass, None, 1.72, 1.45)
    if two_story:
        for index, x in enumerate((-width * .27, width * .27)):
            _sub_window(col, "river_upper_%d" % index, x, front_y - .10,
                        base_z + 3.82, trim, glass, None, 1.20, 1.15)
    elif style == 1:
        _sub_window(col, "river_loft", 0, front_y - .13,
                    base_z + 3.25, trim, glass, None, 1.15, 1.05)
    # Rear glazing keeps the homes recognizable in drone views from the river.
    rear_y = depth/2
    for index, x in enumerate((-width*.22, width*.22)):
        add_box(col, "river_rear_window_frame_%d" % index, 1.42, .12, 1.28,
                x, rear_y+.02, base_z+1.30, trim)
        add_box(col, "river_rear_window_glass_%d" % index, 1.18, .055, 1.04,
                x, rear_y+.055, base_z+1.42, glass)

    # Deep porch/deck and timber frame are the river-district signature.
    porch_width = min(width - .45, 5.8 if style in (2, 5, 7) else 4.8)
    porch_depth = 1.38
    add_box(col, "river_deck", porch_width, porch_depth, .24,
            0, front_y - porch_depth / 2, base_z - .06, timber)
    for px in (-porch_width / 2 + .22, porch_width / 2 - .22):
        add_box(col, "river_porch_post", .20, .20, 2.35,
                px, front_y - porch_depth + .18, base_z + .16, timber)
        add_box(col, "river_porch_brace", .58, .18, .16,
                px * .92, front_y - porch_depth + .18, base_z + 2.22, timber)
    add_box(col, "river_porch_beam", porch_width, .22, .24,
            0, front_y - porch_depth + .18, base_z + 2.43, timber)
    add_prism_roof(col, "river_porch_roof", porch_width + .35,
                   porch_depth + .38, .72, 0, front_y - porch_depth / 2,
                   base_z + 2.62, roof)

    # Stone chimney gives the cabins a clear silhouette in distant drone shots.
    chimney_x = -width * .34 if style % 2 else width * .34
    add_box(col, "river_stone_chimney", .72, .78, body_h + 1.25,
            chimney_x, .55, base_z, stone)
    add_box(col, "river_chimney_cap", .92, .98, .18,
            chimney_x, .55, base_z + body_h + 1.22, metal)

    # Curb-connected gravel drive/walk stay inside the audited suburban lot.
    drive_x = -door_x
    add_box(col, "river_driveway", 2.65, 2.15, .09,
            drive_x, -4.02, .03, m["cap"])
    add_box(col, "river_front_walk", 1.00, max(.80, 3.75 + front_y), .10,
            door_x, (front_y - 3.75) / 2, .04, m["cap"])
    for side in (-1, 1):
        sx = side * (width / 2 - .45)
        add_ngon_cone(col, "river_evergreen_trunk", .11, .13, .62, 7,
                      sx, front_y - .52, .04, timber)
        add_ngon_cone(col, "river_evergreen", .64, .12, 1.45, 8,
                      sx, front_y - .52, .48, green)
    mailbox_x = width / 2 - .45
    add_box(col, "river_mailpost", .14, .14, 1.02,
            mailbox_x, -4.66, .02, timber)
    add_box(col, "river_mailbox", .44, .66, .34,
            mailbox_x, -4.66, .98, metal)

    _merge_asset_meshes(col, "river_house_%02d" % variant)


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
    # Keep the assembled storefront visually flush while placing it just
    # outside the ground-floor shell. Exact coplanarity with the shell made
    # facade pieces flicker as the web camera moved.
    facade_plane_y=.25-depth/2-.012
    facade_depth=.12
    front_y=facade_plane_y+facade_depth/2
    outer_y=facade_plane_y
    glass_depth=.035
    glass_y=facade_plane_y+glass_depth/2
    add_box(col,"storefront_base",width+.12,facade_depth,.30,0,front_y,.18,frame)
    add_box(col,"storefront_lintel",width+.12,facade_depth,.34,0,front_y,2.62,frame)
    corner_pier_width=.46
    corner_clearance=.06
    left_pier_x=mounted_face_center(-width/2,-1,corner_pier_width,corner_clearance)
    right_pier_x=mounted_face_center(width/2,1,corner_pier_width,corner_clearance)
    # The structural side walls and these corner piers formerly ended on the
    # same X planes. Their competing side faces produced a faint vertical
    # shimmer at oblique walking angles even after the front plane was fixed.
    add_box(col,"storefront_left_pier",corner_pier_width,facade_depth,2.44,
            left_pier_x,front_y,.48,frame)
    add_box(col,"storefront_right_pier",corner_pier_width,facade_depth,2.44,
            right_pier_x,front_y,.48,frame)
    add_box(col,"storefront_center_pier",.48,facade_depth,2.44,-width*.10,front_y,.48,frame)
    door_x=-width*.28
    # A framed glazed door replaces the old solid door with a glass rectangle
    # hovering in front of it.
    add_box(col,"door_left_stile",.18,facade_depth,2.37,door_x-.50,front_y,.24,door)
    add_box(col,"door_right_stile",.18,facade_depth,2.37,door_x+.50,front_y,.24,door)
    add_box(col,"door_bottom_rail",.82,facade_depth,.24,door_x,front_y,.24,door)
    add_box(col,"door_top_rail",.82,facade_depth,.15,door_x,front_y,2.46,door)
    # One continuous pane avoids the duplicate internal face produced when
    # the former door glass and same-material transom met at exactly z=2.15.
    add_box(col,"door_glass",.82,glass_depth,1.98,door_x,glass_y,.48,storefront_glass)
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
    """Founder seed-2 Burj: tall skyline, footprint stays inside one ~13m lot."""
    m = std_mats()
    glass = mat("NB_burj_glass", (0.52, 0.63, 0.74), 0.22)
    trim = mat("NB_burj_trim", (0.88, 0.90, 0.93), 0.55)
    dark = mat("NB_burj_dark", (0.22, 0.28, 0.34), 0.35)
    # Radii are half-widths — keep diameter under ~10m so roads stay clear.
    tiers = [
        (4.6, 4.1, 14.0, 0.0),
        (3.8, 3.3, 13.0, 14.0),
        (3.1, 2.6, 12.0, 27.0),
        (2.4, 2.0, 12.0, 39.0),
        (1.8, 1.4, 11.0, 51.0),
        (1.2, 0.85, 10.0, 62.0),
        (0.7, 0.35, 9.0, 72.0),
    ]
    for i, (rb, rt, h, z) in enumerate(tiers):
        add_ngon_cone(col, "tier%d" % i, rb, rt, h, 8, 0, 0, z, glass)
        add_ngon_cone(col, "trim%d" % i, rb + 0.18, rb + 0.08, 0.4, 8, 0, 0, z, trim)
        if i < 5:
            add_ngon_cone(col, "belt%d" % i, rb * 0.9, rt * 0.92, 0.18, 8,
                          0, 0, z + h * 0.45, dark)
    add_ngon_cone(col, "spire", 0.45, 0.04, 12.0, 8, 0, 0, 81.0, trim)
    add_ngon_cone(col, "beacon", 0.22, 0.12, 0.55, 8, 0, 0, 92.5, m["bulb"])
    # Lobby stays on the lot pad only (no mega-podium spilling into roads).
    add_box(col, "pad", 9.6, 9.6, 0.22, 0, 0, 0, trim)
    add_box(col, "lobby", 5.2, 5.2, 3.2, 0, 0, 0.22, trim)
    add_box(col, "lobby_glass", 4.4, 0.18, 2.4, 0, -2.7, 0.5, glass)
    add_box(col, "door", 1.5, 0.28, 2.2, 0, -2.85, 0.35, m["door"])
    add_box(col, "awning", 3.2, 1.4, 0.28, 0, -3.4, 2.9, glass)
    for ang in (0.5, 2.1, 3.7, 5.3):
        build_tree(col, random.Random(seed + int(ang * 10)), 0.55,
                   math.cos(ang) * 3.8, math.sin(ang) * 3.8)

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


METRO_TOWER_PALETTES = (
    ((.82, .88, .91), (.22, .42, .55), (.94, .72, .43)),
    ((.88, .82, .78), (.26, .43, .49), (.69, .84, .72)),
    ((.80, .86, .80), (.20, .39, .45), (.94, .79, .60)),
    ((.88, .84, .92), (.29, .38, .57), (.82, .67, .52)),
    ((.92, .86, .75), (.24, .45, .58), (.72, .84, .88)),
    ((.78, .86, .91), (.19, .36, .50), (.91, .63, .58)),
    ((.91, .79, .76), (.25, .40, .48), (.73, .85, .67)),
    ((.83, .82, .90), (.22, .35, .52), (.94, .78, .50)),
    ((.84, .90, .86), (.19, .40, .46), (.78, .66, .84)),
    ((.91, .88, .82), (.28, .43, .54), (.66, .82, .89)),
)


def _metro_facade_section(col, prefix, w, d, h, z, wall, glass, trim,
                          bands=6, vertical=False):
    """One tower mass with sparse, readable low-poly façade articulation."""
    add_box(col, prefix + "_mass", w, d, h, 0, 0, z, wall)
    # Window ribbons are inset from corners and physically proud of the wall.
    # Their hidden half remains embedded; their visible face clears by 6cm.
    panel_depth = .12
    usable_w, usable_d = max(3.0, w - 2.0), max(3.0, d - 2.0)
    for level in range(bands):
        pz = z + 3.0 + (h - 6.0) * (level + .5) / max(1, bands)
        if vertical:
            stripe_w = max(1.5, usable_w / 3.6)
            for sx in (-usable_w * .27, usable_w * .27):
                add_box(col, prefix + "_glass_ns", stripe_w, panel_depth,
                        max(1.1, h / bands * .52), sx, -d / 2, pz, glass)
                add_box(col, prefix + "_glass_ns", stripe_w, panel_depth,
                        max(1.1, h / bands * .52), sx, d / 2, pz, glass)
            stripe_d = max(1.5, usable_d / 3.6)
            for sy in (-usable_d * .27, usable_d * .27):
                add_box(col, prefix + "_glass_ew", panel_depth, stripe_d,
                        max(1.1, h / bands * .52), -w / 2, sy, pz, glass)
                add_box(col, prefix + "_glass_ew", panel_depth, stripe_d,
                        max(1.1, h / bands * .52), w / 2, sy, pz, glass)
        else:
            band_h = max(.75, min(1.35, h / bands * .17))
            add_box(col, prefix + "_glass_ns", usable_w, panel_depth, band_h,
                    0, -d / 2, pz, glass)
            add_box(col, prefix + "_glass_ns", usable_w, panel_depth, band_h,
                    0, d / 2, pz, glass)
            add_box(col, prefix + "_glass_ew", panel_depth, usable_d, band_h,
                    -w / 2, 0, pz, glass)
            add_box(col, prefix + "_glass_ew", panel_depth, usable_d, band_h,
                    w / 2, 0, pz, glass)
    # A recessed shadow line gives every section a clear top rather than a
    # texture-like stripe sharing the roof plane.
    add_box(col, prefix + "_cornice", w + .28, d + .28, .22,
            0, 0, z + h + .04, trim)


def build_metro_tower(col, variant):
    """One of twenty authored Crown Quarter tower silhouettes.

    The design language stays Followville: simple scripted solids, optimistic
    pastels, dark blue-green glazing, warm accents, and strong roof shapes.
    Variation comes from massing and proportion rather than random decoration.
    """
    slot = METRO_TOWER_PLAN[int(variant) % len(METRO_TOWER_PLAN)]
    height = float(slot["height"])
    palette = METRO_TOWER_PALETTES[int(variant) % len(METRO_TOWER_PALETTES)]
    wall = mat("FV_metro_wall_%02d" % (variant % 10), palette[0], .78)
    glass = mat("FV_metro_glass_%02d" % (variant % 10), palette[1], .20,
                metallic=.08, coat=.18)
    accent = mat("FV_metro_accent_%02d" % (variant % 10), palette[2], .62)
    concrete = mat("FV_metro_podium", (.45, .45, .43), .94)
    dark = mat("FV_metro_frame", (.18, .22, .24), .58, metallic=.18)
    warm = mat("FV_metro_lobby_glow", (1.0, .78, .45), .28)
    green = mat("FV_metro_planter", (.27, .52, .31), .96)

    # Every claimable address has a complete ground interface: serviceable
    # podium, transparent lobby, weather protection, and small forecourt.
    add_box(col, "metro_podium_slab", 38.0, 40.0, .32, 0, 0, 0, concrete)
    add_box(col, "metro_podium", 31.0, 32.0, 6.2, 0, 1.0, .32, wall)
    add_box(col, "metro_lobby", 12.0, .18, 3.9, 0, -15.08, .62, glass)
    add_box(col, "metro_lobby_door", 3.0, .20, 3.35, 0, -15.20, .62, warm)
    add_box(col, "metro_canopy", 13.5, 3.8, .32, 0, -16.5, 4.5, accent)
    for x in (-11.5, -6.0, 6.0, 11.5):
        add_box(col, "metro_retail_window", 4.0, .15, 2.5,
                x, -15.1, .72, glass)
    for x in (-15.5, 15.5):
        add_box(col, "metro_planter_box", 3.0, 2.2, .55,
                x, -17.2, .32, concrete)
        add_ngon_cone(col, "metro_planter_tree", 1.15, .55, 2.7, 7,
                      x, -17.2, .87, green)

    profile = int(variant) % 5
    vertical = (int(variant) // 5) % 2 == 1
    base_z = 6.54
    if profile == 0:  # three-step commercial tower
        h1 = height * .54
        h2 = height * .28
        h3 = height - h1 - h2
        _metro_facade_section(col, "metro_lower", 25.0, 25.0, h1, base_z,
                              wall, glass, dark, 6, vertical)
        _metro_facade_section(col, "metro_mid", 20.5, 21.5, h2,
                              base_z + h1 + .28, wall, glass, accent, 4, not vertical)
        _metro_facade_section(col, "metro_upper", 15.5, 17.0, h3,
                              base_z + h1 + h2 + .56, wall, glass, dark, 3, vertical)
    elif profile == 1:  # offset slab and lantern crown
        _metro_facade_section(col, "metro_slab", 18.0, 29.0, height * .78,
                              base_z, wall, glass, dark, 8, vertical)
        _metro_facade_section(col, "metro_lantern", 13.5, 20.0, height * .22,
                              base_z + height * .78 + .28, accent, glass, dark, 3, False)
    elif profile == 2:  # broad base, narrow setback tower
        _metro_facade_section(col, "metro_base", 28.0, 24.0, height * .34,
                              base_z, wall, glass, accent, 4, False)
        _metro_facade_section(col, "metro_shaft", 19.0, 18.0, height * .66,
                              base_z + height * .34 + .28, wall, glass, dark, 7, vertical)
    elif profile == 3:  # faceted civic-looking tower
        add_ngon_cone(col, "metro_faceted_mass", 14.0, 10.5, height, 8,
                      0, 0, base_z, glass, rot=math.pi / 8)
        for level in range(7):
            pz = base_z + 5.0 + (height - 8.0) * level / 6.0
            add_ngon_cone(col, "metro_faceted_band", 14.18, 14.18, .24, 8,
                          0, 0, pz, accent, rot=math.pi / 8)
    else:  # paired wings around a bright central spine
        wing_h = height * .86
        _metro_facade_section(col, "metro_west_wing", 10.5, 23.0, wing_h,
                              base_z, wall, glass, dark, 7, vertical)
        _metro_facade_section(col, "metro_east_wing", 10.5, 23.0, wing_h,
                              base_z, wall, glass, dark, 7, not vertical)
        # Move the wing objects as coherent authored masses before instancing.
        for obj in list(col.objects):
            if obj.name.startswith("metro_west_wing"):
                obj.location.x -= 6.2
            elif obj.name.startswith("metro_east_wing"):
                obj.location.x += 6.2
        add_box(col, "metro_center_spine", 4.2, 17.0, height,
                0, 0, base_z, accent)

    roof_z = base_z + height + .9
    crown = int(variant) % 4
    if crown == 0:
        add_ngon_cone(col, "metro_crown", 7.0, 2.4, 5.0, 6,
                      0, 0, roof_z, accent, rot=math.pi / 6)
    elif crown == 1:
        add_box(col, "metro_roof_frame", 11.0, 11.0, 3.2,
                0, 0, roof_z, dark)
        add_box(col, "metro_roof_lantern", 8.2, 8.2, 2.5,
                0, 0, roof_z + .35, warm)
    elif crown == 2:
        add_ngon_cone(col, "metro_crown", 6.5, 6.5, 2.2, 8,
                      0, 0, roof_z, accent, rot=math.pi / 8)
        add_ngon_cone(col, "metro_spire", .48, .08, 9.0, 8,
                      0, 0, roof_z + 2.25, dark)
    else:
        for x in (-4.2, 0.0, 4.2):
            add_box(col, "metro_crown_fin", 1.0, 10.0,
                    4.0 + (4.2 - abs(x)) * .45, x, 0, roof_z, accent)
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



# ── Followville High School ─────────────────────────────────────────────────
# The campus stands on the block immediately south of Followville Elementary,
# across the y=-93 street, on the level platform cut for it in
# downtown_visual_plan.HIGH_SCHOOL_PAD.  Local origin is the anchor stored in
# world_state (-69, -156); the declared footprint in
# world_layout.LANDMARK_FOOTPRINTS is x +/-32, y +/-56, and every piece of
# geometry below stays inside it.
#
# North (+Y) faces the town, so the drive, drop-off and car park go there.
# The three buildings stand in a row across the middle with their entrances on
# -Y -- both the campus convention (place_instance leaves civic assets
# unrotated so their doors face local -Y) and the side the town's cameras look
# at.  The stadium fills the southern two thirds.
CAMPUS_HALF_X = 32.0
CAMPUS_HALF_Y = 56.0
# Every horizontal layer gets its own elevation.  Two hardscape surfaces that
# share a plane z-fight in the browser -- the standing rule in CLAUDE.md -- so
# these are staggered by a centimetre or more, and every painted marking sits
# clear above the surface it is painted on rather than in it.
# The lawn sits high enough that the whole campus -- lawn, paving, drive and
# running track -- lies within 6cm of one deck height, which is what lets
# world_layout declare a single 0.28m walk pad for the platform instead of the
# player sinking into the paving or hovering over the grass.
HS_LAWN_TOP = .22
HS_WALK_Z, HS_WALK_H = .15, .13          # plaza and footway, top .28
HS_ASPHALT_Z, HS_ASPHALT_H = .16, .15    # drive and car park, top .31
HS_TURF_Z, HS_TURF_H = .17, .09          # stadium infield, top .26
HS_TRACK_Z, HS_TRACK_H = .18, .14        # running surface, top .32
HS_TURF_PAINT_Z = .27                    # yard lines, clear of the turf top
HS_ASPHALT_PAINT_Z = .32                 # bay stripes, clear of the asphalt
HS_TRACK_PAINT_Z = .33                   # lane lines, clear of the running top
# The running track: an obround with its straights along Y, described by the
# inner kerb radius, half the straight, and a six-lane band.  The proportions
# are a real 400m track brought down to the scale this town is built at.  What
# matters is that the infield (40.6 x 62.6) holds a 23 x 50 football field with
# its corners inside the bends, exactly as a full-size field sits inside a
# full-size track.  Fitting the widest oval the site allows instead gives a
# round one, and a round oval can only hold a square field.
HS_TRACK_CX, HS_TRACK_CY = 5.0, -18.0
HS_TRACK_INNER_R = 20.3
HS_TRACK_HALF_STRAIGHT = 11.0
HS_TRACK_LANES = 6
HS_TRACK_LANE_W = .95
HS_FIELD_W, HS_FIELD_L = 23.0, 50.0      # x across the field, y along it
HS_END_ZONE = 5.0


def _obround_loop(cx, cy, half_straight, radius, arc_steps):
    """Closed loop round an obround whose two straights run along +/-Y.

    The straights are implied by the segments joining the two arcs, so an
    inner and an outer loop built with the same arc_steps always have matching
    point counts and stitch into a ring with no special-casing.
    """
    points = []
    for index in range(arc_steps + 1):          # north end, east -> west
        angle = math.pi * index / arc_steps
        points.append((cx + radius * math.cos(angle),
                       cy + half_straight + radius * math.sin(angle)))
    for index in range(arc_steps + 1):          # south end, west -> east
        angle = math.pi + math.pi * index / arc_steps
        points.append((cx + radius * math.cos(angle),
                       cy - half_straight + radius * math.sin(angle)))
    return points


def _add_obround_pad(col, name, cx, cy, half_straight, radius, z, height,
                     material, arc_steps=18):
    """A filled obround slab -- the stadium infield, a stadium apron."""
    loop = _obround_loop(cx, cy, half_straight, radius, arc_steps)
    count = len(loop)
    verts = ([(x, y, 0.0) for x, y in loop] + [(x, y, height) for x, y in loop]
             + [(cx, cy, 0.0), (cx, cy, height)])
    bottom_hub, top_hub = 2 * count, 2 * count + 1
    faces = []
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((bottom_hub, nxt, index))
        faces.append((top_hub, count + index, count + nxt))
        faces.append((index, nxt, count + nxt, count + index))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0.0, 0.0, z)
    col.objects.link(obj)
    return obj


def _add_obround_band(col, name, cx, cy, half_straight, inner_r, outer_r,
                      z, height, material, arc_steps=18):
    """A closed obround ring -- the lane band, or one painted lane line."""
    inner = _obround_loop(cx, cy, half_straight, inner_r, arc_steps)
    outer = _obround_loop(cx, cy, half_straight, outer_r, arc_steps)
    count = len(inner)
    verts = ([(x, y, 0.0) for x, y in inner] + [(x, y, 0.0) for x, y in outer]
             + [(x, y, height) for x, y in inner]
             + [(x, y, height) for x, y in outer])
    i0, o0, i1, o1 = 0, count, 2 * count, 3 * count
    faces = []
    for index in range(count):
        nxt = (index + 1) % count
        faces.append((i0 + index, i0 + nxt, o0 + nxt, o0 + index))
        faces.append((i1 + index, o1 + index, o1 + nxt, i1 + nxt))
        faces.append((i0 + index, i1 + index, i1 + nxt, i0 + nxt))
        faces.append((o0 + index, o0 + nxt, o1 + nxt, o1 + index))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0.0, 0.0, z)
    col.objects.link(obj)
    return obj


def _hs_campus_tree(col, rng, x, y, scale=1.0, z=HS_LAWN_TOP):
    """A campus tree standing on the raised lawn rather than on the collection
    origin, which is where build_tree() would put it -- 14cm underground."""
    trunk = mat("NB_hs_trunk", (.40, .28, .19), 1.0)
    index = rng.randrange(3)
    canopy = mat("NB_hs_canopy_%d" % index,
                 ((.24, .44, .25), (.29, .50, .27), (.21, .40, .23))[index],
                 1.0)
    add_ngon_cone(col, "hs_tree_trunk", .34 * scale, .26 * scale,
                  2.3 * scale, 6, x, y, z, trunk)
    add_ngon_cone(col, "hs_tree_crown", 1.85 * scale, .70 * scale,
                  2.9 * scale, 7, x, y, z + 2.1 * scale, canopy)
    add_ngon_cone(col, "hs_tree_top", .72 * scale, 0.0, 1.0 * scale, 7,
                  x, y, z + 4.75 * scale, canopy)


def _hs_window(col, name, width, height, cx, cy, cz, outward, wall,
               trim, pane, mullion):
    """One window: a proud stone frame, glazing recessed inside it, a mullion
    and a sill.  outward is the outward axis as (dx, dy) -- (0,-1) on a south
    wall, (1,0) on an east one -- and wall is the coordinate of the wall plane.

    Every layer is placed with mounted_face_center() off that plane, so each is
    anchored inside the masonry while its visible face stands clear of the one
    behind it, and nothing here ends up coplanar with the wall.
    """
    dx, dy = outward
    sign = dx or dy
    frame_c = mounted_face_center(wall, sign, .26, .20)
    pane_c = mounted_face_center(wall, sign, .16, .14)
    mullion_c = mounted_face_center(wall, sign, .18, .17)
    sill_c = mounted_face_center(wall, sign, .34, .28)
    if dx:
        add_box(col, name + "_frame", .26, width + .44, height + .40,
                frame_c, cy, cz - .20, trim)
        add_box(col, name + "_pane", .16, width, height,
                pane_c, cy, cz, pane)
        add_box(col, name + "_mullion", .18, .11, height - .10,
                mullion_c, cy, cz + .05, mullion)
        add_box(col, name + "_sill", .34, width + .74, .16,
                sill_c, cy, cz - .40, trim)
    else:
        add_box(col, name + "_frame", width + .44, .26, height + .40,
                cx, frame_c, cz - .20, trim)
        add_box(col, name + "_pane", width, .16, height,
                cx, pane_c, cz, pane)
        add_box(col, name + "_mullion", .11, .18, height - .10,
                cx, mullion_c, cz + .05, mullion)
        add_box(col, name + "_sill", width + .74, .34, .16,
                cx, sill_c, cz - .40, trim)


def _hs_entrance(col, name, cx, front, base_z, ground_top, width, height,
                 leaf_h, pier, reveal, pane, door, accent, metal, steps=3):
    """A masonry entrance portal on a -Y facade: two piers, a header, glazing
    set back inside the reveal, doors standing proud of the glazing, a canopy
    and broad steps.  The planes step forward in 6-10cm increments from the
    glazing out to the door pulls, so none shares a face with the one behind.

    Each step is one box rising from just below the paving to its own tread
    level, so the treads are all at different heights and the only faces they
    share are the buried undersides.
    """
    pier_w = width * .21
    opening = width - 2 * pier_w
    glaze_y = front - .58
    for side in (-1, 1):
        add_box(col, name + "_pier", pier_w, 1.30, height,
                cx + side * (width - pier_w) / 2, front - .55, base_z, pier)
        # Stands 6cm proud of the lintel so the two caps and the lintel do
        # not present one flat top.
        add_box(col, name + "_pier_cap", pier_w + .26, 1.56, .28,
                cx + side * (width - pier_w) / 2, front - .68,
                base_z + height - .22, pier)
    # A lintel across the opening, not a full-width block: a header the width
    # of the portal put its face, both sides and both edges in exactly the
    # same planes as the piers -- one facade made of three coplanar solids.
    add_box(col, name + "_header", opening + .02, 1.42,
            max(.9, height - leaf_h - 1.05),
            cx, front - .61, base_z + leaf_h + 1.05, pier)
    add_box(col, name + "_reveal", opening + .10, .46, leaf_h + 1.05,
            cx, front - .02, base_z, reveal)
    add_box(col, name + "_glazing", opening - .26, .18, leaf_h + .60,
            cx, glaze_y, base_z + .34, pane)
    add_box(col, name + "_transom", opening - .06, .24, .18,
            cx, glaze_y - .02, base_z + leaf_h + .36, pier)
    for side in (-1, 1):
        add_box(col, name + "_door", opening * .30, .17, leaf_h,
                cx + side * opening * .17, glaze_y - .16, base_z + .18, door)
        add_box(col, name + "_pull", .08, .08, .92,
                cx + side * opening * .295, glaze_y - .29,
                base_z + 1.02, metal)
    add_box(col, name + "_door_stile", .17, .21, leaf_h + .12,
            cx, glaze_y - .15, base_z + .14, pier)
    add_box(col, name + "_canopy", width + 1.60, 2.60, .38,
            cx, front - 1.70, base_z + leaf_h + 1.44, accent)
    add_box(col, name + "_canopy_fascia", width + 1.92, 2.92, .14,
            cx, front - 1.70, base_z + leaf_h + 1.30, metal)
    for side in (-1, 1):
        add_ngon_cone(col, name + "_column", .22, .20, leaf_h + 1.32, 10,
                      cx + side * (width / 2 + .34), front - 2.70,
                      base_z + .12, pier)
    rise = (base_z - ground_top) / (steps + .5)
    for index in range(steps):
        tread = base_z - (index + 1) * rise
        add_box(col, name + "_step", width + 1.0 + index * .70, .48,
                tread - ground_top + .09,
                cx, front - 3.20 - index * .48, ground_top - .09, pier)


def build_high_school(col, seed):
    """Followville High: three buildings, a stadium, and the campus round it.

    Authored in campus-local coordinates about the anchor stored in
    world_state, front doors on -Y.  See the HS_* constants above for the site
    plan and the elevation each horizontal layer sits at.

    The north/south budget is tight and deliberate: 13.8m of arrival, 17.2m of
    buildings, a 5.6m quad, then the 74m stadium.  That is the whole 112m the
    platform gives, which is why the quad is one slab rather than a forecourt
    per building and why the planting sits in the corners the oval leaves.
    """
    rng = random.Random(seed)
    m = std_mats()
    brick = mat("NB_hs_brick", (.55, .25, .20), .93)
    brick_dark = mat("NB_hs_brick_shadow", (.42, .185, .15), .95)
    stone = mat("NB_hs_stone", (.87, .83, .73), .84)
    stone_dark = mat("NB_hs_stone_shadow", (.70, .66, .58), .89)
    slate = mat("NB_hs_roof", (.235, .265, .325), .80)
    navy = mat("NB_hs_navy", (.105, .165, .32), .70)
    gold = mat("NB_hs_gold", (.85, .66, .19), .46, .30)
    pane = m["window"]
    darkpane = m["windark"]
    steel = m["metal"]
    charcoal = mat("NB_hs_charcoal", (.135, .15, .175), .62)
    asphalt = mat("NB_hs_asphalt", (.17, .175, .19), .95)
    paint = mat("NB_hs_paint", (.95, .95, .91), .74)
    concrete = mat("NB_hs_concrete", (.73, .73, .71), .92)
    lawn = mat("NB_hs_lawn", (.36, .60, .28), 1.0)
    turf = mat("NB_hs_turf", (.20, .46, .23), .98)
    rubber = mat("NB_hs_track", (.62, .27, .19), .96)
    hedge = mat("NB_hs_hedge", (.24, .43, .24), 1.0)
    # Paved areas that meet each other get slightly different tops and are made
    # to overlap, so a shared edge is always one slab passing under another
    # rather than two coplanar faces butting together.
    QUAD_TOP = HS_WALK_Z + .13          # .28
    LINK_TOP = HS_WALK_Z + .11          # .26
    STADIUM_TOP = HS_WALK_Z + .10       # .25
    STREET_TOP = HS_WALK_Z + .12        # .27

    # ── campus ground ───────────────────────────────────────────────────────
    # One slab for the whole platform, sunk well below grade so its underside
    # is buried rather than sharing the terrain's plane, and standing 14cm
    # proud so the campus reads as engineered ground with a real kerb.
    add_box(col, "hs_campus_pad", CAMPUS_HALF_X * 2, CAMPUS_HALF_Y * 2, .60,
            0, 0, HS_LAWN_TOP - .60, lawn)
    # Inset far enough that the kerb itself stays inside the declared
    # footprint -- the rectangle is what the geometry audit defends, so nothing
    # built should hang over its edge.
    # The two runs cross at all four corners, so the east/west pair is a
    # centimetre taller and covers the north/south pair where they meet.
    for side in (-1, 1):
        add_box(col, "hs_campus_kerb", .55, CAMPUS_HALF_Y * 2 - .60, .24,
                side * (CAMPUS_HALF_X - .30), 0, HS_LAWN_TOP - .14, concrete)
        add_box(col, "hs_campus_kerb", CAMPUS_HALF_X * 2 - .60, .55, .23,
                0, side * (CAMPUS_HALF_Y - .30), HS_LAWN_TOP - .14, concrete)
    # The west edge is the top of the cut: the meadow climbs a 28.6% bank from
    # here up to Meadow Run, so the campus holds it back with a wall instead of
    # letting the hillside spill onto the running track.
    add_box(col, "hs_retaining_wall", .68, 96.0, 1.30,
            -CAMPUS_HALF_X + .70, -7.0, HS_LAWN_TOP - .30, stone_dark)
    for y in range(-54, 41, 7):
        add_box(col, "hs_retaining_pier", 1.00, .88, 1.58,
                -CAMPUS_HALF_X + .70, float(y), HS_LAWN_TOP - .30, stone)

    # ── arrival: drive, drop-off, bus lay-by, car park ──────────────────────
    # The town's own street runs along y=-93 in world coordinates, 3m north of
    # this campus edge, so the drive needs only two kerb cuts.  Its west leg is
    # on the centreline of world_layout.HIGH_SCHOOL_APPROACH.
    # Every paved surface here overlaps its neighbour, and two slabs at one
    # top height z-fight across the whole overlap. So each is a centimetre
    # lower than the one it runs into and the taller one covers the join.
    add_box(col, "hs_drive_cross", 56.0, 6.50, HS_ASPHALT_H,
            0, 49.5, HS_ASPHALT_Z, asphalt)
    for leg_x in (-14.0, 14.0):
        add_box(col, "hs_drive_leg", 6.50, 8.0, HS_ASPHALT_H - .01,
                leg_x, 49.5, HS_ASPHALT_Z, asphalt)
    add_box(col, "hs_bus_bay", 22.0, 4.20, HS_ASPHALT_H - .02,
            -19.0, 46.0, HS_ASPHALT_Z, asphalt)
    add_box(col, "hs_car_park", 15.0, 10.0, HS_ASPHALT_H - .03,
            23.0, 50.8, HS_ASPHALT_Z, asphalt)
    # No dash at x=0: the crossing is there, and the two markings would have
    # been painted on top of one another.
    for x in range(-24, 25, 6):
        if x:
            add_box(col, "hs_drive_dash", 2.60, .22, .02,
                    float(x), 49.5, HS_ASPHALT_PAINT_Z, m["dash"])
    for index in range(5):
        add_box(col, "hs_bay_stripe", .16, 4.60, .02,
                17.0 + index * 3.0, 53.3, HS_ASPHALT_PAINT_Z - .024, paint)
    add_box(col, "hs_bay_kerb", 14.4, .30, .18,
            23.0, 55.6, HS_ASPHALT_Z + HS_ASPHALT_H - .07, concrete)
    for x in (-2.2, -1.1, 0.0, 1.1, 2.2):
        add_box(col, "hs_crosswalk", .44, 6.10, .02,
                x, 49.5, HS_ASPHALT_PAINT_Z, paint)
    # Kerb cuts. The town's asphalt tops out at 0.17 and the campus deck at
    # 0.31, so each leg ramps the 14cm difference over twelve metres rather
    # than stepping up onto the platform. The far end runs in under the drive
    # leg, whose own top is 1cm higher, so the two never share a face.
    for leg_x in (-14.0, 14.0):
        _add_road_strip(col, "hs_kerb_cut",
                        [(leg_x, 64.0, .02), (leg_x, 61.0, .05),
                         (leg_x, 58.0, .09), (leg_x, 55.0, .13),
                         (leg_x, 52.0, .145)],
                        asphalt, width=6.20, bottom_offset=.005,
                        top_offset=.15)
    add_box(col, "hs_street_walk", 60.0, 2.60, STREET_TOP - HS_WALK_Z,
            0, 54.4, HS_WALK_Z, concrete)
    for walk_x in (-20.0, 2.0, 22.0):
        add_box(col, "hs_entry_walk", 2.60, 12.4, STREET_TOP - HS_WALK_Z,
                walk_x, 46.2, HS_WALK_Z, concrete)
    for x, y in ((-24.0, 46.9), (-4.0, 46.9), (11.0, 46.9), (26.0, 54.4)):
        add_ngon_cone(col, "hs_drive_light", .17, .13, 5.20, 8,
                      x, y, HS_ASPHALT_Z + .10, steel)
        add_box(col, "hs_drive_light_head", 1.10, .40, .22,
                x, y - .40, HS_ASPHALT_Z + 5.30, charcoal)
        add_box(col, "hs_drive_light_lens", .84, .26, .08,
                x, y - .40, HS_ASPHALT_Z + 5.21, m["bulb"])

    # ── the vehicles that make the arrival read as a school ─────────────────
    # Built here rather than instanced through place_instance: that path wants
    # a world_state record and a grid lot, and these belong to the asset.
    bus_yellow = mat("NB_hs_bus", (.94, .69, .12), .74)
    bus_deck = HS_ASPHALT_Z + HS_ASPHALT_H - .02
    add_box(col, "hs_bus_body", 8.60, 2.40, 2.10, -21.0, 46.0, bus_deck + .34,
            bus_yellow)
    add_box(col, "hs_bus_roof", 8.00, 2.46, .34, -21.2, 46.0, bus_deck + 2.44,
            paint)
    add_box(col, "hs_bus_hood", 1.70, 2.24, 1.05, -16.1, 46.0, bus_deck + .30,
            bus_yellow)
    add_box(col, "hs_bus_windshield", 1.10, 2.28, .96, -16.0, 46.0,
            bus_deck + 1.42, darkpane)
    for x in (-24.6, -23.2, -21.8, -20.4, -19.0, -17.6):
        for y, outward in ((44.86, -1), (47.14, 1)):
            add_box(col, "hs_bus_window", 1.05, .14, .82, x,
                    mounted_face_center(y, outward, .14, .10),
                    bus_deck + 1.44, darkpane)
    add_box(col, "hs_bus_band", 8.66, 2.46, .18, -21.0, 46.0, bus_deck + 1.16,
            charcoal)
    for x in (-24.4, -17.4):
        for y in (44.72, 47.28):
            add_box(col, "hs_bus_wheel", .84, .34, .84, x, y, bus_deck,
                    charcoal)
    add_box(col, "hs_bus_stop_arm", .14, .95, .95, -22.6, 44.42,
            bus_deck + 1.10, mat("NB_hs_bus_stop", (.78, .16, .14), .78))
    # Three cars nose-in on the staff bays.
    body_colours = (mat("NB_hs_car_a", (.32, .42, .56), .58, .10),
                    mat("NB_hs_car_b", (.72, .72, .70), .56, .10),
                    mat("NB_hs_car_c", (.48, .30, .28), .58, .10))
    car_deck = HS_ASPHALT_Z + HS_ASPHALT_H - .05
    for index, car_x in enumerate((18.5, 21.5, 27.5)):
        paintwork = body_colours[index]
        add_box(col, "hs_car_body", 2.00, 4.40, .82, car_x, 52.9,
                car_deck + .26, paintwork)
        add_box(col, "hs_car_cabin", 1.78, 2.30, .68, car_x, 53.1,
                car_deck + 1.08, paintwork)
        add_box(col, "hs_car_glass", 1.62, 2.10, .48, car_x, 53.1,
                car_deck + 1.20, darkpane)
        for wheel_x in (car_x - .96, car_x + .96):
            for wheel_y in (51.6, 54.2):
                add_box(col, "hs_car_wheel", .26, .74, .74, wheel_x, wheel_y,
                        car_deck, charcoal)

    # ── monument sign, double sided, at the campus entrance ─────────────────
    add_box(col, "hs_sign_base", 8.60, 1.90, .40, -22.0, 52.4, HS_LAWN_TOP,
            stone_dark)
    add_box(col, "hs_sign_plinth", 8.00, 1.52, .46, -22.0, 52.4,
            HS_LAWN_TOP + .40, stone)
    add_box(col, "hs_sign_panel", 7.30, 1.00, 2.20, -22.0, 52.4,
            HS_LAWN_TOP + .86, brick)
    add_box(col, "hs_sign_cap", 7.92, 1.44, .28, -22.0, 52.4,
            HS_LAWN_TOP + 3.06, stone)
    # Read from the street on one side and from the campus on the other, which
    # is also the side every town camera looks at.
    for face_y, rotation in ((52.93, (math.pi / 2, 0, math.pi)),
                             (51.87, (math.pi / 2, 0, 0))):
        add_text(col, "hs_sign_line_1", "FOLLOWVILLE", .58, .05,
                 -22.0, face_y, HS_LAWN_TOP + 2.36, gold, rotation=rotation)
        add_text(col, "hs_sign_line_2", "HIGH SCHOOL", .58, .05,
                 -22.0, face_y, HS_LAWN_TOP + 1.62, gold, rotation=rotation)
        add_text(col, "hs_sign_line_3", "EST. 2026", .28, .04,
                 -22.0, face_y, HS_LAWN_TOP + 1.10, stone, rotation=rotation)
    for side in (-1, 1):
        add_ngon_cone(col, "hs_sign_light", .17, .13, .34, 8,
                      -22.0 + side * 4.55, 52.4, HS_LAWN_TOP + .86, steel)
        add_ngon_cone(col, "hs_sign_shrub", .95, .42, 1.05, 9,
                      -22.0 + side * 5.60, 51.6, HS_LAWN_TOP, hedge)
    add_box(col, "hs_flag_base", 2.20, 2.20, .34, -30.0, 51.6, HS_LAWN_TOP,
            stone)
    add_ngon_cone(col, "hs_flagpole", .14, .09, 12.0, 10,
                  -30.0, 51.6, HS_LAWN_TOP + .34, steel)
    flag_mesh = bpy.data.meshes.new("hs_flag_mesh")
    flag_mesh.from_pydata([(-29.88, 51.6, HS_LAWN_TOP + 11.20),
                           (-26.10, 51.6, HS_LAWN_TOP + 10.45),
                           (-29.88, 51.6, HS_LAWN_TOP + 9.70)],
                          [], [(0, 1, 2)])
    flag_mesh.materials.append(navy)
    flag_mesh.update()
    col.objects.link(bpy.data.objects.new("hs_flag", flag_mesh))

    # ── the quad, one slab in front of all three buildings ──────────────────
    # Deliberately a single piece of paving rather than a forecourt each: three
    # slabs at one level would meet along shared faces, and staggering them
    # would put steps across the front of the school.
    add_box(col, "hs_quad_paving", 60.0, 5.60, QUAD_TOP - HS_WALK_Z,
            0, 22.2, HS_WALK_Z, concrete)
    add_box(col, "hs_quad_kerb", 60.4, .50, .12, 0, 19.60, HS_WALK_Z + .08,
            stone_dark)
    for x in (11.0, 29.0):
        add_box(col, "hs_quad_bench", 2.20, .58, .46, x, 20.4, QUAD_TOP,
                stone)
        for side in (-.86, .86):
            add_box(col, "hs_quad_bench_leg", .18, .46, .50,
                    x + side, 20.4, QUAD_TOP - .05, charcoal)
    add_box(col, "hs_bike_rack_kerb", 4.40, 2.20, .10, -11.0, 20.5, QUAD_TOP,
            concrete)
    for offset in (-1.5, -.5, .5, 1.5):
        add_box(col, "hs_bike_rack", .10, 1.70, .80, -11.0 + offset, 20.5,
                QUAD_TOP + .08, steel)

    # ── building one: Founders Hall, the academic building ──────────────────
    HALL_X, HALL_Y, HALL_W, HALL_D, HALL_H = -20.0, 34.0, 22.0, 18.0, 8.60
    hall_front, hall_back = HALL_Y - HALL_D / 2, HALL_Y + HALL_D / 2
    hall_floor = HS_LAWN_TOP + .55
    add_box(col, "hs_hall_base", HALL_W + 1.40, HALL_D + 1.40, .55,
            HALL_X, HALL_Y, HS_LAWN_TOP, stone_dark)
    add_box(col, "hs_hall_body", HALL_W, HALL_D, HALL_H,
            HALL_X, HALL_Y, hall_floor, brick)
    add_box(col, "hs_hall_plinth_course", HALL_W + .28, HALL_D + .28, .90,
            HALL_X, HALL_Y, hall_floor, stone)
    add_box(col, "hs_hall_belt", HALL_W + .22, HALL_D + .22, .34,
            HALL_X, HALL_Y, hall_floor + 3.95, stone)
    add_box(col, "hs_hall_cornice", HALL_W + .62, HALL_D + .62, .50,
            HALL_X, HALL_Y, hall_floor + HALL_H - .50, stone)
    add_prism_roof(col, "hs_hall_roof", HALL_W + 1.24, HALL_D + 1.24, 3.00,
                   HALL_X, HALL_Y, hall_floor + HALL_H, slate)
    add_box(col, "hs_hall_ridge", HALL_W + 1.54, .48, .26,
            HALL_X, HALL_Y, hall_floor + HALL_H + 2.94, stone_dark)
    for side in (-1, 1):
        add_box(col, "hs_hall_stack", 1.30, 1.30, 2.30,
                HALL_X + side * 7.60, HALL_Y, hall_floor + HALL_H + 1.50,
                brick_dark)
        add_box(col, "hs_hall_stack_cap", 1.64, 1.64, .22,
                HALL_X + side * 7.60, HALL_Y, hall_floor + HALL_H + 3.80,
                stone)
    for index, offset in enumerate((-9.2, -6.0, 6.0, 9.2)):
        for level, z in ((0, hall_floor + 1.55), (1, hall_floor + 5.20)):
            _hs_window(col, "hs_hall_s%d%d" % (index, level), 2.10, 2.20,
                       HALL_X + offset, None, z, (0, -1), hall_front,
                       stone, pane, navy)
    for index, offset in enumerate((-7.6, -3.8, 0.0, 3.8, 7.6)):
        for level, z in ((0, hall_floor + 1.55), (1, hall_floor + 5.20)):
            _hs_window(col, "hs_hall_n%d%d" % (index, level), 2.10, 2.20,
                       HALL_X + offset, None, z, (0, 1), hall_back,
                       stone, pane, navy)
    for side, wall in ((-1, HALL_X - HALL_W / 2), (1, HALL_X + HALL_W / 2)):
        for y in (HALL_Y - 5.4, HALL_Y, HALL_Y + 5.4):
            for z in (hall_floor + 1.55, hall_floor + 5.20):
                _hs_window(col, "hs_hall_side", 2.10, 2.20, None, y, z,
                           (side, 0), wall, stone, pane, navy)
    _hs_entrance(col, "hs_hall_entry", HALL_X, hall_front, hall_floor,
                 QUAD_TOP, 8.60, 7.60, 2.95, stone, brick_dark, darkpane,
                 navy, navy, steel, steps=3)
    # The name, on the face the town's cameras look at.
    add_box(col, "hs_hall_name_band", 8.20, .20, 1.50,
            HALL_X, hall_front - 1.28, hall_floor + 5.24, navy)
    add_text(col, "hs_hall_name_1", "FOLLOWVILLE", .56, .06,
             HALL_X, hall_front - 1.40, hall_floor + 6.42, gold)
    add_text(col, "hs_hall_name_2", "HIGH SCHOOL", .56, .06,
             HALL_X, hall_front - 1.40, hall_floor + 5.72, gold)
    # Clock in the entrance gable, above the name.
    add_box(col, "hs_hall_gable", 7.40, 1.14, 2.40,
            HALL_X, hall_front - .60, hall_floor + 7.60, stone)
    add_prism_roof(col, "hs_hall_gable_roof", 7.90, 1.54, 1.05,
                   HALL_X, hall_front - .60, hall_floor + 10.00, slate)
    add_box(col, "hs_hall_clock_rim", 2.36, .18, 2.36,
            HALL_X, hall_front - 1.26, hall_floor + 7.85, navy)
    clock = add_ngon_cone(col, "hs_hall_clock", 1.02, 1.02, .20, 24,
                          HALL_X, hall_front - 1.38, hall_floor + 9.03, paint)
    clock.rotation_euler.x = math.pi / 2
    add_box(col, "hs_hall_clock_hand_v", .10, .12, .70,
            HALL_X, hall_front - 1.63, hall_floor + 9.03, navy)
    hand = add_box(col, "hs_hall_clock_hand_h", .60, .12, .10,
                   HALL_X + .20, hall_front - 1.64, hall_floor + 9.16, navy)
    hand.rotation_euler.z = math.radians(22)

    # ── building two: the science and arts wing ─────────────────────────────
    WING_X, WING_Y, WING_W, WING_D, WING_H = 2.0, 33.5, 14.0, 17.0, 7.60
    wing_front, wing_back = WING_Y - WING_D / 2, WING_Y + WING_D / 2
    wing_floor = HS_LAWN_TOP + .48
    add_box(col, "hs_wing_base", WING_W + 1.20, WING_D + 1.20, .48,
            WING_X, WING_Y, HS_LAWN_TOP, stone_dark)
    add_box(col, "hs_wing_body", WING_W, WING_D, WING_H,
            WING_X, WING_Y, wing_floor, brick)
    add_box(col, "hs_wing_plinth_course", WING_W + .26, WING_D + .26, .80,
            WING_X, WING_Y, wing_floor, stone)
    add_box(col, "hs_wing_belt", WING_W + .20, WING_D + .20, .30,
            WING_X, WING_Y, wing_floor + 3.60, stone)
    add_box(col, "hs_wing_parapet", WING_W + .54, WING_D + .54, .98,
            WING_X, WING_Y, wing_floor + WING_H - .34, stone)
    add_box(col, "hs_wing_roof", WING_W + .30, WING_D + .30, .24,
            WING_X, WING_Y, wing_floor + WING_H - .32, slate)
    add_box(col, "hs_wing_coping", WING_W + .80, WING_D + .80, .18,
            WING_X, WING_Y, wing_floor + WING_H + .64, stone_dark)
    # A north-lit studio clerestory, and the rooftop plant beside it.
    add_box(col, "hs_wing_clerestory", 9.20, 3.20, 1.70,
            WING_X, WING_Y + 3.40, wing_floor + WING_H - .10, stone)
    add_box(col, "hs_wing_clerestory_glass", 8.40, .20, 1.10, WING_X,
            mounted_face_center(WING_Y + 1.80, -1, .20, .15),
            wing_floor + WING_H + .20, pane)
    add_box(col, "hs_wing_clerestory_cap", 9.64, 3.62, .20,
            WING_X, WING_Y + 3.40, wing_floor + WING_H + 1.60, slate)
    add_box(col, "hs_wing_plant", 3.20, 2.20, 1.05,
            WING_X - 4.20, WING_Y - 4.60, wing_floor + WING_H - .10, charcoal)
    add_box(col, "hs_wing_plant_grille", 2.60, .18, .64,
            WING_X - 4.20, WING_Y - 5.76, wing_floor + WING_H + .08, steel)
    for index, x in enumerate((WING_X - 4.80, WING_X + 4.80)):
        for level, z in ((0, wing_floor + 1.45), (1, wing_floor + 5.00)):
            _hs_window(col, "hs_wing_s%d%d" % (index, level), 2.60, 2.30,
                       x, None, z, (0, -1), wing_front, stone, pane, navy)
    for index, x in enumerate((WING_X - 4.60, WING_X + 4.60)):
        for level, z in ((0, wing_floor + 1.45), (1, wing_floor + 5.00)):
            _hs_window(col, "hs_wing_n%d%d" % (index, level), 2.60, 2.30,
                       x, None, z, (0, 1), wing_back, stone, pane, navy)
    for side, wall in ((-1, WING_X - WING_W / 2), (1, WING_X + WING_W / 2)):
        for y in (WING_Y - 4.6, WING_Y + 1.0, WING_Y + 6.0):
            for z in (wing_floor + 1.45, wing_floor + 5.00):
                _hs_window(col, "hs_wing_side", 2.20, 2.30, None, y, z,
                           (side, 0), wall, stone, pane, navy)
    _hs_entrance(col, "hs_wing_entry", WING_X, wing_front, wing_floor,
                 QUAD_TOP, 5.60, 5.70, 2.70, stone, brick_dark, darkpane,
                 navy, navy, steel, steps=2)
    add_box(col, "hs_wing_sign", 4.60, .18, .66,
            WING_X, wing_front - 1.24, wing_floor + 4.16, navy)
    add_text(col, "hs_wing_sign_text", "SCIENCE & ARTS", .34, .05,
             WING_X, wing_front - 1.36, wing_floor + 4.49, gold)

    # ── building three: the gymnasium ───────────────────────────────────────
    GYM_X, GYM_Y, GYM_W, GYM_D, GYM_H = 21.50, 34.50, 17.0, 19.0, 9.80
    gym_front, gym_back = GYM_Y - GYM_D / 2, GYM_Y + GYM_D / 2
    gym_floor = HS_LAWN_TOP + .52
    add_box(col, "hs_gym_base", GYM_W + 1.30, GYM_D + 1.30, .52,
            GYM_X, GYM_Y, HS_LAWN_TOP, stone_dark)
    add_box(col, "hs_gym_body", GYM_W, GYM_D, GYM_H,
            GYM_X, GYM_Y, gym_floor, brick)
    add_box(col, "hs_gym_plinth_course", GYM_W + .28, GYM_D + .28, 1.70,
            GYM_X, GYM_Y, gym_floor, stone)
    add_box(col, "hs_gym_cornice", GYM_W + .58, GYM_D + .58, .46,
            GYM_X, GYM_Y, gym_floor + GYM_H - .46, stone)
    add_prism_roof(col, "hs_gym_roof", GYM_W + 1.10, GYM_D + 1.10, 3.30,
                   GYM_X, GYM_Y, gym_floor + GYM_H, slate)
    add_box(col, "hs_gym_ridge_vent", 7.20, 1.90, .90,
            GYM_X, GYM_Y, gym_floor + GYM_H + 2.20, stone)
    add_box(col, "hs_gym_ridge_vent_cap", 7.70, 2.30, .20,
            GYM_X, GYM_Y, gym_floor + GYM_H + 3.10, slate)
    # One tall volume, so it gets a high clerestory band rather than two
    # storeys of classroom windows -- the same brick, read differently.
    for index, x in enumerate((GYM_X - 6.20, GYM_X + 6.20)):
        _hs_window(col, "hs_gym_s%d" % index, 3.20, 2.40, x, None,
                   gym_floor + 6.30, (0, -1), gym_front, stone, pane, navy)
    for index, x in enumerate((GYM_X - 5.40, GYM_X, GYM_X + 5.40)):
        _hs_window(col, "hs_gym_n%d" % index, 3.20, 2.40, x, None,
                   gym_floor + 6.30, (0, 1), gym_back, stone, pane, navy)
    for side, wall in ((-1, GYM_X - GYM_W / 2), (1, GYM_X + GYM_W / 2)):
        for y in (GYM_Y - 5.6, GYM_Y, GYM_Y + 5.6):
            _hs_window(col, "hs_gym_side", 3.20, 2.40, None, y,
                       gym_floor + 6.30, (side, 0), wall, stone, pane, navy)
    _hs_entrance(col, "hs_gym_entry", GYM_X, gym_front, gym_floor,
                 QUAD_TOP, 7.20, 6.90, 2.95, stone, brick_dark, darkpane,
                 navy, gold, steel, steps=2)
    add_box(col, "hs_gym_sign", 6.00, .18, .76,
            GYM_X, gym_front - 1.24, gym_floor + 4.60, navy)
    add_text(col, "hs_gym_sign_text", "GYMNASIUM", .44, .05,
             GYM_X, gym_front - 1.36, gym_floor + 4.98, gold)

    # ── breezeways linking the three buildings ──────────────────────────────
    # Their paving runs in under the quad and in under each building's base, so
    # every join is one slab inside another rather than two faces meeting.
    for link_x in (-7.0, 11.0):
        add_box(col, "hs_link_walk", 4.20, 22.0, LINK_TOP - HS_WALK_Z,
                link_x, 33.0, HS_WALK_Z, concrete)
        add_box(col, "hs_link_roof", 4.90, 9.60, .26,
                link_x, 33.5, HS_LAWN_TOP + 3.35, slate)
        add_box(col, "hs_link_beam", 4.30, 9.20, .22,
                link_x, 33.5, HS_LAWN_TOP + 3.13, stone)
        for post_y in (29.6, 33.5, 37.4):
            for side in (-1, 1):
                add_ngon_cone(col, "hs_link_post", .20, .18, 3.10, 10,
                              link_x + side * 1.90, post_y,
                              LINK_TOP - .02, stone)

    # ── the stadium: infield, running track, football field ─────────────────
    # Layer elevations from the infield up.  Each surface's underside is buried
    # in the one below rather than resting on its face, and each painted layer
    # clears the surface it is painted on, so nothing here is coplanar.
    END_ZONE_Z, END_ZONE_H = .240, .048          # top .288
    FIELD_Z, FIELD_H = .240, .056                # top .296
    PAINT_Z, PAINT_H = .300, .022                # top .322
    track_outer_r = HS_TRACK_INNER_R + HS_TRACK_LANES * HS_TRACK_LANE_W
    _add_obround_pad(col, "hs_infield", HS_TRACK_CX, HS_TRACK_CY,
                     HS_TRACK_HALF_STRAIGHT, HS_TRACK_INNER_R + 1.20,
                     HS_TURF_Z, HS_TURF_H, turf)
    _add_obround_band(col, "hs_track", HS_TRACK_CX, HS_TRACK_CY,
                      HS_TRACK_HALF_STRAIGHT, HS_TRACK_INNER_R,
                      track_outer_r, HS_TRACK_Z, HS_TRACK_H, rubber)
    for lane in range(1, HS_TRACK_LANES):
        radius = HS_TRACK_INNER_R + lane * HS_TRACK_LANE_W
        _add_obround_band(col, "hs_track_lane_%d" % lane, HS_TRACK_CX,
                          HS_TRACK_CY, HS_TRACK_HALF_STRAIGHT,
                          radius - .05, radius + .05,
                          HS_TRACK_PAINT_Z, .02, paint)
    _add_obround_band(col, "hs_track_outer_line", HS_TRACK_CX, HS_TRACK_CY,
                      HS_TRACK_HALF_STRAIGHT, track_outer_r - .16,
                      track_outer_r - .06, HS_TRACK_PAINT_Z, .02, paint)
    # The kerb on the inside of lane one, standing clear of the running surface.
    _add_obround_band(col, "hs_track_kerb", HS_TRACK_CX, HS_TRACK_CY,
                      HS_TRACK_HALF_STRAIGHT, HS_TRACK_INNER_R - .10,
                      HS_TRACK_INNER_R + .08, HS_TRACK_Z, HS_TRACK_H + .07,
                      paint)
    # The football field.  The end zones reach 0.60m in under the playing
    # surface so the two slabs meet inside each other, not face to face.
    goal_south = HS_TRACK_CY - HS_FIELD_L / 2 + HS_END_ZONE
    goal_north = HS_TRACK_CY + HS_FIELD_L / 2 - HS_END_ZONE
    for sign, tag in ((-1, "south"), (1, "north")):
        add_box(col, "hs_end_zone_" + tag, HS_FIELD_W, HS_END_ZONE + .60,
                END_ZONE_H, HS_TRACK_CX,
                HS_TRACK_CY + sign * (HS_FIELD_L / 2 - HS_END_ZONE / 2 + .30),
                END_ZONE_Z, navy)
    add_box(col, "hs_field", HS_FIELD_W, goal_north - goal_south, FIELD_H,
            HS_TRACK_CX, HS_TRACK_CY, FIELD_Z, turf)
    line_count = int(round((goal_north - goal_south) / 4.0))
    for index in range(line_count + 1):
        y = goal_south + index * (goal_north - goal_south) / line_count
        add_box(col, "hs_yard_line", HS_FIELD_W - .60, .22, PAINT_H,
                HS_TRACK_CX, y, PAINT_Z, paint)
    for index in range(line_count * 2):
        y = (goal_south + (index + .5) *
             (goal_north - goal_south) / (line_count * 2))
        for hash_x in (HS_TRACK_CX - 4.40, HS_TRACK_CX + 4.40):
            add_box(col, "hs_hash", .18, .70, PAINT_H, hash_x, y, PAINT_Z,
                    paint)
    for side in (-1, 1):
        add_box(col, "hs_sideline", .30, HS_FIELD_L - .60, PAINT_H,
                HS_TRACK_CX + side * (HS_FIELD_W / 2 - .15), HS_TRACK_CY,
                PAINT_Z, paint)
        add_box(col, "hs_end_line", HS_FIELD_W, .30, PAINT_H, HS_TRACK_CX,
                HS_TRACK_CY + side * (HS_FIELD_L / 2 - .15), PAINT_Z, paint)
    add_box(col, "hs_midfield_mark", 2.60, .26, PAINT_H + .006,
            HS_TRACK_CX, HS_TRACK_CY, PAINT_Z + .008, gold)
    for side in (-1, 1):
        post_y = HS_TRACK_CY + side * (HS_FIELD_L / 2 - .30)
        add_box(col, "hs_goal_base", 1.00, 1.00, .26,
                HS_TRACK_CX, post_y, HS_TURF_Z + HS_TURF_H - .03, paint)
        add_ngon_cone(col, "hs_goal_stem", .16, .14, 3.05, 8,
                      HS_TRACK_CX, post_y, HS_TURF_Z + HS_TURF_H + .21, gold)
        add_box(col, "hs_goal_crossbar", 5.80, .17, .17,
                HS_TRACK_CX, post_y, HS_TURF_Z + HS_TURF_H + 3.18, gold)
        for upright in (-2.75, 2.75):
            add_ngon_cone(col, "hs_goal_upright", .13, .11, 3.40, 8,
                          HS_TRACK_CX + upright, post_y,
                          HS_TURF_Z + HS_TURF_H + 3.35, gold)

    # ── home stand, on the west touchline ───────────────────────────────────
    # Each tier reaches half a metre back under the one above it, so the only
    # faces two neighbouring tiers share are buried, and every visible riser is
    # a single exposed face at its own height.
    STAND_FRONT, STAND_Y, STAND_L = -22.40, -17.0, 42.0
    STAND_TIERS, TIER_DEPTH, TIER_RISE = 6, 1.40, .42
    add_box(col, "hs_stand_apron", 1.20, STAND_L + 2.0, STADIUM_TOP - HS_WALK_Z,
            STAND_FRONT + .60, STAND_Y, HS_WALK_Z, concrete)
    for tier in range(STAND_TIERS):
        tread = HS_LAWN_TOP + .55 + tier * TIER_RISE
        east = STAND_FRONT - tier * TIER_DEPTH
        west = STAND_FRONT - (tier + 1) * TIER_DEPTH - .50
        add_box(col, "hs_stand_tier_%d" % tier, east - west, STAND_L,
                tread - HS_LAWN_TOP + .30, (east + west) / 2, STAND_Y,
                HS_LAWN_TOP - .30, concrete)
        add_box(col, "hs_stand_seat_%d" % tier, TIER_DEPTH - .34,
                STAND_L - .60, .10, east - TIER_DEPTH / 2 + .02, STAND_Y,
                tread + .02, navy if tier % 2 else gold)
    stand_back = STAND_FRONT - STAND_TIERS * TIER_DEPTH - .50
    stand_top = HS_LAWN_TOP + .55 + (STAND_TIERS - 1) * TIER_RISE
    add_box(col, "hs_stand_back_wall", .50, STAND_L + .60, 1.18,
            stand_back + .25, STAND_Y, stand_top, concrete)
    # Full-height ends, wrapped round the tiers rather than set inside them:
    # six tiers finishing on one plane at either end is six visible faces
    # fighting over the same depth. Their own west face is buried inside the
    # retaining wall behind the bank.
    for y in (STAND_Y - STAND_L / 2 - .10, STAND_Y + STAND_L / 2 + .10):
        add_box(col, "hs_stand_end_wall", 9.50, 1.00,
                stand_top + .45 - HS_LAWN_TOP + .30,
                -26.85, y, HS_LAWN_TOP - .30, concrete)
    for y in (STAND_Y - 12.0, STAND_Y + 12.0):
        for tier in range(STAND_TIERS):
            add_box(col, "hs_stand_rail", .10, .10, .95,
                    STAND_FRONT - tier * TIER_DEPTH + .12, y,
                    HS_LAWN_TOP + .55 + tier * TIER_RISE + .04, steel)
    # Press box, on the back of the stand, looking east over the field.
    # Far enough east that the press deck clears the retaining wall behind
    # the stand instead of standing in it.
    PRESS_X, PRESS_Z = stand_back + 3.40, stand_top + 1.30
    add_box(col, "hs_press_deck", 5.60, 10.40, .34, PRESS_X, STAND_Y,
            PRESS_Z - .34, concrete)
    add_box(col, "hs_press_body", 4.80, 9.60, 2.90, PRESS_X, STAND_Y,
            PRESS_Z, stone)
    add_box(col, "hs_press_glass", .20, 8.60, 1.35,
            mounted_face_center(PRESS_X + 2.40, 1, .20, .14), STAND_Y,
            PRESS_Z + .75, darkpane)
    add_box(col, "hs_press_sill", .34, 9.10, .16,
            mounted_face_center(PRESS_X + 2.40, 1, .34, .28), STAND_Y,
            PRESS_Z + .52, stone_dark)
    add_box(col, "hs_press_roof", 5.90, 10.70, .30, PRESS_X, STAND_Y,
            PRESS_Z + 2.90, slate)
    add_box(col, "hs_press_fascia", 6.14, 10.94, .18, PRESS_X, STAND_Y,
            PRESS_Z + 2.74, navy)
    add_text(col, "hs_press_name", "FOLLOWVILLE HIGH", .50, .06,
             PRESS_X + 2.45, STAND_Y, PRESS_Z + 2.38, gold,
             rotation=(math.pi / 2, 0, math.pi / 2))

    # ── scoreboard, on the infield beyond the north end zone ────────────────
    BOARD_X = HS_TRACK_CX
    BOARD_Y = HS_TRACK_CY + HS_FIELD_L / 2 + 3.80
    board_base = HS_TURF_Z + HS_TURF_H
    for side in (-1, 1):
        add_ngon_cone(col, "hs_board_post", .26, .22, 4.30, 8,
                      BOARD_X + side * 2.90, BOARD_Y, board_base, steel)
    add_box(col, "hs_board_body", 8.20, .70, 3.60, BOARD_X, BOARD_Y,
            board_base + 4.10, navy)
    add_box(col, "hs_board_frame", 8.70, .90, .26, BOARD_X, BOARD_Y,
            board_base + 7.70, stone_dark)
    add_box(col, "hs_board_header", 7.60, .16, .80, BOARD_X,
            mounted_face_center(BOARD_Y - .35, -1, .16, .11),
            board_base + 6.70, gold)
    add_text(col, "hs_board_header_text", "FOLLOWVILLE HIGH", .44, .05,
             BOARD_X, BOARD_Y - .49, board_base + 7.10, navy)
    for index, (label, offset) in enumerate((("HOME", -2.10), ("GUEST", 2.10))):
        add_box(col, "hs_board_digits", 2.30, .16, 1.50,
                BOARD_X + offset,
                mounted_face_center(BOARD_Y - .35, -1, .16, .11),
                board_base + 4.40, charcoal)
        for digit in (-.55, .55):
            add_box(col, "hs_board_digit_glow", .78, .09, 1.20,
                    BOARD_X + offset + digit,
                    mounted_face_center(BOARD_Y - .35, -1, .09, .07),
                    board_base + 4.55, gold)
        add_text(col, "hs_board_label_%d" % index, label, .38, .04,
                 BOARD_X + offset, BOARD_Y - .41, board_base + 6.10, paint)

    # ── stadium lights, field house, fencing and planting ───────────────────
    for mast_x, mast_y in ((-18.0, 13.0), (28.0, 13.0),
                           (-18.0, -49.0), (28.0, -49.0)):
        add_box(col, "hs_mast_base", 1.60, 1.60, .40, mast_x, mast_y,
                HS_LAWN_TOP, concrete)
        add_ngon_cone(col, "hs_mast", .38, .22, 15.5, 8, mast_x, mast_y,
                      HS_LAWN_TOP + .40, steel)
        add_box(col, "hs_mast_head", 4.20, .60, .32, mast_x, mast_y,
                HS_LAWN_TOP + 15.90, charcoal)
        for offset in (-1.5, -.5, .5, 1.5):
            add_box(col, "hs_mast_lamp", .82, .46, .30,
                    mast_x + offset, mast_y - .16, HS_LAWN_TOP + 15.58,
                    charcoal)
            add_box(col, "hs_mast_lens", .64, .10, .22,
                    mast_x + offset, mast_y - .44, HS_LAWN_TOP + 15.62,
                    m["bulb"])
    FIELD_HOUSE_X, FIELD_HOUSE_Y = -25.00, -48.40
    add_box(col, "hs_field_house_base", 11.20, 10.20, .40,
            FIELD_HOUSE_X, FIELD_HOUSE_Y, HS_LAWN_TOP, stone_dark)
    add_box(col, "hs_field_house", 10.40, 9.40, 3.60,
            FIELD_HOUSE_X, FIELD_HOUSE_Y, HS_LAWN_TOP + .40, brick)
    add_box(col, "hs_field_house_band", 10.70, 9.70, .26,
            FIELD_HOUSE_X, FIELD_HOUSE_Y, HS_LAWN_TOP + 3.72, stone)
    add_prism_roof(col, "hs_field_house_roof", 11.24, 10.24, 1.50,
                   FIELD_HOUSE_X, FIELD_HOUSE_Y, HS_LAWN_TOP + 4.00, slate)
    add_box(col, "hs_field_house_counter", 5.60, .34, 1.10,
            FIELD_HOUSE_X, FIELD_HOUSE_Y + 4.86, HS_LAWN_TOP + 1.30, stone)
    add_box(col, "hs_field_house_hatch", 5.20, .18, 1.50,
            FIELD_HOUSE_X, FIELD_HOUSE_Y + 4.74, HS_LAWN_TOP + 2.46,
            charcoal)
    add_box(col, "hs_field_house_awning", 6.60, 1.90, .20,
            FIELD_HOUSE_X, FIELD_HOUSE_Y + 5.50, HS_LAWN_TOP + 4.02, navy)
    add_box(col, "hs_field_house_door", 1.40, .18, 2.18,
            FIELD_HOUSE_X + 3.90, FIELD_HOUSE_Y + 4.76, HS_LAWN_TOP + .42,
            navy)
    # Walks from the quad down the west side of the stadium to the field house.
    add_box(col, "hs_stadium_walk", 4.00, 24.0, STADIUM_TOP - HS_WALK_Z,
            -27.50, 14.0, HS_WALK_Z, concrete)
    add_box(col, "hs_stadium_walk_south", 4.00, 10.0, STADIUM_TOP - HS_WALK_Z,
            -27.50, -41.0, HS_WALK_Z, concrete)
    # Boundary fence on the two sides that face neighbours.  The west side is
    # held by the retaining wall and the north side is the campus frontage, so
    # neither is fenced.
    for post_y in range(-55, 25, 3):
        add_box(col, "hs_fence_post", .11, .11, 1.55, 31.40, float(post_y),
                HS_LAWN_TOP, steel)
    for post_x in range(-30, 32, 3):
        add_box(col, "hs_fence_post", .11, .11, 1.55, float(post_x), -55.40,
                HS_LAWN_TOP, steel)
    for rail_z in (.90, 1.52):
        add_box(col, "hs_fence_rail", .09, 79.0, .10, 31.40, -15.50,
                HS_LAWN_TOP + rail_z, steel)
        add_box(col, "hs_fence_rail", 62.0, .09, .10, 0.0, -55.40,
                HS_LAWN_TOP + rail_z, steel)
    for y in range(-52, 22, 8):
        add_ngon_cone(col, "hs_hedge_east", 1.05, .55, 1.20, 8, 30.20,
                      float(y), HS_LAWN_TOP, hedge)
    for x in range(-12, 30, 8):
        add_ngon_cone(col, "hs_hedge_south", 1.05, .55, 1.20, 8, float(x),
                      -54.20, HS_LAWN_TOP, hedge)
    # Planting goes where the oval leaves room: the four corners the track's
    # bends cut off, and the two lawn panels either side of the entrance drive.
    for x, y, scale in ((-24.0, 15.0, .88), (-11.0, 15.5, .84),
                        (24.0, 15.5, .86), (30.0, 8.0, .80),
                        (28.0, -52.0, .85), (18.0, -53.0, .78),
                        (-8.0, 52.0, .80), (6.0, 52.0, .85)):
        _hs_campus_tree(col, rng, x, y, scale)


def _add_followmart_text(col, body, size, x, y, z, material,
                         rot_euler=(math.radians(90), 0.0, 0.0),
                         extrude=0.18, bevel=0.02):
    """Extruded font text on a facade (default faces local -Y, like school front)."""
    curve = bpy.data.curves.new(name="fm_text_curve", type="FONT")
    curve.body = body
    curve.size = size
    curve.extrude = extrude
    curve.bevel_depth = bevel
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    # Prefer a clean sans if present; otherwise Blender default Bfont.
    for font_name in ("Inter", "Helvetica", "Arial", "Bfont"):
        font = bpy.data.fonts.get(font_name)
        if font is None:
            continue
        curve.font = font
        break
    obj = bpy.data.objects.new("fm_text", curve)
    obj.location = (x, y, z)
    obj.rotation_euler = rot_euler
    if material is not None:
        if obj.data.materials:
            obj.data.materials[0] = material
        else:
            obj.data.materials.append(material)
    col.objects.link(obj)
    return obj


def build_followmart(col, seed):
    """Full-block Follow Mart — tall big-box store that reads from first person.

    Classic American box store: tall panel walls, raised front parapet with a
    huge FOLLOW MART sign, deep yellow entry canopy, glass vestibule, parking
    lot with poles and cart corrals. Footprint stays inside the 3-lot pad.
    """
    rng = random.Random(seed)
    m = std_mats()
    blue = mat("NB_fm_blue", (0.10, 0.36, 0.76), .68)
    blue_mid = mat("NB_fm_blue_mid", (0.14, 0.42, 0.82), .62)
    blue_dk = mat("NB_fm_blue_dk", (0.06, 0.18, 0.48), .74)
    yellow = mat("NB_fm_yellow", (0.99, 0.80, 0.10), .48)
    yellow_dk = mat("NB_fm_yellow_dk", (0.88, 0.62, 0.06), .55)
    red = mat("NB_fm_red", (0.86, 0.16, 0.14), .68)
    cream = mat("NB_fm_cream", (0.96, 0.94, 0.90), .78)
    asphalt = mat("NB_fm_asphalt", (0.16, 0.17, 0.19), .95)
    glass = mat("NB_fm_glass", (0.42, 0.66, 0.80), .14, .06, 1.0, 0.0, .55)
    glass_dk = mat("NB_fm_glass_dk", (0.18, 0.32, 0.44), .12, .10, 1.0, 0.0, .62)
    cart = mat("NB_fm_cart", (0.52, 0.55, 0.58), .42)
    white = mat("NB_fm_white", (0.97, 0.97, 0.96), .72)
    concrete = mat("NB_fm_concrete", (0.72, 0.72, 0.70), .92)
    metal = mat("NB_fm_metal", (0.42, 0.44, 0.46), .38, .55)
    dark = mat("NB_fm_dark", (0.10, 0.11, 0.13), .55)

    # Keep overall footprint inside a 3-lot block (~39m): pad ~34m with curb margin.
    #
    # WALK SURFACE CONTRACT (must match town.html CIVIC_WALK.followmart.top):
    # place_instance sits civics at lz≈0.05. Local walkable tops must end near
    # FM_WALK_LOCAL_TOP so world feet height ≈ 0.05 + FM_WALK_LOCAL_TOP.
    # If you raise parking/plaza tops, update CIVIC_WALK.followmart.top too
    # and re-run qa_walk_surfaces.py — otherwise players sink into the lot.
    FM_WALK_LOCAL_TOP = 0.14
    FM_PLACE_Z = 0.05  # mirrors place_instance civic floor; documented only
    z0 = 0.0  # ground pieces start on the local floor (no extra lift)
    # Ground layers stack toward the entrance (pad -> parking -> drive lane ->
    # plaza -> entry walk), each overlapping the one before it in plan view.
    # Giving every layer the *same* top height (as before) put coincident
    # faces in the same plane -- classic z-fighting: the renderer has no
    # consistent answer for which face is in front, so it flickers between
    # them depending on camera angle/distance. A tiny, strictly increasing
    # offset per layer (a few mm -- invisible, and still "near
    # FM_WALK_LOCAL_TOP" for the walk-surface contract above) gives the depth
    # buffer an unambiguous order instead.
    FM_LAYER_EPS = 0.003
    PARK_TOP = FM_WALK_LOCAL_TOP + FM_LAYER_EPS
    DRIVE_TOP = FM_WALK_LOCAL_TOP + 2 * FM_LAYER_EPS
    PLAZA_TOP = FM_WALK_LOCAL_TOP + 3 * FM_LAYER_EPS
    ENTRY_TOP = FM_WALK_LOCAL_TOP + 4 * FM_LAYER_EPS
    front_y = -3.95   # main front wall (local -Y)
    body_y = 4.35
    body_d = 16.2
    body_w = 26.0
    wall_h = 11.8     # tall box walls (was ~7.6)
    parapet_h = 15.4  # raised front parapet for the big sign
    body_floor = FM_WALK_LOCAL_TOP  # building sits on the walk surface

    # ── Ground: cream pad, asphalt parking, entry plaza ─────────────────────
    # Thin decks: tops land at FM_WALK_LOCAL_TOP so feet match walkSurfaceHeight.
    add_box(col, "fm_pad", 34.0, 34.0, FM_WALK_LOCAL_TOP, 0, 0, z0, cream)
    add_box(col, "fm_parking", 31.0, 11.6, PARK_TOP - 0.02, 0, -9.8, z0 + 0.02, asphalt)
    # Center drive aisle toward the doors
    add_box(col, "fm_drive", 6.2, 11.6, DRIVE_TOP - 0.01, 0, -9.8, z0 + 0.01, asphalt)
    # Stall stripes (white) + end stops — painted ON the parking top, not above it
    for x in range(-13, 14, 3):
        if abs(x) < 3.2:
            continue
        add_box(col, "fm_stall", .12, 4.8, .03, x, -11.0, PARK_TOP, white)
        add_box(col, "fm_stop", .55, .18, .06, x, -13.15, PARK_TOP, yellow)
    # Cross-aisle dashed line near the storefront
    for x in range(-14, 15, 2):
        add_box(col, "fm_aisle_dash", 1.1, .14, .025, x, -6.35, DRIVE_TOP, white)
    # Wide concrete entry plaza (own layer — no raised pedestal)
    add_box(col, "fm_plaza", 16.0, 3.6, PLAZA_TOP - 0.02, 0, -4.9, z0 + 0.02, concrete)
    add_box(col, "fm_entry_walk", 9.5, 2.0, ENTRY_TOP - 0.02, 0, -3.35, z0 + 0.02, cream)
    # Decorative curb lip only (not a stair that lifts the walk plane)
    add_box(col, "fm_entry_lip", 10.5, .35, .06, 0, -5.7, ENTRY_TOP, cream)

    # ── Main big-box mass (tall) ────────────────────────────────────────────
    add_box(col, "fm_body", body_w, body_d, wall_h, 0, body_y, body_floor, blue)
    # Horizontal panel belts (reads as metal cladding from street)
    for z in (body_floor + 3.0, body_floor + 6.2, body_floor + 9.4):
        add_box(col, "fm_belt", body_w + 0.25, body_d + 0.25, .28,
                0, body_y, z, blue_mid)
    # Yellow cornice under parapet
    add_box(col, "fm_cornice", body_w + 0.55, body_d + 0.55, .42,
            0, body_y, body_floor + wall_h - 0.15, yellow)
    # Flat roof + HVAC lumps (silhouette from drone / tall angles)
    add_box(col, "fm_roof", body_w + 0.9, body_d + 0.9, .55,
            0, body_y, body_floor + wall_h + 0.2, cream)
    for hx, hy in ((-6.5, 6.5), (0.0, 8.0), (6.5, 5.5), (-3.0, 2.0), (4.5, 9.0)):
        add_box(col, "fm_hvac", 2.4, 1.8, 1.1, hx, hy, body_floor + wall_h + 0.7, metal)
        add_box(col, "fm_hvac_cap", 2.55, 1.95, .18, hx, hy, body_floor + wall_h + 1.7, dark)

    # Side garden / auto wing (shorter, darker blue)
    add_box(col, "fm_wing", 7.8, 11.5, 8.4, 13.2, 3.2, body_floor, blue_dk)
    add_box(col, "fm_wing_roof", 8.3, 12.0, .4, 13.2, 3.2, body_floor + 8.4, cream)
    add_box(col, "fm_wing_door", 2.4, .28, 2.8, 13.2, -2.65, body_floor + 0.1, glass_dk)
    add_box(col, "fm_wing_canopy", 4.2, 1.8, .28, 13.2, -3.4, body_floor + 3.2, yellow_dk)

    # ── Raised front parapet (the big-box “false front”) ────────────────────
    # Side wings of parapet sit on the wall; center rises higher for the sign.
    add_box(col, "fm_parapet_l", 6.5, 1.15, parapet_h - 1.2,
            -9.8, front_y + 0.35, body_floor, blue_dk)
    add_box(col, "fm_parapet_r", 6.5, 1.15, parapet_h - 1.2,
            9.8, front_y + 0.35, body_floor, blue_dk)
    add_box(col, "fm_parapet_c", 14.5, 1.35, parapet_h,
            0, front_y + 0.25, body_floor, blue_dk)
    # Yellow crown on parapet
    add_box(col, "fm_parapet_crown", 15.2, 1.5, .38,
            0, front_y + 0.2, body_floor + parapet_h, yellow)
    add_box(col, "fm_parapet_crown_l", 6.9, 1.3, .32,
            -9.8, front_y + 0.3, body_floor + parapet_h - 1.2, yellow)
    add_box(col, "fm_parapet_crown_r", 6.9, 1.3, .32,
            9.8, front_y + 0.3, body_floor + parapet_h - 1.2, yellow)
    # Vertical pilasters on the front wall
    for x in (-12.2, -8.5, -4.5, 4.5, 8.5, 12.2):
        add_box(col, "fm_pilaster", .55, .55, wall_h + 0.4,
                x, front_y + 0.15, body_floor, blue_mid)

    # ── Glass curtain storefront + vestibule ────────────────────────────────
    # Full-width lower glass band
    add_box(col, "fm_storefront", 20.5, .28, 5.6, 0, front_y - 0.05, body_floor + 0.15, glass)
    # Horizontal transom bar
    add_box(col, "fm_transom", 20.8, .32, .28, 0, front_y - 0.08, body_floor + 5.7, cream)
    # Upper clerestory glass strip under the sign
    add_box(col, "fm_clerestory", 18.0, .22, 1.8, 0, front_y - 0.02, body_floor + 6.2, glass_dk)
    # Mullions
    for x in (-9.0, -6.0, -3.0, 0.0, 3.0, 6.0, 9.0):
        add_box(col, "fm_mullion", .18, .38, 5.6, x, front_y - 0.12, body_floor + 0.15, cream)
    # Projecting glass vestibule (reads as real entry from FP)
    add_box(col, "fm_vestibule", 6.4, 2.4, 4.0, 0, front_y - 1.35, body_floor + 0.08, cream)
    add_box(col, "fm_vest_glass_f", 5.6, .16, 3.35, 0, front_y - 2.55, body_floor + 0.35, glass)
    add_box(col, "fm_vest_glass_l", .16, 2.1, 3.35, -3.1, front_y - 1.35, body_floor + 0.35, glass)
    add_box(col, "fm_vest_glass_r", .16, 2.1, 3.35, 3.1, front_y - 1.35, body_floor + 0.35, glass)
    # Sliding double doors
    add_box(col, "fm_door_l", 1.55, .14, 2.85, -.85, front_y - 2.62, body_floor + 0.25, glass_dk)
    add_box(col, "fm_door_r", 1.55, .14, 2.85, .85, front_y - 2.62, body_floor + 0.25, glass_dk)
    add_box(col, "fm_door_frame", .12, .16, 2.95, 0, front_y - 2.68, body_floor + 0.2, metal)
    add_box(col, "fm_door_bar", 3.2, .14, .12, 0, front_y - 2.68, body_floor + 1.8, metal)
    # Bollards flanking the vestibule
    for x in (-4.0, 4.0):
        add_ngon_cone(col, "fm_bollard", .16, .14, 0.95, 10, x, front_y - 2.9, body_floor, yellow)
        add_ngon_cone(col, "fm_bollard_cap", .17, .12, 0.12, 10, x, front_y - 2.9, body_floor + 0.9, metal)

    # ── Deep yellow entry canopy (big-box porch) ────────────────────────────
    canopy_z = body_floor + 5.0
    add_box(col, "fm_canopy", 22.0, 5.2, .48, 0, front_y - 2.7, canopy_z, yellow)
    add_box(col, "fm_canopy_edge", 22.4, .35, .55, 0, front_y - 5.2, canopy_z - 0.05, yellow_dk)
    add_box(col, "fm_canopy_stripe", 22.2, 5.0, .12, 0, front_y - 2.7, canopy_z + 0.42, blue_dk)
    # Support columns + base pads
    for x in (-9.5, -4.5, 0.0, 4.5, 9.5):
        add_ngon_cone(col, "fm_canopy_col", .22, .20, canopy_z - body_floor - 0.1, 10,
                      x, front_y - 4.6, body_floor, cream)
        add_box(col, "fm_col_base", .55, .55, .12, x, front_y - 4.6, body_floor, concrete)
    # Canopy underside lights
    for x in (-7.0, -2.5, 2.5, 7.0):
        add_box(col, "fm_canopy_light", .7, .45, .12, x, front_y - 3.2, canopy_z - 0.08, white)

    # ── Giant facade sign: dark bar + FOLLOW MART ───────────────────────────
    sign_z = body_floor + 10.4
    add_box(col, "fm_sign_bar", 20.5, 1.05, 3.6, 0, front_y - 0.15, sign_z, blue_dk)
    add_box(col, "fm_sign_trim_bot", 21.0, .28, .28, 0, front_y - 0.55, sign_z, yellow)
    add_box(col, "fm_sign_trim_top", 21.0, .28, .28, 0, front_y - 0.55, sign_z + 3.35, yellow)
    add_box(col, "fm_sign_trim_l", .28, .28, 3.6, -10.3, front_y - 0.55, sign_z, yellow)
    add_box(col, "fm_sign_trim_r", .28, .28, 3.6, 10.3, front_y - 0.55, sign_z, yellow)
    # Sparkle spark on the left of the wordmark
    add_box(col, "fm_logo_spark", 1.15, .35, 1.15, -9.2, front_y - 0.7, sign_z + 1.15, yellow)
    _add_followmart_text(col, "FOLLOW MART", 2.85, 0.55, front_y - 0.85, sign_z + 1.05,
                         yellow, extrude=0.22, bevel=0.025)
    # Side wall lettering for approaches along the street
    add_box(col, "fm_side_banner", .32, 14.0, 2.4, -body_w / 2 - 0.05, body_y, body_floor + 7.3, yellow)
    # Face outward (-X): +90 yaw alone mirrors the letters when viewed from the street.
    _add_followmart_text(col, "FOLLOW MART", 1.85, -body_w / 2 - 0.28, body_y, body_floor + 8.0, blue_dk,
                         rot_euler=(math.radians(90), 0.0, math.radians(-90)),
                         extrude=0.14, bevel=0.015)
    # OPEN 24 HRS strip under canopy edge (small readable plaque)
    add_box(col, "fm_hours_plaque", 4.2, .22, .7, 7.5, front_y - 5.15, canopy_z - 0.85, red)
    _add_followmart_text(col, "OPEN", 0.55, 7.5, front_y - 5.35, canopy_z - 0.55,
                         white, extrude=0.06, bevel=0.008)

    # ── Parking lot light poles (FP vertical scale) ─────────────────────────
    for x, y in ((-12.0, -12.5), (12.0, -12.5), (-12.0, -7.5), (12.0, -7.5)):
        add_ngon_cone(col, "fm_pole", .12, .10, 8.2, 8, x, y, body_floor, metal)
        add_box(col, "fm_pole_arm", 1.6, .12, .12, x + 0.7, y, body_floor + 7.9, metal)
        add_box(col, "fm_pole_lamp", .55, .35, .22, x + 1.35, y, body_floor + 7.75, white)
        add_box(col, "fm_pole_base", .4, .4, .14, x, y, body_floor, concrete)

    # ── Cart corrals ────────────────────────────────────────────────────────
    for base_x in (-11.5, -8.8):
        add_box(col, "fm_corral_rail", 2.4, .12, 1.05, base_x, -5.6, body_floor + 0.1, metal)
        add_box(col, "fm_corral_rail", 2.4, .12, 1.05, base_x, -4.55, body_floor + 0.1, metal)
        for dx in (-0.9, 0.0, 0.9):
            add_box(col, "fm_cart", .7, .55, .95, base_x + dx, -5.1, body_floor + 0.08, cart)
            add_box(col, "fm_cart_h", .1, .1, .75, base_x + dx, -5.35, body_floor + 0.65, metal)

    # ── Loading dock (east wing side) ───────────────────────────────────────
    add_box(col, "fm_dock", 6.2, 3.6, 1.35, 13.5, -3.8, body_floor, concrete)
    add_box(col, "fm_dock_bay", 3.2, .25, 2.8, 13.5, -2.05, body_floor + 1.3, dark)
    add_box(col, "fm_dock_ramp", 5.4, 2.6, .35, 13.5, -6.0, body_floor, asphalt)
    add_box(col, "fm_dock_bumper", 3.4, .35, .45, 13.5, -2.2, body_floor + 1.0, dark)

    # ── Monument roadside sign (readable walking up from the street) ────────
    add_box(col, "fm_monument_base", 3.4, 1.1, .45, -13.5, -13.2, body_floor, concrete)
    add_box(col, "fm_monument_post", .55, .55, 3.4, -13.5, -13.2, body_floor + 0.4, blue_dk)
    add_box(col, "fm_monument_face", 3.8, .45, 1.9, -13.5, -13.2, body_floor + 3.4, blue)
    add_box(col, "fm_monument_trim", 4.0, .2, .18, -13.5, -13.45, body_floor + 3.4, yellow)
    add_box(col, "fm_monument_trim2", 4.0, .2, .18, -13.5, -13.45, body_floor + 5.1, yellow)
    _add_followmart_text(col, "FOLLOW", 0.72, -13.5, -13.55, body_floor + 4.35, yellow,
                         extrude=0.08, bevel=0.01)
    _add_followmart_text(col, "MART", 0.72, -13.5, -13.55, body_floor + 3.65, yellow,
                         extrude=0.08, bevel=0.01)

    # ── Landscaping + flag court (FRONT parking corner — never inside the box)
    # Body occupies |x|<=13 and y≈-3.75..12.45. Flag lives at the SW lot corner.
    for x in (-15.2, 15.2):
        add_box(col, "fm_planter", 2.0, 1.3, .55, x, -14.2, body_floor, concrete)
        build_tree(col, rng, 0.62, x, -14.2)
    for x in (-11.5, -8.0, 8.0, 11.5):
        add_ngon_cone(col, "fm_shrub", .5, .26, .65, 10, x, -5.85, body_floor, m["lawn"])
    flag_x, flag_y = -14.8, -13.5
    add_ngon_cone(col, "fm_flagpole", .10, .07, 11.5, 8, flag_x, flag_y, body_floor, m["metal"])
    # Flag hangs +X toward the lot (clear of walls; body min x is -13)
    add_box(col, "fm_flag", 2.2, .12, 1.15, flag_x + 1.25, flag_y, body_floor + 9.6, red)
    # Small “entrance” arrow pavement mark
    add_box(col, "fm_arrow", 1.4, 2.2, .03, 0, -8.2, FM_WALK_LOCAL_TOP, yellow)
    # QA metadata object name encodes the walk contract for scripts.
    _ = FM_PLACE_Z  # referenced in comments / qa_walk_surfaces.py contract


def build_coffee_truck(col, seed):
    """Cheerful, phone-readable coffee truck for the Follow Mart forecourt."""
    m = std_mats()
    teal = mat("NB_coffee_teal", (0.08, 0.48, 0.48), rough=.62)
    teal_dark = mat("NB_coffee_teal_dark", (0.035, 0.20, 0.22), rough=.58)
    cream = mat("NB_coffee_cream", (0.96, 0.88, 0.69), rough=.72)
    coral = mat("NB_coffee_coral", (0.83, 0.24, 0.20), rough=.68)
    gold = mat("NB_coffee_gold", (0.97, 0.65, 0.12), rough=.62)
    wood = mat("NB_coffee_wood", (0.42, 0.20, 0.08), rough=.78)
    black = mat("NB_coffee_black", (0.025, 0.035, 0.04), rough=.42)
    steel = mat("NB_coffee_steel", (0.38, 0.43, 0.45), rough=.30, metallic=.72)
    glass = mat("NB_coffee_glass", (0.14, 0.32, 0.36), rough=.18, metallic=.08)
    warm = mat("NB_coffee_warm_light", (1.0, 0.56, 0.18), rough=.35)
    chalk = mat("NB_coffee_chalk", (0.045, 0.075, 0.065), rough=.90)
    white = mat("NB_coffee_white", (0.96, 0.96, 0.92), rough=.68)

    # A small paved pull-off keeps the truck grounded without reading as a
    # building foundation. Local -Y is the customer/service side.
    add_box(col, "coffee_pull_off", 12.3, 8.2, .08, 0, 0, 0, m["road"])
    for x in (-5.4, 5.4):
        add_box(col, "coffee_edge_mark", .12, 7.1, .025, x, 0, .08, cream)

    # Vehicle shell: compact delivery cab, long cafe box and roof cap.
    add_box(col, "coffee_box", 7.0, 4.7, 3.9, 1.25, 0, .38, teal)
    add_box(col, "coffee_roof", 7.45, 5.0, .32, 1.25, 0, 4.27, cream)
    add_box(col, "coffee_lower_band", 7.15, 4.82, .42, 1.25, 0, .40, teal_dark)
    add_box(col, "coffee_cab", 3.35, 4.45, 3.15, -3.75, 0, .38, cream)
    hood = add_tapered_box(col, "coffee_hood", 1.75, 4.15, 1.25, 3.85,
                           1.45, -5.45, 0, .55, .12, 0, cream)
    hood.rotation_euler.z = 0
    add_box(col, "coffee_bumper", .28, 4.35, .42, -6.05, 0, .38, steel)
    add_box(col, "coffee_windshield", .16, 3.55, 1.35, -5.18, 0, 2.08, glass)
    add_box(col, "coffee_side_window", 1.65, .14, 1.35, -3.85, -2.28, 2.08, glass)
    add_box(col, "coffee_door", 1.75, .12, 2.15, -3.65, -2.34, .62, teal)
    add_box(col, "coffee_door_handle", .34, .08, .09, -3.15, -2.45, 1.63, steel)
    for y in (-1.45, 1.45):
        add_box(col, "coffee_headlight", .12, .62, .48, -6.22, y, .86, warm)

    # Four chunky wheels with cream hubs. Cylinders are authored vertically,
    # then turned onto the truck axles.
    for x in (-3.75, 3.55):
        for y in (-2.16, 2.16):
            tire = add_ngon_cone(col, "coffee_tire", .78, .78, .42, 12,
                                 x, y, .82, black)
            tire.rotation_euler.x = math.pi / 2
            hub = add_ngon_cone(col, "coffee_hub", .34, .34, .45, 12,
                                x, y, .82, cream)
            hub.rotation_euler.x = math.pi / 2

    # Open service window, lit interior, espresso machine and pickup shelf.
    add_box(col, "coffee_window_recess", 4.55, .15, 2.15,
            1.05, -2.42, 1.48, chalk)
    add_box(col, "coffee_interior_glow", 4.20, .10, 1.80,
            1.05, -2.52, 1.62, warm)
    add_box(col, "coffee_counter", 5.05, .72, .20,
            1.05, -2.73, 1.35, wood)
    add_box(col, "coffee_espresso", 1.25, .34, .82,
            .15, -2.65, 1.55, steel)
    add_box(col, "coffee_espresso_top", 1.05, .28, .14,
            .15, -2.68, 2.34, black)
    for x in (1.45, 1.78, 2.11, 2.44):
        add_ngon_cone(col, "coffee_cup", .12, .10, .34, 10,
                      x, -2.67, 1.52, white)
    add_box(col, "coffee_pastry_case", 1.10, .38, .72,
            2.85, -2.67, 1.50, glass)

    # Lifted striped hatch with visible support arms and warm downlights.
    awning = add_box(col, "coffee_hatch", 5.15, 1.70, .18,
                     1.05, -2.87, 3.95, teal_dark)
    awning.rotation_euler.x = math.radians(-18)
    for x in (-1.05, .0, 1.05, 2.10, 3.15):
        stripe = add_box(col, "coffee_awning_stripe", .52, 1.62, .06,
                         x, -2.93, 4.06, gold if int((x + 1.05) / 1.05) % 2 else cream)
        stripe.rotation_euler.x = math.radians(-18)
    for x in (-1.35, 3.45):
        add_beam_between(col, "coffee_hatch_arm", (x, -2.42, 3.38),
                         (x, -3.45, 4.25), .07, steel)
    for x in (-.35, 2.40):
        add_box(col, "coffee_service_light", .42, .24, .10,
                x, -3.10, 3.84, warm)

    # Branding reads in both close shots and the finished skyline frame.
    add_box(col, "coffee_logo_panel", 2.05, .16, 2.25,
            4.26, -2.42, 1.52, cream)
    add_text(col, "coffee_logo", "COFFEE", .42, .06,
             4.26, -2.54, 2.70, teal_dark,
             rotation=(math.radians(90), 0, 0))
    add_text(col, "coffee_daily", "DAILY", .31, .05,
             4.26, -2.54, 2.08, coral,
             rotation=(math.radians(90), 0, 0))
    add_text(col, "coffee_grind", "GRIND", .31, .05,
             4.26, -2.54, 1.58, coral,
             rotation=(math.radians(90), 0, 0))

    # Freestanding chalkboard and a tiny two-person pickup rail.
    add_box(col, "coffee_menu", 1.55, .16, 2.05, 4.30, -3.38, .12, chalk)
    add_box(col, "coffee_menu_frame", 1.72, .22, .12, 4.30, -3.38, 2.08, wood)
    for z in (.72, 1.10, 1.48):
        add_box(col, "coffee_menu_line", 1.05, .05, .055,
                4.30, -3.51, z, cream)
    for x in (-1.85, -3.20):
        add_ngon_cone(col, "coffee_stool_post", .11, .11, .80, 10,
                      x, -3.35, .10, steel)
        add_ngon_cone(col, "coffee_stool_seat", .38, .34, .16, 12,
                      x, -3.35, .88, wood)


def _add_retaining_skirt(col, name, half_x, half_y, top_z, origin, material,
                         bury=.55, step=1.0, front_gap=None):
    """Close a level deck to the ground it stands on, all the way round.

    A wall across one face only holds up on level ground.  The moment the site
    falls away, every unwalled edge is left standing in mid-air, which is what
    happened to the rafting terrace: pinned to the highest corner of its pad,
    it showed up to 4.6m of daylight under the downhill edges.  Sampling the
    terrain at every perimeter vertex means the plinth beds into the slope
    wherever the slope happens to be.
    """
    perimeter = []

    def run(x0, y0, x1, y1):
        length = math.hypot(x1 - x0, y1 - y0)
        count = max(1, int(math.ceil(length / step)))
        for index in range(count):
            t = index / count
            perimeter.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))

    run(-half_x, -half_y, half_x, -half_y)
    run(half_x, -half_y, half_x, half_y)
    run(half_x, half_y, -half_x, half_y)
    run(-half_x, half_y, -half_x, -half_y)
    verts = [(x, y, top_z) for x, y in perimeter]
    verts += [(x, y, min(top_z - .10,
                         terrain_height(origin[0] + x, origin[1] + y) - bury))
              for x, y in perimeter]
    count = len(perimeter)
    faces = []
    for index in range(count):
        next_index = (index + 1) % count
        a, b = perimeter[index], perimeter[next_index]
        if front_gap and abs(a[1] + half_y) < .001 and abs(b[1] + half_y) < .001:
            gap_center, gap_width = front_gap
            midpoint = (a[0] + b[0]) * .5
            if abs(midpoint - gap_center) < gap_width * .5:
                continue
        faces.append((index, next_index,
                      count + next_index, count + index))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    return obj


def _build_rafting_raft(col, name, cx, cy, z, orange, dark, floor, paddle):
    """Low-poly inflatable raft with a continuous oval tube and fitted gear."""
    points = []
    for index in range(25):
        angle = math.tau * index / 24.0
        points.append((cx + 2.55 * math.cos(angle),
                       cy + 1.42 * math.sin(angle), z + .34))
    _add_connected_tube(col, name + "_inflatable_tube", points, .34,
                        orange, sides=10)
    add_box(col, name + "_floor", 4.15, 1.62, .13,
            cx, cy, z + .16, floor)
    for x in (-1.10, .0, 1.10):
        add_box(col, name + "_seat", .18, 1.55, .18,
                cx + x, cy, z + .46, dark)
    for side in (-1, 1):
        shaft_start = (cx - 1.72, cy + side * 1.02, z + .58)
        shaft_end = (cx + 1.75, cy + side * 1.02, z + .58)
        add_beam_between(col, name + "_paddle_shaft", shaft_start,
                         shaft_end, .055, paddle)
        add_box(col, name + "_paddle_blade", .58, .26, .08,
                cx + 1.94, cy + side * 1.02, z + .54, paddle)
    for side in (-1, 1):
        add_ngon_cone(col, name + "_grab_ring", .09, .09, .18, 8,
                      cx, cy + side * 1.47, z + .48, dark)


def build_rafting_station(col, seed):
    """West-bank outfitter, launch boardwalk, dock, and two complete rafts."""
    rng = random.Random(seed)
    m = std_mats()
    white = mat("NB_rafting_whitewash", (.90, .91, .85), .86)
    white_dark = mat("NB_rafting_whitewash_shadow", (.70, .74, .69), .92)
    teal = mat("NB_rafting_roof", (.08, .31, .34), .88)
    teal_dark = mat("NB_rafting_trim", (.045, .17, .19), .82)
    orange = mat("NB_rafting_orange", (.94, .27, .055), .70)
    yellow = mat("NB_rafting_lifejacket_yellow", (.98, .66, .06), .64)
    blue = mat("NB_rafting_lifejacket_blue", (.08, .34, .68), .72)
    timber = mat("NB_rafting_timber", (.31, .18, .085), .92)
    timber_light = mat("NB_rafting_boardwalk", (.54, .36, .17), .90)
    stone = mat("NB_rafting_stone", (.33, .35, .33), .98)
    gravel = mat("NB_rafting_gravel", (.43, .41, .34), .99)
    glass = mat("NB_rafting_glass", (.09, .28, .34), .12, .10, 1.0, 0.0, .64)
    rope = mat("NB_rafting_rope", (.57, .46, .27), .93)
    foam = mat("NB_rafting_whitewater", (.86, .95, .96), .38)

    base_z = max(
        terrain_height(RAFTING_STATION_X + x, RAFTING_STATION_Y + y)
        for x in (-8.0, 0.0, 8.0) for y in (-6.0, 0.0, 6.0)
    ) + .12
    water_z = river_water_height(RAFTING_STATION_Y)

    # A retained terrace makes the small outfitter sit deliberately on the
    # bank instead of floating above the river-cut slope.
    #
    # The plinth has to reach whatever the ground does on every side, not only
    # the river face. The deck is pinned to base_z, the highest corner of a pad
    # on a bank that falls about five metres diagonally, so walling the +X face
    # alone left the north and west edges cantilevered over the hillside with
    # up to 4.6m of daylight under them -- the first thing anyone walking up
    # from the meadow saw. One continuous plinth samples the terrain at every
    # perimeter vertex and beds into the slope wherever the slope is.
    add_box(col, "rafting_terrace", 18.0, 14.0, .28,
            0, 0, base_z - .18, gravel)
    _add_retaining_skirt(col, "rafting_retaining_wall", 9.0, 7.0, base_z - .12,
                         (RAFTING_STATION_X, RAFTING_STATION_Y), stone)
    # A timber coping round the whole edge. Without it the plinth reads as one
    # blank slab from below, which is what a five-metre wall of one material
    # looks like from the meadow.
    for x, y, width, depth in ((0, -7.09, 18.18, .30), (0, 7.09, 18.18, .30),
                               (-9.09, 0, .30, 13.88), (9.09, 0, .30, 13.88)):
        add_box(col, "rafting_terrace_coping", width, depth, .24,
                x, y, base_z - .20, timber_light)
    # Joints and courses dress the river face, which is the tall exposed one.
    wall_ground = min(
        terrain_height(RAFTING_STATION_X + 9.0, RAFTING_STATION_Y + y)
        for y in (-7.0, -3.5, 0.0, 3.5, 7.0)
    )
    wall_height = max(.80, base_z - .12 - wall_ground)
    for y in (-5.2, -2.6, 0, 2.6, 5.2):
        add_box(col, "rafting_retaining_joint", .70, .08, wall_height - .24,
                8.70, y, base_z - .24 - (wall_height - .24), white_dark)
    # Courses read as masonry lifts up the visible face, however tall it is.
    for course in range(1, max(2, int(wall_height / .66))):
        add_box(col, "rafting_retaining_course", .72, 13.8, .10,
                8.72, 0, base_z - .12 - course * (wall_height / max(2, int(wall_height / .66))),
                timber)

    # Compact whitewashed lodge with its public face toward the water (+X).
    add_box(col, "rafting_lodge_stone_base", 12.6, 8.6, .72,
            -1.6, 0, base_z, stone)
    add_box(col, "rafting_lodge_body", 12.0, 8.0, 3.75,
            -1.6, 0, base_z + .52, white)
    add_prism_roof(col, "rafting_lodge_roof", 12.8, 8.8, 2.18,
                   -1.6, 0, base_z + 4.22, teal)
    for x in (-7.18, 3.98):
        add_box(col, "rafting_corner_trim", .22, 8.08, 3.82,
                x, 0, base_z + .50, teal_dark)

    # River-facing ticket window, broad awning, glazed door, and readable sign.
    add_box(col, "rafting_ticket_recess", .13, 3.55, 1.75,
            4.43, -.62, base_z + 1.35, teal_dark)
    add_box(col, "rafting_ticket_glass", .08, 3.18, 1.42,
            4.51, -.62, base_z + 1.50, glass)
    add_box(col, "rafting_ticket_counter", .72, 3.85, .20,
            4.70, -.62, base_z + 1.18, timber_light)
    awning = add_box(col, "rafting_ticket_awning", 1.40, 4.15, .18,
                     4.76, -.62, base_z + 3.20, orange)
    awning.rotation_euler.y = math.radians(-12)
    add_box(col, "rafting_entry_door", .14, 1.45, 2.55,
            4.46, 2.65, base_z + .72, teal_dark)
    add_box(col, "rafting_entry_glass", .08, 1.02, 1.62,
            4.55, 2.65, base_z + 1.37, glass)
    for y in (-3.20, 3.20):
        add_box(col, "rafting_sign_support", .18, .18, 1.65,
                4.62, y, base_z + 4.28, timber)
    add_box(col, "rafting_sign_board", .20, 7.50, 1.20,
            4.68, 0, base_z + 5.28, teal_dark)
    add_text(col, "rafting_sign_text", "RIVER RUN OUTFITTERS", .32, .055,
             4.80, 0, base_z + 5.72, white,
             rotation=(math.pi / 2, 0, math.pi / 2))

    # Visible outfitting gear turns the building into a working destination.
    add_box(col, "rafting_gear_canopy", 8.1, 3.2, .18,
            -1.6, -5.35, base_z + 2.88, teal)
    for x in (-5.25, 2.05):
        add_box(col, "rafting_gear_post", .18, .18, 2.78,
                x, -5.35, base_z + .02, timber)
    add_box(col, "rafting_jacket_rail", 6.9, .12, .12,
            -1.6, -5.55, base_z + 2.25, timber)
    for index in range(10):
        x = -4.65 + index * .68
        jacket = yellow if index % 3 == 0 else orange if index % 2 else blue
        add_box(col, "rafting_lifejacket", .48, .22, .72,
                x, -5.68, base_z + 1.36, jacket)
        add_box(col, "rafting_jacket_strap", .54, .04, .08,
                x, -5.82, base_z + 1.67, teal_dark)
    for index in range(7):
        y = -3.25 + index * .72
        add_beam_between(col, "rafting_paddle_rack",
                         (-6.95, y, base_z + .55),
                         (-6.95, y, base_z + 2.75), .055, rope)
        add_box(col, "rafting_paddle_blade", .10, .42, .58,
                -6.95, y, base_z + .32, orange if index % 2 else blue)

    # Terrain-following access from Kaleidoscope Crest makes the outpost read
    # as part of the city rather than an isolated prop. See
    # world_layout.RAFTING_ACCESS_SPINE for why the line runs where it does.
    access = [(x - RAFTING_STATION_X, y - RAFTING_STATION_Y,
               terrain_height(x, y)) for x, y in rafting_access_points()]
    _add_road_strip(col, "rafting_access_road", access, gravel, width=4.4,
                    bottom_offset=.006, top_offset=.055,
                    terrain_conform=True,
                    terrain_origin=(RAFTING_STATION_X, RAFTING_STATION_Y))
    for distance in range(14, 140, 18):
        x, y, angle = _polyline_sample(access, distance)
        dash = add_box(col, "rafting_access_marker", 1.20, .13, .025,
                       x, y, terrain_height(
                           RAFTING_STATION_X + x,
                           RAFTING_STATION_Y + y) + .065, white)
        dash.rotation_euler.z = angle

    # The lane can only reach the terrace's downhill face, which stands about
    # 3.9m above grade there; a vehicle ramp onto the deck would need a 30%
    # climb. It ends on a small retained forecourt instead, with a stair up
    # the plinth.
    court_grade = terrain_height(RAFTING_STATION_X - 5.0,
                                 RAFTING_STATION_Y + 7.6)
    add_box(col, "rafting_forecourt", 8.0, 5.0, .26,
            -5.0, 9.5, court_grade - .02, gravel)
    _add_retaining_skirt(col, "rafting_forecourt_wall", 4.0, 2.5,
                         court_grade + .04,
                         (RAFTING_STATION_X - 5.0, RAFTING_STATION_Y + 9.5),
                         stone, bury=.40)
    risers = 13
    riser = (base_z - .12 - (court_grade + .24)) / risers
    for index in range(risers):
        add_box(col, "rafting_terrace_step", 3.4, .32,
                (index + 1) * riser + .34, -5.0, 11.05 - index * .32,
                court_grade - .10, stone)

    # The descending launch boardwalk follows the bank to a T-shaped dock.
    launch = [
        (5.8, 0.0, base_z + .12),
        (10.0, 0.0, base_z - .68),
        (14.5, 0.0, base_z - 1.72),
        (19.0, 0.0, water_z + .34),
        (26.0, 0.0, water_z + .34),
    ]
    _add_road_strip(col, "rafting_launch_boardwalk", launch, timber_light,
                    width=2.45, bottom_offset=-.15, top_offset=.04)
    add_box(col, "rafting_launch_dock", 8.5, 5.6, .24,
            27.5, 0, water_z + .20, timber_light)
    for x in (23.5, 27.5, 31.5):
        for y in (-2.55, 2.55):
            add_ngon_cone(col, "rafting_dock_pile", .13, .16,
                          max(.6, water_z - .25), 8,
                          x, y, .35, timber)
    for x in (24.0, 28.0, 31.0):
        for y in (-2.45, 2.45):
            add_ngon_cone(col, "rafting_dock_cleat", .11, .13, .28, 8,
                          x, y, water_z + .44, teal_dark)

    _build_rafting_raft(col, "rafting_launch_raft", 28.2, 4.25,
                        water_z + .08, orange, teal_dark, teal, timber_light)
    _build_rafting_raft(col, "rafting_stored_raft", -1.8, 5.25,
                        base_z + .18, blue, teal_dark, orange, timber_light)

    # A few authored rapids beside the launch make the river read as moving
    # water from the drone without blocking the navigable dock opening.
    for index in range(12):
        x = 27.0 + index * .72 + rng.uniform(-.25, .25)
        y = 8.0 + math.sin(index * 1.7) * 2.2
        splash = add_uv_sphere(col, "rafting_rapid_foam", .48,
                               x, y, water_z + .05, foam, 5, 7)
        splash.scale = (1.8 + rng.random(), .22, .10)


def _commons_block(col, tag, cx, cy, w, d, floors, base_z,
                   wall, accent, slate, glass, rail, m):
    """One residential block: glazed ground floor, balconied storeys above.

    Every applied detail projects clear of the wall it sits on rather than
    sharing its plane, per the project's visible-surface depth rule.
    """
    floor_h = 3.05
    body_h = floors * floor_h
    add_box(col, tag + "_body", w, d, body_h, cx, cy, base_z, wall)
    # A projecting accent bay so the mass reads as two joined slabs. It owns
    # its faces by 16cm on each side rather than sitting flush.
    add_box(col, tag + "_bay", w * .30, d + .32, body_h, cx, cy, base_z, accent)

    # ground-floor lobby: recessed glazing behind a projecting canopy
    for side in (-1, 1):
        gy = cy + side * (d / 2 + .07)
        add_box(col, tag + "_lobby_glass", w * .62, .14, 2.62,
                cx, gy, base_z + .30, glass)
    add_box(col, tag + "_canopy", w * .78, d + 1.90, .26,
            cx, cy, base_z + 3.05, accent)

    # floor bands — one per storey, projecting 9cm
    for level in range(1, floors):
        add_box(col, tag + "_band_%d" % level, w + .18, d + .18, .16,
                cx, cy, base_z + level * floor_h - .08, slate)

    # balcony stacks on both long faces
    for level in range(1, floors):
        z = base_z + level * floor_h
        for bay in (-1, 1):
            bx = cx + bay * w * .29
            for side in (-1, 1):
                by = cy + side * (d / 2 + .80)
                add_box(col, tag + "_balcony_%d" % level, w * .34, 1.60, .18,
                        bx, by, z, slate)
                add_box(col, tag + "_bal_rail_%d" % level, w * .34, .10, .92,
                        bx, by + side * .74, z + .18, rail)
                for edge in (-1, 1):
                    add_box(col, tag + "_bal_side_%d" % level, .10, 1.52,
                            .92, bx + edge * w * .17, by, z + .18, rail)
                # the window the balcony belongs to, recessed behind the slab
                add_box(col, tag + "_bal_glass_%d" % level, w * .26, .12, 2.05,
                        bx, cy + side * (d / 2 + .06), z + .30, glass)

    # end-wall windows, projecting frames
    for level in range(1, floors):
        z = base_z + level * floor_h + .55
        for side in (-1, 1):
            wx = cx + side * (w / 2 + .07)
            add_box(col, tag + "_endwin_%d" % level, .14, d * .46, 1.45,
                    wx, cy, z, glass)
            add_box(col, tag + "_endtrim_%d" % level, .10, d * .54, 1.65,
                    wx + side * .05, cy, z - .10, rail)

    # parapet, plant and a stair head so the roof is not a bare lid
    top = base_z + body_h
    add_box(col, tag + "_parapet", w + .30, d + .30, .78, cx, cy, top, slate)
    add_box(col, tag + "_roofdeck", w - .30, d - .30, .12, cx, cy, top - .06, m["cap"])
    add_box(col, tag + "_stairhead", w * .26, d * .40, 2.35,
            cx - w * .24, cy, top + .12, accent)
    for unit in (-1, 1):
        add_box(col, tag + "_plant", 2.10, 1.70, 1.05,
                cx + w * .22, cy + unit * d * .22, top + .12, m["metal"])
    return top + .78


def _commons_lounger(col, x, y, z, frame, fabric):
    add_box(col, "commons_lounger", 1.95, .74, .12, x, y, z + .30, fabric)
    add_box(col, "commons_lounger_back", .62, .70, .10, x - .62, y, z + .58, fabric)
    for side in (-1, 1):
        add_box(col, "commons_lounger_leg", .09, .09, .30,
                x + side * .78, y, z, frame)


FOOD_PLINTH_H = .44             # foundation every food home stands on
FOOD_PLINTH_SINK = .10          # bites into the ground so no base can float
FOOD_LANDING_Z = FOOD_PLINTH_H - .06    # doorstep, one threshold below the plinth
FOOD_LAYER_EMBED = .12          # how far each stacked layer sinks into the last
FOOD_BODY_SIDES = 14
FOOD_BODY_R = 4.16              # round bodies; keeps the home inside its reach
FOOD_BODY_APOTHEM = FOOD_BODY_R * math.cos(math.pi / FOOD_BODY_SIDES)
FOOD_PLINTH_R = 4.44
FOOD_WALL_H = 2.86              # tall enough to carry a 2.42m door frame


def _food_ngon_rot(sides):
    """Turn an n-gon so one flat facet is centred on local -Y.

    add_ngon_cone() puts its first vertex at `rot`, so the facet between
    vertices 0 and 1 sits half a step further round. Landing that facet on -Y
    gives every round food body a real flat wall to hang a door on. That is the
    whole reason the old doors and windows floated: they were mounted on the lot
    envelope (-d/2), which on a round body is open air -- the burger's door
    frame stood 6cm clear of the bun, and the cupcake's two windows were left
    hanging in the sky beside the frosting.
    """
    return -math.pi / 2 - math.pi / sides


def _food_facet_angle(index, sides=FOOD_BODY_SIDES):
    """Outward angle of facet `index`, counting from the front facet."""
    return -math.pi / 2 + index * math.tau / sides


def _food_facet_box(col, name, w, d, h, apothem, angle, z, material, out=.10):
    """A detail lying flat on one facet of a round body.

    `out` is how far its outward face stands proud of the facet; the rest of the
    depth stays buried in the body, so trim, ribs, seams and window frames are
    attached to something instead of hovering beside it.
    """
    centre = apothem + out - d / 2
    obj = add_box(col, name, w, d, h,
                  centre * math.cos(angle), centre * math.sin(angle),
                  z, material)
    obj.rotation_euler.z = angle + math.pi / 2
    return obj


def _food_facet_window(col, name, apothem, angle, z, trim, glass,
                       width=1.06, height=1.16):
    """_sub_window's layering, laid flat on one facet of a round body."""
    _food_facet_box(col, name + "_frame", width + .24, .14, height + .24,
                    apothem, angle, z, trim, out=.05)
    _food_facet_box(col, name + "_glass", width, .10, height,
                    apothem, angle, z + .12, glass, out=.10)
    _food_facet_box(col, name + "_mullion", .08, .07, height,
                    apothem, angle, z + .12, trim, out=.15)
    _food_facet_box(col, name + "_transom", width, .07, .08,
                    apothem, angle, z + .12 + height * .49, trim, out=.15)
    _food_facet_box(col, name + "_sill", width + .34, .26, .12,
                    apothem, angle, z - .11, trim, out=.11)


def _food_axial_cylinder(col, name, r, length, sides, x, y, z, material,
                         axis="-y"):
    """A cylinder lying along -Y or +X instead of standing up.

    add_ngon_cone() extrudes along +Z from its origin and keeps its cap circle in
    the object's own XY plane, so rotating the object turns both together and the
    cap stays centred on the origin. That is why a sausage or a doughnut tube
    placed this way lands exactly where it is asked to, and a rotated box does
    not: a box turns about its bottom face, not its middle.
    """
    obj = add_ngon_cone(col, name, r, r, length, sides, x, y, z, material)
    if axis == "-y":
        obj.rotation_euler.x = math.pi / 2
    elif axis == "+x":
        obj.rotation_euler.y = math.pi / 2
    else:
        raise ValueError("axis must be '-y' or '+x'")
    return obj


def _food_tilted_slab(col, name, length, depth, thickness, x, z, normal,
                      material):
    """A shell segment laid along a curve, its thickness following the normal.

    A stack of axis-aligned boxes on a parabola reads as a staircase, which is
    exactly what the taco's shell used to be. Rotating each segment about Y turns
    it about its own bottom face, so the origin goes on the inner surface and the
    slab grows outward from there -- the fold stays smooth and every segment
    overlaps its neighbours.
    """
    obj = add_box(col, name, length, depth, thickness, x, 0, z, material)
    obj.rotation_euler.y = math.atan2(normal[0], normal[1])
    return obj


def _food_disc(col, name, r, depth, sides, x, y, z, material):
    """A disc lying flat against a wall that faces -Y (pepperoni, badges)."""
    obj = add_ngon_cone(col, name, r, r, depth, sides, x, y, z, material)
    obj.rotation_euler.x = math.pi / 2
    return obj


def _food_dome(col, name, bands, base_z, material,
               sides=FOOD_BODY_SIDES, rot=0.0):
    """Stacked cone bands forming a dome that never dips below its own base.

    Each band starts FOOD_LAYER_EMBED below the top of the one under it and a
    few centimetres wider, so consecutive bands share no plane and the joint
    reads as a seam. The old sesame bun was a single 4.45m sphere centred 3.3m
    up: 1.15m of it hung below the world, its lower half cut down through the
    patty and the cheese, and the seeds ended up sealed inside it.

    Returns [(z0, z1, r_bot, r_top), ...] so callers can sit garnish on the real
    surface instead of guessing where it is.
    """
    spans, z = [], base_z
    for index, (r_bot, r_top, height) in enumerate(bands):
        add_ngon_cone(col, "%s_%d" % (name, index), r_bot, r_top, height,
                      sides, 0, 0, z, material, rot=rot)
        spans.append((z, z + height, r_bot, r_top))
        z += height - FOOD_LAYER_EMBED
    return spans


def _food_dome_radius(spans, z):
    """Radius of a _food_dome at height z, or None if z misses it."""
    for z0, z1, r_bot, r_top in spans:
        if z0 <= z <= z1:
            t = 0.0 if z1 == z0 else (z - z0) / (z1 - z0)
            return r_bot + (r_top - r_bot) * t
    return None


def _food_studs(col, name, spans, courses, size, material, phase=0.0):
    """Half-buried studs sitting on a dome's real skin.

    `courses` is (height, count) pairs. Each stud's centre goes one radius inside
    the surface, so it reads as a bump the dome actually carries. The old sesame
    seeds were placed on a nominal radius and ended up entirely inside the bun --
    geometry nobody could ever have seen.
    """
    index = 0
    for z, count in courses:
        surface = _food_dome_radius(spans, z)
        if surface is None:
            continue
        ring = max(0.0, surface - size)
        for step in range(count):
            angle = math.tau * step / count + phase + z
            add_uv_sphere(col, "%s_%02d" % (name, index), size,
                          ring * math.cos(angle), ring * math.sin(angle),
                          z, material, 5, 8)
            index += 1


def _food_plinth(col, front_y, stone, paving, radius=None, box=None):
    """Foundation, doorstep and one step down to the verge.

    Sunk FOOD_PLINTH_SINK into the ground so the base cannot float, and every
    part of it inside FOOD_COURT_HOME_REACH so no home paves the loop road it
    faces. The old homes ran a 4m front path out from the lot envelope; turning
    the ring to face its road would have put that path in the street, and beside
    the Rivergate connector it was already in one.

    Returns the y the front walk may start from.
    """
    z0 = -FOOD_PLINTH_SINK
    if radius is not None:
        add_ngon_cone(col, "food_plinth", radius, radius - .06,
                      FOOD_PLINTH_H + FOOD_PLINTH_SINK, FOOD_BODY_SIDES,
                      0, 0, z0, stone, rot=_food_ngon_rot(FOOD_BODY_SIDES))
    else:
        add_box(col, "food_plinth", box[0], box[1],
                FOOD_PLINTH_H + FOOD_PLINTH_SINK, 0, 0, z0, stone)
    # Foundation, landing and step get staggered undersides. They are all
    # buried, but "it is buried so the shared plane does not matter" is the
    # reasoning that let coplanar faces accumulate here in the first place.
    landing_face = front_y - .42
    add_box(col, "food_landing", 3.60, .92, FOOD_LANDING_Z + .16,
            0, landing_face + .46, -.16, stone)
    add_box(col, "food_step", 3.20, .28, .38, 0, landing_face - .10, -.22,
            paving)
    # The walk starts inside the step rather than butted up against its face.
    return landing_face - .18


def _food_walk(col, from_y, paving):
    """Paving from the bottom step to the verge, stopping short of the kerb."""
    reach = -(FOOD_COURT_HOME_REACH - .08)
    if from_y - reach < .70:
        return
    add_box(col, "food_walk", 1.45, from_y - reach, .12,
            0, (from_y + reach) / 2, -.04, paving)


def _food_entrance(col, front_y, trim, door_m, glass, m, green, green2,
                   apothem=None, window_x=None):
    """Front door and two windows, each on a wall the body really has.

    A round body takes its windows on the facets either side of the door, where
    there is geometry to carry them; a box body takes them flanking the door on
    its own front wall.
    """
    # The frame's foot sits inside the landing, not flush on top of it.
    _sub_door(col, "food_entry", 0, front_y, FOOD_LANDING_Z - .04, trim, door_m,
              glass, m)
    sill_z = FOOD_PLINTH_H + 1.02
    if apothem is not None:
        for index in (-1, 1):
            _food_facet_window(col, "food_window", apothem,
                               _food_facet_angle(index), sill_z, trim, glass)
    else:
        for side in (-1, 1):
            _sub_window(col, "food_window", side * window_x, front_y, sill_z,
                        trim, glass)
    # Planters standing on the doorstep, clear of the door and inside the reach.
    for side in (-1, 1):
        px = side * 1.40
        py = front_y - .13
        add_box(col, "food_planter", .70, .56, .40, px, py,
                FOOD_LANDING_Z - .04, trim)
        add_ngon_cone(col, "food_planter_soil", .27, .25, .10, 8,
                      px, py, FOOD_LANDING_Z + .24, green2)
        add_ngon_cone(col, "food_shrub", .30, .09, .68, 8,
                      px, py, FOOD_LANDING_Z + .30, green)


def build_food_house(col, variant):
    """One of ten food-shaped homes for the Food Court ring.

    Rebuilt 2026-08-09. Every one of these had been a stack of loose primitives
    sized to a rectangular lot envelope, which produced exactly the three faults
    reported from the plaza: pieces with nothing behind them (both windows on
    every home, the doors on the round ones, the doughnut's sprinkles), pieces
    nobody could ever see (the sesame seeds, sealed inside their own bun, and
    1.15m of that bun below the ground), and layer on layer of coincident tops
    and bottoms. Each design now stands on a sunk foundation, hangs its door and
    windows on walls that exist, and embeds every garnish in the surface it sits
    on.
    """
    style = variant % 10
    m = std_mats()
    trim = mat("NB_food_trim", (.97, .96, .92), .70)
    glass = mat("NB_food_glass", (.30, .52, .62), .14, .10, 1.0, 0.0, .58)
    door_m = mat("NB_food_door", (.42, .27, .18), .80)
    bun = mat("NB_food_bun", (.87, .64, .34), .92)
    meat = mat("NB_food_meat", (.40, .22, .15), .93)
    cheese = mat("NB_food_cheese", (.96, .74, .22), .82)
    salad = mat("NB_food_salad", (.42, .68, .32), .94)
    red = mat("NB_food_red", (.80, .21, .18), .86)
    cream = mat("NB_food_cream", (.97, .93, .86), .84)
    pink = mat("NB_food_pink", (.95, .62, .70), .84)
    choc = mat("NB_food_choc", (.36, .22, .16), .88)
    dark = mat("NB_food_dark", (.16, .18, .20), .86)
    white = mat("NB_food_white", (.98, .97, .95), .80)
    stone = mat("NB_food_plinth", (.80, .78, .73), .93)
    green = mat("NB_food_green", (.30, .52, .30), .96)
    green2 = mat("NB_food_green2", (.38, .62, .35), .96)

    body_z = FOOD_PLINTH_H - FOOD_LAYER_EMBED
    ring_rot = _food_ngon_rot(FOOD_BODY_SIDES)
    R = FOOD_BODY_R
    round_body = True
    front_y = -FOOD_BODY_APOTHEM
    plinth_radius, plinth_box, window_x = FOOD_PLINTH_R, None, None

    if style == 0:                              # sesame-bun burger
        add_ngon_cone(col, "bun_bottom", R, R, FOOD_WALL_H, FOOD_BODY_SIDES,
                      0, 0, body_z, bun, rot=ring_rot)
        shoulder_z = body_z + FOOD_WALL_H - FOOD_LAYER_EMBED
        add_ngon_cone(col, "bun_shoulder", 4.20, 3.96, .34, FOOD_BODY_SIDES,
                      0, 0, shoulder_z, bun, rot=ring_rot)
        patty_z = shoulder_z + .34 - FOOD_LAYER_EMBED
        add_ngon_cone(col, "patty", 4.30, 4.26, .58, FOOD_BODY_SIDES,
                      0, 0, patty_z, meat, rot=ring_rot)
        # Four sides turned point-first, so the corners droop over the patty the
        # way a slice of cheese does.
        add_ngon_cone(col, "cheese_slice", 4.52, 4.48, .24, 4,
                      0, 0, patty_z + .46, cheese)
        ruffle_z = patty_z + .58
        add_ngon_cone(col, "lettuce_ruffle", 4.46, 4.18, .38, 22,
                      0, 0, ruffle_z, salad)
        for leaf in range(11):
            _food_facet_box(col, "lettuce_leaf", 1.30, .54, .30, 4.18,
                            math.tau * leaf / 11, ruffle_z + .08, salad,
                            out=.40)
        crown = _food_dome(col, "bun_top",
                           [(R, 3.60, 1.02), (3.64, 2.70, 1.02),
                            (2.74, 1.52, .92), (1.56, 0.0, .82)],
                           ruffle_z + .38 - FOOD_LAYER_EMBED, bun,
                           rot=ring_rot)
        _food_studs(col, "sesame", crown,
                    [(4.45, 7), (5.30, 6), (6.10, 5)], .22, cream)

    elif style == 1:                            # pizza slice on its crust
        round_body = False
        half_w, depth = 4.15, 3.72
        front_y = -depth / 2
        plinth_radius, plinth_box, window_x = None, (9.02, 4.44), 2.55
        add_box(col, "crust_wall", half_w * 2, depth, FOOD_WALL_H,
                0, 0, body_z, bun)
        add_box(col, "crust_lip", half_w * 2 + .16, depth + .20, .52,
                0, 0, body_z - .06, bun)
        wedge_z = body_z + FOOD_WALL_H - FOOD_LAYER_EMBED
        # Tapering on one axis only: a real wedge from one mesh, and a front face
        # that stays a true vertical plane for the pepperoni to sit against.
        add_tapered_box(col, "cheese_wedge", half_w * 2 - .20, depth + .14,
                        .66, depth + .14, 5.70, 0, 0, wedge_z, 0, 0, cheese)
        slice_front = -(depth + .14) / 2
        for px, dz, pr in ((-2.15, .70, .82), (1.85, .95, .78),
                           (0.00, 2.20, .74), (-1.10, 3.30, .62),
                           (0.95, 3.55, .56), (0.00, 4.55, .48)):
            _food_disc(col, "pepperoni", pr, .22, 10,
                       px, slice_front + .03, wedge_z + dz, red)

    elif style == 2:                            # doughnut over a shopfront
        add_ngon_cone(col, "shop_wall", R, R, FOOD_WALL_H, FOOD_BODY_SIDES,
                      0, 0, body_z, cream, rot=ring_rot)
        cornice_z = body_z + FOOD_WALL_H - FOOD_LAYER_EMBED
        add_ngon_cone(col, "shop_cornice", 4.38, 4.28, .30, FOOD_BODY_SIDES,
                      0, 0, cornice_z, choc, rot=ring_rot)
        # The ring stands in the plane of the facade with a third of it sunk
        # into the storey below, so it is held up rather than balanced on a
        # tangent, and the hole still clears the roof.
        ring_r, tube = 2.45, .62
        ring_cz = cornice_z + ring_r - .35
        for index in range(18):
            angle = math.tau * index / 18
            cx = ring_r * math.cos(angle)
            cz = ring_cz + ring_r * math.sin(angle)
            _food_axial_cylinder(col, "dough", tube, 1.16, 8, cx, .58, cz, bun)
            _food_axial_cylinder(col, "icing", tube + .04, .34, 8,
                                 cx, -.52, cz, pink)
        for index in range(13):
            angle = math.tau * index / 13 + .35
            sprinkle_r = ring_r + .20 * math.cos(angle * 3)
            _food_axial_cylinder(col, "sprinkle", .13, .24, 6,
                                 sprinkle_r * math.cos(angle), -.82,
                                 ring_cz + sprinkle_r * math.sin(angle),
                                 cheese)

    elif style == 3:                            # coffee cup
        cup_r = 3.86
        front_y = -cup_r * math.cos(math.pi / FOOD_BODY_SIDES)
        plinth_radius = 4.30
        add_ngon_cone(col, "cup_base", cup_r, cup_r, FOOD_WALL_H,
                      FOOD_BODY_SIDES, 0, 0, body_z, white, rot=ring_rot)
        flare_z = body_z + FOOD_WALL_H - FOOD_LAYER_EMBED
        add_ngon_cone(col, "cup_body", 3.92, R, 2.30, FOOD_BODY_SIDES,
                      0, 0, flare_z, white, rot=ring_rot)
        # Cardboard, not chocolate: a brown sleeve directly under a near-black
        # lid read as one dark band and lost the cup entirely.
        add_ngon_cone(col, "cup_sleeve", 4.02, 4.14, 1.40, FOOD_BODY_SIDES,
                      0, 0, flare_z + .02, bun, rot=ring_rot)
        lid_z = flare_z + 2.30 - FOOD_LAYER_EMBED
        add_ngon_cone(col, "cup_lid", 4.30, 4.20, .62, FOOD_BODY_SIDES,
                      0, 0, lid_z, dark, rot=ring_rot)
        add_box(col, "cup_spout", 1.60, 1.10, .40, 0, -2.10, lid_z + .48, dark)
        add_ngon_cone(col, "cup_lid_dome", 3.10, 2.60, .36, FOOD_BODY_SIDES,
                      0, 0, lid_z + .50, dark, rot=ring_rot)
        # A handle that closes back into the cup wall at both ends.
        for index in range(7):
            t = math.pi * (index / 6) - math.pi / 2
            _food_axial_cylinder(col, "cup_handle", .26, .92, 6,
                                 3.92 + 1.05 * math.cos(t), .46,
                                 body_z + 1.45 + 1.05 * math.sin(t), white)

    elif style == 4:                            # hot dog
        round_body = False
        half_w = 4.33
        front_y = -2.20
        plinth_radius, plinth_box, window_x = None, (9.30, 4.90), 2.80
        add_box(col, "bun_lower", half_w * 2, 4.30, 1.90, 0, 0, body_z, bun)
        _food_axial_cylinder(col, "sausage", .95, 7.10, 12,
                             -3.55, 0, body_z + 2.30, meat, axis="+x")
        for end in (-3.50, 3.50):
            add_uv_sphere(col, "sausage_end", .95, end, 0, body_z + 2.30, meat)
        for side in (-1, 1):
            add_box(col, "bun_side", half_w * 2 - .16, 1.30, 3.16,
                    0, side * 1.55, body_z - .06, bun)
            _food_axial_cylinder(col, "bun_roll", .66, half_w * 2 - .16, 10,
                                 -(half_w - .08), side * 1.55, body_z + 2.90,
                                 bun, axis="+x")
        for index in range(7):
            add_box(col, "mustard", .84, .40, .34, -3.60 + index * 1.20,
                    (.45 if index % 2 else -.45), body_z + 3.02, cheese)

    elif style == 5:                            # ice cream cone
        cone_r = 3.10
        front_y = -cone_r * math.cos(math.pi / FOOD_BODY_SIDES)
        plinth_radius = 3.62
        add_ngon_cone(col, "cone_base", cone_r, cone_r, FOOD_WALL_H,
                      FOOD_BODY_SIDES, 0, 0, body_z, bun, rot=ring_rot)
        flare_z = body_z + FOOD_WALL_H - FOOD_LAYER_EMBED
        add_ngon_cone(col, "cone_flare", 3.16, 4.10, 1.90, FOOD_BODY_SIDES,
                      0, 0, flare_z, bun, rot=ring_rot)
        for waffle_r, waffle_z in ((3.18, body_z + 2.63), (3.54, flare_z + .58),
                                   (3.88, flare_z + 1.28)):
            add_ngon_cone(col, "cone_waffle", waffle_r, waffle_r - .04, .14,
                          FOOD_BODY_SIDES, 0, 0, waffle_z, choc, rot=ring_rot)
        scoop_z = flare_z + 1.90
        add_uv_sphere(col, "scoop_strawberry", 2.05, -.95, .25,
                      scoop_z - .55, pink)
        add_uv_sphere(col, "scoop_vanilla", 1.80, 1.15, -.35, scoop_z, cream)
        cherry_z = scoop_z + 1.94
        add_uv_sphere(col, "cherry", .70, .55, -.10, cherry_z, red)
        add_ngon_cone(col, "cherry_stem", .08, .06, .58, 6,
                      .55, -.10, cherry_z + .48, green)

    elif style == 6:                            # cupcake
        case_r = 3.78
        case_apothem = case_r * math.cos(math.pi / FOOD_BODY_SIDES)
        front_y = -case_apothem
        plinth_radius = 4.06
        add_ngon_cone(col, "case_body", case_r, case_r, 2.90, FOOD_BODY_SIDES,
                      0, 0, body_z, pink, rot=ring_rot)
        # Ribs on the facets of a solid case, not a ring of free-standing
        # slabs: the old paper case was twelve separate boxes with daylight
        # between them, which is what made the base read as a hanging fringe.
        for facet in range(1, FOOD_BODY_SIDES):
            _food_facet_box(col, "case_rib", .52, .30, 2.66, case_apothem,
                            _food_facet_angle(facet), body_z + .10, pink,
                            out=.24)
        rim_z = body_z + 2.90 - FOOD_LAYER_EMBED
        add_ngon_cone(col, "case_rim", 3.90, R, .70, FOOD_BODY_SIDES,
                      0, 0, rim_z, pink, rot=ring_rot)
        swirl = _food_dome(col, "frosting",
                           [(4.06, 3.20, 1.30), (3.24, 2.30, 1.20),
                            (2.34, 1.10, 1.10), (1.14, 0.0, .70)],
                           rim_z + .70 - FOOD_LAYER_EMBED, cream, rot=ring_rot)
        _food_studs(col, "sprinkle", swirl,
                    [(rim_z + 1.30, 9), (rim_z + 2.30, 7)], .17, red)
        add_uv_sphere(col, "cherry", .78, 0, 0, swirl[-1][1] + .14, red)

    elif style == 7:                            # taco
        round_body = False
        front_y = -2.75
        # 1.76 keeps the window sills' outer edges clear of the end wall's own
        # side planes; 1.82 landed them exactly on it.
        plinth_radius, plinth_box, window_x = None, (10.70, 6.20), 1.76
        span, rise, thickness = 3.90, 3.50, 1.10
        curve = rise / (span * span)
        floor_z = body_z + thickness
        # Segments laid along the fold, each tilted to the curve's normal and
        # each a slightly different depth, so no two of the overlapping slabs
        # share a front plane.
        for index in range(17):
            sx = -span + 2 * span * index / 16
            slope = 2 * curve * sx
            scale = math.hypot(slope, 1.0)
            _food_tilted_slab(col, "shell", 1.30, 5.10 - .28 * abs(sx) / span,
                              thickness, sx, floor_z + curve * sx * sx,
                              (slope / scale, -1.0 / scale), bun)
        # The fillings step up inside the fold, each one narrow enough at its
        # top to stay within the shell's inner curve.
        for fw0, fw1, fd, fh, dz, filling in (
                (1.60, 3.80, 4.30, 1.00, -.08, meat),
                (3.55, 5.10, 4.00, .85, .80, salad),
                (4.90, 5.90, 3.60, .60, 1.53, cheese)):
            add_tapered_box(col, "filling", fw0, fd, fw1, fd, fh,
                            0, 0, floor_z + dz, 0, 0, filling)
        # The open ends of the fold are walls in their own right: the front one
        # carries the entrance, the back one keeps the house closed.
        for side in (-1, 1):
            add_box(col, "shell_end", 5.10, .70, 3.16,
                    0, side * 2.40, body_z - .06, bun)

    elif style == 8:                            # fries carton
        round_body = False
        front_y = -2.40
        plinth_radius, plinth_box, window_x = None, (6.16, 5.36), 1.72
        add_box(col, "carton", 5.60, 4.80, FOOD_WALL_H, 0, 0, body_z, red)
        add_box(col, "carton_band", 5.76, 4.96, 1.00, 0, 0, body_z + 1.23,
                cheese)
        flare_z = body_z + FOOD_WALL_H - FOOD_LAYER_EMBED
        add_tapered_box(col, "carton_flare", 5.44, 4.64, 6.90, 5.90, 1.90,
                        0, 0, flare_z, 0, 0, red)
        add_box(col, "carton_lip", 7.20, 6.20, .46, 0, 0, flare_z + 1.78, red)
        # The fries rise out of the solid lip, so their cut ends are inside
        # geometry rather than hanging in the carton's mouth.
        for fx, fy, fh in ((-2.00, -1.40, 2.60), (-.70, .90, 3.40),
                           (.70, -.80, 3.00), (2.00, 1.10, 2.30),
                           (0.00, 0.00, 3.80), (-1.50, 1.60, 2.10),
                           (1.60, -1.70, 2.45), (2.40, .20, 1.90)):
            add_box(col, "fry", .66, .66, fh, fx, fy, flare_z + 1.30, cheese)

    else:                                       # sushi roll
        nori_r = 4.12
        nori_apothem = nori_r * math.cos(math.pi / FOOD_BODY_SIDES)
        front_y = -nori_apothem
        add_ngon_cone(col, "nori", nori_r, nori_r, 4.58, FOOD_BODY_SIDES,
                      0, 0, body_z, dark, rot=ring_rot)
        add_ngon_cone(col, "rice", 3.98, 3.98, 5.70, FOOD_BODY_SIDES,
                      0, 0, body_z, white, rot=ring_rot)
        rice_top = body_z + 5.70
        add_ngon_cone(col, "rice_dome", 4.04, 3.20, .50, FOOD_BODY_SIDES,
                      0, 0, rice_top - FOOD_LAYER_EMBED, white, rot=ring_rot)
        add_ngon_cone(col, "salmon_core", 2.30, 2.10, .80, 10,
                      0, 0, rice_top + .10, red, rot=ring_rot)
        for index in range(7):
            angle = math.tau * index / 7 + .4
            add_uv_sphere(col, "roe", .26, 1.40 * math.cos(angle),
                          1.40 * math.sin(angle), rice_top + .78, cheese, 5, 8)
        # The seam where the sheet laps itself, on the facet opposite the door.
        _food_facet_box(col, "nori_seam", .44, .26, 4.30, nori_apothem,
                        _food_facet_angle(FOOD_BODY_SIDES // 2),
                        body_z + .12, dark, out=.10)

    walk_from = _food_plinth(col, front_y, stone, m["cap"],
                             radius=plinth_radius, box=plinth_box)
    _food_entrance(col, front_y, trim, door_m, glass, m, green, green2,
                   apothem=(-front_y) if round_body else None,
                   window_x=window_x)
    _food_walk(col, walk_from, m["cap"])
    _merge_asset_meshes(col, "food_house_%02d" % variant)


def build_nuclear_plant(col, seed):
    """Followville Point Station: cooling tower, containment, turbine hall.

    Authored front-on-local-minus-Y like every other landmark, so the access
    road can arrive at the gate with no special casing in placement.

    The silhouette is the whole job. At the distance this will usually be seen
    -- across the river, from the log houses, from an aerial -- what reads is
    the hyperboloid cooling tower and the containment dome beside it, so those
    two carry the shape and everything else is supporting mass at a lower
    height. The tower is built as five stacked frusta rather than a true
    hyperboloid: at twenty sides the silhouette is indistinguishable and it
    stays inside the low-poly budget the rest of the town is built to.

    Every stacked segment OVERLAPS the one below by BITE rather than resting on
    it. A cone whose bottom face lands exactly on another's top face puts two
    coplanar faces in the scene; they are hidden inside the tower, but the
    depth rule is about not authoring them at all, and an overlap costs
    nothing. The same applies to everything standing on the pad, which goes
    through `seated`.

    Ground plan, all inside the declared envelope x[-38,38] y[-30,34]:
        cooling tower north-west, containment + turbine hall through the
        middle, switchyard east, admin and gate south, intake pipe running
        off the west edge toward the river.
    """
    BITE = .06

    def seated(name, w, d, h, x, y, surface, material, bite=BITE):
        add_box(col, name, w, d, h + bite, x, y, surface - bite, material)

    # The palette is deliberately not one grey. A first pass built every mass
    # out of the same pale concrete and the result read as a white blob from
    # any distance -- no separation between tower, hall and dome. Followville's
    # buildings carry real colour, so the plant gets a slate-and-teal
    # industrial identity that still sits inside the town's pastel range: warm
    # concrete for the two round masses, slate blue for the hall, teal for
    # every roof, and genuinely dark steel in the switchyard so the yard has
    # something to read against.
    # Cartoon grey: the masses stay grey, but the greys are separated hard --
    # near-white concrete against genuinely dark slate and steel -- instead of
    # the narrow mid-grey band the first pass used, which averaged out to one
    # white blob at distance. Colour is spent only where it means something:
    # teal roofs, and radioactive green on the signage.
    concrete = mat("NB_np_concrete", (.88, .88, .87), .92)
    concrete_dim = mat("NB_np_concrete_dim", (.47, .48, .50), .94)
    pad_mat = mat("NB_np_pad", (.60, .61, .59), .95)
    asphalt = mat("NB_np_asphalt", (.24, .25, .28), .94)
    hall = mat("NB_np_hall", (.60, .67, .74), .62, .20)
    rib = mat("NB_np_rib", (.26, .34, .44), .66, .30)
    steel = mat("NB_np_steel", (.52, .55, .60), .44, .60)
    steel_dark = mat("NB_np_steel_dark", (.28, .31, .36), .50, .65)
    glass = mat("NB_np_glass", (.26, .52, .64), .14, .10, 1.0, 0.0, .58)
    warn_red = mat("NB_np_warn_red", (.88, .22, .18), .78)
    warn_white = mat("NB_np_warn_white", (.95, .95, .93), .72)
    yellow = mat("NB_np_yellow", (.98, .82, .18), .76)
    dark = mat("NB_np_dark", (.15, .17, .20), .86)
    trim = mat("NB_np_trim", (.16, .62, .58), .78)
    cream = mat("NB_np_cream", (.95, .93, .88), .88)
    # The trefoils are meant to GLOW, so the emission is high -- but the base
    # colour is deep rather than bright. That is the whole trick: a light green
    # driven hard turns white and stops reading as radioactive at all, which is
    # what an earlier pass at strength 1.7 on a pale green did. A deep green
    # driven harder still reads green while throwing light.
    rad_green = mat_emissive("NB_np_rad_green", (.10, .70, .12), .34, 2.60)
    rad_plate = mat("NB_np_rad_plate", (.16, .18, .20), .82)

    PAD_TOP = .35
    add_box(col, "np_pad", 76.0, 64.0, PAD_TOP, 0.0, 2.0, 0.0, pad_mat)
    # Yard surfacing, inset from the pad edge so their side walls never align.
    add_box(col, "np_yard", 70.0, 57.0, .10, 0.0, 2.0, PAD_TOP - .02, asphalt)

    # ── cooling tower ──────────────────────────────────────────────────────
    # Five frusta: waist at 0.62 of the base radius is what makes it read as a
    # cooling tower rather than a silo.
    TX, TY = -19.0, 13.0
    tower = ((15.0, 12.4, 0.0, 11.0), (12.4, 10.4, 11.0, 10.0),
             (10.4, 9.3, 21.0, 9.0), (9.3, 9.6, 30.0, 6.0),
             (9.6, 10.9, 36.0, 5.0))
    for index, (r0, r1, z0, h) in enumerate(tower):
        add_ngon_cone(col, "np_tower_%d" % index, r0, r1, h + BITE, 20,
                      TX, TY, PAD_TOP + z0 - (BITE if index else 0.0), concrete)
    # Rim lip, and a dark disc set BELOW the rim so the throat reads as open
    # rather than as a capped cylinder.
    add_ngon_cone(col, "np_tower_rim", 11.4, 11.4, .55, 20, TX, TY,
                  PAD_TOP + 40.6, concrete_dim)
    add_ngon_cone(col, "np_tower_throat", 9.3, 9.3, .12, 20, TX, TY,
                  PAD_TOP + 39.2, dark)
    # Air intake louvres round the base: a ring of legs, which is what gives
    # the base its distinctive gapped look.
    for index in range(20):
        a = index / 20.0 * math.tau + math.pi / 20.0
        add_box(col, "np_tower_leg_%d" % index, 1.5, 1.1, 4.2,
                TX + 14.2 * math.cos(a), TY + 14.2 * math.sin(a),
                PAD_TOP - BITE, concrete_dim)
    # Two grey bands, so the tower is not one unbroken face at distance.
    for index, (z, h) in enumerate(((13.0, 1.1), (24.0, .9))):
        r = 12.4 - (z - 11.0) / 10.0 * 2.0 + .10
        add_ngon_cone(col, "np_tower_band_%d" % index, r, r - .12, h, 20,
                      TX, TY, PAD_TOP + z, concrete_dim)

    # ── radiation trefoils on the tower ────────────────────────────────────
    #
    # Three of them, at 120 degrees, so one reads from wherever the camera is.
    # The blades stand 0.34m proud of the shell and the backing disc 0.14m,
    # both well over the 5cm the depth rule wants, so nothing here is coplanar
    # with the curved facet behind it -- a sign painted flat onto a face is
    # exactly the z-fighting the rule exists to stop.
    def tower_radius(z):
        """The shell radius at height z above the pad, following the taper."""
        for r0, r1, z0, h in tower:
            if z0 <= z <= z0 + h:
                return r0 + (r1 - r0) * (z - z0) / h
        return tower[0][0] if z < 0.0 else tower[-1][1]

    # 5.0m radius -- ten metres across, about half the tower's width, which is
    # what Cade asked for and what a real plant paints on. It can be this big
    # only because it is WRAPPED: the disc spans z=11..21, exactly the second
    # frustum, and follows the taper across that whole span.
    SIGN_Z = 16.0
    for index, facing in enumerate((math.radians(300.0), math.radians(60.0),
                                    math.radians(180.0))):
        add_wrapped_sector(col, "np_trefoil_disc_%d" % index, TX, TY, facing,
                           PAD_TOP + SIGN_Z, 0.0, 5.0, 0.0, math.tau,
                           .10, .14, tower_radius, rad_plate, segments=28)
        # Blades stand off 0.32 against the disc's 0.24 front face: 8cm, over
        # the 5cm the depth rule wants between two visible surfaces.
        add_wrapped_sector(col, "np_trefoil_hub_%d" % index, TX, TY, facing,
                           PAD_TOP + SIGN_Z, 0.0, 1.05, 0.0, math.tau,
                           .32, .16, tower_radius, rad_green, segments=16)
        for blade in range(3):
            a0 = math.radians(90.0 + blade * 120.0 - 30.0)
            add_wrapped_sector(col, "np_trefoil_blade_%d_%d" % (index, blade),
                               TX, TY, facing, PAD_TOP + SIGN_Z,
                               1.70, 4.50, a0, a0 + math.radians(60.0),
                               .32, .16, tower_radius, rad_green, segments=8)

    # ── containment ────────────────────────────────────────────────────────
    CX, CY = 8.0, 15.0
    add_ngon_cone(col, "np_containment_base", 10.4, 10.4, 1.6, 18,
                  CX, CY, PAD_TOP - BITE, concrete_dim)
    add_ngon_cone(col, "np_containment", 9.5, 9.5, 13.0, 18,
                  CX, CY, PAD_TOP + 1.5, concrete)
    dome = ((9.5, 8.1, 14.5, 2.6), (8.1, 6.0, 17.1, 2.4),
            (6.0, 3.2, 19.5, 2.1), (3.2, 0.0, 21.6, 1.9))
    for index, (r0, r1, z0, h) in enumerate(dome):
        add_ngon_cone(col, "np_dome_%d" % index, r0, r1, h + BITE, 18,
                      CX, CY, PAD_TOP + z0 - BITE, concrete)
    # A single band, sized between the shell and the base so no two walls align.
    add_ngon_cone(col, "np_containment_band", 9.8, 9.8, .7, 18,
                  CX, CY, PAD_TOP + 8.2, trim)
    # A trefoil on the containment too, facing the gate. Wrapped for the same
    # reason as the tower's -- flat on a 9.5m cylinder, a 3m disc buries its
    # edges 0.49m into the shell.
    face = math.radians(258.0)

    def containment_radius(_z):
        return 9.5

    add_wrapped_sector(col, "np_dome_sign_disc", CX, CY, face,
                       PAD_TOP + 6.6, 0.0, 3.1, 0.0, math.tau,
                       .10, .13, containment_radius, rad_plate, segments=22)
    add_wrapped_sector(col, "np_dome_sign_hub", CX, CY, face,
                       PAD_TOP + 6.6, 0.0, .66, 0.0, math.tau,
                       .30, .15, containment_radius, rad_green, segments=14)
    for blade in range(3):
        a0 = math.radians(90.0 + blade * 120.0 - 30.0)
        add_wrapped_sector(col, "np_dome_sign_%d" % blade, CX, CY, face,
                           PAD_TOP + 6.6, 1.06, 2.80, a0,
                           a0 + math.radians(60.0), .30, .15,
                           containment_radius, rad_green, segments=8)

    # ── turbine hall ───────────────────────────────────────────────────────
    HX, HY = 6.0, -8.0
    seated("np_hall", 36.0, 15.0, 11.0, HX, HY, PAD_TOP, hall)
    add_box(col, "np_hall_roof", 34.4, 13.6, 1.1, HX, HY, PAD_TOP + 11.0, rib)
    for index in range(9):
        add_box(col, "np_hall_rib_%d" % index, 1.2, 14.4, .5,
                HX - 15.0 + index * 3.75, HY, PAD_TOP + 12.1, rib)
    for index in range(8):
        add_box(col, "np_hall_glass_%d" % index, 2.6, .22, 4.2,
                HX - 14.0 + index * 4.0, HY - 7.62, PAD_TOP + 4.2, glass)
    # Link bridge from containment to the hall, thinner than either.
    add_box(col, "np_link", 5.2, 9.0, 5.4, CX - 1.0, (CY + HY) / 2.0 + 1.0,
            PAD_TOP + 2.0, concrete_dim)

    # ── stack ──────────────────────────────────────────────────────────────
    SX, SY = 24.0, 18.0
    add_ngon_cone(col, "np_stack", 2.3, 1.5, 30.0, 12, SX, SY,
                  PAD_TOP - BITE, concrete)
    for index in range(4):
        r = 2.05 - index * .13
        add_ngon_cone(col, "np_stack_band_%d" % index, r, r, 1.7, 12,
                      SX, SY, PAD_TOP + 5.0 + index * 6.6,
                      warn_red if index % 2 == 0 else warn_white)

    # ── switchyard ─────────────────────────────────────────────────────────
    for index in range(3):
        x = 26.0 + index * 0.0
        y = -2.0 + index * 7.5
        seated("np_transformer_%d" % index, 5.4, 4.2, 3.6, x, y, PAD_TOP,
               steel_dark)
        add_box(col, "np_transformer_cap_%d" % index, 4.6, 3.4, .5, x, y,
                PAD_TOP + 3.6, dark)
        for fin in range(4):
            add_box(col, "np_transformer_fin_%d_%d" % (index, fin), .18, 3.6,
                    2.6, x - 2.0 + fin * 1.35, y, PAD_TOP + .4, dark)
        add_ngon_cone(col, "np_bushing_%d" % index, .22, .16, 1.8, 8,
                      x - 1.2, y, PAD_TOP + 4.1, warn_white)
    for index in range(4):
        x = 33.0
        y = -8.0 + index * 8.0
        for leg in ((-1.1, -1.1), (1.1, -1.1), (1.1, 1.1), (-1.1, 1.1)):
            add_box(col, "np_pylon_leg_%d_%d%d" % (index, leg[0] > 0, leg[1] > 0),
                    .34, .34, 13.0, x + leg[0], y + leg[1], PAD_TOP - BITE, steel)
        for brace in range(3):
            add_box(col, "np_pylon_brace_%d_%d" % (index, brace), 2.9, 2.9, .22,
                    x, y, PAD_TOP + 3.4 + brace * 3.4, steel)
        add_box(col, "np_pylon_arm_%d" % index, 8.4, .5, .42, x, y,
                PAD_TOP + 13.2, steel)

    # ── admin block and gate ───────────────────────────────────────────────
    AX, AY = -25.0, -19.0
    seated("np_admin", 15.0, 9.4, 7.4, AX, AY, PAD_TOP, cream)
    add_box(col, "np_admin_roof", 15.8, 10.2, .6, AX, AY, PAD_TOP + 7.4, trim)
    for floor in range(2):
        for index in range(5):
            add_box(col, "np_admin_glass_%d_%d" % (floor, index), 1.9, .22, 1.7,
                    AX - 5.4 + index * 2.7, AY - 4.76,
                    PAD_TOP + 1.5 + floor * 3.2, glass)
    seated("np_gatehouse", 4.4, 3.6, 3.2, -2.0, -26.5, PAD_TOP, concrete)
    add_box(col, "np_gatehouse_roof", 5.2, 4.4, .45, -2.0, -26.5,
            PAD_TOP + 3.2, trim)
    add_box(col, "np_barrier", 7.0, .3, .3, 3.6, -26.5, PAD_TOP + 1.5, warn_red)

    # Perimeter fence. Posts and a top rail only -- a solid panel would read as
    # a wall at this scale and hide the yard the video needs to see.
    fx, fy = 36.0, 30.0
    for index in range(-12, 13):
        x = index * 3.0
        for y in (2.0 - fy, 2.0 + fy):
            if y < 0 and -6.0 < x < 6.0:
                continue          # the gate opening
            add_box(col, "np_fence_p_%d_%d" % (index, y > 0), .18, .18, 2.4,
                    x, y, PAD_TOP - BITE, steel)
    for index in range(-9, 10):
        y = 2.0 + index * 3.2
        for x in (-fx, fx):
            add_box(col, "np_fence_q_%d_%d" % (index, x > 0), .18, .18, 2.4,
                    x, y, PAD_TOP - BITE, steel)
    for y in (2.0 - fy, 2.0 + fy):
        add_box(col, "np_fence_rail_%d" % (y > 0), 72.0, .12, .14, 0.0, y,
                PAD_TOP + 2.3, steel)
    for x in (-fx, fx):
        add_box(col, "np_fence_rail_x_%d" % (x > 0), .12, 60.0, .14, x, 2.0,
                PAD_TOP + 2.3, steel)

    # ── intake, at the west edge, pointing at the river ────────────────────
    #
    # The pipe LIES DOWN. add_ngon_cone's `rot` turns the section about its own
    # axis, it does not tip the axis over, so the first version stood five
    # cylinders on end outside the fence and they read as a row of stray silos
    # in a field. The cone is built upright and then rotated about Y here.
    seated("np_pumphouse", 8.0, 6.0, 4.0, -28.0, 6.0, PAD_TOP, concrete_dim)
    add_box(col, "np_pumphouse_roof", 8.8, 6.8, .5, -28.0, 6.0,
            PAD_TOP + 4.0, trim)
    pipe = add_ngon_cone(col, "np_intake_pipe", 1.15, 1.15, 25.0, 10,
                         -32.4, 6.0, PAD_TOP + 1.9, steel)
    pipe.rotation_euler = (0.0, math.radians(90.0), 0.0)
    for index in range(4):
        add_box(col, "np_intake_saddle_%d" % index, 1.9, 2.6, 1.35,
                -36.0 - index * 6.4, 6.0, PAD_TOP - BITE, concrete_dim)
    # A screen house where the pipe leaves the site, so the run ends at
    # something rather than in mid-air.
    seated("np_screenhouse", 4.6, 5.2, 2.8, -57.6, 6.0, PAD_TOP - .30,
           concrete_dim)
    add_box(col, "np_screenhouse_roof", 5.4, 6.0, .42, -57.6, 6.0,
            PAD_TOP + 2.5, trim)

    # Yard markings and a few parked cars' worth of bays, so the site reads as
    # worked-in rather than sealed.
    for index in range(6):
        add_box(col, "np_bay_%d" % index, .16, 4.6, .03,
                -14.0 + index * 3.4, -22.0, PAD_TOP + .09, warn_white)
    add_box(col, "np_hazard", 9.0, .5, .04, -2.0, -23.6, PAD_TOP + .09, yellow)
    # Green marker lamps along the gate run and on the stack, so the site
    # carries the same radioactive green at ground level and at the skyline.
    for index in range(7):
        add_box(col, "np_gate_lamp_%d" % index, .34, .34, .34,
                -21.0 + index * 6.4, -28.0, PAD_TOP + 2.5, rad_green)
    add_ngon_cone(col, "np_stack_lamp", .95, .95, .7, 12, SX, SY,
                  PAD_TOP + 30.2, rad_green)
    return col


def build_reactor_hall_interior(col, seed):
    """TEMPORARY interior set for the nuclear station video. Render-only.

    This is a stage, not a building. It exists so the camera can cut inside
    the plant for one sequence and is deleted afterwards -- it is never placed
    by growth, never exported to a GLB, never referenced by world_state.json,
    and nothing in the town depends on it.

    Built as an enclosed room the camera sits INSIDE, so the walls face inward
    and there is no exterior to speak of. Everything a shot might need to move
    is a separate named object -- crane bridge, trolley, hook, beacon domes,
    the pool surface -- because animating a merged mesh means animating the
    room with it.

    The set is lit by what is in it: the refuelling pool and the console
    screens are emissive, so the room reads as working machinery rather than
    as a grey box with a lamp pointed at it.
    """
    BITE = .05
    W, D, H = 46.0, 32.0, 17.0

    def seated(name, w, d, h, x, y, surface, material, bite=BITE):
        add_box(col, name, w, d, h + bite, x, y, surface - bite, material)

    floor_mat = mat("NB_rh_floor", (.32, .33, .35), .93)
    wall = mat("NB_rh_wall", (.58, .59, .60), .92)
    wall_low = mat("NB_rh_wall_low", (.40, .42, .45), .90)
    steel = mat("NB_rh_steel", (.55, .58, .62), .44, .60)
    steel_dark = mat("NB_rh_steel_dark", (.27, .29, .33), .52, .62)
    vessel = mat("NB_rh_vessel", (.72, .73, .75), .40, .55)
    yellow = mat("NB_rh_yellow", (.95, .78, .16), .74)
    hazard = mat("NB_rh_hazard", (.15, .16, .18), .86)
    # Deep base colours at modest strength. Driving a light green hard is what
    # turned the pool into a white rectangle -- an emissive surface saturates
    # to white long before it saturates to its own hue, so the colour has to
    # come from the base and only the lift from the strength.
    pool_glow = mat_emissive("NB_rh_pool", (.05, .52, .24), .18, 2.40)
    screen = mat_emissive("NB_rh_screen", (.08, .46, .52), .22, 1.50)
    beacon = mat_emissive("NB_rh_beacon", (.62, .06, .04), .30, 2.20)
    strip = mat_emissive("NB_rh_strip", (.74, .78, .72), .30, 1.10)
    rad_green = mat_emissive("NB_rh_rad", (.06, .48, .08), .34, 1.60)

    # ── shell ──────────────────────────────────────────────────────────────
    add_box(col, "rh_floor", W, D, .6, 0.0, 0.0, -.6, floor_mat)
    for name, w, d, x, y in (("n", W, .8, 0.0, D / 2), ("s", W, .8, 0.0, -D / 2),
                             ("e", .8, D, W / 2, 0.0), ("w", .8, D, -W / 2, 0.0)):
        add_box(col, "rh_wall_%s" % name, w, d, H, x, y, 0.0, wall)
        # A darker dado, inset so its face never lands on the wall's plane.
        add_box(col, "rh_dado_%s" % name, w - .10 if w > 1 else w + .22,
                d - .10 if d > 1 else d + .22, 2.6, x, y, 0.0, wall_low)
    add_box(col, "rh_ceiling", W, D, .7, 0.0, 0.0, H, wall_low)
    for index in range(7):
        add_box(col, "rh_beam_%d" % index, 1.0, D - 1.8, .8,
                -18.0 + index * 6.0, 0.0, H - .8, steel_dark)
    for index in range(6):
        add_box(col, "rh_striplight_%d" % index, 3.4, .5, .18,
                -15.0 + index * 6.0, 8.0, H - 1.0, strip)
        add_box(col, "rh_striplight_b_%d" % index, 3.4, .5, .18,
                -15.0 + index * 6.0, -9.0, H - 1.0, strip)

    # ── reactor vessel ─────────────────────────────────────────────────────
    VX, VY = -9.0, 2.0
    add_ngon_cone(col, "rh_vessel_plinth", 7.2, 7.2, 1.1, 16, VX, VY, 0.0,
                  wall_low)
    add_ngon_cone(col, "rh_vessel_ring", 6.4, 6.4, .35, 16, VX, VY, 1.05,
                  rad_green)
    add_ngon_cone(col, "rh_vessel", 5.4, 5.4, 8.4, 16, VX, VY, 1.35, vessel)
    add_ngon_cone(col, "rh_vessel_head", 5.4, 3.4, 2.0, 16, VX, VY, 9.70,
                  steel)
    add_ngon_cone(col, "rh_vessel_cap", 3.4, 0.0, 1.5, 16, VX, VY, 11.65,
                  steel)
    for index in range(8):
        a = index / 8.0 * math.tau
        add_ngon_cone(col, "rh_vessel_rod_%d" % index, .22, .22, 3.6, 6,
                      VX + 4.1 * math.cos(a), VY + 4.1 * math.sin(a), 11.4,
                      steel_dark)
    for index in range(3):
        add_ngon_cone(col, "rh_vessel_band_%d" % index, 5.55, 5.55, .3, 16,
                      VX, VY, 2.6 + index * 2.5, steel_dark)

    # ── refuelling pool, the room's main light source ──────────────────────
    # A RAISED basin, not a sunken pit. The floor is one unbroken slab and
    # add_box cannot cut a hole in it, so a pit put the glowing water inside a
    # sealed box under an opaque floor: invisible, and the room went dark
    # because this is what lights it. A basin standing proud of the floor
    # reads the same at this scale and actually shows.
    PX, PY = 11.0, 1.0
    add_box(col, "rh_pool_basin", 17.0, 12.0, .42, PX, PY, 0.0, wall_low)
    # ON the basin, not inside it. Sunk into the basin the water was sealed in
    # an opaque box for the second time -- the basin's own top face was all
    # that showed, which is why the pool read as a dark rectangle. It bites 2cm
    # into the basin so the two tops are not coplanar, and finishes 4cm below
    # the kerb so the kerb still reads as a rim.
    add_box(col, "rh_pool_water", 15.2, 10.2, .10, PX, PY, .40, pool_glow)
    for side, (w, d, x, y) in (("n", (17.4, .34, PX, PY + 5.83)),
                               ("s", (17.4, .34, PX, PY - 5.83)),
                               ("e", (.34, 12.4, PX + 8.33, PY)),
                               ("w", (.34, 12.4, PX - 8.33, PY))):
        add_box(col, "rh_pool_kerb_%s" % side, w, d, .12, x, y, .42, yellow)
        for post in range(6):
            if w > d:
                px, py = x - w / 2 + 1.2 + post * (w - 2.4) / 5.0, y
            else:
                px, py = x, y - d / 2 + 1.2 + post * (d - 2.4) / 5.0
            add_box(col, "rh_pool_post_%s_%d" % (side, post), .16, .16, 1.15,
                    px, py, .54, steel)
        add_box(col, "rh_pool_rail_%s" % side,
                w - .6 if w > d else .12, .12 if w > d else d - .6, .12,
                x, y, 1.61, steel)

    # ── gantry crane, named for animation ──────────────────────────────────
    for y in (D / 2 - 2.4, -D / 2 + 2.4):
        add_box(col, "rh_crane_rail_%d" % (y > 0), W - 2.0, .9, .5, 0.0, y,
                12.4, steel_dark)
    add_box(col, "rh_crane_bridge", 2.2, D - 4.0, 1.4, 2.0, 0.0, 12.9, steel)
    add_box(col, "rh_crane_trolley", 3.0, 3.4, 1.2, 2.0, 3.0, 11.8, steel_dark)
    add_box(col, "rh_crane_cable", .16, .16, 4.6, 2.0, 3.0, 7.2, steel_dark)
    add_box(col, "rh_crane_hook", 1.5, 1.5, 1.0, 2.0, 3.0, 6.2, yellow)

    # ── control mezzanine ──────────────────────────────────────────────────
    MX, MY = -14.0, -11.0
    add_box(col, "rh_mezz_deck", 20.0, 7.0, .55, MX, MY, 4.2, wall_low)
    for index in range(5):
        add_box(col, "rh_mezz_col_%d" % index, .55, .55, 4.2,
                MX - 8.5 + index * 4.25, MY, 0.0, steel_dark)
    for index in range(9):
        add_box(col, "rh_mezz_post_%d" % index, .14, .14, 1.15,
                MX - 9.0 + index * 2.25, MY + 3.2, 4.75, steel)
    add_box(col, "rh_mezz_rail", 19.2, .12, .12, MX, MY + 3.2, 5.82, steel)
    for index in range(4):
        x = MX - 6.6 + index * 4.4
        seated("rh_console_%d" % index, 3.2, 1.5, 1.05, x, MY - 1.0, 4.75,
               steel_dark)
        add_box(col, "rh_console_face_%d" % index, 2.7, .18, .62,
                x, MY - 1.76, 5.20, screen)
        add_box(col, "rh_console_top_%d" % index, 2.9, 1.1, .12, x, MY - 1.0,
                5.80, hazard)
    add_box(col, "rh_wall_display", 9.0, .22, 3.2, MX, MY - 3.30, 6.6, screen)
    add_box(col, "rh_wall_display_frame", 9.8, .16, 3.8, MX, MY - 3.42, 6.3,
            hazard)

    # ── pipework along the east wall ───────────────────────────────────────
    for index in range(4):
        pipe = add_ngon_cone(col, "rh_pipe_%d" % index, .85, .85, 26.0, 10,
                             W / 2 - 1.6, -12.0 + index * 3.0,
                             3.4 + index * 2.4, steel)
        pipe.rotation_euler = (math.radians(90.0), 0.0, 0.0)
        for wheel in range(3):
            add_ngon_cone(col, "rh_valve_%d_%d" % (index, wheel), .62, .62, .16,
                          10, W / 2 - 1.6, -9.0 + wheel * 8.0,
                          4.25 + index * 2.4, yellow)

    # ── beacons and floor markings ─────────────────────────────────────────
    for index, (x, y) in enumerate(((-W / 2 + 1.1, 9.0), (-W / 2 + 1.1, -9.0),
                                    (W / 2 - 1.1, 9.0), (0.0, D / 2 - 1.1))):
        add_box(col, "rh_beacon_base_%d" % index, .9, .9, .5, x, y, 9.4,
                hazard)
        add_ngon_cone(col, "rh_beacon_%d" % index, .55, .38, .75, 10, x, y,
                      9.9, beacon)
    for index in range(9):
        add_box(col, "rh_floor_stripe_%d" % index, .9, 5.0, .04,
                -20.0 + index * 2.2, -D / 2 + 4.0, .02, yellow)
    add_ring_sector(col, "rh_floor_trefoil_disc", 0.0, 3.2, 0.0, math.tau, .05,
                    -9.0, -12.5, .03, hazard, segments=18)
    for blade in range(3):
        a0 = math.radians(90.0 + blade * 120.0 - 30.0)
        add_ring_sector(col, "rh_floor_trefoil_%d" % blade, 1.05, 2.85, a0,
                        a0 + math.radians(60.0), .05, -9.0, -12.5, .09,
                        rad_green, segments=6)
    return col


def build_gas_station(col, seed):
    """A filling station: forecourt, canopy on four columns, two pump islands.

    Authored like every planned house -- front on local -Y, footprint inside the
    lot envelope -- so the reserve can hand it an ordinary street address and it
    faces its road with no special casing anywhere in placement.

    Rebuilt on day 40, when the reserve finally handed this type an address and
    it became a thing people would actually look at rather than a placeholder.
    The first version was six flat boxes and broke two standing rules: its price
    board reached x=-8.80, outside the envelope declared for a gasstation -- so
    the first one ever built would have failed check_world_geometry -- and its
    canopy deck, fascia and shop band were concentric boxes sharing side planes.

    It is built 16m wide, x in [-8.00, 8.00], NOT the 17m the reserve sets
    aside: on a suburban street frontage the wider forecourt stood 5.6m from
    its neighbours' centres and check_world_geometry wants 6.0. See the note on
    world_layout.LANDMARK_FOOTPRINTS["gasstation"], which is the extent this is
    audited at and must be kept in step with the numbers below.

    Every stacked layer here is a single centred box of a DISTINCT size, so no
    two visible faces ever land on one plane and there are no four-wall corner
    joints to share a plane obliquely. Anything mounted on a wall goes through
    mounted_face_center, which keeps its visible face clear of the wall it sits
    on while leaving the hidden side embedded, and anything resting on a surface
    goes through `seated`, which bites SEAT into it rather than sitting flush --
    a box resting exactly on another's top face puts two coplanar faces in the
    scene even though both are hidden, which is what the depth rule forbids.

    Ground plan, all of it inside the envelope:
        shop + planter along the back (+Y), forecourt and canopy at the street
        (-Y), price totem in the front-east corner clear of the canopy deck.
    """
    SEAT = .012

    def seated(name, w, d, h, x, y, surface, material, bite=SEAT):
        """Box of height h standing ON `surface`, biting into it."""
        add_box(col, name, w, d, h + bite, x, y, surface - bite, material)

    pave = mat("NB_gas_pave", (.72, .71, .68), .94)
    drive = mat("NB_gas_drive", (.34, .35, .38), .90)
    wall = mat("NB_gas_wall", (.96, .95, .91), .86)
    band = mat("NB_gas_band", (.86, .31, .25), .82)
    glass = mat("NB_gas_glass", (.30, .54, .64), .14, .10, 1.0, 0.0, .58)
    steel = mat("NB_gas_steel", (.82, .82, .84), .48, .55)
    dark = mat("NB_gas_dark", (.22, .24, .27), .84)
    white = mat("NB_gas_white", (.93, .93, .90), .70)
    green = mat("NB_gas_green", (.41, .64, .33), 1.0)
    leaf = mat("NB_gas_leaf", (.34, .57, .30), .95)

    # ── ground: concrete apron, asphalt forecourt inset inside it ───────────
    # The apron IS the declared footprint. The drive is inset 0.6m on every
    # side so the apron's top reads as a kerb margin and the two slabs share
    # neither a top surface nor a side plane.
    add_box(col, "gas_apron", 16.0, 15.0, .14, 0, -1.0, 0, pave)
    APRON = .14
    seated("gas_drive", 14.8, 9.2, .06, 0, -3.6, APRON, drive)
    DRIVE = .20

    # Two painted bays, tucked between the canopy's east edge (x=4.6) and the
    # air line, and stopping well short of the EV posts at y=0.3.
    for bx in (5.0, 6.1):
        seated("gas_bay_line", .12, 2.4, .03, bx, -3.4, DRIVE, white)

    # ── shop along the back, so the forecourt reads from the street ─────────
    SHOP_X, SHOP_Y = -3.4, 3.9
    SHOP_W, SHOP_D = 8.80, 4.4
    SHOP_FRONT = SHOP_Y - SHOP_D / 2                      # y = 1.70
    seated("gas_shop_plinth", 9.0, 4.6, .22, SHOP_X, SHOP_Y, APRON, band)
    seated("gas_shop_body", SHOP_W, SHOP_D, 3.60, SHOP_X, SHOP_Y, .36, wall)
    # Flat-roof cornice: slab oversails the wall, band steps back in, deck steps
    # back again. Three sizes, three planes, and the roof still reads as flat.
    seated("gas_shop_eaves", 9.12, 4.72, .14, SHOP_X, SHOP_Y, 3.96, wall)
    seated("gas_shop_cornice", 8.74, 4.34, .30, SHOP_X, SHOP_Y, 4.10, band)
    seated("gas_shop_deck", 8.40, 4.00, .08, SHOP_X, SHOP_Y, 4.40, dark)
    # Rooftop plant, sitting on the deck rather than floating over it.
    seated("gas_shop_hvac", 1.30, 1.00, .55, -5.9, 4.2, 4.48, steel)
    seated("gas_shop_hvac_cap", 1.42, 1.12, .10, -5.9, 4.2, 5.03, dark)
    seated("gas_shop_vent", 1.00, .82, .40, -1.4, 4.4, 4.48, steel)
    seated("gas_shop_vent_cap", 1.12, .94, .09, -1.4, 4.4, 4.88, dark)

    # Storefront. Each layer stands proud of the one behind it by a clear
    # margin, so glass, mullion and sign band never share the wall's plane.
    glass_y = mounted_face_center(SHOP_FRONT, -1, .16, .12)
    # The mullion embeds 3cm rather than the glass's 4cm, so the two do not
    # share a back plane where an end mullion laps a panel's edge.
    mull_y = mounted_face_center(SHOP_FRONT, -1, .20, .17)
    door_y = mounted_face_center(SHOP_FRONT, -1, .18, .14)
    sign_y = mounted_face_center(SHOP_FRONT, -1, .24, .20)
    add_box(col, "gas_shop_sill", 6.75, .18, .16, -4.40, glass_y, .54, white)
    for i in range(3):
        seated("gas_shop_glass", 2.05, .16, 2.10,
               -6.75 + i * 2.35, glass_y, .70, glass)
    # Flanking mullions sit inside the wall's own west/east faces rather than
    # on the arithmetic continuation of the panel pitch, which would hang the
    # end one 6cm off the corner.
    for mx in (-7.70, -5.575, -3.225, -.90):
        add_box(col, "gas_shop_mullion", .18, .20, 2.46, mx, mull_y, .60, white)
    # Door, surround and the wall behind them all stand on the plinth. Three
    # different bites, so no two of the three share a base plane.
    seated("gas_shop_door", 1.30, .18, 2.40, .10, door_y, .36, dark, bite=.018)
    seated("gas_shop_door_frame", 1.54, .14, 2.62, .10, sign_y, .36, white,
           bite=.024)
    add_box(col, "gas_shop_signband", 8.20, .24, .66, SHOP_X, sign_y, 3.20, band)
    add_box(col, "gas_shop_signface", 5.40, .12,
            .38, SHOP_X, mounted_face_center(sign_y - .12, -1, .12, .09), 3.34, wall)

    # ── canopy: four tapered columns and a four-layer deck ──────────────────
    # Centred at x=-1.2 rather than 0 so the price totem has real ground in the
    # front-east corner: at centre the deck reached x=5.5 and the board's top
    # west corner passed straight through the fascia.
    CAN_X, CAN_Y = -1.2, -3.8
    for cx in (CAN_X - 4.1, CAN_X + 4.1):
        for cy in (-6.4, -1.6):
            seated("gas_column_base", .86, .86, .16, cx, cy, DRIVE, dark)
            add_ngon_cone(col, "gas_column", .30, .24, 4.512, 8, cx, cy,
                          .36 - SEAT, steel)
    add_box(col, "gas_canopy_soffit", 10.6, 8.0, .12, CAN_X, CAN_Y, 4.86, wall)
    seated("gas_canopy_web", 11.1, 8.5, .34, CAN_X, CAN_Y, 4.98, steel)
    seated("gas_canopy_fascia", 11.6, 9.0, .46, CAN_X, CAN_Y, 5.32, band)
    seated("gas_canopy_cap", 11.3, 8.7, .10, CAN_X, CAN_Y, 5.78, wall)
    # Downlights recessed into the soffit; only the lit face hangs below it.
    # Held to +-3.1 of centre so they clear the column heads at +-4.1.
    for lx in (CAN_X - 3.1, CAN_X, CAN_X + 3.1):
        for ly in (-6.4, -1.6):
            add_box(col, "gas_downlight", .84, .84, .082, lx, ly, 4.79, white)

    # ── pump islands ────────────────────────────────────────────────────────
    # 6.0m, not 6.4m: at 6.4 the kerb reached x=3.2 and the east pair of canopy
    # columns stood on the island instead of on the forecourt beside it.
    for cy in (-6.4, -1.6):
        seated("gas_island_kerb", 6.0, 1.70, .22, CAN_X, cy, DRIVE, pave)
        seated("gas_island_top", 5.0, 1.30, .06, CAN_X, cy, .42, dark)
        for px in (CAN_X - 1.8, CAN_X + 1.8):
            seated("gas_pump_body", .95, .78, 1.55, px, cy, .48, wall)
            seated("gas_pump_cap", 1.05, .88, .14, px, cy, 2.03, band)
            # A screen on both faces: each island is served from both sides.
            for face, outward in ((cy - .39, -1), (cy + .39, 1)):
                add_box(col, "gas_pump_screen", .62, .10, .80,
                        px, mounted_face_center(face, outward, .10, .07),
                        1.16, dark)
            seated("gas_pump_boom", .14, .14, .62, px + .54, cy, 2.17, steel)
        # On the kerb rim beyond the island top, not straddling its edge.
        for bx in (CAN_X - 2.75, CAN_X + 2.75):
            add_ngon_cone(col, "gas_bollard", .13, .11, .82, 8, bx, cy,
                          .42 - SEAT, band)

    # ── forecourt furniture along the east strip, clear of the deck ─────────
    seated("gas_airwater", .70, .60, 1.25, 6.6, -1.4, DRIVE, steel)
    seated("gas_airwater_cap", .80, .70, .12, 6.6, -1.4, 1.45, band)
    for ex in (5.6, 6.9):
        seated("gas_ev_post", .38, .34, 1.62, ex, .3, DRIVE, white)
        add_box(col, "gas_ev_screen", .26, .10, .34, ex,
                mounted_face_center(.3 - .17, -1, .10, .07), 1.20, dark)
        seated("gas_ev_cap", .46, .42, .10, ex, .3, 1.82, band)
    seated("gas_bin", .60, .58, .90, -7.0, .60, DRIVE, dark)
    seated("gas_bin_lid", .70, .68, .10, -7.0, .60, 1.10, steel)

    # ── planting bed beside the shop ────────────────────────────────────────
    seated("gas_planter_kerb", 5.8, 4.0, .26, 5.0, 4.1, APRON, pave)
    seated("gas_planter_soil", 5.3, 3.5, .08, 5.0, 4.1, .40, green)
    for sx, sy, sr in ((3.4, 3.2, .62), (5.3, 5.0, .74), (6.6, 3.4, .55)):
        add_ngon_cone(col, "gas_shrub", sr, sr * .35, sr * 1.9, 7, sx, sy,
                      .48 - SEAT, leaf)

    # ── price totem, front-east, clear of the canopy in x and the shop in y ──
    TOT_X, TOT_Y = 6.45, -6.80
    seated("gas_totem_foot", .90, .90, .18, TOT_X, TOT_Y, DRIVE, dark)
    add_ngon_cone(col, "gas_totem_post", .24, .21, 3.072, 8, TOT_X, TOT_Y,
                  .38 - SEAT, steel)
    add_box(col, "gas_totem_board", 2.90, .42, 2.10, TOT_X, TOT_Y, 3.40, band)
    seated("gas_totem_cap", 3.06, .56, .16, TOT_X, TOT_Y, 5.50, dark)
    for face, outward in ((TOT_Y - .21, -1), (TOT_Y + .21, 1)):
        face_y = mounted_face_center(face, outward, .14, .10)
        add_box(col, "gas_totem_face", 2.45, .14, 1.52, TOT_X, face_y, 3.66, wall)
        add_box(col, "gas_totem_price", 1.90, .10, .62, TOT_X,
                mounted_face_center(face_y + outward * .07, outward, .10, .07),
                3.86, dark)
    _merge_asset_meshes(col, "gas_station")


def build_restaurant(col, seed):
    """A roadside diner: long glazed frontage, pitched roof, entry canopy."""
    m = std_mats()
    pave = mat("NB_din_pave", (.66, .65, .63), .95)
    wall = mat("NB_din_wall", (.94, .90, .82), .87)
    warm = mat("NB_din_warm", (.82, .44, .34), .85)
    glass = mat("NB_din_glass", (.28, .50, .60), .14, .10, 1.0, 0.0, .58)
    roof = mat("NB_din_roof", (.36, .38, .42), .86)
    trim = mat("NB_din_trim", (.98, .97, .94), .70)
    green = mat("NB_din_green", (.41, .64, .33), 1.0)

    add_box(col, "din_pad", 15.0, 13.0, .14, 0, .5, 0, pave)
    add_box(col, "din_lawn", 15.4, 2.2, .10, 0, -6.4, 0, green)

    add_box(col, "din_body", 12.0, 7.2, 3.9, 0, 2.4, .14, wall)
    add_box(col, "din_plinth", 12.3, 7.5, .45, 0, 2.4, .14, warm)
    add_prism_roof(col, "din_roof", 12.6, 7.8, 1.6, 0, 2.4, 4.04, roof)
    # Glazed street frontage, mounted clear of the wall it sits on.
    front = -1.2
    for i in range(4):
        add_box(col, "din_window", 2.15, .16, 2.15,
                -4.35 + i * 2.9, front - .10, 1.05, glass)
        add_box(col, "din_mullion", .22, .22, 2.45,
                -5.55 + i * 2.9, front - .10, .95, trim)
    add_box(col, "din_mullion", .22, .22, 2.45, 6.05 - 2.9, front - .10, .95, trim)

    add_box(col, "din_door", 1.30, .18, 2.45, 4.4, front - .12, .14, warm)
    add_box(col, "din_entry_canopy", 3.6, 1.8, .28, 4.4, front - .95, 2.85, warm)
    for px in (3.0, 5.8):
        add_ngon_cone(col, "din_entry_post", .16, .14, 2.7, 8, px, front - 1.70, .14, trim)

    # Roof sign, stood proud of the ridge rather than lying on it.
    add_box(col, "din_sign_board", 6.2, .34, 1.5, -1.2, 2.4, 5.72, warm)
    add_box(col, "din_sign_face", 5.6, .14, 1.05, -1.2, 2.21, 5.92, trim)
    for px in (-3.6, 1.2):
        add_ngon_cone(col, "din_sign_post", .14, .12, 1.7, 6, px, 2.4, 4.30, trim)

    # A couple of patio tables so the frontage is not a blank apron.
    for tx in (-4.6, -1.6):
        add_ngon_cone(col, "din_table_leg", .16, .14, .70, 6, tx, -3.6, .14, trim)
        add_ngon_cone(col, "din_table_top", 1.05, 1.05, .12, 10, tx, -3.6, .84, wall)
    _merge_asset_meshes(col, "restaurant")


def build_food_court(col, seed):
    """The ring road, its connector out to Rivergate, and the plaza sign."""
    m = std_mats()
    kerb = mat("NB_food_kerb", (.80, .78, .74), .93)
    lawn = mat("NB_food_lawn", (.41, .64, .33), 1.0)
    post = mat("NB_food_post", (.28, .30, .33), .82)
    board = mat("NB_food_board", (.86, .28, .22), .84)
    cream = mat("NB_food_signface", (.98, .96, .90), .82)

    # The roads below bake ABSOLUTE world heights via terrain_conform, while
    # the furniture further down is authored at local zero. The instance is
    # pinned to world zero by "pz", so the furniture has to be lifted here or
    # it ends up buried under the plateau it is meant to sit on. Everything
    # sits inside the plateau's level core, so one sample is exact.
    gz = terrain_height(FOOD_COURT_X, FOOD_COURT_Y)

    ring = []
    for index in range(73):
        a = math.tau * index / 72
        ring.append((32.0 * math.cos(a), 25.0 * math.sin(a)))
    _add_road_strip(col, "foodcourt_loop", ring, m["road"], terrain_conform=True,
                    terrain_origin=(FOOD_COURT_X, FOOD_COURT_Y))

    # The connector out over the river, threading the gap between the third and
    # fourth homes and narrowing to a single track to do it. See
    # food_court_connector() for why, and for what it used to run through.
    #
    # The control points are passed as authored: _add_road_strip subdivides to
    # two metres internally, which is finer than the three this used to
    # pre-densify to, and unlike the suburban roads this lane is in no walk
    # surface manifest -- the browser walks the Food Court off the shared
    # plateau in regionalTerrainHeight, not off a road deck -- so there is no
    # coarser copy of it to drift away from the mesh.
    lane_points, lane_widths = food_court_connector()
    _add_road_strip(col, "foodcourt_approach", lane_points, m["road"],
                    widths=lane_widths, terrain_conform=True,
                    terrain_origin=(FOOD_COURT_X, FOOD_COURT_Y))

    add_ngon_cone(col, "foodcourt_green", 26.0, 26.0, .10, 28, 0, 0, gz + .02, lawn)
    for index in range(12):
        a = math.tau * index / 12
        add_ngon_cone(col, "foodcourt_lamp", .13, .10, 4.4, 6,
                      25.0 * math.cos(a), 19.0 * math.sin(a), gz, post)
        add_box(col, "foodcourt_lampbox", .50, .38, .20,
                25.0 * math.cos(a), 19.0 * math.sin(a), gz + 4.4, m["bulb"])
    # The sign stands on the green, inside the loop road's inner kerb. It used
    # to sit at y=-27.5: the road runs from -22 to -28 here, so both posts stood
    # in the carriageway, half a metre from the far kerb -- and once the ring was
    # turned to face its road, the board was parked squarely in the first home's
    # front garden, filling the view from its doorstep.
    sign_y = -20.0
    for side in (-1, 1):
        add_ngon_cone(col, "foodcourt_signpost", .28, .24, 4.6, 8,
                      side * 3.4, sign_y, gz, post)
    add_box(col, "foodcourt_signboard", 9.0, .40, 2.6,
            0, sign_y, gz + 4.6, board)
    add_box(col, "foodcourt_signface", 8.4, .16, 2.0,
            0, sign_y - .22, gz + 4.9, cream)
    add_text(col, "foodcourt_signtext", "FOOD COURT", .80, .06,
             0, sign_y - .42, gz + 5.5, board)

def build_apartment_complex(col, seed):
    """Followville Commons: two six-storey blocks behind a courtyard pool.

    Turned to face the city. The blocks sit along the SOUTH edge looking
    north, so the drone arriving from downtown meets the lawn, then the pool,
    then the facades -- not the backs of two slabs. The car park is pushed to
    the west end for the same reason: the north frontage stays clear.

    The 616-house reserve is finished, so this is where growth goes now. It is
    one record holding many residents, which is exactly why population is read
    from state["pop"] and never from len(buildings).
    """
    m = std_mats()
    pale = mat("NB_commons_wall", (.90, .86, .78), .88)
    warm = mat("NB_commons_warm", (.80, .58, .45), .86)
    accent = mat("NB_commons_accent", (.44, .55, .60), .84)
    slate = mat("NB_commons_slate", (.31, .35, .40), .86)
    glass = mat("NB_commons_glass", (.16, .32, .42), .12, .10, 1.0, 0.0, .58)
    rail = mat("NB_commons_rail", (.94, .93, .90), .58)
    deck = mat("NB_commons_deck", (.86, .82, .72), .92)
    pave = mat("NB_commons_pave", (.72, .71, .68), .94)
    water = mat("NB_commons_water", (.16, .58, .74), .07, .04, .92, .30, .74)
    lawn = mat("NB_commons_lawn", (.40, .63, .32), 1.0)
    hedge = mat("NB_commons_hedge", (.26, .46, .26), 1.0)
    brick = mat("NB_commons_brick", (.62, .44, .36), .92)

    z = APARTMENTS_PAD_Z
    HX, HY = 34.0, 22.0

    # ── podium ───────────────────────────────────────────────────────────
    add_box(col, "commons_pad", HX * 2, HY * 2, .18, 0, 0, z - .18, pave)
    _add_retaining_skirt(col, "commons_skirt", HX, HY, z - .18,
                         (APARTMENTS_X, APARTMENTS_Y), brick)

    # ── the two blocks, along the SOUTH edge, facing the city ────────────
    _commons_block(col, "commons_a", -18.5, -11.5, 25.0, 13.5, 6, z,
                   pale, accent, slate, glass, rail, m)
    _commons_block(col, "commons_b", 18.5, -11.5, 25.0, 13.5, 6, z,
                   warm, accent, slate, glass, rail, m)

    # ── courtyard and pool, between the blocks and the city ──────────────
    # The deck is a RING. A slab across the courtyard roofs the pool over and
    # from above there is simply no pool.
    POOL_Y = 5.0
    OPEN_X, OPEN_Y = 8.7, 4.2
    DECK_X, DECK_Y = 15.0, 7.5
    for side in (-1, 1):
        add_box(col, "commons_deck_x", DECK_X * 2, DECK_Y - OPEN_Y, .10,
                0, POOL_Y + side * (OPEN_Y + (DECK_Y - OPEN_Y) / 2), z + .02, deck)
        add_box(col, "commons_deck_y", DECK_X - OPEN_X, OPEN_Y * 2, .10,
                side * (OPEN_X + (DECK_X - OPEN_X) / 2), POOL_Y, z + .02, deck)
    add_box(col, "commons_lawn_north", 50.0, 7.0, .06, 2.0, 17.5, z, lawn)
    add_box(col, "commons_lawn_mid", 14.0, 15.0, .06, -24.0, -6.0, z, lawn)

    add_box(col, "commons_pool_basin", OPEN_X * 2, OPEN_Y * 2, 1.02,
            0, POOL_Y, z - 1.12, accent)
    add_box(col, "commons_pool_water", OPEN_X * 2 - .4, OPEN_Y * 2 - .4, .52,
            0, POOL_Y, z - .68, water)
    for lane in (-1, 0, 1):
        add_box(col, "commons_pool_lane", OPEN_X * 2 - 1.8, .22, .05,
                0, POOL_Y + lane * 2.5, z - 1.08, rail)
    for side in (-1, 1):
        add_box(col, "commons_coping_x", OPEN_X * 2 + 1.4, .70, .20,
                0, POOL_Y + side * (OPEN_Y + .35), z + .10, rail)
        add_box(col, "commons_coping_y", .70, OPEN_Y * 2, .20,
                side * (OPEN_X + .35), POOL_Y, z + .10, rail)

    for index in range(6):
        side = -1 if index < 3 else 1
        _commons_lounger(col, -6.5 + (index % 3) * 6.5, POOL_Y + side * 6.3,
                         z + .12, rail, [warm, accent, pale][index % 3])
    for ux in (-12.6, 12.6):
        add_ngon_cone(col, "commons_umbrella_pole", .09, .09, 2.45, 8,
                      ux, POOL_Y, z + .12, rail)
        add_ngon_cone(col, "commons_umbrella", 2.15, .12, .70, 8,
                      ux, POOL_Y, z + 2.35, warm)

    # pool house closes the east end of the courtyard
    add_box(col, "commons_poolhouse", 9.5, 5.0, 3.30, 26.0, 6.0, z, pale)
    add_prism_roof(col, "commons_poolhouse_roof", 10.3, 5.8, 1.25,
                   26.0, 6.0, z + 3.30, slate)
    add_box(col, "commons_poolhouse_door", 1.7, .16, 2.20, 26.0, 3.42, z + .04, glass)

    # ── car park, west end, off the city frontage ────────────────────────
    add_box(col, "commons_lot", 14.0, 17.0, .08, -26.0, 11.0, z + .01, m["road"])
    for slot in range(5):
        add_box(col, "commons_lot_line", 13.2, .16, .03,
                -26.0, 4.0 + slot * 3.4, z + .09, m["dash"])
    for index in range(4):
        cy = 5.6 + index * 3.4
        body = [warm, accent, pale, slate][index % 4]
        add_box(col, "commons_car", 1.85, 4.05, 1.02, -26.0, cy, z + .22, body)
        add_box(col, "commons_car_cabin", 1.70, 2.20, .78, -26.0, cy + .18,
                z + 1.14, glass)
        for wx in (-.92, .92):
            for wy in (-1.35, 1.35):
                add_ngon_cone(col, "commons_car_wheel", .34, .34, .24, 10,
                              -26.0 + wx, cy + wy, z + .06, slate, rot=math.pi / 2)

    # ── approach road, in from the north-west, to the car park ───────────
    # Control points every 3m: _add_road_strip subdivides internally, but
    # walk_surface_manifest uses the points as given, so coarse ones would
    # drift the walk surface off the visible road.
    spine = [(-45.0, 57.0), (-40.0, 46.0), (-34.0, 36.0), (-29.0, 28.0),
             (-26.0, 20.0)]
    dense = []
    for (ax, ay), (bx, by) in zip(spine, spine[1:]):
        steps = max(1, int(math.ceil(math.hypot(bx - ax, by - ay) / 3.0)))
        for step in range(steps):
            t = step / steps
            dense.append((ax + (bx - ax) * t, ay + (by - ay) * t))
    dense.append(spine[-1])
    _add_road_strip(col, "commons_approach", dense, m["road"],
                    terrain_conform=True,
                    terrain_origin=(APARTMENTS_X, APARTMENTS_Y))
    # apron stepping the road up onto the podium
    for step in range(4):
        add_box(col, "commons_step_%d" % step, 11.0 - step * .6, 1.05, .22,
                -26.0, HY + .55 + step * 1.05, z - .20 - step * .30, pave)

    # ── planting and lighting, clear of the lot and the deck ─────────────
    for hx in (-32.6, 32.6):
        add_box(col, "commons_hedge", 1.6, 26.0, 1.05, hx, -6.0, z, hedge)
    tree_spots = [(-14.0, 19.5), (-4.0, 19.5), (6.0, 19.5), (16.0, 19.5),
                  (26.0, 19.5), (-31.0, -18.0), (31.0, -18.0), (0.0, -20.5)]
    for tx, ty in tree_spots:
        add_ngon_cone(col, "commons_trunk", .28, .24, 1.70, 7, tx, ty, z, m["trunk"])
        add_ngon_cone(col, "commons_tree", 2.30, .30, 4.30, 8, tx, ty, z + 1.60,
                      hedge)
    for index in range(5):
        lx = -14.0 + index * 10.0
        add_ngon_cone(col, "commons_lamp_pole", .13, .10, 4.60, 6,
                      lx, 14.5, z, slate)
        add_box(col, "commons_lamp", .55, .40, .22, lx, 14.5, z + 4.60, m["bulb"])

    # ── the sign, on the city side where it can be read ──────────────────
    add_box(col, "commons_sign_base", 6.4, 1.0, .95, 6.0, HY - 2.4, z, brick)
    add_box(col, "commons_sign_panel", 6.0, .30, 1.35, 6.0, HY - 2.4, z + .95, pale)
    add_text(col, "commons_sign_text", "FOLLOWVILLE COMMONS", .52, .05,
             6.0, HY - 2.62, z + 1.52, slate)


def build_north_crown_campus(col, seed):
    """North Crown's permanent 20-parcel apartment campus, phase one.

    Four detailed blocks stand along the entrance row.  The other sixteen
    parcels deliberately remain grass, while the complete circulation,
    parking, perimeter gate and pool are already constructed.  All local
    heights start on the terrain datum stored by the state record; there is no
    common podium and therefore no raised-building effect on the level site.
    """
    m = std_mats()
    cream = mat("NB_nc_campus_cream", (.86, .81, .71), .87)
    peach = mat("NB_nc_campus_peach", (.76, .50, .40), .86)
    blue = mat("NB_nc_campus_blue", (.38, .54, .63), .80)
    sage = mat("NB_nc_campus_sage", (.43, .58, .48), .87)
    slate = mat("NB_nc_campus_slate", (.20, .24, .29), .72, .08)
    glass = mat("NB_nc_campus_glass", (.10, .25, .34), .18, .06,
                1.0, 0.0, .58)
    rail = mat("NB_nc_campus_rail", (.90, .89, .84), .62)
    lawn = mat("NB_nc_campus_lawn", (.35, .57, .30), .98)
    pave = mat("NB_nc_campus_pave", (.66, .64, .60), .94)
    asphalt = mat("NB_nc_campus_asphalt", (.18, .20, .22), .97)
    paint = mat("NB_nc_campus_paint", (.91, .86, .66), .72)
    brick = mat("NB_nc_campus_brick", (.48, .28, .21), .91)
    water = mat("NB_nc_campus_water", (.10, .50, .70), .12, .04,
                1.0, .20, .70)
    hedge = mat("NB_nc_campus_hedge", (.20, .41, .21), .98)

    # A thin lawn owns the visible campus surface and sits 8cm above the
    # shared terrain; every later hardscape layer starts above its top.
    add_box(col, "north_crown_campus_lawn", 200.0, 280.0, .08,
            0, 0, 0, lawn)

    # Complete circulation for all twenty parcels: a central spine, four
    # parking courts and pedestrian walks.  The future building pads are not
    # paved; they stay honest grass until later phases are approved.
    add_box(col, "north_crown_campus_spine", 8.5, 270.0, .08,
            0, 0, .08, asphalt)
    for side in (-1, 1):
        add_box(col, "north_crown_campus_spine_walk", 2.1, 270.0, .07,
                side * 5.55, 0, .16, pave)
    # Carry the road and both walks through the gate to the exact endpoint of
    # NORTH_CROWN_CAMPUS_ACCESS (world y=943).  The lawn begins at y=948, so
    # this short apron is what removes the otherwise-visible grass gap.
    add_box(col, "north_crown_gate_apron", 8.5, 11.0, .08,
            0, -140.5, .08, asphalt)
    for side in (-1, 1):
        add_box(col, "north_crown_gate_apron_walk", 2.1, 11.0, .07,
                side * 5.55, -140.5, .16, pave)
    parking_rows = (-70.0, -10.0, 50.0, 110.0)
    for row_index, y in enumerate(parking_rows):
        add_box(col, "north_crown_campus_parking", 190.0, 16.0, .08,
                0, y, .08, asphalt)
        for x in range(-92, 93, 8):
            for side in (-1, 1):
                add_box(col, "north_crown_campus_stall", .10, 5.1, .025,
                        x, y + side * 5.35, .165, paint)
        add_box(col, "north_crown_campus_centerline", 190.0, .10, .025,
                0, y, .165, paint)
        # Four planted islands per court break up the asphalt without
        # occupying any future building footprint.
        for x in (-88.0, -32.0, 32.0, 88.0):
            add_box(col, "north_crown_campus_island", 3.4, 2.4, .18,
                    x, y, .17, hedge)

    # Phase one: four different-colour, five-storey blocks.  The shared
    # detailed builder provides proper balconies, glazing, bands and roof
    # equipment without any geometry hanging below the roof plane.
    blocks = ((-72.0, cream, blue), (-24.0, peach, sage),
              (24.0, blue, cream), (72.0, sage, peach))
    for index, (x, wall, accent) in enumerate(blocks, 1):
        _commons_block(col, "north_crown_phase1_%d" % index,
                       x, -106.0, 32.0, 20.0, 5, .20,
                       wall, accent, slate, glass, rail, m)
        add_box(col, "north_crown_entry_walk", 4.0, 9.0, .07,
                x, -89.5, .16, pave)

    # Pool behind the western entrance block, fenced separately from the
    # campus perimeter.  Basin and water are vertically separated; no level
    # water shares a plane with the deck or lawn.
    px, py = -60.0, -40.0
    add_box(col, "north_crown_pool_basin", 18.0, 12.0, .70,
            px, py, -.62, slate)
    add_box(col, "north_crown_pool_water", 17.2, 11.2, .10,
            px, py, .09, water)
    for side in (-1, 1):
        add_box(col, "north_crown_pool_deck_x", 22.0, 3.0, .10,
                px, py + side * 7.5, .16, pave)
        add_box(col, "north_crown_pool_deck_y", 2.0, 12.0, .10,
                px + side * 10.0, py, .16, pave)
        add_box(col, "north_crown_pool_fence_x", 22.0, .10, 1.35,
                px, py + side * 9.0, .26, slate)
        add_box(col, "north_crown_pool_fence_y", .10, 18.0, 1.35,
                px + side * 11.0, py, .26, slate)
        _commons_lounger(col, px + side * 7.2, py - 7.2, .26, slate, accent)

    # Continuous perimeter with a controlled 16m opening, real gate leaves,
    # gatehouse and identity beam at the south entrance.
    for y in range(-138, 139, 7):
        for x in (-99.0, 99.0):
            add_box(col, "north_crown_fence_post", .18, .18, 2.1,
                    x, y, .20, slate)
    for x in list(range(-98, -8, 7)) + list(range(8, 99, 7)):
        for y in (-138.0, 138.0):
            add_box(col, "north_crown_fence_post", .18, .18, 2.1,
                    x, y, .20, slate)
    for x in (-99.0, 99.0):
        for z in (.55, 1.25, 2.0):
            add_box(col, "north_crown_fence_rail", .12, 276.0, .12,
                    x, 0, z, slate)
    for y in (-138.0, 138.0):
        for x, width in ((-53.0, 90.0), (53.0, 90.0)):
            for z in (.55, 1.25, 2.0):
                add_box(col, "north_crown_fence_rail", width, .12, .12,
                        x, y, z, slate)
    for side in (-1, 1):
        add_box(col, "north_crown_gate_leaf", 7.6, .18, 1.65,
                side * 4.0, -138.0, .34, slate)
        add_box(col, "north_crown_gate_pier", .85, .85, 2.65,
                side * 8.2, -138.0, .20, brick)
    add_box(col, "north_crown_gatehouse", 8.0, 5.0, 3.5,
            -14.0, -130.0, .20, brick)
    add_box(col, "north_crown_gatehouse_glass", 5.2, .14, 1.55,
            -14.0, -132.57, 1.05, glass)
    add_box(col, "north_crown_entry_beam", 12.0, .42, 1.15,
            0, -134.0, 3.15, brick)

    # Warm practical fixtures carry the pool finale at night.  They remain
    # emissive in the web export while the render adds controlled light pools.
    for y in (-118.0, -82.0, -22.0, 38.0, 98.0, 128.0):
        for x in (-7.0, 7.0):
            add_ngon_cone(col, "north_crown_lamp_post", .12, .10, 4.5, 7,
                          x, y, .20, slate)
            add_box(col, "north_crown_lamp_head", .55, .40, .22,
                    x, y, 4.70, m["bulb"])

    # One merged collection instance keeps website streaming manageable and
    # makes the four completed buildings rise together in the Day 45 film.
    _merge_asset_meshes(col, "north_crown_campus")


def build_day37_statue(world_col, buildings, frame_end):
    """Render-only: the next mayor's plinth, in FRONT of City Hall.

    CITY_HALL_ROAD_Y is -93 and the hall stands at -134, so the hall faces
    NORTH, toward downtown. The first cut put this at hall_y - 34, which is
    round the back of the building. It now stands between the hall and its
    approach road, and the question mark faces north because that is the side
    the drone comes in from.

    Nothing is written to world_state.json and export_web strips every object
    tagged nb_render_only, so the town on the website is unchanged.
    """
    hall = next((b for b in buildings if b.get("type") == "cityhall"), None)
    if not hall:
        raise RuntimeError("Day 37 statue requires City Hall")
    hx, hy = build_pos(hall)
    sx, sy = hx, hy + 30.0
    ground = terrain_height(sx, sy)

    stone = mat("NB_day37_stone", (.74, .71, .64), .93)
    dark = mat("NB_day37_plinth", (.34, .33, .31), .90)
    bronze = mat("NB_day37_bronze", (.44, .33, .20), .48, .62)
    gold = mat("NB_day37_gold", (.95, .74, .26), .32, .70)

    root = bpy.data.objects.new("Day37_MayorPlinth_RenderOnly", None)
    root.location = (sx, sy, ground)
    root["nb_rest_scale"] = (1.0, 1.0, 1.0)
    root["nb_render_only"] = True
    world_col.objects.link(root)

    def attach(obj):
        obj.parent = root
        obj["nb_render_only"] = True
        return obj

    attach(add_box(world_col, "day37_plinth_base", 5.0, 5.0, .55, 0, 0, 0, dark))
    attach(add_box(world_col, "day37_plinth", 3.5, 3.5, 3.10, 0, 0, .55, stone))
    attach(add_box(world_col, "day37_plinth_cap", 4.0, 4.0, .30, 0, 0, 3.65, dark))
    base = 3.95
    for side in (-1, 1):
        attach(add_box(world_col, "day37_leg", .42, .46, 1.70,
                       side * .38, 0, base, bronze))
    attach(add_box(world_col, "day37_torso", 1.55, .80, 1.85, 0, 0, base + 1.70, bronze))
    attach(add_box(world_col, "day37_shoulders", 1.95, .90, .38,
                   0, 0, base + 3.30, bronze))
    for side in (-1, 1):
        attach(add_box(world_col, "day37_arm", .38, .40, 1.60,
                       side * 1.02, 0, base + 1.85, bronze))
    attach(add_ngon_cone(world_col, "day37_neck", .26, .26, .28, 8,
                         0, 0, base + 3.68, bronze))
    attach(add_uv_sphere(world_col, "day37_head", .52, 0, 0, base + 4.48, bronze))
    # Turned to face north: the default text rotation faces -Y, which is now
    # away from the camera.
    attach(add_text(world_col, "day37_question", "?", 2.60, .22,
                    0, .62, base + 6.35, gold,
                    rotation=(math.pi / 2, 0, math.pi)))
    attach(add_box(world_col, "day37_placard", 2.60, .22, .85, 0, 1.80, 2.30, dark))
    attach(add_text(world_col, "day37_placard_text", "MAYOR OF FOLLOWVILLE",
                    .26, .04, 0, 1.94, 2.72, gold,
                    rotation=(math.pi / 2, 0, math.pi)))
    return root


def build_salmon_pro_shop(col, seed):
    """Salmon Pro Shop: a timber-and-fieldstone outdoors superstore.

    The big-box outfitter idiom -- a long lodge with a steep green roof, a
    stone chimney, a projecting entrance gable under a mounted fish, and a
    striped lot in front of it. Front faces local -Y, like the school and the
    cinema, so the south-east camera sees the entrance.

    The site at (120, 220) was chosen by measuring rather than by eye: the
    ground falls 0.27m across the whole 50x56m pad, the nearest house is 45m
    away, and Pebble Court's terminus is a short approach to the west. The pad
    is still skirted, because 0.27m of fall is still 0.27m of daylight under a
    level slab.
    """
    rng = random.Random(seed)
    stone = mat("NB_salmon_fieldstone", (.44, .43, .40), .96)
    stone_dark = mat("NB_salmon_fieldstone_dark", (.30, .29, .27), .97)
    log = mat("NB_salmon_log", (.53, .35, .18), .90)
    log_dark = mat("NB_salmon_log_shadow", (.36, .23, .11), .93)
    timber = mat("NB_salmon_timber", (.29, .17, .085), .92)
    green = mat("NB_salmon_roof", (.055, .24, .16), .84)
    green_dark = mat("NB_salmon_roof_trim", (.03, .145, .10), .80)
    cream = mat("NB_salmon_cream", (.92, .88, .77), .82)
    gold = mat("NB_salmon_gold", (.85, .62, .16), .34, .55)
    glass = mat("NB_salmon_glass", (.11, .26, .32), .12, .10, .90, .08, .62)
    warm = mat("NB_salmon_warm_light", (1.0, .74, .34), .24)
    asphalt = mat("NB_salmon_asphalt", (.155, .16, .17), .96)
    paint = mat("NB_salmon_paint", (.94, .93, .86), .74)
    pink = mat("NB_salmon_fish", (.86, .40, .34), .52)
    pink_pale = mat("NB_salmon_fish_belly", (.95, .82, .74), .56)
    steel = mat("NB_salmon_steel", (.36, .39, .41), .42, .58)
    hull = mat("NB_salmon_hull", (.10, .32, .52), .58)
    needle = mat("NB_salmon_pine", (.10, .26, .15), .92)
    bark = mat("NB_salmon_bark", (.26, .17, .10), .95)

    # Everything below is authored front-toward-local -Y, the same convention
    # as the school and the cinema. The store then gets turned a quarter turn
    # so its face and its lot both look east into the city instead of out at
    # the meadow. The turn is applied to the store's own objects only; the
    # approach road is built afterwards, in true local coordinates, because a
    # road that rotates with the building stops meeting the town.
    store_start = set(col.objects)
    QUARTER = math.pi / 2

    HALF_X, HALF_Y = 25.0, 28.0
    origin = (SALMON_SHOP_X, SALMON_SHOP_Y)
    # The quarter turn swaps the pad's footprint in world space, so terrain is
    # sampled over the rectangle it will actually occupy, not the one it is
    # authored in. Getting this backwards would bed the plinth into the wrong
    # ground on a site that falls 3.8m across itself.
    TURNED_X, TURNED_Y = HALF_Y, HALF_X
    base_z = max(terrain_height(SALMON_SHOP_X + x, SALMON_SHOP_Y + y)
                 for x in (-TURNED_X, 0.0, TURNED_X)
                 for y in (-TURNED_Y, 0.0, TURNED_Y)) + .10

    # Level pad; its skirt is added after the turn, below, so that it samples
    # the ground the pad ends up standing on.
    add_box(col, "salmon_pad", HALF_X * 2, HALF_Y * 2, .30,
            0, 0, base_z - .30, stone_dark)

    # ── parking apron, south half ───────────────────────────────────────────
    LOT_TOP = base_z + .06
    add_box(col, "salmon_lot", 44.0, 22.0, .06, 0, -15.0, base_z, asphalt)
    # The kerb is deliberately broken on the west side: that gap is where the
    # approach road comes in, and a continuous kerb would have the drive
    # running straight into a 16cm wall.
    add_box(col, "salmon_lot_kerb", .5, 4.0, .16, -19.8, -24.0, base_z, cream)
    add_box(col, "salmon_lot_kerb", .5, 4.0, .16, -19.8, -6.0, base_z, cream)
    add_box(col, "salmon_lot_kerb", .5, 22.0, .16, 19.8, -15.0, base_z, cream)
    for index in range(13):
        x = -18.0 + index * 3.0
        for y in (-21.0, -9.6):
            add_box(col, "salmon_lot_stripe", .16, 4.9, .012,
                    x, y, LOT_TOP, paint)
    add_box(col, "salmon_lot_aisle", 40.0, .18, .012, 0, -15.4,
            LOT_TOP, paint)

    # ── the lodge ───────────────────────────────────────────────────────────
    STORE_Y, STORE_W, STORE_D = 9.0, 34.0, 22.0
    add_box(col, "salmon_store_base", STORE_W + .8, STORE_D + .8, 1.05,
            0, STORE_Y, base_z, stone)
    for index in range(22):            # fieldstone coursing, not a flat band
        x = -17.0 + index * 1.62
        add_box(col, "salmon_base_stone", 1.30, .18, .34,
                x, STORE_Y - STORE_D / 2 - .52,
                base_z + .12 + (.40 if index % 2 else .0), stone_dark)
    add_box(col, "salmon_store_body", STORE_W, STORE_D, 6.30,
            0, STORE_Y, base_z + 1.05, log)
    # Horizontal log courses read as a cabin at street level and survive the
    # aerial pass as texture rather than noise.
    # add_ngon_cone's `rot` only spins the n-gon's cross-section; the cylinder
    # always extends along local +Z. Laying a log on its side is a rotation of
    # the object, not of its profile -- getting that wrong stood nine 33m masts
    # up through the roof.
    for index in range(9):
        z = base_z + 1.35 + index * .68
        course = add_ngon_cone(col, "salmon_log_course", .30, .30,
                               STORE_W - .4, 8,
                               -(STORE_W - .4) / 2,
                               STORE_Y - STORE_D / 2 - .06, z, log_dark)
        course.rotation_euler = (0, math.pi / 2, 0)
    for x in (-17.2, 17.2):
        add_box(col, "salmon_corner_post", .62, STORE_D + .5, 7.35,
                x, STORE_Y, base_z + 1.05, timber)

    add_prism_roof(col, "salmon_roof", STORE_W + 2.4, STORE_D + 2.2, 6.60,
                   0, STORE_Y, base_z + 7.35, green)

    # ── massing: an entry tower and two projecting wings ────────────────────
    # One box under one gable reads as a shed at any distance. A destination
    # store needs a silhouette: a tall centre that carries the sign, wings that
    # break the front plane, and dormers that stop the roof being one sheet.
    TOWER_W, TOWER_D, TOWER_H = 12.4, 11.0, 10.6
    add_box(col, "salmon_tower_base", TOWER_W + 1.0, TOWER_D + .8, 1.35,
            0, -3.2, base_z, stone)
    for index in range(14):
        add_box(col, "salmon_tower_stone", 1.35, .20, .38,
                -6.2 + index * .95, -8.72,
                base_z + .16 + (.44 if index % 2 else .0), stone_dark)
    add_box(col, "salmon_tower_body", TOWER_W, TOWER_D, TOWER_H,
            0, -3.2, base_z + 1.35, log)
    for index in range(11):
        course = add_ngon_cone(col, "salmon_tower_log", .29, .29,
                               TOWER_W - .35, 8, -(TOWER_W - .35) / 2,
                               -8.66, base_z + 1.70 + index * .78, log_dark)
        course.rotation_euler = (0, math.pi / 2, 0)
    add_prism_roof(col, "salmon_tower_roof", TOWER_W + 2.0, TOWER_D + 1.8,
                   5.40, 0, -3.2, base_z + 11.95, green)
    add_box(col, "salmon_tower_ridge", TOWER_W + 2.4, .42, .24,
            0, -3.2, base_z + 17.35, green_dark)
    # Exposed truss in the tower gable -- the detail that says "lodge".
    add_beam_between(col, "salmon_tower_truss",
                     (-5.6, -8.9, base_z + 11.95),
                     (0.0, -8.9, base_z + 14.55), .28, timber)
    add_beam_between(col, "salmon_tower_truss",
                     (5.6, -8.9, base_z + 11.95),
                     (0.0, -8.9, base_z + 14.55), .28, timber)
    add_box(col, "salmon_tower_collar", 7.6, .26, .30, 0, -8.9,
            base_z + 12.95, timber)

    # Two wings step forward at each end, each under its own cross gable.
    for side in (-1, 1):
        wx = side * 12.6
        add_box(col, "salmon_wing_base", 9.6, 15.0, 1.05, wx, 1.2,
                base_z, stone)
        add_box(col, "salmon_wing_body", 8.8, 14.2, 6.10, wx, 1.2,
                base_z + 1.05, log)
        for index in range(8):
            course = add_ngon_cone(col, "salmon_wing_log", .27, .27, 8.45, 8,
                                   wx - 4.22, -5.98,
                                   base_z + 1.40 + index * .72, log_dark)
            course.rotation_euler = (0, math.pi / 2, 0)
        wing_roof = add_prism_roof(col, "salmon_wing_roof", 15.2, 9.6, 4.30,
                                   wx, 1.2, base_z + 7.15, green)
        wing_roof.rotation_euler.z = math.pi / 2
        add_box(col, "salmon_wing_ridge", .40, 15.6, .22, wx, 1.2,
                base_z + 11.45, green_dark)
        add_box(col, "salmon_wing_barge", 9.9, .34, .30, wx, -6.12,
                base_z + 7.05, green_dark)
        # Tall gable window under each wing peak.
        add_box(col, "salmon_wing_window", 4.20, .26, 4.60, wx, -6.02,
                base_z + 2.10, glass)
        add_box(col, "salmon_wing_glow", 3.80, .14, 3.90, wx, -5.88,
                base_z + 2.40, warm)
        for mullion in (-1.35, 0.0, 1.35):
            add_box(col, "salmon_wing_mullion", .15, .34, 4.70,
                    wx + mullion, -6.16, base_z + 2.05, timber)
        add_box(col, "salmon_wing_head", 4.90, .36, .32, wx, -6.20,
                base_z + 6.70, timber)

    # Dormers along the main roof, so it is not one uninterrupted sheet.
    for dx in (-6.2, 6.2):
        add_box(col, "salmon_dormer_body", 3.30, 2.60, 2.05, dx, 2.6,
                base_z + 8.65, log)
        add_prism_roof(col, "salmon_dormer_roof", 3.90, 3.20, 1.45,
                       dx, 2.6, base_z + 10.70, green)
        add_box(col, "salmon_dormer_glass", 2.20, .20, 1.30, dx, 1.36,
                base_z + 9.05, glass)
    add_box(col, "salmon_ridge_cap", STORE_W + 2.8, .46, .26,
            0, STORE_Y, base_z + 13.85, green_dark)
    for y in (STORE_Y - STORE_D / 2 - 1.1, STORE_Y + STORE_D / 2 + 1.1):
        add_box(col, "salmon_eave", STORE_W + 2.8, .40, .34,
                0, y, base_z + 7.15, green_dark)

    # Covered entrance porch on heavy log columns, standing off the tower face
    # so the doors sit in shade rather than flat against the wall.
    add_box(col, "salmon_porch_deck", 14.6, 4.6, .34, 0, -11.3,
            base_z + .06, stone)
    add_box(col, "salmon_porch_step", 15.4, .90, .18, 0, -13.7,
            base_z + .06, stone_dark)
    for x in (-6.4, -2.15, 2.15, 6.4):
        add_ngon_cone(col, "salmon_porch_column", .44, .38, 5.10, 10,
                      x, -11.9, base_z + .40, timber)
        add_box(col, "salmon_porch_capital", 1.15, 1.15, .30, x, -11.9,
                base_z + 5.50, log_dark)
        add_box(col, "salmon_porch_base_block", 1.25, 1.25, .40, x, -11.9,
                base_z + .38, stone_dark)
    add_box(col, "salmon_porch_beam", 15.0, .70, .78, 0, -11.9,
            base_z + 5.80, timber)
    add_prism_roof(col, "salmon_porch_roof", 16.0, 6.0, 2.35, 0, -11.0,
                   base_z + 6.58, green)
    add_box(col, "salmon_porch_barge", 16.4, .32, .26, 0, -13.95,
            base_z + 6.48, green_dark)
    for x in (-4.3, 0.0, 4.3):
        add_beam_between(col, "salmon_porch_brace",
                         (x - 1.5, -11.9, base_z + 5.80),
                         (x, -11.9, base_z + 6.55), .20, timber)
        add_beam_between(col, "salmon_porch_brace",
                         (x + 1.5, -11.9, base_z + 5.80),
                         (x, -11.9, base_z + 6.55), .20, timber)

    # Doors, glazing and the warm interior band behind it.
    # Doors and the glazed gable above them, set into the tower face.
    for x in (-3.3, 3.3):
        add_box(col, "salmon_door", 2.90, .26, 3.40, x, -8.76,
                base_z + 1.35, glass)
        add_box(col, "salmon_door_pull", .10, .12, .95,
                x + (-.95 if x < 0 else .95), -8.94, base_z + 2.70, gold)
    add_box(col, "salmon_door_mullion", .22, .30, 3.40, 0, -8.80,
            base_z + 1.35, timber)
    add_box(col, "salmon_transom", 9.4, .22, 1.45, 0, -8.76,
            base_z + 4.85, glass)
    add_box(col, "salmon_lobby_glow", 8.8, .16, 1.15, 0, -8.58,
            base_z + 4.95, warm)
    # Big arched-feel gable window high in the tower, the lit focal point.
    add_box(col, "salmon_tower_window", 7.40, .26, 3.90, 0, -8.76,
            base_z + 7.05, glass)
    add_box(col, "salmon_tower_glow", 6.90, .14, 3.30, 0, -8.60,
            base_z + 7.35, warm)
    for mullion in (-2.4, 0.0, 2.4):
        add_box(col, "salmon_tower_mullion", .16, .34, 4.00, mullion,
                -8.90, base_z + 7.00, timber)
    add_box(col, "salmon_tower_sill", 8.00, .38, .30, 0, -8.92,
            base_z + 6.70, timber)

    # Fieldstone chimney: the silhouette element that stops the roof reading
    # as one long extrusion from the air.
    add_box(col, "salmon_chimney", 3.40, 3.40, 15.60, 13.6,
            STORE_Y + 6.4, base_z + 1.05, stone)
    add_box(col, "salmon_chimney_cap", 4.00, 4.00, .42, 13.6,
            STORE_Y + 6.4, base_z + 16.65, stone_dark)
    for index in range(9):
        add_box(col, "salmon_chimney_stone", 1.5, .16, .30,
                13.6 + (-.7 if index % 2 else .7), STORE_Y + 4.66,
                base_z + 2.0 + index * 1.55, stone_dark)

    # ── the mounted salmon, and the sign it hangs over ──────────────────────
    # The mounted salmon sits clear above the sign board rather than across it,
    # and is built from a tapered body, a forked tail and a real dorsal fin --
    # a single scaled sphere just reads as a lump at any distance.
    fish_z = base_z + 13.35
    body = add_uv_sphere(col, "salmon_fish_body", 1.42, .55, -10.75, fish_z,
                         pink, 9, 16)
    body.scale = (2.15, .58, .92)
    belly = add_uv_sphere(col, "salmon_fish_belly", 1.10, .55, -10.94,
                          fish_z - .40, pink_pale, 8, 12)
    belly.scale = (2.05, .46, .52)
    # Tapered rear third, so the body narrows into the tail instead of ending.
    peduncle = add_ngon_cone(col, "salmon_fish_peduncle", .82, .30, 1.55, 7,
                             -2.55, -10.75, fish_z, pink)
    peduncle.rotation_euler = (0, -math.pi / 2, 0)
    # Forked tail: two swept lobes, not one cone.
    for lobe in (1, -1):
        fin = add_ngon_cone(col, "salmon_fish_tail_lobe", .62, .10, 1.70, 4,
                            -4.05, -10.75, fish_z, pink)
        fin.rotation_euler = (0, -math.radians(118) * lobe, 0)
    add_box(col, "salmon_fish_tail_web", 1.05, .16, .55, -4.55, -10.75,
            fish_z - .27, pink)
    # Dorsal, adipose and pectoral fins, and a head that reads as a head.
    dorsal = add_ngon_cone(col, "salmon_fish_dorsal", .80, .10, 1.25, 4,
                           .30, -10.82, fish_z + 1.02, pink)
    dorsal.rotation_euler = (0, -math.radians(18), 0)
    add_ngon_cone(col, "salmon_fish_adipose", .30, .06, .48, 4,
                  -1.95, -10.82, fish_z + .78, pink)
    for side, y in ((1, -11.32), (-1, -10.22)):
        pec = add_ngon_cone(col, "salmon_fish_pec", .58, .09, 1.05, 4,
                            1.15, y, fish_z - .48, pink_pale)
        pec.rotation_euler = (math.radians(24) * side, 0, math.radians(30))
    anal = add_ngon_cone(col, "salmon_fish_anal", .48, .08, .82, 4,
                         -1.55, -10.82, fish_z - 1.05, pink)
    anal.rotation_euler = (math.pi, 0, 0)
    snout = add_ngon_cone(col, "salmon_fish_snout", .95, .34, 1.15, 8,
                          2.65, -10.75, fish_z - .10, pink)
    snout.rotation_euler = (0, math.pi / 2, 0)
    add_box(col, "salmon_fish_jaw", .70, .52, .16, 3.30, -10.75,
            fish_z - .38, pink_pale)
    for y in (-11.15, -8.95):
        add_uv_sphere(col, "salmon_fish_eye", .155, 2.85, y, fish_z + .30,
                      cream, 6, 8)
        add_uv_sphere(col, "salmon_fish_pupil", .085, 2.98, y, fish_z + .30,
                      timber, 5, 6)
    # Mounting board, so it reads as a trophy fixed to the gable.
    add_box(col, "salmon_fish_mount", 3.60, 2.20, .55, 0, -9.55,
            fish_z - .35, timber)

    add_box(col, "salmon_sign_board", 12.2, .40, 2.05, 0, -8.95,
            base_z + 6.05, timber)
    add_box(col, "salmon_sign_frame", 12.7, .22, .22, 0, -9.08,
            base_z + 8.40, gold)
    add_box(col, "salmon_sign_frame_low", 12.7, .22, .22, 0, -9.08,
            base_z + 5.83, gold)
    _add_followmart_text(col, "SALMON PRO SHOP", 1.02, 0, -9.22,
                         base_z + 7.20, cream, extrude=.11, bevel=.016)
    _add_followmart_text(col, "OUTFITTERS  SINCE  DAY 35", .40, 0, -8.42,
                         base_z + 5.35, gold, extrude=.06, bevel=.008)

    # ── forecourt: flags, a boat on a trailer, planting, parked cars ────────
    for x in (-9.2, 9.2):
        add_ngon_cone(col, "salmon_flagpole", .13, .09, 8.40, 8,
                      x, -9.60, base_z, steel)
        add_uv_sphere(col, "salmon_flagpole_ball", .19, x, -9.60,
                      base_z + 8.50, gold, 6, 8)
        add_box(col, "salmon_flag", .10, 2.10, 1.30, x + .05, -8.50,
                base_z + 6.90, green if x < 0 else cream)

    # Display boat, the thing that says "outdoors store" from 60m up.
    boat_x, boat_y = -15.4, -7.4
    add_box(col, "salmon_trailer_bed", 6.40, 1.90, .28, boat_x, boat_y,
            base_z + .34, steel)
    for dx in (-1.9, 1.9):
        for dy in (-1.02, 1.02):
            wheel = add_ngon_cone(col, "salmon_trailer_wheel", .38, .38, .26,
                                  10, boat_x + dx, boat_y + dy, base_z + .06,
                                  timber)
            wheel.rotation_euler = (math.pi / 2, 0, 0)
    add_box(col, "salmon_boat_hull", 6.00, 2.05, 1.02, boat_x, boat_y,
            base_z + .62, hull)
    add_box(col, "salmon_boat_gunwale", 6.20, 2.25, .18, boat_x, boat_y,
            base_z + 1.64, cream)
    bow = add_ngon_cone(col, "salmon_boat_bow", 1.05, .12, 1.35, 5,
                        boat_x + 3.35, boat_y, base_z + .62, hull)
    bow.rotation_euler = (0, math.pi / 2, 0)
    add_box(col, "salmon_boat_deck", 4.60, 1.70, .10, boat_x - .3, boat_y,
            base_z + 1.56, timber)
    add_box(col, "salmon_boat_console", .85, .95, .78, boat_x - .1, boat_y,
            base_z + 1.66, cream)
    add_box(col, "salmon_boat_motor", .60, .72, 1.15, boat_x - 3.25, boat_y,
            base_z + 1.05, stone_dark)

    for x, y in ((-22.0, 6.0), (-21.4, 16.5), (22.0, 6.0), (21.6, 17.0),
                 (-22.2, 24.0), (22.2, 24.0)):
        height = 5.0 + rng.random() * 2.4
        add_ngon_cone(col, "salmon_pine_trunk", .30, .24, height * .34, 7,
                      x, y, base_z, bark)
        for tier in range(3):
            add_ngon_cone(col, "salmon_pine_tier",
                          2.10 - tier * .52, .12, height * .40, 8,
                          x, y, base_z + height * (.28 + tier * .22), needle)

    car_colors = (mat("NB_salmon_car_a", (.72, .19, .16), .52),
                  mat("NB_salmon_car_b", (.19, .32, .55), .52),
                  mat("NB_salmon_car_c", (.90, .89, .84), .54),
                  mat("NB_salmon_car_d", (.24, .43, .30), .52))
    for index, x in enumerate((-16.5, -10.5, -1.5, 7.5, 16.5)):
        for y, flip in ((-19.0, 1), (-11.2, -1)):
            if (index + (y < -15)) % 2:
                continue
            paint_mat = car_colors[(index + (1 if y < -15 else 0))
                                   % len(car_colors)]
            add_box(col, "salmon_car_body", 1.95, 4.35, .78,
                    x, y, base_z + .34, paint_mat)
            add_box(col, "salmon_car_cabin", 1.78, 2.30, .68,
                    x, y - flip * .22, base_z + 1.12, paint_mat)
            add_box(col, "salmon_car_glass", 1.62, 2.05, .46,
                    x, y - flip * .22, base_z + 1.22, glass)
            for dx in (-.92, .92):
                for dy in (-1.48, 1.48):
                    tyre = add_ngon_cone(col, "salmon_car_wheel", .34, .34,
                                         .22, 10, x + dx, y + dy,
                                         base_z + .12, stone_dark)
                    tyre.rotation_euler = (0, math.pi / 2, 0)

    # A short paved walk from the lot to the doors, stepped clear of both.
    add_box(col, "salmon_entry_walk", 11.0, 4.4, .07, 0, -9.0,
            base_z + .06, cream)

    # Turn the store a quarter turn so it faces the city. Composing on the
    # world matrix carries location, rotation and scale together, which matters
    # because the fish's fins and the cars' wheels already carry rotations of
    # their own and the fish body carries a scale.
    # matrix_basis, not matrix_world. These asset collections are built off the
    # scene so the depsgraph never evaluates them; matrix_world reads back as
    # identity there, and composing onto it replaces every transform instead of
    # adding to it -- which piles the whole store on its own origin.
    turn = Matrix.Rotation(QUARTER, 4, "Z")
    for obj in list(col.objects):
        if obj not in store_start:
            obj.matrix_basis = turn @ obj.matrix_basis

    # Now that the pad is where it will stay, close it to the ground.
    _add_retaining_skirt(col, "salmon_pad_skirt", TURNED_X, TURNED_Y,
                         base_z - .30, origin, stone_dark)

    # Approach from the town road to the lot. Control points every ~3m,
    # because walk_surface_manifest uses them as given while _add_road_strip
    # subdivides internally, and coarse points drift the walk surface off the
    # visible road.
    #
    # The last SALMON_SHOP_ENTRY_RAMP metres lift from the natural ground onto
    # the store's pad, so the drive arrives level with the asphalt instead of
    # butting into the side of a raised slab. The kerb is broken to match.
    dense = []
    for a, b in zip(SALMON_SHOP_APPROACH, SALMON_SHOP_APPROACH[1:]):
        steps = max(1, int(math.ceil(math.hypot(b[0] - a[0], b[1] - a[1]) / 3.0)))
        for step in range(steps):
            t = step / steps
            dense.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    dense.append(tuple(SALMON_SHOP_APPROACH[-1]))

    total = 0.0
    runs = [0.0]
    for a, b in zip(dense, dense[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
        runs.append(total)

    # The climb has to FINISH before the drive crosses onto the pad, not at the
    # end of the polyline. Ramping all the way to the last point left the final
    # stretch still climbing while it was already over a 30cm slab, so the road
    # ran under its own car park for the last few metres.
    ENTRY_FLAT = 11.0
    DECK = LOT_TOP - .055
    approach = []
    for (x, y), run in zip(dense, runs):
        ground = terrain_height(x, y)
        remaining = total - run
        if remaining <= ENTRY_FLAT:
            ground = DECK
        elif remaining < SALMON_SHOP_ENTRY_RAMP:
            blend = ((SALMON_SHOP_ENTRY_RAMP - remaining)
                     / (SALMON_SHOP_ENTRY_RAMP - ENTRY_FLAT))
            blend = blend * blend * (3.0 - 2.0 * blend)      # ease, no kink
            ground = ground + (DECK - ground) * blend
        approach.append((x - SALMON_SHOP_X, y - SALMON_SHOP_Y,
                         max(ground, terrain_height(x, y))))

    _add_road_strip(col, "salmon_approach_road", approach, asphalt, width=5.6,
                    bottom_offset=.006, top_offset=.055)
    # Centre dashes on the same rhythm as every other road in town, riding the
    # authored deck rather than the ground so they stay on the ramp.
    for distance in range(8, int(total) - 6, 9):
        x, y, angle = _polyline_sample(approach, distance)
        deck = max(terrain_height(SALMON_SHOP_X + x, SALMON_SHOP_Y + y),
                   _polyline_height(approach, distance))
        dash = add_box(col, "salmon_approach_dash", 1.40, .14, .025,
                       x, y, deck + .066, paint)
        dash.rotation_euler.z = angle
    # Kerbed shoulders. These were one rotated box per 3m segment, which on a
    # curve leaves a row of disconnected rectangles with visible gaps at every
    # joint. A road strip is a single mitred ribbon with shared vertices, which
    # is exactly the problem _add_road_strip was written to solve for roads --
    # so the kerbs use it too, offset from the same centreline and carrying the
    # same authored deck heights so they never part company with the asphalt.
    for side in (-1, 1):
        shoulder = []
        for index, point in enumerate(approach):
            before = approach[max(0, index - 1)]
            after = approach[min(len(approach) - 1, index + 1)]
            dx, dy = after[0] - before[0], after[1] - before[1]
            length = max(.001, math.hypot(dx, dy))
            nx, ny = -dy / length, dx / length
            shoulder.append((point[0] + nx * 3.05 * side,
                             point[1] + ny * 3.05 * side,
                             point[2] - .02))
        _add_road_strip(col, "salmon_approach_kerb", shoulder, cream,
                        width=.46, bottom_offset=-.10, top_offset=.17)


def build_fire_station(col, seed):
    """Full-block Followville Fire & Rescue campus, front facing local -Y."""
    rng = random.Random(seed)
    m = std_mats()
    brick = mat("NB_fire_brick", (.56, .12, .09), .88)
    brick_dark = mat("NB_fire_brick_dark", (.31, .065, .045), .92)
    cream = mat("NB_fire_cream", (.92, .87, .75), .78)
    red = mat("NB_fire_engine_red", (.82, .035, .025), .62)
    red_dark = mat("NB_fire_engine_dark", (.38, .025, .02), .76)
    glass = mat("NB_fire_glass", (.10, .24, .30), .14, .10, 1.0, 0.0, .62)
    bay_glass = mat("NB_fire_bay_glass", (.16, .27, .30), .18, .08, 1.0, 0.0, .52)
    asphalt = mat("NB_fire_asphalt", (.15, .16, .17), .96)
    concrete = mat("NB_fire_concrete", (.68, .69, .67), .92)
    white = mat("NB_fire_white", (.97, .96, .91), .72)
    yellow = mat("NB_fire_yellow", (.98, .68, .05), .54)
    metal = mat("NB_fire_metal", (.35, .38, .40), .42, .55)
    dark = mat("NB_fire_dark", (.075, .085, .09), .58)
    warm = mat("NB_fire_warm_light", (1.0, .60, .19), .30)
    lawn = mat("NB_fire_lawn", (.24, .45, .25), .94)

    # A complete 3x3-lot civic block with a broad apparatus apron to the road.
    # The paved surfaces use millimetre-scale top offsets above the lawn. Their
    # former exactly coplanar tops z-fought between green and grey at distance.
    add_box(col, "fire_campus_lawn", 36.0, 36.0, .26, 0, 0, 0, lawn)
    add_box(col, "fire_apron", 31.5, 12.2, .123, 0, -11.8, .14, concrete)
    for x in (-9.5, -3.2, 3.2, 9.5):
        add_box(col, "fire_apron_joint", .08, 11.7, .018,
                x, -11.8, .266, cream)
    add_box(col, "fire_side_drive", 6.0, 27.0, .126, 14.2, .8, .14, asphalt)
    add_box(col, "fire_rear_service", 30.0, 5.2, .129, 0, 14.4, .14, asphalt)

    # Main apparatus hall and a taller civic watch tower.
    add_box(col, "fire_hall", 29.0, 17.4, 7.4, 0, 3.4, .26, brick)
    add_box(col, "fire_hall_roof", 29.8, 18.2, .48, 0, 3.4, 7.66, dark)
    add_box(col, "fire_front_belt", 29.5, .42, .42, 0, -5.35, 6.78, cream)
    add_box(col, "fire_parapet", 29.7, 1.0, 1.2, 0, -5.20, 7.35, brick_dark)
    add_box(col, "fire_parapet_cap", 30.2, 1.15, .28, 0, -5.20, 8.55, cream)

    tower_x = -10.9
    add_box(col, "fire_tower", 6.4, 7.2, 13.2, tower_x, 4.7, .26, brick_dark)
    add_box(col, "fire_tower_cap", 7.0, 7.8, .48, tower_x, 4.7, 13.46, cream)
    add_prism_roof(col, "fire_tower_roof", 7.4, 8.2, 2.1,
                   tower_x, 4.7, 13.94, dark)
    for side_x in (-1, 1):
        add_box(col, "fire_tower_louver", 1.15, .16, 2.25,
                tower_x + side_x * 1.55, 1.02, 9.55, glass)
        for dx in (-.34, 0, .34):
            add_box(col, "fire_tower_mullion", .09, .20, 2.25,
                    tower_x + side_x * 1.55 + dx, .92, 9.55, cream)
    add_text(col, "fire_tower_number", "1", 2.15, .09,
             tower_x, .80, 5.75, white)

    # Three correctly proportioned apparatus bays. Two are glazed overhead
    # doors; the center is open so the detailed engine is unmistakable.
    bay_centers = (-7.6, 0.0, 7.6)
    for bay_x in bay_centers:
        add_box(col, "fire_bay_frame", 6.55, .40, 6.15,
                bay_x, -5.48, .42, cream)
        add_box(col, "fire_bay_opening", 5.75, .28, 5.45,
                bay_x, -5.72, .66, dark)
        add_box(col, "fire_bay_header", 6.8, .52, .52,
                bay_x, -5.60, 6.37, brick_dark)
    for bay_x in (-7.6, 7.6):
        add_box(col, "fire_bay_door", 5.45, .12, 5.15,
                bay_x, -5.88, .80, bay_glass)
        for z in (1.72, 2.68, 3.64, 4.60, 5.56):
            add_box(col, "fire_door_rail", 5.45, .08, .09,
                    bay_x, -5.97, z, cream)
        for xoff in (-1.78, 0, 1.78):
            add_box(col, "fire_door_mullion", .09, .08, 5.15,
                    bay_x + xoff, -5.97, .80, cream)

    def add_engine(prefix, x, y, visible=True):
        # Engine front points toward local -Y and sits naturally inside a bay.
        add_box(col, prefix + "_body", 4.55, 7.4, 2.75, x, y, .46,
                red if visible else red_dark)
        add_box(col, prefix + "_cab", 4.35, 2.55, 3.15, x, y - 3.25, .46, red)
        add_box(col, prefix + "_windshield", 3.65, .12, 1.18,
                x, y - 4.56, 2.10, glass)
        add_box(col, prefix + "_bumper", 4.65, .38, .38,
                x, y - 4.72, .50, metal)
        add_box(col, prefix + "_grille", 2.25, .10, .72,
                x, y - 4.94, .94, dark)
        for lx in (-1.58, 1.58):
            add_box(col, prefix + "_headlight", .48, .10, .42,
                    x + lx, y - 4.95, 1.05, warm)
        for wx in (-1.95, 1.95):
            for wy in (y - 2.55, y + 2.15):
                wheel = add_ngon_cone(col, prefix + "_wheel", .70, .70, .34, 12,
                                      x + wx, wy, .38, dark)
                wheel.rotation_euler.y = math.pi / 2
        add_box(col, prefix + "_equipment", 4.15, 3.65, 2.35,
                x, y + 1.45, 2.95, red_dark)
        for side in (-1, 1):
            add_box(col, prefix + "_locker", .10, 3.15, 1.65,
                    x + side * 2.15, y + 1.45, 2.15, metal)
        add_box(col, prefix + "_ladder", 3.75, .42, .30,
                x, y + .65, 5.38, cream)
        for rung_y in (y - .4, y + .35, y + 1.1, y + 1.85):
            add_box(col, prefix + "_ladder_rung", 3.75, .10, .10,
                    x, rung_y, 5.43, metal)
        add_box(col, prefix + "_lightbar", 2.35, .38, .24,
                x, y - 3.35, 3.82, red)

    add_engine("fire_engine_center", 0, -2.4, True)
    # Side engines remain behind the glass for depth and a staffed-station feel.
    add_engine("fire_engine_left", -7.6, .25, False)
    add_engine("fire_engine_right", 7.6, .25, False)

    # Administration entrance and street-readable identity.
    add_box(col, "fire_admin_entry", 4.6, 1.8, 4.3, 11.9, -5.95, .28, cream)
    add_box(col, "fire_admin_glass", 3.7, .12, 3.30,
            11.9, -6.92, .72, glass)
    add_box(col, "fire_admin_split", .12, .16, 3.25,
            11.9, -7.02, .72, metal)
    add_box(col, "fire_admin_canopy", 5.2, 2.2, .30,
            11.9, -6.45, 4.45, red_dark)
    add_text(col, "fire_title", "FOLLOWVILLE FIRE & RESCUE", .78, .07,
             0, -5.86, 7.52, white)
    add_text(col, "fire_station_label", "STATION 1", .48, .06,
             11.9, -7.10, 3.80, red_dark)

    # Side and rear fenestration, rooftop systems, radio mast, and solar array.
    for y in (-1.0, 2.4, 5.8, 9.2):
        add_box(col, "fire_side_window_frame", .30, 1.78, 1.75,
                14.58, y, 2.85, cream)
        add_box(col, "fire_side_window", .18, 1.42, 1.38,
                14.77, y, 3.04, glass)
    for hx, hy in ((4.8, 5.4), (9.0, 5.4)):
        add_box(col, "fire_hvac", 2.8, 2.0, 1.05, hx, hy, 8.14, metal)
        add_box(col, "fire_hvac_cap", 3.0, 2.2, .18, hx, hy, 9.19, dark)
    for sx in (-4.2, 0, 4.2):
        panel = add_box(col, "fire_solar", 3.5, 1.7, .16,
                        sx, 8.0, 8.30, glass)
        panel.rotation_euler.x = math.radians(12)
    add_ngon_cone(col, "fire_radio_mast", .10, .07, 7.0, 10,
                  tower_x, 4.7, 16.05, metal)
    for z in (18.2, 20.2):
        add_box(col, "fire_radio_crossbar", 2.4, .10, .10,
                tower_x, 4.7, z, metal)
    add_uv_sphere(col, "fire_siren", .55, tower_x, 4.7, 23.0, red, 6, 10)

    # Operational street details: flag, hydrant, monument sign, and parking.
    add_ngon_cone(col, "fire_flagpole", .10, .07, 10.5, 10,
                  -15.0, -8.8, .26, metal)
    flag_mesh = bpy.data.meshes.new("fire_flag_mesh")
    flag_mesh.from_pydata([(-14.9, -8.8, 9.5), (-11.4, -8.8, 8.8),
                           (-14.9, -8.8, 8.15)], [], [(0, 1, 2)])
    flag_mesh.materials.append(red)
    flag_mesh.update()
    flag_obj = bpy.data.objects.new("fire_flag", flag_mesh)
    col.objects.link(flag_obj)
    add_box(col, "fire_sign_base", 6.2, 1.2, .45, -10.6, -14.5, .26, concrete)
    add_box(col, "fire_sign", 5.5, .68, 1.55, -10.6, -14.5, .65, brick_dark)
    add_text(col, "fire_sign_text", "FIRE  1", .50, .05,
             -10.6, -14.88, 1.68, white)
    add_ngon_cone(col, "fire_hydrant_body", .32, .27, .95, 10,
                  14.9, -13.4, .27, red)
    add_ngon_cone(col, "fire_hydrant_cap", .43, .22, .42, 10,
                  14.9, -13.4, 1.22, red_dark)
    for y in (10.6, 13.1, 15.6):
        add_box(col, "fire_parking_stripe", 5.2, .10, .025,
                14.2, y, .28, white)
    for x in (-15.5, 15.5):
        build_tree(col, rng, .62 + rng.random() * .12, x, 12.8)


# Moved 13m east on 2026-07-31. The 45m foundation spanned x[-25.5,19.5] and
# swallowed the Pine Hollow connector's terminus at (-24,-137) together with
# the first three segments of the district's own road: the street drove into
# the left wing and stopped. The campus moves rather than the road, because
# the road serves houses and the terminus is fixed by the district plan.
CITY_HALL_X = 10.0
CITY_HALL_Y = -134.0
CITY_HALL_ROAD_Y = -93.0
# CITY_HALL_APPROACH lives in world_layout so the geometry audit can see it.
CIVIC_SQUARE_X = 56.0
CIVIC_SQUARE_Y = -134.0
# FISHING_POND_* now live in downtown_visual_plan beside terrain_height, which
# has to carry the pond's level shelf. See the note there for the move.


def build_city_hall_road(col, seed):
    """Terrain-following extension from the central grid to City Hall."""
    m = std_mats()
    shoulder = mat("NB_cityhall_road_shoulder", (.25, .28, .25), .98)
    walk = mat("NB_cityhall_walk", (.67, .65, .59), .94)
    marking = mat("NB_cityhall_lane_marking", (.88, .82, .58), .80)
    # The junction stays on the x=-3 grid intersection while the campus itself
    # sits 13m further east, so the approach bends instead of running straight.
    origin = (CITY_HALL_X, CITY_HALL_ROAD_Y)
    points = [(x - origin[0], y - origin[1], 0) for x, y in CITY_HALL_APPROACH]
    _add_road_strip(col, "cityhall_road_shoulder", points, shoulder,
                    width=7.6, bottom_offset=.006, top_offset=.046,
                    terrain_origin=origin)
    _add_road_strip(col, "cityhall_road", points, m["road"],
                    width=6.1, bottom_offset=.016, top_offset=.091,
                    terrain_origin=origin)
    for side in (-1, 1):
        side_points = []
        for index, (x, y, z) in enumerate(points):
            before = points[max(0, index - 1)]
            after = points[min(len(points) - 1, index + 1)]
            dx, dy = after[0] - before[0], after[1] - before[1]
            length = math.hypot(dx, dy) or 1.0
            side_points.append((x + side * 4.55 * -dy / length,
                                y + side * 4.55 * dx / length, z))
        _add_road_strip(col, "cityhall_sidewalk", side_points, walk,
                        width=1.35, bottom_offset=.012, top_offset=.062,
                        terrain_origin=origin)
    for distance in (6.0, 15.0, 23.0):
        x, y, angle = _polyline_sample(points, distance)
        z = terrain_height(origin[0] + x, origin[1] + y)
        dash = add_box(col, "cityhall_road_dash", 2.4, .18, .018,
                       x, y, z + .094, marking)
        dash.rotation_euler.z = angle


def build_city_hall(col, seed):
    """Neoclassical civic capitol integrated into Followville's south slope."""
    rng = random.Random(seed)
    limestone = mat("NB_cityhall_limestone", (.83, .81, .74), .78)
    limestone_light = mat("NB_cityhall_limestone_light", (.94, .92, .85), .70)
    stone = mat("NB_cityhall_foundation", (.35, .36, .34), .96)
    roof = mat("NB_cityhall_roof", (.20, .29, .31), .72, .32)
    copper = mat("NB_cityhall_copper", (.28, .48, .43), .66, .22)
    glass = mat("NB_cityhall_glass", (.12, .28, .35), .18, .08, 1.0, 0.0, .54)
    door = mat("NB_cityhall_door", (.22, .12, .075), .78)
    bronze = mat("NB_cityhall_bronze", (.42, .29, .12), .58, .55)
    concrete = mat("NB_cityhall_plaza", (.72, .70, .65), .90)
    lawn = mat("NB_cityhall_lawn", (.30, .52, .27), .98)
    flag_blue = mat("NB_cityhall_flag_blue", (.09, .22, .46), .78)
    flag_gold = mat("NB_cityhall_flag_gold", (.92, .69, .18), .66)

    def grade(lx, ly):
        return terrain_height(CITY_HALL_X + lx, CITY_HALL_Y + ly)

    # The structural floor is level while the exposed stone foundation absorbs
    # the natural grade. Terraced lawn pieces follow the hillside at each side.
    samples = [grade(x, y) for x in (-21, 0, 21) for y in (-9, 0, 9)]
    floor_z = max(samples) + .16
    low_z = min(samples) - .06
    add_box(col, "cityhall_embedded_foundation", 45.0, 20.0,
            floor_z - low_z, 0, -1.0, low_z, stone)
    for x in (-18.5, 18.5):
        side_grade = grade(x, 8)
        add_box(col, "cityhall_terrace_lawn", 8.0, 10.0, .12,
                x, 8.0, side_grade + .02, lawn)
        add_box(col, "cityhall_terrace_wall", 8.5, .42,
                max(.35, floor_z - side_grade), x, 3.1, side_grade, stone)

    # Symmetrical wings and a taller central rotunda block.
    add_box(col, "cityhall_left_wing", 16.0, 16.5, 8.3,
            -14.0, 0, floor_z, limestone)
    add_box(col, "cityhall_right_wing", 16.0, 16.5, 8.3,
            14.0, 0, floor_z, limestone)
    add_box(col, "cityhall_center", 15.5, 18.8, 11.1,
            0, -.6, floor_z, limestone_light)
    add_offset_pyramid(col, "cityhall_left_roof", 17.0, 17.4, 2.2,
                       -14.0, 0, floor_z + 8.3, 0, 0, roof)
    add_offset_pyramid(col, "cityhall_right_roof", 17.0, 17.4, 2.2,
                       14.0, 0, floor_z + 8.3, 0, 0, roof)

    # Portico, columns and pediment face north toward the existing city grid.
    portico_y = 10.0
    add_box(col, "cityhall_portico_floor", 20.0, 5.2, .42,
            0, portico_y, floor_z, limestone_light)
    for x in (-7.6, -5.05, -2.52, 0, 2.52, 5.05, 7.6):
        add_ngon_cone(col, "cityhall_column_base", .58, .58, .30, 16,
                      x, 11.25, floor_z + .42, limestone_light)
        add_ngon_cone(col, "cityhall_column", .43, .36, 7.9, 16,
                      x, 11.25, floor_z + .72, limestone_light)
        add_ngon_cone(col, "cityhall_column_cap", .62, .62, .34, 16,
                      x, 11.25, floor_z + 8.62, limestone_light)
    add_box(col, "cityhall_portico_entablature", 20.5, 4.9, .85,
            0, 10.1, floor_z + 8.96, limestone_light)
    pediment = add_prism_roof(col, "cityhall_pediment", 21.0, 5.1, 3.1,
                             0, 10.1, floor_z + 9.81, limestone_light)
    pediment.rotation_euler.z = 0

    # Broad public stairs descend naturally into the terrain-following plaza.
    for index in range(6):
        width = 21.0 + (5 - index) * .75
        y = 13.1 + index * .9
        top = floor_z - index * .16
        ground = grade(0, y)
        add_box(col, "cityhall_front_step", width, 1.05,
                max(.14, top - ground), 0, y, ground, limestone_light)
    plaza_points = [(0, 20.0, 0), (0, 17.2, 0)]
    _add_road_strip(col, "cityhall_entry_plaza", plaza_points, concrete,
                    width=20.5, bottom_offset=.014, top_offset=.074,
                    terrain_origin=(CITY_HALL_X, CITY_HALL_Y))

    # Doors, windows and trim give the facade readable civic scale.
    for x in (-2.0, 0, 2.0):
        add_box(col, "cityhall_entry_door", 1.55, .22, 3.2,
                x, 9.55, floor_z + .45, door)
        add_box(col, "cityhall_door_glass", 1.12, .08, 1.3,
                x, 9.71, floor_z + 1.65, glass)
    for wing_x in (-14.0, 14.0):
        for xoff in (-5.0, -1.7, 1.7, 5.0):
            for level in (2.0, 5.25):
                add_box(col, "cityhall_window", 1.55, .16, 1.95,
                        wing_x + xoff, 8.32, floor_z + level, glass)
                add_box(col, "cityhall_window_cap", 1.9, .28, .20,
                        wing_x + xoff, 8.43, floor_z + level + 1.95,
                        limestone_light)
    add_text(col, "cityhall_title", "FOLLOWVILLE  CITY  HALL", .58, .055,
             0, 12.62, floor_z + 9.35, bronze,
             rotation=(math.pi / 2, 0, math.pi))

    # Central drum, oxidized civic dome, lantern and flag.
    add_ngon_cone(col, "cityhall_drum", 5.0, 4.7, 3.1, 24,
                  0, -.6, floor_z + 11.1, limestone_light)
    for angle in [i * math.tau / 8 for i in range(8)]:
        add_box(col, "cityhall_drum_window", .85, .18, 1.25,
                3.98 * math.cos(angle), -.6 + 3.98 * math.sin(angle),
                floor_z + 12.05, glass).rotation_euler.z = angle + math.pi / 2
    dome = add_uv_sphere(col, "cityhall_dome", 4.85, 0, -.6,
                         floor_z + 15.05, copper, 10, 24)
    dome.scale.z = .62
    add_ngon_cone(col, "cityhall_lantern", 1.25, 1.0, 2.35, 16,
                  0, -.6, floor_z + 17.55, limestone_light)
    add_ngon_cone(col, "cityhall_cupola", 1.45, 0, 1.35, 16,
                  0, -.6, floor_z + 19.9, copper)
    add_ngon_cone(col, "cityhall_flagpole", .09, .055, 7.2, 12,
                  0, -.6, floor_z + 21.0, bronze)
    flag_mesh = bpy.data.meshes.new("cityhall_flag_mesh")
    z0 = floor_z + 27.2
    flag_mesh.from_pydata([(0, -.6, z0), (4.0, -.6, z0 - .72),
                           (0, -.6, z0 - 1.55)], [], [(0, 1, 2)])
    flag_mesh.materials.append(flag_blue)
    flag_mesh.update()
    flag = bpy.data.objects.new("cityhall_flag", flag_mesh)
    col.objects.link(flag)
    add_ngon_cone(col, "cityhall_flag_seal", .34, .34, .04, 16,
                  1.15, -.64, z0 - .82, flag_gold, rot=math.pi / 16)

    # Restrained civic landscaping, kept low so the architecture stays legible.
    for side in (-1, 1):
        for y in (10.0, 15.2):
            build_tree(col, rng, .52, side * 15.8, y)
        add_box(col, "cityhall_planter", 5.8, 1.2, .48,
                side * 12.2, 13.4, grade(side * 12.2, 13.4) + .05, stone)
        for xoff in (-1.7, 0, 1.7):
            add_uv_sphere(col, "cityhall_shrub", .62,
                          side * 12.2 + xoff, 13.4,
                          grade(side * 12.2 + xoff, 13.4) + .47,
                          lawn, 6, 10)


def build_civic_square(col, seed):
    """Permanent public square that follows the hillside beside City Hall."""
    rng = random.Random(seed)
    paver = mat("NB_civic_square_paver", (.57, .58, .57), .92)
    border = mat("NB_civic_square_border", (.76, .74, .67), .88)
    stone = mat("NB_civic_square_stone", (.43, .44, .42), .94)
    water = mat("NB_civic_square_water", (.17, .52, .66), .18, .08)
    bronze = mat("NB_civic_square_bronze", (.38, .27, .13), .58, .55)
    wood = mat("NB_civic_square_wood", (.35, .19, .10), .78)
    flower_a = mat("NB_civic_flower_a", (.86, .23, .28), .72)
    flower_b = mat("NB_civic_flower_b", (.96, .72, .18), .68)
    m = std_mats()

    def grade(lx, ly):
        return terrain_height(CIVIC_SQUARE_X + lx, CIVIC_SQUARE_Y + ly)

    # A subdivided surface follows the actual regional terrain. This avoids
    # both a hovering slab and a hillside cutting through a flat plaza.
    xs = [-17.0, -11.5, -5.75, 0.0, 5.75, 11.5, 17.0]
    ys = [-16.0, -10.7, -5.35, 0.0, 5.35, 10.7, 16.0]
    verts = [(x, y, grade(x, y) + .065) for y in ys for x in xs]
    faces = []
    row = len(xs)
    for iy in range(len(ys) - 1):
        for ix in range(len(xs) - 1):
            a = iy * row + ix
            faces.append((a, a + 1, a + row + 1, a + row))
    mesh = bpy.data.meshes.new("civic_square_terrain_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(paver)
    mesh.update()
    plaza = bpy.data.objects.new("civic_square_terrain", mesh)
    col.objects.link(plaza)

    origin = (CIVIC_SQUARE_X, CIVIC_SQUARE_Y)
    edges = (
        [(-17, -16, 0), (17, -16, 0)],
        [(17, -16, 0), (17, 16, 0)],
        [(17, 16, 0), (-17, 16, 0)],
        [(-17, 16, 0), (-17, -16, 0)],
    )
    for points in edges:
        _add_road_strip(col, "civic_square_border", points, border,
                        width=1.15, bottom_offset=.062, top_offset=.115,
                        terrain_origin=origin)
    # Short, terrain-following connector from City Hall's east terrace.
    _add_road_strip(col, "civic_square_cityhall_walk",
                    [(-23.0, 8.5, 0), (-16.4, 8.5, 0)], border,
                    width=4.4, bottom_offset=.018, top_offset=.078,
                    terrain_origin=origin)

    # Fountain foundation is intentionally embedded into the slope.
    fountain_grade = grade(-1.0, 1.0)
    add_ngon_cone(col, "civic_fountain_foundation", 5.0, 5.0, .72, 32,
                  -1.0, 1.0, fountain_grade - .22, stone)
    add_ngon_cone(col, "civic_fountain_basin", 4.55, 4.25, .62, 32,
                  -1.0, 1.0, fountain_grade + .25, border)
    add_ngon_cone(col, "civic_fountain_water", 3.82, 3.82, .08, 32,
                  -1.0, 1.0, fountain_grade + .76, water)
    add_ngon_cone(col, "civic_fountain_pedestal", 1.35, .82, 2.1, 20,
                  -1.0, 1.0, fountain_grade + .78, stone)
    add_ngon_cone(col, "civic_fountain_nozzle", .34, .22, .58, 16,
                  -1.0, 1.0, fountain_grade + 2.76, bronze)
    for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        x, y = -1.0 + 1.65 * math.cos(angle), 1.0 + 1.65 * math.sin(angle)
        # Thick, luminous water arcs are readable from the square and from
        # daily aerial footage. The old hair-thin straight cones disappeared
        # against the basin at normal viewing distance.
        start = Vector((x, y, fountain_grade + 1.02))
        end = Vector((-1.0 + .34 * math.cos(angle),
                      1.0 + .34 * math.sin(angle),
                      fountain_grade + 1.72))
        midpoint = (start + end) * .5 + Vector((0, 0, .66))
        _add_connected_tube(
            col, "civic_fountain_water_arc",
            (start, midpoint, end), (.115, .108, .10), water, 10)
        add_uv_sphere(col, "civic_fountain_splash", .20,
                      end.x, end.y, end.z, water, 7, 10)
    # A central plume and two stepped spill bowls make the fountain read as a
    # working civic centerpiece instead of a stone finial in a blue disk.
    add_ngon_cone(col, "civic_fountain_lower_bowl", 1.42, 1.18, .20, 24,
                  -1.0, 1.0, fountain_grade + 2.02, stone)
    add_ngon_cone(col, "civic_fountain_upper_bowl", .90, .66, .17, 24,
                  -1.0, 1.0, fountain_grade + 2.56, border)
    add_ngon_cone(col, "civic_fountain_center_plume", .10, .055, 1.70, 10,
                  -1.0, 1.0, fountain_grade + 3.22, water)
    add_uv_sphere(col, "civic_fountain_plume_crown", .26,
                  -1.0, 1.0, fountain_grade + 5.02, water, 7, 10)

    # A modest permanent stage at the south edge supports future civic events.
    stage_y = -11.8
    stage_samples = [grade(x, y) for x in (-6.8, 0, 6.8)
                     for y in (stage_y - 2.5, stage_y + 2.5)]
    stage_top = max(stage_samples) + .24
    stage_low = min(stage_samples) - .04
    add_box(col, "civic_stage_foundation", 14.2, 5.4,
            stage_top - stage_low, 0, stage_y, stage_low, stone)
    add_box(col, "civic_stage_deck", 13.8, 5.0, .22,
            0, stage_y, stage_top + .006, wood)
    for index in range(3):
        y = stage_y + 3.0 + index * .55
        g = grade(0, y)
        add_box(col, "civic_stage_step", 7.0 + index * .75, .65,
                max(.12, stage_top - index * .16 - g),
                0, y, g, border)

    # Benches, lamps and low planting preserve clear sightlines to the stage.
    for x, y, rot in ((-12.8, 6.5, math.pi / 2), (12.8, 6.5, -math.pi / 2),
                      (-12.8, -5.0, math.pi / 2), (12.8, -5.0, -math.pi / 2)):
        z = grade(x, y) + .11
        seat = add_box(col, "civic_bench_seat", 3.2, .62, .28, x, y, z, wood)
        back = add_box(col, "civic_bench_back", 3.2, .18, 1.05,
                       x, y + .34, z + .22, wood)
        seat.rotation_euler.z = rot
        back.rotation_euler.z = rot
        for dx in (-1.15, 1.15):
            leg = add_box(col, "civic_bench_leg", .18, .42, .72,
                          x + dx * math.cos(rot), y + dx * math.sin(rot),
                          z - .03, bronze)
            leg.rotation_euler.z = rot
    for x, y in ((-14.5, 13.0), (14.5, 13.0), (-14.5, -13.5), (14.5, -13.5)):
        z = grade(x, y) + .10
        add_ngon_cone(col, "civic_lamp_post", .13, .08, 4.7, 10,
                      x, y, z, bronze)
        add_uv_sphere(col, "civic_lamp_globe", .36, x, y, z + 4.72,
                      m["bulb"], 6, 10)
    for side in (-1, 1):
        x = side * 14.0
        for y in (-8.0, 0.0, 8.0):
            z = grade(x, y) + .10
            add_box(col, "civic_planter", 2.3, 1.45, .48,
                    x, y, z, stone)
            for index, dx in enumerate((-.65, 0, .65)):
                add_uv_sphere(col, "civic_flower", .28,
                              x + dx, y, z + .52,
                              flower_a if (index + side) % 2 else flower_b,
                              5, 8)


def build_fishing_pond(col, seed):
    """Large off-grid fishing destination with a walk-up dock and shoreline."""
    rng = random.Random(seed)
    water = mat("NB_fishing_water", (.10, .40, .56), .22, .10)
    deep = mat("NB_fishing_deep", (.045, .20, .28), .72)
    bank = mat("NB_fishing_bank", (.34, .52, .25), .96)
    shore = mat("NB_fishing_shore", (.53, .48, .34), .94)
    stone = mat("NB_fishing_stone", (.46, .47, .44), .92)
    dock = mat("NB_fishing_dock", (.36, .22, .11), .86)
    metal = mat("NB_fishing_metal", (.12, .16, .17), .72, .42)
    reed = mat("NB_fishing_reed", (.31, .46, .18), .90)
    lily = mat("NB_fishing_lily", (.20, .45, .24), .80)
    sign = mat("NB_fishing_sign", (.80, .70, .48), .88)
    red = mat("NB_fishing_buoy_red", (.76, .10, .08), .64)
    white = mat("NB_fishing_buoy_white", (.94, .93, .86), .70)
    m = std_mats()
    segments = 48

    def irregular(angle, phase):
        return 1.0 + .045 * math.sin(angle * 3 + phase) + .025 * math.sin(angle * 7 - phase)

    inner_points = []
    outer_points = []
    for index in range(segments):
        angle = math.tau * index / segments
        outer_scale = irregular(angle, .35)
        inner_scale = irregular(angle, 1.15)
        outer_points.append((FISHING_POND_RX * outer_scale * math.cos(angle),
                             FISHING_POND_RY * outer_scale * math.sin(angle)))
        inner_points.append((18.0 * inner_scale * math.cos(angle),
                             11.3 * inner_scale * math.sin(angle)))

    # Keep the water genuinely level while allowing the surrounding bank to
    # follow the meadow. The inner bank rises just above this datum and masks
    # the untouched terrain below the opaque deep-water layer.
    # The datum only has to clear the pond bed, not the lip around it. Taking
    # the inner ring's maximum raised the surface to the highest point of the
    # rim, which stood the water 66cm proud of the lowest surrounding meadow.
    # The interior is what the opaque surface must hide, so measure that.
    water_z = max(
        terrain_height(FISHING_POND_X + x * .82, FISHING_POND_Y + y * .82)
        for x, y in inner_points) + .10
    verts = []
    for x, y in outer_points:
        verts.append((x, y, terrain_height(FISHING_POND_X + x, FISHING_POND_Y + y) + .06))
    for x, y in inner_points:
        verts.append((x, y, max(water_z + .07,
                               terrain_height(FISHING_POND_X + x, FISHING_POND_Y + y) + .08)))
    faces = []
    for index in range(segments):
        nxt = (index + 1) % segments
        faces.append((index, nxt, segments + nxt, segments + index))
    bank_mesh = bpy.data.meshes.new("fishing_pond_bank_mesh")
    bank_mesh.from_pydata(verts, [], faces)
    bank_mesh.materials.append(bank)
    bank_mesh.update()
    bank_obj = bpy.data.objects.new("fishing_pond_bank", bank_mesh)
    col.objects.link(bank_obj)

    water_verts = [(0, 0, water_z)] + [(x, y, water_z) for x, y in inner_points]
    water_faces = [(0, index + 1, (index + 1) % segments + 1)
                   for index in range(segments)]
    for name, z_offset, material in (
            ("fishing_pond_deep", -.16, deep),
            ("fishing_pond_water", 0, water)):
        mesh = bpy.data.meshes.new(name + "_mesh")
        mesh.from_pydata([(x, y, z + z_offset) for x, y, z in water_verts],
                         [], water_faces)
        mesh.materials.append(material)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        col.objects.link(obj)

    # Terrain-following public sidewalk from the town's northern kerb to the
    # west-bank fishing deck. It is intentionally a path, not a new road, and
    # it starts on the paved edge so the pond reads as somewhere you walk to.
    approach = [(-26.0, -24.0, 0), (-27.0, -18.0, 0), (-26.0, -12.0, 0),
                (-23.0, -7.0, 0), (-20.0, -3.0, 0)]
    _add_road_strip(col, "fishing_pond_sidewalk", approach, shore,
                    width=2.65, bottom_offset=.025, top_offset=.09,
                    terrain_origin=(FISHING_POND_X, FISHING_POND_Y))

    dock_z = water_z + .28
    add_box(col, "fishing_dock_walk", 9.0, 3.0, .28,
            -15.1, -2.7, dock_z - .28, dock)
    add_box(col, "fishing_dock_head", 4.8, 7.0, .28,
            -10.8, -2.7, dock_z - .28, dock)
    for x in (-19.4, -15.0, -10.7, -8.5):
        for y in (-5.8, .4):
            add_ngon_cone(col, "fishing_dock_pile", .18, .16, 1.55, 10,
                          x, y, water_z - .72, metal)
    for x in (-17.8, -14.0, -10.2):
        for y in (-4.35, -1.05):
            add_ngon_cone(col, "fishing_dock_rail_post", .075, .065, 1.10, 8,
                          x, y, dock_z, metal)
    for y in (-4.35, -1.05):
        add_beam_between(col, "fishing_dock_rail",
                         (-17.8, y, dock_z + .92), (-10.2, y, dock_z + .92),
                         .12, metal)

    # Shore stones, reeds, lilies, and a small buoy add scale without
    # cluttering the clear casting lane off the center of the dock.
    for index in range(14):
        angle = math.tau * (index + .25) / 14
        radius_x = 19.0 + rng.uniform(-.4, .5)
        radius_y = 12.3 + rng.uniform(-.3, .4)
        x, y = radius_x * math.cos(angle), radius_y * math.sin(angle)
        z = max(water_z + .03,
                terrain_height(FISHING_POND_X + x, FISHING_POND_Y + y) + .08)
        rock = add_uv_sphere(col, "fishing_shore_stone",
                             rng.uniform(.35, .68), x, y, z, stone, 5, 8)
        rock.scale.z = rng.uniform(.55, .78)
    for index in range(22):
        angle = rng.uniform(0, math.tau)
        x, y = 17.2 * math.cos(angle), 10.7 * math.sin(angle)
        if x < -8 and abs(y + 2.7) < 5.5:
            continue
        height = rng.uniform(.8, 1.45)
        stalk = add_ngon_cone(col, "fishing_reed", .05, .025, height, 7,
                              x, y, water_z + .01, reed)
        stalk.rotation_euler.x = rng.uniform(-.10, .10)
        stalk.rotation_euler.y = rng.uniform(-.10, .10)
    for x, y, scale in ((3.5, 2.8, 1.0), (7.2, -3.4, .8), (-.8, -5.8, .72),
                        (10.5, 4.4, .62), (-5.4, 5.6, .74)):
        add_ngon_cone(col, "fishing_lily", .82 * scale, .82 * scale, .055, 12,
                      x, y, water_z + .035, lily)
    add_ngon_cone(col, "fishing_buoy", .34, .24, .62, 12,
                  4.2, -1.0, water_z + .02, red)
    add_uv_sphere(col, "fishing_buoy_cap", .16,
                  4.2, -1.0, water_z + .71, white, 6, 8)

    # Landmark sign and rod rack face the station-side approach.
    sign_grade = terrain_height(FISHING_POND_X - 21.5, FISHING_POND_Y - 7.4)
    for x in (-23.8, -19.2):
        add_ngon_cone(col, "fishing_sign_post", .10, .08, 2.25, 8,
                      x, -7.4, sign_grade + .04, metal)
    add_box(col, "fishing_sign_board", 5.2, .22, 1.45,
            -21.5, -7.4, sign_grade + 1.25, sign)
    add_text(col, "fishing_sign_text", "FISHING POND", .34, .035,
             -21.5, -7.56, sign_grade + 1.74, metal)
    add_box(col, "fishing_rod_rack", 2.1, .45, .22,
            -18.4, 1.15, dock_z + .05, dock)
    for index in range(3):
        x = -19.05 + index * .65
        rod = add_ngon_cone(col, "fishing_rod", .035, .018, 2.45, 7,
                            x, 1.15, dock_z + .22, metal)
        rod.rotation_euler.x = math.radians(-8)


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

RIVER_ASSET_VARIANTS = [
    ("AST_river_house_%02d" % i, lambda c, i=i: build_river_house(c, i))
    for i in range(8)
]

FOOD_ASSET_VARIANTS = [
    ("AST_food_%02d" % i, lambda c, i=i: build_food_house(c, i))
    for i in range(10)
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
    "highwaymast": [("AST_light_highway_mast",
                     lambda c: build_highway_mast(c))],
    "highmast":    [("AST_light_high_mast",
                     lambda c: build_high_mast(c))],
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
    "metrotower":  [("AST_metro_%02d" % i, lambda c, i=i: build_metro_tower(c, i))
                     for i in range(METRO_TOWER_COUNT)],
    "stadium":     [("AST_stadium_0", lambda c: build_stadium(c, 900))],
    "pond":        [("AST_pond_0", lambda c: build_pond(c, 1950))],
    "elementaryschool": [("AST_elementaryschool_0", lambda c: build_elementary_school(c, 2500))],
    "highschool": [("AST_highschool_0", lambda c: build_high_school(c, 2600))],
    "constructionzone": [("AST_constructionzone_0", lambda c: build_construction_zone(c, 3300))],
    "movietheater": [("AST_movietheater_0", lambda c: build_movie_theater(c, 3500))],
    "arcade": [("AST_arcade_0", lambda c: build_followville_arcade(c, 129))],
    "followmart":  [("AST_followmart_4", lambda c: build_followmart(c, 2600))],
    "coffeetruck": [("AST_coffeetruck_0", lambda c: build_coffee_truck(c, 2700))],
    "firestation": [("AST_firestation_0", lambda c: build_fire_station(c, 2800))],
    "cityhallroad": [("AST_cityhallroad_0", lambda c: build_city_hall_road(c, 2900))],
    "cityhall": [("AST_cityhall_0", lambda c: build_city_hall(c, 3000))],
    "civicsquare": [("AST_civicsquare_0", lambda c: build_civic_square(c, 3100))],
    "fishingpond": [("AST_fishingpond_0", lambda c: build_fishing_pond(c, 3200))],
    "raftingstation": [("AST_raftingstation_0", lambda c: build_rafting_station(c, 3600))],
    "salmonproshop": [("AST_salmonproshop_0", lambda c: build_salmon_pro_shop(c, 3800))],
    "apartmentcomplex": [("AST_apartmentcomplex_0", lambda c: build_apartment_complex(c, 7300))],
    "northcrowncampus": [("AST_northcrowncampus_0", lambda c: build_north_crown_campus(c, 8500))],
    "foodcourt": [("AST_foodcourt_0", lambda c: build_food_court(c, 8100))],
    "gasstation": [("AST_gasstation_0", lambda c: build_gas_station(c, 8200))],
    "restaurant": [("AST_restaurant_0", lambda c: build_restaurant(c, 8300))],
    "weatherstation": [("AST_weatherstation_0", lambda c: build_weather_station(c, 3700))],
    "nuclearplant": [("AST_nuclearplant_0", lambda c: build_nuclear_plant(c, 8400))],
    "forestreserve": [("AST_eastwoods_0", lambda c: build_east_woods(c, 3400))],
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
    if b.get("type") == "fishingpond":
        return "fishing-pond"
    if b.get("type") == "raftingstation":
        return "rafting-station"
    if b.get("type") == "salmonproshop":
        return "salmon-pro-shop"
    if b.get("type") == "apartmentcomplex":
        return "apartment-complex"
    if b.get("type") == "northcrowncampus":
        return "north-crown-campus"
    if b.get("type") == "highschool":
        return "high-school"
    if b.get("type") in ("foodhouse", "foodcourt"):
        return "food-court"
    if b.get("type") == "weatherstation":
        return "weather-station"
    if b.get("type") == "constructionzone":
        return "construction-zone"
    if b.get("type") == "movietheater":
        return "movie-theater"
    if b.get("type") == "forestreserve":
        return "east-woods"
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
        "highwaymast": 1, "highmast": 1,
        "storybookhouse": 1,
        "mushroomhouse": 1, "casinohouse": 1, "cathouse": 1, "castlehouse": 1,
        "eiffelhouse": 1, "flowerhouse": 1, "burjhouse": 1, "toilethouse": 1, "beachhouse": 1,
        "cottagehouse": 1, "pond": 1, "ringhouse": 1, "parkdistrict": 1,
        "apartment": 2, "park": 2, "plaza": 2, "skyscraper": 2,
        "metrotower": 1, "stadium": 3,
        "elementaryschool": 3, "constructionzone": 3, "movietheater": 3, "followmart": 3,
        "highschool": 1,
        "arcade": 1,
        "coffeetruck": 1, "firestation": 3, "forestreserve": 1,
        "cityhallroad": 1, "cityhall": 4, "civicsquare": 3, "fishingpond": 1,
        "raftingstation": 1, "weatherstation": 1, "salmonproshop": 1,
        "apartmentcomplex": 1, "northcrowncampus": 1,
        "foodhouse": 1, "foodcourt": 1,
        "gasstation": 1, "restaurant": 1, "nuclearplant": 1}

# check_world_geometry.py needs a grid landmark's lot size to know where its
# geometry is centred, and it cannot import this module because this module
# needs bpy. world_layout carries the copy it reads; this is the assertion that
# stops the two drifting apart silently.
for _type, _lots in LANDMARK_GRID_SIZE.items():
    assert SIZE.get(_type) == _lots, (
        "world_layout.LANDMARK_GRID_SIZE says %s is %d lots, SIZE says %s"
        % (_type, _lots, SIZE.get(_type)))

# The old generic population-2,000 skyscraper is superseded by Crown Quarter's
# deterministic 100-resident tower reserve.  Keeping both would drop an extra
# unrelated tower into the historic grid on the same day the new skyline grows.
MILESTONES = [(500, "plaza"), (10000, "stadium")]

def footprint(b):
    # Planned suburban houses use exact world positions on curving roads, not
    # grid lots.  They therefore reserve no legacy 3x3-grid cell.
    if (b.get("plan_id") or b.get("metro_id") or b.get("feature_id") or
            b["type"] in ("cityhallroad", "cityhall", "civicsquare", "fishingpond",
                          "raftingstation", "forestreserve", "salmonproshop", "apartmentcomplex",
                          "northcrowncampus", "foodhouse", "foodcourt")):
        return []
    if b["type"] == "highschool":
        # The campus stands on the block immediately south of the grid, on
        # lots the downtown block-fill would otherwise reach within a few
        # days' growth. Reserving every lot it covers keeps houses off the
        # pitch, and keeps scatter_nature off it too -- the scatter works from
        # the same occupied set, so no tree can be planted on the running
        # track without this.
        cells = []
        cx, cy = build_pos(b)
        reach_x, reach_y = CAMPUS_HALF_X + 10.0, CAMPUS_HALF_Y + 10.0
        # LOT is smaller than a block's per-lot pitch, so dividing by it
        # always over-estimates the index range rather than clipping it.
        for gx in range(int(math.floor((cx - reach_x) / LOT)) - BLOCK_N,
                        int(math.ceil((cx + reach_x) / LOT)) + BLOCK_N + 1):
            for gy in range(int(math.floor((cy - reach_y) / LOT)) - BLOCK_N,
                            int(math.ceil((cy + reach_y) / LOT)) + BLOCK_N + 1):
                x, y = lot_to_world(gx, gy)
                if abs(x - cx) <= reach_x and abs(y - cy) <= reach_y:
                    cells.append((gx, gy))
        return cells
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
    if b["type"] == "foodhouse":
        variants = FOOD_ASSET_VARIANTS
    elif b["type"] == "house" and b.get("district") in {
            "Rivergate", "Cedarbank", "Timber Bend",
            "Eastbank Village", "River Meadows"}:
        variants = RIVER_ASSET_VARIANTS
    elif b["type"] == "house" and not b.get("plan_id") and "px" not in b:
        variants = URBAN_ASSET_VARIANTS
    elif b["type"] == "metrotower":
        variants = ASSET_VARIANTS["metrotower"]
    else:
        variants = ASSET_VARIANTS[b["type"]]
    variant_index = ((int(b["metro_id"]) - 1) if b.get("metro_id")
                     else b["seed"] % len(variants))
    vname, builder = variants[variant_index % len(variants)]
    asset = get_asset(vname, builder)
    empty = bpy.data.objects.new(name, None)
    empty.instance_type = "COLLECTION"
    empty.instance_collection = asset
    x, y = build_pos(b)
    s = SIZE.get(b["type"], 1)
    if "px" in b:  # exact world placement (district / suburban houses / forest)
        authored_z = b.get("pz")
        if authored_z is None:
            if b.get("plan_id"):
                authored_z = hillside_pad_levels(x, y, b.get("rot", 0.0))[1]
            elif b["type"] == "ringhouse":
                authored_z = 0.1
            elif b["type"] in ("tree", "bush", "rock", "forestreserve"):
                authored_z = terrain_height(x, y)
            elif b["type"] == "foodhouse":
                # The Food Court sits on a levelled hilltop, so it has to
                # follow the terrain like the scatter does. It used to fall
                # through to the `else: authored_z = 0` below and looked
                # correct only by accident: its first site was at roughly
                # zero elevation, so world zero and the ground were the same
                # place. On the plateau they are 10.20m apart, and the whole
                # neighbourhood rendered underneath its own road.
                authored_z = terrain_height(x, y)
            else:
                authored_z = 0
        empty.location = (x, y, authored_z)
    else:
        lx = x + (s - 1) * LOT / 2
        ly = y + (s - 1) * LOT / 2
        # Civic campuses sit slightly above meadow so pads stay readable.
        if b["type"] in ("followmart", "elementaryschool", "constructionzone",
                         "movietheater", "firestation"):
            lz = max(0.05, terrain_height(lx, ly))
        else:
            lz = 0
        empty.location = (lx, ly, lz)
    rng = random.Random(b["seed"])
    if b.get("rot") is not None:  # exact facing (ring houses face their park)
        empty.rotation_euler = (0, 0, b["rot"])
    elif b["type"] == "coffeetruck":
        # This lot's public street is on +Y. Rotate the authored -Y service
        # hatch toward it so customers order from the sidewalk side.
        empty.rotation_euler = (0, 0, math.pi)
    elif b["type"] in ("elementaryschool", "constructionzone", "movietheater",
                       "followmart", "firestation", "arcade"):
        # Campus assets are authored with main doors facing local -Y;
        # keep that deliberate frontage instead of lot-house rotation.
        empty.rotation_euler = (0, 0, 0)
    elif b.get("face"):  # explicit facing override stored in the state file
        empty.rotation_euler = (0, 0, {"s": 0.0, "e": math.pi / 2,
                                       "n": math.pi, "w": -math.pi / 2}[b["face"]])
    elif b["type"] in ("tree", "bush", "rock", "forestreserve"):
        empty.rotation_euler = (0, 0, rng.random() * math.tau)
    elif b["type"] not in ("park", "plaza", "stadium", "streetlight", "car",
                           "pond", "fishingpond", "duck", "parkdistrict"):
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
    """Grid asphalt for the flat downtown platform.

    Important: do NOT lift every road to max(terrain) across the whole map —
    that floats downtown streets above the sidewalks when hills exist at the
    map edge. Downtown grid roads live on the engineered flat platform (z≈0).
    Suburban roads already terrain-follow in build_suburban_roads.
    """
    min_bx, max_bx, min_by, max_by = block_extent(buildings)
    x0, x1 = min_bx * PITCH - ROAD, (max_bx + 1) * PITCH
    y0, y1 = min_by * PITCH - ROAD, (max_by + 1) * PITCH
    # Bottom of asphalt slightly above z=0 so it wins z-fighting with terrain
    # mesh without floating (sidewalks/hardscape are ~0.10–0.16 high).
    road_z = 0.02
    road_h = 0.14
    for bx in range(min_bx, max_bx + 2):
        x = bx * PITCH - ROAD / 2
        add_box(world_col, "roadV", ROAD, y1 - y0, road_h, x, (y0 + y1) / 2, road_z, m["road"])
    for by in range(min_by, max_by + 2):
        y = by * PITCH - ROAD / 2
        add_box(world_col, "roadH", x1 - x0, ROAD, road_h + 0.01, (x0 + x1) / 2, y, road_z, m["road"])
    # Parked cars belong along block faces, not scattered through junctions.
    # The dedicated public-realm pass owns all downtown streetlights.
    rng = random.Random(9000 + (max_bx - min_bx) * 31 + (max_by - min_by))
    for bx in range(min_bx, max_bx + 1):
        for by in range(min_by, max_by + 1):
            block_x, block_y = bx * PITCH, by * PITCH
            car_z = road_z + road_h + 0.02
            if rng.random() < 0.78:
                b = {"type": "car", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
                e = place_instance(world_col, b, "car")
                e.location = (block_x + LOT*(.65+rng.random()*1.7),
                              block_y - 1.15, car_z)
                e.rotation_euler = (0, 0, 0 if rng.random() < .5 else math.pi)
            if rng.random() < 0.48:
                b = {"type": "car", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
                e = place_instance(world_col, b, "car")
                e.location = (block_x - 1.15,
                              block_y + LOT*(.65+rng.random()*1.7), car_z)
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


def _polyline_height(points, distance):
    """Authored deck height at one distance along a 3D polyline.

    _polyline_sample answers where and which way; a road that ramps needs to
    know how high as well, or its markings stay pinned to the ground while the
    asphalt climbs away from them.
    """
    for a, b in zip(points, points[1:]):
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        if distance <= length:
            t = distance / max(length, .001)
            return a[2] + (b[2] - a[2]) * t
        distance -= length
    return points[-1][2]


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


def build_weather_station(col, seed):
    """Permanent First Alert Weather forecast center and Doppler tower."""
    _ = seed
    m = std_mats()
    navy = mat("FV_weather_navy", (.055, .105, .20), .72)
    navy_light = mat("FV_weather_navy_light", (.11, .23, .38), .64)
    coral = mat("FV_weather_alert_coral", (.91, .24, .18), .60)
    cream = mat("FV_weather_cream", (.92, .90, .82), .86)
    white = mat("FV_weather_white", (.97, .98, .96), .58)
    sign_white = mat("FV_weather_sign_white", (.99, .99, .97), .46)
    sign_bsdf = sign_white.node_tree.nodes.get("Principled BSDF")
    sign_emission = (sign_bsdf.inputs.get("Emission Color")
                     or sign_bsdf.inputs.get("Emission"))
    if sign_emission:
        sign_emission.default_value = (.82, .91, 1.0, 1.0)
    sign_strength = sign_bsdf.inputs.get("Emission Strength")
    if sign_strength:
        sign_strength.default_value = .32
    concrete = mat("FV_weather_concrete", (.44, .45, .43), .96)
    asphalt = m["road"]
    steel = mat("FV_weather_steel", (.28, .31, .34), .42, .62)
    glass = mat("FV_weather_glass", (.075, .22, .34), .12, .12, 1.0, 0.0, .66)
    screen = mat("FV_weather_screen", (.18, .55, .72), .38)
    yellow = mat("FV_weather_lightning", (.98, .73, .08), .55)
    lawn = mat("FV_weather_lawn", (.35, .59, .28), .98)
    logo = image_mat("FV_weather_profile_logo",
                     os.path.join("assets", "branding", "followville_faw.jpg"))

    cx, cy = WEATHER_STATION_CENTER
    half_x, half_y = WEATHER_STATION_HALF_EXTENTS
    base = weather_station_base_height()
    pad_top = base + .18

    # A real retained civic terrace, not a floating slab on the north meadow.
    # The lawn and retaining face contain a real driveway opening. A single
    # full-size slab left grass underneath the asphalt ramp, which showed
    # through the parking notch and made the entrance look pasted on.
    add_box(col, "weather_campus_lawn_rear", half_x * 2, 23.0, .18,
            0, 2.0, base, lawn)
    add_box(col, "weather_campus_lawn_front_west", 2.8, 4.0, .18,
            -14.1, -11.5, base, lawn)
    add_box(col, "weather_campus_lawn_front_east", 22.8, 4.0, .18,
            4.1, -11.5, base, lawn)
    _add_retaining_skirt(col, "weather_campus_retaining", half_x, half_y,
                         base, (cx, cy), concrete, bury=.62, step=.75,
                         front_gap=(-10.0, 5.4))
    for x in (-half_x + .22, half_x - .22):
        add_box(col, "weather_retaining_cap_side", .34, half_y * 2, .18,
                x, 0, pad_top - .01, cream)
    add_box(col, "weather_retaining_cap_end", half_x * 2 - .7, .34, .18,
            0, half_y - .22, pad_top - .01, cream)
    add_box(col, "weather_retaining_cap_front_west", 2.45, .34, .18,
            -13.925, -half_y + .22, pad_top - .01, cream)
    add_box(col, "weather_retaining_cap_front_east", 22.45, .34, .18,
            3.925, -half_y + .22, pad_top - .01, cream)

    # One continuous city-asphalt drive climbs from the existing north-grid
    # street. It flares at the curb, then lands in a matching notch cut into
    # the parking court, so no separate slab edge or material change is visible.
    access_world = weather_station_access_points()
    access_local = [(x - cx, y - cy, z) for x, y, z in access_world]
    access_widths = [5.4 + 1.8 * max(0.0, 1.0 - index / 2.0) ** 2
                     for index in range(len(access_local))]
    _add_road_strip(col, "weather_access_ramp", access_local, asphalt,
                    width=5.4, widths=access_widths,
                    bottom_offset=.015, top_offset=.08,
                    terrain_origin=(cx, cy))
    for index, (wx, wy, wz) in enumerate(access_world[2:-1:3]):
        ground = terrain_height(wx, wy) - .22
        if wz - ground > .35:
            add_ngon_cone(col, "weather_ramp_support", .16, .13,
                          wz - ground, 10, wx - cx, wy - cy, ground, concrete)

    # Parking/arrival court. Three pieces leave a genuine 5.4m opening for the
    # driveway instead of overlapping two coplanar asphalt faces. The rear
    # band closes the court at the driveway endpoint with shared height and
    # material, making the transition read as one poured/paved surface.
    add_box(col, "weather_parking_rear", 28.2, 3.15, .08, 0, -7.925,
            pad_top, asphalt)
    add_box(col, "weather_parking_front_west", 1.4, 3.25, .08, -13.4, -11.125,
            pad_top, asphalt)
    add_box(col, "weather_parking_front_east", 21.4, 3.25, .08, 3.4, -11.125,
            pad_top, asphalt)
    for x in (-7.3, -3.02, 1.26, 5.54, 9.82):
        add_box(col, "weather_parking_line", .10, 4.6, .025, x, -9.7,
                pad_top + .085, white)
    add_box(col, "weather_front_walk", 24.6, 2.25, .10, 0, -5.25,
            pad_top + .01, cream)
    for x in (-11.8, 11.8):
        add_ngon_cone(col, "weather_entry_bollard", .13, .10, .82, 10,
                      x, -6.25, pad_top + .10, navy)

    # Forecast center: a calm modern civic building with a taller operations wing.
    add_box(col, "weather_building_plinth", 24.8, 13.8, .62, 0, 1.7,
            pad_top, concrete)
    add_box(col, "weather_main_body", 23.8, 12.8, 6.0, 0, 1.7,
            pad_top + .62, cream)
    add_box(col, "weather_operations_wing", 7.4, 10.8, 8.5, 7.4, 2.35,
            pad_top + .62, navy_light)
    add_box(col, "weather_entry_volume", 5.0, 2.0, 4.4, .15, -5.35,
            pad_top + .62, navy)

    # Deep parapets, rain canopy, and layered bands give the station a finished silhouette.
    add_box(col, "weather_main_cornice", 24.5, 13.5, .36, 0, 1.7,
            pad_top + 6.62, navy)
    add_box(col, "weather_main_parapet", 23.9, .38, .72, 0, -4.52,
            pad_top + 6.90, navy)
    add_box(col, "weather_wing_cornice", 8.0, 11.4, .38, 7.4, 2.35,
            pad_top + 9.12, coral)
    add_box(col, "weather_entry_canopy", 6.5, 2.5, .30, .15, -6.72,
            pad_top + 4.72, coral)
    for x in (-2.35, 2.65):
        add_ngon_cone(col, "weather_canopy_column", .14, .14, 4.0, 10,
                      x, -7.45, pad_top + .18, steel)

    # Glazed public lobby, studio windows, mullions, sills, and entry hardware.
    add_box(col, "weather_entry_glass", 4.25, .16, 3.45, .15, -6.42,
            pad_top + 1.00, glass)
    add_box(col, "weather_entry_split", .12, .10, 3.42, .15, -6.56,
            pad_top + 1.02, cream)
    for x in (-.70, 1.0):
        add_box(col, "weather_door_handle", .08, .10, .76, x, -6.61,
                pad_top + 2.12, steel)
    for x in (-9.8, -6.75, -3.7, 4.8, 7.35, 9.9):
        add_box(col, "weather_window_frame", 2.45, .30, 2.45, x, -4.82,
                pad_top + 1.75, white)
        add_box(col, "weather_window_glass", 2.08, .12, 2.08, x, -4.99,
                pad_top + 1.93, glass)
        add_box(col, "weather_window_mullion", .10, .08, 2.08, x, -5.08,
                pad_top + 1.93, navy)
        add_box(col, "weather_window_sill", 2.62, .42, .16, x, -5.02,
                pad_top + 1.68, navy)
    for y in (-1.1, 2.0, 5.1):
        add_box(col, "weather_side_window", .12, 2.15, 2.05, 11.96, y,
                pad_top + 2.05, glass)

    # Exact public profile mark plus large geometry text that stays readable in renders.
    add_box(col, "weather_logo_frame", 3.7, .28, 3.7, -8.65, -5.04,
            pad_top + 4.42, white)
    add_image_panel(col, "weather_profile_logo", 3.35, 3.35,
                    -8.65, -5.22, pad_top + 4.60, logo)
    add_box(col, "weather_brand_board", 11.9, .30, 2.75, -1.3, -5.02,
            pad_top + 7.05, navy)
    add_box(col, "weather_brand_alert_bar", 11.3, .10, .42, -1.3, -5.22,
            pad_top + 8.96, coral)
    add_text(col, "weather_brand_first_alert", "FIRST ALERT", .72, .055,
             -1.3, -5.22, pad_top + 8.50, sign_white)
    add_text(col, "weather_brand_weather", "WEATHER", .82, .055,
             -1.3, -5.22, pad_top + 7.58, sign_white)

    # Doppler lattice: four tapered legs, diagonal bracing, service deck and radome.
    tower_x, tower_y = 7.4, 3.6
    tower_bottom, tower_top = pad_top + 9.42, pad_top + 18.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            add_beam_between(col, "weather_tower_leg",
                             (tower_x + sx * 1.65, tower_y + sy * 1.65, tower_bottom),
                             (tower_x + sx * .92, tower_y + sy * .92, tower_top),
                             .20, steel)
    for level in range(4):
        z0 = tower_bottom + level * 2.05
        z1 = min(tower_top, z0 + 2.05)
        spread0 = 1.65 - level * .18
        spread1 = max(.92, spread0 - .18)
        for sy in (-1, 1):
            add_beam_between(col, "weather_tower_brace",
                             (tower_x - spread0, tower_y + sy * spread0, z0),
                             (tower_x + spread1, tower_y + sy * spread1, z1),
                             .09, coral)
            add_beam_between(col, "weather_tower_brace",
                             (tower_x + spread0, tower_y + sy * spread0, z0),
                             (tower_x - spread1, tower_y + sy * spread1, z1),
                             .09, coral)
    add_box(col, "weather_radar_platform", 3.2, 3.2, .28, tower_x, tower_y,
            tower_top, steel)
    for sx in (-1.42, 1.42):
        for sy in (-1.42, 1.42):
            add_ngon_cone(col, "weather_platform_rail_post", .055, .055,
                          1.0, 8, tower_x + sx, tower_y + sy,
                          tower_top + .28, steel)
    add_ngon_cone(col, "weather_radome_base", 2.15, 2.15, .72, 20,
                  tower_x, tower_y, tower_top + .28, navy)
    add_uv_sphere(col, "weather_doppler_radome", 2.55, tower_x, tower_y,
                  tower_top + 3.20, white, rings=10, segments=20)
    add_ngon_cone(col, "weather_beacon_mast", .09, .065, 1.35, 10,
                  tower_x, tower_y, tower_top + 5.55, steel)
    add_uv_sphere(col, "weather_beacon", .22, tower_x, tower_y,
                  tower_top + 6.95, coral, rings=6, segments=10)

    # Secondary instruments make the roof read as a working weather station.
    mast_x, mast_y = -7.1, 3.0
    add_ngon_cone(col, "weather_instrument_mast", .09, .07, 4.3, 10,
                  mast_x, mast_y, pad_top + 7.0, steel)
    add_beam_between(col, "weather_anemometer_bar",
                     (mast_x - 1.15, mast_y, pad_top + 10.92),
                     (mast_x + 1.15, mast_y, pad_top + 10.92), .07, steel)
    for dx, dy in ((-1.15, .0), (1.15, .0), (0, 1.15)):
        add_ngon_cone(col, "weather_anemometer_cup", .24, .16, .34, 10,
                      mast_x + dx, mast_y + dy, pad_top + 10.78, navy)
    add_beam_between(col, "weather_wind_vane",
                     (mast_x, mast_y - .85, pad_top + 10.35),
                     (mast_x, mast_y + 1.2, pad_top + 10.35), .08, steel)
    vane = add_box(col, "weather_wind_vane_tail", .82, .08, .48,
                   mast_x, mast_y - 1.15, pad_top + 10.12, coral)
    vane.rotation_euler.z = math.radians(15)

    # Forecast display, rain gauge, planters and monument sign finish the campus.
    add_box(col, "weather_forecast_display_frame", 4.3, .24, 2.5,
            7.4, -3.38, pad_top + 5.45, white)
    add_box(col, "weather_forecast_display", 3.85, .10, 2.06,
            7.4, -3.54, pad_top + 5.68, screen)
    for x, height in ((6.25, .55), (7.05, 1.05), (7.85, .78), (8.65, 1.38)):
        add_box(col, "weather_radar_bar", .42, .055, height, x, -3.62,
                pad_top + 5.94, yellow if x > 7.5 else coral)
    add_ngon_cone(col, "weather_rain_gauge", .23, .32, 1.35, 12,
                  -11.5, 6.6, pad_top + .20, glass)
    for x in (-12.8, 12.8):
        add_ngon_cone(col, "weather_planter", .62, .52, .68, 12,
                      x, -5.75, pad_top + .10, navy)
        add_uv_sphere(col, "weather_planter_shrub", .72, x, -5.75,
                      pad_top + 1.02, lawn, rings=6, segments=10)
    add_box(col, "weather_monument_base", 5.6, 1.25, .48, 10.0, -11.4,
            pad_top + .08, concrete)
    add_box(col, "weather_monument", 5.0, .62, 2.65, 10.0, -11.4,
            pad_top + .52, navy)
    add_image_panel(col, "weather_monument_logo", 2.15, 2.15,
                    8.55, -11.74, pad_top + .76, logo)
    add_text(col, "weather_monument_text", "FIRST ALERT", .38, .04,
             11.15, -11.76, pad_top + 2.42, sign_white)
    add_text(col, "weather_monument_handle", "@FOLLOWVILLE_FAW", .22, .04,
             11.15, -11.76, pad_top + 1.64, sign_white)



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


def build_point_road(world_col, buildings, m):
    """Point Road and the station's dirt access trail.

    Two roads, deliberately of different kinds, because that is what Cade
    asked for and what a plant this size actually gets:

    Point Road is proper asphalt with a shoulder and centre dashes. It leaves
    Ferry Street where that street is still running -- not at its cul-de-sac
    bulb, where a junction would read as an afterthought -- and carries on
    NORTH PAST the plant to a river overlook. That is what stops it being a
    private driveway: it is a road to somewhere, and the station happens to sit
    on it.

    Station Trail is dirt: no dashes, no shoulder, a narrower and rougher
    surface, running the last thirty metres from Point Road to the gate.

    Both centrelines live in world_layout, because the browser's walk surface
    and check_world_geometry need the same line and copies drift.
    """
    if not any(b.get("type") == "nuclearplant" for b in buildings):
        return []
    from world_layout import (point_road_points, station_trail_points,
                              NUCLEAR_ROAD_HALF_WIDTH,
                              NUCLEAR_TRAIL_HALF_WIDTH)

    shoulder_mat = mat("FV_point_road_shoulder", (.24, .27, .25), .99)
    lane_mat = mat("FV_point_road_marking", (.61, .60, .47), 1.0)
    dirt_mat = mat("FV_station_trail_dirt", (.44, .38, .30), 1.0)
    dirt_edge = mat("FV_station_trail_edge", (.35, .32, .26), 1.0)

    made = []
    road = [(x, y, terrain_height(x, y)) for x, y in point_road_points()]
    # Distinct layer tops, as everywhere else: shoulder .045, deck .085,
    # dashes .095, so no two surfaces land on one plane.
    made.append(_add_road_strip(world_col, "point_road_shoulder", road,
                                shoulder_mat,
                                width=NUCLEAR_ROAD_HALF_WIDTH * 2 + 2.2,
                                bottom_offset=.005, top_offset=.045,
                                terrain_conform=True))
    made.append(_add_road_strip(world_col, "point_road", road, m["road"],
                                width=NUCLEAR_ROAD_HALF_WIDTH * 2,
                                bottom_offset=.015, top_offset=.085,
                                terrain_conform=True))
    for index in range(0, len(road) - 3, 4):
        made.append(_add_road_strip(world_col, "point_road_dash",
                                    road[index:index + 2], lane_mat,
                                    width=.22, bottom_offset=.02,
                                    top_offset=.095, terrain_conform=True))

    trail = [(x, y, terrain_height(x, y)) for x, y in station_trail_points()]
    # The trail gets an edge band instead of a shoulder and no markings at
    # all -- a dirt track with a painted centre line would not be a dirt track.
    made.append(_add_road_strip(world_col, "station_trail_edge", trail,
                                dirt_edge,
                                width=NUCLEAR_TRAIL_HALF_WIDTH * 2 + 1.4,
                                bottom_offset=.004, top_offset=.035,
                                terrain_conform=True))
    made.append(_add_road_strip(world_col, "station_trail", trail, dirt_mat,
                                width=NUCLEAR_TRAIL_HALF_WIDTH * 2,
                                bottom_offset=.012, top_offset=.065,
                                terrain_conform=True))
    return made


def build_northgate_arterial(world_col, buildings, m):
    """The road from downtown up to the chapter-three quarter.

    Cade's requirement was that the new quarter be connected by road to
    downtown. This is that road: it leaves the downtown grid at the crossroads
    of the x=-93 and y=87 streets, runs 220m north up the open gap between
    Creekside Bend and Willow Hills, and lands on the Northgate Avenue
    centreline. Both ends are real junctions on roads that already exist, not
    stubs in a meadow.

    The centreline itself lives in neighborhood_plan, because build_plan() has
    to keep reserved addresses off it and the browser's walk surface and
    check_world_geometry both need the same line. There are no copies to drift.

    Not to be confused with the reverted 2026-08-09 east-west highway along
    y=272: that line was cleared against the reserve's RAW coordinates, where
    Pebble Court's houses look 58m further south than they actually stand, and
    it ran through Willow Hills and Creekside Bend.
    """
    active = max((b.get("plan_id", 0) for b in buildings), default=0)
    if active < NORTHGATE_ARTERIAL_REVEAL:
        return []
    shoulder_mat = mat("FV_suburban_road_shoulder", (.24, .27, .25), .99)
    lane_mat = mat("FV_suburban_lane_marking", (.61, .60, .47), 1.0)
    path_mat = mat("FV_suburban_walking_path", (.52, .49, .42), .99)

    flat = northgate_arterial_points()
    points = [(x, y, terrain_height(x, y)) for x, y in flat]
    made = []
    # Layer tops are all distinct and no two side walls overlap: shoulder .045,
    # footway .035 outside the shoulder's edge, deck .085, dashes .095.
    made.append(_add_road_strip(world_col, "northgate_arterial_shoulder", points,
                                shoulder_mat, width=ARTERIAL_HALF_WIDTH * 2.4,
                                bottom_offset=.005, top_offset=.045,
                                terrain_conform=True))
    made.append(_add_road_strip(world_col, "northgate_arterial", points,
                                m["road"], width=ARTERIAL_HALF_WIDTH * 2.0,
                                bottom_offset=.015, top_offset=.085,
                                terrain_conform=True))
    for side in (-1, 1):
        # 5.5m out clears the 4.8m shoulder edge, so the two hardscape layers
        # never share a vertical face.
        made.append(_add_road_strip(
            world_col, "northgate_arterial_path%d" % side,
            _offset_terrain_path(points, side * 5.5), path_mat, width=1.25,
            bottom_offset=.005, top_offset=.035, terrain_conform=True))

    total = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                for a, b in zip(points, points[1:]))
    distance = 6.0
    while distance < total - 3.0:
        x, y, angle = _polyline_sample(points, distance)
        dash = add_box(world_col, "northgate_arterial_dash", 2.2, .18, .018,
                       x, y, terrain_height(x, y) + .095, lane_mat)
        dash.rotation_euler.z = angle
        made.append(dash)
        distance += 11.0

    # Covers at both ends, so the arterial reads as joined to the grid road it
    # leaves and the avenue it arrives on rather than as a ribbon laid beside
    # them. Same radii and lifts as every other junction in the town.
    junctions = [flat[0], flat[-1]]
    _add_terrain_disc_batch(world_col, "northgate_arterial_junction_shoulders",
                            junctions, 4.55, .052, shoulder_mat, 20)
    _add_terrain_disc_batch(world_col, "northgate_arterial_junction_surfaces",
                            junctions, 3.95, .095, m["road"], 20)
    return [obj for obj in made if obj is not None]


def build_suburban_roads(world_col, buildings, m):
    """Reveal only the road pieces needed by houses already constructed."""
    if not SUBURBAN_PLAN:
        return []
    active = max([b.get("plan_id", 0) for b in buildings] or [0])
    if not active:
        return []
    river_reveal_objects = []
    river_districts = {
        house["district"] for house in SUBURBAN_PLAN["houses"]
        if int(house.get("plan_id", 0)) > 366
    }
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
        # Continuous ribbons seal their own bends. Covers belong only where a
        # connector actually meets another road; putting one at every control
        # point produced the repeated raised circles that read as overlapping
        # cul-de-sacs in low-angle Blender footage.
        junction_points.extend(((points[0][0], points[0][1]),
                                (points[-1][0], points[-1][1])))
        connector_shoulder = _add_road_strip(
            world_col, "district_connector_shoulder_" + district.lower().replace(" ", "_"),
            points, shoulder_mat, width=7.35, bottom_offset=.005,
            top_offset=.045, terrain_conform=True)
        connector_road = _add_road_strip(
            world_col, "district_connector_" + district.lower().replace(" ", "_"),
            points, m["road"], bottom_offset=.015,
            top_offset=.085, terrain_conform=True)
        if district in river_districts:
            river_reveal_objects.extend((connector_shoulder, connector_road))
        for side in (-1, 1):
            path = _offset_terrain_path(points, side*4.45)
            connector_path = _add_road_strip(
                world_col, "district_path_" + district.lower().replace(" ", "_") + str(side),
                path, path_mat, width=1.25, bottom_offset=.005,
                top_offset=.035, terrain_conform=True)
            if district in river_districts:
                river_reveal_objects.append(connector_path)
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
        # The continuous shared-vertex ribbon already seals every bend. One
        # cover at the true street junction is enough for every generation of
        # the reserve; the final turnaround is authored separately below.
        junction_points.append(flat_points[0])
        street_objects = []
        street_objects.append(_add_road_strip(
            world_col, "suburban_shoulder_%02d" % street_index, points,
            shoulder_mat, width=7.35, bottom_offset=.005,
            top_offset=.045, terrain_conform=True))
        street_objects.append(_add_road_strip(
            world_col, "suburban_road_%02d" % street_index, points,
            m["road"], bottom_offset=.015,
            top_offset=.085, terrain_conform=True))
        path = _offset_terrain_path(points, 4.35 if street_index%2==0 else -4.35)
        street_objects.append(_add_road_strip(
            world_col, "suburban_path_%02d" % street_index, path,
            path_mat, width=1.18, bottom_offset=.005,
            top_offset=.035, terrain_conform=True))
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
            street_objects.append(dash)
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
            street_objects.append(lamp)
            light_distance += 34.0
            light_index += 1
        # Tag every piece with the street it belongs to. Dashes and lamps all
        # share one name, so a reveal that filtered by name would leave a
        # street's centre-line dashes floating over bare meadow -- and
        # animating a road that was already standing HIDES it, which is the
        # trap the Day 38 tour records.
        for obj in street_objects:
            if obj is not None:
                obj["nb_street_index"] = street_index
        if street_index >= 18:
            river_reveal_objects.extend(street_objects)
    if any(b.get("type") == "northcrowncampus" for b in buildings):
        # A real, terrain-following connection from Ember Ridge street 72 to
        # the gated campus.  Keeping it outside the merged landmark asset
        # makes it part of the same audited and walkable road system as every
        # residential street in the website export.
        access_points = [(x, y, terrain_height(x, y))
                         for x, y in NORTH_CROWN_CAMPUS_ACCESS]
        access_objects = [
            _add_road_strip(world_col, "north_crown_access_shoulder",
                            access_points, shoulder_mat, width=8.1,
                            bottom_offset=.005, top_offset=.045,
                            terrain_conform=True),
            _add_road_strip(world_col, "north_crown_access_road",
                            access_points, m["road"], width=6.5,
                            bottom_offset=.015, top_offset=.085,
                            terrain_conform=True),
        ]
        for side in (-1, 1):
            access_objects.append(_add_road_strip(
                world_col, "north_crown_access_path_%s" % side,
                _offset_terrain_path(access_points, side * 4.65), path_mat,
                width=1.35, bottom_offset=.005, top_offset=.035,
                terrain_conform=True))
        total = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                    for a, b in zip(access_points, access_points[1:]))
        distance = 6.0
        while distance < total - 3.0:
            x, y, angle = _polyline_sample(access_points, distance)
            dash = add_box(world_col, "north_crown_access_dash",
                           1.75, .17, .018, x, y,
                           terrain_height(x, y) + .095, lane_mat)
            dash.rotation_euler.z = angle
            access_objects.append(dash)
            distance += 10.0
        for obj in access_objects:
            if obj is not None:
                obj["nb_north_crown_access"] = True
        junction_points.extend((NORTH_CROWN_CAMPUS_ACCESS[0],
                                NORTH_CROWN_CAMPUS_ACCESS[-1]))
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
            if int(bulb.get("street_index", -1)) >= 18:
                river_reveal_objects.append(bulb_obj)
    return [obj for obj in river_reveal_objects if obj is not None]


def _metro_add_chair(col, created, name, x, y, z, angle, seat_mat, metal):
    """A compact slatted café chair with a readable seat, legs and back."""
    ca, sa = math.cos(angle), math.sin(angle)

    def point(dx, dy):
        return x + dx*ca-dy*sa, y + dx*sa+dy*ca

    seat = add_box(col, name+"_seat", .72, .72, .12, x, y, z+.48, seat_mat)
    seat.rotation_euler.z = angle
    created.append(seat)
    for dx in (-.27, .27):
        for dy in (-.27, .27):
            lx, ly = point(dx, dy)
            created.append(add_box(col, name+"_leg", .09, .09, .48,
                                   lx, ly, z, metal))
    for dx in (-.28, .28):
        bx, by = point(dx, .31)
        created.append(add_box(col, name+"_back_post", .08, .08, .72,
                               bx, by, z+.50, metal))
    back = add_box(col, name+"_back", .66, .09, .38,
                   *point(0, .33), z+.80, seat_mat)
    back.rotation_euler.z = angle
    created.append(back)


def _metro_add_cafe_set(col, created, x, y, z, accent, timber, metal):
    """Street café ensemble detailed enough to survive close screenshots."""
    stem = add_ngon_cone(col, "metro_cafe_table_stem", .11, .11, .71, 10,
                         x, y, z, metal)
    foot = add_ngon_cone(col, "metro_cafe_table_foot", .34, .28, .08, 12,
                         x, y, z, metal)
    top = add_ngon_cone(col, "metro_cafe_table_top", .86, .86, .10, 16,
                        x, y, z+.71, timber)
    rim = add_torus(col, "metro_cafe_table_rim", .79, .035,
                    x, y, z+.82, metal, 16, 5)
    created.extend((stem, foot, top, rim))
    for cx, cy, angle in ((x-1.18, y, -math.pi/2),
                          (x+1.18, y, math.pi/2),
                          (x, y+1.18, math.pi)):
        _metro_add_chair(col, created, "metro_cafe_chair", cx, cy, z,
                         angle, accent, metal)


def _metro_add_planter(col, created, x, y, z, planter_mat, earth_mat,
                       leaf_a, leaf_b, flower_mat):
    """Layered planter with soil, varied foliage and small flowering accents."""
    planter = add_box(col, "metro_corner_planter", 2.9, 1.35, .58,
                      x, y, z, planter_mat)
    soil = add_box(col, "metro_planter_soil", 2.58, 1.05, .08,
                   x, y, z+.59, earth_mat)
    created.extend((planter, soil))
    foliage = ((-.88, -.18, .47), (-.34, .20, .58), (.25, -.18, .54),
               (.82, .16, .43), (.02, .22, .40))
    for index, (dx, dy, radius) in enumerate(foliage):
        shrub = add_uv_sphere(col, "metro_planter_foliage", radius,
                              x+dx, y+dy, z+.64+radius*.72,
                              leaf_a if index % 2 else leaf_b, 7, 10)
        shrub.scale.z = .82 + .12*(index % 3)
        created.append(shrub)
    for index, dx in enumerate((-.68, -.12, .52)):
        stem = add_ngon_cone(col, "metro_flower_stem", .018, .014, .40, 6,
                             x+dx, y-.34+(index % 2)*.55, z+.64, leaf_a)
        flower = add_uv_sphere(col, "metro_planter_flower", .09,
                               x+dx, y-.34+(index % 2)*.55, z+1.07,
                               flower_mat, 5, 8)
        created.extend((stem, flower))


def _metro_add_bicycle(col, created, x, y, z, frame_mat, metal, rubber):
    """Complete upright bicycle: two tires, hubs, frame, fork, bars and seat."""
    rear = Vector((x, y-.67, z+.47))
    front = Vector((x, y+.67, z+.47))
    crank = Vector((x, y-.04, z+.48))
    saddle_joint = Vector((x, y-.31, z+1.08))
    head = Vector((x, y+.43, z+1.06))
    for center in (rear, front):
        created.append(add_torus(col, "metro_bicycle_tire", .43, .052,
                                 center.x, center.y, center.z, rubber,
                                 18, 6, (0, math.pi/2, 0)))
        created.append(add_beam_between(
            col, "metro_bicycle_hub",
            (center.x-.07, center.y, center.z),
            (center.x+.07, center.y, center.z), .075, metal))
    for start, end in ((rear, crank), (crank, saddle_joint),
                       (saddle_joint, rear), (saddle_joint, head),
                       (head, crank), (head, front)):
        created.append(add_beam_between(col, "metro_bicycle_frame",
                                        start, end, .065, frame_mat))
    seat = add_box(col, "metro_bicycle_saddle", .15, .40, .08,
                   x, y-.36, z+1.10, rubber)
    bar = add_box(col, "metro_bicycle_handlebar", .56, .08, .08,
                  x, y+.48, z+1.17, metal)
    pedal = add_box(col, "metro_bicycle_pedal", .42, .07, .07,
                    x, y-.04, z+.48, metal)
    created.extend((seat, bar, pedal))


def build_metropolitan_district(world_col, buildings, m):
    """Build Crown Quarter infrastructure after its first tower is earned."""
    active = max((int(b.get("metro_id", 0)) for b in buildings), default=0)
    if active < 1:
        return []

    created = []
    asphalt = m["road"]
    concrete = mat("FV_metro_sidewalk", (.56, .55, .51), .96)
    curb = mat("FV_metro_curb", (.38, .39, .38), .98)
    paver = mat("FV_metro_paver", (.63, .54, .47), .94)
    marking = mat("FV_metro_marking", (.91, .87, .66), .82)
    white = mat("FV_metro_crosswalk", (.84, .84, .80), .88)
    metal = mat("FV_metro_street_metal", (.20, .24, .25), .72, metallic=.18)
    shelter_glass = mat("FV_metro_shelter_glass", (.43, .65, .70), .24,
                        alpha=.62, transmission=.12, coat=.12)
    timber = mat("FV_metro_bench", (.48, .29, .16), .90)
    green = mat("FV_metro_green", (.30, .55, .31), .98)
    lawn = mat("FV_metro_interim_lawn", (.39, .61, .34), 1.0)
    earth = mat("FV_metro_construction_earth", (.56, .45, .31), 1.0)
    safety = mat("FV_metro_construction_safety", (.94, .49, .12), .76)
    highway_concrete = mat("FV_expressway_concrete", (.42, .43, .42), .97)
    highway_rail = mat("FV_expressway_rail", (.22, .25, .25), .78, metallic=.18)
    sign_green = mat("FV_expressway_sign", (.08, .30, .22), .76)
    warm_light = mat("FV_expressway_light_warm", (.96, .73, .38), .42,
                     metallic=.04)
    cafe_red = mat("FV_metro_cafe_red", (.76, .20, .17), .74)
    cafe_gold = mat("FV_metro_cafe_gold", (.94, .63, .16), .76)
    civic_blue = mat("FV_metro_civic_blue", (.16, .43, .61), .70)
    utility_green = mat("FV_metro_utility_green", (.20, .39, .30), .88)
    rubber = mat("FV_metro_rubber", (.075, .085, .09), .94)
    cardboard = mat("FV_metro_cardboard", (.61, .42, .24), .94)
    leaf_dark = mat("FV_metro_leaf_dark", (.10, .31, .16), .92)
    leaf_light = mat("FV_metro_leaf_light", (.30, .58, .27), .90)
    flower = mat("FV_metro_flower", (.94, .34, .31), .74)
    storefront = mat("FV_metro_storefront_glass", (.18, .37, .43), .20,
                     alpha=.78, transmission=.08, coat=.18)
    steel_light = mat("FV_metro_brushed_steel", (.48, .52, .52), .52,
                      metallic=.30)
    bus_white = mat("FV_metro_bus_white", (.78, .82, .80), .72)
    lamp_glow = mat("FV_metro_shop_light", (1.0, .72, .30), .34,
                    metallic=.03)

    # Streets continue the inherited coordinates from Northgate/Southline.
    for index, street in enumerate(METRO_STREETS):
        points = [(x, y, METRO_TERRACE_DATUM) for x, y in street["points"]]
        road = _add_road_strip(world_col, "metro_road_%02d" % index, points,
                               asphalt, width=street["width"],
                               bottom_offset=.02, top_offset=.19)
        road["nb_feature_role"] = "metro-road"
        created.append(road)
        # Lane discipline: local center line, or four-lane boulevard divider.
        (x0, y0), (x1, y1) = street["points"]
        length = math.hypot(x1-x0, y1-y0)
        angle = math.atan2(y1-y0, x1-x0)
        if street["kind"] == "boulevard":
            offsets = (-3.45, 0.0, 3.45)
        else:
            offsets = (0.0,)
        nx, ny = -math.sin(angle), math.cos(angle)
        for line_index, offset in enumerate(offsets):
            line = add_box(world_col, "metro_lane_line", length-4.0, .13, .025,
                           (x0+x1)/2 + nx*offset, (y0+y1)/2 + ny*offset,
                           METRO_TERRACE_DATUM+.195, marking)
            line.rotation_euler.z = angle
            created.append(line)

    # Sidewalks and kerbs belong to block edges, so they stop at junctions
    # rather than running visibly across the roadway.
    for row in range(4):
        y0, y1 = METRO_EW_Y[row], METRO_EW_Y[row+1]
        south_half = 7.0 if y0 in (588.0, METRO_INTERCHANGE_Y) else 4.0
        north_half = 7.0 if y1 in (588.0, METRO_INTERCHANGE_Y) else 4.0
        for column in range(5):
            x0, x1 = METRO_NS_X[column], METRO_NS_X[column+1]
            inner_x0, inner_x1 = x0+4.0, x1-4.0
            inner_y0, inner_y1 = y0+south_half, y1-north_half
            block_w = inner_x1-inner_x0
            block_d = inner_y1-inner_y0
            for name, x, y, w, d in (
                ("south", (inner_x0+inner_x1)/2, inner_y0+1.6, block_w, 3.2),
                ("north", (inner_x0+inner_x1)/2, inner_y1-1.6, block_w, 3.2),
                ("west", inner_x0+1.6, (inner_y0+inner_y1)/2,
                 3.2, max(.2, block_d-6.4)),
                ("east", inner_x1-1.6, (inner_y0+inner_y1)/2,
                 3.2, max(.2, block_d-6.4)),
            ):
                walk = add_box(world_col, "metro_sidewalk_"+name, w, d, .16,
                               x, y, METRO_TERRACE_DATUM+.12, concrete)
                created.append(walk)
            for name, x, y, w, d in (
                ("south", (inner_x0+inner_x1)/2, inner_y0+.18, block_w, .36),
                ("north", (inner_x0+inner_x1)/2, inner_y1-.18, block_w, .36),
                ("west", inner_x0+.18, (inner_y0+inner_y1)/2,
                 .36, max(.2, block_d-.72)),
                ("east", inner_x1-.18, (inner_y0+inner_y1)/2,
                 .36, max(.2, block_d-.72)),
            ):
                edge = add_box(world_col, "metro_curb_"+name, w, d, .27,
                               x, y, METRO_TERRACE_DATUM+.11, curb)
                created.append(edge)

            slot = METRO_TOWER_PLAN[row*5+column]
            if int(slot["metro_id"]) <= active:
                # A warm paved forecourt makes each earned tower meet its sidewalk.
                forecourt = add_box(world_col, "metro_forecourt", 42.0, 43.0, .07,
                                    slot["x"], slot["y"],
                                    METRO_TERRACE_DATUM+.055, paver)
                created.append(forecourt)

                # The tower itself occupies the middle of the parcel; the side
                # strips are where downtown life accumulates.  West is a café
                # terrace, south is the front door, and east is the working
                # service edge.  Keeping those roles consistent makes all 20
                # blocks feel planned without cloning one identical plaza.
                sx, sy = slot["x"], slot["y"]
                metro_id = int(slot["metro_id"])
                for bollard_x in (-7.0, -3.5, 3.5, 7.0):
                    bollard = add_ngon_cone(
                        world_col, "metro_entry_bollard", .16, .13, .82, 8,
                        sx+bollard_x, sy-22.2, METRO_TERRACE_DATUM+.17, metal)
                    created.append(bollard)
                # Sidewalk extensions make the café and service functions read
                # as purpose-built public realm instead of props dropped on grass.
                cafe_pad = add_box(world_col, "metro_cafe_paving", 6.4, 38.0,
                                   .08, sx-24.0, sy,
                                   METRO_TERRACE_DATUM+.07, paver)
                service_pad = add_box(world_col, "metro_service_paving", 6.4,
                                      38.0, .08, sx+24.0, sy,
                                      METRO_TERRACE_DATUM+.07, asphalt)
                created.extend((cafe_pad, service_pad))

                # Glazed shopfront bays, mullions and shallow awnings animate
                # the tower podium where the first close render looked blank.
                for shop_index, shop_y in enumerate((-10.5, -3.5, 3.5, 10.5)):
                    glass = add_box(world_col, "metro_shopfront_glass", .13,
                                    5.3, 2.45, sx-19.18, sy+shop_y,
                                    METRO_TERRACE_DATUM+.42, storefront)
                    mullion = add_box(world_col, "metro_shopfront_mullion",
                                      .18, .10, 2.54, sx-19.26, sy+shop_y,
                                      METRO_TERRACE_DATUM+.39, steel_light)
                    awning = add_box(world_col, "metro_shopfront_awning", 1.25,
                                     5.65, .16, sx-19.80, sy+shop_y,
                                     METRO_TERRACE_DATUM+2.90,
                                     cafe_red if (metro_id+shop_index)%2 else cafe_gold)
                    created.extend((glass, mullion, awning))
                for table_index, table_y in enumerate((-7.2, 5.8)):
                    _metro_add_cafe_set(
                        world_col, created, sx-23.7, sy+table_y,
                        METRO_TERRACE_DATUM+.17,
                        cafe_red if (metro_id+table_index)%2 else cafe_gold,
                        timber, steel_light)
                pole = add_ngon_cone(world_col, "metro_cafe_umbrella_pole",
                                     .07, .07, 2.55, 10, sx-23.7, sy+5.8,
                                     METRO_TERRACE_DATUM+.17, steel_light)
                canopy = add_ngon_cone(world_col, "metro_cafe_umbrella", 2.25,
                                       .16, .54, 14, sx-23.7, sy+5.8,
                                       METRO_TERRACE_DATUM+2.47,
                                       cafe_red if metro_id%2 else civic_blue,
                                       rot=math.pi/14)
                finial = add_uv_sphere(world_col, "metro_umbrella_finial", .10,
                                        sx-23.7, sy+5.8,
                                        METRO_TERRACE_DATUM+3.05,
                                        cafe_gold, 6, 10)
                created.extend((pole, canopy, finial))

                # Bicycle parking faces the lobby and doubles as a protective
                # buffer between pedestrians and the service side of the lot.
                for rack_index in range(3):
                    rack_y = sy-14.0+rack_index*3.8
                    for post_y in (-.55, .55):
                        post = add_box(world_col, "metro_bike_rack_post",
                                       .13, .13, .82, sx+23.8,
                                       rack_y+post_y,
                                       METRO_TERRACE_DATUM+.17, metal)
                        created.append(post)
                    rail = add_box(world_col, "metro_bike_rack_rail", .13,
                                   1.23, .13, sx+23.8, rack_y,
                                   METRO_TERRACE_DATUM+.90, metal)
                    created.append(rail)
                bike_color = cafe_red if metro_id % 2 else cafe_gold
                _metro_add_bicycle(world_col, created, sx+23.55, sy-13.8,
                                   METRO_TERRACE_DATUM+.17,
                                   bike_color, steel_light, rubber)
                if metro_id % 3 == 0:
                    _metro_add_bicycle(world_col, created, sx+23.35, sy-6.2,
                                       METRO_TERRACE_DATUM+.17,
                                       civic_blue, steel_light, rubber)

                # A real downtown also needs an unglamorous back-of-house.
                dumpster = add_box(world_col, "metro_dumpster", 2.8, 1.55,
                                   1.35, sx+24.0, sy+13.5,
                                   METRO_TERRACE_DATUM+.17, utility_green)
                lid = add_box(world_col, "metro_dumpster_lid", 2.9, 1.65,
                              .15, sx+24.0, sy+13.5,
                              METRO_TERRACE_DATUM+1.54, rubber)
                utility = add_box(world_col, "metro_utility_box", 1.25, .72,
                                  1.35, sx+24.5, sy+18.0,
                                  METRO_TERRACE_DATUM+.17, metal)
                created.extend((dumpster, lid, utility))
                for rib_x in (-1.02, -.34, .34, 1.02):
                    rib = add_box(world_col, "metro_dumpster_rib", .09, 1.61,
                                  1.08, sx+24.0+rib_x, sy+13.5,
                                  METRO_TERRACE_DATUM+.29, steel_light)
                    created.append(rib)
                for caster_x in (-1.0, 1.0):
                    caster = add_uv_sphere(world_col, "metro_dumpster_caster",
                                           .16, sx+24.0+caster_x, sy+13.5,
                                           METRO_TERRACE_DATUM+.22, rubber, 6, 10)
                    created.append(caster)
                for crate_index in range(2+(metro_id % 2)):
                    crate = add_box(world_col, "metro_delivery_crate", .82,
                                    .72, .55, sx+21.8+crate_index*.9,
                                    sy+16.2, METRO_TERRACE_DATUM+.17,
                                    cardboard)
                    created.append(crate)
                # Loading hatch, drain and yellow clearance bars supply the
                # little functional details that make a service lane believable.
                hatch = add_box(world_col, "metro_service_hatch", .12, 4.4,
                                2.7, sx+19.20, sy+15.6,
                                METRO_TERRACE_DATUM+.30, metal)
                hatch_frame = add_box(world_col, "metro_service_hatch_frame",
                                      .16, 4.75, .16, sx+19.10, sy+15.6,
                                      METRO_TERRACE_DATUM+3.02, cafe_gold)
                drain = add_box(world_col, "metro_service_drain", 1.1, 2.7,
                                .035, sx+24.0, sy+7.8,
                                METRO_TERRACE_DATUM+.165, steel_light)
                created.extend((hatch, hatch_frame, drain))
                for stripe_y in (-.8, -.27, .27, .8):
                    stripe = add_box(world_col, "metro_drain_slot", .72, .08,
                                     .025, sx+24.0, sy+7.8+stripe_y,
                                     METRO_TERRACE_DATUM+.202, rubber)
                    created.append(stripe)
                for guard_y in (11.9, 15.2):
                    guard = add_ngon_cone(world_col, "metro_service_guard",
                                          .11, .11, .88, 8, sx+21.0,
                                          sy+guard_y,
                                          METRO_TERRACE_DATUM+.17, cafe_gold)
                    created.append(guard)

                # Small repeated signals of care at corners: planters, a
                # hydrant and newspaper/parcel boxes.  Positions alternate so
                # an aerial view does not read as a copy-pasted prop grid.
                for planter_index, (px, py) in enumerate(
                        ((sx-24.0, sy-17.0), (sx+24.0, sy+21.0))):
                    _metro_add_planter(world_col, created, px, py,
                                       METRO_TERRACE_DATUM+.17, curb, earth,
                                       leaf_dark, leaf_light,
                                       flower if planter_index == 0 else cafe_gold)
                hydrant = add_ngon_cone(world_col, "metro_fire_hydrant", .25,
                                        .19, .78, 8, sx+26.0, sy-22.5,
                                        METRO_TERRACE_DATUM+.17, cafe_red)
                hydrant_cap = add_uv_sphere(world_col, "metro_hydrant_cap", .23,
                                             sx+26.0, sy-22.5,
                                             METRO_TERRACE_DATUM+1.00,
                                             cafe_red, 5, 8)
                news = add_box(world_col, "metro_news_box", .78, .64, 1.12,
                               sx-25.2, sy+18.0,
                               METRO_TERRACE_DATUM+.17, civic_blue)
                news_glass = add_box(world_col, "metro_news_box_window", .52,
                                     .05, .34, sx-25.2, sy+17.66,
                                     METRO_TERRACE_DATUM+.82, storefront)
                wall_light = add_box(world_col, "metro_service_wall_light",
                                     .20, .42, .24, sx+19.08, sy+12.0,
                                     METRO_TERRACE_DATUM+3.18, lamp_glow)
                created.extend((hydrant, hydrant_cap, news, news_glass,
                                wall_light))
            elif int(slot["metro_id"]) % 3 == 0:
                # Surface parking is an ordinary interim downtown land use,
                # not a permanent sea of asphalt. It disappears when claimed.
                parking = add_box(world_col, "metro_interim_parking", 43.0, 40.0, .07,
                                  slot["x"], slot["y"],
                                  METRO_TERRACE_DATUM+.055, asphalt)
                created.append(parking)
                for line_x in range(-18, 19, 6):
                    stripe = add_box(world_col, "metro_parking_stripe", .11, 8.5, .02,
                                     slot["x"]+line_x, slot["y"]-12.0,
                                     METRO_TERRACE_DATUM+.13, white)
                    created.append(stripe)
                for car_index, line_x in enumerate((-12.0, 6.0)):
                    car = place_instance(
                        world_col,
                        {"type": "car", "gx": 0, "gy": 0,
                         "seed": 26000+int(slot["metro_id"])*7+car_index},
                        "metro_parked_car")
                    car.scale = (.72, .72, .72)
                    car.location = (slot["x"]+line_x, slot["y"]-12.0,
                                    METRO_TERRACE_DATUM+.17)
                    car.rotation_euler.z = math.pi/2
                    created.append(car)
            elif int(slot["metro_id"]) % 3 == 1:
                # Interim green space prevents the reserve from reading as a
                # collection of blank construction pads between growth days.
                park_pad = add_box(world_col, "metro_interim_park", 43.0, 40.0, .07,
                                   slot["x"], slot["y"],
                                   METRO_TERRACE_DATUM+.055, lawn)
                path_ns = add_box(world_col, "metro_interim_park_path", 3.0, 36.0, .04,
                                  slot["x"], slot["y"],
                                  METRO_TERRACE_DATUM+.13, paver)
                path_ew = add_box(world_col, "metro_interim_park_path", 39.0, 3.0, .04,
                                  slot["x"], slot["y"],
                                  METRO_TERRACE_DATUM+.13, paver)
                created.extend((park_pad, path_ns, path_ew))
                for dx, dy in ((-13.0, -11.0), (13.0, -11.0),
                               (-13.0, 11.0), (13.0, 11.0)):
                    trunk = add_ngon_cone(world_col, "metro_interim_tree_trunk",
                                          .22, .18, 2.4, 7,
                                          slot["x"]+dx, slot["y"]+dy,
                                          METRO_TERRACE_DATUM+.13, timber)
                    crown = add_ngon_cone(world_col, "metro_interim_tree_crown",
                                          1.6, .6, 3.0, 8,
                                          slot["x"]+dx, slot["y"]+dy,
                                          METRO_TERRACE_DATUM+2.5, green)
                    created.extend((trunk, crown))
            else:
                # A prepared parcel with foundation marks and safety fencing.
                site = add_box(world_col, "metro_future_construction", 43.0, 40.0, .07,
                               slot["x"], slot["y"],
                               METRO_TERRACE_DATUM+.055, earth)
                created.append(site)
                for side in (-1, 1):
                    fence_ns = add_box(world_col, "metro_construction_fence",
                                       .18, 38.0, 1.25,
                                       slot["x"]+side*20.5, slot["y"],
                                       METRO_TERRACE_DATUM+.13, safety)
                    fence_ew = add_box(world_col, "metro_construction_fence",
                                       41.0, .18, 1.25,
                                       slot["x"], slot["y"]+side*18.8,
                                       METRO_TERRACE_DATUM+.13, safety)
                    created.extend((fence_ns, fence_ew))
                for grid_x in (-9.0, 0.0, 9.0):
                    footing = add_box(world_col, "metro_future_footing", 2.2, 24.0, .22,
                                      slot["x"]+grid_x, slot["y"],
                                      METRO_TERRACE_DATUM+.13, highway_concrete)
                    created.append(footing)

    # Zebra crossings concentrate on the two boulevards and Kettle seam.
    for y in (522.0, 588.0, METRO_INTERCHANGE_Y):
        road_half = 7.0 if y in (588.0, METRO_INTERCHANGE_Y) else 4.0
        for x in METRO_NS_X:
            for stripe in (-1.8, -.6, .6, 1.8):
                north = add_box(world_col, "metro_crosswalk", .54,
                                road_half*2-.8, .025, x+stripe, y,
                                METRO_TERRACE_DATUM+.205, white)
                created.append(north)
            # Curb ramps are separate lower pads, not paint on the sidewalk.
            for side in (-1, 1):
                ramp = add_box(world_col, "metro_curb_ramp", 3.2, 1.15, .07,
                               x, y+side*(road_half+.58),
                               METRO_TERRACE_DATUM+.17, concrete)
                created.append(ramp)

    # Crown Boulevard receives a planted median between junctions.
    for a, b in zip(METRO_NS_X, METRO_NS_X[1:]):
        median = add_box(world_col, "metro_boulevard_median", b-a-12.0, 1.35, .24,
                         (a+b)/2, METRO_INTERCHANGE_Y,
                         METRO_TERRACE_DATUM+.205, curb)
        created.append(median)
        for x in ((a+b)/2-13.0, (a+b)/2+13.0):
            planter = add_box(world_col, "metro_median_planter", 3.4, 1.05, .34,
                              x, METRO_INTERCHANGE_Y,
                              METRO_TERRACE_DATUM+.445, green)
            created.append(planter)

    # Human-scale furnishing repeats consistently without becoming clutter.
    for xi, x in enumerate(METRO_NS_X):
        for yi, y in enumerate(METRO_EW_Y):
            if yi == len(METRO_EW_Y)-1:
                continue
            lamp_data = {"type": "streetlight", "gx": 0, "gy": 0,
                         "seed": 23000+xi*31+yi}
            lamp = place_instance(world_col, lamp_data, "metro_streetlight")
            lamp.location = (x+5.9, y+5.9, METRO_TERRACE_DATUM+.28)
            created.append(lamp)
            if xi < len(METRO_NS_X)-1:
                tx, ty = x+35.0, y+8.0
                trunk = add_ngon_cone(world_col, "metro_tree_trunk", .22, .18,
                                      2.5, 7, tx, ty,
                                      METRO_TERRACE_DATUM+.28, timber)
                crown = add_ngon_cone(world_col, "metro_tree_crown", 1.65, .65,
                                      3.2, 8, tx, ty,
                                      METRO_TERRACE_DATUM+2.75, green)
                created.extend((trunk, crown))

    # Four sheltered bus stops serve both boulevards.  They are modeled here
    # to match Followville materials instead of importing an unrelated pack.
    for index, (x, y, rot) in enumerate(((-82.0, 588.0, 0.0),
                                         (52.0, 588.0, math.pi),
                                         (-82.0, METRO_INTERCHANGE_Y, 0.0),
                                         (52.0, METRO_INTERCHANGE_Y, math.pi))):
        side = 1 if rot == 0.0 else -1
        sy = y+side*9.0
        shelter = add_box(world_col, "metro_bus_shelter_glass", 6.4, .14, 2.7,
                          x, sy, METRO_TERRACE_DATUM+.28, shelter_glass)
        roof = add_box(world_col, "metro_bus_shelter_roof", 7.0, 2.4, .20,
                       x, sy-side*.9, METRO_TERRACE_DATUM+2.98, metal)
        bench = add_box(world_col, "metro_bus_bench", 3.8, .65, .55,
                        x, sy-side*.55, METRO_TERRACE_DATUM+.31, timber)
        bin_obj = add_ngon_cone(world_col, "metro_litter_bin", .34, .34, .88, 8,
                                x+3.0, sy, METRO_TERRACE_DATUM+.28, metal)
        flag = add_box(world_col, "metro_bus_stop_flag", 1.15, .10, .75,
                       x-3.0, sy, METRO_TERRACE_DATUM+2.25, sign_green)
        created.extend((shelter, roof, bench, bin_obj, flag))

    # Parked curbside vehicles, short loading bays and a dedicated city bus
    # make the grid read as occupied even in a still.  They remain well clear
    # of every crosswalk and tower lobby.
    for row_index, y in enumerate(METRO_EW_Y[1:-1], start=1):
        for column in range(5):
            if (row_index+column) % 2:
                continue
            x = (METRO_NS_X[column]+METRO_NS_X[column+1])/2
            side = -1 if (row_index+column) % 4 else 1
            car = place_instance(
                world_col,
                {"type": "car", "gx": 0, "gy": 0,
                 "seed": 28000+row_index*17+column},
                "metro_curbside_car")
            car.scale = (.78, .78, .78)
            car.location = (x, y+side*2.65, METRO_TERRACE_DATUM+.20)
            car.rotation_euler.z = 0.0 if side > 0 else math.pi
            created.append(car)
            loading = add_box(world_col, "metro_loading_mark", 8.0, .14,
                              .025, x+12.0, y+side*2.65,
                              METRO_TERRACE_DATUM+.205, cafe_gold)
            created.append(loading)

    bus_x, bus_y = -16.0, 588.0
    bus_center_y = bus_y-2.7
    bus_chassis = add_box(world_col, "metro_city_bus_chassis", 10.35, 2.48,
                          .28, bus_x, bus_center_y,
                          METRO_TERRACE_DATUM+.34, rubber)
    bus_body = add_tapered_box(world_col, "metro_city_bus_body",
                               10.2, 2.55, 9.85, 2.45, 2.30,
                               bus_x, bus_center_y,
                               METRO_TERRACE_DATUM+.49, 0, 0, civic_blue)
    bus_roof = add_box(world_col, "metro_city_bus_roof", 9.55, 2.30, .20,
                       bus_x-.10, bus_center_y,
                       METRO_TERRACE_DATUM+2.80, bus_white)
    belt = add_box(world_col, "metro_city_bus_belt", 9.90, 2.59, .14,
                   bus_x, bus_center_y, METRO_TERRACE_DATUM+1.37, bus_white)
    created.extend((bus_chassis, bus_body, bus_roof, belt))
    # Individual glazing bays and mullions keep the bus from reading as a
    # single blue box; each side also gets a double passenger door.
    for side in (-1, 1):
        wy = bus_center_y + side*1.286
        for window_index, wx in enumerate((-3.75, -2.35, -.95, .45, 1.85, 3.25)):
            if side < 0 and window_index in (4, 5):
                continue
            window = add_box(world_col, "metro_city_bus_window", 1.15, .055,
                             .78, bus_x+wx, wy,
                             METRO_TERRACE_DATUM+1.55, shelter_glass)
            created.append(window)
        if side < 0:
            for door_x in (2.25, 3.35):
                door = add_box(world_col, "metro_city_bus_door", .96, .06,
                               1.52, bus_x+door_x, wy-.015,
                               METRO_TERRACE_DATUM+.66, storefront)
                door_bar = add_box(world_col, "metro_city_bus_door_bar", .07,
                                   .075, 1.53, bus_x+door_x+.48, wy-.025,
                                   METRO_TERRACE_DATUM+.66, steel_light)
                created.extend((door, door_bar))
    windshield = add_box(world_col, "metro_city_bus_windshield", .065, 2.02,
                         .82, bus_x+5.11, bus_center_y,
                         METRO_TERRACE_DATUM+1.54, storefront)
    rear_glass = add_box(world_col, "metro_city_bus_rear_window", .065, 1.88,
                         .72, bus_x-5.11, bus_center_y,
                         METRO_TERRACE_DATUM+1.62, shelter_glass)
    destination = add_box(world_col, "metro_city_bus_destination", .07, 1.52,
                          .28, bus_x+5.16, bus_center_y,
                          METRO_TERRACE_DATUM+2.45, sign_green)
    created.extend((windshield, rear_glass, destination))
    for side in (-1, 1):
        mirror_arm = add_beam_between(
            world_col, "metro_city_bus_mirror_arm",
            (bus_x+4.55, bus_center_y+side*1.20, METRO_TERRACE_DATUM+2.15),
            (bus_x+4.82, bus_center_y+side*1.55, METRO_TERRACE_DATUM+2.12),
            .055, steel_light)
        mirror = add_box(world_col, "metro_city_bus_mirror", .18, .10, .30,
                         bus_x+4.85, bus_center_y+side*1.57,
                         METRO_TERRACE_DATUM+1.98, rubber)
        created.extend((mirror_arm, mirror))
    for side in (-1, 1):
        for light_y in (-.70, .70):
            headlight = add_box(world_col, "metro_city_bus_headlight", .07,
                                .28, .22, bus_x+5.17,
                                bus_center_y+light_y,
                                METRO_TERRACE_DATUM+.75,
                                lamp_glow if side > 0 else cafe_red)
            if side < 0:
                headlight.location.x = bus_x-5.17
            created.append(headlight)
    for wheel_x in (-3.45, 3.45):
        for wheel_y in (-1.36, 1.36):
            wheel = add_torus(world_col, "metro_city_bus_wheel", .40, .12,
                              bus_x+wheel_x, bus_center_y+wheel_y,
                              METRO_TERRACE_DATUM+.78, rubber,
                              18, 7, (math.pi/2, 0, 0))
            hub = add_uv_sphere(world_col, "metro_city_bus_hub", .18,
                                bus_x+wheel_x, bus_center_y+wheel_y,
                                METRO_TERRACE_DATUM+.80, steel_light, 6, 10)
            hub.scale.y = .42
            created.extend((wheel, hub))

    # Four compact corner kiosks add errands and light without becoming new
    # claimable buildings.  Their canopies use Followville's civic palette.
    for kiosk_index, (kx, ky) in enumerate(((-155.0, 570.0), (125.0, 606.0),
                                             (-155.0, 636.0), (125.0, 768.0))):
        body = add_box(world_col, "metro_corner_kiosk", 3.2, 2.5, 2.5,
                       kx, ky, METRO_TERRACE_DATUM+.17,
                       cafe_gold if kiosk_index % 2 else civic_blue)
        canopy = add_box(world_col, "metro_kiosk_canopy", 4.0, 3.25, .20,
                         kx, ky, METRO_TERRACE_DATUM+2.67,
                         cafe_red if kiosk_index % 2 else sign_green)
        counter = add_box(world_col, "metro_kiosk_counter", 2.45, .42, .78,
                          kx, ky-1.42, METRO_TERRACE_DATUM+.82, timber)
        service_window = add_box(world_col, "metro_kiosk_window", 2.15, .06,
                                 .92, kx, ky-1.272,
                                 METRO_TERRACE_DATUM+1.36, storefront)
        sign = add_box(world_col, "metro_kiosk_sign", 1.65, .08, .42,
                       kx, ky-1.31, METRO_TERRACE_DATUM+2.26,
                       cafe_gold if kiosk_index%2 == 0 else bus_white)
        menu = add_box(world_col, "metro_kiosk_menu", .68, .06, .90,
                       kx+1.28, ky-1.31, METRO_TERRACE_DATUM+.78,
                       sign_green)
        created.extend((body, canopy, counter, service_window, sign, menu))

    # The Crown Expressway used to be built here, in seventy lines wedged
    # between the towers and the kiosks, which is a large part of why it
    # never grew past one interchange and never got a proper end. It now
    # lives in build_highway_system() with the rest of the network.

    for obj in created:
        if obj is not None:
            obj["nb_feature_role"] = obj.get("nb_feature_role", "metropolitan")
    return [obj for obj in created if obj is not None]


# ═══════════════════════════ HIGHWAY SYSTEM ═══════════════════════════════
#
# The freeway and collector tiers. The alignments, heights, ramps, vehicles and
# lighting are all data in highway_plan.py; nothing here decides where a road
# goes, only what it is made of.
#
# This owns the Crown Expressway outright. It used to be built inside
# build_metropolitan_district as one 70-line block with the towers, which is
# why it never grew past a single interchange.


def _offset_path(points, offset):
    """Offset a centreline sideways in plan, keeping every authored height."""
    if len(points) < 2:
        return list(points)
    out = []
    for index, point in enumerate(points):
        before = points[max(0, index-1)]
        after = points[min(len(points)-1, index+1)]
        dx, dy = after[0]-before[0], after[1]-before[1]
        length = math.hypot(dx, dy) or 1.0
        out.append((point[0] - dy/length*offset, point[1] + dx/length*offset,
                    point[2] if len(point) > 2 else 0.0))
    return out


def _extend_path(points, reach):
    """Carry a centreline a little past both ends, along its own direction."""
    def push(near, far):
        dx, dy = near[0]-far[0], near[1]-far[1]
        length = math.hypot(dx, dy) or 1.0
        return (near[0] + dx/length*reach, near[1] + dy/length*reach, near[2])
    return ([push(points[0], points[1])] + list(points)
            + [push(points[-1], points[-2])])


def _densify_path(points, step):
    """Resample a centreline, keeping every authored point."""
    out = []
    for a, b in zip(points, points[1:]):
        count = max(1, int(math.ceil(math.hypot(b[0]-a[0], b[1]-a[1])/step)))
        for index in range(count):
            t = index/count
            out.append(tuple(a[i] + (b[i]-a[i])*t for i in range(3)))
    out.append(tuple(points[-1][:3]))
    return out


def _path_runs(points, keep):
    """Split a centreline into the contiguous runs where keep(point) is true.

    Runs carry one point of overlap at each end so consecutive pieces of
    structure meet instead of leaving a gap the width of one sample.
    """
    runs, current = [], []
    for index, point in enumerate(points):
        if keep(point):
            if not current and index:
                current.append(points[index-1])
            current.append(point)
        elif current:
            current.append(point)
            if len(current) > 1:
                runs.append(current)
            current = []
    if len(current) > 1:
        runs.append(current)
    return runs


def _add_grade_skirt(world_col, name, points, material, width,
                     top_drop=.02, sink=.55):
    """The embankment under a low deck: top just below it, bottom in the ground.

    _add_road_strip's structure box is a constant 1.05m deep, which is right
    for a viaduct on piers and wrong for a road standing two metres over a
    meadow -- it leaves the deck floating on nothing. This ribbon's underside
    follows the terrain instead, so a road that rises out of the ground carries
    its own embankment up with it.
    """
    if len(points) < 2:
        return None
    # Run 1.6m past each end. The ribbon used to stop exactly on its last
    # control point, which left a hairline of unsupported deck at the terminal
    # of every ramp -- eight of them, each one vertex wide.
    points = _extend_path(list(points), 1.6)
    dense = []
    for a, b in zip(points, points[1:]):
        steps = max(1, int(math.ceil(math.hypot(b[0]-a[0], b[1]-a[1])/3.0)))
        for step in range(steps):
            t = step/steps
            dense.append(tuple(a[i] + (b[i]-a[i])*t for i in range(3)))
    dense.append(tuple(points[-1][:3]))
    offsets = []
    for index in range(len(dense)):
        before = dense[max(0, index-1)]
        after = dense[min(len(dense)-1, index+1)]
        dx, dy = after[0]-before[0], after[1]-before[1]
        length = math.hypot(dx, dy) or 1.0
        offsets.append((-dy/length*width/2.0, dx/length*width/2.0))
    verts = []
    for point, offset in zip(dense, offsets):
        for side in (1, -1):
            x = point[0] + side*offset[0]
            y = point[1] + side*offset[1]
            verts.append((x, y, terrain_height(x, y) - sink))
    for point, offset in zip(dense, offsets):
        for side in (1, -1):
            verts.append((point[0] + side*offset[0], point[1] + side*offset[1],
                          point[2] - top_drop))
    count = len(dense)
    faces = []
    for i in range(count-1):
        faces.extend(((2*i, 2*i+1, 2*i+3, 2*i+2),
                      (2*count+2*i, 2*count+2*i+2, 2*count+2*i+3, 2*count+2*i+1),
                      (2*i, 2*i+2, 2*count+2*i+2, 2*count+2*i),
                      (2*i+1, 2*count+2*i+1, 2*count+2*i+3, 2*i+3)))
    faces.extend(((0, 2*count, 2*count+1, 1),
                  (2*count-2, 2*count-1, 4*count-1, 4*count-2)))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    world_col.objects.link(obj)
    return obj


def _batch_plates(world_col, name, plates, material):
    """Many oriented flat plates as one mesh: lane lines, dashes, gore chevrons.

    Road markings on a curve cannot be axis-aligned boxes, and one object per
    dash would put four thousand of them in the scene.
    """
    if not plates:
        return None
    verts, faces = [], []
    for x, y, z, half_length, half_width, heading in plates:
        cos_h, sin_h = math.cos(heading), math.sin(heading)
        start = len(verts)
        for dx, dy in ((-half_length, -half_width), (half_length, -half_width),
                       (half_length, half_width), (-half_length, half_width)):
            verts.append((x + dx*cos_h - dy*sin_h, y + dx*sin_h + dy*cos_h, z))
        faces.append((start, start+1, start+2, start+3))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    world_col.objects.link(obj)
    return obj


def _walk_path(points, step):
    """Sample (x, y, z, heading) along a centreline at fixed intervals."""
    out = []
    carried = 0.0
    for a, b in zip(points, points[1:]):
        span = math.hypot(b[0]-a[0], b[1]-a[1])
        if span < 1e-6:
            continue
        heading = math.atan2(b[1]-a[1], b[0]-a[0])
        travelled = carried
        while travelled < span:
            t = travelled/span
            out.append((a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t,
                        a[2] + (b[2]-a[2])*t, heading))
            travelled += step
        carried = travelled - span
    return out


def _highway_markings(world_col, name, points, white, gores=()):
    """Edge lines, lane separators and gore chevrons for a six-lane deck.

    Markings sit 5mm above the deck surface -- above MIN_VISIBLE_SURFACE_
    CLEARANCE -- because a painted line coplanar with the asphalt is exactly
    the depth-fight the visible-surface rule exists to prevent.
    """
    created = []
    lift = HP.DECK_SURFACE + .025
    edge, dash = [], []
    for x, y, z, heading in _walk_path(points, 3.0):
        for side in (-1, 1):
            edge.append((x - math.sin(heading)*side*HP.SHOULDER_HALF,
                         y + math.cos(heading)*side*HP.SHOULDER_HALF,
                         z + lift, 1.55, .085, heading))
    for x, y, z, heading in _walk_path(points, 12.0):
        for offset in (-8.0, -4.0, 4.0, 8.0):
            dash.append((x - math.sin(heading)*offset,
                         y + math.cos(heading)*offset,
                         z + lift, 2.0, .075, heading))
    created.append(_batch_plates(world_col, name + "_edge_line", edge, white))
    created.append(_batch_plates(world_col, name + "_lane_dash", dash, white))
    chevrons = []
    for gore_x, gore_y, gore_z, heading, side in gores:
        for index in range(7):
            reach = 3.0 + index*3.4
            spread = .55 + index*.62
            chevrons.append((gore_x + math.cos(heading)*reach
                             - math.sin(heading)*side*(HP.SHOULDER_HALF + spread*.5),
                             gore_y + math.sin(heading)*reach
                             + math.cos(heading)*side*(HP.SHOULDER_HALF + spread*.5),
                             gore_z + lift, 1.5, spread*.5, heading))
    created.append(_batch_plates(world_col, name + "_gore", chevrons, white))
    return [obj for obj in created if obj is not None]


def _highway_supports(world_col, name, points, width, concrete,
                      skirt_limit=3.4, pier_step=34.0, bridge_spans=()):
    """Whatever holds a deck up: embankment when it can be, structure when not.

    ``skirt_limit`` is the height below which the deck rides on solid ground
    rather than on piers. It is 3.4m for a six-lane mainline, where a viaduct
    is the point, and much higher for a ramp, where it is not: a 5.4m ribbon on
    34m pier spacing put 347 of 606 ramp centreline points in the air with
    nothing visible under them. Real interchange ramps are earthworks that
    climb to meet a structure, not viaducts the whole way.

    ``bridge_spans`` forces structure inside a rectangle whatever the height,
    which is how a link road crosses the ring without burying it in fill.
    """
    def spanning(point):
        return any(x0 <= point[0] <= x1 and y0 <= point[1] <= y1
                   for x0, x1, y0, y1 in bridge_spans)

    def stands(point):
        return point[2] - terrain_height(point[0], point[1])

    def on_structure(point):
        return spanning(point) or stands(point) > skirt_limit

    # Sampled every few metres before the runs are cut. A hand-authored ramp
    # can be eight points across 350m, and testing the height only at those
    # eight decides forty-five metres of embankment on one sample.
    points = _densify_path(points, 4.0)
    created = []
    low = _path_runs(points,
                     lambda p: stands(p) > .30 and not on_structure(p))
    for index, run in enumerate(low):
        created.append(_add_grade_skirt(world_col, "%s_embankment_%d" % (name, index),
                                        run, concrete, width + 3.2))
    high = _path_runs(points, on_structure)
    piers = []
    caps = []
    for index, run in enumerate(high):
        created.append(_add_road_strip(
            world_col, "%s_structure_%d" % (name, index), run, concrete,
            width=width + HP.STRUCTURE_EXTRA, bottom_offset=-1.05, top_offset=-.05))
        for x, y, z, heading in _walk_path(run, pier_step):
            ground = terrain_height(x, y)
            if z - ground < 1.6:
                continue
            # The cap's top is pushed 2cm into the underside of the structure
            # ribbon rather than meeting it exactly: a shared plane there is
            # two visible faces on one plane, which is the depth fight the
            # visible-surface rule exists to prevent.
            cap_top = z - 1.03
            cap_bottom = cap_top - .76
            caps.append((x, y, cap_bottom, heading, width * .72))
            for side in (-1, 1):
                reach = side * width * .26
                piers.append((x - math.sin(heading)*reach,
                              y + math.cos(heading)*reach,
                              ground, cap_bottom - ground + .04))
    for px, py, base, height in piers:
        created.append(add_ngon_cone(world_col, "%s_pier" % name, .98, .74,
                                     max(.4, height), 8, px, py, base, concrete))
    for x, y, base, heading, span in caps:
        # add_box's width runs along local X, and rotating by the road's
        # heading puts local X along the road. A pier cap crosses it, so the
        # span goes in the depth slot.
        cap = add_box(world_col, "%s_pier_cap" % name, 1.25, span, .76,
                      x, y, base, concrete)
        cap.rotation_euler = (0, 0, heading)
        created.append(cap)
    return [obj for obj in created if obj is not None]


def _highway_barriers(world_col, name, points, rail, gaps=()):
    """Median and outside barriers, with real openings at every ramp gore.

    The existing viaduct runs all three unbroken for 608m, so its four ramps
    leave from behind a barrier. A gap is a (start, end) distance along the
    centreline where a ramp diverges or merges.
    """
    created = []
    run_length = []
    total = 0.0
    for index, point in enumerate(points):
        if index:
            total += math.hypot(point[0]-points[index-1][0],
                                point[1]-points[index-1][1])
        run_length.append(total)

    def blocked(distance, side):
        return any(start <= distance <= end and gap_side == side
                   for start, end, gap_side in gaps)

    # Barriers start 12cm inside the deck rather than on its top face, so no
    # part of the deck shares a plane with the underside of a barrier.
    base = HP.DECK_SURFACE - .12
    # Left and right of the direction the point list runs, not compass points:
    # the ring turns a corner and spends half its length running east-west.
    # _offset_path's positive offset is the left-hand side, which is the same
    # sign convention _ramp_gaps_and_gores uses to decide which barrier a ramp
    # needs opened.
    for label, offset, height, side in (("median", 0.0, .94, 0),
                                        ("left", HP.SHOULDER_HALF + 1.05, .90, 1),
                                        ("right", -HP.SHOULDER_HALF - 1.05, .90, -1)):
        line = _offset_path(points, offset)
        piece, index = [], 0
        for point, distance in zip(line, run_length):
            if offset == 0.0 or not blocked(distance, side):
                piece.append(point)
            elif len(piece) > 1:
                created.append(_add_road_strip(
                    world_col, "%s_barrier_%s_%d" % (name, label, index), piece,
                    rail, width=.38, bottom_offset=base,
                    top_offset=base + height))
                index += 1
                piece = []
            else:
                piece = []
        if len(piece) > 1:
            created.append(_add_road_strip(
                world_col, "%s_barrier_%s_%d" % (name, label, index), piece,
                rail, width=.38, bottom_offset=base,
                top_offset=base + height))
    return [obj for obj in created if obj is not None]


def _build_freeway(world_col, name, points, mats, gaps=(), gores=()):
    """One freeway carriageway pair: deck, supports, barriers and markings."""
    created = []
    created.append(_add_road_strip(world_col, name + "_deck", points,
                                   mats["asphalt"], width=HP.FREEWAY_WIDTH,
                                   bottom_offset=-.04, top_offset=HP.DECK_SURFACE))
    created.extend(_highway_supports(world_col, name, points, HP.FREEWAY_WIDTH,
                                     mats["concrete"]))
    created.extend(_highway_barriers(world_col, name, points, mats["rail"], gaps))
    created.extend(_highway_markings(world_col, name, points, mats["white"], gores))
    return created


def _build_ramp(world_col, name, points, mats, width=None):
    """A ramp: deck, kerbs, whatever holds it up, and a centre line.

    A ramp is an earthwork up to 6.5m and a short structure above that, where
    it is alongside the viaduct it leaves. Piers go in at 16m rather than 34m,
    because a ramp is a fifth the width of the mainline and the same spacing
    reads as no support at all.
    """
    width = width or HP.RAMP_WIDTH
    created = [_add_road_strip(world_col, name + "_deck", points, mats["asphalt"],
                               width=width, bottom_offset=-.04,
                               top_offset=HP.DECK_SURFACE)]
    created.extend(_highway_supports(world_col, name, points, width,
                                     mats["concrete"], skirt_limit=6.5,
                                     pier_step=16.0))
    for side in (-1, 1):
        created.append(_add_road_strip(
            world_col, name + "_kerb", _offset_path(points, side*(width/2.0 + .26)),
            mats["rail"], width=.30, bottom_offset=HP.DECK_SURFACE - .12,
            top_offset=HP.DECK_SURFACE + .46))
    line = [(x, y, z + HP.DECK_SURFACE + .012, 1.3, .07, heading)
            for x, y, z, heading in _walk_path(points, 8.0)]
    created.append(_batch_plates(world_col, name + "_line", line, mats["white"]))
    return [obj for obj in created if obj is not None]


def _build_surface_road(world_col, name, points, width, mats, centre_line=True,
                        bridge_spans=()):
    """A collector, link or interchange cross road: at grade unless it bridges."""
    created = [_add_road_strip(world_col, name + "_deck", points, mats["asphalt"],
                               width=width, bottom_offset=-.04,
                               top_offset=HP.DECK_SURFACE)]
    created.extend(_highway_supports(world_col, name, points, width,
                                     mats["concrete"], skirt_limit=7.5,
                                     pier_step=18.0, bridge_spans=bridge_spans))
    if centre_line:
        line = [(x, y, z + HP.DECK_SURFACE + .012, 1.6, .07, heading)
                for x, y, z, heading in _walk_path(points, 9.0)]
        created.append(_batch_plates(world_col, name + "_line", line, mats["white"]))
    return [obj for obj in created if obj is not None]


def _ramp_gaps_and_gores(points, ramps):
    """Where each ramp touches the mainline, as barrier gaps and gore marks.

    Read straight off the ramp geometry rather than authored twice, so a ramp
    that moves takes its barrier opening and its chevrons with it.
    """
    run = [0.0]
    for index in range(1, len(points)):
        run.append(run[-1] + math.hypot(points[index][0]-points[index-1][0],
                                        points[index][1]-points[index-1][1]))
    gaps, gores = [], []
    for ramp in ramps:
        touch = ramp["points"][0] if ramp["role"] == "exit" else ramp["points"][-1]
        best, best_at = None, 0.0
        for index, point in enumerate(points):
            distance = math.hypot(point[0]-touch[0], point[1]-touch[1])
            if best is None or distance < best:
                best, best_at, best_index = distance, run[index], index
        if best is None or best > 26.0:
            continue
        neighbour = points[min(len(points)-1, best_index+1)]
        anchor = points[best_index]
        heading = math.atan2(neighbour[1]-anchor[1], neighbour[0]-anchor[0])
        # Which side of the deck the ramp leaves from, in the road's own frame:
        # the cross product of its heading with the offset to the ramp.
        cross = (math.cos(heading)*(touch[1]-anchor[1])
                 - math.sin(heading)*(touch[0]-anchor[0]))
        side = 1 if cross > 0 else -1
        gaps.append((best_at - 16.0, best_at + 16.0, side))
        if ramp["role"] == "exit":
            gores.append((anchor[0], anchor[1], anchor[2], heading, side))
    return gaps, gores


def build_highway_system(world_col, buildings, m):
    """Build the whole freeway and collector network for the current state."""
    if not HP.is_active(buildings):
        return []

    mats = {
        "asphalt": mat("FV_highway_asphalt", (.255, .265, .285), .92),
        "concrete": mat("FV_expressway_concrete", (.42, .43, .42), .97),
        "rail": mat("FV_expressway_rail", (.22, .25, .25), .78, metallic=.18),
        "white": mat("FV_highway_paint", (.93, .93, .90), .62),
        "sign": mat("FV_expressway_sign", (.08, .30, .22), .76),
        "metal": mat("NB_metal", (0.25, 0.27, 0.30), 0.5),
    }
    created = []

    # ---- F-1, the Crown Expressway, end to end -------------------------------
    approach = list(HP.crown_approach_points())
    created.append(_add_road_strip(
        world_col, "highway_crown_approach_deck", approach, mats["asphalt"],
        widths=list(HP.crown_approach_widths(approach)),
        bottom_offset=-.04, top_offset=HP.DECK_SURFACE))
    created.extend(_highway_supports(world_col, "highway_crown_approach",
                                     approach, HP.ARTERIAL_WIDTH + 4.0,
                                     mats["concrete"], skirt_limit=9.0))
    created.extend(_highway_markings(world_col, "highway_crown_approach",
                                     approach, mats["white"]))

    mainline = [(HP.EXPRESSWAY_X, y, HP.EXPRESSWAY_DECK_Z)
                for y in _frange(EXPRESSWAY_Y0, EXPRESSWAY_Y1, 3.0)]
    north = list(HP.north_extension_points())
    all_ramps = [ramp for entry in HP.interchanges() if entry["route"] == "F-1"
                 for ramp in entry["ramps"]]
    all_ramps.extend(ramp for entry in HP.interchanges()
                     if entry["id"] == "IC-4" for ramp in entry["ramps"])
    gaps, gores = _ramp_gaps_and_gores(mainline, all_ramps)
    created.extend(_build_freeway(world_col, "highway_crown_viaduct", mainline,
                                  mats, gaps, gores))
    north_gaps, north_gores = _ramp_gaps_and_gores(north, all_ramps)
    created.extend(_build_freeway(world_col, "highway_crown_north", north, mats,
                                  north_gaps, north_gores))

    # ---- F-2, the Ring Freeway ----------------------------------------------
    ring = list(HP.ring_points())
    ring_ramps = [ramp for entry in HP.interchanges()
                  if entry["route"] in ("F-2", "F-1 x F-2")
                  for ramp in entry["ramps"]]
    ring_gaps, ring_gores = _ramp_gaps_and_gores(ring, ring_ramps)
    created.extend(_build_freeway(world_col, "highway_ring", ring, mats,
                                  ring_gaps, ring_gores))

    # ---- collectors, links and interchange cross roads ----------------------
    for collector in HP.COLLECTORS:
        created.extend(_build_surface_road(
            world_col, "highway_collector_" + _slug(collector["name"]),
            list(HP.collector_points(collector)), collector["width"], mats))
    for index, (bulb_x, bulb_y) in enumerate(HP.turnarounds()):
        created.append(add_ngon_cone(
            world_col, "highway_turnaround_%d" % index, HP.TURNAROUND_RADIUS,
            HP.TURNAROUND_RADIUS, .23, 20, bulb_x, bulb_y,
            terrain_height(bulb_x, bulb_y) - .04, mats["asphalt"]))

    for entry in HP.interchanges():
        cross = entry.get("cross_road")
        if cross:
            bridge = cross.get("overbridge")
            spans = ()
            if bridge:
                # Over the freeway itself the link is a bridge; fill there
                # would bury the road it is crossing.
                spans = ((bridge[0] - 22.0, bridge[0] + 22.0,
                          entry["y"] - 30.0, entry["y"] + 30.0),)
            created.extend(_build_surface_road(
                world_col, "highway_cross_" + _slug(cross["name"]),
                list(HP.cross_road_points(cross)), cross["width"], mats,
                bridge_spans=spans))
        for ramp in entry["ramps"]:
            created.extend(_build_ramp(world_col,
                                       "highway_ramp_" + _slug(ramp["name"]),
                                       list(ramp["points"]), mats))

    # ---- overhead wayfinding at every decision point ------------------------
    for entry in HP.interchanges():
        created.extend(_build_gantry(world_col, entry, mats))

    # ---- lighting -----------------------------------------------------------
    # Named so _build_video_practicals() finds them. The viaduct's own fixtures
    # were called metro_expressway_light* and matched nothing, which is why the
    # deck has looked unlit at night with no obvious cause.
    for index, (x, y, z, arm) in enumerate(HP.mainline_masts() + HP.ring_masts()):
        lamp = place_instance(world_col, {"type": "highwaymast", "gx": 0, "gy": 0,
                                          "px": x, "py": y, "pz": z,
                                          "rot": 0.0 if arm > 0 else math.pi,
                                          "seed": 61000 + index},
                              "metro_streetlight_highway_mast")
        created.append(lamp)
    for index, (x, y, z) in enumerate(HP.high_masts()):
        tower = place_instance(world_col, {"type": "highmast", "gx": 0, "gy": 0,
                                           "px": x, "py": y, "pz": z, "rot": 0.0,
                                           "seed": 62000 + index},
                               "metro_streetlight_high_mast")
        created.append(tower)

    # ---- traffic ------------------------------------------------------------
    for vehicle in HP.vehicles():
        created.append(place_instance(world_col, dict(vehicle), "highway_car"))

    for obj in created:
        if obj is not None:
            obj["nb_feature_role"] = obj.get("nb_feature_role", "highway")
    return [obj for obj in created if obj is not None]


def _build_gantry(world_col, entry, mats):
    """Sign gantry over the mainline, one interchange ahead of each exit."""
    created = []
    if entry["route"] == "F-2":
        centre_x, centre_y = HP.RING_X, entry["y"] + 150.0
        deck = HP.ring_height(centre_x, centre_y)
        heading = math.pi/2
    elif entry["id"] == "IC-4":
        centre_x, centre_y = HP.NORTH_JUNCTION_X - 6.0, HP.NORTH_TERMINUS_Y - 120.0
        deck = HP.mainline_deck_z(centre_y)
        heading = math.pi/2
    else:
        centre_y = entry["y"] + 150.0
        centre_x = HP.mainline_x(centre_y)
        deck = HP.mainline_deck_z(centre_y)
        heading = math.pi/2
    # A gantry crosses the road it signs. add_box builds axis-aligned, so the
    # beam and both panels have to be rotated onto the road's own heading --
    # without that they were built with their long axis along +Y, which on a
    # north-south freeway meant every sign faced along the carriageway instead
    # of across it, and read edge-on to the driver.
    across = (-math.sin(heading), math.cos(heading))
    for side in (-1, 1):
        post = add_box(world_col, "highway_gantry_post", .34, .34, 5.6,
                       centre_x + across[0]*side*(HP.SHOULDER_HALF - 1.2),
                       centre_y + across[1]*side*(HP.SHOULDER_HALF - 1.2),
                       deck + HP.DECK_SURFACE, mats["metal"])
        created.append(post)
    beam = add_box(world_col, "highway_gantry_beam", HP.FREEWAY_WIDTH - 2.0, .42,
                   .38, centre_x, centre_y, deck + HP.DECK_SURFACE + 5.55,
                   mats["metal"])
    beam.rotation_euler = (0, 0, heading + math.pi/2)
    created.append(beam)
    for side in (-1, 1):
        # Panels hang either side of the median, facing the traffic that reads
        # them: their face is across the road, their thickness along it.
        panel = add_box(world_col, "highway_gantry_sign", 8.4, .26, 2.5,
                        centre_x + across[0]*side*(HP.FREEWAY_WIDTH*.25)
                        + math.cos(heading)*.42,
                        centre_y + across[1]*side*(HP.FREEWAY_WIDTH*.25)
                        + math.sin(heading)*.42,
                        deck + HP.DECK_SURFACE + 2.85, mats["sign"])
        panel.rotation_euler = (0, 0, heading + math.pi/2)
        created.append(panel)
    return created


def _frange(start, end, step):
    count = max(1, int(math.ceil((end-start)/step)))
    return [start + (end-start)*index/count for index in range(count+1)]


def _slug(text):
    return "".join(character if character.isalnum() else "_"
                   for character in text.lower())


def build_highway_mast(col, _seed=0):
    """A 11.5m freeway lighting mast: a real pole, not a street lamp on a deck."""
    m = std_mats()
    add_ngon_cone(col, "mast", .22, .13, HP.MAST_HEIGHT, 8, 0, 0, 0, m["metal"])
    add_box(col, "mast_arm", 2.6, .17, .17, 1.30, 0, HP.MAST_HEIGHT - .30, m["metal"])
    add_box(col, "mast_brace", 1.5, .12, .12, .80, 0, HP.MAST_HEIGHT - 1.15,
            m["metal"])
    head = add_box(col, "mast_head", 1.05, .52, .22, 2.42, 0,
                   HP.MAST_HEIGHT - .58,
                   mat("FV_expressway_light_warm", (.96, .73, .38), .42,
                       metallic=.04))
    return head


def build_high_mast(col, _seed=0):
    """A 20m interchange high-mast light with a ring of eight heads.

    Every part is named highmast_*. They were "tower", "tower_base",
    "tower_crown" and "tower_head", which is a lighting column's vocabulary and
    a Crown Quarter skyscraper's vocabulary at the same time: in the exported
    GLB thirteen light columns read as 117 nodes called tower-something, next
    to twenty buildings the project also calls towers. Nothing keys off the
    names, so this changes no behaviour -- it stops the export lying about what
    is in it.
    """
    m = std_mats()
    warm = mat("FV_expressway_light_warm", (.96, .73, .38), .42, metallic=.04)
    add_ngon_cone(col, "highmast_column", .62, .30, HP.HIGH_MAST_HEIGHT, 8,
                  0, 0, 0, m["metal"])
    add_ngon_cone(col, "highmast_base", 1.15, .95, 1.10, 8, 0, 0, 0, m["cap"])
    add_ngon_cone(col, "highmast_ring", 1.95, 1.60, .40, 8, 0, 0,
                  HP.HIGH_MAST_HEIGHT - .30, m["metal"])
    for index in range(8):
        angle = math.tau*index/8
        head = add_box(col, "highmast_head", .66, .40, .26,
                       math.cos(angle)*1.62, math.sin(angle)*1.62,
                       HP.HIGH_MAST_HEIGHT - .74, warm)
        head.rotation_euler = (0, 0, angle)


def build_river_chapter(world_col, buildings, m):
    """Build the permanent river valley, riparian belt, and first crossing.

    The feature stays completely absent through plan 366 and appears with the
    first Rivergate address. It is world geometry, not a fake population or
    claimable building record.
    """
    river = SUBURBAN_PLAN.get("river") or {}
    active = max((b.get("plan_id", 0) for b in buildings), default=0)
    bridge = river.get("bridge") or {}
    if active < int(bridge.get("reveal_at", 10**9)):
        return []

    created = []
    centerline = [tuple(point) for point in river["centerline"]]
    water_points = [(x, y, river_water_height(y)) for x, y in centerline]
    water = _add_road_strip(
        world_col, "followville_river_water", water_points, m["water"],
        width=float(river.get("half_width", 14.0))*2.0,
        bottom_offset=-.58, top_offset=.025, terrain_conform=False)
    water["nb_feature_role"] = "river-water"
    created.append(water)

    gravel = mat("FV_riverbank_gravel", (.36, .38, .34), .98)
    trail_mat = mat("FV_riverwalk", (.47, .43, .35), .99)
    for side in (-1, 1):
        edge = _offset_terrain_path(water_points, side*16.2)
        gravel_strip = _add_road_strip(
            world_col, "riverbank_gravel_%s" % ("east" if side < 0 else "west"),
            edge, gravel, width=3.2, bottom_offset=.008, top_offset=.045,
            terrain_conform=True)
        created.append(gravel_strip)
        trail = _offset_terrain_path(water_points, side*21.5)
        trail_strip = _add_road_strip(
            world_col, "riverwalk_%s" % ("east" if side < 0 else "west"),
            trail, trail_mat, width=1.65, bottom_offset=.008, top_offset=.042,
            terrain_conform=True)
        created.append(trail_strip)

    # A deterministic tree/boulder belt frames the water in aerial shots while
    # keeping the bridge sightline and protected future lots open.
    stone = mat("FV_river_boulder", (.30, .32, .31), .98)
    bank_trees = []
    rafting_active = any(b.get("type") == "raftingstation" for b in buildings)
    for index in range(176):
        y = -322.0+index*(1212.0/175.0)
        if abs(y+215.0) < 42.0:
            continue
        side = -1 if index % 2 else 1
        if rafting_active and side < 0 and -78.0 < y < 18.0:
            continue
        rng = random.Random(88000+index*131)
        x = river_center_x(y)+side*(24.0+rng.uniform(1.0, 5.5))
        tree_data = {"type": "tree", "gx": 0, "gy": 0,
                     "px": x, "py": y, "seed": 88000+index}
        tree = place_instance(world_col, tree_data, "riverbank_tree")
        bank_trees.append(tree)
        created.append(tree)
        if index % 5 == 0:
            rock = add_ngon_cone(
                world_col, "riverbank_boulder", .62+rng.random()*.45,
                .42+rng.random()*.28, .65+rng.random()*.55, 7,
                x+side*rng.uniform(1.2, 2.8), y+rng.uniform(-2.4, 2.4),
                terrain_height(x, y)+.02, stone)
            rock.rotation_euler.z = rng.random()*math.tau
            created.append(rock)

    # Founders Crossing: one gently descending viaduct from the completed
    # North Ridge road to Crossing Way. It clears the river by roughly eleven
    # metres at midspan and has continuous guard rails for first-person use.
    start = tuple(bridge["approach"][0])
    end = (410.0, -214.0)
    start_z = terrain_height(*start)+.18
    end_z = terrain_height(*end)+.22
    deck_points = []
    for index in range(9):
        t = index/8.0
        x = start[0]+(end[0]-start[0])*t
        y = start[1]+(end[1]-start[1])*t
        z = start_z+(end_z-start_z)*t
        deck_points.append((x, y, z))
    concrete = mat("FV_bridge_concrete", (.46, .47, .45), .98)
    rail_mat = mat("FV_bridge_rail", (.18, .22, .21), .82)
    timber = mat("FV_rivergate_timber", (.25, .15, .08), .93)
    deck_base = _add_road_strip(
        world_col, "founders_crossing_structure", deck_points, concrete,
        width=8.8, bottom_offset=-.72, top_offset=.02)
    deck = _add_road_strip(
        world_col, "founders_crossing_road", deck_points, m["road"],
        width=7.7, bottom_offset=.025, top_offset=.14)
    created.extend((deck_base, deck))
    for side in (-1, 1):
        rail_points = []
        lower_points = []
        for x, y, z in deck_points:
            rail_points.append((x, y+side*4.12, z+1.25))
            lower_points.append((x, y+side*4.12, z+.68))
        created.append(_add_connected_tube(
            world_col, "founders_crossing_top_rail", rail_points,
            .105, rail_mat, sides=8))
        created.append(_add_connected_tube(
            world_col, "founders_crossing_mid_rail", lower_points,
            .075, rail_mat, sides=8))
        for index in range(17):
            t = index/16.0
            x = start[0]+(end[0]-start[0])*t
            y = start[1]+(end[1]-start[1])*t+side*4.12
            z = start_z+(end_z-start_z)*t
            created.append(_add_connected_tube(
                world_col, "founders_crossing_post",
                ((x, y, z+.12), (x, y, z+1.28)), .075,
                rail_mat, sides=7))

    for x in (319.0, 350.0, 381.0):
        t = (x-start[0])/(end[0]-start[0])
        y = start[1]+(end[1]-start[1])*t
        deck_z = start_z+(end_z-start_z)*t
        ground_z = terrain_height(x, y)
        height = max(.5, deck_z-ground_z-.68)
        pier = add_box(world_col, "founders_crossing_pier", 1.45, 5.4,
                       height, x, y, ground_z, concrete)
        created.append(pier)

    sign_z = terrain_height(405.5, -209.0)
    for sy in (-209.0, -219.0):
        created.append(add_box(world_col, "rivergate_sign_post", .22, .22, 4.05,
                               405.5, sy, sign_z, timber))
    created.append(add_box(world_col, "rivergate_sign_board", .20, 8.6, 1.05,
                           405.5, -214.0, sign_z+2.86, timber))
    created.append(add_text(
        world_col, "rivergate_sign_text", "RIVERGATE", .58, .045,
        405.36, -214.0, sign_z+3.36, m["dash"],
        rotation=(math.pi/2, 0, -math.pi/2)))

    created.extend(build_timber_bend_crossing(world_col, buildings, m,
                                              concrete, rail_mat))
    return [obj for obj in created if obj is not None]


def build_timber_bend_crossing(world_col, buildings, m, concrete, rail_mat):
    """The second crossing: Timber Bend straight into town.

    Everything east of the river used to reach the town only by running 500m
    south to Founders Crossing. This carries the log-house districts west to
    the Kaleidoscope Crest access road instead.

    The centreline, including the arch over the water, comes from
    world_layout.timber_crossing_points() so that the geometry here, the
    browser's walk surface and check_world_geometry all read one description of
    the road rather than three copies that can drift apart.
    """
    if not any(b.get("district") == "Timber Bend" for b in buildings):
        return []
    from world_layout import timber_crossing_points, TIMBER_CROSSING_DECK

    created = []
    points = timber_crossing_points()
    x0, x1 = TIMBER_CROSSING_DECK
    west = [p for p in points if p[0] <= x0]
    deck = [p for p in points if x0 <= p[0] <= x1]
    east = [p for p in points if p[0] >= x1]

    for name, run in (("timber_crossing_west_approach", west),
                      ("timber_crossing_east_approach", east)):
        if len(run) < 2:
            continue
        created.append(_add_road_strip(
            world_col, name, run, m["road"], width=6.5,
            bottom_offset=-.06, top_offset=.08, terrain_conform=True))

    if len(deck) < 2:
        return [obj for obj in created if obj is not None]

    # Deck: a structural slab with the running surface laid on top of it.
    created.append(_add_road_strip(
        world_col, "timber_crossing_structure", deck, concrete,
        width=7.6, bottom_offset=-.62, top_offset=.02, terrain_conform=False))
    created.append(_add_road_strip(
        world_col, "timber_crossing_road", deck, m["road"],
        width=6.5, bottom_offset=.025, top_offset=.13, terrain_conform=False))

    # Continuous guard rails, because this is walked in first person.
    for side in (-1, 1):
        top_rail, mid_rail = [], []
        for x, y, z in deck:
            top_rail.append((x, y+side*3.55, z+1.18))
            mid_rail.append((x, y+side*3.55, z+.64))
        created.append(_add_connected_tube(
            world_col, "timber_crossing_top_rail", top_rail, .10, rail_mat, sides=8))
        created.append(_add_connected_tube(
            world_col, "timber_crossing_mid_rail", mid_rail, .07, rail_mat, sides=8))
        for index in range(0, len(deck), 2):
            x, y, z = deck[index]
            created.append(_add_connected_tube(
                world_col, "timber_crossing_post",
                ((x, y+side*3.55, z+.10), (x, y+side*3.55, z+1.21)), .07,
                rail_mat, sides=7))

    # Piers only where the deck actually stands clear of the ground.
    for index in range(0, len(deck), 4):
        x, y, z = deck[index]
        ground = terrain_height(x, y)
        clear = z-ground-.62
        if clear < .55:
            continue
        created.append(add_box(world_col, "timber_crossing_pier", 1.3, 4.6,
                               clear, x, y, ground, concrete))
    return [obj for obj in created if obj is not None]


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
    access = [(x-cx, y-cy, z) for x, y, z in STORYBOOK_ACCESS]
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
    city_hall_present = any(b.get("type") == "cityhall" for b in buildings)
    civic_square_present = any(b.get("type") == "civicsquare" for b in buildings)
    fishing_pond_present = any(b.get("type") == "fishingpond" for b in buildings)
    weather_station_present = any(b.get("type") == "weatherstation" for b in buildings)
    if city_hall_present:
        active_segments.extend(zip(CITY_HALL_APPROACH, CITY_HALL_APPROACH[1:]))
        active_segments.append((CITY_HALL_APPROACH[-1],
                                (CITY_HALL_X, CITY_HALL_Y + 18.0)))
    # The outpost lane crosses 142m of meadow that scatter would otherwise
    # plant trees on. It was short enough before this to get away with it.
    if any(b.get("type") == "raftingstation" for b in buildings):
        lane = rafting_access_points()
        active_segments.extend(zip(lane, lane[1:]))
    if weather_station_present:
        lane = [(x, y) for x, y, _z in weather_station_access_points()]
        active_segments.extend(zip(lane, lane[1:]))
    salmon_shop_present = any(b.get("type") == "salmonproshop" for b in buildings)
    if salmon_shop_present:
        active_segments.extend(zip(SALMON_SHOP_APPROACH,
                                   SALMON_SHOP_APPROACH[1:]))
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
            if city_hall_present and (
                    abs(point[0] - CITY_HALL_X) < 27.0 and
                    abs(point[1] - CITY_HALL_Y) < 26.0):
                continue
            if civic_square_present and (
                    abs(point[0] - CIVIC_SQUARE_X) < 23.0 and
                    abs(point[1] - CIVIC_SQUARE_Y) < 22.0):
                continue
            if fishing_pond_present and (
                    abs(point[0] - FISHING_POND_X) < FISHING_POND_RX + 6.0 and
                    abs(point[1] - FISHING_POND_Y) < FISHING_POND_RY + 7.0):
                continue
            if weather_station_present and (
                    abs(point[0] - WEATHER_STATION_CENTER[0]) <
                    WEATHER_STATION_HALF_EXTENTS[0] + 5.0 and
                    abs(point[1] - WEATHER_STATION_CENTER[1]) <
                    WEATHER_STATION_HALF_EXTENTS[1] + 5.0):
                continue
            # The store's pad is 56x50 after its quarter turn. Without this a
            # scattered conifer grows straight up through the car park.
            if salmon_shop_present and (
                    abs(point[0] - SALMON_SHOP_X) < 32.0 and
                    abs(point[1] - SALMON_SHOP_Y) < 29.0):
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

    # Crown Quarter has its own traffic scale.  Legacy block extents end south
    # of the new district, so the ordinary traffic pass above can never put a
    # moving vehicle between its towers or on the elevated expressway.
    if any(b.get("type") == "metrotower" for b in buildings):
        metro_routes = (
            ((-215.0, 585.4, METRO_TERRACE_DATUM+.20),
             (185.0, 585.4, METRO_TERRACE_DATUM+.20), 0.0),
            ((185.0, 590.6, METRO_TERRACE_DATUM+.20),
             (-215.0, 590.6, METRO_TERRACE_DATUM+.20), math.pi),
            ((-122.4, 490.0, METRO_TERRACE_DATUM+.20),
             (-122.4, 835.0, METRO_TERRACE_DATUM+.20), math.pi/2),
            ((22.4, 835.0, METRO_TERRACE_DATUM+.20),
             (22.4, 490.0, METRO_TERRACE_DATUM+.20), -math.pi/2),
            ((EXPRESSWAY_X-10.0, EXPRESSWAY_Y0+8.0, EXPRESSWAY_DECK_Z+.22),
             (EXPRESSWAY_X-10.0, EXPRESSWAY_Y1-8.0, EXPRESSWAY_DECK_Z+.22),
             math.pi/2),
            ((EXPRESSWAY_X-6.0, EXPRESSWAY_Y1-8.0, EXPRESSWAY_DECK_Z+.22),
             (EXPRESSWAY_X-6.0, EXPRESSWAY_Y0+8.0, EXPRESSWAY_DECK_Z+.22),
             -math.pi/2),
            ((EXPRESSWAY_X+6.0, EXPRESSWAY_Y0+8.0, EXPRESSWAY_DECK_Z+.22),
             (EXPRESSWAY_X+6.0, EXPRESSWAY_Y1-8.0, EXPRESSWAY_DECK_Z+.22),
             math.pi/2),
            ((EXPRESSWAY_X+10.0, EXPRESSWAY_Y1-8.0, EXPRESSWAY_DECK_Z+.22),
             (EXPRESSWAY_X+10.0, EXPRESSWAY_Y0+8.0, EXPRESSWAY_DECK_Z+.22),
             -math.pi/2),
        )
        for route_index, (start, finish, rotation) in enumerate(metro_routes):
            vehicle = place_instance(
                world_col,
                {"type": "car", "gx": 0, "gy": 0,
                 "seed": 29000+day*19+route_index},
                "metro_moving_traffic")
            vehicle.scale = (.78, .78, .78)
            vehicle.rotation_euler.z = rotation
            vehicle.location = start
            vehicle.keyframe_insert("location", frame=1)
            vehicle.location = finish
            vehicle.keyframe_insert("location", frame=frame_end)
            for fc in obj_fcurves(vehicle):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

def animate_ducks(world_col, buildings, frame_end):
    """Ducks paddle slow loops around every pond in town -- the water version
    of animate_traffic. Ducks aren't saved to world_state; they're
    re-spawned fresh each run from the pond's own seed."""
    ponds = [b for b in buildings if b["type"] in ("pond", "fishingpond")]
    for b in ponds:
        large = b["type"] == "fishingpond"
        cx, cy = build_pos(b) if large else lot_to_world(b["gx"], b["gy"])
        rng = random.Random(5000 + b["seed"])
        n = (5 if large else 2 + rng.randrange(3))
        pond_z = (max(terrain_height(cx + 18.0 * math.cos(math.tau * i / 48),
                                     cy + 11.3 * math.sin(math.tau * i / 48))
                      for i in range(48)) + .18) if large else .02
        for _ in range(n):
            d = {"type": "duck", "gx": 0, "gy": 0, "seed": rng.randrange(999)}
            e = place_instance(world_col, d, "duck")
            r = ((5.0 + rng.random() * 7.0) if large
                 else (1.6 + rng.random() * 1.6))
            a0 = rng.random() * math.tau
            spin = (1 if rng.random() < 0.5 else -1) * (0.5 + rng.random() * 0.4)
            waypoints = 5
            for wp in range(waypoints + 1):
                frame = 1 + (frame_end - 1) * wp / waypoints
                a = a0 + spin * math.tau * wp / waypoints
                e.location = (cx + math.cos(a) * r,
                              cy + math.sin(a) * r * (.62 if large else 1.0),
                              pond_z)
                e.rotation_euler = (0, 0, a + math.pi / 2 * (1 if spin > 0 else -1))
                e.keyframe_insert("location", frame=frame)
                e.keyframe_insert("rotation_euler", frame=frame)
            for fc in obj_fcurves(e):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

def build_fireworks(world_col, cx, cy, frame_end, start_frame=None,
                    end_frame=None, burst_count=6, base_z=28.0,
                    particle_size=1.2, spread=13.0, shards=12,
                    emission=30.0):
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
            bsdf.inputs["Emission Strength"].default_value = emission
        except Exception:
            pass
        fmats.append(fm)
    first = 25 if start_frame is None else int(start_frame)
    last = max(first + 24, frame_end - 100) if end_frame is None else int(end_frame)
    for k in range(burst_count):
        bx = cx + rng.uniform(-26, 26)
        by = cy + rng.uniform(-20, 20)
        # base_z defaults to the historic 28m so every existing caller is
        # unchanged; City Hall's own dome tops out near 28m, so the mayor
        # clip lifts them clear of it rather than bursting through the roof.
        bz = base_z + rng.uniform(0, 12)
        span = max(1, last - first - 22)
        t0 = int(first + span * k / max(1, burst_count - 1) + rng.uniform(0, 5))
        fm = fmats[k % len(fmats)]
        for _ in range(shards):
            th = rng.uniform(0, math.tau)
            ph = math.acos(rng.uniform(-1, 1))
            dx = math.sin(ph) * math.cos(th)
            dy = math.sin(ph) * math.sin(th)
            dz = math.cos(ph)
            # 2026-07-09: particles enlarged (0.75->1.2) + wider spread so the
            # bursts read at drone distance in daylight, not just at sunset
            p = add_ngon_cone(world_col, "fw", particle_size,
                              particle_size * .67, particle_size * 1.17,
                              6, bx, by, bz, fm)
            mid = spread * .65
            p.scale = (0.001, 0.001, 0.001)
            p.keyframe_insert("scale", frame=t0)
            p.keyframe_insert("location", frame=t0)
            p.location = (bx + dx * mid, by + dy * mid, bz + dz * mid)
            p.scale = (1, 1, 1)
            p.keyframe_insert("scale", frame=t0 + 7)
            p.keyframe_insert("location", frame=t0 + 7)
            p.location = (bx + dx * spread, by + dy * spread,
                          bz + dz * spread - 2.0)
            p.scale = (0.001, 0.001, 0.001)
            p.keyframe_insert("scale", frame=t0 + 22)
            p.keyframe_insert("location", frame=t0 + 22)


MAYOR_HANDLE = "@bps_out"


def build_mayor_flyover(world_col, frame_end, handle=MAYOR_HANDLE,
                        y=-142.0, z=54.0, first=70, last=262,
                        x_from=-34.0, x_to=118.0):
    """Render-only: the banner plane that announces Followville's new mayor.

    Nothing here is ever written to world_state.json, the GLB or the Blend --
    it exists only in the video it was made for, exactly like the Day 34
    emergency props. The whole aircraft is parented to one empty so the flight
    is a single animated transform rather than a dozen keyed parts.
    """
    body = mat("NB_plane_body", (.95, .95, .93), .34)
    accent = mat("NB_plane_accent", (.82, .17, .15), .44)
    dark = mat("NB_plane_dark", (.16, .17, .20), .55)
    cloth = mat("NB_banner_cloth", (.86, .16, .15), .74)
    letters = mat("NB_banner_text", (1.0, .97, .88), .38)

    root = bpy.data.objects.new("mayor_plane_root", None)
    world_col.objects.link(root)
    parts = []
    # Nose to tail along +X, which is the direction of flight.
    parts.append(add_box(world_col, "plane_fuselage", 7.6, 1.30, 1.30,
                         0, 0, -.65, body))
    parts.append(add_ngon_cone(world_col, "plane_nose", .65, .06, 1.5, 10,
                               3.8, 0, -.65, accent, rot=0.0))
    parts.append(add_box(world_col, "plane_wing", 2.0, 12.6, .26,
                         -.2, 0, -.16, body))
    parts.append(add_box(world_col, "plane_tailplane", 1.3, 4.6, .22,
                         -3.4, 0, -.10, body))
    parts.append(add_box(world_col, "plane_fin", 1.5, .22, 2.0,
                         -3.5, 0, 0, accent))
    parts.append(add_ngon_cone(world_col, "plane_prop_hub", .28, .22, .35, 8,
                               4.6, 0, -.65, dark))
    parts.append(add_box(world_col, "plane_canopy", 2.2, 1.0, .62,
                         .9, 0, .60, dark))
    # The banner streams behind the tail. Cloth first, then the lettering
    # mounted clear of its face -- coplanar text on its own backing is exactly
    # the depth-fight the visible-surface rule exists to stop.
    parts.append(add_box(world_col, "banner_cloth", 30.0, .12, 4.4,
                         -21.0, 0, -2.2, cloth))
    parts.append(add_box(world_col, "banner_towline", 6.0, .07, .07,
                         -8.6, 0, -.35, dark))
    caption = add_text(world_col, "banner_text", "MAYOR %s" % handle,
                       2.5, .10, -21.0, -.16, 0.0, letters)
    parts.append(caption)
    for part in parts:
        part.parent = root

    # The flight is slow on purpose. A 34mm lens on a 9:16 frame is only about
    # 33 degrees wide, which is roughly 84m of sky at the distance the plane
    # crosses; at a realistic tow speed the banner would be readable for well
    # under a second. This crosses 152m in 6.4s, so it holds the frame for
    # about four of them.
    #
    # The x range is offset east of the camera's aim because the banner trails
    # 21m BEHIND the tug: centring the aircraft puts the words half out of
    # frame, which is exactly how the first render clipped the M off MAYOR.
    root.location = (x_from, y, z)
    root.keyframe_insert("location", frame=first)
    root.location = (x_to, y, z)
    root.keyframe_insert("location", frame=last)
    # Constant speed: a banner tow that eases in and out reads as a zoom.
    for fc in obj_fcurves(root):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    # Hidden before it enters and after it leaves, so no aircraft hangs in the
    # first or last frame of the clip.
    _keyframe_hidden(root, 1, True)
    _keyframe_hidden(root, first, False)
    for part in parts:
        _keyframe_hidden(part, 1, True)
        _keyframe_hidden(part, first, False)
    return [root] + parts


def build_milestone_fireworks(world_col, cx, cy, frame_end):
    """Dusk-friendly radial bursts for Day 24, with retained color and shape."""
    rng = random.Random(40024)
    colors = ((1.0, .22, .30), (1.0, .68, .12), (.22, .58, 1.0),
              (.35, 1.0, .55), (.72, .36, 1.0))
    mats = []
    for index, color in enumerate(colors):
        material = mat("NB_milestone_firework_%d" % index, color, .28)
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            try:
                bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
                bsdf.inputs["Emission Strength"].default_value = 4.5
            except Exception:
                pass
        mats.append(material)
    burst_offsets = ((-20, -5, 35), (15, 7, 39), (-5, -12, 32),
                     (24, -8, 36), (-24, 10, 38), (5, 14, 34),
                     (18, -15, 40), (-10, 3, 37))
    for burst_index, (offset_x, offset_y, burst_z) in enumerate(burst_offsets):
        root = bpy.data.objects.new("milestone_firework_burst", None)
        root.location = (cx + offset_x, cy + offset_y, burst_z)
        world_col.objects.link(root)
        material = mats[burst_index % len(mats)]
        for ray_index in range(14):
            theta = math.tau * ray_index / 14 + rng.uniform(-.11, .11)
            phi = math.acos(rng.uniform(-1.0, 1.0))
            length = rng.uniform(5.0, 8.2)
            end = (length * math.sin(phi) * math.cos(theta),
                   length * math.sin(phi) * math.sin(theta),
                   length * math.cos(phi))
            ray = add_beam_between(world_col, "milestone_firework_ray",
                                   (0, 0, 0), end, .16, material)
            ray.parent = root
        flash = add_uv_sphere(world_col, "milestone_firework_flash", .46,
                              0, 0, 0, material, 6, 10)
        flash.parent = root
        t0 = 500 + burst_index * 11
        root.hide_viewport = True
        root.hide_render = True
        root.keyframe_insert("hide_viewport", frame=1)
        root.keyframe_insert("hide_render", frame=1)
        root.hide_viewport = False
        root.hide_render = False
        root.keyframe_insert("hide_viewport", frame=t0)
        root.keyframe_insert("hide_render", frame=t0)
        root.scale = (.001, .001, .001)
        root.keyframe_insert("scale", frame=t0)
        root.scale = (1.0, 1.0, 1.0)
        root.keyframe_insert("scale", frame=t0 + 8)
        root.scale = (1.22, 1.22, 1.22)
        root.keyframe_insert("scale", frame=t0 + 22)
        root.hide_viewport = True
        root.hide_render = True
        root.keyframe_insert("hide_viewport", frame=t0 + 25)
        root.keyframe_insert("hide_render", frame=t0 + 25)
        for fc in obj_fcurves(root):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"


def build_day24_election_kickoff(world_col, frame_end):
    """Temporary humorous 400-follower election rally for the Day 24 video."""
    rng = random.Random(240400)
    navy = mat("NB_day24_navy", (.055, .12, .27), .72)
    red = mat("NB_day24_red", (.78, .08, .08), .68)
    gold = mat("NB_day24_gold", (.95, .67, .12), .48, .38)
    white = mat("NB_day24_white", (.96, .95, .90), .70)
    wood = mat("NB_day24_podium", (.33, .17, .08), .78)
    dark = mat("NB_day24_dark", (.055, .06, .07), .70)
    skin = mat("NB_day24_skin", (.78, .53, .38), .76)
    shirt_mats = [
        mat("NB_day24_shirt_blue", (.10, .33, .62), .72),
        mat("NB_day24_shirt_green", (.15, .48, .29), .76),
        mat("NB_day24_shirt_red", (.65, .13, .12), .74),
        mat("NB_day24_shirt_gold", (.84, .56, .10), .72),
    ]

    root = bpy.data.objects.new("Day24_ElectionKickoff_RenderOnly", None)
    root.location = (CIVIC_SQUARE_X, CIVIC_SQUARE_Y, 0)
    root["nb_rest_scale"] = (1.0, 1.0, 1.0)
    root["nb_render_only"] = True
    world_col.objects.link(root)
    parts = []

    def attach(obj):
        obj.parent = root
        obj["nb_render_only"] = True
        parts.append(obj)
        return obj

    def local_grade(x, y):
        return terrain_height(CIVIC_SQUARE_X + x, CIVIC_SQUARE_Y + y)

    # The temporary milestone sculpture occupies the permanent event stage.
    stage_z = max(local_grade(x, -11.8 + y)
                  for x in (-6.8, 0, 6.8) for y in (-2.5, 2.5)) + .52
    attach(add_text(world_col, "day24_400", "400", 5.2, .42,
                    0, -13.9, stage_z + 3.1, gold,
                    rotation=(math.pi / 2, 0, math.pi)))
    attach(add_text(world_col, "day24_banner", "400 PEOPLE. 400 MAYORS?",
                    .72, .075, 0, -13.97, stage_z + 7.7, white,
                    rotation=(math.pi / 2, 0, math.pi)))
    banner = attach(add_box(world_col, "day24_banner_board", 21.0, .30, 1.65,
                            0, -14.15, stage_z + 6.9, navy))

    # Three podiums make the joke visible before individual signs can be read.
    for index, x in enumerate((-4.6, 0, 4.6)):
        attach(add_box(world_col, "day24_podium", 2.5, 1.7, 2.7,
                       x, -9.9, stage_z, wood))
        attach(add_box(world_col, "day24_podium_card", 2.1, .12, 1.05,
                       x, -9.00, stage_z + .92,
                       (red, navy, gold)[index]))
        attach(add_text(world_col, "day24_podium_text",
                        ("ME", "ALSO ME", "WHY NOT?")[index],
                        .34 if index != 1 else .27, .045,
                        x, -8.91, stage_z + 1.45, white,
                        rotation=(math.pi / 2, 0, math.pi)))
        attach(add_ngon_cone(world_col, "day24_microphone", .055, .04,
                             1.25, 8, x, -9.75, stage_z + 2.65, dark))

    def add_candidate(index, x, y, sign_text=None):
        z = local_grade(x, y) + .13
        shirt = shirt_mats[index % len(shirt_mats)]
        attach(add_box(world_col, "day24_person_legs", .78, .52, 1.45,
                       x, y, z, dark))
        attach(add_ngon_cone(world_col, "day24_person_body", .72, .48, 1.65,
                             10, x, y, z + 1.42, shirt))
        attach(add_uv_sphere(world_col, "day24_person_head", .43,
                             x, y, z + 3.43, skin, 7, 10))
        if not sign_text:
            return
        pole_z = z + 2.1
        attach(add_ngon_cone(world_col, "day24_sign_pole", .055, .045,
                             2.8, 8, x, y, pole_z, wood))
        attach(add_box(world_col, "day24_campaign_sign", 3.25, .16, 1.38,
                       x, y + .03, pole_z + 2.35,
                       red if index % 2 else navy))
        attach(add_text(world_col, "day24_campaign_text", sign_text,
                        .40 if len(sign_text) < 8 else .30, .045,
                        x, y + .13, pole_z + 3.04, white,
                        rotation=(math.pi / 2, 0, math.pi)))

    sign_people = (
        (-10.5, 4.0, "VOTE ME"),
        (-5.3, 6.2, "NO, ME"),
        (5.2, 6.0, "WHY NOT?"),
        (10.4, 3.7, "FREE SNACKS"),
    )
    for index, (x, y, text) in enumerate(sign_people):
        add_candidate(index, x, y, text)
    for index, (x, y) in enumerate((
            (-12.0, -1.2), (-8.0, -.4), (-3.2, 5.0), (0, 8.2),
            (3.2, 4.6), (8.0, -.2), (12.0, -1.1), (-7.0, 10.7),
            (7.2, 10.5), (-1.8, -3.8), (2.0, -3.7))):
        add_candidate(index + 4, x, y)

    # A few restrained balloons lift above the crowd without obscuring bursts.
    for index, (x, y) in enumerate(((-13, 9), (13, 9), (-9, -5), (9, -5))):
        z = local_grade(x, y)
        attach(add_ngon_cone(world_col, "day24_balloon_string", .018, .014,
                             5.5, 6, x, y, z + .1, white))
        attach(add_uv_sphere(world_col, "day24_balloon", .58, x, y,
                             z + 5.75, (red, gold, navy, red)[index], 7, 10))

    animate_rise(root, 505, dur=28)
    build_milestone_fireworks(world_col, CIVIC_SQUARE_X, CIVIC_SQUARE_Y,
                              frame_end)
    return root


def build_day32_campaign_vignette(world_col, frame_end):
    """Video-only mayoral billboard and moving campaign semi for Day 32."""
    navy = mat("NB_day32_campaign_navy", (.035, .095, .22), .66)
    red = mat("NB_day32_campaign_red", (.72, .055, .07), .62)
    gold = mat("NB_day32_campaign_gold", (.95, .64, .10), .48, .16)
    white = mat("NB_day32_campaign_white", (.97, .96, .91), .60)
    steel = mat("NB_day32_campaign_steel", (.28, .32, .35), .36, .62)
    dark = mat("NB_day32_campaign_dark", (.035, .04, .05), .50)
    glass = mat("NB_day32_campaign_glass", (.20, .42, .53), .16, .12)
    chrome = mat("NB_day32_campaign_chrome", (.62, .67, .70), .24, .78)

    road_angle = math.atan2(247.28592598205583 - 245.70478715197166,
                            557.8577779461675 - 553.114361455915)
    billboard_x, billboard_y = 556.1, 252.5
    billboard = bpy.data.objects.new("Day32_CampaignBillboard_RenderOnly", None)
    billboard.location = (billboard_x, billboard_y,
                          terrain_height(billboard_x, billboard_y))
    billboard.rotation_euler.z = road_angle
    billboard["nb_rest_scale"] = (1.0, 1.0, 1.0)
    billboard["nb_render_only"] = True
    world_col.objects.link(billboard)

    def attach_billboard(obj):
        obj.parent = billboard
        obj["nb_render_only"] = True
        return obj

    for x in (-5.6, 5.6):
        attach_billboard(add_ngon_cone(
            world_col, "day32_billboard_post", .20, .17, 8.8, 8,
            x, 0, 0, steel))
        attach_billboard(add_box(
            world_col, "day32_billboard_foot", 1.0, 1.0, .24,
            x, 0, 0, chrome))
    attach_billboard(add_box(
        world_col, "day32_billboard_board", 16.0, .42, 6.5,
        0, 0, 2.15, navy))
    # The red lower panel and gold frame sit a full five centimetres forward
    # of the navy support face, avoiding the coplanar sign flicker seen in old
    # campaign props.
    attach_billboard(add_box(
        world_col, "day32_billboard_lower_panel", 14.9, .08, 2.35,
        0, -.30, 2.60, red))
    for x in (-7.55, 7.55):
        attach_billboard(add_box(
            world_col, "day32_billboard_side_trim", .22, .08, 6.1,
            x, -.30, 2.35, gold))
    for z in (2.35, 8.23):
        attach_billboard(add_box(
            world_col, "day32_billboard_edge_trim", 15.3, .08, .22,
            0, -.30, z, gold))
    attach_billboard(add_text(
        world_col, "day32_vote_mr_mayor", "VOTE MR MAYOR",
        1.08, .055, 0, -.40, 6.60, white))
    attach_billboard(add_text(
        world_col, "day32_vote_bsb_domwillis", "VOTE BSB_DOMWILLIS",
        .72, .05, 0, -.40, 3.76, white))
    animate_rise(billboard, 382, dur=28)

    truck = bpy.data.objects.new("Day32_CampaignSemi_RenderOnly", None)
    truck["nb_rest_scale"] = (1.0, 1.0, 1.0)
    truck["nb_render_only"] = True
    truck.rotation_euler.z = road_angle
    world_col.objects.link(truck)
    truck_parts = []

    def attach_truck(obj):
        obj.parent = truck
        obj["nb_render_only"] = True
        truck_parts.append(obj)
        return obj

    # Long trailer, detailed tractor, dual rear axles, and a physically raised
    # campaign panel make the vehicle read as a semi instead of a stretched box.
    attach_truck(add_box(world_col, "day32_semi_trailer", 10.8, 2.9, 3.75,
                         1.8, 0, 1.05, white))
    attach_truck(add_box(world_col, "day32_semi_trailer_roof", 11.05, 3.06, .20,
                         1.8, 0, 4.80, chrome))
    attach_truck(add_box(world_col, "day32_semi_chassis", 16.4, 2.45, .42,
                         -1.0, 0, .70, dark))
    attach_truck(add_box(world_col, "day32_semi_cab", 4.3, 2.72, 3.45,
                         -6.0, 0, .82, red))
    attach_truck(add_box(world_col, "day32_semi_sleeper", 2.0, 2.76, 3.70,
                         -3.25, 0, 1.02, navy))
    attach_truck(add_box(world_col, "day32_semi_hood", 2.0, 2.55, 1.45,
                         -9.05, 0, .86, red))
    attach_truck(add_box(world_col, "day32_semi_bumper", .32, 2.72, .46,
                         -10.15, 0, .60, chrome))
    attach_truck(add_box(world_col, "day32_semi_windshield", .12, 2.25, 1.22,
                         -8.12, 0, 2.83, glass))
    attach_truck(add_box(world_col, "day32_semi_side_window", 1.42, .10, 1.18,
                         -6.45, -1.43, 2.78, glass))
    for x in (-8.75, -4.5, .15, 3.5, 5.25):
        for side in (-1, 1):
            wheel = attach_truck(add_ngon_cone(
                world_col, "day32_semi_tire", .62, .62, .34, 12,
                x, side*1.55, .66, dark))
            wheel.rotation_euler.x = side*math.pi/2
            hub = attach_truck(add_ngon_cone(
                world_col, "day32_semi_hub", .28, .28, .37, 12,
                x, side*1.57, .66, chrome))
            hub.rotation_euler.x = side*math.pi/2
    attach_truck(add_box(
        world_col, "day32_semi_campaign_panel", 10.1, .10, 2.55,
        1.8, -1.57, 1.58, navy))
    attach_truck(add_text(
        world_col, "day32_vote_xad_insta", "VOTE XAD_INSTA",
        .88, .055, 1.8, -1.67, 2.86, white))
    attach_truck(add_box(world_col, "day32_semi_campaign_stripe", 10.1, .10, .20,
                         1.8, -1.69, 1.80, gold))
    for y in (-.78, .78):
        attach_truck(add_box(world_col, "day32_semi_headlight", .16, .56, .38,
                             -10.34, y, 1.10, white))

    start = (530.0, 236.2, terrain_height(530.0, 236.2))
    end = (550.2, 244.7, terrain_height(550.2, 244.7))
    truck.location = start
    truck.keyframe_insert("location", frame=470)
    truck.location = end
    truck.keyframe_insert("location", frame=frame_end)
    # Hiding an Empty does not hide its children in final renders. Keyframe the
    # complete vehicle so it enters only for the campaign beat rather than
    # leaking into the earlier house-growth aerial.
    for obj in (truck, *truck_parts):
        _keyframe_hidden(obj, 1, True)
        _keyframe_hidden(obj, 469, True)
        _keyframe_hidden(obj, 470, False)
    for fc in obj_fcurves(truck):
        for kp in fc.keyframe_points:
            if fc.data_path == "location":
                kp.interpolation = "LINEAR"
            else:
                kp.interpolation = "CONSTANT"
    return billboard, truck


def build_day34_fire_response(world_col, buildings, frame_end):
    """Render-only downtown fire and Station 1 response for Day 34.

    Seed 129 is a verified-unclaimed downtown townhouse at (64.5,-38.5).
    Station 1 centers on the same street at (64.5,-70.5), so the response
    remains legible in the background without inventing a route through town.
    """
    target = next((b for b in buildings if int(b.get("seed", -1)) == 129), None)
    station = next((b for b in buildings if b.get("type") == "firestation"), None)
    if not target or target.get("type") != "house":
        raise RuntimeError("Day 34 fire response requires downtown house seed 129")
    if not station or int(station.get("seed", -1)) != 396:
        raise RuntimeError("Day 34 fire response requires canonical Station 1 seed 396")
    target_x, target_y = build_pos(target)
    station_x, station_y = build_pos(station)
    station_center_x = station_x + (SIZE["firestation"] - 1) * LOT / 2
    station_center_y = station_y + (SIZE["firestation"] - 1) * LOT / 2
    if ((target_x, target_y) != (64.5, -38.5)
            or (station_center_x, station_center_y) != (64.5, -70.5)):
        raise RuntimeError("Day 34 fire-response anchors drifted from the audited street")

    red = mat("NB_day34_engine_red", (.80, .025, .018), .58)
    red_dark = mat("NB_day34_engine_dark", (.28, .018, .014), .74)
    white = mat("NB_day34_engine_white", (.94, .93, .87), .66)
    steel = mat("NB_day34_engine_steel", (.38, .42, .44), .34, .62)
    dark = mat("NB_day34_engine_tire", (.025, .03, .035), .72)
    glass = mat("NB_day34_engine_glass", (.08, .24, .34), .12, .10, 1.0, 0.0, .68)
    hot = mat("NB_day34_fire_hot", (1.0, .56, .025), .24)
    flame = mat("NB_day34_fire_flame", (1.0, .105, .008), .28)
    ember = mat("NB_day34_fire_ember", (1.0, .24, .012), .32)
    smoke = mat("NB_day34_fire_smoke", (.10, .095, .085), .98)
    smoke_light = mat("NB_day34_fire_smoke_light", (.24, .22, .19), .98)
    water = mat("NB_day34_hose_water", (.36, .76, .96), .16, .08)
    blue = mat("NB_day34_light_blue", (.05, .30, 1.0), .16)
    emergency_red = mat("NB_day34_light_red", (1.0, .015, .01), .16)
    _set_mat_emission("NB_day34_fire_hot", (1.0, .24, .005), 12.0)
    _set_mat_emission("NB_day34_fire_flame", (1.0, .055, .002), 9.0)
    _set_mat_emission("NB_day34_fire_ember", (1.0, .12, .002), 6.0)
    _set_mat_emission("NB_day34_hose_water", (.14, .52, 1.0), 2.2)
    _set_mat_emission("NB_day34_light_blue", (.02, .16, 1.0), 11.0)
    _set_mat_emission("NB_day34_light_red", (1.0, .005, .002), 11.0)

    truck = bpy.data.objects.new("Day34_FireEngine_RenderOnly", None)
    truck["nb_render_only"] = True
    truck["nb_rest_scale"] = (1.0, 1.0, 1.0)
    truck.rotation_euler.z = math.pi  # authored front -Y drives north/+Y
    world_col.objects.link(truck)
    truck_parts = []

    def attach(obj):
        obj.parent = truck
        obj["nb_render_only"] = True
        truck_parts.append(obj)
        return obj

    attach(add_box(world_col, "day34_engine_chassis", 4.8, 8.4, .48,
                   0, 0, .58, dark))
    attach(add_box(world_col, "day34_engine_body", 4.55, 4.8, 3.15,
                   0, 1.55, .82, red_dark))
    attach(add_box(world_col, "day34_engine_cab", 4.45, 3.15, 3.55,
                   0, -2.55, .82, red))
    attach(add_box(world_col, "day34_engine_windshield", 3.72, .10, 1.18,
                   0, -4.17, 2.70, glass))
    attach(add_box(world_col, "day34_engine_bumper", 4.78, .34, .42,
                   0, -4.40, .66, steel))
    attach(add_box(world_col, "day34_engine_grille", 2.35, .10, .72,
                   0, -4.59, 1.13, dark))
    for side in (-1, 1):
        attach(add_box(world_col, "day34_engine_locker", .12, 3.8, 1.76,
                       side * 2.28, 1.25, 1.42, steel))
        for axle_y in (-2.55, 2.25):
            tire = attach(add_ngon_cone(
                world_col, "day34_engine_tire", .70, .70, .36, 12,
                side * 2.35, axle_y, .70, dark))
            tire.rotation_euler.y = math.pi / 2
            hub = attach(add_ngon_cone(
                world_col, "day34_engine_hub", .30, .30, .39, 12,
                side * 2.37, axle_y, .70, steel))
            hub.rotation_euler.y = math.pi / 2
    attach(add_box(world_col, "day34_engine_ladder", 3.85, .44, .26,
                   0, .35, 4.35, white))
    for y in (-.72, 0, .72, 1.44):
        attach(add_box(world_col, "day34_engine_ladder_rung", 3.85, .09, .09,
                       0, y, 4.42, steel))
    red_light = attach(add_box(world_col, "day34_lightbar_red", 1.05, .42, .28,
                               -.58, -2.55, 4.46, emergency_red))
    blue_light = attach(add_box(world_col, "day34_lightbar_blue", 1.05, .42, .28,
                                .58, -2.55, 4.46, blue))
    for side in (-1, 1):
        attach(add_box(world_col, "day34_engine_headlight", .52, .10, .42,
                       side * 1.58, -4.60, 1.30, white))

    truck.location = (station_center_x, station_center_y - 9.0,
                      terrain_height(station_center_x, station_center_y - 9.0))
    truck.keyframe_insert("location", frame=1)
    truck.keyframe_insert("location", frame=8)
    truck.location = (target_x, target_y - 13.0,
                      terrain_height(target_x, target_y - 13.0))
    truck.keyframe_insert("location", frame=96)
    truck.keyframe_insert("location", frame=frame_end)
    for fc in obj_fcurves(truck):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR" if fc.data_path == "location" else "CONSTANT"
    for frame in range(1, 151, 10):
        red_light.hide_render = (frame // 10) % 2 == 1
        blue_light.hide_render = not red_light.hide_render
        red_light.keyframe_insert("hide_render", frame=frame)
        blue_light.keyframe_insert("hide_render", frame=frame)

    roof_z = 9.65
    for index, (dx, dy, radius, height) in enumerate((
            (-2.5, -.7, 1.25, 4.6), (-1.1, .4, 1.55, 5.8),
            (.5, -.2, 1.35, 5.0), (2.0, .7, 1.20, 4.4),
            (-.2, 1.5, 1.05, 4.1))):
        fire_obj = add_ngon_cone(world_col, "day34_roof_flame", radius, .06,
                                 height, 9, target_x + dx, target_y + dy,
                                 roof_z, flame if index % 2 else hot)
        fire_obj["nb_render_only"] = True
        for frame, scale in ((1, (1.0, .86, 1.0)),
                             (18 + index * 2, (.72, 1.08, 1.28)),
                             (36 + index * 2, (1.12, .78, .88)),
                             (58 + index * 2, (.82, 1.12, 1.20)),
                             (82 + index * 2, (1.0, .86, 1.0)),
                             (120 + index * 2, (.74, 1.04, 1.22)),
                             (150, (1.0, .86, 1.0))):
            fire_obj.scale = scale
            fire_obj.keyframe_insert("scale", frame=frame)
        for fc in obj_fcurves(fire_obj):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

    for index in range(9):
        angle = index * 2.17
        puff = add_uv_sphere(
            world_col, "day34_roof_smoke", 2.5 + (index % 3) * .45,
            target_x + math.cos(angle) * 1.8,
            target_y + math.sin(angle) * 1.3,
            roof_z + 4.0 + index * 1.15,
            smoke if index % 2 else smoke_light, 7, 10)
        puff["nb_render_only"] = True
        puff.scale = (.72, .72, .86)
        puff.keyframe_insert("scale", frame=1)
        puff.keyframe_insert("location", frame=1)
        puff.location.x += math.sin(index * 1.4) * 5.0
        puff.location.y += 2.5 + math.cos(index) * 2.0
        puff.location.z += 12.0 + index * .55
        puff.scale = (1.45, 1.45, 1.85)
        puff.keyframe_insert("location", frame=150)
        puff.keyframe_insert("scale", frame=150)
        for fc in obj_fcurves(puff):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

    for index in range(14):
        angle = index * 2.4
        spark = add_uv_sphere(world_col, "day34_roof_ember", .18 + .05*(index%3),
                              target_x + math.cos(angle) * 2.3,
                              target_y + math.sin(angle) * 1.4,
                              roof_z + 2.0 + index * .26, ember, 5, 7)
        spark["nb_render_only"] = True
        spark.keyframe_insert("location", frame=1)
        spark.location.x += math.sin(index) * 3.0
        spark.location.z += 7.0 + index * .28
        spark.keyframe_insert("location", frame=135)

    nozzle = (target_x, target_y - 10.4, 3.25)
    impact = (target_x, target_y - .45, roof_z + 3.0)
    hose_core = add_beam_between(world_col, "day34_hose_stream",
                                 nozzle, impact, .17, water)
    hose_core["nb_render_only"] = True
    _keyframe_hidden(hose_core, 1, True)
    _keyframe_hidden(hose_core, 99, True)
    _keyframe_hidden(hose_core, 100, False)
    for index in range(11):
        t = (index + .5) / 11.0
        x = nozzle[0]
        y = nozzle[1] + (impact[1] - nozzle[1]) * t
        z = nozzle[2] + (impact[2] - nozzle[2]) * t + math.sin(math.pi*t)*1.5
        drop = add_uv_sphere(world_col, "day34_hose_droplet", .22,
                             x + math.sin(index*1.8)*.18, y, z, water, 5, 7)
        drop["nb_render_only"] = True
        _keyframe_hidden(drop, 1, True)
        _keyframe_hidden(drop, 99, True)
        _keyframe_hidden(drop, 100 + index % 3, False)

    light_data = bpy.data.lights.new("Day34FireGlow", type="POINT")
    light_data.color = (1.0, .12, .015)
    light_data.energy = 1800.0
    light_data.shadow_soft_size = 7.0
    light_obj = bpy.data.objects.new("Day34FireGlow", light_data)
    light_obj.location = (target_x, target_y, roof_z + 4.0)
    light_obj["nb_render_only"] = True
    world_col.objects.link(light_obj)
    return truck

# ═══════════════════════ TIME OF DAY / SEASONS (mood) ═══════════════════════════

TODS = {
    # A complete render preset lives in each row: key, sky, color management
    # and practical-light behavior stay coordinated instead of being adjusted
    # independently until the image turns flat or overexposed.
    "day": dict(
        sun_e=1.00, sun_c=(1.00, .94, .84), sun_rot=(50, 0, 120),
        sun_angle=4.5, fill=.07, sky=(.54, .72, .88), sky_s=1.00,
        sky_mode="nishita", sky_elev=32.0, air=.82, dust=.32, ozone=1.05,
        exposure=.12, win=0.0, darkwin=0.0, lamp=0.0,
        practical=0.0, practical_count=0),
    # Low warm key + physically varied horizon. The blue skylight remains
    # strong enough to preserve Followville's palette in the shadows.
    "sunset": dict(
        sun_e=1.20, sun_c=(1.00, .56, .28), sun_rot=(78, 0, 102),
        sun_angle=3.2, fill=.045, sky=(.30, .46, .72), sky_s=.68,
        sky_mode="nishita", sky_elev=4.5, air=1.05, dust=1.35, ozone=1.12,
        exposure=.28, win=1.15, darkwin=.28, lamp=3.0, practical=85.0,
        practical_count=20),
    "dusk": dict(
        sun_e=.38, sun_c=(1.00, .46, .24), sun_rot=(82, 0, 108),
        sun_angle=5.5, fill=.09, sky=(.09, .14, .28), sky_s=.33,
        sky_mode="color", exposure=.58, win=3.2, darkwin=1.05, lamp=8.0,
        practical=180.0, practical_count=32),
    # Moonlight establishes form; actual pools from existing streetlights and
    # controlled emissive windows make the city inhabited without bleaching it.
    "night": dict(
        sun_e=.24, sun_c=(.46, .58, 1.00), sun_rot=(48, 0, 142),
        sun_angle=7.5, fill=.20, sky=(.028, .050, .115), sky_s=.30,
        sky_mode="color", exposure=1.35, win=6.2, darkwin=2.1, lamp=14.0,
        practical=650.0, practical_count=60),
    "storm": dict(
        sun_e=.38, sun_c=(.60, .70, .86), sun_rot=(58, 0, 132),
        sun_angle=8.0, fill=.10, sky=(.075, .105, .16), sky_s=.34,
        sky_mode="color", exposure=.35, win=2.4, darkwin=.65, lamp=7.0,
        practical=120.0, practical_count=26),
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
    _set_mat_emission("NB_windark", (.62, .76, 1.0), t["darkwin"])
    _set_mat_emission("NB_bulb", (1.0, 0.90, 0.65), t["lamp"])
    # These are authored practical surfaces, not every pane of blue glass.
    # Emitting whole tower curtain walls would erase their nighttime massing.
    for name in ("NB_cinema_warm_light", "NB_coffee_warm_light",
                 "NB_salmon_warm_light", "NB_fire_warm_light",
                 "FV_metro_lobby_glow", "FV_metro_shop_light",
                 "FV_expressway_light_warm"):
        _set_mat_emission(name, (1.0, .73, .38), t["lamp"] * .48)
    for name, rgb in SEASONS.get(season, SEASONS["summer"]).items():
        _set_mat_color(name, rgb)


def _configure_video_sky(tod, preset=None):
    """Build a clean sky shader for the selected video preset.

    No Volume Scatter node is created here. Earlier footage demonstrated that
    camera-facing or dense volumetric fog can become a literal wall; atmospheric
    depth now comes from the procedural horizon and ordinary aerial perspective.
    """
    t = preset or TODS.get(tod, TODS["day"])
    world = bpy.context.scene.world or bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    background = nodes.new("ShaderNodeBackground")
    background.name = "Followville Video Background"
    background.inputs[1].default_value = t["sky_s"]
    links.new(background.outputs["Background"], output.inputs["Surface"])
    if t["sky_mode"] == "nishita":
        sky = nodes.new("ShaderNodeTexSky")
        sky.name = "Followville Procedural Horizon"
        # Blender 5 names the Nishita-derived model MULTIPLE_SCATTERING;
        # Blender 4.x exposed it as NISHITA. Keep the preset portable.
        for sky_type in ("MULTIPLE_SCATTERING", "NISHITA"):
            try:
                sky.sky_type = sky_type
                break
            except TypeError:
                continue
        sky.sun_elevation = math.radians(t["sky_elev"])
        sky.sun_rotation = math.radians(t["sun_rot"][2])
        sky.altitude = .18
        sky.air_density = t["air"]
        if hasattr(sky, "aerosol_density"):
            sky.aerosol_density = t["dust"]
        else:
            sky.dust_density = t["dust"]
        sky.ozone_density = t["ozone"]
        links.new(sky.outputs["Color"], background.inputs[0])
    else:
        background.inputs[0].default_value = (*t["sky"], 1.0)
    world.color = t["sky"]


def _build_video_practicals(world_col, tod):
    """Add sparse render-only light pools beneath existing streetlights."""
    t = TODS.get(tod, TODS["day"])
    limit = int(t["practical_count"])
    if limit <= 0 or t["practical"] <= 0:
        return []
    candidates = []
    for obj in world_col.objects:
        name = obj.name.lower()
        collection_name = (obj.instance_collection.name.lower()
                           if obj.instance_collection else "")
        if ("suburban_light" in name or "metro_streetlight" in name
                or "ast_light" in collection_name):
            candidates.append(obj)
    # Greedy spacing produces an even city-wide sample and caps Eevee's light
    # count. The emissive lamp heads still appear at every other fixture.
    selected = []
    min_spacing = 40.0 if tod == "night" else 62.0
    for obj in sorted(candidates, key=lambda item: (item.location.y,
                                                    item.location.x,
                                                    item.name)):
        x, y = obj.location.x, obj.location.y
        if all(math.hypot(x-p.location.x, y-p.location.y) >= min_spacing
               for p in selected):
            selected.append(obj)
            if len(selected) >= limit:
                break
    lights = []
    for index, fixture in enumerate(selected):
        data = bpy.data.lights.new("VideoStreetPool_%02d" % index, "POINT")
        data.color = (1.0, .66, .32)
        data.energy = t["practical"]
        data.shadow_soft_size = 2.2
        data.use_shadow = False
        light = bpy.data.objects.new("VideoStreetPool_%02d" % index, data)
        light.location = (fixture.location.x, fixture.location.y,
                          fixture.location.z + 4.15)
        light["nb_render_only"] = True
        light["nb_feature_role"] = "video-lighting"
        world_col.objects.link(light)
        lights.append(light)
    return lights

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


def animate_road_extend(empty, f_start, dur=36):
    """Reveal a southbound road from its existing-grid connection."""
    rest = tuple(empty.get("nb_rest_scale", empty.scale))
    _keyframe_hidden(empty, 1, True)
    _keyframe_hidden(empty, f_start, False)
    empty.scale = (rest[0], max(.001, rest[1] * .001), rest[2])
    empty.keyframe_insert("scale", frame=f_start)
    empty.scale = rest
    empty.keyframe_insert("scale", frame=f_start + dur)
    for fc in obj_fcurves(empty):
        if fc.data_path == "scale":
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.easing = "EASE_OUT"


def animate_road_build(obj, f_start, dur=90, reverse=False):
    """Draw a suburban road ribbon ON along its own length.

    animate_road_extend() cannot do this. It scales the object, and a suburban
    street built by _add_road_strip holds its vertices in WORLD space with the
    object origin left at (0,0,0) -- scaling one would sling it across the map
    rather than shorten it. The ribbon's faces are, however, generated in order
    along the centreline, so Blender's Build modifier reveals them end to end,
    which is exactly "the road arrives" rather than "the road pops in".

    Complete long before frame_end, or export_web bakes a half-built street:
    the exporter evaluates the depsgraph at the last frame.
    """
    if obj is None or obj.type != "MESH":
        return
    mod = obj.modifiers.new("nb_road_build", "BUILD")
    mod.frame_start = f_start
    mod.frame_duration = max(1, dur)
    mod.use_random_order = False
    mod.use_reverse = reverse


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

def build_godzilla_attack(world_col, buildings, building_roots, frame_end):
    """Build a temporary monster attack and knock down the rendered town.

    The attack is generated only during ``--replay --godzilla``. It never
    changes world_state.json, exported web assets, or the saved Blend scene.
    """
    _town_cx, _town_cy, ext = city_center_and_extent(buildings)
    # The matched camera is a downtown-forward skyline composition, so the
    # attack must cross that same visible corridor instead of the geometric
    # midpoint between far-flung suburban districts.
    cx, cy = -3.0, -3.0
    green = mat("NB_godzilla_green", (0.10, 0.23, 0.12), .94)
    belly = mat("NB_godzilla_belly", (0.28, 0.36, 0.20), .92)
    dark = mat("NB_godzilla_dark", (0.025, 0.045, 0.03), .88)
    eye = mat("NB_godzilla_eye", (0.95, 0.78, 0.12), .34)
    mouth = mat("NB_godzilla_mouth", (0.38, 0.035, 0.035), .7)
    atomic = mat("NB_atomic_breath", (0.10, 0.68, 1.0), .18, .08)
    dust = mat("NB_attack_dust", (0.42, 0.36, 0.29), 1.0)
    smoke = mat("NB_attack_smoke", (0.13, 0.12, 0.105), 1.0)
    fire = mat("NB_attack_fire", (1.0, 0.24, 0.015), .35)
    flash = mat("NB_attack_flash", (1.0, 0.78, 0.16), .24)
    ember = mat("NB_attack_ember", (1.0, 0.18, 0.025), .42)
    _set_mat_emission("NB_atomic_breath", (0.08, 0.70, 1.0), 9.0)
    _set_mat_emission("NB_attack_fire", (1.0, 0.07, 0.005), 8.0)
    _set_mat_emission("NB_attack_flash", (1.0, 0.55, 0.04), 14.0)
    _set_mat_emission("NB_attack_ember", (1.0, 0.08, 0.01), 5.0)

    monster = bpy.data.objects.new("Godzilla_RenderOnly", None)
    world_col.objects.link(monster)
    parts = []

    def sphere(name, radius, x, y, z, material, scale=(1, 1, 1)):
        obj = add_uv_sphere(world_col, name, radius, x, y, z, material, 10, 16)
        obj.scale = scale
        parts.append(obj)
        return obj

    sphere("godzilla_pelvis", 8.0, 0, 0, 23, green, (1.0, .72, 1.05))
    sphere("godzilla_torso", 11.5, 0, 0, 36, green, (.82, .68, 1.25))
    sphere("godzilla_belly", 8.1, 0, -5.5, 34, belly, (.62, .25, 1.15))
    sphere("godzilla_neck", 7.0, 0, 0, 47, green, (.76, .72, 1.15))
    sphere("godzilla_head", 8.0, 0, -1.0, 55, green, (1.0, .88, .86))
    parts.append(add_box(world_col, "godzilla_snout", 10.5, 10.0, 4.8,
                         0, -6.0, 51.0, green))
    parts.append(add_box(world_col, "godzilla_mouth", 9.2, 8.8, .65,
                         0, -7.1, 50.7, mouth))
    for side in (-1, 1):
        sphere("godzilla_eye", 1.15, side * 3.35, -7.0, 56.2, eye, (1, .55, 1))
        sphere("godzilla_pupil", .46, side * 3.35, -7.62, 56.25, dark, (1, .4, 1))
        parts.append(add_beam_between(world_col, "godzilla_leg",
                                      (side * 5.6, 0, 24),
                                      (side * 7.0, -1.0, 7.0), 6.4, green))
        parts.append(add_box(world_col, "godzilla_foot", 9.0, 14.0, 4.0,
                             side * 7.0, -5.0, 1.0, green))
        parts.append(add_beam_between(world_col, "godzilla_arm",
                                      (side * 7.2, -1.0, 42.0),
                                      (side * 13.0, -7.5, 30.0), 4.2, green))
        claw = sphere("godzilla_claw", 3.0, side * 13.0, -8.0, 28.5,
                      green, (1.0, .78, .65))
        for finger in (-1.4, 0, 1.4):
            parts.append(add_ngon_cone(world_col, "godzilla_finger",
                                        .55, 0, 3.2, 7,
                                        side * 13.0 + finger,
                                        -10.1, 27.3, dark))

    # Heavy segmented tail and pale dorsal plates make the silhouette read at
    # whole-city scale without importing or permanently storing an asset.
    for i in range(8):
        t = i / 7.0
        sphere("godzilla_tail", 6.2 * (1.0 - .68 * t),
               0, 7.0 + i * 7.0, 25.0 - i * 2.45,
               green, (1.0, 1.35, .82))
    for i, z in enumerate(range(20, 55, 5)):
        spike = add_ngon_cone(world_col, "godzilla_dorsal_plate",
                              4.8 - abs(37 - z) * .08, 0,
                              8.0 + (3 if 29 <= z <= 44 else 0), 5,
                              0, 6.0, z, dark, math.radians(18))
        spike.rotation_euler.x = math.radians(90)
        parts.append(spike)

    for obj in parts:
        obj.parent = monster
    monster.rotation_euler = (0, 0, math.radians(-45))
    start = (cx + ext * .62, cy + ext * .48, 0)
    monster.location = start
    monster.keyframe_insert("location", frame=1)
    monster.keyframe_insert("rotation_euler", frame=1)
    monster.location = start
    monster.keyframe_insert("location", frame=55)
    monster.location = (cx + ext * .27, cy + ext * .20, 0)
    monster.rotation_euler.z = math.radians(-38)
    monster.keyframe_insert("location", frame=145)
    monster.keyframe_insert("rotation_euler", frame=145)
    monster.location = (cx + 18.0, cy + 10.0, 0)
    monster.rotation_euler.z = math.radians(-30)
    monster.keyframe_insert("location", frame=235)
    monster.keyframe_insert("rotation_euler", frame=235)
    monster.location = (cx + 5.0, cy - 4.0, 1.5)
    monster.keyframe_insert("location", frame=frame_end)
    for fc in obj_fcurves(monster):
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"

    # Atomic breath sweeps through the middle of town immediately before the
    # destruction wave. The beam, dust, embers, and debris are render-only.
    beam = add_beam_between(world_col, "godzilla_atomic_breath",
                            (0, -11, 51), (-10, -150, 3), 3.1, atomic)
    beam.parent = monster
    _keyframe_hidden(beam, 1, True)
    _keyframe_hidden(beam, 168, False)
    _keyframe_hidden(beam, 224, True)

    attack_start = 178
    max_radius = max(ext * .65, 1.0)
    for index, (building, root) in enumerate(zip(buildings, building_roots)):
        bx, by = build_pos(building)
        dx, dy = bx - cx, by - cy
        distance = math.sqrt(dx * dx + dy * dy)
        hit = min(frame_end - 35, attack_start + int(92 * distance / max_radius))
        root.keyframe_insert("location", frame=max(1, hit - 1))
        root.keyframe_insert("rotation_euler", frame=max(1, hit - 1))
        direction = Vector((dx, dy, 0))
        if direction.length < .1:
            direction = Vector((1, 0, 0))
        direction.normalize()
        toss = 5.0 + (index % 7) * 1.5
        root.location.x += direction.x * toss
        root.location.y += direction.y * toss
        root.location.z -= 3.0 + (index % 4)
        root.rotation_euler.x += (.55 + (index % 5) * .23) * (-1 if index % 2 else 1)
        root.rotation_euler.y += (.42 + (index % 3) * .31) * (-1 if index % 3 else 1)
        root.rotation_euler.z += direction.x * .35
        root.keyframe_insert("location", frame=hit + 28)
        root.keyframe_insert("rotation_euler", frame=hit + 28)
        for fc in obj_fcurves(root):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"

    blast_buildings = buildings[::max(1, len(buildings) // 12)][:12]
    for i, building in enumerate(blast_buildings):
        x, y = build_pos(building)
        blast_frame = attack_start + i * 8
        core = add_uv_sphere(world_col, "attack_flash", 5.5,
                             x, y, 5.0, flash, 7, 10)
        core.scale = (.03, .03, .03)
        core.keyframe_insert("scale", frame=max(1, blast_frame - 1))
        core.scale = (2.1, 2.1, 2.1)
        core.keyframe_insert("scale", frame=blast_frame + 5)
        core.scale = (.08, .08, .08)
        core.keyframe_insert("scale", frame=blast_frame + 16)

        fireball = add_uv_sphere(world_col, "attack_fireball", 7.0,
                                 x, y, 4.5, fire, 7, 11)
        fireball.scale = (.03, .03, .03)
        fireball.keyframe_insert("scale", frame=blast_frame)
        fireball.scale = (1.45, 1.45, 1.75)
        fireball.keyframe_insert("scale", frame=blast_frame + 12)
        fireball.location.z += 8.0
        fireball.scale = (.25, .25, .35)
        fireball.keyframe_insert("location", frame=blast_frame + 34)
        fireball.keyframe_insert("scale", frame=blast_frame + 34)

        plume = add_uv_sphere(world_col, "attack_smoke_plume", 8.0,
                              x, y, 7.0, smoke, 7, 10)
        plume.scale = (.04, .04, .04)
        plume.keyframe_insert("scale", frame=blast_frame + 5)
        plume.scale = (.78, .78, 1.22)
        plume.location.x += math.cos(i * 1.7) * 5.0
        plume.location.y += math.sin(i * 1.7) * 5.0
        plume.location.z += 17.0
        plume.keyframe_insert("location", frame=min(frame_end, blast_frame + 62))
        plume.keyframe_insert("scale", frame=min(frame_end, blast_frame + 62))

        shock = add_uv_sphere(world_col, "attack_shockwave", 6.0,
                              x, y, 1.0, flash, 5, 12)
        shock.scale = (.08, .08, .025)
        shock.keyframe_insert("scale", frame=blast_frame)
        shock.scale = (4.8, 4.8, .035)
        shock.keyframe_insert("scale", frame=blast_frame + 20)
        shock.scale = (.02, .02, .01)
        shock.keyframe_insert("scale", frame=blast_frame + 30)

        light_data = bpy.data.lights.new("AttackFlash", type="POINT")
        light_data.color = (1.0, .24, .035)
        light_data.energy = 0.0
        light_data.keyframe_insert("energy", frame=max(1, blast_frame - 1))
        light_data.energy = 8500.0
        light_data.keyframe_insert("energy", frame=blast_frame + 2)
        light_data.energy = 0.0
        light_data.keyframe_insert("energy", frame=blast_frame + 12)
        light_obj = bpy.data.objects.new("AttackFlash", light_data)
        light_obj.location = (x, y, 13.0)
        world_col.objects.link(light_obj)

        for j in range(4):
            debris = add_box(world_col, "attack_debris", 2.2, 1.6, 1.4,
                             x, y, 1.2, dark)
            debris.rotation_euler = (j * .4, j * .7, j * .9)
            debris.keyframe_insert("location", frame=blast_frame)
            debris.keyframe_insert("rotation_euler", frame=blast_frame)
            debris.location = (x + math.cos(i + j) * (12 + 4 * j),
                               y + math.sin(i + j) * (12 + 4 * j),
                               12.0 + 5.0 * j)
            debris.rotation_euler = (2.2 + j, 1.4 + i * .2, 3.1 + j)
            debris.keyframe_insert("location", frame=blast_frame + 20)
            debris.keyframe_insert("rotation_euler", frame=blast_frame + 20)
            debris.location.z = -2.0
            debris.keyframe_insert("location", frame=blast_frame + 48)

        for obj in (core, fireball, plume, shock):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"

    for i in range(26):
        angle = math.tau * i / 26.0
        radius = ext * (.06 + .34 * ((i % 9) / 8.0))
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        cloud = add_uv_sphere(world_col, "attack_dust", 5.0 + i % 4,
                              x, y, 2.0 + i % 3, dust, 6, 9)
        cloud.scale = (.02, .02, .02)
        cloud.keyframe_insert("scale", frame=attack_start + i * 3)
        cloud.scale = (1.28, 1.28, .82)
        cloud.keyframe_insert("scale", frame=min(frame_end, attack_start + 65 + i * 3))
        for fc in obj_fcurves(cloud):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
        if i % 3 == 0:
            spark = add_ngon_cone(world_col, "attack_ember", 1.4, 0, 8.0, 7,
                                  x, y, 2.5, ember)
            spark.scale = (.05, .05, .05)
            spark.keyframe_insert("scale", frame=attack_start + i * 3)
            spark.scale = (1, 1, 1)
            spark.keyframe_insert("scale", frame=min(frame_end, attack_start + 38 + i * 3))

def build_background_ground(world_col, material, center_x, center_y):
    """Surround the authored terrain without putting another face beneath it.

    The former 4,000m square ground box ended at z=0.  Large areas of the
    regional terrain also clamp to z=0, so the two grass faces were exactly
    coplanar under the city.  A moving aerial camera made the depth buffer
    alternate between them as bright/dark square platforms.  Four perimeter
    slabs preserve the distant horizon while their horizontal faces only
    touch the regional terrain at its outer boundary; they never overlap it.
    """
    terrain_x0, terrain_x1, terrain_y0, terrain_y1 = TERRAIN_BOUNDS
    # Keep the physical horizon outside every production camera's far clip.
    # At 2km the slab's outer vertical face read as a black stripe in Day 43's
    # low sunset previews even though the nearby West Quarter seam was closed.
    # Four 100km boxes add no top-surface tessellation and make the horizon real
    # ground from every planned low angle instead of a framing assumption.
    half_extent = 50000.0
    outer_x0 = min(center_x - half_extent, terrain_x0)
    outer_x1 = max(center_x + half_extent, terrain_x1)
    outer_y0 = min(center_y - half_extent, terrain_y0)
    outer_y1 = max(center_y + half_extent, terrain_y1)
    slab_bottom = -0.10
    slab_height = 0.10
    # The regional mesh now has a real perimeter skirt.  Meet it exactly:
    # sharing an edge has no coplanar area, while the former 5cm clearance was
    # an actual open hole visible in Day 42's western turn.
    boundary_gap = 0.0

    rectangles = (
        ("ground_west", outer_x0, terrain_x0 - boundary_gap, outer_y0, outer_y1),
        ("ground_east", terrain_x1 + boundary_gap, outer_x1, outer_y0, outer_y1),
        ("ground_south", terrain_x0, terrain_x1, outer_y0,
         terrain_y0 - boundary_gap),
        ("ground_north", terrain_x0, terrain_x1, terrain_y1 + boundary_gap,
         outer_y1),
    )
    for name, x0, x1, y0, y1 in rectangles:
        if x1 <= x0 or y1 <= y0:
            raise AssertionError("Invalid background-ground rectangle: %s" % name)
        overlap_x = min(x1, terrain_x1) - max(x0, terrain_x0)
        overlap_y = min(y1, terrain_y1) - max(y0, terrain_y0)
        if overlap_x > 1e-6 and overlap_y > 1e-6:
            raise AssertionError(
                "%s overlaps the regional terrain footprint" % name)
        obj = add_box(
            world_col, name, x1 - x0, y1 - y0, slab_height,
            (x0 + x1) / 2, (y0 + y1) / 2, slab_bottom, material)
        obj["fv_background_ground"] = True


# Day 40's reveal is the first clip in the project made of two shots rather
# than one unbroken camera move: the drone run ends at DAY40_GAS_CUT - 1 and the
# filling station gets the rest to itself. Both the camera rig and the rise
# schedule key off this, and they are built in different functions, so it lives
# here rather than being written out twice.
DAY40_GAS_CUT = 631

# Day 48's street run, as (frame, camera x) on the Wheelwright centreline. The
# camera rig keyframes these positions with LINEAR interpolation and the rise
# schedule inverts the same table to find the frame at which the lens reaches a
# given x. Two copies of these numbers would silently drift apart, and the
# symptom -- homes rising just outside a 9:16 frame -- is invisible until the
# render is finished, so there is exactly one copy.
DAY48_CAM_KNOTS = ((1, -196.0), (70, -240.0), (130, -290.0), (465, -636.0))
# How far ahead of the lens a home stands up, keyed by its distance from the
# y=774 centreline. Derived from the horizontal half-angle at 24mm in 9:16:
# required depth is (offset + 5m half-width) / tan(atan(10.125/24)).
DAY48_WAVE_LEAD = {8.5: 46.0, 27.5: 96.0, 44.5: 146.0}
# The far west of the block would otherwise rise as late as frame 515, after
# the camera has already begun its turn. Frames past the knee are compressed so
# the wave finishes at 440. Compression only ever moves a home EARLIER, which
# means more depth than the lead asked for, so it cannot push one off screen.
DAY48_WAVE_KNEE, DAY48_WAVE_SQUEEZE = 340.0, 0.57


def day48_frame_at_x(x):
    """Frame at which the day48crown camera reaches world x.

    Past the last knot the answer is extrapolated at the run's own rate rather
    than refused. The far end of the block wants to rise as late as frame 515 --
    past the end of the street run -- and that number is real input to the
    squeeze below, which pulls it back to a frame the camera is actually alive
    for. Refusing it here would be refusing to answer the question that makes
    the squeeze correct. East of the first knot there is no answer to give.
    """
    if x > DAY48_CAM_KNOTS[0][1]:
        return None
    for (f0, x0), (f1, x1) in zip(DAY48_CAM_KNOTS, DAY48_CAM_KNOTS[1:]):
        if x1 <= x <= x0:
            return f0 + (f1 - f0) * (x - x0) / (x1 - x0)
    (f0, x0), (f1, x1) = DAY48_CAM_KNOTS[-2], DAY48_CAM_KNOTS[-1]
    return f1 + (x - x1) * (f1 - f0) / (x1 - x0)

# -- Day 49: the North Reach wave --------------------------------------------
#
# Day 49 is the first growth that crosses y=824. Crown Quarter's own six
# north/south streets stop being the city's boundary and run on into open land,
# and 152 homes stand up along five of them. The sixth, Anvil Avenue North
# (x=160), gets nothing: the count runs out ten homes into Quarry Avenue North 2.
#
# The five streets that DO build, as centrelines, with houses 8.5m either side:
DAY49_RIBBON_X = (-190.0, -120.0, -50.0, 20.0, 90.0)
# Maple Avenue North is the exact middle of those five, which is why the street
# run flies it: the outer ribbons sit symmetrically at +/-140m and +/-70m, so
# one line reaches every home in the growth.
DAY49_STREET_X = -50.0
# The camera's northbound path as (frame, camera y). Same contract as
# DAY48_CAM_KNOTS: the rig keyframes these positions with LINEAR interpolation
# on Y and the wave inverts this same table to find when the lens reaches a
# given northing. One copy of the numbers, never two.
DAY49_CAM_KNOTS = ((1, 350.0), (80, 455.0), (200, 700.0),
                   (260, 830.0), (545, 1122.0))
# How far ahead of the lens a home stands up, keyed by its distance from the
# Maple Avenue North centreline. 9:16 makes the HORIZONTAL field the narrow one
# -- the 36mm sensor lands on the 1920 axis, so the horizontal half-width is
# 10.125mm -- and the depth at which a home first enters frame at all is
# (offset + 5m half-width) / tan(atan(10.125/L)).
#
# Those bare minima are 32m / 158m / 198m / 323m / 364m at 24mm. The leads below
# are NOT those numbers. The first cut of this shot used them plus a few metres
# and passed the on-screen test 152/152 -- while putting seven West Market homes
# at u=0.03, three per cent from the left edge and 330m out, which is "on
# screen" in the way a pixel is on screen. Each lead is set so its home enters
# at roughly u=0.13, about a quarter of the way in from the frame edge, which is
# where a house at that distance is actually legible as a house appearing.
# Verified end to end by verify_day49_camera.py, which reads the rise frames out
# of the installed animation rather than back off this table.
DAY49_WAVE_LEAD = {8.5: 46.0, 61.5: 215.0, 78.5: 260.0,
                   131.5: 360.0, 148.5: 405.0}


def day49_frame_at_y(y):
    """Frame at which the day49northreach camera reaches world y.

    South of the first knot there is no answer -- the camera has not started.
    North of the last one the answer is extrapolated at the street run's own
    rate rather than refused, for the same reason day48_frame_at_x extrapolates:
    the far end of the block genuinely wants to rise after the run ends, and
    that number is real input to the squeeze that pulls it back into frames the
    camera is actually alive for.
    """
    if y < DAY49_CAM_KNOTS[0][1]:
        return None
    for (f0, y0), (f1, y1) in zip(DAY49_CAM_KNOTS, DAY49_CAM_KNOTS[1:]):
        if y0 <= y <= y1:
            return f0 + (f1 - f0) * (y - y0) / (y1 - y0)
    (f0, y0), (f1, y1) = DAY49_CAM_KNOTS[-2], DAY49_CAM_KNOTS[-1]
    return f1 + (y - y1) * (f1 - f0) / (y1 - y0)


# The last homes on Maple would otherwise rise at 533 and finish at 555, ten
# frames into the climb-out. Frames past the knee are compressed so the whole
# wave finishes and is held before the camera leaves the street. Compression
# only ever moves a home EARLIER, which means more depth than the lead asked
# for, so it can never push one out of the narrow horizontal frame.
DAY49_WAVE_KNEE, DAY49_WAVE_SQUEEZE = 430.0, 0.80

# -- Day 50: Quarry / Anvil growth and the highway reveal --------------------
#
# The next fifty ordinary-house addresses are not one homogeneous row: thirteen
# finish Quarry Avenue North, twenty-eight fill Anvil Avenue North, and nine
# begin Gateway Row. Ordinary growth deliberately steps over that stretch's
# reserved pond and Followmart parcels; they stay empty until explicitly built.
# The camera flies between Quarry and Anvil; Gateway rises during the wide
# opening while the lens still has enough depth to hold its large lateral offset.
DAY50_STREET_X = 125.0
DAY50_CAM_KNOTS = ((1, 300.0), (100, 500.0), (200, 750.0),
                   (260, 850.0), (500, 1100.0))
DAY50_WAVE_LEAD = {23.6: 90.0, 26.5: 100.0, 43.5: 165.0, 57.2: 210.0}


def day50_frame_at_y(y):
    """Frame at which the linear part of day50highway reaches world y."""
    if y < DAY50_CAM_KNOTS[0][1]:
        return None
    for (f0, y0), (f1, y1) in zip(DAY50_CAM_KNOTS, DAY50_CAM_KNOTS[1:]):
        if y0 <= y <= y1:
            return f0 + (f1 - f0) * (y - y0) / (y1 - y0)
    (f0, y0), (f1, y1) = DAY50_CAM_KNOTS[-2], DAY50_CAM_KNOTS[-1]
    return f1 + (y - y1) * (f1 - f0) / (y1 - y0)

DAY40_GAS_X, DAY40_GAS_Y = 118.25, 319.70

# ═══════════════ FOLLOWVILLE STORIES #001 -- "The Price Sign" ═══════════════
#
# The first Followville Story: the filling station opens, the price collapses,
# the town drains it dry in a day. Two render-only cameras, four shots in the
# day clip and one at dusk. See FOLLOWVILLE_STORIES.md.
#
# Render-only, exactly like --godzilla and the Day 34 emergency props: this
# layer never writes world_state.json, never exports a GLB and never saves the
# Blend. Run it on --replay.
#
# The station is ONE merged mesh. build_gas_station ends in _merge_asset_meshes,
# so gas_totem_price and gas_downlight do not exist as objects at render time
# and cannot be animated in place. Everything below is therefore an OVERLAY
# standing proud of the merged geometry, never a flush repaint of it -- a plate
# laid exactly on the board's face would put two visible faces on one plane,
# which the depth rule forbids.
#
# Station local -> world is +(118.25, 319.70), rot 0, front on local -Y. The
# whole Northgate quarter is a level shelf, so terrain here is a flat 5.0 and
# every z below is measured off it.
STORY001_SHELF = 5.0
STORY001_TOTEM_X = DAY40_GAS_X + 6.45          # TOT_X
STORY001_PRICE_Y = DAY40_GAS_Y - 7.45          # 0.44m proud of the board face
# add_box's z is the BOTTOM of the box, so gas_totem_price spans 3.86 to 4.48
# and its middle is 4.17. The text is align_y CENTER, so it has to be placed at
# the middle -- placing it at 3.86 hangs the number off the bottom of the board.
STORY001_PRICE_Z = STORY001_SHELF + 4.17
STORY001_SWAP = 115                            # frame the price drops


def _story001_plate(world_col, name, body, size, colour, emission=0.0):
    """One price readout standing in front of the totem's merged board.

    A FONT curve rather than geometry: the joke is a number changing, and it
    has to be legible at 7m on a portrait lens. Text objects are render-only
    here, so nothing about them reaches the GLB.
    """
    curve = bpy.data.curves.new(name, type="FONT")
    curve.body = body
    curve.size = size
    curve.align_x = "CENTER"
    curve.align_y = "CENTER"
    curve.extrude = .012
    obj = bpy.data.objects.new(name, curve)
    material = mat("NB_" + name, colour, .30)
    if emission:
        # mat() has no emission argument, so drive the BSDF directly rather
        # than passing it through and silently setting Transmission instead.
        bsdf = material.node_tree.nodes.get("Principled BSDF")
        colour_input = (bsdf.inputs.get("Emission Color")
                        or bsdf.inputs.get("Emission"))
        if colour_input:
            colour_input.default_value = (*colour, 1.0)
        strength = bsdf.inputs.get("Emission Strength")
        if strength:
            strength.default_value = emission
    obj.data.materials.append(material)
    world_col.objects.link(obj)
    # export_web.py strips anything carrying this tag before it bakes the
    # WORLD collection. Story props must never become permanent town geometry.
    obj["nb_render_only"] = True
    obj.location = (STORY001_TOTEM_X, STORY001_PRICE_Y, STORY001_PRICE_Z)
    # Text is authored in XY facing +Z; +90 about X stands it up facing -Y,
    # which is the street, and leaves it reading left-to-right along +X.
    obj.rotation_euler = (math.pi / 2, 0, 0)
    return obj


def _story001_show(obj, first, last, frame_end):
    """Hide obj outside [first, last]. Same keying animate_rise uses."""
    def key(frame, hidden):
        obj.hide_viewport = hidden
        obj.hide_render = hidden
        obj.keyframe_insert("hide_viewport", frame=frame)
        obj.keyframe_insert("hide_render", frame=frame)
    if first > 1:
        key(1, True)
        key(first, False)
    else:
        key(1, False)
    if last < frame_end:
        key(last + 1, True)


def _story001_car(world_col, index, x, y, rot, scale=.82):
    """One parked car on the forecourt or queued down the avenue."""
    car = place_instance(world_col, {"type": "car", "gx": 0, "gy": 0,
                                     "seed": 9600 + index}, "story001_traffic")
    car.scale = (scale, scale, scale)
    car.location = (x, y, terrain_height(x, y) + .20)
    car.rotation_euler = (0, 0, rot)
    car["nb_render_only"] = True
    return car


# Forecourt and avenue positions, and the frame each car first appears on.
# Shot 3 (f151) brings the pumps and the head of the queue; shot 4 (f241)
# reveals how far back it really goes. Rows are (x, y, rot, appear).
STORY001_CARS = (
    (114.6, 311.9, 0.0,   151), (119.4, 311.9, 0.0,   151),
    (114.6, 315.7, 0.0,   151), (119.4, 315.7, 0.0,   151),
    (114.6, 319.4, 0.0,   241), (119.4, 319.4, 0.0,   241),
    (124.2, 309.2, 0.62,  151), (127.4, 306.5, 0.0,   151),
    (133.2, 306.5, 0.0,   241), (139.0, 306.5, 0.0,   241),
    (144.8, 306.5, 0.0,   241), (150.6, 306.5, 0.0,   241),
)


def build_story001_price_sign(world_col, frame_end, dusk=False):
    """Followville Stories #001. Render-only overlay on the filling station."""
    if dusk:
        # The board is dead and the forecourt is empty but for one car left
        # crooked across a painted bay. Canopy downlights come up instead.
        _story001_plate(world_col, "story001_price_out", "$0.00", .44,
                        (.10, .10, .12))
        _story001_car(world_col, 99, 123.4, 316.0, .55)
        for lx in (DAY40_GAS_X - 4.3, DAY40_GAS_X - 1.2, DAY40_GAS_X + 1.9):
            for ly in (DAY40_GAS_Y - 6.4, DAY40_GAS_Y - 1.6):
                data = bpy.data.lights.new("story001_canopy", type="POINT")
                data.color = (1.0, .86, .62)
                data.shadow_soft_size = .55
                lamp = bpy.data.objects.new("story001_canopy", data)
                world_col.objects.link(lamp)
                lamp["nb_render_only"] = True
                lamp.location = (lx, ly, STORY001_SHELF + 4.70)
                # Fluorescents strike, stutter once, then hold.
                for frame, energy in ((1, 0.0), (44, 0.0), (47, 340.0),
                                      (50, 60.0), (54, 400.0)):
                    data.energy = energy
                    data.keyframe_insert("energy", frame=frame)
                for fc in obj_fcurves(data):
                    for kp in fc.keyframe_points:
                        kp.interpolation = "CONSTANT"
        return

    high = _story001_plate(world_col, "story001_price_high", "$4.29", .44,
                           (.94, .93, .88))
    low = _story001_plate(world_col, "story001_price_low", "$0.29", .44,
                          (.97, .32, .24), emission=.9)
    _story001_show(high, 1, STORY001_SWAP - 1, frame_end)
    _story001_show(low, STORY001_SWAP, frame_end, frame_end)

    for i, (x, y, rot, appear) in enumerate(STORY001_CARS):
        car = _story001_car(world_col, i, x, y, rot)
        _story001_show(car, appear, frame_end, frame_end)
        # The two that arrive on camera in shot 3 roll the last 4m in rather
        # than appearing parked. Everything else is already there -- a queue
        # reads as a queue, not as twelve cars materialising.
        if i in (1, 3):
            car.location = (x + 4.0, y, terrain_height(x + 4.0, y) + .20)
            car.keyframe_insert("location", frame=155)
            car.location = (x, y, terrain_height(x, y) + .20)
            car.keyframe_insert("location", frame=200)
            for fc in obj_fcurves(car):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"


def build_stage(world_col, buildings, frame_end, m, tod="day", hero=None, cam=None):
    t = TODS.get(tod, TODS["day"])
    if cam in ("day42reveal", "day43fpv", "day43pov",
               "day44approach", "day44street", "day44drone",
               "day44field", "day44overhead", "day44downtown",
               "day44allapproach", "day44alldrone",
               "day44allfield", "day44southfpv", "day44swrooftop",
               "day44westbank", "day44sereverse",
               "day44fullarc", "day46sunsetdrone",
               "day47reveal", "day48crown",
               "day49northreach", "day50highway") and tod == "sunset":
        # This release is meant to read unmistakably as sunset, not merely as
        # daytime with a warm key. Keep the cool sky needed for material colour
        # separation, but lower and redden the sun, deepen the blue ambient,
        # and let the long shadows carry the westbound construction wave.
        t = dict(t)
        t.update(sun_e=1.62, sun_c=(1.00, 0.42, 0.18),
                 sun_rot=(82, 0, 96), sky=(0.18, 0.29, 0.52), sky_s=.48,
                 sky_elev=1.4, air=1.18, dust=2.15, ozone=1.18,
                 exposure=-.08)
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
        # all new homes rise. Day 17 extended the portrait composition in both
        # horizontal directions; the previous distance clipped Twin Oaks at
        # one end of the orbit and crowded Kaleidoscope Crest at the other.
        # Keep enough margin for the full developed footprint throughout the
        # move while preserving parallax so the shot still reads as a sky
        # camera rather than a flat map.
        pol_deg, dist, fstop = 28, ext * 1.62 + 140, 7.0
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

    # Distant horizon ground surrounds, but never sits beneath, the continuous
    # regional walkable terrain.
    build_background_ground(world_col, m["grass"], cx, cy)

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
    elif cam == "riverdrone":
        if max((b.get("plan_id", 0) for b in buildings), default=0) < 367:
            raise RuntimeError("riverdrone camera needs the river chapter")
        aim = bpy.data.objects.new("RiverDroneAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("RiverDroneCamera")
        cam_data.lens = 37
        cam_data.clip_start = 8.0
        cam_data.clip_end = 6000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("RiverDroneCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        for frame, position, target in (
                (1, (286.0, -354.0, 138.0), (358.0, -205.0, 7.0)),
                (frame_end//2, (418.0, -340.0, 105.0), (377.0, -198.0, 7.0)),
                (frame_end, (520.0, -322.0, 116.0), (421.0, -194.0, 7.0))):
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "riverbridge":
        if max((b.get("plan_id", 0) for b in buildings), default=0) < 367:
            raise RuntimeError("riverbridge camera needs the river chapter")
        start = (286.0, -216.8)
        # Stop before the Rivergate gateway so the finished frame shows the
        # sign and neighborhood instead of parking the lens underneath it.
        end = (390.0, -214.4)
        full_start = (276.0, -217.0)
        full_end = (410.0, -214.0)
        z0 = terrain_height(*full_start)+.18
        z1 = terrain_height(*full_end)+.22
        aim = bpy.data.objects.new("RiverBridgeAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("RiverBridgeCamera")
        cam_data.lens = 27
        cam_data.clip_start = .12
        cam_data.clip_end = 2500.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("RiverBridgeCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        for index in range(9):
            fraction = index/8.0
            x = start[0]+(end[0]-start[0])*fraction
            y = start[1]+(end[1]-start[1])*fraction
            deck_t = (x-full_start[0])/(full_end[0]-full_start[0])
            z = z0+(z1-z0)*deck_t
            look_t = min(1.0, fraction+.10)
            ax = start[0]+(end[0]-start[0])*look_t
            ay = start[1]+(end[1]-start[1])*look_t
            az_t = (ax-full_start[0])/(full_end[0]-full_start[0])
            frame = 1+int(round((frame_end-1)*fraction))
            cam_obj.location = (x, y, z+1.72)
            aim.location = (ax, ay, z0+(z1-z0)*az_t+1.60)
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        bpy.context.scene.camera = cam_obj
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
    elif cam == "day22reveal":
        # One continuous 14-second edit: establish the finished skyline, fly
        # to Meadow Run and hold for ten homes, then settle at Station 1 before
        # that campus rises. Reveal timing is coordinated in main().
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        new_homes = [b for b in buildings
                     if b["type"] == "house" and b.get("day") == latest_day]
        station = next((b for b in reversed(buildings)
                        if b["type"] == "firestation"), None)
        home_points = [build_pos(b) for b in new_homes]
        hx = sum(p[0] for p in home_points) / len(home_points) if home_points else cx
        hy = sum(p[1] for p in home_points) / len(home_points) if home_points else cy
        if station:
            sx, sy = build_pos(station)
            station_size = SIZE.get(station["type"], 1)
            sx += (station_size - 1) * LOT / 2
            sy += (station_size - 1) * LOT / 2
        else:
            sx, sy = 64.5, -70.5

        aim = bpy.data.objects.new("Day22RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day22RevealCamera")
        cam_data.lens = 36
        cam_data.clip_start = 5.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day22RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-3.2s: restrained southeast skyline push.
            (1, (158.0, -124.0, 84.0), (-8.0, 0.0, 12.0)),
            (96, (139.0, -106.0, 73.0), (-3.0, 4.0, 13.5)),
            # 3.2-5.7s: drone crosses to the newest Meadow Run frontage.
            (125, (78.0, -118.0, 78.0), (-32.0, -48.0, 10.0)),
            (145, (-45.0, -155.0, 62.0), (hx + 10.0, hy + 20.0, 7.0)),
            (170, (hx + 47.0, hy - 52.0, 54.0), (hx, hy, 4.2)),
            # 5.7-8.8s: almost-still hover while all ten homes rise.
            (265, (hx + 42.0, hy - 47.0, 49.0), (hx, hy, 4.8)),
            # 8.8-11.0s: arc northeast into the fire-station block.
            (295, (-5.0, -145.0, 68.0), (35.0, -95.0, 8.0)),
            (330, (sx + 48.0, sy - 50.0, 44.0), (sx, sy, 6.2)),
            # 11.0-14.0s: station reveal and a slow architectural push.
            (frame_end, (sx + 39.0, sy - 42.0, 36.0), (sx, sy, 7.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day25reveal":
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest = [b for b in buildings
                  if b["type"] == "house" and b.get("day") == latest_day]
        points = [build_pos(b) for b in newest]
        hx = sum(x for x, _y in points) / len(points) if points else cx
        hy = sum(y for _x, y in points) / len(points) if points else cy

        aim = bpy.data.objects.new("Day25RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day25RevealCamera")
        cam_data.lens = 39
        cam_data.clip_start = 7.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day25RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-3.1s: completed-city angled drone establishing shot.
            (1, (178.0, -112.0, 122.0), (-5.0, -26.0, 13.0)),
            (92, (143.0, -145.0, 108.0), (-18.0, -86.0, 11.0)),
            # 3.1-10.7s: all three new-home areas share one broad portrait
            # composition while the drone eases steadily toward them.
            (128, (66.0, -288.0, 158.0), (hx - 16.0, hy, 5.0)),
            (320, (50.0, -270.0, 133.0), (hx - 8.0, hy + 2.0, 5.5)),
            # 10.7-14.1s: clean aerial transfer back toward Fire Station 1.
            (366, (76.0, -178.0, 110.0), (70.0, -126.0, 7.5)),
            (423, (151.0, -104.0, 72.0),
             (FISHING_POND_X, FISHING_POND_Y, 4.0)),
            # 14.1-18.0s: settled descending push across pond and dock.
            (frame_end, (144.0, -96.0, 39.0),
             (FISHING_POND_X - 3.0, FISHING_POND_Y, 2.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day35store":
        # Day 35, one unbroken 24-second move: the town as it stood, then the
        # 24 new homes rising under the drone, then a descent onto the Salmon
        # Pro Shop as it appears, then a climb out over the finished town.
        # Nothing cuts -- every beat is a keyframe on the same camera.
        # Day 35's 24 homes are NOT one group: 8 finish Ferry Street in
        # Eastbank Village and 16 open Marshlight Lane in River Meadows, 633m
        # apart. Averaging them puts the aim point in empty meadow between the
        # two, which is what the first cut did -- the drone arrived over open
        # grass with older log homes on the horizon and nothing rose on screen.
        # Both groups are on the eastern river side, so one continuous
        # southward sweep can visit each as it builds.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        north = [b for b in newest_homes if b.get("plan_id", 0) <= 584]
        south = [b for b in newest_homes if b.get("plan_id", 0) >= 585]

        def centre(group, fallback):
            points = [build_pos(b) for b in group]
            if not points:
                return fallback
            return (sum(p[0] for p in points) / len(points),
                    sum(p[1] for p in points) / len(points))

        nx, ny = centre(north, (441.0, 392.0))
        mx, my = centre(south, (534.0, -241.0))
        sx, sy = SALMON_SHOP_X, SALMON_SHOP_Y

        aim = bpy.data.objects.new("Day35StoreAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day35StoreCamera")
        cam_data.lens = 40
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day35StoreCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-4s: the town as it stood this morning. Nothing has risen.
            (1, (300.0, -300.0, 200.0), (10.0, -10.0, 12.0)),
            (120, (215.0, -268.0, 178.0), (5.0, -12.0, 12.0)),
            # 4-8s: swing north-east onto Ferry Street's eight.
            (190, (nx + 90.0, ny - 250.0, 168.0), (nx, ny, 10.0)),
            (240, (nx + 82.0, ny - 84.0, 92.0), (nx, ny, 8.0)),
            # 8-11s: hold while they build.
            (330, (nx + 66.0, ny - 62.0, 74.0), (nx, ny + 2.0, 7.0)),
            # 11-15.5s: one continuous sweep south down the river valley.
            (400, (nx + 150.0, (ny + my) / 2, 118.0), (nx + 40.0, 90.0, 8.0)),
            (470, (mx + 150.0, my + 96.0, 108.0), (mx, my, 8.0)),
            # 15.5-18.5s: settle over Marshlight Lane's sixteen.
            (555, (mx + 104.0, my - 76.0, 82.0), (mx, my - 2.0, 7.0)),
            # 18.5-23s: cross the town westward and descend on the store.
            (615, (180.0, -250.0, 196.0), (-40.0, -110.0, 12.0)),
            (665, (sx + 118.0, sy - 104.0, 88.0), (sx + 6.0, sy - 4.0, 11.0)),
            (706, (sx + 66.0, sy - 62.0, 46.0), (sx, sy - 3.0, 9.0)),
            # 23-25s: lift away with the finished town behind it.
            (frame_end, (sx + 168.0, sy - 150.0, 150.0), (-30.0, -24.0, 12.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day38reveal":
        # Day 38, 16 seconds, the established shape: six seconds on the
        # downtown skyline, one fast run east, then the whole Food Court ring
        # coming out of the ground.
        ring = [b for b in buildings if b.get("type") == "foodhouse"]
        points = [build_pos(b) for b in ring]
        fx = sum(p[0] for p in points) / len(points) if points else FOOD_COURT_X
        fy = sum(p[1] for p in points) / len(points) if points else FOOD_COURT_Y

        aim = bpy.data.objects.new("Day38RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day38RevealCamera")
        cam_data.lens = 28
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day38RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"

        skyline_at = (92.8, -127.8, 118.4)
        skyline_on = (25.0, 6.0, 42.0)
        beats = (
            (1, skyline_at, skyline_on),
            (180, skyline_at, skyline_on),
            # 6-8.6s: out east over the river districts.
            (214, (250.0, -90.0, 190.0), (380.0, -10.0, 24.0)),
            (258, (fx - 96.0, fy - 74.0, 86.0), (fx, fy, 8.0)),
            # 8.6-16s: swing round the ring as it rises.
            (330, (fx - 86.0, fy - 62.0, 74.0), (fx, fy, 7.5)),
            (405, (fx - 74.0, fy - 48.0, 62.0), (fx, fy, 7.0)),
            (frame_end, (fx - 66.0, fy - 40.0, 55.0), (fx, fy, 6.5)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day38foodtour":
        # Day 38, 20 seconds, one unbroken move from 230m over downtown to
        # 2m over the Food Court's own loop road:
        #   0.0-4.0s   high drone over the city, pushing slowly in.
        #   4.0-7.5s   one continuous transfer north-east to the Food Court.
        #   7.5-13.6s  a descending arc while the nineteen homes rise, one at
        #              a time, counter-clockwise round the ring.
        #  13.6-17.2s  the same move keeps descending, crosses the ring of
        #              homes well above the tallest of them, and settles on
        #              the loop road.
        #  17.2-20.0s  street level, past the homes, turning south-west to
        #              look back down the valley toward town.
        #
        # Everything after the transfer lives NORTH-EAST of the ring, which is
        # not the side the Day 38 reveal used. TODS["day"] puts the sun at
        # rot (50, 0, 120) -- light running toward (-0.66, -0.38, -0.64), i.e.
        # a sun 40 degrees up in the NORTH-EAST. A camera north-east of the
        # ring therefore has the sun behind it and every food house lit, and
        # the town it turns back toward is south-west, in the same direction.
        yard_b = next((b for b in buildings if b.get("type") == "foodcourt"), None)
        fx, fy = build_pos(yard_b) if yard_b else (FOOD_COURT_X, FOOD_COURT_Y)
        # The loop road is drawn as a 32x25 ellipse about that record, and the
        # homes stand on a wider one, so the road is the clear lane between
        # the ring of homes outside it and the ring of lamp posts inside it.
        gz = terrain_height(fx, fy)
        eye = gz + 2.05                       # road top is gz + 0.19

        def loop(degrees, lift=0.0):
            a = math.radians(degrees)
            return (fx + 32.0 * math.cos(a), fy + 25.0 * math.sin(a), eye + lift)

        aim = bpy.data.objects.new("Day38FoodTourAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day38FoodTourCamera")
        cam_data.lens = 28
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day38FoodTourCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"

        skyline_on = (25.0, 6.0, 42.0)
        beats = (
            # 0.0-4.0s: the city as it stands, from the south-east.
            (1,   (185.0, -232.0, 205.0), skyline_on),
            (60,  (156.0, -200.0, 185.0), skyline_on),
            (120, (128.0, -170.0, 166.0), skyline_on),
            # 4.0-7.5s: north-east across the river districts, ~480m.
            (180, (240.0, 40.0, 150.0), (300.0, 190.0, 20.0)),
            (225, (fx + 74.0, fy + 82.0, 96.0), (fx, fy - 2.0, 10.0)),
            # 7.5-13.6s: settle and sink while the ring builds.
            (290, (fx + 68.0, fy + 72.0, 84.0), (fx, fy - 2.0, 10.0)),
            (350, (fx + 63.0, fy + 64.0, 70.0), (fx, fy - 2.0, 10.0)),
            (408, (fx + 58.0, fy + 58.0, 58.0), (fx, fy - 4.0, 10.0)),
            # 13.6-17.2s: down through the ring. The 28m key is the one that
            # matters -- it is where the camera crosses the homes, and the
            # tallest of them (the fries carton's longest fry) tops out at
            # 20.4m. Sampling the evaluated path frame by frame put the
            # closest approach at 1.4m above a coffee cup's lid with 4.0m of
            # lateral clearance, and no frame inside anything at all.
            (452, (fx + 40.0, fy + 37.0, 40.0), (fx + 4.0, fy, 11.0)),
            (482, (fx + 29.0, fy + 25.0, 28.0), (fx + 10.0, fy + 6.0, 12.0)),
            (500, (fx + 22.5, fy + 18.0, 20.0), (fx + 14.0, fy + 16.0, eye)),
            (515, loop(45.0), loop(80.0)),
            # 17.2-20.0s: counter-clockwise along the loop road, homes passing
            # on the right, lamps and the green on the left, then the turn
            # south-west onto the valley and the town beyond it.
            (545, loop(80.0), loop(115.0)),
            (575, loop(120.0), loop(150.0, lift=-0.3)),
            (frame_end, loop(140.0), (fx - 72.0, fy - 30.0, gz - 4.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"

        # The 10m near clip that keeps thin aerial roads and ponds from
        # flashing (see CLAUDE.md) would erase the whole street beat, so it
        # has to come down with the camera -- but only once nothing is within
        # the value being left behind, and in two steps so depth precision is
        # given up as late as possible. clip_end drops with it for the same
        # reason: it is the ratio that costs precision, not the near plane.
        # LINEAR, because a bezier handle can overshoot a clip plane past zero.
        for frame, near, far in ((1, 10.0, 8000.0), (440, 10.0, 8000.0),
                                 (485, 2.0, 4000.0), (515, 0.30, 1200.0),
                                 (frame_end, 0.30, 1200.0)):
            cam_data.clip_start, cam_data.clip_end = near, far
            cam_data.keyframe_insert("clip_start", frame=frame)
            cam_data.keyframe_insert("clip_end", frame=frame)
        for fc in obj_fcurves(cam_data):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

        bpy.context.scene.camera = cam_obj
    elif cam == "day37reveal":
        # Day 37, 24 seconds:
        #   0-6s     the Day 36 downtown framing, orbiting slowly.
        #   6-8.9s   one fast run south to Followville Commons.
        #   8.9-15.7s the complex rises, framed from the NORTH so the lawn,
        #            the pool and both facades read in that order -- the side
        #            the complex was turned round to present.
        #   15.7-24s back up to City Hall for the mayor's plinth, viewed from
        #            the north with the hall itself behind it.
        commons = next((b for b in buildings
                        if b.get("type") == "apartmentcomplex"), None)
        hall = next((b for b in buildings if b.get("type") == "cityhall"), None)
        cx, cy = build_pos(commons) if commons else (APARTMENTS_X, APARTMENTS_Y)
        hx, hy = build_pos(hall) if hall else (CITY_HALL_X, CITY_HALL_Y)
        stx, sty = hx, hy + 30.0

        skyline_on = (25.0, 6.0, 42.0)
        ORBIT_R, ORBIT_H = 150.0, 76.4

        def orbit(degrees):
            a = math.radians(degrees)
            return (skyline_on[0] + ORBIT_R * math.cos(a),
                    skyline_on[1] + ORBIT_R * math.sin(a),
                    skyline_on[2] + ORBIT_H)

        aim = bpy.data.objects.new("Day37RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day37RevealCamera")
        cam_data.lens = 28
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day37RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"

        beats = (
            (1,   orbit(-63.1), skyline_on),
            (62,  orbit(-56.0), skyline_on),
            (124, orbit(-48.5), skyline_on),
            (180, orbit(-41.0), skyline_on),
            # 6-8.9s: out over the southern suburbs toward the Commons.
            (222, (10.0, -190.0, 172.0), (-30.0, -270.0, 26.0)),
            (268, (cx + 4.0, cy + 96.0, 62.0), (cx, cy - 2.0, 12.0)),
            # 8.9-15.7s: settle and descend on the city-facing frontage.
            (330, (cx + 3.0, cy + 88.0, 55.0), (cx, cy - 2.0, 11.5)),
            (470, (cx + 2.0, cy + 72.0, 43.0), (cx, cy - 3.0, 10.0)),
            # 15.7-24s: back north to City Hall, down onto the plinth.
            (545, (stx - 4.0, sty + 42.0, 32.0), (stx, sty, 9.5)),
            (640, (stx - 2.0, sty + 29.0, 17.0), (stx, sty, 7.8)),
            (frame_end, (stx - 1.0, sty + 25.0, 13.6), (stx, sty, 7.2)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day39mayor":
        # Day 39, 10 seconds, outside the government building on the day the
        # mayoral result is announced. One slow push from the south-east onto
        # City Hall's portico and dome, framed low in a 9:16 frame so the top
        # two-thirds is sky: that is where the shells burst and where the
        # banner plane crosses. No cuts -- the whole clip is one move.
        aim = bpy.data.objects.new("Day39MayorAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day39MayorCamera")
        cam_data.lens = 34
        # Not the 10m aerial clip: this is a ground-level civic shot and the
        # nearest lamp standard is well inside ten metres of the final push.
        cam_data.clip_start = 0.40
        cam_data.clip_end = 6000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day39MayorCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        hx, hy = CITY_HALL_X, CITY_HALL_Y
        beats = (
            (1,   (hx + 88.0, hy - 84.0, 44.0), (hx + 4.0, hy + 2.0, 21.0)),
            (150, (hx + 72.0, hy - 70.0, 39.0), (hx + 3.0, hy + 2.0, 20.0)),
            (300, (hx + 57.0, hy - 57.0, 34.0), (hx + 2.0, hy + 2.0, 19.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "metroreveal":
        # Reusable first-day Crown Quarter reveal. One continuous northward
        # journey establishes the historic core, follows the inherited grid,
        # crosses to the expressway, then settles inside the new downtown.
        aim = bpy.data.objects.new("MetroRevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("MetroRevealCamera")
        cam_data.lens = 25
        cam_data.clip_start = 8.0
        cam_data.clip_end = 10000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("MetroRevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            # Historic grid and the Northgate arterial: prove continuity first.
            # Stay over built fabric until the metro roads are substantially
            # drawn. Flying north at frame 210 used to spend five seconds
            # staring into the empty terrain shelf while roads built offscreen.
            (1,   (35.0, -285.0, 560.0), (5.0, 80.0, 8.0)),
            (150, (30.0, -60.0, 500.0),  (0.0, 300.0, 9.0)),
            (300, (20.0, 180.0, 420.0),  (0.0, 430.0, 10.0)),
            (390, (15.0, 315.0, 350.0),  (0.0, 520.0, 12.0)),
            # Arc east after the street ribbons finish, revealing the viaduct
            # and interchange while the first tower starts to rise.
            (470, (300.0, 455.0, 300.0), (105.0, 625.0, 18.0)),
            (550, (335.0, 690.0, 245.0), (85.0, 655.0, 22.0)),
            # Swing north of the skyline so the towers layer against old town.
            (630, (185.0, 875.0, 220.0), (5.0, 665.0, 32.0)),
            (700, (35.0, 835.0, 150.0),  (0.0, 650.0, 35.0)),
            # Touch boulevard scale, then climb to a complete three-tower
            # portrait for --still and the final video hold.
            (740, (15.0, 735.0, 78.0),   (15.0, 630.0, 18.0)),
            (780, (-85.0, 790.0, 180.0), (-85.0, 555.0, 30.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day47reveal":
        # Day 47: one uninterrupted 24-second sunset move, no cuts anywhere.
        # Authored down IN the street rather than above it -- the first cut of
        # this shot was a 250m aerial and read as a map, not as a town.
        #
        # The geometry it is built on, all measured rather than assumed:
        #   * the 37 homes are ONE street, not two -- 18 at y=729.5 facing
        #     north and 17 at y=746.5 facing south, so the centreline is
        #     y=738.0 and the camera flies straight down it;
        #   * Ember Ridge is a level shelf, terrain_height == 5.0 everywhere
        #     along the corridor, so no terrain following is needed;
        #   * houses measure 8.2m tall (9.55m worst case) off that shelf, so
        #     the 10.5m camera sits just under the 13.2m rooflines and the
        #     homes rise past the lens instead of below it;
        #   * the worst-case facade sits 4.26m from the centreline, which is
        #     why the near plane stays at 2m for the whole street run.
        #
        # Sunset light travels west and slightly south (sun_rot 78/0/102, a
        # 12-degree sun), so east-facing walls are the strongly lit ones.
        # Flying WEST puts the sun behind the camera and every facade it
        # meets is a lit one -- that is where the warmth comes from, and it
        # avoids staring into a 12-degree sun for twenty seconds.
        aim = bpy.data.objects.new("Day47RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day47RevealCamera")
        cam_data.lens = 26
        cam_data.clip_start = 2.0
        cam_data.clip_end = 18000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day47RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            # Five seconds standing in the empty street at the east end, so
            # the ground reads as ground before anything stands on it.
            (1,   (-320.0, 738.0, 10.5), (-450.0, 738.0, 8.5), 26),
            (150, (-370.0, 738.0, 10.5), (-500.0, 738.0, 8.5), 26),
            # Eleven seconds gliding west down the centreline at a steady
            # ~0.9m/frame while the homes rise. The camera keeps roughly 45m
            # of lead on the wave: any nearer and a home at 8.5m off the
            # centreline falls outside the narrow horizontal field before it
            # finishes rising. Checked by projecting all 37 homes at their
            # own rise frame -- 37/37 are on screen as they appear.
            (300, (-505.0, 738.0, 11.0), (-640.0, 738.0, 9.0), 26),
            # Cooper Street is NOT continuous yet. Roughly x -575..-530, at
            # the Cooper Street 2/3 boundary, is still unbuilt ground: the
            # first cut of this shot flew over it at 5m and the film simply
            # crossed an empty field for two seconds. No Day 47 home sits in
            # that stretch either, so the camera arcs over it and drops back
            # onto the road, which reads as a drone hopping an unbuilt block
            # instead of a hole in the street.
            (350, (-550.0, 738.0, 30.0), (-690.0, 738.0, 14.0), 26),
            (400, (-595.0, 738.0, 12.0), (-730.0, 738.0, 9.5), 26),
            (500, (-690.0, 738.0, 11.5), (-800.0, 738.0, 9.0), 26),
            # Lift out of the street and whip south-east. The ending stays
            # low -- 130m over the historic core, not the 1180m of the first
            # cut -- so the film finishes inside the city it is showing.
            (580, (-660.0, 560.0, 120.0), (-420.0, 380.0, 40.0), 28),
            (720, (300.0, -230.0, 130.0), (40.0, 50.0, 5.0), 28),
        )
        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        # 2m near plane while the camera is between the houses, widening to
        # the 10m the aerial modes require once it is above the city.
        for frame, near in ((1, 2.0), (500, 2.0), (580, 10.0), (720, 10.0)):
            cam_data.clip_start = near
            cam_data.keyframe_insert("clip_start", frame=frame)
        for fc in obj_fcurves(cam_data):
            if fc.data_path == "clip_start":
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        bpy.context.scene.camera = cam_obj
    elif cam == "day48crown":
        # Day 48: one uninterrupted 24-second sunset move, no cuts. The day the
        # suburbs run out -- the last 81 addresses of the 2,148-house reserve
        # fill Ember Ridge, and the 11 followers with nowhere left to live earn
        # Crown Quarter's first tower. The shot has to carry both, so it is one
        # descent into a street and one climbing turn out of it.
        #
        # Measured, not assumed:
        #   * the 81 homes sit on THREE parallel streets -- Wheelwright
        #     (centreline y=774, 36 homes), Orchard (y=810, 41) and the tail of
        #     Cooper (y=738, 4). Wheelwright is the middle one, so flying its
        #     centreline puts Orchard 27.5m/44.5m to the north and Cooper the
        #     same distances south, and every new home is reachable from one
        #     line. Road sits under the camera for the whole run: Wheelwright
        #     is continuous from x=-750 to x=-260.
        #   * Ember Ridge is a level shelf, terrain_height == 5.0 across the
        #     entire corridor and the entire climb-out, so nothing follows
        #     terrain here.
        #   * 9:16 makes the HORIZONTAL field the narrow one. At 24mm the
        #     half-angle is atan(10.125/24), so a home 44.5m off the centreline
        #     needs ~117m of depth before it is inside the frame at all. That
        #     is why the lens is 24 rather than day 47's 26, and why the rise
        #     wave below leads by 46m / 96m / 146m depending on which street a
        #     home stands on -- the far street has to rise further ahead.
        #   * 16m of altitude is deliberate: 2.8m over the 13.2m rooflines. Low
        #     enough that homes rise past the lens, high enough that the sight
        #     line to Orchard clears Wheelwright's roofs.
        #
        # Sunset light travels west, so east-facing walls are the lit ones and
        # flying WEST keeps the sun behind the camera -- same reasoning as
        # day47reveal, and the reason the run is east-to-west.
        aim = bpy.data.objects.new("Day48CrownAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day48CrownCamera")
        cam_data.lens = 24
        cam_data.clip_start = 2.0
        cam_data.clip_end = 18000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day48CrownCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        # The x positions at frames 1/70/130/465 are DAY48_CAM_KNOTS, and the
        # rise schedule inverts exactly that table to decide when each home
        # stands up. Keep the two in step: the knots live at module scope so
        # there is one copy of the number, not two.
        beats = (
            # Frames 1-130: a descending approach from the east, over the edge
            # of Bramble Park rather than open meadow, with the three empty
            # Ember Ridge streets laid out ahead. Nothing rises until 107.
            (1,   (-196.0, 778.0, 52.0), (-368.0, 774.0, 22.0), 24),
            (70,  (-240.0, 776.0, 34.0), (-410.0, 774.0, 14.0), 24),
            # Frames 130-465: down in the street, a steady 1.03m/frame west
            # along the centreline while the wave runs ahead of the lens. The
            # aim stays low and close (~75m out, 6m up) so the frame is filled
            # by rising homes and the horizon is pushed into the top third --
            # this corridor points straight at the terrain boundary 230-440m
            # west, and a level aim puts that seam dead centre.
            (130, (-290.0, 774.0, 19.0), (-365.0, 774.0, 6.0), 24),
            (300, (-465.6, 774.0, 16.5), (-540.0, 774.0, 6.0), 24),
            (465, (-636.0, 774.0, 16.0), (-712.0, 770.0, 6.0), 24),
            # Frames 465-720: the wave finished at 440, so the camera banks
            # left and climbs out of the street. The aim swings off the western
            # boundary immediately and never returns to it -- everything from
            # here looks inward over built city.
            (510, (-680.0, 762.0, 30.0), (-700.0, 700.0, 14.0), 26),
            (555, (-696.0, 730.0, 62.0), (-620.0, 648.0, 26.0), 28),
            (600, (-650.0, 700.0, 94.0), (-470.0, 620.0, 34.0), 28),
            (660, (-430.0, 664.0, 84.0), (-260.0, 574.0, 26.0), 28),
            # Ends 116m north-west of Crown Quarter's first tower, looking
            # south-east down the new grid with the historic city behind it.
            # The tower then spans 38% of the frame instead of the 26% it held
            # from 165m, and its 59m roofline breaks the horizon rather than
            # sitting under it. 58m of altitude keeps the shot at skyline
            # height rather than above the skyline, and looking south-east
            # over built city is what keeps the western terrain seam -- which
            # is in frame for the street run -- out of the closing image.
            (720, (-248.0, 626.0, 58.0), (-140.0, 528.0, 20.0), 28),
        )
        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        # The camera's X through the street run must be exactly the piecewise
        # line the rise schedule inverted, so those keyframes are LINEAR. A
        # Bezier ease there would run the camera ahead of its own wave in
        # mid-run and push the outer street out of the narrow frame. Y and Z
        # stay Bezier: they do not enter the on-screen test, and easing the
        # descent is what makes the arrival readable.
        for fc in obj_fcurves(cam_obj):
            if fc.data_path == "location" and fc.array_index == 0:
                for kp in fc.keyframe_points:
                    if kp.co[0] <= 465:
                        kp.interpolation = "LINEAR"
        # 2m near plane down in the street, widening to the 10m the aerial
        # modes require once the camera is above the rooflines.
        for frame, near in ((1, 10.0), (110, 2.0), (465, 2.0),
                            (555, 10.0), (720, 10.0)):
            cam_data.clip_start = near
            cam_data.keyframe_insert("clip_start", frame=frame)
        for fc in obj_fcurves(cam_data):
            if fc.data_path == "clip_start":
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        bpy.context.scene.camera = cam_obj
    elif cam == "day49northreach":
        # Day 49: one uninterrupted 24-second sunset move, no cuts. The day the
        # city crosses y=824. Chapter five's reserve opens and 152 homes stand
        # up on five of Crown Quarter's own north/south streets, which stop
        # being the city's edge and run on into open land.
        #
        # The art-direction problem this shot exists to solve: these 152 homes
        # are NOT a compact new neighbourhood. They are five long north/south
        # ribbons spanning the full 320m depth of Crown Fields, and the
        # east/west avenues between them do not reveal until plan_id 2345 --
        # forty-four addresses past this growth. So there is no grid to shoot.
        # What is actually there is five streets reaching north out of the
        # built city, 70m apart, with meadow between them, and the film is
        # built to read that as intent rather than as a sparse grid.
        #
        # Measured, not assumed:
        #   * the 152 homes sit on FIVE parallel streets, houses 8.5m either
        #     side of centrelines x=-190/-120/-50/20/90. Maple Avenue North
        #     (x=-50) is the exact middle one, so flying its centreline puts
        #     every home in the growth at 8.5m, 61.5m, 78.5m, 131.5m or 148.5m
        #     off the line -- the five offsets DAY49_WAVE_LEAD is keyed on.
        #   * Crown Fields is not one shelf. terrain_height is 5.0 up to y=820,
        #     ramps down over the next 80m and is level at 3.22 from y=900
        #     north. That is a 2.25% grade, so the street run holds 17m of
        #     altitude at the seam and 15m past y=900, keeping the same ~3.5m
        #     of clearance over the 8.2m rooflines the whole way.
        #   * the northern roads simply stop at y=1170 -- Northmoor Street does
        #     not reveal until plan_id 2751 -- so the run ends at y=1122 and
        #     lifts, and the aim never dwells on the cut ends.
        #   * the Crown Expressway's own unfinished end at (222, 858) is 272m
        #     east of Maple and stays 69 degrees off the closing axis. It is
        #     out of frame for the whole shot, deliberately: whether it gets
        #     extended or terminated is Cade's call and not this film's.
        #
        # Sunset light travels west, so east-facing walls are the lit ones.
        # Day 47 and day 48 both flew west to keep the sun behind the lens;
        # this growth runs north, so the sun is broadside right instead. That
        # is the trade the geometry forces, and it is the better one here: a
        # raking cross-light models five parallel rows far more strongly than
        # flat frontal light would, and it throws long shadows west across the
        # meadow between the ribbons, which is what stops the gaps between them
        # reading as nothing. The closing bank turns west so the shot still
        # ends with the sun behind it.
        aim = bpy.data.objects.new("Day49NorthReachAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day49NorthReachCamera")
        cam_data.lens = 20
        cam_data.clip_start = 10.0
        cam_data.clip_end = 18000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day49NorthReachCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        # The y positions at frames 1/80/200/260/545 are DAY49_CAM_KNOTS, and
        # the rise schedule inverts exactly that table. Keep the two in step.
        beats = (
            # Frames 1-200: a long descending approach from the south, held
            # high over Crown Quarter's grid so the built city fills the lower
            # frame and the empty meadow beyond the seam fills the upper. 20mm
            # rather than 24 because the outer ribbons are 148.5m off the axis
            # and this is the only part of the shot far enough back to hold
            # them: their southern homes rise here, from frame 60, while the
            # camera is still 474m short of the seam. The lens holds 20mm all
            # the way to the street for the same reason -- tightening it during
            # the approach is what pinned the far West Market homes against the
            # left edge in the first cut of this shot.
            (1,   (-50.0, 350.0, 118.0), (-50.0, 690.0, 44.0), 20),
            (80,  (-50.0, 455.0, 104.0), (-50.0, 775.0, 36.0), 20),
            (200, (-50.0, 700.0, 62.0),  (-50.0, 900.0, 22.0), 20),
            # Frames 200-260: down through the seam itself. This is the beat
            # the whole film is about, so the camera crosses y=824 at street
            # height rather than looking down on it.
            (260, (-50.0, 830.0, 17.0),  (-50.0, 905.0, 8.0),  20),
            # Frames 260-545: down in Maple Avenue North, a steady 1.025m per
            # frame north along the centreline -- day 48's street speed
            # exactly -- while the wave runs ahead of the lens. The aim stays
            # low and ~75m out so rising homes fill the frame. The lens
            # tightens 20mm to 24mm across this stretch, once every home still
            # to come is one of Maple's own and 8.5m off the lens axis.
            (400, (-50.0, 973.5, 15.0),  (-50.0, 1048.0, 7.0), 24),
            (545, (-50.0, 1122.0, 15.0), (-50.0, 1197.0, 7.0), 24),
            # Frames 545-720: the wave finished at 512, so the camera climbs
            # out of the street and banks east, then turns back to look
            # south-west down all five ribbons at once. Ending here rather
            # than facing north is what keeps both unfinished edges -- the
            # roads' cut ends at y=1170 behind the lens, the expressway's at
            # (222, 858) far off axis -- out of the closing image, and it puts
            # the whole city behind the new quarter instead of empty meadow.
            #
            # 82m, not the 124m this shot first closed at. The horizon seam --
            # the 5.33m step where the authored terrain's perimeter meets the
            # z=0 background slabs, diagnosed on day 48 and deliberately left
            # alone because Cade reviewed it and called it fine -- is a settled
            # matter, but how hard a camera stares at it is not, and dropping
            # the close from 124m to 82m measurably narrows it.
            #
            # MEASURE THE SEAM AT FULL RESOLUTION. tune_day49_close.py compares
            # altitudes at 270x480 to keep the diagnostic cheap, and that is
            # fine for ranking them but its brightness figures are not real: a
            # band 7px wide at 1920 is about 1px at 480, and that single pixel
            # is a blend of dark band and bright sky, so it reads far lighter
            # than it is. The low-res pass called 82m "31.9% of local sky",
            # which would have put it inside day 48's accepted range. The
            # delivered 1080x1920 frame is 3.0%. Rank altitudes at low
            # resolution if you like; only ever quote numbers from a full-size
            # frame.
            #
            # Full-resolution, closing frame: 124m gives a 10px band at 1.8% of
            # local sky brightness, 82m gives 7px at 3.0%. For scale, the same
            # measurement over day 48's delivered reel -- the one Cade reviewed
            # and accepted -- gives 4px at 27.5% at its close but 20px at 10.2%
            # at its frame 600, which is thicker than anything in this shot. So
            # this is the same artefact within the same range, not a new one.
            # 82m is also the lowest altitude that still reads the five ribbons
            # as five parallel streets rather than flattening them into one
            # band of roofs.
            #
            # Worth knowing: the seam does not appear at all during the street
            # run. Frames 300 and 470 have no band, because down at 15m the
            # near ground fills the frame and the map perimeter is occluded.
            # It is only ever an aerial problem.
            (600, (-14.0, 1168.0, 46.0), (-42.0, 1120.0, 14.0), 26),
            (650, (34.0, 1166.0, 70.0),  (-84.0, 1000.0, 15.0), 28),
            (720, (58.0, 1098.0, 82.0),  (-106.0, 872.0, 14.0), 28),
        )
        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        # The camera's Y through the approach and street run must be exactly
        # the piecewise line the rise schedule inverted, so those keyframes are
        # LINEAR -- same reason day48crown pins its X. A Bezier ease there runs
        # the camera ahead of its own wave mid-run and pushes the outer ribbons
        # out of the narrow horizontal frame. X and Z stay Bezier: they do not
        # enter the on-screen test, and easing the descent is what makes the
        # arrival at the seam readable.
        for fc in obj_fcurves(cam_obj):
            if fc.data_path == "location" and fc.array_index == 1:
                for kp in fc.keyframe_points:
                    if kp.co[0] <= 545:
                        kp.interpolation = "LINEAR"
        # 10m near plane for the aerial approach, as every aerial mode requires
        # so thin roads and ponds do not flash from lost depth precision, then
        # 2m down in the street, then back to 10m for the climb-out.
        for frame, near in ((1, 10.0), (200, 10.0), (250, 2.0), (545, 2.0),
                            (610, 10.0), (720, 10.0)):
            cam_data.clip_start = near
            cam_data.keyframe_insert("clip_start", frame=frame)
        for fc in obj_fcurves(cam_data):
            if fc.data_path == "clip_start":
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        bpy.context.scene.camera = cam_obj
    elif cam == "day50highway":
        # Day 50: one continuous 24-second sunset move. The opening is wide
        # enough to catch the first Gateway Row homes west of the flight line;
        # the middle drops between Quarry and Anvil while their addresses rise;
        # the closing climb turns east onto IC-4, where the Crown Expressway
        # curves into the new Ring Freeway. This is intentionally not a copy of
        # Day 49's old south-west close: the highway is part of today's story.
        aim = bpy.data.objects.new("Day50HighwayAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day50HighwayCamera")
        cam_data.lens = 18
        cam_data.clip_start = 10.0
        cam_data.clip_end = 18000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day50HighwayCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            # Wide enough for Gateway Row while its nine new homes rise. The
            # target leans west without losing Quarry/Anvil.
            (1,   (125.0, 300.0, 135.0), (-35.0, 835.0, 28.0), 18),
            (100, (125.0, 500.0, 105.0), (15.0, 865.0, 24.0),  19),
            (200, (125.0, 750.0, 60.0),  (112.0, 925.0, 17.0), 20),
            # Low chase between the two north/south ribbons. Their houses are
            # only 26.5m or 43.5m off axis, so each rise reads at street scale.
            (260, (125.0, 850.0, 20.0),  (125.0, 935.0, 7.0),  21),
            (380, (125.0, 975.0, 16.0),  (125.0, 1055.0, 7.0), 23),
            (500, (125.0, 1100.0, 16.0), (125.0, 1175.0, 7.0), 24),
            # With every new address standing, climb east and look north-west
            # through the expressway bend to the Ring Freeway interchange.
            (560, (182.0, 1162.0, 42.0), (235.0, 1174.0, 9.0),  24),
            (630, (350.0, 1105.0, 108.0), (285.0, 1190.0, 6.0), 28),
            (720, (520.0, 1050.0, 160.0), (280.0, 1170.0, 0.0), 34),
        )
        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        # The rise schedule inverts this exact Y path. Keep it linear until the
        # growth chase ends; easing it would move the lens away from its wave.
        for fc in obj_fcurves(cam_obj):
            if fc.data_path == "location" and fc.array_index == 1:
                for kp in fc.keyframe_points:
                    if kp.co[0] <= 500:
                        kp.interpolation = "LINEAR"
        for frame, near in ((1, 10.0), (200, 10.0), (250, 2.0), (500, 2.0),
                            (575, 10.0), (720, 10.0)):
            cam_data.clip_start = near
            cam_data.keyframe_insert("clip_start", frame=frame)
        for fc in obj_fcurves(cam_data):
            if fc.data_path == "clip_start":
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        bpy.context.scene.camera = cam_obj
    elif cam == "day46sunsetdrone":
        # Day 46: one exact 16-second sunset flight authored from Zach's two
        # reel references.  The opening five seconds hover on the established
        # south-east skyline, the middle drops to a higher version of the
        # reference street flight and runs just behind the construction wave,
        # and the ending climbs rapidly into a finished-city scale reveal.
        aim = bpy.data.objects.new("Day46SunsetDroneAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day46SunsetDroneCamera")
        cam_data.lens = 32
        cam_data.clip_start = 2.0
        cam_data.clip_end = 18000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day46SunsetDroneCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            # Five-second skyline hover: low enough to preserve recognizable
            # buildings and the horizon, with only a quiet lateral drift.
            (1,   (215.0, -205.0, 95.0), (-15.0, 75.0, 24.0), 32),
            (75,  (200.0, -180.0, 92.0), (-25.0, 100.0, 24.0), 32),
            (150, (175.0, -135.0, 88.0), (-45.0, 140.0, 22.0), 31),
            # Fast transfer into Ember Ridge, then a 15-25m-above-rooftop
            # chase across the three new streets.  The aim stays a few blocks
            # ahead, so the next houses rise in view rather than behind us.
            (195, (-35.0, 145.0, 90.0), (-320.0, 520.0, 12.0), 27),
            (225, (-330.0, 520.0, 65.0), (-470.0, 685.0, 8.0), 25),
            (275, (-430.0, 600.0, 50.0), (-555.0, 690.0, 8.0), 23),
            (325, (-535.0, 620.0, 44.0), (-650.0, 688.0, 7.0), 23),
            (365, (-650.0, 625.0, 48.0), (-725.0, 690.0, 8.0), 25),
            # Fast celebratory lift, then two seconds of high completed-city
            # scale so the film lands on "look how far we have come".
            (420, (-120.0, 0.0, 930.0), (-300.0, 430.0, 10.0), 30),
            (480, (480.0, -520.0, 1230.0), (-180.0, 370.0, 10.0), 32),
        )
        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        # Aerial precision matters most in the final climb; the low pass keeps
        # a 2m near plane so nearby roofs do not disappear under the camera.
        for frame, near in ((1, 2.0), (365, 2.0), (420, 10.0), (480, 10.0)):
            cam_data.clip_start = near
            cam_data.keyframe_insert("clip_start", frame=frame)
        for fc in obj_fcurves(cam_data):
            if fc.data_path == "clip_start":
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        bpy.context.scene.camera = cam_obj
    elif cam == "day45northcrown":
        # Day 45: one uninterrupted 20-second move.  It begins high enough to
        # hold every developed district, advances over the single synchronized
        # 214-home construction event, then descends along the same geographic
        # line into North Crown's pool courtyard.  No cut hides the relationship
        # between the old city, Ember Ridge and the new apartment campus.
        aim = bpy.data.objects.new("Day45NorthCrownAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day45NorthCrownCamera")
        cam_data.lens = 28
        cam_data.clip_start = 10.0
        cam_data.clip_end = 16000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day45NorthCrownCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            (1,   (520.0, -540.0, 1250.0), (-180.0, 350.0, 10.0), 31),
            (100, (300.0, -300.0, 1100.0), (-260.0, 500.0, 9.0), 29),
            (220, (40.0, 50.0, 800.0),    (-430.0, 640.0, 8.0), 25),
            (330, (-150.0, 330.0, 520.0), (-520.0, 690.0, 8.0), 23),
            (420, (-350.0, 680.0, 250.0), (-430.0, 950.0, 8.0), 25),
            (500, (-430.0, 920.0, 90.0),  (-430.0, 1030.0, 10.0), 29),
            (560, (-430.0, 1075.0, 20.0), (-405.0, 992.0, 14.0), 34),
            (600, (-430.0, 1062.0, 7.6),  (-405.0, 985.0, 15.0), 38),
        )
        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        # Preserve aerial precision, then relax the near plane only during the
        # final descent where the camera enters the courtyard.
        for frame, near, far in ((1, 10.0, 16000.0),
                                 (440, 10.0, 16000.0),
                                 (520, 2.0, 5000.0),
                                 (560, .35, 1800.0),
                                 (600, .35, 1800.0)):
            cam_data.clip_start, cam_data.clip_end = near, far
            cam_data.keyframe_insert("clip_start", frame=frame)
            cam_data.keyframe_insert("clip_end", frame=frame)
        for fc in obj_fcurves(cam_data):
            if fc.data_path in ("clip_start", "clip_end"):
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"
        bpy.context.scene.camera = cam_obj
    elif cam in ("day44approach", "day44street", "day44drone",
                 "day44field", "day44overhead", "day44downtown",
                 "day44allapproach", "day44alldrone", "day44allfield",
                 "day44fullarc"):
        # Day 44 is delivered as six independent clips so the edit can choose
        # between four genuinely different construction viewpoints and two
        # completed-city closers.  Every camera is continuous inside its clip.
        aim = bpy.data.objects.new("Day44Aim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day44Camera")
        cam_data.clip_start = (10.0 if cam == "day44overhead" else .20)
        cam_data.clip_end = 15000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day44Camera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        if cam == "day44fullarc":
            # One uninterrupted twenty-second round trip: establish every
            # developed district, descend into a wide view of the complete
            # Day 44 construction front, then climb back to the same full-city
            # scale after all 186 homes stand.  There are no duplicate keys or
            # one-frame jumps here, so interpolation cannot create a hidden cut.
            beats = (
                (1,   (300.0, -430.0, 1180.0), (-180.0, 350.0, 10.0), 31),
                (90,  (220.0, -320.0, 1080.0), (-235.0, 420.0, 9.0), 30),
                (190, (40.0, -30.0, 790.0),   (-340.0, 555.0, 8.0), 27),
                (290, (-125.0, 285.0, 525.0), (-455.0, 655.0, 7.0), 24),
                (390, (-285.0, 535.0, 305.0), (-560.0, 685.0, 7.0), 22),
                (445, (-385.0, 650.0, 230.0), (-620.0, 670.0, 7.0), 23),
                (510, (-85.0, 155.0, 690.0),  (-365.0, 545.0, 8.0), 27),
                (600, (300.0, -430.0, 1180.0), (-180.0, 350.0, 10.0), 31),
            )
        elif cam == "day44allapproach":
            # Revision: retain the original overview-to-low idea, but stay
            # wide long enough to watch the entire 504x322m Day 44 footprint
            # build before descending into the western edge of the same wave.
            beats = (
                (1,   (180.0, -300.0, 980.0), (-235.0, 350.0, 10.0), 29),
                (110, (45.0, -25.0, 790.0),  (-335.0, 520.0, 9.0), 27),
                (230, (-95.0, 265.0, 550.0), (-455.0, 650.0, 8.0), 25),
                (330, (-235.0, 500.0, 285.0), (-555.0, 690.0, 7.0), 24),
                (405, (-380.0, 625.0, 125.0), (-665.0, 680.0, 7.0), 25),
                (450, (-560.0, 660.0, 48.0), (-735.0, 650.0, 7.0), 28),
            )
        elif cam == "day44alldrone":
            # A higher and wider companion flight than day44drone.  The full
            # new district band stays readable while the drone moves with it.
            beats = (
                (1,   (-70.0, 255.0, 390.0), (-360.0, 610.0, 7.0), 24),
                (115, (-165.0, 420.0, 330.0), (-420.0, 680.0, 7.0), 23),
                (225, (-285.0, 590.0, 270.0), (-500.0, 690.0, 7.0), 23),
                (335, (-455.0, 735.0, 220.0), (-610.0, 675.0, 7.0), 24),
                (450, (-685.0, 845.0, 175.0), (-650.0, 635.0, 7.0), 26),
            )
        elif cam == "day44allfield":
            # Far enough away that both Bramble Park and Ember Ridge fit even
            # after the optical push.  Position and aim never move.
            field_z = terrain_height(-1170.0, 20.0) + 1.72
            beats = (
                (1,   (-1170.0, 20.0, field_z), (-510.0, 665.0, 8.0), 16),
                (450, (-1170.0, 20.0, field_z), (-510.0, 665.0, 8.0), 34),
            )
        elif cam == "day44approach":
            # Whole-city opener, then one unbroken descent into Bramble Park.
            beats = (
                (1,   (135.0, -225.0, 590.0), (-175.0, 335.0, 10.0), 30),
                (72,  (20.0, 35.0, 410.0),   (-265.0, 545.0, 9.0), 27),
                (150, (-105.0, 300.0, 205.0), (-325.0, 650.0, 7.0), 25),
                (238, (-230.0, 510.0, 72.0), (-345.0, 710.0, 6.5), 24),
                (360, (-326.0, 638.0, 13.0), (-334.0, 790.0, 6.0), 28),
            )
        elif cam == "day44street":
            # Human-height view down West Line Road North.  The camera barely
            # breathes forward while the north-to-south rise wave runs toward it.
            z0 = terrain_height(-756.8, 492.0) + 1.72
            z1 = terrain_height(-756.8, 507.0) + 1.72
            beats = (
                (1,   (-756.8, 492.0, z0), (-756.8, 690.0, 7.0), 34),
                (360, (-756.8, 507.0, z1), (-756.8, 705.0, 7.0), 36),
            )
        elif cam == "day44drone":
            # Fly with the northbound construction front, then bank west so
            # Ember Ridge joins the same moving reveal rather than becoming a cut.
            beats = (
                (1,   (-320.0, 500.0, 42.0), (-325.0, 610.0, 6.0), 25),
                (120, (-330.0, 610.0, 36.0), (-330.0, 720.0, 6.5), 23),
                (225, (-342.0, 748.0, 38.0), (-420.0, 780.0, 7.0), 23),
                (300, (-505.0, 760.0, 42.0), (-655.0, 710.0, 7.0), 24),
                (360, (-650.0, 720.0, 36.0), (-756.0, 655.0, 7.0), 27),
            )
        elif cam == "day44field":
            # A literal fixed observer in the western meadow.  Only focal
            # length changes, giving the requested camera zoom without a dolly.
            field_z = terrain_height(-925.0, 650.0) + 1.72
            beats = (
                (1,   (-925.0, 650.0, field_z), (-635.0, 665.0, 8.0), 24),
                (360, (-925.0, 650.0, field_z), (-635.0, 665.0, 8.0), 92),
            )
        elif cam == "day44overhead":
            # Completed-town sunset master with enough pitch for long shadows
            # and a visible horizon; aerial near clip protects roads and water.
            beats = (
                (1,   (520.0, -520.0, 1180.0), (-175.0, 335.0, 8.0), 34),
                (300, (170.0, -40.0, 1040.0), (-225.0, 410.0, 8.0), 38),
            )
        else:  # day44downtown
            # Low centreline run through the original downtown.  The path is
            # long enough for buildings to pass on both sides of the lens.
            beats = (
                (1,   (-3.0, -112.0, 2.20), (-3.0, -20.0, 3.0), 29),
                (105, (-3.0, -55.0, 2.20),  (-3.0, 38.0, 3.0), 29),
                (210, (-3.0, 4.0, 2.20),    (-3.0, 98.0, 3.0), 31),
                (300, (-3.0, 58.0, 2.20),   (-3.0, 148.0, 3.0), 34),
            )

        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam in ("day44southfpv", "day44swrooftop", "day44westbank",
                 "day44sereverse"):
        # Four independent Day 44 skyline films.  Each begins outside the
        # established city with a nearly horizontal, layered skyline, then
        # follows a different continuous low FPV route into the same 186-home
        # construction event.  The final keys stay oblique and low; none turns
        # into an overhead/map composition.
        aim = bpy.data.objects.new("Day44SkylineAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day44SkylineCamera")
        cam_data.clip_start = .35
        cam_data.clip_end = 15000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day44SkylineCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        if cam == "day44southfpv":
            beats = (
                # South: true skyline, lateral parallax, then a direct punch
                # through the old grid into Bramble Park and west to Ember.
                (1,   (92.0, -246.0, 49.0), (-4.0, 20.0, 25.0), 31),
                (42,  (24.0, -205.0, 46.0), (-16.0, 42.0, 24.0), 29),
                (78,  (-4.0, -118.0, 39.0), (-42.0, 125.0, 20.0), 27),
                (118, (-72.0, 85.0, 34.0), (-182.0, 330.0, 13.0), 24),
                (158, (-205.0, 360.0, 29.0), (-300.0, 548.0, 8.0), 22),
                (215, (-286.0, 535.0, 23.0), (-336.0, 655.0, 7.0), 21),
                (278, (-322.0, 664.0, 25.0), (-360.0, 785.0, 7.0), 22),
                (338, (-454.0, 760.0, 28.0), (-610.0, 718.0, 8.0), 23),
                (400, (-650.0, 735.0, 25.0), (-748.0, 650.0, 8.0), 26),
                (480, (-724.0, 700.0, 31.0), (-340.0, 390.0, 22.0), 32),
            )
        elif cam == "day44swrooftop":
            beats = (
                # South-west: roofs wipe laterally across the skyline before
                # the drone hooks round the mature west side and runs a new
                # street west-to-east, finishing south toward the old city.
                (1,   (-226.0, -150.0, 39.0), (-18.0, 34.0, 24.0), 34),
                (48,  (-292.0, -92.0, 37.0), (-32.0, 74.0, 23.0), 32),
                (88,  (-270.0, 32.0, 31.0), (-116.0, 205.0, 17.0), 29),
                (130, (-292.0, 220.0, 31.0), (-380.0, 402.0, 10.0), 25),
                (172, (-430.0, 420.0, 27.0), (-585.0, 540.0, 7.0), 23),
                (220, (-690.0, 566.0, 16.0), (-590.0, 594.0, 7.0), 22),
                (282, (-620.0, 630.0, 15.0), (-455.0, 666.0, 7.0), 22),
                (338, (-520.0, 701.0, 17.0), (-350.0, 738.0, 7.0), 23),
                (396, (-402.0, 770.0, 21.0), (-315.0, 808.0, 8.0), 26),
                (480, (-335.0, 786.0, 19.0), (-338.0, 510.0, 18.0), 31),
            )
        elif cam == "day44westbank":
            beats = (
                # West: trees and outer roofs layer against the downtown
                # silhouette, followed by a clockwise bank and diagonal dive
                # across both Day 44 districts.
                (1,   (-520.0, 112.0, 47.0), (-38.0, 55.0, 25.0), 33),
                (46,  (-520.0, 188.0, 44.0), (-20.0, 88.0, 24.0), 31),
                (86,  (-474.0, 275.0, 40.0), (-120.0, 250.0, 18.0), 28),
                (126, (-395.0, 365.0, 35.0), (-285.0, 500.0, 10.0), 24),
                (170, (-305.0, 492.0, 30.0), (-360.0, 615.0, 7.0), 22),
                (218, (-350.0, 602.0, 22.0), (-470.0, 675.0, 7.0), 21),
                (270, (-430.0, 680.0, 19.0), (-575.0, 726.0, 7.0), 21),
                (326, (-555.0, 746.0, 20.0), (-690.0, 770.0, 7.0), 22),
                (390, (-710.0, 790.0, 25.0), (-650.0, 650.0, 8.0), 27),
                (480, (-690.0, 754.0, 29.0), (-275.0, 400.0, 24.0), 34),
            )
        else:  # day44sereverse
            beats = (
                # South-east: a separate civic/Founder skyline angle, then a
                # northern wrap that meets the construction front from the
                # opposite (north-west to south-east) direction.
                (1,   (198.0, -172.0, 45.0), (8.0, 35.0, 25.0), 32),
                (46,  (145.0, -118.0, 42.0), (-8.0, 72.0, 24.0), 30),
                (88,  (100.0, 8.0, 36.0), (-15.0, 180.0, 19.0), 27),
                (128, (34.0, 230.0, 34.0), (-205.0, 490.0, 11.0), 24),
                (170, (-170.0, 520.0, 31.0), (-390.0, 760.0, 8.0), 22),
                (214, (-375.0, 836.0, 27.0), (-560.0, 790.0, 7.0), 21),
                (270, (-610.0, 822.0, 20.0), (-720.0, 742.0, 7.0), 21),
                (326, (-748.0, 735.0, 17.0), (-680.0, 620.0, 7.0), 22),
                (384, (-620.0, 640.0, 19.0), (-470.0, 590.0, 7.0), 24),
                (430, (-472.0, 580.0, 21.0), (-330.0, 552.0, 8.0), 27),
                (480, (-420.0, 560.0, 24.0), (-90.0, 245.0, 22.0), 33),
            )

        for frame, position, target, lens in beats:
            cam_obj.location = position
            aim.location = target
            cam_data.lens = lens
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
            cam_data.keyframe_insert("lens", frame=frame)
        for obj in (cam_obj, aim, cam_data):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        bpy.context.scene.camera = cam_obj
    elif cam == "day43fpv":
        # Day 43 film one: a continuous FPV-style trailer move.  The route
        # establishes the Founder skyline, accelerates into Harrow Green,
        # runs low beside the westbound construction wave, banks north through
        # Bramble Park, then crosses the city at speed to a level station
        # approach.  It never relies on a high map-like master.
        aim = bpy.data.objects.new("Day43FPVAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day43FPVCamera")
        cam_data.lens = 23
        cam_data.clip_start = 1.2
        cam_data.clip_end = 12000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day43FPVCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"
        beats = (
            # Strong skyline opener with foreground roofs and long-shadow depth.
            (1,   (154.0, -238.0, 132.0), (-8.0, 12.0, 17.0)),
            (50,  (112.0, -154.0, 106.0), (-42.0, 112.0, 15.0)),
            # Rapid real-estate-drone approach toward the first new street.
            (92,  (18.0, 72.0, 92.0), (-205.0, 405.0, 10.0)),
            (126, (-176.0, 350.0, 58.0), (-330.0, 455.0, 8.0)),
            # Low westbound pass: houses rise directly ahead and beside camera.
            (170, (-316.0, 426.0, 34.0), (-455.0, 474.0, 7.0)),
            (218, (-490.0, 438.0, 28.0), (-625.0, 481.0, 7.0)),
            (258, (-654.0, 449.0, 28.0), (-735.0, 496.0, 7.5)),
            # Bank north through the three new avenues as their wave climbs.
            (292, (-610.0, 515.0, 32.0), (-410.0, 585.0, 5.0)),
            (326, (-500.0, 625.0, 38.0), (-338.0, 710.0, 5.0)),
            (350, (-430.0, 718.0, 45.0), (-322.0, 765.0, 5.0)),
            # One decisive cross-city acceleration into the station approach.
            (382, (-70.0, 690.0, 70.0), (260.0, 585.0, 15.0)),
            (410, (300.0, 510.0, 48.0), (432.0, 557.0, 17.0)),
            # Level south-west reveal: entire station, tower and dome against sky.
            (440, (474.0, 427.0, 25.0), (435.0, 560.0, 16.0)),
            (480, (500.0, 438.0, 22.0), (431.0, 561.0, 17.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
                    kp.easing = "AUTO"
        for frame, lens in ((1, 28), (50, 25), (126, 22), (350, 22),
                            (410, 26), (440, 32), (480, 37)):
            cam_data.lens = lens
            cam_data.keyframe_insert("lens", frame=frame)
        for fc in obj_fcurves(cam_data):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day43pov":
        # Day 43 film two: intentionally cut, immersive, and suspenseful.
        # A brief oblique establish cuts to a human eye at the centre of Wicker
        # Avenue.  The north-to-south construction wave reaches and passes the
        # viewer before a close drone cut finishes the remaining streets.  The
        # finale comes from across the river, never repeating film one's gate
        # approach.
        aim = bpy.data.objects.new("Day43POVAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day43POVCamera")
        cam_data.lens = 30
        cam_data.clip_start = .18
        cam_data.clip_end = 12000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day43POVCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"
        eye_z = terrain_height(-330.0, 650.0) + 1.72
        north_eye = terrain_height(-330.0, 780.0) + 1.72
        beats = (
            # Oblique establish: compact and dimensional, not a whole-town map.
            (1,   (-120.0, 250.0, 162.0), (-430.0, 575.0, 10.0)),
            (55,  (-190.0, 335.0, 126.0), (-455.0, 610.0, 8.0)),
            # Hard cut to a nearly stationary human viewpoint straight up road.
            (56,  (-330.0, 646.0, eye_z), (-330.0, 780.0, north_eye)),
            (220, (-330.0, 653.0, eye_z), (-330.0, 787.0, north_eye)),
            # Hard cut to a genuinely close overhead.  The steep pitch keeps
            # the active lots filling the portrait instead of letting a low
            # terrain crest hide the construction wave at the horizon.
            (221, (-330.0, 515.0, 105.0), (-330.0, 515.0, 6.5)),
            (275, (-330.0, 590.0, 100.0), (-330.0, 590.0, 6.0)),
            (326, (-330.0, 690.0, 86.0), (-330.0, 690.0, 7.0)),
            (350, (-330.0, 755.0, 76.0), (-330.0, 755.0, 8.0)),
            # Fast diagonal transition to the river side of Point Station.
            (390, (180.0, 575.0, 62.0), (410.0, 560.0, 16.0)),
            (414, (292.0, 520.0, 42.0), (425.0, 561.0, 17.0)),
            # Different low three-quarter from the north-west river bank.  A
            # wider lens and lateral separation keep the cooling tower,
            # containment dome, turbine hall and surrounding site readable as
            # one complete reveal instead of letting the tower crop the plant.
            (440, (275.0, 650.0, 43.0), (440.0, 560.0, 16.0)),
            (480, (305.0, 635.0, 32.0), (442.0, 560.0, 17.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        # Lens changes reinforce the cuts: natural street perspective, then a
        # wider close drone, then compressed three-quarter station massing.
        for frame, lens in ((1, 29), (55, 29), (56, 35), (220, 35),
                            (221, 25), (350, 25), (414, 30), (480, 34)):
            cam_data.lens = lens
            cam_data.keyframe_insert("lens", frame=frame)
        for fc in obj_fcurves(cam_data):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day42reveal":
        # Day 42, exactly sixteen seconds, one continuous FPV-style drone move.
        # The batch is unusually wide: the final 109 Southline homes finish the
        # built quarter, then 211 homes carry the city west into Harrow Green.
        # A low street-following shot cannot honestly show all 320, so the move
        # has three deliberate scales:
        #
        #   0-3s    an authored Founder-district skyline push, close enough for
        #           the civic silhouettes and Burj spire to layer in portrait;
        #   3-6s    a fast realtor-drone transfer north-west over the existing
        #           city, rolling its look toward the new avenues;
        #   6-12.2s a westbound run above the southern quarter while roads draw
        #           and all 320 homes rise east-to-west just ahead of camera;
        #   12.2-16s a banking turn at the western edge, looking back east over
        #           completed foreground homes into the full Founder skyline.
        #
        # The 22mm lens is intentional. Portrait crops horizontal field of view
        # hard, while today's developed band is nearly a kilometre wide. The
        # wide lens keeps speed readable during the transfer and lets the final
        # climb hold both the new western edge and the established city.
        aim = bpy.data.objects.new("Day42RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day42RevealCamera")
        cam_data.lens = 22
        cam_data.clip_start = 7.0
        cam_data.clip_end = 9000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day42RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            # Founder skyline: a low southeast push, not another map view.
            (1,   (150.0, -245.0, 150.0), (0.0, -4.0, 17.0)),
            (45,  (126.0, -194.0, 126.0), (-3.0, 2.0, 18.0)),
            (88,  (88.0, -116.0, 104.0), (-12.0, 28.0, 16.0)),
            # Accelerate over the mature town and rotate toward chapter four.
            (120, (20.0, 8.0, 112.0), (-110.0, 220.0, 10.0)),
            (150, (-112.0, 210.0, 104.0), (-245.0, 405.0, 8.0)),
            (180, (-205.0, 350.0, 78.0), (-330.0, 448.0, 7.0)),
            # Westbound FPV run: avenues recede through the tall portrait axis.
            # Drop to a true low cinematic pass: roofs fill the lower frame
            # and the rising rows layer against one another, while the camera
            # remains safely above the 10-20m house envelopes.
            (220, (-302.0, 402.0, 44.0), (-430.0, 450.0, 7.0)),
            (270, (-442.0, 408.0, 35.0), (-565.0, 450.0, 7.0)),
            (320, (-575.0, 409.0, 34.0), (-694.0, 451.0, 7.0)),
            (366, (-704.0, 420.0, 43.0), (-746.0, 452.0, 8.0)),
            # Bank around the western edge rather than climbing into a map.
            # The camera finishes looking almost horizontally east: completed
            # new homes in front, mature neighborhoods through the middle, and
            # the Founder skyline layered on the sunset horizon.
            (390, (-748.0, 408.0, 62.0), (-585.0, 420.0, 10.0)),
            (430, (-735.0, 380.0, 82.0), (-300.0, 330.0, 15.0)),
            (480, (-650.0, 350.0, 95.0), (-25.0, 180.0, 22.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        # Preserve the 22mm FPV speed through the low pass, then smoothly
        # compress the finished city during the turn. A fixed 22mm lens made
        # the skyline technically present but visually tiny at the western
        # stand-off; 36mm gives the horizontal finale the intended hierarchy.
        for frame, lens in ((1, 22), (366, 22), (430, 30), (480, 36)):
            cam_data.lens = lens
            cam_data.keyframe_insert("lens", frame=frame)
        for fc in obj_fcurves(cam_data):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day41reveal":
        # Day 41, 30 seconds, one unbroken move. +300 in a day fills a whole
        # quarter at once -- the rest of Foundry Street, all of Lantern Row,
        # five north-south crosses, all of Southline Avenue and part of
        # Millrace, spanning x -172..191 and y 321..473 -- so this is not a
        # street-tracking shot like day 39 or 40. The drone goes UP and stays
        # up while the grid builds itself underneath, then comes home low.
        #
        #   0-4.7s    overhead of the existing town, high and drifting north.
        #   4.7-11s   one continuous arc out east and around to the north side
        #             of the new quarter, the look rotating N -> WNW -> S as
        #             the camera travels 900m. The turn is spread over the
        #             whole transit precisely so it banks instead of whipping.
        #   11-21.7s  held high, looking due south. The roads draw themselves
        #             on along their own length, then three hundred homes rise
        #             in a wave from the near edge to the far one, with the
        #             existing town on the horizon beyond them.
        #   21.7-30s  dive and run home low over the new streets toward the
        #             city, still looking south. No turn: the camera was put
        #             on the NORTH side of the quarter for the hold precisely
        #             so the return leg is a continuation, not a reversal.
        #
        # 24mm, not the 28 day 40 used. Portrait 9:16 covers ~46 degrees
        # horizontally at 24mm, and the quarter is 363m wide: framing it whole
        # needs 430m of standoff at 24mm against 500m at 28mm, and the wider
        # lens also suits the low run home.
        QUARTER_X, QUARTER_Y = 9.5, 397.0
        SHELF = 5.0

        aim = bpy.data.objects.new("Day41RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day41RevealCamera")
        cam_data.lens = 24
        # 8m rather than the aerial rule's 10: this camera finishes 20m off the
        # deck. Nothing comes within 8m of the lens, and 8/8000 still leaves
        # ample depth precision for the 500m beats.
        cam_data.clip_start = 8.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day41RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            # establishing overhead of the town that already exists
            (1,   (60.0, -300.0, 620.0), (20.0, 40.0, 6.0)),
            (90,  (70.0, -180.0, 600.0), (25.0, 150.0, 6.0)),
            # the long arc: out east, then north, turning to face back south
            (180, (170.0, 60.0, 578.0),  (40.0, 300.0, 8.0)),
            (250, (300.0, 330.0, 545.0), (60.0, 400.0, 8.0)),
            (280, (285.0, 455.0, 530.0), (45.0, 430.0, 8.0)),
            (310, (215.0, 555.0, 515.0), (35.0, 400.0, 8.0)),
            # held high on the north side, looking due south over the quarter
            (330, (105.0, 596.0, 502.0), (18.0, QUARTER_Y + 1.0, SHELF + 3.0)),
            (480, (40.0, 590.0, 494.0),  (10.0, QUARTER_Y, SHELF + 3.0)),
            (650, (-30.0, 580.0, 486.0), (2.0, QUARTER_Y - 1.0, SHELF + 3.0)),
            # dive and run home low, still south, over the streets just built
            (720, (-16.0, 470.0, 250.0), (6.0, 300.0, 10.0)),
            (790, (-6.0, 330.0, 92.0),   (8.0, 190.0, 10.0)),
            (850, (2.0, 230.0, 40.0),    (10.0, 100.0, 8.0)),
            (900, (8.0, 130.0, 20.0),    (14.0, 0.0, 6.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day40reveal":
        # Day 40, 27 seconds, TWO shots.
        #
        # Shot one, frames 1-630, one unbroken drone move that never reverses:
        #   0-5.0s    overhead of the city, high over downtown and drifting
        #             north-west. The establishing look at what already exists.
        #   5.0-10s   one continuous descending transfer out over the meadow,
        #             which climbs from 0 to 15m under the flight path.
        #   10-14.7s  run east down Foundry Street, brand new today, while its
        #             nineteen homes come up just ahead of the camera.
        #   14.7-19.3s cross south-east onto Northgate Avenue and keep running
        #             east; the thirty-nine homes rise ahead in the same order.
        #   19.3-21s  past the east end, climbing away from a finished street.
        #
        # The whole reveal is one eastward flight because the two streets fall
        # that way on the ground: Foundry runs x -164 to -82 at y 342, the new
        # stretch of Northgate Avenue runs x 8 to 184 at y 306. Approaching up
        # the arterial at x=-93 the way day 39 did would arrive in the MIDDLE
        # of Foundry and force the camera to double back, so this one crosses
        # the meadow further west and picks the street up at its west end.
        #
        # Shot two, frames 631-810: the filling station, alone, on its corner.
        # It is the first one the reserve has ever placed, it is the only thing
        # in today's batch that is not a house, and at 17m across it is lost in
        # a street-length tracking shot -- so it is held back and given its own
        # camera rather than rising as house number forty.
        #
        # Portrait 9:16 on a 28mm lens covers only ~40 degrees horizontally, so
        # every street beat flies ALONG the road rather than across it: the
        # frontage recedes into the tall axis, which has ~63 degrees.
        FOUNDRY_Y, AVENUE_Y = 342.0, 306.0
        SHELF = 5.0                      # the whole Northgate quarter is level

        aim = bpy.data.objects.new("Day40RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day40RevealCamera")
        cam_data.lens = 28
        # 10m near clip for the aerial beats, per the aerial-camera rule. The
        # closest this move comes to a roof is ~45m, on the street runs.
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day40RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        # Aim heights follow the ground under them: downtown is at zero, the
        # meadow crossing peaks near 15, and the Northgate shelf is flat at 5.
        beats = (
            (1,   (55.0, -330.0, 662.0),  (25.0, 55.0, 6.0)),
            (80,  (40.0, -292.0, 620.0),  (0.0, 100.0, 6.0)),
            (150, (-10.0, -190.0, 500.0), (-70.0, 175.0, 11.0)),
            (215, (-140.0, -20.0, 340.0), (-170.0, 250.0, 15.0)),
            (255, (-238.0, 120.0, 232.0), (-228.0, 300.0, 13.0)),
            (300, (-262.0, 258.0, 112.0), (-205.0, 336.0, 11.0)),
            # settled behind Foundry's west end, looking straight down it
            (340, (-235.0, 328.0, 62.0), (-160.0, FOUNDRY_Y, SHELF + 3.0)),
            (440, (-140.0, 334.0, 52.0), (-62.0, FOUNDRY_Y, SHELF + 3.0)),
            # south-east onto the avenue without ever turning round
            (500, (-45.0, 302.0, 54.0), (35.0, AVENUE_Y, SHELF + 3.0)),
            (580, (58.0, 300.0, 52.0), (138.0, AVENUE_Y, SHELF + 3.0)),
            (630, (150.0, 296.0, 86.0), (226.0, AVENUE_Y - 2.0, SHELF + 3.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)

        # Shot two: its own camera, cut to with a bound timeline marker rather
        # than whipped to, because a 250m jump back west is not a camera move.
        gas_aim = bpy.data.objects.new("Day40GasAim", None)
        world_col.objects.link(gas_aim)
        gas_data = bpy.data.cameras.new("Day40GasCamera")
        gas_data.lens = 30
        gas_data.clip_start = 1.0
        gas_data.clip_end = 4000.0
        gas_data.dof.use_dof = False
        gas_obj = bpy.data.objects.new("Day40GasCamera", gas_data)
        world_col.objects.link(gas_obj)
        gas_track = gas_obj.constraints.new("TRACK_TO")
        gas_track.target = gas_aim
        gas_track.track_axis = "TRACK_NEGATIVE_Z"
        gas_track.up_axis = "UP_Y"

        # A slow arc from the south-east round to the south, closing and
        # settling as the station comes up. ~42 degrees down, so the forecourt
        # fills the tall axis instead of 40m of empty sky above a 6m canopy.
        gas_beats = (
            (DAY40_GAS_CUT, (DAY40_GAS_X + 32.0, DAY40_GAS_Y - 28.0, SHELF + 37.0),
             (DAY40_GAS_X, DAY40_GAS_Y - 4.0, SHELF + 1.0)),
            (720, (DAY40_GAS_X + 18.0, DAY40_GAS_Y - 32.0, SHELF + 29.0),
             (DAY40_GAS_X - 1.0, DAY40_GAS_Y - 5.0, SHELF + 1.0)),
            (810, (DAY40_GAS_X + 7.0, DAY40_GAS_Y - 33.0, SHELF + 25.0),
             (DAY40_GAS_X - 1.5, DAY40_GAS_Y - 6.0, SHELF + 1.0)),
        )
        for frame, position, target in gas_beats:
            gas_obj.location = position
            gas_aim.location = target
            gas_obj.keyframe_insert("location", frame=frame)
            gas_aim.keyframe_insert("location", frame=frame)

        for obj in (cam_obj, aim, gas_obj, gas_aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"

        scene = bpy.context.scene
        scene.camera = cam_obj
        for marker_name, marker_frame, marker_cam in (
                ("day40_drone", 1, cam_obj),
                ("day40_gasstation", DAY40_GAS_CUT, gas_obj)):
            marker = scene.timeline_markers.new(marker_name, frame=marker_frame)
            marker.camera = marker_cam
    elif cam in ("story001pricesign", "story001dusk"):
        # Followville Stories #001. Four cameras cut by bound timeline markers
        # in the day clip, exactly as day40reveal cuts to its station shot: a
        # 20m jump is a cut, not a camera move. Shot 5 is its own --time dusk
        # run because time of day is a whole-run setting.
        #
        # Portrait 9:16 fits the sensor to the TALL axis, so a 30mm lens covers
        # only ~37 degrees horizontally. The station is 16m wide, which is why
        # the establishing shots stand ~29m off rather than the ~25m that would
        # frame it in landscape.
        GX, GY, SH = DAY40_GAS_X, DAY40_GAS_Y, STORY001_SHELF
        story_cams = []

        def story_cam(name, lens, near, beats, up_axis="UP_Y"):
            aim = bpy.data.objects.new(name + "Aim", None)
            world_col.objects.link(aim)
            data = bpy.data.cameras.new(name)
            data.lens = lens
            data.clip_start = near
            data.clip_end = 4000.0
            data.dof.use_dof = False
            obj = bpy.data.objects.new(name, data)
            world_col.objects.link(obj)
            track = obj.constraints.new("TRACK_TO")
            track.target = aim
            track.track_axis = "TRACK_NEGATIVE_Z"
            track.up_axis = up_axis
            for frame, position, target in beats:
                obj.location = position
                aim.location = target
                obj.keyframe_insert("location", frame=frame)
                aim.keyframe_insert("location", frame=frame)
            for item in (obj, aim):
                for fc in obj_fcurves(item):
                    for kp in fc.keyframe_points:
                        kp.interpolation = "BEZIER"
            story_cams.append(obj)
            return obj

        # WHY THE ESTABLISHING SHOTS ARE ELEVATED AND HEAD-ON, not the oblique
        # ground-level three-quarters this started as:
        #
        # Northgate Avenue has houses on BOTH sides -- the north row at y=314.5
        # (the station's own row) and the south row at y=297.5 -- leaving an
        # 8.3m corridor between their facing walls. Worse, TYPE_FOOTPRINT gives
        # a house y from -4.9 to +3.8, so the neighbours' south faces land at
        # y=309.6, which is 1.6m CLOSER to the street than the station's own
        # apron edge at 311.2. The station is set back behind its neighbours.
        #
        # So no oblique ground angle sees it: house 680 at (132.36, 314.5) eats
        # the eastern third of the frame, totem included, from anywhere down the
        # street, and the corridor itself is far too narrow to stand back the
        # ~29m a 16m-wide subject needs in portrait. The only clear line is up
        # and over the south row, looking straight in.
        if cam == "story001dusk":
            # Shot 5. Shot 1's framing exactly, locked off -- the match is the
            # payoff, so nothing may drift.
            story_cam("Story001Dusk", 30, 1.0,
                      ((1, (GX, 291.0, SH + 19.0), (GX, 315.0, SH + 2.0)),))
        else:
            # Shot 1, 1-84: the station new, clean and empty. A 2.5m push.
            # Sightline clears the south row's roofs by ~12m at its tightest.
            story_cam("Story001Establish", 30, 1.0, (
                (1,  (GX, 291.0, SH + 19.0), (GX, 315.0, SH + 2.0)),
                (84, (GX, 293.5, SH + 17.5), (GX, 315.0, SH + 2.0))))
            # Shot 2, 85-150: the totem, static, ~7.3m off the price face.
            story_cam("Story001Totem", 30, .40, (
                (85,  (129.0, 306.3, SH + 4.6),
                 (STORY001_TOTEM_X, STORY001_PRICE_Y, STORY001_PRICE_Z)),
                (150, (129.0, 306.3, SH + 4.6),
                 (STORY001_TOTEM_X, STORY001_PRICE_Y, STORY001_PRICE_Z))))
            # Shot 3, 151-240: elevated three-quarter from the south-east.
            # Ground level here stood inside the south row, and every oblique
            # angle low enough to feel like a street shot put house 680 across
            # the forecourt. Solved by search: this is the shallowest position
            # with a clear line to all seven station points AND the head of the
            # queue, with every one of them inside the portrait frame.
            #
            # It shows the forecourt and the first cars turning in, NOT the
            # whole queue: station plus full queue spans 40m along the frame's
            # NARROW axis, which 9:16 cannot hold at any usable distance. How
            # far the line really goes is shot 4's reveal, which is the order
            # the story wants anyway.
            story_cam("Story001Queue", 30, 1.0, (
                (151, (142.0, 294.0, SH + 18.0), (124.0, 312.0, SH + 1.8)),
                (240, (140.2, 295.4, SH + 17.4), (124.0, 312.0, SH + 1.8))))
            # Shot 4, 241-330: top-down. UP_X puts the avenue along the frame's
            # tall axis, which is the only way 50m of queue fits a 9:16 frame.
            # 10m near clip, per the aerial-camera rule.
            story_cam("Story001Overhead", 30, 10.0, (
                (241, (126.0, 314.0, SH + 44.0), (126.0, 314.0, SH)),
                (330, (131.0, 314.0, SH + 45.0), (131.0, 314.0, SH))),
                up_axis="UP_X")

        scene = bpy.context.scene
        scene.camera = story_cams[0]
        for marker_frame, marker_cam in zip((1, 85, 151, 241), story_cams):
            marker = scene.timeline_markers.new(
                "story001_%03d" % marker_frame, frame=marker_frame)
            marker.camera = marker_cam
    elif cam == "day39reveal":
        # Day 39, 20 seconds, one unbroken move in four beats:
        #   0-6.0s    high over downtown, drifting north. The establishing look
        #             at the city that already exists.
        #   6.0-11.0s one continuous transfer north, up the corridor the new
        #             arterial runs in. The roads land underneath it in
        #             flight, so the quarter arrives road-first-then-houses.
        #   11-17.9s  track east along Northgate Avenue while the homes rise
        #             one at a time, west to east, just ahead of the camera.
        #   17.9-20s  lift away, looking back down the finished street.
        #
        # Twenty seconds rather than ten because thirty-three homes cannot
        # read as "one at a time" in three: at ten seconds each house got
        # three frames, which is a tenth of a second and looks like a single
        # pop. Six frames each gives them six seconds, and the opening hold
        # over the city grew from two seconds to six.
        #
        # Flying ALONG the street rather than framing it whole is forced by the
        # arithmetic: the batch spans about 175m, and a 30mm lens on a 9:16
        # frame only covers that from ~300m back, which is too far to read a
        # house. Tracking the row keeps every home close.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest = [b for b in buildings
                  if b["type"] == "house" and b.get("day") == latest_day]
        points = sorted((build_pos(b) for b in newest), key=lambda p: p[0])
        if points:
            west, east = points[0], points[-1]
        else:                      # replay of a day with no new homes
            west, east = (-185.0, 306.0), (-10.0, 306.0)
        street_y = sum(p[1] for p in points) / len(points) if points else 306.0

        aim = bpy.data.objects.new("Day39RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day39RevealCamera")
        cam_data.lens = 30
        # 10m near clip for the aerial beats, per the aerial-camera rule; the
        # closest this move ever gets to a roof is the final track at ~40m.
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day39RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        track = cam_obj.constraints.new("TRACK_TO")
        track.target = aim
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        beats = (
            # 0-6.0s establishing: downtown from the south, high and looking
            # down, drifting slowly. Three keys rather than two so the drift
            # decelerates into the transfer instead of snapping into it.
            (1,   (70.0, -200.0, 285.0), (5.0, -30.0, 10.0)),
            (110, (60.0, -176.0, 272.0), (3.0, -10.0, 9.0)),
            (180, (44.0, -136.0, 248.0), (0.0, 22.0, 8.0)),
            # 6.0-11.0s transfer north, following the arterial's own corridor
            (268, (-25.0, 70.0, 172.0), (-93.0, 228.0, 6.0)),
            (325, (-100.0, 190.0, 92.0), (-100.0, 292.0, 5.0)),
            # arrive at the west end of the new frontage
            (360, (west[0] + 15.0, street_y - 62.0, 50.0),
                  (west[0] + 50.0, street_y + 2.0, 6.0)),
            # 11-17.9s track east, staying just behind the homes as they come up
            (520, (-70.0, street_y - 58.0, 52.0), (-40.0, street_y + 2.0, 6.0)),
            # then swing north-east and lift, looking back down the finished
            # street. Tracking any closer to the end was the first attempt and
            # it ended on eight houses in an empty green field: north of the
            # street there is nothing to see yet, so the last beat has to turn
            # round and put the arterial and the town behind the new frontage.
            (600, (55.0, street_y + 95.0, 150.0), (-85.0, street_y + 2.0, 6.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day36reveal":
        # Day 36, 16 seconds, three beats and one unbroken move:
        #   0-6s    locked off on the downtown skyline, ~42 degrees above the
        #           horizontal looking down on it. Deliberately static -- the
        #           only motion is the town's own traffic.
        #   6-8.6s  one fast drone transfer, 700m south-east across the whole
        #           town, to the new Heron Reach cul-de-sac in River Meadows.
        #   8.6-16s a slow descending push while all 13 homes rise, ending
        #           low enough to read the porches and the new street.
        # Heron Reach is a single compact run of 13 homes, so unlike Day 35
        # this needs no split -- one aim point frames the whole batch. The
        # approach deliberately follows the street's own axis so the row of
        # houses climbs the tall portrait frame instead of crossing it.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        points = [build_pos(b) for b in newest_homes]
        hx = sum(p[0] for p in points) / len(points) if points else 560.8
        hy = sum(p[1] for p in points) / len(points) if points else -296.1
        if len(points) >= 2:
            ax, ay = points[-1][0] - points[0][0], points[-1][1] - points[0][1]
            span = math.hypot(ax, ay)
        else:
            ax, ay, span = 69.0, -60.0, 91.5
        ux, uy = (ax / span, ay / span) if span > 1.0 else (.755, -.656)

        def perch(distance, degrees, lift=9.0):
            """Camera `distance` back down the street axis, `degrees` above it."""
            return (hx - ux * distance, hy - uy * distance,
                    lift + distance * math.tan(math.radians(degrees)))

        aim = bpy.data.objects.new("Day36RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day36RevealCamera")
        cam_data.lens = 28
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day36RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"

        # The opening reuses the framing Zach picked off the Day 35 reel: from
        # the south-south-east above Fire Station 1, looking north-north-west
        # up the Burj's spire with downtown filling the frame and a thin band
        # of sky and far suburbs across the top. It is 30 degrees above the
        # horizontal -- clearly a drone looking down, but not so steep that
        # the skyline stops reading as a skyline.
        #
        # The hold is two identical keys, not one. Auto-clamped bezier handles
        # keep an equal-valued pair perfectly flat, so the drone genuinely sits
        # still for the full six seconds and only then accelerates away.
        skyline_at = (92.8, -127.8, 118.4)
        skyline_on = (25.0, 6.0, 42.0)
        beats = (
            (1, skyline_at, skyline_on),
            (180, skyline_at, skyline_on),
            # 6-8.6s: climb out, swing right off downtown, and run south-east
            # across the whole town at roughly 150 m/s.
            (212, (150.0, -170.0, 190.0), (260.0, -140.0, 25.0)),
            (258, perch(115.0, 34.0), (hx, hy, 9.0)),
            # 8.6-16s: settle in and keep descending while the homes come up.
            (330, perch(100.0, 30.0), (hx, hy, 8.5)),
            (405, perch(88.0, 27.0), (hx, hy, 8.0)),
            (frame_end, perch(82.0, 25.0), (hx, hy, 8.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day34fire":
        # Day 34: spend five seconds on an angled downtown skyline where a
        # render-only fire response is readable but remains background action,
        # then make one fast drone transfer to all 31 Eastbank homes.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        points = [build_pos(b) for b in newest_homes]
        hx = sum(p[0] for p in points) / len(points) if points else 425.0
        hy = sum(p[1] for p in points) / len(points) if points else 325.0

        aim = bpy.data.objects.new("Day34FireAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day34FireCamera")
        cam_data.lens = 43
        cam_data.clip_start = 10.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day34FireCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-5s: a low-enough skyline angle to retain building depth. The
            # burning unclaimed townhouse (64.5,-38.5) and Station 1 response on
            # the same north/south street sit right of downtown center.
            (1, (148.0, -190.0, 84.0), (12.0, -10.0, 11.0)),
            (78, (136.0, -174.0, 76.0), (14.0, -11.0, 11.0)),
            (150, (120.0, -151.0, 67.0), (17.0, -12.0, 11.5)),
            # 5-6.7s: deliberately quick cross-town drone transfer.
            (168, (230.0, -66.0, 118.0), (210.0, 126.0, 15.0)),
            (200, (566.0, 146.0, 222.0), (hx, hy, 8.0)),
            # 6.7-16s: descend in a broad three-quarter arc while every home
            # rises. The framing includes late Millstone and all Ferry Street.
            (260, (554.0, 179.0, 190.0), (hx, hy + 2.0, 7.5)),
            (350, (536.0, 216.0, 158.0), (hx, hy + 4.0, 7.0)),
            (420, (535.0, 218.0, 157.0), (hx, hy + 4.0, 6.5)),
            (frame_end, (532.0, 222.0, 154.0), (hx, hy + 4.0, 6.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day33storm":
        # Day 33: a stormy whole-town establish, two overlapping waves for the
        # 33 new homes, and a deliberate final descent onto First Alert Weather.
        # The station's rise is render-only; its canonical seed is not duplicated.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        lodgepole = [b for b in newest_homes
                     if int(b.get("plan_id", 0)) <= 526]
        millstone = [b for b in newest_homes
                     if int(b.get("plan_id", 0)) >= 527]
        weather = next((b for b in buildings
                        if b.get("type") == "weatherstation"), None)

        def _mid(group, fallback):
            if not group:
                return fallback
            pts = [build_pos(b) for b in group]
            return (sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts))

        lodge_x, lodge_y = _mid(lodgepole, (582.0, 264.0))
        mill_x, mill_y = _mid(millstone, (448.0, 226.0))
        weather_x, weather_y = build_pos(weather) if weather else (29.5, 106.0)
        weather_z = weather_station_base_height() + 5.6

        aim = bpy.data.objects.new("Day33StormAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day33StormCamera")
        cam_data.lens = 36
        cam_data.clip_start = .35
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day33StormCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-3.7s: the entire storm-darkened town establishes geography.
            (1, (790.0, -610.0, 930.0), (280.0, 30.0, 10.0)),
            (70, (735.0, -420.0, 680.0), (350.0, 70.0, 9.0)),
            (110, (675.0, -230.0, 430.0), (470.0, 145.0, 8.0)),
            # 3.7-12.0s: one wide, legible composition holds Lodgepole and
            # Millstone together for the entire 33-home rise. Do not turn this
            # back into two close-ups; Cade needs to see the complete batch.
            (120, (760.0, -140.0, 455.0),
             ((lodge_x + mill_x) / 2, (lodge_y + mill_y) / 2, 9.0)),
            (180, (735.0, -85.0, 425.0),
             ((lodge_x + mill_x) / 2, (lodge_y + mill_y) / 2, 8.0)),
            (270, (705.0, -25.0, 392.0),
             ((lodge_x + mill_x) / 2, (lodge_y + mill_y) / 2, 8.0)),
            (360, (675.0, 25.0, 360.0),
             ((lodge_x + mill_x) / 2, (lodge_y + mill_y) / 2, 8.0)),
            # 12.0-15.2s: a high cross-town transfer avoids an abrupt zoom.
            (405, (480.0, 60.0, 245.0), (275.0, 112.0, 10.0)),
            (456, (205.0, 35.0, 160.0),
             (weather_x, weather_y, weather_z)),
            # 15.0-20.0s: settle in front of the station while it rises in rain.
            (500, (102.0, 54.0, 78.0),
             (weather_x, weather_y, weather_z)),
            (550, (77.0, 64.0, 53.0),
             (weather_x, weather_y, weather_z)),
            (frame_end, (66.0, 69.0, 42.0),
             (weather_x, weather_y, weather_z)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day32campaign":
        # Day 32: establish the larger town, follow all 31 Timber Bend homes,
        # then descend to the roadside billboard and moving campaign semi.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        timber_road = [b for b in newest_homes
                       if int(b.get("plan_id", 0)) <= 500]
        lodgepole = [b for b in newest_homes
                     if int(b.get("plan_id", 0)) >= 501]

        def _mid(group, fallback):
            if not group:
                return fallback
            pts = [build_pos(b) for b in group]
            return (sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts))

        tx32, ty32 = _mid(timber_road, (512.2, 216.0))
        lx32, ly32 = _mid(lodgepole, (546.4, 210.9))
        billboard = (556.1, 252.5)

        def _above_ground(x, y, clearance):
            """Return an absolute Z that follows the authored terrain grade."""
            return terrain_height(x, y) + clearance

        aim = bpy.data.objects.new("Day32CampaignAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day32CampaignCamera")
        cam_data.lens = 42
        # The final roadside shots run close to elevated terrain.  A long near
        # clip plane cuts through the truck and road even when the camera is
        # correctly above grade, so keep this suitable for a human-scale shot.
        cam_data.clip_start = 0.25
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day32CampaignCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-3.7s: whole-town drone establish, including the river chapter.
            (1, (800.0, -650.0, 950.0), (280.0, 20.0, 8.0)),
            (70, (760.0, -480.0, 700.0), (330.0, 40.0, 8.0)),
            (110, (700.0, -300.0, 430.0), (440.0, 110.0, 7.0)),
            # 3.7-11.3s: descend through Timber Bend Road and Lodgepole Loop
            # while the 31 follower homes rise in one overlapping wave.
            (140, (660.0, -90.0, 260.0),
             (tx32, ty32 - 18.0,
              _above_ground(tx32, ty32 - 18.0, 6.0))),
            (210, (625.0, 75.0, 165.0),
             (tx32, ty32, _above_ground(tx32, ty32, 6.0))),
            (285, (610.0, 145.0, 118.0),
             ((tx32 + lx32) / 2, (ty32 + ly32) / 2,
              _above_ground((tx32 + lx32) / 2,
                            (ty32 + ly32) / 2, 6.0))),
            (340, (620.0, 160.0, 96.0),
             (lx32, ly32, _above_ground(lx32, ly32, 6.0))),
            # 11.3-15.7s: descend to a readable, front-on billboard view.
            (390, (590.0, 190.0, 64.0),
             (billboard[0], billboard[1],
              _above_ground(*billboard, 5.2))),
            (425, (575.0, 215.0, _above_ground(575.0, 215.0, 35.0)),
             (billboard[0], billboard[1],
              _above_ground(*billboard, 5.2))),
            (470, (570.0, 222.0, _above_ground(570.0, 222.0, 25.0)),
             (billboard[0], billboard[1],
              _above_ground(*billboard, 5.2))),
            # 15.7-20.0s: track the semi's campaign side as it approaches the
            # billboard. The raised southeast-side camera looks over the nearby
            # house roofs while holding both campaign messages in one frame.
            (495, (568.0, 223.0, _above_ground(568.0, 223.0, 23.0)),
             (553.0, 248.0, _above_ground(553.0, 248.0, 4.8))),
            (545, (570.0, 220.0, _above_ground(570.0, 220.0, 22.0)),
             (553.0, 248.0, _above_ground(553.0, 248.0, 4.8))),
            (frame_end,
             (570.0, 220.0, _above_ground(570.0, 220.0, 20.0)),
             (553.0, 248.0, _above_ground(553.0, 248.0, 4.8))),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day31reveal":
        # Day 31: one continuous 20-second drone story. Establish the complete
        # town, descend into the two newest housing clusters while all twenty
        # homes rise, then cross back to a settled front view of City Hall.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        cedarbank = [b for b in newest_homes
                     if int(b.get("plan_id", 0)) <= 472]
        timber_bend = [b for b in newest_homes
                       if int(b.get("plan_id", 0)) >= 473]

        def _mid(group, fallback):
            if not group:
                return fallback
            pts = [build_pos(b) for b in group]
            return (sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts))

        cx31, cy31 = _mid(cedarbank, (620.0, 57.0))
        tx31, ty31 = _mid(timber_bend, (494.0, 151.0))

        aim = bpy.data.objects.new("Day31RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day31RevealCamera")
        cam_data.lens = 38
        cam_data.clip_start = 7.0
        cam_data.clip_end = 8000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day31RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-4.2s: broad, readable portrait establish of the whole town.
            (1, (780.0, -650.0, 900.0), (260.0, 10.0, 8.0)),
            (70, (750.0, -500.0, 700.0), (300.0, 15.0, 8.0)),
            (125, (720.0, -330.0, 430.0), (410.0, 30.0, 7.0)),
            # 4.2-9.0s: descend over the final Cedarbank/Alder Court homes.
            (155, (760.0, -170.0, 260.0), (cx31, cy31, 6.0)),
            (215, (690.0, -60.0, 155.0), (cx31, cy31, 6.0)),
            (270, (650.0, 45.0, 125.0), (cx31, cy31 + 8.0, 6.0)),
            # 9.0-13.0s: sweep northwest along the new Timber Bend run.
            (325, (605.0, 125.0, 115.0),
             ((cx31 + tx31) / 2, (cy31 + ty31) / 2, 6.0)),
            (390, (550.0, 215.0, 98.0), (tx31, ty31, 6.0)),
            # 13.0-17.4s: climb and cross the town toward its civic center.
            (425, (570.0, 170.0, 155.0), (450.0, 80.0, 8.0)),
            (470, (420.0, 10.0, 260.0), (220.0, -30.0, 9.0)),
            (520, (230.0, -20.0, 180.0), (80.0, -105.0, 10.0)),
            # 17.4-20.0s: settle into City Hall's front architectural view.
            (555, (125.0, -45.0, 90.0),
             (CITY_HALL_X, CITY_HALL_Y, 10.0)),
            (580, (82.0, -66.0, 56.0),
             (CITY_HALL_X, CITY_HALL_Y, 10.0)),
            (frame_end, (65.0, -79.0, 44.0),
             (CITY_HALL_X, CITY_HALL_Y, 10.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day30reveal":
        # Day 30: one continuous 18-second drone move. Five seconds of a low,
        # close city angle (~33 degrees, downtown filling frame), then a
        # decelerating transfer northeast into Cedarbank while all forty-six
        # river/log homes rise. No second shot and no landmark finale: the new
        # district itself is the payoff.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        lane = [b for b in newest_homes
                if 416 <= int(b.get("plan_id", 0)) <= 444]
        court = [b for b in newest_homes
                 if 445 <= int(b.get("plan_id", 0)) <= 472]

        def _mid(group, fallback):
            if not group:
                return fallback
            pts = [build_pos(b) for b in group]
            return (sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts))

        lx, ly = _mid(lane, (527.0, 40.0))
        ax, ay = _mid(court, (581.0, 11.0))
        hx, hy = _mid(newest_homes, (547.0, 29.0))

        aim = bpy.data.objects.new("Day30RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day30RevealCamera")
        cam_data.lens = 38
        cam_data.clip_start = 7.0
        cam_data.clip_end = 7000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day30RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-5s: a low, close, roughly 33-degree drone angle that lets
            # downtown fill the frame with the spire standing over it and the
            # civic plaza in the near foreground, then accelerates east. This
            # opening framing is held deliberately tight per Zach's reference
            # still - do not raise it back to a distant overhead establish.
            # Shifted +13m east on 2026-07-31 to track City Hall and Civic
            # Square after the landmark ground-level correction moved them.
            (1, (121.0, -318.0, 196.0), (41.0, -46.0, 10.0)),
            (60, (189.0, -300.0, 206.0), (77.0, -30.0, 9.0)),
            (110, (278.0, -274.0, 228.0), (158.0, -22.0, 8.0)),
            (150, (392.0, -242.0, 256.0), (300.0, -40.0, 7.0)),
            # 5-14s: descend northeast into Cedarbank and travel the new lane as
            # the forty-six homes arrive in overlapping waves.
            (212, (560.0, -170.0, 208.0), (lx - 11.0, ly - 44.0, 6.0)),
            (282, (600.0, -70.0, 148.0), (lx, ly - 20.0, 6.0)),
            (352, (592.0, 14.0, 112.0), (lx, ly + 8.0, 6.0)),
            (420, (604.0, 74.0, 102.0), (lx + 9.0, ly + 34.0, 6.0)),
            # 14-18s: swing across Alder Court and settle into a wide hold that
            # keeps the finished district, the river, and the old city in frame.
            (472, (656.0, 58.0, 120.0), (ax, ay, 6.0)),
            (frame_end, (704.0, -34.0, 172.0), (hx + 13.0, hy - 11.0, 8.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day29reveal":
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest_homes = [b for b in buildings
                        if b["type"] == "house" and b.get("day") == latest_day]
        hx = (sum(build_pos(b)[0] for b in newest_homes) / len(newest_homes)
              if newest_homes else 458.0)
        hy = (sum(build_pos(b)[1] for b in newest_homes) / len(newest_homes)
              if newest_homes else -112.0)
        station = next((b for b in buildings
                        if b["type"] == "raftingstation"), None)
        sx, sy = build_pos(station) if station else (
            RAFTING_STATION_X, RAFTING_STATION_Y)

        aim = bpy.data.objects.new("Day29RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day29RevealCamera")
        cam_data.lens = 36
        cam_data.clip_start = 7.0
        cam_data.clip_end = 6000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day29RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-3s: a broad realtor-drone arc holds downtown and the mature
            # neighborhoods, with the river chapter legible in the distance.
            (1, (430.0, -520.0, 650.0), (40.0, -10.0, 6.0)),
            (50, (520.0, -430.0, 580.0), (90.0, -20.0, 6.0)),
            (90, (585.0, -320.0, 380.0), (180.0, -40.0, 5.0)),
            # 3-11s: descend into Rivergate and fly the new river-house street
            # while all thirty-one follower homes arrive in overlapping waves.
            (120, (600.0, -245.0, 185.0), (hx, hy, 6.0)),
            (180, (565.0, -205.0, 115.0), (hx, hy + 5.0, 6.0)),
            (260, (530.0, -135.0, 75.0), (hx + 4.0, hy + 24.0, 6.5)),
            (330, (500.0, -90.0, 62.0), (455.0, -75.0, 7.0)),
            # 11-18s: cross the water at low drone height and finish on the
            # west-bank outfitter as its lodge, gear, dock, and rafts rise.
            (380, (430.0, -78.0, 52.0), (370.0, -35.0, 5.0)),
            (430, (430.0, -100.0, 75.0), (sx + 10.0, sy, 5.0)),
            (500, (400.0, -82.0, 55.0), (sx + 14.0, sy, 4.8)),
            (frame_end, (390.0, -72.0, 48.0), (sx + 14.0, sy, 4.7)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day28reveal":
        newest = [b for b in buildings
                  if b["type"] == "house" and b.get("day") == max(
                      (item.get("day", 0) for item in buildings), default=0)]
        summit = [b for b in newest if int(b.get("plan_id", 0)) <= 366]
        river_homes = [b for b in newest if int(b.get("plan_id", 0)) >= 367]
        sx = sum(build_pos(b)[0] for b in summit)/len(summit) if summit else 260.0
        sy = sum(build_pos(b)[1] for b in summit)/len(summit) if summit else -240.0
        rx = (sum(build_pos(b)[0] for b in river_homes)/len(river_homes)
              if river_homes else 455.0)
        ry = (sum(build_pos(b)[1] for b in river_homes)/len(river_homes)
              if river_homes else -208.0)
        aim = bpy.data.objects.new("Day28RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day28RevealCamera")
        cam_data.lens = 43
        cam_data.clip_start = 8.0
        cam_data.clip_end = 6000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day28RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-2.5s: establish the entire completed Day 27 city from a high
            # portrait drone, then descend decisively toward Summit Court.
            (1, (635.0, -402.0, 1206.0), (129.0, -7.0, 0.0)),
            (30, (590.0, -438.0, 990.0), (145.0, -35.0, 2.0)),
            (70, (205.0, -356.0, 142.0), (sx-12.0, sy+8.0, 8.0)),
            (130, (238.0, -330.0, 105.0), (sx+8.0, sy, 6.0)),
            # 2.3-9.0s: the ten Summit Court homes finish the original plan,
            # then the drone pulls east as the river and viaduct rise.
            (160, (318.0, -354.0, 126.0), (360.0, -212.0, 5.0)),
            (225, (402.0, -344.0, 112.0), (365.0, -205.0, 7.0)),
            (270, (448.0, -316.0, 88.0), (372.0, -205.0, 8.0)),
            # 9.0-12.0s: Crossing Way forms as the drone crosses the bridge.
            (310, (405.0, -276.0, 60.0), (407.0, -214.0, 7.5)),
            (360, (472.0, -269.0, 54.0), (rx-15.0, ry, 6.0)),
            # 12-20s: the eighteen timber homes rise beyond the water, ending
            # wide enough to hold river, bridge, old ridge, and new chapter.
            (420, (552.0, -294.0, 72.0), (rx, ry, 6.5)),
            (520, (527.0, -326.0, 105.0), (rx-25.0, ry+8.0, 7.0)),
            (frame_end, (512.0, -372.0, 150.0), (430.0, -196.0, 8.5)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day27reveal":
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest = [b for b in buildings
                  if b["type"] == "house" and b.get("day") == latest_day]
        points = [build_pos(b) for b in newest]
        hx = sum(x for x, _y in points) / len(points) if points else cx
        hy = sum(y for _x, y in points) / len(points) if points else cy
        theater = next((b for b in buildings if b["type"] == "movietheater"), None)
        tx, ty = build_pos(theater) if theater else (-83.5, 60.5)
        if theater and "px" not in theater:
            tx += LOT
            ty += LOT

        aim = bpy.data.objects.new("Day27RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day27RevealCamera")
        cam_data.lens = 46
        cam_data.clip_start = 7.0
        cam_data.clip_end = 5000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day27RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-6s: strong whole-city hook with a single curved drone push.
            (1, (238.0, -325.0, 168.0), (0.0, -46.0, 15.0)),
            (92, (195.0, -300.0, 138.0), (18.0, -76.0, 12.0)),
            (180, (154.0, -278.0, 108.0), (60.0, -122.0, 9.0)),
            # 6-14s: North Ridge fills the portrait frame as all 36 homes rise.
            (218, (121.0, -313.0, 86.0), (hx, hy - 7.0, 5.2)),
            (330, (139.0, -294.0, 61.0), (hx + 7.0, hy, 5.0)),
            (418, (158.0, -273.0, 50.0), (hx + 12.0, hy + 5.0, 5.0)),
            # 14-20s: decisive transfer and descending final push to the cinema.
            (450, (88.0, -150.0, 98.0), (tx, ty, 10.0)),
            (505, (-15.0, -18.0, 58.0), (tx, ty, 8.5)),
            (frame_end, (-57.0, 18.0, 25.0), (tx, ty, 7.2)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day26reveal":
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        newest = [b for b in buildings
                  if b["type"] == "house" and b.get("day") == latest_day]
        points = [build_pos(b) for b in newest]
        hx = sum(x for x, _y in points) / len(points) if points else cx
        hy = sum(y for _x, y in points) / len(points) if points else cy
        zone = next((b for b in buildings
                     if b["type"] == "constructionzone" and b.get("day") == latest_day),
                    None)
        zx, zy = build_pos(zone) if zone else (-83.5, -83.5)
        if zone and "px" not in zone:
            zx += LOT
            zy += LOT

        aim = bpy.data.objects.new("Day26RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day26RevealCamera")
        cam_data.lens = 48
        cam_data.clip_start = 7.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day26RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # A brief whole-city opener keeps the larger East Woods present
            # without sacrificing the scale of today's actual growth.
            (1, (205.0, -300.0, 150.0), (0.0, -38.0, 14.0)),
            (72, (170.0, -276.0, 125.0), (22.0, -72.0, 11.0)),
            # Move close enough that every Pine Hollow house reads as a house,
            # rather than as a tiny roof dot in an overhead diagram.
            (112, (150.0, -278.0, 75.0), (hx, hy - 4.0, 5.2)),
            (270, (128.0, -242.0, 50.0), (hx, hy + 5.0, 5.0)),
            # Give the final North Ridge pair their own visible rise beat.
            (312, (132.0, -154.0, 43.0), (98.0, -87.0, 5.5)),
            (360, (121.0, -137.0, 35.0), (98.0, -87.0, 5.5)),
            # Transfer southeast of the corrected downtown block, then settle
            # at pedestrian-readable height while the copied site rises.
            (410, (25.0, 2.0, 64.0), (zx, zy, 7.0)),
            (472, (-12.0, 14.0, 43.0), (zx, zy, 6.5)),
            (frame_end, (-24.0, 20.0, 30.0), (zx, zy, 5.2)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day24reveal":
        # One controlled 20-second milestone flight. Camera motion is mostly
        # forward or lateral; there are no repeated orbits or full spins.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        new_homes = [b for b in buildings
                     if b["type"] == "house" and b.get("day") == latest_day]
        larkspur = [build_pos(b) for b in new_homes
                    if b.get("street") == "Larkspur Loop"]
        sunset = [build_pos(b) for b in new_homes
                  if b.get("street") == "Sunset Court"]

        def center(points, fallback):
            if not points:
                return fallback
            return (sum(p[0] for p in points) / len(points),
                    sum(p[1] for p in points) / len(points))

        lx, ly = center(larkspur, (-257.0, -217.0))
        sx, sy = center(sunset, (-193.0, -264.0))
        aim = bpy.data.objects.new("Day24RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day24RevealCamera")
        cam_data.lens = 40
        cam_data.clip_start = 5.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day24RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-3.5s: dusk skyline push over the established city.
            (1, (184.0, -148.0, 100.0), (-8.0, -4.0, 13.0)),
            (105, (150.0, -128.0, 88.0), (-12.0, -8.0, 14.0)),
            # 3.5-7.5s: one direct transfer and steady Larkspur reveal.
            (140, (-130.0, -302.0, 116.0), (lx, ly, 6.0)),
            (165, (-175.0, -300.0, 98.0), (lx, ly, 5.0)),
            (225, (-166.0, -302.0, 92.0), (lx, ly, 5.5)),
            # 7.5-12.0s: lateral tracking pass as Sunset Court grows.
            (245, (-154.0, -335.0, 98.0), (sx - 42.0, sy, 5.0)),
            (330, (-74.0, -330.0, 88.0), (sx + 8.0, sy, 5.5)),
            (360, (-54.0, -307.0, 88.0), (sx + 38.0, sy + 5.0, 5.5)),
            # 12.0-15.7s: one high, readable transfer back to City Hall.
            (405, (18.0, -252.0, 106.0), (-24.0, -180.0, 8.0)),
            (445, (112.0, -164.0, 79.0), (25.0, -137.0, 8.0)),
            (470, (125.0, -58.0, 70.0), (20.0, -134.0, 9.0)),
            # 15.7-20.0s: settled civic-square push, election joke, fireworks.
            (520, (101.0, -74.0, 55.0), (37.0, -134.0, 8.0)),
            (frame_end, (88.0, -82.0, 48.0), (40.0, -134.0, 8.5)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day23reveal":
        # One continuous 16-second civic-growth flight: skyline, all nineteen
        # homes, the new central road, then City Hall after the camera settles.
        latest_day = max((item.get("day", 0) for item in buildings), default=0)
        new_homes = [b for b in buildings
                     if b["type"] == "house" and b.get("day") == latest_day]
        home_points = [build_pos(b) for b in new_homes]
        hx = sum(p[0] for p in home_points) / len(home_points) if home_points else cx
        hy = sum(p[1] for p in home_points) / len(home_points) if home_points else cy

        aim = bpy.data.objects.new("Day23RevealAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day23RevealCamera")
        cam_data.lens = 42
        cam_data.clip_start = 5.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day23RevealCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            # 0-3.2s: elevated southeast skyline with the established city.
            (1, (178.0, -142.0, 96.0), (-8.0, -2.0, 12.0)),
            (96, (151.0, -119.0, 84.0), (-12.0, -8.0, 13.5)),
            # 3.2-5.5s: fast but readable crossing toward Larkspur Loop.
            (126, (55.0, -148.0, 105.0), (hx + 8.0, hy, 7.0)),
            (165, (hx + 112.0, hy - 132.0, 116.0), (hx, hy, 5.0)),
            # 5.5-9.0s: steady wide hover while all nineteen homes rise.
            (270, (hx + 104.0, hy - 122.0, 106.0), (hx, hy, 5.5)),
            # 9.0-11.5s: high civic arc back across the southern city edge.
            (305, (-102.0, -118.0, 102.0), (-18.0, -112.0, 6.0)),
            (345, (35.0, -68.0, 55.0), (CITY_HALL_X, -107.0, 3.0)),
            # 11.5-13.2s: travel along the newly extending center road.
            (395, (66.0, -73.0, 52.0), (CITY_HALL_X, CITY_HALL_Y, 8.5)),
            # 13.2-16.0s: City Hall rises after the architectural view settles.
            (frame_end, (60.0, -79.0, 46.0),
             (CITY_HALL_X, CITY_HALL_Y, 10.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day21growth":
        # Edited two-part reveal: the coffee truck and new subdivision are too
        # far apart for one useful wide frame, so this camera makes a clean
        # cut after the truck reveal and gives the five homes their own shot.
        coffee = next((b for b in reversed(buildings)
                       if b["type"] == "coffeetruck"), None)
        new_homes = [b for b in buildings
                     if b["type"] == "house" and b.get("day") == max(
                         item.get("day", 0) for item in buildings)]
        tx, ty = build_pos(coffee) if coffee else (64.5, 32.5)
        if new_homes:
            home_points = [build_pos(b) for b in new_homes]
            hx = sum(p[0] for p in home_points) / len(home_points)
            hy = sum(p[1] for p in home_points) / len(home_points)
        else:
            hx, hy = cx, cy
        aim = bpy.data.objects.new("Day21GrowthAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day21GrowthCamera")
        cam_data.lens = 46
        cam_data.clip_start = .5
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day21GrowthCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            (1, (tx + 22.0, ty + 20.0, 12.5), (tx - .8, ty - .8, 2.5)),
            (92, (tx + 19.0, ty + 17.0, 11.3), (tx - .7, ty - 1.0, 2.7)),
            (93, (hx + 39.0, hy - 50.0, 43.0), (hx, hy, 4.1)),
            (frame_end, (hx + 31.0, hy - 43.0, 37.0), (hx, hy, 4.5)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT" if kp.co.x == 92 else "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day21drone":
        # Eight-second route unique to Day 21: begin over the newest edge of
        # Meadow Run, skim the district connector, then finish on Follow Mart
        # and the new coffee truck instead of repeating the prior crescent.
        newest = [b for b in buildings if b["type"] == "house" and
                  b.get("day") == max(item.get("day", 0) for item in buildings)]
        points = [build_pos(b) for b in newest]
        nx = sum(p[0] for p in points) / len(points) if points else cx
        ny = sum(p[1] for p in points) / len(points) if points else cy
        aim = bpy.data.objects.new("Day21DroneAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day21DroneCamera")
        cam_data.lens = 34
        cam_data.clip_start = 5.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day21DroneCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            (1, (nx - 10.0, ny - 42.0, 72.0), (nx, ny, 4.0)),
            (frame_end // 3, (-124.0, -106.0, 62.0), (-54.0, -28.0, 10.0)),
            (frame_end * 2 // 3, (-22.0, -55.0, 58.0), (-18.0, -10.0, 11.0)),
            (frame_end, (145.0, 95.0, 78.0), (55.0, 47.0, 9.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "day21skyline":
        # A restrained oblique skyline push from the southeast. The low pitch
        # keeps roofs, streets and the downtown silhouette layered in depth.
        aim = bpy.data.objects.new("Day21SkylineAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("Day21SkylineCamera")
        cam_data.lens = 52
        cam_data.clip_start = 4.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("Day21SkylineCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            (1, (156.0, -122.0, 83.0), (-8.0, 0.0, 12.0)),
            (frame_end, (137.0, -105.0, 72.0), (-3.0, 4.0, 13.5)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "cinematic":
        # Elevated skyline reveal used for a clean/destruction matched pair.
        # The camera is independent from temporary scene layers so both
        # renders have exactly the same lens, framing, timing, and motion.
        aim = bpy.data.objects.new("CinematicAim", None)
        aim.location = (cx, cy, 13.0)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("CinematicCamera")
        cam_data.lens = 48
        cam_data.clip_start = 5.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("CinematicCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        cam_obj.location = (108.0, -128.0, 86.0)
        cam_obj.keyframe_insert("location", frame=1)
        cam_obj.location = (96.0, -116.0, 78.0)
        cam_obj.keyframe_insert("location", frame=frame_end)
        aim.location = (-3.0, -3.0, 13.0)
        aim.keyframe_insert("location", frame=1)
        aim.location = (-3.0, -3.0, 13.0)
        aim.keyframe_insert("location", frame=frame_end)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "dronezoom":
        # Fast drone dive, lateral sweep, and pullback. Both altitude and
        # bearing change so this reads as a piloted move, not a lens effect.
        aim = bpy.data.objects.new("DroneZoomAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("DroneZoomCamera")
        cam_data.lens = 29
        cam_data.clip_start = 4.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("DroneZoomCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            (1, (cx - ext * .70, cy - ext * .66, ext * 1.18), (cx, cy, 4.0)),
            (90, (120.0, -145.0, 95.0), (-3.0, -3.0, 14.0)),
            (165, (cx + ext * .50, cy - ext * .40, ext * .62),
             (cx, cy, 6.0)),
            (245, (-105.0, 120.0, 86.0), (-3.0, -3.0, 13.0)),
            (frame_end, (cx + ext * .58, cy + ext * .54, ext * 1.08),
             (cx, cy, 4.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
    elif cam == "dronehover":
        # Smooth crescent flight along the town's southern edge. Unlike the
        # fast dronezoom route, this camera holds a steady helicopter-like
        # altitude while its changing bearing reveals the completed western
        # suburbs, downtown, and Kaleidoscope Crest through slow parallax.
        aim = bpy.data.objects.new("DroneHoverAim", None)
        world_col.objects.link(aim)
        cam_data = bpy.data.cameras.new("DroneHoverCamera")
        cam_data.lens = 38
        cam_data.clip_start = 6.0
        cam_data.clip_end = 4000.0
        cam_data.dof.use_dof = False
        cam_obj = bpy.data.objects.new("DroneHoverCamera", cam_data)
        world_col.objects.link(cam_obj)
        tr = cam_obj.constraints.new("TRACK_TO")
        tr.target = aim
        tr.track_axis = "TRACK_NEGATIVE_Z"
        tr.up_axis = "UP_Y"
        beats = (
            (1, (cx - ext * .48, cy - ext * .50, ext * .42),
             (cx - ext * .15, cy - ext * .03, 10.0)),
            (frame_end // 3, (cx - ext * .19, cy - ext * .57, ext * .39),
             (cx - ext * .06, cy - ext * .08, 12.0)),
            (frame_end * 2 // 3, (cx + ext * .12, cy - ext * .56, ext * .37),
             (cx, cy - ext * .04, 13.0)),
            (frame_end, (cx + ext * .40, cy - ext * .42, ext * .40),
             (cx + ext * .06, cy + ext * .01, 12.0)),
        )
        for frame, position, target in beats:
            cam_obj.location = position
            aim.location = target
            cam_obj.keyframe_insert("location", frame=frame)
            aim.keyframe_insert("location", frame=frame)
        for obj in (cam_obj, aim):
            for fc in obj_fcurves(obj):
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"
        bpy.context.scene.camera = cam_obj
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

    # Coordinated key/fill pair. Day retains the documented 1.0 / .07 baseline;
    # evening presets trade key strength for practical light instead of simply
    # raising every source and flattening the image.
    sun_data = bpy.data.lights.new("Sun", type="SUN")
    sun_data.energy = t["sun_e"]
    sun_data.angle = math.radians(t["sun_angle"])
    sun_data.color = t["sun_c"]
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = tuple(math.radians(a) for a in t["sun_rot"])
    world_col.objects.link(sun)
    fill_data = bpy.data.lights.new("Fill", type="SUN")
    fill_data.energy = t["sun_e"] * t["fill"]
    fill_data.angle = math.radians(30)
    fill_data.color = tuple(min(1.0, c * 0.5 + 0.5) for c in t["sky"])
    try:
        fill_data.use_shadow = False
    except Exception:
        pass
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.rotation_euler = (math.radians(55), 0, math.radians(t["sun_rot"][2] + 170))
    world_col.objects.link(fill)
    _configure_video_sky(tod, t)
    _build_video_practicals(world_col, tod)
    if cam == "day45northcrown" and tod in ("dusk", "night"):
        # Courtyard practicals are render-only.  The web keeps the authored
        # emissive lamp heads, while the cinematic file gets soft amber pools
        # that model the apartments and water in the final close shot.
        practicals = ((-430.0, 1048.0, 10.5, 720.0),
                      (-452.0, 1002.0, 10.0, 520.0),
                      (-408.0, 1002.0, 10.0, 520.0),
                      (-370.0, 970.0, 9.5, 480.0),
                      (-370.0, 1088.0, 9.5, 480.0))
        for index, (x, y, z, energy) in enumerate(practicals):
            data = bpy.data.lights.new("Day45CampusPractical_%02d" % index,
                                       "POINT")
            data.color = (1.0, .58, .26)
            data.energy = energy
            data.shadow_soft_size = 2.2
            lamp = bpy.data.objects.new("Day45CampusPractical_%02d" % index,
                                        data)
            lamp.location = (x, y, z)
            lamp["nb_render_only"] = True
            world_col.objects.link(lamp)


def build_storm_layer(world_col, frame_end):
    """Camera-following rain and brief lightning, excluded from every GLB."""
    camera = bpy.context.scene.camera
    if camera is None:
        raise RuntimeError("Storm layer requires an active camera")

    rain = mat("NB_storm_rain", (.58, .72, .86), .22, alpha=.32)
    bsdf = rain.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        emission = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if emission:
            emission.default_value = (.48, .66, .88, 1.0)
        strength = bsdf.inputs.get("Emission Strength")
        if strength:
            strength.default_value = 1.25

    # Each field sits at one fixed camera depth and repeats the same streaks one
    # exact vertical tile apart. Moving the field by precisely one tile makes
    # frame N and the cycle restart visually identical: rain continues falling
    # without the old random-pattern snap every 22 frames.
    layer_specs = ((12.0, 44), (30.0, 58), (58.0, 72))
    for layer_index, (depth, base_count) in enumerate(layer_specs):
        rng = random.Random(3300 + layer_index)
        verts, faces = [], []
        tile_height = depth * 1.08
        for _index in range(base_count):
            x = rng.uniform(-depth * .44, depth * .44)
            base_y = rng.uniform(0.0, tile_height)
            length = depth * rng.uniform(.025, .043)
            width = depth * rng.uniform(.00045, .00082)
            slant = length * .16
            z = -depth
            for tile_index in range(-2, 3):
                y = base_y + tile_index * tile_height
                start = len(verts)
                verts.extend(((x - width, y + length * .5, z),
                              (x + width, y + length * .5, z),
                              (x + slant + width, y - length * .5, z),
                              (x + slant - width, y - length * .5, z)))
                faces.append((start, start + 1, start + 2, start + 3))
        mesh = bpy.data.meshes.new("storm_rain_mesh_%d" % layer_index)
        mesh.from_pydata(verts, [], faces)
        mesh.materials.append(rain)
        mesh.update()
        field = bpy.data.objects.new("storm_rain_%d" % layer_index, mesh)
        world_col.objects.link(field)
        field.parent = camera
        field["nb_render_only"] = True
        field.location.y = 0.0
        field.keyframe_insert("location", frame=1)
        field.location.y = -tile_height
        field.keyframe_insert("location", frame=46 + layer_index * 9)
        for fc in obj_fcurves(field):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            fc.modifiers.new("CYCLES")

    # A restrained fork behind the forecast center gives the storm a authored
    # focal beat without covering the logo or turning the film into an effect reel.
    lightning = mat("NB_storm_lightning", (.83, .91, 1.0), .18)
    if lightning.use_nodes:
        _set_mat_emission("NB_storm_lightning", (.72, .86, 1.0), 14.0)
    points = ((13.0, 139.0, 64.0), (17.0, 137.0, 51.0),
              (14.5, 140.0, 39.0), (20.0, 137.5, 25.0),
              (18.0, 141.0, 11.0))
    bolt_parts = []
    for index, (start, end) in enumerate(zip(points, points[1:])):
        bolt_parts.append(add_beam_between(
            world_col, "storm_lightning_bolt_%d" % index,
            start, end, .19 if index < 2 else .13, lightning))
    bolt_parts.append(add_beam_between(
        world_col, "storm_lightning_branch", points[2], (8.0, 143.5, 29.0),
        .09, lightning))
    for part in bolt_parts:
        part["nb_render_only"] = True
        _keyframe_hidden(part, 1, True)
        _keyframe_hidden(part, 452, False)
        _keyframe_hidden(part, 456, True)
        _keyframe_hidden(part, 522, False)
        _keyframe_hidden(part, 525, True)

    flash_data = bpy.data.lights.new("StormLightningFlash", type="AREA")
    flash_data.color = (.64, .78, 1.0)
    flash_data.shape = "DISK"
    flash_data.size = 95.0
    flash = bpy.data.objects.new("StormLightningFlash", flash_data)
    flash.location = (29.5, 106.0, 68.0)
    flash["nb_render_only"] = True
    world_col.objects.link(flash)
    for frame, energy in ((1, 0.0), (451, 0.0), (452, 1750.0),
                          (455, 0.0), (521, 0.0), (522, 1250.0),
                          (525, 0.0), (frame_end, 0.0)):
        flash_data.energy = energy
        flash_data.keyframe_insert("energy", frame=frame)
    for fc in obj_fcurves(flash_data):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"

    world = bpy.context.scene.world
    bg = world.node_tree.nodes.get("Background") if world and world.use_nodes else None
    if bg:
        base = bg.inputs[1].default_value
        for frame, strength in ((1, base), (451, base), (452, base * 2.8),
                                (455, base), (521, base), (522, base * 2.25),
                                (525, base), (frame_end, base)):
            bg.inputs[1].default_value = strength
            bg.inputs[1].keyframe_insert("default_value", frame=frame)

def setup_render(state, frame_end, tag=None, tod="day", cam=None):
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
    if cam in ("day45northcrown", "day46sunsetdrone", "day47reveal",
               "day48crown", "day49northreach", "day50highway",
               "day43fpv", "day43pov",
               "day44approach", "day44drone",
               "day44downtown", "day44allapproach", "day44alldrone",
               "day44southfpv", "day44swrooftop", "day44westbank",
               "day44sereverse", "day44fullarc"):
        # Restrained motion blur smooths the FPV transfers while leaving the
        # short vertical construction rises crisp enough to read.
        try:
            sc.render.use_motion_blur = True
            sc.render.motion_blur_shutter = .12
        except Exception:
            pass
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
    # Exposure is part of the preset, not a camera-by-camera rescue value.
    # AgX retains warm lamp color and highlight roll-off at sunset/night.
    try:
        exposure = TODS.get(tod, TODS["day"])["exposure"]
        if cam in ("day43fpv", "day43pov", "day44approach", "day44street",
                   "day44drone", "day44field", "day44overhead",
                   "day44downtown", "day44allapproach", "day44alldrone",
                   "day44allfield", "day44southfpv", "day44swrooftop",
                   "day44westbank", "day44sereverse",
                   "day44fullarc", "day46sunsetdrone",
                   "day47reveal", "day48crown",
                   "day49northreach", "day50highway") and tod == "sunset":
            exposure = -.08
        sc.view_settings.exposure = exposure
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
    if cfg.get("forest") and n_trees <= 0:
        n_trees = 48  # dense low-poly grove for --forest
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
        if not new_batch:
            # "Re-animate yesterday's batch" only works while the newest
            # buildings carry state["day"], and the --foodcourt block breaks
            # that: it appends its records and stamps them BEFORE the
            # `state["day"] += 1` further down, while every other addition is
            # created after it. So the Food Court's twenty records carry day
            # 37 in a day-38 world, an exact match finds nothing, and a replay
            # renders a town where nothing rises at all -- which is what
            # `--cam day38reveal` did when it was replayed. Fall back to the
            # newest day that actually exists. Render-only: replay never
            # writes world_state.json, so no stamp is corrected here.
            newest = max((b.get("day", 0) for b in state["buildings"]), default=0)
            new_batch = [b for b in state["buildings"]
                         if b.get("day", 0) == newest]
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

        if cfg.get("foodcourt") and gained > 0:
            # The 616-house reserve is finished, so these do not consume plan
            # addresses -- the ring carries its own nineteen exact positions.
            if not any(b["type"] == "foodcourt" for b in state["buildings"]):
                yard = {"type": "foodcourt", "gx": 0, "gy": 0,
                        "px": FOOD_COURT_X, "py": FOOD_COURT_Y, "pz": 0.0,
                        "rot": 0.0, "seed": state["seed_counter"],
                        "name": "Food Court", "day": state["day"]}
                state["seed_counter"] += 1
                state["buildings"].append(yard)
                new_batch.append(yard)
            built = len([b for b in state["buildings"] if b["type"] == "foodhouse"])
            for x, y, rot in food_court_lots()[built:built + gained]:
                home = {"type": "foodhouse", "gx": 0, "gy": 0,
                        "px": round(x, 3), "py": round(y, 3), "rot": round(rot, 5),
                        "district": "Food Court", "street": "Food Court Loop",
                        "seed": state["seed_counter"], "day": state["day"]}
                state["seed_counter"] += 1
                state["buildings"].append(home)
                new_batch.append(home)
            house_gained = 0
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
        if (gained or lost or n_apart or n_parks or n_trees or n_mush or
                specials or cfg.get("cityhall") or cfg.get("civicsquare") or
                cfg.get("fishingpond") or cfg.get("constructionzone") or
                cfg.get("movietheater") or cfg.get("arcade") or
                cfg.get("eastwoods") or cfg.get("raftingstation") or
                cfg.get("gasstation") or cfg.get("salmonproshop") or
                cfg.get("highschool") or cfg.get("northcrowncampus")):
            state["day"] += 1
            state["pop"] = max(0, state["pop"] + followers)
            # milestone buildings appear the day a threshold is crossed
            done = state.setdefault("milestones", [])
            for thr, btype in MILESTONES:
                if state["pop"] >= thr and thr not in done:
                    done.append(thr)
                    # Cade's approved 135..500 reserve is ordinary houses
                    # only. Reaching 500 completes that first neighborhood plan;
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
        if cfg.get("cityhall"):
            if any(b["type"] in ("cityhall", "cityhallroad")
                   for b in state["buildings"]):
                raise RuntimeError("City Hall civic campus already exists")
            civic_records = (
                {"type": "cityhallroad", "gx": 0, "gy": 0,
                 "px": CITY_HALL_X, "py": CITY_HALL_ROAD_Y, "pz": 0.0,
                 "rot": 0.0},
                {"type": "cityhall", "gx": 0, "gy": 0,
                 "px": CITY_HALL_X, "py": CITY_HALL_Y, "pz": 0.0,
                 "rot": 0.0},
            )
            for civic in civic_records:
                civic.update({"seed": state["seed_counter"], "day": state["day"]})
                state["seed_counter"] += 1
                state["buildings"].append(civic)
                new_batch.append(civic)
        if cfg.get("civicsquare"):
            if any(b["type"] == "civicsquare" for b in state["buildings"]):
                raise RuntimeError("Civic Square already exists")
            square = {"type": "civicsquare", "gx": 0, "gy": 0,
                      "px": CIVIC_SQUARE_X, "py": CIVIC_SQUARE_Y, "pz": 0.0,
                      "rot": 0.0, "seed": state["seed_counter"],
                      "day": state["day"]}
            state["seed_counter"] += 1
            state["buildings"].append(square)
            new_batch.append(square)
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
                # Consume exact addresses from the hidden 616-address
                # neighborhood reserve before falling back to the legacy grid. The plan
                # lives outside world_state and creates no future objects.
                # "+50 followers" means FIFTY HOMES (Cade, 2026-08-09).
                #
                # Chapter three reserves ten of its addresses for something
                # other than a house -- a filling station, a diner, the
                # grocery, the school, the fire station. Those are NOT built by
                # ordinary growth: their ground stays empty and the homes go up
                # around it, and the building itself appears only when Cade
                # asks for it. So the next N unbuilt HOUSE addresses are taken,
                # in plan order, stepping over any reserved slot on the way.
                #
                # Indexing by count no longer works once slots can be skipped,
                # so this matches on the plan_ids that are actually standing.
                built_ids = {b["plan_id"] for b in state["buildings"]
                             if b.get("plan_id")}
                available = [slot for slot in SUBURBAN_PLAN["houses"]
                             if slot["plan_id"] not in built_ids
                             and slot.get("type", "house") == "house"] \
                    if SUBURBAN_PLAN else []
                take = min(n, len(available))
                if take:
                    for slot in available[:take]:
                        b = {"type": slot.get("type", "house"), "gx": 0, "gy": 0,
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
                # Once the deterministic ordinary reserve is exhausted, new
                # followers occupy Crown Quarter at 100 residents per tower.
                # A partial tower is filled before another address is created;
                # the first partial group still earns the building, matching
                # Cade's approved ceil(overage/100) reveal rule.
                existing_towers = sorted(
                    (b for b in state["buildings"] if b.get("type") == "metrotower"),
                    key=lambda b: int(b.get("metro_id", 0)))
                for tower in existing_towers:
                    if n <= 0:
                        break
                    current = int(tower.get("residents", TOWER_RESIDENT_CAPACITY))
                    room = max(0, TOWER_RESIDENT_CAPACITY-current)
                    moved = min(n, room)
                    if moved:
                        tower["residents"] = current+moved
                        n -= moved
                built_metro_ids = {int(b.get("metro_id", 0))
                                   for b in existing_towers}
                for slot in METRO_TOWER_PLAN:
                    if n <= 0:
                        break
                    if int(slot["metro_id"]) in built_metro_ids:
                        continue
                    residents = min(TOWER_RESIDENT_CAPACITY, n)
                    tower = {
                        "type": "metrotower", "gx": 0, "gy": 0,
                        "px": slot["x"], "py": slot["y"], "pz": slot["z"],
                        "rot": slot["rot"], "metro_id": slot["metro_id"],
                        "district": slot["district"], "street": slot["street"],
                        "resident_capacity": TOWER_RESIDENT_CAPACITY,
                        "residents": residents,
                        "seed": state["seed_counter"], "day": state["day"],
                    }
                    state["seed_counter"] += 1
                    state["buildings"].append(tower)
                    new_batch.append(tower)
                    built_metro_ids.add(int(slot["metro_id"]))
                    n -= residents
                if n > 0:
                    raise RuntimeError(
                        "Crown Quarter is full: %d followers exceed its remaining "
                        "%d-person tower reserve" %
                        (n, METRO_TOWER_COUNT*TOWER_RESIDENT_CAPACITY))
                continue
            else:
                lots = find_free_lots(n, size, occupied, fill_mode=fill_mode)
            for gx, gy in lots:
                b = {"type": btype, "gx": gx, "gy": gy,
                     "seed": state["seed_counter"], "day": state["day"]}
                state["seed_counter"] += 1
                state["buildings"].append(b)
                occupied.update(footprint(b))
                new_batch.append(b)
        # Keep today's 39 follower homes contiguous (seeds 458-496), then add
        # the non-population destination as the final Day 25 record.
        if cfg.get("fishingpond"):
            if any(b["type"] == "fishingpond" for b in state["buildings"]):
                raise RuntimeError("Fishing pond already exists")
            fishing_pond = {
                "type": "fishingpond", "gx": 0, "gy": 0,
                "px": FISHING_POND_X, "py": FISHING_POND_Y, "pz": 0.0,
                "rot": 0.0, "seed": state["seed_counter"],
                "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(fishing_pond)
            new_batch.append(fishing_pond)
        if cfg.get("nuclearplant"):
            if any(b["type"] == "nuclearplant" for b in state["buildings"]):
                raise RuntimeError("Followville Point Station already exists")
            from world_layout import (NUCLEAR_PLANT_CENTER,
                                      nuclear_plant_base_height)
            # pz is pinned above the site's HIGHEST corner, like the Salmon Pro
            # Shop's. The terrain mesh comes from terrain_height(), so a pad
            # set to the average or the centre has the ground rising through
            # its own switchyard on the high side.
            plant = {
                "type": "nuclearplant", "gx": 0, "gy": 0,
                "px": NUCLEAR_PLANT_CENTER[0], "py": NUCLEAR_PLANT_CENTER[1],
                "pz": round(nuclear_plant_base_height(), 4),
                "rot": 0.0, "seed": state["seed_counter"],
                "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(plant)
            new_batch.append(plant)
        if cfg.get("gasstation"):
            # The first reserved NON-house address the project has ever
            # claimed. Chapter three holds ten of them -- two filling stations,
            # two diners, two parks, a pond, the grocery, the school and the
            # fire station -- and ordinary growth steps straight over every one
            # (see the addition loop above), so their ground stays empty and
            # the homes go up around it until someone asks. This is the asking.
            #
            # It takes the reserve's own address rather than a free grid lot,
            # which is the whole point: --special gasstation would drop one on
            # whatever downtown lot happened to be free, 300m from the street
            # the plan built a frontage for.
            built_ids = {b["plan_id"] for b in state["buildings"]
                         if b.get("plan_id")}
            slot = next((s for s in SUBURBAN_PLAN["houses"]
                         if s.get("type") == "gasstation"
                         and s["plan_id"] not in built_ids), None)
            if slot is None:
                raise RuntimeError("The reserve has no unbuilt filling-station "
                                   "address left")
            station = {"type": "gasstation", "gx": 0, "gy": 0,
                       "px": slot["x"], "py": slot["y"], "rot": slot["rot"],
                       "plan_id": slot["plan_id"], "district": slot["district"],
                       "street": slot["street"],
                       "seed": state["seed_counter"], "day": state["day"]}
            state["seed_counter"] += 1
            state["buildings"].append(station)
            new_batch.append(station)
        if cfg.get("raftingstation"):
            if any(b["type"] == "raftingstation" for b in state["buildings"]):
                raise RuntimeError("Rafting station already exists")
            rafting_station = {
                "type": "raftingstation", "gx": 0, "gy": 0,
                "px": RAFTING_STATION_X, "py": RAFTING_STATION_Y, "pz": 0.0,
                "rot": 0.0, "seed": state["seed_counter"],
                "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(rafting_station)
            new_batch.append(rafting_station)
        if cfg.get("salmonproshop"):
            if any(b["type"] == "salmonproshop" for b in state["buildings"]):
                raise RuntimeError("Salmon Pro Shop already exists")
            salmon_pro_shop = {
                "type": "salmonproshop", "gx": 0, "gy": 0,
                "px": SALMON_SHOP_X, "py": SALMON_SHOP_Y, "pz": 0.0,
                "rot": 0.0, "seed": state["seed_counter"],
                "name": "Salmon Pro Shop",
                "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(salmon_pro_shop)
            new_batch.append(salmon_pro_shop)
        if cfg.get("highschool"):
            if any(b["type"] == "highschool" for b in state["buildings"]):
                raise RuntimeError("Followville High already exists")
            high_school = {
                "type": "highschool", "gx": 0, "gy": 0,
                "px": HIGH_SCHOOL_X, "py": HIGH_SCHOOL_Y, "pz": 0.0,
                "rot": 0.0, "seed": state["seed_counter"],
                "name": "Followville High School",
                "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(high_school)
            new_batch.append(high_school)
        if cfg.get("apartmentcomplex"):
            if any(b["type"] == "apartmentcomplex" for b in state["buildings"]):
                raise RuntimeError("Followville Commons already exists")
            commons = {
                "type": "apartmentcomplex", "gx": 0, "gy": 0,
                "px": APARTMENTS_X, "py": APARTMENTS_Y, "pz": 0.0,
                "rot": 0.0, "seed": state["seed_counter"],
                "name": "Followville Commons",
                "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(commons)
            new_batch.append(commons)
        if cfg.get("northcrowncampus"):
            if any(b["type"] == "northcrowncampus"
                   for b in state["buildings"]):
                raise RuntimeError("North Crown apartment campus already exists")
            campus = {
                "type": "northcrowncampus", "gx": 0, "gy": 0,
                "px": NORTH_CROWN_CAMPUS_X,
                "py": NORTH_CROWN_CAMPUS_Y,
                "pz": NORTH_CROWN_CAMPUS_Z,
                "rot": 0.0, "seed": state["seed_counter"],
                "name": "North Crown Apartments — Phase One",
                "district": "North Crown Campus",
                "completed_apartments": 4,
                "planned_apartments": 20,
                "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(campus)
            new_batch.append(campus)
        if cfg.get("constructionzone"):
            existing_zone = [b for b in state["buildings"]
                             if b["type"] == "constructionzone"]
            if existing_zone:
                raise RuntimeError("Construction zone already exists")
            zone = {
                "type": "constructionzone", "gx": -6, "gy": 3,
                "seed": state["seed_counter"], "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(zone)
            occupied.update(footprint(zone))
            new_batch.append(zone)
        if cfg.get("movietheater"):
            zones = [b for b in state["buildings"]
                     if b["type"] == "constructionzone"]
            theaters = [b for b in state["buildings"]
                        if b["type"] == "movietheater"]
            if theaters:
                raise RuntimeError("Movie theater already exists")
            if len(zones) != 1 or int(zones[0].get("seed", -1)) != 524:
                raise RuntimeError(
                    "Movie theater requires canonical construction zone seed 524")
            theater = zones[0]
            theater["type"] = "movietheater"
            theater["day"] = state["day"]
            new_batch.append(theater)
        if cfg.get("arcade"):
            arcades = [b for b in state["buildings"] if b["type"] == "arcade"]
            if arcades:
                raise RuntimeError("Followville Arcade already exists")
            candidates = [b for b in state["buildings"]
                          if int(b.get("seed", -1)) == 129]
            if len(candidates) != 1:
                raise RuntimeError("Arcade requires canonical downtown seed 129")
            arcade = candidates[0]
            if arcade.get("type") != "house" or arcade.get("gx") != 4 or arcade.get("gy") != -3:
                raise RuntimeError("Arcade seed 129 is no longer the expected downtown house")
            arcade["type"] = "arcade"
            arcade["day"] = state["day"]
            arcade["name"] = "Followville Arcade"
            new_batch.append(arcade)
        if cfg.get("eastwoods"):
            if any(b["type"] == "forestreserve" for b in state["buildings"]):
                raise RuntimeError("East Woods already exists")
            woods = {
                "type": "forestreserve", "gx": 0, "gy": 0,
                "px": EAST_WOODS_X, "py": EAST_WOODS_Y,
                "pz": terrain_height(EAST_WOODS_X, EAST_WOODS_Y),
                "rot": 0.0, "radius": EAST_WOODS_RADIUS,
                "feature_id": "east_woods_day26",
                "district": "East Woods",
                "seed": state["seed_counter"], "day": state["day"],
            }
            state["seed_counter"] += 1
            state["buildings"].append(woods)

    # rebuild world (removed houses still placed so they can sink on camera)
    world_col = clear_world()
    m = std_mats()
    focus_type = cfg.get("focus_type")
    animation_batch = ([b for b in new_batch if b["type"] == focus_type]
                       if focus_type else new_batch)
    new_ids = {id(b) for b in animation_batch}
    rem_ids = {id(b) for b in removed}
    rise, sink, building_roots = [], [], []
    for b in state["buildings"]:
        e = place_instance(world_col, b, "%s_d%d" % (b["type"], b.get("day", 0)))
        building_roots.append(e)
        # Export-only identity.  The web chunker partitions these canonical
        # building roots but leaves roads, terrain, nature, traffic, and public
        # feature dressing in the always-loaded base asset.
        e["nb_world_seed"] = int(b["seed"])
        e["nb_world_type"] = str(b["type"])
        e["nb_web_chunk"] = web_chunk_id(b)
        if b.get("district"):
            e["nb_world_district"] = str(b["district"])
        if b.get("plan_id"):
            e["nb_world_plan_id"] = int(b["plan_id"])
        if b.get("metro_id"):
            e["nb_world_metro_id"] = int(b["metro_id"])
            e["nb_resident_capacity"] = int(b.get("resident_capacity", 100))
            e["nb_residents"] = int(b.get("residents", 0))
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
    build_northgate_arterial(world_col, keep or state["buildings"], m)
    build_point_road(world_col, keep or state["buildings"], m)
    river_road_objects = build_suburban_roads(
        world_col, keep or state["buildings"], m)
    river_objects = build_river_chapter(world_col, keep or state["buildings"], m)
    metro_objects = build_metropolitan_district(
        world_col, keep or state["buildings"], m)
    highway_objects = build_highway_system(
        world_col, keep or state["buildings"], m)
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

    if cfg.get("cam") == "day39mayor":
        # Render-only celebration for the mayoral result. Neither the shells
        # nor the aircraft is ever written to world_state, the GLB or the
        # Blend -- same contract as the Day 34 emergency props.
        # Sized for THIS shot, not for a drone pass. The defaults are 1.2m
        # shards over a 13m spread, which is a couple of pixels at the ~150m
        # this camera stands off and rendered as a scatter of white specks.
        # 3.0m shards over 26m give bursts that read as fireworks, and the
        # emission comes down from 30 to 16 so the colour survives the
        # exposure instead of clipping to white.
        build_fireworks(world_col, CITY_HALL_X, CITY_HALL_Y, FPS * 10,
                        start_frame=34, end_frame=268, burst_count=9,
                        base_z=54.0, particle_size=3.0, spread=26.0,
                        shards=20, emission=16.0)
        build_mayor_flyover(world_col, FPS * 10)

    # animation timing: sinks first, then rises
    n_anim = len(rise) + len(sink)
    prehold = int(1.5 * FPS)
    stagger = max(2, min(6, 240 // max(n_anim, 1)))
    posthold = int(2.5 * FPS)
    frame_end = prehold + max(n_anim - 1, 0) * stagger + 22 + posthold
    if cfg.get("cam") == "day48crown":
        frame_end = FPS * 24          # exact brief: twenty-four seconds
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        tower_roots = [root for root in rise
                       if root.name.startswith("metrotower_d")]
        if len(home_roots) != 81 or len(tower_roots) != 1 or len(rise) != 82:
            raise RuntimeError(
                "day48crown requires exactly 81 Day 48 homes and Crown "
                "Quarter's first tower; got %d homes / %d towers / %d rising "
                "records. Use the exact 2268 -> 2360 growth."
                % (len(home_roots), len(tower_roots), len(rise)))

        # Roads and Crown Quarter's new grid stand from frame one. The story is
        # the 81 homes and the tower; finished pavement is what makes an empty
        # street read as an empty street rather than as unbuilt ground.
        for root in home_roots:
            offset = round(abs(root.location.y - 774.0), 1)
            lead = DAY48_WAVE_LEAD.get(offset)
            if lead is None:
                raise RuntimeError(
                    "day48crown: home at y=%.1f is %.1fm off the Wheelwright "
                    "centreline, which is not one of the three streets this "
                    "wave was measured for" % (root.location.y, offset))
            start = day48_frame_at_x(root.location.x + lead)
            if start is None:
                raise RuntimeError(
                    "day48crown: no frame reaches x=%.1f, so the home at "
                    "(%.1f, %.1f) would rise behind the camera"
                    % (root.location.x + lead,
                       root.location.x, root.location.y))
            if start > DAY48_WAVE_KNEE:
                start = DAY48_WAVE_KNEE + (start - DAY48_WAVE_KNEE) * DAY48_WAVE_SQUEEZE
            animate_rise(root, int(round(start)), dur=22)

        # Crown Quarter's first tower is 54m and 500m away when the turn brings
        # it into frame at ~600. It rises across the whole approach and tops out
        # at 675, leaving a second and a half of held skyline to end on.
        animate_rise(tower_roots[0], 580, dur=95)
    elif cfg.get("cam") == "day50highway":
        frame_end = FPS * 24
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 50 or len(rise) != 50:
            raise RuntimeError(
                "day50highway requires the exact Day 50 +50 allocation: 50 "
                "ordinary homes, with the reserved pond and Followmart slots "
                "skipped; got %d homes / %d rising records. Use the exact "
                "2512 -> 2562 growth."
                % (len(home_roots), len(rise)))

        # Gateway Row is almost 300m west of the flight line, so its nine new
        # homes rise during the wide opening. Everything else follows the
        # camera's measured northbound Y path between Quarry and Anvil.
        for root in rise:
            if root.location.x < 0.0:
                start = min(105.0, 45.0 + (root.location.x + 167.0) * .65
                            + (root.location.y - 837.5) * .55)
            else:
                offset = round(abs(root.location.x - DAY50_STREET_X), 1)
                lead = DAY50_WAVE_LEAD.get(offset)
                if lead is None:
                    raise RuntimeError(
                        "day50highway: new record at (%.1f, %.1f) is %.1fm "
                        "off the Quarry/Anvil flight line; expected one of %s."
                        % (root.location.x, root.location.y, offset,
                           ", ".join("%.1f" % k for k in sorted(DAY50_WAVE_LEAD))))
                start = day50_frame_at_y(root.location.y - lead)
                if start is None:
                    raise RuntimeError(
                        "day50highway: no frame reaches y=%.1f for new record "
                        "at (%.1f, %.1f)"
                        % (root.location.y - lead,
                           root.location.x, root.location.y))
            animate_rise(root, max(1, int(round(start))), dur=22)
    elif cfg.get("cam") == "day49northreach":
        frame_end = FPS * 24          # exact brief: twenty-four seconds
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 152 or len(rise) != 152:
            raise RuntimeError(
                "day49northreach requires exactly 152 Day 49 homes and nothing "
                "else rising; got %d homes / %d rising records. Use the exact "
                "2360 -> 2512 growth. No tower is touched by this growth: the "
                "allocator takes ordinary house addresses first, and chapter "
                "five put 1,023 of them back."
                % (len(home_roots), len(rise)))

        # Roads stand from frame one, including the five new ribbons. The story
        # is the 152 homes; finished pavement reaching north into meadow is
        # what makes the empty ground read as a street rather than as nothing,
        # and it is what makes the crossing of y=824 legible at all.
        for root in home_roots:
            offset = round(abs(root.location.x - DAY49_STREET_X), 1)
            lead = DAY49_WAVE_LEAD.get(offset)
            if lead is None:
                raise RuntimeError(
                    "day49northreach: home at x=%.1f is %.1fm off the Maple "
                    "Avenue North centreline, which is not one of the five "
                    "ribbons this wave was measured for. Expected one of %s."
                    % (root.location.x, offset,
                       ", ".join("%.1f" % k for k in sorted(DAY49_WAVE_LEAD))))
            start = day49_frame_at_y(root.location.y - lead)
            if start is None:
                raise RuntimeError(
                    "day49northreach: no frame reaches y=%.1f, so the home at "
                    "(%.1f, %.1f) would rise behind the camera"
                    % (root.location.y - lead,
                       root.location.x, root.location.y))
            if start > DAY49_WAVE_KNEE:
                start = DAY49_WAVE_KNEE + (start - DAY49_WAVE_KNEE) * DAY49_WAVE_SQUEEZE
            animate_rise(root, max(1, int(round(start))), dur=22)
    elif cfg.get("cam") == "day47reveal":
        frame_end = FPS * 24          # exact brief: twenty-four seconds / 720 frames
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 37 or len(rise) != 37:
            raise RuntimeError(
                "day47reveal requires exactly 37 Day 47 follower homes; "
                "got %d homes / %d rising records. Use the exact 2231 -> 2268 "
                "growth, or replay with --focus-type house."
                % (len(home_roots), len(rise)))

        # Roads stand from frame one: the story is the 37 homes, and finished
        # pavement is what makes an empty street read as an empty street.
        # East to west, keeping pace with the westbound camera so each home
        # rises about 45m ahead of the lens, and finishing at frame 468 --
        # before the lift at 500, or the last home rises as the aim swings
        # away and is never seen.
        east_x = max(root.location.x for root in home_roots)
        west_x = min(root.location.x for root in home_roots)
        span_x = max(1.0, east_x - west_x)
        for root in home_roots:
            # Two of the 37 sit off the corridor, 27m and 44m south of the
            # centreline. At the wave's 45m lead they would be 30-45 degrees
            # off axis and never enter the narrow horizontal frame, so they
            # rise early instead, while the camera is still far enough east
            # for them to sit inside it.
            if abs(root.location.y - 738.0) > 12.0:
                start = 155 if root.location.y > 700.0 else 170
            else:
                progress = (east_x - root.location.x) / span_x
                start = 150 + int(progress * 318.0)
            animate_rise(root, start, dur=22)
    elif cfg.get("cam") == "day46sunsetdrone":
        frame_end = FPS * 16          # exact brief: sixteen seconds / 480 frames
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 47 or len(rise) != 47:
            raise RuntimeError(
                "day46sunsetdrone requires exactly 47 Day 46 follower homes; "
                "got %d homes / %d rising records. Use the exact 2184 -> 2231 "
                "growth, or replay with --focus-type house."
                % (len(home_roots), len(rise)))

        # The streets are complete from frame one.  The story is the follower
        # homes, not pavement, and standing roads make the low pass legible.
        # East-to-west starts just after the five-second skyline hold, a few
        # blocks ahead of the westbound drone.  Three adjacent streets are
        # mixed into one broad spatial front instead of rising in seed order.
        east_x = max(root.location.x for root in home_roots)
        west_x = min(root.location.x for root in home_roots)
        span_x = max(1.0, east_x - west_x)
        for root in home_roots:
            progress = (east_x - root.location.x) / span_x
            start = 168 + int(progress * 166.0)
            animate_rise(root, start, dur=22)
    elif cfg.get("cam") == "day45northcrown":
        frame_end = FPS * 20
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        campus_roots = [root for root in rise
                        if root.name.startswith("northcrowncampus_d")]
        if len(home_roots) != 214 or len(campus_roots) != 1 or len(rise) != 215:
            raise RuntimeError(
                "day45northcrown requires exactly 214 follower homes and one "
                "North Crown campus; got %d homes, %d campuses, %d rising records"
                % (len(home_roots), len(campus_roots), len(rise)))

        # New road ribbons draw on before the synchronized building event.
        # Street 70 already carried Day 44 homes, so its newly revealed end is
        # left standing rather than hiding pavement under existing residents.
        new_plan_ids = {b["plan_id"] for b in new_batch if b.get("plan_id")}
        built_plan_ids = ({b.get("plan_id") for b in state["buildings"]}
                          - new_plan_ids)
        old_streets = {slot["street_index"]
                       for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in built_plan_ids}
        new_streets = sorted({slot["street_index"]
                              for slot in SUBURBAN_PLAN["houses"]
                              if slot["plan_id"] in new_plan_ids} - old_streets)
        if new_streets != list(range(71, 83)):
            raise RuntimeError("Day 45 road suite expected new street indices "
                               "71..82; got %r" % new_streets)
        ribbons_prefix = ("suburban_shoulder_", "suburban_road_",
                          "suburban_path_")
        for offset, street_index in enumerate(new_streets):
            pieces = [obj for obj in world_col.objects
                      if obj.get("nb_street_index") == street_index]
            start = 92 + offset * 6
            ribbons = [obj for obj in pieces
                       if obj.name.startswith(ribbons_prefix)]
            trim = [obj for obj in pieces if obj not in ribbons]
            for obj in ribbons:
                animate_road_build(obj, start, dur=54,
                                   reverse=(street_index % 2 == 0))
            if trim:
                xs = [obj.location.x for obj in trim]
                ys = [obj.location.y for obj in trim]
                along_x = (max(xs) - min(xs)) >= (max(ys) - min(ys))
                trim.sort(key=lambda obj: (obj.location.x if along_x
                                            else obj.location.y))
                span = max(1, len(trim) - 1)
                for index, obj in enumerate(trim):
                    _keyframe_hidden(obj, 1, True)
                    _keyframe_hidden(obj, start + 10 + int(54 * index / span),
                                     False)

        access_pieces = [obj for obj in world_col.objects
                         if obj.get("nb_north_crown_access")]
        access_ribbons = [obj for obj in access_pieces
                          if obj.name.startswith(("north_crown_access_shoulder",
                                                  "north_crown_access_road",
                                                  "north_crown_access_path_"))]
        access_trim = [obj for obj in access_pieces
                       if obj not in access_ribbons]
        for obj in access_ribbons:
            animate_road_build(obj, 142, dur=46)
        for index, obj in enumerate(access_trim):
            _keyframe_hidden(obj, 1, True)
            _keyframe_hidden(obj, 152 + index * 2, False)

        # The brief asks for one large simultaneous population event rather
        # than a machine-gun sequence.  All 214 homes and all four apartment
        # blocks (inside one campus root) therefore rise on the same frames.
        for root in home_roots:
            animate_rise(root, 190, dur=34)
        animate_rise(campus_roots[0], 190, dur=34)
    elif cfg.get("cam") == "story001pricesign":
        frame_end = 330               # 11.0s: 2.8 + 2.2 + 3.0 + 3.0
    elif cfg.get("cam") == "story001dusk":
        frame_end = 126               # 4.2s, the payoff held
    elif cfg.get("cam") in ("day44approach", "day44street", "day44drone",
                            "day44field"):
        frame_end = FPS * 12
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 186 or len(rise) != 186:
            raise RuntimeError(
                "%s is authored for exactly 186 Day 44 homes. Got %d homes / "
                "%d rising records. Use the exact 1784 -> 1970 growth, and "
                "use --focus-type house for replay renders."
                % (cfg.get("cam"), len(home_roots), len(rise)))

        camera_name = cfg.get("cam")
        for root in home_roots:
            x, y = root.location.x, root.location.y
            if camera_name == "day44street":
                # North to south: paired roadside houses visibly approach the
                # viewer along West Line Road, while the rest follow the same wave.
                start = 50 + int((832.5-y) / 322.0 * 245.0)
            elif camera_name == "day44drone":
                # The drone travels north, then west; Bramble rises with the
                # first leg and Ember follows the bank into the second.
                if x > -500.0:
                    start = 45 + int((y-510.0) / 322.0 * 190.0)
                else:
                    start = 225 + int((-500.0-x) / 272.5 * 72.0)
            elif camera_name == "day44field":
                # Distant Bramble first, then the westward wave reaches the
                # fixed observer as the optical zoom closes in.
                start = 48 + int((-268.0-x) / 504.5 * 245.0)
            else:
                # Construction fills northward while the city overview dives
                # into the active streets, keeping arrivals ahead of the lens.
                start = 78 + int((y-510.0) / 322.0 * 205.0)
            animate_rise(root, max(40, min(300, start)), dur=20)
    elif cfg.get("cam") in ("day44allapproach", "day44alldrone",
                            "day44allfield"):
        frame_end = FPS * 15
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 186 or len(rise) != 186:
            raise RuntimeError(
                "%s is authored for the full 186-home Day 44 growth. Got %d "
                "homes / %d rising records. Replay with --focus-type house."
                % (cfg.get("cam"), len(home_roots), len(rise)))

        camera_name = cfg.get("cam")
        for root in home_roots:
            x, y = root.location.x, root.location.y
            if camera_name == "day44allapproach":
                # One broad east-to-west front. Nearly the whole batch is
                # visible from the overview before the camera joins its tail.
                start = 88 + int((-268.0-x) / 504.5 * 235.0)
            elif camera_name == "day44alldrone":
                # Bramble rises northward under the first half of the flight;
                # Ember follows in a compressed western front during the bank.
                if x > -500.0:
                    start = 82 + int((y-510.0) / 322.0 * 150.0)
                else:
                    start = 220 + int((-500.0-x) / 272.5 * 105.0)
            else:
                # Distant homes appear first and the complete front advances
                # west toward the stationary observer while the lens tightens.
                start = 92 + int((-268.0-x) / 504.5 * 210.0)
            animate_rise(root, max(72, min(330, start)), dur=32)
    elif cfg.get("cam") == "day44fullarc":
        frame_end = FPS * 20
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 186 or len(rise) != 186:
            raise RuntimeError(
                "day44fullarc is authored for the full 186-home Day 44 growth. "
                "Got %d homes / %d rising records. Replay with --focus-type house."
                % (len(home_roots), len(rise)))
        # The complete east-to-west front runs while the camera is descending
        # and holding its wide low aerial.  The last home finishes before the
        # climb begins, so the closing overhead proves the full result.
        for root in home_roots:
            start = 165 + int((-268.0-root.location.x) / 504.5 * 205.0)
            animate_rise(root, max(155, min(375, start)), dur=36)
    elif cfg.get("cam") in ("day44southfpv", "day44swrooftop",
                            "day44westbank", "day44sereverse"):
        frame_end = FPS * 16          # exact brief: 16 seconds / 480 frames
        camera_name = cfg.get("cam")
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 186 or len(rise) != 186:
            raise RuntimeError(
                "%s requires exactly the 186 Day 44 houses and no landmark; "
                "got %d homes / %d rising records. Replay with --focus-type house."
                % (camera_name, len(home_roots), len(rise)))

        # Granary Street (index 60) already held Day 43 homes and must never be
        # hidden.  These ten indices are the genuinely new Day 44 ribbons.
        new_ids = {b["plan_id"] for b in new_batch if b.get("plan_id")}
        built_ids = {b.get("plan_id") for b in state["buildings"]} - new_ids
        old_streets = {slot["street_index"] for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in built_ids}
        new_streets = sorted({slot["street_index"]
                              for slot in SUBURBAN_PLAN["houses"]
                              if slot["plan_id"] in new_ids} - old_streets)
        if new_streets != list(range(61, 71)):
            raise RuntimeError("Day 44 road suite expected new street indices "
                               "61..70; got %r" % new_streets)
        road_beats = {
            "day44southfpv": {68: 118, 69: 130, 70: 142, 61: 166, 62: 184,
                              63: 202, 64: 220, 65: 238, 66: 256, 67: 274},
            "day44swrooftop": {68: 132, 69: 146, 70: 160, 61: 180, 62: 196,
                               63: 212, 64: 228, 65: 244, 66: 260, 67: 276},
            "day44westbank": {61: 132, 62: 150, 63: 168, 68: 174, 64: 190,
                              69: 204, 65: 218, 70: 234, 66: 252, 67: 270},
            "day44sereverse": {67: 132, 66: 150, 65: 168, 68: 176, 69: 188,
                               70: 200, 64: 218, 63: 238, 62: 258, 61: 278},
        }[camera_name]
        ribbons_prefix = ("suburban_shoulder_", "suburban_road_",
                          "suburban_path_")
        for street_index in new_streets:
            pieces = [obj for obj in world_col.objects
                      if obj.get("nb_street_index") == street_index]
            start = road_beats[street_index]
            reverse = ((camera_name in ("day44southfpv", "day44westbank")
                        and street_index < 68) or
                       (camera_name == "day44sereverse" and street_index >= 68))
            ribbons = [obj for obj in pieces
                       if obj.name.startswith(ribbons_prefix)]
            trim = [obj for obj in pieces if obj not in ribbons]
            for obj in ribbons:
                animate_road_build(obj, start, dur=44, reverse=reverse)
            if trim:
                xs = [obj.location.x for obj in trim]
                ys = [obj.location.y for obj in trim]
                along_x = (max(xs)-min(xs)) >= (max(ys)-min(ys))
                trim.sort(key=lambda obj: obj.location.x if along_x
                          else obj.location.y, reverse=reverse)
                span = max(1, len(trim)-1)
                for index, obj in enumerate(trim):
                    _keyframe_hidden(obj, 1, True)
                    _keyframe_hidden(obj, start+8+int(44*index/span), False)

        for root in home_roots:
            x, y = root.location.x, root.location.y
            if camera_name == "day44southfpv":
                start = (148 + int((y-510.0)/308.0*150.0)
                         if x > -500.0 else
                         286 + int((-610.0-x)/148.5*60.0))
            elif camera_name == "day44swrooftop":
                start = 174 + int((x+758.5)/490.1*158.0)
            elif camera_name == "day44westbank":
                diagonal = (.58*(x+758.5)/490.1 + .42*(y-510.0)/308.0)
                start = 152 + int(diagonal*184.0)
            else:
                reverse_wave = (.54*(x+758.5)/490.1 +
                                .46*(818.5-y)/308.0)
                start = 142 + int(reverse_wave*190.0)
            animate_rise(root, max(136, min(344, start)), dur=18)
    elif cfg.get("cam") in ("day44overhead", "day44downtown"):
        frame_end = FPS * 10
    elif cfg.get("cam") in ("day43fpv", "day43pov"):
        frame_end = FPS * 16          # exact brief: sixteen seconds / 480 frames
        camera_name = cfg.get("cam")
        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 224 or len(rise) != 224:
            raise RuntimeError(
                "%s is authored for exactly 224 ordinary Day 43 homes and "
                "no landmark. Got %d homes / %d rising records. Use the exact "
                "1560 -> 1784 growth; Followville Point Station already exists."
                % (camera_name, len(home_roots), len(rise)))

        # Only genuinely new streets animate.  Millrace West 3 is carried from
        # Day 42, so hiding it would pull pavement out from under standing
        # homes.  The seven remaining Day 43 streets draw on before their house
        # waves and are complete at the export frame.
        new_ids = {b["plan_id"] for b in new_batch if b.get("plan_id")}
        built_ids = {b.get("plan_id") for b in state["buildings"]} - new_ids
        old_streets = {slot["street_index"] for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in built_ids}
        new_streets = sorted({slot["street_index"]
                              for slot in SUBURBAN_PLAN["houses"]
                              if slot["plan_id"] in new_ids} - old_streets)
        ribbons_prefix = ("suburban_shoulder_", "suburban_road_",
                          "suburban_path_")
        if camera_name == "day43fpv":
            road_beats = {53: 92, 54: 116, 55: 142, 56: 190,
                          57: 202, 58: 214, 59: 222, 60: 236}
        else:
            # Wicker Avenue reaches toward the stationary viewer first.  The
            # rest begin as the film cuts into its close overhead continuation.
            road_beats = {57: 62, 56: 188, 58: 198, 53: 214,
                          54: 224, 55: 234, 59: 244, 60: 254}
        for street_index in new_streets:
            pieces = [obj for obj in world_col.objects
                      if obj.get("nb_street_index") == street_index]
            start = road_beats.get(street_index, 210)
            ribbons = [obj for obj in pieces
                       if obj.name.startswith(ribbons_prefix)]
            trim = [obj for obj in pieces if obj not in ribbons]
            for obj in ribbons:
                animate_road_build(obj, start, dur=58,
                                   reverse=(camera_name == "day43pov"
                                            and street_index == 57))
            if trim:
                xs = [obj.location.x for obj in trim]
                ys = [obj.location.y for obj in trim]
                along_x = (max(xs) - min(xs)) >= (max(ys) - min(ys))
                trim.sort(key=lambda obj: (obj.location.x if along_x
                                            else obj.location.y),
                          reverse=(camera_name == "day43pov"
                                   and street_index == 57))
                span = max(1, len(trim)-1)
                for index, obj in enumerate(trim):
                    _keyframe_hidden(obj, 1, True)
                    _keyframe_hidden(obj, start+10+int(58*index/span), False)

        if camera_name == "day43fpv":
            for root in home_roots:
                x, y = root.location.x, root.location.y
                if y < 505.0:
                    # During the low westbound pass, begin 0.8-1.2 seconds
                    # before the camera reaches each longitude.
                    crossing = 126.0 + (-176.0-x)*(132.0/478.0)
                    start = int(max(108, min(252, crossing-30.0)))
                else:
                    # The bank north follows the wave's latitude, keeping the
                    # next rows above the nose instead of already behind it.
                    start = int(max(222, min(330, 224.0+(y-509.0)*.38)))
                animate_rise(root, start, dur=18)
            plant_start, plant_dur = 414, 44
        else:
            for root in home_roots:
                x, y = root.location.x, root.location.y
                on_wicker = abs(x+330.0) < 12.0 and y > 500.0
                if on_wicker:
                    # Far north to south: the paired houses race at the human
                    # eye, reach y=650 around mid-shot, then continue behind it.
                    start = int(78.0+(787.5-y)*.43)
                elif y > 500.0:
                    # The adjacent avenues continue under the close overhead.
                    start = int(218.0+(787.5-y)*.36)
                else:
                    # Southern rows sweep east-to-west with the overhead move.
                    start = int(232.0+(-200.0-x)*.20)
                animate_rise(root, max(72, min(338, start)), dur=18)
            plant_start, plant_dur = 416, 46

        # The station is already canonical Day 42 geometry.  Its only Day 43
        # treatment is this temporary animation: hidden until the finale, then
        # the existing root rises intact.  It never enters new_batch, state, or
        # the follower count, and export_web bakes the fully standing end frame.
        plant_roots = [root for root in building_roots
                       if root.get("nb_world_type") == "nuclearplant"]
        if len(plant_roots) != 1:
            raise RuntimeError("Day 43 finale requires exactly one existing "
                               "Followville Point Station; found %d"
                               % len(plant_roots))
        animate_rise(plant_roots[0], plant_start, dur=plant_dur)
    elif cfg.get("cam") == "day42reveal":
        frame_end = FPS * 16          # exact brief: sixteen seconds / 480 frames
    elif cfg.get("cam") == "day41reveal":
        frame_end = FPS * 30          # exactly thirty seconds, not "at least"
    elif cfg.get("cam") == "metroreveal":
        frame_end = FPS * 26          # historic city -> highway -> boulevard
    elif cfg.get("cam") == "day40reveal":
        frame_end = FPS * 27          # 21s drone run, then 6s on the station
    elif cfg.get("cam") == "day39reveal":
        frame_end = FPS * 20          # exactly twenty seconds, not "at least"
    elif cfg.get("cam") == "day39mayor":
        frame_end = FPS * 10
    elif cfg.get("cam") == "day38foodtour":
        frame_end = max(frame_end, FPS * 20)
    elif cfg.get("cam") == "day38reveal":
        frame_end = max(frame_end, FPS * 16)
    elif cfg.get("cam") == "day37reveal":
        frame_end = max(frame_end, FPS * 24)
    elif cfg.get("cam") == "day36reveal":
        frame_end = max(frame_end, FPS * 16)
    elif cfg.get("cam") == "day35store":
        frame_end = max(frame_end, FPS * 25)
    elif cfg.get("cam") == "day34fire":
        frame_end = max(frame_end, FPS * 16)
    elif cfg.get("cam") == "day33storm":
        frame_end = max(frame_end, FPS * 20)
    elif cfg.get("cam") == "day32campaign":
        frame_end = max(frame_end, FPS * 20)
    elif cfg.get("cam") == "day31reveal":
        frame_end = max(frame_end, FPS * 20)
    elif cfg.get("cam") == "day30reveal":
        frame_end = max(frame_end, FPS * 18)
    elif cfg.get("cam") == "day29reveal":
        frame_end = max(frame_end, FPS * 18)
    elif cfg.get("cam") == "day28reveal":
        frame_end = max(frame_end, FPS * 20)
    elif cfg.get("cam") == "day27reveal":
        frame_end = max(frame_end, FPS * 20)
    elif cfg.get("cam") in ("day25reveal", "day26reveal"):
        frame_end = max(frame_end, FPS * 18)
    elif cfg.get("cam") == "day24reveal":
        frame_end = max(frame_end, FPS * 20)
    elif cfg.get("cam") == "day23reveal":
        frame_end = max(frame_end, FPS * 16)
    elif cfg.get("cam") == "day22reveal":
        frame_end = max(frame_end, FPS * 14)
    elif cfg.get("cam") in ("day21growth", "day21drone", "day21skyline"):
        frame_end = max(frame_end, FPS * 8)
    elif cfg.get("cam") in ("street", "newstreet", "storybookstreet", "housefront",
                           "park", "overhead", "wholeoverhead", "downtown",
                           "downtownstreet", "cinematic", "dronezoom", "dronehover",
                           "riverdrone", "riverbridge"):
        frame_end = max(frame_end, FPS * 12)  # give slow showcase cams time to breathe
    elif cfg.get("cam") == "football":
        frame_end = max(frame_end, FPS * 10)
    elif cfg.get("cam") == "school":
        frame_end = max(frame_end, FPS * 8)
    f = prehold
    for e in sink:
        animate_sink(e, f)
        f += stagger
    if cfg.get("cam") == "metroreveal":
        home_roots = sorted(
            (e for e in rise if e.name.startswith("house_d")),
            key=lambda o: (o.location.y, o.location.x))
        tower_roots = sorted(
            (e for e in rise if e.name.startswith("metrotower_d")),
            key=lambda o: int(o.get("nb_world_metro_id", 0)))
        for index, root in enumerate(home_roots):
            animate_rise(root, 205 + int(index*1.15), dur=24)

        first_metro_day = any(int(e.get("nb_world_metro_id", 0)) == 1
                              for e in tower_roots)
        if first_metro_day:
            # The expressway used to be built inside the metropolitan district,
            # so its deck, structure and ramps were in metro_objects and
            # matched here by name. They live in build_highway_system() now,
            # and the whole highway network builds on with the streets: without
            # this the prefixes below would match nothing and 4.4km of freeway
            # would appear in a single frame.
            ribbon_prefixes = ("metro_road_", "highway_")
            # Everything under highway_ that is furniture rather than roadway:
            # animate_road_build sweeps a ribbon along its length, which is the
            # wrong verb for a parked car or a lighting mast.
            not_roadway = ("highway_car", "highway_gantry", "highway_turnaround")
            candidates = list(metro_objects) + list(highway_objects)
            ribbons = [obj for obj in candidates
                       if obj.name.startswith(ribbon_prefixes)
                       and not obj.name.startswith(not_roadway)]
            trim = [obj for obj in candidates if obj not in ribbons]
            for index, obj in enumerate(ribbons):
                animate_road_build(obj, 285 + min(index, 10)*4, dur=112)
            for index, obj in enumerate(trim):
                _keyframe_hidden(obj, 1, True)
                _keyframe_hidden(obj, 372 + min(index, 70), False)
        for index, root in enumerate(tower_roots):
            animate_rise(root, 430 + index*38, dur=62)
        for root in rise:
            if root not in home_roots and root not in tower_roots:
                animate_rise(root, 250, dur=30)
    elif cfg.get("cam") == "day47reveal":
        # Day 47's exact spatial wave is installed with its frame length above.
        pass
    elif cfg.get("cam") == "day48crown":
        # Day 48's spatial wave and tower rise are installed with its frame
        # length above.
        pass
    elif cfg.get("cam") == "day50highway":
        # Day 50's exact spatial wave is installed with its frame length above.
        pass
    elif cfg.get("cam") == "day49northreach":
        # Day 49's spatial wave is installed with its frame length above.
        pass
    elif cfg.get("cam") == "day46sunsetdrone":
        # Day 46's exact spatial wave is installed with its frame length above.
        pass
    elif cfg.get("cam") in ("day44approach", "day44street", "day44drone",
                            "day44field", "day44overhead", "day44downtown",
                            "day44allapproach", "day44alldrone",
                            "day44allfield", "day44southfpv",
                            "day44swrooftop", "day44westbank",
                            "day44sereverse", "day44fullarc"):
        # Day 44 animation was installed with its exact frame length above.
        pass
    elif cfg.get("cam") in ("day43fpv", "day43pov"):
        # Day 43's spatial road/house/station schedule is installed alongside
        # its exact frame length above, before the generic stagger is reached.
        pass
    elif cfg.get("cam") == "day42reveal":
        # Roads and houses move in the same east-to-west direction as the
        # camera. Only streets with no previously built addresses are animated:
        # hiding a carried street would pull pavement out from under Day 41.
        new_ids = {b["plan_id"] for b in new_batch if b.get("plan_id")}
        built_ids = {b.get("plan_id") for b in state["buildings"]} - new_ids
        old_streets = {slot["street_index"] for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in built_ids}
        new_streets = sorted({slot["street_index"]
                              for slot in SUBURBAN_PLAN["houses"]
                              if slot["plan_id"] in new_ids} - old_streets)
        ribbons_prefix = ("suburban_shoulder_", "suburban_road_",
                          "suburban_path_")
        def _camera_crossing_frame(x):
            """Approximate when the low westbound camera reaches world x."""
            # Camera beats are (-205, f180), (-302, f220), (-442, f270),
            # (-575, f320), (-704, f366). Piecewise interpolation is needless
            # here: the low pass is deliberately close to constant velocity.
            return 180.0 + (-205.0 - x) * (186.0 / 499.0)

        for order, street_index in enumerate(new_streets):
            pieces = [obj for obj in world_col.objects
                      if obj.get("nb_street_index") == street_index]
            # Put paving about two seconds ahead of the camera. The street is
            # complete before its house wave and remains visible as the drone
            # passes through the newly finished block.
            # Road ribbons keep world-space vertices and an origin at zero, so
            # obj.location is not their position. Measure transformed bounds;
            # otherwise every new road would falsely schedule as if downtown.
            bounds_x = [float((obj.matrix_world @ Vector(corner)).x)
                        for obj in pieces for corner in obj.bound_box]
            piece_x = ((min(bounds_x) + max(bounds_x)) * .5
                       if bounds_x else -205.0)
            start = max(100, min(300,
                                 int(_camera_crossing_frame(piece_x) - 62)))
            ribbons = [obj for obj in pieces
                       if obj.name.startswith(ribbons_prefix)]
            trim = [obj for obj in pieces if obj not in ribbons]
            for obj in ribbons:
                animate_road_build(obj, start, dur=46)
            if trim:
                xs = [obj.location.x for obj in trim]
                ys = [obj.location.y for obj in trim]
                along_x = (max(xs) - min(xs)) >= (max(ys) - min(ys))
                trim.sort(key=lambda obj: (obj.location.x if along_x
                                            else obj.location.y), reverse=True)
                span = max(1, len(trim) - 1)
                for index, obj in enumerate(trim):
                    _keyframe_hidden(obj, 1, True)
                    _keyframe_hidden(obj, start + 8 + int(46 * index / span),
                                     False)

        home_roots = [root for root in rise if root.name.startswith("house_d")]
        if len(home_roots) != 320:
            raise RuntimeError(
                "day42reveal is authored for exactly 320 homes and got %d. "
                "Use the exact 1240 -> 1560 growth or choose another camera."
                % len(home_roots))
        # Spatial rather than ordinal timing: each house begins about one
        # second before the camera reaches its longitude and finishes while it
        # is still ahead in frame. That produces the requested construction
        # wave in front of the drone instead of a wave underneath or behind it.
        for root in home_roots:
            start = max(112, min(336,
                                 int(_camera_crossing_frame(root.location.x) - 30)))
            animate_rise(root, start, dur=18)
        for root in rise:
            if root not in home_roots:
                animate_rise(root, 210, dur=24)
    elif cfg.get("cam") == "day41reveal":
        # +300 in one day is a whole quarter at once, so nothing here tracks an
        # individual house. The roads draw themselves on along their own
        # length, then three hundred homes rise in one wave, all of it under a
        # camera holding 500m up on the north side.
        #
        # ONLY today's streets are touched, and Foundry Street is deliberately
        # NOT among them even though 58 of today's homes stand on it. Both
        # animate_rise and the Build modifier HIDE what they animate until its
        # turn, and day 40 already built nineteen homes along Foundry --
        # drawing its ribbon on again would pull the road out from under houses
        # that have been standing since yesterday. Same trap the Day 38 tour
        # records, and the same reason day 40 left Northgate Avenue alone.
        new_ids = {b["plan_id"] for b in new_batch if b.get("plan_id")}
        built_ids = {b.get("plan_id") for b in state["buildings"]} - new_ids
        old_streets = {slot["street_index"] for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in built_ids}
        new_streets = sorted({slot["street_index"]
                              for slot in SUBURBAN_PLAN["houses"]
                              if slot["plan_id"] in new_ids} - old_streets)
        # The five north-south crosses go first, near enough together to read
        # as one gesture -- they are what ties the new grid to the town. Then
        # the avenues south to north, so the quarter grows outward from the
        # streets that already exist. Millrace, the far edge, lands at 504.
        ROAD_BEATS = {31: 315, 32: 318, 33: 321, 34: 324, 35: 327,
                      30: 336, 36: 372, 37: 408}
        RIBBONS = ("suburban_shoulder_", "suburban_road_", "suburban_path_")
        for index in new_streets:
            pieces = [obj for obj in world_col.objects
                      if obj.get("nb_street_index") == index]
            if not pieces:
                continue
            start = ROAD_BEATS.get(index, 330)
            ribbons = [o for o in pieces if o.name.startswith(RIBBONS)]
            trim = [o for o in pieces if not o.name.startswith(RIBBONS)]
            for obj in ribbons:
                animate_road_build(obj, start, dur=96)
            # Dashes and lamps chase the paving down the street instead of
            # arriving with it. Which axis to sort on comes from the street's
            # own spread, so this holds for the east-west avenues and the
            # north-south crosses alike.
            if trim:
                xs = [o.location.x for o in trim]
                ys = [o.location.y for o in trim]
                along_x = (max(xs) - min(xs)) >= (max(ys) - min(ys))
                trim.sort(key=lambda o: o.location.x if along_x else o.location.y)
                span = max(1, len(trim) - 1)
                for order, obj in enumerate(trim):
                    _keyframe_hidden(obj, 1, True)
                    _keyframe_hidden(obj, start + 14 + int(96 * order / span),
                                     False)

        home_roots = [e for e in rise if e.name.startswith("house_d")]
        if not 250 <= len(home_roots) <= 340:
            raise RuntimeError(
                "day41reveal is choreographed for a ~300-home day and got %d. "
                "The road beats and the rise wave are both timed to it; use "
                "--cam newgrowthoverhead for a different size."
                % len(home_roots))
        # South to north, which is both away from the town and away from the
        # far edge of frame toward the camera, and -- not a coincidence -- the
        # same order the roads finish in, so no home ever rises onto meadow.
        # 0.55 frames apart: at three hundred homes this is a rolling wave
        # rather than three hundred separate events, and the last one is up at
        # 612, well before the dive home starts at 650.
        for index, e in enumerate(sorted(home_roots, key=lambda o: o.location.y)):
            animate_rise(e, 430 + int(index * 0.55), dur=18)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 300)
    elif cfg.get("cam") == "day40reveal":
        # Foundry Street's road first, then its eighteen homes west to east,
        # then Northgate Avenue's thirty-nine, then the filling station alone
        # in the second shot.
        #
        # ONLY what is new today is touched. animate_rise is also what HIDES an
        # object before its turn, so sweeping in every road would delete the
        # standing town for the first ten seconds. Foundry is the one entirely
        # new street, found by the nb_street_index tag build_suburban_roads
        # stamps on every piece; Northgate Avenue is NOT hidden, because day 39
        # built its western half and the pieces carry no per-segment reveal
        # tag to tell yesterday's pavement from today's.
        new_ids = {b["plan_id"] for b in new_batch if b.get("plan_id")}
        built_ids = {b.get("plan_id") for b in state["buildings"]} - new_ids
        old_streets = {slot["street_index"] for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in built_ids}
        new_streets = {slot["street_index"] for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in new_ids} - old_streets
        for obj in world_col.objects:
            if obj.get("nb_street_index") in new_streets:
                _keyframe_hidden(obj, 1, True)
                _keyframe_hidden(obj, 292, False)

        # Split by position, not by name: the station is the one root that is
        # not a house, and both streets run east-west at known latitudes.
        roots = [e for e in rise
                 if e.name.startswith(("house_d", "gasstation_d"))]
        station = [e for e in roots if e.name.startswith("gasstation_d")]
        homes = [e for e in roots if e not in station]
        foundry = sorted((e for e in homes if e.location.y > 325.0),
                         key=lambda o: o.location.x)
        avenue = sorted((e for e in homes if e.location.y <= 325.0),
                        key=lambda o: o.location.x)
        if len(foundry) != 19 or len(avenue) != 39 or len(station) != 1:
            raise RuntimeError(
                "day40reveal is cut to day 40's exact batch -- 19 Foundry "
                "homes, 39 Northgate Avenue homes and 1 filling station. Got "
                "%d / %d / %d. It needs `+58 --gasstation`; +58 alone steps "
                "over the reserve's filling-station address and builds a "
                "59th home instead."
                % (len(foundry), len(avenue), len(station)))

        # Foundry: 7 frames apart, so nineteen homes take 4.2 seconds rather
        # than reading as one pop. Last is up at 478, as the camera leaves.
        for index, e in enumerate(foundry):
            animate_rise(e, 322 + index * 7, dur=20)
        # The avenue starts while the camera is still finishing Foundry, so its
        # west end is already coming alive in the far depth. 5 frames apart
        # gives thirty-nine homes 6.3 seconds. It starts at 412 rather than 430
        # so the LAST home finishes at 620 -- eleven frames before the cut to
        # the filling station, instead of eight frames after it, which left the
        # easternmost house frozen at nine-tenths height as the shot changed.
        for index, e in enumerate(avenue):
            animate_rise(e, 412 + index * 5, dur=18)
        # The station, alone, thirty frames into its own shot.
        for e in station:
            animate_rise(e, DAY40_GAS_CUT + 30, dur=46)
        for e in rise:
            if e not in roots:
                animate_rise(e, 292)
    elif cfg.get("cam") == "day39mayor":
        # Deliberately animates nothing. This clip is a replay of Day 39, so
        # the batch handed to it is the thirty-three homes 440m north -- and
        # animate_rise is also what HIDES an object before its turn, so
        # touching them would delete the new quarter from its own city's
        # celebration. Everything stays standing.
        pass
    elif cfg.get("cam") == "day39reveal":
        # Roads first, then the homes one at a time. Both land while the
        # camera is still in transit over open meadow, so the quarter reads as
        # "the road arrives, then the street fills in".
        #
        # ONLY the pieces that are new today are touched. animate_rise and
        # _keyframe_hidden both hide an object before its turn, so sweeping in
        # every road would delete the standing town for the first three
        # seconds. The arterial is found by name and today's street by the
        # nb_street_index tag build_suburban_roads stamps on every piece.
        # Building records carry `street` (a name) but not `street_index`, so
        # the indices come back from the plan via the addresses just built.
        new_ids = {b["plan_id"] for b in new_batch if b.get("plan_id")}
        new_streets = {slot["street_index"] for slot in SUBURBAN_PLAN["houses"]
                       if slot["plan_id"] in new_ids}
        arterial = [obj for obj in world_col.objects
                    if obj.name.startswith("northgate_arterial")]
        street = [obj for obj in world_col.objects
                  if obj.get("nb_street_index") in new_streets]
        # Mid-transfer, while the camera is still crossing open meadow.
        for obj in arterial:
            _keyframe_hidden(obj, 1, True)
            _keyframe_hidden(obj, 238, False)
        for obj in street:
            _keyframe_hidden(obj, 1, True)
            _keyframe_hidden(obj, 258, False)
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        # Six frames apart, not three. Thirty-three homes at three frames each
        # is a tenth of a second per house and reads as one pop rather than a
        # street filling in; six gives the sequence six and a half seconds.
        # The last home is up at 555, so the closing lift still lands on a
        # finished street.
        for index, e in enumerate(sorted(home_roots, key=lambda o: o.location.x)):
            animate_rise(e, 345 + index * 6, dur=18)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 345)
    elif cfg.get("cam") == "day38foodtour":
        # The loop road, green and lamps land as the drone arrives at 225;
        # then one home every 8 frames, finishing at 414 -- before the camera
        # is down among them at 515, so nothing pops up in a face.
        #
        # Nothing else is touched. The replay batch is the whole of day 37,
        # which also holds three Heron Reach cabins and Followville Commons,
        # 600m away and already standing for two days. Leaving them
        # un-animated is what keeps them standing: animate_rise is also what
        # hides an object before its turn.
        yard = [e for e in rise if e.name.startswith("foodcourt_d")]
        homes = [e for e in rise if e.name.startswith("foodhouse_d")]
        if len(homes) != 19:
            raise RuntimeError("Day 38 food tour expects 19 food homes in the"
                               " animation batch, found %d" % len(homes))
        for e in yard:
            animate_rise(e, 230, dur=28)
        for index, e in enumerate(homes):
            animate_rise(e, 248 + index * 8, dur=22)
    elif cfg.get("cam") == "day38reveal":
        # The loop road first, then the ring clockwise, finishing with time in
        # hand to look at the finished court.
        yard = [e for e in rise if e.name.startswith("foodcourt_d")]
        homes = [e for e in rise if e.name.startswith("foodhouse_d")]
        for e in yard:
            animate_rise(e, 262, dur=34)
        for index, e in enumerate(homes):
            animate_rise(e, 280 + index * 8, dur=26)
        for e in rise:
            if e not in yard and e not in homes:
                animate_rise(e, 280)
    elif cfg.get("cam") == "day37reveal":
        # The three Heron Reach cabins that finish the 616-house plan are 640m
        # from anything this camera looks at, so they go up early and unseen.
        # The Commons is the only thing that rises on screen.
        commons_roots = [e for e in rise if e.name.startswith("apartmentcomplex_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        for e in home_roots:
            animate_rise(e, 150, dur=30)
        for e in commons_roots:
            animate_rise(e, 286, dur=76)          # settles at 362, well held
        for e in rise:
            if e not in commons_roots and e not in home_roots:
                animate_rise(e, 286, dur=60)
    elif cfg.get("cam") == "day36reveal":
        # Nothing may rise until the drone has arrived at frame 258, and the
        # last home must finish with time left to look at the finished street.
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        for index, e in enumerate(home_roots):
            animate_rise(e, 268 + index * 9, dur=28)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 262)          # the new road/kerbs arrive first
    elif cfg.get("cam") == "day34fire":
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        millstone_roots = [e for e in home_roots
                           if int(e.get("nb_world_plan_id", 0)) <= 556]
        ferry_roots = [e for e in home_roots
                       if int(e.get("nb_world_plan_id", 0)) >= 557]
        for index, e in enumerate(millstone_roots):
            animate_rise(e, 205 + index * 5, dur=28)
        for index, e in enumerate(ferry_roots):
            animate_rise(e, 250 + index * 5, dur=28)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 205)
    elif cfg.get("cam") == "day35store":
        # One continuous shot, so the rises have to land under the camera
        # rather than the camera cutting to them. Homes finish before the
        # drone leaves them; the store starts as the drone arrives over it.
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        store_roots = [e for e in rise if e.name.startswith("salmonproshop_d")]
        if len(store_roots) != 1:
            raise RuntimeError("Day 35 reveal needs exactly one Salmon Pro Shop"
                               " root, found %d" % len(store_roots))
        # 30fps, 720 frames. The camera establishes the town as it stood over
        # frames 1-180, sits on the new homes 250-390, descends onto the store
        # 440-560, then climbs out. Every rise is timed inside the beat that
        # frames it: nothing appears before the drone has arrived to see it,
        # and nothing is still growing when the drone leaves.
        ferry = [e for e in home_roots
                 if int(e.get("nb_world_plan_id", 0)) <= 584]
        marshlight = [e for e in home_roots
                      if int(e.get("nb_world_plan_id", 0)) >= 585]
        for index, e in enumerate(ferry):
            animate_rise(e, 246 + index * 6, dur=26)     # 8 up by frame 314
        for index, e in enumerate(marshlight):
            animate_rise(e, 408 + index * 5, dur=26)     # 16 up by frame 509
        animate_rise(store_roots[0], 648, dur=56)        # settles at 704
        for e in rise:
            if e not in home_roots and e not in store_roots:
                animate_rise(e, 232)
    elif cfg.get("cam") == "day33storm":
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        lodgepole_roots = [e for e in home_roots
                           if int(e.get("nb_world_plan_id", 0)) <= 526]
        millstone_roots = [e for e in home_roots
                           if int(e.get("nb_world_plan_id", 0)) >= 527]
        for index, e in enumerate(lodgepole_roots):
            animate_rise(e, 135 + index * 5, dur=29)
        for index, e in enumerate(millstone_roots):
            animate_rise(e, 225 + index * 5, dur=29)
        weather_roots = [e for e in building_roots
                         if e.get("nb_world_type") == "weatherstation"]
        if len(weather_roots) != 1:
            raise RuntimeError("Day 33 storm reveal requires exactly one weather station")
        animate_rise(weather_roots[0], 442, dur=46)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 190)
    elif cfg.get("cam") == "day32campaign":
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        for index, e in enumerate(home_roots):
            animate_rise(e, 140 + index * 6, dur=28)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 130)
    elif cfg.get("cam") == "day31reveal":
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        cedarbank_roots = [e for e in home_roots
                           if int(e.get("nb_world_plan_id", 0)) <= 472]
        timber_roots = [e for e in home_roots
                        if int(e.get("nb_world_plan_id", 0)) >= 473]
        for index, e in enumerate(cedarbank_roots):
            animate_rise(e, 180 + index * 7, dur=28)
        for index, e in enumerate(timber_roots):
            animate_rise(e, 270 + index * 8, dur=30)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 165)
    elif cfg.get("cam") == "day30reveal":
        # Streets and terrain settle just before the drone arrives, then the
        # forty-six homes rise in a nine-second wave that finishes with roughly
        # two and a half seconds of clean hold left in the shot.
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        for index, e in enumerate(home_roots):
            animate_rise(e, 165 + index * 6, dur=30)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 132)
    elif cfg.get("cam") == "day29reveal":
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        station_roots = [e for e in rise
                         if e.name.startswith("raftingstation_d")]
        for index, e in enumerate(home_roots):
            animate_rise(e, 150 + index * 4, dur=29)
        for e in station_roots:
            animate_rise(e, 420, dur=42)
        for e in rise:
            if e not in home_roots and e not in station_roots:
                animate_rise(e, 205)
    elif cfg.get("cam") == "day28reveal":
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        summit_roots = [e for e in home_roots
                        if int(e.get("nb_world_plan_id", 0)) <= 366]
        river_roots = [e for e in home_roots
                       if int(e.get("nb_world_plan_id", 0)) >= 367]
        for index, e in enumerate(summit_roots):
            animate_rise(e, 75+index*3, dur=25)
        for index, obj in enumerate(river_objects):
            # Water/banks arrive first, then bridge furniture and planting.
            animate_rise(obj, 165+min(index, 18)*3, dur=30)
        for index, obj in enumerate(river_road_objects):
            # Crossing Way visibly forms after the river and before its homes.
            animate_rise(obj, 260+min(index, 14)*2, dur=28)
        for index, e in enumerate(river_roots):
            animate_rise(e, 325+index*6, dur=27)
        for e in rise:
            if e not in home_roots:
                animate_rise(e, 170)
    elif cfg.get("cam") == "day27reveal":
        theater_roots = [e for e in rise if e.name.startswith("movietheater_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        ridgeview = [e for e in home_roots
                     if e.get("nb_world_district") == "North Ridge"]
        for index, e in enumerate(ridgeview):
            # Four overlapping waves keep motion continuous without turning
            # the 36-home milestone into a one-at-a-time checklist.
            animate_rise(e, 210 + index * 5, dur=29)
        for e in theater_roots:
            animate_rise(e, 486, dur=48)
        for e in rise:
            if e not in theater_roots and e not in home_roots:
                animate_rise(e, 224)
    elif cfg.get("cam") == "day26reveal":
        zone_roots = [e for e in rise if e.name.startswith("constructionzone_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        pine_roots = [e for e in home_roots
                      if e.get("nb_world_district") == "Pine Hollow"]
        ridge_roots = [e for e in home_roots
                       if e.get("nb_world_district") == "North Ridge"]
        for index, e in enumerate(pine_roots):
            animate_rise(e, 142 + index * 6, dur=27)
        for index, e in enumerate(ridge_roots):
            animate_rise(e, 326 + index * 9, dur=27)
        for e in zone_roots:
            animate_rise(e, 440, dur=42)
        for e in rise:
            if (e not in zone_roots and e not in home_roots
                    and not e.name.startswith("forestreserve_d")):
                animate_rise(e, 160)
    elif cfg.get("cam") == "day25reveal":
        pond_roots = [e for e in rise if e.name.startswith("fishingpond_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        meadow_roots = home_roots[:4]
        pine_roots = home_roots[4:23]
        juniper_roots = home_roots[23:]
        for index, e in enumerate(meadow_roots):
            animate_rise(e, 128 + index * 7, dur=24)
        for index, e in enumerate(pine_roots):
            animate_rise(e, 150 + index * 5, dur=25)
        for index, e in enumerate(juniper_roots):
            animate_rise(e, 242 + index * 5, dur=25)
        for e in pond_roots:
            animate_rise(e, 424, dur=36)
        for e in rise:
            if e not in pond_roots and e not in home_roots:
                animate_rise(e, 150)
    elif cfg.get("cam") == "day24reveal":
        square_roots = [e for e in rise if e.name.startswith("civicsquare_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        larkspur_roots = home_roots[:7]
        sunset_roots = home_roots[7:]
        for index, e in enumerate(larkspur_roots):
            animate_rise(e, 165 + index * 7, dur=25)
        for index, e in enumerate(sunset_roots):
            animate_rise(e, 225 + index * 4, dur=25)
        for e in square_roots:
            animate_rise(e, 460, dur=35)
        for e in rise:
            if e not in square_roots and e not in home_roots:
                animate_rise(e, 165)
    elif cfg.get("cam") == "day23reveal":
        road_roots = [e for e in rise if e.name.startswith("cityhallroad_d")]
        hall_roots = [e for e in rise if e.name.startswith("cityhall_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        for index, e in enumerate(home_roots):
            animate_rise(e, 166 + index * 4, dur=25)
        for e in road_roots:
            animate_road_extend(e, 326, dur=44)
        for e in hall_roots:
            animate_rise(e, 400, dur=42)
        for e in rise:
            if e not in road_roots and e not in hall_roots and e not in home_roots:
                animate_rise(e, 166)
    elif cfg.get("cam") == "day22reveal":
        station_roots = [e for e in rise if e.name.startswith("firestation_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        for index, e in enumerate(home_roots):
            animate_rise(e, 176 + index * 6, dur=24)
        for e in station_roots:
            animate_rise(e, 334, dur=34)
        for e in rise:
            if e not in station_roots and e not in home_roots:
                animate_rise(e, 176)
    elif cfg.get("cam") == "day21growth":
        truck_roots = [e for e in rise if e.name.startswith("coffeetruck_d")]
        home_roots = [e for e in rise if e.name.startswith("house_d")]
        for e in truck_roots:
            animate_rise(e, 28)
        for index, e in enumerate(home_roots):
            animate_rise(e, 112 + index * 9)
        for e in rise:
            if e not in truck_roots and e not in home_roots:
                animate_rise(e, 112)
    else:
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
    if (cfg.get("hero") or cfg.get("cam") in ("newgrowth", "newgrowthall", "newgrowthoverhead")) and hero_batch:
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
    if cfg.get("cam") == "day37reveal":
        animate_rise(build_day37_statue(world_col, state["buildings"], frame_end),
                     566, dur=80)
    if cfg.get("cam") == "day34fire":
        build_day34_fire_response(world_col, state["buildings"], frame_end)
    if cfg.get("cam") == "day33storm":
        build_storm_layer(world_col, frame_end)
    if cfg.get("cam") == "day32campaign":
        build_day32_campaign_vignette(world_col, frame_end)
    if cfg.get("cam") == "football":
        build_football_vignette(world_col, state["buildings"], frame_end)
    if cfg.get("cam") in ("story001pricesign", "story001dusk"):
        build_story001_price_sign(world_col, frame_end,
                                  dusk=cfg.get("cam") == "story001dusk")
    if cfg.get("godzilla"):
        build_godzilla_attack(world_col, state["buildings"], building_roots, frame_end)
    apply_mood(tod, season)
    setup_render(state, frame_end, cfg.get("tag"), tod, cfg.get("cam"))

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

    # Production previews render selected full-quality frames from an isolated
    # state copy before anyone commits to 480 frames.  This is deliberately an
    # environment hook rather than another camera mode: it exercises the exact
    # same scene, timing, lighting, terrain, and render settings as the movie.
    preview_spec = os.environ.get("FOLLOWVILLE_PREVIEW_FRAMES", "").strip()
    if preview_spec:
        frames = sorted({int(value.strip()) for value in preview_spec.split(",")
                         if value.strip()})
        if not frames or frames[0] < 1 or frames[-1] > frame_end:
            raise RuntimeError("FOLLOWVILLE_PREVIEW_FRAMES must stay inside "
                               "1..%d" % frame_end)
        preview_root = os.environ.get(
            "FOLLOWVILLE_PREVIEW_DIR",
            os.path.join(os.path.dirname(bpy.data.filepath), "renders",
                         "day_%03d_%s_previews" %
                         (state["day"], cfg.get("cam") or "camera")))
        os.makedirs(preview_root, exist_ok=True)
        try:
            bpy.context.scene.render.image_settings.media_type = "IMAGE"
        except Exception:
            pass
        bpy.context.scene.render.image_settings.file_format = "PNG"
        for frame in frames:
            bpy.context.scene.frame_set(frame)
            path = os.path.join(preview_root, "frame_%04d.png" % frame)
            bpy.context.scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print("PREVIEW " + path)
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
        items=[(k, k.title(), "") for k in ("auto", "day", "sunset", "night", "storm")])
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

# Importing this module inside a background Blender session used to GROW THE
# CITY, because the line below is all there is between "load the generator" and
# "run a growth". check_food_assets.py imports it to build the ten food house
# designs and measure them; the first time that ran with NEIGHBORHOOD_STATE_DIR
# pointing at the repo, the import advanced the world to day 40 and appended
# five Northgate houses, which then made town_manifest.json disagree with
# world_state.json and dropped the browser out of district streaming.
#
# FOLLOWVILLE_IMPORT_ONLY says "I want the functions, not a growth". Nothing in
# the growth path sets it, so grow_windows.ps1, grow.sh and the GUI panel are
# unaffected -- but any tool that wants to read the generator can now do so
# without changing the city.
if bpy.app.background:
    if os.environ.get("FOLLOWVILLE_IMPORT_ONLY"):
        print("neighborhood_blender: imported for inspection; no growth run.")
    else:
        main()
else:
    _register_ui()
    print("City panel ready — press N in the 3D viewport and open the 'City' tab.")
