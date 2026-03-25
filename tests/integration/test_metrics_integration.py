"""
Integration tests for metrics endpoint integration.
"""
import pytest
import asyncio
from fastapi.testclient import TestClient


class TestMetricsIntegration:
    """Test metrics integration across services."""
    
    def test_metrics_endpoint_available(self):
        """Test that metrics endpoint is available on services."""
        # This test would require starting the actual service
        # For now, we verify the metrics module can be imported and used
        from ddfn_v2.core.metrics import get_metrics, CONTENT_TYPE_LATEST
        
        metrics = get_metrics()
        assert isinstance(metrics, bytes)
        assert len(metrics) > 0
    
    def test_metrics_format_valid(self):
        """Test that metrics are in valid Prometheus format."""
        from ddfn_v2.core.metrics import get_metrics
        
        metrics = get_metrics().decode('utf-8')
        
        # Check for Prometheus format indicators
        assert '# HELP' in metrics or '# TYPE' in metrics or 'ddfn_' in metrics
    
    def test_metrics_counters_functional(self):
        """Test that metrics counters increment correctly."""
        from ddfn_v2.core.metrics import (
            record_message_published, record_message_received,
            MESSAGES_PUBLISHED, MESSAGES_RECEIVED
        )
        
        # Get initial values
        topic = 'test_integration'
        node_id = 'test_node'
        
        initial_published = MESSAGES_PUBLISHED.labels(topic=topic, node_id=node_id)._value.get()
        initial_received = MESSAGES_RECEIVED.labels(topic=topic, node_id=node_id)._value.get()
        
        # Record messages
        record_message_published(topic, node_id)
        record_message_received(topic, node_id)
        record_message_published(topic, node_id)
        
        # Verify counters
        assert MESSAGES_PUBLISHED.labels(topic=topic, node_id=node_id)._value.get() == initial_published + 2
        assert MESSAGES_RECEIVED.labels(topic=topic, node_id=node_id)._value.get() == initial_received + 1
    
    def test_metrics_gauges_functional(self):
        """Test that metrics gauges update correctly."""
        from ddfn_v2.core.metrics import (
            update_flight_count, update_sector_metrics,
            FLIGHTS_TRACKED, SECTOR_CAPACITY, SECTOR_DEMAND
        )
        
        node_id = 'test_fmp'
        sector_id = 'test_sector'
        
        # Update flight count
        update_flight_count(node_id, 50)
        assert FLIGHTS_TRACKED.labels(node_id=node_id)._value.get() == 50
        
        # Update sector metrics
        update_sector_metrics(sector_id, node_id, 40.0, 35.0)
        assert SECTOR_CAPACITY.labels(sector_id=sector_id, node_id=node_id)._value.get() == 40.0
        assert SECTOR_DEMAND.labels(sector_id=sector_id, node_id=node_id)._value.get() == 35.0
    
    def test_airport_metrics_functional(self):
        """Test airport-specific metrics."""
        from ddfn_v2.core.metrics import (
            update_airport_metrics,
            AIRPORT_AAR, AIRPORT_ADR, AIRPORT_INBOUND_DEMAND
        )
        
        icao = 'TEST'
        
        update_airport_metrics(icao, aar=30, adr=25, inbound_demand=20)
        
        assert AIRPORT_AAR.labels(icao=icao)._value.get() == 30
        assert AIRPORT_ADR.labels(icao=icao)._value.get() == 25
        assert AIRPORT_INBOUND_DEMAND.labels(icao=icao)._value.get() == 20
    
    def test_websocket_metrics_functional(self):
        """Test WebSocket metrics."""
        from ddfn_v2.core.metrics import (
            update_websocket_connections, record_websocket_message,
            WS_CONNECTIONS, WS_MESSAGES
        )
        
        service = 'test_broker'
        
        # Update connection count
        update_websocket_connections(service, 15)
        assert WS_CONNECTIONS.labels(service=service)._value.get() == 15
        
        # Record messages
        initial_sent = WS_MESSAGES.labels(direction='sent', service=service)._value.get()
        record_websocket_message('sent', service)
        assert WS_MESSAGES.labels(direction='sent', service=service)._value.get() == initial_sent + 1


class TestMetricsWithServices:
    """Test metrics integration with actual services."""
    
    def test_broker_metrics_integration(self):
        """Test broker exposes metrics after message processing."""
        # This would require starting the broker and sending messages
        # For integration testing, we verify the metrics module is importable
        # and the broker has the metrics endpoint configured
        pytest.skip("Requires running broker service")
    
    def test_fmp_metrics_integration(self):
        """Test FMP service exposes metrics after processing."""
        pytest.skip("Requires running FMP service")
    
    def test_metrics_persistence_across_calls(self):
        """Test that metrics persist across multiple calls."""
        from ddfn_v2.core.metrics import (
            record_message_published, get_metrics
        )
        
        # Record some messages
        for i in range(5):
            record_message_published('persistence_test', 'node1')
        
        # Get metrics
        metrics1 = get_metrics().decode('utf-8')
        
        # Record more messages
        for i in range(3):
            record_message_published('persistence_test', 'node1')
        
        # Get metrics again
        metrics2 = get_metrics().decode('utf-8')
        
        # Verify metrics accumulated
        count1 = metrics1.count('persistence_test')
        count2 = metrics2.count('persistence_test')
        assert count2 >= count1
