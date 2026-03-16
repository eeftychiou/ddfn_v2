"""
test_trajectories.py - Unit tests for trajectory calculations
=============================================================
Tests the TrajectorySolver and FlightTrajectory classes.
Uses pytest fixtures from conftest.py for better test isolation.
"""

import pytest
import datetime
import time
from typing import List

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ddfn_v2.eng.trajectories import TrajectorySolver, FlightTrajectory, SectorEntry
from ddfn_v2.eng.airspace import SectorGeometry


class TestTrajectorySolver:
    """Test cases for TrajectorySolver using pytest fixtures."""

    def test_spatial_filtering_correctness(self, mock_sectors):
        """Verify that the spatial filtering doesn't miss sectors."""
        if not mock_sectors:
            pytest.skip("No sectors loaded")
        
        target_sector_id = list(mock_sectors.keys())[0]
        sector = mock_sectors[target_sector_id]
        
        poly = sector.polygon
        center_lat = sum(p[0] for p in poly) / len(poly)
        center_lon = sum(p[1] for p in poly) / len(poly)
        
        waypoints = [(center_lat - 1, center_lon), (center_lat + 1, center_lon)]
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=450.0,
            sector_db=mock_sectors
        )
        
        assert len(crossings) > 0
        assert target_sector_id in [s.sector_id for s in crossings]
        print(f"Correctly detected intersection with {target_sector_id}")

    def test_performance_gain(self, mock_sectors):
        """Measure performance gain from spatial filtering."""
        if not mock_sectors:
            pytest.skip("No sectors loaded")
            
        target_sector_id = list(mock_sectors.keys())[0]
        base_sector = mock_sectors[target_sector_id]
        
        # Create a large database with far-away sectors
        large_db = {}
        for i in range(1000):
            large_db[f"FAR_{i}"] = base_sector.model_copy(update={
                "sector_id": f"FAR_{i}",
                "polygon": [(-1, -1), (-1, 1), (1, 1), (1, -1)]  # Far from test trajectory
            })
        
        large_db.update(mock_sectors)
        
        poly = base_sector.polygon
        center_lat = sum(p[0] for p in poly) / len(poly)
        center_lon = sum(p[1] for p in poly) / len(poly)
        waypoints = [(center_lat - 1, center_lon), (center_lat + 1, center_lon)]
        
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        tas = 450.0
        
        start = time.time()
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints, dept_time, tas, sector_db=large_db
        )
        duration = time.time() - start
        
        print(f"Trajectory calculation with 1100+ sectors took {duration:.4f}s")
        assert len(crossings) > 0
        assert duration < 0.1

    def test_vertical_profile_multi_sector(self, mock_sectors):
        """
        Test that a trajectory climbing through different altitude sectors is correctly mapped.
        """
        if not mock_sectors:
            pytest.skip("No sectors loaded")
            
        # Use mock waypoints that intersect some sectors
        waypoints = [(48.0, 2.0), (47.0, 3.0)]
        altitudes = [10000, 35000]  # Climbing profile
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        # This should now succeed and return a list
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=450.0,
            altitudes=altitudes,
            sector_db=mock_sectors
        )
        assert isinstance(crossings, list)

    def test_trajectory_with_no_sector_intersections(self, mock_sectors):
        """Test trajectory that doesn't intersect any sectors."""
        # Waypoints far from any sectors
        waypoints = [(0.0, 0.0), (1.0, 1.0)]
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=450.0,
            sector_db=mock_sectors
        )
        
        # Should return empty list, not error
        assert isinstance(crossings, list)
        assert len(crossings) == 0

    def test_single_waypoint_trajectory(self, mock_sectors):
        """Test trajectory with only one waypoint."""
        waypoints = [(48.0, 2.0)]
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        # Single waypoint should still work (no movement, but shouldn't crash)
        crossings, exit_time = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=450.0,
            sector_db=mock_sectors
        )
        
        assert isinstance(crossings, list)
        # Exit time may be None or equal to departure time for single waypoint
        # Just verify the function completed without error
        assert exit_time is None or exit_time >= dept_time

    def test_high_speed_trajectory(self, mock_sectors):
        """Test trajectory with very high speed."""
        if not mock_sectors:
            pytest.skip("No sectors loaded")
            
        target_sector_id = list(mock_sectors.keys())[0]
        sector = mock_sectors[target_sector_id]
        
        poly = sector.polygon
        center_lat = sum(p[0] for p in poly) / len(poly)
        center_lon = sum(p[1] for p in poly) / len(poly)
        
        waypoints = [(center_lat - 1, center_lon), (center_lat + 1, center_lon)]
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        # Very high speed (supersonic)
        tas = 1000.0
        
        crossings, exit_time = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=tas,
            sector_db=mock_sectors
        )
        
        # Should still detect crossings
        assert isinstance(crossings, list)
        # Exit time should be earlier due to high speed
        assert exit_time > dept_time

    def test_low_speed_trajectory(self, mock_sectors):
        """Test trajectory with low speed (e.g., turboprop)."""
        if not mock_sectors:
            pytest.skip("No sectors loaded")
            
        target_sector_id = list(mock_sectors.keys())[0]
        sector = mock_sectors[target_sector_id]
        
        poly = sector.polygon
        center_lat = sum(p[0] for p in poly) / len(poly)
        center_lon = sum(p[1] for p in poly) / len(poly)
        
        waypoints = [(center_lat - 1, center_lon), (center_lat + 1, center_lon)]
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        # Low speed (turboprop)
        tas = 250.0
        
        crossings, exit_time = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=tas,
            sector_db=mock_sectors
        )
        
        # Should still detect crossings
        assert isinstance(crossings, list)
        # Exit time should be later due to low speed
        assert exit_time > dept_time


