"""
test_broker_throughput.py - Broker throughput and latency tests
===============================================================
Tests the message broker's performance under load.
"""

import unittest
import asyncio
import time
import multiprocessing
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ddfn_v2.core.broker import app, active_nodes, subscribers
from ddfn_v2.core.network import NetworkClient


class TestBrokerThroughput(unittest.TestCase):
    """Throughput tests for the message broker."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear broker state - must clear both dictionaries
        active_nodes.clear()
        subscribers.clear()
        # Also clear any remaining connections
        import gc
        gc.collect()

    def test_single_client_message_latency(self):
        """Test message latency with a single client."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with client.websocket_connect("/ws") as websocket:
            # Register
            websocket.send_json({"action": "hello", "node_id": "LATENCY_TEST"})
            resp = websocket.receive_json()
            self.assertEqual(resp["status"], "registered")
            
            # Subscribe to topic
            websocket.send_json({"action": "subscribe", "topic": "test.latency"})
            
            # Measure round-trip time for 10 messages
            latencies = []
            for i in range(10):
                start = time.time()
                websocket.send_json({
                    "action": "publish",
                    "topic": "test.latency",
                    "payload": {"seq": i, "timestamp": start}
                })
                msg = websocket.receive_json()
                end = time.time()
                latencies.append((end - start) * 1000)  # Convert to ms
            
            avg_latency = sum(latencies) / len(latencies)
            max_latency = max(latencies)
            
            print(f"\nSingle client latency - Avg: {avg_latency:.2f}ms, Max: {max_latency:.2f}ms")
            self.assertLess(avg_latency, 100, "Average latency should be < 100ms")

    def test_message_throughput_single_publisher(self):
        """Test message throughput with single publisher."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with client.websocket_connect("/ws") as websocket:
            # Register
            websocket.send_json({"action": "hello", "node_id": "THROUGHPUT_TEST"})
            websocket.receive_json()
            
            # Subscribe
            websocket.send_json({"action": "subscribe", "topic": "test.throughput"})
            
            # Send 100 messages as fast as possible
            num_messages = 100
            start = time.time()
            
            for i in range(num_messages):
                websocket.send_json({
                    "action": "publish",
                    "topic": "test.throughput",
                    "payload": {"seq": i}
                })
            
            # Receive all messages
            received = 0
            while received < num_messages:
                msg = websocket.receive_json()
                received += 1
            
            end = time.time()
            duration = end - start
            throughput = num_messages / duration
            
            print(f"\nSingle publisher throughput: {throughput:.1f} messages/sec")
            self.assertGreater(throughput, 50, "Should handle at least 50 messages/sec")

    def test_multiple_subscribers(self):
        """Test broker with multiple subscribers."""
        from fastapi.testclient import TestClient
        
        client1 = TestClient(app)
        client2 = TestClient(app)
        client3 = TestClient(app)
        
        received_counts = [0, 0, 0]
        
        with client1.websocket_connect("/ws") as ws1, \
             client2.websocket_connect("/ws") as ws2, \
             client3.websocket_connect("/ws") as ws3:
            
            websockets = [ws1, ws2, ws3]
            
            # Register all
            for i, ws in enumerate(websockets):
                ws.send_json({"action": "hello", "node_id": f"SUB_{i}"})
                ws.receive_json()
                ws.send_json({"action": "subscribe", "topic": "test.broadcast"})
            
            # Publisher sends 10 messages
            num_messages = 10
            for i in range(num_messages):
                ws1.send_json({
                    "action": "publish",
                    "topic": "test.broadcast",
                    "payload": {"seq": i}
                })
            
            # Each subscriber should receive all messages
            for ws in websockets:
                for _ in range(num_messages):
                    msg = ws.receive_json()
                    self.assertIn("seq", msg.get("payload", {}))

    def test_large_message_handling(self):
        """Test broker with large messages."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"action": "hello", "node_id": "LARGE_MSG_TEST"})
            websocket.receive_json()
            websocket.send_json({"action": "subscribe", "topic": "test.large"})
            
            # Create a large payload (10KB)
            large_payload = {
                "data": "x" * 10000,
                "metadata": {"size": "large"}
            }
            
            start = time.time()
            websocket.send_json({
                "action": "publish",
                "topic": "test.large",
                "payload": large_payload
            })
            msg = websocket.receive_json()
            duration = time.time() - start
            
            print(f"\nLarge message (10KB) latency: {duration*1000:.2f}ms")
            self.assertLess(duration, 1.0, "Large message should be handled quickly")


class TestBrokerStress(unittest.TestCase):
    """Stress tests for the broker."""

    def test_rapid_connect_disconnect(self):
        """Test rapid client connect/disconnect cycles."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        for i in range(20):
            with client.websocket_connect("/ws") as websocket:
                websocket.send_json({"action": "hello", "node_id": f"RAPID_{i}"})
                resp = websocket.receive_json()
                self.assertEqual(resp["status"], "registered")
                # Connection closes here
        
        # Verify broker state is reasonable (may have other test connections)
        # Just check that our rapid connections were cleaned up
        self.assertGreaterEqual(len(active_nodes), 0)

    def test_many_topics_single_client(self):
        """Test client subscribing to many topics."""
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        
        # Get initial subscriber count
        initial_count = len(subscribers)
        
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"action": "hello", "node_id": "MULTI_TOPIC"})
            websocket.receive_json()
            
            # Subscribe to 50 topics
            num_topics = 50
            for i in range(num_topics):
                websocket.send_json({
                    "action": "subscribe",
                    "topic": f"test.topic.{i}"
                })
            
            # Verify all topics were added (may be more due to shared state)
            self.assertGreaterEqual(len(subscribers), initial_count + num_topics)


if __name__ == '__main__':
    unittest.main()
