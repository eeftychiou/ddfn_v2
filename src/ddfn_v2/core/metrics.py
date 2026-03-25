"""
Prometheus metrics collection for DDFN v2.
"""
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from functools import wraps
import time
import asyncio

# Service info
SERVICE_INFO = Info('ddfn_service', 'DDFN service information')

# Message metrics
MESSAGES_PUBLISHED = Counter(
    'ddfn_messages_published_total',
    'Total messages published',
    ['topic', 'node_id']
)

MESSAGES_RECEIVED = Counter(
    'ddfn_messages_received_total',
    'Total messages received',
    ['topic', 'node_id']
)

MESSAGE_PROCESSING_TIME = Histogram(
    'ddfn_message_processing_seconds',
    'Time spent processing messages',
    ['message_type', 'node_id']
)

# Node metrics
ACTIVE_NODES = Gauge(
    'ddfn_active_nodes',
    'Number of active nodes in the network',
    ['node_type']
)

NODE_UP = Gauge(
    'ddfn_node_up',
    'Whether the node is up (1) or down (0)',
    ['node_id', 'service']
)

# FMP specific metrics
SECTOR_CAPACITY = Gauge(
    'ddfn_sector_capacity',
    'Current sector capacity',
    ['sector_id', 'node_id']
)

SECTOR_DEMAND = Gauge(
    'ddfn_sector_demand',
    'Current sector demand',
    ['sector_id', 'node_id']
)

FLIGHTS_TRACKED = Gauge(
    'ddfn_flights_tracked',
    'Number of flights being tracked',
    ['node_id']
)

# Airport specific metrics
AIRPORT_AAR = Gauge(
    'ddfn_airport_aar',
    'Airport Arrival Acceptance Rate',
    ['icao']
)

AIRPORT_ADR = Gauge(
    'ddfn_airport_adr',
    'Airport Departure Rate',
    ['icao']
)

AIRPORT_INBOUND_DEMAND = Gauge(
    'ddfn_airport_inbound_demand',
    'Current inbound demand',
    ['icao']
)

# WebSocket metrics
WS_CONNECTIONS = Gauge(
    'ddfn_websocket_connections',
    'Number of active WebSocket connections',
    ['service']
)

WS_MESSAGES = Counter(
    'ddfn_websocket_messages_total',
    'Total WebSocket messages',
    ['direction', 'service']  # direction: sent|received
)

# Health check metrics
HEALTH_CHECK_DURATION = Histogram(
    'ddfn_health_check_duration_seconds',
    'Time spent performing health checks',
    ['service']
)

# API metrics
API_REQUESTS = Counter(
    'ddfn_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status']
)

API_REQUEST_DURATION = Histogram(
    'ddfn_api_request_duration_seconds',
    'Time spent processing API requests',
    ['endpoint']
)


def track_processing_time(message_type: str, node_id: str):
    """Decorator to track message processing time."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                MESSAGE_PROCESSING_TIME.labels(
                    message_type=message_type,
                    node_id=node_id
                ).observe(time.time() - start)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                return func(*args, **kwargs)
            finally:
                MESSAGE_PROCESSING_TIME.labels(
                    message_type=message_type,
                    node_id=node_id
                ).observe(time.time() - start)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def track_api_request(endpoint: str):
    """Decorator to track API request metrics."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                status = 'success'
                return result
            except Exception:
                status = 'error'
                raise
            finally:
                duration = time.time() - start
                API_REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                status = 'success'
                return result
            except Exception:
                status = 'error'
                raise
            finally:
                duration = time.time() - start
                API_REQUEST_DURATION.labels(endpoint=endpoint).observe(duration)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def get_metrics():
    """Generate Prometheus metrics output."""
    return generate_latest()


def set_service_info(service_name: str, version: str = '2.0.0'):
    """Set service information metrics."""
    SERVICE_INFO.info({'service': service_name, 'version': version})


def record_node_up(node_id: str, service: str, up: bool = True):
    """Record node up/down status."""
    NODE_UP.labels(node_id=node_id, service=service).set(1 if up else 0)


def record_message_published(topic: str, node_id: str):
    """Record a message being published."""
    MESSAGES_PUBLISHED.labels(topic=topic, node_id=node_id).inc()


def record_message_received(topic: str, node_id: str):
    """Record a message being received."""
    MESSAGES_RECEIVED.labels(topic=topic, node_id=node_id).inc()


def update_sector_metrics(sector_id: str, node_id: str, capacity: float, demand: float):
    """Update sector capacity and demand metrics."""
    SECTOR_CAPACITY.labels(sector_id=sector_id, node_id=node_id).set(capacity)
    SECTOR_DEMAND.labels(sector_id=sector_id, node_id=node_id).set(demand)


def update_flight_count(node_id: str, count: int):
    """Update flights tracked metric."""
    FLIGHTS_TRACKED.labels(node_id=node_id).set(count)


def update_airport_metrics(icao: str, aar: int = None, adr: int = None, inbound_demand: int = None):
    """Update airport metrics."""
    if aar is not None:
        AIRPORT_AAR.labels(icao=icao).set(aar)
    if adr is not None:
        AIRPORT_ADR.labels(icao=icao).set(adr)
    if inbound_demand is not None:
        AIRPORT_INBOUND_DEMAND.labels(icao=icao).set(inbound_demand)


def update_websocket_connections(service: str, count: int):
    """Update WebSocket connection count."""
    WS_CONNECTIONS.labels(service=service).set(count)


def record_websocket_message(direction: str, service: str):
    """Record WebSocket message sent or received."""
    WS_MESSAGES.labels(direction=direction, service=service).inc()
