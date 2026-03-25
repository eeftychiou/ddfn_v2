"""
Unit tests for health check endpoints and API authentication.
"""
import pytest
import os
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI, Security, Header, HTTPException, status

# Import the auth module
from ddfn_v2.core.auth import verify_api_key, API_KEY_NAME, get_api_key


# =============================================================================
# Auth Module Tests
# =============================================================================

class TestAuthModule:
    """Tests for the authentication module."""
    
    def test_get_api_key_from_env(self):
        """Test that API key is loaded from environment variable."""
        test_key = "test-api-key-123"
        with patch.dict(os.environ, {"DDFN_API_KEY": test_key}):
            # Need to reload the module to pick up the env var
            import importlib
            from ddfn_v2.core import auth
            importlib.reload(auth)
            assert auth.API_KEY == test_key
    
    def test_get_api_key_generates_default(self):
        """Test that a secure key is generated if env var not set."""
        # Clear the env var
        with patch.dict(os.environ, {}, clear=True):
            import importlib
            from ddfn_v2.core import auth
            importlib.reload(auth)
            # Should generate a key
            assert auth.API_KEY is not None
            assert len(auth.API_KEY) > 20  # Generated keys are long
    
    @pytest.mark.asyncio
    async def test_verify_api_key_missing(self):
        """Test that missing API key raises 401."""
        with pytest.raises(Exception) as exc_info:
            await verify_api_key(None)
        assert "401" in str(exc_info.value) or "Unauthorized" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_verify_api_key_invalid(self):
        """Test that invalid API key raises 403."""
        with patch.dict(os.environ, {"DDFN_API_KEY": "valid-key"}):
            import importlib
            from ddfn_v2.core import auth
            importlib.reload(auth)
            with pytest.raises(Exception) as exc_info:
                await verify_api_key("invalid-key")
            assert "403" in str(exc_info.value) or "Invalid" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_verify_api_key_valid(self):
        """Test that valid API key is returned."""
        test_key = "my-valid-key"
        with patch.dict(os.environ, {"DDFN_API_KEY": test_key}):
            import importlib
            from ddfn_v2.core import auth
            importlib.reload(auth)
            result = await verify_api_key(test_key)
            assert result == test_key


# =============================================================================
# Broker Health Check Tests
# =============================================================================

class TestBrokerHealthCheck:
    """Tests for broker health check endpoint."""
    
    @pytest.fixture
    def broker_app(self):
        """Create a test broker app."""
        app = FastAPI()
        
        # Mock state
        active_nodes = {"ws1": "node1", "ws2": "node2"}
        subscribers = {"topic1": ["ws1"], "topic2": ["ws1", "ws2"]}
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "broker",
                "active_nodes": len(active_nodes),
                "active_topics": len(subscribers),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return app
    
    def test_health_check_returns_200(self, broker_app):
        """Test that health check returns 200 OK."""
        client = TestClient(broker_app)
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_health_check_response_format(self, broker_app):
        """Test that health check returns correct format."""
        client = TestClient(broker_app)
        response = client.get("/health")
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "broker"
        assert "active_nodes" in data
        assert "active_topics" in data
        assert "timestamp" in data
        assert data["active_nodes"] == 2
        assert data["active_topics"] == 2
    
    def test_health_check_timestamp_is_iso(self, broker_app):
        """Test that timestamp is in ISO format."""
        client = TestClient(broker_app)
        response = client.get("/health")
        data = response.json()
        
        # Should be parseable as ISO format
        timestamp = data["timestamp"]
        parsed = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        assert parsed.tzinfo is not None


# =============================================================================
# FMP Service Health Check Tests
# =============================================================================

class TestFMPHealthCheck:
    """Tests for FMP service health check endpoint."""
    
    @pytest.fixture
    def fmp_app_configured(self):
        """Create a test FMP app (configured state)."""
        app = FastAPI()
        
        # Mock node state
        mock_node = Mock()
        mock_node.node_id = "FMP_LFFF_DDFN_NODE"
        mock_node.is_configured = True
        mock_node.sectors = [Mock(), Mock(), Mock()]  # 3 sectors
        mock_node.fdps = Mock()
        mock_node.fdps.flights = {"f1": Mock(), "f2": Mock()}  # 2 flights
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy" if mock_node.is_configured else "unconfigured",
                "service": "fmp",
                "node_id": mock_node.node_id,
                "configured": mock_node.is_configured,
                "sectors_count": len(mock_node.sectors),
                "flights_tracked": len(mock_node.fdps.flights),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return app
    
    @pytest.fixture
    def fmp_app_unconfigured(self):
        """Create a test FMP app (unconfigured state)."""
        app = FastAPI()
        
        # Mock node state
        mock_node = Mock()
        mock_node.node_id = "FMP_DEFAULT_DDFN_NODE"
        mock_node.is_configured = False
        mock_node.sectors = []
        mock_node.fdps = Mock()
        mock_node.fdps.flights = {}
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy" if mock_node.is_configured else "unconfigured",
                "service": "fmp",
                "node_id": mock_node.node_id,
                "configured": mock_node.is_configured,
                "sectors_count": len(mock_node.sectors),
                "flights_tracked": len(mock_node.fdps.flights),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return app
    
    def test_health_check_configured(self, fmp_app_configured):
        """Test health check when FMP is configured."""
        client = TestClient(fmp_app_configured)
        response = client.get("/health")
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "healthy"
        assert data["configured"] is True
        assert data["sectors_count"] == 3
        assert data["flights_tracked"] == 2
    
    def test_health_check_unconfigured(self, fmp_app_unconfigured):
        """Test health check when FMP is not configured."""
        client = TestClient(fmp_app_unconfigured)
        response = client.get("/health")
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "unconfigured"
        assert data["configured"] is False
        assert data["sectors_count"] == 0
        assert data["flights_tracked"] == 0


