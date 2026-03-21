import os
import unittest
import sqlite3
import uuid
from datetime import datetime, timezone
from ddfn_v2.core.persistence import PersistenceManager

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # Use a unique DB name per test to avoid locking issues on Windows
        os.makedirs("test_output", exist_ok=True)
        self.db_path = os.path.join("test_output", f"test_persistence_{uuid.uuid4().hex}.db")
        self.pm = PersistenceManager(self.db_path)

    def tearDown(self):
        self.pm.close()
        # Try to cleanup, but don't fail if Windows holds a lock
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    def test_idempotency_behavior(self):
        """
        Test that we can mark a message as processed and it remembers it.
        """
        msg_id = "msg-12345"
        self.assertFalse(self.pm.is_processed(msg_id), "Message should not be processed yet")
        
        self.pm.mark_processed(msg_id)
        self.assertTrue(self.pm.is_processed(msg_id), "Message should be marked as processed")
        
        # Mark again - should not error and should remain processed
        self.pm.mark_processed(msg_id)
        self.assertTrue(self.pm.is_processed(msg_id), "Message should still be processed")

    def test_processed_count(self):
        """
        Verify get_processed_count works correctly in a fresh DB.
        """
        self.assertEqual(self.pm.get_processed_count(), 0)
        self.pm.mark_processed("msg-1")
        self.pm.mark_processed("msg-2")
        self.assertEqual(self.pm.get_processed_count(), 2)
        # Duplicate should not increase count
        self.pm.mark_processed("msg-1")
        self.assertEqual(self.pm.get_processed_count(), 2)

    def test_overrides_persistence(self):
        """
        Test saving and loading manual overrides.
        """
        override = {
            "id": "ovr-1",
            "sector_id": "SEC-A",
            "start": datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc),
            "end": datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc),
            "capacity": 45,
            "reason": "Test override"
        }
        self.pm.save_override(override)
        
        loaded = self.pm.load_overrides()
        self.assertIn("SEC-A", loaded)
        self.assertEqual(len(loaded["SEC-A"]), 1)
        self.assertEqual(loaded["SEC-A"][0]["id"], "ovr-1")
        self.assertEqual(loaded["SEC-A"][0]["capacity"], 45)

if __name__ == "__main__":
    unittest.main()
