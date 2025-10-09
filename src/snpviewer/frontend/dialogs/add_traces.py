"""
Advanced trace management dialog for adding traces to existing charts.

Provides functionality to add traces from any loaded dataset to the current chart,
with parameter selection and style customization options.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.trace import PortPath, Trace, TraceStyle
from snpviewer.frontend.constants import DEFAULT_TRACE_COLORS, DEFAULT_LINE_STYLES


class AddTracesDialog(QDialog):
    """
    Dialog for adding traces from any loaded dataset to an existing chart.

    Allows selection of datasets, parameters, and trace styling options.
    """

    def __init__(self, available_datasets: Dict[str, Dataset], chart_type: str,
                 existing_traces: Dict[str, Tuple[str, Trace, Dataset]] = None, parent: Optional[QWidget] = None):
        """
        Initialize the add traces dialog.

        Args:
            available_datasets: Dictionary of {dataset_id: Dataset} available for trace creation
            chart_type: Type of the target chart ('magnitude', 'phase', etc.)
            existing_traces: Dict of {trace_id: (dataset_id, trace, dataset)} for existing traces
            parent: Parent widget
        """
        super().__init__(parent)

        self._available_datasets = available_datasets
        self._chart_type = chart_type
        self._existing_traces = existing_traces or {}
        self._checkboxes: Dict[str, QCheckBox] = {}  # {trace_id: checkbox}
        self._current_dataset_id: Optional[str] = None
        self._dataset_combo: Optional[QComboBox] = None

        self.setWindowTitle(f"Manage Traces - {chart_type.title()} Chart")
        self.setModal(True)
        self.resize(600, 500)

        self._setup_ui()

    def _get_preselected_dataset(self) -> Optional[str]:
        """
        Get a dataset ID to preselect based on existing traces.

        Returns:
            Dataset ID to preselect, or None if no preference
        """
        if not self._existing_traces:
            return None

        # Count traces by dataset to find the most common one
        dataset_counts = {}
        for trace_id, (trace_dataset_id, trace, dataset_obj) in self._existing_traces.items():
            # Look for the dataset by matching the dataset object with available datasets
            # Since available_datasets now uses user-friendly names as keys, we need to find the matching dataset
            matching_dataset_id = None
            for available_id, available_dataset in self._available_datasets.items():
                if available_dataset is dataset_obj:
                    matching_dataset_id = available_id
                    break

            if matching_dataset_id:
                dataset_counts[matching_dataset_id] = dataset_counts.get(matching_dataset_id, 0) + 1

        if dataset_counts:
            # Return the dataset with the most traces
            return max(dataset_counts, key=dataset_counts.get)

        return None

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(f"Select a dataset to manage traces for the {self._chart_type} chart:")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)

        # Dataset selection and trace management section
        if self._available_datasets:
            main_group = QGroupBox("Dataset Traces")
            main_layout = QVBoxLayout(main_group)

            # Dataset selection dropdown
            dataset_layout = QHBoxLayout()
            dataset_layout.addWidget(QLabel("Select Dataset:"))

            self._dataset_combo = QComboBox()
            self._dataset_combo.addItem("-- Select a dataset --", "")
            for dataset_id, dataset in self._available_datasets.items():
                # Count existing traces for this dataset
                trace_count = sum(1 for _, (trace_dataset_id, _, dataset_obj) in self._existing_traces.items()
                                  if dataset_obj is dataset or trace_dataset_id == dataset_id)

                if trace_count > 0:
                    display_name = f"{dataset.display_name} ({dataset.n_ports}p) - {trace_count} traces"
                else:
                    display_name = f"{dataset.display_name} ({dataset.n_ports}p)"

                self._dataset_combo.addItem(display_name, dataset_id)

            self._dataset_combo.currentTextChanged.connect(self._on_dataset_changed)
            dataset_layout.addWidget(self._dataset_combo)
            dataset_layout.addStretch()
            main_layout.addLayout(dataset_layout)

            # Scroll area for parameter selection
            self._param_scroll = QScrollArea()
            self._param_scroll.setWidgetResizable(True)
            self._param_scroll.setMinimumHeight(200)
            self._param_scroll.setVisible(False)  # Hidden until dataset selected

            main_layout.addWidget(self._param_scroll)
            layout.addWidget(main_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        # Add Apply button
        self._apply_button = button_box.addButton("Apply", QDialogButtonBox.ButtonRole.ApplyRole)
        self._apply_button.clicked.connect(self._on_apply_clicked)
        self._apply_button.setEnabled(False)  # Disabled until dataset selected

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Preselect dataset if there are existing traces (do this after UI is fully set up)
        preselected_dataset_id = self._get_preselected_dataset()
        if preselected_dataset_id:
            for i in range(self._dataset_combo.count()):
                if self._dataset_combo.itemData(i) == preselected_dataset_id:
                    self._dataset_combo.setCurrentIndex(i)
                    # Manually trigger the change to update UI (now that UI is fully initialized)
                    self._on_dataset_changed()
                    break

    def _on_dataset_changed(self) -> None:
        """Handle dataset selection change."""
        dataset_id = self._dataset_combo.currentData()

        if not dataset_id:
            self._param_scroll.setVisible(False)
            return

        # Always allow refresh if dataset_id matches current but _current_dataset_id is None
        # This happens during refresh operations
        force_refresh = (self._current_dataset_id is None)

        # Skip if same dataset is selected and not a forced refresh
        if self._current_dataset_id == dataset_id and not force_refresh:
            return

        # Clean up old checkboxes from previous dataset selection
        self._checkboxes.clear()

        self._current_dataset_id = dataset_id
        dataset = self._available_datasets[dataset_id]        # Create parameter selection widget
        param_widget = QWidget()
        param_layout = QVBoxLayout(param_widget)

        # Dataset info
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"Points: {len(dataset.frequency_hz)}"))
        freq_range = f"Frequency: {dataset.frequency_hz[0]/1e9:.3f} - {dataset.frequency_hz[-1]/1e9:.3f} GHz"
        info_layout.addWidget(QLabel(freq_range))
        info_layout.addStretch()
        param_layout.addLayout(info_layout)

        # Parameter checkboxes
        grid_layout = QGridLayout()

        # Get existing traces for this dataset
        # Match based on dataset identity (same dataset object)
        existing_traces_for_dataset = {}
        selected_dataset = self._available_datasets[dataset_id]
        for trace_id, (trace_dataset_id, trace, dataset_obj) in self._existing_traces.items():
            # Match if it's the same dataset object or same dataset ID
            if dataset_obj is selected_dataset or trace_dataset_id == dataset_id:
                existing_traces_for_dataset[trace_id] = (trace_dataset_id, trace, dataset_obj)

        # Reflection parameters
        refl_label = QLabel("Reflection (Sii):")
        refl_label.setStyleSheet("font-weight: bold;")
        grid_layout.addWidget(refl_label, 0, 0, 1, -1)

        row = 1
        col = 0
        for i in range(dataset.n_ports):
            # Standardized format: dataset_id:S{i},{j}_{chart_type}
            trace_id = f"{dataset_id}:S{i+1},{i+1}_{self._chart_type}"

            checkbox = QCheckBox(f"S{i+1},{i+1}")

            # Check if this trace already exists in the chart
            if trace_id in existing_traces_for_dataset:
                checkbox.setChecked(True)
                checkbox.setToolTip(f"Existing reflection parameter for port {i+1} (uncheck to remove)")
                checkbox.setStyleSheet("font-weight: bold; color: #2E7D32;")  # Green for existing
                self._checkboxes[trace_id] = checkbox
            else:
                checkbox.setChecked(False)
                checkbox.setToolTip(f"Add reflection parameter for port {i+1}")
                checkbox.setStyleSheet("color: #1976D2;")  # Blue for new
                # Map the new trace ID for adding new traces
                self._checkboxes[trace_id] = checkbox
            grid_layout.addWidget(checkbox, row, col)
            col += 1
            if col >= 4:  # 4 columns max
                col = 0
                row += 1

        # Transmission parameters (only if multi-port)
        if dataset.n_ports > 1:
            if col > 0:  # Start new row if needed
                row += 1
                col = 0

            trans_label = QLabel("Transmission (Sij, i≠j):")
            trans_label.setStyleSheet("font-weight: bold;")
            grid_layout.addWidget(trans_label, row, 0, 1, -1)
            row += 1
            col = 0

            for i in range(dataset.n_ports):
                for j in range(dataset.n_ports):
                    if i != j:
                        # Standardized format: dataset_id:S{i},{j}_{chart_type}
                        trace_id = f"{dataset_id}:S{i+1},{j+1}_{self._chart_type}"

                        checkbox = QCheckBox(f"S{i+1},{j+1}")

                        # Check if this trace already exists in the chart
                        if trace_id in existing_traces_for_dataset:
                            checkbox.setChecked(True)
                            tooltip = f"Existing transmission from port {j+1} to port {i+1} (uncheck to remove)"
                            checkbox.setToolTip(tooltip)
                            checkbox.setStyleSheet("font-weight: bold; color: #2E7D32;")  # Green for existing
                            self._checkboxes[trace_id] = checkbox
                        else:
                            checkbox.setChecked(False)
                            checkbox.setToolTip(f"Add transmission from port {j+1} to port {i+1}")
                            checkbox.setStyleSheet("color: #1976D2;")  # Blue for new
                            # Map the new trace ID for adding new traces
                            self._checkboxes[trace_id] = checkbox
                        grid_layout.addWidget(checkbox, row, col)
                        col += 1
                        if col >= 4:  # 4 columns max
                            col = 0
                            row += 1

        param_layout.addLayout(grid_layout)
        param_layout.addStretch()

        self._param_scroll.setWidget(param_widget)
        self._param_scroll.setVisible(True)

        # Enable Apply button now that a dataset is selected
        self._apply_button.setEnabled(True)

    def _on_apply_clicked(self) -> None:
        """Apply current trace selections without closing the dialog."""
        # Signal the parent to apply current changes
        if hasattr(self, '_apply_callback') and self._apply_callback:
            traces_to_add = self.get_traces_to_add()
            traces_to_remove = self.get_traces_to_remove()
            selected_datasets = self.get_selected_datasets()

            # Call the callback to apply changes
            self._apply_callback(traces_to_add, traces_to_remove, selected_datasets)

            # Refresh the existing traces after applying changes
            self._refresh_existing_traces()

    def _refresh_existing_traces(self) -> None:
        """Refresh the existing traces and update the dialog."""
        # This will be set by the parent when creating the dialog
        if hasattr(self, '_refresh_callback') and self._refresh_callback:
            self._existing_traces = self._refresh_callback()

            # Refresh the current dataset view to show updated trace states
            if self._current_dataset_id:
                current_dataset_id = self._current_dataset_id

                # Reset current dataset ID to None to force refresh in _on_dataset_changed
                self._current_dataset_id = None

                # Find and select the same dataset again
                for i in range(self._dataset_combo.count()):
                    if self._dataset_combo.itemData(i) == current_dataset_id:
                        self._dataset_combo.setCurrentIndex(i)
                        break

                # Manually trigger _on_dataset_changed since setCurrentIndex might not trigger signal
                # if the index/text is the same
                self._on_dataset_changed()

    def get_traces_to_add(self) -> List[Tuple[str, Trace]]:
        """
        Get list of new traces to add to chart.

        Returns:
            List of (trace_id, Trace) tuples for new traces
        """
        traces_to_add = []

        # Get colors already in use to avoid duplication
        used_colors = set()
        for trace_id, (trace_dataset_id, trace, dataset_obj) in self._existing_traces.items():
            if hasattr(trace, 'style') and hasattr(trace.style, 'color'):
                used_colors.add(trace.style.color)

        # Start with colors not already in use
        available_colors = [c for c in DEFAULT_TRACE_COLORS if c not in used_colors]
        if not available_colors:
            # If all colors are used, cycle through all colors
            available_colors = DEFAULT_TRACE_COLORS

        color_index = 0

        # Get existing traces for current dataset
        existing_traces_for_dataset = {}
        if not self._current_dataset_id:
            # No current dataset selected, return empty list
            return traces_to_add

        selected_dataset = self._available_datasets[self._current_dataset_id]
        for trace_id, (trace_dataset_id, trace, dataset_obj) in self._existing_traces.items():
            # Match if it's the same dataset object or same dataset ID
            if dataset_obj is selected_dataset or trace_dataset_id == self._current_dataset_id:
                existing_traces_for_dataset[trace_id] = (trace_dataset_id, trace, dataset_obj)

        for trace_id, checkbox in self._checkboxes.items():
            # Check if checkbox is still valid (not deleted)
            try:
                is_checked = checkbox.isChecked()
            except RuntimeError:
                # Widget was deleted, skip it
                continue

            # Only add traces that are checked AND not already existing
            if is_checked and trace_id not in existing_traces_for_dataset:
                # Parse trace_id to get parameters
                # Format: dataset_id:S{i},{j}_{chart_type}
                if ':' not in trace_id:
                    continue  # Invalid format

                # Split dataset_id from rest
                _, rest = trace_id.split(':', 1)

                # Split S-parameter from chart type
                parts = rest.split('_')
                if not parts:
                    continue

                param = parts[0]  # e.g., "S1,2"

                # Parse port numbers - handle comma-separated format
                if param.startswith('S'):
                    param_part = param[1:]  # Remove 'S'
                    if ',' in param_part:
                        # Format: "S1,2"
                        port_parts = param_part.split(',')
                        i = int(port_parts[0])
                        j = int(port_parts[1])
                    else:
                        continue  # Invalid format, we only support comma-separated now
                else:
                    continue  # Invalid format

                # Determine metric based on chart type
                if self._chart_type.lower() == "magnitude":
                    metric = "magnitude_dB"
                elif self._chart_type.lower() == "phase":
                    metric = "phase_deg"
                elif self._chart_type.lower() in ['smith', 'smith_chart']:
                    metric = "reflection" if i == j else "transmission"
                else:
                    metric = self._chart_type.lower()

                # Create style with better color and style variety
                selected_color = available_colors[color_index % len(available_colors)]

                # Vary line styles for visual distinction
                line_style = DEFAULT_LINE_STYLES[(color_index // len(available_colors)) % len(DEFAULT_LINE_STYLES)]
                line_width = 2

                style = TraceStyle(
                    color=selected_color,
                    line_width=line_width,
                    line_style=line_style,
                    marker_style='none'
                )
                color_index += 1

                # Create trace
                trace = Trace(
                    id=trace_id,
                    dataset_id=self._current_dataset_id,
                    domain="S",
                    metric=metric,
                    port_path=PortPath(i=i, j=j),
                    style=style
                )

                traces_to_add.append((trace_id, trace))

        return traces_to_add

    def get_traces_to_remove(self) -> List[str]:
        """
        Get list of existing trace IDs to remove from chart.

        Returns:
            List of trace IDs to remove
        """
        traces_to_remove = []

        # Get existing traces for current dataset
        existing_traces_for_dataset = {}
        if not self._current_dataset_id:
            # No current dataset selected, return empty list
            return traces_to_remove

        selected_dataset = self._available_datasets[self._current_dataset_id]
        for trace_id, (trace_dataset_id, trace, dataset_obj) in self._existing_traces.items():
            # Match if it's the same dataset object or same dataset ID
            if dataset_obj is selected_dataset or trace_dataset_id == self._current_dataset_id:
                existing_traces_for_dataset[trace_id] = (trace_dataset_id, trace, dataset_obj)

        for trace_id, checkbox in self._checkboxes.items():
            # Only check traces that actually exist in the chart for this dataset
            if trace_id in existing_traces_for_dataset:
                # Check if checkbox is still valid (not deleted)
                try:
                    is_checked = checkbox.isChecked()
                except RuntimeError:
                    # Widget was deleted, skip it
                    continue

                if not is_checked:  # Unchecked means remove
                    traces_to_remove.append(trace_id)

        return traces_to_remove

    def get_selected_datasets(self) -> Dict[str, Dataset]:
        """
        Get dictionary of datasets that have traces being added.

        Returns:
            Dictionary of {dataset_id: Dataset}
        """
        selected_datasets = {}

        # Get existing traces for current dataset
        existing_traces_for_dataset = {}
        if not self._current_dataset_id:
            # No current dataset selected, return empty dict
            return selected_datasets

        selected_dataset = self._available_datasets[self._current_dataset_id]
        for trace_id, (trace_dataset_id, trace, dataset_obj) in self._existing_traces.items():
            # Match if it's the same dataset object or same dataset ID
            if dataset_obj is selected_dataset or trace_dataset_id == self._current_dataset_id:
                existing_traces_for_dataset[trace_id] = (trace_dataset_id, trace, dataset_obj)

        for trace_id, checkbox in self._checkboxes.items():
            # Check if checkbox is still valid (not deleted)
            try:
                is_checked = checkbox.isChecked()
            except RuntimeError:
                # Widget was deleted, skip it
                continue

            # Only include dataset if we have new traces being added
            if is_checked and trace_id not in existing_traces_for_dataset:
                # Since we now only show one dataset at a time, use the current dataset
                if self._current_dataset_id and self._current_dataset_id not in selected_datasets:
                    selected_datasets[self._current_dataset_id] = self._available_datasets[self._current_dataset_id]

        return selected_datasets
