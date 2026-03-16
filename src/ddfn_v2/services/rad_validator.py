"""
rad_validator.py — Route Availability Document (RAD) Validator
==============================================================
Simulates Eurocontrol's RAD logic by enforcing route restrictions.
Used by edge nodes to validate flight plans and slot swaps.
"""

import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from ddfn_v2.eng.trajectories import FlightTrajectory

@dataclass
class RADRule:
    rule_id: str
    description: str
    waypoint: Optional[str] = None  # Affected waypoint
    min_fl: Optional[int] = None   # Restriction below this FL
    max_fl: Optional[int] = None   # Restriction above this FL
    start_time: Optional[str] = None # HH:MM (UTC)
    end_time: Optional[str] = None   # HH:MM (UTC)
    forbidden_origins: Optional[List[str]] = None
    forbidden_destinations: Optional[List[str]] = None
    active: bool = True  # Added for dynamic toggling

class RADValidator:
    def __init__(self, rules_path="rad_rules.json"):
        import json
        import os
        self.rules: List[RADRule] = []
        if not os.path.exists(rules_path) and os.path.exists(os.path.join("data", rules_path)):
            rules_path = os.path.join("data", rules_path)
            
        if os.path.exists(rules_path):
            try:
                with open(rules_path, "r") as f:
                    data = json.load(f)
                    for r in data:
                        # Ensure types are correct after loading from JSON
                        if "max_fl" in r and r["max_fl"] is not None: r["max_fl"] = int(r["max_fl"])
                        if "min_fl" in r and r["min_fl"] is not None: r["min_fl"] = int(r["min_fl"])
                        if "active" in r: r["active"] = bool(r["active"])
                        self.rules.append(RADRule(**r))
            except Exception as e:
                print(f"Failed to load RAD rules: {e}")
        
        if not self.rules:
            # Fallback to defaults if file missing or empty
            self.rules = [
                RADRule(
                    rule_id="RAD_EG_001",
                    description="DVR restricted for FL < 280 (Military area activation)",
                    waypoint="DVR",
                    max_fl=279
                )
            ]

    def is_valid(self, trajectory: FlightTrajectory) -> Tuple[bool, Optional[str]]:
        """
        Validates a trajectory against all active RAD rules.
        Returns (is_valid, error_message).
        """
        # Resolve waypoints from route string if not populated
        # (Assuming trajectory object already has them for simplicity in this prototype)
        
        # 1. Flight Level Check
        fl = trajectory.cruise_fl
        
        # 2. Check each waypoint in the trajectory
        # Note: we need to know WHICH waypoints are in the trajectory.
        # Trajectory has 'route_string' which we can parse again or 'waypoints' (lat, lon).
        # Let's parse the route string for exact waypoint identity.
        tokens = trajectory.route_string.upper().split()
        
        for rule in self.rules:
            # 0. Skip inactive rules
            if not rule.active:
                continue

            # Check if this trajectory hits the restricted waypoint
            if rule.waypoint and rule.waypoint in tokens:
                # 1. Establish violations for this rule
                fl_violation = False
                if rule.min_fl is not None and fl >= rule.min_fl: fl_violation = True
                if rule.max_fl is not None and fl <= rule.max_fl: fl_violation = True

                od_violation = False
                if rule.forbidden_origins is not None:
                    if trajectory.origin in rule.forbidden_origins:
                        od_violation = True
                if rule.forbidden_destinations is not None:
                    if trajectory.destination in rule.forbidden_destinations:
                        od_violation = True

                # 2. Check each constraint type match
                is_fl_match = True
                if rule.min_fl is not None or rule.max_fl is not None:
                    is_fl_match = fl_violation

                is_od_match = True
                if rule.forbidden_origins or rule.forbidden_destinations:
                    is_od_match = od_violation

                is_time_match = True
                if rule.start_time is not None and rule.end_time is not None:
                    try:
                        dep_time = trajectory.departure_time.time()
                        from datetime import time as dt_time
                        start = dt_time.fromisoformat(rule.start_time)
                        end = dt_time.fromisoformat(rule.end_time)
                        if not (start <= dep_time <= end):
                            is_time_match = False
                    except:
                        is_time_match = False 
                elif rule.start_time is not None or rule.end_time is not None:
                    is_time_match = False

                # 4. Global violation check: if all active constraints match
                if is_fl_match and is_od_match and is_time_match:
                     return False, f"RAD Violation {rule.rule_id}: {rule.description}"

        return True, None

    def update_rule_status(self, rule_id: str, active: bool):
        """Dynamically activates or deactivates a rule by its ID."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                rule.active = active
                return True
        return False

# Global instance
VALIDATOR = RADValidator()
