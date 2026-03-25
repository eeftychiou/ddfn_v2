import sqlite3
import json
from datetime import datetime, timezone
import os
import threading
import queue
import logging

from ddfn_v2.core.config import config

logger = logging.getLogger("Audit")

class SWIMAuditLog:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = config.AUDIT_DB_PATH
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self.db_path = db_path
        self.queue = queue.Queue()
        self._stop_event = threading.Event()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    topic TEXT,
                    message_type TEXT,
                    source_node TEXT,
                    payload TEXT
                )
            ''')
            conn.commit()
            
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()

    def log_event(self, topic: str, payload_dict: dict):
        # Push to queue immediately to avoid blocking caller
        self.queue.put((topic, payload_dict))

    def _worker(self):
        """Background thread worker to batch writes if needed, or just keep them off main loop."""
        while not self._stop_event.is_set():
            try:
                # Wait for an item
                topic, payload_dict = self.queue.get(timeout=1.0)
                
                msg_type = payload_dict.get("message_type") or payload_dict.get("type") or "UNKNOWN"
                source_node = (payload_dict.get("node_id") or 
                               payload_dict.get("source_node") or 
                               payload_dict.get("origin_node") or "UNKNOWN")
                ts = datetime.now(timezone.utc).isoformat()
                dumped = json.dumps(payload_dict)
                
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "INSERT INTO audit_log (timestamp, topic, message_type, source_node, payload) VALUES (?, ?, ?, ?, ?)",
                            (ts, topic, msg_type, source_node, dumped)
                        )
                        conn.commit()
                except Exception as e:
                    logger.error(f"Audit log database error: {e}")
                
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Audit worker thread error: {e}")

    def stop(self):
        self._stop_event.set()
        self.worker_thread.join()
