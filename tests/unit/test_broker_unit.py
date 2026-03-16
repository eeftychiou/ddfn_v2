import pytest
import asyncio
import json
from fastapi.testclient import TestClient
from ddfn_v2.core.broker import app, active_nodes, subscribers
from ddfn_v2.core.network import NetworkClient

@pytest.fixture(autouse=True)
def cleanup():
    active_nodes.clear()
    subscribers.clear()
    yield

def test_broker_hello():
    """
    Test that the broker handles 'hello' action via WebSocket.
    """
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"action": "hello", "node_id": "TEST_NODE"})
        resp = websocket.receive_json()
        assert resp["status"] == "registered"
        assert "TEST_NODE" in active_nodes.values()

def test_broker_subscribe():
    """
    Test that the broker handles 'subscribe' action.
    """
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json({"action": "subscribe", "topic": "test.topic"})
        assert "test.topic" in subscribers
        assert websocket in subscribers["test.topic"]

@pytest.mark.asyncio
async def test_network_client_connection_failure():
    """
    Test NetworkClient connection failure.
    """
    client = NetworkClient(broker_url="ws://localhost:9999/ws")
    with pytest.raises(Exception):
        await client.connect("TEST_NODE")

def test_broker_duplicate_node_id_rejected():
    """
    Test that the broker rejects duplicate node IDs.
    """
    client1 = TestClient(app)
    client2 = TestClient(app)
    with client1.websocket_connect("/ws") as ws1:
        ws1.send_json({"action": "hello", "node_id": "SAME_ID"})
        resp1 = ws1.receive_json()
        assert resp1["status"] == "registered"
        
        with client2.websocket_connect("/ws") as ws2:
            ws2.send_json({"action": "hello", "node_id": "SAME_ID"})
            resp2 = ws2.receive_json()
            assert resp2["error"] == "node_id_taken"
            
            # Verify internal state: only one node with this ID
            nodes = list(active_nodes.values())
            assert nodes.count("SAME_ID") == 1
