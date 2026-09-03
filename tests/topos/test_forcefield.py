"""Physical acceptance tests for automated forcefield assignment (GAFF2 and OPLS-AA)."""

from __future__ import annotations

import pytest

from cochem.topos.exceptions import UnparameterizedAtomError
from cochem.topos.forcefield import (
    assign_forcefield_parameters,
    geometric_combine,
    lorentz_berthelot_combine,
)
from cochem.topos.models import ForceFieldAssignmentResult, NonBondedParameter


def test_forcefield_assignment_phenanthrene() -> None:
    """REQ-TOPOS-002: Verify RCB ring perception and GAFF2 aromatic typing on phenanthrene."""
    # Phenanthrene has 14 carbons: aromatic ring carbons 'ca' and fused bridgehead carbons 'cp'/'cq'
    result = assign_forcefield_parameters(smiles="C1=CC2=C(C=C1)C3=CC=CC=C3C=C2", forcefield="GAFF2")
    assert isinstance(result, ForceFieldAssignmentResult)
    assert len(result.atom_types) == 14
    # Check that fused bridgehead carbons are distinguished from standard peripheral aromatic carbons
    assert "ca" in result.atom_types
    assert any(t in ["cp", "cq"] for t in result.atom_types)
    assert len(result.non_bonded_parameters) == 14
    assert result.non_bonded_parameters[0].r_min_half_angstrom > 0.0
    assert result.energy_unit == "kcal/mol"
    assert result.distance_unit == "angstrom"


def test_forcefield_assignment_oplsaa() -> None:
    """REQ-TOPOS-002: Verify OPLS-AA parameterization and geometric mixing units."""
    result = assign_forcefield_parameters(smiles="c1ccccc1", forcefield="OPLS-AA")
    assert isinstance(result, ForceFieldAssignmentResult)
    assert result.forcefield_family == "OPLS-AA"
    assert result.energy_unit == "kJ/mol"
    assert result.distance_unit == "nanometer"
    assert len(result.atom_types) == 6
    assert all(t == "CA" for t in result.atom_types)
    assert result.non_bonded_parameters[0].sigma_nm > 0.0


def test_nonbonded_combination_rules() -> None:
    """REQ-TOPOS-002: Verify Lorentz-Berthelot and Geometric combination rules."""
    p1 = NonBondedParameter(
        atom_type="ca",
        sigma_nm=0.339967,
        epsilon_kj_mol=0.359824,
        r_min_half_angstrom=1.9080,
        epsilon_kcal_mol=0.0860,
    )
    p2 = NonBondedParameter(
        atom_type="ha",
        sigma_nm=0.259964,
        epsilon_kj_mol=0.062760,
        r_min_half_angstrom=1.4590,
        epsilon_kcal_mol=0.0150,
    )
    # Lorentz-Berthelot
    r_half_ij, eps_kcal_ij = lorentz_berthelot_combine(p1, p2)
    expected_r = 0.5 * (1.9080 + 1.4590)
    expected_eps = (0.0860 * 0.0150) ** 0.5
    assert abs(r_half_ij - expected_r) < 1e-4
    assert abs(eps_kcal_ij - expected_eps) < 1e-4

    # Geometric
    sig_ij, eps_kj_ij = geometric_combine(p1, p2)
    expected_sig = (0.339967 * 0.259964) ** 0.5
    expected_eps_kj = (0.359824 * 0.062760) ** 0.5
    assert abs(sig_ij - expected_sig) < 1e-4
    assert abs(eps_kj_ij - expected_eps_kj) < 1e-4


def test_unparameterized_metal_raises_error() -> None:
    """REQ-TOPOS-002: Verify UnparameterizedAtomError when encountering unparameterized metals."""
    with pytest.raises(UnparameterizedAtomError) as exc_info:
        assign_forcefield_parameters("C[Fe]C", forcefield="GAFF2")
    assert "unsupported metal" in str(exc_info.value)
    assert "1" in str(exc_info.value)
