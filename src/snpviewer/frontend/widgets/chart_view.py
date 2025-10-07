"""
Chart view widget using PyQtGraph for S-parameter visualization.

Provides interactive plotting capabilities for magnitude, phase, group delay,
and other RF parameter representations in Cartesian coordinates.
"""
from __future__ import annotations

import re
import csv
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

import pyqtgraph as pg
from pyqtgraph import LinearRegionItem, FillBetweenItem
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import QPoint, Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QContextMenuEvent, QFont
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMenu, QSizePolicy, QTabWidget,
                               QVBoxLayout, QWidget, QMessageBox, QColorDialog, QComboBox, QDialog,
                               QGroupBox, QPushButton, QSpinBox, QFileDialog, QInputDialog,
                               QHeaderView, QTableWidget, QTableWidgetItem, QCheckBox, QLineEdit)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.trace import Trace, TraceStyle, PortPath
from snpviewer.frontend.plotting.plot_pipelines import (
    PlotData, PlotType, prepare_group_delay_data, prepare_magnitude_data,
    prepare_phase_data, convert_s_to_phase, get_frequency_array, unwrap_phase)
from snpviewer.frontend.dialogs.linear_phase_error import LinearPhaseErrorDialog
from snpviewer.frontend.dialogs.common_dialogs import FontStylingWidget, PlotAreaPropertiesWidget


