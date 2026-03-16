import datetime
from ddfn_v2.eng.airspace import WAYPOINTS, SECTORS
from ddfn_v2.eng.trajectories import FlightTrajectory, FlightDataProcessingSystem

def test_lfff1a_intersection():
    lfff_set = {"LFPG", "LFMN", "VESAN", "KORER", "NAKID", "OKRIB", "DIJON", "MOLUS", "SBT", "RANUX", "LGL", "AMB", "OKASI", "NEVIL", "BALAN", "VEULE", "KOVIN", "BRANE", "LUMEL"}
    node_wpts = {k: v for k, v in WAYPOINTS.items() if k in lfff_set}
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Simulate a handover from EDDD to LFFF at VESAN
    flt_eddd = FlightTrajectory.from_flight_plan(
        flight_id="DLH101",
        origin="VESAN",
        destination="LEMD",
        departure_time=now,
        cruise_fl=350,
        route_string="KORER NAKID OKRIB BRANE PAMPI LEMD",
        waypoint_db=node_wpts
    )
    
    # Simulate a handover from EGTT to LFFF at BALAN
    flt_egtt = FlightTrajectory.from_flight_plan(
        flight_id="BAW200",
        origin="BALAN",
        destination="LEMD",
        departure_time=now,
        cruise_fl=350,
        route_string="OKASI LERGA PAMPI SOSAL LEMD",
        waypoint_db=node_wpts
    )
    
    print("\n--- Testing EDDD Flight (via VESAN) ---")
    print(f"Waypoints resolved: {flt_eddd.waypoints}")
    print("Routes calculated:")
    for crossing in flt_eddd.route:
        print(f" -> Crosses {crossing.sector_id} at {crossing.estimated_time_over}")
        
    print("\n--- Testing EGTT Flight (via BALAN) ---")
    print(f"Waypoints resolved: {flt_egtt.waypoints}")
    print("Routes calculated:")
    for crossing in flt_egtt.route:
        print(f" -> Crosses {crossing.sector_id} at {crossing.estimated_time_over}")

if __name__ == '__main__':
    test_lfff1a_intersection()
