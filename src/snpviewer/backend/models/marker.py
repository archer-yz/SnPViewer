"""
Marker model for chart annotations.

Represents interactive markers on charts that can display parameter
values at specific frequencies or points.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


@dataclass
class MarkerStyle:
    """
    Visual styling for a marker.

    Attributes:
        color: Marker color (hex string)
        size: Marker size in pixels
        symbol: Marker symbol ('circle', 'square', 'triangle', 'diamond', 'x', '+')
        line_color: Color of marker lines (hex string)
        line_width: Width of marker lines in pixels
        label_color: Color of marker label text (hex string)
        label_size: Size of marker label text in points
        show_coordinates: Whether to show coordinates in label
        show_readout: Whether to show parameter readout
    """
    color: str = '#ff0000'
    size: int = 8
    symbol: str = 'circle'
    line_color: str = '#ff0000'
    line_width: int = 1
    label_color: str = '#000000'
    label_size: int = 10
    show_coordinates: bool = True
    show_readout: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert marker style to dictionary for serialization."""
        return {
            'color': self.color,
            'size': self.size,
            'symbol': self.symbol,
            'line_color': self.line_color,
            'line_width': self.line_width,
            'label_color': self.label_color,
            'label_size': self.label_size,
            'show_coordinates': self.show_coordinates,
            'show_readout': self.show_readout
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MarkerStyle:
        """Create marker style from dictionary for deserialization."""
        return cls(
            color=data.get('color', '#ff0000'),
            size=data.get('size', 8),
            symbol=data.get('symbol', 'circle'),
            line_color=data.get('line_color', '#ff0000'),
            line_width=data.get('line_width', 1),
            label_color=data.get('label_color', '#000000'),
            label_size=data.get('label_size', 10),
            show_coordinates=data.get('show_coordinates', True),
            show_readout=data.get('show_readout', True)
        )


@dataclass
class MarkerPosition:
    """
    Position and value information for a marker.

    Attributes:
        frequency: Frequency where marker is positioned (Hz)
        x_value: X-coordinate value (typically frequency)
        y_value: Y-coordinate value (parameter-dependent)
        interpolated: Whether position was interpolated between data points
        data_index: Index in original data array (if not interpolated)
    """
    frequency: float
    x_value: float
    y_value: float
    interpolated: bool = False
    data_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert marker position to dictionary for serialization."""
        return {
            'frequency': self.frequency,
            'x_value': self.x_value,
            'y_value': self.y_value,
            'interpolated': self.interpolated,
            'data_index': self.data_index
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MarkerPosition:
        """Create marker position from dictionary for deserialization."""
        return cls(
            frequency=data['frequency'],
            x_value=data['x_value'],
            y_value=data['y_value'],
            interpolated=data.get('interpolated', False),
            data_index=data.get('data_index')
        )


@dataclass
class Marker:
    """
    An interactive marker on a chart for displaying parameter values.

    Markers allow users to inspect parameter values at specific
    frequencies or points on traces. They can be positioned manually
    or automatically (e.g., at maximum/minimum values).

    Attributes:
        id: Unique identifier for this marker
        name: Display name for the marker
        trace_id: ID of the trace this marker is attached to
        chart_id: ID of the chart containing this marker
        position: Current position and value information
        style: Visual styling for the marker
        enabled: Whether the marker is currently displayed
        locked: Whether the marker position is locked from editing
        auto_track: Whether marker automatically tracks max/min values
        track_mode: Automatic tracking mode ('max', 'min', 'center', None)
        created_at: Marker creation timestamp
        updated_at: Last modification timestamp
        metadata: Additional marker-specific data
    """
    id: str
    name: str
    trace_id: str
    chart_id: str
    position: MarkerPosition
    style: MarkerStyle = field(default_factory=MarkerStyle)
    enabled: bool = True
    locked: bool = False
    auto_track: bool = False
    track_mode: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def set_position(self, frequency: float, x_value: float, y_value: float,
                     interpolated: bool = False, data_index: Optional[int] = None) -> None:
        """
        Update marker position.

        Args:
            frequency: New frequency position (Hz)
            x_value: New X-coordinate value
            y_value: New Y-coordinate value
            interpolated: Whether position is interpolated
            data_index: Index in original data array (if not interpolated)
        """
        if not self.locked:
            self.position = MarkerPosition(
                frequency=frequency,
                x_value=x_value,
                y_value=y_value,
                interpolated=interpolated,
                data_index=data_index
            )
            self.updated_at = datetime.now()

    def set_style(self, **kwargs) -> None:
        """
        Update marker style properties.

        Args:
            **kwargs: Style properties to update (color, size, symbol, etc.)
        """
        for key, value in kwargs.items():
            if hasattr(self.style, key):
                setattr(self.style, key, value)
        self.updated_at = datetime.now()

    def enable(self) -> None:
        """Enable marker display."""
        self.enabled = True
        self.updated_at = datetime.now()

    def disable(self) -> None:
        """Disable marker display."""
        self.enabled = False
        self.updated_at = datetime.now()

    def lock(self) -> None:
        """Lock marker position from editing."""
        self.locked = True
        self.updated_at = datetime.now()

    def unlock(self) -> None:
        """Unlock marker position for editing."""
        self.locked = False
        self.updated_at = datetime.now()

    def set_auto_track(self, track_mode: str) -> None:
        """
        Enable automatic tracking of max/min values.

        Args:
            track_mode: Tracking mode ('max', 'min', 'center')
        """
        valid_modes = ['max', 'min', 'center']
        if track_mode not in valid_modes:
            raise ValueError(f"Invalid track_mode: {track_mode}. Must be one of {valid_modes}")

        self.auto_track = True
        self.track_mode = track_mode
        self.updated_at = datetime.now()

    def disable_auto_track(self) -> None:
        """Disable automatic tracking."""
        self.auto_track = False
        self.track_mode = None
        self.updated_at = datetime.now()

    def get_display_text(self) -> str:
        """
        Get formatted display text for marker label.

        Returns:
            Formatted string for marker display
        """
        parts = []

        if self.style.show_coordinates:
            freq_str = f"f = {self.position.frequency:.3e} Hz"
            value_str = f"y = {self.position.y_value:.3f}"
            parts.extend([freq_str, value_str])

        if self.style.show_readout and self.name:
            parts.insert(0, self.name)

        return '\n'.join(parts)

    def get_coordinates(self) -> Tuple[float, float]:
        """
        Get marker coordinates for plotting.

        Returns:
            Tuple of (x, y) coordinates
        """
        return (self.position.x_value, self.position.y_value)

    def is_at_frequency(self, frequency: float, tolerance: float = 1e-6) -> bool:
        """
        Check if marker is positioned at a specific frequency.

        Args:
            frequency: Frequency to check (Hz)
            tolerance: Frequency tolerance for comparison

        Returns:
            True if marker is at the specified frequency
        """
        return abs(self.position.frequency - frequency) <= tolerance

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get marker metadata value.

        Args:
            key: Metadata key
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set marker metadata value.

        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert marker to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'name': self.name,
            'trace_id': self.trace_id,
            'chart_id': self.chart_id,
            'position': self.position.to_dict(),
            'style': self.style.to_dict(),
            'enabled': self.enabled,
            'locked': self.locked,
            'auto_track': self.auto_track,
            'track_mode': self.track_mode,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Marker:
        """
        Create marker from dictionary for deserialization.

        Args:
            data: Dictionary representation from JSON

        Returns:
            Reconstructed Marker instance
        """
        return cls(
            id=data['id'],
            name=data['name'],
            trace_id=data['trace_id'],
            chart_id=data['chart_id'],
            position=MarkerPosition.from_dict(data['position']),
            style=MarkerStyle.from_dict(data.get('style', {})),
            enabled=data.get('enabled', True),
            locked=data.get('locked', False),
            auto_track=data.get('auto_track', False),
            track_mode=data.get('track_mode'),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat())),
            metadata=data.get('metadata', {})
        )
