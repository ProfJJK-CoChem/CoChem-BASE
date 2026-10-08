"""Actual chemical structures and selected potentials never imply fake science.

RDKit creates/validates real Lewis graphs. ASE EMT evaluates actual copper-pair
forces; its empirical energies are explicitly not a quantum chemistry benchmark.
Unavailable scientific context and failed selected models are typed refusals.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from rdkit import Chem
from ase import Atoms
from ase.calculators.emt import EMT
from ase.calculators.lj import LennardJones
from ase.calculators.morse import MorsePotential

from cochem.topos.graph import TopologyGraph
from cochem.topos.resonance import ResonanceEnumerator, ResonanceStructure, ResonanceThermodynamicsUnavailableError
from cochem.topos.tautomer import TopologyInput, _build_rdkit_mol_from_topology
from cochem_base.topology.cochem_topos_wiggle import LightningQuenchError, execute_lightning_quench


def graph_from_smiles(smiles):
    molecule = Chem.MolFromSmiles(smiles)
    assert molecule is not None
    result = TopologyGraph()
    for atom in molecule.GetAtoms():
        result.add_chemical_node(atom.GetIdx(), atom.GetSymbol(), formal_charge=atom.GetFormalCharge(),
            hybridization=str(atom.GetHybridization()).lower(), in_ring=atom.IsInRing(), isotope=atom.GetIsotope())
    for bond in molecule.GetBonds():
        result.add_chemical_edge(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx(), bond_order=bond.GetBondTypeAsDouble(), aromatic=bond.GetIsAromatic(), in_ring=bond.IsInRing())
    return result


def copper_pair(distance):
    return Atoms("Cu2", positions=[[0, 0, 0], [distance, 0, 0]])


def test_general_resonance_retains_real_kekule_forms_without_isomer_populations():
    result = ResonanceEnumerator.enumerate(graph_from_smiles("c1ccccc1"))
    assert result.ensemble_size == 2
    assert result.acceptance_scope == "structural_enumeration_only" and result.scientific_execution_performed is False
    assert result.weights is None and result.temperature_k is None
    assert all(form.relative_energy_kcal is None and form.boltzmann_weight is None for form in result.structures)
    assert result.structures[0].bond_orders != result.structures[1].bond_orders


def test_resonance_temperature_and_guessed_numeric_weights_are_explicitly_refused():
    graph = graph_from_smiles("c1ccccc1")
    with pytest.raises(ResonanceThermodynamicsUnavailableError, match="not thermally occupied isomers"):
        ResonanceEnumerator.enumerate(graph, temperature_k=298.15)
    actual = ResonanceEnumerator.enumerate(graph).structures[0].model_dump()
    with pytest.raises(ValidationError):
        ResonanceStructure(**{**actual, "boltzmann_weight": .5})
    with pytest.raises(ValidationError):
        ResonanceStructure(**{**actual, "relative_energy_kcal": 1.0})


def test_structural_truncation_is_declared_instead_of_claiming_complete_coverage():
    result = ResonanceEnumerator.enumerate(graph_from_smiles("c1ccccc1"), max_structures=1)
    assert result.ensemble_size == 1 and result.enumeration_truncated is True


def test_tautomer_topology_preserves_exact_explicit_nuclear_label():
    source = TopologyInput(molecule_id="isotope-formaldehyde", elements=["13C", "O"], atomic_numbers=[6, 8], bonds=[(0, 1, 2.0)])
    assert source.masses[0] > 13.0
    molecule = _build_rdkit_mol_from_topology(source)
    assert molecule.GetAtomWithIdx(0).GetIsotope() == 13
    assert molecule.GetAtomWithIdx(1).GetIsotope() == 0


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


def test_tracked_source_and_checkout_aliases_expose_the_same_scientific_contract():
    root = Path(__file__).resolve().parents[2]
    for name in ("tautomer", "resonance"):
        assert (root / f"src/cochem/topos/{name}.py").read_bytes() == (root / f"cochem/topos/{name}.py").read_bytes()
