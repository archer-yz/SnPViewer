"""
Unit tests for Touchstone parser implementation.

Tests all aspects of Touchstone file parsing including v1/v2 formats,
different data formats (DB/MA/RI), frequency units, reference impedance,
and n-port configurations.
"""
from pathlib import Path

import numpy as np
import pytest

from snpviewer.backend.parsing.touchstone import TouchstoneError, parse_touchstone


class TestTouchstoneParserV1:
    """Test Touchstone v1 format parsing."""

    def test_parse_s1p_basic(self, tmp_path: Path) -> None:
        """Test parsing basic 1-port S-parameter file."""
        s1p_content = """# Hz S RI R 50
        100 0.1 0.2
        200 0.2 0.3
        300 0.3 0.4
        """
        s1p_file = tmp_path / "test.s1p"
        s1p_file.write_text(s1p_content)

        result = parse_touchstone(str(s1p_file))

        assert result.n_ports == 1
        assert result.version == 'v1'
        assert result.data_format == 'RI'
        assert result.z0 == 50.0
        assert len(result.frequency_hz) == 3
        assert np.allclose(result.frequency_hz, [100, 200, 300])
        assert result.s_params.shape == (3, 1, 1)
        assert np.allclose(result.s_params[0, 0, 0], 0.1 + 0.2j)

    def test_parse_s2p_ri_format(self, tmp_path: Path) -> None:
        """Test parsing 2-port file with RI format."""
        s2p_content = """# MHz S RI R 75
        1.0 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8
        2.0 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9
        """
        s2p_file = tmp_path / "test.s2p"
        s2p_file.write_text(s2p_content)

        result = parse_touchstone(str(s2p_file))

        assert result.n_ports == 2
        assert result.data_format == 'RI'
        assert result.z0 == 75.0
        assert len(result.frequency_hz) == 2
        assert np.allclose(result.frequency_hz, [1e6, 2e6])  # MHz to Hz
        assert result.s_params.shape == (2, 2, 2)

        # Check S11 at first frequency
        assert np.allclose(result.s_params[0, 0, 0], 0.1 + 0.2j)
        # Check S21 at first frequency
        assert np.allclose(result.s_params[0, 1, 0], 0.3 + 0.4j)

    def test_parse_s2p_db_format(self, tmp_path: Path) -> None:
        """Test parsing 2-port file with DB format."""
        s2p_content = """# GHz S DB R 50
        0.1 -10 45 -20 90 -30 135 -40 180
        0.2 -11 50 -21 95 -31 140 -41 185
        """
        s2p_file = tmp_path / "test.s2p"
        s2p_file.write_text(s2p_content)

        result = parse_touchstone(str(s2p_file))

        assert result.n_ports == 2
        assert result.data_format == 'DB'
        assert result.z0 == 50.0
        assert len(result.frequency_hz) == 2
        assert np.allclose(result.frequency_hz, [0.1e9, 0.2e9])  # GHz to Hz

        # Check S11 at first frequency: -10dB @ 45° = 10^(-10/20) * e^(j*45°)
        expected_s11 = 10**(-10/20) * np.exp(1j * np.radians(45))
        assert np.allclose(result.s_params[0, 0, 0], expected_s11, rtol=1e-6)

    def test_parse_s2p_ma_format(self, tmp_path: Path) -> None:
        """Test parsing 2-port file with MA format."""
        s2p_content = """# kHz S MA R 100
        100 0.5 45 0.3 90 0.2 135 0.1 180
        200 0.6 50 0.4 95 0.3 140 0.2 185
        """
        s2p_file = tmp_path / "test.s2p"
        s2p_file.write_text(s2p_content)

        result = parse_touchstone(str(s2p_file))

        assert result.n_ports == 2
        assert result.data_format == 'MA'
        assert result.z0 == 100.0
        assert len(result.frequency_hz) == 2
        assert np.allclose(result.frequency_hz, [100e3, 200e3])  # kHz to Hz

        # Check S11 at first frequency: 0.5 @ 45°
        expected_s11 = 0.5 * np.exp(1j * np.radians(45))
        assert np.allclose(result.s_params[0, 0, 0], expected_s11, rtol=1e-6)

    def test_parse_s3p_format(self, tmp_path: Path) -> None:
        """Test parsing 3-port file."""
        s3p_content = """# Hz S RI R 50
        100 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 1.0 1.1 1.2 1.3 1.4 1.5 1.6 1.7 1.8
        """
        s3p_file = tmp_path / "test.s3p"
        s3p_file.write_text(s3p_content)

        result = parse_touchstone(str(s3p_file))

        assert result.n_ports == 3
        assert result.s_params.shape == (1, 3, 3)
        # S11 = 0.1 + 0.2j, S21 = 0.3 + 0.4j, S31 = 0.5 + 0.6j
        assert np.allclose(result.s_params[0, 0, 0], 0.1 + 0.2j)
        assert np.allclose(result.s_params[0, 1, 0], 0.3 + 0.4j)
        assert np.allclose(result.s_params[0, 2, 0], 0.5 + 0.6j)

    def test_parse_multiline_data(self, tmp_path: Path) -> None:
        """Test parsing data that spans multiple lines."""
        s2p_content = """# Hz S RI R 50
        100 0.1 0.2 0.3 0.4
            0.5 0.6 0.7 0.8
        200 0.2 0.3 0.4 0.5
            0.6 0.7 0.8 0.9
        """
        s2p_file = tmp_path / "test.s2p"
        s2p_file.write_text(s2p_content)

        result = parse_touchstone(str(s2p_file))

        assert result.n_ports == 2
        assert len(result.frequency_hz) == 2
        assert result.s_params.shape == (2, 2, 2)

    def test_parse_with_comments(self, tmp_path: Path) -> None:
        """Test parsing file with comments throughout."""
        s1p_content = """! This is a test file
        # Hz S RI R 50
        ! Frequency S11_real S11_imag
        100 0.1 0.2  ! First point
        200 0.2 0.3  ! Second point
        ! End of data
        """
        s1p_file = tmp_path / "test.s1p"
        s1p_file.write_text(s1p_content)

        result = parse_touchstone(str(s1p_file))

        assert result.n_ports == 1
        assert len(result.frequency_hz) == 2
        assert np.allclose(result.frequency_hz, [100, 200])

    def test_parse_different_frequency_units(self, tmp_path: Path) -> None:
        """Test parsing files with different frequency units."""
        units_test_cases = [
            ("Hz", 1.0),
            ("KHz", 1e3),
            ("MHz", 1e6),
            ("GHz", 1e9),
            ("THz", 1e12),
        ]

        for unit, multiplier in units_test_cases:
            s1p_content = f"""# {unit} S RI R 50
            1.0 0.1 0.2
            """
            s1p_file = tmp_path / f"test_{unit.lower()}.s1p"
            s1p_file.write_text(s1p_content)

            result = parse_touchstone(str(s1p_file))
            expected_freq = 1.0 * multiplier
            assert np.allclose(result.frequency_hz, [expected_freq])


