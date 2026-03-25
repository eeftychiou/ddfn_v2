import unittest
import json
from datetime import datetime
from ddfn_v2.core.models import (
    SectorCapacity, CapacityStateBroadcast, TimeWindow, FlowReduction,
    CapacityConstraintWarning, ProposedAction, ActionDetails,
    FlowNegotiationProposal, CTOTAssignmentProposal, SlotDetails,
    DistributedFlowConsensus, FlightSummary, AirspaceInventory,
    FlightPlanFiled, UIInboxApprovalRequest, to_json, from_dict
)

class TestModels(unittest.TestCase):
    def test_sector_capacity_serialization(self):
        sc = SectorCapacity(
            sector_id="LFFF1A",
            configuration="NORTH",
            declared_capacity_per_hour=30,
            current_demand_per_hour=15,
            status="GREEN",
            is_virtual=True,
            base_sectors=["LFFF1A_1", "LFFF1A_2"]
        )
        data = json.loads(to_json(sc))
        self.assertEqual(data["sector_id"], "LFFF1A")
        self.assertTrue(data["is_virtual"])
        self.assertEqual(data["base_sectors"], ["LFFF1A_1", "LFFF1A_2"])

        # Deserialization
        sc_back = from_dict(SectorCapacity, data)
        self.assertEqual(sc_back.sector_id, "LFFF1A")
        self.assertTrue(sc_back.is_virtual)
        self.assertEqual(sc_back.base_sectors, ["LFFF1A_1", "LFFF1A_2"])

    def test_sector_capacity_with_polygon(self):
        polygon = [(34.5, 32.1), (34.6, 32.2), (34.7, 32.1)]
        sc = SectorCapacity(
            sector_id="LCCC001",
            configuration="DEFAULT",
            declared_capacity_per_hour=40,
            current_demand_per_hour=0,
            status="GREEN",
            polygon=polygon
        )
        # Serialization (Pydantic v2 to_json uses lists for tuples)
        data = json.loads(to_json(sc))
        self.assertEqual(data["polygon"], [[34.5, 32.1], [34.6, 32.2], [34.7, 32.1]])
        
        # Deserialization
        sc_back = from_dict(SectorCapacity, data)
        self.assertEqual(len(sc_back.polygon), 3)
        self.assertEqual(sc_back.polygon[0], (34.5, 32.1))

    def test_nested_ctot_proposal(self):
        slot = SlotDetails(
            flight_id="AFR123",
            origin="LFPG",
            etot="2026-03-11T12:00:00Z",
            ctot="2026-03-11T12:15:00Z",
            delay=15
        )
        proposal = CTOTAssignmentProposal(
            proposal_id="prop-1",
            referencing_warning_id="warn-1",
            originating_node="LFFF",
            target_nodes=["LFPG"],
            slot_assignments=[slot],
            total_delay_minutes=15
        )
        
        js_data = to_json(proposal)
        data = json.loads(js_data)
        
        # Verify nested list handling in from_dict
        prop_back = from_dict(CTOTAssignmentProposal, data)
        self.assertEqual(len(prop_back.slot_assignments), 1)
        self.assertEqual(prop_back.slot_assignments[0].flight_id, "AFR123")
        self.assertIsInstance(prop_back.slot_assignments[0], SlotDetails)

    def test_capacity_state_broadcast(self):
        sc = SectorCapacity(
            sector_id="EGTT1C",
            configuration="DEFAULT",
            declared_capacity_per_hour=40,
            current_demand_per_hour=10,
            status="GREEN"
        )
        broadcast = CapacityStateBroadcast(node_id="EGTT", sectors=[sc])
        
        data = json.loads(to_json(broadcast))
        back = from_dict(CapacityStateBroadcast, data)
        
        self.assertEqual(back.node_id, "EGTT")
        self.assertEqual(len(back.sectors), 1)
        self.assertEqual(back.sectors[0].sector_id, "EGTT1C")

    def test_backward_compatibility_sector_capacity(self):
        # Test loading data without optional fields is_virtual/base_sectors
        legacy_data = {
            "sector_id": "LFFFXX",
            "configuration": "LEGACY",
            "declared_capacity_per_hour": 20,
            "current_demand_per_hour": 5,
            "status": "GREEN"
        }
        sc = from_dict(SectorCapacity, legacy_data)
        self.assertEqual(sc.sector_id, "LFFFXX")
        self.assertFalse(sc.is_virtual)
        self.assertEqual(sc.base_sectors, [])

    def test_sector_capacity_filtering(self):
        # Test that extra fields (like 'fir') are filtered out
        data_with_fir = {
            "sector_id": "LFFF1A",
            "declared_capacity_per_hour": 40,
            "fir": "LFFF" # Extra field to be filtered
        }
        sc = from_dict(SectorCapacity, data_with_fir)
        self.assertEqual(sc.sector_id, "LFFF1A")

if __name__ == '__main__':
    unittest.main()
