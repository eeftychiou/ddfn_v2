"""Unit tests for task cleanup in broker."""
import pytest
import asyncio
import weakref
from unittest.mock import AsyncMock, MagicMock


class TestTaskCleanup:
    """Test cases for asyncio task cleanup."""
    
    @pytest.mark.asyncio
    async def test_task_tracking(self):
        """Test that tasks are properly tracked."""
        _active_tasks = weakref.WeakSet()
        
        async def dummy_task():
            await asyncio.sleep(0.01)
            return "done"
        
        task = asyncio.create_task(dummy_task())
        _active_tasks.add(task)
        task.add_done_callback(lambda t: _active_tasks.discard(t))
        
        await task
        assert len(list(_active_tasks)) == 0
    
    @pytest.mark.asyncio
    async def test_task_timeout_cleanup(self):
        """Test that tasks are cancelled on timeout."""
        async def slow_task():
            await asyncio.sleep(10)
        
        task = asyncio.create_task(slow_task())
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(task, timeout=0.01)
        
        assert task.cancelled() or task.done()
    
    @pytest.mark.asyncio
    async def test_multiple_tasks_cleanup(self):
        """Test cleanup of multiple concurrent tasks."""
        _active_tasks = weakref.WeakSet()
        
        async def quick_task(id):
            await asyncio.sleep(0.01)
            return f"task_{id}"
        
        tasks = [asyncio.create_task(quick_task(i)) for i in range(5)]
        
        for task in tasks:
            _active_tasks.add(task)
            task.add_done_callback(lambda t: _active_tasks.discard(t))
        
        await asyncio.gather(*tasks)
        assert len(list(_active_tasks)) == 0
    
    @pytest.mark.asyncio
    async def test_task_gather_with_exceptions(self):
        """Test task cleanup when some tasks raise exceptions."""
        async def success_task():
            await asyncio.sleep(0.01)
            return "success"
        
        async def fail_task():
            await asyncio.sleep(0.01)
            raise ValueError("Test error")
        
        tasks = [
            asyncio.create_task(success_task()),
            asyncio.create_task(fail_task()),
            asyncio.create_task(success_task())
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all tasks completed (some with exceptions)
        assert len(results) == 3
        assert results[0] == "success"
        assert isinstance(results[1], ValueError)
        assert results[2] == "success"
    
    @pytest.mark.asyncio
    async def test_task_cancel_remaining(self):
        """Test explicit cancellation of remaining tasks."""
        async def slow_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                return "cancelled"
            return "completed"
        
        task = asyncio.create_task(slow_task())
        
        # Cancel the task
        task.cancel()
        
        try:
            result = await task
            assert result == "cancelled"
        except asyncio.CancelledError:
            assert task.cancelled()
