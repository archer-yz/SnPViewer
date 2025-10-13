"""
Smith Chart View Widget

Interactive Smith chart visualization for S-parameter reflection coefficients using PyQtGraph.
Displays complex impedance/admittance data on the Smith chart with customizable grid overlays.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QPen
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                               QFileDialog, QFrame, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QMessageBox,
                               QPushButton, QSizePolicy, QSpinBox, QVBoxLayout,
                               QWidget)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.trace import Trace, TraceStyle
from snpviewer.frontend.constants import DEFAULT_LINE_STYLES
from snpviewer.frontend.plotting.plot_pipelines import prepare_smith_data


class SmithChartGrid:
    """Generates Smith chart grid lines and labels."""

    def __init__(self):
        self.resistance_circles = []
        self.reactance_arcs = []
        self.labels = []

    def generate_grid(self, r_values: List[float] = None, x_values: List[float] = None) -> Dict[str, Any]:
        """
        Generate Smith chart grid components.

        Args:
            r_values: Resistance values for constant resistance circles
            x_values: Reactance values for constant reactance arcs

        Returns:
            Dictionary containing grid components and labels
        """
        if r_values is None:
            r_values = [0.2, 0.5, 1.0, 2.0, 5.0]
        if x_values is None:
            x_values = [0.2, 0.5, 1.0, 2.0, 5.0, -0.2, -0.5, -1.0, -2.0, -5.0]

        grid_data = {
            'resistance_circles': [],
            'reactance_arcs': [],
            'labels': []
        }

        # Generate constant resistance circles
        for r in r_values:
            circle = self._resistance_circle(r)
            if circle is not None:
                grid_data['resistance_circles'].append({
                    'x': circle[0],
                    'y': circle[1],
                    'value': r,
                    'label': str(r)  # Just the value
                })

        # Generate constant reactance arcs
        for x in x_values:
            arc = self._reactance_arc(x)
            if arc is not None:
                grid_data['reactance_arcs'].append({
                    'x': arc[0],
                    'y': arc[1],
                    'value': x,
                    'label': str(x)  # Just the value
                })

        return grid_data

    def _resistance_circle(self, r: float) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Generate points for constant resistance circle."""
        if r <= 0:
            return None

        # Circle center and radius in Smith chart coordinates
        center_x = r / (1 + r)
        center_y = 0
        radius = 1 / (1 + r)

        # Generate circle points - but NOT a complete circle to avoid fill
        # Leave a small gap to prevent PyQtGraph from detecting a closed path
        theta = np.linspace(0, 2*np.pi - 0.1, 100)
        x = center_x + radius * np.cos(theta)
        y = center_y + radius * np.sin(theta)

        # Clip to unit circle
        mask = (x**2 + y**2) <= 1.01  # Small tolerance
        return x[mask], y[mask]

    def _reactance_arc(self, x: float) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Generate points for constant reactance arc."""
        if abs(x) < 1e-10:
            # Real axis - horizontal line
            x_points = np.linspace(-1, 1, 100)
            y_points = np.zeros_like(x_points)
            return x_points, y_points

        # Arc center and radius in Smith chart coordinates
        center_x = 1.0
        center_y = 1.0 / x
        radius = abs(1.0 / x)

        # Calculate the exact intersection angle with unit circle
        # The arc passes through (1, 0) which is at angle π for x>0 or 0 for x<0
        # Find the other intersection point by solving:
        # (x - 1)^2 + (y - 1/x)^2 = (1/x)^2  AND  x^2 + y^2 = 1

        # Expanding: x^2 - 2x + 1 + y^2 - 2y/x + 1/x^2 = 1/x^2
        # Simplifies: x^2 + y^2 - 2x - 2y/x + 1 = 0
        # With x^2 + y^2 = 1: 1 - 2x - 2y/x + 1 = 0
        # So: 2 - 2x - 2y/x = 0  =>  1 - x - y/x = 0  =>  x - x^2 = y
        # With x^2 + y^2 = 1: x^2 + (x - x^2)^2 = 1
        # This gives the intersection points

        # For practical purposes, calculate angles that keep arc inside unit circle
        # The arc passes through (1, 0)
        # Calculate start and end angles to reach unit circle boundary

        if x > 0:
            # Upper half - arc goes counterclockwise from unit circle to (1,0)
            # Start angle: where arc enters unit circle from left
            # End angle: π (at point (1,0))

            # Calculate the angle range more carefully
            # The other intersection is roughly at angle that makes arc tangent to circle
            theta_start = np.pi - np.arcsin(min(1.0, 2.0 / (1.0 + radius**2 / radius)))
            theta_end = 2 * np.pi
            theta = np.linspace(theta_start, theta_end, 300)
        else:
            # Lower half - arc goes clockwise from (1,0) to unit circle
            theta_start = 0.0
            theta_end = np.pi + np.arcsin(min(1.0, 2.0 / (1.0 + radius**2 / radius)))
            theta = np.linspace(theta_start, theta_end, 300)

        x_arc = center_x + radius * np.cos(theta)
        y_arc = center_y + radius * np.sin(theta)

        # Keep only points inside unit circle
        distances = np.sqrt(x_arc**2 + y_arc**2)
        mask = distances <= 1.001  # Tight tolerance

        if np.any(mask):
            return x_arc[mask], y_arc[mask]
        else:
            return None


class SmithView(QWidget):
    """
    Smith Chart view widget for displaying S-parameter reflection coefficients.

    Features:
    - Interactive Smith chart with grid overlay
    - Multiple trace support with styling
    - Multiple dataset support
    - Impedance/Admittance mode switching
    - Legend support
    - Marker support and coordinate readout
    - Export capabilities (PNG, SVG, CSV)
    """

    # Signals - match ChartView for consistency
    trace_selected = Signal(str)  # trace_id
    marker_moved = Signal(str, float, complex)  # trace_id, frequency, value
    marker_added = Signal(float, float, str)  # x, y, trace_id
    view_changed = Signal()
    add_traces_requested = Signal()  # Request to add traces from main window
    tab_title_changed = Signal(str)  # New tab title with type
    chart_title_changed = Signal(str)  # New chart title
    properties_changed = Signal()  # Emitted when any chart properties are modified

    def __init__(self, parent=None):
        super().__init__(parent)

        # Chart titles
        self._chart_title = "Smith Chart"
        self._tab_title = "Smith Chart"

        # Data storage - support multiple datasets
        self._dataset = None  # For backward compatibility with single-dataset API
        self._datasets: Dict[str, Dataset] = {}  # {dataset_id: Dataset}
        self._traces: Dict[str, Trace] = {}
        self._plot_items: Dict[str, pg.PlotDataItem] = {}
        self._markers: Dict[str, pg.InfiniteLine] = {}

        # Legend
        self._legend = None
        self._legend_columns = 1  # Number of columns in legend

        # Font and color settings for chart title and legend
        self._chart_fonts: Dict[str, QFont] = {}
        self._chart_colors: Dict[str, str] = {}

        self._setup_ui()
        self._setup_chart()
        self._configure_plot_style()  # Add this like ChartView does
        self._setup_grid()

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Control panel
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        control_frame.setMaximumHeight(40)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(6, 4, 6, 4)

        # Mode selector
        self.mode_label = QLabel("Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Impedance (Z)", "Admittance (Y)"])
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        # Grid controls
        self.grid_checkbox = QCheckBox("Show Grid")
        self.grid_checkbox.setChecked(True)
        self.grid_checkbox.toggled.connect(self._on_grid_toggled)

        self.labels_checkbox = QCheckBox("Show Labels")
        self.labels_checkbox.setChecked(True)
        self.labels_checkbox.toggled.connect(self._on_labels_toggled)

        # Coordinate readout
        self.coord_label = QLabel("Γ: -- | Z: --")
        self.coord_label.setMinimumWidth(200)
        font = QFont("Consolas", 9)
        self.coord_label.setFont(font)

        control_layout.addWidget(self.mode_label)
        control_layout.addWidget(self.mode_combo)
        control_layout.addWidget(self.grid_checkbox)
        control_layout.addWidget(self.labels_checkbox)
        control_layout.addStretch()
        control_layout.addWidget(self.coord_label)

        layout.addWidget(control_frame)

        # Chart widget
        self.chart_widget = pg.PlotWidget()
        self.chart_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # CRITICAL: Force white background using stylesheet targeting QGraphicsView
        # self.chart_widget.setStyleSheet("""
        #     QGraphicsView {
        #         background-color: white;
        #         border: none;
        #     }
        # """)

        layout.addWidget(self.chart_widget)

    def _setup_chart(self):
        """Configure the Smith chart plot widget."""
        self.plot_item = self.chart_widget.getPlotItem()

        # Get the view box
        vb = self.plot_item.getViewBox()

        # Disable ViewBox border
        transparent_pen = QPen(Qt.NoPen)
        vb.setBorder(transparent_pen)

        # Disable auto range to prevent distortion
        vb.enableAutoRange(enable=False)

        # Set equal aspect ratio for circular Smith chart
        self.plot_item.setAspectLocked(True, ratio=1.0)

        # Set axis limits to unit circle with padding
        self.plot_item.setXRange(-1.1, 1.1, padding=0)
        self.plot_item.setYRange(-1.1, 1.1, padding=0)

        # Configure axes
        self.plot_item.showGrid(False)  # We'll draw custom grid
        self.plot_item.setLabel('left', 'Imaginary')
        self.plot_item.setLabel('bottom', 'Real')
        self.plot_item.setTitle(self._chart_title)

        # Hide all axes for Smith chart (we don't need them)
        self.plot_item.hideAxis('left')
        self.plot_item.hideAxis('right')
        self.plot_item.hideAxis('top')
        self.plot_item.hideAxis('bottom')

        # Create legend
        self._create_legend()

        # Add mouse tracking
        self.chart_widget.setMouseTracking(True)
        scene = self.plot_item.scene()
        if scene:
            scene.sigMouseMoved.connect(self._on_mouse_moved)

        # Add context menu
        self.chart_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chart_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _configure_plot_style(self) -> None:
        """Configure the visual appearance of the plot - exactly like ChartView."""
        # Set background color - this is the KEY setting
        self.chart_widget.setBackground('w')  # White background

        # Don't show grid for Smith chart (we draw custom grid)
        self.plot_item.showGrid(False)

    def _create_legend(self) -> None:
        """Create legend for Smith chart - similar to ChartView."""
        if self._legend is None:
            self._legend = self.plot_item.addLegend()
            # Configure legend appearance
            self._legend.setOffset((10, 10))  # Offset from top-left corner

    def set_chart_title(self, title: str) -> None:
        """Set the chart title."""
        if self._chart_title != title:
            self._chart_title = title
            self.plot_item.setTitle(title)
            self.chart_title_changed.emit(title)
            self.properties_changed.emit()

    def get_chart_title(self) -> str:
        """Get the current chart title."""
        return self._chart_title

    def set_chart_tab_title(self, title: str) -> None:
        """Set the tab title (without type suffix)."""
        if self._tab_title != title:
            self._tab_title = title
            # Emit with (Smith) suffix
            self.tab_title_changed.emit(f"{title} (Smith)")
            self.properties_changed.emit()

    def get_chart_tab_title(self) -> str:
        """Get the tab title."""
        return self._tab_title

    def get_tab_title(self) -> str:
        """Get the tab title with (Smith) suffix for display."""
        return f"{self._tab_title} (Smith)"

    def set_tab_title(self, title: str) -> None:
        """Set the tab title (alias for compatibility with ChartView)."""
        self.set_chart_tab_title(title)

    def _setup_grid(self):
        """Initialize Smith chart grid."""
        self.grid_generator = SmithChartGrid()
        self.grid_items = []
        self.label_items = []

        # Draw Smith chart boundary circle
        self._draw_boundary()

        # Update grid based on checkbox state
        self._update_grid()

    def _draw_boundary(self):
        """Draw the unit circle boundary of the Smith chart."""
        # Generate full circle
        num_points = 200
        theta = np.linspace(0, 2 * np.pi, num_points)
        x_circle = np.cos(theta)
        y_circle = np.sin(theta)

        # Create pen for boundary - black like ChartView traces
        boundary_pen = pg.mkPen(color='k', width=2)

        # Use plot() method exactly like ChartView does
        self.boundary_item = self.plot_item.plot(
            x_circle, y_circle,
            pen=boundary_pen
        )

    def _update_grid(self):
        """Update Smith chart grid display."""
        # Clear existing grid
        for item in self.grid_items:
            self.plot_item.removeItem(item)
        for item in self.label_items:
            self.plot_item.removeItem(item)

        self.grid_items.clear()
        self.label_items.clear()

        if not self.grid_checkbox.isChecked():
            return

        # Generate grid data
        grid_data = self.grid_generator.generate_grid()

        # Draw resistance circles - use pg.mkPen for consistency
        grid_pen = pg.mkPen(color=(150, 150, 150), width=1, style=Qt.DashLine)

        # Draw horizontal real axis line (x-axis from -1 to 1, y=0)
        real_axis = self.plot_item.plot(
            [-1, 1], [0, 0],
            pen=grid_pen
        )
        self.grid_items.append(real_axis)

        for circle in grid_data['resistance_circles']:
            # Use plot() method exactly like ChartView
            curve = self.plot_item.plot(
                circle['x'], circle['y'],
                pen=grid_pen
            )
            self.grid_items.append(curve)

            # Add label if enabled
            if self.labels_checkbox.isChecked() and len(circle['x']) > 0:
                # Place label at the LEFT crossing point with horizontal line (y=0)
                # This is where the circle intersects the real axis on the left side
                r_value = circle['value']
                center_x = r_value / (1 + r_value)
                radius = 1 / (1 + r_value)

                # Left intersection point: center_x - radius, y = 0
                label_x = center_x - radius
                label_y = 0

                label_item = pg.TextItem(
                    circle['label'],
                    color=(80, 80, 80),
                    anchor=(1.0, 0.5)  # Anchor at right-center so label is to the left
                )
                label_item.setPos(label_x - 0.05, label_y)  # Slight offset to the left
                self.plot_item.addItem(label_item)
                self.label_items.append(label_item)

        # Draw reactance arcs
        for arc in grid_data['reactance_arcs']:
            # Use plot() method exactly like ChartView
            curve = self.plot_item.plot(
                arc['x'], arc['y'],
                pen=grid_pen
            )
            self.grid_items.append(curve)

            # Add label if enabled
            if self.labels_checkbox.isChecked() and len(arc['x']) > 0:
                # Calculate the intersection point with unit circle
                # All reactance arcs pass through (1, 0) which is common
                # We want the OTHER intersection point which is unique to each arc
                x_value = arc['value']

                if abs(x_value) < 1e-10:
                    # Real axis - label at the right end
                    x_label = 1.0
                    y_label = 0.0
                else:
                    # Find the intersection point that is NOT (1, 0)
                    # Filter out points close to (1, 0) and find the one closest to unit circle
                    distances_from_origin = np.sqrt(arc['x']**2 + arc['y']**2)
                    distances_from_1_0 = np.sqrt((arc['x'] - 1.0)**2 + arc['y']**2)

                    # Exclude points too close to (1, 0) - within 0.1 distance
                    valid_mask = distances_from_1_0 > 0.1

                    if np.any(valid_mask):
                        # Among valid points, find the one closest to unit circle
                        valid_distances = distances_from_origin[valid_mask]
                        valid_x = arc['x'][valid_mask]
                        valid_y = arc['y'][valid_mask]

                        # Get the point with maximum distance (closest to unit circle)
                        idx = np.argmax(valid_distances)
                        x_label = valid_x[idx]
                        y_label = valid_y[idx]
                    else:
                        # Fallback to maximum distance point
                        idx = np.argmax(distances_from_origin)
                        x_label = arc['x'][idx]
                        y_label = arc['y'][idx]

                # Position label slightly outside the unit circle
                # Calculate direction from center to this point
                angle = np.arctan2(y_label, x_label)
                offset = 0.10
                x_label_pos = x_label + offset * np.cos(angle)
                y_label_pos = y_label + offset * np.sin(angle)

                # Anchor at center
                label_item = pg.TextItem(
                    arc['label'],
                    color=(80, 80, 80),
                    anchor=(0.5, 0.5)
                )
                label_item.setPos(x_label_pos, y_label_pos)
                self.plot_item.addItem(label_item)
                self.label_items.append(label_item)

    def set_dataset(self, dataset: Dataset):
        """
        Set/add a dataset for Smith chart display.
        For backward compatibility only - stores as _dataset for later use by add_trace.
        Note: With the new pattern, datasets are stored per-trace in add_trace().
        """
        # For backward compatibility with single-dataset code
        self._dataset = dataset

    def add_trace(self, trace: Trace, style: TraceStyle = None, dataset: Dataset = None):
        """
        Add a trace to the Smith chart.

        Args:
            trace: Trace object containing S-parameter data
            style: Optional styling information
            dataset: Dataset containing the trace data (optional, for multi-dataset support)
        """
        # Generate trace_id using standardized format to match AddTracesDialog expectations
        # Format: dataset_id:S{i},{j}_{chart_type}
        # This matches the format used by ChartView and expected by AddTracesDialog
        trace_id = f"{trace.dataset_id}:S{trace.port_path.i},{trace.port_path.j}_smith"

        # Support both old single-dataset and new multi-dataset APIs
        if dataset is not None:
            # Multi-dataset API: store dataset by trace_id like ChartView
            trace_dataset = dataset
        elif self._dataset is not None:
            # Fallback to single dataset (backward compatibility)
            trace_dataset = self._dataset
        else:
            return

        # Prepare Smith chart data
        try:
            mode = 'Z' if 'Impedance' in self.mode_combo.currentText() else 'Y'
            plot_data = prepare_smith_data(trace, trace_dataset, mode=mode)
        except Exception:
            import traceback
            traceback.print_exc()
            return

        # Apply styling - use defaults if not provided
        if style is None:
            style = TraceStyle()

        # Create pen exactly like ChartView does
        pen = pg.mkPen(color=style.color, width=style.line_width)
        if style.line_style == 'dashed':
            pen.setStyle(Qt.DashLine)
        elif style.line_style == 'dotted':
            pen.setStyle(Qt.DotLine)

        # Create plot item using plot() method exactly like ChartView
        # Smith chart traces don't use symbols, just line styles
        # Use plot_data.label which includes dataset display name
        plot_item = self.plot_item.plot(
            plot_data.x, plot_data.y,
            pen=pen,
            name=plot_data.label  # Use plot_data.label, not trace.label
        )

        # Make plot item clickable for trace properties
        plot_item.curve.setClickable(True, width=10)

        # Connect click signal for trace properties
        plot_item.sigClicked.connect(
            lambda plot, event, tid=trace_id, pi=plot_item:
            self._on_trace_clicked(tid, pi, event)
        )

        # Store references - match ChartView pattern
        self._traces[trace_id] = trace
        self._datasets[trace_id] = trace_dataset  # Store dataset by trace_id like ChartView
        self._plot_items[trace_id] = plot_item

        # Apply legend styling to newly added legend item (critical for color preservation)
        # This ensures that legend color settings are applied to the new legend entry
        # Only apply if we have styling configured (avoid applying defaults during initial load)
        if self._chart_fonts.get('legend') or self._chart_colors.get('legend'):
            self._apply_font_styling()
            self._apply_color_styling()

    def remove_trace(self, trace_id: str):
        """Remove a trace from the Smith chart."""
        if trace_id in self._plot_items:
            self.plot_item.removeItem(self._plot_items[trace_id])
            del self._plot_items[trace_id]

        if trace_id in self._traces:
            del self._traces[trace_id]

        if trace_id in self._datasets:
            del self._datasets[trace_id]

        if trace_id in self._markers:
            self.plot_item.removeItem(self._markers[trace_id])
            del self._markers[trace_id]

    def remove_traces_by_dataset(self, dataset_id: str) -> int:
        """
        Remove all traces from a specific dataset.

        Args:
            dataset_id: ID of the dataset whose traces should be removed

        Returns:
            Number of traces removed
        """
        traces_to_remove = []

        # Find all traces that belong to this dataset - match ChartView pattern
        for trace_id, dataset in self._datasets.items():
            if dataset.id == dataset_id:
                traces_to_remove.append(trace_id)

        # Remove the traces
        for trace_id in traces_to_remove:
            self.remove_trace(trace_id)

        # Clear backward compatibility reference if it matches
        if self._dataset and self._dataset.id == dataset_id:
            self._dataset = None

        return len(traces_to_remove)

    def clear_traces(self):
        """Remove all traces from the Smith chart."""
        # Get list of all trace IDs to avoid dictionary modification during iteration
        # Use _traces.keys() not _plot_items.keys() to match ChartView
        trace_ids = list(self._traces.keys())

        # Remove each trace
        for trace_id in trace_ids:
            self.remove_trace(trace_id)

        # Clear backward compatibility reference
        self._dataset = None

    def get_existing_trace_ids(self) -> list[str]:
        """Get list of existing trace IDs in this chart."""
        return list(self._traces.keys())

    def get_existing_traces(self) -> Dict[str, Tuple[str, Trace, Dataset]]:
        """
        Get dictionary of existing traces with their details.

        Returns:
            Dictionary mapping trace_id to (dataset_id, trace, dataset) tuples.
            Matches ChartView's interface for compatibility with AddTracesDialog.
        """
        existing_traces = {}
        for trace_id, trace in self._traces.items():
            # SmithView stores datasets by trace_id (like ChartView)
            if trace_id in self._datasets:
                dataset = self._datasets[trace_id]
                # Use dataset.id as the authoritative dataset ID
                existing_traces[trace_id] = (dataset.id, trace, dataset)
            else:
                # Fallback for traces without datasets (shouldn't happen in normal operation)
                existing_traces[trace_id] = (trace.dataset_id, trace, None)
        return existing_traces

    def get_limit_lines(self) -> Dict[str, Any]:
        """
        Get limit lines (Smith charts don't support limit lines, return empty dict).

        This method is required for save/load compatibility with ChartView.
        """
        return {}

    def restore_limit_lines(self, limit_lines: Dict[str, Any]) -> None:
        """
        Restore limit lines (Smith charts don't support limit lines, no-op).

        This method is required for save/load compatibility with ChartView.
        """
        pass

    def update_dataset_name(self, dataset_id: str, new_name: str) -> bool:
        """
        Update the dataset name and refresh legend entries for traces from this dataset.

        Args:
            dataset_id: UUID of the dataset to update
            new_name: New display name for the dataset

        Returns:
            True if any traces were updated, False otherwise
        """
        updated = False

        # Update the dataset's display_name for all traces from this dataset
        # Match ChartView: iterate over _datasets which is keyed by trace_id
        for trace_id, dataset in self._datasets.items():
            if dataset.id == dataset_id:
                # Update the dataset's display_name
                dataset.display_name = new_name

                # Refresh the legend entry for this trace
                if trace_id in self._plot_items and trace_id in self._traces:
                    trace = self._traces[trace_id]

                    # Regenerate plot data to get the updated label
                    from snpviewer.frontend.plotting.plot_pipelines import \
                        prepare_smith_data
                    try:
                        mode = 'Z' if 'Impedance' in self.mode_combo.currentText() else 'Y'
                        plot_data = prepare_smith_data(trace, dataset, mode=mode)

                        if plot_data and self._legend:
                            # Find this item in the legend and update its label
                            plot_item = self._plot_items[trace_id]
                            if hasattr(self._legend, 'items'):
                                for idx, (sample, label) in enumerate(self._legend.items):
                                    # The sample is an ItemSample, get the actual plot item
                                    actual_item = None
                                    if hasattr(sample, 'item'):
                                        actual_item = sample.item

                                    if actual_item == plot_item or actual_item is plot_item:
                                        # Found the matching item - update its label text
                                        label.setText(plot_data.label)
                                        label.updateGeometry()

                                        # Force legend to update its layout
                                        if hasattr(self._legend, 'updateSize'):
                                            self._legend.updateSize()

                                        break
                    except Exception as e:
                        print(f"Warning: Could not update legend label: {e}")

                updated = True

        return updated

    def export_image(self, filename: str):
        """Export Smith chart as image."""
        exporter = pg.exporters.ImageExporter(self.plot_item)
        exporter.export(filename)

    def export_data(self, filename: str):
        """Export trace data as CSV."""
        if not self._traces:
            return

        with open(filename, 'w') as f:
            # Write header
            f.write("Trace,Frequency_Hz,Real,Imaginary,Magnitude,Phase_deg\n")

            # Write data for each trace
            for trace_id, trace in self._traces.items():
                if trace_id in self._plot_items:
                    plot_item = self._plot_items[trace_id]
                    x_data = plot_item.xData
                    y_data = plot_item.yData

                    # Convert back to complex reflection coefficients
                    gamma = x_data + 1j * y_data
                    magnitude = np.abs(gamma)
                    phase = np.angle(gamma, deg=True)

                    # Use dataset frequency
                    freq = self._dataset.frequency_hz

                    for i in range(len(x_data)):
                        f.write(f"{trace.label},{freq[i]},{x_data[i]},{y_data[i]},{magnitude[i]},{phase[i]}\n")

    def _on_mode_changed(self, mode_text: str):
        """Handle mode change between impedance and admittance."""
        # Refresh all traces with new mode
        traces_to_refresh = list(self._traces.items())
        self.clear_traces()

        for trace_id, trace in traces_to_refresh:
            # TODO: Restore original styling
            self.add_trace(trace)

    def _on_grid_toggled(self, checked: bool):
        """Handle grid visibility toggle."""
        self._update_grid()

    def _on_labels_toggled(self, checked: bool):
        """Handle grid labels visibility toggle."""
        self._update_grid()

    def _on_mouse_moved(self, pos):
        """Handle mouse movement for coordinate display."""
        if self.plot_item.sceneBoundingRect().contains(pos):
            mouse_point = self.plot_item.vb.mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()

            # Calculate reflection coefficient
            gamma = complex(x, y)

            # Convert to impedance/admittance
            if 'Impedance' in self.mode_combo.currentText():
                if abs(1 - gamma) > 1e-10:
                    z = (1 + gamma) / (1 - gamma)
                    coord_text = f"Γ: {gamma:.3f} | Z: {z:.3f}"
                else:
                    coord_text = f"Γ: {gamma:.3f} | Z: ∞"
            else:
                if abs(1 + gamma) > 1e-10:
                    y_val = (1 - gamma) / (1 + gamma)
                    coord_text = f"Γ: {gamma:.3f} | Y: {y_val:.3f}"
                else:
                    coord_text = f"Γ: {gamma:.3f} | Y: ∞"

            self.coord_label.setText(coord_text)
        else:
            self.coord_label.setText("Γ: -- | Z: --")

    def _show_context_menu(self, pos):
        """Show context menu for chart operations - matches ChartView."""
        menu = QMenu(self)

        # View actions
        auto_range_action = QAction("Auto Range", self)
        auto_range_action.triggered.connect(self.plot_item.autoRange)
        menu.addAction(auto_range_action)

        menu.addSeparator()

        # Trace management actions
        add_traces_action = QAction("Add Traces...", self)
        add_traces_action.triggered.connect(lambda: self.add_traces_requested.emit())
        menu.addAction(add_traces_action)

        clear_all_traces_action = QAction("Clear All Traces", self)
        clear_all_traces_action.triggered.connect(self._remove_all_traces)
        menu.addAction(clear_all_traces_action)

        menu.addSeparator()

        # Legend properties action
        legend_properties_action = QAction("Legend Properties...", self)
        legend_properties_action.triggered.connect(self._show_legend_properties_dialog)
        menu.addAction(legend_properties_action)

        menu.addSeparator()

        # Chart management actions
        change_chart_title_action = QAction("Change Chart Title...", self)
        change_chart_title_action.triggered.connect(self._change_chart_title)
        menu.addAction(change_chart_title_action)

        menu.addSeparator()

        # Export actions
        export_image_action = QAction("Export as Image...", self)
        export_image_action.triggered.connect(self._export_image_dialog)
        menu.addAction(export_image_action)

        export_data_action = QAction("Export Data as CSV...", self)
        export_data_action.triggered.connect(self._export_data_dialog)
        menu.addAction(export_data_action)

        menu.exec_(self.chart_widget.mapToGlobal(pos))

    def _export_image_dialog(self):
        """Show export image dialog."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Smith Chart", "", "PNG Files (*.png);;All Files (*)"
        )
        if filename:
            self.export_image(filename)

    def _export_data_dialog(self):
        """Show export data dialog."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Data", "", "CSV Files (*.csv);;All Files (*)"
        )
        if filename:
            self.export_data(filename)

    def _remove_all_traces(self):
        """Remove all traces from the chart."""
        if not self._traces:
            QMessageBox.information(self, "No Traces", "No traces to remove.")
            return

        reply = QMessageBox.question(
            self,
            "Clear Traces",
            "Are you sure you want to remove all traces from this chart?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.clear_traces()
            self.properties_changed.emit()

    def _change_chart_title(self):
        """Show dialog to change chart title with font and color options."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Chart Title Properties")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)

        # Title text
        title_layout = QVBoxLayout()
        title_layout.addWidget(QLabel("Title Text:"))
        title_input = QLineEdit(self._chart_title)
        title_layout.addWidget(title_input)
        layout.addLayout(title_layout)

        # Font properties group
        font_group = QGroupBox("Font Properties")
        font_layout = QVBoxLayout(font_group)

        # Get current font or use default
        current_font = self._chart_fonts.get('title', QFont("Arial", 12))

        # Font family
        family_layout = QHBoxLayout()
        family_layout.addWidget(QLabel("Font Family:"))
        font_combo = QComboBox()
        font_combo.addItems(["Arial", "Times New Roman", "Courier New", "Helvetica", "Verdana", "Georgia"])
        font_combo.setCurrentText(current_font.family())
        family_layout.addWidget(font_combo)
        font_layout.addLayout(family_layout)

        # Font size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Font Size:"))
        size_spin = QSpinBox()
        size_spin.setMinimum(6)
        size_spin.setMaximum(72)
        size_spin.setValue(current_font.pointSize())
        size_layout.addWidget(size_spin)
        size_layout.addStretch()
        font_layout.addLayout(size_layout)

        # Font style
        style_layout = QHBoxLayout()
        bold_check = QCheckBox("Bold")
        bold_check.setChecked(current_font.bold())
        italic_check = QCheckBox("Italic")
        italic_check.setChecked(current_font.italic())
        style_layout.addWidget(bold_check)
        style_layout.addWidget(italic_check)
        style_layout.addStretch()
        font_layout.addLayout(style_layout)

        layout.addWidget(font_group)

        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Title Color:"))
        color_button = QPushButton()
        color_button.setFixedSize(80, 30)

        # Get current color or use default
        current_color = self._chart_colors.get('title', '#000000')
        color_button.setStyleSheet(f"background-color: {current_color}; border: 1px solid black;")
        color_button.current_color = current_color

        def choose_color():
            color = QColorDialog.getColor(QColor(color_button.current_color), dialog, "Choose Title Color")
            if color.isValid():
                color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
                color_button.current_color = color.name()

        color_button.clicked.connect(choose_color)
        color_layout.addWidget(color_button)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        # Buttons
        button_layout = QHBoxLayout()
        apply_button = QPushButton("Apply")
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        def apply_changes():
            new_title = title_input.text().strip()
            if new_title:
                # Update title text
                self.set_chart_title(new_title)

                # Update font
                font = QFont(font_combo.currentText(), size_spin.value())
                if bold_check.isChecked():
                    font.setWeight(QFont.Weight.Bold)
                if italic_check.isChecked():
                    font.setItalic(True)
                self.set_title_font(font)

                # Update color
                self.set_title_color(color_button.current_color)

        apply_button.clicked.connect(apply_changes)
        ok_button.clicked.connect(lambda: (apply_changes(), dialog.accept()))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def _show_legend_properties_dialog(self) -> None:
        """Show dialog to configure legend properties (columns, font, color)."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Legend Properties")
        dialog.setModal(True)
        dialog.resize(400, 400)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel("Configure legend appearance and layout.")
        info_label.setStyleSheet("color: #666; font-style: italic;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Layout group
        layout_group = QGroupBox("Layout")
        layout_group_layout = QVBoxLayout(layout_group)

        columns_layout = QHBoxLayout()
        columns_layout.addWidget(QLabel("Number of Columns:"))
        columns_spin = QSpinBox()
        columns_spin.setMinimum(1)
        columns_spin.setMaximum(10)
        columns_spin.setValue(self._legend_columns)
        columns_spin.setToolTip("Number of columns in the legend (1-10)")
        columns_layout.addWidget(columns_spin)
        columns_layout.addStretch()
        layout_group_layout.addLayout(columns_layout)

        layout.addWidget(layout_group)

        # Font properties group
        font_group = QGroupBox("Font Properties")
        font_layout = QVBoxLayout(font_group)

        # Get current font or use default
        current_font = self._chart_fonts.get('legend', QFont("Arial", 10))

        # Font family
        family_layout = QHBoxLayout()
        family_layout.addWidget(QLabel("Font Family:"))
        font_combo = QComboBox()
        font_combo.addItems(["Arial", "Times New Roman", "Courier New", "Helvetica", "Verdana", "Georgia"])
        font_combo.setCurrentText(current_font.family())
        family_layout.addWidget(font_combo)
        font_layout.addLayout(family_layout)

        # Font size
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Font Size:"))
        size_spin = QSpinBox()
        size_spin.setMinimum(6)
        size_spin.setMaximum(24)
        size_spin.setValue(current_font.pointSize())
        size_layout.addWidget(size_spin)
        size_layout.addStretch()
        font_layout.addLayout(size_layout)

        # Font style
        style_layout = QHBoxLayout()
        bold_check = QCheckBox("Bold")
        bold_check.setChecked(current_font.bold())
        italic_check = QCheckBox("Italic")
        italic_check.setChecked(current_font.italic())
        style_layout.addWidget(bold_check)
        style_layout.addWidget(italic_check)
        style_layout.addStretch()
        font_layout.addLayout(style_layout)

        layout.addWidget(font_group)

        # Color selection
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Legend Text Color:"))
        color_button = QPushButton()
        color_button.setFixedSize(80, 30)

        # Get current color or use default
        current_color = self._chart_colors.get('legend', '#000000')
        color_button.setStyleSheet(f"background-color: {current_color}; border: 1px solid black;")
        color_button.current_color = current_color

        def choose_color():
            color = QColorDialog.getColor(QColor(color_button.current_color), dialog, "Choose Legend Color")
            if color.isValid():
                color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
                color_button.current_color = color.name()

        color_button.clicked.connect(choose_color)
        color_layout.addWidget(color_button)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        # Buttons
        button_layout = QHBoxLayout()
        apply_button = QPushButton("Apply")
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        def apply_legend_settings():
            # Update columns
            new_columns = columns_spin.value()
            if new_columns != self._legend_columns:
                self.set_legend_columns(new_columns)

            # Update font
            font = QFont(font_combo.currentText(), size_spin.value())
            if bold_check.isChecked():
                font.setWeight(QFont.Weight.Bold)
            if italic_check.isChecked():
                font.setItalic(True)
            self.set_legend_font(font)

            # Update color
            self.set_legend_color(color_button.current_color)

        apply_button.clicked.connect(apply_legend_settings)
        ok_button.clicked.connect(lambda: (apply_legend_settings(), dialog.accept()))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def _on_trace_clicked(self, trace_id: str, plot_item, event=None) -> None:
        """Handle trace click to show context menu for trace actions."""
        self._show_trace_context_menu(trace_id, event)

    def _show_trace_context_menu(self, trace_id: str, event=None) -> None:
        """Show context menu for trace actions."""
        if trace_id not in self._traces:
            return

        # Create context menu
        menu = QMenu(self)

        # Trace Properties action
        properties_action = menu.addAction("Trace Properties...")
        properties_action.triggered.connect(lambda: self._show_trace_properties_dialog(selected_trace_id=trace_id))

        menu.addSeparator()

        # Delete Trace action
        delete_action = menu.addAction("Delete Trace")
        delete_action.triggered.connect(lambda: self._delete_trace_with_confirmation(trace_id))

        # Show menu at cursor position
        if event is not None:
            # Get the global position from the scene event using chart_widget
            global_pos = self.chart_widget.mapToGlobal(self.chart_widget.mapFromScene(event.scenePos()))
            menu.exec(global_pos)
        else:
            # Fallback to cursor position
            menu.exec(QCursor.pos())

    def _delete_trace_with_confirmation(self, trace_id: str) -> None:
        """Delete a trace after user confirmation."""
        if trace_id not in self._traces:
            return

        # Get the legend name from the plot item for confirmation message
        if trace_id in self._plot_items:
            plot_item = self._plot_items[trace_id]
            trace_label = plot_item.name() if hasattr(plot_item, 'name') else trace_id
        else:
            trace_label = trace_id

        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Delete Trace",
            f"Are you sure you want to delete the trace:\n\n{trace_label}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.remove_trace(trace_id)
            self.properties_changed.emit()

    def _show_trace_properties_dialog(self, selected_trace_id: str | None = None) -> None:
        """Show trace properties dialog for editing trace style."""
        if not self._traces:
            QMessageBox.information(self, "No Traces", "No traces are currently displayed in this chart.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Trace Properties")
        dialog.setModal(True)
        dialog.resize(380, 250)

        layout = QVBoxLayout(dialog)

        # Trace selection
        trace_layout = QHBoxLayout()
        trace_label = QLabel("Trace:")
        trace_combo = QComboBox()

        # Get the legend names for each trace
        for trace_id, trace in self._traces.items():
            if trace_id in self._plot_items:
                plot_item = self._plot_items[trace_id]
                legend_name = plot_item.name() if hasattr(plot_item, 'name') else trace_id
                trace_combo.addItem(legend_name, trace_id)
            else:
                trace_combo.addItem(trace_id, trace_id)

        # Set current selection to selected_trace_id if provided
        if selected_trace_id is not None:
            index = trace_combo.findData(selected_trace_id)
            if index != -1:
                trace_combo.setCurrentIndex(index)

        trace_layout.addWidget(trace_label)
        trace_layout.addWidget(trace_combo)
        trace_layout.addStretch()
        layout.addLayout(trace_layout)

        # Properties section
        props_group = QGroupBox("Properties")
        props_layout = QVBoxLayout(props_group)

        # Color selection
        color_layout = QHBoxLayout()
        color_label = QLabel("Color:")
        color_button = QPushButton()
        color_button.setFixedSize(50, 30)

        color_layout.addWidget(color_label)
        color_layout.addWidget(color_button)
        color_layout.addStretch()
        props_layout.addLayout(color_layout)

        # Line style selection
        style_layout = QHBoxLayout()
        style_label = QLabel("Line Style:")
        style_combo = QComboBox()
        style_combo.addItems(DEFAULT_LINE_STYLES)

        style_layout.addWidget(style_label)
        style_layout.addWidget(style_combo)
        style_layout.addStretch()
        props_layout.addLayout(style_layout)

        # Line width selection
        width_layout = QHBoxLayout()
        width_label = QLabel("Line Width:")
        width_spin = QSpinBox()
        width_spin.setMinimum(1)
        width_spin.setMaximum(10)

        width_layout.addWidget(width_label)
        width_layout.addWidget(width_spin)
        width_layout.addStretch()
        props_layout.addLayout(width_layout)

        layout.addWidget(props_group)

        # Buttons
        button_layout = QHBoxLayout()
        apply_button = QPushButton("Apply")
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")

        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Update properties when trace selection changes
        def update_properties():
            current_trace_id = trace_combo.currentData()
            if current_trace_id and current_trace_id in self._traces:
                trace = self._traces[current_trace_id]

                # Update color button
                current_color = QColor(trace.style.color)
                color_button.setStyleSheet(f"background-color: {current_color.name()}; border: 1px solid black;")
                color_button.current_color = current_color.name()

                # Update style combo
                style_combo.setCurrentText(trace.style.line_style)

                # Update width spin
                width_spin.setValue(int(trace.style.line_width))

        # Color button click handler
        def choose_color():
            current_trace_id = trace_combo.currentData()
            if current_trace_id and current_trace_id in self._traces:
                current_color = QColor(self._traces[current_trace_id].style.color)
                color = QColorDialog.getColor(current_color, dialog, "Choose Trace Color")
                if color.isValid():
                    color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
                    color_button.current_color = color.name()

        color_button.clicked.connect(choose_color)
        trace_combo.currentTextChanged.connect(update_properties)

        # Initialize with first trace
        if trace_combo.count() > 0:
            update_properties()

        # Button handlers
        def apply_changes():
            current_trace_id = trace_combo.currentData()
            if current_trace_id and current_trace_id in self._traces:
                trace = self._traces[current_trace_id]

                # Update trace style
                trace.style.color = getattr(color_button, 'current_color', trace.style.color)
                trace.style.line_style = style_combo.currentText()
                trace.style.line_width = float(width_spin.value())

                # Refresh the plot item with new style
                self._update_trace_style(current_trace_id)
                self.properties_changed.emit()

        apply_button.clicked.connect(apply_changes)
        ok_button.clicked.connect(lambda: (apply_changes(), dialog.accept()))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def _update_trace_style(self, trace_id: str) -> None:
        """Update the visual style of a trace."""
        if trace_id not in self._traces or trace_id not in self._plot_items:
            return

        trace = self._traces[trace_id]
        plot_item = self._plot_items[trace_id]

        # Create new pen with updated style
        pen = pg.mkPen(color=trace.style.color, width=trace.style.line_width)
        if trace.style.line_style == 'dashed':
            pen.setStyle(Qt.DashLine)
        elif trace.style.line_style == 'dotted':
            pen.setStyle(Qt.DotLine)

        # Update the plot item's pen
        plot_item.setPen(pen)

    # Legend column management
    def get_legend_columns(self) -> int:
        """Get the number of legend columns."""
        return self._legend_columns

    def set_legend_columns(self, columns: int) -> None:
        """Set the number of legend columns."""
        if columns > 0 and columns != self._legend_columns:
            self._legend_columns = columns
            if self._legend:
                self._legend.setColumnCount(columns)

    # Font and color management for chart title and legend
    def get_chart_fonts(self) -> Dict[str, Any]:
        """Get chart font settings for serialization (title and legend only)."""
        if not self._chart_fonts:
            return {}

        # Convert QFont objects to serializable dictionaries
        serializable_fonts = {}
        for key, font in self._chart_fonts.items():
            if key in ['title', 'legend']:  # Only save title and legend fonts
                if hasattr(font, 'family'):  # It's a QFont object
                    serializable_fonts[key] = {
                        'family': font.family(),
                        'pointSize': font.pointSize(),
                        'weight': font.weight(),
                        'italic': font.italic(),
                        'bold': font.bold()
                    }
                else:
                    serializable_fonts[key] = font  # Already serializable

        return serializable_fonts

    def get_chart_colors(self) -> Dict[str, str]:
        """Get chart color settings for serialization (title and legend only)."""
        if not self._chart_colors:
            return {}

        # Only return title and legend colors
        return {k: v for k, v in self._chart_colors.items() if k in ['title', 'legend']}

    def restore_chart_fonts(self, font_data: Dict[str, Any]) -> None:
        """Restore chart font settings from saved data (title and legend only)."""
        if not font_data:
            return

        for key, font_info in font_data.items():
            if key not in ['title', 'legend']:  # Only restore title and legend fonts
                continue

            try:
                if isinstance(font_info, dict) and 'family' in font_info:
                    # Reconstruct QFont from serialized data
                    family = font_info['family']
                    point_size = font_info.get('pointSize', 10)

                    # Create font with family and size
                    font = QFont(family, point_size)

                    # Set italic first (before weight/bold)
                    if font_info.get('italic', False):
                        font.setItalic(True)

                    # Handle weight
                    if 'weight' in font_info:
                        weight = font_info['weight']
                        if isinstance(weight, int):
                            font.setWeight(QFont.Weight(weight))
                        else:
                            font.setWeight(weight)
                    elif font_info.get('bold', False):
                        font.setWeight(QFont.Weight.Bold)

                    self._chart_fonts[key] = font
                else:
                    self._chart_fonts[key] = font_info
            except Exception as e:
                print(f"Warning: Could not restore font for {key}: {e}")
                self._chart_fonts[key] = QFont("Arial", 10)

        # Apply the restored fonts
        self._apply_font_styling()

    def restore_chart_colors(self, color_data: Dict[str, str]) -> None:
        """Restore chart color settings from saved data (title and legend only)."""
        if not color_data:
            return

        # Only restore title and legend colors
        for key, value in color_data.items():
            if key in ['title', 'legend']:
                self._chart_colors[key] = value

        # Apply the restored colors
        self._apply_color_styling()

    def _apply_font_styling(self) -> None:
        """Apply font styling to chart title and legend."""
        try:
            # Apply title font
            if 'title' in self._chart_fonts:
                font = self._chart_fonts['title']
                color = self._chart_colors.get('title', '#000000')

                # Use setTitle with color and size to apply initial styling
                self.plot_item.setTitle(
                    self._chart_title,
                    color=color,
                    size=f"{font.pointSize()}pt"
                )

                # Then apply complete font properties
                if hasattr(self.plot_item, 'titleLabel') and hasattr(self.plot_item.titleLabel, 'item'):
                    try:
                        # Apply the complete font (family, size, weight, italic)
                        self.plot_item.titleLabel.item.setFont(font)
                        # Reapply color to ensure it's set
                        self.plot_item.titleLabel.item.setDefaultTextColor(QColor(color))
                    except Exception as e:
                        print(f"Warning: Could not apply full title font: {e}")

            # Apply legend font
            if 'legend' in self._chart_fonts and self._legend:
                font = self._chart_fonts['legend']

                # Method 1: Use setLabelTextSize
                if hasattr(self._legend, 'setLabelTextSize'):
                    self._legend.setLabelTextSize(f"{font.pointSize()}pt")

                # Method 2: Apply font to existing legend items
                if hasattr(self._legend, 'items') and self._legend.items:
                    for sample, label in self._legend.items:
                        try:
                            if hasattr(label, 'setFont'):
                                label.setFont(font)
                            if hasattr(label, 'item') and hasattr(label.item, 'setFont'):
                                label.item.setFont(font)
                        except Exception:
                            pass

                # Force update
                if hasattr(self._legend, 'update'):
                    self._legend.update()
        except Exception as e:
            print(f"Warning: Could not apply font styling: {e}")

    def _apply_color_styling(self) -> None:
        """Apply color styling to chart title and legend."""
        try:
            # Apply title color
            if 'title' in self._chart_colors:
                color = self._chart_colors['title']
                font_size = "12pt"  # Default

                # Get font size if available
                if 'title' in self._chart_fonts:
                    font_size = f"{self._chart_fonts['title'].pointSize()}pt"

                # Use setTitle with color parameter
                self.plot_item.setTitle(
                    self._chart_title,
                    color=color,
                    size=font_size
                )

                # Also set color on the title label directly
                if hasattr(self.plot_item, 'titleLabel') and hasattr(self.plot_item.titleLabel, 'item'):
                    self.plot_item.titleLabel.item.setDefaultTextColor(QColor(color))

            # Apply legend color
            if 'legend' in self._chart_colors and self._legend:
                legend_color = self._chart_colors['legend']
                qcolor = QColor(legend_color)

                # Method 1: Try setLabelTextColor if available
                if hasattr(self._legend, 'setLabelTextColor'):
                    self._legend.setLabelTextColor(legend_color)

                # Method 2: Try setDefaultTextColor
                if hasattr(self._legend, 'setDefaultTextColor'):
                    self._legend.setDefaultTextColor(qcolor)

                # Method 3: Apply color to existing legend items (most reliable)
                if hasattr(self._legend, 'items') and self._legend.items:
                    for sample, label in self._legend.items:
                        try:
                            # Try multiple ways to set text color
                            if hasattr(label, 'setDefaultTextColor'):
                                label.setDefaultTextColor(qcolor)

                            if hasattr(label, 'item'):
                                text_item = label.item
                                if hasattr(text_item, 'setDefaultTextColor'):
                                    text_item.setDefaultTextColor(qcolor)
                                if hasattr(text_item, 'setColor'):
                                    text_item.setColor(qcolor)

                            # Try HTML approach as last resort (CRITICAL for PyQtGraph)
                            if hasattr(label, 'setText') and hasattr(label, 'text'):
                                current_text = label.text if callable(label.text) else str(label.text)
                                # Strip existing color tags first
                                clean_text = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', current_text)
                                clean_text = re.sub(r'<font[^>]*>(.*?)</font>', r'\1', clean_text)
                                # Wrap in span with color style
                                colored_text = f'<span style="color:{legend_color}">{clean_text}</span>'
                                label.setText(colored_text)
                        except Exception:
                            pass

                # Force update
                if hasattr(self._legend, 'update'):
                    self._legend.update()
        except Exception as e:
            print(f"Warning: Could not apply color styling: {e}")

    def set_title_font(self, font: QFont) -> None:
        """Set the font for the chart title."""
        self._chart_fonts['title'] = font
        self._apply_font_styling()
        self.properties_changed.emit()

    def set_title_color(self, color: str) -> None:
        """Set the color for the chart title."""
        self._chart_colors['title'] = color
        self._apply_color_styling()
        self.properties_changed.emit()

    def set_legend_font(self, font: QFont) -> None:
        """Set the font for the legend."""
        self._chart_fonts['legend'] = font
        self._apply_font_styling()
        self.properties_changed.emit()

    def set_legend_color(self, color: str) -> None:
        """Set the color for the legend."""
        self._chart_colors['legend'] = color
        self._apply_color_styling()
        self.properties_changed.emit()
