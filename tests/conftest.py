"""
conftest.py - Shared pytest fixtures for DDFN v2 tests
======================================================
Provides mock data and fixtures for isolated unit testing.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, List, Tuple

# Import after path setup
import sys
import os

# Add src directory to path for importing ddfn_v2
src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from ddfn_v2.eng.airspace import Waypoint, SectorGeometry, WAYPOINTS, SECTORS
from ddfn_v2.eng.trajectories import FlightTrajectory, FlightDataProcessingSystem
from ddfn_v2.core.models import SectorCapacity


@pytest.fixture
def mock_waypoints() -> Dict[str, Waypoint]:
    """Returns a dictionary of mock waypoints for testing."""
    return {
        "LFPG": Waypoint(ident="LFPG", lat=49.0128, lon=2.5500, type="AIRPORT", name="Charles de Gaulle"),
        "EGLL": Waypoint(ident="EGLL", lat=51.4700, lon=-0.4543, type="AIRPORT", name="Heathrow"),
        "EDDF": Waypoint(ident="EDDF", lat=50.0379, lon=8.5622, type="AIRPORT", name="Frankfurt"),
        "LEMD": Waypoint(ident="LEMD", lat=40.4983, lon=-3.5676, type="AIRPORT", name="Madrid Barajas"),
        "WPT1": Waypoint(ident="WPT1", lat=48.0, lon=2.0, type="ENRT"),
        "WPT2": Waypoint(ident="WPT2", lat=47.0, lon=3.0, type="ENRT"),
        "WPT3": Waypoint(ident="WPT3", lat=46.0, lon=4.0, type="ENRT"),
        "DVR": Waypoint(ident="DVR", lat=51.1000, lon=1.3000, type="ENRT", name="Dover"),
        "PODIP": Waypoint(ident="PODIP", lat=50.5000, lon=9.0000, type="ENRT"),
        "VESAN": Waypoint(ident="VESAN", lat=49.5000, lon=5.0000, type="ENRT"),
    }


@pytest.fixture
def mock_sectors() -> Dict[str, SectorGeometry]:
    """Returns a dictionary of mock sectors for testing."""
    return {
        "LFFF1A": SectorGeometry(
            sector_id="LFFF1A",
            fir="LFFF",
            fl_lower=245,
            fl_upper=660,
            polygon=[(48.5, 1.5), (48.5, 3.5), (47.5, 3.5), (47.5, 1.5)]
        ),
        "LFFF1B": SectorGeometry(
            sector_id="LFFF1B",
            fir="LFFF",
            fl_lower=245,
            fl_upper=660,
            polygon=[(47.5, 1.5), (47.5, 3.5), (46.5, 3.5), (46.5, 1.5)]
        ),
        "EGTT1C": SectorGeometry(
            sector_id="EGTT1C",
            fir="EGTT",
            fl_lower=245,
            fl_upper=660,
            polygon=[(51.5, -1.0), (51.5, 1.0), (50.5, 1.0), (50.5, -1.0)]
        ),
        "EDDD1A": SectorGeometry(
            sector_id="EDDD1A",
            fir="EDDD",
            fl_lower=245,
            fl_upper=660,
            polygon=[(51.0, 7.0), (51.0, 10.0), (49.0, 10.0), (49.0, 7.0)]
        ),
    }


@pytest.fixture
def mock_sector_capacities() -> List[SectorCapacity]:
    """Returns a list of mock SectorCapacity objects."""
    return [
        SectorCapacity(
            sector_id="LFFF1A",
            configuration="NORTH",
            declared_capacity_per_hour=40,
            current_demand_per_hour=0,
            status="GREEN",
            fl_lower=245,
            fl_upper=660
        ),
        SectorCapacity(
            sector_id="LFFF1B",
            configuration="SOUTH",
            declared_capacity_per_hour=35,
            current_demand_per_hour=0,
            status="GREEN",
            fl_lower=245,
            fl_upper=660
        ),
        SectorCapacity(
            sector_id="EGTT1C",
            configuration="DEFAULT",
            declared_capacity_per_hour=45,
            current_demand_per_hour=0,
            status="GREEN",
            fl_lower=245,
            fl_upper=660
        ),
    ]


@pytest.fixture
def sample_flight_trajectory(mock_waypoints) -> FlightTrajectory:
    """Returns a sample flight trajectory for testing."""
    dept_time = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
    return FlightTrajectory.from_flight_plan(
        flight_id="TEST001",
        origin="LFPG",
        destination="EGLL",
        departure_time=dept_time,
        cruise_fl=350,
        route_string="WPT1 WPT2 DVR",
        waypoint_db=mock_waypoints
    )


@pytest.fixture
def mock_network_client():
    """Returns a mocked NetworkClient for isolated testing."""
    client = MagicMock()
    client.publish = AsyncMock(return_value=None)
    client.subscribe = AsyncMock(return_value=None)
    client.connect = AsyncMock(return_value=None)
    client.node_id = "TEST_NODE"
    client.broker_url = "ws://localhost:8001/ws"
    return client


@pytest.fixture
def mock_broker():
    """Returns a mocked broker for testing."""
    broker = MagicMock()
    broker.subscribers = {}
    broker.active_nodes = {}
    return broker


@pytest.fixture
def isolated_fdps():
    """Returns an isolated FlightDataProcessingSystem for testing."""
    return FlightDataProcessingSystem()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_global_state(request):
    """Reset global state before each test to ensure isolation, except for integration tests."""
    if "integration" in request.node.nodeid:
        yield
        return
    # Save original state
    original_waypoints = WAYPOINTS.copy()
    original_sectors = SECTORS.copy()
    
    # Clear global state
    WAYPOINTS.clear()
    SECTORS.clear()
    
    yield
    
    # Restore original state
    WAYPOINTS.update(original_waypoints)
    SECTORS.update(original_sectors)


@pytest.fixture
def sample_flight_plan():
    """Returns a sample flight plan dictionary."""
    return {
        "flight_id": "AFR123",
        "origin": "LFPG",
        "destination": "EGLL",
        "route_string": "DCT WPT1 DCT WPT2 DCT DVR DCT EGLL",
        "cruise_fl": 350,
        "departure_time": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def sample_capacity_warning():
    """Returns a sample capacity constraint warning."""
    return {
        "message_type": "CONSTRAINT_WARNING_TRIGGER",
        "warning_id": "WARN_TEST_001",
        "originating_node": "LFFF",
        "target_nodes": ["LFPG_AIRPORT"],
        "constrained_sector_id": "LFFF1A",
        "affected_time_window": {
            "start": datetime.now(timezone.utc).isoformat(),
            "end": (datetime.now(timezone.utc).replace(hour=23, minute=59)).isoformat()
        },
        "required_flow_reduction": {
            "metric": "FLIGHTS_PER_HOUR",
            "amount_to_reduce": 10
        },
        "affected_flights_pool": ["AFR123", "AFR124"]
    }


@pytest.fixture
def mock_aixm_xml():
    """Returns a minimal valid AIXM XML string for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
    <AIXM-Snapshot xmlns="http://www.aixm.aero/schema/4.5">
        <Ase>
            <AseUid mid="ASE001">
                <codeId>TEST01</codeId>
                <codeType>SECTOR</codeType>
            </AseUid>
            <txtName>Test Sector 1</txtName>
            <valDistVerLower>245</valDistVerLower>
            <valDistVerUpper>660</valDistVerUpper>
        </Ase>
        <Abd>
            <AbdUid>
                <AseUid mid="ASE001">
                    <codeId>TEST01</codeId>
                </AseUid>
            </AbdUid>
            <Avx>
                <geoLat>481200N</geoLat>
                <geoLong>0023000E</geoLong>
            </Avx>
            <Avx>
                <geoLat>481200N</geoLat>
                <geoLong>0033000E</geoLong>
            </Avx>
            <Avx>
                <geoLat>471200N</geoLat>
                <geoLong>0033000E</geoLong>
            </Avx>
            <Avx>
                <geoLat>471200N</geoLat>
                <geoLong>0023000E</geoLong>
            </Avx>
        </Abd>
        <Dpn>
            <DpnUid>
                <codeId>WPT001</codeId>
                <geoLat>480000N</geoLat>
                <geoLong>0030000E</geoLong>
            </DpnUid>
            <codeType>ENRT</codeType>
        </Dpn>
        <Ahp>
            <AhpUid>
                <codeId>LFPG</codeId>
            </AhpUid>
            <txtName>Charles de Gaulle</txtName>
            <geoLat>490046N</geoLat>
            <geoLong>0023300E</geoLong>
            <codeIcao>LFPG</codeIcao>
        </Ahp>
    </AIXM-Snapshot>"""