class TestTouchstoneParserV2:
    """Test Touchstone v2 format parsing."""

    def test_parse_v2_basic(self, tmp_path: Path) -> None:
        """Test parsing basic v2 format file."""
        s2p_content = """[Version] 2.0
        [Number of Ports] 2
        [Two-Port Data Order] 21_12
        [Number of Frequencies] 2
        [Reference] 75.0
        [Matrix Format] Full
        [Mixed Mode Order] None
        [Begin Information]
        Test file for v2 format
        [End Information]
        # Hz S RI R 75
        100 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8
        200 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9
        """
        s2p_file = tmp_path / "test_v2.s2p"
        s2p_file.write_text(s2p_content)

        result = parse_touchstone(str(s2p_file))

        assert result.version == 'v2'
        assert result.n_ports == 2
        assert result.z0 == 75.0
        assert len(result.frequency_hz) == 2

    def test_parse_v2_with_keywords(self, tmp_path: Path) -> None:
        """Test parsing v2 file with keyword sections."""
        s1p_content = """[Version] 2.0
        [Number of Ports] 1
        [Begin Information]
        Manufacturer: Test Corp
        Model: Test Device
        [End Information]
        # MHz S DB R 50
        1000 -10 45
        2000 -11 50
        """
        s1p_file = tmp_path / "test_v2_keywords.s1p"
        s1p_file.write_text(s1p_content)

        result = parse_touchstone(str(s1p_file))

        assert result.version == 'v2'
        assert result.n_ports == 1
        assert result.data_format == 'DB'

    def test_parse_v2_matrix_formats(self, tmp_path: Path) -> None:
        """Test v2 matrix format parsing."""
        # Test with explicit matrix format
        s2p_content = """[Version] 2.0
        [Number of Ports] 2
        [Matrix Format] Full
        # Hz S RI R 50
        100 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8
        """
        s2p_file = tmp_path / "test_v2_matrix.s2p"
        s2p_file.write_text(s2p_content)

        result = parse_touchstone(str(s2p_file))
        assert result.version == 'v2'
        assert result.s_params.shape == (1, 2, 2)


