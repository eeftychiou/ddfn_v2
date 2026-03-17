import asyncio
import logging
import uuid
import random
import json
import argparse
from ddfn_v2.services import schedule
from ddfn_v2.services.rad_validator import VALIDATOR as RAD_VALIDATOR
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import uvicorn
from fastapi import FastAPI, Request, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from ddfn_v2.core.node import DDFN_Node
from ddfn_v2.core.network import NetworkClient
from ddfn_v2.core.models import (
    SectorCapacity, TimeWindow, FlowReduction,
    DistributedFlowConsensus, from_dict,
    CapacityConstraintWarning,
    SlotDetails, SlotSwapRequest, HandoverAdvisory,
    FlightSummary, AirspaceInventory, CTOTAssignmentProposal,
    UIInboxApprovalRequest, FlightPlanFiled
)
from ddfn_v2.eng.trajectories import FlightDataProcessingSystem, FlightTrajectory, SectorEntry
from ddfn_v2.eng.airspace import Waypoint, WAYPOINTS, SectorGeometry, load_from_aixm as load_aixm_to_registry, SECTORS as GLOBAL_SECTORS
import dataclasses
from ddfn_v2.util.aixm_tool import AIXMParser
import os
from ddfn_v2.core.persistence import PersistenceManager
from ddfn_v2.services.regulation_service import RegulationService
from ddfn_v2.core.request_models import (
    SetupConfigurationRequest, ApplyAIXMConfigRequest, CapacityOverrideRequest,
    MergeSectorsRequest, SetWindowRequest, ApplyConfigurationRequest,
    RADToggleRequest, AIXMFileRequest, LoadConfigurationRequest,
    SuccessResponse, ErrorResponse, ConfigurationListResponse,
    SetupStatusResponse, AIXMSourceResponse, AIXMUploadResponse
)
from ddfn_v2.util.validators import validate_file_path_for_aixm, ValidationError

CONFIG_DIR = "node_configs"
os.makedirs(CONFIG_DIR, exist_ok=True)



