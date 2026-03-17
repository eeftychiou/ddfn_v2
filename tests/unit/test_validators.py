"""
Unit tests for the input validation utilities.

Tests cover:
- File path validation (directory traversal prevention)
- ID sanitization (sector IDs, flight IDs, FIR IDs)
- Value validation (capacity, time strings, window sizes)
"""

import os
import pytest
from pathlib import Path

# Import the validators module
from ddfn_v2.util.validators import (
    validate_file_path,
    validate_file_path_for_aixm,
    validate_sector_id,
    validate_flight_id,
    validate_fir_id,
    validate_capacity_value,
    validate_time_string,
    validate_window_size,
    validate_config_name,
    validate_sector_ids,
    SECTOR_ID_PATTERN,
    FLIGHT_ID_PATTERN,
    FIR_ID_PATTERN,
    DEFAULT_ALLOWED_BASE_DIRS,
)


# =============================================================================
# File Path Validation Tests
# =============================================================================

class TestFilePathValidation:
    """Tests for file path validation functions."""

    def test_valid_file_path_in_uploads(self):
        """Test that valid paths in uploads directory are accepted."""
        # Create a test file in the actual project uploads directory
        project_root = Path(__file__).parent.parent.parent
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        test_file = uploads_dir / "test_validation.xml"
        test_file.write_text("<test></test>")

        try:
            # Should not raise
            result = validate_file_path(str(test_file), allowed_base_dirs=["uploads"], must_exist=True)
            assert result == str(test_file.resolve())
        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()

    def test_valid_file_path_in_data(self):
        """Test that valid paths in data directory are accepted."""
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "data"
        data_dir.mkdir(exist_ok=True)
        test_file = data_dir / "test_validation.xml"
        test_file.write_text("<test></test>")

        try:
            result = validate_file_path(str(test_file), allowed_base_dirs=["data"], must_exist=True)
            assert result == str(test_file.resolve())
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_directory_traversal_with_double_dot(self):
        """Test that directory traversal with .. is rejected."""
        with pytest.raises(ValueError, match="directory traversal"):
            validate_file_path("../../../etc/passwd", allowed_base_dirs=["uploads"])

    def test_directory_traversal_with_tilde(self):
        """Test that directory traversal with ~ is rejected."""
        with pytest.raises(ValueError, match="directory traversal"):
            validate_file_path("~/.ssh/id_rsa", allowed_base_dirs=["uploads"])

    def test_path_outside_allowed_directories(self):
        """Test that paths outside allowed directories are rejected."""
        with pytest.raises(ValueError, match="not within allowed directories"):
            validate_file_path("/tmp/test.xml", allowed_base_dirs=["uploads"])

    def test_nonexistent_file_when_must_exist(self):
        """Test that non-existent files are rejected when must_exist=True."""
        project_root = Path(__file__).parent.parent.parent
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        test_file = uploads_dir / "nonexistent_validation.xml"

        with pytest.raises(ValueError, match="File does not exist"):
            validate_file_path(str(test_file), allowed_base_dirs=["uploads"], must_exist=True)

    def test_nonexistent_file_when_must_not_exist(self):
        """Test that non-existent files are accepted when must_exist=False."""
        project_root = Path(__file__).parent.parent.parent
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        test_file = uploads_dir / "nonexistent_validation.xml"

        # Should not raise
        result = validate_file_path(str(test_file), allowed_base_dirs=["uploads"], must_exist=False)
        assert result == str(test_file.resolve())

    def test_empty_file_path(self):
        """Test that empty file paths are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_file_path("")

    def test_none_file_path(self):
        """Test that None file paths are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_file_path(None)

    def test_file_path_too_long(self):
        """Test that very long file paths are rejected."""
        long_path = "uploads/" + "a" * 1000
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_file_path(long_path)

    def test_allowed_extensions_valid(self):
        """Test that files with allowed extensions are accepted."""
        project_root = Path(__file__).parent.parent.parent
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        test_file = uploads_dir / "test_validation.xml"
        test_file.write_text("<test></test>")

        try:
            result = validate_file_path(
                str(test_file),
                allowed_base_dirs=["uploads"],
                must_exist=True,
                allowed_extensions={".xml"}
            )
            assert result == str(test_file.resolve())
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_allowed_extensions_invalid(self):
        """Test that files with disallowed extensions are rejected."""
        project_root = Path(__file__).parent.parent.parent
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        test_file = uploads_dir / "test_validation.txt"
        test_file.write_text("test")

        try:
            with pytest.raises(ValueError, match="not allowed"):
                validate_file_path(
                    str(test_file),
                    allowed_base_dirs=["uploads"],
                    must_exist=True,
                    allowed_extensions={".xml"}
                )
        finally:
            if test_file.exists():
                test_file.unlink()


