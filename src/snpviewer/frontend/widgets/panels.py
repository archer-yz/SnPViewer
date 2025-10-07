"""
Panel widgets for the main application layout.

Provides the dataset browser panel and charts area scaffolding
for organizing and displaying S-parameter data and visualizations.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Optional

from PySide6 import QtGui
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QMenu, QMessageBox,
                               QPushButton, QScrollArea, QSplitter, QTabBar,
                               QTabWidget, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget, QInputDialog)

from snpviewer.backend.models.chart import Chart
from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.project import Project


class DatasetBrowserPanel(QWidget):
    """
    Dataset browser panel for managing loaded datasets and projects.

    Provides a tree view of datasets with metadata display and
    drag-and-drop support for creating charts.

    Signals:
        dataset_selected: Emitted when a dataset is selected
        dataset_double_clicked: Emitted when a dataset is double-clicked
        create_chart_requested: Emitted when user wants to create a chart_
    """

    dataset_selected = Signal(str)  # dataset_id
    dataset_double_clicked = Signal(str)  # dataset_id
    create_chart_requested = Signal(str, str)  # dataset_id, chart_type
    dataset_removed = Signal(str, str)  # user_friendly_name, dataset_uuid
    dataset_renamed = Signal(str, str)  # dataset_id, new_display_name
    add_parameter_to_chart_requested = Signal(str, str, str)  # chart_id, dataset_id, param_name

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the dataset browser panel."""
        super().__init__(parent)

        self._current_project: Optional[Project] = None
        self._datasets: Dict[str, Dataset] = {}
        self._newly_added_datasets: set[str] = set()  # Track newly added datasets for collapsing

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Title
        title_label = QLabel("Dataset Browser")
        # Use the palette to set color for both light and dark themes
        palette = title_label.palette()
        text_color = palette.color(title_label.foregroundRole())
        title_label.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {text_color.name()};")
        layout.addWidget(title_label)

        # Dataset tree
        self._dataset_tree = QTreeWidget()
        self._dataset_tree.setHeaderLabels(["Name", "Type", "Points", "Ports"])
        self._dataset_tree.setRootIsDecorated(True)
        self._dataset_tree.setAlternatingRowColors(True)
        self._dataset_tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self._dataset_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # Configure header
        header = self._dataset_tree.header()
        header.setDefaultSectionSize(120)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        # Create a splitter for tree and details
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.addWidget(self._dataset_tree)

        details_group = QGroupBox("Dataset Details")
        details_layout = QVBoxLayout(details_group)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)

        self._details_scroll = QScrollArea()
        self._details_scroll.setWidgetResizable(True)
        self._details_scroll.setMaximumHeight(16777215)  # Remove height limit

        self._details_widget = QWidget()
        self._details_layout = QVBoxLayout(self._details_widget)
        self._details_layout.setContentsMargins(5, 5, 5, 5)

        self._details_label = QLabel("Select a dataset to view details")
        self._details_label.setWordWrap(True)
        self._details_label.setStyleSheet("color: gray; font-style: italic;")
        self._details_layout.addWidget(self._details_label)

        self._details_scroll.setWidget(self._details_widget)
        details_layout.addWidget(self._details_scroll)

        self._splitter.addWidget(details_group)

        # Set initial splitter sizes (2:1 ratio - tree larger than details)
        self._splitter.setSizes([400, 200])
        self._splitter.setCollapsible(0, False)  # Don't allow tree to collapse
        self._splitter.setCollapsible(1, False)  # Don't allow details to collapse

        layout.addWidget(self._splitter)

        # Action buttons
        button_layout = QHBoxLayout()

        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.setToolTip("Refresh the dataset list")
        button_layout.addWidget(self._refresh_button)

        self._remove_button = QPushButton("Remove")
        self._remove_button.setToolTip("Remove selected dataset")
        self._remove_button.setEnabled(False)
        button_layout.addWidget(self._remove_button)

        button_layout.addStretch()

        layout.addLayout(button_layout)

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        self._dataset_tree.itemSelectionChanged.connect(self._on_selection_changed)
        self._dataset_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._dataset_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._dataset_tree.customContextMenuRequested.connect(self._show_context_menu)

        self._refresh_button.clicked.connect(self._refresh_datasets)
        self._remove_button.clicked.connect(self._remove_selected_dataset)

    def set_project(self, project: Optional[Project]) -> None:
        """Set the current project and update the display."""
        self._current_project = project
        self._refresh_datasets()

    def add_dataset(self, dataset_id: str, dataset: Dataset) -> None:
        """Add a dataset to the browser."""
        # Ensure display name is unique and set on the dataset
        self._ensure_unique_display_name(dataset)

        self._datasets[dataset_id] = dataset
        self._newly_added_datasets.add(dataset_id)  # Mark as newly added
        self._refresh_datasets()

    def _ensure_unique_display_name(self, dataset: Dataset) -> None:
        """
        Ensure the dataset has a unique display name.

        If the display name conflicts with existing datasets, add (1), (2), etc.
        """
        # Get existing display names from all loaded datasets
        existing_names = {ds.display_name for ds in self._datasets.values()}

        # If no conflict, keep the current display_name
        if dataset.display_name not in existing_names:
            return

        # If duplicate, add (1), (2), etc.
        base_name = dataset.display_name
        counter = 1
        while f"{base_name} ({counter})" in existing_names:
            counter += 1

        dataset.display_name = f"{base_name} ({counter})"

    def rename_dataset(self, dataset_id: str, new_name: str) -> bool:
        """
        Rename a dataset's display name.

        Args:
            dataset_id: The dataset ID to rename
            new_name: The new display name

        Returns:
            True if renamed successfully, False otherwise
        """
        if dataset_id not in self._datasets:
            return False

        # Check if the new name is already in use by a different dataset
        for did, ds in self._datasets.items():
            if did != dataset_id and ds.display_name == new_name:
                return False

        # Update display name in the dataset model
        dataset = self._datasets[dataset_id]
        dataset.display_name = new_name

        # Emit signal so charts can update their legends
        self.dataset_renamed.emit(dataset_id, new_name)

        # Refresh the display
        self._refresh_datasets()

        return True

    def get_display_name(self, dataset_id: str) -> str:
        """Get the display name for a dataset."""
        dataset = self._datasets.get(dataset_id)
        return dataset.display_name if dataset else dataset_id

    def remove_dataset(self, dataset_id: str) -> None:
        """Remove a dataset from the browser."""
        dataset_uuid = None
        display_name = dataset_id  # Default to dataset_id

        if dataset_id in self._datasets:
            # Get the actual UUID and display name from the dataset object before removing it
            dataset_obj = self._datasets[dataset_id]
            dataset_uuid = dataset_obj.id
            display_name = dataset_obj.display_name
            del self._datasets[dataset_id]

        # Also remove from project if present
        if self._current_project and dataset_uuid:
            # Remove any dataset references with matching UUID
            self._current_project.dataset_refs = [
                ref for ref in self._current_project.dataset_refs
                if ref.dataset_id != dataset_uuid
            ]

        self._refresh_datasets()
        # Emit the display name (not dataset_id) and UUID for proper cleanup
        self.dataset_removed.emit(display_name, dataset_uuid or dataset_id)

    def get_dataset(self, dataset_id: str) -> Optional[Dataset]:
        """Get a dataset by ID."""
        return self._datasets.get(dataset_id)

    def clear_all_datasets(self) -> None:
        """Clear all datasets from the browser."""
        self._datasets.clear()
        self._newly_added_datasets.clear()
        self._current_project = None
        self._refresh_datasets()

    def _refresh_datasets(self) -> None:
        """Refresh the dataset tree display."""
        # Store existing expansion states before clearing
        existing_expansion_states = {}
        for i in range(self._dataset_tree.topLevelItemCount()):
            item = self._dataset_tree.topLevelItem(i)
            dataset_id = item.data(0, Qt.ItemDataRole.UserRole)
            if dataset_id:
                existing_expansion_states[dataset_id] = item.isExpanded()

        self._dataset_tree.clear()

        if not self._current_project and not self._datasets:
            # Show placeholder
            item = QTreeWidgetItem(["No datasets loaded", "", "", ""])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setForeground(0, QtGui.QColor("gray"))
            self._dataset_tree.addTopLevelItem(item)
            return

        # Add datasets from project
        if self._current_project:
            # Map project dataset UUIDs to loaded dataset user-friendly names
            project_uuids = {ref.dataset_id for ref in self._current_project.dataset_refs}

            for dataset_id, dataset in self._datasets.items():
                if hasattr(dataset, 'id') and dataset.id in project_uuids:
                    # This loaded dataset corresponds to a project dataset
                    self._add_dataset_item(dataset_id, dataset, from_project=True)
                else:
                    # This is a standalone dataset (not part of the project)
                    self._add_dataset_item(dataset_id, dataset, from_project=False)
        else:
            # No project - add all datasets as standalone
            for dataset_id, dataset in self._datasets.items():
                self._add_dataset_item(dataset_id, dataset, from_project=False)

        # Set expansion states: preserve existing states, collapse newly added datasets
        for i in range(self._dataset_tree.topLevelItemCount()):
            item = self._dataset_tree.topLevelItem(i)
            dataset_id = item.data(0, Qt.ItemDataRole.UserRole)
            if dataset_id:
                if dataset_id in self._newly_added_datasets:
                    # Newly added datasets should be collapsed
                    item.setExpanded(False)
                elif dataset_id in existing_expansion_states:
                    # Restore previous expansion state
                    item.setExpanded(existing_expansion_states[dataset_id])
                else:
                    # Default behavior for datasets that weren't previously in the tree
                    # (e.g., first time loading): expand them
                    item.setExpanded(True)

        # Clear the newly added list after processing
        self._newly_added_datasets.clear()

    def _add_dataset_item(self, dataset_id: str, dataset: Optional[Dataset], from_project: bool) -> None:
        """Add a dataset item to the tree."""
        # For project datasets, we might need to load the actual dataset
        if from_project and dataset is None:
            # Try to get the dataset from our loaded datasets
            dataset = self._datasets.get(dataset_id)

        # Use actual dataset information if available
        if dataset:
            # Use the display name from the dataset model
            name = dataset.display_name
            dataset_type = "S-Parameters"

            # Get number of frequency points
            if hasattr(dataset, 'frequency_hz') and dataset.frequency_hz is not None:
                points = str(len(dataset.frequency_hz))
            else:
                points = "N/A"

            # Get number of ports
            if hasattr(dataset, 's_params') and dataset.s_params is not None:
                n_ports = dataset.s_params.shape[1]
                ports = f"{n_ports}x{n_ports}"
            elif hasattr(dataset, 'n_ports'):
                ports = f"{dataset.n_ports}x{dataset.n_ports}"
            else:
                ports = "N/A"
        else:
            # Fallback for datasets we don't have loaded
            name = dataset_id
            dataset_type = "S-Parameters"
            points = "N/A"
            ports = "N/A"

        # Create tree item
        item = QTreeWidgetItem([name, dataset_type, points, ports])
        item.setData(0, Qt.ItemDataRole.UserRole, dataset_id)

        # Set icon and styling
        if from_project:
            item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
        else:
            item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))

        # Enable drag and drop
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)

        self._dataset_tree.addTopLevelItem(item)

        # Add parameter subitems if we have dataset details
        if dataset and hasattr(dataset, 's_params') and dataset.s_params is not None:
            n_ports = dataset.s_params.shape[1]
            for i in range(n_ports):
                for j in range(n_ports):
                    param_name = f"S{i+1},{j+1}"
                    param_item = QTreeWidgetItem([param_name, "S-Parameter", "", ""])
                    param_item.setData(0, Qt.ItemDataRole.UserRole, f"{dataset_id}:{param_name}")
                    param_item.setFlags(param_item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
                    item.addChild(param_item)

    def _on_selection_changed(self) -> None:
        """Handle selection change in the tree."""
        current_item = self._dataset_tree.currentItem()

        if current_item is None:
            self._remove_button.setEnabled(False)
            self._update_details(None)
            return

        dataset_id = current_item.data(0, Qt.ItemDataRole.UserRole)

        if dataset_id:
            # Extract base dataset ID (remove parameter suffix if present)
            base_dataset_id = dataset_id.split(':')[0]

            self._remove_button.setEnabled(True)
            self._update_details(base_dataset_id)
            self.dataset_selected.emit(base_dataset_id)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Handle double-click on tree item."""
        dataset_id = item.data(0, Qt.ItemDataRole.UserRole)
        if dataset_id:
            base_dataset_id = dataset_id.split(':')[0]
            self.dataset_double_clicked.emit(base_dataset_id)

    def _show_context_menu(self, position: QPoint) -> None:
        """Show context menu for dataset items."""
        item = self._dataset_tree.itemAt(position)
        if not item:
            return

        dataset_id = item.data(0, Qt.ItemDataRole.UserRole)
        if not dataset_id:
            return

        # Check if this is a child item (S-parameter) or parent item (dataset)
        is_child_item = ':' in dataset_id

        menu = QMenu(self)

        if is_child_item:
            # Context menu for S-parameter child items
            # Extract base dataset ID and parameter name
            base_dataset_id, param_name = dataset_id.split(':', 1)

            # Add to Chart action
            add_to_chart_action = menu.addAction("Add to Chart...")
            add_to_chart_action.triggered.connect(
                lambda: self._request_add_to_chart(base_dataset_id, param_name)
            )
        else:
            # Context menu for dataset parent items
            # Chart creation actions
            create_menu = menu.addMenu("Create Chart")

            magnitude_action = create_menu.addAction("Magnitude Plot")
            magnitude_action.triggered.connect(
                lambda: self.create_chart_requested.emit(dataset_id, "magnitude")
            )

            phase_action = create_menu.addAction("Phase Plot")
            phase_action.triggered.connect(
                lambda: self.create_chart_requested.emit(dataset_id, "phase")
            )

            smith_action = create_menu.addAction("Smith Chart")
            smith_action.triggered.connect(
                lambda: self.create_chart_requested.emit(dataset_id, "smith")
            )

            menu.addSeparator()

            # Rename action
            rename_action = menu.addAction("Rename Dataset...")
            rename_action.triggered.connect(
                lambda: self._show_rename_dialog(dataset_id)
            )

            # Dataset actions
            remove_action = menu.addAction("Remove Dataset")
            remove_action.triggered.connect(self._remove_selected_dataset)

        menu.exec(self._dataset_tree.mapToGlobal(position))

    def _update_details(self, dataset_id: Optional[str]) -> None:
        """Update the dataset details display."""
        # Clear existing details
        for i in reversed(range(self._details_layout.count())):
            child = self._details_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        if not dataset_id:
            label = QLabel("Select a dataset to view details")
            label.setStyleSheet("color: gray; font-style: italic;")
            self._details_layout.addWidget(label)
            return

        # Get dataset
        dataset = self._datasets.get(dataset_id)
        if not dataset:
            label = QLabel("Dataset details not available")
            label.setStyleSheet("color: red; font-style: italic;")
            self._details_layout.addWidget(label)
            return

        # Display dataset information
        info_text = f"""
        <b>File:</b> {Path(dataset.file_path).name}<br>
        <b>Path:</b> {dataset.file_path}<br>
        <b>Format:</b> {dataset.data_format}<br>
        <b>Reference Impedance:</b> {dataset.ref_impedance} Ω<br>
        """

        if hasattr(dataset, 'frequency_hz'):
            freq_start = dataset.frequency_hz[0] / 1e9
            freq_stop = dataset.frequency_hz[-1] / 1e9
            info_text += f"<b>Frequency Range:</b> {freq_start:.3f} - {freq_stop:.3f} GHz<br>"
            info_text += f"<b>Points:</b> {len(dataset.frequency_hz)}<br>"

        if hasattr(dataset, 's_params'):
            n_ports = dataset.s_params.shape[1]
            info_text += f"<b>Ports:</b> {n_ports}x{n_ports}<br>"

        # Add additional info
        info_text += "<br><b>Additional Info:</b><br>"
        info_text += f"  Version: {dataset.version}<br>"
        info_text += f"  Units: {dataset.units}<br>"
        if dataset.loaded_at:
            info_text += f"  Loaded: {dataset.loaded_at.strftime('%Y-%m-%d %H:%M:%S')}<br>"

        label = QLabel(info_text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        self._details_layout.addWidget(label)

    def _remove_selected_dataset(self) -> None:
        """Remove the selected dataset."""
        current_item = self._dataset_tree.currentItem()
        if not current_item:
            return

        dataset_id = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not dataset_id:
            return

        base_dataset_id = dataset_id.split(':')[0]

        reply = QMessageBox.question(
            self,
            "Remove Dataset",
            f"Are you sure you want to remove dataset '{base_dataset_id}'?\n\n"
            f"This will also close any charts using this dataset.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.remove_dataset(base_dataset_id)

    def _show_rename_dialog(self, dataset_id: str) -> None:
        """Show dialog to rename a dataset."""
        base_dataset_id = dataset_id.split(':')[0]
        current_name = self.get_display_name(base_dataset_id)

        new_name, ok = QInputDialog.getText(
            self,
            "Rename Dataset",
            "Enter new name for the dataset:",
            text=current_name
        )

        if ok and new_name.strip():
            new_name = new_name.strip()

            # Check if name is already in use
            if not self.rename_dataset(base_dataset_id, new_name):
                QMessageBox.warning(
                    self,
                    "Rename Failed",
                    f"The name '{new_name}' is already in use by another dataset."
                )
            else:
                # Success - the display has already been refreshed by rename_dataset
                pass

    def _request_add_to_chart(self, dataset_id: str, param_name: str) -> None:
        """
        Request to add a parameter to a chart. This will be handled by app.py.

        Args:
            dataset_id: The dataset ID containing the parameter
            param_name: The S-parameter name (e.g., "S1,1")
        """
        # Parse port numbers from param_name (e.g., "S1,1" -> (1, 1))
        # For now, we'll pass the param_name and let app.py handle the parsing
        # We emit a signal with empty chart_id - app.py will show a dialog to select the chart
        self.add_parameter_to_chart_requested.emit("", dataset_id, param_name)


class ChartsAreaPanel(QWidget):
    """
    Charts area panel for displaying and managing chart tabs.

    Provides a tabbed interface for multiple charts with support
    for different chart types and layouts.

    Signals:
        chart_selected: Emitted when a chart tab is selected
        chart_closed: Emitted when a chart is closed
    """

    chart_selected = Signal(str)  # chart_id
    chart_closed = Signal(str)  # chart_id

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the charts area panel."""
        super().__init__(parent)

        self._charts: Dict[str, Chart] = {}
        self._chart_datasets: Dict[str, str] = {}  # chart_id -> dataset_id mapping
        self._chart_counter: int = 0  # Counter for sequential chart naming

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Charts tab widget
        self._chart_tabs = QTabWidget()
        self._chart_tabs.setTabsClosable(True)
        self._chart_tabs.setMovable(True)
        self._chart_tabs.setDocumentMode(True)

        # Add placeholder tab
        self._add_placeholder_tab()

        layout.addWidget(self._chart_tabs)

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        self._chart_tabs.currentChanged.connect(self._on_tab_changed)
        self._chart_tabs.tabCloseRequested.connect(self._on_tab_close_requested)

    def _add_placeholder_tab(self) -> None:
        """Add a placeholder tab when no charts are open."""
        placeholder = QWidget()
        placeholder_layout = QVBoxLayout(placeholder)

        # Welcome message
        welcome_label = QLabel("Welcome to SnP Viewer")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #666;
            margin: 20px;
        """)

        instructions_label = QLabel("""
            <center>
            <p style="font-size: 14px; color: #888; margin: 10px;">
                To get started:<br>
                1. Use <b>File → Open File</b> to load Touchstone files<br>
                2. Drag datasets from the browser to create charts<br>
                3. Right-click datasets to create specific chart types
            </p>
            </center>
        """)
        instructions_label.setTextFormat(Qt.TextFormat.RichText)
        instructions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        placeholder_layout.addStretch()
        placeholder_layout.addWidget(welcome_label)
        placeholder_layout.addWidget(instructions_label)
        placeholder_layout.addStretch()

        self._chart_tabs.addTab(placeholder, "Welcome")

        # Disable close button for placeholder
        self._chart_tabs.tabBar().setTabButton(0, QTabBar.ButtonPosition.RightSide, None)

    def get_next_chart_number(self) -> int:
        """Get the next chart number for naming purposes."""
        return self._chart_counter + 1

    def add_chart(self, chart_id: str, chart: Chart, widget: QWidget, dataset_id: str = None) -> None:
        """Add a new chart tab."""
        # Remove placeholder if this is the first real chart
        if self._chart_tabs.count() == 1 and not self._charts:
            self._chart_tabs.removeTab(0)

        self._charts[chart_id] = chart

        # Track dataset association if provided
        if dataset_id:
            self._chart_datasets[chart_id] = dataset_id

        # Increment chart counter
        self._chart_counter += 1

        # Add tab - use the widget's tab title if it has one, otherwise use chart title
        if hasattr(widget, 'get_tab_title'):
            tab_title = widget.get_tab_title()
        else:
            tab_title = chart.title

        # Ensure the tab title is unique
        unique_tab_title, unique_tab_title_no_type = self._ensure_unique_chart_tab_title(tab_title, chart_id)

        # Update the chart's tab_title to the unique version
        chart.tab_title = unique_tab_title_no_type

        # Update the widget's tab title if it was changed
        if unique_tab_title != tab_title and hasattr(widget, 'set_chart_tab_title'):
            widget.set_chart_tab_title(unique_tab_title_no_type)

        tab_index = self._chart_tabs.addTab(widget, unique_tab_title)
        self._chart_tabs.setCurrentIndex(tab_index)

        # Store chart ID in tab data using tabBar
        self._chart_tabs.tabBar().setTabData(tab_index, chart_id)

        # Connect to tab title changes if the widget supports it
        if hasattr(widget, 'tab_title_changed'):
            widget.tab_title_changed.connect(
                lambda new_title, new_title_no_type, cid=chart_id: self._update_tab_title(
                    cid, new_title, new_title_no_type)
            )
            # widget.tab_title_changed.connect(
            #     lambda _, new_title, cid=chart_id: self._update_chart_tab_title(cid, new_title)
            # )

        if hasattr(widget, 'chart_title_changed'):
            widget.chart_title_changed.connect(
                lambda new_title, cid=chart_id: self._update_chart_title(cid, new_title)
            )

    def _ensure_unique_chart_tab_title(self, desired_title: str, current_chart_id: str) -> tuple[str, str]:
        """
        Ensure the chart tab title is unique among all charts.

        Args:
            desired_title: The desired tab title
            current_chart_id: The ID of the chart being renamed

        Returns:
            str: A unique tab title with plot type, potentially with a suffix like (1), (2), etc.
            str: The tab title without the plot type suffix
        """
        existing_titles = set()
        for i in range(self._chart_tabs.count()):
            tab_chart_id = self._chart_tabs.tabBar().tabData(i)
            if tab_chart_id and tab_chart_id != current_chart_id:
                existing_titles.add(self._chart_tabs.tabText(i))

        if desired_title not in existing_titles:
            return desired_title, re.sub(r'\s*\([^()]*\)\s*$', '', desired_title)

        # Find a unique suffix
        counter = 1
        new_title = re.sub(r'(\s*)(\([^)]*\))$', rf' ({counter})\1\2', desired_title)
        while new_title in existing_titles:
            counter += 1
            new_title = re.sub(r'(\s*)(\([^)]*\))$', rf' ({counter})\1\2', desired_title)

        return new_title, re.sub(r'\s*\([^()]*\)\s*$', '', new_title)

    def _update_chart_title(self, chart_id: str, new_title: str) -> None:
        """Update the chart model's title when the chart title changes."""
        if chart_id in self._charts:
            self._charts[chart_id].title = new_title

    def remove_chart(self, chart_id: str) -> None:
        """Remove a chart tab."""
        if chart_id not in self._charts:
            return

        # Find tab index
        for i in range(self._chart_tabs.count()):
            if self._chart_tabs.tabBar().tabData(i) == chart_id:
                self._chart_tabs.removeTab(i)
                break

        del self._charts[chart_id]

        # Clean up dataset mapping
        if chart_id in self._chart_datasets:
            del self._chart_datasets[chart_id]

        # Add placeholder if no charts left
        if not self._charts:
            self._add_placeholder_tab()

    def _update_tab_title(self, chart_id: str, new_title: str) -> None:
        """Update the tab title for a specific chart."""
        # Ensure the new title is unique
        unique_title, unique_title_no_type = self._ensure_unique_chart_tab_title(new_title, chart_id)

        # Find tab index for this chart and update
        for i in range(self._chart_tabs.count()):
            if self._chart_tabs.tabBar().tabData(i) == chart_id:
                self._chart_tabs.setTabText(i, unique_title)

                # Update the chart model
                self._charts[chart_id].tab_title = unique_title_no_type
                break

    def get_current_chart_id(self) -> Optional[str]:
        """Get the ID of the currently selected chart."""
        current_index = self._chart_tabs.currentIndex()
        if current_index >= 0:
            return self._chart_tabs.tabBar().tabData(current_index)
        return None

    def get_chart_list(self) -> list[tuple[str, str]]:
        """
        Get a list of all charts for selection dialogs.

        Returns:
            List of tuples (chart_id, chart_tab_title)
        """
        chart_list = []
        for i in range(self._chart_tabs.count()):
            chart_id = self._chart_tabs.tabBar().tabData(i)
            if chart_id:  # Skip placeholder tabs
                tab_title = self._chart_tabs.tabText(i)
                chart_list.append((chart_id, tab_title))
        return chart_list

    def get_chart_widget(self, chart_id: str) -> Optional[QWidget]:
        """
        Get the widget for a specific chart.

        Args:
            chart_id: The chart ID

        Returns:
            The chart widget, or None if not found
        """
        for i in range(self._chart_tabs.count()):
            if self._chart_tabs.tabBar().tabData(i) == chart_id:
                return self._chart_tabs.widget(i)
        return None

    def get_all_charts(self) -> Dict[str, Dict]:
        """Get all charts with their associated information."""
        result = {}
        for chart_id, chart in self._charts.items():
            # Find the widget for this chart by searching through tabs
            widget = None
            for i in range(self._chart_tabs.count()):
                if self._chart_tabs.tabBar().tabData(i) == chart_id:
                    widget = self._chart_tabs.widget(i)
                    break

            result[chart_id] = {
                'chart': chart,
                'widget': widget,
                'dataset_id': self._chart_datasets.get(chart_id)
            }
        return result

    def remove_traces_by_dataset(self, dataset_id: str) -> tuple[int, int]:
        """
        Remove all traces from the specified dataset across all charts.

        Args:
            dataset_id: ID of the dataset whose traces should be removed

        Returns:
            Tuple of (traces_removed, charts_affected)
        """
        traces_removed = 0
        charts_affected = 0
        charts_to_remove = []

        # Go through all chart widgets and remove traces from this dataset
        for i in range(self._chart_tabs.count()):
            widget = self._chart_tabs.widget(i)
            if hasattr(widget, 'remove_traces_by_dataset'):
                removed_count = widget.remove_traces_by_dataset(dataset_id)
                if removed_count > 0:
                    traces_removed += removed_count
                    charts_affected += 1

                    # Check if chart is now empty and should be removed
                    if hasattr(widget, 'get_existing_trace_ids'):
                        remaining_traces = widget.get_existing_trace_ids()
                        if not remaining_traces:
                            chart_id = self._chart_tabs.tabBar().tabData(i)
                            if chart_id:
                                charts_to_remove.append(chart_id)

        # Remove empty charts
        for chart_id in charts_to_remove:
            self.remove_chart(chart_id)

        return traces_removed, charts_affected

    def remove_charts_by_dataset(self, dataset_id: str) -> None:
        """Remove all charts that use the specified dataset (legacy method)."""
        charts_to_remove = []

        # First, try using the direct dataset mapping
        for chart_id, mapped_dataset_id in self._chart_datasets.items():
            if mapped_dataset_id == dataset_id:
                charts_to_remove.append(chart_id)

        # Fallback: check chart titles for dataset identification
        # This handles cases where the mapping might not be available
        if not charts_to_remove:
            for chart_id, chart in self._charts.items():
                # Charts are titled like "Magnitude Chart - filename.s2p"
                if " - " in chart.title:
                    # Extract the filename part from the chart title
                    chart_filename = chart.title.split(" - ", 1)[1]
                    # If the dataset_id matches the filename or is part of the title
                    if dataset_id == chart_filename or dataset_id in chart.title:
                        charts_to_remove.append(chart_id)

        # Remove found charts
        for chart_id in charts_to_remove:
            self.remove_chart(chart_id)

        # Show feedback if charts were removed
        if charts_to_remove:
            print(f"Removed {len(charts_to_remove)} chart(s) using dataset {dataset_id}")

    def clear_all_charts(self) -> None:
        """Clear all charts from the area."""
        # Clear all tabs except placeholder
        while self._chart_tabs.count() > 0:
            self._chart_tabs.removeTab(0)

        # Clear internal data structures
        self._charts.clear()
        self._chart_datasets.clear()
        self._chart_counter = 0  # Reset counter when clearing all charts

        # Add back the placeholder
        self._add_placeholder_tab()

    def _on_tab_changed(self, index: int) -> None:
        """Handle tab selection change."""
        chart_id = self._chart_tabs.tabBar().tabData(index)
        if chart_id:
            self.chart_selected.emit(chart_id)

    def _on_tab_close_requested(self, index: int) -> None:
        """Handle tab close request."""
        chart_id = self._chart_tabs.tabBar().tabData(index)
        if chart_id:
            self.chart_closed.emit(chart_id)


class MainPanelLayout(QWidget):
    """
    Main panel layout combining dataset browser and charts area.

    Provides the complete layout for the main window with proper
    splitter management and panel coordination.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the main panel layout."""
        super().__init__(parent)

        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create main splitter
        self._main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Create panels
        self._dataset_browser = DatasetBrowserPanel()
        self._charts_area = ChartsAreaPanel()

        # Configure panels
        self._dataset_browser.setMinimumWidth(250)
        self._dataset_browser.setMaximumWidth(500)

        # Add panels to splitter
        self._main_splitter.addWidget(self._dataset_browser)
        self._main_splitter.addWidget(self._charts_area)

        # Set initial sizes (1:3 ratio)
        self._main_splitter.setSizes([300, 900])

        layout.addWidget(self._main_splitter)

    def _setup_connections(self) -> None:
        """Setup signal connections between panels."""
        # Forward signals from panels
        self._dataset_browser.dataset_selected.connect(self._on_dataset_selected)
        self._dataset_browser.dataset_double_clicked.connect(self._on_dataset_double_clicked)
        self._dataset_browser.create_chart_requested.connect(self._on_create_chart_requested)

        self._charts_area.chart_selected.connect(self._on_chart_selected)
        self._charts_area.chart_closed.connect(self._on_chart_closed)

    # Properties for accessing panels
    @property
    def dataset_browser(self) -> DatasetBrowserPanel:
        """Get the dataset browser panel."""
        return self._dataset_browser

    @property
    def charts_area(self) -> ChartsAreaPanel:
        """Get the charts area panel."""
        return self._charts_area

    @property
    def splitter(self) -> QSplitter:
        """Get the main splitter."""
        return self._main_splitter

    # Panel event handlers
    def _on_dataset_selected(self, dataset_id: str) -> None:
        """Handle dataset selection."""
        # Could implement cross-panel coordination here
        pass

    def _on_dataset_double_clicked(self, dataset_id: str) -> None:
        """Handle dataset double-click."""
        # Could auto-create a default chart
        pass

    def _on_create_chart_requested(self, dataset_id: str, chart_type: str) -> None:
        """Handle chart creation request."""
        # This would be handled by the main window
        pass

    def _on_chart_selected(self, chart_id: str) -> None:
        """Handle chart selection."""
        # Could update other UI elements based on selected chart
        pass

    def _on_chart_closed(self, chart_id: str) -> None:
        """Handle chart close."""
        # Clean up chart resources
        pass
