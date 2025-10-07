import numpy as np
import pytest

from snpviewer.backend.conversions import (abcd_to_s, calculate_group_delay, g_to_s,
                                           h_to_s, s_to_abcd, s_to_g, s_to_h, s_to_t,
                                           s_to_y, s_to_z, t_to_s, unwrap_phase, y_to_s,
                                           z_to_s)


def test_identity_network_yz_roundtrip():
    # S = 0 for a perfectly matched network; Z = Z0 * I, Y = (1/Z0) * I
    Z0 = 50.0
    N = 3
    n = 2
    s = np.zeros((N, n, n), dtype=complex)

    z = s_to_z(s, Z0)
    y = s_to_y(s, Z0)

    # z should be Z0 * I
    for k in range(N):
        assert np.allclose(z[k], Z0 * np.eye(n), rtol=1e-6, atol=0)
        assert np.allclose(y[k], (1.0 / Z0) * np.eye(n), rtol=1e-6, atol=0)


class TestSParameterConversions:
    """Test S-parameter to Z/Y parameter conversions."""

    def test_s_to_z_1_port(self) -> None:
        """Test S to Z conversion for 1-port network."""
        # Test data: S11 = 0.5 at Z0 = 50Ω
        s = np.array([[[0.5]]], dtype=complex)  # Shape: (1, 1, 1)
        z0 = 50.0

        # Expected: Z11 = Z0 * (1 + S11) / (1 - S11) = 50 * 1.5 / 0.5 = 150Ω
        expected_z = np.array([[[150.0]]], dtype=complex)

        result = s_to_z(s, z0)
        np.testing.assert_allclose(result, expected_z, rtol=1e-10)

    def test_s_to_z_2_port(self) -> None:
        """Test S to Z conversion for 2-port network."""
        # Simple test case with diagonal S-matrix
        s = np.array([[
            [0.2, 0.1],
            [0.1, 0.3]
        ]], dtype=complex)  # Shape: (1, 2, 2)
        z0 = 50.0

        result = s_to_z(s, z0)

        # Verify result shape and basic properties
        assert result.shape == (1, 2, 2)
        assert np.iscomplexobj(result)

        # Check reciprocity: Z12 should equal Z21
        np.testing.assert_allclose(result[0, 0, 1], result[0, 1, 0], rtol=1e-10)

    def test_s_to_y_1_port(self) -> None:
        """Test S to Y conversion for 1-port network."""
        s = np.array([[[0.5]]], dtype=complex)
        z0 = 50.0

        # Y = Z^-1, where Z = Z0 * (1 + S) / (1 - S)
        # For S11 = 0.5: Z11 = 150Ω, so Y11 = 1/150 = 0.00667 S
        expected_y = np.array([[[1/150.0]]], dtype=complex)

        result = s_to_y(s, z0)
        np.testing.assert_allclose(result, expected_y, rtol=1e-10)

    def test_z_to_s_roundtrip(self) -> None:
        """Test S→Z→S roundtrip conversion."""
        original_s = np.array([[
            [0.2 + 0.1j, 0.8 + 0.2j],
            [0.8 + 0.2j, 0.3 - 0.1j]
        ]], dtype=complex)
        z0 = 50.0

        # Convert S→Z→S
        z = s_to_z(original_s, z0)
        recovered_s = z_to_s(z, z0)

        np.testing.assert_allclose(recovered_s, original_s, rtol=1e-12)

    def test_y_to_s_roundtrip(self) -> None:
        """Test S→Y→S roundtrip conversion."""
        original_s = np.array([[
            [0.1 + 0.2j, 0.7 - 0.1j],
            [0.7 - 0.1j, 0.2 + 0.3j]
        ]], dtype=complex)
        z0 = 75.0

        # Convert S→Y→S
        y = s_to_y(original_s, z0)
        recovered_s = y_to_s(y, z0)

        np.testing.assert_allclose(recovered_s, original_s, rtol=1e-12)

    def test_conversion_broadcasting(self) -> None:
        """Test conversions work with multiple frequency points."""
        s = np.array([
            [[0.1, 0.8], [0.8, 0.2]],  # f1
            [[0.2, 0.7], [0.7, 0.3]],  # f2
            [[0.3, 0.6], [0.6, 0.4]]   # f3
        ], dtype=complex)
        z0 = 50.0

        z = s_to_z(s, z0)
        y = s_to_y(s, z0)

        assert z.shape == (3, 2, 2)
        assert y.shape == (3, 2, 2)

        # Verify reciprocity at all frequencies
        for i in range(3):
            np.testing.assert_allclose(z[i, 0, 1], z[i, 1, 0], rtol=1e-10)
            np.testing.assert_allclose(y[i, 0, 1], y[i, 1, 0], rtol=1e-10)


