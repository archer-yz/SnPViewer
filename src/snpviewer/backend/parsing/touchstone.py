"""
Touchstone file parser for S-parameter data.

Supports both Touchstone v1 and v2 formats with various data formats
(DB, MA, RI) and frequency units. Provides comprehensive error handling
and validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np


class TouchstoneError(ValueError):
    """Exception raised for Touchstone file parsing errors."""
    pass


@dataclass
class TouchstoneData:
    """
    Parsed Touchstone file data.

    Attributes:
        n_ports: Number of ports
        frequency_hz: Frequency points in Hz
        z0: Reference impedance in Ohms
        data_format: Data format ('DB', 'MA', 'RI')
        version: Touchstone version ('v1' or 'v2')
        s_params: S-parameter data array [freq, row, col]
        metadata: Additional file metadata
    """
    n_ports: int
    frequency_hz: np.ndarray
    z0: float
    data_format: str
    version: str
    s_params: np.ndarray
    metadata: Dict[str, Any]


def parse_touchstone(file_path: str) -> TouchstoneData:
    """
    Parse a Touchstone file and return structured data.

    Args:
        file_path: Path to the Touchstone file

    Returns:
        TouchstoneData object containing parsed data

    Raises:
        FileNotFoundError: If file doesn't exist
        TouchstoneError: If file format is invalid or unsupported
    """
    file_path_obj = Path(file_path)

    # Validate file exists
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Validate file extension
    if not _is_valid_touchstone_file(file_path_obj):
        raise TouchstoneError(f"Invalid file extension: {file_path_obj.suffix}")

    # Read file content
    try:
        with open(file_path_obj, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        # Try with latin-1 encoding for older files
        with open(file_path_obj, 'r', encoding='latin-1') as f:
            content = f.read()

    if not content.strip():
        raise TouchstoneError("Empty file")

    # Parse the file
    lines = content.split('\n')

    # Determine version and parse accordingly
    if _is_version_2(lines):
        return _parse_v2_format(lines, file_path_obj)
    else:
        return _parse_v1_format(lines, file_path_obj)


def _is_valid_touchstone_file(file_path: Path) -> bool:
    """Check if file has valid Touchstone extension."""
    suffix = file_path.suffix.lower()
    if suffix.startswith('.s') and len(suffix) >= 3:
        try:
            # Handle both .s1p and .s1 formats
            port_str = suffix[2:]
            if port_str.endswith('p'):
                port_str = port_str[:-1]  # Remove 'p' suffix
            port_count = int(port_str)
            return 1 <= port_count <= 99
        except ValueError:
            return False
    return False


def _is_version_2(lines: List[str]) -> bool:
    """Check if file is Touchstone v2 format."""
    for line in lines[:10]:  # Check first 10 lines
        if line.strip().lower().startswith('[version]'):
            return True
    return False


def _parse_v1_format(lines: List[str], file_path: Path) -> TouchstoneData:
    """Parse Touchstone v1 format file."""
    # Extract port count from extension
    n_ports = _get_port_count_from_extension(file_path)

    # Find header line
    header_line = None
    header_idx = -1
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('#') and not line.startswith('!'):
            header_line = line
            header_idx = i
            break

    if header_line is None:
        raise TouchstoneError("Failed to parse Touchstone file: No valid header found")    # Parse header
    freq_unit, param_type, data_format, z0 = _parse_v1_header(header_line)

    # Validate parameter type
    if param_type.upper() != 'S':
        raise TouchstoneError("Only S-parameters are supported in v1 format")

    # Parse data lines
    data_lines = []
    for line in lines[header_idx + 1:]:
        line = line.strip()
        if line and not line.startswith('!'):
            data_lines.append(line)

    if not data_lines:
        raise TouchstoneError("No data found in file")

    # Parse frequency and parameter data
    frequencies, s_params = _parse_v1_data(data_lines, n_ports, data_format)

    # Convert frequencies to Hz
    freq_multiplier = _get_frequency_multiplier(freq_unit)
    frequencies = frequencies * freq_multiplier

    # Create metadata
    metadata = {
        'filename': file_path.name,
        'file_size': file_path.stat().st_size if file_path.exists() else 0,
        'header_line': header_line,
        'frequency_unit': freq_unit,
        'parameter_type': param_type
    }

    return TouchstoneData(
        n_ports=n_ports,
        frequency_hz=frequencies,
        z0=z0,
        data_format=data_format,
        version='v1',
        s_params=s_params,
        metadata=metadata
    )


def _parse_v2_format(lines: List[str], file_path: Path) -> TouchstoneData:
    """Parse Touchstone v2 format file."""
    # Parse v2 keywords
    keywords = _parse_v2_keywords(lines)

    # Extract required information
    n_ports = keywords.get('number_of_ports')
    if n_ports is None:
        raise TouchstoneError("Missing required v2 keyword: [Number of Ports]")

    z0 = keywords.get('reference', 50.0)

    # Find header line (same as v1)
    header_line = None
    header_idx = -1
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('#') and not line.startswith('!'):
            header_line = line
            header_idx = i
            break

    if header_line is None:
        raise TouchstoneError("No valid header found in v2 file")

    # Parse header
    freq_unit, param_type, data_format, header_z0 = _parse_v1_header(header_line)

    # Use header z0 if provided, otherwise use keyword value
    if header_z0 != 50.0:  # Header overrides keyword if not default
        z0 = header_z0

    # Parse data lines
    data_lines = []
    for line in lines[header_idx + 1:]:
        line = line.strip()
        if line and not line.startswith('!') and not line.startswith('['):
            data_lines.append(line)

    if not data_lines:
        raise TouchstoneError("No data found in v2 file")

    # Parse frequency and parameter data
    frequencies, s_params = _parse_v1_data(data_lines, n_ports, data_format)

    # Convert frequencies to Hz
    freq_multiplier = _get_frequency_multiplier(freq_unit)
    frequencies = frequencies * freq_multiplier

    # Create metadata
    metadata = {
        'filename': file_path.name,
        'file_size': file_path.stat().st_size if file_path.exists() else 0,
        'header_line': header_line,
        'frequency_unit': freq_unit,
        'parameter_type': param_type,
        'v2_keywords': keywords
    }

    return TouchstoneData(
        n_ports=n_ports,
        frequency_hz=frequencies,
        z0=z0,
        data_format=data_format,
        version='v2',
        s_params=s_params,
        metadata=metadata
    )


def _get_port_count_from_extension(file_path: Path) -> int:
    """Extract port count from file extension."""
    suffix = file_path.suffix.lower()
    if suffix.startswith('.s'):
        try:
            # Handle both .s1p and .s1 formats
            port_str = suffix[2:]
            if port_str.endswith('p'):
                port_str = port_str[:-1]  # Remove 'p' suffix
            return int(port_str)
        except ValueError:
            raise TouchstoneError(f"Invalid file extension: {suffix}")
    raise TouchstoneError(f"Not a Touchstone file: {suffix}")


def _parse_v1_header(header_line: str) -> Tuple[str, str, str, float]:
    """
    Parse v1 format header line.

    Returns:
        Tuple of (frequency_unit, parameter_type, data_format, z0)
    """
    # Remove '#' and split
    parts = header_line[1:].strip().split()

    if len(parts) < 4:
        raise TouchstoneError(f"Invalid header format: {header_line}")

    freq_unit = parts[0].upper()
    param_type = parts[1].upper()
    data_format = parts[2].upper()

    # Parse reference impedance
    if parts[3].upper() != 'R':
        raise TouchstoneError(f"Expected 'R' for reference impedance, got: {parts[3]}")

    if len(parts) < 5:
        z0 = 50.0  # Default
    else:
        try:
            z0 = float(parts[4])
        except ValueError:
            raise TouchstoneError(f"Invalid reference impedance: {parts[4]}")

    # Validate values
    if freq_unit not in ['HZ', 'KHZ', 'MHZ', 'GHZ', 'THZ']:
        raise TouchstoneError(f"Invalid frequency unit: {freq_unit}")

    if data_format not in ['DB', 'MA', 'RI']:
        raise TouchstoneError(f"Invalid data format: {data_format}")

    if z0 <= 0:
        raise TouchstoneError("Reference impedance must be positive")

    return freq_unit, param_type, data_format, z0


def _parse_v2_keywords(lines: List[str]) -> Dict[str, Any]:
    """Parse v2 format keyword sections."""
    keywords = {}

    for line in lines:
        line = line.strip()

        # Handle both formats: [Keyword] Value and [Keyword Value]
        if line.startswith('['):
            # Find the closing bracket
            bracket_end = line.find(']')
            if bracket_end == -1:
                continue

            # Check if there's a value after the closing bracket
            if bracket_end < len(line) - 1:
                # Format: [Keyword] Value
                keyword_part = line[1:bracket_end].strip().lower()
                value_part = line[bracket_end + 1:].strip()
            else:
                # Format: [Keyword Value] - extract keyword and value from inside brackets
                keyword_line = line[1:bracket_end].strip().lower()

                if keyword_line.startswith('version'):
                    parts = keyword_line.split()
                    if len(parts) >= 2:
                        keywords['version'] = parts[1]
                elif keyword_line.startswith('number of ports'):
                    parts = keyword_line.split()
                    if len(parts) >= 4:
                        try:
                            keywords['number_of_ports'] = int(parts[3])
                        except ValueError:
                            pass
                elif keyword_line.startswith('reference'):
                    parts = keyword_line.split()
                    if len(parts) >= 2:
                        try:
                            keywords['reference'] = float(parts[1])
                        except ValueError:
                            pass
                elif keyword_line.startswith('matrix format'):
                    parts = keyword_line.split()
                    if len(parts) >= 3:
                        keywords['matrix_format'] = parts[2]
                continue

            # Process format: [Keyword] Value
            keyword_part = keyword_part.lower()

            if keyword_part == 'version':
                keywords['version'] = value_part
            elif keyword_part == 'number of ports':
                try:
                    keywords['number_of_ports'] = int(value_part)
                except ValueError:
                    pass
            elif keyword_part == 'reference':
                try:
                    keywords['reference'] = float(value_part)
                except ValueError:
                    pass
            elif keyword_part == 'matrix format':
                keywords['matrix_format'] = value_part

    return keywords


def _parse_v1_data(data_lines: List[str], n_ports: int,
                   data_format: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Parse v1 format data lines.

    Returns:
        Tuple of (frequencies, s_parameters)
    """
    expected_values_per_freq = 1 + 2 * n_ports * n_ports  # freq + 2*N^2 params

    # Join all data lines and split into tokens
    all_tokens = []
    for line in data_lines:
        # Remove inline comments (both ! and # for robustness)
        if '!' in line:
            line = line[:line.index('!')]
        elif '#' in line:
            line = line[:line.index('#')]
        tokens = line.split()
        all_tokens.extend(tokens)

    if len(all_tokens) == 0:
        raise TouchstoneError("No numeric data found")

    # Check if we have complete frequency points
    if len(all_tokens) % expected_values_per_freq != 0:
        if len(all_tokens) < expected_values_per_freq:
            raise TouchstoneError(
                f"insufficient values in data: expected {expected_values_per_freq} values per frequency "
                f"for {n_ports}-port file, got {len(all_tokens)} total values"
            )
        else:
            raise TouchstoneError(
                f"Data columns don't match expected count for {n_ports}-port file. "
                f"Expected {expected_values_per_freq} values per frequency, "
                f"got {len(all_tokens)} total values"
            )

    n_freqs = len(all_tokens) // expected_values_per_freq

    # Parse numeric values
    try:
        values = np.array([float(token) for token in all_tokens])
    except ValueError as e:
        raise TouchstoneError(f"Invalid numeric data: {e}")

    # Reshape into frequency points
    values = values.reshape(n_freqs, expected_values_per_freq)

    # Extract frequencies
    frequencies = values[:, 0]
    param_data = values[:, 1:]

    # Convert parameter data to complex S-parameters
    s_params = _convert_to_complex_matrix(param_data, n_ports, data_format)

    return frequencies, s_params


