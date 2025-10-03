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

from PySide6 import QtGui
from PySide6.QtCore import QSettings, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QLabel,
                               QMainWindow, QMessageBox, QProgressBar, QWidget)

import snpviewer.frontend.resources_rc  # noqa: F401
from snpviewer.backend import parse_touchstone
from snpviewer.backend.conversions import touchstone_to_dataset
from snpviewer.backend.models.chart import AxisConfiguration, Chart, ChartAxes
from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend.models.project import DatasetRef, Preferences, Project
from snpviewer.backend.models.trace import PortPath, Trace, TraceStyle
from snpviewer.frontend.dialogs.add_traces import AddTracesDialog
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
        self.resize(1400, 900)

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
        self._toolbar.addAction(self._save_project_action)
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

        # Charts area signals
        charts_area = self._main_panels.charts_area
        charts_area.chart_selected.connect(self._on_chart_selected)
        charts_area.chart_closed.connect(self._on_chart_closed)

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
        """Create a new project."""
        if not self._check_unsaved_changes():
            return

        # Clear current project state first
        self._clear_current_project()

        self._current_project = Project(
            name="Untitled Project",
            preferences=Preferences()
        )
        self._current_project_path = None
        self._set_modified(False)

        # Update dataset browser with new project
        self._main_panels.dataset_browser.set_project(self._current_project)

        self._enable_project_actions(True)
        self._update_window_title()

        self.statusBar().showMessage("New project created", 2000)

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
                    # Update trace IDs
                    chart.trace_ids = list(chart_widget.get_existing_traces().keys())
                    # Update limit lines
                    chart.limit_lines = chart_widget.get_limit_lines()
                    # Update font, color, and plot area settings
                    if hasattr(chart_widget, 'get_chart_fonts'):
                        chart.chart_fonts = chart_widget.get_chart_fonts()
                    if hasattr(chart_widget, 'get_chart_colors'):
                        chart.chart_colors = chart_widget.get_chart_colors()
                    if hasattr(chart_widget, 'get_plot_area_settings'):
                        chart.plot_area_settings = chart_widget.get_plot_area_settings()

    def _save_project_to_path(self, file_path: Path) -> bool:
        """Save project to specified path."""
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
                f"Failed to save project to '{file_path}':\n\n{str(e)}"
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
                colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]
                for i in range(min(n_ports, 4)):  # Limit to 4 traces for readability
                    style = TraceStyle(
                        color=colors[i % len(colors)],
                        line_width=2,
                        marker_style='none'
                    )
                    trace = Trace(
                        id=f"S{i+1}{i+1}_smith",
                        dataset_id=dataset.id if hasattr(dataset, 'id') else '',
                        domain="S",
                        metric="reflection",
                        port_path=PortPath(i=i+1, j=i+1),
                        style=style
                    )
                    # SmithView.add_trace(trace, style)
                    chart_widget.add_trace(trace, style)
            else:
                # For Cartesian charts, add magnitude traces
                colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"]
                trace_count = 0

                # Add reflection parameters (S11, S22, etc.)
                for i in range(min(n_ports, 2)):  # S11, S22
                    style = TraceStyle(
                        color=colors[trace_count % len(colors)],
                        line_width=2,
                        marker_style='none'
                    )
                    trace_id = f"S{i+1}{i+1}_{chart_type}"
                    trace = Trace(
                        id=trace_id,
                        dataset_id=dataset.id if hasattr(dataset, 'id') else '',
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
                        style = TraceStyle(
                            color=colors[trace_count % len(colors)],
                            line_width=2,
                            line_style="dashed" if i != j else "solid",
                            marker_style='none'
                        )
                        trace_id = f"S{i+1}{j+1}_{chart_type}"
                        trace = Trace(
                            id=trace_id,
                            dataset_id=dataset.id if hasattr(dataset, 'id') else '',
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
        # Update menus, toolbars, or status based on selected chart
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

                        # Create dataset with the correct file path
                        dataset = touchstone_to_dataset(touchstone_data, str(file_path))

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
                    # Find the dataset for this chart's traces
                    chart_dataset = None
                    chart_dataset_id = None

                    # Look through loaded datasets to find one that matches this chart's traces
                    for dataset_id, dataset_obj in self._main_panels.dataset_browser._datasets.items():
                        # Try multiple matching strategies:
                        # 1. New format: trace_id starts with dataset_id (e.g., "dataset_id:S11")
                        trace_matches_new = [trace_id for trace_id in chart.trace_ids
                                             if trace_id.startswith(dataset_id)]

                        # 2. Check if trace_ids start with the original UUID (for backward compatibility)
                        original_uuid = None
                        for _uuid, friendly_name in uuid_to_friendly_name.items():
                            if friendly_name == dataset_id:
                                original_uuid = _uuid
                                break

                        trace_matches_uuid = []
                        if original_uuid:
                            trace_matches_uuid = [trace_id for trace_id in chart.trace_ids
                                                  if trace_id.startswith(original_uuid)]

                        # 2. Legacy format: check if dataset has S-parameters that match trace names
                        trace_matches_legacy = []

                        # Get available S-parameters using get_port_pairs or generate from n_ports
                        available_s_params = []
                        if hasattr(dataset_obj, 'get_port_pairs'):
                            try:
                                port_pairs = dataset_obj.get_port_pairs()
                                available_s_params = [f"S{i}{j}" for i, j in port_pairs]
                            except Exception:
                                pass

                        # Fallback: generate from n_ports
                        if not available_s_params and hasattr(dataset_obj, 'n_ports'):
                            n_ports = dataset_obj.n_ports
                            for i in range(1, n_ports + 1):
                                for j in range(1, n_ports + 1):
                                    available_s_params.append(f"S{i}{j}")

                        # Test each trace ID against available S-parameters
                        if available_s_params:
                            for trace_id in chart.trace_ids:
                                s_param = trace_id.split('_')[0] if '_' in trace_id else trace_id
                                if s_param in available_s_params:
                                    # Double-check by trying to get the actual data
                                    try:
                                        if hasattr(dataset_obj, 'get_s_parameter'):
                                            # Parse S-parameter string (e.g., "S11" -> i=1, j=1)
                                            if len(s_param) >= 3 and s_param.startswith('S'):
                                                i = int(s_param[1])  # First port number
                                                j = int(s_param[2])  # Second port number
                                                param_data = dataset_obj.get_s_parameter(i, j)
                                                if param_data is not None:
                                                    trace_matches_legacy.append(trace_id)
                                    except Exception:
                                        pass

                        if trace_matches_new or trace_matches_uuid or trace_matches_legacy:
                            chart_dataset = dataset_obj
                            chart_dataset_id = dataset_id
                            break

                    if chart_dataset and chart_dataset_id:
                        # # Get the next chart number for naming
                        # chart_number = self._main_panels.charts_area.get_next_chart_number()

                        # Recreate the chart widget with counter-based naming
                        chart_widget = self._create_chart_widget(
                            chart.chart_type,
                            chart_dataset,
                            chart.tab_title
                        )
                        if chart_widget:
                            chart_widget.set_chart_title(chart.title)

                            # Add chart to charts area
                            self._main_panels.charts_area.add_chart(chart.id, chart, chart_widget, chart_dataset_id)

                            # Restore the traces that were in this chart
                            self._restore_chart_traces(chart_widget, chart_dataset, chart.trace_ids, chart.chart_type)

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
                            except Exception as e:
                                print(f"Warning: Could not restore styling settings for chart {chart.id}: {e}")
                                # Continue without styling restoration

                            charts_restored += 1
                        else:
                            charts_failed += 1
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
                self._save_project_to_path(backup_path)
            except Exception:
                # Silently ignore autosave errors
                pass

    # Dialog Methods
    def _show_preferences(self) -> None:
        """Show preferences dialog."""
        QMessageBox.information(
            self,
            "Preferences",
            "Preferences dialog will be implemented in a future version."
        )

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

                return chart_widget

        except Exception as e:
            print(f"Error creating chart widget: {e}")
            return None

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
            colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD",
                      "#74B9FF", "#E17055", "#00B894", "#FDCB6E", "#6C5CE7", "#A29BFE"]

            for idx, trace_id in enumerate(trace_ids):

                s_param = None

                # Parse trace ID to extract S-parameter info
                # Handle multiple formats:
                if ':' in trace_id:
                    # New format: "dataset_id:S11"
                    _, s_param = trace_id.split(':', 1)

                elif '_' in trace_id:
                    # Legacy format: "S11_magnitude", "S21_phase", etc.
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
                                # Parse S-parameter string (e.g., "S11" -> i=1, j=1)
                                if len(s_param) >= 3 and s_param.startswith('S'):
                                    i = int(s_param[1])  # First port number
                                    j = int(s_param[2])  # Second port number
                                    s_param_data = dataset.get_s_parameter(i, j)
                            except Exception:
                                pass

                        if s_param_data is not None:
                            # Parse S-parameter to get port indices (e.g., "S21" -> i=2, j=1)
                            if len(s_param) >= 3 and s_param.startswith('S'):
                                i = int(s_param[1])  # First port number
                                j = int(s_param[2])  # Second port number

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
                                color = colors[idx % len(colors)]
                                line_style = "solid" if i == j else "dashed"  # Reflection vs transmission

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

                            else:
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
