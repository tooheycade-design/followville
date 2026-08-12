import math
import unittest

import metropolitan_plan as metro
from downtown_visual_plan import terrain_height


class MetropolitanPlanTests(unittest.TestCase):
    def test_capacity_and_stable_ids(self):
        self.assertEqual(metro.TOWER_COUNT, 20)
        self.assertEqual(metro.METRO_RESIDENT_CAPACITY, 2000)
        self.assertEqual([slot["metro_id"] for slot in metro.TOWER_PLAN],
                         list(range(1, 21)))
        self.assertEqual(metro.validate_plan(), [])

    def test_every_parcel_is_unique_and_inside_the_grid(self):
        locations = {(slot["x"], slot["y"]) for slot in metro.TOWER_PLAN}
        self.assertEqual(len(locations), 20)
        for slot in metro.TOWER_PLAN:
            self.assertGreater(slot["x"], metro.NORTH_SOUTH_X[0])
            self.assertLess(slot["x"], metro.NORTH_SOUTH_X[-1])
            self.assertGreater(slot["y"], metro.EAST_WEST_Y[0])
            self.assertLess(slot["y"], metro.EAST_WEST_Y[-1])
            self.assertAlmostEqual(terrain_height(slot["x"], slot["y"]),
                                   metro.TERRACE_DATUM, places=3)

    def test_streets_continue_southline_and_reach_interchange(self):
        north_south = [street for street in metro.STREETS
                       if street["points"][0][0] == street["points"][1][0]]
        self.assertEqual(len(north_south), 6)
        self.assertTrue(all(street["points"][0][1] == 486.0
                            for street in north_south))
        crown = next(street for street in metro.STREETS
                     if street["name"] == "Crown Boulevard")
        self.assertGreater(crown["points"][-1][0], metro.EXPRESSWAY_X)

    def test_highway_and_ramps_are_continuous(self):
        points = metro.expressway_points()
        self.assertLessEqual(max(math.dist(a, b) for a, b in zip(points, points[1:])),
                             3.01)
        self.assertEqual(len(metro.RAMPS), 4)
        for ramp in metro.RAMPS:
            self.assertEqual(len(ramp["points"]), 4)
            if "off" in ramp["name"]:
                self.assertGreater(ramp["points"][0][2],
                                   ramp["points"][-1][2])
            else:
                self.assertLess(ramp["points"][0][2],
                                ramp["points"][-1][2])


if __name__ == "__main__":
    unittest.main()
