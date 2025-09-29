"""
Marker interactions for chart widgets.

Provides interactive markers using PyQtGraph InfiniteLine and ROI widgets
with real-time value readouts for S-parameter analysis.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPen
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from snpviewer.backend.models.dataset import Dataset


@dataclass
class MarkerData:
    """Data for a single marker measurement."""
    marker_id: str
    trace_id: str
    frequency: float
    value: complex
    magnitude_db: float
    phase_deg: float
    real: float
    imag: float
    position_x: float  # Chart coordinate
    position_y: float  # Chart coordinate


class InteractiveMarker:
    """
    Interactive marker using PyQtGraph InfiniteLine for frequency-based measurements.

    Supports both Cartesian and Smith chart views with automatic value interpolation.
    """

    def __init__(self, marker_id: str, plot_item: pg.PlotItem, color: str = "#FF0000"):
        self.marker_id = marker_id
        self.plot_item = plot_item
        self.color = color
        self.visible = True

        # Create vertical line marker for frequency
        self.line = pg.InfiniteLine(
            angle=90,  # Vertical line
            movable=True,
            pen=QPen(QColor(color), 2, Qt.DashLine),
            label=f"M{marker_id}",
            labelOpts={'position': 0.95, 'color': color, 'movable': True}
        )

        # Connect signal for movement
        self.line.sigPositionChanged.connect(self._on_position_changed)

        # Add to plot
        self.plot_item.addItem(self.line)

        # Store reference traces for interpolation
        self.traces: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}  # trace_id -> (freq, x_data, y_data)

    def set_position(self, frequency: float):
        """Set marker position to specific frequency."""
        self.line.setPos(frequency)

    def get_position(self) -> float:
        """Get current marker frequency position."""
        return self.line.pos()[0]

    def add_trace_data(self, trace_id: str, frequency: np.ndarray, x_data: np.ndarray, y_data: np.ndarray):
        """Add trace data for interpolation."""
        self.traces[trace_id] = (frequency, x_data, y_data)

    def remove_trace_data(self, trace_id: str):
        """Remove trace data."""
        if trace_id in self.traces:
            del self.traces[trace_id]

    def get_interpolated_values(self) -> Dict[str, MarkerData]:
        """Get interpolated values at current marker position for all traces."""
        marker_freq = self.get_position()
        results = {}

        for trace_id, (freq_array, x_data, y_data) in self.traces.items():
            # Find interpolation points
            if marker_freq < freq_array[0] or marker_freq > freq_array[-1]:
                continue  # Outside frequency range

            # Linear interpolation
            x_value = np.interp(marker_freq, freq_array, x_data)
            y_value = np.interp(marker_freq, freq_array, y_data)

            # Convert to complex value (assuming x,y are real/imag or mag/phase)
            complex_value = complex(x_value, y_value)

            # Calculate derived values
            magnitude_db = 20 * np.log10(abs(complex_value)) if abs(complex_value) > 0 else -float('inf')
            phase_deg = np.angle(complex_value, deg=True)

            results[trace_id] = MarkerData(
                marker_id=self.marker_id,
                trace_id=trace_id,
                frequency=marker_freq,
                value=complex_value,
                magnitude_db=magnitude_db,
                phase_deg=phase_deg,
                real=x_value,
                imag=y_value,
                position_x=x_value,
                position_y=y_value
            )

        return results

    def set_visible(self, visible: bool):
        """Set marker visibility."""
        self.visible = visible
        self.line.setVisible(visible)

    def remove(self):
        """Remove marker from plot."""
        self.plot_item.removeItem(self.line)

    def _on_position_changed(self):
        """Handle marker position change."""
        # This will be connected to MarkerController signals
        pass


class SmithMarker:
    """
    Interactive marker for Smith charts using crosshair display.

    Shows reflection coefficient and impedance/admittance values at cursor position.
    """

    def __init__(self, marker_id: str, plot_item: pg.PlotItem, color: str = "#FF0000"):
        self.marker_id = marker_id
        self.plot_item = plot_item
        self.color = color
        self.visible = True

        # Create crosshair lines
        self.h_line = pg.InfiniteLine(angle=0, movable=False, pen=QPen(QColor(color), 1, Qt.DashLine))
        self.v_line = pg.InfiniteLine(angle=90, movable=False, pen=QPen(QColor(color), 1, Qt.DashLine))

        # Create marker point
        self.marker_point = pg.ScatterPlotItem(
            pos=[(0, 0)],
            size=8,
            brush=QColor(color),
            pen=QPen(QColor(color), 2),
            symbol='o'
        )

        # Add to plot
        self.plot_item.addItem(self.h_line)
        self.plot_item.addItem(self.v_line)
        self.plot_item.addItem(self.marker_point)

        # Store trace data for nearest point finding
        self.traces: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

        # Current position
        self.current_pos = (0.0, 0.0)

    def set_position(self, x: float, y: float):
        """Set marker position in Smith chart coordinates."""
        self.current_pos = (x, y)
        self.h_line.setPos(y)
        self.v_line.setPos(x)
        self.marker_point.setData(pos=[(x, y)])

    def get_position(self) -> Tuple[float, float]:
        """Get current marker position."""
        return self.current_pos

    def add_trace_data(self, trace_id: str, frequency: np.ndarray, x_data: np.ndarray, y_data: np.ndarray):
        """Add trace data for nearest point finding."""
        self.traces[trace_id] = (frequency, x_data, y_data)

    def remove_trace_data(self, trace_id: str):
        """Remove trace data."""
        if trace_id in self.traces:
            del self.traces[trace_id]

    def find_nearest_points(self) -> Dict[str, MarkerData]:
        """Find nearest points on all traces to current marker position."""
        marker_x, marker_y = self.current_pos
        results = {}

        for trace_id, (freq_array, x_data, y_data) in self.traces.items():
            # Find nearest point
            distances = (x_data - marker_x)**2 + (y_data - marker_y)**2
            nearest_idx = np.argmin(distances)

            # Get values at nearest point
            x_value = x_data[nearest_idx]
            y_value = y_data[nearest_idx]
            frequency = freq_array[nearest_idx]
            complex_value = complex(x_value, y_value)

            # Calculate derived values
            magnitude = abs(complex_value)
            phase_deg = np.angle(complex_value, deg=True)

            results[trace_id] = MarkerData(
                marker_id=self.marker_id,
                trace_id=trace_id,
                frequency=frequency,
                value=complex_value,
                magnitude_db=20 * np.log10(magnitude) if magnitude > 0 else -float('inf'),
                phase_deg=phase_deg,
                real=x_value,
                imag=y_value,
                position_x=x_value,
                position_y=y_value
            )

        return results

    def set_visible(self, visible: bool):
        """Set marker visibility."""
        self.visible = visible
        self.h_line.setVisible(visible)
        self.v_line.setVisible(visible)
        self.marker_point.setVisible(visible)

    def remove(self):
        """Remove marker from plot."""
        self.plot_item.removeItem(self.h_line)
        self.plot_item.removeItem(self.v_line)
        self.plot_item.removeItem(self.marker_point)


class MarkerController(QWidget):
    """
    Marker control widget with table display and interaction controls.

    Manages multiple markers across different chart types with real-time value updates.
    """

    # Signals
    marker_added = Signal(str)  # marker_id
    marker_removed = Signal(str)  # marker_id
    marker_moved = Signal(str, dict)  # marker_id, marker_data_dict

    def __init__(self, parent=None):
        super().__init__(parent)

        self.markers: Dict[str, Any] = {}  # marker_id -> InteractiveMarker or SmithMarker
        self.chart_type = "cartesian"  # "cartesian" or "smith"
        self.plot_item: Optional[pg.PlotItem] = None
        self.dataset: Optional[Dataset] = None

        # Marker colors
        self.marker_colors = ["#FF0000", "#00FF00", "#0000FF", "#FF00FF", "#00FFFF", "#FFFF00"]
        self.next_marker_id = 1

        self._setup_ui()

        # Update timer for marker values
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_marker_values)
        self.update_timer.start(100)  # 10 Hz update rate

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header with controls
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.StyledPanel)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(6, 4, 6, 4)

        self.title_label = QLabel("Markers")
        font = QFont()
        font.setBold(True)
        self.title_label.setFont(font)

        self.add_button = QPushButton("Add")
        self.add_button.clicked.connect(self.add_marker)

        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_selected_marker)

        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_markers)

        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.add_button)
        header_layout.addWidget(self.remove_button)
        header_layout.addWidget(self.clear_button)

        layout.addWidget(header_frame)

        # Marker table
        self.marker_table = QTableWidget()
        self.marker_table.setColumnCount(8)
        self.marker_table.setHorizontalHeaderLabels([
            "Marker", "Trace", "Frequency", "Magnitude", "Phase", "Real", "Imag", "Visible"
        ])

        # Set column widths
        header = self.marker_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Marker
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Trace
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Frequency
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Magnitude
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Phase
        header.setSectionResizeMode(5, QHeaderView.Fixed)  # Real
        header.setSectionResizeMode(6, QHeaderView.Fixed)  # Imag
        header.setSectionResizeMode(7, QHeaderView.Fixed)  # Visible

        self.marker_table.setColumnWidth(0, 60)  # Marker
        self.marker_table.setColumnWidth(2, 100)  # Frequency
        self.marker_table.setColumnWidth(3, 80)   # Magnitude
        self.marker_table.setColumnWidth(4, 80)   # Phase
        self.marker_table.setColumnWidth(5, 80)   # Real
        self.marker_table.setColumnWidth(6, 80)   # Imag
        self.marker_table.setColumnWidth(7, 60)   # Visible

        self.marker_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.marker_table)

    def set_chart(self, plot_item: pg.PlotItem, chart_type: str = "cartesian"):
        """Set the target chart for marker interactions."""
        self.plot_item = plot_item
        self.chart_type = chart_type
        self.clear_markers()  # Clear existing markers when switching charts

    def set_dataset(self, dataset: Dataset):
        """Set the dataset for marker calculations."""
        self.dataset = dataset

    def add_marker(self) -> str:
        """Add a new marker to the chart."""
        if not self.plot_item:
            return ""

        marker_id = str(self.next_marker_id)
        color = self.marker_colors[(self.next_marker_id - 1) % len(self.marker_colors)]

        if self.chart_type == "cartesian":
            marker = InteractiveMarker(marker_id, self.plot_item, color)
            # Set initial position to middle of frequency range
            if self.dataset:
                mid_freq = (self.dataset.frequency_hz[0] + self.dataset.frequency_hz[-1]) / 2
                marker.set_position(mid_freq)
        else:  # Smith chart
            marker = SmithMarker(marker_id, self.plot_item, color)
            marker.set_position(0.0, 0.0)  # Center of Smith chart

        self.markers[marker_id] = marker
        self.next_marker_id += 1

        self._update_table()
        self.marker_added.emit(marker_id)

        return marker_id

    def remove_marker(self, marker_id: str):
        """Remove a marker by ID."""
        if marker_id in self.markers:
            self.markers[marker_id].remove()
            del self.markers[marker_id]
            self._update_table()
            self.marker_removed.emit(marker_id)

    def remove_selected_marker(self):
        """Remove currently selected marker."""
        current_row = self.marker_table.currentRow()
        if current_row >= 0:
            marker_id = self.marker_table.item(current_row, 0).text().replace("M", "")
            self.remove_marker(marker_id)

    def clear_markers(self):
        """Remove all markers."""
        for marker_id in list(self.markers.keys()):
            self.remove_marker(marker_id)

    def add_trace_data(self, trace_id: str, frequency: np.ndarray, x_data: np.ndarray, y_data: np.ndarray):
        """Add trace data to all markers for interpolation."""
        for marker in self.markers.values():
            marker.add_trace_data(trace_id, frequency, x_data, y_data)

    def remove_trace_data(self, trace_id: str):
        """Remove trace data from all markers."""
        for marker in self.markers.values():
            marker.remove_trace_data(trace_id)

    def _update_marker_values(self):
        """Update marker value display."""
        if not self.markers:
            return

        # Get current marker values
        all_marker_data = {}
        for marker_id, marker in self.markers.items():
            if self.chart_type == "cartesian":
                marker_data = marker.get_interpolated_values()
            else:  # Smith chart
                marker_data = marker.find_nearest_points()
            all_marker_data[marker_id] = marker_data

        # Update table
        self._update_table_values(all_marker_data)

        # Emit signals for updated markers
        for marker_id, marker_data in all_marker_data.items():
            if marker_data:  # Only emit if we have data
                self.marker_moved.emit(marker_id, marker_data)

    def _update_table(self):
        """Update marker table structure."""
        # Count total rows needed (markers * traces)
        total_rows = 0
        for marker_id, marker in self.markers.items():
            total_rows += max(1, len(marker.traces))

        self.marker_table.setRowCount(total_rows)

        row = 0
        for marker_id, marker in self.markers.items():
            if not marker.traces:
                # Show marker with no trace data
                self.marker_table.setItem(row, 0, QTableWidgetItem(f"M{marker_id}"))
                for col in range(1, 7):
                    self.marker_table.setItem(row, col, QTableWidgetItem("--"))

                # Visibility checkbox
                checkbox = QCheckBox()
                checkbox.setChecked(marker.visible)
                checkbox.toggled.connect(lambda checked, mid=marker_id: self._on_visibility_changed(mid, checked))
                self.marker_table.setCellWidget(row, 7, checkbox)
                row += 1
            else:
                # Show marker for each trace
                for i, trace_id in enumerate(marker.traces.keys()):
                    if i == 0:
                        self.marker_table.setItem(row, 0, QTableWidgetItem(f"M{marker_id}"))
                    else:
                        self.marker_table.setItem(row, 0, QTableWidgetItem(""))

                    self.marker_table.setItem(row, 1, QTableWidgetItem(trace_id))

                    # Values will be filled by _update_table_values
                    for col in range(2, 7):
                        self.marker_table.setItem(row, col, QTableWidgetItem("--"))

                    # Visibility checkbox (only on first row for each marker)
                    if i == 0:
                        checkbox = QCheckBox()
                        checkbox.setChecked(marker.visible)
                        checkbox.toggled.connect(
                            lambda checked, mid=marker_id: self._on_visibility_changed(mid, checked))
                        self.marker_table.setCellWidget(row, 7, checkbox)
                    else:
                        self.marker_table.setItem(row, 7, QTableWidgetItem(""))

                    row += 1

    def _update_table_values(self, all_marker_data: Dict[str, Dict[str, MarkerData]]):
        """Update marker table with current values."""
        row = 0
        for marker_id in self.markers.keys():
            marker_data = all_marker_data.get(marker_id, {})

            if not marker_data:
                # Skip to next marker
                row += max(1, len(self.markers[marker_id].traces))
                continue

            for trace_id, data in marker_data.items():
                # Update frequency
                freq_text = f"{data.frequency/1e9:.3f} GHz" if data.frequency >= 1e9 else f"{data.frequency/1e6:.1f} MHz"
                self.marker_table.setItem(row, 2, QTableWidgetItem(freq_text))

                # Update magnitude (dB)
                mag_text = f"{data.magnitude_db:.2f} dB" if data.magnitude_db != -float('inf') else "-∞ dB"
                self.marker_table.setItem(row, 3, QTableWidgetItem(mag_text))

                # Update phase
                self.marker_table.setItem(row, 4, QTableWidgetItem(f"{data.phase_deg:.1f}°"))

                # Update real/imag
                self.marker_table.setItem(row, 5, QTableWidgetItem(f"{data.real:.3f}"))
                self.marker_table.setItem(row, 6, QTableWidgetItem(f"{data.imag:.3f}"))

                row += 1

    def _on_visibility_changed(self, marker_id: str, visible: bool):
        """Handle marker visibility change."""
        if marker_id in self.markers:
            self.markers[marker_id].set_visible(visible)
