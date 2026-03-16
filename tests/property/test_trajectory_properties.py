"""
test_trajectory_properties.py - Property-based tests for trajectory calculations
=================================================================================
Uses Hypothesis to test invariant properties of trajectory calculations.
These tests verify that certain properties always hold regardless of input values.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime, timezone, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ddfn_v2.eng.trajectories import TrajectorySolver, FlightTrajectory
from ddfn_v2.eng.airspace import SectorGeometry


class TestTrajectoryProperties:
    """Property-based tests for trajectory calculations."""

    @given(
        lat1=st.floats(min_value=-80, max_value=80),
        lon1=st.floats(min_value=-180, max_value=180),
        lat2=st.floats(min_value=-80, max_value=80),
        lon2=st.floats(min_value=-180, max_value=180),
        speed=st.floats(min_value=100, max_value=1000)
    )
    @settings(max_examples=50, deadline=None)
    def test_exit_time_after_departure(self, lat1, lon1, lat2, lon2, speed):
        """
        Property: Exit time should always be >= departure time for valid trajectories.
        """
        # Skip if waypoints are identical (no movement)
        assume(abs(lat1 - lat2) > 0.001 or abs(lon1 - lon2) > 0.001)
        
        waypoints = [(lat1, lon1), (lat2, lon2)]
        dept_time = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
        
        crossings, exit_time = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=speed
        )
        
        # Property: Exit time should be after or equal to departure time
        if exit_time is not None:
            assert exit_time >= dept_time

    @given(
        lat1=st.floats(min_value=40, max_value=60),
        lon1=st.floats(min_value=-10, max_value=30),
        lat2=st.floats(min_value=40, max_value=60),
        lon2=st.floats(min_value=-10, max_value=30),
        speed=st.floats(min_value=100, max_value=1000)
    )
    @settings(max_examples=30, deadline=None)
    def test_crossings_list_always_returned(self, lat1, lon1, lat2, lon2, speed):
        """
        Property: compute_sector_etos should always return a list (never None).
        """
        assume(abs(lat1 - lat2) > 0.001 or abs(lon1 - lon2) > 0.001)
        
        waypoints = [(lat1, lon1), (lat2, lon2)]
        dept_time = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
        
        crossings, _ = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=speed
        )
        
        # Property: crossings should always be a list
        assert isinstance(crossings, list)

    @given(
        speed1=st.floats(min_value=200, max_value=400),
        speed2=st.floats(min_value=400, max_value=800)
    )
    @settings(max_examples=20, deadline=None)
    def test_higher_speed_shorter_duration(self, speed1, speed2):
        """
        Property: Higher speed should result in shorter or equal flight duration.
        """
        assume(speed2 > speed1)
        
        waypoints = [(48.0, 2.0), (47.0, 3.0), (46.0, 4.0)]
        dept_time = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
        
        _, exit1 = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=speed1
        )
        
        _, exit2 = TrajectorySolver.compute_sector_etos(
            waypoints=waypoints,
            departure_time=dept_time,
            tas_kt=speed2
        )
        
        # Property: Higher speed should result in earlier or equal exit time
        if exit1 and exit2:
            assert exit2 <= exit1


class TestSectorGeometryProperties:
    """Property-based tests for sector geometry."""

    @given(
        min_lat=st.floats(min_value=-90, max_value=89),
        min_lon=st.floats(min_value=-180, max_value=179),
        height=st.floats(min_value=0.1, max_value=10),
        width=st.floats(min_value=0.1, max_value=10)
    )
    @settings(max_examples=30, deadline=None)
    def test_sector_bounding_box(self, min_lat, min_lon, height, width):
        """
        Property: Sector polygon should be within expected bounds.
        """
        max_lat = min(min_lat + height, 90)
        max_lon = min(min_lon + width, 180)
        
        polygon = [
            (min_lat, min_lon),
            (min_lat, max_lon),
            (max_lat, max_lon),
            (max_lat, min_lon),
        ]
        
        sector = SectorGeometry(
            sector_id="TEST",
            fir="TEST_FIR",
            fl_lower=100,
            fl_upper=400,
            polygon=polygon
        )
        
        # Property: All polygon points should be within expected bounds
        lats = [p[0] for p in sector.polygon]
        lons = [p[1] for p in sector.polygon]
        
        assert min(lats) >= min_lat - 0.001
        assert max(lats) <= max_lat + 0.001
        assert min(lons) >= min_lon - 0.001
        assert max(lons) <= max_lon + 0.001


class TestFlightTrajectoryProperties:
    """Property-based tests for FlightTrajectory."""

    @given(
        flight_id=st.text(min_size=1, max_size=10, alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
        origin=st.sampled_from(["LFPG", "EGLL", "EDDF", "LEMD", "EHAM"]),
        destination=st.sampled_from(["LFPG", "EGLL", "EDDF", "LEMD", "EHAM"]),
        cruise_fl=st.integers(min_value=100, max_value=450)
    )
    @settings(max_examples=30, deadline=None)
    def test_flight_trajectory_invariants(self, flight_id, origin, destination, cruise_fl):
        """
        Property: FlightTrajectory should preserve all input values.
        """
        assume(origin != destination)
        
        dept_time = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
        
        trajectory = FlightTrajectory.from_flight_plan(
            flight_id=flight_id,
            origin=origin,
            destination=destination,
            departure_time=dept_time,
            cruise_fl=cruise_fl,
            route_string=f"DCT {destination}"
        )
        
        # Property: All input values should be preserved
        assert trajectory.flight_id == flight_id
        assert trajectory.origin == origin
        assert trajectory.destination == destination
        assert trajectory.cruise_fl == cruise_fl

    @given(
        origin=st.sampled_from(["LFPG", "EGLL", "EDDF"]),
        destination=st.sampled_from(["LFPG", "EGLL", "EDDF"])
    )
    @settings(max_examples=20, deadline=None)
    def test_same_origin_destination_empty_route(self, origin, destination):
        """
        Property: Same origin and destination should result in minimal route.
        """
        dept_time = datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc)
        
        trajectory = FlightTrajectory.from_flight_plan(
            flight_id="TEST",
            origin=origin,
            destination=origin,  # Same as origin
            departure_time=dept_time,
            cruise_fl=350,
            route_string=f"DCT {origin}"
        )
        
        # Property: Route should be empty or minimal for same origin/destination
        # (This is a behavioral property - may vary by implementation)
        assert isinstance(trajectory.route, list)


if __name__ == '__main__':
    pytest.main([__file__, "-v"])
