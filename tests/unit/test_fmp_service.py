"""
test_fmp_service.py - Unit tests for FMP Node
================================================
Tests the FMPNode class and its message handlers.
"""

import unittest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from datetime import datetime, timezone, timedelta

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from ddfn_v2.services.fmp_service import FMPNode
from ddfn_v2.eng.trajectories import FlightDataProcessingSystem
from ddfn_v2.core.models import SlotDetails


class TestFMPNodeHandlerRegistration(unittest.IsolatedAsyncioTestCase):
    """Test cases for FMPNode handler registration - P0 Bug Fix Verification."""

    async def asyncSetUp(self):
        """Set up async test fixtures."""
        self.mock_network = MagicMock()
        self.mock_network.publish = AsyncMock(return_value=None)
        self.mock_network.subscribe = AsyncMock(return_value=None)
        
        # Create FMPNode with minimal configuration
        self.fmp_node = FMPNode(
            node_id="LFFF_FMP",
            network=self.mock_network,
            sectors=[]
        )

    async def test_slot_swap_handler_registered(self):
        """
        Test that FMP_SLOT_SWAP_REQUEST handler is properly registered.
        
        This is a P0 bug fix verification - the handle_slot_swap method
        was defined but never registered in the handler map, causing
        FMP_SLOT_SWAP_REQUEST messages to be silently ignored.
        """
        # Mock the parent class start method to avoid actual network operations
        with patch.object(FMPNode, '__init__', lambda self, node_id, network, sectors: None):
            with patch('ddfn_v2.core.node.DDFN_Node.start', new_callable=AsyncMock) as mock_super_start:
                # Track registered handlers
                registered_handlers = {}
                
                def mock_register_handler(msg_type, handler):
                    registered_handlers[msg_type] = handler
                
                self.fmp_node.register_handler = mock_register_handler
                
                # Call start() which should register all handlers
                await self.fmp_node.start()
                
                # Verify FMP_SLOT_SWAP_REQUEST handler is registered
                self.assertIn("FMP_SLOT_SWAP_REQUEST", registered_handlers)
                self.assertEqual(
                    registered_handlers["FMP_SLOT_SWAP_REQUEST"],
                    self.fmp_node.handle_slot_swap
                )

    async def test_all_expected_handlers_registered(self):
        """
        Test that all expected message handlers are registered during start().
        """
        expected_handlers = [
            "DISTRIBUTED_FLOW_CONSENSUS",
            "MANUAL_CAPACITY_OVERRIDE",
            "REMOVE_CAPACITY_OVERRIDE",
            "FMP_PROPOSAL_APPROVAL",
            "SET_MEASURE_WINDOW",
            "MERGE_SECTORS",
            "APPLY_CONFIGURATION",
            "RAD_RULE_UPDATE",
            "FIR_HANDOVER_ADVISORY",
            "FLIGHT_PLAN_FILED",
            "AOCC_READY_TO_FLY",
            "FMP_SLOT_SWAP_REQUEST",  # P0 bug fix
        ]
        
        with patch.object(FMPNode, '__init__', lambda self, node_id, network, sectors: None):
            with patch('ddfn_v2.core.node.DDFN_Node.start', new_callable=AsyncMock):
                registered_handlers = {}
                
                def mock_register_handler(msg_type, handler):
                    registered_handlers[msg_type] = handler
                
                self.fmp_node.register_handler = mock_register_handler
                await self.fmp_node.start()
                
                for handler_type in expected_handlers:
                    self.assertIn(
                        handler_type, 
                        registered_handlers,
                        f"Handler {handler_type} should be registered"
                    )


class TestFMPNodeSlotSwap(unittest.IsolatedAsyncioTestCase):
    """Test cases for FMPNode slot swap functionality."""

    async def asyncSetUp(self):
        """Set up async test fixtures."""
        self.mock_network = MagicMock()
        self.mock_network.publish = AsyncMock(return_value=None)
        
        self.fmp_node = FMPNode(
            node_id="LFFF_FMP",
            network=self.mock_network,
            sectors=[]
        )
        
        # Set up active slots for testing
        self.fmp_node.active_slots["WARN_001"] = [
            SlotDetails(
                flight_id="AFR001",
                origin="LFPG",
                destination="EGLL",
                etot=datetime.now(timezone.utc).isoformat(),
                ctot=(datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
                delay=30,
                status="ASSIGNED"
            ),
            SlotDetails(
                flight_id="AFR002",
                origin="LFPG",
                destination="EGLL",
                etot=datetime.now(timezone.utc).isoformat(),
                ctot=(datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat(),
                delay=45,
                status="ASSIGNED"
            ),
        ]

    async def test_handle_slot_swap_wrong_target(self):
        """Test that slot swap for different target is ignored."""
        message = {
            "target_node": "EGTT_FMP",  # Different node
            "warning_id": "WARN_001",
            "flight_id_1": "AFR001",
            "flight_id_2": "AFR002"
        }
        
        # Should not raise exception and should not process
        try:
            await self.fmp_node.handle_slot_swap(message)
        except Exception as e:
            self.fail(f"handle_slot_swap raised {e} unexpectedly!")

    async def test_handle_slot_swap_empty_target(self):
        """Test that slot swap with empty target is processed (broadcast)."""
        message = {
            "target_node": "",  # Empty means broadcast/all nodes
            "warning_id": "WARN_001",
            "flight_id_1": "AFR001",
            "flight_id_2": "AFR002"
        }
        
        # Should process without error
        try:
            await self.fmp_node.handle_slot_swap(message)
        except Exception as e:
            self.fail(f"handle_slot_swap raised {e} unexpectedly!")

    async def test_handle_slot_swap_nonexistent_warning(self):
        """Test handling slot swap for non-existent warning."""
        message = {
            "target_node": "LFFF_FMP",
            "warning_id": "WARN_NONEXISTENT",
            "flight_id_1": "AFR001",
            "flight_id_2": "AFR002"
        }
        
        # Should not raise exception
        try:
            await self.fmp_node.handle_slot_swap(message)
        except Exception as e:
            self.fail(f"handle_slot_swap raised {e} unexpectedly!")


class TestFMPNodeInitialization(unittest.TestCase):
    """Test cases for FMPNode initialization."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_network = MagicMock()

    def test_fmp_node_initialization(self):
        """Test FMPNode basic initialization."""
        fmp = FMPNode(
            node_id="LFFF_FMP",
            network=self.mock_network,
            sectors=[]
        )
        
        self.assertEqual(fmp.node_id, "LFFF_FMP")
        self.assertEqual(fmp.sectors, [])
        self.assertFalse(fmp.is_configured)
        self.assertEqual(fmp._measure_window_minutes, 120)  # Default value

    def test_fmp_node_with_sectors(self):
        """Test FMPNode initialization with sectors."""
        from ddfn_v2.core.models import SectorCapacity
        
        sectors = [
            SectorCapacity(
                sector_id="LFFF1A",
                configuration="NORTH",
                declared_capacity_per_hour=40,
                current_demand_per_hour=0,
                status="GREEN"
            )
        ]
        
        fmp = FMPNode(
            node_id="LFFF_FMP",
            network=self.mock_network,
            sectors=sectors
        )
        
        self.assertEqual(len(fmp.sectors), 1)
        self.assertEqual(fmp.sectors[0].sector_id, "LFFF1A")


if __name__ == '__main__':
    unittest.main()
