"""Standalone, no-Blender validation for the optional visual layer."""

import json
import math

from downtown_visual_plan import audit_terrain, sample_road_points, terrain_height
from neighborhood_plan import PLAN, validate_plan
from world_layout import DISTRICT_CONNECTORS, transform_building_point, transform_point


def lot_to_world(gx, gy, block_n=3, lot=13, road=6):
    pitch = block_n*lot+road
    bx, ix = divmod(gx, block_n)
    by, iy = divmod(gy, block_n)
    return (bx*pitch+ix*lot+lot/2, by*pitch+iy*lot+lot/2)


def main():
    with open("world_state.json") as handle:
        state = json.load(handle)
    points = []
    for building in state["buildings"]:
        point = (transform_building_point(building)
                 if "px" in building else
                 lot_to_world(building["gx"], building["gy"]))
        points.append(("current house/building %s" % building["seed"], point))
    points.extend(("future house %d" % house["plan_id"],
                   transform_point(house["x"], house["y"], district=house["district"]))
                  for house in PLAN["houses"])
    for index, segment in enumerate(PLAN["roads"]):
        a=transform_point(*segment["a"],district=segment["district"])
        b=transform_point(*segment["b"],district=segment["district"])
        points.extend(("future road %d" % index,
                       (a[0]+(b[0]-a[0])*t/4,a[1]+(b[1]-a[1])*t/4))
                      for t in range(5))
    heights = [terrain_height(*point) for _label, point in points]
    errors = validate_plan()+audit_terrain(PLAN)
    # The full rectangular downtown datum must stay clear of meadow terrain.
    # This includes outer grid corners and the elementary-school campus; the
    # old circular mask clipped these diagonals and buried paved surfaces.
    for x in (-100.0, 0.0, 100.0):
        for y in (-100.0, 0.0, 100.0):
            if terrain_height(x, y) > .001:
                errors.append("downtown protected datum raised at %.1f,%.1f" % (x, y))
    school_origin = (-77.0, -77.0)
    for ox, oy in ((-14.2, -14.2), (14.2, -14.2),
                   (-14.2, 14.2), (14.2, 14.2), (0.0, -11.3)):
        if terrain_height(school_origin[0]+ox, school_origin[1]+oy) > .001:
            errors.append("school paved footprint intersects regional terrain")
    for index,segment in enumerate(PLAN["roads"]):
        a=transform_point(*segment["a"],district=segment["district"])
        b=transform_point(*segment["b"],district=segment["district"])
        length=max(.001,math.hypot(b[0]-a[0],b[1]-a[1]))
        grade=abs(terrain_height(*b)-terrain_height(*a))/length
        if grade>.16:
            errors.append("shifted future road %d grade %.3f exceeds .160"%(index,grade))
    # No shifted house may intrude into the expanded downtown road envelope.
    for house in PLAN["houses"]:
        x,y=transform_point(house["x"],house["y"],district=house["district"])
        if -99<x<93 and -99<y<93:
            errors.append("shifted future house %d overlaps downtown"%house["plan_id"])
    if not all(0 <= height < 40 for height in heights):
        errors.append("terrain produced an invalid current/future height")
    if errors:
        raise SystemExit("\n".join(errors))
    print("DOWNTOWN_VISUAL_CHECK_OK day=%d population=%d buildings=%d "
          "future_houses=%d future_roads=%d" %
          (state["day"], state["pop"], len(state["buildings"]),
           len(PLAN["houses"]), len(PLAN["roads"])))


if __name__ == "__main__":
    main()
