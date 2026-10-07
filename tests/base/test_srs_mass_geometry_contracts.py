"""SRS Chunk 17 REQ-004/005/006/014 regressions using real ASE/EMT calculations.

EMT validates mass transformation and numerics here, not publication accuracy.
"""
from pathlib import Path

import numpy as np
import pytest
from ase.build import molecule
from ase.calculators.emt import EMT
from ase.optimize import BFGS
from ase.units import Bohr, Hartree
from ase.vibrations import Vibrations
from mendeleev import element

from cochem_base.analysis.mass_perturbation import compute_isotopologue_observables
from cochem_base.core.cochem_constants import C_ROT_MHZ_U_ANG2
from cochem_base.intake.conformer_deduplication import (
    ConformerCandidate, ConformerDeduplicator, are_duplicate_conformers,
    kabsch_quaternion_rmsd,
)
from cochem_base.physics.eckart_aligner import (
    align_coordinates, translate_to_center_of_mass, verify_eckart_residual,
)
from cochem_base.physics.isotopes import get_element_mass_and_abundance, get_isotope_mass
from cochem_base.spectroscopy.isotopologue import IsotopologueSpectroscopyEngine, get_nuclide_mass


@pytest.fixture(scope="module")
def water_calculation(tmp_path_factory):
    atoms = molecule("H2O")
    atoms.calc = EMT()
    assert BFGS(atoms, logfile=None).run(fmax=1e-8, steps=200)
    vibrations = Vibrations(atoms, name=str(tmp_path_factory.mktemp("water") / "vib"))
    vibrations.run()
    hessian = vibrations.get_vibrations().get_hessian_2d() * Bohr**2 / Hartree
    return atoms, hessian


def test_exact_spectral_masses_and_natural_abundance():
    for symbol in ("C", "O", "H"):
        isotopes = [i for i in element(symbol).isotopes if i.abundance]
        dominant = max(isotopes, key=lambda iso: iso.abundance)
        assert get_nuclide_mass(symbol) == dominant.mass
    oxygen18 = next(i for i in element("O").isotopes if i.mass_number == 18)
    mass, abundance, number = get_element_mass_and_abundance("18O")
    assert mass == oxygen18.mass
    assert abundance == oxygen18.abundance / 100
    assert number == element("O").atomic_number


@pytest.mark.parametrize("token, number", [("13C", 12), ("D", 1), ("C", 12.5), ("C", True), ("C", 0)])
def test_contradictory_or_noninteger_isotopes_are_rejected(token, number):
    with pytest.raises(ValueError):
        get_isotope_mass(token, number)


def test_projected_modes_reuse_real_electronic_hessian(water_calculation):
    atoms, hessian = water_calculation
    original = hessian.copy()
    engine = IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, hessian)
    parent = engine.compute_observables()
    heavy = engine.compute_observables({1: "D", 2: "D"})
    assert parent.rigid_mode_count == heavy.rigid_mode_count == 6
    assert len(parent.harmonic_frequencies_cm1) == len(heavy.harmonic_frequencies_cm1) == 3
    assert np.all(np.asarray(parent.harmonic_frequencies_cm1) > np.asarray(heavy.harmonic_frequencies_cm1))
    assert parent.B_0_MHz is None and parent.delta_B_vib_MHz is None
    assert "B_0" not in parent.provenance_tags
    assert parent.B_e_MHz * parent.I_b == pytest.approx(C_ROT_MHZ_U_ANG2)
    np.testing.assert_array_equal(hessian, original)
    alternate = compute_isotopologue_observables(hessian, atoms.positions, atoms.get_chemical_symbols(), {1: 2, 2: ("H", 2)})
    np.testing.assert_allclose(alternate.harmonic_frequencies_cm1, heavy.harmonic_frequencies_cm1)
    assert alternate.B_e_MHz == heavy.B_e_MHz


