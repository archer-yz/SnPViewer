"""
Project persistence service for saving and loading SnP Viewer projects.

Handles JSON serialization/deserialization with path relinking for portability
and crash recovery mechanisms.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from snpviewer.backend.models.project import DatasetRef, Project


class ProjectError(Exception):
    """Base exception for project-related errors."""
    pass


class ProjectSaveError(ProjectError):
    """Error occurred during project save operation."""
    pass


class ProjectLoadError(ProjectError):
    """Error occurred during project load operation."""
    pass


class PathResolver:
    """
    Handles path resolution for project portability.

    Converts between absolute and relative paths to enable projects
    to work when moved between different locations or computers.
    """

    def __init__(self, project_dir: Optional[Path] = None):
        self.project_dir = project_dir

    def make_relative(self, file_path: str) -> str:
        """
        Convert absolute path to relative path from project directory.

        Args:
            file_path: Absolute file path

        Returns:
            Relative path if possible, otherwise absolute path
        """
        if not self.project_dir or not os.path.isabs(file_path):
            return file_path

        try:
            path_obj = Path(file_path)
            relative = os.path.relpath(path_obj, self.project_dir)

            # Don't use relative paths that go up too many levels
            if relative.count('..') > 3:
                return file_path

            return relative
        except (ValueError, OSError):
            # Can't make relative (different drives on Windows, etc.)
            return file_path

    def make_absolute(self, file_path: str) -> str:
        """
        Convert relative path to absolute path using project directory.

        Args:
            file_path: Relative or absolute file path

        Returns:
            Absolute path if conversion successful, otherwise original path
        """
        if not self.project_dir or os.path.isabs(file_path):
            return file_path

        try:
            absolute = self.project_dir / file_path
            return str(absolute.resolve())
        except (ValueError, OSError):
            return file_path

    def resolve_dataset_paths(self, dataset_refs: List[DatasetRef]) -> List[Tuple[DatasetRef, bool]]:
        """
        Resolve dataset paths and check file existence.

        Args:
            dataset_refs: List of dataset references to resolve

        Returns:
            List of tuples (dataset_ref, file_exists)
        """
        results = []

        for ref in dataset_refs:
            # Try to resolve path
            absolute_path = self.make_absolute(ref.file_path)
            file_exists = os.path.exists(absolute_path)

            # Update the reference with resolved path
            resolved_ref = DatasetRef(
                dataset_id=ref.dataset_id,
                file_path=absolute_path,
                file_name=ref.file_name,
                last_modified=ref.last_modified,
                file_size=ref.file_size,
                load_status='found' if file_exists else 'missing',
                error_message=None if file_exists else f"File not found: {absolute_path}"
            )

            results.append((resolved_ref, file_exists))

        return results


class ProjectPersistence:
    """
    Main service for project save/load operations.

    Provides high-level interface for project persistence with automatic
    path resolution, backup creation, and recovery mechanisms.
    """

    def __init__(self):
        self.current_project: Optional[Project] = None
        self.backup_count = 5  # Number of backup files to keep

    def save_project(self, project: Project, file_path: str, create_backup: bool = True) -> None:
        """
        Save project to JSON file with path conversion and backup.

        Args:
            project: Project instance to save
            file_path: Target file path for the project
            create_backup: Whether to create backup of existing file

        Raises:
            ProjectSaveError: If save operation fails
        """
        try:
            file_path_obj = Path(file_path)
            project_dir = file_path_obj.parent

            # Ensure project directory exists
            project_dir.mkdir(parents=True, exist_ok=True)

            # Create backup if requested and file exists
            if create_backup and file_path_obj.exists():
                self._create_backup(file_path_obj)

            # Create path resolver for this project
            path_resolver = PathResolver(project_dir)

            # Convert project to dictionary with relative paths
            project_data = project.to_dict()

            # Convert dataset paths to relative
            for ref_data in project_data['dataset_refs']:
                ref_data['file_path'] = path_resolver.make_relative(ref_data['file_path'])

            # Update project metadata
            project_data['project_file_path'] = str(file_path_obj)
            project_data['updated_at'] = datetime.now().isoformat()

            # Write to temporary file first
            temp_path = file_path_obj.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)

            # Atomic rename to final location
            temp_path.replace(file_path_obj)

            # Update project instance
            project.project_file_path = str(file_path_obj)
            project.updated_at = datetime.now()

            self.current_project = project

        except Exception as e:
            raise ProjectSaveError(f"Failed to save project: {e}") from e

    def load_project(self, file_path: str, relink_missing: bool = True) -> Project:
        """
        Load project from JSON file with path resolution.

        Args:
            file_path: Path to project file to load
            relink_missing: Whether to attempt relinking missing dataset files

        Returns:
            Loaded Project instance

        Raises:
            ProjectLoadError: If load operation fails
        """
        try:
            file_path_obj = Path(file_path)

            if not file_path_obj.exists():
                raise ProjectLoadError(f"Project file not found: {file_path}")

            # Load JSON data
            with open(file_path_obj, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            # Create project from data
            project = Project.from_dict(project_data)
            project.project_file_path = str(file_path_obj)

            # Resolve dataset paths
            project_dir = file_path_obj.parent
            path_resolver = PathResolver(project_dir)

            resolved_refs = path_resolver.resolve_dataset_paths(project.dataset_refs)

            # Update dataset references with resolved paths
            project.dataset_refs = []
            missing_files = []

            for resolved_ref, file_exists in resolved_refs:
                project.dataset_refs.append(resolved_ref)
                if not file_exists:
                    missing_files.append(resolved_ref)

            # Attempt to relink missing files if requested
            if relink_missing and missing_files:
                self._attempt_relink(missing_files, project_dir)

            self.current_project = project
            return project

        except json.JSONDecodeError as e:
            raise ProjectLoadError(f"Invalid project file format: {e}") from e
        except Exception as e:
            raise ProjectLoadError(f"Failed to load project: {e}") from e

    def create_new_project(self, name: str) -> Project:
        """
        Create a new empty project.

        Args:
            name: Name for the new project

        Returns:
            New Project instance
        """
        project = Project(name=name)
        self.current_project = project
        return project

    def get_current_project(self) -> Optional[Project]:
        """Get the currently loaded project."""
        return self.current_project

    def save_recovery_data(self, project: Project, recovery_dir: str) -> str:
        """
        Save recovery data for crash protection.

        Args:
            project: Project to save recovery data for
            recovery_dir: Directory to store recovery files

        Returns:
            Path to recovery file created
        """
        try:
            recovery_path = Path(recovery_dir)
            recovery_path.mkdir(parents=True, exist_ok=True)

            # Create timestamped recovery file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recovery_file = recovery_path / f"recovery_{timestamp}.json"

            # Save without backup creation
            self.save_project(project, str(recovery_file), create_backup=False)

            # Clean up old recovery files
            self._cleanup_recovery_files(recovery_path)

            return str(recovery_file)

        except Exception as e:
            # Don't raise exception for recovery save failures
            print(f"Warning: Failed to save recovery data: {e}")
            return ""

    def find_recovery_files(self, recovery_dir: str) -> List[str]:
        """
        Find available recovery files.

        Args:
            recovery_dir: Directory to search for recovery files

        Returns:
            List of recovery file paths sorted by modification time (newest first)
        """
        try:
            recovery_path = Path(recovery_dir)
            if not recovery_path.exists():
                return []

            recovery_files = list(recovery_path.glob("recovery_*.json"))

            # Sort by modification time (newest first)
            recovery_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            return [str(f) for f in recovery_files]

        except Exception:
            return []

    def get_project_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic project information without full loading.

        Args:
            file_path: Path to project file

        Returns:
            Dictionary with project metadata
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return {
                'name': data.get('name', 'Unknown'),
                'created_at': data.get('created_at'),
                'updated_at': data.get('updated_at'),
                'dataset_count': len(data.get('dataset_refs', [])),
                'chart_count': len(data.get('chart_ids', [])),
                'file_size': os.path.getsize(file_path)
            }

        except Exception:
            return {'name': 'Error', 'error': 'Failed to read project file'}

    def _create_backup(self, file_path: Path) -> None:
        """Create numbered backup of existing file."""
        backup_path = file_path.with_suffix(f'{file_path.suffix}.bak')

        # Find next backup number
        counter = 1
        while backup_path.exists() and counter < self.backup_count:
            backup_path = file_path.with_suffix(f'{file_path.suffix}.bak{counter}')
            counter += 1

        # Shift existing backups
        for i in range(self.backup_count - 1, 0, -1):
            old_backup = file_path.with_suffix(f'{file_path.suffix}.bak{i}')
            new_backup = file_path.with_suffix(f'{file_path.suffix}.bak{i+1}')

            if old_backup.exists():
                if new_backup.exists():
                    new_backup.unlink()
                old_backup.rename(new_backup)

        # Create new backup
        backup_path = file_path.with_suffix(f'{file_path.suffix}.bak')
        if backup_path.exists():
            backup_path.unlink()
        shutil.copy2(file_path, backup_path)

    def _attempt_relink(self, missing_refs: List[DatasetRef], project_dir: Path) -> None:
        """Attempt to find missing dataset files in common locations."""
        search_dirs = [
            project_dir,  # Same directory as project
            project_dir / "data",  # Data subdirectory
            project_dir / "touchstone",  # Touchstone subdirectory
            project_dir.parent,  # Parent directory
        ]

        for ref in missing_refs:
            file_found = False
            original_name = Path(ref.file_name).name

            # Search in each directory
            for search_dir in search_dirs:
                if not search_dir.exists():
                    continue

                # Look for exact filename match
                candidate = search_dir / original_name
                if candidate.exists():
                    ref.file_path = str(candidate)
                    ref.load_status = 'found'
                    ref.error_message = None
                    file_found = True
                    break

                # Look for files with same extension
                extension = Path(ref.file_name).suffix
                if extension:
                    for candidate in search_dir.glob(f"*{extension}"):
                        if candidate.name.lower() == original_name.lower():
                            ref.file_path = str(candidate)
                            ref.load_status = 'found'
                            ref.error_message = None
                            file_found = True
                            break

                    if file_found:
                        break

    def _cleanup_recovery_files(self, recovery_dir: Path, max_files: int = 10) -> None:
        """Remove old recovery files keeping only the most recent ones."""
        try:
            recovery_files = list(recovery_dir.glob("recovery_*.json"))

            if len(recovery_files) <= max_files:
                return

            # Sort by modification time (oldest first for deletion)
            recovery_files.sort(key=lambda p: p.stat().st_mtime)

            # Remove oldest files
            files_to_remove = recovery_files[:-max_files]
            for file_path in files_to_remove:
                file_path.unlink()

        except Exception:
            pass  # Ignore cleanup errors


# Global instance for application use
project_service = ProjectPersistence()
