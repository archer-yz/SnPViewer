"""
S-parameter conversion functions and utilities.

Provides conversions between different network parameter representations:
- S ↔ Z, S ↔ Y parameter conversions
- 2-port matrix conversions: ABCD, h, g, T parameters
- Group delay calculation from S-parameters
- Phase unwrapping utilities

All functions support broadcasting over multiple frequency points.
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import numpy as np

from snpviewer.backend.models.dataset import Dataset


def s_to_z(s: np.ndarray, z0: float) -> np.ndarray:
    """
    Convert S-parameters to Z-parameters.

    Uses the transformation: Z = Z0 * (I + S) * (I - S)^-1

    Args:
        s: S-parameter matrix of shape (N_freq, n_ports, n_ports)
        z0: Reference impedance in ohms

    Returns:
        Z-parameter matrix of same shape as input

    Raises:
        ValueError: If S-matrix is not square or has invalid shape
    """
    if s.ndim != 3:
        raise ValueError("S-parameters must have shape (N_freq, n_ports, n_ports)")

    N, n, m = s.shape
    if N == 0:
        raise ValueError("Empty frequency array not supported")
    if n != m:
        raise ValueError("S-parameter matrices must be square")

    # Create identity matrix
    ident = np.eye(n, dtype=complex)

    # Allocate output array
    z = np.empty_like(s, dtype=complex)

    # Convert for each frequency point
    for k in range(N):
        s_k = s[k]
        # Z = Z0 * (I + S) * (I - S)^-1
        i_minus_s = ident - s_k
        i_plus_s = ident + s_k

        # Check for singular condition (det(I - S) ≈ 0)
        det_i_minus_s = np.linalg.det(i_minus_s)
        if abs(det_i_minus_s) < 1e-15:
            raise ValueError("Singular S-matrix: det(I - S) is zero")

        try:
            z[k] = z0 * i_plus_s @ np.linalg.inv(i_minus_s)
        except np.linalg.LinAlgError as e:
            raise ValueError(f"Singular S-matrix during conversion: {e}") from e

    return z


def z_to_s(z: np.ndarray, z0: float) -> np.ndarray:
    """
    Convert Z-parameters to S-parameters.

    Uses the transformation: S = (Z - Z0*I) * (Z + Z0*I)^-1

    Args:
        z: Z-parameter matrix of shape (N_freq, n_ports, n_ports)
        z0: Reference impedance in ohms

    Returns:
        S-parameter matrix of same shape as input

    Raises:
        ValueError: If Z-matrix is not square or has invalid shape
    """
    if z.ndim != 3:
        raise ValueError("Z-parameters must have shape (N_freq, n_ports, n_ports)")

    N, n, m = z.shape
    if N == 0:
        raise ValueError("Empty frequency array not supported")
    if n != m:
        raise ValueError("Z-parameter matrices must be square")

    # Create identity matrix
    ident = np.eye(n, dtype=complex)

    # Allocate output array
    s = np.empty_like(z, dtype=complex)

    # Convert for each frequency point
    for k in range(N):
        try:
            z_k = z[k]
            # S = (Z - Z0*I) * (Z + Z0*I)^-1
            z_minus_z0 = z_k - z0 * ident
            z_plus_z0 = z_k + z0 * ident
            s[k] = z_minus_z0 @ np.linalg.inv(z_plus_z0)
        except np.linalg.LinAlgError:
            # Matrix is singular
            s[k] = np.full_like(z_k, np.inf + 1j * np.inf)

    return s


def s_to_y(s: np.ndarray, z0: float) -> np.ndarray:
    """
    Convert S-parameters to Y-parameters.

    Uses the transformation: Y = (I - S) * (I + S)^-1 / Z0

    Args:
        s: S-parameter matrix of shape (N_freq, n_ports, n_ports)
        z0: Reference impedance in ohms

    Returns:
        Y-parameter matrix of same shape as input

    Raises:
        ValueError: If S-matrix is not square or has invalid shape
    """
    if s.ndim != 3:
        raise ValueError("S-parameters must have shape (N_freq, n_ports, n_ports)")

    N, n, m = s.shape
    if N == 0:
        raise ValueError("Empty frequency array not supported")
    if n != m:
        raise ValueError("S-parameter matrices must be square")

    # Create identity matrix
    ident = np.eye(n, dtype=complex)

    # Allocate output array
    y = np.empty_like(s, dtype=complex)

    # Convert for each frequency point
    for k in range(N):
        try:
            s_k = s[k]
            # Y = (I - S) * (I + S)^-1 / Z0
            i_minus_s = ident - s_k
            i_plus_s = ident + s_k
            y[k] = i_minus_s @ np.linalg.inv(i_plus_s) / z0
        except np.linalg.LinAlgError:
            # Matrix is singular
            y[k] = np.full_like(s_k, np.inf + 1j * np.inf)

    return y


def y_to_s(y: np.ndarray, z0: float) -> np.ndarray:
    """
    Convert Y-parameters to S-parameters.

    Uses the transformation: S = (I - Z0*Y) * (I + Z0*Y)^-1

    Args:
        y: Y-parameter matrix of shape (N_freq, n_ports, n_ports)
        z0: Reference impedance in ohms

    Returns:
        S-parameter matrix of same shape as input

    Raises:
        ValueError: If Y-matrix is not square or has invalid shape
    """
    if y.ndim != 3:
        raise ValueError("Y-parameters must have shape (N_freq, n_ports, n_ports)")

    N, n, m = y.shape
    if N == 0:
        raise ValueError("Empty frequency array not supported")
    if n != m:
        raise ValueError("Y-parameter matrices must be square")

    # Create identity matrix
    ident = np.eye(n, dtype=complex)

    # Allocate output array
    s = np.empty_like(y, dtype=complex)

    # Convert for each frequency point
    for k in range(N):
        try:
            y_k = y[k]
            # S = (I - Z0*Y) * (I + Z0*Y)^-1
            i_minus_z0y = ident - z0 * y_k
            i_plus_z0y = ident + z0 * y_k
            s[k] = i_minus_z0y @ np.linalg.inv(i_plus_z0y)
        except np.linalg.LinAlgError:
            # Matrix is singular
            s[k] = np.full_like(y_k, np.inf + 1j * np.inf)

    return s


# Additional conversion functions for 2-port networks
def s_to_abcd(s: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert 2-port S-parameters to ABCD-parameters."""
    if s.shape[1:] != (2, 2):
        raise ValueError("ABCD conversion only supports 2-port networks")

    N = s.shape[0]
    abcd = np.empty_like(s)

    for k in range(N):
        s11, s12, s21, s22 = s[k, 0, 0], s[k, 0, 1], s[k, 1, 0], s[k, 1, 1]

        # ABCD conversion formulas
        a = ((1 + s11) * (1 - s22) + s12 * s21) / (2 * s21)
        b = ((1 + s11) * (1 + s22) - s12 * s21) / (2 * s21)
        c = ((1 - s11) * (1 - s22) - s12 * s21) / (2 * s21)
        d = ((1 - s11) * (1 + s22) + s12 * s21) / (2 * s21)

        abcd[k] = np.array([[a, b], [c, d]], dtype=complex)

    return abcd


