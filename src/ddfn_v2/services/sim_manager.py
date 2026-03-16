import asyncio
import logging
import argparse
import datetime
import uuid
import dataclasses
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn
import os

from ddfn_v2.core.network import NetworkClient
from ddfn_v2.eng import airspace
from ddfn_v2.util.aixm_tool import AIXMParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("SimManager")

network_client = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global network_client
    # Connect to the broker during startup
    broker_url = os.environ.get("BROKER_URL", "ws://127.0.0.1:8001/ws")
    network_client = NetworkClient(broker_url)
    await network_client.connect("SIM_MANAGER")
    logger.info("Connected to SWIM Broker.")
    yield
    # Cleanup during shutdown
    logger.info("Disconnecting from SWIM Broker.")

app = FastAPI(title="DDFN Simulation Manager", lifespan=lifespan)

# Mount static files for the dashboard
# Project root is 3 levels up from src/ddfn_v2/services/
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
dashboard_dir = os.path.join(root_dir, "web", "sim_dashboard")
app.mount("/static", StaticFiles(directory=dashboard_dir, html=True), name="static")

class FlightInjectionRequest(BaseModel):
    flight_id: str
    origin: str
    destination: str
    route_string: str
    cruise_fl: int
    departure_offset_mins: int

@app.post("/api/aixm/load")
async def load_aixm(req: dict):
    """
    Load AIXM from a provided file path on the server.
    In a real app, this would handle file uploads.
    """
    file_path = req.get("file_path")
    if not file_path:
        return {"status": "error", "message": "No file path provided."}
    
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}
    
    try:
        airspace.load_from_aixm(file_path)
        return {"status": "success", "message": f"Loaded sectors from {file_path}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/aixm/sectors")
async def get_sectors():
    """Returns the list of currently loaded sectors."""
    sectors = []
    for s_id, s_geo in airspace.SECTORS.items():
        sectors.append({
            "id": s_id,
            "fir": s_geo.fir,
            "polygon": s_geo.polygon
        })
    return {"status": "success", "sectors": sectors}

@app.post("/api/flights/inject")
async def inject_flight(req: FlightInjectionRequest):
    """API endpoint called by the UI to inject a new flight plan."""
    now = datetime.datetime.now(datetime.timezone.utc)
    dept_time = now + datetime.timedelta(minutes=req.departure_offset_mins)
    
    msg = {
        "message_type": "FLIGHT_PLAN_FILED",
        "flight_id": req.flight_id,
        "origin": req.origin,
        "destination": req.destination,
        "route_string": req.route_string,
        "cruise_fl": req.cruise_fl,
        "departure_time": dept_time.isoformat()
    }
    
    if network_client:
        await network_client.publish("ddfn.flight.plan", msg)
        logger.info(f"Broadcasted FLIGHT_PLAN_FILED for {req.flight_id}")
        return {"status": "success", "message": f"Flight {req.flight_id} injected."}
    else:
        return {"status": "error", "message": "Network client not initialized."}

@app.get("/")
async def root():
    # Redirect to the static dashboard index
    with open(os.path.join(dashboard_dir, "index.html"), "r") as f:
        html = f.read()
    return HTMLResponse(content=html)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DDFN Simulation Manager")
    parser.add_argument("--broker", default="ws://127.0.0.1:8001/ws", help="Broker WebSocket URL")
    parser.add_argument("--port", type=int, default=8050, help="Port for the Sim Manager UI")
    args = parser.parse_args()

    # Pass broker URL via environment so the lifespan event can read it
    os.environ["BROKER_URL"] = args.broker

    logger.info(f"Starting Simulation Manager on http://127.0.0.1:{args.port}")
    uvicorn.run("ddfn_v2.services.sim_manager:app", host="127.0.0.1", port=args.port, log_level="warning")
