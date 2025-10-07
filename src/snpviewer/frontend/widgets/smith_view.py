"""
Smith Chart View Widget

Interactive Smith chart visualization for S-parameter reflection coefficients using PyQtGraph.
Displays complex impedance/admittance data on the Smith chart with customizable grid overlays.
"""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout,
                               QLabel, QMenu, QSizePolicy, QVBoxLayout,
                               QWidget, QFileDialog)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.trace import Trace, TraceStyle
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
                    'label': f'R={r}'
                })

        # Generate constant reactance arcs
        for x in x_values:
            arc = self._reactance_arc(x)
            if arc is not None:
                grid_data['reactance_arcs'].append({
                    'x': arc[0],
                    'y': arc[1],
                    'value': x,
                    'label': f'X={x}' if x >= 0 else f'X={x}'
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

        # Generate circle points
        theta = np.linspace(0, 2*np.pi, 100)
        x = center_x + radius * np.cos(theta)
        y = center_y + radius * np.sin(theta)

        # Clip to unit circle
        mask = (x**2 + y**2) <= 1.01  # Small tolerance
        return x[mask], y[mask]

    def _reactance_arc(self, x: float) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """Generate points for constant reactance arc."""
        if x == 0:
            # Real axis
            x_points = np.linspace(-1, 1, 100)
            y_points = np.zeros_like(x_points)
            return x_points, y_points

        # Arc center and radius in Smith chart coordinates
        center_x = 1
        center_y = 1 / x
        radius = abs(1 / x)

        # Generate arc points
        if x > 0:
            # Upper half
            theta_start = np.pi
            theta_end = 0
        else:
            # Lower half
            theta_start = 0
            theta_end = np.pi

        theta = np.linspace(theta_start, theta_end, 50)
        x_arc = center_x + radius * np.cos(theta)
        y_arc = center_y + radius * np.sin(theta)

        # Clip to unit circle
        mask = (x_arc**2 + y_arc**2) <= 1.01  # Small tolerance
        return x_arc[mask], y_arc[mask]


class SmithView(QWidget):
    """
    Smith Chart view widget for displaying S-parameter reflection coefficients.

    Features:
    - Interactive Smith chart with grid overlay
    - Multiple trace support with styling
    - Impedance/Admittance mode switching
    - Marker support and coordinate readout
    - Export capabilities (PNG, SVG, CSV)
    """

    # Signals
    trace_selected = Signal(str)  # trace_id
    marker_moved = Signal(str, float, complex)  # trace_id, frequency, value

    def __init__(self, parent=None):
        super().__init__(parent)

        self._dataset: Optional[Dataset] = None
        self._traces: Dict[str, Trace] = {}
        self._plot_items: Dict[str, pg.PlotDataItem] = {}
        self._markers: Dict[str, pg.InfiniteLine] = {}

        self._setup_ui()
        self._setup_chart()
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
        layout.addWidget(self.chart_widget)

    def _setup_chart(self):
        """Configure the Smith chart plot widget."""
        self.plot_item = self.chart_widget.getPlotItem()

        # Set equal aspect ratio for circular Smith chart
        self.plot_item.setAspectLocked(True, ratio=1)

        # Set axis limits to unit circle with padding
        self.plot_item.setXRange(-1.1, 1.1, padding=0)
        self.plot_item.setYRange(-1.1, 1.1, padding=0)

        # Configure axes
        self.plot_item.showGrid(False)  # We'll draw custom grid
        self.plot_item.setLabel('left', 'Imaginary')
        self.plot_item.setLabel('bottom', 'Real')
        self.plot_item.setTitle('Smith Chart')

        # Add mouse tracking
        self.chart_widget.setMouseTracking(True)
        self.plot_item.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Add context menu
        self.chart_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chart_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _setup_grid(self):
        """Initialize Smith chart grid."""
        self.grid_generator = SmithChartGrid()
        self.grid_items = []
        self.label_items = []

        # Draw unit circle boundary
        theta = np.linspace(0, 2*np.pi, 200)
        x_circle = np.cos(theta)
        y_circle = np.sin(theta)

        boundary_pen = QPen(QColor(100, 100, 100), 2)
        self.boundary_item = self.plot_item.plot(
            x_circle, y_circle,
            pen=boundary_pen,
            name="Boundary"
        )

        self._update_grid()

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

        # Draw resistance circles
        grid_pen = QPen(QColor(150, 150, 150), 1, Qt.DashLine)
        for circle in grid_data['resistance_circles']:
            item = self.plot_item.plot(
                circle['x'], circle['y'],
                pen=grid_pen,
                name=f"R={circle['value']}"
            )
            self.grid_items.append(item)

            # Add label if enabled
            if self.labels_checkbox.isChecked() and len(circle['x']) > 0:
                # Place label at rightmost point
                idx = np.argmax(circle['x'])
                label_item = pg.TextItem(
                    circle['label'],
                    color=(120, 120, 120),
                    anchor=(0, 0.5)
                )
                label_item.setPos(circle['x'][idx], circle['y'][idx])
                self.plot_item.addItem(label_item)
                self.label_items.append(label_item)

        # Draw reactance arcs
        for arc in grid_data['reactance_arcs']:
            item = self.plot_item.plot(
                arc['x'], arc['y'],
                pen=grid_pen,
                name=f"X={arc['value']}"
            )
            self.grid_items.append(item)

            # Add label if enabled
            if self.labels_checkbox.isChecked() and len(arc['x']) > 0:
                # Place label at edge of unit circle
                distances = arc['x']**2 + arc['y']**2
                idx = np.argmax(distances)
                label_item = pg.TextItem(
                    arc['label'],
                    color=(120, 120, 120),
                    anchor=(0.5, 0.5)
                )
                label_item.setPos(arc['x'][idx], arc['y'][idx])
                self.plot_item.addItem(label_item)
                self.label_items.append(label_item)

    def set_dataset(self, dataset: Dataset):
        """Set the dataset for Smith chart display."""
        self._dataset = dataset
        self.clear_traces()

    def add_trace(self, trace: Trace, style: TraceStyle = None):
        """
        Add a trace to the Smith chart.

        Args:
            trace: Trace object containing S-parameter data
            style: Optional styling information
        """
        if not self._dataset:
            return

        # Prepare Smith chart data
        try:
            mode = 'Z' if 'Impedance' in self.mode_combo.currentText() else 'Y'
            plot_data = prepare_smith_data(trace, self._dataset, mode=mode)
        except Exception as e:
            print(f"Error preparing Smith chart data: {e}")
            return

        # Apply styling
        if style is None:
            style = TraceStyle()

        pen = QPen(QColor(style.color), style.line_width)
        if style.line_style == 'dashed':
            pen.setStyle(Qt.DashLine)
        elif style.line_style == 'dotted':
            pen.setStyle(Qt.DotLine)

        # Create plot item
        plot_item = self.plot_item.plot(
            plot_data.x_data, plot_data.y_data,
            pen=pen,
            name=trace.label,
            symbol='o' if style.show_markers else None,
            symbolSize=4,
            symbolBrush=style.color
        )

        # Store references
        trace_id = f"{trace.domain}_{trace.metric}_{trace.port_path}"
        self._traces[trace_id] = trace
        self._plot_items[trace_id] = plot_item

    def remove_trace(self, trace_id: str):
        """Remove a trace from the Smith chart."""
        if trace_id in self._plot_items:
            self.plot_item.removeItem(self._plot_items[trace_id])
            del self._plot_items[trace_id]
            del self._traces[trace_id]

            if trace_id in self._markers:
                self.plot_item.removeItem(self._markers[trace_id])
                del self._markers[trace_id]

    def remove_traces_by_dataset(self, dataset_id: str) -> int:
        """
        Remove all traces from a specific dataset.

        For SmithView, if the dataset matches, all traces are removed since
        SmithView is designed for single-dataset use.

        Args:
            dataset_id: ID of the dataset whose traces should be removed

        Returns:
            Number of traces removed
        """
        if self._dataset and self._dataset.id == dataset_id:
            trace_count = len(self._traces)
            self.clear_traces()
            return trace_count
        return 0

    def clear_traces(self):
        """Remove all traces from the Smith chart."""
        for trace_id in list(self._plot_items.keys()):
            self.remove_trace(trace_id)

    def get_existing_trace_ids(self) -> list[str]:
        """Get list of existing trace IDs in this chart."""
        return list(self._traces.keys())

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
        """Show context menu for chart operations."""
        menu = QMenu(self)

        # Export actions
        export_image_action = QAction("Export as PNG...", self)
        export_image_action.triggered.connect(self._export_image_dialog)
        menu.addAction(export_image_action)

        export_data_action = QAction("Export Data as CSV...", self)
        export_data_action.triggered.connect(self._export_data_dialog)
        menu.addAction(export_data_action)

        menu.addSeparator()

        # View actions
        auto_range_action = QAction("Auto Range", self)
        auto_range_action.triggered.connect(self.plot_item.autoRange)
        menu.addAction(auto_range_action)

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
