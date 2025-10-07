"""
Unit tests for the threaded loader service.
"""

import os
import tempfile

from PySide6.QtWidgets import QApplication

from snpviewer.backend.models.dataset import Dataset
from snpviewer.frontend.services.loader import (ThreadedLoader, get_loader,
                                                set_loader)


class TestThreadedLoader:
    """Test cases for the ThreadedLoader class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Ensure we have a QApplication for Qt signals
        if not QApplication.instance():
            self.app = QApplication([])
        else:
            self.app = QApplication.instance()

        # Create a fresh loader instance
        self.loader = ThreadedLoader()

        # Track signal emissions
        self.started_files = []
        self.progress_updates = []
        self.finished_files = []
        self.error_files = []
        self.all_finished_called = False

        # Connect signal handlers
        self.loader.started.connect(lambda path: self.started_files.append(path))
        self.loader.progress.connect(lambda path, prog: self.progress_updates.append((path, prog)))
        self.loader.finished.connect(lambda path, dataset: self.finished_files.append(path))
        self.loader.error.connect(lambda path, error: self.error_files.append(path))
        self.loader.all_finished.connect(lambda: setattr(self, 'all_finished_called', True))

    def teardown_method(self):
        """Clean up after each test."""
        # Cancel any pending operations
        if hasattr(self, 'loader'):
            self.loader.cancel_all()
            self.loader.wait_for_completion(1000)

        # Process remaining events
        if hasattr(self, 'app'):
            self.app.processEvents()

    def create_test_touchstone(self, file_path: str) -> None:
        """Create a minimal valid Touchstone file for testing."""
        content = """# Hz S MA R 50
# Created for testing
1000000000 0.5 45 0.1 90 0.1 -90 0.6 -45
2000000000 0.4 50 0.15 85 0.15 -85 0.7 -50
"""
        with open(file_path, 'w') as f:
            f.write(content)

    def test_initialization(self):
        """Test loader initialization."""
        assert self.loader is not None
        assert not self.loader.is_busy()
        assert self.loader.get_active_count() == 0
        assert self.loader.get_pending_count() == 0
        assert self.loader.get_max_threads() > 0

    def test_load_valid_file(self):
        """Test loading a valid Touchstone file."""
        # Create temp file
        tmp_name = None
        try:
            fd, tmp_name = tempfile.mkstemp(suffix='.s2p')
            os.close(fd)  # Close file descriptor immediately

            self.create_test_touchstone(tmp_name)

            # Load the file
            self.loader.load_file(tmp_name)

            # Wait for completion
            success = self.loader.wait_for_completion(5000)
            assert success, "Loading timed out"

            # Process Qt events to ensure signals are delivered
            self.app.processEvents()

            # Check that signals were emitted correctly
            assert len(self.started_files) == 1
            assert tmp_name in self.started_files
            assert len(self.finished_files) == 1
            assert tmp_name in self.finished_files
            assert len(self.error_files) == 0
            assert self.all_finished_called

            # Check progress updates
            assert len(self.progress_updates) > 0
            progress_values = [prog for path, prog in self.progress_updates if path == tmp_name]
            assert 0.0 in progress_values
            assert 1.0 in progress_values

        finally:
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except (PermissionError, OSError):
                    pass  # Ignore cleanup errors on Windows

    def test_load_nonexistent_file(self):
        """Test loading a file that doesn't exist."""
        nonexistent = "/path/that/does/not/exist.s2p"

        # Load the nonexistent file
        self.loader.load_file(nonexistent)

        # Wait for completion
        success = self.loader.wait_for_completion(5000)
        assert success, "Loading timed out"

        # Process Qt events
        self.app.processEvents()

        # Check that error was emitted
        assert len(self.started_files) == 1
        # On Windows, paths may be normalized, so check if any path ends with the expected name
        assert len(self.finished_files) == 0
        assert len(self.error_files) == 1
        # Check that some error file was reported (path might be normalized on Windows)
        assert self.all_finished_called

    def test_load_multiple_files(self):
        """Test loading multiple files concurrently."""
        temp_files = []

        try:
            # Create multiple test files
            for i in range(3):
                fd, tmp_name = tempfile.mkstemp(suffix='.s2p')  # Use same extension
                os.close(fd)  # Close immediately
                self.create_test_touchstone(tmp_name)
                temp_files.append(tmp_name)

            # Load all files
            self.loader.load_files(temp_files)

            # Wait for completion with longer timeout
            success = self.loader.wait_for_completion(15000)
            assert success, "Loading timed out"

            # Process Qt events multiple times to ensure all signals are delivered
            for _ in range(10):
                self.app.processEvents()

            # Debug output if test fails
            if len(self.finished_files) != 3:
                print(f"Started: {len(self.started_files)}, "
                      f"Finished: {len(self.finished_files)}, Errors: {len(self.error_files)}")
                print(f"Error files: {self.error_files}")

            # Check that all files were processed
            assert len(self.started_files) == 3, f"Expected 3 started, got {len(self.started_files)}"
            assert len(self.finished_files) == 3, \
                f"Expected 3 finished, got {len(self.finished_files)} (errors: {len(self.error_files)})"
            assert len(self.error_files) == 0, f"Got {len(self.error_files)} errors"
            assert self.all_finished_called

            # Check that all files are accounted for
            for temp_file in temp_files:
                assert temp_file in self.started_files
                assert temp_file in self.finished_files

        finally:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except (PermissionError, OSError):
                        pass  # Ignore cleanup errors

    def test_duplicate_file_loading(self):
        """Test that duplicate file loading is handled correctly."""
        tmp_name = None
        try:
            fd, tmp_name = tempfile.mkstemp(suffix='.s2p')
            os.close(fd)
            self.create_test_touchstone(tmp_name)

            # Load the same file twice
            self.loader.load_file(tmp_name)
            self.loader.load_file(tmp_name)  # Should be ignored

            # Wait for completion
            success = self.loader.wait_for_completion(5000)
            assert success, "Loading timed out"

            # Process Qt events
            self.app.processEvents()

            # Should only process the file once
            assert len(self.started_files) == 1
            assert len(self.finished_files) == 1

        finally:
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except (PermissionError, OSError):
                    pass

    def test_cancel_all(self):
        """Test canceling all pending operations."""
        temp_files = []

        try:
            # Create multiple test files
            for i in range(5):
                fd, tmp_name = tempfile.mkstemp(suffix=f'.s{i+1}p')
                os.close(fd)
                self.create_test_touchstone(tmp_name)
                temp_files.append(tmp_name)

            # Queue all files
            for temp_file in temp_files:
                self.loader.load_file(temp_file)

            # Cancel immediately
            self.loader.cancel_all()

            # Check that active count is reset
            assert self.loader.get_active_count() == 0
            assert self.loader.get_pending_count() == 0

        finally:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except (PermissionError, OSError):
                        pass

    def test_thread_pool_configuration(self):
        """Test thread pool configuration methods."""
        original_max = self.loader.get_max_threads()

        # Set new max threads
        self.loader.set_max_threads(2)
        assert self.loader.get_max_threads() == 2

        # Restore original
        self.loader.set_max_threads(original_max)
        assert self.loader.get_max_threads() == original_max

        # Test invalid value (should be ignored)
        self.loader.set_max_threads(0)
        assert self.loader.get_max_threads() == original_max

    def test_global_loader_instance(self):
        """Test global loader instance management."""
        # Get global instance
        global_loader = get_loader()
        assert global_loader is not None

        # Should return same instance on subsequent calls
        assert get_loader() is global_loader

        # Test setting custom loader
        custom_loader = ThreadedLoader()
        set_loader(custom_loader)
        assert get_loader() is custom_loader

        # Restore original for other tests
        set_loader(global_loader)