class FMPNode(DDFN_Node):
    def __init__(self, node_id: str, network: NetworkClient, sectors: List[dict], waypoint_db: Optional[Dict[str, Waypoint]] = None):
        super().__init__(node_id, network)
        
        # All sectors should be loaded via Airspace Config page or Persistent config
        self.sectors: List[SectorCapacity] = []
        self.is_configured = False
        
        self.logger.info(f"FMPNode {node_id}: Initializing in base state. is_configured={self.is_configured}")
            
        self.pending_warnings: Dict[str, dict] = {}
        self.active_slots: Dict[str, List[SlotDetails]] = {}
        self.fdps = FlightDataProcessingSystem()
        self.waypoint_db: Dict[str, Waypoint] = waypoint_db if waypoint_db is not None else WAYPOINTS
        self._measure_window_minutes = 120 # Default setting
        # --- Race-condition protection ---
        self._state_lock = asyncio.Lock()
        self.processed_proposal_ids: set = set()   # idempotency: skip duplicates
        self.processed_consensus_ids: set = set()  # idempotency: skip replayed consensus
        self.manual_overrides: Dict[str, List[dict]] = {} # sector_id -> list of overrides (dict with start, end, cap, reason)
        self._latest_inventory: List[dict] = []
        self.aixm_source_file: Optional[str] = None
        self.aixm_source_fir: Optional[str] = None
        self.active_config_name: str = "Default"
        self.config_path = os.path.join(CONFIG_DIR, f"{node_id}.json")
        self.saved_configs_path = os.path.join(CONFIG_DIR, f"{node_id}_saved.json")
        self._historic_sectors: List[SectorCapacity] = []
        
        # --- Persistence Initialize ---
        db_path = os.path.join(CONFIG_DIR, f"{node_id}_state.db")
        self.persistence = PersistenceManager(db_path)
        
        # Load manual overrides from persistent storage
        self.manual_overrides = self.persistence.load_overrides()
        
        self.load_local_config()

    def load_local_config(self):
        """Load airspace configuration from local storage."""
        self.logger.info(f"DEBUG: Attempting to load config from {self.config_path}")
        if os.path.exists(self.config_path):
            self.logger.info(f"DEBUG: Config file found at {self.config_path}")
            try:
                with open(self.config_path, "r") as f:
                    config = json.load(f)
                    self.aixm_source_file = config.get("aixm_source_file")
                    self.aixm_source_fir = config.get("aixm_source_fir")
                    self.active_config_name = config.get("config_name", "Default")
                    self._measure_window_minutes = config.get("measure_window", 120)
                    self.is_configured = config.get("is_configured", False)
                    
                    if self.is_configured and self.aixm_source_file:
                        # Ensure AIXM is loaded into the registry
                        load_aixm_to_registry(self.aixm_source_file)
                        
                    if "sectors" in config:
                        self.sectors = [from_dict(SectorCapacity, s) for s in config["sectors"]]
                    elif self.is_configured and self.aixm_source_fir:
                        from ddfn_v2.eng.airspace import get_fir_sectors as get_global_fir_sectors
                        aixm_sectors = get_global_fir_sectors(self.aixm_source_fir)
                        if aixm_sectors:
                             self.sectors = [from_dict(SectorCapacity, s) for s in aixm_sectors]
            except Exception as e:
                self.logger.error(f"Failed to load local config: {e}")

    def save_local_config(self, sectors=None, config_name=None):
        """Save current airspace configuration to local storage."""
        if config_name:
            self.logger.info(f"FMPNode: Updating active_config_name from {self.active_config_name} to {config_name}")
            self.active_config_name = config_name
            
        try:
            config = {
                "sectors": [s.model_dump() for s in (sectors or self.sectors)],
                "aixm_source_file": self.aixm_source_file,
                "aixm_source_fir": self.aixm_source_fir,
                "config_name": self.active_config_name,
                "measure_window": self._measure_window_minutes,
                "is_configured": self.is_configured
            }
            self.logger.info(f"FMPNode: Saving config dict with name: {config['config_name']}")
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=4)
            
            # If a name is provided, also save to named storage
            if config_name and config_name != "Default":
                self.save_named_config(config_name, config)
                
            self.logger.info(f"Saved configuration to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save local config: {e}")

    def save_named_config(self, name: str, config_data: dict):
        """Saves a configuration into the persistent library."""
        saved = {}
        if os.path.exists(self.saved_configs_path):
            with open(self.saved_configs_path, "r") as f:
                saved = json.load(f)
        
        saved[name] = config_data
        with open(self.saved_configs_path, "w") as f:
            json.dump(saved, f, indent=4)

    def list_saved_configs(self) -> List[str]:
        if not os.path.exists(self.saved_configs_path):
            return []
        with open(self.saved_configs_path, "r") as f:
            return list(json.load(f).keys())

    def delete_named_config(self, name: str):
        if not os.path.exists(self.saved_configs_path):
            return
        with open(self.saved_configs_path, "r") as f:
            saved = json.load(f)
        if name in saved:
            del saved[name]
            with open(self.saved_configs_path, "w") as f:
                json.dump(saved, f, indent=4)

    def load_named_config(self, name: str):
        if not os.path.exists(self.saved_configs_path):
            return False
        with open(self.saved_configs_path, "r") as f:
            saved = json.load(f)
        if name in saved:
            config = saved[name]
            self.sectors = [from_dict(SectorCapacity, s) for s in config["sectors"]]
            self.aixm_source_file = config.get("aixm_source_file")
            self.aixm_source_fir = config.get("aixm_source_fir")
            self.active_config_name = name
            self.save_local_config()
            return True
        return False

    async def start(self):
        # Register handlers BEFORE starting the message loop in super().start()
        self.register_handler("DISTRIBUTED_FLOW_CONSENSUS", self.handle_consensus)
        
        # UI specific handlers
        self.register_handler("MANUAL_CAPACITY_OVERRIDE", self.handle_manual_override)
        self.register_handler("REMOVE_CAPACITY_OVERRIDE", self.handle_remove_override)
        self.register_handler("FMP_PROPOSAL_APPROVAL", self.handle_fmp_approval)
        self.register_handler("SET_MEASURE_WINDOW", self.handle_set_measure_window)
        self.register_handler("MERGE_SECTORS", self.handle_merge_sectors)
        self.register_handler("APPLY_CONFIGURATION", self.handle_apply_configuration)
        self.register_handler("RAD_RULE_UPDATE", self.handle_rad_update)
        
        # Phase 12 Relay
        self.register_handler("FIR_HANDOVER_ADVISORY", self.handle_handover_advisory)
        self.register_handler("FLIGHT_PLAN_FILED", self.handle_flight_plan_filed)
        self.register_handler("AOCC_READY_TO_FLY", self.handle_aoc_ready)

        await super().start()
        
        # Topic subscriptions
        await self.network.subscribe("ddfn.relay.handover", self.subscription_queue)
        await self.network.subscribe("ddfn.flow.negotiation", self.subscription_queue)
        await self.network.subscribe("ddfn.flow.consensus", self.subscription_queue)
        await self.network.subscribe("ddfn.flight.plan", self.subscription_queue)
        await self.network.subscribe("ddfn.aoc.messages", self.subscription_queue)
        await self.network.subscribe("ddfn.fmp.command", self.subscription_queue)

        # Start background syncs

        # Start background syncs
        asyncio.create_task(self._sync_capacity())
        asyncio.create_task(self._broadcast_inventory())

        # Wait for network mesh to settle before initial handover scan
        await asyncio.sleep(2.0)

        # Initial FDPS scan: for any flight exiting our FIR, emit handover
        for flight in list(self.fdps.flights.values()):
            if flight.exit_fix:
                await self._emit_handover(flight)
        
        self.logger.info(f"FMP Node {self.node_id} started and synchronized (Truly Distributed).")

    async def handle_flight_plan_filed(self, message: dict):
        """Handle dynamic injection of new flight plans from the Sim Manager."""
        try:
            self.logger.debug(f"Received raw flight plan message: {message}")
            fp = from_dict(FlightPlanFiled, message)
            self.logger.info(f"FMP Processing FPL: {fp.flight_id} {fp.origin}->{fp.destination}")
            
            # Use TrajectorySolver to build the 4D geometry
            dept_time = datetime.fromisoformat(fp.departure_time)
            # Ensure dept_time is aware if it's naive
            if dept_time.tzinfo is None:
                dept_time = dept_time.replace(tzinfo=timezone.utc)
            
            traj = FlightTrajectory.from_flight_plan(
                flight_id=fp.flight_id,
                origin=fp.origin,
                destination=fp.destination,
                departure_time=dept_time,
                cruise_fl=fp.cruise_fl,
                route_string=fp.route_string,
                waypoint_db=self.waypoint_db
            )
            
            # --- Phase 2: RAD Validation ---
            try:
                is_valid, err_msg = RAD_VALIDATOR.is_valid(traj)
                if not is_valid:
                    self.logger.warning(f"FPL {fp.flight_id} VIOLATES RAD RULES: {err_msg}. Flagging for action.")
                    setattr(traj, 'rad_violation', err_msg)
            except Exception as e:
                self.logger.error(f"RAD validation CRASHED for {fp.flight_id}: {e}")
                is_valid, err_msg = True, None # Fallback to valid if validator crashes
            
            async with self._state_lock:
                self.fdps.add_flight(traj)
            
            if not is_valid:
                self.logger.info(f"Track initialized for {fp.flight_id} (RAD VIOLATION: {err_msg})")
            else:
                self.logger.info(f"Track initialized for {fp.flight_id}. Route intercepts {len(traj.route)} sectors. Entry: {traj.entry_fix}, Exit: {traj.exit_fix}")
            
        except Exception as e:
            self.logger.error(f"Failed to process dynamic flight plan {message.get('flight_id', 'Unknown')}: {e}")

    async def _sync_capacity(self):
        while True:
            try:
                now = datetime.now(timezone.utc)
                window_end = now + timedelta(minutes=self._measure_window_minutes)
                
                # Demand profile window: -12 hours to +12 hours
                profile_start = now - timedelta(hours=12)
                profile_end = now + timedelta(hours=12)
                
                # Broadcast our sector state so the UI Map can reflect it
                async with self._state_lock:
                    # Create a composite map for predict_flights_in_sector
                    composite_map = {}
                    for s_inner in self.sectors:
                        if s_inner.is_virtual:
                            composite_map[s_inner.sector_id] = s_inner.base_sectors
                    
                    for s in self.sectors:
                        # Resolve active override for current time
                        active_cap = s.declared_capacity_per_hour
                        active_reason = ""
                        
                        if s.sector_id in self.manual_overrides:
                            # Prune expired overrides
                            self.manual_overrides[s.sector_id] = [ovr for ovr in self.manual_overrides[s.sector_id] if ovr["end"] > now]
                            for ovr in self.manual_overrides[s.sector_id]:
                                if ovr["start"] <= now <= ovr["end"]:
                                    active_cap = ovr["capacity"]
                                    active_reason = ovr["reason"]
                                    break
                        
                        s.active_capacity = active_cap
                        if active_reason:
                            s.constraint_reason = active_reason
                        
                        # Calculate real dynamic demand
                        affected = self.fdps.predict_flights_in_sector(
                            s.sector_id, 
                            now, 
                            window_end,
                            composite_sector_map=composite_map
                        )
                        s.current_demand_per_hour = len(affected)
                        
                        # Update status based on active capacity
                        if s.current_demand_per_hour > active_cap:
                            s.status = "RED"
                            if not active_reason:
                                s.constraint_reason = "AUTO_CAPACITY_BREACH"
                        else:
                            s.status = "GREEN"
                            if not active_reason:
                                s.constraint_reason = ""
                        
                        demand_profile = self.fdps.calculate_demand_profile(
                            s.sector_id,
                            profile_start,
                            profile_end,
                            bin_size_minutes=5,
                            composite_sector_map=composite_map
                        )
                        # Serialize active overrides for this sector
                        active_overrides = []
                        if s.sector_id in self.manual_overrides:
                            for ovr in self.manual_overrides[s.sector_id]:
                                active_overrides.append({
                                    "id": ovr.get("id", ""),
                                    "start": ovr["start"].isoformat(),
                                    "end": ovr["end"].isoformat(),
                                    "capacity": ovr["capacity"],
                                    "reason": ovr["reason"]
                                })

                        if active_overrides:
                            self.logger.info(f"Sector {s.sector_id} broadcasting {len(active_overrides)} active overrides.")

                        state_msg = {
                            "message_type": "CAPACITY_STATE_BROADCAST",
                            "node_id": self.node_id,
                            "sector": s.model_dump(),
                            "measure_window": self._measure_window_minutes,
                            "demand_profile": demand_profile,
                            "active_overrides": active_overrides
                        }
                        await self.network.publish("ddfn.capacity.state", state_msg)
            except Exception as e:
                self.logger.error(f"Error in _sync_capacity: {e}")

            await asyncio.sleep(3.0)

    async def _reprocess_all_flights(self):
        """Re-evaluates trajectories for all flights in FDPS (e.g. after AIXM load)."""
        async with self._state_lock:
            count = 0
            for fid in list(self.fdps.flights.keys()):
                old_flt = self.fdps.flights[fid]
                new_flt = FlightTrajectory.from_flight_plan(
                    old_flt.flight_id, old_flt.origin, old_flt.destination, 
                    old_flt.departure_time, old_flt.cruise_fl, old_flt.route_string,
                    waypoint_db=self.waypoint_db
                )
                self.fdps.add_flight(new_flt)
                count += 1
            self.logger.info(f"Reprocessed {count} flights after configuration update.")

    async def _broadcast_inventory(self):
        """Periodically broadcast the list of flights in this FIR's FDPS."""
        while True:
            now = datetime.now(timezone.utc)
            summaries = []
            
            async with self._state_lock:
                # Local sectors for this node
                local_sector_ids = {s.sector_id for s in self.sectors}
                
                if not local_sector_ids and self.is_configured:
                    self.logger.warning(f"Node is configured but has NO local sectors! State: {len(self.sectors)} sectors.")

                # self.logger.info(f"DEBUG: Broadcasting inventory. Local sectors: {len(local_sector_ids)}. Flights in FDPS: {len(self.fdps.flights)}")

                for fid, flt in self.fdps.flights.items():
                    # Find first and last sector belonging to this FIR
                    local_entries = [e for e in flt.route if e.sector_id in local_sector_ids]
                    
                    if not local_entries:
                        # if len(flt.route) > 0:
                        #    self.logger.info(f"Flight {fid} has {len(flt.route)} sectors but NONE in {local_sector_ids}")
                        continue # Not relevant for this node anymore?
                        
                    entry_seg = local_entries[0]
                    exit_seg = local_entries[-1]
                    
                    eta_entry = entry_seg.estimated_time_over
                    self.logger.info(f"DEBUG: Flight {fid} is LOCAL. Entry: {entry_seg.sector_id} at {eta_entry}")

                    
                    # Determine when the flight exits this node's FIR
                    idx = flt.route.index(exit_seg)
                    if idx + 1 < len(flt.route):
                        next_seg = flt.route[idx + 1]
                        eta_exit = next_seg.estimated_time_over
                        exit_point = next_seg.sector_id
                    else:
                        # Flight arrives exactly at or right after this segment
                        eta_exit = flt.exit_time or (exit_seg.estimated_time_over + timedelta(minutes=15))
                        exit_point = flt.destination
                        
                    # If flight has completely left the node's airspace, don't show it in the live inventory
                    if now > eta_exit:
                        continue
                    
                    status = "SCHEDULED"
                    if eta_entry <= now <= eta_exit:
                        status = "ACTIVE"
                        
                    summaries.append(FlightSummary(
                        flight_id=fid,
                        origin=flt.origin,
                        destination=flt.destination,
                        status=status,
                        entry_point=entry_seg.sector_id,
                        exit_point=exit_point,
                        eta_entry=eta_entry.isoformat(),
                        eta_exit=eta_exit.isoformat(),
                        route_string=flt.route_string
                    ))
                
                self._latest_inventory = [s.model_dump() for s in summaries]
            
            inv = AirspaceInventory(node_id=self.node_id, flights=summaries)
            await self.network.publish("ddfn.airspace.inventory", inv.model_dump())
            await asyncio.sleep(5.0)

    async def handle_manual_override(self, msg: dict):
        """Called when UI dictates a capacity constraint (The V2 UI Builder)"""
        if msg.get("target_node") == self.node_id:
            sector_id = msg.get("sector")
            if not msg.get("capacity"): return
            
            new_cap = int(msg.get("capacity"))
            reason = msg.get("reason", "FMP_MANUAL_ADJUSTMENT")
            
            # Parse time window
            try:
                window_start_str = msg.get("start_time", "16:00")
                window_end_str = msg.get("end_time", "18:00")
                now_parsed = datetime.now(timezone.utc)
                
                start_dt = now_parsed.replace(hour=int(window_start_str.split(':')[0]), minute=int(window_start_str.split(':')[1]), second=0, microsecond=0)
                end_dt = now_parsed.replace(hour=int(window_end_str.split(':')[0]), minute=int(window_end_str.split(':')[1]), second=0, microsecond=0)
            except Exception:
                start_dt = datetime.now(timezone.utc)
                end_dt = start_dt + timedelta(hours=2)

            self.logger.info(f"FMP Manual Override Received: {sector_id} capacity set to {new_cap} from {start_dt.time()} to {end_dt.time()} reason: {reason}")
            
            async with self._state_lock:
                if sector_id not in self.manual_overrides:
                    self.manual_overrides[sector_id] = []
                
                new_override_id = f"OVR_{uuid.uuid4().hex[:8]}"
                new_override = {
                    "id": new_override_id,
                    "sector_id": sector_id,
                    "start": start_dt,
                    "end": end_dt,
                    "capacity": new_cap,
                    "reason": reason
                }
                self.manual_overrides[sector_id].append(new_override)
                self.persistence.save_override(new_override)

            # Check if this override triggers CASA immediately
            for s in self.sectors:
                if s.sector_id == sector_id:
                    self.logger.info(f"Sector {sector_id} checking for immediate CASA window: {start_dt.time()} to {end_dt.time()}")
                    
                    composite_map = {}
                    for s_inner in self.sectors:
                        if s_inner.is_virtual:
                            composite_map[s_inner.sector_id] = s_inner.base_sectors
                    
                    affected_flights = self.fdps.predict_flights_in_sector(
                        sector_id, 
                        start_dt, 
                        end_dt,
                        composite_sector_map=composite_map
                    )
                    
                    # Fix: Units mismatch. new_cap is flights/hour. 
                    # We must compare against effective capacity for this specific window duration.
                    window_duration_mins = (end_dt - start_dt).total_seconds() / 60.0
                    effective_window_cap = new_cap * (window_duration_mins / 60.0)

                    if len(affected_flights) > effective_window_cap:
                        self.logger.info(f"Demand {len(affected_flights)} > Effective Window Capacity {effective_window_cap:.1f} (Rate: {new_cap}/hr). Running CASA...")
                        
                        slots = RegulationService.run_casa(
                            sector_id=sector_id,
                            start_dt=start_dt,
                            end_dt=end_dt,
                            capacity_per_hour=new_cap,
                            affected_flights=affected_flights
                        )
                        
                        participating_nodes = RegulationService.identify_participating_nodes(affected_flights, self.node_id)

                        if slots:
                            warn_id = f"WARN_{self.node_id}_{uuid.uuid4().hex[:6]}"
                            self.pending_warnings[warn_id] = {
                                "status": "PENDING_HITL_APPROVAL",
                                "slots": slots,
                                "participating_nodes": list(participating_nodes)
                            }
                            
                            await self.emit("ddfn.ui.inbox", UIInboxApprovalRequest(
                                target_node=self.node_id,
                                warning_id=warn_id,
                                sector_id=sector_id,
                                demand=len(affected_flights),
                                capacity=new_cap,
                                delayed_flights=len(slots)
                            ))
                            self.logger.info(f"CASA calculated {len(slots)} delayed flights via RegulationService. Emitted to UI Inbox for {warn_id}.")

    async def handle_remove_override(self, msg: dict):
        """Removes a specific capacity override from a sector."""
        if msg.get("target_node") == self.node_id:
            sector_id = msg.get("sector")
            override_id = msg.get("override_id")
            
            if not sector_id or not override_id: return
            
            async with self._state_lock:
                if sector_id in self.manual_overrides:
                    initial_count = len(self.manual_overrides[sector_id])
                    self.manual_overrides[sector_id] = [
                        ovr for ovr in self.manual_overrides[sector_id] 
                        if ovr.get("id") != override_id
                    ]
                    if len(self.manual_overrides[sector_id]) < initial_count:
                        self.persistence.remove_override(override_id)
                        self.logger.info(f"FMP Removed Override: {override_id} from {sector_id}.")
                    else:
                        self.logger.warning(f"FMP Override not found: {override_id} for {sector_id}.")

    async def handle_set_measure_window(self, msg):
        if msg.get("target_node") == self.node_id:
            val = int(msg.get("minutes", 60))
            self._measure_window_minutes = val
            self.logger.info(f"FMP adjusted capacity measurement window to {val} minutes.")

    async def handle_merge_sectors(self, msg):
        if msg.get("target_node") == self.node_id:
            sector_ids = msg.get("sectors", [])
            new_id = msg.get("new_id", "".join(sector_ids))
            
            async with self._state_lock:
                to_merge = [s for s in self.sectors if s.sector_id in sector_ids]
                if len(to_merge) < 2:
                    return
                # Accumulate capacities for the virtual sector
                total_cap = sum(s.declared_capacity_per_hour for s in to_merge)
                
                # Backup originals
                for s in to_merge:
                    self._historic_sectors.append(s)
                    self.sectors.remove(s)
                
                new_sec = SectorCapacity(sector_id=new_id, configuration="MERGED_VIRTUAL", declared_capacity_per_hour=total_cap, current_demand_per_hour=0, status="GREEN", constraint_reason="")
                setattr(new_sec, 'is_virtual', True)
                setattr(new_sec, 'base_sectors', sector_ids)
                self.sectors.append(new_sec)
                self.logger.info(f"FMP merged sectors {sector_ids} into {new_id} with combined capacity {total_cap}.")

    async def handle_apply_configuration(self, msg):
        if msg.get("target_node") == self.node_id:
            config_name = msg.get("config_name")
            # This legacy handler is now superseded by the AIXM-based configuration flow.
            # We keep the method signature for compatibility but it will be moved to a 
            # named-configuration lookup in the future.
            self.logger.warning(f"Legacy APPLY_CONFIGURATION called for '{config_name}'. Use /api/config/load instead.")

            
    async def handle_rad_update(self, msg: dict):
        """Called when a dynamic RAD rule activation/deactivation is broadcast."""
        rule_id = msg.get("rule_id")
        active = msg.get("active", True)
        if rule_id:
            success = RAD_VALIDATOR.update_rule_status(rule_id, active)
            if success:
                self.logger.info(f"RAD rule {rule_id} status updated to: {'ACTIVE' if active else 'INACTIVE'}")
            else:
                self.logger.warning(f"RAD rule {rule_id} not found in validator.")

    async def handle_aoc_ready(self, msg: dict):
        """Called when a flight is ready to fly earlier (REA from AOC)"""
        flight_id = msg.get("flight_id")
        self.logger.info(f"FMP Received REA for {flight_id}. Checking for scavenging opportunities...")
        
        recalc_count = 0
        async with self._state_lock:
            # Phase 25: Check both pending and active slots for scavenging
            for warn_id, slots in list(self.active_slots.items()):
                slots_copy = [s.model_copy() for s in slots]
                found = False
                for s in slots_copy:
                    if s.flight_id == flight_id:
                        s.delay = max(0, s.delay - 5)
                        new_ctot = datetime.fromisoformat(s.etot) + timedelta(minutes=s.delay)
                        s.ctot = new_ctot.isoformat()
                        self.logger.info(f"SCAVENGED: Reduced delay for {flight_id} by 5m.")
                        found = True
                
                if found:
                    self.active_slots[warn_id] = slots_copy
                    cons = DistributedFlowConsensus(
                        consensus_id=f"CONS_{self.node_id}_{uuid.uuid4().hex[:6]}",
                        referencing_warning_id=warn_id,
                        participating_nodes=[self.node_id], # Simplified for re-broadcast
                        final_action_plan=["REA_DRIVEN_SCAVENGING"],
                        slot_table=slots_copy
                    )
                    await self.emit("ddfn.flow.consensus", cons)
                    recalc_count += 1
        
        if recalc_count == 0:
            self.logger.info(f"REA for {flight_id} ignored - no active regulation found.")

    async def handle_fmp_approval(self, msg):
        """Called when UI dictates approval of the pending consensus"""
        if msg.get("target_node") == self.node_id:
            warn_id = msg.get("warning_id")
            action = msg.get("action")
            
            if warn_id in self.pending_warnings and self.pending_warnings[warn_id]["status"] == "PENDING_HITL_APPROVAL":
                if action == "APPROVE":
                    self.logger.info(f"FMP explicitly approved proposals for {warn_id}! Emitting Consensus.")
                    warning_data = self.pending_warnings[warn_id]
                    slots = warning_data["slots"]
                    self.active_slots[warn_id] = slots
                    
                    cons = DistributedFlowConsensus(
                        consensus_id=f"CONS_{self.node_id}_{uuid.uuid4().hex[:6]}",
                        referencing_warning_id=warn_id,
                        participating_nodes=list(warning_data["participating_nodes"]),
                        final_action_plan=["CASA_MANDATED_CTOTS"],
                        slot_table=slots
                    )
                    await self.emit("ddfn.flow.consensus", cons)
                else:
                    self.logger.warning(f"FMP REJECTED CASA proposals for {warn_id}.")
                self.pending_warnings.pop(warn_id, None)

    async def handle_slot_swap(self, msg):
        """Operator manually swapped delays between two flights in the Slot List."""
        target = msg.get("target_node", "")
        if target == self.node_id or target == "":
            warn_id = msg.get("warning_id")
            fid1 = msg.get("flight_id_1")
            fid2 = msg.get("flight_id_2")
            
            if warn_id in self.active_slots:
                slots = self.active_slots[warn_id]
                s1 = next((s for s in slots if s.flight_id == fid1), None)
                s2 = next((s for s in slots if s.flight_id == fid2), None)
                
                if s1 and s2:
                    # --- PHASE 21: SECONDARY RAD VALIDATION (DEFENSE-IN-DEPTH) ---
                    # We need to compute the temporary trajectories with new CTOTs
                    # (In this prototype, we check the existing trajectory object)
                    # For a real system, changing CTOT might change the trajectory (Step-climb, speed, etc.)
                    # Here we just validate the current trajectory against RAD.
                    
                    # We need to find the full trajectory object from FDPS
                    fl1 = self.fdps.flights.get(fid1)
                    fl2 = self.fdps.flights.get(fid2)
                    
                    if fl1 and fl2:
                        valid1, err1 = RAD_VALIDATOR.is_valid(fl1)
                        valid2, err2 = RAD_VALIDATOR.is_valid(fl2)
                        
                        if not valid1 or not valid2:
                            err_msg = err1 or err2
                            self.logger.warning(f"FMP SLOT SWAP REJECTED by RAD: {err_msg}")
                            return
                    
                    self.logger.info(f"FMP SLOT SWAP: Trading delays between {fid1} and {fid2}")
                    # Swap delays
                    d1, d2 = s1.delay, s2.delay
                    s1.delay = d2
                    s2.delay = d1
                    
                    # Recalculate CTOTs
                    e1 = datetime.fromisoformat(s1.etot)
                    e2 = datetime.fromisoformat(s2.etot)
                    s1.ctot = (e1 + timedelta(minutes=s1.delay)).isoformat()
                    s2.ctot = (e2 + timedelta(minutes=s2.delay)).isoformat()
                    
                    s1.locked = True
                    s2.locked = True
                    s1.status = "MANUALLY_SWAPPED"
                    s2.status = "MANUALLY_SWAPPED"
                    
                    # Re-emit Consensus with updated table
                    cons = DistributedFlowConsensus(
                        consensus_id=f"CONS_{self.node_id}_UPDATE_{uuid.uuid4().hex[:6]}",
                        referencing_warning_id=warn_id,
                        participating_nodes=[self.node_id], # simplified update
                        final_action_plan=[], # update doesn't need to repeat all actions
                        slot_table=slots
                    )
                    await self.emit("ddfn.flow.consensus", cons)


    async def handle_handover_advisory(self, msg):
        """A neighboring node is handing over a flight to us."""
        fid = msg.get("flight_id")
        exit_fix = msg.get("exit_fix")
        
        # Only accept if the exit fix is known to us (it's an entry fix for our FIR)
        if exit_fix in self.waypoint_db:
            async with self._state_lock:
                if fid in self.fdps.flights:
                    return # Already tracking
            
            self.logger.info(f"RESUMING tracking for relayed flight {fid} via {exit_fix}.")
            
            # Reconstruct trajectory from handover point
            exit_time = datetime.fromisoformat(msg.get("exit_time").replace('Z', '+00:00'))
            fl = msg.get("fl")
            dest = msg.get("destination")
            rem_route = msg.get("remaining_route")
            
            # Calculate trajectory from exit_fix onwards
            new_flt = FlightTrajectory.from_flight_plan(
                flight_id=fid,
                origin=exit_fix, 
                destination=dest,
                departure_time=exit_time,
                cruise_fl=fl,
                route_string=rem_route,
                waypoint_db=self.waypoint_db
            )
            
            self.fdps.add_flight(new_flt)
            
            # If it exits our FIR too, relay it further
            if new_flt.exit_fix:
                await self._emit_handover(new_flt)

    async def _emit_handover(self, flight: FlightTrajectory):
        """Broadcast a handover advisory so neighbors can pick up the flight."""
        if not flight.exit_time:
            return
            
        advisory = HandoverAdvisory(
            flight_id=flight.flight_id,
            exit_fix=flight.exit_fix,
            exit_time=flight.exit_time.isoformat(),
            fl=flight.cruise_fl,
            destination=flight.destination,
            remaining_route=flight.remaining_route,
            originating_node=self.node_id
        )
        await self.emit("ddfn.relay.handover", advisory)
        self.logger.info(f"RELAYED flight {flight.flight_id} to neighbors via {flight.exit_fix}.")

    async def handle_consensus(self, msg):
        cid = msg.get("consensus_id", "")
        # --- Idempotency: skip replayed consensus ---
        if self.persistence.is_processed(cid):
            return
            
        async with self._state_lock:
            self.persistence.mark_processed(cid)
            
            # PHASE 25: Sync local FDPS trajectories with the agreed CTOTs
            slot_table = msg.get("slot_table", [])
            for slot in slot_table:
                fid = slot.get("flight_id")
                ctot_str = slot.get("ctot")
                if fid in self.fdps.flights:
                    try:
                        new_ctot = datetime.fromisoformat(ctot_str.replace('Z', '+00:00'))
                        flt = self.fdps.flights[fid]
                        
                        # Most Restrictive CTOT logic: Only apply if it's LATER than current
                        if new_ctot > flt.departure_time:
                            self.logger.info(f"Syncing trajectory for {fid}: New CTOT {new_ctot.time()}")
                            # Re-solve trajectory with new departure time
                            new_traj = FlightTrajectory.from_flight_plan(
                                flight_id=fid,
                                origin=flt.origin,
                                destination=flt.destination,
                                departure_time=new_ctot,
                                cruise_fl=flt.cruise_fl,
                                route_string=flt.route_string,
                                waypoint_db=self.waypoint_db
                            )
                            self.fdps.flights[fid] = new_traj
                    except Exception as e:
                        self.logger.error(f"Failed to sync trajectory for {fid}: {e}")



