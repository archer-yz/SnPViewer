"""
Threaded loader service for non-blocking file operations.

This module provides threaded file loading capabilities to prevent UI blocking
during parsing of large Touchstone files.
"""

import os
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from snpviewer.backend.conversions import touchstone_to_dataset
from snpviewer.backend.models.dataset import Dataset
from snpviewer.backend import parse_touchstone


class LoaderSignals(QObject):
    """Signals for the threaded loader."""

    # Emitted when file loading starts
    started = Signal(str)  # file_path

    # Emitted with progress updates (0.0 to 1.0)
    progress = Signal(str, float)  # file_path, progress

    # Emitted when loading completes successfully
    finished = Signal(str, Dataset)  # file_path, dataset

    # Emitted when loading fails
    error = Signal(str, str)  # file_path, error_message

    # Emitted when all queued operations complete
    all_finished = Signal()


class TouchstoneLoadTask(QRunnable):
    """Runnable task for loading a single Touchstone file."""

    def __init__(self, file_path: str, signals: LoaderSignals):
        super().__init__()
        self.file_path = file_path
        self.signals = signals
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        """Execute the file loading task."""
        try:
            # Emit started signal
            self.signals.started.emit(self.file_path)

            # Emit initial progress
            self.signals.progress.emit(self.file_path, 0.0)

            # Check if file exists
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"File not found: {self.file_path}")

            # Parse the touchstone file
            self.signals.progress.emit(self.file_path, 0.3)
            touchstone_data = parse_touchstone(self.file_path)

            # Convert to dataset
            self.signals.progress.emit(self.file_path, 0.7)

            # Create additional metadata
            additional_metadata = {
                'file_size': os.path.getsize(self.file_path),
                'modified_time': os.path.getmtime(self.file_path),
            }

            # Use the conversion function to create dataset
            dataset = touchstone_to_dataset(touchstone_data, self.file_path, additional_metadata)

            # Emit completion
            self.signals.progress.emit(self.file_path, 1.0)
            self.signals.finished.emit(self.file_path, dataset)

        except Exception as e:
            error_msg = f"Failed to load {Path(self.file_path).name}: {str(e)}"
            self.signals.error.emit(self.file_path, error_msg)


class ThreadedLoader(QObject):
    """
    Threaded file loader service using QThreadPool.

    Provides non-blocking file loading with progress reporting and error handling.
    Manages a queue of file loading tasks and coordinates their execution.
    """

    # Re-expose signals for convenience
    started = Signal(str)  # file_path
    progress = Signal(str, float)  # file_path, progress
    finished = Signal(str, Dataset)  # file_path, dataset
    error = Signal(str, str)  # file_path, error_message
    all_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        # Thread pool for managing background tasks
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(4)  # Limit concurrent file operations

        # Signals object for communication
        self.signals = LoaderSignals()

        # Connect internal signals to external ones
        self.signals.started.connect(self.started)
        self.signals.progress.connect(self.progress)
        self.signals.finished.connect(self.finished)
        self.signals.error.connect(self.error)
        self.signals.all_finished.connect(self.all_finished)

        # Track active tasks
        self._active_tasks = set()
        self._pending_count = 0

        # Connect to track task completion
        self.signals.finished.connect(self._on_task_finished)
        self.signals.error.connect(self._on_task_finished)

    def load_file(self, file_path: str) -> None:
        """
        Queue a file for loading in the background.

        Args:
            file_path: Path to the Touchstone file to load
        """
        # Convert to absolute path
        abs_path = os.path.abspath(file_path)

        # Skip if already loading this file
        if abs_path in self._active_tasks:
            return

        # Create and queue the task
        task = TouchstoneLoadTask(abs_path, self.signals)
        self._active_tasks.add(abs_path)
        self._pending_count += 1

        self.thread_pool.start(task)

    def load_files(self, file_paths: list[str]) -> None:
        """
        Queue multiple files for loading in the background.

        Args:
            file_paths: List of paths to Touchstone files to load
        """
        for file_path in file_paths:
            self.load_file(file_path)

    def wait_for_completion(self, timeout_ms: int = 30000) -> bool:
        """
        Wait for all queued tasks to complete.

        Args:
            timeout_ms: Maximum time to wait in milliseconds

        Returns:
            True if all tasks completed, False if timeout occurred
        """
        return self.thread_pool.waitForDone(timeout_ms)

    def cancel_all(self) -> None:
        """Cancel all pending tasks and clear the queue."""
        self.thread_pool.clear()
        self._active_tasks.clear()
        self._pending_count = 0

    def is_busy(self) -> bool:
        """Check if any loading tasks are currently active."""
        return self.thread_pool.activeThreadCount() > 0 or self._pending_count > 0

    def get_max_threads(self) -> int:
        """Get the maximum number of concurrent threads."""
        return self.thread_pool.maxThreadCount()

    def set_max_threads(self, count: int) -> None:
        """Set the maximum number of concurrent threads."""
        if count > 0:
            self.thread_pool.setMaxThreadCount(count)

    @Slot(str, Dataset)
    @Slot(str, str)
    def _on_task_finished(self, file_path: str, *args: Any) -> None:
        """Handle task completion (success or error)."""
        # Remove from active tasks
        if file_path in self._active_tasks:
            self._active_tasks.remove(file_path)

        # Decrement pending count
        self._pending_count = max(0, self._pending_count - 1)

        # Emit all_finished if no more tasks are pending
        if self._pending_count == 0 and not self.is_busy():
            self.all_finished.emit()

    def get_active_count(self) -> int:
        """Get the number of currently active loading tasks."""
        return len(self._active_tasks)

    def get_pending_count(self) -> int:
        """Get the number of pending loading tasks."""
        return self._pending_count


# Global instance for application-wide use
_loader_instance: Optional[ThreadedLoader] = None


def get_loader() -> ThreadedLoader:
    """Get the global ThreadedLoader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = ThreadedLoader()
    return _loader_instance


def set_loader(loader: ThreadedLoader) -> None:
    """Set a custom ThreadedLoader instance (mainly for testing)."""
    global _loader_instance
    _loader_instance = loader
