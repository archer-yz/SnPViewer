"""
Linear Phase Error Analysis Dialog.

Provides comprehensive analysis of linear phase errors in S-parameters,
including fitted line visualization, error statistics, and interactive adjustment.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSplitter, QTextEdit, QVBoxLayout,
                               QWidget)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.frontend.plotting.plot_pipelines import (convert_s_to_phase,
                                                        get_frequency_array,
                                                        unwrap_phase)


class LinearPhaseErrorDialog(QDialog):
    """
    Dialog for analyzing linear phase errors.

    Features:
    - Dataset and S-parameter selection
    - Frequency range selection (with unit support)
    - Two subplots: unwrapped phase with fit, and error plot
    - Interactive fit parameter adjustment
    - Comprehensive error statistics
    - Create chart from error plot
    """

    # Signal emitted when user wants to create a chart from error data
    create_chart_requested = Signal(dict)  # Emits chart configuration

    def __init__(self, datasets: Dict[str, Dataset], parent: Optional[QWidget] = None):
        """
        Initialize the linear phase error dialog.

        Args:
            datasets: Dictionary of available datasets {trace_id: Dataset}
            parent: Parent widget
        """
        super().__init__(parent)

        self._datasets = datasets
        self._current_data = None  # Stores computed data for current selection

        self.setWindowTitle("Linear Phase Error Analysis")
        self.resize(1200, 800)

        self._setup_ui()
        self._populate_datasets()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Control panel at the top
        control_group = self._create_control_panel()
        layout.addWidget(control_group)

        # Splitter for plots and statistics
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Plots
        plot_widget = self._create_plot_area()
        splitter.addWidget(plot_widget)

        # Right side: Statistics and fit parameters
        stats_widget = self._create_stats_area()
        splitter.addWidget(stats_widget)

        splitter.setStretchFactor(0, 3)  # Plots take more space
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._analyze_button = QPushButton("Analyze")
        self._analyze_button.clicked.connect(self._perform_analysis)
        button_layout.addWidget(self._analyze_button)

        self._create_chart_button = QPushButton("Create Chart from Error")
        self._create_chart_button.clicked.connect(self._create_error_chart)
        self._create_chart_button.setEnabled(False)  # Disabled until analysis is done
        button_layout.addWidget(self._create_chart_button)

        self._close_button = QPushButton("Close")
        self._close_button.clicked.connect(self.accept)
        button_layout.addWidget(self._close_button)

        layout.addLayout(button_layout)

    def _create_control_panel(self) -> QGroupBox:
        """Create the control panel for dataset and parameter selection."""
        group = QGroupBox("Data Selection")
        layout = QFormLayout(group)

        # Dataset selection
        self._dataset_combo = QComboBox()
        self._dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        layout.addRow("Dataset:", self._dataset_combo)

        # S-parameter selection
        self._sparam_combo = QComboBox()
        layout.addRow("S-Parameter:", self._sparam_combo)

        # Frequency range with unit support
        freq_layout = QHBoxLayout()

        # Start frequency
        start_layout = QHBoxLayout()
        self._freq_start_input = QLineEdit()
        self._freq_start_input.setPlaceholderText("e.g., 1e9, 1G, 1000M")
        self._freq_start_input.setMinimumWidth(120)
        start_layout.addWidget(self._freq_start_input)

        self._freq_start_unit = QComboBox()
        self._freq_start_unit.addItems(["Hz", "kHz", "MHz", "GHz", "THz"])
        self._freq_start_unit.setCurrentText("GHz")
        start_layout.addWidget(self._freq_start_unit)
        freq_layout.addLayout(start_layout)

        freq_layout.addWidget(QLabel("to"))

        # End frequency
        end_layout = QHBoxLayout()
        self._freq_end_input = QLineEdit()
        self._freq_end_input.setPlaceholderText("e.g., 10e9, 10G, 10000M")
        self._freq_end_input.setMinimumWidth(120)
        end_layout.addWidget(self._freq_end_input)

        self._freq_end_unit = QComboBox()
        self._freq_end_unit.addItems(["Hz", "kHz", "MHz", "GHz", "THz"])
        self._freq_end_unit.setCurrentText("GHz")
        end_layout.addWidget(self._freq_end_unit)
        freq_layout.addLayout(end_layout)

        freq_layout.addStretch()
        layout.addRow("Frequency Range:", freq_layout)

        return group

    def _create_plot_area(self) -> QWidget:
        """Create the plot area with two subplots."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top plot: Unwrapped phase with linear fit
        self._phase_plot = pg.PlotWidget()
        self._phase_plot.setBackground('w')
        self._phase_plot.setLabel('left', 'Phase', units='°')
        self._phase_plot.setLabel('bottom', 'Frequency', units='Hz')
        self._phase_plot.setTitle('Unwrapped Phase with Linear Fit')
        self._phase_plot.showGrid(x=True, y=True, alpha=0.3)
        self._phase_plot.addLegend()

        layout.addWidget(self._phase_plot)

        # Bottom plot: Linear phase error
        self._error_plot = pg.PlotWidget()
        self._error_plot.setBackground('w')
        self._error_plot.setLabel('left', 'Phase Error', units='°')
        self._error_plot.setLabel('bottom', 'Frequency', units='Hz')
        self._error_plot.setTitle('Linear Phase Error')
        self._error_plot.showGrid(x=True, y=True, alpha=0.3)

        layout.addWidget(self._error_plot)

        return widget

    def _create_stats_area(self) -> QWidget:
        """Create the statistics and fit parameter area."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Fit parameters group
        fit_group = QGroupBox("Linear Fit Parameters")
        fit_layout = QFormLayout(fit_group)

        self._slope_spin = QDoubleSpinBox()
        self._slope_spin.setDecimals(6)
        self._slope_spin.setRange(-1e12, 1e12)
        self._slope_spin.setSingleStep(0.000001)
        self._slope_spin.valueChanged.connect(self._on_fit_parameter_changed)
        fit_layout.addRow("Slope (°/Hz):", self._slope_spin)

        self._intercept_spin = QDoubleSpinBox()
        self._intercept_spin.setDecimals(3)
        self._intercept_spin.setRange(-1e6, 1e6)
        self._intercept_spin.setSingleStep(0.1)
        self._intercept_spin.valueChanged.connect(self._on_fit_parameter_changed)
        fit_layout.addRow("Intercept (°):", self._intercept_spin)

        # Fit equation display with theme-friendly styling
        self._equation_label = QLabel("Phase = slope × f + intercept")
        self._equation_label.setWordWrap(True)
        self._equation_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                border: 1px solid palette(mid);
                border-radius: 4px;
                background-color: palette(base);
                font-family: 'Courier New', 'Consolas', monospace;
                font-size: 10pt;
            }
        """)
        fit_layout.addRow("Equation:", self._equation_label)

        # Residual info
        self._residual_label = QLabel("R² = -")
        fit_layout.addRow("Goodness of Fit:", self._residual_label)

        layout.addWidget(fit_group)

        # Statistics group
        stats_group = QGroupBox("Error Statistics")
        stats_layout = QVBoxLayout(stats_group)

        self._stats_text = QTextEdit()
        self._stats_text.setReadOnly(True)
        self._stats_text.setMaximumHeight(250)
        self._stats_text.setStyleSheet("font-family: 'Courier New', monospace; font-size: 10pt;")
        stats_layout.addWidget(self._stats_text)

        layout.addWidget(stats_group)

        layout.addStretch()

        return widget

    def _populate_datasets(self) -> None:
        """Populate the dataset combo box."""
        self._dataset_combo.clear()

        for dataset_id, dataset in self._datasets.items():
            display_name = getattr(dataset, 'display_name', getattr(dataset, 'file_name', 'Unknown'))
            # Store both display name and trace_id
            self._dataset_combo.addItem(display_name, dataset_id)

        if self._dataset_combo.count() > 0:
            self._on_dataset_changed(0)

    def _on_dataset_changed(self, index: int) -> None:
        """Handle dataset selection change."""
        if index < 0:
            return

        dataset_id = self._dataset_combo.currentData()
        if not dataset_id or dataset_id not in self._datasets:
            return

        dataset = self._datasets[dataset_id]

        # Populate S-parameter combo
        self._sparam_combo.clear()

        if hasattr(dataset, 's_params') and dataset.s_params is not None:
            # Get matrix dimensions
            n_ports = dataset.s_params.shape[1]  # Assuming shape is (freq, ports, ports)

            for i in range(n_ports):
                for j in range(n_ports):
                    self._sparam_combo.addItem(f"S{i+1},{j+1}", (i, j))

        # Set frequency range to full range and populate input fields
        if hasattr(dataset, 'frequency') and dataset.frequency is not None:
            freq = get_frequency_array(dataset, unit='Hz')
            freq_start_hz = float(freq[0])
            freq_end_hz = float(freq[-1])

            # Auto-select appropriate unit and display value
            self._set_frequency_display(self._freq_start_input, self._freq_start_unit, freq_start_hz)
            self._set_frequency_display(self._freq_end_input, self._freq_end_unit, freq_end_hz)

    def _set_frequency_display(self, input_widget: QLineEdit, unit_widget: QComboBox, freq_hz: float) -> None:
        """Set frequency display with appropriate unit."""
        # Choose the most appropriate unit
        if freq_hz >= 1e12:
            unit_widget.setCurrentText("THz")
            input_widget.setText(f"{freq_hz / 1e12:.6g}")
        elif freq_hz >= 1e9:
            unit_widget.setCurrentText("GHz")
            input_widget.setText(f"{freq_hz / 1e9:.6g}")
        elif freq_hz >= 1e6:
            unit_widget.setCurrentText("MHz")
            input_widget.setText(f"{freq_hz / 1e6:.6g}")
        elif freq_hz >= 1e3:
            unit_widget.setCurrentText("kHz")
            input_widget.setText(f"{freq_hz / 1e3:.6g}")
        else:
            unit_widget.setCurrentText("Hz")
            input_widget.setText(f"{freq_hz:.6g}")

    def _parse_frequency(self, text: str, unit: str) -> float:
        """
        Parse frequency from text and unit, supporting scientific notation.

        Args:
            text: Frequency value text (may contain scientific notation)
            unit: Unit string (Hz, kHz, MHz, GHz, THz)

        Returns:
            Frequency in Hz
        """
        try:
            # Parse the numeric value (handles scientific notation)
            value = float(text.strip())

            # Convert to Hz based on unit
            multipliers = {
                'Hz': 1,
                'kHz': 1e3,
                'MHz': 1e6,
                'GHz': 1e9,
                'THz': 1e12
            }

            return value * multipliers.get(unit, 1)
        except ValueError:
            raise ValueError(f"Invalid frequency value: {text}")

    def _perform_analysis(self) -> None:
        """Perform the linear phase error analysis."""
        # Get selected dataset
        dataset_id = self._dataset_combo.currentData()
        if not dataset_id or dataset_id not in self._datasets:
            return

        dataset = self._datasets[dataset_id]

        # Get S-parameter indices
        sparam_data = self._sparam_combo.currentData()
        if sparam_data is None:
            return

        i_port, j_port = sparam_data

        # Get frequency range with error handling
        try:
            freq_start = self._parse_frequency(
                self._freq_start_input.text(),
                self._freq_start_unit.currentText()
            )
            freq_end = self._parse_frequency(
                self._freq_end_input.text(),
                self._freq_end_unit.currentText()
            )
        except ValueError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Frequency", str(e))
            return

        if freq_start >= freq_end:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Invalid Range",
                "Start frequency must be less than end frequency."
            )
            return

        # Extract data
        freq = get_frequency_array(dataset, unit='Hz')

        # Get S-parameter
        s_param = dataset.s_params[:, i_port, j_port]

        # Apply frequency range filter
        mask = (freq >= freq_start) & (freq <= freq_end)
        freq_filtered = freq[mask]
        s_param_filtered = s_param[mask]

        if len(freq_filtered) < 2:
            self._stats_text.setText("Error: Insufficient data points in selected frequency range.")
            self._create_chart_button.setEnabled(False)
            return

        # Compute unwrapped phase in degrees
        phase = convert_s_to_phase(s_param_filtered, degrees=True)
        phase = unwrap_phase(phase)

        # Perform linear fit
        coeffs = np.polyfit(freq_filtered, phase, 1)
        slope = coeffs[0]
        intercept = coeffs[1]

        # Get dataset and S-parameter info for later chart creation
        display_name = getattr(dataset, 'display_name', getattr(dataset, 'file_name', 'Unknown'))
        sparam_label = f"S{i_port+1},{j_port+1}"

        # Store current data
        self._current_data = {
            'frequency': freq_filtered,
            'phase': phase,
            'slope': slope,
            'intercept': intercept,
            'dataset_name': display_name,
            'sparam': sparam_label,
            'dataset_id': dataset_id,
            'i_port': i_port,
            'j_port': j_port,
            'freq_start': freq_start,
            'freq_end': freq_end
        }

        # Update spinboxes (without triggering update)
        self._slope_spin.blockSignals(True)
        self._intercept_spin.blockSignals(True)
        self._slope_spin.setValue(slope)
        self._intercept_spin.setValue(intercept)
        self._slope_spin.blockSignals(False)
        self._intercept_spin.blockSignals(False)

        # Update plots and statistics
        self._update_visualization()

        # Enable the create chart button
        self._create_chart_button.setEnabled(True)

    def _on_fit_parameter_changed(self) -> None:
        """Handle manual adjustment of fit parameters."""
        if self._current_data is None:
            return

        # Update stored parameters
        self._current_data['slope'] = self._slope_spin.value()
        self._current_data['intercept'] = self._intercept_spin.value()

        # Update plots and statistics
        self._update_visualization()

    def _update_visualization(self) -> None:
        """Update plots and statistics based on current data and fit parameters."""
        if self._current_data is None:
            return

        freq = self._current_data['frequency']
        phase = self._current_data['phase']
        slope = self._current_data['slope']
        intercept = self._current_data['intercept']

        # Compute fitted phase
        phase_fit = slope * freq + intercept

        # Compute error
        phase_error = phase - phase_fit

        # Update equation label
        self._equation_label.setText(f"Phase = {slope:.8e} × f + {intercept:.3f}")

        # Calculate R²
        ss_res = np.sum(phase_error ** 2)
        ss_tot = np.sum((phase - np.mean(phase)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        self._residual_label.setText(f"R² = {r_squared:.6f}")

        # Update phase plot
        self._phase_plot.clear()

        # Plot measured phase
        pen_measured = pg.mkPen(color='b', width=2)
        self._phase_plot.plot(freq, phase, pen=pen_measured, name='Measured Phase')

        # Plot fitted phase
        pen_fit = pg.mkPen(color='r', width=2, style=Qt.PenStyle.DashLine)
        self._phase_plot.plot(freq, phase_fit, pen=pen_fit, name='Linear Fit')

        # Update error plot
        self._error_plot.clear()

        pen_error = pg.mkPen(color='g', width=2)
        self._error_plot.plot(freq, phase_error, pen=pen_error)

        # Add zero reference line
        pen_zero = pg.mkPen(color='k', width=1, style=Qt.PenStyle.DashLine)
        self._error_plot.plot([freq[0], freq[-1]], [0, 0], pen=pen_zero)

        # Calculate statistics
        stats = self._calculate_statistics(phase_error)
        self._update_statistics_display(stats)

    def _calculate_statistics(self, error: np.ndarray) -> Dict[str, float]:
        """Calculate error statistics."""
        return {
            'max': float(np.max(error)),
            'min': float(np.min(error)),
            'peak_to_peak': float(np.max(error) - np.min(error)),
            'mean': float(np.mean(error)),
            'std': float(np.std(error)),
            'rms': float(np.sqrt(np.mean(error ** 2))),
            'median': float(np.median(error)),
        }

    def _update_statistics_display(self, stats: Dict[str, float]) -> None:
        """Update the statistics text display."""
        text = "Linear Phase Error Statistics\n"
        text += "=" * 40 + "\n\n"
        text += f"Maximum Error:      {stats['max']:>12.4f} °\n"
        text += f"Minimum Error:      {stats['min']:>12.4f} °\n"
        text += f"Peak-to-Peak:       {stats['peak_to_peak']:>12.4f} °\n"
        text += f"Mean Error:         {stats['mean']:>12.4f} °\n"
        text += f"Median Error:       {stats['median']:>12.4f} °\n"
        text += f"Std Deviation:      {stats['std']:>12.4f} °\n"
        text += f"RMS Error:          {stats['rms']:>12.4f} °\n"

        self._stats_text.setText(text)

    def _create_error_chart(self) -> None:
        """Create a new chart view with the linear phase error plot."""
        if self._current_data is None:
            return

        freq = self._current_data['frequency']
        phase = self._current_data['phase']
        slope = self._current_data['slope']
        intercept = self._current_data['intercept']

        # Compute error
        phase_fit = slope * freq + intercept
        phase_error = phase - phase_fit

        # Get dataset_id and create proper trace_id
        dataset_id = self._current_data['dataset_id']
        i_port = self._current_data['i_port']
        j_port = self._current_data['j_port']
        sparam_label = self._current_data['sparam']

        # Create trace_id in standardized format: dataset_id:S{i},{j}_linear_phase_error
        trace_id = f"{dataset_id}:S{i_port+1},{j_port+1}_linear_phase_error"

        # Prepare chart configuration matching Chart model structure
        chart_config = {
            'type': 'linear_phase_error',
            'title': "Linear Phase Error",
            'dataset_id': dataset_id,
            'trace_id': trace_id,
            'i_port': i_port,
            'j_port': j_port,
            'sparam': sparam_label,
            'frequency': freq,
            'error': phase_error,
            'slope': slope,
            'intercept': intercept,
            'freq_start': self._current_data['freq_start'],
            'freq_end': self._current_data['freq_end'],
            'equation': f"Phase = {slope:.8e} × f + {intercept:.3f}",
            'dataset_name': self._current_data['dataset_name']
        }

        # Emit signal to create chart
        self.create_chart_requested.emit(chart_config)

        # Show confirmation
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Chart Created",
            "Linear phase error chart has been added to the workspace."
        )
