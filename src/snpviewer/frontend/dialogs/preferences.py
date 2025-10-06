"""
Preferences dialog for application-wide settings.

Provides a comprehensive dialog for configuring default chart styling,
including font properties and plot area settings. Follows the same pattern
as chart_view dialogs for consistency.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDoubleSpinBox, QFontDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)


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

        # Current font and color settings (matching chart_view structure)
        self._current_fonts = {
            'title': QFont("Arial", 12, QFont.Weight.Bold),
            'x_axis': QFont("Arial", 10),
            'y_axis': QFont("Arial", 10),
            'x_ticks': QFont("Arial", 9),
            'y_ticks': QFont("Arial", 9),
            'legend': QFont("Arial", 9)
        }

        self._current_colors = {
            'title': '#000000',
            'x_axis': '#000000',
            'y_axis': '#000000',
            'x_ticks': '#000000',
            'y_ticks': '#000000',
            'legend': '#000000'
        }

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

        # Add tabs
        self._tab_widget.addTab(self._create_general_tab(), "General")
        self._tab_widget.addTab(self._create_chart_fonts_tab(), "Chart Fonts")
        self._tab_widget.addTab(self._create_plot_area_tab(), "Plot Area")

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

    def _create_chart_fonts_tab(self) -> QWidget:
        """Create the chart fonts configuration tab (following chart_view pattern exactly)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Create tab widget for different chart elements
        tab_widget = QTabWidget()

        # Chart Title Tab
        title_tab = QWidget()
        title_layout = QVBoxLayout(title_tab)

        title_group = QGroupBox("Chart Title Font")
        title_group_layout = QVBoxLayout(title_group)

        # Title font selection
        title_font_layout = QHBoxLayout()
        self._title_font_btn = QPushButton("Choose Font...")
        self._title_font_btn.setFixedHeight(35)
        self._title_color_btn = QPushButton()
        self._title_color_btn.setFixedSize(50, 35)
        self._title_color_btn.setStyleSheet("background-color: black; border: 1px solid gray;")

        title_font_layout.addWidget(QLabel("Font:"))
        title_font_layout.addWidget(self._title_font_btn)
        title_font_layout.addWidget(QLabel("Color:"))
        title_font_layout.addWidget(self._title_color_btn)
        title_font_layout.addStretch()
        title_group_layout.addLayout(title_font_layout)

        title_layout.addWidget(title_group)
        title_layout.addStretch()
        tab_widget.addTab(title_tab, "Chart Title")

        # X & Y Axes Tab (combined labels and ticks)
        axes_tab = QWidget()
        axes_layout = QVBoxLayout(axes_tab)

        # X-axis group (label font + tick font & color)
        x_axis_group = QGroupBox("X-Axis (Label + Ticks)")
        x_axis_group_layout = QVBoxLayout(x_axis_group)

        # X-axis label font (no color - controlled by tick color)
        x_label_layout = QHBoxLayout()
        self._x_axis_font_btn = QPushButton("Choose Label Font...")
        self._x_axis_font_btn.setFixedHeight(35)
        x_label_layout.addWidget(QLabel("Label Font:"))
        x_label_layout.addWidget(self._x_axis_font_btn)
        x_label_layout.addStretch()
        x_axis_group_layout.addLayout(x_label_layout)

        # X-axis tick font and color (controls both ticks and label color)
        x_tick_layout = QHBoxLayout()
        self._x_ticks_font_btn = QPushButton("Choose Tick Font...")
        self._x_ticks_font_btn.setFixedHeight(35)
        self._x_ticks_color_btn = QPushButton()
        self._x_ticks_color_btn.setFixedSize(50, 35)
        self._x_ticks_color_btn.setStyleSheet("background-color: black; border: 1px solid gray;")
        self._x_ticks_color_btn.setToolTip("Controls color of both tick numbers and axis label")

        x_tick_layout.addWidget(QLabel("Tick Font & Color:"))
        x_tick_layout.addWidget(self._x_ticks_font_btn)
        x_tick_layout.addWidget(QLabel("Color:"))
        x_tick_layout.addWidget(self._x_ticks_color_btn)
        x_tick_layout.addStretch()
        x_axis_group_layout.addLayout(x_tick_layout)

        # Y-axis group (label font + tick font & color)
        y_axis_group = QGroupBox("Y-Axis (Label + Ticks)")
        y_axis_group_layout = QVBoxLayout(y_axis_group)

        # Y-axis label font (no color - controlled by tick color)
        y_label_layout = QHBoxLayout()
        self._y_axis_font_btn = QPushButton("Choose Label Font...")
        self._y_axis_font_btn.setFixedHeight(35)
        y_label_layout.addWidget(QLabel("Label Font:"))
        y_label_layout.addWidget(self._y_axis_font_btn)
        y_label_layout.addStretch()
        y_axis_group_layout.addLayout(y_label_layout)

        # Y-axis tick font and color (controls both ticks and label color)
        y_tick_layout = QHBoxLayout()
        self._y_ticks_font_btn = QPushButton("Choose Tick Font...")
        self._y_ticks_font_btn.setFixedHeight(35)
        self._y_ticks_color_btn = QPushButton()
        self._y_ticks_color_btn.setFixedSize(50, 35)
        self._y_ticks_color_btn.setStyleSheet("background-color: black; border: 1px solid gray;")
        self._y_ticks_color_btn.setToolTip("Controls color of both tick numbers and axis label")

        y_tick_layout.addWidget(QLabel("Tick Font & Color:"))
        y_tick_layout.addWidget(self._y_ticks_font_btn)
        y_tick_layout.addWidget(QLabel("Color:"))
        y_tick_layout.addWidget(self._y_ticks_color_btn)
        y_tick_layout.addStretch()
        y_axis_group_layout.addLayout(y_tick_layout)

        axes_layout.addWidget(x_axis_group)
        axes_layout.addWidget(y_axis_group)
        axes_layout.addStretch()
        tab_widget.addTab(axes_tab, "X & Y Axes")

        # Legend Tab
        legend_tab = QWidget()
        legend_layout = QVBoxLayout(legend_tab)

        legend_group = QGroupBox("Legend Font")
        legend_group_layout = QVBoxLayout(legend_group)

        legend_font_layout = QHBoxLayout()
        self._legend_font_btn = QPushButton("Choose Font...")
        self._legend_font_btn.setFixedHeight(35)
        self._legend_color_btn = QPushButton()
        self._legend_color_btn.setFixedSize(50, 35)
        self._legend_color_btn.setStyleSheet("background-color: black; border: 1px solid gray;")
        self._legend_color_btn.setToolTip("Change legend text color")

        legend_font_layout.addWidget(QLabel("Font:"))
        legend_font_layout.addWidget(self._legend_font_btn)
        legend_font_layout.addWidget(QLabel("Color:"))
        legend_font_layout.addWidget(self._legend_color_btn)
        legend_font_layout.addStretch()
        legend_group_layout.addLayout(legend_font_layout)

        legend_layout.addWidget(legend_group)
        legend_layout.addStretch()
        tab_widget.addTab(legend_tab, "Legend")

        layout.addWidget(tab_widget)

        # Connect font buttons
        self._title_font_btn.clicked.connect(lambda: self._choose_font('title', self._title_font_btn))
        self._x_axis_font_btn.clicked.connect(lambda: self._choose_font('x_axis', self._x_axis_font_btn))
        self._y_axis_font_btn.clicked.connect(lambda: self._choose_font('y_axis', self._y_axis_font_btn))
        self._x_ticks_font_btn.clicked.connect(lambda: self._choose_font('x_ticks', self._x_ticks_font_btn))
        self._y_ticks_font_btn.clicked.connect(lambda: self._choose_font('y_ticks', self._y_ticks_font_btn))
        self._legend_font_btn.clicked.connect(lambda: self._choose_font('legend', self._legend_font_btn))

        # Connect color buttons
        self._title_color_btn.clicked.connect(lambda: self._choose_color('title', self._title_color_btn))
        self._x_ticks_color_btn.clicked.connect(lambda: self._choose_color('x_ticks', self._x_ticks_color_btn))
        self._y_ticks_color_btn.clicked.connect(lambda: self._choose_color('y_ticks', self._y_ticks_color_btn))
        self._legend_color_btn.clicked.connect(lambda: self._choose_color('legend', self._legend_color_btn))

        return widget

    def _create_plot_area_tab(self) -> QWidget:
        """Create the plot area properties tab (following chart_view pattern exactly)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Create tabs for different property categories
        tab_widget = QTabWidget()

        # Tab 1: Background & Borders
        bg_border_tab = QWidget()
        bg_border_layout = QVBoxLayout(bg_border_tab)

        # Background section
        bg_group = QGroupBox("Background")
        bg_layout = QVBoxLayout(bg_group)

        # Background color
        bg_color_layout = QHBoxLayout()
        bg_color_label = QLabel("Background Color:")
        self._bg_color_btn = QPushButton()
        self._bg_color_btn.setFixedSize(50, 30)
        self._bg_color_btn.setStyleSheet("background-color: white; border: 1px solid black;")

        bg_color_layout.addWidget(bg_color_label)
        bg_color_layout.addWidget(self._bg_color_btn)
        bg_color_layout.addStretch()
        bg_layout.addLayout(bg_color_layout)

        bg_border_layout.addWidget(bg_group)

        # Border section
        border_group = QGroupBox("Plot Area Border")
        border_layout = QVBoxLayout(border_group)

        # Border type selection
        border_type_layout = QHBoxLayout()
        border_type_label = QLabel("Border Type:")
        self._border_type_combo = QComboBox()
        self._border_type_combo.addItems(["Standard (Left & Bottom)", "Full Border (All Sides)", "No Border"])
        self._border_type_combo.setCurrentIndex(0)  # Default to standard

        border_type_layout.addWidget(border_type_label)
        border_type_layout.addWidget(self._border_type_combo)
        border_type_layout.addStretch()
        border_layout.addLayout(border_type_layout)

        # Show tick labels on top/right (only relevant for full border)
        self._show_tick_labels_check = QCheckBox("Show Tick Labels on Top & Right")
        self._show_tick_labels_check.setChecked(False)
        border_layout.addWidget(self._show_tick_labels_check)

        # Border color
        border_color_layout = QHBoxLayout()
        border_color_label = QLabel("Border Color:")
        self._border_color_btn = QPushButton()
        self._border_color_btn.setFixedSize(50, 30)
        self._border_color_btn.setStyleSheet("background-color: #333333; border: 1px solid black;")

        border_color_layout.addWidget(border_color_label)
        border_color_layout.addWidget(self._border_color_btn)
        border_color_layout.addStretch()
        border_layout.addLayout(border_color_layout)

        # Border style
        border_style_layout = QHBoxLayout()
        border_style_label = QLabel("Border Style:")
        self._border_style_combo = QComboBox()
        self._border_style_combo.addItems(["solid", "dashed", "dotted", "dashdot"])
        self._border_style_combo.setCurrentText("solid")

        border_style_layout.addWidget(border_style_label)
        border_style_layout.addWidget(self._border_style_combo)
        border_style_layout.addStretch()
        border_layout.addLayout(border_style_layout)

        # Border width
        border_width_layout = QHBoxLayout()
        border_width_label = QLabel("Border Width:")
        self._border_width_spin = QSpinBox()
        self._border_width_spin.setMinimum(1)
        self._border_width_spin.setMaximum(10)
        self._border_width_spin.setValue(1)

        border_width_layout.addWidget(border_width_label)
        border_width_layout.addWidget(self._border_width_spin)
        border_width_layout.addStretch()
        border_layout.addLayout(border_width_layout)

        bg_border_layout.addWidget(border_group)
        tab_widget.addTab(bg_border_tab, "Background & Borders")

        # Tab 2: Grid
        grid_tab = QWidget()
        grid_layout = QVBoxLayout(grid_tab)

        # Grid visibility
        grid_group = QGroupBox("Grid Lines")
        grid_group_layout = QVBoxLayout(grid_group)

        # Show grid checkboxes
        self._show_grid_x_check = QCheckBox("Show X-axis Grid")
        self._show_grid_y_check = QCheckBox("Show Y-axis Grid")
        self._show_grid_x_check.setChecked(True)
        self._show_grid_y_check.setChecked(True)

        grid_group_layout.addWidget(self._show_grid_x_check)
        grid_group_layout.addWidget(self._show_grid_y_check)

        # Grid alpha (transparency)
        grid_alpha_layout = QHBoxLayout()
        grid_alpha_label = QLabel("Grid Transparency:")
        self._grid_alpha_spin = QSpinBox()
        self._grid_alpha_spin.setMinimum(10)
        self._grid_alpha_spin.setMaximum(100)
        self._grid_alpha_spin.setSuffix("%")
        self._grid_alpha_spin.setValue(30)

        grid_alpha_layout.addWidget(grid_alpha_label)
        grid_alpha_layout.addWidget(self._grid_alpha_spin)
        grid_alpha_layout.addStretch()
        grid_group_layout.addLayout(grid_alpha_layout)

        grid_layout.addWidget(grid_group)
        tab_widget.addTab(grid_tab, "Grid")

        layout.addWidget(tab_widget)

        # Connect color buttons
        self._bg_color_btn.clicked.connect(lambda: self._choose_plot_color('background', self._bg_color_btn))
        self._border_color_btn.clicked.connect(lambda: self._choose_plot_color('border_color', self._border_color_btn))

        return widget

    def _format_font_info(self, font: QFont) -> str:
        """Format font information with family, size, weight, and italic status."""
        style_parts = []

        # Add weight information
        if font.weight() >= QFont.Weight.Bold.value:
            style_parts.append("Bold")

        # Add italic information
        if font.italic():
            style_parts.append("Italic")

        # Combine style info
        style_str = ", ".join(style_parts)
        if style_str:
            return f"{font.family()}, {font.pointSize()}pt, {style_str}"
        else:
            return f"{font.family()}, {font.pointSize()}pt"

    def _choose_font(self, element: str, button: QPushButton) -> None:
        """
        Open font dialog for a specific element (following chart_view pattern).

        Args:
            element: Font element key
            button: Button to update with font info
        """
        # Get current font
        current_font = self._current_fonts.get(element, QFont("Arial", 10))

        # Show font dialog (note: returns (ok, font) not (font, ok))
        ok, selected_font = QFontDialog.getFont(current_font, self, f"Choose {element.replace('_', ' ').title()} Font")

        if ok:
            # Store font
            self._current_fonts[element] = selected_font

            # Update button text
            button.setText(self._format_font_info(selected_font))

    def _choose_color(self, element: str, button: QPushButton) -> None:
        """
        Open color dialog for a font element.

        Args:
            element: Color element key
            button: Button to update with color
        """
        current_color_str = self._current_colors.get(element, '#000000')
        current_color = QColor(current_color_str)

        color = QColorDialog.getColor(current_color, self, f"Choose {element.replace('_', ' ').title()} Color")

        if color.isValid():
            self._current_colors[element] = color.name()
            button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")

    def _choose_plot_color(self, element: str, button: QPushButton) -> None:
        """
        Open color dialog for a plot area element.

        Args:
            element: Plot area color key
            button: Button to update with color
        """
        # Extract current color from button stylesheet
        current_color_str = self._extract_color_from_style(button.styleSheet())
        current_color = QColor(current_color_str)

        color = QColorDialog.getColor(current_color, self, f"Choose {element.replace('_', ' ').title()}")

        if color.isValid():
            # Use solid black border for plot area buttons (matching chart_view)
            button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")

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

        # Chart fonts tab - load from preferences (matching chart_view structure)
        default_fonts = self._preferences.get('default_chart_fonts', {})
        for element in ['title', 'x_axis', 'y_axis', 'x_ticks', 'y_ticks', 'legend']:
            font_data = default_fonts.get(element, {})
            if font_data and 'family' in font_data:
                font = QFont(
                    font_data.get('family', 'Arial'),
                    font_data.get('pointSize', 10)
                )
                if font_data.get('bold', False):
                    font.setBold(True)
                if font_data.get('italic', False):
                    font.setItalic(True)
                self._current_fonts[element] = font

        # Load colors
        default_colors = self._preferences.get('default_chart_colors', {})
        for element in ['title', 'x_axis', 'y_axis', 'x_ticks', 'y_ticks', 'legend']:
            if element in default_colors:
                self._current_colors[element] = default_colors[element]

        # Update button texts with loaded fonts
        self._title_font_btn.setText(self._format_font_info(self._current_fonts['title']))
        self._x_axis_font_btn.setText(self._format_font_info(self._current_fonts['x_axis']))
        self._y_axis_font_btn.setText(self._format_font_info(self._current_fonts['y_axis']))
        self._x_ticks_font_btn.setText(self._format_font_info(self._current_fonts['x_ticks']))
        self._y_ticks_font_btn.setText(self._format_font_info(self._current_fonts['y_ticks']))
        self._legend_font_btn.setText(self._format_font_info(self._current_fonts['legend']))

        # Update color buttons
        self._title_color_btn.setStyleSheet(
            f"background-color: {self._current_colors['title']}; border: 1px solid gray;")
        self._x_ticks_color_btn.setStyleSheet(
            f"background-color: {self._current_colors['x_ticks']}; border: 1px solid gray;")
        self._y_ticks_color_btn.setStyleSheet(
            f"background-color: {self._current_colors['y_ticks']}; border: 1px solid gray;")
        self._legend_color_btn.setStyleSheet(
            f"background-color: {self._current_colors['legend']}; border: 1px solid gray;")

        # Plot area tab (matching chart_view structure)
        plot_settings = self._preferences.get('default_plot_area_settings', {})

        # Background color
        if 'background_color' in plot_settings:
            self._bg_color_btn.setStyleSheet(
                f"background-color: {plot_settings['background_color']}; border: 1px solid black;")

        # Border type
        border_type = plot_settings.get('border_type', 'standard')
        if border_type == 'full':
            self._border_type_combo.setCurrentIndex(1)
        elif border_type == 'none':
            self._border_type_combo.setCurrentIndex(2)
        else:  # 'standard'
            self._border_type_combo.setCurrentIndex(0)

        # Show tick labels
        self._show_tick_labels_check.setChecked(plot_settings.get('show_top_right_labels', False))

        # Border color
        if 'border_color' in plot_settings:
            self._border_color_btn.setStyleSheet(
                f"background-color: {plot_settings['border_color']}; border: 1px solid black;")

        # Border style and width
        self._border_style_combo.setCurrentText(plot_settings.get('border_style', 'solid'))
        self._border_width_spin.setValue(plot_settings.get('border_width', 1))

        # Grid settings
        self._show_grid_x_check.setChecked(plot_settings.get('show_grid_x', True))
        self._show_grid_y_check.setChecked(plot_settings.get('show_grid_y', True))

        # Grid alpha (convert from 0.0-1.0 to percentage)
        grid_alpha = plot_settings.get('grid_alpha', 0.3)
        self._grid_alpha_spin.setValue(int(grid_alpha * 100))

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

        # Reset fonts to defaults (matching chart_view structure)
        self._current_fonts = {
            'title': QFont("Arial", 12, QFont.Weight.Bold),
            'x_axis': QFont("Arial", 10),
            'y_axis': QFont("Arial", 10),
            'x_ticks': QFont("Arial", 9),
            'y_ticks': QFont("Arial", 9),
            'legend': QFont("Arial", 9)
        }

        self._current_colors = {
            'title': '#000000',
            'x_axis': '#000000',
            'y_axis': '#000000',
            'x_ticks': '#000000',
            'y_ticks': '#000000',
            'legend': '#000000'
        }

        # Update button texts
        self._title_font_btn.setText(self._format_font_info(self._current_fonts['title']))
        self._x_axis_font_btn.setText(self._format_font_info(self._current_fonts['x_axis']))
        self._y_axis_font_btn.setText(self._format_font_info(self._current_fonts['y_axis']))
        self._x_ticks_font_btn.setText(self._format_font_info(self._current_fonts['x_ticks']))
        self._y_ticks_font_btn.setText(self._format_font_info(self._current_fonts['y_ticks']))
        self._legend_font_btn.setText(self._format_font_info(self._current_fonts['legend']))

        # Reset color buttons
        self._title_color_btn.setStyleSheet("background-color: #000000; border: 1px solid gray;")
        self._x_ticks_color_btn.setStyleSheet("background-color: #000000; border: 1px solid gray;")
        self._y_ticks_color_btn.setStyleSheet("background-color: #000000; border: 1px solid gray;")
        self._legend_color_btn.setStyleSheet("background-color: #000000; border: 1px solid gray;")

        # Plot area defaults (matching chart_view structure)
        self._bg_color_btn.setStyleSheet("background-color: white; border: 1px solid black;")
        self._border_type_combo.setCurrentIndex(0)  # Standard border
        self._show_tick_labels_check.setChecked(False)
        self._border_color_btn.setStyleSheet("background-color: #333333; border: 1px solid black;")
        self._border_style_combo.setCurrentText("solid")
        self._border_width_spin.setValue(1)
        self._show_grid_x_check.setChecked(True)
        self._show_grid_y_check.setChecked(True)
        self._grid_alpha_spin.setValue(30)

        # Reset preferences dict
        self._preferences['default_chart_fonts'] = {}
        self._preferences['default_chart_colors'] = {}
        self._preferences['default_plot_area_settings'] = {}

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

        # Update chart fonts - convert QFont to serializable dict (matching chart_view structure)
        self._preferences['default_chart_fonts'] = {}
        for key, font in self._current_fonts.items():
            self._preferences['default_chart_fonts'][key] = {
                'family': font.family(),
                'pointSize': font.pointSize(),
                'weight': font.weight(),
                'bold': font.bold(),
                'italic': font.italic()
            }

        # Update chart colors
        self._preferences['default_chart_colors'] = self._current_colors.copy()

        # Update plot area settings from UI (matching chart_view structure)
        if 'default_plot_area_settings' not in self._preferences:
            self._preferences['default_plot_area_settings'] = {}

        # Extract colors from button styles
        bg_color = self._extract_color_from_style(self._bg_color_btn.styleSheet())
        border_color = self._extract_color_from_style(self._border_color_btn.styleSheet())

        # Map border type combo index to string
        border_type_map = {0: 'standard', 1: 'full', 2: 'none'}

        self._preferences['default_plot_area_settings'] = {
            'background_color': bg_color,
            'border_type': border_type_map[self._border_type_combo.currentIndex()],
            'show_top_right_labels': self._show_tick_labels_check.isChecked(),
            'border_color': border_color,
            'border_style': self._border_style_combo.currentText(),
            'border_width': self._border_width_spin.value(),
            'show_grid_x': self._show_grid_x_check.isChecked(),
            'show_grid_y': self._show_grid_y_check.isChecked(),
            'grid_alpha': self._grid_alpha_spin.value() / 100.0  # Convert percentage to 0.0-1.0
        }

        return self._preferences

    def _extract_color_from_style(self, style_sheet: str) -> str:
        """Extract color hex code from button stylesheet."""
        # Parse "background-color: #XXXXXX; ..."
        import re
        match = re.search(r'background-color:\s*(#[0-9A-Fa-f]{6})', style_sheet)
        if match:
            return match.group(1)
        return '#FFFFFF'  # Default fallback