class ChartView(QWidget):
    """
    Chart view widget for displaying S-parameter data using PyQtGraph.

    Provides interactive plotting with zoom, pan, and cursor capabilities.
    Supports multiple traces with customizable styling and legends.

    Signals:
        trace_selected: Emitted when a trace is selected (trace_id)
        marker_added: Emitted when a marker is added (x, y, trace_id)
        view_changed: Emitted when the plot view is changed
    """

    trace_selected = Signal(str)  # trace_id
    marker_added = Signal(float, float, str)  # x, y, trace_id
    view_changed = Signal()
    add_traces_requested = Signal()  # Request to add traces from main window
    tab_title_changed = Signal(str)  # New tab title with type
    chart_title_changed = Signal(str)  # New chart title
    properties_changed = Signal()  # Emitted when any chart properties are modified
    create_new_chart_requested = Signal(dict)  # Request to create a new chart (e.g., linear phase error)

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the chart view."""
        super().__init__(parent)

        # Plot configuration
        self._plot_type = PlotType.MAGNITUDE
        self._x_axis_unit = 'Hz'  # PyQtGraph will automatically scale and add appropriate prefix
        self._y_axis_label = 'Magnitude (dB)'
        self._phase_unwrap = True  # Default to unwrapped phase

        # Separate titles for different purposes
        self._chart_title = "S-Parameter Plot"  # Plot widget title (user-editable, no restrictions)
        self._tab_title = ""  # Tab title (user-editable but includes plot type)

        # Font and color settings (stored to persist across label updates)
        self._chart_fonts = None
        self._chart_colors = None
        self._plot_area_settings = None

        # Data storage
        self._traces: Dict[str, Trace] = {}
        self._plot_items: Dict[str, pg.PlotDataItem] = {}
        self._datasets: Dict[str, Dataset] = {}

        # Limit lines storage
        self._limit_lines: Dict[str, Dict] = {}  # {line_id: {type, value, label, color, style, item}}
        self._next_limit_id = 1

        # Setup UI
        self._setup_ui()
        self._setup_plot_widget()
        self._setup_context_menu()

        # Configure plot appearance
        self._configure_plot_style()

    def _setup_ui(self) -> None:
        """Setup the basic UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create plot widget
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout.addWidget(self._plot_widget)

        # Add status bar for cursor coordinates
        self._status_layout = QHBoxLayout()
        self._cursor_label = QLabel("Ready")
        self._cursor_label.setStyleSheet(
            "QLabel { "
            "color: #333; "
            "font-size: 11px; "
            "font-family: 'Consolas', 'Courier New', monospace; "
            "padding: 2px 5px; "
            "background-color: #f0f0f0; "
            "border: 1px solid #ccc; "
            "border-radius: 3px; "
            "}"
        )
        self._status_layout.addWidget(self._cursor_label)
        self._status_layout.addStretch()

        layout.addLayout(self._status_layout)

    def _setup_plot_widget(self) -> None:
        """Configure the PyQtGraph plot widget."""
        # Get the plot item
        self._plot_item = self._plot_widget.getPlotItem()

        # Enable mouse interaction
        self._plot_widget.setMouseEnabled(x=True, y=True)

        # Add crosshair cursor
        crosshair_pen = pg.mkPen('#888', width=1, style=pg.QtCore.Qt.PenStyle.DashLine)
        self._crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen=crosshair_pen)
        self._crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen=crosshair_pen)
        self._plot_item.addItem(self._crosshair_v, ignoreBounds=True)
        self._plot_item.addItem(self._crosshair_h, ignoreBounds=True)

        # Connect mouse move events
        self._plot_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

        # Connect view change events
        self._plot_item.getViewBox().sigRangeChanged.connect(self._on_view_changed)

        # Set labels (with styling if available)
        self._set_axis_label_with_styling('bottom', 'Frequency', self._x_axis_unit)
        self._set_axis_label_with_styling('left', self._y_axis_label)
        self._set_title_with_styling(self._chart_title)

        # Add legend
        self._legend = self._plot_item.addLegend()

        # Set initial legend text color to black
        self._set_initial_legend_color()

    def _setup_context_menu(self) -> None:
        """Setup context menu actions."""
        self._context_menu = QMenu(self)

        # View actions
        self._auto_range_action = QAction("Auto Range", self)
        self._auto_range_action.triggered.connect(self._auto_range)
        self._context_menu.addAction(self._auto_range_action)

        self._context_menu.addSeparator()

        # Plot type actions
        plot_type_menu = self._context_menu.addMenu("Plot Type")

        self._magnitude_action = QAction("Magnitude (dB)", self)
        self._magnitude_action.setCheckable(True)
        self._magnitude_action.setChecked(True)
        self._magnitude_action.triggered.connect(lambda: self.set_plot_type(PlotType.MAGNITUDE))
        plot_type_menu.addAction(self._magnitude_action)

        self._phase_action = QAction("Phase (°)", self)
        self._phase_action.setCheckable(True)
        self._phase_action.triggered.connect(lambda: self.set_plot_type(PlotType.PHASE))
        plot_type_menu.addAction(self._phase_action)

        # Phase options submenu
        phase_options_menu = plot_type_menu.addMenu("Phase Options")

        self._phase_unwrap_action = QAction("Unwrap Phase", self)
        self._phase_unwrap_action.setCheckable(True)
        self._phase_unwrap_action.setChecked(True)
        self._phase_unwrap_action.triggered.connect(self._toggle_phase_unwrap)
        phase_options_menu.addAction(self._phase_unwrap_action)

        self._group_delay_action = QAction("Group Delay", self)
        self._group_delay_action.setCheckable(True)
        self._group_delay_action.triggered.connect(lambda: self.set_plot_type(PlotType.GROUP_DELAY))
        plot_type_menu.addAction(self._group_delay_action)

        self._context_menu.addSeparator()

        # Trace management actions
        self._add_traces_action = QAction("Add Traces...", self)
        self._add_traces_action.triggered.connect(self._show_add_traces_dialog)
        self._context_menu.addAction(self._add_traces_action)

        self._remove_all_traces_action = QAction("Clear All Traces", self)
        self._remove_all_traces_action.triggered.connect(self._remove_all_traces)
        self._context_menu.addAction(self._remove_all_traces_action)

        self._context_menu.addSeparator()

        # Limit lines actions
        limit_menu = self._context_menu.addMenu("Limit Lines")

        self._add_horizontal_limit_action = QAction("Horizontal Line...", self)
        self._add_horizontal_limit_action.triggered.connect(lambda: self._add_limit_line('horizontal'))
        limit_menu.addAction(self._add_horizontal_limit_action)

        self._add_vertical_limit_action = QAction("Vertical Line...", self)
        self._add_vertical_limit_action.triggered.connect(lambda: self._add_limit_line('vertical'))
        limit_menu.addAction(self._add_vertical_limit_action)

        limit_menu.addSeparator()

        self._add_frequency_range_action = QAction("Frequency Range...", self)
        self._add_frequency_range_action.triggered.connect(lambda: self._add_limit_range('horizontal'))
        limit_menu.addAction(self._add_frequency_range_action)

        self._add_value_range_action = QAction("Value Range...", self)
        self._add_value_range_action.triggered.connect(lambda: self._add_limit_range('vertical'))
        limit_menu.addAction(self._add_value_range_action)

        self._add_points_limit_action = QAction("Point-Based Limit...", self)
        self._add_points_limit_action.triggered.connect(self._add_points_limit)
        limit_menu.addAction(self._add_points_limit_action)

        limit_menu.addSeparator()

        # Limit line properties action (moved into limit lines submenu)
        self._limit_line_properties_action = QAction("Limit Line Properties...", self)
        self._limit_line_properties_action.triggered.connect(self._show_limit_line_selection_dialog)
        limit_menu.addAction(self._limit_line_properties_action)

        limit_menu.addSeparator()

        self._remove_all_limits_action = QAction("Clear All Limit Lines", self)
        self._remove_all_limits_action.triggered.connect(self._remove_all_limits)
        limit_menu.addAction(self._remove_all_limits_action)

        self._context_menu.addSeparator()

        # Trace properties action
        self._trace_properties_action = QAction("Trace Properties...", self)
        self._trace_properties_action.triggered.connect(self._show_trace_selection_dialog)
        self._context_menu.addAction(self._trace_properties_action)

        self._context_menu.addSeparator()

        # Chart management actions
        self._change_chart_title_action = QAction("Change Chart Title...", self)
        self._change_chart_title_action.triggered.connect(self._change_chart_title)
        self._context_menu.addAction(self._change_chart_title_action)

        self._change_tab_title_action = QAction("Change Tab Title...", self)
        self._change_tab_title_action.triggered.connect(self._change_tab_title)
        self._context_menu.addAction(self._change_tab_title_action)

        self._font_styling_action = QAction("Font Styling...", self)
        self._font_styling_action.triggered.connect(self._show_font_styling_dialog)
        self._context_menu.addAction(self._font_styling_action)

        self._plot_area_properties_action = QAction("Plot Area Properties...", self)
        self._plot_area_properties_action.triggered.connect(self._show_plot_area_properties_dialog)
        self._context_menu.addAction(self._plot_area_properties_action)

        self._context_menu.addSeparator()

        # Export actions
        self._export_image_action = QAction("Export as Image...", self)
        self._export_image_action.triggered.connect(self._export_image)
        self._context_menu.addAction(self._export_image_action)

        self._export_data_action = QAction("Export Data as CSV...", self)
        self._export_data_action.triggered.connect(self._export_data)
        self._context_menu.addAction(self._export_data_action)

    def _configure_plot_style(self) -> None:
        """Configure the visual appearance of the plot."""
        # Set background color
        self._plot_widget.setBackground('w')  # White background

        # Configure axes
        axis_pen = pg.mkPen('#333', width=1)
        self._plot_item.getAxis('left').setPen(axis_pen)
        self._plot_item.getAxis('bottom').setPen(axis_pen)

        # Configure grid
        self._plot_item.showGrid(x=True, y=True, alpha=0.3)

        # Set font for labels
        font = QFont()
        font.setPointSize(10)
        self._plot_item.getAxis('left').setStyle(tickFont=font)
        self._plot_item.getAxis('bottom').setStyle(tickFont=font)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Handle context menu events."""
        self._context_menu.exec(event.globalPos())

    def _show_trace_selection_dialog(self) -> None:
        """Show combined trace selection and properties dialog."""
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

        # Get the plot data labels (legend names) for each trace
        for trace_id, trace in self._traces.items():
            dataset = self._datasets.get(trace_id)
            if dataset:
                # Generate the same plot data to get the legend label
                plot_data = self._generate_plot_data(trace, dataset)
                if plot_data:
                    legend_name = plot_data.label
                    trace_combo.addItem(legend_name, trace_id)
                else:
                    # Fallback if plot data generation fails
                    fallback_name = trace.label if trace.label else trace_id
                    trace_combo.addItem(fallback_name, trace_id)
            else:
                # No dataset (e.g., linear phase error traces) - use trace label
                trace_name = trace.label if trace.label else trace_id
                trace_combo.addItem(trace_name, trace_id)

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
        style_combo.addItems(["solid", "dashed", "dotted", "dashdot"])

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

        apply_button.clicked.connect(apply_changes)
        ok_button.clicked.connect(lambda: (apply_changes(), dialog.accept()))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    def _show_limit_line_selection_dialog(self) -> None:
        """Show combined limit line selection and properties dialog."""
        if not self._limit_lines:
            QMessageBox.information(self, "No Limit Lines", "No limit lines are currently displayed in this chart.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Limit Line Properties")
        dialog.setModal(True)
        dialog.resize(380, 250)

        layout = QVBoxLayout(dialog)

        # Limit line selection
        line_layout = QHBoxLayout()
        line_label = QLabel("Limit Line:")
        line_combo = QComboBox()

        # Add limit lines to combo box (exclude range types as they don't support styling well)
        for line_id, line_data in self._limit_lines.items():
            line_type = line_data.get('type', 'unknown')

            # Skip range types as they use filled areas that don't work well with line styling
            if line_type.endswith('_range'):
                continue

            label = line_data.get('label', '')
            if label:
                display_name = f"{label} ({line_type})"
            else:
                display_name = f"{line_type.title()} Line ({line_id})"
            line_combo.addItem(display_name, line_id)

        line_layout.addWidget(line_label)
        line_layout.addWidget(line_combo)
        line_layout.addStretch()
        layout.addLayout(line_layout)

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
        style_combo.addItems(["solid", "dash", "dot", "dashdot"])

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

        # Update properties when limit line selection changes
        def update_properties():
            current_line_id = line_combo.currentData()
            if current_line_id and current_line_id in self._limit_lines:
                line_data = self._limit_lines[current_line_id]

                # Update color button - handle both single letter colors and hex colors
                color_str = line_data.get('color', 'r')
                if color_str == 'r':
                    current_color = QColor('red')
                elif color_str == 'g':
                    current_color = QColor('green')
                elif color_str == 'b':
                    current_color = QColor('blue')
                else:
                    current_color = QColor(color_str)

                if not current_color.isValid():
                    current_color = QColor('red')  # fallback

                color_button.setStyleSheet(f"background-color: {current_color.name()}; border: 1px solid black;")
                color_button.current_color = current_color.name()

                # Update style combo
                current_style = line_data.get('style', 'dash')
                style_combo.setCurrentText(current_style)

                # Update width spin (default to 2 if not stored)
                current_width = line_data.get('width', 2)
                width_spin.setValue(int(current_width))

        # Color button click handler
        def choose_color():
            current_line_id = line_combo.currentData()
            if current_line_id and current_line_id in self._limit_lines:
                line_data = self._limit_lines[current_line_id]
                color_str = line_data.get('color', 'r')

                # Convert single letter colors to proper color names
                if color_str == 'r':
                    current_color = QColor('red')
                elif color_str == 'g':
                    current_color = QColor('green')
                elif color_str == 'b':
                    current_color = QColor('blue')
                else:
                    current_color = QColor(color_str)

                if not current_color.isValid():
                    current_color = QColor('red')

                color = QColorDialog.getColor(current_color, dialog, "Choose Limit Line Color")
                if color.isValid():
                    color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
                    color_button.current_color = color.name()

        color_button.clicked.connect(choose_color)
        line_combo.currentTextChanged.connect(update_properties)

        # Initialize with first limit line
        if line_combo.count() > 0:
            update_properties()

        # Button handlers
        def apply_changes():
            current_line_id = line_combo.currentData()
            if current_line_id and current_line_id in self._limit_lines:
                line_data = self._limit_lines[current_line_id]

                # Update limit line properties
                line_data['color'] = getattr(color_button, 'current_color', line_data.get('color', 'r'))
                line_data['style'] = style_combo.currentText()
                line_data['width'] = float(width_spin.value())

                # Refresh the plot item with new style
                self._update_limit_line_style(current_line_id)

                # Emit signal to notify that properties changed
                self.properties_changed.emit()

        apply_button.clicked.connect(apply_changes)
        ok_button.clicked.connect(lambda: (apply_changes(), dialog.accept()))
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec()

    @Slot(object)
    def _on_mouse_moved(self, pos: QPoint) -> None:
        """Handle mouse movement for crosshair and status updates."""
        if self._plot_item.sceneBoundingRect().contains(pos):
            # Convert scene coordinates to data coordinates
            mouse_point = self._plot_item.getViewBox().mapSceneToView(pos)
            x, y = mouse_point.x(), mouse_point.y()

            # Update crosshairs
            self._crosshair_v.setPos(x)
            self._crosshair_h.setPos(y)

            # Format x value with appropriate units
            # PyQtGraph automatically scales Hz to kHz, MHz, GHz with SI prefixes
            x_formatted = self._format_frequency_value(x)

            # Format y value based on plot type
            y_formatted = self._format_y_value(y)

            # Update status bar with formatted values
            self._cursor_label.setText(f"X: {x_formatted} | Y: {y_formatted}")
        else:
            # Hide crosshairs when outside plot area
            self._crosshair_v.setPos(float('inf'))
            self._crosshair_h.setPos(float('inf'))
            self._cursor_label.setText("Ready")

    def _format_frequency_value(self, freq: float) -> str:
        """Format frequency value with appropriate SI prefix."""
        abs_freq = abs(freq)
        if abs_freq >= 1e9:
            return f"{freq/1e9:.3f} GHz"
        elif abs_freq >= 1e6:
            return f"{freq/1e6:.3f} MHz"
        elif abs_freq >= 1e3:
            return f"{freq/1e3:.3f} kHz"
        else:
            return f"{freq:.3f} Hz"

    def _format_y_value(self, y: float) -> str:
        """Format y value based on current plot type."""
        if self._plot_type == PlotType.MAGNITUDE:
            return f"{y:.3f} dB"
        elif self._plot_type == PlotType.PHASE:
            return f"{y:.2f}°"
        elif self._plot_type == PlotType.GROUP_DELAY:
            return f"{y:.3f} ns"
        else:
            return f"{y:.3f}"

    def _on_view_changed(self) -> None:
        """Handle view change events."""
        self.view_changed.emit()

    def set_plot_type(self, plot_type: PlotType) -> None:
        """
        Set the plot type and refresh all traces.

        Args:
            plot_type: The new plot type to display
        """
        if plot_type == self._plot_type:
            return

        self._plot_type = plot_type

        # Update action checkboxes
        self._magnitude_action.setChecked(plot_type == PlotType.MAGNITUDE)
        self._phase_action.setChecked(plot_type == PlotType.PHASE)
        self._group_delay_action.setChecked(plot_type == PlotType.GROUP_DELAY)

        # Update axis labels
        if plot_type == PlotType.MAGNITUDE:
            self._y_axis_label = 'Magnitude (dB)'
        elif plot_type == PlotType.PHASE or plot_type == PlotType.LINEAR_PHASE_ERROR:
            self._y_axis_label = 'Phase (°)'
        elif plot_type == PlotType.GROUP_DELAY:
            self._y_axis_label = 'Group Delay (ns)'

        self._set_axis_label_with_styling('left', self._y_axis_label)

        # Update tab title to reflect new plot type
        self._update_tab_title()

        # Refresh all traces
        self._refresh_all_traces()

    def add_trace(self, trace_id: str, trace: Trace, dataset: Dataset) -> None:
        """
        Add a new trace to the chart.

        Args:
            trace_id: Unique identifier for the trace
            trace: Trace object with plotting parameters
            dataset: Dataset containing the S-parameter data
        """
        self._traces[trace_id] = trace
        self._datasets[trace_id] = dataset

        # Generate plot data
        plot_data = self._generate_plot_data(trace, dataset)

        if plot_data is not None:
            # Create PyQtGraph plot item
            pen = pg.mkPen(
                color=trace.style.color,
                width=trace.style.line_width,
                style=self._get_pen_style(trace.style.line_style)
            )

            symbol = self._get_symbol(trace.style.marker_style)
            symbol_size = trace.style.marker_size

            plot_item = self._plot_item.plot(
                plot_data.x, plot_data.y,
                pen=pen,
                symbol=symbol,
                symbolSize=symbol_size,
                name=plot_data.label
            )

            # Set visibility
            plot_item.setVisible(trace.style.visible)

            # Connect double-click signal for trace properties
            plot_item.sigClicked.connect(lambda *args, tid=trace_id: self._on_trace_clicked(tid, plot_item))

            # Store reference
            self._plot_items[trace_id] = plot_item

            # Apply legend styling if available
            self._apply_legend_styling()

    def remove_trace(self, trace_id: str) -> None:
        """
        Remove a trace from the chart.

        Args:
            trace_id: ID of the trace to remove
        """
        if trace_id in self._plot_items:
            self._plot_item.removeItem(self._plot_items[trace_id])
            del self._plot_items[trace_id]

        if trace_id in self._traces:
            del self._traces[trace_id]

        if trace_id in self._datasets:
            del self._datasets[trace_id]

    def remove_traces_by_dataset(self, dataset_id: str) -> int:
        """
        Remove all traces from a specific dataset.

        Args:
            dataset_id: ID of the dataset whose traces should be removed

        Returns:
            Number of traces removed
        """
        traces_to_remove = []

        # Find all traces that belong to this dataset
        for trace_id, dataset in self._datasets.items():
            if dataset.id == dataset_id:
                traces_to_remove.append(trace_id)

        # Remove the traces
        for trace_id in traces_to_remove:
            self.remove_trace(trace_id)

        return len(traces_to_remove)

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

        # Update the dataset file_name for all traces from this dataset
        for trace_id, dataset in self._datasets.items():
            if dataset.id == dataset_id:
                # Update the dataset's display_name
                dataset.display_name = new_name

                # Refresh the legend entry for this trace
                if trace_id in self._plot_items and trace_id in self._traces:
                    plot_item = self._plot_items[trace_id]
                    trace = self._traces[trace_id]

                    # Regenerate plot data to get the updated label
                    plot_data = self._generate_plot_data(trace, dataset)

                    if plot_data:
                        # Remove the old legend entry
                        try:
                            self._legend.removeItem(plot_item)
                        except Exception:
                            pass  # Item might not be in legend

                        # Add the updated legend entry with new label
                        self._legend.addItem(plot_item, plot_data.label)

                        updated = True

        return updated

    def update_trace_style(self, trace_id: str, style: TraceStyle) -> None:
        """
        Update the visual style of a trace.

        Args:
            trace_id: ID of the trace to update
            style: New style settings
        """
        if trace_id not in self._plot_items:
            return

        plot_item = self._plot_items[trace_id]
        trace = self._traces[trace_id]

        # Update style in trace object
        trace.style = style

        # Update plot item appearance
        pen = pg.mkPen(
            color=style.color,
            width=style.line_width,
            style=self._get_pen_style(style.line_style)
        )
        plot_item.setPen(pen)

        symbol = self._get_symbol(style.marker_style)
        plot_item.setSymbol(symbol)
        plot_item.setSymbolSize(style.marker_size)
        plot_item.setVisible(style.visible)

    def _generate_plot_data(self, trace: Trace, dataset: Dataset) -> Optional[PlotData]:
        """
        Generate plot data for a trace based on current plot type.

        Args:
            trace: Trace configuration
            dataset: Source dataset

        Returns:
            PlotData object or None if generation fails
        """
        try:
            if self._plot_type == PlotType.MAGNITUDE:
                return prepare_magnitude_data(trace, dataset)
            elif self._plot_type == PlotType.PHASE:
                return prepare_phase_data(trace, dataset, unwrap=self._phase_unwrap)
            elif self._plot_type == PlotType.GROUP_DELAY:
                return prepare_group_delay_data(trace, dataset)
            else:
                return None
        except Exception as e:
            print(f"Warning: Failed to generate plot data for trace {trace.id}: {e}")
            return None

    def _refresh_all_traces(self) -> None:
        """Refresh all traces with current plot type."""
        for trace_id in list(self._traces.keys()):
            trace = self._traces[trace_id]
            dataset = self._datasets[trace_id]

            # Remove old plot item
            if trace_id in self._plot_items:
                self._plot_item.removeItem(self._plot_items[trace_id])
                del self._plot_items[trace_id]

            # Re-add with new plot type
            self.add_trace(trace_id, trace, dataset)

    def _get_pen_style(self, line_style: str) -> pg.QtCore.Qt.PenStyle:
        """Convert line style string to PyQtGraph pen style."""
        style_map = {
            'solid': pg.QtCore.Qt.PenStyle.SolidLine,
            'dashed': pg.QtCore.Qt.PenStyle.DashLine,
            'dotted': pg.QtCore.Qt.PenStyle.DotLine,
            'dashdot': pg.QtCore.Qt.PenStyle.DashDotLine
        }
        return style_map.get(line_style, pg.QtCore.Qt.PenStyle.SolidLine)

    def _get_symbol(self, marker_style: str) -> Optional[str]:
        """Convert marker style string to PyQtGraph symbol."""
        symbol_map = {
            'none': None,
            'circle': 'o',
            'square': 's',
            'triangle': 't',
            'diamond': 'd',
            'plus': '+'
        }
        return symbol_map.get(marker_style, None)

    def _auto_range(self) -> None:
        """Auto-range the plot to fit all data."""
        self._plot_item.getViewBox().autoRange()

    def _export_image(self) -> None:
        """Export the current plot as an image."""

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Chart as Image",
            "chart.png",
            "PNG Files (*.png);;JPEG Files (*.jpg);;PDF Files (*.pdf)"
        )

        if file_path:
            # Export the plot as an image using pyqtgraph's ImageExporter
            exporter = ImageExporter(self._plot_item)
            exporter.export(file_path)

    def _export_data(self) -> None:
        """Export the current plot data as CSV."""

        if not self._traces:
            QMessageBox.information(self, "No Data", "No traces to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Data as CSV",
            "chart_data.csv",
            "CSV Files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)

                    # Write header
                    header = ['Frequency']
                    for trace_id in self._traces:
                        header.append(f"{trace_id}_{self._plot_type.value}")
                    writer.writerow(header)

                    # Collect all data
                    all_data = {}
                    for trace_id in self._traces:
                        trace = self._traces[trace_id]
                        dataset = self._datasets[trace_id]
                        plot_data = self._generate_plot_data(trace, dataset)
                        if plot_data:
                            all_data[trace_id] = plot_data

                    # Write data rows
                    if all_data:
                        # Use the first trace's frequency points as reference
                        first_trace = next(iter(all_data.values()))
                        for i in range(len(first_trace.x)):
                            row = [first_trace.x[i]]
                            for trace_id in self._traces:
                                if trace_id in all_data and i < len(all_data[trace_id].y):
                                    row.append(all_data[trace_id].y[i])
                                else:
                                    row.append('')
                            writer.writerow(row)

                QMessageBox.information(self, "Export Complete", f"Data exported to {file_path}")

            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export data: {str(e)}")

    def clear(self) -> None:
        """Clear all traces from the chart."""
        for trace_id in list(self._traces.keys()):
            self.remove_trace(trace_id)

        # Clear legend
        self._legend.clear()

    def get_view_range(self) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """
        Get the current view range.

        Returns:
            ((x_min, x_max), (y_min, y_max))
        """
        view_box = self._plot_item.getViewBox()
        ranges = view_box.viewRange()
        return ((ranges[0][0], ranges[0][1]), (ranges[1][0], ranges[1][1]))

    def set_view_range(self, x_range: Tuple[float, float], y_range: Tuple[float, float]) -> None:
        """
        Set the view range.

        Args:
            x_range: (x_min, x_max)
            y_range: (y_min, y_max)
        """
        self._plot_item.getViewBox().setRange(xRange=x_range, yRange=y_range)

    def set_chart_title(self, title: str) -> None:
        """Set the chart title (plot widget title)."""
        self._chart_title = title
        self._set_title_with_styling(title)
        # Emit signal to notify that chart title changed
        self.chart_title_changed.emit(title)

    def get_chart_title(self) -> str:
        """Get the current chart title."""
        return self._chart_title

    def set_tab_title(self, title: str) -> None:
        """Set the tab title (user-defined but includes plot type)."""
        self._tab_title = title
        self._update_tab_title()

    def get_tab_title(self) -> str:
        """Get the current tab title."""
        return self._get_current_tab_title()

    def set_chart_tab_title(self, tab_title: str) -> None:
        """Set the chart tab title (typically from filename)."""

        self._tab_title = tab_title
        self._update_tab_title()

    def _get_plot_type_name(self) -> str:
        """Get the current plot type name."""
        return {
            PlotType.MAGNITUDE: "Magnitude",
            PlotType.PHASE: "Phase",
            PlotType.GROUP_DELAY: "Group Delay",
            PlotType.LINEAR_PHASE_ERROR: "Linear Phase Error"
        }.get(self._plot_type, "Unknown")

    def _get_current_tab_title(self) -> str:
        """Get the current tab title including plot type."""
        plot_type_name = self._get_plot_type_name()

        if self._tab_title:
            # User has set a custom tab title, include plot type
            return f"{self._tab_title} ({plot_type_name})"
        else:
            return f"Chart ({plot_type_name})"

    def _update_tab_title(self) -> None:
        """Update the tab title and emit signal for tab to be updated."""
        new_tab_title = self._get_current_tab_title()
        self.tab_title_changed.emit(new_tab_title)

    def _change_chart_title(self) -> None:
        """Show dialog to change the chart title (plot widget title)."""

        current_title = self._chart_title or "S-Parameter Plot"
        new_title, ok = QInputDialog.getText(
            self,
            "Change Chart Title",
            "Enter new chart title:",
            text=current_title
        )

        if ok and new_title.strip():
            self.set_chart_title(new_title.strip())

    def _change_tab_title(self) -> None:
        """Show dialog to change the tab title."""

        current_name = self._tab_title or "Chart"
        new_name, ok = QInputDialog.getText(
            self,
            "Change Tab Title",
            "Enter new tab title:\n(Plot type will be added automatically)",
            text=current_name
        )

        if ok and new_name.strip():
            self.set_tab_title(new_name.strip())

    def _toggle_phase_unwrap(self) -> None:
        """Toggle phase unwrap option and refresh if in phase mode."""
        self._phase_unwrap = self._phase_unwrap_action.isChecked()

        # If we're currently displaying phase, refresh all traces
        if self._plot_type == PlotType.PHASE:
            self._refresh_all_traces()

    def _show_linear_phase_error_dialog(self) -> None:
        """Show the linear phase error analysis dialog."""
        if not self._datasets:
            QMessageBox.information(
                self,
                "No Data",
                "No datasets are available. Please load data first."
            )
            return

        # Create and show the dialog
        dialog = LinearPhaseErrorDialog(self._datasets, parent=self)
        # Connect signal to handle chart creation
        dialog.create_chart_requested.connect(self._handle_linear_phase_error_chart_request)
        dialog.exec()

    def _handle_linear_phase_error_chart_request(self, config: dict) -> None:
        """Handle request to create a linear phase error chart."""
        # Emit signal to request the main app to create a new chart
        self.create_new_chart_requested.emit(config)

    def create_linear_phase_error_plot(self, config: Dict[str, Any], dataset: Optional[Dataset] = None) -> None:
        """
        Create a linear phase error plot from configuration.

        Args:
            config: Configuration dictionary containing:
                - slope: Fit slope
                - intercept: Fit intercept
                - freq_start, freq_end: Frequency range limits
                - dataset_id: Dataset identifier
                - i_port, j_port: Port indices
                - Optional: frequency, error (will be recalculated if missing)
            dataset: Optional dataset to use for recalculation
        """

        dataset_id = config.get('dataset_id', '')
        i_port = config.get('i_port', 0)
        j_port = config.get('j_port', 0)

        # Get frequency and error arrays
        # If they're in the config (newly created chart), use them
        # If they're missing (loaded from file), recalculate them
        if 'frequency' in config and 'error' in config:
            freq = config['frequency']
            error = config['error']
        else:
            # Need to recalculate from the dataset
            # Use provided dataset, or find it in self._datasets
            if dataset is None:
                # Find the dataset in self._datasets by matching dataset_id
                for trace_id, ds in self._datasets.items():
                    if hasattr(ds, 'id') and ds.id == dataset_id:
                        dataset = ds
                        break

            if dataset is None:
                print(f"Warning: Cannot recalculate linear phase error - dataset {dataset_id} not found")
                return

            # Recalculate frequency and error from parameters
            freq, error = self._recalculate_linear_phase_error(config, dataset)

            # Store recalculated arrays in config for later use
            config['frequency'] = freq
            config['error'] = error

        trace_id = config.get('trace_id', '')
        i_port = config.get('i_port', 0)
        j_port = config.get('j_port', 0)

        # Store the configuration
        self._linear_phase_error_config = config
        self._plot_type = PlotType.LINEAR_PHASE_ERROR

        # Clear existing items
        self._plot_item.clear()
        self._legend.clear()
        self._traces.clear()
        self._plot_items.clear()

        # Get or create trace style from config
        if 'trace_style' in config:
            saved_style = config['trace_style']
            # Check if it's already a TraceStyle object or needs to be created from dict
            if isinstance(saved_style, TraceStyle):
                style = saved_style
            elif isinstance(saved_style, dict):
                # Reconstruct TraceStyle from dictionary
                style = TraceStyle(
                    color=saved_style.get('color', '#00AA00'),
                    line_width=saved_style.get('line_width', 2),
                    line_style=saved_style.get('line_style', 'solid'),
                    marker_style=saved_style.get('marker_style', 'none'),
                    marker_size=saved_style.get('marker_size', 8),
                    visible=saved_style.get('visible', True)
                )
            else:
                # Fallback to default
                style = TraceStyle(
                    color='#00AA00',
                    line_width=2,
                    line_style='solid',
                    marker_style='none'
                )
        else:
            # Default style for linear phase error
            style = TraceStyle(
                color='#00AA00',  # Green
                line_width=2,
                line_style='solid',
                marker_style='none'
            )

        # Create a Trace object for the linear phase error plot
        trace_label = f"{config.get('dataset_name', 'Unknown')}: {config.get('sparam', 'S11')} Linear Phase Error"

        trace = Trace(
            id=trace_id,
            dataset_id=dataset_id,
            domain="S",
            metric="linear_phase_error",
            port_path=PortPath(i=i_port+1, j=j_port+1),
            style=style,
            label=trace_label
        )

        # Store trace
        self._traces[trace_id] = trace
        # Plot error with trace style
        pen_error = pg.mkPen(
            color=style.color,
            width=style.line_width,
            style=self._get_pen_style(style.line_style)
        )

        symbol = self._get_symbol(style.marker_style)
        symbol_size = style.marker_size

        plot_item = self._plot_item.plot(
            freq, error,
            pen=pen_error,
            symbol=symbol,
            symbolSize=symbol_size,
            name=f"{config['dataset_name']}: {config['sparam']}"
        )

        # Make plot item clickable for trace properties
        plot_item.curve.setClickable(True, width=10)  # width is the click tolerance in pixels

        # Connect click signal for trace properties
        # Note: sigClicked signal passes event/item but we ignore it and use captured trace_id
        plot_item.sigClicked.connect(lambda *args, tid=trace_id: self._on_trace_clicked(tid, plot_item))

        # Store plot item reference
        self._plot_items[trace_id] = plot_item

        # # Add zero reference line
        # pen_zero = pg.mkPen(color='k', width=1, style=Qt.PenStyle.DashLine)
        # self._plot_item.plot([freq[0], freq[-1]], [0, 0], pen=pen_zero, name='Zero Reference')

        # Set axis labels
        self._y_axis_label = 'Phase Error (°)'
        self._set_axis_label_with_styling('left', self._y_axis_label)
        self._set_axis_label_with_styling('bottom', 'Frequency', self._x_axis_unit)

        # Set title with equation
        title = f"{config.get('title', 'Linear Phase Error')}"
        self.set_chart_title(title)

        # Fix view range to specified frequency range
        freq_start = config.get('freq_start', freq[0])
        freq_end = config.get('freq_end', freq[-1])
        self._plot_item.setXRange(freq_start, freq_end, padding=0.02)
        self._plot_item.enableAutoRange(axis='y')

        # Apply legend styling if available
        self._apply_legend_styling()

    def get_existing_trace_ids(self) -> List[str]:
        """Get list of existing trace IDs in this chart."""
        return list(self._traces.keys())

    def get_existing_traces(self) -> Dict[str, Tuple[str, Trace, Dataset]]:
        """Get dictionary of existing traces with their details."""
        existing_traces = {}
        for trace_id, trace in self._traces.items():
            # Check if this trace has a dataset (regular traces do, linear phase error doesn't)
            if trace_id in self._datasets:
                dataset = self._datasets[trace_id]
                # Use dataset.id as the authoritative dataset ID rather than trace.dataset_id
                # to ensure consistency when matching in dialogs
                existing_traces[trace_id] = (dataset.id, trace, dataset)
            else:
                # For traces without datasets (e.g., linear phase error), use trace's dataset_id
                # and None for dataset object
                existing_traces[trace_id] = (trace.dataset_id, trace, None)
        return existing_traces

    def _show_add_traces_dialog(self) -> None:
        """Show dialog to add new traces to the chart."""
        # We need to signal the main window to show the add traces dialog
        # since the chart widget doesn't have direct access to all datasets
        self.add_traces_requested.emit()

    def _remove_all_traces(self) -> None:
        """Remove all traces from the chart."""

        if not self._traces:
            QMessageBox.information(self, "No Traces", "No traces to remove.")
            return

        reply = QMessageBox.question(self, "Clear Traces",
                                     "Are you sure you want to remove all traces from this chart?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # Remove all traces
            trace_ids = list(self._traces.keys())
            for trace_id in trace_ids:
                self.remove_trace(trace_id)

    def _add_limit_line(self, line_type: str) -> None:
        """Add a limit line to the chart."""

        # Get the appropriate prompt based on line type
        if line_type == 'horizontal':
            prompt = "Enter limit value (Y-axis):"
            if self._plot_type == PlotType.MAGNITUDE:
                title = "Add Horizontal Limit Line (dB)"
            elif self._plot_type == PlotType.PHASE:
                title = "Add Horizontal Limit Line (degrees)"
            else:
                title = "Add Horizontal Limit Line"
        else:  # vertical
            prompt = "Enter limit value (X-axis frequency in Hz):"
            title = "Add Vertical Limit Line"

        # Get value from user with text input for flexibility
        value_str, ok = QInputDialog.getText(self, title, prompt + "\n(Supports: 2.1e9, 2.1G, etc.)")
        if not ok or not value_str.strip():
            return

        # Parse the value with enhanced format support
        try:
            if line_type == 'vertical':
                # For frequency, support suffixes
                value = self._parse_frequency(value_str.strip())
            else:
                # For Y values, just parse as float
                value = float(value_str.strip())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Value", f"Could not parse '{value_str}': {str(e)}")
            return

        # Get label from user
        label, ok = QInputDialog.getText(self, "Limit Line Label",
                                         "Enter label for limit line (optional):")
        if not ok:
            label = ""

        # Create limit line
        self._create_limit_line(line_type, value, label)

    def _create_limit_line(self, line_type: str, value: float, label: str = "") -> str:
        """Create and add a limit line to the chart."""
        # Generate unique ID
        line_id = f"limit_{self._next_limit_id}"
        self._next_limit_id += 1

        # Create the line item with default styling (will be updated if needed)
        default_pen = pg.mkPen('r', width=2, style=Qt.PenStyle.DashLine)
        if line_type == 'horizontal':
            line_item = pg.InfiniteLine(
                pos=value,
                angle=0,  # horizontal
                pen=default_pen,
                movable=True
            )
        else:  # vertical
            line_item = pg.InfiniteLine(
                pos=value,
                angle=90,  # vertical
                pen=default_pen,
                movable=True
            )

        # Add label if provided
        if label:
            # Create a text item for the label
            label_item = pg.TextItem(text=label, color='r', anchor=(0, 1))
            if line_type == 'horizontal':
                # Position label within the current view range, not at x=0
                view_box = self._plot_item.getViewBox()
                x_range = view_box.viewRange()[0]  # [x_min, x_max]
                # Position at 10% from the left of the current view
                label_x = x_range[0] + 0.1 * (x_range[1] - x_range[0])
                label_item.setPos(label_x, value)
            else:  # vertical
                label_item.setPos(value, 0)
            self._plot_item.addItem(label_item)

        # Add to plot
        self._plot_item.addItem(line_item)

        # Store limit line data
        self._limit_lines[line_id] = {
            'type': line_type,
            'value': value,
            'label': label,
            'color': 'r',
            'style': 'dash',
            'width': 2,
            'item': line_item
        }

        # Apply initial styling to make sure the line appears with correct default style
        self._update_limit_line_style(line_id)

        return line_id

    def _remove_all_limits(self) -> None:
        """Remove all limit lines from the chart."""

        if not self._limit_lines:
            QMessageBox.information(self, "No Limit Lines", "No limit lines to remove.")
            return

        reply = QMessageBox.question(self, "Clear Limit Lines",
                                     "Are you sure you want to remove all limit lines from this chart?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            # Remove all limit lines
            for line_data in self._limit_lines.values():
                # Only remove item if it's a real graphics item (not a dict)
                if 'item' in line_data and hasattr(line_data['item'], 'zValue'):
                    self._plot_item.removeItem(line_data['item'])
                # Also remove label item if it exists
                if 'label_item' in line_data and line_data['label_item']:
                    self._plot_item.removeItem(line_data['label_item'])
                # Also remove line items for vertical ranges
                if 'line1' in line_data and line_data['line1']:
                    self._plot_item.removeItem(line_data['line1'])
                if 'line2' in line_data and line_data['line2']:
                    self._plot_item.removeItem(line_data['line2'])
            self._limit_lines.clear()

    def remove_limit_line(self, line_id: str) -> None:
        """Remove a specific limit line."""
        if line_id in self._limit_lines:
            line_data = self._limit_lines[line_id]

            # Only remove item if it's a real graphics item (not a dict)
            if 'item' in line_data and hasattr(line_data['item'], 'zValue'):
                self._plot_item.removeItem(line_data['item'])

            # Also remove label item if it exists
            if 'label_item' in line_data and line_data['label_item']:
                self._plot_item.removeItem(line_data['label_item'])
            # Also remove line items for vertical ranges
            if 'line1' in line_data and line_data['line1']:
                self._plot_item.removeItem(line_data['line1'])
            if 'line2' in line_data and line_data['line2']:
                self._plot_item.removeItem(line_data['line2'])
            # Remove polygon item for complex vertical ranges
            if 'polygon' in line_data and line_data['polygon']:
                self._plot_item.removeItem(line_data['polygon'])
            del self._limit_lines[line_id]

    def get_limit_lines(self) -> Dict[str, Dict]:
        """Get all limit lines data for serialization."""
        limit_data = {}
        for line_id, line_info in self._limit_lines.items():
            limit_type = line_info['type']

            if limit_type in ['horizontal', 'vertical']:
                # Get current position (in case user moved the line)
                current_pos = line_info['item'].getPos()
                if limit_type == 'horizontal':
                    current_value = current_pos[1]
                else:
                    current_value = current_pos[0]

                limit_data[line_id] = {
                    'type': limit_type,
                    'value': current_value,
                    'label': line_info['label'],
                    'color': line_info['color'],
                    'style': line_info['style'],
                    'width': line_info.get('width', 2)
                }
            elif limit_type.endswith('_range'):
                # Range types store min/max values
                limit_data[line_id] = {
                    'type': limit_type,
                    'min_value': line_info['min_value'],
                    'max_value': line_info['max_value'],
                    'label': line_info['label'],
                    'color': line_info['color'],
                    'style': line_info['style'],
                    'width': line_info.get('width', 2)
                }
            elif limit_type == 'points':
                # Points type stores the point list
                limit_data[line_id] = {
                    'type': limit_type,
                    'points': line_info['points'],
                    'label': line_info['label'],
                    'color': line_info['color'],
                    'style': line_info['style'],
                    'width': line_info.get('width', 2),
                    'show_chart_label': line_info.get('show_chart_label', False),
                    'show_legend': line_info.get('show_legend', True)
                }

        return limit_data

    def restore_limit_lines(self, limit_data: Dict[str, Dict]) -> None:
        """Restore limit lines from saved data."""
        for line_id, line_info in limit_data.items():
            limit_type = line_info['type']

            if limit_type in ['horizontal', 'vertical']:
                # Restore simple line limits
                self._create_limit_line(
                    limit_type,
                    line_info['value'],
                    line_info.get('label', '')
                )
            elif limit_type.endswith('_range'):
                # Restore range limits
                range_base_type = limit_type.replace('_range', '')
                self._create_limit_range(
                    range_base_type,
                    line_info['min_value'],
                    line_info['max_value'],
                    line_info.get('label', '')
                )
            elif limit_type == 'points':
                # Restore point-based limits
                self._create_points_limit(
                    line_info['points'],
                    line_info.get('label', ''),
                    line_info.get('show_chart_label', False),
                    line_info.get('show_legend', True)
                )

            # Update the stored ID to match saved data (only if ID remapping is needed)
            if line_id not in self._limit_lines:
                # Find the last created line and update its ID
                # Need to handle different prefixes based on limit type
                if limit_type == 'points':
                    last_id = f"points_{self._next_limit_id - 1}"
                elif limit_type in ['frequency_range', 'value_range']:
                    last_id = f"range_{self._next_limit_id - 1}"
                else:
                    last_id = f"limit_{self._next_limit_id - 1}"

                if last_id in self._limit_lines:
                    self._limit_lines[line_id] = self._limit_lines.pop(last_id)

            # Restore saved style properties (always do this, regardless of ID remapping)
            if line_id in self._limit_lines:
                restored_line = self._limit_lines[line_id]
                restored_line['color'] = line_info.get('color', 'r')
                restored_line['style'] = line_info.get('style', 'dash')
                restored_line['width'] = line_info.get('width', 2)

                # Apply the restored style to the visual elements
                self._update_limit_line_style(line_id)

    def get_chart_fonts(self) -> Dict[str, Any]:
        """Get chart font settings for serialization."""
        if not hasattr(self, '_chart_fonts') or not self._chart_fonts:
            return {}

        # Convert QFont objects to serializable dictionaries
        serializable_fonts = {}
        for key, font in self._chart_fonts.items():
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
        """Get chart color settings for serialization."""
        if not hasattr(self, '_chart_colors') or not self._chart_colors:
            return {}
        return self._chart_colors.copy()

    def restore_chart_fonts(self, font_data: Dict[str, Any]) -> None:
        """Restore chart font settings from saved data."""
        if not font_data:
            return

        self._chart_fonts = {}
        for key, font_info in font_data.items():
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

                    # Handle weight - use the saved weight value directly
                    # Don't use both setWeight and setBold as they conflict
                    if 'weight' in font_info:
                        weight = font_info['weight']
                        if isinstance(weight, int):
                            font.setWeight(QFont.Weight(weight))
                        else:
                            font.setWeight(weight)
                    elif font_info.get('bold', False):
                        # If no weight but bold is True, set bold weight
                        font.setWeight(QFont.Weight.Bold)

                    self._chart_fonts[key] = font
                else:
                    self._chart_fonts[key] = font_info
            except Exception as e:
                print(f"Warning: Could not restore font for {key}: {e}")
                # Use default font as fallback
                self._chart_fonts[key] = QFont("Arial", 10)

        # Apply the restored fonts
        try:
            self._apply_all_styling()
        except Exception as e:
            print(f"Warning: Could not apply restored fonts: {e}")

    def restore_chart_colors(self, color_data: Dict[str, str]) -> None:
        """Restore chart color settings from saved data."""
        if not color_data:
            return
        self._chart_colors = color_data.copy()

        # Apply the restored colors
        try:
            self._apply_all_styling()
        except Exception as e:
            print(f"Warning: Could not apply restored colors: {e}")

    def get_plot_area_settings(self) -> Dict[str, Any]:
        """Get plot area settings for serialization."""
        if not self._plot_area_settings:
            return {}
        return self._plot_area_settings.copy()

    def restore_plot_area_settings(self, settings_data: Dict[str, Any]) -> None:
        """Restore plot area settings from saved data."""
        if not settings_data:
            return

        self._plot_area_settings = settings_data.copy()

        # Apply the restored settings
        try:
            self._apply_plot_area_settings(self._plot_area_settings)
        except Exception as e:
            print(f"Warning: Could not apply restored plot area settings: {e}")

    def get_phase_unwrap(self) -> bool:
        """Get phase unwrap setting for serialization."""
        return self._phase_unwrap

    def restore_phase_unwrap(self, unwrap: bool) -> None:
        """Restore phase unwrap setting from saved data."""
        self._phase_unwrap = unwrap
        self._phase_unwrap_action.setChecked(unwrap)

        # If currently in phase mode, refresh
        if self._plot_type == PlotType.PHASE:
            self._refresh_all_traces()

    def _recalculate_linear_phase_error(self, config: Dict[str, Any], dataset: Dataset) -> Tuple[Any, Any]:
        """
        Recalculate frequency and error arrays from saved parameters and dataset.

        Args:
            config: Configuration containing slope, intercept, freq_start, freq_end, i_port, j_port
            dataset: Dataset containing the S-parameter data

        Returns:
            Tuple of (frequency_array, error_array)
        """
        # Extract parameters
        slope = config['slope']
        intercept = config['intercept']
        freq_start = config['freq_start']
        freq_end = config['freq_end']
        i_port = config['i_port']
        j_port = config['j_port']

        # Get frequency array
        freq = get_frequency_array(dataset, unit='Hz')

        # Get S-parameter
        s_param = dataset.s_params[:, i_port, j_port]

        # Apply frequency range filter
        mask = (freq >= freq_start) & (freq <= freq_end)
        freq_filtered = freq[mask]
        s_param_filtered = s_param[mask]

        # Compute unwrapped phase in degrees
        phase = convert_s_to_phase(s_param_filtered, degrees=True)
        phase = unwrap_phase(phase)

        # Compute linear fit line
        phase_fit = slope * freq_filtered + intercept

        # Compute error
        error = phase - phase_fit

        return freq_filtered, error

    def get_linear_phase_error_config(self) -> Optional[Dict[str, Any]]:
        """
        Get linear phase error configuration for serialization.

        Only saves the mathematical parameters (slope, intercept, frequency range, ports)
        and NOT the frequency/error arrays, which will be recalculated on load.
        """
        if not hasattr(self, '_linear_phase_error_config'):
            return None

        # Make a copy of the config
        config = self._linear_phase_error_config.copy()

        # Remove frequency and error arrays - these will be recalculated on load
        config.pop('frequency', None)
        config.pop('error', None)
        config.pop('phase', None)  # Also remove intermediate phase data if present

        # Update with current trace style if trace exists
        trace_id = config.get('trace_id', '')
        if trace_id and trace_id in self._traces:
            trace = self._traces[trace_id]
            # Store trace style as dict for JSON serialization
            config['trace_style'] = trace.style.to_dict()

        return config

    def restore_linear_phase_error_config(self, config: Dict[str, Any], dataset: Optional[Dataset] = None) -> None:
        """
        Restore linear phase error configuration from saved data.

        Args:
            config: Configuration dictionary with parameters
            dataset: Optional dataset to use for recalculation (if not provided, will search in _datasets)
        """
        if not config:
            return
        self._linear_phase_error_config = config

        # If this is a linear phase error chart, recreate the plot
        if config.get('type') == 'linear_phase_error':
            self.create_linear_phase_error_plot(config, dataset)

    def _apply_all_styling(self) -> None:
        """Apply all stored font and color styling to chart elements."""
        if not (self._chart_fonts or self._chart_colors):
            return

        try:
            # Apply title styling
            if 'title' in (self._chart_fonts or {}) or 'title' in (self._chart_colors or {}):
                self._set_title_with_styling(self._chart_title)
        except Exception as e:
            print(f"Warning: Could not apply title styling: {e}")

        try:
            # Apply axis labels
            self._set_axis_label_with_styling('bottom', 'Frequency', self._x_axis_unit)
            self._set_axis_label_with_styling('left', self._y_axis_label)
        except Exception as e:
            print(f"Warning: Could not apply axis label styling: {e}")

        try:
            # Apply tick styling
            if self._chart_fonts or self._chart_colors:
                bottom_axis = self._plot_item.getAxis('bottom')
                left_axis = self._plot_item.getAxis('left')

                if bottom_axis and self._chart_fonts and 'x_ticks' in self._chart_fonts:
                    try:
                        bottom_axis.setTickFont(self._chart_fonts['x_ticks'])
                        if self._chart_colors and 'x_ticks' in self._chart_colors:
                            bottom_axis.setTextPen(self._chart_colors['x_ticks'])
                    except (AttributeError, Exception) as e:
                        print(f"Warning: Could not apply X-axis tick styling: {e}")

                if left_axis and self._chart_fonts and 'y_ticks' in self._chart_fonts:
                    try:
                        left_axis.setTickFont(self._chart_fonts['y_ticks'])
                        if self._chart_colors and 'y_ticks' in self._chart_colors:
                            left_axis.setTextPen(self._chart_colors['y_ticks'])
                    except (AttributeError, Exception) as e:
                        print(f"Warning: Could not apply Y-axis tick styling: {e}")
        except Exception as e:
            print(f"Warning: Could not apply tick styling: {e}")

        try:
            # Apply legend styling
            self._apply_legend_styling()
        except Exception as e:
            print(f"Warning: Could not apply legend styling: {e}")

    def _parse_frequency(self, freq_str: str) -> float:
        """Parse frequency string with suffix support."""
        freq_str = freq_str.strip().upper()

        # Handle suffixes
        multipliers = {'K': 1e3, 'M': 1e6, 'G': 1e9, 'T': 1e12}

        for suffix, mult in multipliers.items():
            if freq_str.endswith(suffix):
                return float(freq_str[:-1]) * mult

        # No suffix, parse as-is
        return float(freq_str)

    def _add_limit_range(self, range_type: str) -> None:
        """Add a limit range (filled region) to the chart."""
        # Get the appropriate prompts based on range type
        if range_type == 'horizontal':
            # Horizontal range = frequency band (X-axis range)
            min_prompt = "Enter start frequency (Hz):"
            max_prompt = "Enter end frequency (Hz):"
            title = "Add Frequency Range"
        else:  # vertical - value range (Y-axis range)
            min_prompt = "Enter minimum Y value:"
            max_prompt = "Enter maximum Y value:"
            if self._plot_type == PlotType.MAGNITUDE:
                title = "Add Vertical Limit Range (dB)"
            elif self._plot_type == PlotType.PHASE:
                title = "Add Vertical Limit Range (degrees)"
            else:
                title = "Add Vertical Limit Range"

        # Get minimum value with text input for flexibility
        min_value_str, ok = QInputDialog.getText(self, title, min_prompt + "\n(Supports: 2.1e9, 2.1G, etc.)")
        if not ok or not min_value_str.strip():
            return

        # Get maximum value with text input for flexibility
        max_value_str, ok = QInputDialog.getText(self, title, max_prompt + "\n(Supports: 2.1e9, 2.1G, etc.)")
        if not ok or not max_value_str.strip():
            return

        # Parse the values with enhanced format support
        try:
            if range_type == 'horizontal':
                # For frequency ranges, support suffixes
                min_value = self._parse_frequency(min_value_str.strip())
                max_value = self._parse_frequency(max_value_str.strip())
            else:
                # For Y value ranges, just parse as float
                min_value = float(min_value_str.strip())
                max_value = float(max_value_str.strip())
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Value", f"Could not parse values: {str(e)}")
            return

        if min_value >= max_value:
            QMessageBox.warning(self, "Invalid Range", "Maximum value must be greater than minimum value.")
            return

        # Get label from user
        label, ok = QInputDialog.getText(self, "Limit Range Label",
                                         "Enter label for limit range (optional):")
        if not ok:
            label = ""

        # Create limit range
        self._create_limit_range(range_type, min_value, max_value, label)

    def _create_limit_range(self, range_type: str, min_value: float, max_value: float, label: str = "") -> str:
        """Create and add a limit range to the chart."""
        # Generate unique ID
        range_id = f"range_{self._next_limit_id}"
        self._next_limit_id += 1

        # Create filled region
        if range_type == 'horizontal':
            # Horizontal range = frequency band (X-axis range)
            fill_item = LinearRegionItem(values=[min_value, max_value], brush=pg.mkBrush(255, 0, 0, 50))
            fill_item.setMovable(True)
        else:  # vertical - value range (Y-axis range)
            # Create a filled region between two Y values
            # We'll use a FillBetweenItem or create a polygon fill
            # Get the current X range to span the fill across
            view_range = self._plot_item.viewRange()
            x_min, x_max = view_range[0]

            # Create a wide X range for the fill
            x_values = np.array([x_min - abs(x_max - x_min) * 0.1, x_max + abs(x_max - x_min) * 0.1])
            y1_values = np.array([min_value, min_value])
            y2_values = np.array([max_value, max_value])

            # Create fill between item
            try:
                fill_item = FillBetweenItem(
                    curve1=pg.PlotCurveItem(x_values, y1_values),
                    curve2=pg.PlotCurveItem(x_values, y2_values),
                    brush=pg.mkBrush(255, 0, 0, 50)
                )
            except (ImportError, TypeError):
                # Fallback: create boundary lines with filled polygon
                line1 = pg.InfiniteLine(pos=min_value, angle=0,
                                        pen=pg.mkPen('r', width=1, style=Qt.PenStyle.DashLine))
                line2 = pg.InfiniteLine(pos=max_value, angle=0,
                                        pen=pg.mkPen('r', width=1, style=Qt.PenStyle.DashLine))

                # Add labels positioned within view range
                line1.label = pg.InfLineLabel(line1, text=f'{min_value:.3g}', position=0.95, anchor=(1, 1))
                line2.label = pg.InfLineLabel(line2, text=f'{max_value:.3g}', position=0.95, anchor=(1, 1))

                # Create polygon points for filled region
                x_wide = np.array([x_min - abs(x_max - x_min), x_max + abs(x_max - x_min),
                                   x_max + abs(x_max - x_min), x_min - abs(x_max - x_min)])
                y_wide = np.array([min_value, min_value, max_value, max_value])

                polygon_item = pg.PlotCurveItem(x_wide, y_wide,
                                                fillLevel=min_value,
                                                brush=pg.mkBrush(255, 0, 0, 50),
                                                pen=None)

                fill_item = {'type': 'y_range_complex', 'line1': line1, 'line2': line2, 'polygon': polygon_item}
                self._plot_item.addItem(line1)
                self._plot_item.addItem(line2)
                self._plot_item.addItem(polygon_item)

        # Add to plot
        if range_type == 'horizontal':
            # LinearRegionItem for horizontal ranges
            self._plot_item.addItem(fill_item)
        else:
            # For vertical ranges, add the FillBetweenItem if it's not a complex fallback
            if not isinstance(fill_item, dict):
                self._plot_item.addItem(fill_item)

        # Add label if provided
        label_item = None
        if label:
            label_item = pg.TextItem(text=label, color='r', anchor=(0.5, 0))
            mid_value = (min_value + max_value) / 2
            if range_type == 'horizontal':
                # Horizontal range = frequency band, position at middle frequency
                # Position at 10% from bottom of current view range
                view_range = self._plot_item.viewRange()
                y_min, y_max = view_range[1]
                y_pos = y_min + (y_max - y_min) * 0.1
                label_item.setPos(mid_value, y_pos)
            else:  # vertical range = value band, position at middle value
                # Position at 10% from left of current view range
                view_range = self._plot_item.viewRange()
                x_min, x_max = view_range[0]
                x_pos = x_min + (x_max - x_min) * 0.1
                label_item.setPos(x_pos, mid_value)
            self._plot_item.addItem(label_item)

        # Store limit range data
        range_data = {
            'type': f'{range_type}_range',
            'min_value': min_value,
            'max_value': max_value,
            'label': label,
            'color': 'r',
            'style': 'filled',
            'width': 2,
            'item': fill_item,
            'label_item': label_item
        }

        # For vertical ranges, also store the line items if they exist (fallback case)
        if range_type == 'vertical' and isinstance(fill_item, dict):
            # This is the complex fallback case with multiple items
            if 'line1' in fill_item:
                range_data['line1'] = fill_item['line1']
            if 'line2' in fill_item:
                range_data['line2'] = fill_item['line2']
            if 'polygon' in fill_item:
                range_data['polygon'] = fill_item['polygon']

        self._limit_lines[range_id] = range_data

        return range_id

    def _add_points_limit(self) -> None:
        """Add a point-based limit line to the chart."""
        # Create a custom dialog with table input
        dialog = QDialog(self)
        dialog.setWindowTitle("Point-Based Limit Line")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        # Instructions
        instructions = QLabel(
            "Enter frequency and value pairs:\n"
            "• Frequency supports: 1e9, 1G, 1000000000\n"
            "• Use scientific notation or suffixes (k, M, G, T)\n"
            "• Right-click to add/remove rows"
        )
        layout.addWidget(instructions)

        # Create table
        table = QTableWidget(5, 2)  # Start with 5 rows, 2 columns
        table.setHorizontalHeaderLabels(["Frequency (Hz)", "Value"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Add some default values
        default_points = [
            ("1G", "-10"),
            ("5G", "-20"),
            ("10G", "-15"),
            ("", ""),
            ("", "")
        ]

        for row, (freq, value) in enumerate(default_points):
            table.setItem(row, 0, QTableWidgetItem(freq))
            table.setItem(row, 1, QTableWidgetItem(value))

        # Context menu for table
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def add_row():
            row_count = table.rowCount()
            table.setRowCount(row_count + 1)
            table.setItem(row_count, 0, QTableWidgetItem(""))
            table.setItem(row_count, 1, QTableWidgetItem(""))

        def remove_row():
            current_row = table.currentRow()
            if current_row >= 0 and table.rowCount() > 1:
                table.removeRow(current_row)

        def show_context_menu(pos):
            menu = QMenu()

            add_action = menu.addAction("Add Row")
            add_action.triggered.connect(add_row)

            if table.rowCount() > 1:
                remove_action = menu.addAction("Remove Row")
                remove_action.triggered.connect(remove_row)

            menu.exec(table.mapToGlobal(pos))

        table.customContextMenuRequested.connect(show_context_menu)
        layout.addWidget(table)

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        add_row_button = QPushButton("Add Row")

        add_row_button.clicked.connect(add_row)
        button_layout.addWidget(add_row_button)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Extract points from table
        points = []
        try:
            for row in range(table.rowCount()):
                freq_item = table.item(row, 0)
                value_item = table.item(row, 1)

                if freq_item and value_item:
                    freq_text = freq_item.text().strip()
                    value_text = value_item.text().strip()

                    if freq_text and value_text:  # Both cells have content
                        try:
                            freq = self._parse_frequency(freq_text)
                            value = float(value_text)
                            points.append((freq, value))
                        except ValueError as ve:
                            raise ValueError(f"Row {row + 1}: {str(ve)}")

            if len(points) < 2:
                raise ValueError("At least 2 points are required")

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Points", f"Error parsing points:\n{str(e)}")
            return

        # Get label and display options from user
        label_dialog = QDialog(self)
        label_dialog.setWindowTitle("Point Limit Options")
        label_dialog.setModal(True)
        label_dialog.resize(350, 200)

        label_layout = QVBoxLayout(label_dialog)

        # Label input
        label_input = QLineEdit()
        label_input.setPlaceholderText("Enter label for point-based limit (optional)")
        label_layout.addWidget(QLabel("Label:"))
        label_layout.addWidget(label_input)

        # Label display options
        show_label_on_chart = QCheckBox("Show label on chart")
        show_label_on_chart.setChecked(False)  # Default: don't show on chart
        show_label_on_chart.setToolTip("Display label text near the limit line")

        show_in_legend = QCheckBox("Show in legend")
        show_in_legend.setChecked(True)  # Default: show in legend
        show_in_legend.setToolTip("Include this limit line in the chart legend")

        label_layout.addWidget(show_label_on_chart)
        label_layout.addWidget(show_in_legend)

        # Buttons
        label_button_layout = QHBoxLayout()
        label_ok_button = QPushButton("OK")
        label_cancel_button = QPushButton("Cancel")
        label_button_layout.addWidget(label_ok_button)
        label_button_layout.addWidget(label_cancel_button)
        label_layout.addLayout(label_button_layout)

        label_ok_button.clicked.connect(label_dialog.accept)
        label_cancel_button.clicked.connect(label_dialog.reject)

        if label_dialog.exec() != QDialog.DialogCode.Accepted:
            return

        label = label_input.text().strip()
        show_chart_label = show_label_on_chart.isChecked()
        show_legend = show_in_legend.isChecked()

        # Create points limit with options
        self._create_points_limit(points, label, show_chart_label, show_legend)

    def _create_points_limit(self, points: list, label: str = "",
                             show_chart_label: bool = False,
                             show_legend: bool = True) -> str:
        """Create and add a point-based limit line to the chart."""
        # Generate unique ID
        points_id = f"points_{self._next_limit_id}"
        self._next_limit_id += 1

        # Extract x and y values
        x_values = [p[0] for p in points]
        y_values = [p[1] for p in points]

        # Create plot curve with or without legend name
        curve_name = None
        if show_legend and label:
            curve_name = label
        elif show_legend and not label:
            curve_name = "Point Limit"
        # If show_legend is False, curve_name stays None (no legend entry)

        curve_item = pg.PlotCurveItem(
            x=x_values,
            y=y_values,
            pen=pg.mkPen('r', width=2, style=Qt.PenStyle.DashLine),
            name=curve_name
        )

        # Add to plot
        self._plot_item.addItem(curve_item)

        # Add label on chart if requested and label exists
        label_item = None
        if show_chart_label and label:
            # Position label at first point
            label_item = pg.TextItem(text=label, color='r', anchor=(0, 1))
            label_item.setPos(x_values[0], y_values[0])
            self._plot_item.addItem(label_item)

        # Store points limit data
        self._limit_lines[points_id] = {
            'type': 'points',
            'points': points,
            'label': label,
            'color': 'r',
            'style': 'line',
            'width': 2,
            'item': curve_item,
            'label_item': label_item,
            'show_chart_label': show_chart_label,
            'show_legend': show_legend
        }

        # Apply initial styling to make sure the curve appears with correct default style
        self._update_limit_line_style(points_id)

        return points_id

    def _on_trace_clicked(self, trace_id: str, plot_item) -> None:
        """Handle trace click for selection and properties."""
        self._show_trace_selection_dialog()

    def _update_trace_style(self, trace_id: str) -> None:
        """Update the visual style of a trace."""
        if trace_id not in self._traces or trace_id not in self._plot_items:
            return

        trace = self._traces[trace_id]
        plot_item = self._plot_items[trace_id]

        # Create new pen with updated style
        pen = pg.mkPen(
            color=trace.style.color,
            width=trace.style.line_width,
            style=self._get_pen_style(trace.style.line_style)
        )

        # Update the plot item pen
        plot_item.setPen(pen)

        # Update markers if they exist
        symbol = self._get_symbol(trace.style.marker_style)
        symbol_size = trace.style.marker_size
        plot_item.setSymbol(symbol)
        plot_item.setSymbolSize(symbol_size)

    def _update_limit_line_style(self, line_id: str) -> None:
        """Update the visual style of a limit line."""
        if line_id not in self._limit_lines:
            return

        line_data = self._limit_lines[line_id]
        line_type = line_data.get('type', 'horizontal')

        # Get the new style properties
        color = line_data.get('color', 'r')
        style = line_data.get('style', 'dash')
        width = line_data.get('width', 2)

        # Create new pen with updated style
        pen_style = self._get_limit_pen_style(style)
        pen = pg.mkPen(color=color, width=width, style=pen_style)

        # Update the appropriate plot items based on line type
        if line_type in ['horizontal', 'vertical']:
            # Simple infinite lines
            line_item = line_data.get('item')
            if line_item and hasattr(line_item, 'setPen'):
                line_item.setPen(pen)

        elif line_type in ['frequency_range', 'value_range']:
            # Range lines - update fill area and boundary lines
            fill_item = line_data.get('item')
            if fill_item and hasattr(fill_item, 'setBrush'):
                # Update FillBetweenItem with brush color (semi-transparent)
                brush = pg.mkBrush(color=color, alpha=50)  # Semi-transparent fill
                fill_item.setBrush(brush)

            # Also update boundary lines if they exist (fallback case)
            line1 = line_data.get('line1')
            line2 = line_data.get('line2')
            if line1 and hasattr(line1, 'setPen'):
                line1.setPen(pen)
            if line2 and hasattr(line2, 'setPen'):
                line2.setPen(pen)

        elif line_type == 'points':
            # Point-based curve
            curve_item = line_data.get('item')
            if curve_item and hasattr(curve_item, 'setPen'):
                curve_item.setPen(pen)

    def _get_limit_pen_style(self, style_name: str):
        """Convert limit line style name to PyQtGraph pen style."""
        style_map = {
            'solid': Qt.PenStyle.SolidLine,
            'dash': Qt.PenStyle.DashLine,
            'dot': Qt.PenStyle.DotLine,
            'dashdot': Qt.PenStyle.DashDotLine
        }
        return style_map.get(style_name, Qt.PenStyle.DashLine)

    def _show_font_styling_dialog(self) -> None:
        """Show font styling dialog for chart elements."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Font Styling")
        dialog.setModal(True)
        dialog.resize(450, 400)

        layout = QVBoxLayout(dialog)

        # Load existing stored fonts and colors, or use defaults
        current_fonts = {
            'title': QFont("Arial", 12, QFont.Weight.Bold),
            'x_axis': QFont("Arial", 10),
            'y_axis': QFont("Arial", 10),
            'x_ticks': QFont("Arial", 9),
            'y_ticks': QFont("Arial", 9),
            'legend': QFont("Arial", 9)
        }

        current_colors = {
            'title': '#000000',
            'x_axis': '#000000',
            'y_axis': '#000000',
            'x_ticks': '#000000',
            'y_ticks': '#000000',
            'legend': '#000000'
        }

        # Load existing settings if available
        if hasattr(self, '_chart_fonts') and self._chart_fonts:
            current_fonts.update(self._chart_fonts)

        if hasattr(self, '_chart_colors') and self._chart_colors:
            current_colors.update(self._chart_colors)

        # Create font styling widget with current settings
        font_widget = FontStylingWidget(
            initial_fonts=current_fonts,
            initial_colors=current_colors,
            parent=dialog
        )
        layout.addWidget(font_widget)

        # Buttons
        button_layout = QHBoxLayout()
        apply_button = QPushButton("Apply Current Tab")
        apply_button.setToolTip("Apply changes from the currently selected tab only")
        ok_button = QPushButton("OK")
        ok_button.setToolTip("Apply all changes and close dialog")
        cancel_button = QPushButton("Cancel")
        reset_button = QPushButton("Reset to Defaults")

        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Get the tab widget from the font_widget to determine current tab
        tab_widget = font_widget.findChild(QTabWidget)

        # Apply styling function for current tab only
        def apply_current_tab():
            current_tab_index = tab_widget.currentIndex() if tab_widget else 0
            fonts = font_widget.get_fonts()
            colors = font_widget.get_colors()

            if current_tab_index == 0:  # Chart Title tab
                self._apply_title_styling(fonts['title'], colors['title'])
            elif current_tab_index == 1:  # X & Y Axes tab (combined)
                self._apply_combined_axes_styling(fonts, colors)
            elif current_tab_index == 2:  # Legend tab
                self._apply_legend_styling_with_color(fonts['legend'], colors['legend'])

        # Apply all styling function (for OK button)
        def apply_all_styling():
            fonts = font_widget.get_fonts()
            colors = font_widget.get_colors()
            self._apply_chart_fonts(fonts, colors)
            # Emit signal to notify that properties changed
            self.properties_changed.emit()

        # Connect buttons
        apply_button.clicked.connect(apply_current_tab)
        ok_button.clicked.connect(lambda: (apply_all_styling(), dialog.accept()))
        cancel_button.clicked.connect(dialog.reject)
        reset_button.clicked.connect(font_widget.reset_to_defaults)

        dialog.exec()

    def _show_plot_area_properties_dialog(self) -> None:
        """Show plot area properties dialog for customizing borders, background, grid, etc."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Plot Area Properties")
        dialog.setModal(True)
        dialog.resize(450, 400)

        layout = QVBoxLayout(dialog)

        # Load existing settings or use defaults
        current_settings = {
            'background_color': 'white',
            'border_type': 'standard',
            'show_top_right_labels': False,
            'border_color': '#333333',
            'border_style': 'solid',
            'border_width': 1,
            'show_grid_x': True,
            'show_grid_y': True,
            'grid_alpha': 0.3
        }

        # Update with existing settings if available
        if self._plot_area_settings:
            current_settings.update(self._plot_area_settings)

        # Create plot area properties widget with current settings
        plot_widget = PlotAreaPropertiesWidget(
            initial_settings=current_settings,
            parent=dialog
        )
        layout.addWidget(plot_widget)

        # Buttons
        button_layout = QHBoxLayout()
        apply_button = QPushButton("Apply")
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        reset_button = QPushButton("Reset to Defaults")

        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(apply_button)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        # Button handlers
        def apply_plot_area_settings():
            # Get settings from widget
            settings = plot_widget.get_settings()

            # Store settings
            self._plot_area_settings = settings

            # Apply the settings to the plot
            self._apply_plot_area_settings(settings)

            # Emit signal to notify that properties changed
            self.properties_changed.emit()

        # Connect buttons
        apply_button.clicked.connect(apply_plot_area_settings)
        ok_button.clicked.connect(lambda: (apply_plot_area_settings(), dialog.accept()))
        cancel_button.clicked.connect(dialog.reject)
        reset_button.clicked.connect(plot_widget.reset_to_defaults)

        dialog.exec()

    def _apply_plot_area_settings(self, settings: dict) -> None:
        """Apply plot area settings to the chart."""
        # Apply background color
        bg_color = settings.get('background_color', 'white')
        self._plot_widget.setBackground(bg_color)

        # Apply grid settings (independent from border settings)
        show_grid_x = settings.get('show_grid_x', True)
        show_grid_y = settings.get('show_grid_y', True)
        grid_alpha = settings.get('grid_alpha', 0.3)

        # Apply grid settings
        self._plot_item.showGrid(x=show_grid_x, y=show_grid_y, alpha=grid_alpha)

        # Note: PyQtGraph grid color customization is complex and not easily supported
        # Grid uses internal styling that's tied to the theme

        # Apply border settings
        border_type = settings.get('border_type', 'standard')
        border_color = settings.get('border_color', '#333333')
        border_style = settings.get('border_style', 'solid')
        border_width = settings.get('border_width', 1)
        show_top_right_labels = settings.get('show_top_right_labels', False)

        # Convert border style to Qt pen style
        style_map = {
            'solid': pg.QtCore.Qt.PenStyle.SolidLine,
            'dashed': pg.QtCore.Qt.PenStyle.DashLine,
            'dotted': pg.QtCore.Qt.PenStyle.DotLine,
            'dashdot': pg.QtCore.Qt.PenStyle.DashDotLine
        }
        pen_style = style_map.get(border_style, pg.QtCore.Qt.PenStyle.SolidLine)

        # Create pen for axes
        axis_pen = pg.mkPen(color=border_color, width=border_width, style=pen_style)
        transparent_pen = pg.mkPen(color='transparent')

        if border_type == 'full':
            # Show all four axes
            self._plot_item.getAxis('left').setPen(axis_pen)
            self._plot_item.getAxis('bottom').setPen(axis_pen)
            self._plot_item.getAxis('right').setPen(axis_pen)
            self._plot_item.getAxis('top').setPen(axis_pen)

            # Always show top and right axes (for the border lines)
            self._plot_item.showAxis('right', True)
            self._plot_item.showAxis('top', True)

            # Control tick labels independently from axis line visibility
            # PyQtGraph limitation: setStyle(showValues=False) also hides the axis line
            # Workaround: Use setTicks() with empty list to hide tick labels but keep axis line
            right_axis = self._plot_item.getAxis('right')
            top_axis = self._plot_item.getAxis('top')

            if show_top_right_labels:
                # Show tick labels - restore normal ticking behavior
                right_axis.setStyle(showValues=True)
                top_axis.setStyle(showValues=True)
                # Reset ticks to auto-generate
                right_axis.setTicks(None)
                top_axis.setTicks(None)
            else:
                # Hide tick labels but keep axis line by setting empty tick list
                # This prevents PyQtGraph from hiding the entire axis
                right_axis.setStyle(showValues=True)  # Keep axis visible
                top_axis.setStyle(showValues=True)    # Keep axis visible
                # Set empty tick lists to hide labels but keep lines
                right_axis.setTicks([[]])  # Empty major ticks, no minor ticks
                top_axis.setTicks([[]])    # Empty major ticks, no minor ticks

        elif border_type == 'standard':
            # Standard border: only left and bottom
            self._plot_item.getAxis('left').setPen(axis_pen)
            self._plot_item.getAxis('bottom').setPen(axis_pen)
            self._plot_item.getAxis('right').setPen(transparent_pen)
            self._plot_item.getAxis('top').setPen(transparent_pen)

            # Hide top and right axes
            self._plot_item.showAxis('right', False)
            self._plot_item.showAxis('top', False)

        else:  # border_type == 'none'
            # No border - make all axes transparent
            self._plot_item.getAxis('left').setPen(transparent_pen)
            self._plot_item.getAxis('bottom').setPen(transparent_pen)
            self._plot_item.getAxis('right').setPen(transparent_pen)
            self._plot_item.getAxis('top').setPen(transparent_pen)

            # Hide top and right axes
            self._plot_item.showAxis('right', False)
            self._plot_item.showAxis('top', False)

    def _apply_chart_fonts(self, fonts: dict, colors: dict) -> None:
        """Apply font styling to chart elements."""
        # Store the font and color settings for persistent application
        self._chart_fonts = fonts.copy()
        self._chart_colors = colors.copy()

        # Apply title styling
        self._set_title_with_styling(self._chart_title)

        # Apply axis labels with styling
        self._set_axis_label_with_styling('bottom', 'Frequency', self._x_axis_unit)
        self._set_axis_label_with_styling('left', self._y_axis_label)

        # Apply tick font styling
        bottom_axis = self._plot_item.getAxis('bottom')
        left_axis = self._plot_item.getAxis('left')

        # Apply tick label fonts and colors (axis objects already retrieved above)
        if bottom_axis:
            try:
                bottom_axis.setTickFont(fonts['x_ticks'])
                bottom_axis.setTextPen(colors['x_ticks'])
            except AttributeError:
                pass  # Some PyQtGraph versions may not support this

        if left_axis:
            try:
                left_axis.setTickFont(fonts['y_ticks'])
                left_axis.setTextPen(colors['y_ticks'])
            except AttributeError:
                pass  # Some PyQtGraph versions may not support this

        # Apply legend styling using our persistent method
        self._apply_legend_styling()

        # Store the font and color settings for future use
        self._chart_fonts = fonts.copy()
        self._chart_colors = colors.copy()

        # Force a repaint/update of the plot to ensure changes are visible
        self._plot_item.update()
        self._plot_widget.update()

    def _apply_title_styling(self, font, color) -> None:
        """Apply font and color styling to chart title only."""
        # Update stored settings for this element
        if not hasattr(self, '_chart_fonts') or self._chart_fonts is None:
            self._chart_fonts = {}
        if not hasattr(self, '_chart_colors') or self._chart_colors is None:
            self._chart_colors = {}

        self._chart_fonts['title'] = font
        self._chart_colors['title'] = color

        # Apply title styling
        self._set_title_with_styling(self._chart_title)

    def _apply_axis_labels_styling(self, fonts, colors) -> None:
        """Apply font styling to axis labels only."""
        # Update stored settings for axis labels
        if not hasattr(self, '_chart_fonts') or self._chart_fonts is None:
            self._chart_fonts = {}
        if not hasattr(self, '_chart_colors') or self._chart_colors is None:
            self._chart_colors = {}

        self._chart_fonts.update({
            'x_axis': fonts['x_axis'],
            'y_axis': fonts['y_axis']
        })
        self._chart_colors.update({
            'x_axis': colors['x_axis'],
            'y_axis': colors['y_axis']
        })

        # Apply axis labels with styling
        self._set_axis_label_with_styling('bottom', 'Frequency', self._x_axis_unit)
        self._set_axis_label_with_styling('left', self._y_axis_label)

    def _apply_tick_labels_styling(self, fonts, colors) -> None:
        """Apply font and color styling to tick labels only."""
        # Update stored settings for tick labels
        if not hasattr(self, '_chart_fonts') or self._chart_fonts is None:
            self._chart_fonts = {}
        if not hasattr(self, '_chart_colors') or self._chart_colors is None:
            self._chart_colors = {}

        self._chart_fonts.update({
            'x_ticks': fonts['x_ticks'],
            'y_ticks': fonts['y_ticks']
        })
        self._chart_colors.update({
            'x_ticks': colors['x_ticks'],
            'y_ticks': colors['y_ticks']
        })

        # Apply tick font styling
        bottom_axis = self._plot_item.getAxis('bottom')
        left_axis = self._plot_item.getAxis('left')

        if bottom_axis:
            try:
                bottom_axis.setTickFont(fonts['x_ticks'])
                bottom_axis.setTextPen(colors['x_ticks'])
            except AttributeError:
                pass

        if left_axis:
            try:
                left_axis.setTickFont(fonts['y_ticks'])
                left_axis.setTextPen(colors['y_ticks'])
            except AttributeError:
                pass

    def _apply_legend_styling_single(self, font) -> None:
        """Apply font styling to legend only."""
        # Update stored settings for legend
        if not hasattr(self, '_chart_fonts') or self._chart_fonts is None:
            self._chart_fonts = {}

        self._chart_fonts['legend'] = font

        # Apply legend styling
        self._apply_legend_styling()

    def _apply_legend_styling_with_color(self, font, color) -> None:
        """Apply font and color styling to legend only."""
        # Update stored settings for legend
        if not hasattr(self, '_chart_fonts') or self._chart_fonts is None:
            self._chart_fonts = {}
        if not hasattr(self, '_chart_colors') or self._chart_colors is None:
            self._chart_colors = {}

        self._chart_fonts['legend'] = font
        self._chart_colors['legend'] = color

        # Apply legend styling
        self._apply_legend_styling()

    def _apply_combined_axes_styling(self, fonts, colors) -> None:
        """Apply font and color styling to both axis labels and ticks (combined tab)."""
        # Update stored settings for both labels and ticks
        if not hasattr(self, '_chart_fonts') or self._chart_fonts is None:
            self._chart_fonts = {}
        if not hasattr(self, '_chart_colors') or self._chart_colors is None:
            self._chart_colors = {}

        # Update both axis label fonts and tick styling
        self._chart_fonts.update({
            'x_axis': fonts['x_axis'],    # Label font
            'y_axis': fonts['y_axis'],    # Label font
            'x_ticks': fonts['x_ticks'],  # Tick font
            'y_ticks': fonts['y_ticks']   # Tick font
        })
        self._chart_colors.update({
            'x_ticks': colors['x_ticks'],  # Tick color (controls both ticks and label)
            'y_ticks': colors['y_ticks']   # Tick color (controls both ticks and label)
        })

        # Apply axis labels with stored fonts (color controlled by tick styling)
        self._set_axis_label_with_styling('bottom', 'Frequency', self._x_axis_unit)
        self._set_axis_label_with_styling('left', self._y_axis_label)

        # Apply tick styling (font + color for both ticks and labels)
        bottom_axis = self._plot_item.getAxis('bottom')
        left_axis = self._plot_item.getAxis('left')

        if bottom_axis:
            try:
                bottom_axis.setTickFont(fonts['x_ticks'])
                bottom_axis.setTextPen(colors['x_ticks'])  # This controls both tick numbers and axis label color
            except AttributeError:
                pass

        if left_axis:
            try:
                left_axis.setTickFont(fonts['y_ticks'])
                left_axis.setTextPen(colors['y_ticks'])   # This controls both tick numbers and axis label color
            except AttributeError:
                pass

    def _set_axis_label_with_styling(self, axis_name: str, text: str, units: str = None) -> None:
        """Set axis label with stored font/color styling if available."""
        if axis_name == 'bottom':
            # Set the label first
            if units:
                self._plot_item.setLabel(axis_name, text, units=units)
            else:
                self._plot_item.setLabel(axis_name, text)

            # Apply stored styling if available
            if self._chart_colors and ('x_axis' in self._chart_colors or 'x_ticks' in self._chart_colors):
                try:
                    bottom_axis = self._plot_item.getAxis('bottom')
                    # Use the simple method that worked before
                    if units:
                        bottom_axis.setLabel(text, units=units, color=self._chart_colors.get(
                            'x_ticks', self._chart_colors.get('x_axis', '#000000')))
                    else:
                        bottom_axis.setLabel(text, color=self._chart_colors['x_axis'])

                    # Apply font if available
                    if (self._chart_fonts and 'x_axis' in self._chart_fonts and
                            hasattr(bottom_axis, 'label') and bottom_axis.label):
                        bottom_axis.label.setFont(self._chart_fonts['x_axis'])
                except Exception:
                    pass

        elif axis_name == 'left':
            # Set the label first
            self._plot_item.setLabel(axis_name, text)

            # Apply stored styling if available
            if self._chart_colors and ('y_axis' in self._chart_colors or 'y_ticks' in self._chart_colors):
                try:
                    left_axis = self._plot_item.getAxis('left')
                    # Use the simple method that worked before
                    left_axis.setLabel(text, color=self._chart_colors.get(
                        'y_ticks', self._chart_colors.get('y_axis', '#000000')))

                    # Apply font if available
                    if (self._chart_fonts and 'y_axis' in self._chart_fonts and
                            hasattr(left_axis, 'label') and left_axis.label):
                        left_axis.label.setFont(self._chart_fonts['y_axis'])
                except Exception:
                    pass

    def _apply_legend_styling(self) -> None:
        """Apply stored legend font styling if available (colors disabled due to PyQtGraph limitations)."""
        if not self._chart_fonts:
            return

        legend = self._legend or self._plot_item.legend
        if not legend:
            return

        try:
            # Apply legend font (this was working before)
            if self._chart_fonts and 'legend' in self._chart_fonts:

                # Method 1: Standard PyQtGraph method
                if hasattr(legend, 'setFont'):
                    legend.setFont(self._chart_fonts['legend'])

                # Method 2: Apply font to individual items (this was the working approach)
                if hasattr(legend, 'items') and legend.items:
                    for sample, label in legend.items:
                        try:
                            if hasattr(label, 'setFont'):
                                label.setFont(self._chart_fonts['legend'])

                            # Try accessing the underlying text item more aggressively
                            if hasattr(label, 'item'):
                                text_item = label.item
                                if hasattr(text_item, 'setFont'):
                                    text_item.setFont(self._chart_fonts['legend'])
                        except Exception:
                            pass  # Ignore individual item failures

                # Method 3: Use setLabelTextSize as fallback
                elif hasattr(legend, 'setLabelTextSize'):
                    legend.setLabelTextSize(f"{self._chart_fonts['legend'].pointSize()}pt")

            # Apply legend color (stored color or default black)
            legend_color = '#000000'  # Default black
            if self._chart_colors and 'legend' in self._chart_colors:
                legend_color = self._chart_colors['legend']
            self._set_legend_color(legend, legend_color)

            # Force legend update
            if hasattr(legend, 'update'):
                legend.update()

        except Exception:
            pass  # Silently handle any legend styling failures

    def _set_initial_legend_color(self) -> None:
        """Set initial legend text color to black."""
        if not self._legend:
            return

        try:
            # Try multiple methods to set initial legend color to black
            legend = self._legend

            # Method 1: Standard PyQtGraph color method
            if hasattr(legend, 'setLabelTextColor'):
                legend.setLabelTextColor('#000000')

            # Method 2: Try to set default text color
            if hasattr(legend, 'setDefaultTextColor'):
                legend.setDefaultTextColor(QColor('#000000'))

            # Method 3: Apply to individual items as they get added
            # This will be handled when traces are actually plotted

        except Exception:
            pass  # Silently handle any legend color setting failures

    def _set_legend_color(self, legend, color='#000000') -> None:
        """Set legend text items to specified color."""
        if not legend:
            return

        try:
            # Method 1: Set via standard methods
            if hasattr(legend, 'setLabelTextColor'):
                legend.setLabelTextColor(color)

            # Method 2: Apply to individual items
            if hasattr(legend, 'items') and legend.items:
                qcolor = QColor(color)

                for sample, label in legend.items:
                    try:
                        # Try multiple ways to set text color
                        if hasattr(label, 'setDefaultTextColor'):
                            label.setDefaultTextColor(qcolor)
                        elif hasattr(label, 'setColor'):
                            label.setColor(qcolor)

                        # Try accessing underlying text item
                        if hasattr(label, 'item'):
                            text_item = label.item
                            if hasattr(text_item, 'setDefaultTextColor'):
                                text_item.setDefaultTextColor(qcolor)
                            elif hasattr(text_item, 'setColor'):
                                text_item.setColor(qcolor)

                        # Try HTML approach as last resort
                        if hasattr(label, 'setText') and hasattr(label, 'text'):
                            current_text = label.text if callable(label.text) else str(label.text)
                            # Strip existing color tags first
                            clean_text = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', current_text)
                            clean_text = re.sub(r'<font[^>]*>(.*?)</font>', r'\1', clean_text)
                            colored_text = f'<span style="color:{color}">{clean_text}</span>'
                            label.setText(colored_text)

                    except Exception:
                        pass  # Ignore individual item failures

        except Exception:
            pass  # Silently handle any failures

    def _set_title_with_styling(self, title: str) -> None:
        """Set chart title with stored font/color styling if available."""
        if self._chart_colors and self._chart_fonts:
            # Apply both color and font
            if 'title' in self._chart_colors and 'title' in self._chart_fonts:
                font = self._chart_fonts['title']
                color = self._chart_colors['title']

                # Use setTitle with color and size parameters
                self._plot_item.setTitle(
                    title,
                    color=color,
                    size=f"{font.pointSize()}pt"
                )

                # Then access the title label to set the complete font
                # This ensures family, weight, and italic are applied
                title_label = self._plot_item.titleLabel
                if title_label and hasattr(title_label, 'item'):
                    try:
                        # Apply the complete font (family, size, weight, italic)
                        title_label.item.setFont(font)

                        # Reapply color as QColor to ensure it's set correctly
                        if isinstance(color, str):
                            qcolor = QColor(color)
                        else:
                            qcolor = color
                        title_label.item.setDefaultTextColor(qcolor)
                    except Exception as e:
                        # If direct font setting fails, at least we have size and color from setTitle
                        print(f"Warning: Could not apply full title font styling: {e}")
                return
            self._plot_item.setTitle(title)

        # Fallback to basic title
        self._plot_item.setTitle(title)
