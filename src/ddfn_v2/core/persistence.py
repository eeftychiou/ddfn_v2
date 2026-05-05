import aiosqlite
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

class PersistenceManager:
    """
    Handles SQLite-based persistence for DDFN node state.
    Uses aiosqlite for non-blocking async I/O.
    Ensures that manual overrides and message IDs (for idempotency) survive restarts.
    """
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger("Persistence")

    async def _init_db(self):
        """Initialize database tables. Call once at startup."""
        async with aiosqlite.connect(self.db_path) as conn:
            # Enable WAL mode for better concurrency and performance
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")

            # Idempotency table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS idempotency (
                    message_id TEXT PRIMARY KEY,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Manual Overrides table
            await conn.execute("""
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
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            await conn.commit()

    # --- Idempotency ---
    async def is_processed(self, message_id: str) -> bool:
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM idempotency WHERE message_id = ?", (message_id,)
            )
            row = await cursor.fetchone()
            await cursor.close()
            return row is not None

    async def mark_processed(self, message_id: str):
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    "INSERT OR IGNORE INTO idempotency (message_id) VALUES (?)",
                    (message_id,)
                )
                await conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to mark message {message_id} as processed: {e}")

    async def get_processed_count(self) -> int:
        """Returns the total number of processed messages (idempotency entries)."""
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM idempotency")
                row = await cursor.fetchone()
                await cursor.close()
                return row[0] if row else 0
        except Exception as e:
            self.logger.error(f"Failed to get processed count: {e}")
            return 0

    # --- Manual Overrides ---
    async def save_override(self, override: Dict[str, Any]):
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
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
                await conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to save override: {e}")

    async def remove_override(self, override_id: str):
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    "DELETE FROM manual_overrides WHERE override_id = ?",
                    (override_id,)
                )
                await conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to remove override {override_id}: {e}")

    async def load_overrides(self) -> Dict[str, List[Dict[str, Any]]]:
        overrides = {}
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute("SELECT * FROM manual_overrides")
                rows = await cursor.fetchall()
                await cursor.close()
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
    async def set_config(self, key: str, value: Any):
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute(
                    "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                    (key, json.dumps(value))
                )
                await conn.commit()
        except Exception as e:
            self.logger.error(f"Failed to set config {key}: {e}")

    async def get_config(self, key: str, default: Any = None) -> Any:
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                cursor = await conn.execute(
                    "SELECT value FROM kv_store WHERE key = ?",
                    (key,)
                )
                row = await cursor.fetchone()
                await cursor.close()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            self.logger.error(f"Failed to get config {key}: {e}")
        return default

    async def close(self):
        """No-op for aiosqlite as we use context managers per call."""
        pass
