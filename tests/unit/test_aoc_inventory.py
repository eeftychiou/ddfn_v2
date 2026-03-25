import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from ddfn_v2.services.aoc_service import AOCNode
from ddfn_v2.core.network import NetworkClient

@pytest.mark.asyncio
async def test_aoc_inventory_tracking():
    mock_network = MagicMock(spec=NetworkClient)
    aoc = AOCNode("DLH", mock_network)
    
    # Pre-populate with a flight
    aoc.flights = [{
        "flight_id": "DLH123",
        "origin": "EDDF",
        "destination": "EGLL"
    }]
    
    # Simulate an inventory update message for this flight
    inventory_msg = {
        "message_type": "AIRSPACE_INVENTORY_UPDATE",
        "flights": [
            {
                "flight_id": "DLH123",
                "status": "ACTIVE",
                "entry_point": "PODIP",
                "exit_point": "LAMSO",
                "eta_entry": "2026-03-24T15:00:00Z",
                "eta_exit": "2026-03-24T15:30:00Z"
            }
        ]
    }
    
    await aoc._handle_inventory(inventory_msg)
    
    # Verify tracking was updated
    f = aoc.flights[0]
    assert f["status"] == "ACTIVE"
    assert f["entry_point"] == "PODIP"
    assert f["eta_entry"] == "2026-03-24T15:00:00Z"
    assert "status" in aoc.flights[0]