class TestGroupDelayCalculation:
    """Test group delay calculation from S-parameters."""

    def test_group_delay_linear_phase(self) -> None:
        """Test group delay for linear phase response."""
        # Create S11 with linear phase vs frequency
        frequencies = np.linspace(1e9, 2e9, 100)  # 1-2 GHz
        delay_sec = 1e-9  # 1 ns delay

        # S11 with constant magnitude, linear phase
        s11_phase = -2 * np.pi * frequencies * delay_sec
        s11 = 0.5 * np.exp(1j * s11_phase)
        s = s11.reshape(-1, 1, 1)  # Shape: (100, 1, 1)

        group_delay = calculate_group_delay(frequencies, s, port1=0, port2=0)

        # Expected group delay should be approximately constant at 1 ns
        expected_delay = np.full_like(frequencies, delay_sec)
        np.testing.assert_allclose(group_delay, expected_delay, rtol=0.1)

    def test_group_delay_2_port(self) -> None:
        """Test group delay calculation for 2-port S21."""
        frequencies = np.linspace(1e9, 3e9, 50)
        delay_sec = 0.5e-9  # 0.5 ns

        # Create S21 with linear phase (transmission delay)
        s21_phase = -2 * np.pi * frequencies * delay_sec
        s21 = 0.9 * np.exp(1j * s21_phase)  # High transmission

        # Build 2x2 S-matrix
        s = np.zeros((len(frequencies), 2, 2), dtype=complex)
        s[:, 1, 0] = s21  # S21
        s[:, 0, 1] = s21  # S12 (reciprocal)
        s[:, 0, 0] = 0.1  # S11 (small reflection)
        s[:, 1, 1] = 0.1  # S22 (small reflection)

        group_delay = calculate_group_delay(frequencies, s, port1=1, port2=0)

        expected_delay = np.full_like(frequencies, delay_sec)
        np.testing.assert_allclose(group_delay, expected_delay, rtol=0.1)

    def test_group_delay_edge_cases(self) -> None:
        """Test group delay with edge cases."""
        frequencies = np.array([1e9, 2e9])

        # Case 1: Constant phase (zero group delay)
        s = np.array([
            [[0.5 + 0.5j]],  # 45° phase
            [[0.5 + 0.5j]]   # Same phase
        ], dtype=complex)

        group_delay = calculate_group_delay(frequencies, s, port1=0, port2=0)
        np.testing.assert_allclose(group_delay, 0.0, atol=1e-12)


class TestPhaseUnwrapping:
    """Test phase unwrapping utilities."""

    def test_unwrap_phase_basic(self) -> None:
        """Test basic phase unwrapping."""
        # Create wrapped phase with discontinuities
        phase_wrapped = np.array([0.1, 0.2, 0.3, -3.0, -2.9, -2.8])  # Jump at index 3

        phase_unwrapped = unwrap_phase(phase_wrapped)

        # Should remove 2π jumps
        expected = np.array([0.1, 0.2, 0.3, 3.283, 3.383, 3.483])  # 2π added
        np.testing.assert_allclose(phase_unwrapped, expected, rtol=1e-3)

    def test_unwrap_phase_multiple_jumps(self) -> None:
        """Test unwrapping with multiple 2π jumps."""
        # Phase that wraps multiple times
        t = np.linspace(0, 4*np.pi, 100)
        phase_true = 3.0 * t  # Linear growth
        phase_wrapped = np.angle(np.exp(1j * phase_true))  # Wrapped to [-π, π]

        phase_unwrapped = unwrap_phase(phase_wrapped)

        # Should recover the original linear trend
        np.testing.assert_allclose(phase_unwrapped, phase_true, rtol=1e-10)