def test_projection_does_not_hide_imaginary_or_soft_modes(water_calculation):
    atoms, hessian = water_calculation
    # Algebraic sign/scale transformations test the spectral contract. They are
    # not represented as independent physical calculations or measured evidence.
    inverted = IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, -hessian)
    assert np.all(np.asarray(inverted.compute_observables().harmonic_frequencies_cm1) < 0)
    soft = IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, hessian * 1e-10)
    frequencies = soft.compute_observables().harmonic_frequencies_cm1
    assert len(frequencies) == 3 and np.all(np.asarray(frequencies) > 0)


def test_linear_molecule_keeps_one_vibrational_mode(tmp_path):
    atoms = molecule("H2")
    atoms.calc = EMT()
    assert BFGS(atoms, logfile=None).run(fmax=1e-8, steps=200)
    vibrations = Vibrations(atoms, name=str(tmp_path / "hydrogen"))
    vibrations.run()
    hessian = vibrations.get_vibrations().get_hessian_2d() * Bohr**2 / Hartree
    result = IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, hessian).compute_observables()
    assert result.rigid_mode_count == 5
    assert len(result.harmonic_frequencies_cm1) == 1
    assert result.harmonic_frequencies_cm1[0] > 0
    assert np.isinf(result.A_e_MHz)
    assert result.B_e_MHz == pytest.approx(result.C_e_MHz)


@pytest.mark.parametrize("replacement", [{0: "C"}, {3: "D"}, {-1: "D"}, {True: "D"}])
def test_isotope_substitution_requires_same_element_and_existing_atom(water_calculation, replacement):
    atoms, hessian = water_calculation
    engine = IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, hessian)
    with pytest.raises(ValueError):
        engine.compute_observables(replacement)


def test_hessian_validation_and_correction_provenance(water_calculation):
    atoms, hessian = water_calculation
    for invalid in (hessian[:3, :3], hessian * np.nan, np.triu(hessian)):
        with pytest.raises(ValueError, match="Hessian"):
            IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, invalid)
    engine = IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, hessian)
    with pytest.raises(ValueError, match="provenance"):
        engine.compute_observables(vibrational_corrections_mhz=(0, 0, 0))
    # Explicit zero is a caller-supplied harmonic approximation, with its own label.
    result = engine.compute_observables(vibrational_corrections_mhz=(0, 0, 0), correction_source="harmonic approximation: zero anharmonic correction")
    assert result.B_0_MHz == result.B_e_MHz
    assert result.vibrational_correction_source.startswith("harmonic approximation")


def _water_dimer():
    lines = (Path(__file__).parents[1] / "data/water_dimer.xyz").read_text().splitlines()[2:8]
    return [line.split()[0] for line in lines], np.array([[float(v) for v in line.split()[1:4]] for line in lines])


def test_conformer_sieve_is_invariant_to_atom_order_and_keeps_lowest_energy():
    symbols, coords = _water_dimer()
    permutation = [4, 0, 3, 1, 5, 2]
    rotation = np.array([[0.8, -0.6, 0], [0.6, 0.8, 0], [0, 0, 1]])
    reordered = coords[permutation] @ rotation + [7, 8, -4]
    lower = ConformerCandidate("lower", [symbols[i] for i in permutation], reordered, -1.00001)
    higher = ConformerCandidate("higher", symbols, coords, -1)
    assert ConformerDeduplicator().deduplicate([higher, lower]) == [lower]


def test_close_but_spectroscopically_distinct_conformers_survive():
    symbols, coords = _water_dimer()
    shifted = coords.copy()
    shifted[3:, 0] += 0.02
    assert kabsch_quaternion_rmsd(coords, shifted) < 0.08
    assert not are_duplicate_conformers(coords, symbols, shifted, symbols)


def test_stale_conformer_metadata_cannot_force_a_duplicate():
    symbols, coords = _water_dimer()
    separated = coords.copy()
    separated[3:, 0] += 0.02
    candidates = [ConformerCandidate("a", symbols, coords, -1, "forged", (1, 1, 1)),
                  ConformerCandidate("b", symbols, separated, -1, "forged", (1, 1, 1))]
    assert len(ConformerDeduplicator().deduplicate(candidates)) == 2