class TestAIXMFilePathValidation:
    """Tests for AIXM-specific file path validation."""

    def test_valid_aixm_file(self):
        """Test that valid AIXM files are accepted."""
        project_root = Path(__file__).parent.parent.parent
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        test_file = uploads_dir / "test_aixm_validation.xml"
        test_file.write_text("<test></test>")

        try:
            result = validate_file_path_for_aixm(str(test_file), must_exist=True)
            assert result == str(test_file.resolve())
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_aixm_file_wrong_extension(self):
        """Test that non-XML files are rejected for AIXM."""
        project_root = Path(__file__).parent.parent.parent
        uploads_dir = project_root / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        test_file = uploads_dir / "test_aixm_validation.txt"
        test_file.write_text("test")

        try:
            with pytest.raises(ValueError, match="not allowed"):
                validate_file_path_for_aixm(str(test_file), must_exist=True)
        finally:
            if test_file.exists():
                test_file.unlink()


# =============================================================================
# ID Validation Tests
# =============================================================================

class TestSectorIdValidation:
    """Tests for sector ID validation."""

    def test_valid_sector_id(self):
        """Test valid sector IDs."""
        assert validate_sector_id("LFFFUIR") == "LFFFUIR"
        assert validate_sector_id("LGGG") == "LGGG"
        assert validate_sector_id("SECTOR_01") == "SECTOR_01"
        assert validate_sector_id("sector-01") == "SECTOR-01"

    def test_sector_id_with_whitespace(self):
        """Test that sector IDs are stripped of whitespace."""
        assert validate_sector_id("  LFFFUIR  ") == "LFFFUIR"

    def test_sector_id_converted_to_uppercase(self):
        """Test that sector IDs are converted to uppercase."""
        assert validate_sector_id("lfffuir") == "LFFFUIR"

    def test_empty_sector_id(self):
        """Test that empty sector IDs are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_sector_id("")

    def test_none_sector_id(self):
        """Test that None sector IDs are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_sector_id(None)

    def test_sector_id_too_long(self):
        """Test that very long sector IDs are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_sector_id("A" * 51)

    def test_sector_id_invalid_characters(self):
        """Test that sector IDs with invalid characters are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_sector_id("LFFF/../etc")

    def test_sector_id_with_special_chars(self):
        """Test that sector IDs with special characters are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_sector_id("LFFF@#$%")


class TestFlightIdValidation:
    """Tests for flight ID validation."""

    def test_valid_flight_id(self):
        """Test valid flight IDs."""
        assert validate_flight_id("AAL123") == "AAL123"
        assert validate_flight_id("BAW456") == "BAW456"
        assert validate_flight_id("DLH789") == "DLH789"

    def test_flight_id_with_whitespace(self):
        """Test that flight IDs are stripped of whitespace."""
        assert validate_flight_id("  AAL123  ") == "AAL123"

    def test_flight_id_converted_to_uppercase(self):
        """Test that flight IDs are converted to uppercase."""
        assert validate_flight_id("aal123") == "AAL123"

    def test_empty_flight_id(self):
        """Test that empty flight IDs are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_flight_id("")

    def test_flight_id_with_underscore(self):
        """Test that flight IDs with underscores are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_flight_id("AAL_123")

    def test_flight_id_with_hyphen(self):
        """Test that flight IDs with hyphens are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_flight_id("AAL-123")


