"""
Trace model for plot traces.

Represents a single trace on a chart, linking to dataset data
with specific parameter domain and port path selections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class TraceStyle:
    """
    Visual styling properties for a trace.

    Attributes:
        color: Trace color (hex string or color name)
        line_style: Line style ('solid', 'dashed', 'dotted', 'dashdot')
        line_width: Line width in points
        marker_style: Marker style ('none', 'circle', 'square', 'triangle')
        marker_size: Marker size in points
        visible: Whether trace is currently visible
        opacity: Trace opacity (0.0 to 1.0)
    """
    color: str = '#1f77b4'  # Default matplotlib blue
    line_style: str = 'solid'
    line_width: float = 1.5
    marker_style: str = 'none'
    marker_size: float = 4.0
    visible: bool = True
    opacity: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert style to dictionary for serialization."""
        return {
            'color': self.color,
            'line_style': self.line_style,
            'line_width': self.line_width,
            'marker_style': self.marker_style,
            'marker_size': self.marker_size,
            'visible': self.visible,
            'opacity': self.opacity
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TraceStyle:
        """Create style from dictionary for deserialization."""
        return cls(
            color=data.get('color', '#1f77b4'),
            line_style=data.get('line_style', 'solid'),
            line_width=data.get('line_width', 1.5),
            marker_style=data.get('marker_style', 'none'),
            marker_size=data.get('marker_size', 4.0),
            visible=data.get('visible', True),
            opacity=data.get('opacity', 1.0)
        )


@dataclass
class PortPath:
    """
    Port path specification for n-port parameters.

    Attributes:
        i: Input port number (1-indexed)
        j: Output port number (1-indexed)
    """
    i: int
    j: int

    def __str__(self) -> str:
        """String representation for display."""
        return f"S({self.i},{self.j})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {'i': self.i, 'j': self.j}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PortPath:
        """Create from dictionary for deserialization."""
        return cls(i=data['i'], j=data['j'])


@dataclass
class Trace:
    """
    A single trace representing data from a dataset on a chart.

    A trace connects a specific dataset's parameter (e.g., S21) with a
    chart, defining how the data should be displayed and processed.

    Attributes:
        id: Unique identifier for this trace
        dataset_id: ID of the source dataset
        domain: Parameter domain ('S', 'Y', 'Z', 'ABCD', 'h', 'g', 'T')
        port_path: Which port-to-port parameter to display
        metric: Display metric ('magnitude_dB', 'magnitude', 'phase_deg',
                'phase_rad', 'group_delay', 'linear_phase', 'phase_error',
                'smith_z', 'smith_y')
        style: Visual styling properties
        label: Display label for the trace (auto-generated if None)
        marker_ids: List of marker IDs attached to this trace
        data_cache: Cached processed data for performance
        processing_options: Additional processing parameters
    """
    id: str
    dataset_id: str
    domain: str
    port_path: PortPath
    metric: str
    style: TraceStyle = field(default_factory=TraceStyle)
    label: Optional[str] = None
    marker_ids: List[str] = field(default_factory=list)
    data_cache: Dict[str, np.ndarray] = field(default_factory=dict)
    processing_options: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Post-initialization to set default label if not provided."""
        if self.label is None:
            self.label = self._generate_default_label()

    def _generate_default_label(self) -> str:
        """
        Generate a default label for the trace.

        Returns:
            Default label based on domain, port path, and metric
        """
        port_str = str(self.port_path)

        # Convert domain to display format
        if self.domain == 'S':
            param_name = port_str
        elif self.domain in ['Y', 'Z']:
            param_name = f"{self.domain}({self.port_path.i},{self.port_path.j})"
        else:
            # 2-port only parameters
            param_name = self.domain

        # Add metric suffix if not magnitude
        if self.metric == 'magnitude_dB':
            return f"{param_name} (dB)"
        elif self.metric == 'magnitude':
            return f"{param_name} (mag)"
        elif self.metric == 'phase_deg':
            return f"{param_name} (°)"
        elif self.metric == 'phase_rad':
            return f"{param_name} (rad)"
        elif self.metric == 'group_delay':
            return f"{param_name} (group delay)"
        elif self.metric in ['smith_z', 'smith_y']:
            return param_name  # Smith charts don't need metric suffix
        else:
            return f"{param_name} ({self.metric})"

    def add_marker_id(self, marker_id: str) -> None:
        """
        Add a marker ID to this trace.

        Args:
            marker_id: ID of the marker to associate with this trace
        """
        if marker_id not in self.marker_ids:
            self.marker_ids.append(marker_id)

    def remove_marker_id(self, marker_id: str) -> bool:
        """
        Remove a marker ID from this trace.

        Args:
            marker_id: ID of the marker to remove

        Returns:
            True if marker was removed, False if not found
        """
        if marker_id in self.marker_ids:
            self.marker_ids.remove(marker_id)
            return True
        return False

    def get_cached_data(self, key: str) -> Optional[np.ndarray]:
        """
        Get cached processed data.

        Args:
            key: Cache key (e.g., 'magnitude', 'phase', 'frequencies')

        Returns:
            Cached data array if available, None otherwise
        """
        return self.data_cache.get(key)

    def set_cached_data(self, key: str, data: np.ndarray) -> None:
        """
        Cache processed data for performance.

        Args:
            key: Cache key
            data: Data array to cache
        """
        self.data_cache[key] = data.copy()

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.data_cache.clear()

    def is_compatible_with_chart_type(self, chart_type: str) -> bool:
        """
        Check if this trace is compatible with a chart type.

        Args:
            chart_type: Chart type to check compatibility with

        Returns:
            True if trace can be displayed on this chart type
        """
        smith_metrics = {'smith_z', 'smith_y'}
        smith_charts = {'SmithZ', 'SmithY'}

        if chart_type in smith_charts:
            return self.metric in smith_metrics
        else:
            return self.metric not in smith_metrics

    def validate_domain_port_compatibility(self, n_ports: int) -> bool:
        """
        Validate that domain and port path are compatible with dataset.

        Args:
            n_ports: Number of ports in the dataset

        Returns:
            True if trace configuration is valid for the dataset
        """
        # Check port indices are in range
        if not (1 <= self.port_path.i <= n_ports and 1 <= self.port_path.j <= n_ports):
            return False

        # Check domain constraints
        two_port_only = {'ABCD', 'h', 'g', 'T'}
        if self.domain in two_port_only and n_ports != 2:
            return False

        return True

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert trace to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'dataset_id': self.dataset_id,
            'domain': self.domain,
            'port_path': self.port_path.to_dict(),
            'metric': self.metric,
            'style': self.style.to_dict(),
            'label': self.label,
            'marker_ids': self.marker_ids,
            'processing_options': self.processing_options
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Trace:
        """
        Create trace from dictionary for deserialization.

        Args:
            data: Dictionary representation from JSON

        Returns:
            Reconstructed Trace instance
        """
        return cls(
            id=data['id'],
            dataset_id=data['dataset_id'],
            domain=data['domain'],
            port_path=PortPath.from_dict(data['port_path']),
            metric=data['metric'],
            style=TraceStyle.from_dict(data.get('style', {})),
            label=data.get('label'),
            marker_ids=data.get('marker_ids', []),
            processing_options=data.get('processing_options', {})
        )