def test_eckart_gate_rejects_nan_in_batched_masses_and_residuals(water_calculation):
    atoms, _ = water_calculation
    masses = np.array([get_nuclide_mass(s) for s in atoms.get_chemical_symbols()])
    invalid = masses.copy()
    invalid[0] = np.nan
    with pytest.raises(ValueError):
        translate_to_center_of_mass(np.stack([atoms.positions, atoms.positions]), masses=invalid)
    with pytest.raises(ValueError):
        verify_eckart_residual(atoms.positions, atoms.positions * np.nan, masses)
    with pytest.raises(ValueError):
        translate_to_center_of_mass(atoms.positions, masses=masses, tol=np.nan)
    _, rotation, rmsd = align_coordinates(atoms.positions, atoms.positions + [1, 3, 4], masses=masses[:, None])
    assert rmsd < 1e-12
    assert np.linalg.det(rotation) == pytest.approx(1)


@pytest.mark.parametrize("text", ["", "ORCA job started", "{invalid", '{"success":false,"properties":{}}'])
def test_spectroscopic_parser_fails_closed_for_missing_or_failed_output(text):
    from cochem_base.analysis.output_parser import OutputParser
    with pytest.raises(ValueError):
        OutputParser().parse_text(text)


def test_spectroscopic_json_derives_inertia_after_parsing(water_calculation):
    import json
    from cochem_base.analysis.output_parser import OutputParser
    atoms, hessian = water_calculation
    physical = IsotopologueSpectroscopyEngine(atoms.get_chemical_symbols(), atoms.positions, hessian).compute_observables()
    payload = {"success": True, "provenance": {"creator": "ASE/EMT"}, "properties": {
        "rotational_constants": [physical.A_e_MHz, physical.B_e_MHz, physical.C_e_MHz],
    }}
    parsed = OutputParser().parse_text(json.dumps(payload))
    assert parsed.engine == "ASE/EMT"
    assert parsed.a_0 is None and parsed.delta_a_vib is None
    assert parsed.dipole_components is None and parsed.total_dipole is None
    assert parsed.inertial_defect == pytest.approx(physical.inertial_defect_amu_A2, abs=1e-12)
    assert sum(parsed.planar_moments) == pytest.approx((physical.I_a + physical.I_b + physical.I_c) / 2)


def test_ingestion_routes_share_spectroscopic_gate_and_lowest_energy_selection():
    from cochem_base.intake.cochem_stage2_ingestor import JiggleQuenchDeduplicator
    from cochem_base.intake.stage2_ingestor import Stage2PreFilter
    symbols, coords = _water_dimer()
    shifted = coords.copy()
    shifted[3:, 0] += 0.02
    conformers = [coords, coords + 7, shifted]
    names = ["high", "low", "spectrally_distinct"]
    energies = [1, 0, 2]
    canonical = JiggleQuenchDeduplicator().deduplicate(conformers, symbols, names, energies)
    assert canonical.unique_indices == [1, 2]
    assert canonical.cluster_assignments[0] == 1
    _, kept_names, summary = Stage2PreFilter().filter_ensemble(conformers, symbols, names, energies)
    assert kept_names == ["low", "spectrally_distinct"]
    assert summary.duplicate_rejected_count == 1


def test_registry_rejects_invented_mass_overrides():
    from cochem_base.cochem_core_registry_schema import EnvironmentSchema
    from pydantic import ValidationError
    with pytest.raises(ValidationError, match="Mendeleev"):
        EnvironmentSchema(isotopic_mass_13c=99)
    with pytest.raises(ValidationError, match="Mendeleev"):
        EnvironmentSchema(isotopic_masses={"18O": 99})
    mass = get_isotope_mass("18O")
    assert EnvironmentSchema(isotopic_masses={"18O": mass}).get_isotopic_mass("18O") == mass


def test_warm_mass_cache_cannot_bypass_isotope_number_validation():
    for resolver in (get_isotope_mass, get_nuclide_mass):
        assert resolver("H", 1) > 0
        for invalid in (True, 1.0):
            with pytest.raises(ValueError):
                resolver("H", invalid)
