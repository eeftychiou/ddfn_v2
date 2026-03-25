"""Unit tests for async file I/O operations."""
import pytest
import asyncio
import json
import aiofiles
from pathlib import Path


class TestAsyncFileOperations:
    """Test cases for async file I/O."""
    
    @pytest.mark.asyncio
    async def test_async_config_save(self, tmp_path):
        """Test async configuration saving."""
        config_file = tmp_path / "test_config.json"
        test_data = {"sectors": [], "config_name": "test"}
        
        async with aiofiles.open(config_file, "w") as f:
            await f.write(json.dumps(test_data, indent=4))
        
        assert config_file.exists()
        content = json.loads(config_file.read_text())
        assert content["config_name"] == "test"
    
    @pytest.mark.asyncio
    async def test_async_config_load(self, tmp_path):
        """Test async configuration loading."""
        config_file = tmp_path / "test_config.json"
        test_data = {"sectors": [], "config_name": "test"}
        config_file.write_text(json.dumps(test_data))
        
        async with aiofiles.open(config_file, "r") as f:
            content = await f.read()
            loaded_data = json.loads(content)
        
        assert loaded_data["config_name"] == "test"
    
    @pytest.mark.asyncio
    async def test_async_file_not_exists(self, tmp_path):
        """Test async file operations with non-existent file."""
        import aiofiles.os
        config_file = tmp_path / "nonexistent.json"
        
        exists = await aiofiles.os.path.exists(config_file)
        assert exists == False
    
    @pytest.mark.asyncio
    async def test_async_multiple_writes(self, tmp_path):
        """Test multiple async writes to same file."""
        config_file = tmp_path / "multi_write.json"
        
        for i in range(5):
            data = {"iteration": i, "timestamp": i * 1000}
            async with aiofiles.open(config_file, "w") as f:
                await f.write(json.dumps(data))
        
        # Verify last write
        content = json.loads(config_file.read_text())
        assert content["iteration"] == 4
    
    @pytest.mark.asyncio
    async def test_async_large_file(self, tmp_path):
        """Test async operations with larger data."""
        config_file = tmp_path / "large_config.json"
        large_data = {
            "sectors": [{"id": i, "name": f"sector_{i}"} for i in range(100)],
            "flights": [{"callsign": f"FLIGHT{i:03d}"} for i in range(1000)]
        }
        
        async with aiofiles.open(config_file, "w") as f:
            await f.write(json.dumps(large_data, indent=2))
        
        async with aiofiles.open(config_file, "r") as f:
            content = await f.read()
            loaded_data = json.loads(content)
        
        assert len(loaded_data["sectors"]) == 100
        assert len(loaded_data["flights"]) == 1000
