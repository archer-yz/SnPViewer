"""
Preferences dialog for application-wide settings.

Provides a comprehensive dialog for configuring default chart styling,
including font properties and plot area settings. Follows the same pattern
as chart_view dialogs for consistency.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QDoubleSpinBox, QFontDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)


class PreferencesDialog(QDialog):
    """
    Dialog for configuring application preferences.

    Includes tabs for:
    - General settings (units, theme, auto-save)
    - Default Chart Styling (fonts, colors)
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
        self.resize(600, 500)

        self._setup_ui()
        self._load_preferences()

    def _setup_ui(self) -> None:
        """Setup the dialog UI with tabs."""
        layout = QVBoxLayout(self)

        # Create tab widget
        self._tab_widget = QTabWidget()

        # Add tabs
        self._tab_widget.addTab(self._create_general_tab(), "General")
        self._tab_widget.addTab(self._create_chart_fonts_tab(), "Chart Fonts")
        self._tab_widget.addTab(self._create_plot_area_tab(), "Plot Area")

        layout.addWidget(self._tab_widget)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.RestoreDefaults
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._restore_defaults
        )
        layout.addWidget(button_box)

    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

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
        layout.addRow("Default Port Impedance:", self._impedance_spin)

        # Marker snap
        self._marker_snap_check = QCheckBox("Enable marker snapping to data points")
        layout.addRow("Marker Behavior:", self._marker_snap_check)

        # Grid enabled
        self._grid_check = QCheckBox("Show grid on new charts")
        layout.addRow("Grid:", self._grid_check)

        # Legend position
        self._legend_pos_combo = QComboBox()
        self._legend_pos_combo.addItems(['top', 'bottom', 'left', 'right'])
        layout.addRow("Default Legend Position:", self._legend_pos_combo)

        return widget

    def _create_chart_fonts_tab(self) -> QWidget:
        """Create the chart fonts configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Title font group
        title_group = QGroupBox("Title Font")
        title_layout = QHBoxLayout(title_group)

        self._title_font_label = QLabel("Arial, 12pt")
        title_layout.addWidget(self._title_font_label)
        title_layout.addStretch()

        self._title_font_btn = QPushButton("Choose Font...")
        self._title_font_btn.clicked.connect(lambda: self._choose_font('title'))
        title_layout.addWidget(self._title_font_btn)

        self._title_color_btn = QPushButton("Color...")
        self._title_color_btn.clicked.connect(lambda: self._choose_color('title'))
        title_layout.addWidget(self._title_color_btn)

        layout.addWidget(title_group)

        # Axis labels font group
        axis_group = QGroupBox("Axis Labels Font")
        axis_layout = QHBoxLayout(axis_group)

        self._axis_font_label = QLabel("Arial, 10pt")
        axis_layout.addWidget(self._axis_font_label)
        axis_layout.addStretch()

        self._axis_font_btn = QPushButton("Choose Font...")
        self._axis_font_btn.clicked.connect(lambda: self._choose_font('axis_labels'))
        axis_layout.addWidget(self._axis_font_btn)

        self._axis_color_btn = QPushButton("Color...")
        self._axis_color_btn.clicked.connect(lambda: self._choose_color('axis_labels'))
        axis_layout.addWidget(self._axis_color_btn)

        layout.addWidget(axis_group)

        # X-axis ticks font group
        x_ticks_group = QGroupBox("X-Axis Ticks Font")
        x_ticks_layout = QHBoxLayout(x_ticks_group)

        self._x_ticks_font_label = QLabel("Arial, 9pt")
        x_ticks_layout.addWidget(self._x_ticks_font_label)
        x_ticks_layout.addStretch()

        self._x_ticks_font_btn = QPushButton("Choose Font...")
        self._x_ticks_font_btn.clicked.connect(lambda: self._choose_font('x_ticks'))
        x_ticks_layout.addWidget(self._x_ticks_font_btn)

        self._x_ticks_color_btn = QPushButton("Color...")
        self._x_ticks_color_btn.clicked.connect(lambda: self._choose_color('x_ticks'))
        x_ticks_layout.addWidget(self._x_ticks_color_btn)

        layout.addWidget(x_ticks_group)

        # Y-axis ticks font group
        y_ticks_group = QGroupBox("Y-Axis Ticks Font")
        y_ticks_layout = QHBoxLayout(y_ticks_group)

        self._y_ticks_font_label = QLabel("Arial, 9pt")
        y_ticks_layout.addWidget(self._y_ticks_font_label)
        y_ticks_layout.addStretch()

        self._y_ticks_font_btn = QPushButton("Choose Font...")
        self._y_ticks_font_btn.clicked.connect(lambda: self._choose_font('y_ticks'))
        y_ticks_layout.addWidget(self._y_ticks_font_btn)

        self._y_ticks_color_btn = QPushButton("Color...")
        self._y_ticks_color_btn.clicked.connect(lambda: self._choose_color('y_ticks'))
        y_ticks_layout.addWidget(self._y_ticks_color_btn)

        layout.addWidget(y_ticks_group)

        # Legend font group
        legend_group = QGroupBox("Legend Font")
        legend_layout = QHBoxLayout(legend_group)

        self._legend_font_label = QLabel("Arial, 9pt")
        legend_layout.addWidget(self._legend_font_label)
        legend_layout.addStretch()

        self._legend_font_btn = QPushButton("Choose Font...")
        self._legend_font_btn.clicked.connect(lambda: self._choose_font('legend'))
        legend_layout.addWidget(self._legend_font_btn)

        self._legend_color_btn = QPushButton("Color...")
        self._legend_color_btn.clicked.connect(lambda: self._choose_color('legend'))
        legend_layout.addWidget(self._legend_color_btn)

        layout.addWidget(legend_group)

        layout.addStretch()

        return widget

    def _create_plot_area_tab(self) -> QWidget:
        """Create the plot area properties tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Background group
        bg_group = QGroupBox("Background")
        bg_layout = QFormLayout(bg_group)

        bg_color_layout = QHBoxLayout()
        self._bg_color_label = QLabel("#FFFFFF")
        bg_color_layout.addWidget(self._bg_color_label)
        self._bg_color_btn = QPushButton("Choose Color...")
        self._bg_color_btn.clicked.connect(lambda: self._choose_plot_color('background'))
        bg_color_layout.addWidget(self._bg_color_btn)
        bg_layout.addRow("Background Color:", bg_color_layout)

        layout.addWidget(bg_group)

        # Border group
        border_group = QGroupBox("Border")
        border_layout = QFormLayout(border_group)

        self._border_enabled_check = QCheckBox("Show border")
        border_layout.addRow("Border:", self._border_enabled_check)

        border_color_layout = QHBoxLayout()
        self._border_color_label = QLabel("#000000")
        border_color_layout.addWidget(self._border_color_label)
        self._border_color_btn = QPushButton("Choose Color...")
        self._border_color_btn.clicked.connect(lambda: self._choose_plot_color('border_color'))
        border_color_layout.addWidget(self._border_color_btn)
        border_layout.addRow("Border Color:", border_color_layout)

        self._border_width_spin = QSpinBox()
        self._border_width_spin.setRange(1, 10)
        self._border_width_spin.setSuffix(" px")
        border_layout.addRow("Border Width:", self._border_width_spin)

        layout.addWidget(border_group)

        # Grid group
        grid_group = QGroupBox("Grid")
        grid_layout = QFormLayout(grid_group)

        self._grid_enabled_check = QCheckBox("Show grid")
        grid_layout.addRow("Grid:", self._grid_enabled_check)

        grid_color_layout = QHBoxLayout()
        self._grid_color_label = QLabel("#CCCCCC")
        grid_color_layout.addWidget(self._grid_color_label)
        self._grid_color_btn = QPushButton("Choose Color...")
        self._grid_color_btn.clicked.connect(lambda: self._choose_plot_color('grid_color'))
        grid_color_layout.addWidget(self._grid_color_btn)
        grid_layout.addRow("Grid Color:", grid_color_layout)

        self._grid_alpha_spin = QSpinBox()
        self._grid_alpha_spin.setRange(0, 255)
        self._grid_alpha_spin.setSuffix(" (0-255)")
        grid_layout.addRow("Grid Alpha:", self._grid_alpha_spin)

        layout.addWidget(grid_group)

        layout.addStretch()

        return widget

    def _choose_font(self, element: str) -> None:
        """
        Open font dialog for a specific element.

        Args:
            element: Font element key ('title', 'axis_labels', 'x_ticks', 'y_ticks', 'legend')
        """
        # Get current font
        if 'default_chart_fonts' not in self._preferences:
            self._preferences['default_chart_fonts'] = {}

        current_font_data = self._preferences['default_chart_fonts'].get(element, {})
        current_font = QFont(
            current_font_data.get('family', 'Arial'),
            current_font_data.get('pointSize', 10)
        )
        if current_font_data.get('bold', False):
            current_font.setBold(True)
        if current_font_data.get('italic', False):
            current_font.setItalic(True)

        # Show font dialog
        result = QFontDialog.getFont(current_font, self, f"Choose {element.replace('_', ' ').title()} Font")

        # getFont returns (QFont, bool) tuple - but check which is which
        if isinstance(result, tuple) and len(result) == 2:
            # Check which element is the bool (ok status)
            if isinstance(result[0], bool):
                ok, selected_font = result  # Order is (ok, font)
            else:
                selected_font, ok = result  # Order is (font, ok)
        else:
            # Fallback in case of unexpected return
            return

        if ok and isinstance(selected_font, QFont):
            # Store font data
            self._preferences['default_chart_fonts'][element] = {
                'family': selected_font.family(),
                'pointSize': selected_font.pointSize(),
                'weight': selected_font.weight(),
                'bold': selected_font.bold(),
                'italic': selected_font.italic()
            }

            # Update label
            self._update_font_label(element, selected_font)

    def _choose_color(self, element: str) -> None:
        """
        Open color dialog for a font element.

        Args:
            element: Color element key
        """
        if 'default_chart_colors' not in self._preferences:
            self._preferences['default_chart_colors'] = {}

        current_color_str = self._preferences['default_chart_colors'].get(element, '#000000')
        current_color = QColor(current_color_str)

        color = QColorDialog.getColor(current_color, self, f"Choose {element.replace('_', ' ').title()} Color")

        if color.isValid():
            self._preferences['default_chart_colors'][element] = color.name()
            self._update_color_button(element, color.name())

    def _choose_plot_color(self, element: str) -> None:
        """
        Open color dialog for a plot area element.

        Args:
            element: Plot area color key
        """
        if 'default_plot_area_settings' not in self._preferences:
            self._preferences['default_plot_area_settings'] = {}

        current_color_str = self._preferences['default_plot_area_settings'].get(element, '#FFFFFF')
        current_color = QColor(current_color_str)

        color = QColorDialog.getColor(current_color, self, f"Choose {element.replace('_', ' ').title()}")

        if color.isValid():
            self._preferences['default_plot_area_settings'][element] = color.name()

            # Update label
            if element == 'background':
                self._bg_color_label.setText(color.name())
            elif element == 'border_color':
                self._border_color_label.setText(color.name())
            elif element == 'grid_color':
                self._grid_color_label.setText(color.name())

    def _update_font_label(self, element: str, font: QFont) -> None:
        """Update font label with current font info."""
        label_text = f"{font.family()}, {font.pointSize()}pt"
        if font.bold():
            label_text += ", Bold"
        if font.italic():
            label_text += ", Italic"

        if element == 'title':
            self._title_font_label.setText(label_text)
        elif element == 'axis_labels':
            self._axis_font_label.setText(label_text)
        elif element == 'x_ticks':
            self._x_ticks_font_label.setText(label_text)
        elif element == 'y_ticks':
            self._y_ticks_font_label.setText(label_text)
        elif element == 'legend':
            self._legend_font_label.setText(label_text)

    def _update_color_button(self, element: str, color: str) -> None:
        """Update color button style to show current color."""
        # You could set button background color here if desired
        pass

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

        # Chart fonts tab
        default_fonts = self._preferences.get('default_chart_fonts', {})
        for element in ['title', 'axis_labels', 'x_ticks', 'y_ticks', 'legend']:
            font_data = default_fonts.get(element, {})
            if font_data:
                font = QFont(
                    font_data.get('family', 'Arial'),
                    font_data.get('pointSize', 10)
                )
                if font_data.get('bold', False):
                    font.setBold(True)
                if font_data.get('italic', False):
                    font.setItalic(True)
                self._update_font_label(element, font)

        # Plot area tab
        plot_settings = self._preferences.get('default_plot_area_settings', {})
        self._bg_color_label.setText(plot_settings.get('background', '#FFFFFF'))
        self._border_enabled_check.setChecked(plot_settings.get('border_enabled', True))
        self._border_color_label.setText(plot_settings.get('border_color', '#000000'))
        self._border_width_spin.setValue(plot_settings.get('border_width', 1))
        self._grid_enabled_check.setChecked(plot_settings.get('grid_enabled', True))
        self._grid_color_label.setText(plot_settings.get('grid_color', '#CCCCCC'))
        self._grid_alpha_spin.setValue(plot_settings.get('grid_alpha', 128))

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

        # Reset font preferences
        self._preferences['default_chart_fonts'] = {}
        self._preferences['default_chart_colors'] = {}
        self._preferences['default_plot_area_settings'] = {}

        # Update labels to defaults
        self._title_font_label.setText("Arial, 12pt")
        self._axis_font_label.setText("Arial, 10pt")
        self._x_ticks_font_label.setText("Arial, 9pt")
        self._y_ticks_font_label.setText("Arial, 9pt")
        self._legend_font_label.setText("Arial, 9pt")

        # Plot area defaults
        self._bg_color_label.setText("#FFFFFF")
        self._border_enabled_check.setChecked(True)
        self._border_color_label.setText("#000000")
        self._border_width_spin.setValue(1)
        self._grid_enabled_check.setChecked(True)
        self._grid_color_label.setText("#CCCCCC")
        self._grid_alpha_spin.setValue(128)

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

        # Update plot area settings from UI
        if 'default_plot_area_settings' not in self._preferences:
            self._preferences['default_plot_area_settings'] = {}

        self._preferences['default_plot_area_settings']['background'] = self._bg_color_label.text()
        self._preferences['default_plot_area_settings']['border_enabled'] = self._border_enabled_check.isChecked()
        self._preferences['default_plot_area_settings']['border_color'] = self._border_color_label.text()
        self._preferences['default_plot_area_settings']['border_width'] = self._border_width_spin.value()
        self._preferences['default_plot_area_settings']['grid_enabled'] = self._grid_enabled_check.isChecked()
        self._preferences['default_plot_area_settings']['grid_color'] = self._grid_color_label.text()
        self._preferences['default_plot_area_settings']['grid_alpha'] = self._grid_alpha_spin.value()

        return self._preferences