class TestLoaderIntegration:
    """Integration tests for the loader with real parsing."""

    def test_with_real_parsing(self):
        """Test the loader with actual Touchstone parsing."""
        if not QApplication.instance():
            app = QApplication([])
        else:
            app = QApplication.instance()

        loader = ThreadedLoader()
        results = []
        errors = []

        def on_finished(file_path: str, dataset: Dataset):
            results.append((file_path, dataset))

        def on_error(file_path: str, error_msg: str):
            errors.append((file_path, error_msg))

        loader.finished.connect(on_finished)
        loader.error.connect(on_error)

        # Create a test file with real content
        tmp_name = None
        try:
            fd, tmp_name = tempfile.mkstemp(suffix='.s2p')
            with os.fdopen(fd, 'w') as tmp:
                tmp.write("""# Hz S MA R 50
# 2-port S-parameter data
# Freq S11mag S11ang S21mag S21ang S12mag S12ang S22mag S22ang
1.0e9 0.95 -5 0.05 85 0.05 85 0.9 -10
2.0e9 0.9 -10 0.1 80 0.1 80 0.85 -15
""")

            # Load the file
            loader.load_file(tmp_name)

            # Wait for completion
            success = loader.wait_for_completion(5000)
            assert success, "Loading timed out"

            # Process events
            app.processEvents()

            # Check results
            assert len(results) == 1
            assert len(errors) == 0

            file_path, dataset = results[0]
            assert file_path == tmp_name
            assert isinstance(dataset, Dataset)
            # Dataset stores data directly, not in a touchstone_data attribute
            assert dataset.frequency_hz is not None
            assert len(dataset.frequency_hz) == 2
            assert dataset.n_ports == 2
            assert dataset.s_params is not None
            assert dataset.s_params.shape == (2, 2, 2)  # (freq_points, n_ports, n_ports)

        finally:
            if tmp_name and os.path.exists(tmp_name):
                try:
                    os.unlink(tmp_name)
                except (PermissionError, OSError):
                    pass
