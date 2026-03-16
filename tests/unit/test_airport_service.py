"""
test_airport_service.py - Unit tests for Airport Node
======================================================
Tests the AirportNode class and its capabilities.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from datetime import datetime, timezone, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ddfn_v2.services.airport_service import AirportNode, AirportStatus
from ddfn_v2.eng.trajectories import FlightDataProcessingSystem, FlightTrajectory
from ddfn_v2.core.models import CapacityConstraintWarning, FlowNegotiationProposal, DistributedFlowConsensus


class TestAirportStatus(unittest.TestCase):
    """Test cases for AirportStatus dataclass."""

    def test_airport_status_initialization(self):
        """Test AirportStatus initialization."""
        status = AirportStatus(
            icao="LFPG",
            aar=30,
            adr=28,
            inbound_demand=25,
            outbound_demand=20
        )
        
        self.assertEqual(status.icao, "LFPG")
        self.assertEqual(status.aar, 30)
        self.assertEqual(status.adr, 28)
        self.assertEqual(status.inbound_demand, 25)
        self.assertEqual(status.outbound_demand, 20)
        self.assertEqual(status.status, "GREEN")

    def test_aar_breach_detection(self):
        """Test AAR breach detection."""
        status = AirportStatus(
            icao="LFPG",
            aar=30,
            adr=28,
            inbound_demand=35,  # Exceeds AAR
            outbound_demand=20
        )
        
        self.assertTrue(status.aar_breach)
        self.assertEqual(status.aar_excess, 5)

    def test_adr_breach_detection(self):
        """Test ADR breach detection."""
        status = AirportStatus(
            icao="LFPG",
            aar=30,
            adr=28,
            inbound_demand=25,
            outbound_demand=35  # Exceeds ADR
        )
        
        self.assertTrue(status.adr_breach)
        self.assertEqual(status.adr_excess, 7)

    def test_no_breach(self):
        """Test when demand is within capacity."""
        status = AirportStatus(
            icao="LFPG",
            aar=30,
            adr=28,
            inbound_demand=25,
            outbound_demand=20
        )
        
        self.assertFalse(status.aar_breach)
        self.assertFalse(status.adr_breach)
        self.assertEqual(status.aar_excess, 0)
        self.assertEqual(status.adr_excess, 0)


class TestAirportNode(unittest.TestCase):
    """Test cases for AirportNode."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_network = MagicMock()
        self.mock_network.publish = AsyncMock(return_value=None)
        self.mock_network.subscribe = AsyncMock(return_value=None)
        
        self.fdps = FlightDataProcessingSystem()
        
        self.airport = AirportNode(
            icao="LFPG",
            network=self.mock_network,
            fdps=self.fdps,
            adjacent_sector="LFFF1A",
            upstream_sector="EGTT1C"
        )

    def test_airport_node_initialization(self):
        """Test AirportNode initialization."""
        self.assertEqual(self.airport.icao, "LFPG")
        self.assertEqual(self.airport.node_id, "LFPG_AIRPORT")
        self.assertEqual(self.airport.adjacent_sector, "LFFF1A")
        self.assertEqual(self.airport.upstream_sector, "EGTT1C")
        self.assertEqual(self.airport.status.icao, "LFPG")

    def test_default_aar_adr_values(self):
        """Test default AAR/ADR values from AIRPORT_DEFAULTS or fallback."""
        # Should use defaults or fallback to 30/28
        self.assertGreaterEqual(self.airport.status.aar, 1)
        self.assertGreaterEqual(self.airport.status.adr, 1)

    def test_status_property_access(self):
        """Test that status properties work correctly."""
        # Set specific values for testing
        self.airport.status.aar = 40
        self.airport.status.adr = 35
        self.airport.status.inbound_demand = 45
        self.airport.status.outbound_demand = 30
        
        self.assertTrue(self.airport.status.aar_breach)
        self.assertFalse(self.airport.status.adr_breach)


class TestAirportNodeAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for AirportNode."""

    async def asyncSetUp(self):
        """Set up async test fixtures."""
        self.mock_network = MagicMock()
        self.mock_network.publish = AsyncMock(return_value=None)
        self.mock_network.subscribe = AsyncMock(return_value=None)
        
        self.fdps = FlightDataProcessingSystem()
        
        self.airport = AirportNode(
            icao="LFPG",
            network=self.mock_network,
            fdps=self.fdps,
            adjacent_sector="LFFF1A",
            upstream_sector="EGTT1C"
        )

    async def test_handle_flight_plan_filed_origin(self):
        """Test handling flight plan for airport as origin."""
        message = {
            "flight_id": "AFR123",
            "origin": "LFPG",
            "destination": "EGLL",
            "route_string": "DCT DVR DCT EGLL",
            "cruise_fl": 350,
            "departure_time": datetime.now(timezone.utc).isoformat()
        }
        
        await self.airport.handle_flight_plan_filed(message)
        
        # Verify flight was added to FDPS
        self.assertIn("AFR123", self.airport.fdps.flights)
        flight = self.airport.fdps.flights["AFR123"]
        self.assertEqual(flight.origin, "LFPG")
        self.assertEqual(flight.destination, "EGLL")

    async def test_handle_flight_plan_filed_destination(self):
        """Test handling flight plan for airport as destination."""
        message = {
            "flight_id": "BAW456",
            "origin": "EGLL",
            "destination": "LFPG",
            "route_string": "DCT DVR DCT LFPG",
            "cruise_fl": 350,
            "departure_time": datetime.now(timezone.utc).isoformat()
        }
        
        await self.airport.handle_flight_plan_filed(message)
        
        # Verify flight was added to FDPS
        self.assertIn("BAW456", self.airport.fdps.flights)

    async def test_handle_flight_plan_filed_irrelevant(self):
        """Test ignoring flight plan not involving this airport."""
        initial_count = len(self.airport.fdps.flights)
        
        message = {
            "flight_id": "DLH789",
            "origin": "EDDF",
            "destination": "EGLL",
            "route_string": "DCT PODIP DCT EGLL",
            "cruise_fl": 350,
            "departure_time": datetime.now(timezone.utc).isoformat()
        }
        
        await self.airport.handle_flight_plan_filed(message)
        
        # Verify flight was NOT added
        self.assertEqual(len(self.airport.fdps.flights), initial_count)

    async def test_handle_aar_override(self):
        """Test handling AAR override message."""
        original_aar = self.airport.status.aar
        
        message = {
            "target_node": "LFPG_AIRPORT",
            "aar": 50
        }
        
        await self.airport.handle_aar_override(message)
        
        self.assertEqual(self.airport.status.aar, 50)

    async def test_handle_aar_override_wrong_target(self):
        """Test that AAR override for different target is ignored."""
        original_aar = self.airport.status.aar
        
        message = {
            "target_node": "EGLL_AIRPORT",  # Different airport
            "aar": 50
        }
        
        await self.airport.handle_aar_override(message)
        
        self.assertEqual(self.airport.status.aar, original_aar)

    async def test_handle_en_route_warning_relevant(self):
        """Test handling warning for adjacent sector."""
        message = {
            "warning_id": "WARN_001",
            "originating_node": "LFFF_FMP",
            "constrained_sector_id": "LFFF1A",  # Our adjacent sector
            "required_flow_reduction": {"amount_to_reduce": 10},
            "affected_time_window": {
                "start": datetime.now(timezone.utc).isoformat(),
                "end": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
            }
        }
        
        # Should process without error - implementation may send proposals
        try:
            await self.airport.handle_en_route_warning(message)
        except Exception as e:
            self.fail(f"handle_en_route_warning raised {e} unexpectedly!")

    async def test_handle_en_route_warning_irrelevant(self):
        """Test ignoring warning for unrelated sector."""
        message = {
            "warning_id": "WARN_002",
            "originating_node": "EDDD_FMP",
            "constrained_sector_id": "EDDD1A",  # Not our sector
            "required_flow_reduction": {"amount_to_reduce": 10},
            "affected_time_window": {
                "start": datetime.now(timezone.utc).isoformat(),
                "end": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
            }
        }
        
        await self.airport.handle_en_route_warning(message)
        
        # Should NOT have created a pending warning
        self.assertNotIn("WARN_002", self.airport.pending_warnings)

    async def test_handle_en_route_warning_own_node(self):
        """Test ignoring warning from self."""
        message = {
            "warning_id": "WARN_003",
            "originating_node": "LFPG_AIRPORT",  # Our own node
            "constrained_sector_id": "LFFF1A",
            "required_flow_reduction": {"amount_to_reduce": 10},
            "affected_time_window": {
                "start": datetime.now(timezone.utc).isoformat(),
                "end": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
            }
        }
        
        await self.airport.handle_en_route_warning(message)
        
        # Should NOT have created a pending warning
        self.assertNotIn("WARN_003", self.airport.pending_warnings)

    async def test_handle_proposal_idempotency(self):
        """Test that duplicate proposals are ignored."""
        message = {
            "proposal_id": "PROP_001",
            "referencing_warning_id": "WARN_001",
            "proposing_node": "EDDF_AIRPORT",
            "contribution_to_reduction": 5,
            "proposed_actions": []
        }
        
        # First proposal should be accepted
        await self.airport.handle_proposal(message)
        self.assertIn("PROP_001", self.airport.processed_proposal_ids)
        
        # Duplicate should be ignored
        initial_count = len(self.airport.processed_proposal_ids)
        await self.airport.handle_proposal(message)
        self.assertEqual(len(self.airport.processed_proposal_ids), initial_count)

    async def test_handle_consensus_idempotency(self):
        """Test that duplicate consensus messages are ignored."""
        message = {
            "consensus_id": "CONS_001",
            "referencing_warning_id": "WARN_001",
            "participating_nodes": ["LFPG_AIRPORT"],
            "final_action_plan": [],
            "slot_table": []
        }
        
        # First consensus should be processed
        await self.airport.handle_consensus(message)
        self.assertIn("CONS_001", self.airport.processed_consensus_ids)
        
        # Duplicate should be ignored
        initial_count = len(self.airport.processed_consensus_ids)
        await self.airport.handle_consensus(message)
        self.assertEqual(len(self.airport.processed_consensus_ids), initial_count)

    async def test_emit_gdp_warning(self):
        """Test GDP warning emission when AAR is breached."""
        # Set up AAR breach condition
        self.airport.status.aar = 30
        self.airport.status.inbound_demand = 40  # 10 over AAR
        
        await self.airport._emit_gdp_warning(10)
        
        # Verify warning was published
        self.mock_network.publish.assert_called()
        call_args = self.mock_network.publish.call_args
        self.assertEqual(call_args[0][0], "ddfn.warning.trigger")
        
        # Verify warning structure
        warning = call_args[0][1]
        self.assertEqual(warning["constrained_sector_id"], "LFFF1A")
        self.assertEqual(warning["required_flow_reduction"]["amount_to_reduce"], 10)

    async def test_cascade_warning(self):
        """Test cascade warning emission."""
        await self.airport._cascade_warning("WARN_ORIGINAL", 5)
        
        # Verify cascade warning was published
        self.mock_network.publish.assert_called()
        call_args = self.mock_network.publish.call_args
        self.assertEqual(call_args[0][0], "ddfn.warning.trigger")
        
        warning = call_args[0][1]
        self.assertEqual(warning["required_flow_reduction"]["amount_to_reduce"], 5)


class TestAirportNodeEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Edge case tests for AirportNode."""

    async def asyncSetUp(self):
        """Set up async test fixtures."""
        self.mock_network = MagicMock()
        self.mock_network.publish = AsyncMock(return_value=None)
        self.mock_network.subscribe = AsyncMock(return_value=None)
        
        self.fdps = FlightDataProcessingSystem()
        
        self.airport = AirportNode(
            icao="LFPG",
            network=self.mock_network,
            fdps=self.fdps,
            adjacent_sector="LFFF1A"
        )

    async def test_invalid_flight_plan(self):
        """Test handling of invalid flight plan data."""
        message = {
            "flight_id": "INVALID",
            "origin": "LFPG",
            "destination": "EGLL",
            "route_string": "DCT EGLL",
            "cruise_fl": 350,
            "departure_time": "invalid-datetime"  # Invalid format
        }
        
        # Should not raise exception
        try:
            await self.airport.handle_flight_plan_filed(message)
        except Exception as e:
            self.fail(f"handle_flight_plan_filed raised {e} unexpectedly!")

    async def test_proposal_without_warning(self):
        """Test handling proposal for non-existent warning."""
        message = {
            "proposal_id": "PROP_ORPHAN",
            "referencing_warning_id": "NONEXISTENT",
            "proposing_node": "EDDF_AIRPORT",
            "contribution_to_reduction": 5,
            "proposed_actions": []
        }
        
        # Should not raise exception
        try:
            await self.airport.handle_proposal(message)
        except Exception as e:
            self.fail(f"handle_proposal raised {e} unexpectedly!")

    async def test_consensus_without_participation(self):
        """Test handling consensus where we're not a participant."""
        message = {
            "consensus_id": "CONS_EXT",
            "referencing_warning_id": "WARN_EXT",
            "participating_nodes": ["EGLL_AIRPORT", "EDDF_AIRPORT"],  # Not us
            "final_action_plan": [],
            "slot_table": []
        }
        
        # Should process but not log as ours
        await self.airport.handle_consensus(message)
        self.assertIn("CONS_EXT", self.airport.processed_consensus_ids)


if __name__ == '__main__':
    unittest.main()
