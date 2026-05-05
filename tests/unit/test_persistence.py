import os
import pytest
import aiosqlite
import uuid
from datetime import datetime, timezone
from ddfn_v2.core.persistence import PersistenceManager

class TestPersistence:
    @pytest.fixture(autouse=True)
    async def setup_pm(self):
        os.makedirs("test_output", exist_ok=True)
        self.db_path = os.path.join("test_output", f"test_persistence_{uuid.uuid4().hex}.db")
        self.pm = PersistenceManager(self.db_path)
        await self.pm._init_db()
        yield
        await self.pm.close()
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
        except PermissionError:
            pass

    @pytest.mark.asyncio
    async def test_idempotency_behavior(self):
        msg_id = "msg-12345"
        assert not await self.pm.is_processed(msg_id), "Message should not be processed yet"
        
        await self.pm.mark_processed(msg_id)
        assert await self.pm.is_processed(msg_id), "Message should be marked as processed"
        
        await self.pm.mark_processed(msg_id)
        assert await self.pm.is_processed(msg_id), "Message should still be processed"

    @pytest.mark.asyncio
    async def test_processed_count(self):
        assert await self.pm.get_processed_count() == 0
        await self.pm.mark_processed("msg-1")
        await self.pm.mark_processed("msg-2")
        assert await self.pm.get_processed_count() == 2
        await self.pm.mark_processed("msg-1")
        assert await self.pm.get_processed_count() == 2

    @pytest.mark.asyncio
    async def test_overrides_persistence(self):
        override = {
            "id": "ovr-1",
            "sector_id": "SEC-A",
            "start": datetime(2026, 3, 14, 12, 0, tzinfo=timezone.utc),
            "end": datetime(2026, 3, 14, 14, 0, tzinfo=timezone.utc),
            "capacity": 45,
            "reason": "Test override"
        }
        await self.pm.save_override(override)
        
        loaded = await self.pm.load_overrides()
        assert "SEC-A" in loaded
        assert len(loaded["SEC-A"]) == 1
        assert loaded["SEC-A"][0]["id"] == "ovr-1"
        assert loaded["SEC-A"][0]["capacity"] == 45
