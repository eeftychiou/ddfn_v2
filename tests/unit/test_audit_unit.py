import unittest
import os
import sqlite3
import time
import json
import uuid
from ddfn_v2.core.audit import SWIMAuditLog

class TestAuditUnit(unittest.TestCase):
    def setUp(self):
        # Use a unique DB name for each test run to avoid lock issues
        self.db_path = f"logs/test_audit_{uuid.uuid4().hex}.db"
        self.audit = SWIMAuditLog(db_path=self.db_path)

    def tearDown(self):
        self.audit.stop()
        # Wait a bit for the thread to fully release the file
        time.sleep(0.5)
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except Exception as e:
                print(f"Warning: could not delete {self.db_path}: {e}")

    def test_log_and_retrieve(self):
        topic = "ddfn.test"
        payload = {"message_type": "TEST_MSG", "node_id": "TEST_NODE", "data": 123}
        self.audit.log_event(topic, payload)
        
        # Give worker thread time to write
        max_retries = 5
        row = None
        for _ in range(max_retries):
            time.sleep(0.5)
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT topic, message_type, source_node, payload FROM audit_log")
                    row = cursor.fetchone()
                    if row: break
            except:
                continue
            
        self.assertIsNotNone(row, "Audit log row was not found after retries")
        self.assertEqual(row[0], topic)
        self.assertEqual(row[1], "TEST_MSG")
        self.assertEqual(row[2], "TEST_NODE")
        
        stored_payload = json.loads(row[3])
        self.assertEqual(stored_payload["data"], 123)

    def test_different_id_fields(self):
        payloads = [
            {"type": "A", "node_id": "NODE_A"},
            {"message_type": "B", "source_node": "NODE_B"},
            {"message_type": "C", "origin_node": "NODE_C"}
        ]
        
        for p in payloads:
            self.audit.log_event("test", p)
        
        time.sleep(1.5)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT source_node FROM audit_log ORDER BY message_type ASC")
            nodes = [r[0] for r in cursor.fetchall()]
            self.assertIn("NODE_A", nodes)
            self.assertIn("NODE_B", nodes)
            self.assertIn("NODE_C", nodes)

if __name__ == '__main__':
    unittest.main()
