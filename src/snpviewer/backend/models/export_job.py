"""
Export job model for chart export operations.

Represents export operations for charts and plots with various
output formats and configurations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ExportFormat(Enum):
    """
    Supported export formats.

    Defines the file formats available for exporting charts and data.
    """
    PNG = "png"
    SVG = "svg"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"
    TOUCHSTONE = "touchstone"


class ExportStatus(Enum):
    """
    Status of export operation.

    Tracks the current state of an export job.
    """
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExportDimensions:
    """
    Dimensions for image/PDF exports.

    Attributes:
        width: Width in pixels (for raster) or points (for vector)
        height: Height in pixels (for raster) or points (for vector)
        dpi: Resolution in dots per inch (for raster formats)
        scale_factor: Scaling factor for high-DPI displays
    """
    width: int
    height: int
    dpi: int = 300
    scale_factor: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert dimensions to dictionary for serialization."""
        return {
            'width': self.width,
            'height': self.height,
            'dpi': self.dpi,
            'scale_factor': self.scale_factor
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExportDimensions:
        """Create dimensions from dictionary for deserialization."""
        return cls(
            width=data['width'],
            height=data['height'],
            dpi=data.get('dpi', 300),
            scale_factor=data.get('scale_factor', 1.0)
        )


@dataclass
class ExportOptions:
    """
    Configuration options for export operations.

    Attributes:
        include_legend: Whether to include legend in exported charts
        include_markers: Whether to include markers in exported charts
        include_grid: Whether to include grid lines
        background_transparent: Whether to use transparent background
        line_width_scale: Scaling factor for line widths
        font_size_scale: Scaling factor for font sizes
        color_scheme: Color scheme override ('light', 'dark', 'print')
        compression_quality: Quality/compression level (0-100)
    """
    include_legend: bool = True
    include_markers: bool = True
    include_grid: bool = True
    background_transparent: bool = False
    line_width_scale: float = 1.0
    font_size_scale: float = 1.0
    color_scheme: Optional[str] = None
    compression_quality: int = 95

    def to_dict(self) -> Dict[str, Any]:
        """Convert options to dictionary for serialization."""
        return {
            'include_legend': self.include_legend,
            'include_markers': self.include_markers,
            'include_grid': self.include_grid,
            'background_transparent': self.background_transparent,
            'line_width_scale': self.line_width_scale,
            'font_size_scale': self.font_size_scale,
            'color_scheme': self.color_scheme,
            'compression_quality': self.compression_quality
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExportOptions:
        """Create options from dictionary for deserialization."""
        return cls(
            include_legend=data.get('include_legend', True),
            include_markers=data.get('include_markers', True),
            include_grid=data.get('include_grid', True),
            background_transparent=data.get('background_transparent', False),
            line_width_scale=data.get('line_width_scale', 1.0),
            font_size_scale=data.get('font_size_scale', 1.0),
            color_scheme=data.get('color_scheme'),
            compression_quality=data.get('compression_quality', 95)
        )


@dataclass
class ExportProgress:
    """
    Progress information for export operations.

    Attributes:
        current_step: Current step number (0-based)
        total_steps: Total number of steps
        step_description: Description of current step
        percent_complete: Percentage completion (0-100)
        estimated_remaining: Estimated time remaining in seconds
    """
    current_step: int = 0
    total_steps: int = 1
    step_description: str = "Initializing..."
    percent_complete: float = 0.0
    estimated_remaining: Optional[float] = None

    def update(self, step: int, description: str) -> None:
        """
        Update progress information.

        Args:
            step: Current step number
            description: Description of current step
        """
        self.current_step = step
        self.step_description = description
        self.percent_complete = (step / max(self.total_steps, 1)) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert progress to dictionary for serialization."""
        return {
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'step_description': self.step_description,
            'percent_complete': self.percent_complete,
            'estimated_remaining': self.estimated_remaining
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExportProgress:
        """Create progress from dictionary for deserialization."""
        return cls(
            current_step=data.get('current_step', 0),
            total_steps=data.get('total_steps', 1),
            step_description=data.get('step_description', "Initializing..."),
            percent_complete=data.get('percent_complete', 0.0),
            estimated_remaining=data.get('estimated_remaining')
        )


@dataclass
class ExportJob:
    """
    An export job for charts, data, or complete projects.

    Represents a single export operation with all necessary configuration,
    progress tracking, and result information.

    Attributes:
        id: Unique identifier for this export job
        name: Human-readable name for the export
        export_type: Type of export ('chart', 'data', 'project')
        format: Output format (PNG, SVG, PDF, CSV, etc.)
        output_path: Destination file path
        source_ids: List of source object IDs (chart IDs, trace IDs, etc.)
        dimensions: Image dimensions (for visual exports)
        options: Export configuration options
        status: Current status of the export
        progress: Progress information
        created_at: Job creation timestamp
        started_at: Job start timestamp
        completed_at: Job completion timestamp
        error_message: Error message if job failed
        result_info: Information about export results
        metadata: Additional job-specific data
    """
    id: str
    name: str
    export_type: str
    format: ExportFormat
    output_path: str
    source_ids: List[str] = field(default_factory=list)
    dimensions: Optional[ExportDimensions] = None
    options: ExportOptions = field(default_factory=ExportOptions)
    status: ExportStatus = ExportStatus.PENDING
    progress: ExportProgress = field(default_factory=ExportProgress)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_info: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """Mark export job as started."""
        self.status = ExportStatus.IN_PROGRESS
        self.started_at = datetime.now()
        self.progress.update(0, "Starting export...")

    def complete(self, file_size: Optional[int] = None) -> None:
        """
        Mark export job as completed.

        Args:
            file_size: Size of exported file in bytes
        """
        self.status = ExportStatus.COMPLETED
        self.completed_at = datetime.now()
        self.progress.update(self.progress.total_steps, "Export completed")

        if file_size is not None:
            self.result_info['file_size'] = file_size

    def fail(self, error_message: str) -> None:
        """
        Mark export job as failed.

        Args:
            error_message: Description of the error
        """
        self.status = ExportStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error_message

    def cancel(self) -> None:
        """Mark export job as cancelled."""
        self.status = ExportStatus.CANCELLED
        self.completed_at = datetime.now()

    def update_progress(self, step: int, description: str) -> None:
        """
        Update job progress.

        Args:
            step: Current step number
            description: Description of current step
        """
        self.progress.update(step, description)

    def get_duration(self) -> Optional[float]:
        """
        Get export duration in seconds.

        Returns:
            Duration in seconds, or None if not completed
        """
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def is_image_export(self) -> bool:
        """
        Check if this is an image export.

        Returns:
            True if exporting to PNG, SVG, or PDF
        """
        return self.format in [ExportFormat.PNG, ExportFormat.SVG, ExportFormat.PDF]

    def is_data_export(self) -> bool:
        """
        Check if this is a data export.

        Returns:
            True if exporting to CSV, JSON, or Touchstone
        """
        return self.format in [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.TOUCHSTONE]

    def get_file_extension(self) -> str:
        """
        Get appropriate file extension for export format.

        Returns:
            File extension including dot (e.g., '.png')
        """
        return f".{self.format.value}"

    def validate_output_path(self) -> bool:
        """
        Validate that output path is writable.

        Returns:
            True if path is valid and writable
        """
        try:
            output_path = Path(self.output_path)
            parent_dir = output_path.parent

            # Check if parent directory exists or can be created
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)

            return parent_dir.is_dir() and parent_dir.exists()
        except (OSError, PermissionError):
            return False

    def get_estimated_file_size(self) -> Optional[int]:
        """
        Get estimated output file size in bytes.

        Returns:
            Estimated file size, or None if cannot estimate
        """
        if not self.dimensions:
            return None

        if self.format == ExportFormat.PNG:
            # Rough estimate: width * height * 4 bytes per pixel * compression
            base_size = self.dimensions.width * self.dimensions.height * 4
            compression_factor = (100 - self.options.compression_quality) / 100.0
            return int(base_size * (0.1 + 0.9 * compression_factor))
        elif self.format == ExportFormat.SVG:
            # SVG size depends on complexity, rough estimate
            return self.dimensions.width * self.dimensions.height // 10
        elif self.format == ExportFormat.PDF:
            # PDF estimate based on dimensions
            return self.dimensions.width * self.dimensions.height // 5

        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert export job to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'id': self.id,
            'name': self.name,
            'export_type': self.export_type,
            'format': self.format.value,
            'output_path': self.output_path,
            'source_ids': self.source_ids,
            'dimensions': self.dimensions.to_dict() if self.dimensions else None,
            'options': self.options.to_dict(),
            'status': self.status.value,
            'progress': self.progress.to_dict(),
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'result_info': self.result_info,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExportJob:
        """
        Create export job from dictionary for deserialization.

        Args:
            data: Dictionary representation from JSON

        Returns:
            Reconstructed ExportJob instance
        """
        dimensions = None
        if data.get('dimensions'):
            dimensions = ExportDimensions.from_dict(data['dimensions'])

        return cls(
            id=data['id'],
            name=data['name'],
            export_type=data['export_type'],
            format=ExportFormat(data['format']),
            output_path=data['output_path'],
            source_ids=data.get('source_ids', []),
            dimensions=dimensions,
            options=ExportOptions.from_dict(data.get('options', {})),
            status=ExportStatus(data.get('status', 'pending')),
            progress=ExportProgress.from_dict(data.get('progress', {})),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
            started_at=(
                datetime.fromisoformat(data['started_at']) if data.get('started_at') else None
            ),
            completed_at=(
                datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None
            ),
            error_message=data.get('error_message'),
            result_info=data.get('result_info', {}),
            metadata=data.get('metadata', {})
        )
