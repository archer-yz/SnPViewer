"""
Dataset model for Touchstone files.

Represents a loaded Touchstone file with all its S-parameter data,
metadata, and derived information.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class Dataset:
    """
    Touchstone dataset with complete file information and S-parameter data.

    This class represents a loaded Touchstone file containing n-port S-parameter
    measurements across frequency. It includes all metadata from the file header
    and provides methods for data access and integrity checking.

    Attributes:
        id: Unique identifier for this dataset (stable hash of path+mtime+size)
        file_path: Full path to the Touchstone file
        file_name: Display name of the file (basename)
        n_ports: Number of ports in the network
        frequency_hz: Frequency points in Hz (converted from file units)
        version: Touchstone version ('v1' or 'v2')
        units: Original frequency units from file ('Hz', 'kHz', 'MHz', 'GHz')
        ref_impedance: Reference impedance in ohms (default 50.0)
        data_format: Data format ('DB', 'MA', 'RI')
        s_params: S-parameter matrix [freq, n_ports, n_ports] (complex)
        loaded_at: Timestamp when data was loaded
        file_size: Size of source file in bytes
        file_modified: Last modification time of source file
        load_error: Error message if loading failed
        derived_caches: Cached converted parameters (Z, Y, etc.)
    """
    id: str
    file_path: str
    file_name: str
    n_ports: int
    frequency_hz: np.ndarray
    version: str
    units: str
    ref_impedance: float
    data_format: str
    s_params: np.ndarray
    loaded_at: datetime = field(default_factory=datetime.now)
    file_size: Optional[int] = None
    file_modified: Optional[datetime] = None
    load_error: Optional[str] = None
    derived_caches: Dict[str, np.ndarray] = field(default_factory=dict)

    @classmethod
    def create_id(cls, file_path: str, file_size: Optional[int] = None,
                  file_modified: Optional[datetime] = None) -> str:
        """
        Create a stable dataset ID from file metadata.

        The ID is a hash of the file path, modification time, and size.
        This ensures the same physical file gets the same ID, but changes
        to the file result in a new ID.

        Args:
            file_path: Path to the file
            file_size: Size of the file in bytes
            file_modified: Last modification time

        Returns:
            Stable string identifier for the dataset
        """
        path_obj = Path(file_path)

        # Get file stats if not provided
        if path_obj.exists():
            stat = path_obj.stat()
            if file_size is None:
                file_size = stat.st_size
            if file_modified is None:
                file_modified = datetime.fromtimestamp(stat.st_mtime)

        # Create hash from path + metadata
        hasher = hashlib.sha256()
        hasher.update(str(path_obj.absolute()).encode('utf-8'))

        if file_size is not None:
            hasher.update(str(file_size).encode('utf-8'))

        if file_modified is not None:
            hasher.update(file_modified.isoformat().encode('utf-8'))

        return hasher.hexdigest()[:16]  # Use first 16 chars for readability

    def get_frequency_range(self) -> tuple[float, float]:
        """
        Get the frequency range of the dataset.

        Returns:
            Tuple of (min_frequency, max_frequency) in Hz
        """
        if len(self.frequency_hz) == 0:
            return (0.0, 0.0)
        return (float(np.min(self.frequency_hz)), float(np.max(self.frequency_hz)))

    def get_s_parameter(self, i: int, j: int) -> np.ndarray:
        """
        Get S-parameter for specific port pair.

        Args:
            i: Input port (1-indexed)
            j: Output port (1-indexed)

        Returns:
            Complex S-parameter values across frequency

        Raises:
            IndexError: If port indices are out of range
        """
        if not (1 <= i <= self.n_ports and 1 <= j <= self.n_ports):
            raise IndexError(
                f"Port indices ({i}, {j}) out of range for {self.n_ports}-port network"
            )

        # Convert to 0-indexed for array access
        return self.s_params[:, i-1, j-1].copy()

    def get_port_pairs(self) -> list[tuple[int, int]]:
        """
        Get all valid port pairs for this dataset.

        Returns:
            List of (i, j) port pairs (1-indexed)
        """
        pairs = []
        for i in range(1, self.n_ports + 1):
            for j in range(1, self.n_ports + 1):
                pairs.append((i, j))
        return pairs

    def get_cached_parameter(self, domain: str) -> Optional[np.ndarray]:
        """
        Get cached converted parameters (Z, Y, etc.).

        Args:
            domain: Parameter domain ('Z', 'Y', 'ABCD', 'h', 'g', 'T')

        Returns:
            Cached parameter array if available, None otherwise
        """
        return self.derived_caches.get(domain)

    def set_cached_parameter(self, domain: str, data: np.ndarray) -> None:
        """
        Cache converted parameters for future use.

        Args:
            domain: Parameter domain ('Z', 'Y', 'ABCD', 'h', 'g', 'T')
            data: Converted parameter array
        """
        self.derived_caches[domain] = data.copy()

    def clear_caches(self) -> None:
        """Clear all cached derived parameters."""
        self.derived_caches.clear()

    def validate_integrity(self) -> bool:
        """
        Validate dataset integrity.

        Checks that arrays have consistent shapes and reasonable values.

        Returns:
            True if dataset appears valid, False otherwise
        """
        try:
            # Check basic shape consistency
            n_freq = len(self.frequency_hz)
            if self.s_params.shape != (n_freq, self.n_ports, self.n_ports):
                return False

            # Check frequency is monotonic
            if n_freq > 1 and not np.all(np.diff(self.frequency_hz) > 0):
                return False

            # Check S-parameters are finite
            if not np.all(np.isfinite(self.s_params)):
                return False

            # Check S-parameter magnitudes are reasonable (< 10 for passive devices)
            s_magnitudes = np.abs(self.s_params)
            if np.any(s_magnitudes > 10.0):
                return False

            return True

        except Exception:
            return False

    def get_summary_info(self) -> Dict[str, Any]:
        """
        Get summary information about the dataset.

        Returns:
            Dictionary with key dataset information
        """
        freq_min, freq_max = self.get_frequency_range()

        return {
            'id': self.id,
            'file_name': self.file_name,
            'n_ports': self.n_ports,
            'n_frequencies': len(self.frequency_hz),
            'frequency_range_hz': (freq_min, freq_max),
            'frequency_range_display': self._format_frequency_range(freq_min, freq_max),
            'version': self.version,
            'data_format': self.data_format,
            'ref_impedance': self.ref_impedance,
            'file_size': self.file_size,
            'loaded_at': self.loaded_at.isoformat(),
            'has_errors': self.load_error is not None
        }

    def _format_frequency_range(self, freq_min: float, freq_max: float) -> str:
        """
        Format frequency range for display.

        Args:
            freq_min: Minimum frequency in Hz
            freq_max: Maximum frequency in Hz

        Returns:
            Human-readable frequency range string
        """
        def format_freq(freq: float) -> str:
            if freq >= 1e9:
                return f"{freq/1e9:.2f} GHz"
            elif freq >= 1e6:
                return f"{freq/1e6:.2f} MHz"
            elif freq >= 1e3:
                return f"{freq/1e3:.2f} kHz"
            else:
                return f"{freq:.0f} Hz"

        if freq_min == freq_max:
            return format_freq(freq_min)
        else:
            return f"{format_freq(freq_min)} - {format_freq(freq_max)}"

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert dataset to dictionary for serialization.

        Note: This excludes the large numpy arrays to keep serialized
        size reasonable. Arrays can be reconstructed by re-parsing the file.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'file_path': self.file_path,
            'file_name': self.file_name,
            'n_ports': self.n_ports,
            'version': self.version,
            'units': self.units,
            'ref_impedance': self.ref_impedance,
            'data_format': self.data_format,
            'loaded_at': self.loaded_at.isoformat(),
            'file_size': self.file_size,
            'file_modified': self.file_modified.isoformat() if self.file_modified else None,
            'load_error': self.load_error,
            'frequency_range_hz': self.get_frequency_range(),
            'n_frequencies': len(self.frequency_hz)
        }
