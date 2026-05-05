"""
Tests for the RegulationService (CASA algorithm).
"""
import pytest
from datetime import datetime, timezone, timedelta
from ddfn_v2.services.regulation_service import RegulationService
from ddfn_v2.eng.trajectories import FlightTrajectory, SectorEntry


class TestRegulationService:
    """Test the CASA slot allocation algorithm."""

    def test_run_casa_basic_fpfs(self):
        """Test basic first-planned-first-served slot allocation."""
        # Create mock flights with different ETOs
        flt1 = FlightTrajectory(
            flight_id="TEST001",
            origin="EDDF",
            destination="LEMD",
            departure_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            cruise_fl=350,
            tas_kt=450,
            route=[
                SectorEntry(sector_id="SEC1", estimated_time_over=datetime(2026, 5, 4, 12, 30, tzinfo=timezone.utc)),
            ]
        )
        flt2 = FlightTrajectory(
            flight_id="TEST002",
            origin="EDDF",
            destination="LEMD",
            departure_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            cruise_fl=350,
            tas_kt=450,
            route=[
                SectorEntry(sector_id="SEC1", estimated_time_over=datetime(2026, 5, 4, 12, 35, tzinfo=timezone.utc)),
            ]
        )

        slots = RegulationService.run_casa(
            sector_id="SEC1",
            start_dt=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 5, 4, 14, 0, tzinfo=timezone.utc),
            capacity_per_hour=10,
            affected_flights=[flt1, flt2]
        )

        assert len(slots) == 2
        # First flight should keep its original slot (no delay)
        assert slots[0].flight_id == "TEST001"
        assert slots[0].delay == 0
        # Second flight: ETO=12:35, next slot after first (12:30 + 6min=12:36)
        # Delay = 12:36 - 12:35 = 1 minute
        assert slots[1].flight_id == "TEST002"
        assert slots[1].delay == 1

    def test_run_casa_total_closure(self):
        """Test CASA when capacity is zero (total closure)."""
        flt = FlightTrajectory(
            flight_id="TEST003",
            origin="EDDF",
            destination="LEMD",
            departure_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            cruise_fl=350,
            tas_kt=450,
            route=[
                SectorEntry(sector_id="SEC1", estimated_time_over=datetime(2026, 5, 4, 12, 30, tzinfo=timezone.utc)),
            ]
        )

        end_time = datetime(2026, 5, 4, 14, 0, tzinfo=timezone.utc)
        slots = RegulationService.run_casa(
            sector_id="SEC1",
            start_dt=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            end_dt=end_time,
            capacity_per_hour=0,
            affected_flights=[flt]
        )

        assert len(slots) == 1
        # Flight should be pushed to the end of the closure window
        assert slots[0].delay > 0
        # CTOT should be at or after end_time, not departure_time + delay
        ctot = datetime.fromisoformat(slots[0].ctot)
        assert ctot >= end_time

    def test_run_casa_ctot_uses_assigned_slot(self):
        """
        Regression test: CTOT should be based on assigned_slot, not departure_time + delay.
        This ensures in-flight aircraft get correct CTOTs.
        """
        # Flight that departed 2 hours ago and is now in flight
        departure_time = datetime(2026, 5, 4, 10, 0, tzinfo=timezone.utc)
        eto = datetime(2026, 5, 4, 12, 30, tzinfo=timezone.utc)  # Current time ~12:00

        flt = FlightTrajectory(
            flight_id="TEST004",
            origin="EDDF",
            destination="LEMD",
            departure_time=departure_time,
            cruise_fl=350,
            tas_kt=450,
            route=[
                SectorEntry(sector_id="SEC1", estimated_time_over=eto),
            ]
        )

        slots = RegulationService.run_casa(
            sector_id="SEC1",
            start_dt=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 5, 4, 14, 0, tzinfo=timezone.utc),
            capacity_per_hour=10,
            affected_flights=[flt]
        )

        assert len(slots) == 1
        # CTOT should be ~12:30 (the assigned slot), NOT 10:00 + small_delay
        ctot = datetime.fromisoformat(slots[0].ctot)
        # CTOT should be close to ETO (within slot interval)
        assert ctot >= eto
        # Critical: CTOT should NOT be near departure_time
        assert ctot > departure_time + timedelta(hours=2)

    def test_run_casa_empty_flights(self):
        """Test CASA with no affected flights."""
        slots = RegulationService.run_casa(
            sector_id="SEC1",
            start_dt=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 5, 4, 14, 0, tzinfo=timezone.utc),
            capacity_per_hour=10,
            affected_flights=[]
        )
        assert slots == []

    def test_identify_participating_nodes(self):
        """Test node identification for consensus."""
        flt1 = FlightTrajectory(
            flight_id="DLH001",
            origin="EDDF",
            destination="LEMD",
            departure_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            cruise_fl=350,
            tas_kt=450,
            route=[SectorEntry(sector_id="SEC1", estimated_time_over=datetime.now(timezone.utc))]
        )
        flt2 = FlightTrajectory(
            flight_id="AFR002",
            origin="LFPG",
            destination="LEMD",
            departure_time=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
            cruise_fl=350,
            tas_kt=450,
            route=[SectorEntry(sector_id="SEC1", estimated_time_over=datetime.now(timezone.utc))]
        )

        nodes = RegulationService.identify_participating_nodes([flt1, flt2], "FMP_LOCAL")

        assert "FMP_LOCAL" in nodes
        assert "EDDF_AIRPORT" in nodes
        assert "LFPG_AIRPORT" in nodes
