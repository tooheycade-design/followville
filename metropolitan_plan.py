"""Deterministic post-Northgate metropolitan expansion for Followville.

This module is pure data and geometry-free.  It reserves twenty individually
claimable tower addresses after the ordinary neighborhood reserve is exhausted.
Each tower represents at most 100 followers.  Roads and public realm remain
absent until the first tower record exists in ``world_state.json``.

The district is an extension of the Northgate/Southline grid, not a second
city: every north/south street continues an existing cross street, Kettle Row
becomes the southern seam, and Crown Boulevard connects the local grid to a
six-lane elevated regional expressway on the east edge.
"""

import math


DISTRICT = "Crown Quarter"
TOWER_RESIDENT_CAPACITY = 100
TOWER_COUNT = 20
METRO_RESIDENT_CAPACITY = TOWER_COUNT * TOWER_RESIDENT_CAPACITY
TERRACE_DATUM = 5.0

# Six inherited north/south street lines form five 70m-wide blocks.  The five
# east/west streets form four 66m-deep blocks: exactly twenty tower parcels.
NORTH_SOUTH_X = (-190.0, -120.0, -50.0, 20.0, 90.0, 160.0)
EAST_WEST_Y = (522.0, 588.0, 654.0, 720.0, 786.0)

LOCAL_ROAD_WIDTH = 8.0
BOULEVARD_WIDTH = 14.0
SIDEWALK_WIDTH = 3.2

# Where the east/west streets stop on their western side.  It used to be -220,
# which put every one of them -- including both boulevards -- into a dead end
# in open meadow.  Chapter four's West Quarter now runs up the outside of the
# district, and its eastern edge street is Forge Avenue at x=-260, so the five
# streets run on and meet it at a junction instead of simply stopping.
#
# At y=522 this does more than tidy an end: the West Quarter's Harrow Row is
# on the same line, so Kettle Row and Harrow Row become one continuous road
# from x=-680 all the way through downtown to x=196.
#
# The other four cannot be carried west THROUGH the suburb, only up to it.
# Crown Quarter's east/west ladder steps 66m and the West Quarter's steps 36m,
# so Founders Boulevard at y=588 lands 6m from Thresher Street at y=594 --
# closer than either road is wide. They meet the quarter's edge at a junction;
# they do not continue into it.
WEST_END = -260.0

# The highway is deliberately on the outer edge.  It gives the city regional
# infrastructure without cutting the walkable tower grid in two.
EXPRESSWAY_X = 222.0
EXPRESSWAY_Y0 = 250.0
EXPRESSWAY_Y1 = 858.0
EXPRESSWAY_DECK_Z = 14.0
EXPRESSWAY_WIDTH = 24.0
EXPRESSWAY_REVEAL_TOWER = 1
INTERCHANGE_Y = 654.0

STREET_NAMES_NS = (
    "West Market Street", "Kiln Avenue", "Maple Avenue",
    "Cedar Avenue", "Quarry Avenue", "Anvil Avenue",
)
STREET_NAMES_EW = (
    "Kettle Row", "Founders Boulevard", "Crown Boulevard",
    "Aurora Street", "Summit Street",
)


def _tower_height(column, row):
    """A realistic skyline: lower shoulders, tall center, varied silhouettes."""
    center = 1.0 - min(1.0, math.hypot((column - 2.0) / 2.4,
                                      (row - 1.55) / 2.1))
    rhythm = (0.0, 7.0, -4.0, 11.0, 3.0)[column]
    row_shift = (0.0, 9.0, -3.0, 5.0)[row]
    return round(54.0 + center * 54.0 + rhythm + row_shift, 1)


def _build_tower_plan():
    plan = []
    metro_id = 1
    # Growth fills from the inherited Kettle Row edge northward, so the skyline
    # visibly grows out of the existing city rather than appearing at its far end.
    for row in range(4):
        for column in range(5):
            x = (NORTH_SOUTH_X[column] + NORTH_SOUTH_X[column + 1]) / 2.0
            y = (EAST_WEST_Y[row] + EAST_WEST_Y[row + 1]) / 2.0
            # Alternating shallow setbacks keep façades from forming one wall.
            x += (-2.5, 2.0, -1.5, 2.5, 0.0)[column]
            y += (-1.5, 2.0, -2.0, 1.5, 0.0)[(column + row) % 5]
            plan.append({
                "metro_id": metro_id,
                "district": DISTRICT,
                "street": STREET_NAMES_EW[row],
                "x": round(x, 3),
                "y": round(y, 3),
                "z": TERRACE_DATUM,
                "rot": 0.0 if (column + row) % 2 == 0 else math.pi,
                "variant": metro_id - 1,
                "height": _tower_height(column, row),
                "capacity": TOWER_RESIDENT_CAPACITY,
                "column": column,
                "row": row,
            })
            metro_id += 1
    return tuple(plan)


