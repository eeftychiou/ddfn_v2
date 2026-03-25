"""
Unit tests for Prometheus metrics module.
"""
import pytest
from unittest.mock import patch, MagicMock
import time

# Import metrics module
from ddfn_v2.core.metrics import (
    MESSAGES_PUBLISHED, MESSAGES_RECEIVED, MESSAGE_PROCESSING_TIME,
    ACTIVE_NODES, NODE_UP, SECTOR_CAPACITY, SECTOR_DEMAND,
    FLIGHTS_TRACKED, AIRPORT_AAR, AIRPORT_ADR, AIRPORT_INBOUND_DEMAND,
    WS_CONNECTIONS, WS_MESSAGES, HEALTH_CHECK_DURATION, API_REQUESTS, API_REQUEST_DURATION,
    get_metrics, track_processing_time, track_api_request,
    set_service_info, record_node_up, record_message_published, record_message_received,
    update_sector_metrics, update_flight_count, update_airport_metrics,
    update_websocket_connections, record_websocket_message
)


class TestMetricsCounters:
    """Test counter metrics."""
    
    def test_message_counters_increment(self):
        """Test that message counters increment correctly."""
        # Get initial values
        initial_published = MESSAGES_PUBLISHED.labels(topic='test', node_id='node1')._value.get()
        initial_received = MESSAGES_RECEIVED.labels(topic='test', node_id='node1')._value.get()
        
        # Increment counters
        record_message_published('test', 'node1')
        record_message_received('test', 'node1')
        
        # Verify increment
        assert MESSAGES_PUBLISHED.labels(topic='test', node_id='node1')._value.get() == initial_published + 1
        assert MESSAGES_RECEIVED.labels(topic='test', node_id='node1')._value.get() == initial_received + 1
    
    def test_websocket_message_counter(self):
        """Test WebSocket message counter."""
        initial = WS_MESSAGES.labels(direction='sent', service='broker')._value.get()
        
        record_websocket_message('sent', 'broker')
        
        assert WS_MESSAGES.labels(direction='sent', service='broker')._value.get() == initial + 1


class TestMetricsGauges:
    """Test gauge metrics."""
    
    def test_gauge_values_update(self):
        """Test that gauge metrics update correctly."""
        # Test node up gauge
        record_node_up('node1', 'fmp', True)
        assert NODE_UP.labels(node_id='node1', service='fmp')._value.get() == 1
        
        record_node_up('node1', 'fmp', False)
        assert NODE_UP.labels(node_id='node1', service='fmp')._value.get() == 0
    
    def test_flight_count_gauge(self):
        """Test flight count gauge."""
        update_flight_count('fmp1', 42)
        assert FLIGHTS_TRACKED.labels(node_id='fmp1')._value.get() == 42
        
        update_flight_count('fmp1', 100)
        assert FLIGHTS_TRACKED.labels(node_id='fmp1')._value.get() == 100
    
    def test_sector_metrics(self):
        """Test sector capacity and demand metrics."""
        update_sector_metrics('sector1', 'fmp1', 40.0, 35.0)
        
        assert SECTOR_CAPACITY.labels(sector_id='sector1', node_id='fmp1')._value.get() == 40.0
        assert SECTOR_DEMAND.labels(sector_id='sector1', node_id='fmp1')._value.get() == 35.0
    
    def test_airport_metrics(self):
        """Test airport metrics."""
        update_airport_metrics('LFPG', aar=35, adr=30, inbound_demand=25)
        
        assert AIRPORT_AAR.labels(icao='LFPG')._value.get() == 35
        assert AIRPORT_ADR.labels(icao='LFPG')._value.get() == 30
        assert AIRPORT_INBOUND_DEMAND.labels(icao='LFPG')._value.get() == 25
    
    def test_websocket_connections(self):
        """Test WebSocket connection gauge."""
        update_websocket_connections('broker', 10)
        assert WS_CONNECTIONS.labels(service='broker')._value.get() == 10


class TestProcessingTimeDecorator:
    """Test processing time tracking decorator."""
    
    @pytest.mark.asyncio
    async def test_async_processing_time_tracking(self):
        """Test async function processing time tracking."""
        
        @track_processing_time('test_message', 'node1')
        async def async_test_func():
            await asyncio.sleep(0.01)
            return 'result'
        
        result = await async_test_func()
        assert result == 'result'
    
    def test_sync_processing_time_tracking(self):
        """Test sync function processing time tracking."""
        
        @track_processing_time('test_message', 'node1')
        def sync_test_func():
            time.sleep(0.01)
            return 'result'
        
        result = sync_test_func()
        assert result == 'result'


class TestAPIRequestDecorator:
    """Test API request tracking decorator."""
    
    @pytest.mark.asyncio
    async def test_async_api_request_tracking(self):
        """Test async API request tracking."""
        
        @track_api_request('/api/test')
        async def async_api_func():
            await asyncio.sleep(0.01)
            return {'status': 'ok'}
        
        result = await async_api_func()
        assert result['status'] == 'ok'
    
    def test_sync_api_request_tracking(self):
        """Test sync API request tracking."""
        
        @track_api_request('/api/test')
        def sync_api_func():
            time.sleep(0.01)
            return {'status': 'ok'}
        
        result = sync_api_func()
        assert result['status'] == 'ok'


class TestMetricsExport:
    """Test metrics export functionality."""
    
    def test_get_metrics_returns_bytes(self):
        """Test that get_metrics returns bytes."""
        metrics = get_metrics()
        assert isinstance(metrics, bytes)
    
    def test_metrics_contains_expected_content(self):
        """Test that metrics output contains expected Prometheus format."""
        # Set some metrics
        record_message_published('test_topic', 'node1')
        update_flight_count('fmp1', 10)
        
        metrics = get_metrics().decode('utf-8')
        
        # Check for expected metric names
        assert 'ddfn_messages_published_total' in metrics
        assert 'ddfn_flights_tracked' in metrics


class TestServiceInfo:
    """Test service info metrics."""
    
    def test_set_service_info(self):
        """Test setting service information."""
        # This should not raise an exception
        set_service_info('broker', '2.0.0')
        set_service_info('fmp', '2.0.0')


# Import asyncio for async tests
import asyncio
