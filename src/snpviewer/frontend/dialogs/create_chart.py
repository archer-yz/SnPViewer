"""
Chart creation dialog with multi-dataset support.

Provides a comprehensive interface for creating charts with multiple datasets,
allowing users to select chart type, datasets, and S-parameters to plot.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QListWidget, QScrollArea, QVBoxLayout, QWidget)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.trace import PortPath, Trace, TraceStyle


class CreateChartDialog(QDialog):
    """
    Dialog for creating a new chart with multiple datasets.

    Allows selection of chart type, datasets, and S-parameters to plot.
    """

    def __init__(self, available_datasets: Dict[str, Dataset], parent: Optional[QWidget] = None):
        """
        Initialize the create chart dialog.

        Args:
            available_datasets: Dictionary of {dataset_id: Dataset} available for chart creation
            parent: Parent widget
        """
        super().__init__(parent)

        self._available_datasets = available_datasets
        self._selected_datasets: Dict[str, Dataset] = {}
        self._parameter_checkboxes: Dict[Tuple[int, int], QCheckBox] = {}
        self._min_ports: int = 0

        self.setWindowTitle("Create New Chart")
        self.setModal(True)
        self.resize(700, 600)

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Chart type selection
        chart_type_group = QGroupBox("Chart Type")
        chart_type_layout = QHBoxLayout(chart_type_group)

        chart_type_layout.addWidget(QLabel("Select chart type:"))

        self._chart_type_combo = QComboBox()
        self._chart_type_combo.addItem("Magnitude Plot", "magnitude")
        self._chart_type_combo.addItem("Phase Plot", "phase")
        self._chart_type_combo.addItem("Group Delay Plot", "group_delay")
        self._chart_type_combo.addItem("Smith Chart", "smith")
        chart_type_layout.addWidget(self._chart_type_combo)
        chart_type_layout.addStretch()

        layout.addWidget(chart_type_group)

        # Dataset selection
        dataset_group = QGroupBox("Select Datasets (Multiple Selection)")
        dataset_layout = QVBoxLayout(dataset_group)

        self._dataset_list = QListWidget()
        self._dataset_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        for dataset_id, dataset in self._available_datasets.items():
            display_text = f"{dataset.display_name} ({dataset.n_ports}p, {len(dataset.frequency_hz)} points)"
            self._dataset_list.addItem(display_text)
            self._dataset_list.item(self._dataset_list.count() - 1).setData(Qt.ItemDataRole.UserRole, dataset_id)

        self._dataset_list.itemSelectionChanged.connect(self._on_dataset_selection_changed)
        dataset_layout.addWidget(self._dataset_list)

        layout.addWidget(dataset_group)

        # S-parameter selection
        self._param_group = QGroupBox("Select S-Parameters")
        self._param_layout = QVBoxLayout(self._param_group)

        self._param_info_label = QLabel("Select datasets first to see available S-parameters")
        self._param_info_label.setStyleSheet("color: gray; font-style: italic;")
        self._param_layout.addWidget(self._param_info_label)

        self._param_scroll = QScrollArea()
        self._param_scroll.setWidgetResizable(True)
        self._param_scroll.setVisible(False)
        self._param_layout.addWidget(self._param_scroll)

        layout.addWidget(self._param_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_dataset_selection_changed(self) -> None:
        """Handle dataset selection change."""
        selected_items = self._dataset_list.selectedItems()

        if not selected_items:
            # No datasets selected
            self._param_info_label.setVisible(True)
            self._param_info_label.setText("Select datasets first to see available S-parameters")
            self._param_scroll.setVisible(False)
            self._selected_datasets.clear()
            self._min_ports = 0
            return

        # Get selected datasets
        self._selected_datasets.clear()
        port_counts = []

        for item in selected_items:
            dataset_id = item.data(Qt.ItemDataRole.UserRole)
            dataset = self._available_datasets.get(dataset_id)
            if dataset:
                self._selected_datasets[dataset_id] = dataset
                port_counts.append(dataset.n_ports)

        # Calculate minimum port count
        self._min_ports = min(port_counts) if port_counts else 0

        # Update parameter selection UI
        self._update_parameter_selection()

    def _update_parameter_selection(self) -> None:
        """Update the S-parameter selection area."""
        if self._min_ports == 0:
            self._param_info_label.setVisible(True)
            self._param_info_label.setText("No valid datasets selected")
            self._param_scroll.setVisible(False)
            return

        # Hide info label and show parameter selection
        self._param_info_label.setVisible(False)
        self._param_scroll.setVisible(True)

        # Create parameter checkboxes based on minimum port count
        param_widget = QWidget()
        param_layout = QVBoxLayout(param_widget)

        # Info about selected datasets
        info_label = QLabel(
            f"Selected {len(self._selected_datasets)} dataset(s). "
            f"Showing S-parameters up to {self._min_ports}x{self._min_ports} ports."
        )
        info_label.setWordWrap(True)
        param_layout.addWidget(info_label)

        # Clear previous checkboxes
        self._parameter_checkboxes.clear()

        # Reflection parameters
        refl_group = QGroupBox("Reflection Parameters (Sii)")
        refl_layout = QGridLayout(refl_group)

        for i in range(self._min_ports):
            port_pair = (i + 1, i + 1)
            checkbox = QCheckBox(f"S{i+1},{i+1}")
            checkbox.setToolTip(f"Reflection parameter for port {i+1}")
            self._parameter_checkboxes[port_pair] = checkbox
            refl_layout.addWidget(checkbox, i // 4, i % 4)

        param_layout.addWidget(refl_group)

        # Transmission parameters
        if self._min_ports > 1:
            trans_group = QGroupBox("Transmission Parameters (Sij, i≠j)")
            trans_layout = QGridLayout(trans_group)

            row = 0
            col = 0
            for i in range(self._min_ports):
                for j in range(self._min_ports):
                    if i != j:
                        port_pair = (i + 1, j + 1)
                        checkbox = QCheckBox(f"S{i+1},{j+1}")
                        checkbox.setToolTip(f"Transmission from port {j+1} to port {i+1}")
                        self._parameter_checkboxes[port_pair] = checkbox
                        trans_layout.addWidget(checkbox, row, col)
                        col += 1
                        if col >= 4:
                            col = 0
                            row += 1

            param_layout.addWidget(trans_group)

        param_layout.addStretch()
        self._param_scroll.setWidget(param_widget)

        # Apply default selections based on chart type
        self._apply_default_selections()

    def _apply_default_selections(self) -> None:
        """Apply default parameter selections based on chart type."""
        chart_type = self._chart_type_combo.currentData()

        if chart_type == "smith":
            # For Smith charts, select reflection parameters
            for i in range(min(self._min_ports, 4)):
                port_pair = (i + 1, i + 1)
                if port_pair in self._parameter_checkboxes:
                    self._parameter_checkboxes[port_pair].setChecked(True)
        else:
            # For Cartesian charts, select common parameters
            # S11, S22
            for i in range(min(self._min_ports, 2)):
                port_pair = (i + 1, i + 1)
                if port_pair in self._parameter_checkboxes:
                    self._parameter_checkboxes[port_pair].setChecked(True)

            # S12, S21 for 2-port
            if self._min_ports >= 2:
                for i, j in [(1, 2), (2, 1)]:
                    port_pair = (i, j)
                    if port_pair in self._parameter_checkboxes:
                        self._parameter_checkboxes[port_pair].setChecked(True)

    def get_chart_type(self) -> str:
        """Get the selected chart type."""
        return self._chart_type_combo.currentData()

    def get_selected_datasets(self) -> Dict[str, Dataset]:
        """Get the selected datasets."""
        return self._selected_datasets

    def get_selected_parameters(self) -> List[Tuple[int, int]]:
        """Get list of selected S-parameter port pairs."""
        selected = []
        for port_pair, checkbox in self._parameter_checkboxes.items():
            if checkbox.isChecked():
                selected.append(port_pair)
        return selected

    def create_traces(self) -> List[Tuple[str, Trace, str]]:
        """
        Create Trace objects for all combinations of selected datasets and parameters.

        Returns:
            List of (trace_id, Trace, dataset_id) tuples
        """
        traces = []
        selected_params = self.get_selected_parameters()
        chart_type = self.get_chart_type()

        if not selected_params:
            return traces

        # Color palette for traces
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD",
                  "#74B9FF", "#E17055", "#00B894", "#FDCB6E", "#6C5CE7", "#A29BFE"]

        trace_idx = 0

        # Create traces for each combination of dataset and parameter
        for dataset_id, dataset in self._selected_datasets.items():
            for i, j in selected_params:
                # Determine metric based on chart type
                if chart_type == "magnitude":
                    metric = "magnitude_dB"
                elif chart_type == "phase":
                    metric = "phase_deg"
                elif chart_type == "group_delay":
                    metric = "group_delay"
                elif chart_type == "smith":
                    metric = "reflection" if i == j else "transmission"
                else:
                    metric = "magnitude_dB"

                # Create style
                style = TraceStyle(
                    color=colors[trace_idx % len(colors)],
                    line_width=2,
                    line_style="solid" if i == j else "dashed",
                    marker_style='none'
                )

                # Create trace
                trace_id = f"{dataset_id}_S{i}{j}_{chart_type}"
                trace = Trace(
                    id=trace_id,
                    dataset_id=dataset.id,
                    domain="S",
                    metric=metric,
                    port_path=PortPath(i=i, j=j),
                    style=style
                )

                traces.append((trace_id, trace, dataset_id))
                trace_idx += 1

        return traces