class TestFirIdValidation:
    """Tests for FIR ID validation."""

    def test_valid_fir_id(self):
        """Test valid FIR IDs."""
        assert validate_fir_id("LFFF") == "LFFF"
        assert validate_fir_id("LGGG") == "LGGG"
        assert validate_fir_id("EGTT") == "EGTT"
        assert validate_fir_id("EDDD") == "EDDD"

    def test_fir_id_with_whitespace(self):
        """Test that FIR IDs are stripped of whitespace."""
        assert validate_fir_id("  LFFF  ") == "LFFF"

    def test_fir_id_converted_to_uppercase(self):
        """Test that FIR IDs are converted to uppercase."""
        assert validate_fir_id("lfff") == "LFFF"

    def test_empty_fir_id(self):
        """Test that empty FIR IDs are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_fir_id("")

    def test_fir_id_too_short(self):
        """Test that FIR IDs with less than 4 characters are rejected."""
        with pytest.raises(ValueError, match="invalid"):
            validate_fir_id("LFF")

    def test_fir_id_too_long(self):
        """Test that FIR IDs with more than 4 characters are rejected."""
        with pytest.raises(ValueError, match="invalid"):
            validate_fir_id("LFFFF")

    def test_fir_id_with_numbers(self):
        """Test that FIR IDs with numbers are rejected."""
        with pytest.raises(ValueError, match="invalid"):
            validate_fir_id("LFF1")

    def test_fir_id_lowercase(self):
        """Test that lowercase FIR IDs are converted to uppercase."""
        assert validate_fir_id("lfff") == "LFFF"


# =============================================================================
# Value Validation Tests
# =============================================================================

class TestCapacityValidation:
    """Tests for capacity value validation."""

    def test_valid_capacity(self):
        """Test valid capacity values."""
        assert validate_capacity_value(1) == 1
        assert validate_capacity_value(40) == 40
        assert validate_capacity_value(100) == 100
        assert validate_capacity_value(10000) == 10000

    def test_capacity_string_conversion(self):
        """Test that string capacity values are converted to integers."""
        assert validate_capacity_value("40") == 40

    def test_capacity_zero(self):
        """Test that zero capacity is rejected."""
        with pytest.raises(ValueError, match="between 1 and 10000"):
            validate_capacity_value(0)

    def test_capacity_negative(self):
        """Test that negative capacity is rejected."""
        with pytest.raises(ValueError, match="between 1 and 10000"):
            validate_capacity_value(-1)

    def test_capacity_too_high(self):
        """Test that capacity over 10000 is rejected."""
        with pytest.raises(ValueError, match="between 1 and 10000"):
            validate_capacity_value(10001)

    def test_capacity_invalid_string(self):
        """Test that invalid string capacity is rejected."""
        with pytest.raises(ValueError, match="must be an integer"):
            validate_capacity_value("abc")


class TestTimeStringValidation:
    """Tests for time string validation."""

    def test_valid_time_strings(self):
        """Test valid time strings."""
        assert validate_time_string("00:00") == "00:00"
        assert validate_time_string("12:30") == "12:30"
        assert validate_time_string("23:59") == "23:59"
        assert validate_time_string("9:05") == "9:05"

    def test_time_string_with_whitespace(self):
        """Test that time strings are stripped of whitespace."""
        assert validate_time_string("  12:30  ") == "12:30"

    def test_empty_time_string(self):
        """Test that empty time strings are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_time_string("")

    def test_invalid_time_format(self):
        """Test that invalid time formats are rejected."""
        with pytest.raises(ValueError, match="invalid"):
            validate_time_string("25:00")

    def test_invalid_minutes(self):
        """Test that invalid minutes are rejected."""
        with pytest.raises(ValueError, match="invalid"):
            validate_time_string("12:60")

    def test_missing_colon(self):
        """Test that time strings without colon are rejected."""
        with pytest.raises(ValueError, match="invalid"):
            validate_time_string("1230")


class TestWindowSizeValidation:
    """Tests for window size validation."""

    def test_valid_window_sizes(self):
        """Test valid window sizes."""
        assert validate_window_size(15) == 15
        assert validate_window_size(60) == 60
        assert validate_window_size(120) == 120
        assert validate_window_size(480) == 480

    def test_window_size_string_conversion(self):
        """Test that string window sizes are converted to integers."""
        assert validate_window_size("120") == 120

    def test_window_size_too_small(self):
        """Test that window sizes below 15 are rejected."""
        with pytest.raises(ValueError, match="between 15 and 480"):
            validate_window_size(14)

    def test_window_size_too_large(self):
        """Test that window sizes above 480 are rejected."""
        with pytest.raises(ValueError, match="between 15 and 480"):
            validate_window_size(481)

    def test_window_size_invalid_string(self):
        """Test that invalid string window sizes are rejected."""
        with pytest.raises(ValueError, match="must be an integer"):
            validate_window_size("abc")


