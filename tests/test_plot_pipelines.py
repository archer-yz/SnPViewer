"""
Simplified unit tests for plot pipeline data preparation.

Tests the core functionality of converting S-parameter data into plot-ready arrays.
"""
from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import Mock

from snpviewer.backend.models.trace import Trace, TraceStyle, PortPath
from snpviewer.frontend.plotting.plot_pipelines import (
    get_frequency_array,
    convert_s_to_db,
    convert_s_to_phase,
    unwrap_phase,
    compute_group_delay,
    _extract_s_parameter,
    PlotData,
    PlotType
)


class TestFrequencyArrayGeneration:
    """Test frequency array extraction and unit conversion."""

    def test_get_frequency_from_dataset(self):
        """Test extracting frequency array from dataset."""
        freq = np.array([1e6, 2e6, 3e6])  # Hz

        dataset = Mock()
        dataset.frequency_hz = freq

        result = get_frequency_array(dataset)
        np.testing.assert_array_equal(result, freq)

    def test_frequency_unit_conversion(self):
        """Test frequency unit conversion."""
        freq_hz = np.array([1e6, 2e6, 3e6])

        # Test GHz conversion
        freq_ghz = get_frequency_array(Mock(frequency_hz=freq_hz), unit='GHz')
        expected_ghz = freq_hz / 1e9
        np.testing.assert_array_almost_equal(freq_ghz, expected_ghz)

        # Test MHz conversion
        freq_mhz = get_frequency_array(Mock(frequency_hz=freq_hz), unit='MHz')
        expected_mhz = freq_hz / 1e6
        np.testing.assert_array_almost_equal(freq_mhz, expected_mhz)


class TestSParameterConversions:
    """Test S-parameter conversion utilities."""

    def test_convert_s_to_db(self):
        """Test S-parameter to dB conversion utility."""
        s_complex = np.array([0.5+0.3j, 0.1+0.05j, 1.0+0.0j])

        db_values = convert_s_to_db(s_complex)

        expected = 20 * np.log10(np.abs(s_complex))
        np.testing.assert_array_almost_equal(db_values, expected)

    def test_magnitude_zero_handling(self):
        """Test handling of zero magnitude values."""
        s_complex = np.array([0.5+0.3j, 0.0+0.0j, 0.1+0.05j])

        db_values = convert_s_to_db(s_complex)

        # Should handle zero magnitude gracefully (not produce -inf)
        assert np.isfinite(db_values[0])
        assert np.isfinite(db_values[2])
        # Zero magnitude should produce a very negative but finite dB value
        assert db_values[1] < -100

    def test_convert_s_to_phase(self):
        """Test S-parameter to phase conversion utility."""
        s_complex = np.array([1.0+0.0j, 0.0+1.0j, -1.0+0.0j, 0.0-1.0j])

        phase_deg = convert_s_to_phase(s_complex, degrees=True)
        phase_rad = convert_s_to_phase(s_complex, degrees=False)

        expected_rad = np.array([0, np.pi/2, np.pi, -np.pi/2])
        expected_deg = expected_rad * 180 / np.pi

        np.testing.assert_array_almost_equal(phase_rad, expected_rad)
        np.testing.assert_array_almost_equal(phase_deg, expected_deg)

    def test_phase_unwrapping(self):
        """Test phase unwrapping functionality."""
        # Create phase data with discontinuity
        phase_wrapped = np.array([0.1, 0.2, 6.0, -6.0, -5.9])  # Discontinuity around π

        phase_unwrapped = unwrap_phase(phase_wrapped)

        # Should be continuous after unwrapping
        phase_diff = np.diff(phase_unwrapped)
        assert np.all(np.abs(phase_diff) < np.pi)


class TestGroupDelayComputation:
    """Test group delay computation."""

    def test_compute_group_delay(self):
        """Test group delay computation utility."""
        freq = np.array([1e6, 2e6, 3e6, 4e6])
        phase = np.array([0, -0.1, -0.2, -0.3])  # Linear phase

        group_delay = compute_group_delay(freq, phase)

        # For linear phase, group delay should be approximately constant
        assert len(group_delay) == len(freq) - 1
        # Check that values are reasonable (should be positive for this case)
        assert np.all(group_delay > 0)

    def test_group_delay_units(self):
        """Test group delay unit conversion."""
        freq = np.linspace(1e9, 2e9, 100)  # 1-2 GHz
        phase = -2 * np.pi * freq * 1e-9  # 1 ns delay

        # Group delay should be approximately 1e-9 seconds
        group_delay = compute_group_delay(freq, phase)
        expected_delay = 1e-9  # 1 ns

        # Should be close to expected delay
        np.testing.assert_allclose(group_delay, expected_delay, rtol=0.1)


