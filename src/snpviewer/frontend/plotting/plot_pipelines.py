"""
Plot pipeline data preparation for PyQtGraph visualization.

Transforms S-parameter data into PyQtGraph-compatible arrays for various
plot types: magnitude, phase, group delay, and Smith chart presentations.
Handles unit conversions, data clipping, and coordinate transformations.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from snpviewer.backend.models.trace import Trace
from snpviewer.backend.smith import gamma_to_cartesian


class PlotType(Enum):
    """Supported plot types for S-parameter visualization."""
    MAGNITUDE = "magnitude"
    PHASE = "phase"
    GROUP_DELAY = "group_delay"
    SMITH = "smith"


@dataclass
class PlotData:
    """Container for plot-ready data with metadata."""
    x: np.ndarray
    y: np.ndarray
    plot_type: PlotType
    label: str = ""
    units_x: str = ""
    units_y: str = ""


def get_frequency_array(dataset, unit: str = 'Hz') -> np.ndarray:
    """
    Extract frequency array from dataset with unit conversion.

    Args:
        dataset: Dataset object with frequency attribute
        unit: Target frequency unit ('Hz', 'MHz', 'GHz')

    Returns:
        Frequency array in requested units
    """
    freq_hz = dataset.frequency_hz

    if unit == 'Hz':
        return freq_hz
    elif unit == 'MHz':
        return freq_hz / 1e6
    elif unit == 'GHz':
        return freq_hz / 1e9
    else:
        raise ValueError(f"Unsupported frequency unit: {unit}")


def convert_s_to_db(s_complex: np.ndarray) -> np.ndarray:
    """
    Convert complex S-parameters to magnitude in dB.

    Args:
        s_complex: Complex S-parameter array

    Returns:
        Magnitude in dB (20*log10|S|)
    """
    magnitude = np.abs(s_complex)

    # Handle zero magnitude to avoid -inf
    magnitude = np.maximum(magnitude, 1e-12)

    return 20 * np.log10(magnitude)


def convert_s_to_phase(s_complex: np.ndarray, degrees: bool = True) -> np.ndarray:
    """
    Convert complex S-parameters to phase.

    Args:
        s_complex: Complex S-parameter array
        degrees: If True, return phase in degrees; otherwise radians

    Returns:
        Phase array in requested units
    """
    phase_rad = np.angle(s_complex)

    if degrees:
        return phase_rad * 180 / np.pi
    else:
        return phase_rad


def unwrap_phase(phase: np.ndarray) -> np.ndarray:
    """
    Unwrap phase discontinuities.

    Args:
        phase: Phase array (any units)

    Returns:
        Unwrapped phase array
    """
    return np.unwrap(phase)


def compute_group_delay(frequency: np.ndarray, phase: np.ndarray) -> np.ndarray:
    """
    Compute group delay from frequency and phase data.

    Group delay = -dφ/dω where φ is phase and ω is angular frequency.

    Args:
        frequency: Frequency array in Hz
        phase: Phase array in radians

    Returns:
        Group delay array in seconds (one element shorter than input)
    """
    # Convert frequency to angular frequency
    omega = 2 * np.pi * frequency

    # Compute derivative using central difference
    dphase = np.diff(phase)
    domega = np.diff(omega)

    # Avoid division by zero
    domega = np.where(np.abs(domega) < 1e-15, 1e-15, domega)

    # Group delay (negative derivative)
    group_delay = -dphase / domega

    return group_delay


def _extract_s_parameter(s_matrix: np.ndarray, trace: Trace) -> np.ndarray:
    """
    Extract specific S-parameter from full matrix based on trace port path.

    Args:
        s_matrix: S-parameter matrix (N_freq, n_ports, n_ports)
        trace: Trace configuration with port path information

    Returns:
        Complex S-parameter array (N_freq,)
    """
    if trace.domain != "S":
        raise ValueError(f"Only S-parameters supported, got: {trace.domain}")

    # Convert from 1-based to 0-based indexing
    row = trace.port_path.i - 1
    col = trace.port_path.j - 1

    if row >= s_matrix.shape[1] or col >= s_matrix.shape[2]:
        raise IndexError(f"Port path ({trace.port_path.i}, {trace.port_path.j}) exceeds matrix size")

    return s_matrix[:, row, col]


def prepare_magnitude_data(trace: Trace, dataset, linear_scale: bool = False) -> PlotData:
    """
    Prepare magnitude plot data for given trace.

    Args:
        trace: Trace configuration
        dataset: Dataset containing S-parameter data
        linear_scale: If True, use linear scale; otherwise dB

    Returns:
        PlotData ready for plotting
    """
    freq = get_frequency_array(dataset, unit='Hz')
    s_param = _extract_s_parameter(dataset.s_params, trace)

    if linear_scale:
        y_data = np.abs(s_param)
        units_y = "Linear"
    else:
        y_data = convert_s_to_db(s_param)
        units_y = "dB"

    # Create label with display name
    display_name = getattr(dataset, 'display_name', getattr(dataset, 'file_name', 'Unknown'))
    param_label = f"{trace.domain}{trace.port_path.i},{trace.port_path.j}"
    label = f"{display_name}: {param_label}"

    return PlotData(
        x=freq,
        y=y_data,
        plot_type=PlotType.MAGNITUDE,
        label=label,
        units_x="Hz",
        units_y=units_y
    )


def prepare_phase_data(trace: Trace, dataset, degrees: bool = True, unwrap: bool = True) -> PlotData:
    """
    Prepare phase plot data for given trace.

    Args:
        trace: Trace configuration
        dataset: Dataset containing S-parameter data
        degrees: If True, use degrees; otherwise radians
        unwrap: If True, unwrap phase discontinuities

    Returns:
        PlotData ready for plotting
    """
    freq = get_frequency_array(dataset, unit='Hz')
    s_param = _extract_s_parameter(dataset.s_params, trace)

    phase = convert_s_to_phase(s_param, degrees=degrees)

    if unwrap:
        phase = unwrap_phase(phase)

    units_y = "Degrees" if degrees else "Radians"

    # Create label with display name
    display_name = getattr(dataset, 'display_name', getattr(dataset, 'file_name', 'Unknown'))
    param_label = f"{trace.domain}{trace.port_path.i},{trace.port_path.j}"
    label = f"{display_name}: {param_label}"

    return PlotData(
        x=freq,
        y=phase,
        plot_type=PlotType.PHASE,
        label=label,
        units_x="Hz",
        units_y=units_y
    )


def prepare_group_delay_data(trace: Trace, dataset) -> PlotData:
    """
    Prepare group delay plot data for given trace.

    Args:
        trace: Trace configuration
        dataset: Dataset containing S-parameter data

    Returns:
        PlotData ready for plotting
    """
    freq = get_frequency_array(dataset, unit='Hz')
    s_param = _extract_s_parameter(dataset.s_params, trace)

    # Get phase in radians
    phase = convert_s_to_phase(s_param, degrees=False)

    # Compute group delay
    group_delay = compute_group_delay(freq, phase)

    # Frequency array for group delay (one point shorter)
    freq_gd = (freq[:-1] + freq[1:]) / 2  # Midpoint frequencies

    # Create label with display name
    display_name = getattr(dataset, 'display_name', getattr(dataset, 'file_name', 'Unknown'))
    param_label = f"{trace.domain}{trace.port_path.i},{trace.port_path.j}"
    label = f"{display_name}: {param_label}"

    return PlotData(
        x=freq_gd,
        y=group_delay,
        plot_type=PlotType.GROUP_DELAY,
        label=label,
        units_x="Hz",
        units_y="s"
    )


def prepare_smith_data(trace: Trace, dataset, mode: str = 'Z') -> PlotData:
    """
    Prepare Smith chart plot data for given trace.

    Args:
        trace: Trace configuration
        dataset: Dataset containing S-parameter data
        mode: 'Z' for impedance mode, 'Y' for admittance mode

    Returns:
        PlotData ready for plotting (x=real, y=imag of reflection coefficient)
    """
    s_param = _extract_s_parameter(dataset.s_params, trace)

    # For reflection parameters (S11, S22), use directly as reflection coefficient
    # For transmission parameters (S12, S21), plot as if they were reflection coefficients
    gamma = s_param

    # Apply magnitude clipping to ensure |gamma| <= 1 for Smith chart
    magnitude = np.abs(gamma)
    mask = magnitude > 1.0
    if np.any(mask):
        # Normalize to unit circle
        gamma[mask] = gamma[mask] / magnitude[mask]

    # Convert to Cartesian coordinates
    x_data, y_data = gamma_to_cartesian(gamma)

    # In Y-mode, we might want to show the admittance representation
    # This typically involves the same gamma but interpreted differently

    # Create label with display name
    display_name = getattr(dataset, 'display_name', getattr(dataset, 'file_name', 'Unknown'))
    param_label = f"{trace.domain}{trace.port_path.i},{trace.port_path.j}"
    label = f"{display_name}: {param_label}"

    return PlotData(
        x=x_data,
        y=y_data,
        plot_type=PlotType.SMITH,
        label=label,
        units_x="Real(Γ)",
        units_y="Imag(Γ)"
    )


def create_plot_data(trace: Trace, dataset, plot_type: PlotType, **kwargs) -> PlotData:
    """
    Unified interface for creating plot data of any type.

    Args:
        trace: Trace configuration
        dataset: Dataset containing S-parameter data
        plot_type: Type of plot to create
        **kwargs: Additional parameters for specific plot types

    Returns:
        PlotData ready for plotting

    Raises:
        ValueError: If plot_type is not supported
    """
    if plot_type == PlotType.MAGNITUDE:
        return prepare_magnitude_data(trace, dataset, **kwargs)
    elif plot_type == PlotType.PHASE:
        return prepare_phase_data(trace, dataset, **kwargs)
    elif plot_type == PlotType.GROUP_DELAY:
        return prepare_group_delay_data(trace, dataset, **kwargs)
    elif plot_type == PlotType.SMITH:
        return prepare_smith_data(trace, dataset, **kwargs)
    else:
        raise ValueError(f"Unknown plot type: {plot_type}")


def get_axis_limits(plot_data: PlotData) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Calculate appropriate axis limits for plot data.

    Args:
        plot_data: PlotData to analyze

    Returns:
        Tuple of ((x_min, x_max), (y_min, y_max))
    """
    if plot_data.plot_type == PlotType.SMITH:
        # Smith chart always uses unit circle
        return ((-1.1, 1.1), (-1.1, 1.1))

    # For other plot types, use data-driven limits with some padding
    x_min, x_max = np.min(plot_data.x), np.max(plot_data.x)
    y_min, y_max = np.min(plot_data.y), np.max(plot_data.y)

    # Add 5% padding
    x_range = x_max - x_min
    y_range = y_max - y_min

    x_padding = 0.05 * x_range if x_range > 0 else 0.1
    y_padding = 0.05 * y_range if y_range > 0 else 0.1

    return ((x_min - x_padding, x_max + x_padding),
            (y_min - y_padding, y_max + y_padding))


