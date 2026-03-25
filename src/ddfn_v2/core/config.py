"""
Centralized configuration management for DDFN v2.
Loads configuration from environment variables with sensible defaults.
"""
import os
from pathlib import Path
from typing import Optional

PROJECT_ROOT = str(Path(__file__).parent.parent.parent.parent.absolute())


class DDFNConfig:
    """Configuration class for DDFN services."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Broker Configuration
        self.BROKER_HOST: str = os.environ.get("DDFN_BROKER_HOST", "127.0.0.1")
        self.BROKER_PORT: int = int(os.environ.get("DDFN_BROKER_PORT", "8001"))
        self.BROKER_WS_PATH: str = os.environ.get("DDFN_BROKER_WS_PATH", "/ws")
        
        # FMP Service Configuration
        self.FMP_DEFAULT_MEASURE_WINDOW: int = int(os.environ.get("DDFN_FMP_MEASURE_WINDOW", "120"))
        self.FMP_DEFAULT_CAPACITY: int = int(os.environ.get("DDFN_FMP_DEFAULT_CAPACITY", "40"))
        self.FMP_CAPACITY_SYNC_INTERVAL: float = float(os.environ.get("DDFN_FMP_SYNC_INTERVAL", "3.0"))
        self.FMP_NETWORK_SETTLE_TIME: float = float(os.environ.get("DDFN_FMP_SETTLE_TIME", "2.0"))
        
        # Airport Service Configuration
        self.AIRPORT_DEFAULT_AAR: int = int(os.environ.get("DDFN_AIRPORT_DEFAULT_AAR", "30"))
        self.AIRPORT_DEFAULT_ADR: int = int(os.environ.get("DDFN_AIRPORT_DEFAULT_ADR", "28"))
        self.AIRPORT_CLEARINGHOUSE_WAIT: float = float(os.environ.get("DDFN_AIRPORT_CLEARINGHOUSE_WAIT", "4.0"))
        self.AIRPORT_INBOUND_LOAD_FACTOR: float = float(os.environ.get("DDFN_AIRPORT_INBOUND_LOAD", "0.85"))
        self.AIRPORT_OUTBOUND_LOAD_FACTOR: float = float(os.environ.get("DDFN_AIRPORT_OUTBOUND_LOAD", "0.80"))
        
        # AOC Service Configuration
        self.AOC_FLIGHT_PLAN_DELAY: int = int(os.environ.get("DDFN_AOC_PLAN_DELAY", "10"))
        
        self.PROJECT_ROOT: str = PROJECT_ROOT
        
        # Paths
        self.CONFIG_DIR: str = os.environ.get("DDFN_CONFIG_DIR", os.path.join(PROJECT_ROOT, "data", "node_configs"))
        self.LOGS_DIR: str = os.environ.get("DDFN_LOGS_DIR", os.path.join(PROJECT_ROOT, "logs"))
        self.DATA_DIR: str = os.environ.get("DDFN_DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
        self.AIXM_DIR: str = os.environ.get("DDFN_AIXM_DIR", os.path.join(PROJECT_ROOT, "AIXM"))
        self.UPLOADS_DIR: str = os.environ.get("DDFN_UPLOADS_DIR", os.path.join(PROJECT_ROOT, "uploads"))
        
        # Default Time Windows
        self.DEFAULT_WINDOW_START: str = os.environ.get("DDFN_DEFAULT_WINDOW_START", "16:00")
        self.DEFAULT_WINDOW_END: str = os.environ.get("DDFN_DEFAULT_WINDOW_END", "18:00")
        
        # Audit Configuration
        self.AUDIT_DB_PATH: str = os.environ.get("DDFN_AUDIT_DB", os.path.join(PROJECT_ROOT, "logs", "swim_audit.db"))
        self.AUDIT_RETENTION_DAYS: int = int(os.environ.get("DDFN_AUDIT_RETENTION", "30"))
        
        # API Authentication
        self.API_KEY: Optional[str] = os.environ.get("DDFN_API_KEY", None)
    
    @property
    def BROKER_URL(self) -> str:
        return f"ws://{self.BROKER_HOST}:{self.BROKER_PORT}{self.BROKER_WS_PATH}"
    
    def ensure_directories(self) -> None:
        """Ensure all configured directories exist."""
        for dir_path in [self.CONFIG_DIR, self.LOGS_DIR, self.DATA_DIR, self.UPLOADS_DIR]:
            os.makedirs(dir_path, exist_ok=True)


# Global config instance
config = DDFNConfig()
