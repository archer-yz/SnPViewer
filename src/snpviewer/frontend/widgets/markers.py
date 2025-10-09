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
from PySide6.QtGui import QAction, QColor, QFont, QPen
from PySide6.QtWidgets import (QCheckBox, QHeaderView, QInputDialog, QMenu,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from snpviewer.frontend.constants import DEFAULT_MARKER_COLORS


class DraggableScatterPlotItem(pg.ScatterPlotItem):
    """ScatterPlotItem with proper mouse press/drag/release handling and context menu."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_dragging = False
        self._drag_callbacks = {
            'press': None,
            'move': None,
            'release': None,
            'context_menu': None
        }

    def set_drag_callbacks(self, press_cb=None, move_cb=None, release_cb=None, context_menu_cb=None):
        """Set callbacks for drag events and context menu."""
        self._drag_callbacks['press'] = press_cb
        self._drag_callbacks['move'] = move_cb
        self._drag_callbacks['release'] = release_cb
        self._drag_callbacks['context_menu'] = context_menu_cb

    def mousePressEvent(self, ev):
        """Handle mouse press - start dragging or show context menu."""
        if ev.button() == Qt.MouseButton.LeftButton:
            # Check if click is near our point
            pts = self.pointsAt(ev.pos())
            if len(pts) > 0:
                self._is_dragging = True
                ev.accept()
                if self._drag_callbacks['press']:
                    self._drag_callbacks['press'](ev)
                return
        elif ev.button() == Qt.MouseButton.RightButton:
            # Right-click for context menu
            pts = self.pointsAt(ev.pos())
            if len(pts) > 0:
                ev.accept()
                if self._drag_callbacks['context_menu']:
                    self._drag_callbacks['context_menu'](ev)
                return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        """Handle mouse move - dragging."""
        if self._is_dragging:
            ev.accept()
            if self._drag_callbacks['move']:
                self._drag_callbacks['move'](ev)
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        """Handle mouse release - stop dragging."""
        if self._is_dragging and ev.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            ev.accept()
            if self._drag_callbacks['release']:
                self._drag_callbacks['release'](ev)
        else:
            super().mouseReleaseEvent(ev)


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
    Interactive marker with two modes:
    - Vertical Marker (coupled=True): Vertical line with label, shows all traces data
    - Triangle Marker (coupled=False): Draggable triangle on specific trace, shows single trace data

    Supports dragging, double-click editing, automatic value interpolation, and selection.
    """

    # Signal for when marker is moved
    position_changed = Signal(str, float)  # marker_id, new_frequency

    def __init__(self, marker_num: int, plot_item: pg.PlotItem, color: str = "#4A90E2",
                 coupled: bool = True, target_trace: Optional[str] = None,
                 selection_callback=None):
        """
        Initialize marker.

        Args:
            marker_num: Marker number (1, 2, 3, etc.) for display
            plot_item: PyQtGraph plot item to add marker to
            color: Marker color (hex string)
            coupled: If True, show vertical line (no symbol) and data for all traces.
                    If False, show draggable triangle symbol on target trace only.
            selection_callback: Callback function(marker_num) when marker is clicked
            target_trace: For uncoupled mode, which trace to attach to
        """
        self.marker_num = marker_num
        self.plot_item = plot_item
        self.color = color
        self.visible = True
        self.coupled = coupled
        self.target_trace = target_trace
        self.selection_callback = selection_callback
        self._selected = False

        # Create vertical dashed line (only for coupled/vertical mode)
        self.line = pg.InfiniteLine(
            angle=90,  # Vertical line
            movable=True,
            pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine),
            hoverPen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine),
        )

        # Create triangle marker pointing DOWN (vertex at bottom, base on top)
        # Only used in uncoupled mode - use custom draggable version
        self.marker_symbol = DraggableScatterPlotItem(
            size=12,
            pen=pg.mkPen(color, width=1),
            brush=pg.mkBrush(color),
            symbol='t',  # Triangle pointing down (t not t1)
            pxMode=True,
            hoverable=True,
            tip=None
        )

        # Selection indicator (box around triangle when selected)
        self.selection_box = pg.ScatterPlotItem(
            size=18,
            pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DotLine),
            brush=None,
            symbol='s',  # Square
            pxMode=True
        )
        self.selection_box.setVisible(False)

        # Enable dragging for uncoupled mode
        if not self.coupled:
            # Make the symbol accept events with higher priority
            self.marker_symbol.setZValue(1000)  # High Z value for priority
            self.selection_box.setZValue(999)

            # Set up drag callbacks
            self.marker_symbol.set_drag_callbacks(
                press_cb=self._on_drag_press,
                move_cb=self._on_drag_move,
                release_cb=self._on_drag_release,
                context_menu_cb=self._on_context_menu
            )

        # Create text label
        # For vertical marker: positioned near the line
        # For triangle marker: positioned above the triangle base
        # Anchor (0.5, Y): Y=1.0 means label bottom at position, lower values bring label down
        # For triangle pointing down, we want label above the base (top of triangle)
        self.label = pg.TextItem(
            text=f'M{marker_num}',
            color=color,
            anchor=(0.5, 1.0) if not self.coupled else (0.5, 0.5),  # 1.3 = further above
        )
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        self.label.setFont(font)

        # Connect signals
        self.line.sigPositionChanged.connect(self._on_line_moved)
        self.line.sigPositionChangeFinished.connect(self._on_move_finished)

        # Add click handler for vertical line selection
        if self.coupled:
            # Override mouseClickEvent to add selection behavior
            original_mouse_click = self.line.mouseClickEvent
            original_mouse_press = self.line.mousePressEvent

            def line_mouse_click(ev):
                if ev.button() == Qt.MouseButton.LeftButton:
                    # Trigger selection
                    if self.selection_callback:
                        self.selection_callback(self.marker_num)
                # Call original handler
                original_mouse_click(ev)

            def line_mouse_press(ev):
                if ev.button() == Qt.MouseButton.RightButton:
                    # Right-click for context menu
                    ev.accept()
                    self._on_context_menu(ev)
                else:
                    # Call original handler
                    original_mouse_press(ev)

            self.line.mouseClickEvent = line_mouse_click
            self.line.mousePressEvent = line_mouse_press

        # Add to plot based on mode
        if self.coupled:
            # Vertical marker: only line and label
            self.plot_item.addItem(self.line)
            self.plot_item.addItem(self.label)
        else:
            # Triangle marker: symbol, selection box, and label (no line)
            self.plot_item.addItem(self.selection_box)
            self.plot_item.addItem(self.marker_symbol)
            self.plot_item.addItem(self.label)
            # Dragging is handled by DraggableScatterPlotItem callbacks (set up earlier)

        # Store reference traces for interpolation
        self.traces: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

        # Track last position for updates
        self._last_frequency = 0.0
        self._updating = False
        self._dragging = False  # Track if triangle is being dragged
        self._drag_start_pos = None

    def set_marker_number(self, marker_num: int):
        """Update marker number and label."""
        self.marker_num = marker_num
        self.label.setText(f'M{marker_num}')

    def set_position(self, frequency: float):
        """Set marker position to specific frequency."""
        self._updating = True
        if self.coupled:
            self.line.setPos(frequency)
        self._last_frequency = frequency
        self._update_symbol_position()
        self._updating = False

    def get_position(self) -> float:
        """Get current marker frequency position."""
        if self.coupled:
            return self.line.value()
        else:
            return self._last_frequency

    def _update_symbol_position(self):
        """Update marker positions based on mode."""
        if self.coupled:
            freq = self.line.value()
        else:
            freq = self._last_frequency

        # Get Y value from trace data (interpolated)
        y_value = None
        if self.traces:
            # For uncoupled mode, use target trace; for coupled, use first trace (for label positioning)
            if not self.coupled and self.target_trace and self.target_trace in self.traces:
                trace_id = self.target_trace
            else:
                trace_id = list(self.traces.keys())[0]

            freq_array, x_data, y_data = self.traces[trace_id]

            # Check if frequency is within range
            if freq_array[0] <= freq <= freq_array[-1]:
                # Interpolate Y value from trace
                y_value = np.interp(freq, freq_array, y_data)

        # Only update if we have valid trace data
        if y_value is not None:
            if self.coupled:
                # Vertical marker mode: only update label near the line
                view_range = self.plot_item.viewRange()
                y_range = view_range[1]
                # Position label near top of view
                label_y = y_range[1] - (y_range[1] - y_range[0]) * 0.05
                self.label.setPos(freq, label_y)
                if self.visible:
                    self.label.setVisible(True)
            else:
                # Triangle marker mode: update symbol and label
                # Position triangle so VERTEX (not center) is on the trace
                # For 't' symbol pointing down, the vertex is at the bottom
                # We need to offset the position upward to place vertex on trace
                view_range = self.plot_item.viewRange()
                y_range = view_range[1]
                y_span = y_range[1] - y_range[0]

                # Offset for triangle height (in data coordinates)
                # The triangle size is 12 pixels, so we convert pixel offset to data offset
                # Get the view's pixel height and convert
                view_box = self.plot_item.getViewBox()
                view_height_pixels = view_box.size().height()
                if view_height_pixels > 0:
                    triangle_height_pixels = 12 * 0.866  # Height of equilateral triangle (approx)
                    pixel_to_data = y_span / view_height_pixels
                    triangle_offset = triangle_height_pixels * pixel_to_data / 2  # Offset to center->vertex
                else:
                    triangle_offset = y_span * 0.01  # Fallback: 1% of range

                # Position symbol with offset so vertex touches trace
                symbol_y = y_value + triangle_offset
                self.marker_symbol.setData(pos=[(freq, symbol_y)])

                # Update selection box position (same as symbol)
                if hasattr(self, 'selection_box'):
                    self.selection_box.setData(pos=[(freq, symbol_y)])

                # Position label just above the triangle
                # The triangle base is at symbol_y + triangle_offset (top of triangle)
                # Add offset to put label further above the base
                label_y = symbol_y + triangle_offset * 0.6  # More offset for better visibility
                self.label.setPos(freq, label_y)
                self.label.setPos(freq, label_y)

                # Ensure symbol and label are visible if marker is visible
                if self.visible:
                    self.marker_symbol.setVisible(True)
                    self.label.setVisible(True)
        else:
            # No trace data - hide symbol and label to prevent axis expansion
            if not self.coupled:
                self.marker_symbol.setData(pos=[])  # Empty data hides the symbol
            self.label.setVisible(False)

    def _on_line_moved(self):
        """Handle marker line movement."""
        if not self._updating:
            self._update_symbol_position()

    def _on_move_finished(self):
        """Handle when marker movement is finished."""
        new_freq = self.line.value()
        if new_freq != self._last_frequency:
            self._last_frequency = new_freq
            # Emit signal (to be connected by MarkerController)

    def _on_drag_press(self, event):
        """Handle mouse press on triangle - start dragging and select marker."""
        if not self.coupled:
            # Trigger selection callback
            if self.selection_callback:
                self.selection_callback(self.marker_num)

            # Show selection box around triangle
            self.selection_box.setVisible(True)
            self._dragging = True

            # Disable ViewBox panning during drag
            view_box = self.plot_item.getViewBox()
            self._original_mouse_enabled = (
                view_box.state['mouseEnabled'][0],
                view_box.state['mouseEnabled'][1]
            )
            view_box.setMouseEnabled(x=False, y=False)

    def _on_drag_move(self, event):
        """Handle mouse move - drag the triangle."""
        if not self.coupled and self._dragging:
            # Convert scene position to data coordinates
            view_box = self.plot_item.getViewBox()
            scene_pos = event.scenePos()

            if view_box.sceneBoundingRect().contains(scene_pos):
                mouse_point = view_box.mapSceneToView(scene_pos)
                new_freq = mouse_point.x()

                # Constrain to trace frequency range
                if self.traces:
                    trace_id = self.target_trace if self.target_trace in self.traces else list(self.traces.keys())[0]
                    freq_array, _, _ = self.traces[trace_id]
                    new_freq = np.clip(new_freq, freq_array[0], freq_array[-1])

                # Update marker position
                self._last_frequency = new_freq
                self._update_symbol_position()

    def _on_drag_release(self, event):
        """Handle mouse release - stop dragging."""
        if not self.coupled and self._dragging:
            self._dragging = False

            # Restore selection box based on selection state (not just hide it)
            if hasattr(self, 'selection_box'):
                self.selection_box.setVisible(self._selected)

            # Re-enable ViewBox mouse interaction
            view_box = self.plot_item.getViewBox()
            if hasattr(self, '_original_mouse_enabled'):
                view_box.setMouseEnabled(
                    x=self._original_mouse_enabled[0],
                    y=self._original_mouse_enabled[1]
                )

    def _on_context_menu(self, event):
        """Handle right-click context menu."""
        # Create context menu
        menu = QMenu()

        # Always add Remove action
        remove_action = QAction("Remove Marker", menu)
        remove_action.triggered.connect(lambda: self._context_menu_remove())
        menu.addAction(remove_action)

        # For uncoupled (triangle) markers, add Peak, Min, and Move to Frequency
        if not self.coupled:
            menu.addSeparator()
            peak_action = QAction("Move to Peak", menu)
            peak_action.triggered.connect(lambda: self._context_menu_peak())
            menu.addAction(peak_action)

            min_action = QAction("Move to Min", menu)
            min_action.triggered.connect(lambda: self._context_menu_min())
            menu.addAction(min_action)

            menu.addSeparator()
            move_freq_action = QAction("Move to Frequency...", menu)
            move_freq_action.triggered.connect(lambda: self._context_menu_move_to_frequency())
            menu.addAction(move_freq_action)

        # Show menu at cursor position
        if hasattr(event, 'screenPos'):
            # screenPos() already returns QPoint
            menu.exec(event.screenPos())

    def _context_menu_remove(self):
        """Handle Remove action from context menu."""
        # Trigger removal through controller
        if hasattr(self, '_context_menu_controller'):
            self._context_menu_controller.remove_marker(str(self.marker_num))

    def _context_menu_peak(self):
        """Handle Peak action from context menu."""
        if hasattr(self, '_context_menu_controller'):
            self._context_menu_controller.move_marker_to_peak(str(self.marker_num))

    def _context_menu_min(self):
        """Handle Min action from context menu."""
        if hasattr(self, '_context_menu_controller'):
            self._context_menu_controller.move_marker_to_minimum(str(self.marker_num))

    def _context_menu_move_to_frequency(self):
        """Handle Move to Frequency action from context menu."""
        if hasattr(self, '_context_menu_controller'):
            self._context_menu_controller.edit_marker_frequency(str(self.marker_num))

    def add_trace_data(self, trace_id: str, frequency: np.ndarray,
                       x_data: np.ndarray, y_data: np.ndarray):
        """Add trace data for interpolation."""
        self.traces[trace_id] = (frequency, x_data, y_data)
        # Make label visible now that we have data
        self.label.setVisible(self.visible)
        # Update position
        self._update_symbol_position()

    def remove_trace_data(self, trace_id: str):
        """Remove trace data."""
        if trace_id in self.traces:
            del self.traces[trace_id]

    def get_interpolated_values(self) -> Dict[str, MarkerData]:
        """Get interpolated values at current marker position.

        For coupled markers: returns data for all traces.
        For uncoupled markers: returns data only for target trace.

        Note: y_data contains the actual plotted values (dB, degrees, etc.)
        depending on the current plot type, not complex S-parameters.
        """
        marker_freq = self.get_position()
        results = {}

        # Determine which traces to process
        if not self.coupled and self.target_trace:
            # Uncoupled mode: only process target trace
            traces_to_process = {self.target_trace: self.traces[self.target_trace]} \
                if self.target_trace in self.traces else {}
        else:
            # Coupled mode: process all traces
            traces_to_process = self.traces

        for trace_id, (freq_array, x_data, y_data) in traces_to_process.items():
            # Find interpolation points
            if marker_freq < freq_array[0] or marker_freq > freq_array[-1]:
                continue  # Outside frequency range

            # Linear interpolation
            # x_data is typically frequency (same as freq_array)
            # y_data is the actual plotted value (magnitude dB, phase degrees, etc.)
            x_value = np.interp(marker_freq, freq_array, x_data)
            y_value = np.interp(marker_freq, freq_array, y_data)

            # Store the plotted Y value as position_y for direct display
            # Don't try to interpret as complex - just use the actual plot value
            results[trace_id] = MarkerData(
                marker_id=str(self.marker_num),
                trace_id=trace_id,
                frequency=marker_freq,
                value=complex(0, 0),  # Not meaningful for all plot types
                magnitude_db=0.0,  # Not meaningful for all plot types
                phase_deg=0.0,  # Not meaningful for all plot types
                real=0.0,  # Not meaningful for all plot types
                imag=0.0,  # Not meaningful for all plot types
                position_x=x_value,  # X coordinate (frequency)
                position_y=y_value  # Y coordinate (the actual plotted value)
            )

        return results

    def find_peak(self, trace_id: Optional[str] = None) -> Optional[float]:
        """
        Find maximum value in trace data (uses actual plotted y_data).

        Args:
            trace_id: Specific trace to search, or None for first trace (or target trace if uncoupled)

        Returns:
            Frequency of maximum, or None if no data
        """
        if not self.traces:
            return None

        # For uncoupled markers, use target trace by default
        if trace_id is None and not self.coupled and self.target_trace:
            search_trace = self.target_trace
        else:
            search_trace = trace_id if trace_id and trace_id in self.traces else list(self.traces.keys())[0]

        if search_trace not in self.traces:
            return None

        freq_array, x_data, y_data = self.traces[search_trace]

        # Use the actual plotted y_data (works for Magnitude, Phase, Group Delay, etc.)
        max_idx = np.argmax(y_data)

        return float(freq_array[max_idx])

    def find_minimum(self, trace_id: Optional[str] = None) -> Optional[float]:
        """
        Find minimum value in trace data (uses actual plotted y_data).

        Args:
            trace_id: Specific trace to search, or None for first trace (or target trace if uncoupled)

        Returns:
            Frequency of minimum, or None if no data
        """
        if not self.traces:
            return None

        # For uncoupled markers, use target trace by default
        if trace_id is None and not self.coupled and self.target_trace:
            search_trace = self.target_trace
        else:
            search_trace = trace_id if trace_id and trace_id in self.traces else list(self.traces.keys())[0]

        if search_trace not in self.traces:
            return None

        freq_array, x_data, y_data = self.traces[search_trace]

        # Use the actual plotted y_data (works for Magnitude, Phase, Group Delay, etc.)
        min_idx = np.argmin(y_data)

        return float(freq_array[min_idx])

    def set_selected(self, selected: bool):
        """Set marker selection state and update visual feedback."""
        self._selected = selected
        if self.coupled:
            # For vertical markers, change line appearance to show selection
            if selected:
                # Make line thicker and solid when selected
                self.line.setPen(pg.mkPen(self.color, width=2, style=Qt.PenStyle.SolidLine))
                self.line.setHoverPen(pg.mkPen(self.color, width=3, style=Qt.PenStyle.SolidLine))
            else:
                # Restore original dashed line
                self.line.setPen(pg.mkPen(self.color, width=1, style=Qt.PenStyle.DashLine))
                self.line.setHoverPen(pg.mkPen(self.color, width=2, style=Qt.PenStyle.DashLine))
        else:
            # For triangle markers, show selection box when selected (but not when dragging)
            if selected and not self._dragging:
                self.selection_box.setVisible(True)
            elif not self._dragging:
                self.selection_box.setVisible(False)

    def set_visible(self, visible: bool):
        """Set marker visibility."""
        self.visible = visible
        if self.coupled:
            # Vertical marker: show line and label
            self.line.setVisible(visible)
            self.label.setVisible(visible)
        else:
            # Triangle marker: show symbol and label
            self.marker_symbol.setVisible(visible)
            self.label.setVisible(visible)
            # Selection box visibility depends on selection state and drag state
            if hasattr(self, 'selection_box'):
                if not self._dragging:
                    self.selection_box.setVisible(visible and self._selected)

    def remove(self):
        """Remove marker from plot."""
        if self.coupled:
            # Vertical marker: remove line and label
            self.plot_item.removeItem(self.line)
            self.plot_item.removeItem(self.label)
        else:
            # Triangle marker: remove symbol, selection box, and label
            self.plot_item.removeItem(self.marker_symbol)
            if hasattr(self, 'selection_box'):
                self.plot_item.removeItem(self.selection_box)
            self.plot_item.removeItem(self.label)

    def update_view(self):
        """Update marker display after view changes."""
        self._update_symbol_position()


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


