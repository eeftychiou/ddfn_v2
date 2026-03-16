import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class PersistenceManager:
    """
    Handles SQLite-based persistence for DDFN node state.
    Ensures that manual overrides and message IDs (for idempotency) survive restarts.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger("Persistence")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Idempotency table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS idempotency (
                    message_id TEXT PRIMARY KEY,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Manual Overrides table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS manual_overrides (
                    override_id TEXT PRIMARY KEY,
                    sector_id TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    capacity INTEGER,
                    reason TEXT
                )
            """)
            # KV Store for generic configuration/state
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    # --- Idempotency ---
    def is_processed(self, message_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM idempotency WHERE message_id = ?", (message_id,))
            return cursor.fetchone() is not None

    def mark_processed(self, message_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO idempotency (message_id) VALUES (?)", (message_id,))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to mark message {message_id} as processed: {e}")

    def get_processed_count(self) -> int:
        """Returns the total number of processed messages (idempotency entries)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM idempotency")
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            self.logger.error(f"Failed to get processed count: {e}")
            return 0

    # --- Manual Overrides ---
    def save_override(self, override: Dict[str, Any]):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO manual_overrides 
                    (override_id, sector_id, start_time, end_time, capacity, reason)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    override["id"],
                    override["sector_id"],
                    override["start"].isoformat() if isinstance(override["start"], datetime) else override["start"],
                    override["end"].isoformat() if isinstance(override["end"], datetime) else override["end"],
                    override["capacity"],
                    override["reason"]
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to save override: {e}")

    def remove_override(self, override_id: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM manual_overrides WHERE override_id = ?", (override_id,))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to remove override {override_id}: {e}")

    def load_overrides(self) -> Dict[str, List[Dict[str, Any]]]:
        overrides = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM manual_overrides")
                rows = cursor.fetchall()
                for row in rows:
                    sector_id = row["sector_id"]
                    if sector_id not in overrides:
                        overrides[sector_id] = []
                    
                    ovr = {
                        "id": row["override_id"],
                        "sector_id": row["sector_id"],
                        "start": datetime.fromisoformat(row["start_time"]),
                        "end": datetime.fromisoformat(row["end_time"]),
                        "capacity": row["capacity"],
                        "reason": row["reason"]
                    }
                    overrides[sector_id].append(ovr)
        except Exception as e:
            self.logger.error(f"Failed to load overrides: {e}")
        return overrides

    # --- KV Store ---
    def set_config(self, key: str, value: Any):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)", (key, json.dumps(value)))
                conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to set config {key}: {e}")

    def get_config(self, key: str, default: Any = None) -> Any:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            self.logger.error(f"Failed to get config {key}: {e}")
        return default

    def close(self):
        """No-op for now as we use context managers per call."""
        pass
