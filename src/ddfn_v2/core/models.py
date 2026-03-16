import json
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

# --- Data Models reflecting ddfn_data_models.md ---

class SectorCapacity(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sector_id: str
    configuration: str
    declared_capacity_per_hour: int
    current_demand_per_hour: int
    status: str
    fl_lower: int = 0
    fl_upper: int = 660
    is_virtual: bool = False
    base_sectors: List[str] = Field(default_factory=list)
    active_capacity: Optional[int] = None # The capacity currently taking effect (after overrides)
    constraint_reason: str = ""

class CapacityStateBroadcast(BaseModel):
    node_id: str
    sectors: List[SectorCapacity]
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z")
    message_type: str = "CAPACITY_STATE_BROADCAST"

class TimeWindow(BaseModel):
    start: str
    end: str

class FlowReduction(BaseModel):
    metric: str
    amount_to_reduce: int

class CapacityConstraintWarning(BaseModel):
    warning_id: str
    originating_node: str
    target_nodes: List[str]
    constrained_sector_id: str
    affected_time_window: TimeWindow
    required_flow_reduction: FlowReduction
    affected_flights_pool: List[str]
    cascade_of: Optional[str] = None # Linking to parent warning in a cascade
    message_type: str = "CONSTRAINT_WARNING_TRIGGER"

class ActionDetails(BaseModel):
    estimated_delay_minutes: int
    speed_mach: float

class ProposedAction(BaseModel):
    action_type: str
    flight_id: str
    details: ActionDetails

class FlowNegotiationProposal(BaseModel):
    proposal_id: str
    referencing_warning_id: str
    proposing_node: str
    proposed_actions: List[ProposedAction]
    contribution_to_reduction: int
    message_type: str = "FLOW_NEGOTIATION_PROPOSAL"

class SlotDetails(BaseModel):
    flight_id: str
    origin: str         # Added to help edge nodes identify their flights
    etot: str           # Estimated Take-Off Time (Schedule)
    ctot: str           # Calculated Take-Off Time (After regulation)
    delay: int          # Minutes
    status: str = "REGULATED" 
    locked: bool = False # Manually swapped by FMP

class CTOTAssignmentProposal(BaseModel):
    proposal_id: str
    referencing_warning_id: str
    originating_node: str # The node that calculated the CTOTs (the constrained node)
    target_nodes: List[str] # The nodes that need to apply the CTOTs
    slot_assignments: List[SlotDetails]
    total_delay_minutes: int
    message_type: str = "CTOT_ASSIGNMENT_PROPOSAL"

class DistributedFlowConsensus(BaseModel):
    consensus_id: str
    referencing_warning_id: str
    participating_nodes: List[str]
    final_action_plan: List[str]
    slot_table: List[SlotDetails] = Field(default_factory=list) # Full list of assignments
    status: str = "AGREED_AND_LOCKED"
    b2b_submission_status: str = "PENDING_NM_VALIDATION"
    message_type: str = "DISTRIBUTED_FLOW_CONSENSUS"

class SlotSwapRequest(BaseModel):
    target_node: str
    flight_id_1: str
    flight_id_2: str
    warning_id: str
    message_type: str = "FMP_SLOT_SWAP_REQUEST"

class HandoverAdvisory(BaseModel):
    flight_id: str
    exit_fix: str
    exit_time: str
    fl: int
    destination: str
    remaining_route: str
    originating_node: str
    message_type: str = "FIR_HANDOVER_ADVISORY"

class FlightSummary(BaseModel):
    flight_id: str
    origin: str
    destination: str
    status: str  # ACTIVE or SCHEDULED
    entry_point: str
    exit_point: str
    eta_entry: str
    eta_exit: str
    route_string: str = ""

class AirspaceInventory(BaseModel):
    node_id: str
    flights: List[FlightSummary]
    message_type: str = "AIRSPACE_INVENTORY_UPDATE"

class FlightPlanFiled(BaseModel):
    flight_id: str
    origin: str
    destination: str
    route_string: str
    cruise_fl: int
    departure_time: str # ISO format string representing the scheduled ETOT
    message_type: str = "FLIGHT_PLAN_FILED"

class UIInboxApprovalRequest(BaseModel):
    target_node: str
    warning_id: str
    sector_id: str
    demand: int
    capacity: int
    delayed_flights: int
    message_type: str = "UI_INBOX_APPROVAL_REQUEST"

def to_json(obj) -> str:
    if hasattr(obj, 'model_dump_json'):
        return obj.model_dump_json()
    return json.dumps(obj)

def from_dict(data_class, data: dict):
    if hasattr(data_class, 'model_validate'):
        # backward compatibility for SectorCapacity missing fields
        if data_class is SectorCapacity:
             if "configuration" not in data: data["configuration"] = "SINGLE"
             if "declared_capacity_per_hour" not in data: data["declared_capacity_per_hour"] = 40
             if "current_demand_per_hour" not in data: data["current_demand_per_hour"] = 0
             if "status" not in data: data["status"] = "GREEN"
             
        return data_class.model_validate(data)
    return data
