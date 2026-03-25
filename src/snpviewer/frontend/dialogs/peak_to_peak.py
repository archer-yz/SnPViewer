"""
Peak-to-peak analysis dialog for chart traces.

Allows selecting one or more traces and calculating min/max/P2P metrics
within a user-defined frequency range.
"""
from __future__ import annotations

import csv
from typing import Dict, Optional, Tuple

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from snpviewer.frontend.plotting.plot_pipelines import compute_peak_to_peak_metrics


class PeakToPeakDialog(QDialog):
    """Dialog for peak-to-peak analysis over a selected frequency range."""

    def __init__(
        self,
        traces: Dict[str, Tuple[str, np.ndarray, np.ndarray]],
        y_axis_label: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._traces = traces
        self._y_axis_label = y_axis_label
        self._updating_range = False

        self.setWindowTitle("Peak-to-Peak Analysis")
        self.resize(860, 560)

        self._setup_ui()
        self._populate_traces()
        self._initialize_range()

    def _setup_ui(self) -> None:
        """Create dialog widgets and layouts."""
        layout = QVBoxLayout(self)

        title = QLabel(
            "Select traces and frequency range, then compute min/max frequencies and peak-to-peak values."
        )
        title.setWordWrap(True)
        layout.addWidget(title)

        top_row = QHBoxLayout()

        traces_group = QGroupBox("Trace Selection")
        traces_layout = QVBoxLayout(traces_group)
        self._trace_list = QListWidget()
        traces_layout.addWidget(self._trace_list)
        top_row.addWidget(traces_group, 1)

        range_group = QGroupBox("Frequency Range")
        range_layout = QVBoxLayout(range_group)

        unit_layout = QFormLayout()
        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["Hz", "kHz", "MHz", "GHz"])
        self._unit_combo.setCurrentText("GHz")
        self._unit_combo.currentTextChanged.connect(self._on_unit_changed)
        unit_layout.addRow("Unit:", self._unit_combo)
        range_layout.addLayout(unit_layout)

        self._start_stop_radio = QRadioButton("Use Start + Stop")
        self._start_stop_radio.setChecked(True)
        self._start_stop_radio.toggled.connect(self._update_mode_enabled_state)
        range_layout.addWidget(self._start_stop_radio)

        start_stop_form = QFormLayout()
        self._start_spin = self._create_freq_spinbox()
        self._stop_spin = self._create_freq_spinbox()
        self._start_spin.valueChanged.connect(self._sync_center_span_from_start_stop)
        self._stop_spin.valueChanged.connect(self._sync_center_span_from_start_stop)
        start_stop_form.addRow("Start:", self._start_spin)
        start_stop_form.addRow("Stop:", self._stop_spin)
        range_layout.addLayout(start_stop_form)

        self._center_span_radio = QRadioButton("Use Center + Span")
        self._center_span_radio.toggled.connect(self._update_mode_enabled_state)
        range_layout.addWidget(self._center_span_radio)

        center_span_form = QFormLayout()
        self._center_spin = self._create_freq_spinbox()
        self._span_spin = self._create_freq_spinbox(minimum=0.0)
        self._center_spin.valueChanged.connect(self._sync_start_stop_from_center_span)
        self._span_spin.valueChanged.connect(self._sync_start_stop_from_center_span)
        center_span_form.addRow("Center:", self._center_spin)
        center_span_form.addRow("Span:", self._span_spin)
        range_layout.addLayout(center_span_form)

        top_row.addWidget(range_group, 1)
        layout.addLayout(top_row)

        self._results_table = QTableWidget(0, 7)
        self._results_table.setHorizontalHeaderLabels(
            [
                "Frequency Range",
                "Trace",
                "Min Value",
                "Min Freq",
                "Max Value",
                "Max Freq",
                "Peak-to-Peak",
            ]
        )
        self._results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._results_table)

        buttons = QHBoxLayout()

        clear_button = QPushButton("Clear Results")
        clear_button.clicked.connect(self._clear_results)
        buttons.addWidget(clear_button)

        export_button = QPushButton("Export CSV")
        export_button.clicked.connect(self._export_results_csv)
        buttons.addWidget(export_button)

        buttons.addStretch()

        analyze_button = QPushButton("Analyze")
        analyze_button.clicked.connect(self._run_analysis)
        buttons.addWidget(analyze_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)
        buttons.addWidget(close_button)

        layout.addLayout(buttons)
        self._update_mode_enabled_state()

    def _create_freq_spinbox(self, minimum: float = 0.0) -> QDoubleSpinBox:
        """Create a frequency spinbox with shared formatting."""
        spin = QDoubleSpinBox()
        spin.setDecimals(6)
        spin.setRange(minimum, 1e12)
        spin.setSingleStep(0.1)
        return spin

    def _populate_traces(self) -> None:
        """Populate trace list with checkable items."""
        for trace_id, (label, _, _) in self._traces.items():
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, trace_id)
            self._trace_list.addItem(item)

    def _initialize_range(self) -> None:
        """Initialize range fields using all available trace frequency limits."""
        if not self._traces:
            self._start_spin.setValue(0.0)
            self._stop_spin.setValue(0.0)
            self._center_spin.setValue(0.0)
            self._span_spin.setValue(0.0)
            return

        min_freq = min(float(np.min(data[1])) for data in self._traces.values())
        max_freq = max(float(np.max(data[1])) for data in self._traces.values())

        unit_factor = self._unit_factor()
        start = min_freq / unit_factor
        stop = max_freq / unit_factor

        self._updating_range = True
        self._start_spin.setValue(start)
        self._stop_spin.setValue(stop)
        self._center_spin.setValue((start + stop) / 2.0)
        self._span_spin.setValue(max(stop - start, 0.0))
        self._updating_range = False

        self._on_unit_changed(self._unit_combo.currentText())

    def _unit_factor(self) -> float:
        """Return conversion factor from selected unit to Hz."""
        unit = self._unit_combo.currentText()
        return {
            "Hz": 1.0,
            "kHz": 1e3,
            "MHz": 1e6,
            "GHz": 1e9,
        }[unit]

    def _on_unit_changed(self, unit: str) -> None:
        """Update suffixes and preserve the current physical range in Hz."""
        del unit

        prev_factor = getattr(self, "_previous_unit_factor", self._unit_factor())
        new_factor = self._unit_factor()

        start_hz = self._start_spin.value() * prev_factor
        stop_hz = self._stop_spin.value() * prev_factor
        center_hz = self._center_spin.value() * prev_factor
        span_hz = self._span_spin.value() * prev_factor

        self._updating_range = True
        suffix = f" {self._unit_combo.currentText()}"
        self._start_spin.setSuffix(suffix)
        self._stop_spin.setSuffix(suffix)
        self._center_spin.setSuffix(suffix)
        self._span_spin.setSuffix(suffix)

        self._start_spin.setValue(start_hz / new_factor)
        self._stop_spin.setValue(stop_hz / new_factor)
        self._center_spin.setValue(center_hz / new_factor)
        self._span_spin.setValue(span_hz / new_factor)
        self._updating_range = False

        self._previous_unit_factor = new_factor

    def _sync_center_span_from_start_stop(self) -> None:
        """Keep center/span fields synchronized from start/stop inputs."""
        if self._updating_range:
            return

        self._updating_range = True
        start = self._start_spin.value()
        stop = self._stop_spin.value()
        center = (start + stop) / 2.0
        span = max(stop - start, 0.0)
        self._center_spin.setValue(center)
        self._span_spin.setValue(span)
        self._updating_range = False

    def _sync_start_stop_from_center_span(self) -> None:
        """Keep start/stop fields synchronized from center/span inputs."""
        if self._updating_range:
            return

        self._updating_range = True
        center = self._center_spin.value()
        span = max(self._span_spin.value(), 0.0)
        start = center - span / 2.0
        stop = center + span / 2.0
        self._start_spin.setValue(max(start, 0.0))
        self._stop_spin.setValue(max(stop, 0.0))
        self._updating_range = False

    def _update_mode_enabled_state(self) -> None:
        """Enable the active range input mode and disable the inactive one."""
        use_start_stop = self._start_stop_radio.isChecked()

        self._start_spin.setEnabled(use_start_stop)
        self._stop_spin.setEnabled(use_start_stop)

        self._center_spin.setEnabled(not use_start_stop)
        self._span_spin.setEnabled(not use_start_stop)

    def _selected_trace_ids(self) -> list[str]:
        """Get selected trace ids from checkable list."""
        selected = []
        for row in range(self._trace_list.count()):
            item = self._trace_list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                trace_id = item.data(Qt.ItemDataRole.UserRole)
                if trace_id:
                    selected.append(trace_id)
        return selected

    def _current_range_hz(self) -> Tuple[float, float]:
        """Get current analysis range in Hz based on selected mode."""
        factor = self._unit_factor()
        if self._start_stop_radio.isChecked():
            start = self._start_spin.value() * factor
            stop = self._stop_spin.value() * factor
        else:
            center = self._center_spin.value() * factor
            span = self._span_spin.value() * factor
            start = center - (span / 2.0)
            stop = center + (span / 2.0)

        return start, stop

    def _format_freq(self, freq_hz: float) -> str:
        """Format frequency in currently selected unit."""
        factor = self._unit_factor()
        unit = self._unit_combo.currentText()
        return f"{freq_hz / factor:.6g} {unit}"

    def _format_value(self, value: float) -> str:
        """Format metric value with axis units when available."""
        return f"{value:.6g} ({self._y_axis_label})"

    def _run_analysis(self) -> None:
        """Compute and display peak-to-peak metrics for selected traces."""
        selected_trace_ids = self._selected_trace_ids()
        if not selected_trace_ids:
            QMessageBox.information(self, "No Traces Selected", "Select at least one trace to analyze.")
            return

        freq_start, freq_stop = self._current_range_hz()
        if freq_start >= freq_stop:
            QMessageBox.warning(self, "Invalid Range", "Stop frequency must be greater than start frequency.")
            return

        skipped: list[str] = []

        for trace_id in selected_trace_ids:
            label, x_data, y_data = self._traces[trace_id]

            trace_min_freq = float(np.min(x_data))
            trace_max_freq = float(np.max(x_data))
            effective_start = max(freq_start, trace_min_freq)
            effective_stop = min(freq_stop, trace_max_freq)

            if effective_start >= effective_stop:
                skipped.append(label)
                continue

            try:
                metrics = compute_peak_to_peak_metrics(x_data, y_data, effective_start, effective_stop)
            except ValueError:
                skipped.append(label)
                continue

            range_text = f"{self._format_freq(effective_start)} to {self._format_freq(effective_stop)}"

            row = self._results_table.rowCount()
            self._results_table.insertRow(row)
            self._results_table.setItem(row, 0, QTableWidgetItem(range_text))
            self._results_table.setItem(row, 1, QTableWidgetItem(label))
            self._results_table.setItem(row, 2, QTableWidgetItem(self._format_value(metrics['min_value'])))
            self._results_table.setItem(row, 3, QTableWidgetItem(self._format_freq(metrics['min_frequency'])))
            self._results_table.setItem(row, 4, QTableWidgetItem(self._format_value(metrics['max_value'])))
            self._results_table.setItem(row, 5, QTableWidgetItem(self._format_freq(metrics['max_frequency'])))
            self._results_table.setItem(row, 6, QTableWidgetItem(self._format_value(metrics['peak_to_peak'])))

        self._results_table.resizeColumnsToContents()

        if skipped:
            QMessageBox.information(
                self,
                "Partial Results",
                (
                    "Some traces were skipped because the selected frequency range "
                    "did not overlap the trace data range:\n\n"
                )
                + "\n".join(skipped),
            )

    def _clear_results(self) -> None:
        """Clear all rows from the results table."""
        if self._results_table.rowCount() == 0:
            QMessageBox.information(self, "No Results", "There are no results to clear.")
            return
        self._results_table.setRowCount(0)

    def _export_results_csv(self) -> None:
        """Export all current table rows to a CSV file."""
        if self._results_table.rowCount() == 0:
            QMessageBox.information(self, "No Results", "There are no results to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Peak-to-Peak Results",
            "peak_to_peak_results.csv",
            "CSV Files (*.csv)",
        )

        if not file_path:
            return

        try:
            headers = []
            for col in range(self._results_table.columnCount()):
                header_item = self._results_table.horizontalHeaderItem(col)
                headers.append(header_item.text() if header_item else f"Column {col + 1}")

            rows = []
            for row in range(self._results_table.rowCount()):
                row_values = []
                for col in range(self._results_table.columnCount()):
                    item = self._results_table.item(row, col)
                    row_values.append(item.text() if item else "")
                rows.append(row_values)

            with open(file_path, 'w', newline='', encoding='utf-8') as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(headers)
                writer.writerows(rows)

            QMessageBox.information(self, "Export Complete", f"Results exported to:\n{file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", f"Could not export results:\n{exc}")
