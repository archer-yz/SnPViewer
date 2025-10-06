"""
Preferences dialog for application-wide settings.

Provides a comprehensive dialog for configuring default chart styling,
including font properties and plot area settings. Uses common dialog widgets
for consistency with ChartView.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QPushButton, QSpinBox,
                               QTabWidget, QVBoxLayout, QWidget)

from snpviewer.frontend.dialogs.common_dialogs import (
    FontStylingWidget, PlotAreaPropertiesWidget)


class PreferencesDialog(QDialog):
    """
    Dialog for configuring application preferences.

    Includes tabs for:
    - General settings (units, theme, auto-save)
    - Default Chart Fonts (fonts, colors - following chart_view pattern)
    - Default Plot Area Properties (background, borders, grid)
    """

    def __init__(self, preferences: Dict[str, Any], parent: Optional[QWidget] = None):
        """
        Initialize preferences dialog.

        Args:
            preferences: Current preferences dictionary
            parent: Parent widget
        """
        super().__init__(parent)

        self._preferences = preferences.copy()

        self.setWindowTitle("Preferences")
        self.setModal(True)
        self.resize(600, 550)

        self._setup_ui()
        self._load_preferences()

    def _setup_ui(self) -> None:
        """Setup the dialog UI with tabs."""
        layout = QVBoxLayout(self)

        # Create tab widget
        self._tab_widget = QTabWidget()

        # Add General tab
        self._tab_widget.addTab(self._create_general_tab(), "General")

        # Add Font Styling widget as a tab
        self._font_widget = FontStylingWidget(parent=self)
        self._tab_widget.addTab(self._font_widget, "Chart Fonts")

        # Add Plot Area widget as a tab
        self._plot_widget = PlotAreaPropertiesWidget(parent=self)
        self._tab_widget.addTab(self._plot_widget, "Plot Area")

        layout.addWidget(self._tab_widget)

        # Dialog buttons
        button_layout = QHBoxLayout()
        self._reset_button = QPushButton("Reset to Defaults")
        self._reset_button.setToolTip("Reset all settings to application defaults")
        self._ok_button = QPushButton("OK")
        self._ok_button.setToolTip("Save all changes and close")
        self._cancel_button = QPushButton("Cancel")

        button_layout.addWidget(self._reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self._ok_button)
        button_layout.addWidget(self._cancel_button)
        layout.addLayout(button_layout)

        # Connect buttons
        self._reset_button.clicked.connect(self._restore_defaults)
        self._ok_button.clicked.connect(self.accept)
        self._cancel_button.clicked.connect(self.reject)

    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(10)

        # Units
        self._units_combo = QComboBox()
        self._units_combo.addItems(['Hz', 'kHz', 'MHz', 'GHz'])
        layout.addRow("Frequency Units:", self._units_combo)

        # Theme
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(['light', 'dark', 'auto'])
        layout.addRow("Theme:", self._theme_combo)

        # Default chart type
        self._chart_type_combo = QComboBox()
        self._chart_type_combo.addItems(['Magnitude', 'Phase', 'GroupDelay', 'Smith'])
        layout.addRow("Default Chart Type:", self._chart_type_combo)

        # Auto-save interval
        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(0, 3600)
        self._autosave_spin.setSuffix(" seconds")
        self._autosave_spin.setSpecialValueText("Disabled")
        layout.addRow("Auto-save Interval:", self._autosave_spin)

        # Default port impedance
        self._impedance_spin = QDoubleSpinBox()
        self._impedance_spin.setRange(1.0, 1000.0)
        self._impedance_spin.setSuffix(" Ω")
        self._impedance_spin.setValue(50.0)
        layout.addRow("Default Port Impedance:", self._impedance_spin)

        # Marker snap
        self._marker_snap_check = QCheckBox("Enable marker snapping to data points")
        self._marker_snap_check.setChecked(True)
        layout.addRow("Marker Behavior:", self._marker_snap_check)

        # Grid enabled
        self._grid_check = QCheckBox("Show grid on new charts")
        self._grid_check.setChecked(True)
        layout.addRow("Grid:", self._grid_check)

        # Legend position
        self._legend_pos_combo = QComboBox()
        self._legend_pos_combo.addItems(['top', 'bottom', 'left', 'right'])
        self._legend_pos_combo.setCurrentText('right')
        layout.addRow("Default Legend Position:", self._legend_pos_combo)

        return widget

    def _load_preferences(self) -> None:
        """Load current preferences into UI controls."""
        # General tab
        self._units_combo.setCurrentText(self._preferences.get('units', 'Hz'))
        self._theme_combo.setCurrentText(self._preferences.get('theme', 'light'))
        self._chart_type_combo.setCurrentText(self._preferences.get('default_chart_type', 'Magnitude'))
        self._autosave_spin.setValue(self._preferences.get('auto_save_interval', 300))
        self._impedance_spin.setValue(self._preferences.get('default_port_impedance', 50.0))
        self._marker_snap_check.setChecked(self._preferences.get('marker_snap_enabled', True))
        self._grid_check.setChecked(self._preferences.get('grid_enabled', True))
        self._legend_pos_combo.setCurrentText(self._preferences.get('legend_position', 'right'))

        # Load fonts into widget
        default_fonts = self._preferences.get('default_chart_fonts', {})
        if default_fonts:
            fonts = {}
            for element in ['title', 'x_axis', 'y_axis', 'x_ticks', 'y_ticks', 'legend']:
                font_data = default_fonts.get(element, {})
                if font_data and 'family' in font_data:
                    family = font_data.get('family', 'Arial')
                    point_size = font_data.get('pointSize', 10)

                    # Create font with family and size
                    font = QFont(family, point_size)

                    # Set italic first
                    if font_data.get('italic', False):
                        font.setItalic(True)

                    # Handle weight - use the saved weight value directly
                    # Don't use both setWeight and setBold as they conflict
                    if 'weight' in font_data:
                        weight = font_data['weight']
                        font.setWeight(QFont.Weight(weight))
                    elif font_data.get('bold', False):
                        # If no weight but bold is True, set bold weight
                        font.setWeight(QFont.Weight.Bold)

                    fonts[element] = font
            self._font_widget.set_fonts(fonts)

        # Load colors into widget
        default_colors = self._preferences.get('default_chart_colors', {})
        if default_colors:
            self._font_widget.set_colors(default_colors)

        # Load plot settings into widget
        plot_settings = self._preferences.get('default_plot_area_settings', {})
        if plot_settings:
            self._plot_widget.set_settings(plot_settings)

    def _restore_defaults(self) -> None:
        """Restore all settings to defaults."""
        # General defaults
        self._units_combo.setCurrentText('Hz')
        self._theme_combo.setCurrentText('light')
        self._chart_type_combo.setCurrentText('Magnitude')
        self._autosave_spin.setValue(300)
        self._impedance_spin.setValue(50.0)
        self._marker_snap_check.setChecked(True)
        self._grid_check.setChecked(True)
        self._legend_pos_combo.setCurrentText('right')

        # Reset widgets to defaults
        self._font_widget.reset_to_defaults()
        self._plot_widget.reset_to_defaults()

    def get_preferences(self) -> Dict[str, Any]:
        """
        Get the updated preferences.

        Returns:
            Dictionary of preferences
        """
        # Update preferences from UI controls
        self._preferences['units'] = self._units_combo.currentText()
        self._preferences['theme'] = self._theme_combo.currentText()
        self._preferences['default_chart_type'] = self._chart_type_combo.currentText()
        self._preferences['auto_save_interval'] = self._autosave_spin.value()
        self._preferences['default_port_impedance'] = self._impedance_spin.value()
        self._preferences['marker_snap_enabled'] = self._marker_snap_check.isChecked()
        self._preferences['grid_enabled'] = self._grid_check.isChecked()
        self._preferences['legend_position'] = self._legend_pos_combo.currentText()

        # Get fonts from widget and convert to serializable dict
        fonts = self._font_widget.get_fonts()
        self._preferences['default_chart_fonts'] = {
            key: {
                'family': font.family(),
                'pointSize': font.pointSize(),
                'weight': font.weight(),
                'bold': font.bold(),
                'italic': font.italic()
            }
            for key, font in fonts.items()
        }

        # Get colors from widget
        self._preferences['default_chart_colors'] = self._font_widget.get_colors()

        # Get plot settings from widget
        self._preferences['default_plot_area_settings'] = self._plot_widget.get_settings()

        return self._preferences
