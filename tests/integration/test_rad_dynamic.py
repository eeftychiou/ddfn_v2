import sys
import os
import datetime

# Add the project root to sys.path to import modules
from ddfn_v2.services.rad_validator import RADValidator, RADRule
from ddfn_v2.eng.trajectories import FlightTrajectory

def test_dynamic_rad_activation():
    """
    TDD Phase 1: RED
    This test verifies that we can toggle RAD rules.
    It should FAIL because the 'active' attribute and 'update_rule_status' method
    do not exist yet in rad_validator.py.
    """
    print("Running Test: test_dynamic_rad_activation...")
    
    validator = RADValidator()
    
    # Define a rule for DVR restricted for FL < 280
    rule_id = "RAD_EG_001"
    
    # Create a trajectory that violates this rule
    # DVR is in the route_string, and cruise_fl is 250 (< 280)
    traj = FlightTrajectory(
        flight_id="BAW123",
        origin="EGLL",
        destination="LFPG",
        departure_time=datetime.datetime.now(),
        cruise_fl=250,
        tas_kt=420.0,
        route_string="EGLL DVR LFPG"
    )
    
    # 1. Verify rule is active by default and blocks trajectory
    is_valid, msg = validator.is_valid(traj)
    print(f"Initial check (should be blocked): valid={is_valid}, msg={msg}")
    assert is_valid is False, "Rule should block trajectory by default"
    assert rule_id in msg, f"Error message should mention {rule_id}"
    
    # 2. Deactivate the rule
    print(f"Deactivating rule {rule_id}...")
    try:
        validator.update_rule_status(rule_id, active=False)
    except AttributeError:
        print("FAIL: 'update_rule_status' method does not exist.")
        raise
    
    # 3. Verify trajectory is now valid
    is_valid, msg = validator.is_valid(traj)
    print(f"Post-deactivation check (should be allowed): valid={is_valid}, msg={msg}")
    assert is_valid is True, "Trajectory should be valid after rule deactivation"
    
    # 4. Reactivate the rule
    print(f"Reactivating rule {rule_id}...")
    validator.update_rule_status(rule_id, active=True)
    
    # 5. Verify it's blocked again
    is_valid, msg = validator.is_valid(traj)
    print(f"Post-reactivation check (should be blocked): valid={is_valid}, msg={msg}")
    assert is_valid is False, "Rule should block trajectory again after reactivation"
    
    print("SUCCESS: Dynamic RAD Rule toggling works!")

if __name__ == "__main__":
    try:
        test_dynamic_rad_activation()
    except Exception as e:
        print(f"\nTEST FAILED as expected for RED phase: {e}")
        sys.exit(1)
