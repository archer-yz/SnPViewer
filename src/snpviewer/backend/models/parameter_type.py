"""
Parameter type definitions for S-parameter analysis.

Defines the types of parameters that can be measured and converted
in RF circuit analysis (S, Z, Y, H, G, T, ABCD parameters).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ParameterDomain(Enum):
    """
    Measurement domain for parameters.

    Defines whether parameters are measured in frequency or time domain.
    """
    FREQUENCY = "frequency"
    TIME = "time"


class ParameterFormat(Enum):
    """
    Data format for parameter representation.

    Defines how complex parameter data is stored and displayed.
    """
    MAGNITUDE_ANGLE = "MA"  # Magnitude and angle (degrees)
    DECIBEL_ANGLE = "DB"    # Magnitude in dB and angle (degrees)
    REAL_IMAGINARY = "RI"   # Real and imaginary parts


class ParameterFamily(Enum):
    """
    Family of parameter types.

    Groups related parameter types together for conversion purposes.
    """
    SCATTERING = "S"    # Scattering parameters
    IMPEDANCE = "Z"     # Impedance parameters
    ADMITTANCE = "Y"    # Admittance parameters
    HYBRID_H = "H"      # Hybrid-H parameters
    HYBRID_G = "G"      # Hybrid-G parameters
    TRANSMISSION = "T"  # Transmission parameters
    ABCD = "ABCD"       # ABCD (chain) parameters


@dataclass
class ParameterSpec:
    """
    Specification for a parameter measurement.

    Defines what parameter is being measured and how it should be
    interpreted in terms of port relationships and normalization.

    Attributes:
        row: Output port number (1-based)
        col: Input port number (1-based)
        family: Parameter family (S, Z, Y, etc.)
        normalization: Reference impedance or admittance for normalization
        description: Human-readable description of parameter
    """
    row: int
    col: int
    family: ParameterFamily
    normalization: Optional[float] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate parameter specification after initialization."""
        if self.row < 1 or self.col < 1:
            raise ValueError("Port numbers must be >= 1")

        if self.description is None:
            self.description = f"{self.family.value}{self.row}{self.col}"

    def get_parameter_name(self) -> str:
        """
        Get standard parameter name.

        Returns:
            Standard parameter name (e.g., "S11", "Z21")
        """
        return f"{self.family.value}{self.row}{self.col}"

    def is_reflection(self) -> bool:
        """
        Check if this is a reflection parameter.

        Returns:
            True if row == col (diagonal parameter)
        """
        return self.row == self.col

    def is_transmission(self) -> bool:
        """
        Check if this is a transmission parameter.

        Returns:
            True if row != col (off-diagonal parameter)
        """
        return self.row != self.col

    def get_port_pair(self) -> Tuple[int, int]:
        """
        Get the port pair for this parameter.

        Returns:
            Tuple of (output_port, input_port)
        """
        return (self.row, self.col)

    def to_dict(self) -> Dict[str, Any]:
        """Convert parameter spec to dictionary for serialization."""
        return {
            'row': self.row,
            'col': self.col,
            'family': self.family.value,
            'normalization': self.normalization,
            'description': self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ParameterSpec:
        """Create parameter spec from dictionary for deserialization."""
        return cls(
            row=data['row'],
            col=data['col'],
            family=ParameterFamily(data['family']),
            normalization=data.get('normalization'),
            description=data.get('description')
        )


@dataclass
class ParameterType:
    """
    Complete definition of a parameter type for measurement and analysis.

    Combines parameter specification with format and domain information
    to fully define how parameter data should be interpreted and processed.

    Attributes:
        spec: Parameter specification (ports, family, normalization)
        format: Data format (MA, DB, RI)
        domain: Measurement domain (frequency, time)
        units: Physical units for the parameter values
        reference_impedance: Reference impedance for S-parameters (Ohms)
        reference_admittance: Reference admittance for Y-parameters (Siemens)
    """
    spec: ParameterSpec
    format: ParameterFormat = ParameterFormat.MAGNITUDE_ANGLE
    domain: ParameterDomain = ParameterDomain.FREQUENCY
    units: Optional[str] = None
    reference_impedance: float = 50.0
    reference_admittance: Optional[float] = None

    def __post_init__(self) -> None:
        """Set default units and reference values after initialization."""
        if self.units is None:
            self.units = self._get_default_units()

        if self.reference_admittance is None:
            self.reference_admittance = 1.0 / self.reference_impedance

    def _get_default_units(self) -> str:
        """
        Get default units for this parameter type.

        Returns:
            Default units string
        """
        if self.spec.family == ParameterFamily.SCATTERING:
            return "dimensionless"
        elif self.spec.family == ParameterFamily.IMPEDANCE:
            return "Ohms"
        elif self.spec.family == ParameterFamily.ADMITTANCE:
            return "Siemens"
        elif self.spec.family in [ParameterFamily.HYBRID_H, ParameterFamily.HYBRID_G]:
            # Hybrid parameters have mixed units depending on position
            if self.spec.is_reflection():
                return (
                    "dimensionless" if self.spec.family == ParameterFamily.HYBRID_H
                    else "Siemens"
                )
            else:
                return "Ohms" if self.spec.family == ParameterFamily.HYBRID_H else "dimensionless"
        elif self.spec.family in [ParameterFamily.TRANSMISSION, ParameterFamily.ABCD]:
            return "dimensionless"
        else:
            return "unknown"

    def get_display_name(self) -> str:
        """
        Get display name for this parameter type.

        Returns:
            Human readable parameter name
        """
        base_name = self.spec.get_parameter_name()

        if self.format == ParameterFormat.DECIBEL_ANGLE:
            if "magnitude" in base_name.lower():
                return f"|{base_name}| (dB)"
            else:
                return f"{base_name} (dB)"
        elif self.format == ParameterFormat.MAGNITUDE_ANGLE:
            return f"|{base_name}|"
        else:  # Real/Imaginary
            return base_name

    def is_compatible_with(self, other: ParameterType) -> bool:
        """
        Check if this parameter type is compatible with another for operations.

        Args:
            other: Other parameter type to check compatibility

        Returns:
            True if parameters are compatible for mathematical operations
        """
        # Same family and format are always compatible
        if (self.spec.family == other.spec.family and
            self.format == other.format and
                self.domain == other.domain):
            return True

        # S-parameters with different reference impedances need conversion
        if (self.spec.family == ParameterFamily.SCATTERING and
            other.spec.family == ParameterFamily.SCATTERING and
                abs(self.reference_impedance - other.reference_impedance) > 1e-6):
            return False  # Need impedance renormalization

        return False

    def requires_conversion_to(self, target: ParameterType) -> bool:
        """
        Check if conversion is required to match target parameter type.

        Args:
            target: Target parameter type

        Returns:
            True if conversion is needed
        """
        return not self.is_compatible_with(target)

    def get_conversion_path(self, target: ParameterType) -> List[str]:
        """
        Get the conversion path required to transform to target type.

        Args:
            target: Target parameter type

        Returns:
            List of conversion steps required
        """
        path = []

        # Format conversion
        if self.format != target.format:
            path.append(f"format_{self.format.value}_to_{target.format.value}")

        # Family conversion
        if self.spec.family != target.spec.family:
            path.append(f"family_{self.spec.family.value}_to_{target.spec.family.value}")

        # Reference impedance renormalization for S-parameters
        if (self.spec.family == ParameterFamily.SCATTERING and
            target.spec.family == ParameterFamily.SCATTERING and
                abs(self.reference_impedance - target.reference_impedance) > 1e-6):
            path.append(f"renormalize_{self.reference_impedance}_to_{target.reference_impedance}")

        return path

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert parameter type to dictionary for serialization.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            'spec': self.spec.to_dict(),
            'format': self.format.value,
            'domain': self.domain.value,
            'units': self.units,
            'reference_impedance': self.reference_impedance,
            'reference_admittance': self.reference_admittance
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ParameterType:
        """
        Create parameter type from dictionary for deserialization.

        Args:
            data: Dictionary representation from JSON

        Returns:
            Reconstructed ParameterType instance
        """
        return cls(
            spec=ParameterSpec.from_dict(data['spec']),
            format=ParameterFormat(data.get('format', 'MA')),
            domain=ParameterDomain(data.get('domain', 'frequency')),
            units=data.get('units'),
            reference_impedance=data.get('reference_impedance', 50.0),
            reference_admittance=data.get('reference_admittance')
        )

    @classmethod
    def create_s_parameter(cls, row: int, col: int,
                           format: ParameterFormat = ParameterFormat.MAGNITUDE_ANGLE,
                           reference_impedance: float = 50.0) -> ParameterType:
        """
        Create an S-parameter type.

        Args:
            row: Output port number (1-based)
            col: Input port number (1-based)
            format: Data format (MA, DB, RI)
            reference_impedance: Reference impedance in Ohms

        Returns:
            S-parameter type instance
        """
        spec = ParameterSpec(row=row, col=col, family=ParameterFamily.SCATTERING)
        return cls(spec=spec, format=format, reference_impedance=reference_impedance)

    @classmethod
    def create_z_parameter(
        cls, row: int, col: int,
        format: ParameterFormat = ParameterFormat.MAGNITUDE_ANGLE
    ) -> ParameterType:
        """
        Create a Z-parameter type.

        Args:
            row: Output port number (1-based)
            col: Input port number (1-based)
            format: Data format (MA, DB, RI)

        Returns:
            Z-parameter type instance
        """
        spec = ParameterSpec(row=row, col=col, family=ParameterFamily.IMPEDANCE)
        return cls(spec=spec, format=format)

    @classmethod
    def create_y_parameter(
        cls, row: int, col: int,
        format: ParameterFormat = ParameterFormat.MAGNITUDE_ANGLE
    ) -> ParameterType:
        """
        Create a Y-parameter type.

        Args:
            row: Output port number (1-based)
            col: Input port number (1-based)
            format: Data format (MA, DB, RI)

        Returns:
            Y-parameter type instance
        """
        spec = ParameterSpec(row=row, col=col, family=ParameterFamily.ADMITTANCE)
        return cls(spec=spec, format=format)
