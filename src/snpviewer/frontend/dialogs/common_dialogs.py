"""
Common dialog widgets for chart styling.

Provides reusable dialog components for font styling and plot area properties
that are shared between ChartView and PreferencesDialog.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QFontDialog,
                               QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QSpinBox, QTabWidget, QVBoxLayout, QWidget)


class FontStylingWidget(QWidget):
    """
    Reusable widget for font styling configuration.

    Provides a tab-based interface for configuring chart element fonts and colors:
    - Chart Title: Font and color
    - X & Y Axes: Separate label fonts + tick fonts with colors
    - Legend: Font and color

    This widget is used in both ChartView (for current chart) and
    PreferencesDialog (for default settings).
    """

    def __init__(
        self,
        initial_fonts: Optional[Dict[str, QFont]] = None,
        initial_colors: Optional[Dict[str, str]] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize font styling widget.

        Args:
            initial_fonts: Initial font settings (title, x_axis, y_axis, x_ticks, y_ticks, legend)
            initial_colors: Initial color settings (title, x_ticks, y_ticks, legend)
            parent: Parent widget
        """
        super().__init__(parent)

        # Initialize current fonts with defaults or provided values
        default_fonts = {
            'title': QFont("Arial", 12, QFont.Weight.Bold),
            'x_axis': QFont("Arial", 10),
            'y_axis': QFont("Arial", 10),
            'x_ticks': QFont("Arial", 9),
            'y_ticks': QFont("Arial", 9),
            'legend': QFont("Arial", 9)
        }
        self._current_fonts = initial_fonts.copy() if initial_fonts else default_fonts

        # Initialize current colors with defaults or provided values
        default_colors = {
            'title': '#000000',
            'x_axis': '#000000',
            'y_axis': '#000000',
            'x_ticks': '#000000',
            'y_ticks': '#000000',
            'legend': '#000000'
        }
        self._current_colors = initial_colors.copy() if initial_colors else default_colors

        self._setup_ui()
        self._update_button_displays()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tab widget for different chart elements
        self._tab_widget = QTabWidget()

        # Chart Title Tab
        title_tab = self._create_title_tab()
        self._tab_widget.addTab(title_tab, "Chart Title")

        # X & Y Axes Tab
        axes_tab = self._create_axes_tab()
        self._tab_widget.addTab(axes_tab, "X & Y Axes")

        # Legend Tab
        legend_tab = self._create_legend_tab()
        self._tab_widget.addTab(legend_tab, "Legend")

        layout.addWidget(self._tab_widget)

    def _create_title_tab(self) -> QWidget:
        """Create the chart title font configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

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

        layout.addWidget(title_group)
        layout.addStretch()

        # Connect signals
        self._title_font_btn.clicked.connect(lambda: self._choose_font('title', self._title_font_btn))
        self._title_color_btn.clicked.connect(lambda: self._choose_color('title', self._title_color_btn))

        return tab

    def _create_axes_tab(self) -> QWidget:
        """Create the X & Y axes font configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

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

        layout.addWidget(x_axis_group)
        layout.addWidget(y_axis_group)
        layout.addStretch()

        # Connect signals
        self._x_axis_font_btn.clicked.connect(lambda: self._choose_font('x_axis', self._x_axis_font_btn))
        self._y_axis_font_btn.clicked.connect(lambda: self._choose_font('y_axis', self._y_axis_font_btn))
        self._x_ticks_font_btn.clicked.connect(lambda: self._choose_font('x_ticks', self._x_ticks_font_btn))
        self._y_ticks_font_btn.clicked.connect(lambda: self._choose_font('y_ticks', self._y_ticks_font_btn))
        self._x_ticks_color_btn.clicked.connect(lambda: self._choose_color('x_ticks', self._x_ticks_color_btn))
        self._y_ticks_color_btn.clicked.connect(lambda: self._choose_color('y_ticks', self._y_ticks_color_btn))

        return tab

    def _create_legend_tab(self) -> QWidget:
        """Create the legend font configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

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

        layout.addWidget(legend_group)
        layout.addStretch()

        # Connect signals
        self._legend_font_btn.clicked.connect(lambda: self._choose_font('legend', self._legend_font_btn))
        self._legend_color_btn.clicked.connect(lambda: self._choose_color('legend', self._legend_color_btn))

        return tab

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
        Open font dialog for a specific element.

        Args:
            element: Font element key
            button: Button to update with font info
        """
        # Get current font
        current_font = self._current_fonts.get(element, QFont("Arial", 10))

        # Show font dialog (returns (ok, font) not (font, ok))
        ok, selected_font = QFontDialog.getFont(
            current_font,
            self,
            f"Choose {element.replace('_', ' ').title()} Font"
        )

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

        color = QColorDialog.getColor(
            current_color,
            self,
            f"Choose {element.replace('_', ' ').title()} Color"
        )

        if color.isValid():
            self._current_colors[element] = color.name()
            button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")

    def _update_button_displays(self) -> None:
        """Update all button displays with current font and color settings."""
        # Update font button texts
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

    def reset_to_defaults(self) -> None:
        """Reset all fonts and colors to defaults."""
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

        self._update_button_displays()

    def get_fonts(self) -> Dict[str, QFont]:
        """
        Get current font settings.

        Returns:
            Dictionary of QFont objects keyed by element name
        """
        return self._current_fonts.copy()

    def get_colors(self) -> Dict[str, str]:
        """
        Get current color settings.

        Returns:
            Dictionary of color hex strings keyed by element name
        """
        return self._current_colors.copy()

    def set_fonts(self, fonts: Dict[str, QFont]) -> None:
        """
        Set font settings.

        Args:
            fonts: Dictionary of QFont objects keyed by element name
        """
        self._current_fonts.update(fonts)
        self._update_button_displays()

    def set_colors(self, colors: Dict[str, str]) -> None:
        """
        Set color settings.

        Args:
            colors: Dictionary of color hex strings keyed by element name
        """
        self._current_colors.update(colors)
        self._update_button_displays()