def format_frequency_label(frequency: float, auto_unit: bool = True) -> str:
    """
    Format frequency value with appropriate unit.

    Args:
        frequency: Frequency in Hz
        auto_unit: If True, automatically choose best unit

    Returns:
        Formatted frequency string
    """
    if not auto_unit:
        return f"{frequency:.3g} Hz"

    if frequency >= 1e9:
        return f"{frequency/1e9:.3g} GHz"
    elif frequency >= 1e6:
        return f"{frequency/1e6:.3g} MHz"
    elif frequency >= 1e3:
        return f"{frequency/1e3:.3g} kHz"
    else:
        return f"{frequency:.3g} Hz"


def interpolate_trace_data(plot_data: PlotData, n_points: int) -> PlotData:
    """
    Interpolate trace data to specified number of points.

    Args:
        plot_data: Original plot data
        n_points: Target number of points

    Returns:
        New PlotData with interpolated data
    """
    if len(plot_data.x) >= n_points:
        # Already have enough points
        return plot_data

    # Create interpolated x values
    x_new = np.linspace(np.min(plot_data.x), np.max(plot_data.x), n_points)

    # Interpolate y values
    y_new = np.interp(x_new, plot_data.x, plot_data.y)

    return PlotData(
        x=x_new,
        y=y_new,
        plot_type=plot_data.plot_type,
        label=plot_data.label,
        units_x=plot_data.units_x,
        units_y=plot_data.units_y
    )


def decimate_trace_data(plot_data: PlotData, max_points: int) -> PlotData:
    """
    Decimate trace data if it exceeds maximum points.

    Args:
        plot_data: Original plot data
        max_points: Maximum allowed points

    Returns:
        New PlotData with decimated data
    """
    if len(plot_data.x) <= max_points:
        # Already within limit
        return plot_data

    # Calculate decimation factor
    factor = len(plot_data.x) // max_points

    # Decimate by taking every Nth point
    indices = np.arange(0, len(plot_data.x), factor)

    return PlotData(
        x=plot_data.x[indices],
        y=plot_data.y[indices],
        plot_type=plot_data.plot_type,
        label=plot_data.label,
        units_x=plot_data.units_x,
        units_y=plot_data.units_y
    )
