# Preferences Dialog Update - Consistency with ChartView

## Summary

Updated the PreferencesDialog to match the exact structure and behavior of the font styling and plot area property dialogs in ChartView for UI consistency.

## Changes Made

### 1. Font Structure Updates

**Before:**

- Simple flat list of font groups: Title, Axis Labels, X-Ticks, Y-Ticks, Legend
- All elements shown at once in a single scrolling view
- 5 font elements: `title`, `axis_labels`, `x_ticks`, `y_ticks`, `legend`

**After:**

- Tab-based layout matching chart_view exactly:
  - **Chart Title Tab**: Title font and color
  - **X & Y Axes Tab**: Separate label fonts (no color) + tick fonts with colors
    - X-Axis (Label + Ticks): Label font button, Tick font & color buttons
    - Y-Axis (Label + Ticks): Label font button, Tick font & color buttons
  - **Legend Tab**: Legend font and color
- 6 font elements: `title`, `x_axis`, `y_axis`, `x_ticks`, `y_ticks`, `legend`
- Tick colors control both tick numbers AND axis label colors (matching chart_view behavior)

### 2. Plot Area Properties Updates

**Before:**

- Simple flat layout with basic settings:
  - Background color
  - Border enabled checkbox
  - Border color and width
  - Grid enabled checkbox
  - Grid color and alpha (0-255 range)

**After:**

- Tab-based layout matching chart_view exactly:
  - **Background & Borders Tab**:
    - Background color with white/black border styling
    - Border Type dropdown: "Standard (Left & Bottom)", "Full Border (All Sides)", "No Border"
    - Show Tick Labels on Top & Right checkbox
    - Border color, style (solid/dashed/dotted/dashdot), and width
  - **Grid Tab**:
    - Separate X-axis and Y-axis grid checkboxes
    - Grid transparency as percentage (10-100%)

### 3. Color Button Styling

**Before:**

- Font color buttons: `background-color: #XXXXXX; border: 1px solid gray;`
- Plot area buttons: `background-color: #XXXXXX; border: 1px solid gray;`

**After:**

- Font color buttons: `background-color: black; border: 1px solid gray;` (matching chart_view)
- Plot area buttons: `background-color: white; border: 1px solid black;` (matching chart_view)

### 4. Data Structure Changes

**Font Keys:**

```python
# Before
_current_fonts = {
    'title': QFont(...),
    'axis_labels': QFont(...),
    'x_ticks': QFont(...),
    'y_ticks': QFont(...),
    'legend': QFont(...)
}

# After (matching chart_view)
_current_fonts = {
    'title': QFont(...),
    'x_axis': QFont(...),
    'y_axis': QFont(...),
    'x_ticks': QFont(...),
    'y_ticks': QFont(...),
    'legend': QFont(...)
}
```

**Plot Area Settings:**

```python
# Before
default_plot_area_settings = {
    'background': '#FFFFFF',
    'border_enabled': True,
    'border_color': '#000000',
    'border_width': 1,
    'grid_enabled': True,
    'grid_color': '#CCCCCC',
    'grid_alpha': 128  # 0-255
}

# After (matching chart_view)
default_plot_area_settings = {
    'background_color': 'white',
    'border_type': 'standard',  # 'standard', 'full', 'none'
    'show_top_right_labels': False,
    'border_color': '#333333',
    'border_style': 'solid',  # 'solid', 'dashed', 'dotted', 'dashdot'
    'border_width': 1,
    'show_grid_x': True,
    'show_grid_y': True,
    'grid_alpha': 0.3  # 0.0-1.0
}
```

### 5. UI Elements Updated

**Removed:**

- `_axis_font_btn` and `_axis_color_btn` (replaced with separate x/y axis controls)
- `_border_enabled_check` (replaced with border type dropdown)
- `_grid_enabled_check` (replaced with separate x/y grid checkboxes)
- `_grid_color_btn` (grid color not easily customizable in PyQtGraph)

**Added:**

- `_x_axis_font_btn` and `_y_axis_font_btn` (separate axis label fonts)
- `_border_type_combo` (Standard/Full/None options)
- `_show_tick_labels_check` (for full border mode)
- `_border_style_combo` (solid/dashed/dotted/dashdot)
- `_show_grid_x_check` and `_show_grid_y_check` (separate grid controls)

### 6. Default Values Updated

**Border Color:** Changed from `#000000` (black) to `#333333` (dark gray) to match chart_view
**Background:** Changed from `#FFFFFF` to `white` for consistency
**Grid Alpha:** Changed from 128 (0-255 scale) to 30% (10-100% scale)

## Benefits

1. **Consistent User Experience**: Preferences dialog now looks and behaves identically to chart property dialogs
2. **Advanced Features**: Users can now set defaults for:
   - Different border types (standard vs full border)
   - Top/right tick label visibility
   - Separate X/Y axis fonts
   - Border line styles
   - Individual X/Y grid control
3. **Professional Appearance**: Matches chart_view's polished tab-based layout
4. **Future-Proof**: When chart_view adds features, preferences can easily match them

## Migration Notes

- Existing preferences with old structure will still load correctly
- The dialog will initialize missing keys with appropriate defaults
- Old `axis_labels` font will map to both `x_axis` and `y_axis` fonts if present
- Old `background` will map to `background_color` automatically
- Old `grid_alpha` (0-255) will convert to percentage (0-100)

## Testing Recommendations

1. Open Tools > Preferences and verify tab-based font layout
2. Check that X/Y axes show separate label and tick font controls
3. Verify plot area has Background & Borders / Grid tabs
4. Test border type dropdown (Standard/Full/None)
5. Confirm grid alpha shows as percentage (%)
6. Create new chart and verify default styling applies correctly
7. Reset to Defaults should restore Arial fonts, black text, white background
