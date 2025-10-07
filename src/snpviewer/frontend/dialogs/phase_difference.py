"""
Phase Difference Analysis Dialog.

Provides comprehensive analysis of phase differences between multiple datasets
against a reference dataset, with S-parameter selection and frequency range control.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QPushButton, QSplitter,
                               QVBoxLayout, QWidget)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.frontend.plotting.plot_pipelines import (convert_s_to_phase,
                                                        get_frequency_array,
                                                        unwrap_phase)


class PhaseDifferenceDialog(QDialog):
    """
    Dialog for analyzing phase differences between datasets.

    Features:
    - Multiple dataset selection
    - Reference dataset designation
    - S-parameter selection
    - Frequency range selection (with unit support)
    - Preview plot of phase differences
    - Create chart from difference data
    """

    # Signal emitted when user wants to create a chart from difference data
    create_chart_requested = Signal(dict)  # Emits chart configuration

    def __init__(self, datasets: Dict[str, Dataset], parent: Optional[QWidget] = None):
        """
        Initialize the phase difference dialog.

        Args:
            datasets: Dictionary of available datasets {dataset_id: Dataset}
            parent: Parent widget
        """
        super().__init__(parent)

        self._datasets = datasets
        self._current_data = None  # Store current analysis data

        self.setWindowTitle("Phase Difference Analysis")
        self.resize(900, 700)

        self._setup_ui()
        self._setup_connections()
        self._populate_datasets()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Create splitter for controls and plot
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel: Controls
        controls_widget = self._create_controls_panel()
        splitter.addWidget(controls_widget)

        # Right panel: Plot
        plot_widget = self._create_plot_panel()
        splitter.addWidget(plot_widget)

        # Set initial sizes (1:2 ratio)
        splitter.setSizes([300, 600])

        layout.addWidget(splitter)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._create_chart_button = QPushButton("Create Chart")
        self._create_chart_button.setEnabled(False)
        button_layout.addWidget(self._create_chart_button)

        close_button = QPushButton("Close")
        button_layout.addWidget(close_button)
        close_button.clicked.connect(self.reject)

        layout.addLayout(button_layout)

    def _create_controls_panel(self) -> QWidget:
        """Create the controls panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Dataset selection group
        dataset_group = QGroupBox("Dataset Selection")
        dataset_layout = QVBoxLayout(dataset_group)

        # Reference dataset
        ref_layout = QFormLayout()
        self._reference_combo = QComboBox()
        ref_layout.addRow("Reference Dataset:", self._reference_combo)
        dataset_layout.addLayout(ref_layout)

        # Comparison datasets
        dataset_layout.addWidget(QLabel("Comparison Datasets:"))
        self._comparison_list = QListWidget()
        self._comparison_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        dataset_layout.addWidget(self._comparison_list)

        layout.addWidget(dataset_group)

        # S-parameter selection
        sparam_group = QGroupBox("S-Parameter")
        sparam_layout = QFormLayout(sparam_group)
        self._sparam_combo = QComboBox()
        sparam_layout.addRow("Select S-Parameter:", self._sparam_combo)
        layout.addWidget(sparam_group)

        # Frequency range group
        freq_group = QGroupBox("Frequency Range")
        freq_layout = QFormLayout(freq_group)

        self._freq_unit_combo = QComboBox()
        self._freq_unit_combo.addItems(["Hz", "kHz", "MHz", "GHz"])
        self._freq_unit_combo.setCurrentText("GHz")
        freq_layout.addRow("Unit:", self._freq_unit_combo)

        self._freq_start_spin = QDoubleSpinBox()
        self._freq_start_spin.setDecimals(3)
        self._freq_start_spin.setRange(0, 1000)
        self._freq_start_spin.setSuffix(" GHz")
        freq_layout.addRow("Start:", self._freq_start_spin)

        self._freq_end_spin = QDoubleSpinBox()
        self._freq_end_spin.setDecimals(3)
        self._freq_end_spin.setRange(0, 1000)
        self._freq_end_spin.setSuffix(" GHz")
        freq_layout.addRow("End:", self._freq_end_spin)

        layout.addWidget(freq_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        self._unwrap_check = QCheckBox("Unwrap Phase")
        self._unwrap_check.setChecked(True)
        options_layout.addWidget(self._unwrap_check)
        layout.addWidget(options_group)

        # Analyze button
        self._analyze_button = QPushButton("Analyze")
        layout.addWidget(self._analyze_button)

        layout.addStretch()

        return widget

    def _create_plot_panel(self) -> QWidget:
        """Create the plot panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Plot widget
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground('w')
        self._plot_widget.setLabel('left', 'Phase Difference', units='°')
        self._plot_widget.setLabel('bottom', 'Frequency', units='Hz')
        self._plot_widget.addLegend()
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)

        layout.addWidget(self._plot_widget)

        return widget

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        self._reference_combo.currentIndexChanged.connect(self._on_reference_changed)
        self._freq_unit_combo.currentTextChanged.connect(self._on_freq_unit_changed)
        self._analyze_button.clicked.connect(self._perform_analysis)
        self._create_chart_button.clicked.connect(self._on_create_chart)

    def _populate_datasets(self) -> None:
        """Populate dataset lists."""
        if not self._datasets:
            return

        # Populate reference combo
        for dataset_id, dataset in self._datasets.items():
            display_name = getattr(dataset, 'display_name', getattr(dataset, 'file_name', dataset_id))
            self._reference_combo.addItem(display_name, dataset_id)
            self._comparison_list.addItem(display_name)
            self._comparison_list.item(self._comparison_list.count() - 1).setData(Qt.ItemDataRole.UserRole, dataset_id)

        # Populate S-parameters based on first dataset
        if self._datasets:
            first_dataset = next(iter(self._datasets.values()))
            if hasattr(first_dataset, 's_params') and first_dataset.s_params is not None:
                n_ports = first_dataset.s_params.shape[1]
                for i in range(n_ports):
                    for j in range(n_ports):
                        self._sparam_combo.addItem(f"S{i+1},{j+1}", (i, j))

        # Set frequency range from first dataset
        if self._datasets:
            first_dataset = next(iter(self._datasets.values()))
            if hasattr(first_dataset, 'frequency_hz'):
                freq_hz = first_dataset.frequency_hz
                # Convert to GHz for display
                self._freq_start_spin.setValue(freq_hz[0] / 1e9)
                self._freq_end_spin.setValue(freq_hz[-1] / 1e9)

    def _on_reference_changed(self) -> None:
        """Handle reference dataset change."""
        # Could update UI based on reference dataset selection
        pass

    def _on_freq_unit_changed(self, unit: str) -> None:
        """Handle frequency unit change."""
        # Update spinbox suffixes
        self._freq_start_spin.setSuffix(f" {unit}")
        self._freq_end_spin.setSuffix(f" {unit}")

    def _perform_analysis(self) -> None:
        """Perform phase difference analysis."""
        # Get reference dataset
        ref_dataset_id = self._reference_combo.currentData()
        if not ref_dataset_id or ref_dataset_id not in self._datasets:
            return

        ref_dataset = self._datasets[ref_dataset_id]

        # Get comparison datasets
        comparison_ids = []
        for i in range(self._comparison_list.count()):
            item = self._comparison_list.item(i)
            if item.isSelected():
                dataset_id = item.data(Qt.ItemDataRole.UserRole)
                if dataset_id != ref_dataset_id:  # Don't compare with itself
                    comparison_ids.append(dataset_id)

        if not comparison_ids:
            return

        # Get S-parameter
        sparam_data = self._sparam_combo.currentData()
        if not sparam_data:
            return
        i_port, j_port = sparam_data

        # Get frequency range
        unit = self._freq_unit_combo.currentText()
        freq_multiplier = {'Hz': 1, 'kHz': 1e3, 'MHz': 1e6, 'GHz': 1e9}[unit]
        freq_start = self._freq_start_spin.value() * freq_multiplier
        freq_end = self._freq_end_spin.value() * freq_multiplier

        # Calculate phase differences
        self._calculate_and_plot(ref_dataset, ref_dataset_id, comparison_ids,
                                 i_port, j_port, freq_start, freq_end)

    def _calculate_and_plot(self, ref_dataset: Dataset, ref_dataset_id: str,
                            comparison_ids: List[str], i_port: int, j_port: int,
                            freq_start: float, freq_end: float) -> None:
        """Calculate phase differences and update plot."""
        # Get reference data
        ref_freq = get_frequency_array(ref_dataset, unit='Hz')
        ref_s_param = ref_dataset.s_params[:, i_port, j_port]

        # Filter by frequency range
        mask = (ref_freq >= freq_start) & (ref_freq <= freq_end)
        ref_freq_filtered = ref_freq[mask]
        ref_s_param_filtered = ref_s_param[mask]

        if len(ref_freq_filtered) < 2:
            return

        # Calculate reference phase
        ref_phase = convert_s_to_phase(ref_s_param_filtered, degrees=True)
        if self._unwrap_check.isChecked():
            ref_phase = unwrap_phase(ref_phase)

        # Clear plot
        self._plot_widget.clear()

        # Store data for chart creation
        differences_data = []
        ref_display_name = getattr(ref_dataset, 'display_name', ref_dataset_id)

        # Calculate and plot differences
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]

        for idx, comp_id in enumerate(comparison_ids):
            if comp_id not in self._datasets:
                continue

            comp_dataset = self._datasets[comp_id]
            comp_freq = get_frequency_array(comp_dataset, unit='Hz')
            comp_s_param = comp_dataset.s_params[:, i_port, j_port]

            # Filter by frequency range
            comp_mask = (comp_freq >= freq_start) & (comp_freq <= freq_end)
            comp_freq_filtered = comp_freq[comp_mask]
            comp_s_param_filtered = comp_s_param[comp_mask]

            # Calculate phase
            comp_phase = convert_s_to_phase(comp_s_param_filtered, degrees=True)
            if self._unwrap_check.isChecked():
                comp_phase = unwrap_phase(comp_phase)

            # Interpolate to reference frequency points if needed
            if not np.array_equal(comp_freq_filtered, ref_freq_filtered):
                comp_phase = np.interp(ref_freq_filtered, comp_freq_filtered, comp_phase)

            # Calculate difference
            phase_diff = comp_phase - ref_phase

            # Plot
            comp_display_name = getattr(comp_dataset, 'display_name', comp_id)
            pen = pg.mkPen(color=colors[idx % len(colors)], width=2)
            self._plot_widget.plot(ref_freq_filtered, phase_diff,
                                   pen=pen, name=f"{comp_display_name} - {ref_display_name}")

            # Store for chart creation
            differences_data.append({
                'dataset_id': comp_id,
                'dataset_name': comp_display_name,
                'frequency': ref_freq_filtered,
                'phase_difference': phase_diff,
                'color': colors[idx % len(colors)]
            })

        # Store current data
        self._current_data = {
            'reference_dataset_id': ref_dataset_id,
            'reference_dataset_name': ref_display_name,
            'comparison_datasets': comparison_ids,
            'sparam': f"S{i_port+1},{j_port+1}",
            'i_port': i_port,
            'j_port': j_port,
            'frequency': ref_freq_filtered,
            'freq_start': freq_start,
            'freq_end': freq_end,
            'unwrap_phase': self._unwrap_check.isChecked(),
            'differences': differences_data
        }

        # Enable create chart button
        self._create_chart_button.setEnabled(True)

    def _on_create_chart(self) -> None:
        """Create a new chart view with the phase difference plot."""
        if self._current_data is None:
            return

        # Create trace_id for phase difference chart
        import uuid
        chart_id = str(uuid.uuid4())[:8]

        # Prepare chart configuration
        chart_config = {
            'type': 'phase_difference',
            'title': f"Phase Difference - {self._current_data['sparam']}",
            'chart_id': chart_id,
            'reference_dataset_id': self._current_data['reference_dataset_id'],
            'reference_dataset_name': self._current_data['reference_dataset_name'],
            'comparison_datasets': self._current_data['comparison_datasets'],
            'sparam': self._current_data['sparam'],
            'i_port': self._current_data['i_port'],
            'j_port': self._current_data['j_port'],
            'freq_start': self._current_data['freq_start'],
            'freq_end': self._current_data['freq_end'],
            'unwrap_phase': self._current_data['unwrap_phase'],
            'differences': self._current_data['differences']
        }

        # Emit signal to create chart
        self.create_chart_requested.emit(chart_config)

        # Show confirmation
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self,
            "Chart Created",
            "Phase difference chart has been added to the workspace."
        )
