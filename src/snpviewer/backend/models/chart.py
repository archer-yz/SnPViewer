"""
Chart model for plot containers.

Represents a chart that contains multiple traces with shared axes,
styling, and display properties.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AxisConfiguration:
    """
    Configuration for chart axes.

    Attributes:
        unit: Unit label for the axis ('Hz', 'dB', '°', 'Ω', etc.)
        scale: Scale type ('linear' or 'log')
        auto_range: Whether to auto-scale the axis range
        min_value: Manual minimum value (if not auto_range)
        max_value: Manual maximum value (if not auto_range)
        label: Custom axis label (uses unit if None)
        grid_enabled: Whether to show grid lines for this axis
        tick_format: Custom tick formatting string
    """
    unit: str
    scale: str = 'linear'
    auto_range: bool = True
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    label: Optional[str] = None
    grid_enabled: bool = True
    tick_format: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert axis config to dictionary for serialization."""
        return {
            'unit': self.unit,
            'scale': self.scale,
            'auto_range': self.auto_range,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'label': self.label,
            'grid_enabled': self.grid_enabled,
            'tick_format': self.tick_format
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AxisConfiguration:
        """Create axis config from dictionary for deserialization."""
        return cls(
            unit=data['unit'],
            scale=data.get('scale', 'linear'),
            auto_range=data.get('auto_range', True),
            min_value=data.get('min_value'),
            max_value=data.get('max_value'),
            label=data.get('label'),
            grid_enabled=data.get('grid_enabled', True),
            tick_format=data.get('tick_format')
        )


@dataclass
class ChartAxes:
    """
    Complete axis configuration for a chart.

    Attributes:
        x: X-axis configuration (typically frequency)
        y: Y-axis configuration (parameter-dependent)
    """
    x: AxisConfiguration
    y: AxisConfiguration

    def to_dict(self) -> Dict[str, Any]:
        """Convert axes to dictionary for serialization."""
        return {
            'x': self.x.to_dict(),
            'y': self.y.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChartAxes:
        """Create axes from dictionary for deserialization."""
        return cls(
            x=AxisConfiguration.from_dict(data['x']),
            y=AxisConfiguration.from_dict(data['y'])
        )


@dataclass
class Chart:
    """
    A chart containing multiple traces with shared display properties.

    Charts group related traces together with common axes, styling,
    and layout properties. Each chart type has specific requirements
    for compatible traces and axis configurations.

    Attributes:
        id: Unique identifier for this chart
        tab_title: Title displayed on the chart's tab
        title: Display title for the chart
        chart_type: Type of chart ('Magnitude', 'Phase', 'GroupDelay',
                   'SmithZ', 'SmithY', 'LinearPhase', 'PhaseError')
        trace_ids: List of trace IDs displayed on this chart
        limit_lines: Dictionary of limit line configurations
        axes: Axis configurations for x and y axes
        linked_x_axis: Whether x-axis is linked to other charts
        legend_enabled: Whether to show the legend
        legend_position: Legend position ('top', 'bottom', 'left', 'right')
        background_color: Chart background color
        chart_fonts: Dictionary of font configurations for chart elements
        chart_colors: Dictionary of color configurations for chart elements
        plot_area_settings: Dictionary of plot area styling (background, borders, grid)
        created_at: Chart creation timestamp
        updated_at: Last modification timestamp
        layout_options: Additional layout and styling options
    """
    id: str
    tab_title: str
    title: str
    chart_type: str
    trace_ids: List[str] = field(default_factory=list)
    traces: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # Serialized trace data {trace_id: trace_dict}
    limit_lines: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    axes: Optional[ChartAxes] = None
    linked_x_axis: bool = False
    legend_enabled: bool = True
    legend_position: str = 'right'
    background_color: str = '#ffffff'
    chart_fonts: Dict[str, Any] = field(default_factory=dict)
    chart_colors: Dict[str, str] = field(default_factory=dict)
    plot_area_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    layout_options: Dict[str, Any] = field(default_factory=dict)
    phase_unwrap: bool = True  # Whether to unwrap phase for Phase charts
    linear_phase_error_data: Optional[Dict[str, Any]] = None  # Linear phase error analysis data
    phase_difference_data: Optional[Dict[str, Any]] = None  # Phase difference analysis data

    def __post_init__(self) -> None:
        """Post-initialization to set default axes if not provided."""
        if self.axes is None:
            self.axes = self._create_default_axes()

    def _create_default_axes(self) -> ChartAxes:
        """
        Create default axis configuration based on chart type.

        Returns:
            Default ChartAxes configuration for this chart type
        """
        # X-axis is always frequency for all chart types
        x_axis = AxisConfiguration(
            unit='Hz',
            scale='log',  # Frequency is typically log scale
            label='Frequency'
        )

        # Y-axis depends on chart type
        if self.chart_type == 'Magnitude':
            y_axis = AxisConfiguration(
                unit='dB',
                scale='linear',
                label='Magnitude (dB)'
            )
        elif self.chart_type == 'Phase':
            y_axis = AxisConfiguration(
                unit='°',
                scale='linear',
                label='Phase (degrees)'
            )
        elif self.chart_type == 'GroupDelay':
            y_axis = AxisConfiguration(
                unit='s',
                scale='linear',
                label='Group Delay (s)'
            )
        elif self.chart_type in ['SmithZ', 'SmithY']:
            # Smith charts have special axis handling
            y_axis = AxisConfiguration(
                unit='',
                scale='linear',
                label='Imaginary',
                auto_range=False,
                min_value=-2.0,
                max_value=2.0
            )
            x_axis.label = 'Real'
            x_axis.scale = 'linear'
            x_axis.unit = ''
            x_axis.auto_range = False
            x_axis.min_value = -2.0
            x_axis.max_value = 2.0
        elif self.chart_type == 'LinearPhase':
            y_axis = AxisConfiguration(
                unit='°',
                scale='linear',
                label='Linear Phase (degrees)'
            )
        elif self.chart_type == 'PhaseError':
            y_axis = AxisConfiguration(
                unit='°',
                scale='linear',
                label='Phase Error (degrees)'
            )
        elif self.chart_type == 'LinearPhaseError':
            y_axis = AxisConfiguration(
                unit='°',
                scale='linear',
                label='Phase Error (degrees)'
            )
        else:
            # Default fallback
            y_axis = AxisConfiguration(
                unit='',
                scale='linear',
                label='Amplitude'
            )

        return ChartAxes(x=x_axis, y=y_axis)

    def add_trace_id(self, trace_id: str) -> None:
        """
        Add a trace ID to this chart.

        Args:
            trace_id: ID of the trace to add
        """
        if trace_id not in self.trace_ids:
            self.trace_ids.append(trace_id)
            self.updated_at = datetime.now()

    def remove_trace_id(self, trace_id: str) -> bool:
        """
        Remove a trace ID from this chart.

        Args:
            trace_id: ID of the trace to remove

        Returns:
            True if trace was removed, False if not found
        """
        if trace_id in self.trace_ids:
            self.trace_ids.remove(trace_id)
            self.updated_at = datetime.now()
            return True
        return False

    def get_trace_count(self) -> int:
        """
        Get the number of traces on this chart.

        Returns:
            Number of traces currently displayed
        """
        return len(self.trace_ids)

    def is_empty(self) -> bool:
        """
        Check if chart has no traces.

        Returns:
            True if chart has no traces
        """
        return len(self.trace_ids) == 0

    def is_smith_chart(self) -> bool:
        """
        Check if this is a Smith chart type.

        Returns:
            True if chart is SmithZ or SmithY
        """
        return self.chart_type in ['SmithZ', 'SmithY']

    def get_compatible_trace_metrics(self) -> List[str]:
        """
        Get list of trace metrics compatible with this chart type.

        Returns:
            List of compatible metric strings
        """
        if self.chart_type == 'Magnitude':
            return ['magnitude_dB', 'magnitude']
        elif self.chart_type == 'Phase':
            return ['phase_deg', 'phase_rad']
        elif self.chart_type == 'GroupDelay':
            return ['group_delay']
        elif self.chart_type == 'SmithZ':
            return ['smith_z']
        elif self.chart_type == 'SmithY':
            return ['smith_y']
        elif self.chart_type == 'LinearPhase':
            return ['linear_phase']
        elif self.chart_type == 'PhaseError':
            return ['phase_error']
        elif self.chart_type == 'LinearPhaseError':
            return ['linear_phase_error']
        else:
            return []  # Unknown chart type

    def update_layout_option(self, key: str, value: Any) -> None:
        """
        Update a layout option.

        Args:
            key: Option key
            value: Option value
        """
        self.layout_options[key] = value
        self.updated_at = datetime.now()

    def get_layout_option(self, key: str, default: Any = None) -> Any:
        """
        Get a layout option value.

        Args:
            key: Option key
            default: Default value if key not found

        Returns:
            Option value or default
        """
        return self.layout_options.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert chart to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'tab_title': self.tab_title,
            'title': self.title,
            'chart_type': self.chart_type,
            'trace_ids': self.trace_ids,
            'traces': self.traces,
            'limit_lines': self.limit_lines,
            'axes': self.axes.to_dict() if self.axes else None,
            'linked_x_axis': self.linked_x_axis,
            'legend_enabled': self.legend_enabled,
            'legend_position': self.legend_position,
            'background_color': self.background_color,
            'chart_fonts': self.chart_fonts,
            'chart_colors': self.chart_colors,
            'plot_area_settings': self.plot_area_settings,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'layout_options': self.layout_options,
            'phase_unwrap': self.phase_unwrap,
            'linear_phase_error_data': self.linear_phase_error_data,
            'phase_difference_data': self.phase_difference_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Chart:
        """
        Create chart from dictionary for deserialization.

        Args:
            data: Dictionary representation from JSON

        Returns:
            Reconstructed Chart instance
        """
        axes = None
        if data.get('axes'):
            axes = ChartAxes.from_dict(data['axes'])

        return cls(
            id=data['id'],
            tab_title=data.get('tab_title', data['title']),
            title=data['title'],
            chart_type=data['chart_type'],
            trace_ids=data.get('trace_ids', []),
            traces=data.get('traces', {}),
            limit_lines=data.get('limit_lines', {}),
            axes=axes,
            linked_x_axis=data.get('linked_x_axis', False),
            legend_enabled=data.get('legend_enabled', True),
            legend_position=data.get('legend_position', 'right'),
            background_color=data.get('background_color', '#ffffff'),
            chart_fonts=data.get('chart_fonts', {}),
            chart_colors=data.get('chart_colors', {}),
            plot_area_settings=data.get('plot_area_settings', {}),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat())),
            layout_options=data.get('layout_options', {}),
            phase_unwrap=data.get('phase_unwrap', True),
            linear_phase_error_data=data.get('linear_phase_error_data'),
            phase_difference_data=data.get('phase_difference_data')
        )
