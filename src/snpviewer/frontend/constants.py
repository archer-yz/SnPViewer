"""
Frontend constants and configuration values.

This module contains shared constants used across the frontend,
particularly for consistent styling and color schemes.
"""

# Default color palette for traces (12 colors for variety)
DEFAULT_TRACE_COLORS = [
    # "#FF6B6B",  # Red
    # "#4ECDC4",  # Teal
    # "#45B7D1",  # Light Blue
    # "#96CEB4",  # Sage Green
    # "#FFEAA7",  # Yellow
    # "#DDA0DD",  # Plum
    # "#74B9FF",  # Sky Blue
    # "#E17055",  # Orange
    # "#00B894",  # Emerald
    # "#FDCB6E",  # Gold
    # "#6C5CE7",  # Purple
    # "#A29BFE",  # Lavender

    # excel default colors
    "#4472C4",  # blue
    "#ED7D31",  # orange
    "#A5A5A5",  # gray
    "#FFC000",  # gold
    "#5B9BD5",  # light blue
    "#70AD47",  # green
    "#264478",  # dark blue
    "#9E480E",  # dark orange
    "#636363",  # dark gray
    "#997300",  # dark gold
]

# Shorter color palette (6 colors) - for backward compatibility
SHORT_TRACE_COLORS = DEFAULT_TRACE_COLORS[:6]

DEFAULT_LINE_STYLES = [
    "solid", "dotted", "dashed", "dash_dot"
]

# Marker colors (distinct from trace colors)
DEFAULT_MARKER_COLORS = [
    "#FF0000",  # Red
    "#00FF00",  # Green
    "#0000FF",  # Blue
    "#FF00FF",  # Magenta
    "#00FFFF",  # Cyan
    "#FFFF00",  # Yellow
]
