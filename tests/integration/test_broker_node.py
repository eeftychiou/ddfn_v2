import unittest
import time
import socket
from ddfn_v2.core.broker import Broker
from ddfn_v2.core.node import DDFN_Node as Node
from ddfn_v2.core.network import get_local_ip

class TestBrokerNode(unittest.TestCase):
    def setUp(self):
        self.host = get_local_ip()
        self.broker_port = 50005 # Use a dedicated test port
        self.broker = Broker(host=self.host, port=self.broker_port)
        self.broker.start()
        time.sleep(0.5) # Give broker time to start

    def tearDown(self):
        self.broker.stop()
        time.sleep(0.5)

    def test_node_registration(self):
        """
        Test that a node can register with the broker.
        """
        node_id = "TEST_NODE"
        node = Node(node_id=node_id, broker_host=self.host, broker_port=self.broker_port)
        node.start()
        time.sleep(1) # Wait for registration
        
        # Verify node is in broker's registry
        self.assertIn(node_id, self.broker.nodes)
        node.stop()

    def test_duplicate_registration_failure(self):
        """
        RED: Test that registering a node with an existing ID fails or is handled.
        Currently, the implementation might just overwrite. We want to see how it behaves.
        """
        node_id = "DUPE_NODE"
        node1 = Node(node_id=node_id, broker_host=self.host, broker_port=self.broker_port)
        node1.start()
        time.sleep(0.5)
        
        # This will be our RED test: we expect it to fail if we want to enforce uniqueness
        # or at least we want to observe current behavior.
        # Let's say we want the broker to reject duplicates.
        node2 = Node(node_id=node_id, broker_host=self.host, broker_port=self.broker_port)
        node2.start()
        time.sleep(0.5)
        
        # Check broker logs or state. If it overwrote, node1 might be 'lost'.
        # For now, let's just assert something that might fail if not handled.
        self.assertEqual(len(self.broker.nodes), 1)
        node1.stop()
        node2.stop()

if __name__ == "__main__":
    unittest.main()