class TestConfigNameValidation:
    """Tests for configuration name validation."""

    def test_valid_config_names(self):
        """Test valid configuration names."""
        assert validate_config_name("Default") == "Default"
        assert validate_config_name("LGGG Config") == "LGGG Config"
        assert validate_config_name("Test-Config_123") == "Test-Config_123"

    def test_config_name_with_whitespace(self):
        """Test that config names are stripped of whitespace."""
        assert validate_config_name("  Default  ") == "Default"

    def test_empty_config_name(self):
        """Test that empty config names are rejected."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_config_name("")

    def test_config_name_too_long(self):
        """Test that very long config names are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum length"):
            validate_config_name("A" * 101)

    def test_config_name_invalid_characters(self):
        """Test that config names with invalid characters are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_config_name("Config@#$%")


# =============================================================================
# List Validation Tests
# =============================================================================

class TestSectorIdsValidation:
    """Tests for sector ID list validation."""

    def test_valid_sector_ids_list(self):
        """Test valid lists of sector IDs."""
        result = validate_sector_ids(["LFFF", "LGGG", "EGTT"])
        assert result == ["LFFF", "LGGG", "EGTT"]

    def test_sector_ids_converted_to_uppercase(self):
        """Test that sector IDs are converted to uppercase."""
        result = validate_sector_ids(["lfff", "lggg"])
        assert result == ["LFFF", "LGGG"]

    def test_empty_list(self):
        """Test that empty lists are rejected."""
        with pytest.raises(ValueError, match="At least one sector ID"):
            validate_sector_ids([])

    def test_not_a_list(self):
        """Test that non-list inputs are rejected."""
        with pytest.raises(ValueError, match="must be a list"):
            validate_sector_ids("LFFF")

    def test_too_many_sector_ids(self):
        """Test that lists with more than 100 IDs are rejected."""
        with pytest.raises(ValueError, match="more than 100"):
            validate_sector_ids([f"SECTOR{i}" for i in range(101)])

    def test_invalid_sector_id_in_list(self):
        """Test that lists with invalid sector IDs are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_sector_ids(["LFFF", "../etc"])


# =============================================================================
# Regex Pattern Tests
# =============================================================================

class TestRegexPatterns:
    """Tests for validation regex patterns."""

    def test_sector_id_pattern(self):
        """Test SECTOR_ID_PATTERN regex."""
        assert SECTOR_ID_PATTERN.match("LFFFUIR")
        assert SECTOR_ID_PATTERN.match("SECTOR_01")
        assert SECTOR_ID_PATTERN.match("SECTOR-01")
        assert SECTOR_ID_PATTERN.match("123ABC")
        assert not SECTOR_ID_PATTERN.match("sector.name")  # dot not allowed
        assert not SECTOR_ID_PATTERN.match("sector@name")  # @ not allowed

    def test_flight_id_pattern(self):
        """Test FLIGHT_ID_PATTERN regex."""
        assert FLIGHT_ID_PATTERN.match("AAL123")
        assert FLIGHT_ID_PATTERN.match("BAW456")
        assert not FLIGHT_ID_PATTERN.match("AAL_123")  # underscore not allowed
        assert not FLIGHT_ID_PATTERN.match("AAL-123")  # hyphen not allowed
        assert not FLIGHT_ID_PATTERN.match("AAL.123")  # dot not allowed

    def test_fir_id_pattern(self):
        """Test FIR_ID_PATTERN regex."""
        assert FIR_ID_PATTERN.match("LFFF")
        assert FIR_ID_PATTERN.match("LGGG")
        assert FIR_ID_PATTERN.match("EGTT")
        assert not FIR_ID_PATTERN.match("LFF")  # too short
        assert not FIR_ID_PATTERN.match("LFFFF")  # too long
        assert not FIR_ID_PATTERN.match("LFF1")  # number not allowed
        assert not FIR_ID_PATTERN.match("lfff")  # lowercase not allowed by pattern (but validated separately)


# =============================================================================
# Default Constants Tests
# =============================================================================

class TestDefaultConstants:
    """Tests for default constant values."""

    def test_default_allowed_base_dirs(self):
        """Test that default allowed base directories are correct."""
        assert "uploads" in DEFAULT_ALLOWED_BASE_DIRS
        assert "data" in DEFAULT_ALLOWED_BASE_DIRS
        assert "node_configs" in DEFAULT_ALLOWED_BASE_DIRS
