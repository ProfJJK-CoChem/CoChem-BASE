"""CoChem-TORQ: Torsional and Machine Learning Potential Backbones and Calculators."""

from __future__ import annotations

from cochem.torq.backbones import (
    BesselBasis,
    CartesianEquivariantBackbone,
    CFConv,
    DifferentiableObservables,
    EquivariantInteractionBlock,
    GaussianSmearing,
    MACEBackbone,
    NequIPWrapper,
    RadialBasis,
    SchNetBackbone,
    SchNetFallbackRouter,
    polynomial_cutoff,
    real_spherical_harmonics,
)
from cochem.torq.calculators import TORQCalculator
from cochem.torq.constants import (
    ANGSTROM_TO_METER,
    BOHR_TO_ANGSTROM,
    DEBYE_PER_EAA,
    EV_PER_ANGSTROM_TO_NEWTON,
    EV_PER_ANGSTROM3_TO_GPA,
    EV_TO_JOULE,
    HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM,
    HARTREE_TO_EV,
)
from cochem.torq.errors import (
    AutogradForceError,
    CoChemError,
    EquivarianceViolationError,
    ObservableComputationError,
    PeriodicBoundaryConditionError,
    TorqDeviceAllocationError,
    TorqError,
    TorqModelBackboneError,
    TorqPersistenceLockError,
)
from cochem.torq.models import (
    AtomicConfigurationInput,
    HDF5PersistenceConfig,
    ObservableOutput,
    PotentialEnergyOutput,
    TorqModelConfig,
)
from cochem.torq.storage import HDF5TorqStorage
from cochem.torq.utils import get_monoisotopic_masses

__all__ = [
    # Errors
    "CoChemError",
    "TorqError",
    "TorqModelBackboneError",
    "EquivarianceViolationError",
    "AutogradForceError",
    "ObservableComputationError",
    "TorqPersistenceLockError",
    "TorqDeviceAllocationError",
    "PeriodicBoundaryConditionError",
    # Schemas
    "TorqModelConfig",
    "AtomicConfigurationInput",
    "PotentialEnergyOutput",
    "ObservableOutput",
    "HDF5PersistenceConfig",
    # Constants
    "HARTREE_TO_EV",
    "BOHR_TO_ANGSTROM",
    "HARTREE_PER_BOHR_TO_EV_PER_ANGSTROM",
    "DEBYE_PER_EAA",
    "EV_TO_JOULE",
    "ANGSTROM_TO_METER",
    "EV_PER_ANGSTROM_TO_NEWTON",
    "EV_PER_ANGSTROM3_TO_GPA",
    # Utils
    "get_monoisotopic_masses",
    # Backbones
    "polynomial_cutoff",
    "real_spherical_harmonics",
    "RadialBasis",
    "GaussianSmearing",
    "BesselBasis",
    "CFConv",
    "SchNetBackbone",
    "SchNetFallbackRouter",
    "CartesianEquivariantBackbone",
    "EquivariantInteractionBlock",
    "MACEBackbone",
    "NequIPWrapper",
    "DifferentiableObservables",
    # Calculators
    "TORQCalculator",
    # Storage
    "HDF5TorqStorage",
]