def _convert_to_complex_matrix(param_data: np.ndarray, n_ports: int,
                               data_format: str) -> np.ndarray:
    """
    Convert parameter data to complex S-parameter matrix.

    Args:
        param_data: Parameter data array [freq, param_values]
        n_ports: Number of ports
        data_format: Data format ('DB', 'MA', 'RI')

    Returns:
        Complex S-parameter array [freq, row, col]
    """
    n_freqs = param_data.shape[0]
    n_params = n_ports * n_ports

    # Reshape to [freq, param_index, real/imag]
    param_pairs = param_data.reshape(n_freqs, n_params, 2)

    # Convert based on format
    if data_format == 'RI':
        # Real/Imaginary format
        s_complex = param_pairs[:, :, 0] + 1j * param_pairs[:, :, 1]
    elif data_format == 'MA':
        # Magnitude/Angle format (angle in degrees)
        magnitude = param_pairs[:, :, 0]
        angle_deg = param_pairs[:, :, 1]
        angle_rad = np.radians(angle_deg)
        s_complex = magnitude * np.exp(1j * angle_rad)
    elif data_format == 'DB':
        # dB/Angle format (magnitude in dB, angle in degrees)
        magnitude_db = param_pairs[:, :, 0]
        angle_deg = param_pairs[:, :, 1]
        magnitude = 10**(magnitude_db / 20.0)
        angle_rad = np.radians(angle_deg)
        s_complex = magnitude * np.exp(1j * angle_rad)
    else:
        raise TouchstoneError(f"Unsupported data format: {data_format}")

    # Reshape to matrix form [freq, row, col]
    # Touchstone format is: S11, S21, S12, S22, S13, S23, S31, S32, S33, etc.
    # This is column-major order for the S-matrix
    s_matrix = np.zeros((n_freqs, n_ports, n_ports), dtype=complex)

    for freq_idx in range(n_freqs):
        param_idx = 0
        for col in range(n_ports):  # Input port (column index)
            for row in range(n_ports):  # Output port (row index)
                s_matrix[freq_idx, row, col] = s_complex[freq_idx, param_idx]
                param_idx += 1

    return s_matrix


def _get_frequency_multiplier(freq_unit: str) -> float:
    """Get multiplier to convert frequency unit to Hz."""
    multipliers = {
        'HZ': 1.0,
        'KHZ': 1e3,
        'MHZ': 1e6,
        'GHZ': 1e9,
        'THZ': 1e12
    }
    return multipliers.get(freq_unit.upper(), 1.0)
