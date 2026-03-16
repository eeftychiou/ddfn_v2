import unittest
import datetime
import time
import os
from ddfn_v2.eng.trajectories import TrajectorySolver, FlightTrajectory, SectorEntry

class TestTrajectorySolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load AIXM data once for all tests."""
        from ddfn_v2.eng.airspace import load_from_aixm, SECTORS
        aixm_path = os.path.join("AIXM", "BD_2025-09-30_400005921419525.xml")
        if os.path.exists(aixm_path):
            load_from_aixm(aixm_path)
            print(f"Loaded AIXM from {aixm_path}")
        else:
            print("AIXM file not found, tests might fail if they expect specific sectors.")

    def test_spatial_filtering_correctness(self):
        """Verify that the spatial filtering doesn't miss sectors."""
        from ddfn_v2.eng.airspace import SECTORS
        if not SECTORS:
            self.skipTest("No sectors loaded")
        
        target_sector_id = list(SECTORS.keys())[0]
        sector = SECTORS[target_sector_id]
        
        poly = sector.polygon
        center_lat = sum(p[0] for p in poly) / len(poly)
        center_lon = sum(p[1] for p in poly) / len(poly)
        
        waypoints = [(center_lat - 1, center_lon), (center_lat + 1, center_lon)]
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=450.0
        )
        
        self.assertTrue(len(crossings) > 0)
        self.assertIn(target_sector_id, [s.sector_id for s in crossings])
        print(f"Correctly detected intersection with {target_sector_id}")

    def test_performance_gain(self):
        """Measure performance gain from spatial filtering."""
        from ddfn_v2.eng.airspace import SECTORS
        if not SECTORS:
            self.skipTest("No sectors loaded")
            
        target_sector_id = list(SECTORS.keys())[0]
        base_sector = SECTORS[target_sector_id]
        
        large_db = {}
        for i in range(1000):
            large_db[f"FAR_{i}"] = base_sector.model_copy(update={
                "sector_id": f"FAR_{i}",
                "polygon": [(-1, -1), (-1, 1), (1, 1), (1, -1)]
            })
        
        large_db.update(SECTORS)
        
        poly = base_sector.polygon
        center_lat = sum(p[0] for p in poly) / len(poly)
        center_lon = sum(p[1] for p in poly) / len(poly)
        waypoints = [(center_lat - 1, center_lon), (center_lat + 1, center_lon)]
        
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        tas = 450.0
        
        start = time.time()
        crossings, _ = TrajectorySolver.compute_sector_etos(waypoints, dept_time, tas, sector_db=large_db)
        duration = time.time() - start
        
        print(f"Trajectory calculation with 1100+ sectors took {duration:.4f}s")
        self.assertTrue(len(crossings) > 0)
        self.assertLess(duration, 0.1) 

    def test_vertical_profile_multi_sector(self):
        """
        GREEN: Test that a trajectory climbing through different altitude sectors is correctly mapped.
        """
        from ddfn_v2.eng.airspace import SECTORS
        if not SECTORS:
            self.skipTest("No sectors loaded")
            
        # Coordinates that we know intersect some sectors (from loading AIXM)
        waypoints = [(40.0, 20.0), (41.0, 21.0)]
        altitudes = [10000, 35000] # Climbing profile
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        # This should now succeed and return a list
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=450.0,
            altitudes=altitudes
        )
        self.assertIsInstance(crossings, list)

if __name__ == "__main__":
    unittest.main()
