"""
Project model dataclass.

Represents a complete SnP Viewer project containing datasets, charts, traces,
markers, and user preferences.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from snpviewer.backend.models.chart import Chart


@dataclass
class DatasetRef:
    """
    Reference to a dataset file with path resolution metadata.

    Attributes:
        dataset_id: Unique identifier for the dataset
        file_path: Path to the Touchstone file (relative preferred, absolute fallback)
        file_name: Display name of the file
        last_modified: Last modification time for change detection
        file_size: File size for integrity checks
        load_status: Current loading status ('loaded', 'missing', 'error')
        error_message: Error details if load_status is 'error'
    """
    dataset_id: str
    file_path: str
    file_name: str
    last_modified: Optional[datetime] = None
    file_size: Optional[int] = None
    load_status: str = 'unknown'
    error_message: Optional[str] = None


@dataclass
class Preferences:
    """
    User preferences and application settings.

    Attributes:
        units: Frequency units preference ('Hz', 'kHz', 'MHz', 'GHz')
        theme: UI theme ('light', 'dark', 'auto')
        default_chart_type: Default chart type for new charts
        auto_save_interval: Auto-save interval in seconds (0 to disable)
        default_port_impedance: Default reference impedance in ohms
        marker_snap_enabled: Whether markers snap to data points by default
        grid_enabled: Whether to show grid on charts by default
        legend_position: Default legend position ('top', 'bottom', 'left', 'right')
    """
    units: str = 'Hz'
    theme: str = 'light'
    default_chart_type: str = 'Magnitude'
    auto_save_interval: int = 300  # 5 minutes
    default_port_impedance: float = 50.0
    marker_snap_enabled: bool = True
    grid_enabled: bool = True
    legend_position: str = 'right'

    def to_dict(self) -> Dict[str, Any]:
        """Convert preferences to dictionary for serialization."""
        return {
            'units': self.units,
            'theme': self.theme,
            'default_chart_type': self.default_chart_type,
            'auto_save_interval': self.auto_save_interval,
            'default_port_impedance': self.default_port_impedance,
            'marker_snap_enabled': self.marker_snap_enabled,
            'grid_enabled': self.grid_enabled,
            'legend_position': self.legend_position
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Preferences:
        """Create preferences from dictionary for deserialization."""
        return cls(
            units=data.get('units', 'Hz'),
            theme=data.get('theme', 'light'),
            default_chart_type=data.get('default_chart_type', 'Magnitude'),
            auto_save_interval=data.get('auto_save_interval', 300),
            default_port_impedance=data.get('default_port_impedance', 50.0),
            marker_snap_enabled=data.get('marker_snap_enabled', True),
            grid_enabled=data.get('grid_enabled', True),
            legend_position=data.get('legend_position', 'right')
        )


@dataclass
class Project:
    """
    Complete SnP Viewer project.

    A project encapsulates all user work including datasets, charts, traces,
    markers, and preferences. Projects can be saved and loaded to preserve
    the complete analysis state.

    Attributes:
        name: Human-readable project name
        created_at: Project creation timestamp
        updated_at: Last modification timestamp
        dataset_refs: References to all datasets in the project
        charts: List of complete Chart objects in this project
        preferences: User preferences and settings
        project_file_path: Path to the saved project file (if any)
        auto_save_enabled: Whether auto-save is currently active
        recovery_data_path: Path to crash recovery data (if any)
    """
    name: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    dataset_refs: List[DatasetRef] = field(default_factory=list)
    charts: List['Chart'] = field(default_factory=list)
    preferences: Preferences = field(default_factory=Preferences)
    project_file_path: Optional[str] = None
    auto_save_enabled: bool = False
    recovery_data_path: Optional[str] = None

    def add_dataset_ref(self, dataset_ref: DatasetRef) -> None:
        """
        Add a dataset reference to the project.

        Args:
            dataset_ref: The dataset reference to add
        """
        self.dataset_refs.append(dataset_ref)
        self.updated_at = datetime.now()

    def remove_dataset_ref(self, dataset_id: str) -> bool:
        """
        Remove a dataset reference from the project.

        Args:
            dataset_id: ID of the dataset to remove

        Returns:
            True if dataset was found and removed, False otherwise
        """
        original_length = len(self.dataset_refs)
        self.dataset_refs = [ref for ref in self.dataset_refs
                             if ref.dataset_id != dataset_id]

        if len(self.dataset_refs) < original_length:
            self.updated_at = datetime.now()
            return True
        return False

    def add_chart(self, chart: 'Chart') -> None:
        """
        Add a chart to the project.

        Args:
            chart: The Chart object to add
        """
        # Check if chart already exists (by ID)
        if not any(c.id == chart.id for c in self.charts):
            self.charts.append(chart)
            self.updated_at = datetime.now()

    def remove_chart(self, chart_id: str) -> bool:
        """
        Remove a chart from the project.

        Args:
            chart_id: ID of the chart to remove

        Returns:
            True if chart was found and removed, False otherwise
        """
        for i, chart in enumerate(self.charts):
            if chart.id == chart_id:
                del self.charts[i]
                self.updated_at = datetime.now()
                return True
        return False

    def get_chart(self, chart_id: str) -> Optional['Chart']:
        """
        Get a chart by ID.

        Args:
            chart_id: The chart ID to search for

        Returns:
            The Chart object if found, None otherwise
        """
        for chart in self.charts:
            if chart.id == chart_id:
                return chart
        return None

    # Legacy methods for backward compatibility
    def add_chart_id(self, chart_id: str) -> None:
        """Legacy method - use add_chart() instead."""
        pass  # No-op for backward compatibility

    def remove_chart_id(self, chart_id: str) -> bool:
        """Legacy method - use remove_chart() instead."""
        return self.remove_chart(chart_id)

    def get_dataset_ref(self, dataset_id: str) -> Optional[DatasetRef]:
        """
        Get a dataset reference by ID.

        Args:
            dataset_id: The dataset ID to search for

        Returns:
            The dataset reference if found, None otherwise
        """
        for ref in self.dataset_refs:
            if ref.dataset_id == dataset_id:
                return ref
        return None

    def update_preference(self, key: str, value: Any) -> None:
        """
        Update a single preference value.

        Args:
            key: The preference key to update
            value: The new value for the preference
        """
        if hasattr(self.preferences, key):
            setattr(self.preferences, key, value)
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert project to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'dataset_refs': [
                {
                    'dataset_id': ref.dataset_id,
                    'file_path': ref.file_path,
                    'file_name': ref.file_name,
                    'last_modified': ref.last_modified.isoformat() if ref.last_modified else None,
                    'file_size': ref.file_size,
                    'load_status': ref.load_status,
                    'error_message': ref.error_message
                }
                for ref in self.dataset_refs
            ],
            'charts': [chart.to_dict() for chart in self.charts],
            'preferences': self.preferences.to_dict(),
            'project_file_path': self.project_file_path,
            'auto_save_enabled': self.auto_save_enabled,
            'recovery_data_path': self.recovery_data_path
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Project:
        """
        Create project from dictionary for deserialization.

        Args:
            data: Dictionary representation from JSON

        Returns:
            Reconstructed Project instance
        """
        dataset_refs = []
        for ref_data in data.get('dataset_refs', []):
            last_modified = None
            if ref_data.get('last_modified'):
                last_modified = datetime.fromisoformat(ref_data['last_modified'])

            dataset_refs.append(DatasetRef(
                dataset_id=ref_data['dataset_id'],
                file_path=ref_data['file_path'],
                file_name=ref_data['file_name'],
                last_modified=last_modified,
                file_size=ref_data.get('file_size'),
                load_status=ref_data.get('load_status', 'unknown'),
                error_message=ref_data.get('error_message')
            ))

        return cls(
            name=data['name'],
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.now().isoformat())),
            dataset_refs=dataset_refs,
            charts=cls._load_charts_from_data(data),
            preferences=Preferences.from_dict(data.get('preferences', {})),
            project_file_path=data.get('project_file_path'),
            auto_save_enabled=data.get('auto_save_enabled', False),
            recovery_data_path=data.get('recovery_data_path')
        )

    @classmethod
    def _load_charts_from_data(cls, data: Dict[str, Any]) -> List['Chart']:
        """
        Load charts from serialized data with backward compatibility.

        Args:
            data: Dictionary representation from JSON

        Returns:
            List of Chart objects
        """
        charts = []

        # Try to load new format (Chart objects)
        if 'charts' in data:
            for chart_data in data['charts']:
                try:
                    chart = Chart.from_dict(chart_data)
                    charts.append(chart)
                except Exception as e:
                    print(f"Warning: Could not load chart {chart_data.get('id', 'unknown')}: {e}")

        # Backward compatibility: handle old format (chart_ids only)
        elif 'chart_ids' in data:
            print(f"Warning: Project uses legacy chart format. {len(data['chart_ids'])} chart(s) cannot be restored.")
            # Legacy chart IDs are not restored as full charts since we lack the data

        return charts
