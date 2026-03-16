"""
test_trajectory_performance.py - Performance benchmarks for trajectory calculations
===================================================================================
Tests the performance of trajectory computation with varying loads.
"""

import unittest
import time
import tempfile
import os
from datetime import datetime, timezone, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ddfn_v2.eng.trajectories import TrajectorySolver, FlightTrajectory
from ddfn_v2.eng.airspace import SectorGeometry


class TestTrajectoryPerformance(unittest.TestCase):
    """Performance benchmarks for trajectory calculations."""

    def setUp(self):
        """Set up test fixtures."""
        self.dept_time = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        self.waypoints = [(48.0, 2.0), (47.0, 3.0), (46.0, 4.0)]

    def _create_sector_db(self, count: int) -> dict:
        """Create a sector database with the specified number of sectors."""
        sectors = {}
        for i in range(count):
            # Create sectors in a grid pattern
            lat_offset = (i // 10) * 2.0
            lon_offset = (i % 10) * 2.0
            sectors[f"SEC_{i:04d}"] = SectorGeometry(
                sector_id=f"SEC_{i:04d}",
                fir="TEST",
                fl_lower=245,
                fl_upper=660,
                polygon=[
                    (40.0 + lat_offset, 0.0 + lon_offset),
                    (40.0 + lat_offset, 1.0 + lon_offset),
                    (41.0 + lat_offset, 1.0 + lon_offset),
                    (41.0 + lat_offset, 0.0 + lon_offset),
                ]
            )
        return sectors

    def test_trajectory_calculation_100_sectors(self):
        """Benchmark trajectory calculation with 100 sectors."""
        sector_db = self._create_sector_db(100)
        
        start = time.time()
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=self.waypoints,
            departure_time=self.dept_time,
            tas_kt=450.0,
            sector_db=sector_db
        )
        duration = time.time() - start
        
        print(f"\nTrajectory calculation with 100 sectors: {duration:.4f}s")
        self.assertLess(duration, 1.0, "Should complete in less than 1 second")

    def test_trajectory_calculation_500_sectors(self):
        """Benchmark trajectory calculation with 500 sectors."""
        sector_db = self._create_sector_db(500)
        
        start = time.time()
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=self.waypoints,
            departure_time=self.dept_time,
            tas_kt=450.0,
            sector_db=sector_db
        )
        duration = time.time() - start
        
        print(f"\nTrajectory calculation with 500 sectors: {duration:.4f}s")
        self.assertLess(duration, 2.0, "Should complete in less than 2 seconds")

    def test_trajectory_calculation_1000_sectors(self):
        """Benchmark trajectory calculation with 1000 sectors."""
        sector_db = self._create_sector_db(1000)
        
        start = time.time()
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=self.waypoints,
            departure_time=self.dept_time,
            tas_kt=450.0,
            sector_db=sector_db
        )
        duration = time.time() - start
        
        print(f"\nTrajectory calculation with 1000 sectors: {duration:.4f}s")
        self.assertLess(duration, 5.0, "Should complete in less than 5 seconds")

    def test_spatial_filtering_effectiveness(self):
        """Verify that spatial filtering improves performance."""
        # Create sectors far away from the trajectory
        far_sectors = {}
        for i in range(500):
            # These sectors are far from the trajectory (Europe vs trajectory)
            far_sectors[f"FAR_{i:04d}"] = SectorGeometry(
                sector_id=f"FAR_{i:04d}",
                fir="FAR",
                fl_lower=245,
                fl_upper=660,
                polygon=[
                    (-30.0, 120.0),  # Australia area
                    (-30.0, 121.0),
                    (-29.0, 121.0),
                    (-29.0, 120.0),
                ]
            )
        
        # Add a few sectors that actually intersect
        near_sectors = self._create_sector_db(10)
        sector_db = {**far_sectors, **near_sectors}
        
        start = time.time()
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=self.waypoints,
            departure_time=self.dept_time,
            tas_kt=450.0,
            sector_db=sector_db
        )
        duration = time.time() - start
        
        print(f"\nSpatial filtering with 510 sectors (500 far, 10 near): {duration:.4f}s")
        print(f"Detected {len(crossings)} crossings")
        
        # Should be fast due to spatial filtering
        self.assertLess(duration, 1.0, "Spatial filtering should make this fast")
        # Should only find crossings in the 10 nearby sectors
        self.assertLessEqual(len(crossings), 10)

    def test_batch_flight_processing(self):
        """Test processing multiple flights in batch."""
        sector_db = self._create_sector_db(100)
        num_flights = 50
        
        start = time.time()
        for i in range(num_flights):
            waypoints = [
                (48.0 + i * 0.01, 2.0 + i * 0.01),
                (47.0 + i * 0.01, 3.0 + i * 0.01),
            ]
            TrajectorySolver.compute_sector_etos(
                waypoints=waypoints,
                departure_time=self.dept_time,
                tas_kt=450.0,
                sector_db=sector_db
            )
        duration = time.time() - start
        
        avg_time = duration / num_flights
        print(f"\nBatch processing {num_flights} flights: {duration:.4f}s total, {avg_time:.4f}s avg")
        self.assertLess(avg_time, 0.1, "Average time per flight should be < 100ms")


class TestFlightDataProcessingSystemPerformance(unittest.TestCase):
    """Performance tests for FDPS operations."""

    def test_fdps_add_many_flights(self):
        """Test adding many flights to FDPS."""
        from ddfn_v2.eng.trajectories import FlightDataProcessingSystem
        
        fdps = FlightDataProcessingSystem()
        dept_time = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        
        # Create 100 flights
        flights = []
        for i in range(100):
            traj = FlightTrajectory.from_flight_plan(
                flight_id=f"TEST{i:04d}",
                origin="LFPG",
                destination="EGLL",
                departure_time=dept_time,
                cruise_fl=350,
                route_string="DCT DVR DCT EGLL"
            )
            flights.append(traj)
        
        start = time.time()
        for flight in flights:
            fdps.add_flight(flight)
        duration = time.time() - start
        
        print(f"\nAdding 100 flights to FDPS: {duration:.4f}s")
        self.assertEqual(len(fdps.flights), 100)
        self.assertLess(duration, 1.0)

    def test_fdps_query_performance(self):
        """Test querying flights within sector."""
        from ddfn_v2.eng.trajectories import FlightDataProcessingSystem
        
        fdps = FlightDataProcessingSystem()
        dept_time = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
        
        # Add 50 flights
        for i in range(50):
            traj = FlightTrajectory.from_flight_plan(
                flight_id=f"TEST{i:04d}",
                origin="LFPG",
                destination="EGLL",
                departure_time=dept_time,
                cruise_fl=350,
                route_string="DCT DVR DCT EGLL"
            )
            fdps.add_flight(traj)
        
        # Query flights in a sector
        window_end = dept_time + timedelta(hours=2)
        start = time.time()
        results = fdps.predict_flights_in_sector("LFFF1A", dept_time, window_end)
        duration = time.time() - start
        
        print(f"\nQuerying flights in sector (50 flights): {duration:.4f}s")
        self.assertLess(duration, 0.5)


if __name__ == '__main__':
    unittest.main()
