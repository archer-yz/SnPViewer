# Enhanced Limit Lines - User Guide

## Point-Based Limit Input Formats

The point-based limit line feature now supports multiple input formats for convenience:

### Frequency Formats

- **Scientific notation**: `1e9,-20` (1 GHz, -20 dB)
- **Full numbers**: `1000000000,-20` (1 billion Hz, -20 dB)
- **With suffixes**: `1G,-20` (1 GHz, -20 dB)

### Supported Suffixes

- `k` or `K` = ×1,000 (kHz)
- `M` = ×1,000,000 (MHz)
- `G` = ×1,000,000,000 (GHz)
- `T` = ×1,000,000,000,000 (THz)

### Example Input for Insertion Loss Limit

```
1G,-10
2.5G,-15
5G,-20
7.5G,-15
10G,-10
```

## Range Types Fixed

### Frequency Range (Horizontal Range)

- **Purpose**: Mark frequency bands (e.g., operating band 4-6 GHz)
- **Input**: Start frequency, End frequency (in Hz)
- **Visual**: Vertical shaded region on chart

### Value Range (Vertical Range)

- **Purpose**: Mark acceptable value ranges (e.g., -25 to -15 dB pass zone)
- **Input**: Minimum value, Maximum value (in current Y-axis units)
- **Visual**: Horizontal shaded region on chart

## Complete Menu Structure

Right-click on chart → **Limit Lines** →

1. **Horizontal Line...** - Single horizontal limit (constant Y value)
2. **Vertical Line...** - Single vertical limit (constant frequency)
3. **Frequency Range...** - Frequency band marking (X-axis range)
4. **Value Range...** - Acceptable value zone (Y-axis range)
5. **Point-Based Limit...** - Custom curve from points
6. **Clear All Limit Lines** - Remove all limits

## RF Engineering Use Cases

- **Horizontal Lines**: Spec limits (-20 dB max insertion loss)
- **Vertical Lines**: Critical frequencies (center frequency, band edges)
- **Frequency Range**: Operating bands, restricted bands
- **Value Range**: Pass/fail zones, tolerance bands
- **Point-Based**: Complex specification envelopes, FCC masks
