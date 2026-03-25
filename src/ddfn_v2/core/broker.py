import asyncio
import json
import logging
import uvicorn
import weakref
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Security
from fastapi.security import APIKeyHeader
from typing import Dict, List, Any, Set

from ddfn_v2.core.audit import SWIMAuditLog
from ddfn_v2.core.auth import verify_api_key, API_KEY_NAME
from ddfn_v2.core.config import config

# Configure brief logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - Broker - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Broker")

auditor = SWIMAuditLog()

app = FastAPI(title="DDFN SWIM Message Broker")

# topic -> list of websockets
subscribers: Dict[str, List[WebSocket]] = {}
active_nodes: Dict[WebSocket, str] = {}

# Track active tasks for proper cleanup
_active_tasks: weakref.WeakSet = weakref.WeakSet()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_subscriptions = []
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                action = payload.get("action")
                
                if action == "hello":
                    node_id = payload.get("node_id")
                    if node_id:
                        # Check if node_id already exists from a DIFFERENT websocket
                        is_taken = False
                        for ws, existing_id in active_nodes.items():
                            if existing_id == node_id and ws != websocket:
                                is_taken = True
                                break
                        
                        if is_taken:
                            logger.warning(f"Registration rejected for '{node_id}': ID already in use.")
                            await websocket.send_json({"error": "node_id_taken", "node_id": node_id})
                            return # Terminate this connection
                                
                        active_nodes[websocket] = node_id
                        logger.info(f"Node '{node_id}' formally registered.")
                        await websocket.send_json({"status": "registered", "node_id": node_id})
                        
                elif action == "subscribe":
                    topic = payload.get("topic")
                    if topic not in subscribers:
                        subscribers[topic] = []
                    if websocket not in subscribers[topic]:
                        subscribers[topic].append(websocket)
                        client_subscriptions.append(topic)
                    logger.debug(f"Client subscribed to {topic}")
                    
                elif action == "publish":
                    topic = payload.get("topic")
                    message = payload.get("message")
                    
                    # Log to persistent audit storage (now non-blocking)
                    if isinstance(message, dict):
                        auditor.log_event(topic, message)
                        
                    if topic in subscribers:
                        # Broadcast concurrently with proper task cleanup
                        async def send_to_ws(ws, t, m):
                            try:
                                await ws.send_json({"topic": t, "message": m})
                            except Exception:
                                pass

                        tasks = [asyncio.create_task(send_to_ws(ws, topic, message)) 
                                 for ws in subscribers[topic]]
                        
                        # Track tasks for cleanup
                        for task in tasks:
                            _active_tasks.add(task)
                            task.add_done_callback(lambda t: _active_tasks.discard(t))
                        
                        # Wait for all tasks with timeout to prevent hanging
                        try:
                            await asyncio.wait_for(
                                asyncio.gather(*tasks, return_exceptions=True),
                                timeout=5.0
                            )
                        except asyncio.TimeoutError:
                            logger.warning(f"Publish to topic {topic} timed out")
                            # Cancel remaining tasks
                            for task in tasks:
                                if not task.done():
                                    task.cancel()
                            
            except json.JSONDecodeError:
                logger.error("Received malformed JSON")
                
    except WebSocketDisconnect:
        # Cleanup subscriptions on disconnect
        if websocket in active_nodes:
            logger.info(f"Node {active_nodes[websocket]} disconnected.")
            del active_nodes[websocket]
            
        for topic in client_subscriptions:
            if topic in subscribers and websocket in subscribers[topic]:
                subscribers[topic].remove(websocket)
        logger.debug("A client disconnected and was cleaned up.")

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
import sqlite3

os.makedirs(config.LOGS_DIR, exist_ok=True)

@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    Returns 200 OK if broker is operational.
    """
    return {
        "status": "healthy",
        "service": "broker",
        "active_nodes": len(active_nodes),
        "active_topics": len(subscribers),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/nodes", dependencies=[Security(verify_api_key)])
async def api_get_nodes():
    return {"nodes": list(active_nodes.values())}

@app.get("/api/audit", dependencies=[Security(verify_api_key)])
async def api_get_audit():
    with sqlite3.connect(config.AUDIT_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, topic, message_type, source_node, payload FROM audit_log ORDER BY id DESC LIMIT 100")
        rows = cursor.fetchall()
        msgs = [{"timestamp": r[0], "topic": r[1], "message_type": r[2], "source_node": r[3], "payload": json.loads(r[4])} for r in rows]
        return {"logs": msgs}

@app.get("/", response_class=HTMLResponse)
async def get_index():
    # Adjusted path for web/broker_dashboard
    with open(os.path.join(config.PROJECT_ROOT, "web", "broker_dashboard", "index.html"), "r", encoding="utf-8") as f:
        return f.read()

app.mount("/", StaticFiles(directory=os.path.join(config.PROJECT_ROOT, "web", "broker_dashboard")), name="static")

if __name__ == "__main__":
    logger.info("Starting DDFN V2 Message Broker on ws://127.0.0.1:8001/ws")
    uvicorn.run(app, host="127.0.0.1", port=8001, ws_ping_interval=30, ws_ping_timeout=30)
