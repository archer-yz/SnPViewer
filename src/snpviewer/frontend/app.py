"""
Main application window for SnPViewer.

Provides the primary user interface with menu system, toolbar, and layout
for dataset browsing, chart viewing, and project management functionality.
"""
from __future__ import annotations

import ctypes
import json
import platform
import sys
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
from PySide6 import QtGui
from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                               QFileDialog, QLabel, QListWidget, QMainWindow,
                               QMessageBox, QProgressBar, QVBoxLayout, QWidget)

import snpviewer.frontend.resources_rc  # noqa: F401
from snpviewer.backend import parse_touchstone
from snpviewer.backend.conversions import touchstone_to_dataset
from snpviewer.backend.models.chart import AxisConfiguration, Chart, ChartAxes
from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.project import DatasetRef, Preferences, Project
from snpviewer.backend.models.trace import PortPath, Trace, TraceStyle
from snpviewer.frontend.constants import (DEFAULT_LINE_STYLES,
                                          DEFAULT_TRACE_COLORS)
from snpviewer.frontend.dialogs.add_traces import AddTracesDialog
from snpviewer.frontend.dialogs.create_chart import CreateChartDialog
from snpviewer.frontend.dialogs.linear_phase_error import LinearPhaseErrorDialog
from snpviewer.frontend.dialogs.phase_difference import PhaseDifferenceDialog
from snpviewer.frontend.dialogs.preferences import PreferencesDialog
from snpviewer.frontend.dialogs.trace_selection import TraceSelectionDialog
from snpviewer.frontend.plotting.plot_pipelines import PlotType
from snpviewer.frontend.services.loader import ThreadedLoader
from snpviewer.frontend.widgets.chart_view import ChartView
from snpviewer.frontend.widgets.panels import MainPanelLayout
from snpviewer.frontend.widgets.smith_view import SmithView