class TestTouchstoneParserErrors:
    """Test error handling in Touchstone parser."""

    def test_nonexistent_file(self) -> None:
        """Test error when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            parse_touchstone("nonexistent.s2p")

    def test_invalid_extension(self, tmp_path: Path) -> None:
        """Test error for invalid file extension."""
        bad_file = tmp_path / "test.txt"
        bad_file.write_text("# Hz S RI R 50\n100 0.1 0.2")

        with pytest.raises(TouchstoneError, match="Invalid file extension"):
            parse_touchstone(str(bad_file))

    def test_missing_header(self, tmp_path: Path) -> None:
        """Test error when header line is missing."""
        s1p_content = """100 0.1 0.2
        200 0.2 0.3
        """
        s1p_file = tmp_path / "no_header.s1p"
        s1p_file.write_text(s1p_content)

        with pytest.raises(TouchstoneError, match="No valid header found"):
            parse_touchstone(str(s1p_file))

    def test_invalid_header_format(self, tmp_path: Path) -> None:
        """Test error for malformed header."""
        s1p_content = """# Hz S INVALID R 50
        100 0.1 0.2
        """
        s1p_file = tmp_path / "bad_header.s1p"
        s1p_file.write_text(s1p_content)

        with pytest.raises(TouchstoneError, match="Invalid data format"):
            parse_touchstone(str(s1p_file))

    def test_port_mismatch(self, tmp_path: Path) -> None:
        """Test error when port count doesn't match extension."""
        s1p_content = """# Hz S RI R 50
        100 0.1 0.2 0.3 0.4  # Too many values for S1P
        """
        s1p_file = tmp_path / "port_mismatch.s1p"
        s1p_file.write_text(s1p_content)

        with pytest.raises(TouchstoneError,
                           match="Data columns don't match expected count"):
            parse_touchstone(str(s1p_file))

    def test_insufficient_data(self, tmp_path: Path) -> None:
        """Test error when data line has too few values."""
        s1p_content = """# Hz S RI R 50
        100 0.1  # Missing imaginary part
        """
        s1p_file = tmp_path / "insufficient_data.s1p"
        s1p_file.write_text(s1p_content)

        with pytest.raises(TouchstoneError,
                           match="insufficient values|not enough values"):
            parse_touchstone(str(s1p_file))

    def test_invalid_numeric_data(self, tmp_path: Path) -> None:
        """Test error for non-numeric data."""
        s1p_content = """# Hz S RI R 50
        100 invalid 0.2
        """
        s1p_file = tmp_path / "invalid_numeric.s1p"
        s1p_file.write_text(s1p_content)

        with pytest.raises(TouchstoneError, match="Invalid numeric data"):
            parse_touchstone(str(s1p_file))

    def test_negative_reference_impedance(self, tmp_path: Path) -> None:
        """Test error for negative reference impedance."""
        s1p_content = """# Hz S RI R -50
        100 0.1 0.2
        """
        s1p_file = tmp_path / "negative_z0.s1p"
        s1p_file.write_text(s1p_content)

        with pytest.raises(TouchstoneError,
                           match="Reference impedance must be positive"):
            parse_touchstone(str(s1p_file))

    def test_unsupported_parameter_type(self, tmp_path: Path) -> None:
        """Test error for unsupported parameter types."""
        s1p_content = """# Hz Y RI R 50  # Y-parameters not supported in v1
        100 0.1 0.2
        """
        s1p_file = tmp_path / "unsupported_param.s1p"
        s1p_file.write_text(s1p_content)

        with pytest.raises(TouchstoneError,
                           match="Only S-parameters are supported"):
            parse_touchstone(str(s1p_file))

    def test_empty_file(self, tmp_path: Path) -> None:
        """Test error for empty file."""
        empty_file = tmp_path / "empty.s1p"
        empty_file.write_text("")

        with pytest.raises(TouchstoneError, match="Empty file"):
            parse_touchstone(str(empty_file))

    def test_v2_missing_required_keywords(self, tmp_path: Path) -> None:
        """Test error when v2 file is missing required keywords."""
        s2p_content = """[Version] 2.0
        # Missing [Number of Ports]
        # Hz S RI R 50
        100 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8
        """
        s2p_file = tmp_path / "v2_missing_keywords.s2p"
        s2p_file.write_text(s2p_content)

        with pytest.raises(TouchstoneError,
                           match="Missing required v2 keyword"):
            parse_touchstone(str(s2p_file))


