"""BASE's actual selected-potential admission and empirical-quench contracts.

ASE EMT evaluates actual copper-pair forces. Its empirical energies are explicitly
not a quantum chemistry benchmark. Unconfigured or failed models remain refusals.

The four Lewis-graph/isotope cases and their graph helper moved unchanged with
ownership to CoChem-TOPOS tests/v010/test_structural_ownership.py, verified at
commit eecff25b13343305a3f05310800503014667e80a. Their source/proof inventory is
.docs/evidence/structural-ownership-transfer-20261019.json in that repository.
BASE's five quench test bodies below are unchanged. Real wheel/sdist ownership
checks in test_module_package_ownership.py replace the retired alias-byte check;
BASE must not import a bundled TOPOS implementation to test canonical science.
"""
from __future__ import annotations

import numpy as np
import pytest
from ase import Atoms
from ase.calculators.emt import EMT
from ase.calculators.lj import LennardJones
from ase.calculators.morse import MorsePotential

from cochem_base.topology.cochem_topos_wiggle import LightningQuenchError, execute_lightning_quench


def copper_pair(distance):
    return Atoms("Cu2", positions=[[0, 0, 0], [distance, 0, 0]])


def test_unconfigured_potential_cannot_be_replaced_by_lennard_jones():
    left, right = copper_pair(2.1), copper_pair(2.3)
    original = left.positions.copy()
    with pytest.raises(LightningQuenchError, match="explicit supported potential"):
        execute_lightning_quench(left, right)
    assert left.calc is None and right.calc is None and np.array_equal(left.positions, original)


def test_requested_unreviewed_model_is_refused_without_model_substitution():
    with pytest.raises(LightningQuenchError, match="selected model has no audited"):
        execute_lightning_quench(copper_pair(2.1), copper_pair(2.3), calculator=MorsePotential())


def test_comparison_of_different_explicit_potential_parameters_is_refused():
    left, right = copper_pair(2.1), copper_pair(2.3)
    left.calc, right.calc = LennardJones(epsilon=.5), LennardJones(epsilon=.8)
    with pytest.raises(LightningQuenchError, match="same explicit potential"):
        execute_lightning_quench(left, right)


def test_actual_nonconverged_optimizer_cannot_return_an_optimized_geometry():
    left, right = copper_pair(2.7), copper_pair(2.8)
    original = left.positions.copy()
    with pytest.raises(LightningQuenchError, match="no relaxed geometry or substitute"):
        execute_lightning_quench(left, right, calculator=EMT(), max_steps=1, fmax_ev_angstrom=1e-10)
    assert np.array_equal(left.positions, original) and "cochem_quench" not in left.info


def test_genuine_explicit_emt_force_convergence_retains_exact_method_scope():
    left, right = copper_pair(2.1), copper_pair(2.3)
    left.calc, right.calc = EMT(), EMT()
    optimized_a, optimized_b, energy_a, energy_b = execute_lightning_quench(left, right)
    assert np.isfinite([energy_a, energy_b]).all()
    for atoms in (optimized_a, optimized_b):
        receipt = atoms.info["cochem_quench"]
        assert receipt["converged"] is True and receipt["maximum_force_ev_angstrom"] <= receipt["force_threshold_ev_angstrom"]
        assert receipt["potential"]["class"] == "EMT"
        assert receipt["potential"]["method_scope"] == "explicit_empirical_potential_not_quantum_chemistry"
        assert receipt["minimum_qualification"] == "not_performed"
        assert "InHess" not in atoms.info and "Calc_Hess" not in atoms.info
