"""
Smith chart utilities for S-parameter visualization.

Provides reflection coefficient transformations, Smith chart grid generation
for both impedance (Z) and admittance (Y) modes, and coordinate mapping
functions for plotting S-parameters on Smith charts.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np


def s_to_gamma(s: np.ndarray, port1: int, port2: int) -> np.ndarray:
    """
    Extract reflection coefficient from S-parameters.

    For reflection coefficients (port1 == port2), this directly returns
    the diagonal S-parameter. For transmission, returns the off-diagonal
    S-parameter which can also be plotted on Smith chart.

    Args:
        s: S-parameter matrix, shape (N_freq, n_ports, n_ports)
        port1: Output port index (0-based)
        port2: Input port index (0-based)

    Returns:
        Reflection coefficient array, shape (N_freq,)

    Raises:
        IndexError: If port indices are out of range
    """
    if s.ndim != 3:
        raise ValueError("S-parameters must have shape (N_freq, n_ports, n_ports)")

    N_freq, n_ports, _ = s.shape

    if port1 >= n_ports or port2 >= n_ports:
        raise IndexError(f"Port indices ({port1}, {port2}) exceed matrix size ({n_ports}x{n_ports})")

    return s[:, port1, port2]


def gamma_to_s(gamma: np.ndarray) -> np.ndarray:
    """
    Convert reflection coefficient array to 1-port S-parameters.

    Args:
        gamma: Reflection coefficient array, shape (N_freq,)

    Returns:
        S-parameter matrix, shape (N_freq, 1, 1)
    """
    gamma = np.asarray(gamma, dtype=complex)
    if gamma.ndim != 1:
        raise ValueError("Gamma must be 1D array")

    N_freq = len(gamma)
    s = np.zeros((N_freq, 1, 1), dtype=complex)
    s[:, 0, 0] = gamma

    return s


def z_to_gamma(z_normalized: np.ndarray) -> np.ndarray:
    """
    Convert normalized impedance to reflection coefficient.

    Uses the transformation: Γ = (Z - 1) / (Z + 1)
    where Z is the normalized impedance (Z_actual / Z0).

    Args:
        z_normalized: Normalized impedance array

    Returns:
        Reflection coefficient array
    """
    z_normalized = np.asarray(z_normalized, dtype=complex)
    return (z_normalized - 1) / (z_normalized + 1)


def y_to_gamma(y_normalized: np.ndarray) -> np.ndarray:
    """
    Convert normalized admittance to reflection coefficient.

    Uses the transformation: Γ = (1 - Y) / (1 + Y)
    where Y is the normalized admittance (Y_actual * Z0).

    Args:
        y_normalized: Normalized admittance array

    Returns:
        Reflection coefficient array
    """
    y_normalized = np.asarray(y_normalized, dtype=complex)
    return (1 - y_normalized) / (1 + y_normalized)


def normalize_impedance(z_actual: np.ndarray, z0: float) -> np.ndarray:
    """
    Normalize impedance by reference impedance.

    Args:
        z_actual: Actual impedance values
        z0: Reference impedance

    Returns:
        Normalized impedance (z_actual / z0)

    Raises:
        ValueError: If reference impedance is zero
    """
    if abs(z0) < 1e-15:
        raise ValueError("Reference impedance cannot be zero")

    return np.asarray(z_actual, dtype=complex) / z0


def denormalize_impedance(z_normalized: np.ndarray, z0: float) -> np.ndarray:
    """
    Convert normalized impedance back to actual impedance.

    Args:
        z_normalized: Normalized impedance values
        z0: Reference impedance

    Returns:
        Actual impedance (z_normalized * z0)

    Raises:
        ValueError: If reference impedance is zero
    """
    if abs(z0) < 1e-15:
        raise ValueError("Reference impedance cannot be zero")

    return np.asarray(z_normalized, dtype=complex) * z0


def generate_constant_resistance_circles(resistance_values: List[float]) -> List[Dict[str, Any]]:
    """
    Generate constant resistance circles for Smith chart Z-mode.

    Each constant resistance circle on the Smith chart corresponds to
    impedances with the same real part. The circles are centered on
    the real axis.

    Args:
        resistance_values: List of normalized resistance values

    Returns:
        List of circle definitions with center, radius, and resistance value
    """
    circles = []

    for r in resistance_values:
        if r < 0:
            continue  # Skip negative resistance (unphysical for passive circuits)

        # Circle geometry for constant resistance r:
        # Center: (r/(1+r), 0)
        # Radius: 1/(1+r)
        center_x = r / (1 + r)
        center_y = 0.0
        radius = 1 / (1 + r)

        circles.append({
            'center': (center_x, center_y),
            'radius': radius,
            'resistance': r
        })

    return circles


def generate_constant_reactance_arcs(reactance_values: List[float]) -> List[Dict[str, Any]]:
    """
    Generate constant reactance arcs for Smith chart Z-mode.

    Each constant reactance arc on the Smith chart corresponds to
    impedances with the same imaginary part. The arcs are circular
    arcs passing through the point (1, 0).

    Args:
        reactance_values: List of normalized reactance values

    Returns:
        List of arc definitions with center, radius, and reactance value
    """
    arcs = []

    for x in reactance_values:
        if abs(x) < 1e-15:
            # For X = 0 (real axis), create a degenerate arc (line segment)
            arcs.append({
                'center': (0.0, 0.0),
                'radius': float('inf'),
                'reactance': x,
                'type': 'line'  # Special marker for real axis
            })
            continue

        # Arc geometry for constant reactance x:
        # Center: (1, 1/x)
        # Radius: |1/x|
        center_x = 1.0
        center_y = 1.0 / x
        radius = abs(1.0 / x)

        arcs.append({
            'center': (center_x, center_y),
            'radius': radius,
            'reactance': x
        })

    return arcs


def generate_constant_conductance_circles(conductance_values: List[float]) -> List[Dict[str, Any]]:
    """
    Generate constant conductance circles for Smith chart Y-mode.

    In Y-mode Smith chart, constant conductance circles are similar
    to resistance circles but reflected about the imaginary axis.

    Args:
        conductance_values: List of normalized conductance values

    Returns:
        List of circle definitions with center, radius, and conductance value
    """
    circles = []

    for g in conductance_values:
        if g < 0:
            continue  # Skip negative conductance

        # Circle geometry for constant conductance g in Y-mode:
        # Center: (-g/(1+g), 0)
        # Radius: 1/(1+g)
        center_x = -g / (1 + g)
        center_y = 0.0
        radius = 1 / (1 + g)

        circles.append({
            'center': (center_x, center_y),
            'radius': radius,
            'conductance': g
        })

    return circles


def generate_constant_susceptance_arcs(susceptance_values: List[float]) -> List[Dict[str, Any]]:
    """
    Generate constant susceptance arcs for Smith chart Y-mode.

    In Y-mode Smith chart, constant susceptance arcs are similar
    to reactance arcs but reflected and inverted.

    Args:
        susceptance_values: List of normalized susceptance values

    Returns:
        List of arc definitions with center, radius, and susceptance value
    """
    arcs = []

    for b in susceptance_values:
        if abs(b) < 1e-15:
            # For B = 0 (real axis), create a degenerate arc
            arcs.append({
                'center': (0.0, 0.0),
                'radius': float('inf'),
                'susceptance': b,
                'type': 'line'
            })
            continue

        # Arc geometry for constant susceptance b in Y-mode:
        # Center: (-1, -1/b)
        # Radius: |1/b|
        center_x = -1.0
        center_y = -1.0 / b
        radius = abs(1.0 / b)

        arcs.append({
            'center': (center_x, center_y),
            'radius': radius,
            'susceptance': b
        })

    return arcs


def generate_smith_grid(mode: str = 'Z',
                        resistance_values: List[float] = None,
                        reactance_values: List[float] = None,
                        conductance_values: List[float] = None,
                        susceptance_values: List[float] = None) -> Dict[str, Any]:
    """
    Generate complete Smith chart grid for specified mode.

    Args:
        mode: 'Z' for impedance mode or 'Y' for admittance mode
        resistance_values: Custom resistance values (Z-mode)
        reactance_values: Custom reactance values (Z-mode)
        conductance_values: Custom conductance values (Y-mode)
        susceptance_values: Custom susceptance values (Y-mode)

    Returns:
        Dictionary containing grid elements and metadata

    Raises:
        ValueError: If mode is not 'Z' or 'Y'
    """
    if mode not in ['Z', 'Y']:
        raise ValueError("mode must be 'Z' or 'Y'")

    grid = {'mode': mode}

    if mode == 'Z':
        # Default resistance values for Z-mode
        if resistance_values is None:
            resistance_values = [0.2, 0.5, 1.0, 2.0, 5.0]

        # Default reactance values for Z-mode
        if reactance_values is None:
            reactance_values = [-5.0, -2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 5.0]

        grid['resistance_circles'] = generate_constant_resistance_circles(resistance_values)
        grid['reactance_arcs'] = generate_constant_reactance_arcs(reactance_values)

    else:  # Y-mode
        # Default conductance values for Y-mode
        if conductance_values is None:
            conductance_values = [0.2, 0.5, 1.0, 2.0, 5.0]

        # Default susceptance values for Y-mode
        if susceptance_values is None:
            susceptance_values = [-5.0, -2.0, -1.0, -0.5, 0.5, 1.0, 2.0, 5.0]

        grid['conductance_circles'] = generate_constant_conductance_circles(conductance_values)
        grid['susceptance_arcs'] = generate_constant_susceptance_arcs(susceptance_values)

    return grid


def gamma_to_cartesian(gamma: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convert reflection coefficient to Cartesian coordinates for plotting.

    Args:
        gamma: Complex reflection coefficient array

    Returns:
        Tuple of (x, y) coordinates for plotting
    """
    gamma = np.asarray(gamma, dtype=complex)
    return np.real(gamma), np.imag(gamma)