class TestTouchstoneParserEdgeCases:
    """Test edge cases and corner cases."""

    def test_parse_very_large_file(self, tmp_path: Path) -> None:
        """Test parsing file with many frequency points."""
        # Generate 10000 frequency points
        frequencies = np.logspace(6, 10, 10000)  # 1 MHz to 10 GHz

        lines = ["# Hz S RI R 50"]
        for freq in frequencies:
            lines.append(f"{freq:.3e} 0.1 0.2")

        s1p_file = tmp_path / "large.s1p"
        s1p_file.write_text("\n".join(lines))

        result = parse_touchstone(str(s1p_file))
        assert len(result.frequency_hz) == 10000
        assert result.s_params.shape == (10000, 1, 1)

    def test_parse_mixed_whitespace(self, tmp_path: Path) -> None:
        """Test parsing with mixed tabs and spaces."""
        s1p_content = """# Hz S RI R 50
        100\t0.1\t0.2
        200   0.2   0.3
        300\t  0.3  \t0.4
        """
        s1p_file = tmp_path / "mixed_whitespace.s1p"
        s1p_file.write_text(s1p_content)

        result = parse_touchstone(str(s1p_file))
        assert len(result.frequency_hz) == 3

    def test_parse_scientific_notation(self, tmp_path: Path) -> None:
        """Test parsing data in scientific notation."""
        s1p_content = """# Hz S RI R 50
        1.0e2 1.0e-3 2.0e-3
        2.0e2 1.5e-3 2.5e-3
        """
        s1p_file = tmp_path / "scientific.s1p"
        s1p_file.write_text(s1p_content)

        result = parse_touchstone(str(s1p_file))
        assert np.allclose(result.frequency_hz, [100, 200])
        assert np.allclose(result.s_params[0, 0, 0], 1e-3 + 2e-3j)

    def test_parse_extreme_values(self, tmp_path: Path) -> None:
        """Test parsing with extreme numeric values."""
        s1p_content = """# Hz S RI R 50
        1 1e-15 1e15
        2 -1e15 -1e-15
        """
        s1p_file = tmp_path / "extreme_values.s1p"
        s1p_file.write_text(s1p_content)

        result = parse_touchstone(str(s1p_file))
        assert len(result.frequency_hz) == 2
        assert result.s_params.shape == (2, 1, 1)

    def test_parse_with_trailing_whitespace(self, tmp_path: Path) -> None:
        """Test parsing with trailing whitespace on lines."""
        s1p_content = """# Hz S RI R 50
        100 0.1 0.2
        200 0.2 0.3
        """
        s1p_file = tmp_path / "trailing_whitespace.s1p"
        s1p_file.write_text(s1p_content)

        result = parse_touchstone(str(s1p_file))
        assert len(result.frequency_hz) == 2