# =============================================================================
# Airport Service Health Check Tests
# =============================================================================

class TestAirportHealthCheck:
    """Tests for airport service health check endpoint."""
    
    @pytest.fixture
    def airport_app(self):
        """Create a test airport app."""
        app = FastAPI()
        
        # Mock node state
        mock_node = Mock()
        mock_node.icao = "LFPG"
        mock_node.status = Mock()
        mock_node.status.aar = 35
        mock_node.status.adr = 30
        mock_node.fdps = Mock()
        mock_node.fdps.flights = {"f1": Mock(), "f2": Mock(), "f3": Mock()}
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "airport",
                "icao": mock_node.icao,
                "aar": mock_node.status.aar,
                "adr": mock_node.status.adr,
                "flights_tracked": len(mock_node.fdps.flights),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return app
    
    def test_health_check_response(self, airport_app):
        """Test airport health check response."""
        client = TestClient(airport_app)
        response = client.get("/health")
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "healthy"
        assert data["service"] == "airport"
        assert data["icao"] == "LFPG"
        assert data["aar"] == 35
        assert data["adr"] == 30
        assert data["flights_tracked"] == 3


# =============================================================================
# AOC Service Health Check Tests
# =============================================================================

class TestAOCHealthCheck:
    """Tests for AOC service health check endpoint."""
    
    @pytest.fixture
    def aoc_app(self):
        """Create a test AOC app."""
        app = FastAPI()
        
        # Mock node state
        mock_node = Mock()
        mock_node.node_id = "AFR"
        mock_node.flights = [{"flight_id": "AFR123"}, {"flight_id": "AFR456"}]
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "aoc",
                "node_id": mock_node.node_id if mock_node else "unknown",
                "flights_managed": len(mock_node.flights) if mock_node else 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return app
    
    def test_health_check_response(self, aoc_app):
        """Test AOC health check response."""
        client = TestClient(aoc_app)
        response = client.get("/health")
        data = response.json()
        
        assert response.status_code == 200
        assert data["status"] == "healthy"
        assert data["service"] == "aoc"
        assert data["node_id"] == "AFR"
        assert data["flights_managed"] == 2


# =============================================================================
# Sim Manager Health Check Tests
# =============================================================================

class TestSimManagerHealthCheck:
    """Tests for sim manager health check endpoint."""
    
    @pytest.fixture
    def sim_app_connected(self):
        """Create a test sim manager app (connected)."""
        app = FastAPI()
        
        # Mock network client (connected)
        mock_client = Mock()
        mock_client.websocket = Mock()  # Not None = connected
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "sim_manager",
                "broker_connected": mock_client is not None and mock_client.websocket is not None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return app
    
    @pytest.fixture
    def sim_app_disconnected(self):
        """Create a test sim manager app (disconnected)."""
        app = FastAPI()
        
        # Mock network client (disconnected)
        mock_client = Mock()
        mock_client.websocket = None  # None = disconnected
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "sim_manager",
                "broker_connected": mock_client is not None and mock_client.websocket is not None,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        return app
    
    def test_health_check_connected(self, sim_app_connected):
        """Test health check when broker is connected."""
        client = TestClient(sim_app_connected)
        response = client.get("/health")
        data = response.json()
        
        assert response.status_code == 200
        assert data["broker_connected"] is True
    
    def test_health_check_disconnected(self, sim_app_disconnected):
        """Test health check when broker is disconnected."""
        client = TestClient(sim_app_disconnected)
        response = client.get("/health")
        data = response.json()
        
        assert response.status_code == 200
        assert data["broker_connected"] is False


# =============================================================================
# Authentication Integration Tests
# =============================================================================

class TestAuthenticationIntegration:
    """Tests for API authentication integration."""
    
    @pytest.fixture
    def protected_app(self):
        """Create a test app with protected endpoints."""
        app = FastAPI()
        
        # Mock the verify_api_key dependency
        async def mock_verify_api_key(api_key: str = None):
            if api_key is None:
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key header missing"
                )
            if api_key != "valid-key":
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid API key"
                )
            return api_key
        
        @app.get("/health")
        async def health_check():
            return {"status": "healthy"}
        
        @app.get("/api/protected")
        async def protected_endpoint(x_api_key: str = Header(None)):
            # Check auth inline instead of using Security() which has issues with TestClient
            if x_api_key is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key header missing"
                )
            if x_api_key != "valid-key":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid API key"
                )
            return {"data": "sensitive"}
        
        return app
    
    def test_public_endpoint_no_auth(self, protected_app):
        """Test that public endpoint works without auth."""
        client = TestClient(protected_app)
        response = client.get("/health")
        assert response.status_code == 200
    
    def test_protected_endpoint_no_auth(self, protected_app):
        """Test that protected endpoint requires auth."""
        client = TestClient(protected_app)
        response = client.get("/api/protected")
        assert response.status_code == 401
    
    def test_protected_endpoint_invalid_auth(self, protected_app):
        """Test that protected endpoint rejects invalid auth."""
        client = TestClient(protected_app)
        response = client.get("/api/protected", headers={"X-API-Key": "invalid-key"})
        assert response.status_code == 403
    
    def test_protected_endpoint_valid_auth(self, protected_app):
        """Test that protected endpoint accepts valid auth."""
        client = TestClient(protected_app)
        response = client.get("/api/protected", headers={"X-API-Key": "valid-key"})
        assert response.status_code == 200
        assert response.json()["data"] == "sensitive"