class TestPlotDataClass:
    """Test PlotData dataclass functionality."""

    def test_plot_data_creation(self):
        """Test PlotData instance creation."""
        x = np.array([1, 2, 3])
        y = np.array([4, 5, 6])

        plot_data = PlotData(
            x=x,
            y=y,
            plot_type=PlotType.MAGNITUDE,
            label="Test Trace",
            units_x="Hz",
            units_y="dB"
        )

        assert plot_data.plot_type == PlotType.MAGNITUDE
        assert plot_data.label == "Test Trace"
        assert plot_data.units_x == "Hz"
        assert plot_data.units_y == "dB"
        np.testing.assert_array_equal(plot_data.x, x)
        np.testing.assert_array_equal(plot_data.y, y)

    def test_plot_data_defaults(self):
        """Test PlotData default values."""
        x = np.array([1, 2, 3])
        y = np.array([4, 5, 6])

        plot_data = PlotData(x=x, y=y, plot_type=PlotType.PHASE)

        assert plot_data.label == ""
        assert plot_data.units_x == ""
        assert plot_data.units_y == ""


class TestTraceParameterExtraction:
    """Test extraction of S-parameters from traces."""

    def test_s11_extraction(self):
        """Test S11 parameter extraction."""
        # freq = np.array([1e6, 2e6, 3e6])
        s_params = np.array([
            [[0.5+0.3j, 0.1+0.05j], [0.1+0.05j, 0.6+0.2j]],
            [[0.4+0.2j, 0.08+0.04j], [0.08+0.04j, 0.5+0.1j]],
            [[0.3+0.1j, 0.06+0.03j], [0.06+0.03j, 0.4+0.05j]]
        ])

        trace = Trace(
            id="test_trace",
            dataset_id="test",
            domain="S",
            port_path=PortPath(i=1, j=1),  # S11
            metric="magnitude",
            style=TraceStyle()
        )

        s_param = _extract_s_parameter(s_params, trace)
        expected = s_params[:, 0, 0]  # S11

        np.testing.assert_array_equal(s_param, expected)

    def test_s21_extraction(self):
        """Test S21 parameter extraction."""
        s_params = np.array([
            [[0.5+0.3j, 0.1+0.05j], [0.1+0.05j, 0.6+0.2j]],
            [[0.4+0.2j, 0.08+0.04j], [0.08+0.04j, 0.5+0.1j]],
            [[0.3+0.1j, 0.06+0.03j], [0.06+0.03j, 0.4+0.05j]]
        ])

        trace = Trace(
            id="test_trace",
            dataset_id="test",
            domain="S",
            port_path=PortPath(i=2, j=1),  # S21
            metric="magnitude",
            style=TraceStyle()
        )

        s_param = _extract_s_parameter(s_params, trace)
        expected = s_params[:, 1, 0]  # S21

        np.testing.assert_array_equal(s_param, expected)

    def test_invalid_domain(self):
        """Test handling of non-S parameter domains."""
        s_params = np.zeros((3, 2, 2), dtype=complex)

        trace = Trace(
            id="test_trace",
            dataset_id="test",
            domain="Z",  # Not S-parameters
            port_path=PortPath(i=1, j=1),
            metric="magnitude",
            style=TraceStyle()
        )

        with pytest.raises(ValueError, match="Only S-parameters supported"):
            _extract_s_parameter(s_params, trace)

    def test_port_index_out_of_range(self):
        """Test handling of out-of-range port indices."""
        s_params = np.zeros((3, 2, 2), dtype=complex)  # 2x2 matrix

        trace = Trace(
            id="test_trace",
            dataset_id="test",
            domain="S",
            port_path=PortPath(i=3, j=1),  # Port 3 doesn't exist in 2x2 matrix
            metric="magnitude",
            style=TraceStyle()
        )

        with pytest.raises(IndexError, match="Port path .* exceeds matrix size"):
            _extract_s_parameter(s_params, trace)