class MarkerInfoOverlay(pg.GraphicsWidget):
    """
    Movable, transparent overlay showing marker information on the chart.
    Similar to legend but specifically for marker values.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QGraphicsTextItem

        # Single text item for all content
        self.text_item = QGraphicsTextItem(self)
        text_font = QFont("Courier New")  # Monospace font for alignment
        text_font.setPointSize(9)
        self.text_item.setFont(text_font)
        self.text_item.setDefaultTextColor(QColor("#4A90E2"))

        # Dimensions
        self.padding = 5
        self.min_width = 10
        self.min_height = 10

        # Track if user has manually positioned the overlay
        self.user_positioned = False

        # Make it movable and ignore transformations (so it doesn't scale with plot)
        self.setFlag(self.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(self.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(self.GraphicsItemFlag.ItemIgnoresTransformations, True)

    def itemChange(self, change, value):
        """Track when user manually moves the overlay."""
        if change == self.GraphicsItemChange.ItemPositionHasChanged:
            # User has moved the overlay
            self.user_positioned = True
        return super().itemChange(change, value)

    def boundingRect(self):
        """Return the bounding rectangle."""
        from PySide6.QtCore import QRectF
        return QRectF(0, 0, self.min_width, self.min_height)

    def paint(self, p, *args):
        """Custom paint to draw transparent background (like legend)."""
        # Fully transparent background - no background at all
        # Text is rendered by the QGraphicsTextItem, we don't need to paint anything
        pass

    def update_markers(self, marker_data_list):
        """
        Update displayed marker information.

        Args:
            marker_data_list: List of dicts with marker info
                             [{'marker': 'M1', 'trace': 'S11', 'freq': '1.0 GHz', 'value': '-20.5 dB'}, ...]
        """
        if not marker_data_list:
            self.text_item.setPlainText("")
            self.min_width = 10
            self.min_height = 10
            self.prepareGeometryChange()
            return

        # Build text with proper spacing (single line per marker)
        lines = []
        for data in marker_data_list:
            # Use single line: "M1: 1.000 GHz, -20.543 dB (S11)"
            line = f"{data['marker']}: {data['freq']}, {data['value']} ({data['trace']})"
            lines.append(line)

        text = '\n'.join(lines)
        self.text_item.setPlainText(text)

        # Update size based on text bounds
        text_bounds = self.text_item.boundingRect()
        self.min_width = text_bounds.width() + 2 * self.padding
        self.min_height = text_bounds.height() + 2 * self.padding

        # Position text with padding
        self.text_item.setPos(self.padding, self.padding)

        # Force repaint
        self.prepareGeometryChange()
        self.update()


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
        # self.dataset: Optional[Dataset] = None
        self.plot_type_name = "Magnitude"  # Current plot type for value display (Magnitude, Phase, Group Delay, etc.)
        self.frequency_unit = "Hz"  # Frequency unit for display (Hz, with auto-scaling)

        # Cache trace data for newly created markers
        self._trace_data_cache: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

        # Marker mode: False for uncoupled (triangle, default), True for coupled (vertical)
        self.coupled_mode = False

        # Marker colors
        self.marker_colors = DEFAULT_MARKER_COLORS
        self.next_marker_id = 1

        # Marker info overlay (will be created when plot_item is set)
        self.marker_info_overlay: Optional[MarkerInfoOverlay] = None
        self.show_overlay = True  # Default to shown

        self._setup_ui()

        # Update timer for marker values
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_marker_values)
        self.update_timer.timeout.connect(self._update_marker_overlay)
        self.update_timer.start(100)  # 10 Hz update rate

    def _setup_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Marker table with simplified columns
        self.marker_table = QTableWidget()
        self.marker_table.setColumnCount(5)
        self.marker_table.setHorizontalHeaderLabels([
            "Marker", "Trace", "Frequency", "Value", "Visible"
        ])

        # Enable double-click to edit frequency
        self.marker_table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # Enable single-click to select marker and show selection box
        self.marker_table.itemSelectionChanged.connect(self._on_table_selection_changed)

        # Set column widths
        header = self.marker_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Marker
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Trace
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Frequency
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Value
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Visible

        self.marker_table.setColumnWidth(0, 60)  # Marker
        self.marker_table.setColumnWidth(2, 120)  # Frequency
        self.marker_table.setColumnWidth(3, 100)  # Value
        self.marker_table.setColumnWidth(4, 60)   # Visible

        self.marker_table.setSelectionBehavior(QTableWidget.SelectRows)

        # Hide table by default
        self.marker_table.hide()

        layout.addWidget(self.marker_table)

    def set_chart(self, plot_item: pg.PlotItem, chart_type: str = "cartesian"):
        """Set the target chart for marker interactions."""
        self.plot_item = plot_item
        self.chart_type = chart_type

        # Create marker info overlay
        if chart_type == "cartesian" and not self.marker_info_overlay:
            self.marker_info_overlay = MarkerInfoOverlay()
            # Add to view box so it doesn't affect axis scaling
            view_box = plot_item.getViewBox()
            self.marker_info_overlay.setParentItem(view_box)
            # Position in top-right corner
            # We'll update position dynamically since view coordinates can change
            self._update_overlay_position()
            self.marker_info_overlay.setVisible(self.show_overlay)

    def set_plot_type(self, plot_type_name: str):
        """Set the current plot type for value display (e.g., 'Magnitude', 'Phase', 'Group Delay')."""
        self.plot_type_name = plot_type_name
        # Update the table header
        self.marker_table.setHorizontalHeaderLabels([
            "Marker", "Trace", "Frequency", plot_type_name, "Visible"
        ])
        self.clear_markers()  # Clear existing markers when switching charts

    def add_marker(self, target_trace: Optional[str] = None) -> str:
        """Add a new marker to the chart.

        Args:
            target_trace: For uncoupled mode, the trace to attach marker to.
                         For coupled mode, this is ignored.

        Returns:
            Marker ID
        """
        if not self.plot_item:
            return ""

        marker_id = str(self.next_marker_id)
        # color = self.marker_colors[(self.next_marker_id - 1) % len(self.marker_colors)]
        # use single color for all markers
        color = "#4A90E2"

        if self.chart_type == "cartesian":
            marker = InteractiveMarker(
                self.next_marker_id,
                self.plot_item,
                color,
                coupled=self.coupled_mode,
                target_trace=target_trace,
                selection_callback=self._on_marker_selected
            )

            # Set controller reference for context menu
            marker._context_menu_controller = self
        else:  # Smith chart
            marker = SmithMarker(marker_id, self.plot_item, color)
            marker.set_position(0.0, 0.0)  # Center of Smith chart

        self.markers[marker_id] = marker
        self.next_marker_id += 1

        # Add existing trace data to new marker
        for trace_id, (frequency, x_data, y_data) in self._trace_data_cache.items():
            marker.add_trace_data(trace_id, frequency, x_data, y_data)

        self._update_table()
        self.marker_added.emit(marker_id)

        return marker_id

    def remove_marker(self, marker_id: str):
        """Remove a marker by ID."""
        if marker_id in self.markers:
            self.markers[marker_id].remove()
            del self.markers[marker_id]
            self.renumber_markers()  # Renumber remaining markers
            self.marker_removed.emit(marker_id)

    def remove_selected_marker(self):
        """Remove currently selected marker."""
        current_row = self.marker_table.currentRow()
        if current_row >= 0:
            marker_id = self.marker_table.item(current_row, 0).text().replace("M", "")
            self.remove_marker(marker_id)

    def clear_markers(self):
        """Remove all markers."""
        # Remove all markers at once without renumbering after each
        marker_ids = list(self.markers.keys())
        for marker_id in marker_ids:
            if marker_id in self.markers:
                self.markers[marker_id].remove()
                del self.markers[marker_id]
                self.marker_removed.emit(marker_id)

        # Reset next_marker_id
        self.next_marker_id = 1

        # Update table once at the end
        self._update_table()

    def add_trace_data(self, trace_id: str, frequency: np.ndarray, x_data: np.ndarray, y_data: np.ndarray):
        """Add trace data to all markers for interpolation."""
        # Cache trace data for future markers
        self._trace_data_cache[trace_id] = (frequency, x_data, y_data)

        # Add to all existing markers
        for marker in self.markers.values():
            marker.add_trace_data(trace_id, frequency, x_data, y_data)
            # Update marker symbol position now that it has data
            if isinstance(marker, InteractiveMarker):
                marker._update_symbol_position()

        # Update table structure to show new trace
        self._update_table()

    def remove_trace_data(self, trace_id: str):
        """Remove trace data from all markers."""
        # Remove from cache
        if trace_id in self._trace_data_cache:
            del self._trace_data_cache[trace_id]

        # Remove from all markers
        for marker in self.markers.values():
            marker.remove_trace_data(trace_id)

    def rename_trace_label(self, old_label: str, new_label: str):
        """
        Rename a trace label in all markers, preserving order and data.

        Args:
            old_label: Current trace label
            new_label: New trace label
        """
        # Update cache - need to maintain order
        if old_label in self._trace_data_cache:
            # Rebuild the dict to maintain order
            new_cache = {}
            for key, value in self._trace_data_cache.items():
                if key == old_label:
                    new_cache[new_label] = value
                else:
                    new_cache[key] = value
            self._trace_data_cache = new_cache

        # Update all markers
        for marker in self.markers.values():
            if isinstance(marker, InteractiveMarker):
                # Update the marker's traces dictionary, preserving order
                if old_label in marker.traces:
                    # Rebuild traces dict to maintain order
                    new_traces = {}
                    for key, value in marker.traces.items():
                        if key == old_label:
                            new_traces[new_label] = value
                        else:
                            new_traces[key] = value
                    marker.traces = new_traces

                    # Update target_trace if it matches the old label
                    if marker.target_trace == old_label:
                        marker.target_trace = new_label

        # Update table to reflect new labels
        self._update_table()

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
        # Count total rows needed (markers * traces, but for uncoupled only show target trace)
        total_rows = 0
        for marker_id, marker in self.markers.items():
            if not marker.coupled and marker.target_trace:
                # Uncoupled: only one row per marker
                total_rows += 1
            else:
                # Coupled: one row per trace
                total_rows += max(1, len(marker.traces))

        self.marker_table.setRowCount(total_rows)

        row = 0
        for marker_id, marker in self.markers.items():
            if not marker.traces:
                # Show marker with no trace data
                self.marker_table.setItem(row, 0, QTableWidgetItem(f"M{marker_id}"))
                for col in range(1, 4):
                    self.marker_table.setItem(row, col, QTableWidgetItem("--"))

                # Visibility checkbox
                checkbox = QCheckBox()
                checkbox.setChecked(marker.visible)
                checkbox.toggled.connect(lambda checked, mid=marker_id: self._on_visibility_changed(mid, checked))
                self.marker_table.setCellWidget(row, 4, checkbox)
                row += 1
            elif not marker.coupled and marker.target_trace:
                # Uncoupled mode: only show target trace
                self.marker_table.setItem(row, 0, QTableWidgetItem(f"M{marker_id}"))
                self.marker_table.setItem(row, 1, QTableWidgetItem(marker.target_trace))

                # Values will be filled by _update_table_values
                for col in range(2, 4):
                    self.marker_table.setItem(row, col, QTableWidgetItem("--"))

                # Visibility checkbox
                checkbox = QCheckBox()
                checkbox.setChecked(marker.visible)
                checkbox.toggled.connect(
                    lambda checked, mid=marker_id: self._on_visibility_changed(mid, checked))
                self.marker_table.setCellWidget(row, 4, checkbox)
                row += 1
            else:
                # Coupled mode: show all traces
                for i, trace_id in enumerate(marker.traces.keys()):
                    if i == 0:
                        self.marker_table.setItem(row, 0, QTableWidgetItem(f"M{marker_id}"))
                    else:
                        self.marker_table.setItem(row, 0, QTableWidgetItem(""))

                    self.marker_table.setItem(row, 1, QTableWidgetItem(trace_id))

                    # Values will be filled by _update_table_values
                    for col in range(2, 4):
                        self.marker_table.setItem(row, col, QTableWidgetItem("--"))

                    # Visibility checkbox (only on first row for each marker)
                    if i == 0:
                        checkbox = QCheckBox()
                        checkbox.setChecked(marker.visible)
                        checkbox.toggled.connect(
                            lambda checked, mid=marker_id: self._on_visibility_changed(mid, checked))
                        self.marker_table.setCellWidget(row, 4, checkbox)
                    else:
                        self.marker_table.setItem(row, 4, QTableWidgetItem(""))

                    row += 1

    def _update_table_values(self, all_marker_data: Dict[str, Dict[str, MarkerData]]):
        """Update marker table with current values based on plot type."""
        row = 0
        for marker_id, marker in self.markers.items():
            marker_data = all_marker_data.get(marker_id, {})

            if not marker_data:
                # Skip to appropriate number of rows
                if not marker.coupled and marker.target_trace:
                    row += 1
                else:
                    row += max(1, len(marker.traces))
                continue

            # For uncoupled markers, only show target trace
            if not marker.coupled and marker.target_trace:
                if marker.target_trace in marker_data:
                    data = marker_data[marker.target_trace]
                    self._set_table_row_values(row, data)
                row += 1
            else:
                # For coupled markers, show all traces
                for trace_id, data in marker_data.items():
                    self._set_table_row_values(row, data)
                    row += 1

    def _set_table_row_values(self, row: int, data: MarkerData):
        """Set values for a single table row - shows the actual plotted Y value."""
        # Update frequency
        freq_text = (f"{data.frequency/1e9:.3f} GHz" if data.frequency >= 1e9
                     else f"{data.frequency/1e6:.1f} MHz")
        self.marker_table.setItem(row, 2, QTableWidgetItem(freq_text))

        # Update value - just show the Y value being plotted
        # This works for all plot types (magnitude dB, phase degrees, group delay, etc.)
        value_text = f"{data.position_y:.3f}"
        self.marker_table.setItem(row, 3, QTableWidgetItem(value_text))

    def _on_visibility_changed(self, marker_id: str, visible: bool):
        """Handle marker visibility change."""
        if marker_id in self.markers:
            self.markers[marker_id].set_visible(visible)

    def renumber_markers(self):
        """
        Renumber all markers sequentially after deletion.

        Maintains marker order and updates all displays accordingly.
        """
        if not self.markers:
            return

        # Get marker IDs in order
        marker_ids = sorted(self.markers.keys(), key=lambda x: int(x))

        # Create new marker dict with renumbered markers
        new_markers = {}
        for new_num, old_id in enumerate(marker_ids, start=1):
            marker = self.markers[old_id]
            marker.set_marker_number(new_num)
            new_markers[str(new_num)] = marker

        # Replace markers dict
        self.markers = new_markers

        # Update next_marker_id
        self.next_marker_id = len(self.markers) + 1

        # Update table display
        self._update_table()

    def add_marker_at_frequency(self, frequency: float, target_trace: Optional[str] = None) -> str:
        """
        Add a marker at a specific frequency.

        Args:
            frequency: Frequency position in Hz
            target_trace: For uncoupled mode, which trace to attach to

        Returns:
            Marker ID
        """
        marker_id = self.add_marker(target_trace=target_trace)
        if marker_id and marker_id in self.markers:
            self.markers[marker_id].set_position(frequency)
        return marker_id

    def move_marker_to_peak(self, marker_id: str, trace_id: Optional[str] = None):
        """
        Move marker to peak (maximum) of trace.

        Args:
            marker_id: Marker to move
            trace_id: Specific trace to search, or None for first trace
        """
        if marker_id not in self.markers:
            return

        marker = self.markers[marker_id]
        peak_freq = marker.find_peak(trace_id)

        if peak_freq is not None:
            marker.set_position(peak_freq)

    def move_marker_to_minimum(self, marker_id: str, trace_id: Optional[str] = None):
        """
        Move marker to minimum of trace.

        Args:
            marker_id: Marker to move
            trace_id: Specific trace to search, or None for first trace
        """
        if marker_id not in self.markers:
            return

        marker = self.markers[marker_id]
        min_freq = marker.find_minimum(trace_id)

        if min_freq is not None:
            marker.set_position(min_freq)

    def edit_marker_frequency(self, marker_id: str):
        """
        Show dialog to edit marker frequency.
        If the frequency is out of range, clamps to the trace's min/max frequency.
        Uses appropriate frequency unit (GHz, MHz, kHz, Hz) based on the frequency range.

        Args:
            marker_id: Marker to edit
        """
        if marker_id not in self.markers:
            return

        marker = self.markers[marker_id]
        current_freq = marker.get_position()

        # Get frequency range from marker's trace data
        min_freq_hz = 0.0
        max_freq_hz = 1000e9  # 1000 GHz default

        if marker.traces:
            # Get the first available trace (or target trace for uncoupled markers)
            if marker.target_trace and marker.target_trace in marker.traces:
                trace_id = marker.target_trace
            else:
                trace_id = list(marker.traces.keys())[0]

            freq_array, _, _ = marker.traces[trace_id]
            min_freq_hz = freq_array[0]
            max_freq_hz = freq_array[-1]

        # Determine appropriate scale based on the frequency range
        # Use the max frequency to determine the unit
        scale_factor, unit_label = self._get_frequency_scale(max_freq_hz)

        # Convert current frequency and range to display unit
        current_freq_scaled = current_freq / scale_factor
        min_freq_scaled = min_freq_hz / scale_factor
        max_freq_scaled = max_freq_hz / scale_factor

        # Determine decimal places based on unit
        decimals = 3 if unit_label in ["GHz", "MHz"] else (1 if unit_label == "kHz" else 0)

        freq_scaled, ok = QInputDialog.getDouble(
            self,
            f"Edit Marker M{marker_id} Frequency",
            f"Frequency ({unit_label}):\n(Range: {min_freq_scaled:.{decimals}f} - {max_freq_scaled:.{decimals}f})",
            current_freq_scaled,
            0.0,
            max_freq_scaled * 10,  # Allow some headroom
            decimals
        )

        if ok:
            # Convert back to Hz
            new_freq = freq_scaled * scale_factor

            # Clamp to trace frequency range
            if marker.traces:
                if marker.target_trace and marker.target_trace in marker.traces:
                    trace_id = marker.target_trace
                else:
                    trace_id = list(marker.traces.keys())[0]

                freq_array, _, _ = marker.traces[trace_id]
                new_freq = np.clip(new_freq, freq_array[0], freq_array[-1])

            marker.set_position(new_freq)

    def _get_frequency_scale(self, freq_hz: float) -> Tuple[float, str]:
        """
        Determine appropriate frequency scale and unit based on value.

        Args:
            freq_hz: Frequency in Hz

        Returns:
            Tuple of (scale_factor, unit_label)
        """
        # Determine scale based on frequency magnitude
        if abs(freq_hz) >= 1e9:
            return 1e9, "GHz"
        elif abs(freq_hz) >= 1e6:
            return 1e6, "MHz"
        elif abs(freq_hz) >= 1e3:
            return 1e3, "kHz"
        else:
            return 1.0, "Hz"

    def get_marker_count(self) -> int:
        """Get the number of active markers."""
        return len(self.markers)

    def get_marker_by_number(self, marker_num: int) -> Optional[Any]:
        """Get marker by its display number."""
        marker_id = str(marker_num)
        return self.markers.get(marker_id)

    def update_view(self):
        """Update all markers after view changes (zoom, pan, etc.)."""
        for marker in self.markers.values():
            if hasattr(marker, 'update_view'):
                marker.update_view()

    def _on_cell_double_clicked(self, row: int, column: int):
        """Handle double-click on table cell - edit frequency if frequency column."""
        if column == 2:  # Frequency column
            marker_id = self.marker_table.item(row, 0).text().replace("M", "")
            self.edit_marker_frequency(marker_id)

    def set_coupled_mode(self, coupled: bool):
        """Set marker mode (vertical/triangle)."""
        self.coupled_mode = coupled
        # Note: Existing markers keep their mode. Only new markers use the new mode.

    def set_overlay_visibility(self, visible: bool):
        """Set overlay visibility."""
        self.show_overlay = visible
        if self.marker_info_overlay:
            self.marker_info_overlay.setVisible(visible)
            if visible:
                self._update_overlay_position()
                self._update_marker_overlay()

    def set_table_visibility(self, visible: bool):
        """Set marker table visibility."""
        if visible:
            self.marker_table.show()
        else:
            self.marker_table.hide()

    def _update_overlay_position(self):
        """Update overlay position to center of view initially."""
        if not self.marker_info_overlay or not self.plot_item:
            return

        # Don't reposition if user has manually moved it
        if self.marker_info_overlay.user_positioned:
            return

        view_box = self.plot_item.getViewBox()
        if view_box:
            # With ItemIgnoresTransformations, we work in scene/pixel coordinates
            # Get the view box geometry in scene coordinates
            vb_rect = view_box.sceneBoundingRect()

            # Position at center of view
            overlay_width = self.marker_info_overlay.min_width
            overlay_height = self.marker_info_overlay.min_height
            x_pos = vb_rect.center().x() - overlay_width / 2
            y_pos = vb_rect.center().y() - overlay_height / 2

            # Map to view box local coordinates
            pos = view_box.mapFromScene(x_pos, y_pos)
            self.marker_info_overlay.setPos(pos)

    def _update_marker_overlay(self):
        """Update marker info overlay with current marker data."""
        if not self.marker_info_overlay or not self.show_overlay:
            return

        # Collect marker data
        marker_data_list = []
        for marker_id in sorted(self.markers.keys(), key=lambda x: int(x)):
            marker = self.markers[marker_id]
            if isinstance(marker, InteractiveMarker) and marker.visible:
                # Get marker frequency
                freq = marker.get_position()
                freq_ghz = freq / 1e9

                # Get traces to display
                traces_to_show = []
                if marker.coupled:
                    # Vertical marker: show all traces
                    traces_to_show = list(marker.traces.keys())
                else:
                    # Triangle marker: show only target trace
                    if marker.target_trace and marker.target_trace in marker.traces:
                        traces_to_show = [marker.target_trace]

                # Add entry for each trace
                for trace_id in traces_to_show:
                    if trace_id in marker.traces:
                        freq_array, x_data, y_data = marker.traces[trace_id]
                        # Interpolate value at marker frequency
                        y_value = np.interp(freq, freq_array, y_data)

                        marker_data_list.append({
                            'marker': f"M{marker_id}",
                            'trace': trace_id,
                            'freq': f"{freq_ghz:.3f} GHz",
                            'value': f"{y_value:.3f}"
                        })

        # Update overlay
        self.marker_info_overlay.update_markers(marker_data_list)
        # Reposition in case size changed
        self._update_overlay_position()

    def _on_marker_selected(self, marker_num: int):
        """Handle marker selection from click with toggle support."""
        marker_id = str(marker_num)

        # Check if this marker is already selected (toggle feature)
        is_already_selected = False
        if marker_id in self.markers and isinstance(self.markers[marker_id], InteractiveMarker):
            is_already_selected = self.markers[marker_id]._selected

        # First, deselect all markers
        for marker in self.markers.values():
            if isinstance(marker, InteractiveMarker):
                marker.set_selected(False)

        # If marker was not already selected, select it (toggle behavior)
        if not is_already_selected:
            if marker_id in self.markers and isinstance(self.markers[marker_id], InteractiveMarker):
                self.markers[marker_id].set_selected(True)

        # Find and select/deselect the row in the table
        for row in range(self.marker_table.rowCount()):
            item = self.marker_table.item(row, 0)
            if item and item.text() == f"M{marker_num}":
                # Block signals to avoid triggering _on_table_selection_changed
                self.marker_table.blockSignals(True)

                if not is_already_selected:
                    # Select the row
                    self.marker_table.selectRow(row)
                else:
                    # Deselect the row (clear selection)
                    self.marker_table.clearSelection()

                self.marker_table.blockSignals(False)

                # Force table to update display - try multiple methods
                self.marker_table.scrollToItem(item)
                self.marker_table.viewport().update()
                self.marker_table.repaint()  # Force immediate repaint
                # Process events to ensure UI updates
                from PySide6.QtCore import QCoreApplication
                QCoreApplication.processEvents()
                break

    def _on_table_selection_changed(self):
        """Handle table row selection - update marker selection visuals."""
        # First, deselect all markers
        for marker in self.markers.values():
            if isinstance(marker, InteractiveMarker):
                marker.set_selected(False)

        # Then select markers for selected rows
        selected_rows = self.marker_table.selectionModel().selectedRows()
        for index in selected_rows:
            row = index.row()
            item = self.marker_table.item(row, 0)
            if item:
                marker_num_text = item.text().replace("M", "")
                marker_id = marker_num_text
                if marker_id in self.markers and isinstance(self.markers[marker_id], InteractiveMarker):
                    self.markers[marker_id].set_selected(True)

    def export_markers_to_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Export all markers to dictionary format for serialization.

        Returns:
            Dictionary mapping marker_id to marker data dict
        """
        markers_dict = {}

        for marker_id, marker in self.markers.items():
            if isinstance(marker, InteractiveMarker):
                # Get current position and interpolated values
                frequency = marker.get_position()
                marker_data = marker.get_interpolated_values()

                # Use target trace for uncoupled markers, or first trace for coupled
                if marker.target_trace and marker.target_trace in marker_data:
                    trace_id = marker.target_trace
                    data = marker_data[trace_id]
                elif marker_data:
                    trace_id = list(marker_data.keys())[0]
                    data = marker_data[trace_id]
                else:
                    continue  # Skip markers with no data

                # Create marker dict
                markers_dict[marker_id] = {
                    'id': marker_id,
                    'name': f"M{marker.marker_num}",
                    'marker_num': marker.marker_num,
                    'trace_id': trace_id,
                    'target_trace': marker.target_trace,
                    'frequency': frequency,
                    'x_value': data.position_x,
                    'y_value': data.position_y,
                    'coupled': marker.coupled,
                    'visible': marker.visible,
                    'color': marker.color
                }

        return markers_dict

    def import_markers_from_dict(self, markers_dict: Dict[str, Dict[str, Any]]) -> None:
        """
        Import markers from dictionary format (from loaded project).

        Args:
            markers_dict: Dictionary mapping marker_id to marker data dict
        """
        # Clear existing markers first
        self.clear_markers()

        # Sort by marker_num to maintain order
        sorted_markers = sorted(markers_dict.values(), key=lambda m: m.get('marker_num', 0))

        for marker_data in sorted_markers:
            # Get the coupled state for this specific marker
            coupled = marker_data.get('coupled', False)
            target_trace = marker_data.get('target_trace')

            # Temporarily set the controller's coupled_mode to match this marker
            # so that add_marker creates the right type
            original_coupled_mode = self.coupled_mode
            self.coupled_mode = coupled

            # Add marker
            marker_id = self.add_marker(target_trace=target_trace if not coupled else None)

            # Restore original coupled mode
            self.coupled_mode = original_coupled_mode

            if marker_id and marker_id in self.markers:
                marker = self.markers[marker_id]

                # Ensure the marker has the correct coupled state
                marker.coupled = coupled

                # Set position
                frequency = marker_data.get('frequency')
                if frequency is not None:
                    marker.set_position(frequency)

                # Set visibility
                if not marker_data.get('visible', True):
                    marker.set_visible(False)

                # Update marker number to match saved value
                saved_marker_num = marker_data.get('marker_num')
                if saved_marker_num is not None:
                    marker.marker_num = saved_marker_num

        # Update next_marker_id based on highest marker_num
        if sorted_markers:
            max_marker_num = max(m.get('marker_num', 0) for m in sorted_markers)
            self.next_marker_id = max_marker_num + 1

        # Update table to reflect imported markers
        self._update_table()