async def main():
    parser = argparse.ArgumentParser(description='Run a standalone DDFN FMP Node Service.')
    parser.add_argument('--node_id', type=str, help='Optional ID of the node. Default is FMP_[port]')
    parser.add_argument("--port", type=int, help="Optional port for the local UI/API")
    parser.add_argument('--broker', type=str, default='ws://127.0.0.1:8001/ws', help='WebSocket broker URL')
    parser.add_argument('--aixm', type=str, help='Path to AIXM 4.5 XML file')
    args = parser.parse_args()

    # Derived port logic
    port_map_legacy = {"LFFF": 8010, "EDDD": 8011, "EGTT": 8012}
    fir_prefix = args.node_id[:4] if args.node_id else ""
    http_port = args.port or port_map_legacy.get(fir_prefix, 8080)

    # If node_id not provided, use a default based on port
    if not args.node_id:
        args.node_id = f"FMP_{http_port}"

    # 1. Load AIXM if provided
    if args.aixm:
        load_aixm_to_registry(args.aixm)

    network = NetworkClient(args.broker)
    node_id_full = f"{args.node_id}_DDFN_NODE"
    
    # Initialize with NO hardcoded sectors - force use of AIXM or setup via Airspace Config
    node = FMPNode(node_id_full, network, [], waypoint_db=WAYPOINTS)
    
    # CLI-based auto-configuration is deprecated. Configuration is now managed via the dashboard.
    if args.aixm:
        node.logger.info(f"AIXM source provided via CLI: {args.aixm}. Please configure the FIR in the dashboard.")
        node.aixm_source_file = args.aixm

    # Isolated Dashboard HTTP Server
    app = FastAPI(title=f"FMP Dashboard - {args.node_id}")

    @app.get("/metadata")
    async def get_metadata():
        from ddfn_v2.services.rad_validator import VALIDATOR
        return {
            "node_id": node.node_id,
            "status": "DDFN True Distributed Local FMP",
            "sectors": [dataclasses.asdict(s) for s in node.sectors],
            "rad_restrictions": [dataclasses.asdict(r) for r in VALIDATOR.rules]
        }

    @app.get("/metrics/node/{req_node_id}")
    async def get_node_metrics(req_node_id: str):
        async with node._state_lock:
            return {
                "node_id": node.node_id,
                "sectors": [dataclasses.asdict(s) for s in node.sectors],
                "flights": node._latest_inventory
            }

    @app.post("/api/sectors/window")
    async def api_set_window(data: SetWindowRequest):
        # Request is validated by Pydantic model
        await node.network.publish("ddfn.fmp.command", {
            "message_type": "SET_MEASURE_WINDOW",
            "target_node": data.node_id,
            "measure_window": data.measure_window
        })
        return {"status": "success"}

    @app.post("/api/sectors/merge")
    async def api_merge_sectors(data: MergeSectorsRequest):
        # Request is validated by Pydantic model
        await node.network.publish("ddfn.fmp.command", {
            "message_type": "MERGE_SECTORS",
            "target_node": data.target_node,
            "sector_ids": data.sector_ids,
            "virtual_id": data.virtual_id
        })
        return {"status": "success"}

    @app.get("/api/rad")
    async def get_rad_rules():
        """Returns the list of RAD rules from the validator."""
        if hasattr(node, 'rad_validator'):
            return {"rules": [dataclasses.asdict(r) for r in node.rad_validator.rules]}
        # Fallback to a standalone validator if node not fully init
        from ddfn_v2.services.rad_validator import RADValidator
        v = RADValidator()
        return {"rules": [dataclasses.asdict(r) for r in v.rules]}

    @app.post("/api/rad/toggle")
    async def toggle_rad_rule(data: RADToggleRequest):
        """Activates or deactivates a RAD rule."""
        # Request is validated by Pydantic model
        if hasattr(node, 'rad_validator'):
            for r in node.rad_validator.rules:
                if r.rule_id == data.rule_id:
                    r.active = data.active
                    return {"status": "success", "rule_id": data.rule_id, "active": data.active}
        return {"status": "error", "message": "Rule not found or node not initialized"}

    @app.get("/api/configurations")
    async def api_get_configurations():
        # This legacy endpoint should ideally return named configs from local storage
        return {
            "configurations": node.list_saved_configs()
        }

    @app.post("/api/configurations/apply")
    async def api_apply_configuration(data: ApplyConfigurationRequest):
        # Request is validated by Pydantic model
        await node.network.publish("ddfn.fmp.command", {
            "message_type": "APPLY_CONFIGURATION",
            "target_node": data.target_node,
            "config_name": data.config_name
        })
        return {"status": "success"}


    @app.get("/api/aixm/firs")
    async def api_get_aixm_firs(file_path: str):
        # Validate file path to prevent directory traversal
        try:
            validated_path = validate_file_path_for_aixm(file_path, must_exist=True)
        except ValueError as e:
            node.logger.warning(f"Invalid file path in /api/aixm/firs: {e}")
            return {"status": "error", "message": f"Invalid file path: {e}"}

        try:
            parser = AIXMParser(validated_path)
            sectors = parser.extract_sectors()
            firs = sorted(list(set(s.parent_fir for s in sectors if s.parent_fir)))
            node.logger.info(f"AIXM Source: {validated_path}. Found {len(sectors)} sectors and {len(firs)} FIRs.")
            return {"status": "success", "firs": firs}
        except Exception as e:
            node.logger.error(f"Error extracting FIRs: {str(e)}")
            return {"status": "error", "message": str(e)}

    @app.get("/api/aixm/sectors")
    async def api_get_aixm_sectors(file_path: str, fir_id: str):
        # Validate file path and FIR ID
        try:
            validated_path = validate_file_path_for_aixm(file_path, must_exist=True)
        except ValueError as e:
            node.logger.warning(f"Invalid file path in /api/aixm/sectors: {e}")
            return {"status": "error", "message": f"Invalid file path: {e}"}

        try:
            parser = AIXMParser(validated_path)
            all_sectors = parser.extract_sectors()
            # Filter by parent_fir prefix
            filtered = [s for s in all_sectors if s.parent_fir == fir_id]
            node.logger.info(f"Extracted {len(filtered)} sectors for FIR {fir_id} out of {len(all_sectors)} total.")
            return {
                "status": "success",
                "sectors": [dataclasses.asdict(s) for s in filtered]
            }
        except Exception as e:
            node.logger.error(f"Error extracting sectors: {str(e)}")
            return {"status": "error", "message": str(e)}

    @app.post("/api/config/apply_aixm")
    async def api_apply_aixm_config(data: ApplyAIXMConfigRequest):
        # Request is validated by Pydantic model
        node.logger.info(f"API: Apply AIXM. File: {data.file_path}, FIR: {data.fir_id}, Config Name: {data.config_name}, Sectors: {len(data.sectors)}")

        try:
            # Ensure geometries are loaded in registry
            load_aixm_to_registry(data.file_path)

            new_sectors = []
            for s_info in data.sectors:
                s_id = s_info["id"]
                if s_id in GLOBAL_SECTORS:
                    geo = GLOBAL_SECTORS[s_id]
                    # Use manual FLs if provided, else use AIXM defaults
                    lo = s_info.get("fl_lower", geo.fl_lower)
                    hi = s_info.get("fl_upper", geo.fl_upper)

                    new_sectors.append(SectorCapacity(
                        sector_id=s_id,
                        configuration="AIXM_DYNAMIC",
                        declared_capacity_per_hour=40,
                        current_demand_per_hour=0,
                        status="GREEN",
                        fl_lower=lo,
                        fl_upper=hi
                    ))

            async with node._state_lock:
                node.sectors = new_sectors
                node.aixm_source_file = data.file_path
                node.aixm_source_fir = data.fir_id
                node.save_local_config(config_name=data.config_name)

            return {"status": "success", "message": f"Applied {len(new_sectors)} sectors."}
        except Exception as e:
            node.logger.error(f"Error applying AIXM config: {e}")
            return {"status": "error", "message": str(e)}

    @app.get("/api/config/aixm_source")
    async def api_get_aixm_source():
        return {
            "file_path": node.aixm_source_file,
            "fir_id": node.aixm_source_fir,
            "config_name": node.active_config_name
        }

    @app.get("/api/config/list")
    async def api_list_configs():
        return {"status": "success", "configs": node.list_saved_configs()}

    @app.get("/api/setup/status")
    async def api_get_setup_status():
        return {
            "is_configured": node.is_configured,
            "node_id": node.node_id
        }

    @app.post("/api/setup/configure")
    async def api_setup_configure(data: SetupConfigurationRequest):
        # Request is validated by Pydantic model
        node.logger.info(f"Received setup configuration request for FIR: {data.fir_id}")

        try:
            # 1. Load AIXM
            load_aixm_to_registry(data.file_path)

            # 2. Extract and assign sectors
            from ddfn_v2.eng.airspace import get_fir_sectors as get_global_fir_sectors
            aixm_sectors = get_global_fir_sectors(data.fir_id)
            if not aixm_sectors:
                return {"status": "error", "message": f"No sectors found for FIR {data.fir_id} in {data.file_path}"}

            config_name = data.config_name or f"{data.fir_id} Config"

            async with node._state_lock:
                node.sectors = [from_dict(SectorCapacity, s) for s in aixm_sectors]
                node.aixm_source_file = data.file_path
                node.aixm_source_fir = data.fir_id
                node._measure_window_minutes = data.window_size
                node.is_configured = True
                node.save_local_config(config_name=config_name)

            # 3. Reprocess any flights received during unconfigured state
            await node._reprocess_all_flights()

            return {"status": "success", "message": f"Node configured for {data.fir_id} with {len(node.sectors)} sectors as '{config_name}'"}
        except Exception as e:
            node.logger.error(f"Setup failure: {e}")
            return {"status": "error", "message": str(e)}

    @app.get("/api/config/load")
    async def api_load_config(name: str):
        # Validate config name
        try:
            from ddfn_v2.util.validators import validate_config_name
            validate_config_name(name)
        except ValueError as e:
            return {"status": "error", "message": f"Invalid configuration name: {e}"}

        success = node.load_named_config(name)
        if success:
            return {"status": "success"}
        return {"status": "error", "message": "Configuration not found"}

    @app.delete("/api/config/delete/{name}")
    async def api_delete_config(name: str):
        # Validate config name
        try:
            from ddfn_v2.util.validators import validate_config_name
            validate_config_name(name)
        except ValueError as e:
            return {"status": "error", "message": f"Invalid configuration name: {e}"}

        node.delete_named_config(name)
        return {"status": "success"}

    @app.post("/api/aixm/upload")
    async def api_upload_aixm(file: UploadFile = File(...)):
        """Handle AIXM file upload and save it locally for processing."""
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        
        try:
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            node.logger.info(f"API: AIXM file uploaded to {file_path}")
            return {"status": "success", "file_path": file_path}
        except Exception as e:
            node.logger.error(f"Upload failure: {e}")
            return {"status": "error", "message": str(e)}

    @app.get("/api/aixm/airports")
    async def api_get_aixm_airports(file_path: str, fir_id: str = None):
        # Validate file path
        try:
            validated_path = validate_file_path_for_aixm(file_path, must_exist=True)
        except ValueError as e:
            node.logger.warning(f"Invalid file path in /api/aixm/airports: {e}")
            return {"status": "error", "message": f"Invalid file path: {e}"}

        try:
            parser = AIXMParser(validated_path)
            airports = parser.extract_airports(fir_id=fir_id)
            node.logger.info(f"API: Extracted {len(airports)} airports for FIR {fir_id} from {validated_path}")
            return {"status": "success", "airports": airports}
        except Exception as e:
            node.logger.error(f"Error extracting airports: {str(e)}")
            return {"status": "error", "message": str(e)}

    @app.get("/api/aixm/waypoints")
    async def api_get_aixm_waypoints(file_path: str, fir_id: str = None):
        # Validate file path
        try:
            validated_path = validate_file_path_for_aixm(file_path, must_exist=True)
        except ValueError as e:
            node.logger.warning(f"Invalid file path in /api/aixm/waypoints: {e}")
            return {"status": "error", "message": f"Invalid file path: {e}"}

        try:
            parser = AIXMParser(validated_path)
            waypoints = parser.extract_waypoints(fir_id=fir_id)
            node.logger.info(f"API: Extracted {len(waypoints)} waypoints for FIR {fir_id} from {validated_path}")
            return {"status": "success", "waypoints": waypoints}
        except Exception as e:
            node.logger.error(f"Error extracting waypoints: {str(e)}")
            return {"status": "error", "message": str(e)}

    @app.get("/api/aixm/routes")
    async def api_get_aixm_routes(file_path: str, fir_id: str = None):
        # Validate file path
        try:
            validated_path = validate_file_path_for_aixm(file_path, must_exist=True)
        except ValueError as e:
            node.logger.warning(f"Invalid file path in /api/aixm/routes: {e}")
            return {"status": "error", "message": f"Invalid file path: {e}"}

        try:
            parser = AIXMParser(validated_path)
            routes = parser.extract_routes(fir_id=fir_id)
            node.logger.info(f"API: Extracted {len(routes)} routes for FIR {fir_id} from {validated_path}")
            return {"status": "success", "routes": routes}
        except Exception as e:
            node.logger.error(f"Error extracting routes: {str(e)}")
            return {"status": "error", "message": str(e)}

    @app.post("/api/sectors/override")
    async def api_override_capacity(data: CapacityOverrideRequest):
        # Request is validated by Pydantic model
        await node.network.publish("ddfn.fmp.command", {
            "message_type": "MANUAL_CAPACITY_OVERRIDE",
            "target_node": data.target_node,
            "sector": data.sector,
            "capacity": data.capacity,
            "start_time": data.start_time,
            "end_time": data.end_time,
            "reason": data.reason
        })
        return {"status": "success"}

    @app.get("/", response_class=HTMLResponse)
    async def get_index():
        # Project root is 3 levels up from src/ddfn_v2/services/
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        dashboard_dir = os.path.join(root_dir, "web", "fmp_dashboard")
        index_path = os.path.join(dashboard_dir, "index.html")
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Inject the active node directly into the HTML context
        html = html.replace("window.ACTIVE_NODE_ID = null;", f"window.ACTIVE_NODE_ID = '{args.node_id}_DDFN_NODE';")
        
        current_config = node.active_config_name
        node.logger.info(f"Serving index.html. Active Config: '{current_config}'")
        
        # Super robust ID-based replacements
        # Replacement for <div id="config-name-display" ...>Config: Default</div>
        # We look for the ID and the text inside.
        import re
        html = re.sub(r'(id="config-name-display"[^>]*>)[^<]*(</div>)', rf'\1Config: {current_config}\2', html)
        if current_config != "Default":
            html = re.sub(r'(id="active-node-badge"[^>]*>)[^<]*(</div>)', rf'\1Config: {current_config}\2', html)
        else:
            html = re.sub(r'(id="active-node-badge"[^>]*>)[^<]*(</div>)', rf'\1Node: {args.node_id}\2', html)
        
        return html
        
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    dashboard_static = os.path.join(root_dir, "web", "fmp_dashboard")
    app.mount("/", StaticFiles(directory=dashboard_static), name="static")
    
    # API / UI - already calculated at startup
    node.logger.info(f"FMP Node logic started. Serving isolated UI on http://127.0.0.1:{http_port}")

    config = uvicorn.Config(app, host="127.0.0.1", port=http_port, log_level="info")
    server = uvicorn.Server(config)
    
    # Run both the background FMP task and the web server
    await asyncio.gather(
        node.start(),
        server.serve()
    )

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    asyncio.run(main())