TOWER_PLAN = _build_tower_plan()


def street_plan():
    streets = []
    for index, x in enumerate(NORTH_SOUTH_X):
        streets.append({
            "name": STREET_NAMES_NS[index],
            "points": ((x, 486.0), (x, 824.0)),
            "width": LOCAL_ROAD_WIDTH,
            "kind": "collector" if index in (1, 3, 5) else "local",
        })
    for index, y in enumerate(EAST_WEST_Y):
        is_boulevard = y in (588.0, INTERCHANGE_Y)
        east_end = 278.0 if y == INTERCHANGE_Y else 196.0
        streets.append({
            "name": STREET_NAMES_EW[index],
            "points": ((WEST_END, y), (east_end, y)),
            "width": BOULEVARD_WIDTH if is_boulevard else LOCAL_ROAD_WIDTH,
            "kind": "boulevard" if is_boulevard else "local",
        })
    return tuple(streets)


STREETS = street_plan()


def expressway_points(step=3.0):
    count = int(math.ceil((EXPRESSWAY_Y1 - EXPRESSWAY_Y0) / step))
    return tuple((EXPRESSWAY_X,
                  EXPRESSWAY_Y0 + (EXPRESSWAY_Y1 - EXPRESSWAY_Y0) * i / count,
                  EXPRESSWAY_DECK_Z) for i in range(count + 1))


def ramp_plan():
    """Diamond interchange ramps, all one-way-width and grade-limited."""
    return (
        {"name": "southbound-off", "points": (
            (EXPRESSWAY_X - 6.5, 586.0, EXPRESSWAY_DECK_Z),
            (205.0, 610.0, 12.0), (196.0, 635.0, 8.0),
            (186.0, INTERCHANGE_Y, TERRACE_DATUM + .18))},
        {"name": "southbound-on", "points": (
            (186.0, INTERCHANGE_Y, TERRACE_DATUM + .18),
            (196.0, 674.0, 8.0), (205.0, 700.0, 12.0),
            (EXPRESSWAY_X - 6.5, 724.0, EXPRESSWAY_DECK_Z))},
        {"name": "northbound-off", "points": (
            (EXPRESSWAY_X + 6.5, 724.0, EXPRESSWAY_DECK_Z),
            (240.0, 700.0, 12.0), (248.0, 674.0, 8.0),
            (258.0, INTERCHANGE_Y, TERRACE_DATUM + .18))},
        {"name": "northbound-on", "points": (
            (258.0, INTERCHANGE_Y, TERRACE_DATUM + .18),
            (248.0, 635.0, 8.0), (240.0, 610.0, 12.0),
            (EXPRESSWAY_X + 6.5, 586.0, EXPRESSWAY_DECK_Z))},
    )


RAMPS = ramp_plan()


def validate_plan():
    errors = []
    if len(TOWER_PLAN) != TOWER_COUNT:
        errors.append("tower count is not %d" % TOWER_COUNT)
    ids = [tower["metro_id"] for tower in TOWER_PLAN]
    if ids != list(range(1, TOWER_COUNT + 1)):
        errors.append("metro ids are not continuous")
    for a_index, a in enumerate(TOWER_PLAN):
        if not (NORTH_SOUTH_X[0] < a["x"] < NORTH_SOUTH_X[-1]):
            errors.append("tower %d lies outside the street grid" % a["metro_id"])
        if not (EAST_WEST_Y[0] < a["y"] < EAST_WEST_Y[-1]):
            errors.append("tower %d lies outside the street grid" % a["metro_id"])
        for b in TOWER_PLAN[a_index + 1:]:
            if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < 48.0:
                errors.append("tower parcels %d and %d overlap" %
                              (a["metro_id"], b["metro_id"]))
    if abs(EAST_WEST_Y[0] - 522.0) > .001:
        errors.append("Kettle Row seam moved")
    if EXPRESSWAY_X - NORTH_SOUTH_X[-1] < 45.0:
        errors.append("expressway is too close to tower blocks")
    return errors


if __name__ == "__main__":
    failures = validate_plan()
    if failures:
        raise SystemExit("\n".join(failures))
    print("Crown Quarter: %d claimable towers, %d follower capacity" %
          (TOWER_COUNT, METRO_RESIDENT_CAPACITY))
    print("Existing grid continuations: %d; east/west streets: %d; ramps: %d" %
          (len(NORTH_SOUTH_X), len(EAST_WEST_Y), len(RAMPS)))
