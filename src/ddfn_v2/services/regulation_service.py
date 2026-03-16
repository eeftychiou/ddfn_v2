import datetime as dt
import uuid
from typing import List, Tuple, Set, Optional
from ddfn_v2.core.models import SlotDetails, FlightSummary
from ddfn_v2.eng.trajectories import FlightTrajectory

class RegulationService:
    """
    Domain service for flow management algorithms (CASA - Computer Assisted Slot Allocation).
    Isolated from networking and node-specific logic for easier testing.
    """
    
    @staticmethod
    def run_casa(
        sector_id: str,
        start_dt: dt.datetime,
        end_dt: dt.datetime,
        capacity_per_hour: int,
        affected_flights: List[FlightTrajectory]
    ) -> List[SlotDetails]:
        """
        Calculates CTOTs (slots) for a list of affected flights using 
        First-Planned, First-Served (FPFS) logic.
        """
        if not affected_flights:
            return []

        def get_eto_for_sector(flt: FlightTrajectory) -> dt.datetime:
            for se in flt.route:
                if se.sector_id == sector_id:
                    return se.estimated_time_over
            return flt.departure_time

        # 1. FPFS Sorting: Sort by their original estimated time over the sector
        affected_flights.sort(key=get_eto_for_sector)
        
        slot_interval = dt.timedelta(minutes=60 / capacity_per_hour)
        slots = []
        last_assigned_slot = None

        for flt in affected_flights:
            eto = get_eto_for_sector(flt)
            
            # Slot cannot be before the regulation start time or before the flight's ETO
            if last_assigned_slot is None:
                assigned_slot = max(eto, start_dt)
            else:
                next_min_slot = last_assigned_slot + slot_interval
                assigned_slot = max(eto, next_min_slot)
            
            delay = int((assigned_slot - eto).total_seconds() / 60)
            ctot = flt.departure_time + dt.timedelta(minutes=delay)
            
            slots.append(SlotDetails(
                flight_id=flt.flight_id,
                origin=flt.origin,
                etot=flt.departure_time.isoformat(),
                ctot=ctot.isoformat(),
                delay=delay
            ))
            
            last_assigned_slot = assigned_slot
            
        return slots

    @staticmethod
    def identify_participating_nodes(flights: List[FlightTrajectory], local_node_id: str) -> Set[str]:
        """
        Identifies which nodes need to be involved in the consensus for these flights.
        """
        participating_nodes = {local_node_id}
        for flt in flights:
            if flt.origin.endswith("PORT") or "_" in flt.origin:
                participating_nodes.add(flt.origin)
            else:
                # Guessing airport node ID convention
                participating_nodes.add(f"{flt.origin}_AIRPORT")
        return participating_nodes