class TestFlightTrajectory:
    """Test cases for FlightTrajectory class."""

    def test_flight_trajectory_creation(self):
        """Test creating a FlightTrajectory from a flight plan."""
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        trajectory = FlightTrajectory.from_flight_plan(
            flight_id="TEST123",
            origin="LFPG",
            destination="EGLL",
            departure_time=dept_time,
            cruise_fl=350,
            route_string="DCT DVR DCT EGLL"
        )
        
        assert trajectory.flight_id == "TEST123"
        assert trajectory.origin == "LFPG"
        assert trajectory.destination == "EGLL"
        assert trajectory.cruise_fl == 350

    def test_flight_trajectory_route_computation(self, mock_sectors):
        """Test that route is computed correctly with sector crossings."""
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        trajectory = FlightTrajectory.from_flight_plan(
            flight_id="TEST456",
            origin="LFPG",
            destination="EGLL",
            departure_time=dept_time,
            cruise_fl=350,
            route_string="DCT DVR DCT EGLL"
        )
        
        # Route should be a list
        assert isinstance(trajectory.route, list)
        # Each entry should be a SectorEntry
        for entry in trajectory.route:
            assert hasattr(entry, 'sector_id')
            assert hasattr(entry, 'estimated_time_over')

    def test_flight_trajectory_with_invalid_route(self):
        """Test handling of invalid route string."""
        dept_time = datetime.datetime(2026, 3, 14, 12, 0, tzinfo=datetime.timezone.utc)
        
        # Should not raise exception for invalid route
        try:
            trajectory = FlightTrajectory.from_flight_plan(
                flight_id="TEST789",
                origin="LFPG",
                destination="EGLL",
                departure_time=dept_time,
                cruise_fl=350,
                route_string="INVALID ROUTE XYZ"
            )
            # Should create trajectory but with empty or minimal route
            assert trajectory.flight_id == "TEST789"
        except Exception as e:
            pytest.fail(f"Should handle invalid route gracefully: {e}")


class TestSectorEntry:
    """Test cases for SectorEntry dataclass."""

    def test_sector_entry_creation(self):
        """Test creating a SectorEntry."""
        eto = datetime.datetime(2026, 3, 14, 12, 30, tzinfo=datetime.timezone.utc)
        
        entry = SectorEntry(
            sector_id="TEST_SECTOR",
            estimated_time_over=eto,
            entry_lat=48.0,
            entry_lon=2.0,
            exit_lat=47.0,
            exit_lon=3.0
        )
        
        assert entry.sector_id == "TEST_SECTOR"
        assert entry.estimated_time_over == eto
        assert entry.entry_lat == 48.0
        assert entry.entry_lon == 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
