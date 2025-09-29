"""
Trace selection dialog for choosing which S-parameters to plot.

Provides a user-friendly interface for selecting specific S-parameters
from multi-port datasets with preview of available parameters.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                               QGridLayout, QGroupBox, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.trace import PortPath, Trace, TraceStyle


class TraceSelectionDialog(QDialog):
    """
    Dialog for selecting which S-parameters to plot on a chart.

    Provides checkboxes for all available S-parameters in the dataset
    with reflection and transmission parameter grouping.
    """

    def __init__(self, dataset: Dataset, chart_type: str, parent: Optional[QWidget] = None):
        """
        Initialize the trace selection dialog.

        Args:
            dataset: Dataset containing S-parameter data
            chart_type: Type of chart being created ('magnitude', 'phase', etc.)
            parent: Parent widget
        """
        super().__init__(parent)

        self._dataset = dataset
        self._chart_type = chart_type
        self._selected_traces: List[Tuple[int, int]] = []

        self.setWindowTitle(f"Select S-Parameters for {chart_type.title()} Chart")
        self.setModal(True)
        self.resize(400, 300)

        self._setup_ui()
        self._setup_defaults()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(f"Dataset: {self._dataset.file_name}")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)

        ports_label = QLabel(f"Ports: {self._dataset.n_ports}")
        layout.addWidget(ports_label)

        # Scroll area for parameter selection
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(200)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        # Create parameter selection groups
        self._create_parameter_groups(content_layout)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_parameter_groups(self, layout: QVBoxLayout) -> None:
        """Create parameter selection groups."""
        n_ports = self._dataset.n_ports

        # Store checkboxes for easy access
        self._checkboxes: Dict[Tuple[int, int], QCheckBox] = {}

        # Reflection parameters group
        if n_ports > 0:
            reflection_group = QGroupBox("Reflection Parameters (Sii)")
            reflection_layout = QGridLayout(reflection_group)

            for i in range(n_ports):
                port_pair = (i + 1, i + 1)
                checkbox = QCheckBox(f"S{i+1}{i+1}")
                checkbox.setToolTip(f"Reflection parameter for port {i+1}")
                self._checkboxes[port_pair] = checkbox
                reflection_layout.addWidget(checkbox, i // 2, i % 2)

            layout.addWidget(reflection_group)

        # Transmission parameters group
        if n_ports > 1:
            transmission_group = QGroupBox("Transmission Parameters (Sij, i≠j)")
            transmission_layout = QGridLayout(transmission_group)

            row = 0
            for i in range(n_ports):
                for j in range(n_ports):
                    if i != j:
                        port_pair = (i + 1, j + 1)
                        checkbox = QCheckBox(f"S{i+1}{j+1}")
                        checkbox.setToolTip(f"Transmission from port {j+1} to port {i+1}")
                        self._checkboxes[port_pair] = checkbox
                        transmission_layout.addWidget(checkbox, row // 3, row % 3)
                        row += 1

            layout.addWidget(transmission_group)

    def _setup_defaults(self) -> None:
        """Setup default parameter selections based on chart type and port count."""
        n_ports = self._dataset.n_ports

        if self._chart_type.lower() in ['smith', 'smith_chart']:
            # For Smith charts, default to reflection parameters
            for i in range(min(n_ports, 4)):  # Limit to 4 for readability
                port_pair = (i + 1, i + 1)
                if port_pair in self._checkboxes:
                    self._checkboxes[port_pair].setChecked(True)
        else:
            # For Cartesian charts, default to common parameters
            # S11, S22 (reflection)
            for i in range(min(n_ports, 2)):
                port_pair = (i + 1, i + 1)
                if port_pair in self._checkboxes:
                    self._checkboxes[port_pair].setChecked(True)

            # S12, S21 (transmission) for 2-port
            if n_ports >= 2:
                for i, j in [(1, 2), (2, 1)]:
                    port_pair = (i, j)
                    if port_pair in self._checkboxes:
                        self._checkboxes[port_pair].setChecked(True)

    def get_selected_parameters(self) -> List[Tuple[int, int]]:
        """
        Get list of selected S-parameter port pairs.

        Returns:
            List of (i, j) tuples for selected Sij parameters
        """
        selected = []
        for port_pair, checkbox in self._checkboxes.items():
            if checkbox.isChecked():
                selected.append(port_pair)
        return selected

    def create_selected_traces(self) -> List[Tuple[str, Trace]]:
        """
        Create Trace objects for selected parameters.

        Returns:
            List of (trace_id, Trace) tuples
        """
        selected_params = self.get_selected_parameters()
        traces = []

        # Color palette for traces
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD",
                  "#74B9FF", "#E17055", "#00B894", "#FDCB6E", "#6C5CE7", "#A29BFE"]

        for idx, (i, j) in enumerate(selected_params):
            # Determine metric based on chart type
            if self._chart_type.lower() == "magnitude":
                metric = "magnitude_dB"
            elif self._chart_type.lower() == "phase":
                metric = "phase_deg"
            elif self._chart_type.lower() in ['smith', 'smith_chart']:
                metric = "reflection" if i == j else "transmission"
            else:
                metric = self._chart_type.lower()

            # Create style
            style = TraceStyle(
                color=colors[idx % len(colors)],
                line_width=2,
                line_style="solid" if i == j else "dashed",
                marker_style='none'
            )

            # Create trace
            trace_id = f"S{i}{j}_{self._chart_type}"
            trace = Trace(
                id=trace_id,
                dataset_id=getattr(self._dataset, 'id', ''),
                domain="S",
                metric=metric,
                port_path=PortPath(i=i, j=j),
                style=style
            )

            traces.append((trace_id, trace))

        return traces