class PlotAreaPropertiesWidget(QWidget):
    """
    Reusable widget for plot area properties configuration.

    Provides a tab-based interface for configuring plot area properties:
    - Background & Borders: Background color, border type/style/width
    - Grid: X/Y grid visibility, transparency

    This widget is used in both ChartView (for current chart) and
    PreferencesDialog (for default settings).
    """

    def __init__(
        self,
        initial_settings: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None
    ):
        """
        Initialize plot area properties widget.

        Args:
            initial_settings: Initial plot area settings
            parent: Parent widget
        """
        super().__init__(parent)

        # Initialize current settings with defaults or provided values
        default_settings = {
            'background_color': 'white',
            'border_type': 'standard',
            'show_top_right_labels': False,
            'border_color': '#333333',
            'border_style': 'solid',
            'border_width': 1,
            'show_grid_x': True,
            'show_grid_y': True,
            'grid_alpha': 0.3
        }
        self._current_settings = initial_settings.copy() if initial_settings else default_settings

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Setup the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create tabs for different property categories
        self._tab_widget = QTabWidget()

        # Background & Borders Tab
        bg_border_tab = self._create_background_borders_tab()
        self._tab_widget.addTab(bg_border_tab, "Background & Borders")

        # Grid Tab
        grid_tab = self._create_grid_tab()
        self._tab_widget.addTab(grid_tab, "Grid")

        layout.addWidget(self._tab_widget)

    def _create_background_borders_tab(self) -> QWidget:
        """Create the background and borders configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

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

        layout.addWidget(bg_group)

        # Border section
        border_group = QGroupBox("Plot Area Border")
        border_layout = QVBoxLayout(border_group)

        # Border type selection
        border_type_layout = QHBoxLayout()
        border_type_label = QLabel("Border Type:")
        self._border_type_combo = QComboBox()
        self._border_type_combo.addItems([
            "Standard (Left & Bottom)",
            "Full Border (All Sides)",
            "No Border"
        ])

        border_type_layout.addWidget(border_type_label)
        border_type_layout.addWidget(self._border_type_combo)
        border_type_layout.addStretch()
        border_layout.addLayout(border_type_layout)

        # Show tick labels on top/right (only relevant for full border)
        self._show_tick_labels_check = QCheckBox("Show Tick Labels on Top & Right")
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

        border_width_layout.addWidget(border_width_label)
        border_width_layout.addWidget(self._border_width_spin)
        border_width_layout.addStretch()
        border_layout.addLayout(border_width_layout)

        layout.addWidget(border_group)

        # Connect signals
        self._bg_color_btn.clicked.connect(self._choose_background_color)
        self._border_color_btn.clicked.connect(self._choose_border_color)

        return tab

    def _create_grid_tab(self) -> QWidget:
        """Create the grid configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Grid visibility
        grid_group = QGroupBox("Grid Lines")
        grid_group_layout = QVBoxLayout(grid_group)

        # Show grid checkboxes
        self._show_grid_x_check = QCheckBox("Show X-axis Grid")
        self._show_grid_y_check = QCheckBox("Show Y-axis Grid")

        grid_group_layout.addWidget(self._show_grid_x_check)
        grid_group_layout.addWidget(self._show_grid_y_check)

        # Grid alpha (transparency)
        grid_alpha_layout = QHBoxLayout()
        grid_alpha_label = QLabel("Grid Transparency:")
        self._grid_alpha_spin = QSpinBox()
        self._grid_alpha_spin.setMinimum(10)
        self._grid_alpha_spin.setMaximum(100)
        self._grid_alpha_spin.setSuffix("%")

        grid_alpha_layout.addWidget(grid_alpha_label)
        grid_alpha_layout.addWidget(self._grid_alpha_spin)
        grid_alpha_layout.addStretch()
        grid_group_layout.addLayout(grid_alpha_layout)

        layout.addWidget(grid_group)

        return tab

    def _choose_background_color(self) -> None:
        """Open color dialog for background color."""
        # Extract current color from button stylesheet
        match = re.search(r'background-color:\s*(\S+);', self._bg_color_btn.styleSheet())
        current_color_str = match.group(1) if match else 'white'
        current_color = QColor(current_color_str)

        color = QColorDialog.getColor(current_color, self, "Choose Background Color")

        if color.isValid():
            self._bg_color_btn.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid black;")

    def _choose_border_color(self) -> None:
        """Open color dialog for border color."""
        # Extract current color from button stylesheet
        match = re.search(r'background-color:\s*(\S+);', self._border_color_btn.styleSheet())
        current_color_str = match.group(1) if match else '#333333'
        current_color = QColor(current_color_str)

        color = QColorDialog.getColor(current_color, self, "Choose Border Color")

        if color.isValid():
            self._border_color_btn.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid black;")

    def _load_settings(self) -> None:
        """Load current settings into UI controls."""
        # Background color
        bg_color = self._current_settings.get('background_color', 'white')
        self._bg_color_btn.setStyleSheet(
            f"background-color: {bg_color}; border: 1px solid black;")

        # Border type
        border_type = self._current_settings.get('border_type', 'standard')
        if border_type == 'full':
            self._border_type_combo.setCurrentIndex(1)
        elif border_type == 'none':
            self._border_type_combo.setCurrentIndex(2)
        else:  # 'standard'
            self._border_type_combo.setCurrentIndex(0)

        # Show tick labels
        self._show_tick_labels_check.setChecked(
            self._current_settings.get('show_top_right_labels', False))

        # Border color
        border_color = self._current_settings.get('border_color', '#333333')
        self._border_color_btn.setStyleSheet(
            f"background-color: {border_color}; border: 1px solid black;")

        # Border style and width
        self._border_style_combo.setCurrentText(
            self._current_settings.get('border_style', 'solid'))
        self._border_width_spin.setValue(
            self._current_settings.get('border_width', 1))

        # Grid settings
        self._show_grid_x_check.setChecked(
            self._current_settings.get('show_grid_x', True))
        self._show_grid_y_check.setChecked(
            self._current_settings.get('show_grid_y', True))

        # Grid alpha (convert from 0.0-1.0 to percentage)
        grid_alpha = self._current_settings.get('grid_alpha', 0.3)
        self._grid_alpha_spin.setValue(int(grid_alpha * 100))

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._current_settings = {
            'background_color': 'white',
            'border_type': 'standard',
            'show_top_right_labels': False,
            'border_color': '#333333',
            'border_style': 'solid',
            'border_width': 1,
            'show_grid_x': True,
            'show_grid_y': True,
            'grid_alpha': 0.3
        }
        self._load_settings()

    def get_settings(self) -> Dict[str, Any]:
        """
        Get current plot area settings.

        Returns:
            Dictionary of plot area settings
        """
        # Extract colors from button stylesheets
        bg_match = re.search(r'background-color:\s*(\S+);', self._bg_color_btn.styleSheet())
        bg_color = bg_match.group(1) if bg_match else 'white'

        border_match = re.search(r'background-color:\s*(\S+);', self._border_color_btn.styleSheet())
        border_color = border_match.group(1) if border_match else '#333333'

        # Map border type combo index to string
        border_type_map = {0: 'standard', 1: 'full', 2: 'none'}

        return {
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

    def set_settings(self, settings: Dict[str, Any]) -> None:
        """
        Set plot area settings.

        Args:
            settings: Dictionary of plot area settings
        """
        self._current_settings.update(settings)
        self._load_settings()