def abcd_to_s(abcd: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert 2-port ABCD-parameters to S-parameters."""
    if abcd.shape[1:] != (2, 2):
        raise ValueError("ABCD conversion only supports 2-port networks")

    N = abcd.shape[0]
    s = np.empty_like(abcd)

    for k in range(N):
        a, b, c, d = abcd[k, 0, 0], abcd[k, 0, 1], abcd[k, 1, 0], abcd[k, 1, 1]

        # Denominator for S-parameter conversion
        denom = a + b + c + d

        s11 = (a + b - c - d) / denom
        s12 = 2 * (a * d - b * c) / denom
        s21 = 2 / denom
        s22 = (-a + b - c + d) / denom

        s[k] = np.array([[s11, s12], [s21, s22]], dtype=complex)

    return s


# Placeholder implementations for other conversion functions
def s_to_h(s: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert S-parameters to h-parameters (2-port only)."""
    if s.shape[1:] != (2, 2):
        raise ValueError("h-parameter conversion only supports 2-port networks")

    # Convert via Z-parameters for simplicity
    z = s_to_z(s, z0)
    return z_to_h(z)


def h_to_s(h: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert h-parameters to S-parameters (2-port only)."""
    if h.shape[1:] != (2, 2):
        raise ValueError("h-parameter conversion only supports 2-port networks")

    # Convert via Z-parameters
    z = h_to_z(h)
    return z_to_s(z, z0)


def s_to_g(s: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert S-parameters to g-parameters (2-port only)."""
    if s.shape[1:] != (2, 2):
        raise ValueError("g-parameter conversion only supports 2-port networks")

    # Convert via Y-parameters
    y = s_to_y(s, z0)
    return y_to_g(y)


def g_to_s(g: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert g-parameters to S-parameters (2-port only)."""
    if g.shape[1:] != (2, 2):
        raise ValueError("g-parameter conversion only supports 2-port networks")

    # Convert via Y-parameters
    y = g_to_y(g)
    return y_to_s(y, z0)


def s_to_t(s: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert S-parameters to T-parameters (transmission parameters)."""
    if s.shape[1:] != (2, 2):
        raise ValueError("T-parameter conversion only supports 2-port networks")

    N = s.shape[0]
    t = np.empty_like(s)

    for k in range(N):
        s11, s12, s21, s22 = s[k, 0, 0], s[k, 0, 1], s[k, 1, 0], s[k, 1, 1]

        # T-parameter conversion
        det_s = s11 * s22 - s12 * s21

        t11 = -det_s / s21
        t12 = s11 / s21
        t21 = -s22 / s21
        t22 = 1 / s21

        t[k] = np.array([[t11, t12], [t21, t22]], dtype=complex)

    return t


def t_to_s(t: np.ndarray, z0: float = 50.0) -> np.ndarray:
    """Convert T-parameters to S-parameters."""
    if t.shape[1:] != (2, 2):
        raise ValueError("T-parameter conversion only supports 2-port networks")

    N = t.shape[0]
    s = np.empty_like(t)

    for k in range(N):
        t11, t12, t21, t22 = t[k, 0, 0], t[k, 0, 1], t[k, 1, 0], t[k, 1, 1]

        # S-parameter conversion
        det_t = t11 * t22 - t12 * t21

        s11 = t12 / t22
        s12 = det_t / t22
        s21 = 1 / t22
        s22 = -t21 / t22

        s[k] = np.array([[s11, s12], [s21, s22]], dtype=complex)

    return s


# Helper functions for parameter conversions
def z_to_h(z: np.ndarray) -> np.ndarray:
    """Convert Z-parameters to h-parameters (2-port only)."""
    if z.shape[1:] != (2, 2):
        raise ValueError("h-parameter conversion only supports 2-port networks")

    N = z.shape[0]
    h = np.empty_like(z)

    for k in range(N):
        # Using matrix formulation: H = [[Z11/Z22, ΔZ/Z22], [1/Z22, 1/Z22]]
        # where ΔZ = Z11*Z22 - Z12*Z21
        z_mat = z[k]
        z11, z12, z21, z22 = z_mat[0, 0], z_mat[0, 1], z_mat[1, 0], z_mat[1, 1]

        # Check for singular matrix
        if abs(z22) < 1e-15:
            raise ValueError("Singular Z-matrix: z22 is zero")

        det_z = z11 * z22 - z12 * z21

        h11 = det_z / z22
        h12 = z12 / z22
        h21 = -z21 / z22
        h22 = 1 / z22

        h[k] = np.array([[h11, h12], [h21, h22]], dtype=complex)

    return h


def h_to_z(h: np.ndarray) -> np.ndarray:
    """Convert h-parameters to Z-parameters (2-port only)."""
    if h.shape[1:] != (2, 2):
        raise ValueError("h-parameter conversion only supports 2-port networks")

    N = h.shape[0]
    z = np.empty_like(h)

    for k in range(N):
        h_mat = h[k]
        h11, h12, h21, h22 = h_mat[0, 0], h_mat[0, 1], h_mat[1, 0], h_mat[1, 1]

        # Check for singular matrix
        if abs(h22) < 1e-15:
            raise ValueError("Singular H-matrix: h22 is zero")

        det_h = h11 * h22 - h12 * h21

        z11 = det_h / h22
        z12 = h12 / h22
        z21 = -h21 / h22
        z22 = 1 / h22

        z[k] = np.array([[z11, z12], [z21, z22]], dtype=complex)

    return z


def y_to_g(y: np.ndarray) -> np.ndarray:
    """Convert Y-parameters to g-parameters (2-port only)."""
    if y.shape[1:] != (2, 2):
        raise ValueError("g-parameter conversion only supports 2-port networks")

    N = y.shape[0]
    g = np.empty_like(y)

    for k in range(N):
        y11, y12, y21, y22 = y[k, 0, 0], y[k, 0, 1], y[k, 1, 0], y[k, 1, 1]
        det_y = y11 * y22 - y12 * y21

        g11 = 1 / y11
        g12 = -y12 / y11
        g21 = y21 / y11
        g22 = det_y / y11

        g[k] = np.array([[g11, g12], [g21, g22]], dtype=complex)

    return g


def g_to_y(g: np.ndarray) -> np.ndarray:
    """Convert g-parameters to Y-parameters (2-port only)."""
    if g.shape[1:] != (2, 2):
        raise ValueError("g-parameter conversion only supports 2-port networks")

    N = g.shape[0]
    y = np.empty_like(g)

    for k in range(N):
        g11, g12, g21, g22 = g[k, 0, 0], g[k, 0, 1], g[k, 1, 0], g[k, 1, 1]
        det_g = g11 * g22 - g12 * g21

        y11 = 1 / g11
        y12 = -g12 / g11
        y21 = g21 / g11
        y22 = det_g / g11

        y[k] = np.array([[y11, y12], [y21, y22]], dtype=complex)

    return y


# Utility functions
def calculate_group_delay(freq: np.ndarray, s: np.ndarray, port1: int, port2: int) -> np.ndarray:
    """
    Calculate group delay from S-parameters for specific port pair.

    Args:
        freq: Frequency array in Hz
        s: S-parameter array of shape (N_freq, n_ports, n_ports)
        port1: Input port index (0-based)
        port2: Output port index (0-based)

    Returns:
        Group delay array of length N_freq, in seconds

    Raises:
        IndexError: If port indices are invalid
        ValueError: If input parameters are invalid
    """
    if s.ndim != 3:
        raise ValueError("S-parameters must have shape (N_freq, n_ports, n_ports)")

    N, n_ports, _ = s.shape
    if port1 >= n_ports or port2 >= n_ports or port1 < 0 or port2 < 0:
        raise IndexError(f"Port indices must be in range [0, {n_ports-1}]")

    if len(freq) < 2:
        raise ValueError("Need at least 2 frequency points for group delay calculation")

    # Extract S-parameter for the specific port pair
    s_param = s[:, port2, port1]  # S[port2,port1] - note the indexing order

    # Calculate phase
    phase = np.angle(s_param)

    # Unwrap phase to avoid discontinuities
    phase_unwrapped = np.unwrap(phase)

    # Calculate group delay as -d(phase)/d(omega)
    omega = 2 * np.pi * freq

    # Use gradient for numerical differentiation
    group_delay = -np.gradient(phase_unwrapped, omega)

    return group_delay


def unwrap_phase(phase: np.ndarray, axis: int = 0) -> np.ndarray:
    """
    Unwrap phase to remove 2π discontinuities.

    Args:
        phase: Phase array in radians
        axis: Axis along which to unwrap

    Returns:
        Unwrapped phase array
    """
    return np.unwrap(phase, axis=axis)


def touchstone_to_dataset(touchstone_data, file_path: str, metadata=None):
    """
    Convert TouchstoneData to Dataset format.

    Args:
        touchstone_data: Parsed Touchstone data
        file_path: Original file path
        metadata: Additional metadata to include

    Returns:
        Dataset object with converted data
    """
    if metadata is None:
        metadata = {}

    # Get file stats
    path_obj = Path(file_path)
    file_size = metadata.get('file_size')
    file_modified = metadata.get('modified_time')

    if path_obj.exists():
        stat = path_obj.stat()
        if file_size is None:
            file_size = stat.st_size
        if file_modified is None:
            file_modified = datetime.fromtimestamp(stat.st_mtime)
        elif isinstance(file_modified, (int, float)):
            # Convert timestamp to datetime if needed
            file_modified = datetime.fromtimestamp(file_modified)

    # Determine frequency units from the original data
    # This is a simplified heuristic - in practice you'd want to preserve
    # the original units from the file
    freq_max = np.max(touchstone_data.frequency_hz)
    if freq_max < 1e6:
        units = 'Hz'
    elif freq_max < 1e9:
        units = 'MHz'
    else:
        units = 'GHz'

    # Create Dataset with correct field names
    dataset = Dataset(
        id=Dataset.create_id(file_path, file_size, file_modified),
        file_path=file_path,
        file_name=path_obj.name,
        display_name=path_obj.stem,  # Default display name without extension
        n_ports=touchstone_data.n_ports,
        frequency_hz=touchstone_data.frequency_hz,
        version=touchstone_data.version,
        units=units,
        ref_impedance=touchstone_data.z0,
        data_format=touchstone_data.data_format,
        s_params=touchstone_data.s_params,
        file_size=file_size,
        file_modified=file_modified
    )

    return dataset