def cartesian_to_gamma(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """
    Convert Cartesian coordinates back to reflection coefficient.

    Args:
        x: Real part coordinates
        y: Imaginary part coordinates

    Returns:
        Complex reflection coefficient array
    """
    return np.asarray(x, dtype=float) + 1j * np.asarray(y, dtype=float)


def gamma_to_impedance_normalized(gamma: np.ndarray) -> np.ndarray:
    """
    Convert reflection coefficient to normalized impedance.

    Uses the inverse transformation: Z = (1 + Γ) / (1 - Γ)

    Args:
        gamma: Reflection coefficient array

    Returns:
        Normalized impedance array
    """
    gamma = np.asarray(gamma, dtype=complex)
    return (1 + gamma) / (1 - gamma)


def gamma_to_admittance_normalized(gamma: np.ndarray) -> np.ndarray:
    """
    Convert reflection coefficient to normalized admittance.

    Uses the inverse transformation: Y = (1 - Γ) / (1 + Γ)

    Args:
        gamma: Reflection coefficient array

    Returns:
        Normalized admittance array
    """
    gamma = np.asarray(gamma, dtype=complex)
    return (1 - gamma) / (1 + gamma)


def generate_unit_circle(n_points: int = 360) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate unit circle for Smith chart boundary.

    Args:
        n_points: Number of points in the circle

    Returns:
        Tuple of (x, y) coordinates for unit circle
    """
    theta = np.linspace(0, 2*np.pi, n_points)
    x = np.cos(theta)
    y = np.sin(theta)
    return x, y


def interpolate_arc(center: Tuple[float, float], radius: float,
                    start_angle: float, end_angle: float,
                    n_points: int = 100) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate points along a circular arc for plotting.

    Args:
        center: Arc center coordinates (x, y)
        radius: Arc radius
        start_angle: Starting angle in radians
        end_angle: Ending angle in radians
        n_points: Number of points to generate

    Returns:
        Tuple of (x, y) coordinates for the arc
    """
    if radius == float('inf'):
        # Handle degenerate case (straight line)
        x = np.array([center[0], center[0]])
        y = np.array([center[1] - 1, center[1] + 1])
        return x, y

    theta = np.linspace(start_angle, end_angle, n_points)
    x = center[0] + radius * np.cos(theta)
    y = center[1] + radius * np.sin(theta)

    # Clip to unit circle boundary
    r = np.sqrt(x**2 + y**2)
    mask = r <= 1.0

    return x[mask], y[mask]


def find_smith_chart_intersections(center: Tuple[float, float], radius: float) -> List[Tuple[float, float]]:
    """
    Find intersection points of a circle/arc with the unit circle.

    Args:
        center: Circle center coordinates
        radius: Circle radius

    Returns:
        List of intersection points as (x, y) tuples
    """
    cx, cy = center

    # Solve for intersection with unit circle: x² + y² = 1
    # Circle equation: (x - cx)² + (y - cy)² = r²

    # This becomes a quadratic equation in x or y
    # For simplicity, solve numerically or return empty for infinite radius
    if radius == float('inf'):
        return []

    # Distance from origin to circle center
    d = np.sqrt(cx**2 + cy**2)

    if d > radius + 1 or d + 1 < radius:
        # No intersection
        return []

    if abs(d - abs(radius - 1)) < 1e-12:
        # Single intersection (tangent)
        t = 1 / d
        return [(cx * t, cy * t)]

    # Two intersections - use geometric solution
    a = (1 - radius**2 + d**2) / (2 * d)
    h = np.sqrt(1 - a**2)

    # Intersection point on line from origin to center
    px = a * cx / d
    py = a * cy / d

    # Two intersection points
    p1 = (px + h * (-cy / d), py + h * (cx / d))
    p2 = (px - h * (-cy / d), py - h * (cx / d))

    return [p1, p2]
