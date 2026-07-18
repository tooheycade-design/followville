"""Deterministic render-time layout transforms for the experimental city.

The authoritative Day-15 state keeps its original IDs, claims, addresses and
stored coordinates.  This module moves complete districts as rigid groups so
the expanded downtown cannot overlap their roads.  Every consumer (Blender,
the local browser and QA) uses the same offsets.
"""


DISTRICT_OFFSETS = {
    "Creekside Bend": (0.0, 58.0),
    "Willow Hills": (-48.0, 48.0),
    "Twin Oaks": (-62.0, 0.0),
    "Meadow Run": (-48.0, -48.0),
    "Pine Hollow": (0.0, -62.0),
    "North Ridge": (48.0, -48.0),
}

FOUNDER_PARK_OFFSET = (35.0, 0.0)
STORYBOOK_OFFSET = (35.0, 0.0)
STORYBOOK_LAYOUT_CENTER = (305.0, 60.0)

# Curved transition roads begin on an outer downtown street and terminate at
# each shifted district's original entrance. They reveal only when that
# district has at least one house, preserving staged-road behavior.
DISTRICT_CONNECTORS = {
    "Creekside Bend": [(-35.0, 87.0), (-41.0, 99.0), (-39.0, 114.0), (-35.0, 127.0)],
    "Willow Hills": [(-93.0, 70.0), (-101.0, 82.0), (-112.0, 96.0), (-123.0, 112.0)],
    "Twin Oaks": [(-93.0, 20.0), (-108.0, 17.0), (-123.0, 18.0), (-137.0, 20.0)],
    "Meadow Run": [(-93.0, -70.0), (-101.0, -88.0), (-112.0, -107.0), (-123.0, -123.0)],
    "Pine Hollow": [(-24.0, -93.0), (-29.0, -108.0), (-27.0, -123.0), (-24.0, -137.0)],
    "North Ridge": [(70.0, -93.0), (91.0, -99.0), (114.0, -111.0), (133.0, -123.0)],
}


def offset_for(district=None, building_type=None, feature_id=None):
    if district in DISTRICT_OFFSETS:
        return DISTRICT_OFFSETS[district]
    if building_type in ("parkdistrict", "ringhouse"):
        return FOUNDER_PARK_OFFSET
    if building_type == "storybookhouse" or feature_id == "kaleidoscope_crest_day15":
        return STORYBOOK_OFFSET
    return (0.0, 0.0)


def transform_point(x, y, district=None, building_type=None, feature_id=None):
    dx, dy = offset_for(district, building_type, feature_id)
    return float(x) + dx, float(y) + dy


def transform_building_point(building):
    return transform_point(
        building.get("px", 0.0), building.get("py", 0.0),
        district=building.get("district"),
        building_type=building.get("type"),
        feature_id=building.get("feature_id"),
    )