class TestTwoPortConversions:
    """Test 2-port matrix conversions (ABCD, h, g, T parameters)."""

    def test_s_to_abcd_conversion(self) -> None:
        """Test S-parameter to ABCD parameter conversion."""
        # Simple 2-port S-matrix
        s = np.array([[
            [0.1, 0.9],
            [0.9, 0.2]
        ]], dtype=complex)
        z0 = 50.0

        abcd = s_to_abcd(s, z0)

        assert abcd.shape == (1, 2, 2)

        # ABCD matrix should have det(ABCD) = 1 for reciprocal networks
        det_abcd = np.linalg.det(abcd[0])
        np.testing.assert_allclose(det_abcd, 1.0, rtol=1e-10)

    def test_abcd_to_s_roundtrip(self) -> None:
        """Test S→ABCD→S roundtrip conversion."""
        original_s = np.array([[
            [0.2 + 0.1j, 0.8 - 0.1j],
            [0.8 - 0.1j, 0.3 + 0.2j]
        ]], dtype=complex)
        z0 = 50.0

        abcd = s_to_abcd(original_s, z0)
        recovered_s = abcd_to_s(abcd, z0)

        np.testing.assert_allclose(recovered_s, original_s, rtol=1e-12)

    def test_h_parameter_conversions(self) -> None:
        """Test hybrid (h) parameter conversions."""
        s = np.array([[
            [0.1, 0.8],
            [0.8, 0.2]
        ]], dtype=complex)
        z0 = 50.0

        h = s_to_h(s, z0)
        recovered_s = h_to_s(h, z0)

        np.testing.assert_allclose(recovered_s, s, rtol=1e-12)

    def test_g_parameter_conversions(self) -> None:
        """Test inverse hybrid (g) parameter conversions."""
        s = np.array([[
            [0.15, 0.85],
            [0.85, 0.25]
        ]], dtype=complex)
        z0 = 50.0

        g = s_to_g(s, z0)
        recovered_s = g_to_s(g, z0)

        np.testing.assert_allclose(recovered_s, s, rtol=1e-12)

    def test_t_parameter_conversions(self) -> None:
        """Test transmission (T) parameter conversions."""
        s = np.array([[
            [0.1, 0.9],
            [0.8, 0.2]
        ]], dtype=complex)
        z0 = 50.0

        t = s_to_t(s, z0)
        recovered_s = t_to_s(t, z0)

        np.testing.assert_allclose(recovered_s, s, rtol=1e-12)

    def test_conversion_multiple_frequencies(self) -> None:
        """Test all conversions work with multiple frequency points."""
        s = np.array([
            [[0.1, 0.8], [0.8, 0.2]],  # f1
            [[0.2, 0.7], [0.7, 0.3]],  # f2
            [[0.3, 0.6], [0.6, 0.4]]   # f3
        ], dtype=complex)
        z0 = 50.0

        # Test all conversion roundtrips
        abcd = s_to_abcd(s, z0)
        assert abcd.shape == (3, 2, 2)
        np.testing.assert_allclose(abcd_to_s(abcd, z0), s, rtol=1e-12)

        h = s_to_h(s, z0)
        assert h.shape == (3, 2, 2)
        np.testing.assert_allclose(h_to_s(h, z0), s, rtol=1e-12)

        g = s_to_g(s, z0)
        assert g.shape == (3, 2, 2)
        np.testing.assert_allclose(g_to_s(g, z0), s, rtol=1e-12)

        t = s_to_t(s, z0)
        assert t.shape == (3, 2, 2)
        np.testing.assert_allclose(t_to_s(t, z0), s, rtol=1e-12)


class TestConversionErrors:
    """Test error handling in conversions."""

    def test_invalid_shapes(self) -> None:
        """Test error handling for invalid array shapes."""
        # Wrong shape for S-parameters
        s_bad = np.array([[0.1, 0.2]], dtype=complex)  # Should be (N, n, n)
        z0 = 50.0

        with pytest.raises(ValueError, match="shape"):
            s_to_z(s_bad, z0)

        with pytest.raises(ValueError, match="shape"):
            s_to_y(s_bad, z0)

    def test_non_square_matrices(self) -> None:
        """Test error for non-square S-matrices."""
        s_nonsquare = np.array([[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]], dtype=complex)
        z0 = 50.0

        with pytest.raises(ValueError, match="square"):
            s_to_z(s_nonsquare, z0)

    def test_singular_matrices(self) -> None:
        """Test handling of singular matrices in conversions."""
        # Create S-matrix that leads to singular Z-matrix
        s_singular = np.array([[[1.0, 0.0], [0.0, 1.0]]], dtype=complex)  # |S| = 1
        z0 = 50.0

        # This should raise an error or return inf/nan values
        with pytest.raises((ValueError, np.linalg.LinAlgError)):
            s_to_z(s_singular, z0)

    def test_group_delay_insufficient_points(self) -> None:
        """Test group delay calculation with too few frequency points."""
        frequencies = np.array([1e9])  # Only one point
        s = np.array([[[0.5]]], dtype=complex)

        with pytest.raises(ValueError, match="frequency points"):
            calculate_group_delay(frequencies, s, port1=0, port2=0)

    def test_port_index_validation(self) -> None:
        """Test validation of port indices."""
        frequencies = np.array([1e9, 2e9])
        s = np.array([[[0.1, 0.8], [0.8, 0.2]], [[0.2, 0.7], [0.7, 0.3]]], dtype=complex)

        # Invalid port indices
        with pytest.raises(IndexError):
            calculate_group_delay(frequencies, s, port1=2, port2=0)  # port1 >= n_ports

        with pytest.raises(IndexError):
            calculate_group_delay(frequencies, s, port1=0, port2=2)  # port2 >= n_ports


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])
