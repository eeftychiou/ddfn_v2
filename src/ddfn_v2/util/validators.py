"""
Input validation utilities for ddfn_v2.

Provides centralized validation functions and Pydantic types for:
- File path validation (directory traversal protection)
- ID sanitization (sector IDs, flight IDs)
- FIR identifier validation
- Time string validation
- Capacity value validation
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Set
from pydantic import BeforeValidator, ValidationInfo
from typing_extensions import Annotated


# =============================================================================
# Constants
# =============================================================================

# Allowed base directories for file operations
DEFAULT_ALLOWED_BASE_DIRS: List[str] = ["uploads", "data", "node_configs", "AIXM"]

# Regex patterns for validation
SECTOR_ID_PATTERN = re.compile(r'^[A-Z0-9_-]+$')
FLIGHT_ID_PATTERN = re.compile(r'^[A-Z0-9]+$')
FIR_ID_PATTERN = re.compile(r'^[A-Z]{4}$')
TIME_STRING_PATTERN = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')
CONFIG_NAME_PATTERN = re.compile(r'^[\w\s-]{1,100}$')

# Maximum lengths
MAX_ID_LENGTH = 50
MAX_CONFIG_NAME_LENGTH = 100
MAX_FILE_PATH_LENGTH = 500


# =============================================================================
# File Path Validation
# =============================================================================

def validate_file_path(
    path: str,
    allowed_base_dirs: Optional[List[str]] = None,
    must_exist: bool = False,
    allowed_extensions: Optional[Set[str]] = None
) -> str:
    """
    Validate a file path to prevent directory traversal attacks.

    Args:
        path: The file path to validate
        allowed_base_dirs: List of allowed base directory names (relative to project root)
        must_exist: Whether the file must exist
        allowed_extensions: Set of allowed file extensions (e.g., {'.xml', '.json'})

    Returns:
        The validated absolute path

    Raises:
        ValueError: If the path is invalid or contains traversal attempts
    """
    if not path or not isinstance(path, str):
        raise ValueError("File path must be a non-empty string")

    if len(path) > MAX_FILE_PATH_LENGTH:
        raise ValueError(f"File path exceeds maximum length of {MAX_FILE_PATH_LENGTH}")

    # Check for directory traversal attempts
    if '..' in path or '~' in path:
        raise ValueError("File path contains directory traversal attempt")

    # Normalize the path
    try:
        normalized_path = Path(path).resolve()
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid file path: {e}")

    # Check extension if specified
    if allowed_extensions:
        ext = normalized_path.suffix.lower()
        if ext not in allowed_extensions:
            raise ValueError(f"File extension '{ext}' not allowed. Allowed: {allowed_extensions}")

    # Determine allowed base directories
    if allowed_base_dirs is None:
        allowed_base_dirs = DEFAULT_ALLOWED_BASE_DIRS

    # Find project root (assume we're in src/ddfn_v2/util/)
    # validators.py is at: project_root/src/ddfn_v2/util/validators.py
    # So we need to go up 4 levels: util -> ddfn_v2 -> src -> project_root
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent

    # Check if path is within allowed directories
    is_allowed = False
    for base_dir in allowed_base_dirs:
        allowed_path = (project_root / base_dir).resolve()
        try:
            # Check if normalized_path is within allowed_path
            normalized_path.relative_to(allowed_path)
            is_allowed = True
            break
        except ValueError:
            continue

    if not is_allowed:
        raise ValueError(
            f"File path '{path}' is not within allowed directories: {allowed_base_dirs}"
        )

    # Check if file exists if required
    if must_exist and not normalized_path.exists():
        raise ValueError(f"File does not exist: {path}")

    return str(normalized_path)


def validate_file_path_for_aixm(path: str, must_exist: bool = False) -> str:
    """
    Validate an AIXM file path.

    Args:
        path: The file path to validate
        must_exist: Whether the file must exist

    Returns:
        The validated absolute path
    """
    return validate_file_path(
        path,
        allowed_base_dirs=DEFAULT_ALLOWED_BASE_DIRS,
        must_exist=must_exist,
        allowed_extensions={'.xml'}
    )


# =============================================================================
# ID Validation and Sanitization
# =============================================================================

def sanitize_id(id_str: str, pattern: re.Pattern, id_type: str = "ID") -> str:
    """
    Sanitize and validate an identifier string.

    Args:
        id_str: The identifier to validate
        pattern: Regex pattern to match against
        id_type: Type of ID for error messages (e.g., "Sector ID", "Flight ID")

    Returns:
        The sanitized ID string

    Raises:
        ValueError: If the ID is invalid
    """
    if not id_str or not isinstance(id_str, str):
        raise ValueError(f"{id_type} must be a non-empty string")

    # Strip whitespace
    id_str = id_str.strip().upper()

    if len(id_str) > MAX_ID_LENGTH:
        raise ValueError(f"{id_type} exceeds maximum length of {MAX_ID_LENGTH}")

    if not pattern.match(id_str):
        raise ValueError(
            f"{id_type} '{id_str}' contains invalid characters. "
            f"Allowed: alphanumeric, underscores, hyphens"
        )

    return id_str


def validate_sector_id(sector_id: str) -> str:
    """
    Validate a sector identifier.

    Args:
        sector_id: The sector ID to validate

    Returns:
        The validated sector ID
    """
    return sanitize_id(sector_id, SECTOR_ID_PATTERN, "Sector ID")


def validate_flight_id(flight_id: str) -> str:
    """
    Validate a flight identifier.

    Args:
        flight_id: The flight ID to validate

    Returns:
        The validated flight ID
    """
    return sanitize_id(flight_id, FLIGHT_ID_PATTERN, "Flight ID")


def validate_fir_id(fir_id: str) -> str:
    """
    Validate a FIR (Flight Information Region) identifier.

    Args:
        fir_id: The FIR ID to validate (e.g., "LGGG", "EGTT")

    Returns:
        The validated FIR ID
    """
    if not fir_id or not isinstance(fir_id, str):
        raise ValueError("FIR ID must be a non-empty string")

    fir_id = fir_id.strip().upper()

    if not FIR_ID_PATTERN.match(fir_id):
        raise ValueError(
            f"FIR ID '{fir_id}' is invalid. Must be 4 uppercase letters (e.g., LGGG, EGTT)"
        )

    return fir_id


# =============================================================================
# Value Validation
# =============================================================================

def validate_capacity_value(capacity: int, field_name: str = "Capacity") -> int:
    """
    Validate a capacity value.

    Args:
        capacity: The capacity value to validate
        field_name: Name of the field for error messages

    Returns:
        The validated capacity value
    """
    if not isinstance(capacity, int):
        try:
            capacity = int(capacity)
        except (ValueError, TypeError):
            raise ValueError(f"{field_name} must be an integer")

    if capacity < 1 or capacity > 10000:
        raise ValueError(f"{field_name} must be between 1 and 10000")

    return capacity


def validate_time_string(time_str: str, field_name: str = "Time") -> str:
    """
    Validate a time string in HH:MM format.

    Args:
        time_str: The time string to validate
        field_name: Name of the field for error messages

    Returns:
        The validated time string
    """
    if not time_str or not isinstance(time_str, str):
        raise ValueError(f"{field_name} must be a non-empty string")

    time_str = time_str.strip()

    if not TIME_STRING_PATTERN.match(time_str):
        raise ValueError(f"{field_name} '{time_str}' is invalid. Must be in HH:MM format")

    return time_str


def validate_window_size(minutes: int) -> int:
    """
    Validate a measurement window size in minutes.

    Args:
        minutes: The window size to validate

    Returns:
        The validated window size
    """
    if not isinstance(minutes, int):
        try:
            minutes = int(minutes)
        except (ValueError, TypeError):
            raise ValueError("Window size must be an integer")

    if minutes < 1 or minutes > 480:
        raise ValueError("Window size must be between 1 and 480 minutes (8 hours)")

    return minutes


def validate_config_name(name: str) -> str:
    """
    Validate a configuration name.

    Args:
        name: The configuration name to validate

    Returns:
        The validated configuration name
    """
    if not name or not isinstance(name, str):
        raise ValueError("Configuration name must be a non-empty string")

    name = name.strip()

    if len(name) > MAX_CONFIG_NAME_LENGTH:
        raise ValueError(f"Configuration name exceeds maximum length of {MAX_CONFIG_NAME_LENGTH}")

    if not CONFIG_NAME_PATTERN.match(name):
        raise ValueError(
            "Configuration name contains invalid characters. "
            "Allowed: alphanumeric, spaces, underscores, hyphens"
        )

    return name


# =============================================================================
# Pydantic Custom Types
# =============================================================================

def _validate_safe_path(value: str, info: ValidationInfo) -> str:
    """Validator function for SafePath type."""
    # Get context from field info if available
    allowed_dirs = None
    must_exist = False
    allowed_exts = None

    if info.context:
        allowed_dirs = info.context.get('allowed_base_dirs')
        must_exist = info.context.get('must_exist', False)
        allowed_exts = info.context.get('allowed_extensions')

    return validate_file_path(value, allowed_dirs, must_exist, allowed_exts)


def _validate_sector_id(value: str) -> str:
    """Validator function for SectorId type."""
    return validate_sector_id(value)


def _validate_flight_id(value: str) -> str:
    """Validator function for FlightId type."""
    return validate_flight_id(value)


def _validate_fir_id(value: str) -> str:
    """Validator function for FirId type."""
    return validate_fir_id(value)


# Pydantic custom types using Annotated
SafePath = Annotated[str, BeforeValidator(_validate_safe_path)]
SectorId = Annotated[str, BeforeValidator(_validate_sector_id)]
FlightId = Annotated[str, BeforeValidator(_validate_flight_id)]
FirId = Annotated[str, BeforeValidator(_validate_fir_id)]


# =============================================================================
# List Validation Helpers
# =============================================================================

def validate_sector_ids(sector_ids: List[str]) -> List[str]:
    """
    Validate a list of sector IDs.

    Args:
        sector_ids: List of sector IDs to validate

    Returns:
        List of validated sector IDs
    """
    if not isinstance(sector_ids, list):
        raise ValueError("Sector IDs must be a list")

    if len(sector_ids) < 1:
        raise ValueError("At least one sector ID is required")

    if len(sector_ids) > 100:
        raise ValueError("Cannot process more than 100 sector IDs at once")

    return [validate_sector_id(sid) for sid in sector_ids]


def validate_flight_ids(flight_ids: List[str]) -> List[str]:
    """
    Validate a list of flight IDs.

    Args:
        flight_ids: List of flight IDs to validate

    Returns:
        List of validated flight IDs
    """
    if not isinstance(flight_ids, list):
        raise ValueError("Flight IDs must be a list")

    if len(flight_ids) > 1000:
        raise ValueError("Cannot process more than 1000 flight IDs at once")

    return [validate_flight_id(fid) for fid in flight_ids]