class SnPViewerMainWindow(QMainWindow):
    """
    Main application window for SnPViewer.

    Provides file management, project operations, and UI coordination
    for RF parameter visualization and analysis.

    Signals:
        file_opened: Emitted when a Touchstone file is successfully opened
        project_loaded: Emitted when a project file is loaded
        project_saved: Emitted when a project is saved
    """

    file_opened = Signal(str)  # file_path
    project_loaded = Signal(Project)
    project_saved = Signal(str)  # file_path

    def __init__(self, parent: Optional[QWidget] = None):
        """Initialize the main window."""
        super().__init__(parent)

        # Application state
        self._current_project: Optional[Project] = None
        self._current_project_path: Optional[Path] = None
        self._modified: bool = False

        # Settings
        self._settings = QSettings("SnPViewer", "SnPViewer")

        # Initialize UI
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_layout()

        # Restore window state
        self._restore_settings()

        # Setup autosave timer
        self._autosave_timer = QTimer()
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(30000)  # Autosave every 30 seconds

        # Setup threaded loader
        self._loader = ThreadedLoader(self)
        self._loader.started.connect(self._on_file_load_started)
        self._loader.progress.connect(self._on_file_load_progress)
        self._loader.finished.connect(self._on_file_load_finished)
        self._loader.error.connect(self._on_file_load_error)
        self._loader.all_finished.connect(self._on_all_files_loaded)

    def _setup_ui(self) -> None:
        """Setup basic UI properties."""
        self.setWindowTitle("SnP Viewer")
        self.setWindowIcon(QIcon(":/icons/snpviewer.ico"))
        self.setMinimumSize(1000, 700)
        self.resize(1366, 768)

    def _setup_menus(self) -> None:
        """Setup the menu bar and actions."""
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        # Open File action
        self._open_file_action = QAction("&Open Files...", self)
        self._open_file_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_file_action.setStatusTip("Open Touchstone files (supports multiple selection)")
        self._open_file_action.triggered.connect(self._open_file)
        file_menu.addAction(self._open_file_action)

        # Open Folder action
        self._open_folder_action = QAction("Open &Folder...", self)
        self._open_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self._open_folder_action.setStatusTip("Open folder (non-recursive)")
        self._open_folder_action.triggered.connect(self._open_folder)
        file_menu.addAction(self._open_folder_action)

        file_menu.addSeparator()

        # New Project action
        self._new_project_action = QAction("&New Project", self)
        self._new_project_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_project_action.setStatusTip("Create a new project")
        self._new_project_action.triggered.connect(self._new_project)
        file_menu.addAction(self._new_project_action)

        # Open Project action
        self._open_project_action = QAction("Open &Project...", self)
        self._open_project_action.setShortcut(QKeySequence("Ctrl+Alt+O"))
        self._open_project_action.setStatusTip("Open an existing project")
        self._open_project_action.triggered.connect(self._open_project)
        file_menu.addAction(self._open_project_action)

        # Save Project action
        self._save_project_action = QAction("&Save Project", self)
        self._save_project_action.setShortcut(QKeySequence.StandardKey.Save)
        self._save_project_action.setStatusTip("Save the current project")
        self._save_project_action.triggered.connect(self._save_project)
        self._save_project_action.setEnabled(False)
        file_menu.addAction(self._save_project_action)

        # Save Project As action
        self._save_project_as_action = QAction("Save Project &As...", self)
        self._save_project_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self._save_project_as_action.setStatusTip("Save the project with a new name")
        self._save_project_as_action.triggered.connect(self._save_project_as)
        self._save_project_as_action.setEnabled(False)
        file_menu.addAction(self._save_project_as_action)

        file_menu.addSeparator()

        # Close Project action
        self._close_project_action = QAction("&Close Project", self)
        self._close_project_action.setShortcut(QKeySequence("Ctrl+W"))
        self._close_project_action.setStatusTip("Close the current project")
        self._close_project_action.triggered.connect(self._close_project)
        self._close_project_action.setEnabled(False)
        file_menu.addAction(self._close_project_action)

        file_menu.addSeparator()

        # Export action
        self._export_action = QAction("&Export...", self)
        self._export_action.setShortcut(QKeySequence("Ctrl+E"))
        self._export_action.setStatusTip("Export charts and data")
        self._export_action.triggered.connect(self._export)
        self._export_action.setEnabled(False)
        file_menu.addAction(self._export_action)

        file_menu.addSeparator()

        # Recent Files submenu
        self._recent_files_menu = file_menu.addMenu("Recent &Files")
        self._update_recent_files_menu()

        file_menu.addSeparator()

        # Exit action
        self._exit_action = QAction("E&xit", self)
        self._exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._exit_action.setStatusTip("Exit the application")
        self._exit_action.triggered.connect(self.close)
        file_menu.addAction(self._exit_action)

        # Chart Menu
        chart_menu = menubar.addMenu("&Chart")

        # Create Chart action
        self._create_chart_action = QAction("&Create Chart...", self)
        self._create_chart_action.setShortcut(QKeySequence("Ctrl+N"))
        self._create_chart_action.setStatusTip("Create a new chart with multiple datasets")
        self._create_chart_action.triggered.connect(self._create_new_chart)
        chart_menu.addAction(self._create_chart_action)

        # Duplicate Chart action
        self._duplicate_chart_action = QAction("&Duplicate Chart", self)
        self._duplicate_chart_action.setShortcut(QKeySequence("Ctrl+D"))
        self._duplicate_chart_action.setStatusTip("Duplicate the current chart with all settings")
        self._duplicate_chart_action.triggered.connect(self._duplicate_current_chart)
        chart_menu.addAction(self._duplicate_chart_action)

        # View Menu
        view_menu = menubar.addMenu("&View")

        # Show/Hide panels
        self._show_dataset_browser_action = QAction("&Dataset Browser", self)
        self._show_dataset_browser_action.setCheckable(True)
        self._show_dataset_browser_action.setChecked(True)
        self._show_dataset_browser_action.setStatusTip("Show/hide dataset browser")
        self._show_dataset_browser_action.triggered.connect(self._toggle_dataset_browser)
        view_menu.addAction(self._show_dataset_browser_action)

        self._show_toolbar_action = QAction("&Toolbar", self)
        self._show_toolbar_action.setCheckable(True)
        self._show_toolbar_action.setChecked(True)
        self._show_toolbar_action.setStatusTip("Show/hide toolbar")
        self._show_toolbar_action.triggered.connect(self._toggle_toolbar)
        view_menu.addAction(self._show_toolbar_action)

        self._show_status_bar_action = QAction("&Status Bar", self)
        self._show_status_bar_action.setCheckable(True)
        self._show_status_bar_action.setChecked(True)
        self._show_status_bar_action.setStatusTip("Show/hide status bar")
        self._show_status_bar_action.triggered.connect(self._toggle_status_bar)
        view_menu.addAction(self._show_status_bar_action)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")

        # Linear Phase Error Analysis action
        self._linear_phase_error_action = QAction("&Linear Phase Error Analysis...", self)
        self._linear_phase_error_action.setShortcut(QKeySequence("Ctrl+L"))
        self._linear_phase_error_action.setStatusTip("Analyze linear phase errors in S-parameters")
        self._linear_phase_error_action.triggered.connect(self._show_linear_phase_error_analysis)
        tools_menu.addAction(self._linear_phase_error_action)

        # Phase Difference Analysis action
        self._phase_difference_action = QAction("&Phase Difference Analysis...", self)
        self._phase_difference_action.setShortcut(QKeySequence("Ctrl+D"))
        self._phase_difference_action.setStatusTip("Compare phase differences between datasets")
        self._phase_difference_action.triggered.connect(self._show_phase_difference_analysis)
        tools_menu.addAction(self._phase_difference_action)

        tools_menu.addSeparator()

        # Preferences action
        self._preferences_action = QAction("&Preferences...", self)
        self._preferences_action.setStatusTip("Open preferences dialog")
        self._preferences_action.triggered.connect(self._show_preferences)
        tools_menu.addAction(self._preferences_action)

        # Help Menu
        help_menu = menubar.addMenu("&Help")

        # About action
        self._about_action = QAction("&About SnP Viewer", self)
        self._about_action.setStatusTip("About this application")
        self._about_action.triggered.connect(self._show_about)
        help_menu.addAction(self._about_action)

        # About Qt action
        self._about_qt_action = QAction("About &Qt", self)
        self._about_qt_action.setStatusTip("About Qt")
        self._about_qt_action.triggered.connect(QApplication.aboutQt)
        help_menu.addAction(self._about_qt_action)

    def _setup_toolbar(self) -> None:
        """Setup the main toolbar."""
        self._toolbar = self.addToolBar("Main")
        self._toolbar.setObjectName("MainToolBar")

        # Add frequently used actions to toolbar
        self._toolbar.addAction(self._open_file_action)
        self._toolbar.addAction(self._open_folder_action)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._new_project_action)
        self._toolbar.addAction(self._open_project_action)
        self._toolbar.addAction(self._save_project_action)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._create_chart_action)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._linear_phase_error_action)
        self._toolbar.addAction(self._phase_difference_action)
        self._toolbar.addSeparator()
        self._toolbar.addAction(self._export_action)

    def _setup_status_bar(self) -> None:
        """Setup the status bar."""
        self._status_bar = self.statusBar()

        # Project info label
        self._project_label = QLabel("No project")
        self._status_bar.addWidget(self._project_label)

        # Progress bar for file operations
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setMaximumWidth(200)
        self._status_bar.addPermanentWidget(self._progress_bar)

        # Memory usage label
        self._memory_label = QLabel()
        self._status_bar.addPermanentWidget(self._memory_label)

        # Update memory usage periodically
        self._memory_timer = QTimer()
        self._memory_timer.timeout.connect(self._update_memory_usage)
        self._memory_timer.start(5000)  # Update every 5 seconds

    def _setup_layout(self) -> None:
        """Setup the main window layout."""
        # Create main panel layout with dataset browser and charts area
        self._main_panels = MainPanelLayout()
        self.setCentralWidget(self._main_panels)

        # Connect panel signals
        self._setup_panel_connections()

    def _setup_panel_connections(self) -> None:
        """Setup connections between panels and main window."""
        # Dataset browser signals
        dataset_browser = self._main_panels.dataset_browser
        dataset_browser.dataset_selected.connect(self._on_dataset_selected)
        dataset_browser.dataset_double_clicked.connect(self._on_dataset_double_clicked)
        dataset_browser.create_chart_requested.connect(self._on_create_chart_requested)
        dataset_browser.dataset_removed.connect(self._on_dataset_removed)
        dataset_browser.dataset_renamed.connect(self._on_dataset_renamed)
        dataset_browser.add_parameter_to_chart_requested.connect(self._on_add_parameter_to_chart_requested)

        # Charts area signals
        charts_area = self._main_panels.charts_area
        charts_area.chart_selected.connect(self._on_chart_selected)
        charts_area.chart_closed.connect(self._on_chart_closed)
        charts_area.duplicate_chart_requested.connect(self._on_duplicate_chart_requested)

        # Project signals
        self.project_loaded.connect(self._on_project_loaded)

    def _restore_settings(self) -> None:
        """Restore window settings from previous session."""
        # Restore window geometry
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Restore window state
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)

        # Restore splitter state
        splitter_state = self._settings.value("splitterState")
        if splitter_state and hasattr(self, '_main_panels'):
            self._main_panels.splitter.restoreState(splitter_state)

    def _save_settings(self) -> None:
        """Save window settings for next session."""
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        if hasattr(self, '_main_panels'):
            self._settings.setValue("splitterState", self._main_panels.splitter.saveState())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle application close event."""
        if self._check_unsaved_changes():
            self._save_settings()
            event.accept()
        else:
            event.ignore()

    def _check_unsaved_changes(self) -> bool:
        """Check for unsaved changes and prompt user if needed."""
        if not self._modified:
            return True

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "The current project has unsaved changes. Do you want to save them?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save
        )

        if reply == QMessageBox.StandardButton.Save:
            return self._save_project()
        elif reply == QMessageBox.StandardButton.Discard:
            return True
        else:  # Cancel
            return False

    # File Operations
    def _open_file(self) -> None:
        """Open Touchstone files (supports multiple selection)."""
        # Generate Touchstone file patterns (s1p to s99p)
        touchstone_patterns = []
        for i in range(1, 100):  # Support 1 to 99 ports
            touchstone_patterns.append(f"*.s{i}p")
        touchstone_patterns.append("*.ts")  # Add .ts format

        filter_string = f"Touchstone Files ({' '.join(touchstone_patterns)});;All Files (*)"

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open Touchstone Files",
            str(self._get_last_directory()),
            filter_string
        )

        if file_paths:
            # Save the directory from the first file
            self._save_last_directory(file_paths[0])

            # Load all selected files
            self._load_touchstone_files(file_paths)

    def _open_folder(self) -> None:
        """Open a folder and load all Touchstone files (non-recursive)."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
            str(self._get_last_directory())
        )

        if folder_path:
            self._load_touchstone_folder(folder_path)

    def _load_touchstone_file(self, file_path: str) -> None:
        """Load a single Touchstone file using threaded loader."""
        # Check if file is already loaded
        if self._current_project and self._is_file_already_loaded(file_path):
            file_name = Path(file_path).name
            reply = QMessageBox.question(
                self,
                "File Already Loaded",
                f"The file '{file_name}' is already loaded in the current project.\n\n"
                "Do you want to reload it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.No:
                return

        # Use the threaded loader to load the file asynchronously
        self._loader.load_file(file_path)

    def _load_touchstone_files(self, file_paths: list[str]) -> None:
        """Load multiple Touchstone files using threaded loader."""
        # Filter out already loaded files (with confirmation)
        files_to_load = []

        for file_path in file_paths:
            if self._current_project and self._is_file_already_loaded(file_path):
                file_name = Path(file_path).name
                reply = QMessageBox.question(
                    self,
                    "File Already Loaded",
                    f"The file '{file_name}' is already loaded in the current project.\n\n"
                    "Do you want to reload it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    files_to_load.append(file_path)
            else:
                files_to_load.append(file_path)

        if files_to_load:
            # Use the threaded loader to load all files asynchronously
            self._loader.load_files(files_to_load)

    def _load_touchstone_folder(self, folder_path: str) -> None:
        """Load all Touchstone files from a folder (non-recursive) using threaded loader."""
        try:
            folder = Path(folder_path)
            touchstone_files = []

            # Find all Touchstone files (s1p to s99p)
            patterns = []
            for i in range(1, 100):  # Support 1 to 99 ports
                patterns.append(f"*.s{i}p")
            patterns.append("*.ts")  # Add .ts format

            for pattern in patterns:
                touchstone_files.extend(folder.glob(pattern))

            if not touchstone_files:
                QMessageBox.information(
                    self,
                    "No Files Found",
                    f"No Touchstone files found in '{folder_path}'"
                )
                return

            # Create new project if none exists
            if self._current_project is None:
                self._new_project()

            # Filter out already loaded files
            files_to_load = []
            duplicate_files = []

            for file_path in touchstone_files:
                file_path_str = str(file_path)
                if self._is_file_already_loaded(file_path_str):
                    duplicate_files.append(file_path.name)
                else:
                    files_to_load.append(file_path_str)

            # Show warning if duplicates found
            if duplicate_files:
                if len(duplicate_files) == 1:
                    msg = f"The file '{duplicate_files[0]}' is already loaded and will be skipped."
                else:
                    msg = (f"{len(duplicate_files)} files are already loaded and will be skipped:\n" +
                           "\n".join(duplicate_files))

                QMessageBox.information(self, "Duplicate Files", msg)

            # Load remaining files
            if files_to_load:
                self._loader.load_files(files_to_load)
            elif not duplicate_files:
                QMessageBox.information(self, "No New Files", "All files in the folder are already loaded.")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Folder",
                f"Failed to load folder '{folder_path}':\n\n{str(e)}"
            )

    # Project Operations
    def _clear_current_project(self) -> None:
        """Clear the current project state - datasets and charts."""
        try:
            # Clear all charts
            self._main_panels.charts_area.clear_all_charts()

            # Clear all datasets from dataset browser
            self._main_panels.dataset_browser.clear_all_datasets()

            # Reset project state
            self._current_project = None
            self._current_project_path = None
            self._set_modified(False)

        except Exception as e:
            print(f"Warning: Error clearing project state: {e}")

    def _new_project(self) -> None:
        """Create a new project with user's saved preferences."""
        if not self._check_unsaved_changes():
            return

        # Clear current project state first
        self._clear_current_project()

        # Load user's persistent preferences if available
        saved_prefs = self._settings.value("user_preferences", None)
        if saved_prefs and isinstance(saved_prefs, dict):
            # Use user's saved preferences
            preferences = Preferences.from_dict(saved_prefs)
        else:
            # Use default preferences
            preferences = Preferences()

        self._current_project = Project(
            name="Untitled Project",
            preferences=preferences
        )
        self._current_project_path = None
        self._set_modified(False)

        # Update dataset browser with new project
        self._main_panels.dataset_browser.set_project(self._current_project)

        self._enable_project_actions(True)
        self._update_window_title()

        self.statusBar().showMessage("New project created with your preferences", 2000)

    def _open_project(self) -> None:
        """Open an existing project file."""
        if not self._check_unsaved_changes():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(self._get_last_directory()),
            "SnP Viewer Projects (*.snpproj);;JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self._load_project(file_path)

    def _load_project(self, file_path: str) -> None:
        """Load a project from file."""
        try:
            self._show_progress("Loading project...", 0)

            # Clear current project state first
            self._clear_current_project()

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Create project from data
            self._current_project = Project.from_dict(data)
            self._current_project_path = Path(file_path)
            self._set_modified(False)

            self._enable_project_actions(True)
            self._update_window_title()

            self.project_loaded.emit(self._current_project)

            self._show_progress("Project loaded successfully", 100)
            self._hide_progress_delayed()

        except Exception as e:
            self._hide_progress()
            QMessageBox.critical(
                self,
                "Error Loading Project",
                f"Failed to load project '{file_path}':\n\n{str(e)}"
            )

    def _save_project(self) -> bool:
        """Save the current project."""
        if self._current_project_path is None:
            return self._save_project_as()

        return self._save_project_to_path(self._current_project_path)

    def _save_project_as(self) -> bool:
        """Save the project with a new name."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            str(self._get_last_directory() / "untitled.snpproj"),
            "SnP Viewer Projects (*.snpproj);;JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            return self._save_project_to_path(Path(file_path))

        return False

    def _sync_chart_widgets_to_models(self) -> None:
        """Synchronize chart widget state to chart models before saving."""
        for chart_id, chart_info in self._main_panels.charts_area.get_all_charts().items():
            chart_widget = chart_info.get('widget')
            if chart_widget and hasattr(chart_widget, 'get_limit_lines'):
                # Update chart model with current widget state
                chart = self._current_project.get_chart(chart_id)
                if chart:
                    # Get existing traces with their Trace objects
                    existing_traces = chart_widget.get_existing_traces()

                    # Update trace IDs
                    chart.trace_ids = list(existing_traces.keys())

                    # Update traces with serialized Trace data
                    chart.traces = {}
                    for trace_id, (dataset_id, trace, dataset) in existing_traces.items():
                        # Serialize the Trace object to dict
                        chart.traces[trace_id] = trace.to_dict()

                    # Update limit lines
                    chart.limit_lines = chart_widget.get_limit_lines()
                    # Update font, color, and plot area settings
                    if hasattr(chart_widget, 'get_chart_fonts'):
                        chart.chart_fonts = chart_widget.get_chart_fonts()
                    if hasattr(chart_widget, 'get_chart_colors'):
                        chart.chart_colors = chart_widget.get_chart_colors()
                    if hasattr(chart_widget, 'get_plot_area_settings'):
                        chart.plot_area_settings = chart_widget.get_plot_area_settings()
                    # Update phase unwrap setting
                    if hasattr(chart_widget, 'get_phase_unwrap'):
                        chart.phase_unwrap = chart_widget.get_phase_unwrap()

                    # Update axis ranges
                    if hasattr(chart_widget, 'get_axis_ranges'):
                        axis_ranges = chart_widget.get_axis_ranges()
                        if axis_ranges and chart.axes:
                            # Update X axis
                            if 'x_min' in axis_ranges and 'x_max' in axis_ranges:
                                chart.axes.x.auto_range = False
                                chart.axes.x.min_value = axis_ranges['x_min']
                                chart.axes.x.max_value = axis_ranges['x_max']
                            # Update Y axis
                            if 'y_min' in axis_ranges and 'y_max' in axis_ranges:
                                chart.axes.y.auto_range = False
                                chart.axes.y.min_value = axis_ranges['y_min']
                                chart.axes.y.max_value = axis_ranges['y_max']

                    # Update marker state
                    if hasattr(chart_widget, 'get_marker_controller'):
                        marker_controller = chart_widget.get_marker_controller()
                        if marker_controller:
                            # Export markers to dict
                            chart.markers = marker_controller.export_markers_to_dict()
                            # Save marker mode state
                            chart.marker_mode_active = chart_widget.is_marker_mode_active()
                            chart.marker_coupled_mode = marker_controller.coupled_mode
                            chart.marker_show_overlay = marker_controller.show_overlay
                            if hasattr(marker_controller, 'marker_table'):
                                chart.marker_show_table = marker_controller.marker_table.isVisible()

                            # Save marker overlay position if manually positioned
                            if hasattr(marker_controller, 'marker_info_overlay'):
                                overlay = marker_controller.marker_info_overlay
                                if overlay and hasattr(overlay, 'user_positioned') and overlay.user_positioned:
                                    pos = overlay.pos()
                                    chart.marker_overlay_offset_x = pos.x()
                                    chart.marker_overlay_offset_y = pos.y()

                    # Save legend columns and position
                    if hasattr(chart_widget, 'get_legend_columns'):
                        chart.legend_columns = chart_widget.get_legend_columns()
                    if hasattr(chart_widget, 'get_legend_offset'):
                        offset = chart_widget.get_legend_offset()
                        if offset:
                            chart.legend_offset_x = offset[0]
                            chart.legend_offset_y = offset[1]

                    # Update linear phase error data
                    if hasattr(chart_widget, 'get_linear_phase_error_config'):
                        chart.linear_phase_error_data = chart_widget.get_linear_phase_error_config()
                        # chart.trace_ids = [chart.linear_phase_error_data.get('trace_id', '')]
                    # Update phase difference data
                    if hasattr(chart_widget, 'get_phase_difference_config'):
                        phase_diff_data = chart_widget.get_phase_difference_config()
                        if phase_diff_data:
                            # Remove numpy arrays from differences (they will be recalculated on load)
                            cleaned_data = phase_diff_data.copy()
                            if 'differences' in cleaned_data:
                                cleaned_differences = []
                                for diff in cleaned_data['differences']:
                                    # Keep only the metadata, not the array data
                                    cleaned_diff = {
                                        'dataset_id': diff['dataset_id'],
                                        'dataset_name': diff['dataset_name'],
                                        'color': diff.get('color', '#FF6B6B')
                                    }
                                    cleaned_differences.append(cleaned_diff)
                                cleaned_data['differences'] = cleaned_differences
                            chart.phase_difference_data = cleaned_data

    def _save_project_to_path(self, file_path: Path, update_current_path: bool = True) -> bool:
        """
        Save project to specified path.

        Args:
            file_path: Path to save the project to
            update_current_path: Whether to update self._current_project_path (False for backups)
        """
        try:
            self._show_progress("Saving project...", 0)

            # Update project name from filename
            self._current_project.name = file_path.stem

            # Sync chart widget state to chart models before saving
            self._sync_chart_widgets_to_models()

            # Convert project to dictionary
            data = self._current_project.to_dict()

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Only update current path if this is a regular save (not autosave/backup)
            if update_current_path:
                self._current_project_path = file_path

            self._set_modified(False)
            self._update_window_title()

            self.project_saved.emit(str(file_path))

            self._show_progress("Project saved successfully", 100)
            self._hide_progress_delayed()

            return True

        except Exception as e:
            self._hide_progress()
            QMessageBox.critical(
                self,
                "Error Saving Project",
                f"Failed to save project to '{file_path}':\n\n{str(e)}\n\nCheck console for details."
            )
            return False

    def _close_project(self) -> None:
        """Close the current project."""
        if not self._check_unsaved_changes():
            return

        # Clear current project state
        self._clear_current_project()

        # Disable project-related actions
        self._enable_project_actions(False)
        self._update_window_title()

        self.statusBar().showMessage("Project closed", 2000)

    def _export(self) -> None:
        """Export charts and data."""
        # Placeholder for export functionality
        QMessageBox.information(
            self,
            "Export",
            "Export functionality will be implemented in a future version."
        )

    # UI State Management
    def _enable_project_actions(self, enabled: bool) -> None:
        """Enable/disable project-related actions."""
        self._save_project_action.setEnabled(enabled)
        self._save_project_as_action.setEnabled(enabled)
        self._close_project_action.setEnabled(enabled)
        self._export_action.setEnabled(enabled)

    def _set_modified(self, modified: bool) -> None:
        """Set the modified state of the project."""
        self._modified = modified
        self._update_window_title()

    def _update_window_title(self) -> None:
        """Update the window title based on current project."""
        title = "SnP Viewer"

        if self._current_project:
            project_name = self._current_project.name
            if self._current_project_path:
                project_name = self._current_project_path.stem

            title = f"{project_name} - SnP Viewer"

            if self._modified:
                title = f"*{title}"

        self.setWindowTitle(title)

        # Update status bar
        if self._current_project:
            status = f"Project: {self._current_project.name}"
            if self._modified:
                status += " (modified)"
            self._project_label.setText(status)
        else:
            self._project_label.setText("No project")

    # View Menu Actions
    def _toggle_dataset_browser(self, checked: bool) -> None:
        """Toggle dataset browser visibility."""
        self._main_panels.dataset_browser.setVisible(checked)

    def _toggle_toolbar(self, checked: bool) -> None:
        """Toggle toolbar visibility."""
        self._toolbar.setVisible(checked)

    def _toggle_status_bar(self, checked: bool) -> None:
        """Toggle status bar visibility."""
        self._status_bar.setVisible(checked)

    # Progress and Status
    def _show_progress(self, message: str, value: int) -> None:
        """Show progress in status bar."""
        self._progress_bar.setValue(value)
        self._progress_bar.setVisible(True)
        self.statusBar().showMessage(message)

    def _hide_progress(self) -> None:
        """Hide progress bar."""
        self._progress_bar.setVisible(False)
        self.statusBar().clearMessage()

    def _hide_progress_delayed(self) -> None:
        """Hide progress bar after a short delay."""
        QTimer.singleShot(2000, self._hide_progress)

    def _update_memory_usage(self) -> None:
        """Update memory usage display."""
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            self._memory_label.setText(f"Memory: {memory_mb:.1f} MB")
        except ImportError:
            # psutil not available
            pass

    # Panel Event Handlers
    def _on_dataset_selected(self, dataset_id: str) -> None:
        """Handle dataset selection in browser."""
        # Get the dataset to show its display name
        dataset = self._main_panels.dataset_browser.get_dataset(dataset_id)
        display_name = dataset.display_name if dataset else dataset_id
        self.statusBar().showMessage(f"Selected dataset: {display_name}")

    def _on_dataset_double_clicked(self, dataset_id: str) -> None:
        """Handle dataset double-click in browser."""
        # Auto-create a default chart for the dataset
        self._on_create_chart_requested(dataset_id, "magnitude")

    def _on_create_chart_requested(self, dataset_id: str, chart_type: str) -> None:
        """Handle chart creation request from browser."""
        try:
            # Get the dataset
            dataset = self._main_panels.dataset_browser.get_dataset(dataset_id)
            if not dataset:
                QMessageBox.warning(self, "Error", f"Dataset {dataset_id} not found")
                return

            # Get the next chart number for naming
            chart_number = self._main_panels.charts_area.get_next_chart_number()

            # Create appropriate chart widget
            if chart_type.lower() in ['smith', 'smith_chart']:
                chart_widget = SmithView()
                chart_widget.set_dataset(dataset)
                chart_tab_title = f"Chart{chart_number} (Smith Chart)"
            else:
                chart_widget = ChartView()

                # Connect signals
                chart_widget.add_traces_requested.connect(
                    lambda: self._on_add_traces_requested(chart_widget, chart_type)
                )
                chart_widget.properties_changed.connect(
                    lambda: self._set_modified(True)
                )
                chart_widget.create_new_chart_requested.connect(
                    self._on_create_linear_phase_error_chart
                )

                # Set a counter-based chart name instead of dataset name
                chart_widget.set_chart_tab_title(f"Chart{chart_number}")

                # Set the correct plot type based on chart_type (this will also update the tab title)
                if chart_type.lower() == "magnitude":
                    chart_widget.set_plot_type(PlotType.MAGNITUDE)
                elif chart_type.lower() == "phase":
                    chart_widget.set_plot_type(PlotType.PHASE)
                elif chart_type.lower() == "group_delay":
                    chart_widget.set_plot_type(PlotType.GROUP_DELAY)

                chart_tab_title = chart_widget._tab_title

            chart_id = str(uuid.uuid4())[:8]  # Short unique ID

            # Create axis configurations based on chart type
            if chart_type.lower() in ['smith', 'smith_chart']:
                x_axis = AxisConfiguration(unit="", label="Real")
                y_axis = AxisConfiguration(unit="", label="Imaginary")
            else:
                x_axis = AxisConfiguration(unit="Hz", label="Frequency", scale="log")
                if chart_type.lower() == "magnitude":
                    y_axis = AxisConfiguration(unit="dB", label="Magnitude")
                elif chart_type.lower() == "phase":
                    y_axis = AxisConfiguration(unit="°", label="Phase")
                else:
                    y_axis = AxisConfiguration(unit="", label="Value")

            axes = ChartAxes(x=x_axis, y=y_axis)

            chart = Chart(
                id=chart_id,
                tab_title=chart_tab_title,
                title=chart_widget.get_chart_title(),
                chart_type=chart_type,
                trace_ids=[],
                limit_lines={},
                axes=axes
            )

            # Show trace selection dialog
            dialog = TraceSelectionDialog(dataset, chart_type, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Get selected traces from dialog
                selected_traces = dialog.create_selected_traces()

                if not selected_traces:
                    QMessageBox.information(self, "No Traces",
                                            "No S-parameters were selected. Chart creation cancelled.")
                    return

                # Add chart to charts area with dataset tracking
                self._main_panels.charts_area.add_chart(chart_id, chart, chart_widget, dataset_id)

                # Apply default styling from preferences
                self._apply_default_chart_styling(chart_widget)

                # Add selected traces to chart
                self._add_selected_traces(chart_widget, dataset, selected_traces, chart_type)

                # Update project if we have one
                if self._current_project:
                    # Store the selected traces in the chart object
                    # selected_traces is List[Tuple[str, Trace]], so extract trace IDs
                    chart.trace_ids = [trace_id for trace_id, trace in selected_traces]
                    self._current_project.add_chart(chart)
                    self._set_modified(True)

                msg = f"Created {chart_type} chart with {len(selected_traces)} traces for {dataset.display_name}"
                self.statusBar().showMessage(msg)
            else:
                # User cancelled - don't create chart
                return

        except Exception as e:
            QMessageBox.critical(self, "Chart Creation Error", f"Failed to create chart: {str(e)}")

    def _on_create_linear_phase_error_chart(self, config: dict) -> None:
        """
        Handle request to create a new Linear Phase Error chart.

        Args:
            config: Chart configuration dictionary containing:
                - type: 'linear_phase_error'
                - title: Chart title
                - dataset_id: Source dataset ID
                - trace_id: Full trace ID (dataset_id:S11 format)
                - i_port, j_port: S-parameter indices
                - sparam: S-parameter label (e.g., 'S11')
                - frequency, error: Data arrays (converted to lists for JSON)
                - slope, intercept: Fit parameters
                - freq_start, freq_end: Frequency range
                - equation: Fit equation string
                - dataset_name: Display name
        """
        try:
            # Get the dataset ID from config
            dataset_id = config.get('dataset_id')
            if not dataset_id:
                QMessageBox.warning(self, "Error", "No dataset ID specified for chart")
                return

            # Find the dataset
            dataset = self._main_panels.dataset_browser.get_dataset(dataset_id)
            if not dataset:
                QMessageBox.warning(self, "Error",
                                    f"Could not find dataset '{dataset_id}' for linear phase error chart")
                return

            # Get the next chart number for naming
            chart_number = self._main_panels.charts_area.get_next_chart_number()

            # Create a new chart widget
            chart_widget = ChartView()

            # Connect signals
            chart_widget.add_traces_requested.connect(
                lambda: self._on_add_traces_requested(chart_widget, 'LinearPhaseError')
            )
            chart_widget.properties_changed.connect(
                lambda: self._set_modified(True)
            )
            # chart_widget.create_new_chart_requested.connect(
            #     self._on_create_linear_phase_error_chart
            # )

            # Set chart title and tab title
            chart_widget.set_chart_tab_title(f"Chart{chart_number}")
            # chart_widget.set_chart_title(config.get('title', 'Linear Phase Error'))

            # Convert numpy arrays to lists if needed (for JSON serialization later)
            if isinstance(config.get('frequency'), np.ndarray):
                config['frequency'] = config['frequency'].tolist()
            if isinstance(config.get('error'), np.ndarray):
                config['error'] = config['error'].tolist()

            # Create the linear phase error plot
            chart_widget.create_linear_phase_error_plot(config)

            # Create chart ID and model
            chart_id = str(uuid.uuid4())[:8]

            x_axis = AxisConfiguration(unit="Hz", label="Frequency", scale="linear")
            y_axis = AxisConfiguration(unit="°", label="Phase Error")
            axes = ChartAxes(x=x_axis, y=y_axis)

            chart = Chart(
                id=chart_id,
                tab_title=chart_widget._tab_title,
                title=chart_widget.get_chart_title(),
                chart_type='LinearPhaseError',
                trace_ids=[config.get('trace_id', '')],  # Store the trace_id
                limit_lines={},
                axes=axes,
                linear_phase_error_data=config
            )

            # Add chart to charts area
            self._main_panels.charts_area.add_chart(chart_id, chart, chart_widget, dataset_id)

            # Apply default styling
            self._apply_default_chart_styling(chart_widget)

            # Update project if we have one
            if self._current_project:
                self._current_project.add_chart(chart)
                self._set_modified(True)

            msg = f"Created Linear Phase Error chart from {config.get('dataset_name', 'dataset')}"
            self.statusBar().showMessage(msg)

        except Exception as e:
            QMessageBox.critical(self, "Chart Creation Error",
                                 f"Failed to create Linear Phase Error chart: {str(e)}")

    def _on_create_phase_difference_chart(self, config: dict) -> None:
        """
        Handle request to create a new Phase Difference chart.

        Args:
            config: Chart configuration dictionary containing:
                - type: 'phase_difference'
                - title: Chart title
                - reference_dataset_id: Reference dataset ID
                - comparison_datasets: List of comparison dataset IDs
                - sparam: S-parameter label (e.g., 'S1,1')
                - i_port, j_port: S-parameter indices
                - freq_start, freq_end: Frequency range
                - unwrap_phase: Whether to unwrap phase
                - differences: List of difference data for each comparison
        """
        try:
            # Get reference dataset
            ref_dataset_id = config.get('reference_dataset_id')
            if not ref_dataset_id:
                QMessageBox.warning(self, "Error", "No reference dataset specified for chart")
                return

            # Verify reference dataset exists
            ref_dataset = self._main_panels.dataset_browser.get_dataset(ref_dataset_id)
            if not ref_dataset:
                QMessageBox.warning(self, "Error",
                                    f"Could not find reference dataset '{ref_dataset_id}'")
                return

            # Verify comparison datasets exist
            comparison_ids = config.get('comparison_datasets', [])
            for comp_id in comparison_ids:
                if not self._main_panels.dataset_browser.get_dataset(comp_id):
                    QMessageBox.warning(self, "Error",
                                        f"Could not find comparison dataset '{comp_id}'")
                    return

            # Get the next chart number for naming
            chart_number = self._main_panels.charts_area.get_next_chart_number()

            # Create a new chart widget
            chart_widget = ChartView()

            # Connect signals
            chart_widget.properties_changed.connect(
                lambda: self._set_modified(True)
            )

            # Set chart title and tab title
            chart_widget.set_chart_tab_title(f"Chart{chart_number}")
            chart_widget.set_chart_title(config.get('title', 'Phase Difference'))

            # Create the phase difference plot using the chart_view method
            if hasattr(ChartView, 'create_phase_difference_plot'):
                chart_widget.create_phase_difference_plot(config)
            else:
                raise NotImplementedError("create_phase_difference_plot not yet implemented in ChartView")

            # Create chart ID and model
            chart_id = str(uuid.uuid4())[:8]

            # Build trace_ids list for all comparison traces
            trace_ids = []
            for diff_data in config.get('differences', []):
                dataset_id = diff_data['dataset_id']
                sparam = config['sparam'].replace(',', '_')
                trace_id = f"{dataset_id}:{sparam}_phase_difference"
                trace_ids.append(trace_id)

            x_axis = AxisConfiguration(unit="Hz", label="Frequency", scale="linear")
            y_axis = AxisConfiguration(unit="°", label="Phase Difference")
            axes = ChartAxes(x=x_axis, y=y_axis)

            chart = Chart(
                id=chart_id,
                tab_title=chart_widget._tab_title,
                title=chart_widget.get_chart_title(),
                chart_type='PhaseDifference',
                trace_ids=trace_ids,
                limit_lines={},
                axes=axes,
                phase_difference_data=config
            )

            # Add chart to charts area - use reference dataset as primary dataset
            self._main_panels.charts_area.add_chart(chart_id, chart, chart_widget, ref_dataset_id)

            # Apply default styling
            self._apply_default_chart_styling(chart_widget)

            # Update project if we have one
            if self._current_project:
                self._current_project.add_chart(chart)
                self._set_modified(True)

            msg = f"Created Phase Difference chart comparing {len(comparison_ids)} dataset(s) against reference"
            self.statusBar().showMessage(msg)

        except Exception as e:
            QMessageBox.critical(self, "Chart Creation Error",
                                 f"Failed to create Phase Difference chart: {str(e)}")

    def _apply_default_chart_styling(self, chart_widget: ChartView | SmithView) -> None:
        """
        Apply default chart styling from preferences to a newly created chart.

        Args:
            chart_widget: The chart widget to apply styling to
        """
        if not self._current_project or not self._current_project.preferences:
            return

        preferences = self._current_project.preferences

        try:
            # Apply default font styling if ChartView has the methods
            if hasattr(chart_widget, 'restore_chart_fonts') and preferences.default_chart_fonts:
                chart_widget.restore_chart_fonts(preferences.default_chart_fonts)

            # Apply default color styling
            if hasattr(chart_widget, 'restore_chart_colors') and preferences.default_chart_colors:
                chart_widget.restore_chart_colors(preferences.default_chart_colors)

            # Apply default plot area settings
            if hasattr(chart_widget, 'restore_plot_area_settings') and preferences.default_plot_area_settings:
                chart_widget.restore_plot_area_settings(preferences.default_plot_area_settings)

        except Exception as e:
            print(f"Warning: Could not apply default chart styling: {e}")

    def _add_selected_traces(self, chart_widget: ChartView | SmithView, dataset: Dataset,
                             selected_traces, chart_type: str) -> None:
        """Add selected traces to a newly created chart."""
        try:
            # Determine if this is a Smith chart
            is_smith_chart = chart_type.lower() in ['smith', 'smith_chart']

            # Add traces based on chart type
            for trace_id, trace in selected_traces:
                if is_smith_chart:
                    # SmithView uses add_trace(trace, style)
                    chart_widget.add_trace(trace, trace.style)
                else:
                    # ChartView uses add_trace(trace_id, trace, dataset)
                    chart_widget.add_trace(trace_id, trace, dataset)

        except Exception as e:
            print(f"Warning: Failed to add selected traces: {e}")

    def _add_default_traces(self, chart_widget: ChartView | SmithView, dataset: Dataset, chart_type: str) -> None:
        """Add default traces to a newly created chart (deprecated - use trace selection dialog)."""
        try:
            # Create default traces based on number of ports
            n_ports = dataset.n_ports

            if chart_type.lower() in ['smith', 'smith_chart']:
                # For Smith charts, add reflection parameters (S11, S22, etc.)
                for i in range(min(n_ports, 4)):  # Limit to 4 traces for readability
                    style = TraceStyle(
                        color=DEFAULT_TRACE_COLORS[i % len(DEFAULT_TRACE_COLORS)],
                        line_width=2,
                        marker_style='none'
                    )
                    dataset_id = dataset.id if hasattr(dataset, 'id') else ''
                    trace = Trace(
                        id=f"{dataset_id}:S{i+1},{i+1}_smith",
                        dataset_id=dataset_id,
                        domain="S",
                        metric="reflection",
                        port_path=PortPath(i=i+1, j=i+1),
                        style=style
                    )
                    # SmithView.add_trace(trace, style)
                    chart_widget.add_trace(trace, style)
            else:
                # For Cartesian charts, add magnitude traces
                trace_count = 0

                # Add reflection parameters (S11, S22, etc.)
                for i in range(min(n_ports, 2)):  # S11, S22
                    style = TraceStyle(
                        color=DEFAULT_TRACE_COLORS[trace_count % len(DEFAULT_TRACE_COLORS)],
                        line_width=2,
                        marker_style='none'
                    )
                    dataset_id = dataset.id if hasattr(dataset, 'id') else ''
                    trace_id = f"{dataset_id}:S{i+1},{i+1}_{chart_type}"
                    trace = Trace(
                        id=trace_id,
                        dataset_id=dataset_id,
                        domain="S",
                        metric="magnitude_dB" if chart_type.lower() == "magnitude" else chart_type.lower(),
                        port_path=PortPath(i=i+1, j=i+1),
                        style=style
                    )
                    # ChartView.add_trace(trace_id, trace, dataset)
                    chart_widget.add_trace(trace_id, trace, dataset)
                    trace_count += 1

                # Add transmission parameters if 2-port
                if n_ports >= 2 and trace_count < 4:
                    for i, j in [(0, 1), (1, 0)]:  # S12, S21
                        if trace_count >= 4:
                            break
                        # Use dashed line for transmission (i != j), solid for reflection (i == j)
                        line_style = DEFAULT_LINE_STYLES[1] if i != j else DEFAULT_LINE_STYLES[0]
                        style = TraceStyle(
                            color=DEFAULT_TRACE_COLORS[trace_count % len(DEFAULT_TRACE_COLORS)],
                            line_width=2,
                            line_style=line_style,
                            marker_style='none'
                        )
                        dataset_id = dataset.id if hasattr(dataset, 'id') else ''
                        trace_id = f"{dataset_id}:S{i+1},{j+1}_{chart_type}"
                        trace = Trace(
                            id=trace_id,
                            dataset_id=dataset_id,
                            domain="S",
                            metric="magnitude_dB" if chart_type.lower() == "magnitude" else chart_type.lower(),
                            port_path=PortPath(i=i+1, j=j+1),
                            style=style
                        )
                        # ChartView.add_trace(trace_id, trace, dataset)
                        chart_widget.add_trace(trace_id, trace, dataset)
                        trace_count += 1

        except Exception as e:
            print(f"Warning: Failed to add default traces: {e}")

    def _on_chart_selected(self, chart_id: str) -> None:
        """Handle chart selection in charts area."""
        # Get the chart's tab title to show in status bar
        chart_info = self._main_panels.charts_area.get_all_charts().get(chart_id)
        if chart_info and 'widget' in chart_info:
            chart_tab_title = chart_info['widget'].get_tab_title()
            self.statusBar().showMessage(f"Selected chart: {chart_tab_title}")
        else:
            # Fallback to chart_id if we can't find the chart
            self.statusBar().showMessage(f"Selected chart: {chart_id}")

    def _on_chart_closed(self, chart_id: str) -> None:
        """Handle chart close request."""
        # Remove chart from charts area
        self._main_panels.charts_area.remove_chart(chart_id)

        # Remove from project if we have one
        if self._current_project:
            self._current_project.remove_chart(chart_id)
            self._set_modified(True)

        # Clean up chart resources
        self.statusBar().showMessage(f"Closed chart: {chart_id}")

    def _on_duplicate_chart_requested(self, chart_id: str) -> None:
        """
        Handle duplicate chart request from context menu.

        Args:
            chart_id: ID of the chart to duplicate
        """
        # We need to temporarily set this as the current chart to duplicate it
        # Find the tab index for this chart
        for i in range(self._main_panels.charts_area._chart_tabs.count()):
            if self._main_panels.charts_area._chart_tabs.tabBar().tabData(i) == chart_id:
                # Set as current
                self._main_panels.charts_area._chart_tabs.setCurrentIndex(i)

                # Duplicate it
                self._duplicate_current_chart()

                # Note: We don't restore the old index because the user probably wants
                # to see the newly duplicated chart
                break

    def _on_dataset_removed(self, user_friendly_name: str, dataset_uuid: str) -> None:
        """Handle dataset removal - clean up related traces and charts."""
        # Remove traces from this dataset across all charts using UUID
        traces_removed, charts_affected = self._main_panels.charts_area.remove_traces_by_dataset(dataset_uuid)

        # Remove from project if we have one (dataset references use UUID)
        if self._current_project:
            self._current_project.remove_dataset_ref(dataset_uuid)
            self._set_modified(True)

        # Provide informative status message
        if traces_removed > 0:
            if charts_affected == 1:
                msg = f"Removed dataset '{user_friendly_name}': {traces_removed} trace(s) from 1 chart"
            else:
                msg = (f"Removed dataset '{user_friendly_name}': {traces_removed} trace(s) "
                       f"from {charts_affected} chart(s)")
            self.statusBar().showMessage(msg)

    def _on_dataset_renamed(self, dataset_id: str, new_display_name: str) -> None:
        """Handle dataset rename - update legends in all charts using this dataset."""
        # Get the dataset object
        dataset = self._main_panels.dataset_browser.get_dataset(dataset_id)
        if not dataset:
            return

        # Update all charts that use this dataset
        all_charts = self._main_panels.charts_area.get_all_charts()
        charts_updated = 0

        for chart_id, chart_info in all_charts.items():
            widget = chart_info['widget']

            # Check if this chart has traces from this dataset
            if hasattr(widget, 'update_dataset_name'):
                # For ChartView widgets, update the dataset name
                if widget.update_dataset_name(dataset.id, new_display_name):
                    charts_updated += 1

        # Update the display_name in the project's dataset_ref for persistence
        if self._current_project and dataset:
            for ref in self._current_project.dataset_refs:
                if ref.dataset_id == dataset.id:
                    ref.display_name = new_display_name
                    break

        # Mark project as modified if charts were updated
        if charts_updated > 0 and self._current_project:
            self._set_modified(True)
            self.statusBar().showMessage(
                f"Renamed dataset to '{new_display_name}' and updated {charts_updated} chart(s)"
            )

    def _create_new_chart(self) -> None:
        """
        Handle Chart > Create Chart menu action.

        Opens a dialog to select chart type, datasets, and S-parameters, then creates
        a new chart with traces for all selected dataset×parameter combinations.
        """
        # Get available datasets
        datasets = self._main_panels.dataset_browser._datasets
        if not datasets:
            QMessageBox.information(
                self,
                "No Datasets Available",
                "Please load datasets first before creating a chart."
            )
            return

        # Show the create chart dialog
        dialog = CreateChartDialog(datasets, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Get selections
        chart_type = dialog.get_chart_type()
        selected_dataset_ids = dialog.get_selected_datasets()

        if not selected_dataset_ids:
            QMessageBox.warning(
                self,
                "No Datasets Selected",
                "Please select at least one dataset."
            )
            return

        # Create traces
        traces_data = dialog.create_traces()

        if not traces_data:
            QMessageBox.warning(
                self,
                "No Parameters Selected",
                "Please select at least one S-parameter."
            )
            return

        # Get the next chart number for naming
        chart_number = self._main_panels.charts_area.get_next_chart_number()
        chart_id = str(uuid.uuid4())[:8]  # Short unique ID

        # Create appropriate chart widget based on chart type
        if chart_type.lower() in ['smith', 'smith_chart']:
            chart_widget = SmithView()
            chart_tab_title = f"Chart{chart_number} (Smith Chart)"
        else:
            chart_widget = ChartView()

            # Connect signals
            chart_widget.add_traces_requested.connect(
                lambda: self._on_add_traces_requested(chart_widget, chart_type)
            )
            chart_widget.properties_changed.connect(
                lambda: self._set_modified(True)
            )
            chart_widget.create_new_chart_requested.connect(
                self._on_create_linear_phase_error_chart
            )

            # Set a counter-based chart name
            chart_widget.set_chart_tab_title(f"Chart{chart_number}")

            # Set the correct plot type based on chart_type
            if chart_type.lower() == "magnitude":
                chart_widget.set_plot_type(PlotType.MAGNITUDE)
            elif chart_type.lower() == "phase":
                chart_widget.set_plot_type(PlotType.PHASE)
            elif chart_type.lower() == "group_delay":
                chart_widget.set_plot_type(PlotType.GROUP_DELAY)

            chart_tab_title = chart_widget._tab_title

        # Create axis configurations based on chart type
        if chart_type.lower() in ['smith', 'smith_chart']:
            x_axis = AxisConfiguration(unit="", label="Real")
            y_axis = AxisConfiguration(unit="", label="Imaginary")
        else:
            x_axis = AxisConfiguration(unit="Hz", label="Frequency", scale="log")
            if chart_type.lower() == "magnitude":
                y_axis = AxisConfiguration(unit="dB", label="Magnitude")
            elif chart_type.lower() == "phase":
                y_axis = AxisConfiguration(unit="°", label="Phase")
            elif chart_type.lower() == "group_delay":
                y_axis = AxisConfiguration(unit="s", label="Group Delay")
            else:
                y_axis = AxisConfiguration(unit="", label="Value")

        axes = ChartAxes(x=x_axis, y=y_axis)

        # Create chart model with all required parameters
        chart = Chart(
            id=chart_id,
            tab_title=chart_tab_title,
            title=chart_widget.get_chart_title() if hasattr(chart_widget, 'get_chart_title') else chart_tab_title,
            chart_type=chart_type,
            trace_ids=[],
            limit_lines={},
            axes=axes
        )

        # Add chart to charts area with the widget
        self._main_panels.charts_area.add_chart(chart_id, chart, chart_widget)

        # Apply default styling from preferences
        self._apply_default_chart_styling(chart_widget)

        # Add all traces to the chart
        for trace_id, trace, dataset_id in traces_data:
            # Add trace to chart model
            chart.trace_ids.append(trace_id)

            # Get dataset for plotting
            dataset = datasets.get(dataset_id)
            if dataset:
                # Add trace to chart widget
                if chart_type.lower() in ['smith', 'smith_chart']:
                    # SmithView uses add_trace(trace, style)
                    chart_widget.add_trace(trace, trace.style)
                else:
                    # ChartView uses add_trace(trace_id, trace, dataset)
                    chart_widget.add_trace(trace_id, trace, dataset)

        # Update project if we have one
        if self._current_project:
            self._current_project.add_chart(chart)
            self._set_modified(True)

        # Show success message
        dataset_count = len(selected_dataset_ids)
        trace_count = len(traces_data)
        self.statusBar().showMessage(
            f"Created {chart_type} chart with {trace_count} trace(s) from {dataset_count} dataset(s)"
        )

    def _duplicate_current_chart(self) -> None:
        """
        Duplicate the currently active chart with all its settings.

        Creates a copy of the current chart including:
        - All traces and their styling
        - All markers
        - Chart styling (fonts, colors, plot area settings)
        - Legend configuration (columns, position)
        - Axis ranges
        - Limit lines
        - Marker overlay position
        """
        # Get the current chart
        current_chart_id = self._main_panels.charts_area.get_current_chart_id()
        if not current_chart_id:
            QMessageBox.information(
                self,
                "No Chart Selected",
                "Please select a chart to duplicate."
            )
            return

        # Get the chart widget and model
        current_widget = self._main_panels.charts_area.get_chart_widget(current_chart_id)
        if not current_widget:
            QMessageBox.warning(
                self,
                "Chart Not Found",
                "Could not find the selected chart."
            )
            return

        # Get the chart model from charts area
        all_charts_data = self._main_panels.charts_area.get_all_charts()
        if current_chart_id not in all_charts_data:
            QMessageBox.warning(
                self,
                "Chart Data Not Found",
                "Could not find the chart data."
            )
            return

        current_chart = all_charts_data[current_chart_id]['chart']

        # Generate new IDs and title
        new_chart_id = str(uuid.uuid4())[:8]
        chart_number = self._main_panels.charts_area.get_next_chart_number()
        new_tab_title = f"Chart{chart_number}"

        # Determine chart type from the current chart
        chart_type = current_chart.chart_type

        # Create new chart widget of the same type
        if chart_type in ['SmithZ', 'SmithY']:
            new_widget = SmithView()
        else:
            new_widget = ChartView()

            # Connect signals
            new_widget.add_traces_requested.connect(
                lambda: self._on_add_traces_requested(new_widget, chart_type)
            )
            new_widget.properties_changed.connect(
                lambda: self._set_modified(True)
            )
            new_widget.create_new_chart_requested.connect(
                self._on_create_linear_phase_error_chart
            )

            # Set plot type - use case-insensitive comparison to match all variations
            chart_type_lower = chart_type.lower()
            if chart_type_lower == "magnitude":
                new_widget.set_plot_type(PlotType.MAGNITUDE)
            elif chart_type_lower == "phase":
                new_widget.set_plot_type(PlotType.PHASE)
            elif chart_type_lower in ["group_delay", "groupdelay"]:
                new_widget.set_plot_type(PlotType.GROUP_DELAY)
            elif chart_type_lower in ["linearphaseerror", "linear_phase_error"]:
                new_widget.set_plot_type(PlotType.LINEAR_PHASE_ERROR)
            elif chart_type_lower in ["phasedifference", "phase_difference"]:
                new_widget.set_plot_type(PlotType.PHASE_DIFFERENCE)

            # Set phase unwrap setting
            if hasattr(current_widget, 'get_phase_unwrap') and hasattr(new_widget, 'restore_phase_unwrap'):
                new_widget.restore_phase_unwrap(current_widget.get_phase_unwrap())

        # Copy chart titles
        if hasattr(current_widget, 'get_chart_title'):
            chart_title = current_widget.get_chart_title()
            if hasattr(new_widget, 'set_chart_title'):
                new_widget.set_chart_title(chart_title + " (Copy)")

        # Set the tab title
        if hasattr(new_widget, 'set_chart_tab_title'):
            new_widget.set_chart_tab_title(new_tab_title)

        # Copy axis configuration
        import copy
        axes_copy = copy.deepcopy(current_chart.axes) if current_chart.axes else None

        # Create the new chart model
        new_chart = Chart(
            id=new_chart_id,
            tab_title=new_tab_title,
            title=current_chart.title + " (Copy)",
            chart_type=chart_type,
            trace_ids=[],  # Will be populated as we add traces
            axes=axes_copy,
            linked_x_axis=current_chart.linked_x_axis,
            legend_enabled=current_chart.legend_enabled,
            legend_position=current_chart.legend_position,
            legend_columns=current_chart.legend_columns,
            legend_offset_x=current_chart.legend_offset_x,
            legend_offset_y=current_chart.legend_offset_y,
            background_color=current_chart.background_color,
            chart_fonts=copy.deepcopy(current_chart.chart_fonts),
            chart_colors=copy.deepcopy(current_chart.chart_colors),
            plot_area_settings=copy.deepcopy(current_chart.plot_area_settings),
            phase_unwrap=current_chart.phase_unwrap,
            marker_mode_active=False,  # Don't copy marker mode state
            marker_coupled_mode=current_chart.marker_coupled_mode,
            marker_show_overlay=current_chart.marker_show_overlay,
            marker_show_table=current_chart.marker_show_table,
            marker_overlay_offset_x=current_chart.marker_overlay_offset_x,
            marker_overlay_offset_y=current_chart.marker_overlay_offset_y,
        )

        # Add the new chart to the charts area
        self._main_panels.charts_area.add_chart(new_chart_id, new_chart, new_widget)

        # Copy chart styling (fonts, colors, plot area settings)
        if hasattr(current_widget, 'get_chart_fonts') and hasattr(new_widget, 'restore_chart_fonts'):
            chart_fonts = current_widget.get_chart_fonts()
            if chart_fonts:
                new_widget.restore_chart_fonts(chart_fonts)

        if hasattr(current_widget, 'get_chart_colors') and hasattr(new_widget, 'restore_chart_colors'):
            chart_colors = current_widget.get_chart_colors()
            if chart_colors:
                new_widget.restore_chart_colors(chart_colors)

        if hasattr(current_widget, 'get_plot_area_settings') and hasattr(new_widget, 'restore_plot_area_settings'):
            plot_area_settings = current_widget.get_plot_area_settings()
            if plot_area_settings:
                new_widget.restore_plot_area_settings(plot_area_settings)

        # Copy legend configuration
        if hasattr(current_widget, 'get_legend_columns') and hasattr(new_widget, 'set_legend_columns'):
            legend_columns = current_widget.get_legend_columns()
            new_widget.set_legend_columns(legend_columns)

        # Copy limit lines
        if hasattr(current_widget, 'get_limit_lines'):
            limit_lines = current_widget.get_limit_lines()
            if limit_lines and hasattr(new_widget, 'restore_limit_lines'):
                new_widget.restore_limit_lines(limit_lines)

        # Handle special chart types that use custom data structures
        chart_type_lower = chart_type.lower()
        is_special_chart = chart_type_lower in [
            "linearphaseerror", "linear_phase_error", "phasedifference", "phase_difference"
        ]

        if is_special_chart:
            # For Linear Phase Error charts
            if chart_type_lower in ["linearphaseerror", "linear_phase_error"]:
                if current_chart.linear_phase_error_data and hasattr(new_widget, 'restore_linear_phase_error_config'):
                    datasets = self._main_panels.dataset_browser._datasets
                    lpe_dataset_id = current_chart.linear_phase_error_data.get('dataset_id')
                    lpe_dataset = datasets.get(lpe_dataset_id) if lpe_dataset_id else None
                    if lpe_dataset:
                        new_widget.restore_linear_phase_error_config(
                            current_chart.linear_phase_error_data, lpe_dataset
                        )

            # For Phase Difference charts
            elif chart_type_lower in ["phasedifference", "phase_difference"]:
                if current_chart.phase_difference_data and hasattr(new_widget, 'restore_phase_difference_config'):
                    datasets = self._main_panels.dataset_browser._datasets
                    # Collect all required datasets
                    chart_datasets = {}
                    ref_dataset_id = current_chart.phase_difference_data.get('reference_dataset_id')
                    if ref_dataset_id and ref_dataset_id in datasets:
                        chart_datasets[ref_dataset_id] = datasets[ref_dataset_id]
                    comparison_ids = current_chart.phase_difference_data.get('comparison_datasets', [])
                    for comp_id in comparison_ids:
                        if comp_id in datasets:
                            chart_datasets[comp_id] = datasets[comp_id]

                    if chart_datasets:
                        new_widget.restore_phase_difference_config(
                            current_chart.phase_difference_data, chart_datasets
                        )
        else:
            # Copy all traces with their styling for normal chart types
            # Get traces directly from the widget (more reliable than model)
            if hasattr(current_widget, 'get_existing_traces'):
                existing_traces = current_widget.get_existing_traces()

                for trace_id, (dataset_id, trace, dataset) in existing_traces.items():
                    # Generate new trace ID for the duplicate
                    new_trace_id = str(uuid.uuid4())[:8]

                    # Create a copy of the trace with new ID
                    new_trace = Trace(
                        id=new_trace_id,
                        dataset_id=trace.dataset_id,
                        domain=trace.domain,
                        port_path=trace.port_path,
                        metric=trace.metric,
                        label=trace.label,
                        style=copy.deepcopy(trace.style)
                    )

                    # Add to chart model
                    new_chart.trace_ids.append(new_trace_id)
                    new_chart.traces[new_trace_id] = new_trace.to_dict()

                    # Add to widget
                    if chart_type in ['SmithZ', 'SmithY']:
                        if hasattr(new_widget, 'add_trace'):
                            new_widget.add_trace(new_trace, new_trace.style)
                    else:
                        if hasattr(new_widget, 'add_trace'):
                            new_widget.add_trace(new_trace_id, new_trace, dataset)

        # Copy axis ranges if they were manually set
        if axes_copy and hasattr(new_widget, 'set_axis_range'):
            x_axis = axes_copy.x
            y_axis = axes_copy.y

            if not x_axis.auto_range and x_axis.min_value is not None and x_axis.max_value is not None:
                new_widget.set_axis_range('x', x_axis.min_value, x_axis.max_value)

            if not y_axis.auto_range and y_axis.min_value is not None and y_axis.max_value is not None:
                new_widget.set_axis_range('y', y_axis.min_value, y_axis.max_value)

        # Copy markers and marker settings
        if current_chart.markers and hasattr(new_widget, 'restore_markers'):
            # Prepare marker overlay offset tuple if available
            marker_overlay_offset = None
            if current_chart.marker_overlay_offset_x is not None and current_chart.marker_overlay_offset_y is not None:
                marker_overlay_offset = (current_chart.marker_overlay_offset_x, current_chart.marker_overlay_offset_y)

            # Restore markers with all settings
            new_widget.restore_markers(
                markers_dict=current_chart.markers,
                marker_mode_active=False,  # Don't activate marker mode automatically
                marker_coupled_mode=current_chart.marker_coupled_mode,
                marker_show_overlay=current_chart.marker_show_overlay,
                marker_show_table=current_chart.marker_show_table,
                marker_overlay_offset=marker_overlay_offset
            )

        # Update project if we have one
        if self._current_project:
            self._current_project.add_chart(new_chart)
            self._set_modified(True)

        # Show success message
        # For special chart types, we may not have trace_ids but we have data
        marker_count = len(current_chart.markers) if current_chart.markers else 0

        if is_special_chart:
            # Special charts don't use regular trace counting
            if marker_count > 0:
                self.statusBar().showMessage(
                    f"Duplicated {chart_type} chart with {marker_count} marker(s)"
                )
            else:
                self.statusBar().showMessage(
                    f"Duplicated {chart_type} chart"
                )
        else:
            # Regular charts
            trace_count = len(new_chart.trace_ids)
            if marker_count > 0:
                self.statusBar().showMessage(
                    f"Duplicated chart with {trace_count} trace(s) and {marker_count} marker(s)"
                )
            else:
                self.statusBar().showMessage(
                    f"Duplicated chart with {trace_count} trace(s)"
                )

    def _on_add_parameter_to_chart_requested(self, chart_id: str, dataset_id: str, param_name: str) -> None:
        """
        Handle request to add a parameter to a chart.

        Args:
            chart_id: Empty string means show dialog to select chart
            dataset_id: The dataset ID containing the parameter
            param_name: The S-parameter name (e.g., "S1,1")
        """
        # Get available charts
        chart_list = self._main_panels.charts_area.get_chart_list()

        if not chart_list:
            QMessageBox.information(
                self,
                "No Charts Available",
                "Please create a chart first before adding traces."
            )
            return

        # Show dialog to select chart
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Chart")
        dialog.setModal(True)
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)

        # Info label
        dataset = self._main_panels.dataset_browser.get_dataset(dataset_id)
        dataset_name = dataset.display_name if dataset else dataset_id
        info_label = QLabel(f"Add {param_name} from dataset '{dataset_name}' to which chart(s)?")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Chart list with multiple selection enabled
        chart_list_widget = QListWidget()
        chart_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for cid, title in chart_list:
            chart_list_widget.addItem(title)
            chart_list_widget.item(chart_list_widget.count() - 1).setData(Qt.ItemDataRole.UserRole, cid)

        # Select current chart if available
        current_chart_id = self._main_panels.charts_area.get_current_chart_id()
        if current_chart_id:
            for i in range(chart_list_widget.count()):
                if chart_list_widget.item(i).data(Qt.ItemDataRole.UserRole) == current_chart_id:
                    chart_list_widget.item(i).setSelected(True)
                    break

        layout.addWidget(chart_list_widget)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog
        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_items = chart_list_widget.selectedItems()
            if selected_items:
                # Add to all selected charts
                added_count = 0
                skipped_count = 0
                for item in selected_items:
                    selected_chart_id = item.data(Qt.ItemDataRole.UserRole)
                    result = self._add_parameter_to_chart(selected_chart_id, dataset_id, param_name)
                    if result:
                        added_count += 1
                    else:
                        skipped_count += 1

                # Show summary message
                if added_count > 0:
                    if skipped_count > 0:
                        msg = f"Added {param_name} to {added_count} chart(s), skipped {skipped_count} (already exists)"
                    else:
                        msg = f"Added {param_name} from '{dataset_name}' to {added_count} chart(s)"
                    self.statusBar().showMessage(msg)
                elif skipped_count > 0:
                    self.statusBar().showMessage(f"{param_name} already exists in all selected charts")

    def _add_parameter_to_chart(self, chart_id: str, dataset_id: str, param_name: str) -> bool:
        """
        Actually add the parameter to the specified chart.

        Args:
            chart_id: The chart ID to add to
            dataset_id: The dataset ID containing the parameter
            param_name: The S-parameter name (e.g., "S1,1")

        Returns:
            True if the trace was added, False if it already exists or there was an error
        """
        # Get the chart widget
        chart_widget = self._main_panels.charts_area.get_chart_widget(chart_id)
        if not chart_widget:
            return False

        # Get the dataset
        dataset = self._main_panels.dataset_browser.get_dataset(dataset_id)
        if not dataset:
            return False

        # Parse port numbers from param_name (e.g., "S1,1" -> (1, 1))
        try:
            # Remove 'S' prefix and split by comma
            parts = param_name[1:].split(',')
            port_i = int(parts[0])
            port_j = int(parts[1])
        except (IndexError, ValueError):
            return False

        # Check if this trace already exists in the chart (by looking at existing traces)
        if hasattr(chart_widget, '_traces'):
            for existing_trace_id, existing_trace in chart_widget._traces.items():
                if (hasattr(existing_trace, 'dataset_id') and
                        existing_trace.dataset_id == dataset.id and
                        hasattr(existing_trace, 'port_path') and
                        existing_trace.port_path.i == port_i and
                        existing_trace.port_path.j == port_j):
                    # Trace already exists, skip silently
                    return False

        # Determine the chart type string for trace ID and the metric based on chart type
        chart_type = getattr(chart_widget, '_plot_type', None)
        if chart_type:
            chart_type_str = chart_type.value  # Get enum value (e.g., "magnitude", "phase")
        else:
            chart_type_str = "magnitude"  # Default

        # Generate trace ID using standardized format: dataset_id:S{i},{j}_{chart_type}
        trace_id = f"{dataset.id}:S{port_i},{port_j}_{chart_type_str}"

        if chart_type:
            # For ChartView, map plot type to metric
            if chart_type == PlotType.MAGNITUDE:
                metric = "magnitude_dB"
            elif chart_type == PlotType.PHASE:
                metric = "phase_deg"
            elif chart_type == PlotType.GROUP_DELAY:
                metric = "group_delay"
            else:
                metric = "magnitude_dB"  # Default
        else:
            # For SmithView or unknown, default to magnitude
            metric = "magnitude_dB"

        # Add the trace to the chart
        if hasattr(chart_widget, 'add_trace'):
            # Pick a color from a palette (cycling through available colors)
            trace_count = len(chart_widget._traces) if hasattr(chart_widget, '_traces') else 0
            color = DEFAULT_TRACE_COLORS[trace_count % len(DEFAULT_TRACE_COLORS)]

            # Create a new trace with all required fields
            trace = Trace(
                id=trace_id,
                dataset_id=dataset.id,
                domain="S",
                port_path=PortPath(i=port_i, j=port_j),
                metric=metric,
                style=TraceStyle(color=color, line_width=2, marker_style='none')
            )

            # Add the trace
            chart_widget.add_trace(trace_id, trace, dataset)

            # Mark project as modified
            if self._current_project:
                self._set_modified(True)

            return True
        else:
            return False

    def _on_project_loaded(self, project: Project) -> None:
        """Handle project loaded - restore UI state with datasets and charts."""
        try:
            # Don't set the project yet - wait until datasets are loaded
            # self._main_panels.dataset_browser.set_project(project)

            # Load datasets from file references synchronously
            datasets_loaded = 0
            datasets_failed = 0

            # Create mapping from UUID to user-friendly name for chart restoration
            uuid_to_friendly_name = {}

            for dataset_ref in project.dataset_refs:
                try:
                    # Load the dataset from the file path
                    file_path = Path(dataset_ref.file_path)
                    if not file_path.is_absolute():
                        # Make relative paths relative to project file location
                        if self._current_project_path:
                            file_path = self._current_project_path.parent / file_path

                    if file_path.exists():
                        # Load synchronously using the backend parser directly
                        touchstone_data = parse_touchstone(str(file_path))

                        # Generate user-friendly dataset name from filename (without extension)
                        user_friendly_name = file_path.stem

                        # Create dataset with the saved dataset_id from project
                        # This preserves the dataset identity even if the file is moved
                        dataset = touchstone_to_dataset(
                            touchstone_data,
                            str(file_path),
                            dataset_id=dataset_ref.dataset_id
                        )

                        if dataset:
                            # Restore the saved display_name from the project if available
                            if dataset_ref.display_name:
                                dataset.display_name = dataset_ref.display_name

                            # Store mapping from UUID to user-friendly name
                            uuid_to_friendly_name[dataset_ref.dataset_id] = user_friendly_name

                            # Add dataset with UUID as key (not user-friendly name)
                            self._main_panels.dataset_browser.add_dataset(dataset.id, dataset)
                            datasets_loaded += 1
                        else:
                            datasets_failed += 1
                    else:
                        print(f"Warning: Dataset file not found: {file_path}")
                        datasets_failed += 1

                except Exception as e:
                    print(f"Error loading dataset {dataset_ref.dataset_id}: {e}")
                    datasets_failed += 1

            # Now set the project in the dataset browser after all datasets are loaded
            self._main_panels.dataset_browser.set_project(project)

            # Restore charts from project
            charts_restored = 0
            charts_failed = 0

            # Restore charts from project
            for chart in project.charts:
                try:
                    # NEW APPROACH: Parse dataset_id from each trace_id
                    # Format: dataset_id:S{i},{j}_{chart_type}

                    # Extract unique dataset IDs from all trace_ids in this chart
                    chart_dataset_ids = set()
                    for trace_id in chart.trace_ids:
                        if trace_id and ':' in trace_id:
                            dataset_id = trace_id.split(':')[0]
                            chart_dataset_ids.add(dataset_id)

                    # Special handling for linear phase error charts - check config for dataset_id
                    if hasattr(chart, 'linear_phase_error_data') and chart.linear_phase_error_data:
                        config_dataset_id = chart.linear_phase_error_data.get('dataset_id')
                        if config_dataset_id:
                            chart_dataset_ids.add(config_dataset_id)

                    # Special handling for phase difference charts - check config for dataset_ids
                    if hasattr(chart, 'phase_difference_data') and chart.phase_difference_data:
                        ref_dataset_id = chart.phase_difference_data.get('reference_dataset_id')
                        if ref_dataset_id:
                            chart_dataset_ids.add(ref_dataset_id)
                        comparison_ids = chart.phase_difference_data.get('comparison_datasets', [])
                        for comp_id in comparison_ids:
                            chart_dataset_ids.add(comp_id)

                    if not chart_dataset_ids:
                        print(f"Warning: Chart {chart.id} has no valid trace_ids with dataset references")
                        continue

                    # Map dataset IDs to actual dataset objects
                    chart_datasets = {}
                    for dataset_id in chart_dataset_ids:
                        if dataset_id in self._main_panels.dataset_browser._datasets:
                            chart_datasets[dataset_id] = self._main_panels.dataset_browser._datasets[dataset_id]
                        else:
                            print(f"Warning: Dataset '{dataset_id}' not found for chart {chart.id}")

                    if not chart_datasets:
                        print(f"Warning: No datasets found for chart {chart.id}")
                        continue

                    # Use the first dataset for chart widget creation (needed for initialization)
                    primary_dataset_id = list(chart_datasets.keys())[0]
                    primary_dataset = chart_datasets[primary_dataset_id]

                    # Recreate the chart widget with counter-based naming
                    chart_widget = self._create_chart_widget(
                        chart.chart_type,
                        primary_dataset,
                        chart.tab_title
                    )
                    if chart_widget:
                        chart_widget.set_chart_title(chart.title)

                        # Add chart to charts area (use primary dataset ID for tracking)
                        self._main_panels.charts_area.add_chart(chart.id, chart, chart_widget, primary_dataset_id)

                        # Restore the traces that were in this chart (NEW: multi-dataset support)
                        # Skip trace restoration for linear phase error charts (they use custom config)
                        if chart.chart_type.lower() not in ['linearphaseerror', 'phasedifference']:
                            # Pass saved trace data if available for style preservation
                            saved_traces = getattr(chart, 'traces', {})
                            self._restore_chart_traces_multi_dataset(
                                chart_widget, chart_datasets, chart.trace_ids, chart.chart_type, saved_traces
                            )

                        # Restore limit lines if they exist
                        if hasattr(chart, 'limit_lines') and chart.limit_lines:
                            chart_widget.restore_limit_lines(chart.limit_lines)

                        # Restore font, color, and plot area settings if they exist
                        try:
                            if hasattr(chart, 'chart_fonts') and chart.chart_fonts:
                                chart_widget.restore_chart_fonts(chart.chart_fonts)
                            if hasattr(chart, 'chart_colors') and chart.chart_colors:
                                chart_widget.restore_chart_colors(chart.chart_colors)
                            if hasattr(chart, 'plot_area_settings') and chart.plot_area_settings:
                                chart_widget.restore_plot_area_settings(chart.plot_area_settings)
                            # Restore phase unwrap setting
                            if hasattr(chart, 'phase_unwrap') and hasattr(chart_widget, 'restore_phase_unwrap'):
                                chart_widget.restore_phase_unwrap(chart.phase_unwrap)

                            # Restore axis ranges
                            if hasattr(chart, 'axes') and chart.axes and hasattr(chart_widget, 'restore_axis_ranges'):
                                if not chart.axes.x.auto_range or not chart.axes.y.auto_range:
                                    axis_ranges = {}
                                    if not chart.axes.x.auto_range:
                                        axis_ranges['x_min'] = chart.axes.x.min_value
                                        axis_ranges['x_max'] = chart.axes.x.max_value
                                    if not chart.axes.y.auto_range:
                                        axis_ranges['y_min'] = chart.axes.y.min_value
                                        axis_ranges['y_max'] = chart.axes.y.max_value
                                    chart_widget.restore_axis_ranges(axis_ranges)

                            # Restore linear phase error data BEFORE markers
                            if hasattr(chart, 'linear_phase_error_data') and chart.linear_phase_error_data:
                                if hasattr(chart_widget, 'restore_linear_phase_error_config'):
                                    # Get the dataset for linear phase error recalculation
                                    lpe_dataset_id = chart.linear_phase_error_data.get('dataset_id')
                                    lpe_dataset = chart_datasets.get(lpe_dataset_id) if lpe_dataset_id else None
                                    chart_widget.restore_linear_phase_error_config(
                                        chart.linear_phase_error_data, lpe_dataset
                                    )
                            # Restore phase difference data BEFORE markers
                            if hasattr(chart, 'phase_difference_data') and chart.phase_difference_data:
                                if hasattr(chart_widget, 'restore_phase_difference_config'):
                                    chart_widget.restore_phase_difference_config(
                                        chart.phase_difference_data, chart_datasets
                                    )

                            # Restore markers AFTER special plots so trace data is available
                            if hasattr(chart, 'markers') and chart.markers and hasattr(chart_widget, 'restore_markers'):
                                marker_mode_active = getattr(chart, 'marker_mode_active', False)
                                marker_coupled_mode = getattr(chart, 'marker_coupled_mode', False)
                                marker_show_overlay = getattr(chart, 'marker_show_overlay', True)
                                marker_show_table = getattr(chart, 'marker_show_table', False)
                                marker_overlay_offset = None
                                if (hasattr(chart, 'marker_overlay_offset_x') and
                                        hasattr(chart, 'marker_overlay_offset_y')):
                                    if (chart.marker_overlay_offset_x is not None and
                                            chart.marker_overlay_offset_y is not None):
                                        marker_overlay_offset = (
                                            chart.marker_overlay_offset_x,
                                            chart.marker_overlay_offset_y
                                        )

                                chart_widget.restore_markers(
                                    chart.markers,
                                    marker_mode_active=marker_mode_active,
                                    marker_coupled_mode=marker_coupled_mode,
                                    marker_show_overlay=marker_show_overlay,
                                    marker_show_table=marker_show_table,
                                    marker_overlay_offset=marker_overlay_offset
                                )

                            # Restore legend columns and position
                            if hasattr(chart, 'legend_columns') and hasattr(chart_widget, 'set_legend_columns'):
                                chart_widget.set_legend_columns(chart.legend_columns)

                            if hasattr(chart, 'legend_offset_x') and hasattr(chart, 'legend_offset_y'):
                                if chart.legend_offset_x is not None and chart.legend_offset_y is not None:
                                    if hasattr(chart_widget, 'set_legend_offset'):
                                        chart_widget.set_legend_offset(
                                            chart.legend_offset_x, chart.legend_offset_y)

                        except Exception as e:
                            print(f"Warning: Could not restore styling settings for chart {chart.id}: {e}")
                            # Continue without styling restoration

                        charts_restored += 1
                    else:
                        charts_failed += 1

                except Exception:
                    charts_failed += 1

            # Show comprehensive status message
            if datasets_loaded > 0:
                msg = f"Project '{project.name}' loaded: {datasets_loaded} dataset(s)"
                if datasets_failed > 0:
                    msg += f" ({datasets_failed} failed)"

                if charts_restored > 0:
                    msg += f", {charts_restored} chart(s) restored"
                    if charts_failed > 0:
                        msg += f" ({charts_failed} failed)"
                elif len(project.charts) > 0:
                    msg += f", {charts_failed} chart(s) could not be restored"

                self.statusBar().showMessage(msg)

                # Show summary dialog if there were issues
                if charts_failed > 0 or datasets_failed > 0:
                    issues = []
                    if datasets_failed > 0:
                        issues.append(f"{datasets_failed} dataset(s) failed to load")
                    if charts_failed > 0:
                        issues.append(f"{charts_failed} chart(s) could not be restored")

                    QMessageBox.information(
                        self,
                        "Project Load Summary",
                        f"Project '{project.name}' loaded successfully!\n\n"
                        f"Restored: {datasets_loaded} dataset(s), {charts_restored} chart(s)\n"
                        f"Issues: {', '.join(issues) if issues else 'None'}"
                    )
            else:
                self.statusBar().showMessage(f"Project '{project.name}' loaded (no datasets)")

        except Exception as e:
            QMessageBox.warning(
                self,
                "Project Load Warning",
                f"Project loaded but some data may not be restored properly:\n\n{str(e)}"
            )

    def _on_add_traces_requested(self, chart_widget: ChartView | SmithView, chart_type: str) -> None:
        """Handle request to manage traces in an existing chart."""
        try:
            # Get all available datasets
            available_datasets = {}
            for dataset_id, dataset in self._main_panels.dataset_browser._datasets.items():
                available_datasets[dataset_id] = dataset

            if not available_datasets:
                QMessageBox.information(self, "No Datasets",
                                        "No datasets are loaded. Please load S-parameter files first.")
                return

            # Get existing traces with their details
            existing_traces = chart_widget.get_existing_traces()

            # Show trace management dialog
            dialog = AddTracesDialog(available_datasets, chart_type, existing_traces, self)

            # Set up callbacks for Apply button functionality
            dialog._apply_callback = lambda traces_to_add, traces_to_remove, selected_datasets: \
                self._apply_trace_changes(chart_widget, traces_to_add, traces_to_remove, selected_datasets)
            dialog._refresh_callback = lambda: chart_widget.get_existing_traces()

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Get traces to add and remove
                traces_to_add = dialog.get_traces_to_add()
                traces_to_remove = dialog.get_traces_to_remove()
                selected_datasets = dialog.get_selected_datasets()

                # Remove traces first
                removed_count = 0
                for trace_id in traces_to_remove:
                    chart_widget.remove_trace(trace_id)
                    removed_count += 1

                # Add new traces
                added_count = 0
                for trace_id, trace in traces_to_add:
                    dataset = selected_datasets[trace.dataset_id]
                    chart_widget.add_trace(trace_id, trace, dataset)
                    added_count += 1

                # Update status
                if added_count > 0 and removed_count > 0:
                    self.statusBar().showMessage(f"Added {added_count} trace(s), removed {removed_count} trace(s)")
                elif added_count > 0:
                    self.statusBar().showMessage(f"Added {added_count} trace(s) to chart")
                elif removed_count > 0:
                    self.statusBar().showMessage(f"Removed {removed_count} trace(s) from chart")
                else:
                    self.statusBar().showMessage("No changes made to chart")

        except Exception as e:
            QMessageBox.critical(self, "Trace Management Error", f"Failed to manage traces: {str(e)}")

    def _apply_trace_changes(self, chart_widget: ChartView | SmithView,
                             traces_to_add,
                             traces_to_remove,
                             selected_datasets) -> None:
        """Helper method to apply trace changes for the Apply button."""
        try:
            # Remove traces first
            removed_count = 0
            for trace_id in traces_to_remove:
                chart_widget.remove_trace(trace_id)
                removed_count += 1

            # Add new traces
            added_count = 0
            for trace_id, trace in traces_to_add:
                dataset = selected_datasets[trace.dataset_id]
                chart_widget.add_trace(trace_id, trace, dataset)
                added_count += 1

            # Update status
            if added_count > 0 and removed_count > 0:
                self.statusBar().showMessage(f"Applied: Added {added_count} trace(s), removed {removed_count} trace(s)")
            elif added_count > 0:
                self.statusBar().showMessage(f"Applied: Added {added_count} trace(s) to chart")
            elif removed_count > 0:
                self.statusBar().showMessage(f"Applied: Removed {removed_count} trace(s) from chart")
            else:
                self.statusBar().showMessage("Applied: No changes made to chart")

        except Exception as e:
            QMessageBox.critical(self, "Apply Error", f"Failed to apply trace changes: {str(e)}")

    # Utility Methods
    def _is_file_already_loaded(self, file_path: str) -> bool:
        """Check if a file is already loaded in the current project."""
        if not self._current_project:
            return False

        file_path_obj = Path(file_path).resolve()
        for dataset_ref in self._current_project.dataset_refs:
            if Path(dataset_ref.file_path).resolve() == file_path_obj:
                return True
        return False

    def _get_last_directory(self) -> Path:
        """Get the last used directory from settings."""
        last_dir = self._settings.value("lastDirectory", "")
        if last_dir and Path(last_dir).exists():
            return Path(last_dir)
        return Path.home()

    def _save_last_directory(self, file_path: str) -> None:
        """Save the directory of the given file path."""
        directory = Path(file_path).parent
        self._settings.setValue("lastDirectory", str(directory))

    def _add_to_recent_files(self, file_path: str) -> None:
        """Add file to recent files list."""
        recent_files = self._settings.value("recentFiles", [])
        if not isinstance(recent_files, list):
            recent_files = []

        # Remove if already in list
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to beginning
        recent_files.insert(0, file_path)

        # Keep only last 10
        recent_files = recent_files[:10]

        self._settings.setValue("recentFiles", recent_files)
        self._save_last_directory(file_path)
        self._update_recent_files_menu()

    def _update_recent_files_menu(self) -> None:
        """Update the recent files menu."""
        self._recent_files_menu.clear()

        recent_files = self._settings.value("recentFiles", [])
        if not isinstance(recent_files, list):
            recent_files = []

        if not recent_files:
            action = self._recent_files_menu.addAction("No recent files")
            action.setEnabled(False)
            return

        for file_path in recent_files:
            if Path(file_path).exists():
                action = self._recent_files_menu.addAction(Path(file_path).name)
                action.setStatusTip(file_path)
                action.triggered.connect(lambda checked, path=file_path: self._load_touchstone_file(path))

    def _autosave(self) -> None:
        """Perform autosave if enabled and project is modified."""
        if not self._modified or not self._current_project:
            return

        # Only autosave if we have a project path
        if self._current_project_path:
            try:
                backup_path = self._current_project_path.with_suffix('.snpproj.bak')
                # Don't update current path when autosaving to backup
                self._save_project_to_path(backup_path, update_current_path=False)
            except Exception:
                # Silently ignore autosave errors
                pass

    # Dialog Methods
    def _show_preferences(self) -> None:
        """Show preferences dialog with persistent storage."""
        # Load preferences from persistent storage or project
        if self._current_project and self._current_project.preferences:
            # Use project preferences if available
            prefs_dict = self._current_project.preferences.to_dict()
        else:
            # Load from persistent application settings
            saved_prefs = self._settings.value("user_preferences", None)
            if saved_prefs and isinstance(saved_prefs, dict):
                # User has saved preferences - use them
                prefs_dict = saved_prefs
            else:
                # No saved preferences - use defaults
                prefs_dict = Preferences().to_dict()

        # Show preferences dialog
        dialog = PreferencesDialog(prefs_dict, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Get updated preferences
            updated_prefs = dialog.get_preferences()

            # Always save to persistent application settings
            self._settings.setValue("user_preferences", updated_prefs)
            self._settings.sync()  # Force write to disk

            # Also update project preferences if project is open
            if self._current_project:
                self._current_project.preferences = Preferences.from_dict(updated_prefs)
                self._set_modified(True)
                self.statusBar().showMessage(
                    "Preferences updated and saved (applied to current project)", 3000
                )
            else:
                self.statusBar().showMessage(
                    "Preferences saved (will apply to new charts)", 3000
                )

    def _show_linear_phase_error_analysis(self) -> None:
        """Show the Linear Phase Error Analysis dialog."""
        # Get all datasets from the dataset browser
        datasets = self._main_panels.dataset_browser._datasets

        if not datasets:
            QMessageBox.information(
                self,
                "No Datasets",
                "No datasets are available. Please load data files first."
            )
            return

        # Create and show the dialog
        dialog = LinearPhaseErrorDialog(datasets, self)
        dialog.create_chart_requested.connect(self._on_create_linear_phase_error_chart)
        dialog.exec()

    def _show_phase_difference_analysis(self) -> None:
        """Show the Phase Difference Analysis dialog."""
        # Get all datasets from the dataset browser
        datasets = self._main_panels.dataset_browser._datasets

        if not datasets:
            QMessageBox.information(
                self,
                "No Datasets",
                "No datasets are available. Please load data files first."
            )
            return

        if len(datasets) < 2:
            QMessageBox.information(
                self,
                "Insufficient Datasets",
                "At least two datasets are required for phase difference analysis."
            )
            return

        # Create and show the dialog
        dialog = PhaseDifferenceDialog(datasets, self)
        dialog.create_chart_requested.connect(self._on_create_phase_difference_chart)
        dialog.exec()

    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About SnP Viewer",
            """<h3>SnP Viewer</h3>
            <p>A modern tool for S-parameter visualization and analysis.</p>
            <p>Built with Python, PySide6, and PyQtGraph.</p>
            <p>Version 1.0.0</p>
            """
        )

    # Threaded loader signal handlers
    def _on_file_load_started(self, file_path: str) -> None:
        """Handle file loading started."""
        file_name = Path(file_path).name
        self._show_progress(f"Loading {file_name}...", 0)

    def _on_file_load_progress(self, file_path: str, progress: float) -> None:
        """Handle file loading progress."""
        file_name = Path(file_path).name
        progress_percent = int(progress * 100)
        self._show_progress(f"Loading {file_name}...", progress_percent)

    def _on_file_load_finished(self, file_path: str, dataset: Dataset) -> None:
        """Handle successful file loading."""
        try:
            # Create new project if none exists
            if self._current_project is None:
                self._new_project()

            # Keep the dataset's UUID for internal tracking
            dataset_uuid = dataset.id

            # Add dataset to project
            if self._current_project:
                dataset_ref = DatasetRef(
                    dataset_id=dataset_uuid,  # Store UUID in project
                    file_path=file_path,
                    file_name=Path(file_path).name,
                    display_name=dataset.display_name,  # Save the display name
                    last_modified=dataset.file_modified,
                    file_size=Path(file_path).stat().st_size if Path(file_path).exists() else None,
                    load_status='loaded'
                )
                self._current_project.add_dataset_ref(dataset_ref)

            # Add dataset to browser with dataset UUID as the key
            self._main_panels.dataset_browser.add_dataset(dataset.id, dataset)

            # Emit signal
            self.file_opened.emit(file_path)

            # Update recent files
            self._add_to_recent_files(file_path)

            # Update UI state
            self._enable_project_actions(True)
            self._set_modified(True)

        except Exception as e:
            # If there's an error in processing, show it
            file_name = Path(file_path).name
            QMessageBox.critical(
                self,
                "Error Processing File",
                f"Failed to process loaded file '{file_name}':\n\n{str(e)}"
            )

    def _on_file_load_error(self, file_path: str, error_message: str) -> None:
        """Handle file loading error."""
        QMessageBox.critical(
            self,
            "Error Loading File",
            f"Failed to load file:\n\n{error_message}"
        )

    def _on_all_files_loaded(self) -> None:
        """Handle completion of all file loading operations."""
        self._show_progress("All files loaded successfully", 100)
        self._hide_progress_delayed()

    def _create_chart_widget(self, chart_type: str, dataset: Dataset, tab_title: str = None):
        """
        Create a chart widget of the specified type.

        Args:
            chart_type: Type of chart to create
            dataset: Dataset to associate with the chart
            tab_title: User-friendly name for the dataset (optional)

        Returns:
            Chart widget instance or None if creation failed
        """
        try:
            if chart_type.lower() in ['smith', 'smith_chart', 'smithz', 'smithy']:
                chart_widget = SmithView()
                chart_widget.set_dataset(dataset)
                return chart_widget
            else:
                chart_widget = ChartView()

                # Connect signals
                chart_widget.add_traces_requested.connect(
                    lambda: self._on_add_traces_requested(chart_widget, chart_type)
                )
                chart_widget.properties_changed.connect(
                    lambda: self._set_modified(True)
                )
                chart_widget.create_new_chart_requested.connect(
                    self._on_create_linear_phase_error_chart
                )

                # Set the dataset name for tab title generation
                display_name = tab_title if tab_title else dataset.display_name

                chart_widget.set_chart_tab_title(display_name)

                # Set the correct plot type based on chart_type
                if chart_type.lower() == "magnitude":
                    chart_widget.set_plot_type(PlotType.MAGNITUDE)
                elif chart_type.lower() == "phase":
                    chart_widget.set_plot_type(PlotType.PHASE)
                elif chart_type.lower() in ["group_delay", "groupdelay"]:
                    chart_widget.set_plot_type(PlotType.GROUP_DELAY)
                elif chart_type.lower() in ["linearphaseerror", "linear_phase_error"]:
                    chart_widget.set_plot_type(PlotType.LINEAR_PHASE_ERROR)
                elif chart_type.lower() in ["phasedifference", "phase_difference"]:
                    chart_widget.set_plot_type(PlotType.PHASE_DIFFERENCE)

                return chart_widget

        except Exception as e:
            print(f"Error creating chart widget: {e}")
            return None

    def _restore_chart_traces_multi_dataset(
        self, chart_widget, datasets: dict, trace_ids: list, chart_type: str, saved_traces: dict = None
    ):
        """
        Restore traces from multiple datasets to a chart widget.
        Uses standardized trace_id format: dataset_id:S{i},{j}_{plot_type}

        Args:
            chart_widget: The chart widget to restore traces to
            datasets: Dictionary of available datasets {dataset_id: Dataset}
            trace_ids: List of trace IDs to restore
            chart_type: Type of chart being restored
            saved_traces: Optional dict of saved trace data {trace_id: trace_dict} for style preservation
        """
        try:
            traces_to_add = []

            for idx, trace_id in enumerate(trace_ids):
                try:
                    # Parse: dataset_id:S{i},{j}_{plot_type}
                    if ':' not in trace_id:
                        continue
                    dataset_id, rest = trace_id.split(':', 1)
                    if dataset_id not in datasets:
                        continue
                    dataset = datasets[dataset_id]

                    # Parse S-parameter
                    s_param = rest.split('_')[0] if '_' in rest else rest
                    if not s_param.startswith('S'):
                        continue
                    param_part = s_param[1:]
                    if ',' not in param_part:
                        continue
                    parts = param_part.split(',')
                    i, j = int(parts[0]), int(parts[1])

                    # Get data
                    if dataset.get_s_parameter(i, j) is None:
                        continue

                    # Determine metric
                    if chart_type.lower() == "magnitude":
                        metric = "magnitude_dB"
                    elif chart_type.lower() == "phase":
                        metric = "phase_deg"
                    elif chart_type.lower() in ['smith', 'smith_chart']:
                        metric = "reflection" if i == j else "transmission"
                    else:
                        metric = chart_type.lower()

                    # Check if we have saved trace data for this trace_id
                    if saved_traces and trace_id in saved_traces:
                        # Restore trace from saved data (includes style)
                        trace = Trace.from_dict(saved_traces[trace_id])
                    else:
                        # Create trace with default style
                        line_style = DEFAULT_LINE_STYLES[(idx // len(DEFAULT_TRACE_COLORS)) % len(DEFAULT_LINE_STYLES)]
                        style = TraceStyle(
                            color=DEFAULT_TRACE_COLORS[idx % len(DEFAULT_TRACE_COLORS)],
                            line_width=2,
                            line_style=line_style
                        )
                        trace = Trace(
                            id=trace_id,
                            dataset_id=dataset_id,
                            domain="S",
                            metric=metric,
                            port_path=PortPath(i=i, j=j),
                            style=style
                        )
                    traces_to_add.append((trace_id, trace, dataset))
                except Exception:
                    continue

            # Add traces to chart
            if traces_to_add:
                for trace_id, trace, dataset in traces_to_add:
                    if hasattr(chart_widget, 'add_trace'):
                        if chart_type.lower() in ['smith', 'smith_chart']:
                            chart_widget.add_trace(trace, trace.style)
                        else:
                            chart_widget.add_trace(trace_id, trace, dataset)
        except Exception as e:
            print(f"Error restoring traces: {e}")

    def _restore_chart_traces(self, chart_widget, dataset: Dataset, trace_ids: list, chart_type: str):
        """
        Restore traces to a chart widget based on saved trace IDs.

        Args:
            chart_widget: The chart widget to add traces to
            dataset: Dataset containing the trace data
            trace_ids: List of trace IDs to restore
            chart_type: Type of chart for trace creation
        """
        try:
            # Create traces based on the stored trace IDs
            traces_to_add = []

            # Color palette for different traces
            for idx, trace_id in enumerate(trace_ids):

                s_param = None

                # Parse trace ID to extract S-parameter info
                # Handle multiple formats:
                if ':' in trace_id:
                    # New format: "dataset_id:S11"
                    _, s_param = trace_id.split(':', 1)

                elif '_' in trace_id:
                    # Current format: "S1,2_magnitude_dataset" or legacy "S11_magnitude"
                    s_param = trace_id.split('_')[0]

                else:
                    # Direct format: "S11", "S21", etc.
                    s_param = trace_id

                if s_param:

                    # Create trace for this S-parameter
                    if hasattr(dataset, 'create_trace'):
                        trace = dataset.create_trace(s_param, trace_id)
                        if trace:
                            traces_to_add.append(trace)

                    else:
                        # Fallback: create trace using existing methods
                        s_param_data = None

                        # Try different ways to get S-parameter data
                        if hasattr(dataset, 'get_s_parameter'):
                            try:
                                # Parse S-parameter string
                                # Handle formats: "S1,2" (new) or "S12" (old)
                                if s_param.startswith('S'):
                                    param_part = s_param[1:]  # Remove 'S'
                                    if ',' in param_part:
                                        # New format: "S1,2"
                                        parts = param_part.split(',')
                                        i = int(parts[0])
                                        j = int(parts[1])
                                    else:
                                        # Old format: "S12" or "S11"
                                        if len(param_part) >= 2:
                                            i = int(param_part[0])
                                            j = int(param_part[1])
                                        else:
                                            continue
                                    s_param_data = dataset.get_s_parameter(i, j)
                            except Exception as e:
                                print(f"Warning: Failed to parse S-parameter '{s_param}': {e}")
                                pass

                        if s_param_data is not None:
                            # Parse S-parameter to get port indices
                            try:
                                if s_param.startswith('S'):
                                    param_part = s_param[1:]  # Remove 'S'
                                    if ',' in param_part:
                                        # New format: "S1,2"
                                        parts = param_part.split(',')
                                        i = int(parts[0])
                                        j = int(parts[1])
                                    else:
                                        # Old format: "S12" or "S11"
                                        if len(param_part) >= 2:
                                            i = int(param_part[0])
                                            j = int(param_part[1])
                                        else:
                                            continue

                                    # Determine metric based on chart type
                                    if chart_type.lower() == "magnitude":
                                        metric = "magnitude_dB"
                                    elif chart_type.lower() == "phase":
                                        metric = "phase_deg"
                                    elif chart_type.lower() in ['smith', 'smith_chart']:
                                        metric = "reflection" if i == j else "transmission"
                                    else:
                                        metric = chart_type.lower()

                                    # Create trace with correct parameters
                                    # Use different colors and styles for different traces
                                    color = DEFAULT_TRACE_COLORS[idx % len(DEFAULT_TRACE_COLORS)]
                                    line_style = DEFAULT_LINE_STYLES[(idx // len(DEFAULT_TRACE_COLORS))
                                                                     % len(DEFAULT_LINE_STYLES)]

                                    style = TraceStyle(
                                        color=color,
                                        line_width=2,
                                        line_style=line_style
                                    )

                                    trace = Trace(
                                        id=trace_id,
                                        dataset_id=dataset.id,
                                        domain="S",
                                        metric=metric,
                                        port_path=PortPath(i=i, j=j),
                                        style=style
                                    )
                                    traces_to_add.append(trace)
                            except Exception as e:
                                print(f"Warning: Failed to create trace for '{s_param}': {e}")
                                pass

            # Add traces to the chart widget
            if traces_to_add:
                # Convert to the format expected by _add_selected_traces: List[Tuple[str, Trace]]
                trace_tuples = [(trace.id, trace) for trace in traces_to_add]

                self._add_selected_traces(chart_widget, dataset, trace_tuples, chart_type)

        except Exception as e:
            print(f"Error restoring traces: {e}")


def show_taskbar_icon(app_id: str) -> None:
    """
    Show the taskbar icon for a Windows application.

    Args:
        app_id (str): The application ID to set for the taskbar icon.
    """
    if platform.system() == 'Windows':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("SnP Viewer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SnPViewer")
    app.setOrganizationDomain("snpviewer.com")

    # Set application style
    app.setStyle("Fusion")

    show_taskbar_icon("snpviewer.app.1")

    # Create and show main window
    window = SnPViewerMainWindow()
    window.show()

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
