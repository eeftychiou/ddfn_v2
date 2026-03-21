"""
Pydantic request models for API endpoint validation.

This module defines request/response models for FastAPI endpoints
to ensure proper input validation and type safety.
"""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from ddfn_v2.util.validators import (
    validate_file_path_for_aixm,
    validate_sector_id,
    validate_fir_id,
    validate_capacity_value,
    validate_time_string,
    validate_window_size,
    validate_config_name,
    validate_sector_ids,
    SectorId,
    FlightId,
    FirId,
)


# =============================================================================
# AIXM File Request Models
# =============================================================================

class AIXMFileRequest(BaseModel):
    """Request model for endpoints that require an AIXM file path."""
    file_path: str = Field(..., description="Path to the AIXM XML file")
    fir_id: Optional[str] = Field(None, description="Optional FIR identifier filter")

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        return validate_file_path_for_aixm(v, must_exist=True)

    @field_validator('fir_id')
    @classmethod
    def validate_fir(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_fir_id(v)
        return v


class AIXMUploadResponse(BaseModel):
    """Response model for AIXM file upload."""
    status: str
    file_path: Optional[str] = None
    message: Optional[str] = None


# =============================================================================
# Configuration Request Models
# =============================================================================

class SetupConfigurationRequest(BaseModel):
    """Request model for /api/setup/configure endpoint."""
    file_path: str = Field(..., description="Path to the AIXM XML file")
    fir_id: str = Field(..., description="FIR identifier (e.g., LGGG, EGTT)")
    window_size: int = Field(default=120, description="Measurement window size in minutes (15-480)")
    config_name: Optional[str] = Field(default=None, description="Name for this configuration")

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        return validate_file_path_for_aixm(v, must_exist=True)

    @field_validator('fir_id')
    @classmethod
    def validate_fir(cls, v: str) -> str:
        return validate_fir_id(v)

    @field_validator('window_size')
    @classmethod
    def validate_window(cls, v: int) -> int:
        return validate_window_size(v)

    @field_validator('config_name')
    @classmethod
    def validate_config(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_config_name(v)
        return v


class ApplyAIXMConfigRequest(BaseModel):
    """Request model for /api/config/apply_aixm endpoint."""
    file_path: str = Field(..., description="Path to the AIXM XML file")
    fir_id: str = Field(..., description="FIR identifier")
    sectors: List[dict] = Field(..., description="List of selected sectors with id, fl_lower, fl_upper")
    config_name: Optional[str] = Field(default=None, description="Name for this configuration")

    @field_validator('file_path')
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        return validate_file_path_for_aixm(v, must_exist=True)

    @field_validator('fir_id')
    @classmethod
    def validate_fir(cls, v: str) -> str:
        return validate_fir_id(v)

    @field_validator('sectors')
    @classmethod
    def validate_sectors(cls, v: List[dict]) -> List[dict]:
        if not v:
            raise ValueError("At least one sector must be selected")
        if len(v) > 100:
            raise ValueError("Cannot select more than 100 sectors at once")

        # Validate each sector has required fields
        for sector in v:
            if not isinstance(sector, dict):
                raise ValueError("Each sector must be a dictionary")
            if 'id' not in sector:
                raise ValueError("Each sector must have an 'id' field")
            # Validate sector ID
            validate_sector_id(sector['id'])

        return v

    @field_validator('config_name')
    @classmethod
    def validate_config(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_config_name(v)
        return v


class ApplyConfigurationRequest(BaseModel):
    """Request model for /api/configurations/apply endpoint."""
    target_node: str = Field(..., description="Target node ID")
    config_name: str = Field(..., description="Name of the configuration to apply")

    @field_validator('target_node')
    @classmethod
    def validate_node(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Target node must be a non-empty string")
        v = v.strip()
        if len(v) > 100:
            raise ValueError("Target node ID exceeds maximum length")
        return v

    @field_validator('config_name')
    @classmethod
    def validate_config(cls, v: str) -> str:
        return validate_config_name(v)


class LoadConfigurationRequest(BaseModel):
    """Request model for /api/config/load endpoint."""
    name: str = Field(..., description="Name of the configuration to load")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_config_name(v)


# =============================================================================
# Sector Management Request Models
# =============================================================================

class CapacityOverrideRequest(BaseModel):
    """Request model for /api/sectors/override endpoint."""
    target_node: str = Field(..., description="Target node ID")
    sector: str = Field(..., description="Sector ID to override")
    capacity: int = Field(..., description="New capacity value (flights per hour)")
    start_time: str = Field(default="00:00", description="Start time in HH:MM format")
    end_time: str = Field(default="23:59", description="End time in HH:MM format")
    reason: str = Field(default="WEATHER", description="Reason for the override")

    @field_validator('target_node')
    @classmethod
    def validate_node(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Target node must be a non-empty string")
        return v.strip()

    @field_validator('sector')
    @classmethod
    def validate_sector(cls, v: str) -> str:
        return validate_sector_id(v)

    @field_validator('capacity')
    @classmethod
    def validate_cap(cls, v: int) -> int:
        return validate_capacity_value(v)

    @field_validator('start_time')
    @classmethod
    def validate_start(cls, v: str) -> str:
        return validate_time_string(v, "Start time")

    @field_validator('end_time')
    @classmethod
    def validate_end(cls, v: str) -> str:
        return validate_time_string(v, "End time")

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v: str) -> str:
        allowed_reasons = {"WEATHER", "STAFFING", "EQUIPMENT", "MILITARY", "OTHER"}
        v = v.strip().upper()
        if v not in allowed_reasons:
            raise ValueError(f"Reason must be one of: {allowed_reasons}")
        return v


class MergeSectorsRequest(BaseModel):
    """Request model for /api/sectors/merge endpoint."""
    target_node: str = Field(..., description="Target node ID")
    sector_ids: List[str] = Field(..., description="List of sector IDs to merge")
    virtual_id: str = Field(..., description="ID for the merged virtual sector")

    @field_validator('target_node')
    @classmethod
    def validate_node(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Target node must be a non-empty string")
        return v.strip()

    @field_validator('sector_ids')
    @classmethod
    def validate_sectors(cls, v: List[str]) -> List[str]:
        return validate_sector_ids(v)

    @field_validator('virtual_id')
    @classmethod
    def validate_virtual_id(cls, v: str) -> str:
        return validate_sector_id(v)


class SetWindowRequest(BaseModel):
    """Request model for /api/sectors/window endpoint."""
    node_id: str = Field(..., description="Target node ID")
    measure_window: int = Field(..., description="Measurement window in minutes")

    @field_validator('node_id')
    @classmethod
    def validate_node(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Node ID must be a non-empty string")
        return v.strip()

    @field_validator('measure_window')
    @classmethod
    def validate_window(cls, v: int) -> int:
        return validate_window_size(v)


class RemoveOverrideRequest(BaseModel):
    """Request model for removing a capacity override."""
    target_node: str = Field(..., description="Target node ID")
    sector: str = Field(..., description="Sector ID")
    override_id: str = Field(..., description="ID of the override to remove")

    @field_validator('target_node')
    @classmethod
    def validate_node(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Target node must be a non-empty string")
        return v.strip()

    @field_validator('sector')
    @classmethod
    def validate_sector(cls, v: str) -> str:
        return validate_sector_id(v)

    @field_validator('override_id')
    @classmethod
    def validate_override_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Override ID must be a non-empty string")
        v = v.strip()
        if len(v) > 100:
            raise ValueError("Override ID exceeds maximum length")
        return v


# =============================================================================
# RAD Management Request Models
# =============================================================================

class RADToggleRequest(BaseModel):
    """Request model for /api/rad/toggle endpoint."""
    rule_id: str = Field(..., description="ID of the RAD rule to toggle")
    active: bool = Field(default=True, description="New active state for the rule")

    @field_validator('rule_id')
    @classmethod
    def validate_rule_id(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Rule ID must be a non-empty string")
        v = v.strip()
        if len(v) > 100:
            raise ValueError("Rule ID exceeds maximum length")
        # Allow alphanumeric, underscores, hyphens
        import re
        if not re.match(r'^[A-Z0-9_-]+$', v.upper()):
            raise ValueError("Rule ID contains invalid characters")
        return v.upper()


# =============================================================================
# Flight Management Request Models
# =============================================================================

class SlotSwapRequest(BaseModel):
    """Request model for slot swap operations."""
    target_node: str = Field(..., description="Target node ID")
    warning_id: str = Field(..., description="Warning ID for the regulation")
    flight_id_1: str = Field(..., description="First flight ID")
    flight_id_2: str = Field(..., description="Second flight ID")

    @field_validator('target_node')
    @classmethod
    def validate_node(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Target node must be a non-empty string")
        return v.strip()

    @field_validator('warning_id')
    @classmethod
    def validate_warning(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Warning ID must be a non-empty string")
        v = v.strip()
        if len(v) > 100:
            raise ValueError("Warning ID exceeds maximum length")
        return v

    @field_validator('flight_id_1', 'flight_id_2')
    @classmethod
    def validate_flight(cls, v: str) -> str:
        return validate_flight_id(v)


class FlightPlanRequest(BaseModel):
    """Request model for flight plan filing."""
    flight_id: str = Field(..., description="Flight identifier")
    origin: str = Field(..., description="Origin airport code")
    destination: str = Field(..., description="Destination airport code")
    route_string: str = Field(..., description="Route string")
    cruise_fl: int = Field(..., description="Cruise flight level")
    departure_time: str = Field(..., description="Departure time in ISO format")

    @field_validator('flight_id')
    @classmethod
    def validate_flight(cls, v: str) -> str:
        return validate_flight_id(v)

    @field_validator('origin', 'destination')
    @classmethod
    def validate_airport(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Airport code must be a non-empty string")
        v = v.strip().upper()
        if len(v) != 4:
            raise ValueError("Airport code must be 4 characters (ICAO format)")
        import re
        if not re.match(r'^[A-Z]{4}$', v):
            raise ValueError("Airport code must be 4 uppercase letters")
        return v

    @field_validator('cruise_fl')
    @classmethod
    def validate_fl(cls, v: int) -> int:
        if not isinstance(v, int):
            try:
                v = int(v)
            except (ValueError, TypeError):
                raise ValueError("Flight level must be an integer")
        if v < 10 or v > 660:
            raise ValueError("Flight level must be between 10 and 660")
        return v

    @field_validator('route_string')
    @classmethod
    def validate_route(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("Route string must be a non-empty string")
        v = v.strip()
        if len(v) > 1000:
            raise ValueError("Route string exceeds maximum length of 1000 characters")
        return v


# =============================================================================
# Response Models
# =============================================================================

class SuccessResponse(BaseModel):
    """Standard success response."""
    status: str = "success"
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    status: str = "error"
    message: str


class ConfigurationListResponse(BaseModel):
    """Response for configuration list endpoint."""
    status: str = "success"
    configs: List[str]


class SetupStatusResponse(BaseModel):
    """Response for setup status endpoint."""
    is_configured: bool
    node_id: str


class AIXMSourceResponse(BaseModel):
    """Response for AIXM source endpoint."""
    file_path: Optional[str] = None
    fir_id: Optional[str] = None
    config_name: str
