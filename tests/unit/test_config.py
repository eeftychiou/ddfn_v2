"""Unit tests for the configuration module."""
import os
import pytest
from ddfn_v2.core.config import DDFNConfig, config


class TestDDFNConfig:
    """Test cases for DDFNConfig class."""
    
    def test_default_broker_host(self):
        """Test default broker host configuration."""
        assert config.BROKER_HOST == "127.0.0.1"
    
    def test_default_broker_port(self):
        """Test default broker port configuration."""
        assert config.BROKER_PORT == 8001
    
    def test_broker_url_property(self):
        """Test broker URL construction."""
        assert config.BROKER_URL == "ws://127.0.0.1:8001/ws"
    
    def test_environment_override(self, monkeypatch):
        """Test that environment variables override defaults."""
        monkeypatch.setenv("DDFN_FMP_MEASURE_WINDOW", "90")
        # Create a fresh instance to pick up the new environment variable
        test_config = DDFNConfig()
        assert test_config.FMP_DEFAULT_MEASURE_WINDOW == 90
    
    def test_ensure_directories(self, tmp_path, monkeypatch):
        """Test directory creation."""
        monkeypatch.setenv("DDFN_CONFIG_DIR", str(tmp_path / "configs"))
        monkeypatch.setenv("DDFN_LOGS_DIR", str(tmp_path / "logs"))
        # Create fresh instance to pick up environment changes
        test_config = DDFNConfig()
        test_config.ensure_directories()
        assert os.path.exists(tmp_path / "configs")
        assert os.path.exists(tmp_path / "logs")
    
    def test_fmp_default_measure_window(self):
        """Test default FMP measure window."""
        assert config.FMP_DEFAULT_MEASURE_WINDOW == 120
    
    def test_fmp_default_capacity(self):
        """Test default FMP capacity."""
        assert config.FMP_DEFAULT_CAPACITY == 40
    
    def test_airport_default_aar(self):
        """Test default airport AAR."""
        assert config.AIRPORT_DEFAULT_AAR == 30
    
    def test_airport_default_adr(self):
        """Test default airport ADR."""
        assert config.AIRPORT_DEFAULT_ADR == 28
    
    def test_broker_port_environment_override(self, monkeypatch):
        """Test broker port environment override."""
        monkeypatch.setenv("DDFN_BROKER_PORT", "9000")
        # Create a fresh instance to pick up the new environment variable
        test_config = DDFNConfig()
        assert test_config.BROKER_PORT == 9000
        assert test_config.BROKER_URL == "ws://127.0.0.1:9000/ws"
    
    def test_multiple_environment_overrides(self, monkeypatch):
        """Test multiple environment variable overrides."""
        monkeypatch.setenv("DDFN_BROKER_HOST", "0.0.0.0")
        monkeypatch.setenv("DDFN_BROKER_PORT", "8080")
        monkeypatch.setenv("DDFN_FMP_DEFAULT_CAPACITY", "50")
        
        # Create a fresh instance to pick up the new environment variables
        test_config = DDFNConfig()
        assert test_config.BROKER_HOST == "0.0.0.0"
        assert test_config.BROKER_PORT == 8080
        assert test_config.FMP_DEFAULT_CAPACITY == 50
        assert test_config.BROKER_URL == "ws://0.0.0.0:8080/ws"
