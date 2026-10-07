"""Chain parsing and publication contracts without simulated chemistry engines."""

import shutil
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest
from ase.build import molecule
from ase.io import write

from cochem_base.chain.chain import (
    Chain, ConvergenceFailureError, CorruptOutputError, MissingBinaryError, Stage,
    get_atomic_mass, get_atomic_masses_for_symbols, parse_orca_energy,
    parse_orca_hessian, parse_xtb_output, read_xyz, reanalyze_isotopologue,
)
from cochem_base.physics.isotopes import get_isotope_mass
from cochem_base.core_engine.execution_authority import RegistryAuthorityViolationError


@pytest.fixture
def seed(tmp_path):
    path = tmp_path / "seed.xyz"
    write(path, molecule("H2O"), format="xyz")
    return path


def _hessian_text(rows="0 1D0 0 0\n1 0 2D0 0\n2 0 0 3D0", header="0 1 2"):
    return f"$hessian\n3\n{header}\n{rows}\n$end\n"


def test_complete_hessian_accepts_fortran_exponents(tmp_path):
    path = tmp_path / "matrix.hess"
    path.write_text(_hessian_text())
    assert np.array_equal(parse_orca_hessian(path)["hessian"], np.diag([1, 2, 3]))


@pytest.mark.parametrize("text", [
    _hessian_text(header="0 0 2"),
    _hessian_text(rows="0 1 0 0\n0 0 2 0\n2 0 0 3"),
    _hessian_text(rows="0 1\n1 0\n2 0", header="0"),
    _hessian_text(rows="0 1 0 0\n1 0 2 0"),
    _hessian_text(rows="0 NaN 0 0\n1 0 2 0\n2 0 0 3"),
    _hessian_text(rows="0 1 1 0\n1 0 2 0\n2 0 0 3"),
    _hessian_text(rows="0 1 0 0 9\n1 0 2 0\n2 0 0 3"),
    _hessian_text().replace("$hessian\n3", "$hessian\n4"),
    _hessian_text().replace("$end", "$vibrational_frequencies\n3\n0 1\n0 2\n2 3"),
    _hessian_text().replace("$end", "$atoms\n2\nH 1 0 0 0\nH 1 0 0 1"),
    _hessian_text() + _hessian_text(),
    "$atoms\n1\nH 1 0 0 0\n$end\n",
])
def test_hessian_rejects_incomplete_or_corrupt_evidence(tmp_path, text):
    path = tmp_path / "invalid.hess"
    path.write_text(text)
    with pytest.raises(CorruptOutputError):
        parse_orca_hessian(path)


def test_unknown_isotopes_cannot_fall_back_to_average_mass():
    assert get_atomic_mass("C", 13) == get_isotope_mass("13C")
    with pytest.raises(ValueError):
        get_atomic_mass("C", 999)
    with pytest.raises(ValueError):
        get_atomic_masses_for_symbols(["C", "H"], [13])


def test_isotopologue_retains_soft_and_imaginary_vibrations():
    # Analytic two-mass spring; changing sign checks unstable modes, not a solver surrogate.
    geometry = np.array([[0., 0., 0.], [1., 0., 0.]])
    hessian = np.zeros((6, 6))
    hessian[0, 0] = hessian[3, 3] = 1e-6
    hessian[0, 3] = hessian[3, 0] = -1e-6
    for sign in (1, -1):
        result = reanalyze_isotopologue(sign * hessian, geometry, ["H", "H"], [1, 1], "analytic")
        frequencies = result["vibrational_frequencies_cm_inv"]
        assert len(frequencies) == 1
        assert 0 < sign * frequencies[0] < 20


def test_final_invalid_energy_does_not_reuse_previous_value(tmp_path):
    path = tmp_path / "stage.out"
    path.write_text("FINAL SINGLE POINT ENERGY -1D0\nFINAL SINGLE POINT ENERGY NaN\n")
    with pytest.raises(CorruptOutputError):
        parse_orca_energy(path)
    path.write_text("normal termination of xtb\nTOTAL ENERGY -1D0\n")
    assert parse_xtb_output(path)["converged"] is False


def test_dry_pipeline_records_decks_without_physical_publication(tmp_path, seed):
    chain = Chain(workdir=tmp_path / "campaign")
    records = chain.run_canonical_pipeline(seed, dry_run=True, include_ccsd=True)
    assert len(records) == 6
    assert all(record.exit_status == "DECK_GENERATED" and not record.converged for record in records)
    assert all(record.energy_hartree is None and record.geometry.size == 0 for record in records)
    assert not list(chain.workdir.glob("s?.xyz"))
    assert not list(chain.workdir.glob("*.out"))
    with h5py.File(chain.h5_path, "r") as campaign:
        assert len(campaign["chain"]) == 6
        assert all("geometry" not in group and "energy_hartree" not in group.attrs
                   for group in campaign["chain"].values())


def test_unregistered_interpreter_cannot_impersonate_orca(tmp_path, seed):
    chain = Chain(workdir=tmp_path / "campaign", orca_cmd=sys.executable,
                  registry_path=tmp_path / "absent-registry.json")
    with pytest.raises(RegistryAuthorityViolationError, match="authority denied"):
        chain.run_stage(Stage("failed", "r2SCAN-3c TightOpt"), seed)
    assert not chain.stage_records
    assert not (chain.workdir / "failed.xyz").exists()
    assert not (chain.workdir / "failed.err").exists()
    with h5py.File(chain.h5_path, "r") as campaign:
        assert not list(campaign["chain"])


def test_zero_exit_utility_cannot_bypass_registry_authority(tmp_path, seed):
    binary = shutil.which("true") or sys.executable
    chain = Chain(workdir=tmp_path / "campaign", orca_cmd=binary,
                  registry_path=tmp_path / "absent-registry.json")
    with pytest.raises(RegistryAuthorityViolationError, match="authority denied"):
        chain.run_stage(Stage("empty", "r2SCAN-3c TightOpt"), seed)
    assert not (chain.workdir / "empty.xyz").exists()
    assert not chain.stage_records


def test_canonical_chain_uses_principal_isotopes_and_staged_grids(tmp_path, seed):
    assert get_atomic_mass("C") == get_isotope_mass("C", 12)
    assert get_atomic_mass("N") == get_isotope_mass("N", 14)
    chain = Chain(workdir=tmp_path / "campaign")
    chain.run_canonical_pipeline(seed, dry_run=True, include_ccsd=True)
    for stage, grid in (("s2", 1), ("s3", 2), ("s4", 3), ("s5", 3), ("s6", 3)):
        text = (chain.workdir / f"{stage}.inp").read_text().upper()
        assert f"DEFGRID{grid}" in text
        assert all(f"DEFGRID{other}" not in text for other in (1, 2, 3) if other != grid)


@pytest.mark.parametrize("stage", [
    Stage("bad", "B3LYP def2-SVP TightOpt"),
    Stage("bad", "wB97M-V D3BJ def2-QZVPP TightOpt"),
    Stage("bad", "wB97M-V def2-QZVPP Freq DEFGRID1"),
    Stage("bad", "r2SCAN-3c TightOpt", blocks="%geom Calc_Hess true end"),
    Stage("bad", "r2SCAN-3c TightOpt", blocks="%pal nprocs 9999 end"),
    Stage("bad", "r2SCAN-3c TightOpt\n%maxcore 99999"),
    Stage("bad", "wB97M-V def2-QZVPP", product_class="A"),
    Stage("bad", "r2SCAN-3c TightOpt", counterpoise="full"),
])
def test_chain_cannot_bypass_scientific_deck_policy(tmp_path, seed, stage):
    chain = Chain(workdir=tmp_path / "campaign")
    with pytest.raises(Exception):
        chain.run_stage(stage, seed, dry_run=True)
    assert not chain.stage_records
    assert not (chain.workdir / "bad.inp").exists()


def test_seed_normalization_preserves_original_and_provenance(tmp_path, seed):
    import hashlib
    original = seed.read_bytes()
    chain = Chain(workdir=tmp_path / "campaign")
    chain.run_stage(Stage("normalized", "r2SCAN-3c TightOpt"), seed, dry_run=True)
    assert seed.read_bytes() == original
    symbols, coordinates, _ = read_xyz(chain.workdir / "normalized_input.xyz")
    assert np.linalg.norm(np.average(coordinates, axis=0, weights=get_atomic_masses_for_symbols(symbols))) < 1e-9
    import json
    provenance = json.loads((chain.workdir / "normalized.ingress.json").read_text())
    assert provenance["source_sha256"] == hashlib.sha256(original).hexdigest()


def test_compound_deck_uses_identical_stage_policy(tmp_path, seed):
    chain = Chain(workdir=tmp_path / "campaign")
    deck = chain.generate_compound_script([
        Stage("s2", "r2SCAN-3c TightOpt"),
        Stage("s3", "wB97X-V def2-TZVPP TightOpt", geom_from="s2", mo_from="s2", hess_from="s2"),
    ], seed)
    assert "DEFGRID1" in deck and "DEFGRID2" in deck
    assert '%base "s2"' in deck and '%base "s3"' in deck
    assert deck.count("%compound") == 1 and deck.rstrip().endswith("end")
    assert deck.count("%pal ") == deck.count("%maxcore ") == 1
    assert deck.index("%pal ") < deck.index("%compound") and deck.index("%maxcore ") < deck.index("%compound")
    assert deck.count("ConvCheckMode 0") == 2 and deck.count("ConvForced true") == 2
    for invalid in (Stage("bad", "B3LYP def2-SVP"),
                    Stage("bad", "r2SCAN-3c", blocks="%geom Calc_Hess true end")):
        with pytest.raises(Exception):
            chain.generate_compound_script([invalid], seed)


def test_chain_prepares_private_writable_copy_of_readonly_checkpoint(tmp_path, seed):
    """Opaque file transport only: this is not an electronic-structure fixture."""
    import hashlib
    import json
    import stat

    chain = Chain(workdir=tmp_path / "campaign")
    source = chain.workdir / "prior.gbw"
    original = b"Opaque bytes for the checkpoint copy/permission boundary only."
    source.write_bytes(original)
    source.chmod(0o444)
    chain.run_stage(Stage("consumer", "HF STO-3G TightSCF", mo_from="prior"), seed, dry_run=True)
    snapshot = chain.workdir / "consumer.moinp.gbw"
    assert source.read_bytes() == snapshot.read_bytes() == original
    assert not source.stat().st_mode & stat.S_IWUSR
    assert snapshot.stat().st_mode & stat.S_IWUSR
    assert '%moinp "consumer.moinp.gbw"' in (chain.workdir / "consumer.inp").read_text()
    evidence = json.loads((chain.workdir / "consumer.checkpoint_inputs.json").read_text())
    assert evidence["orbital_source_sha256"] == evidence["orbital_consumer_initial_sha256"] == hashlib.sha256(original).hexdigest()
    assert chain.stage_records["consumer"].converged is False


def test_direct_deck_builder_rejects_injected_and_empty_checkpoints(tmp_path, seed):
    chain = Chain(workdir=tmp_path / "campaign")
    local = chain.workdir / seed.name
    shutil.copyfile(seed, local)
    with pytest.raises(ValueError, match="filename"):
        chain.build_stage_input(Stage("safe", "r2SCAN-3c", mo_from='old"\n%maxcore 999'), local.name)
    (chain.workdir / "old.opt").touch()
    with pytest.raises(CorruptOutputError, match="empty"):
        chain.build_stage_input(Stage("safe", "r2SCAN-3c TightOpt", hess_from="old"), local.name)


def test_canonical_pipeline_preserves_seed_already_in_campaign(tmp_path):
    chain = Chain(workdir=tmp_path / "campaign")
    seed = chain.workdir / "original.xyz"
    write(seed, molecule("H2O"), format="xyz")
    original = seed.read_bytes()
    chain.run_canonical_pipeline(seed, dry_run=True)
    assert seed.read_bytes() == original


def test_standard_campaign_includes_real_emt_nitrogen_hessian(tmp_path):
    import time
    from ase.calculators.emt import EMT
    from ase.optimize import BFGS
    from ase.vibrations import Vibrations
    from cochem_base.chain.chain import StateRecord, BOHR_TO_ANGSTROM, HARTREE_TO_EV

    atoms = molecule("N2")
    atoms.calc = EMT()
    start = time.monotonic()
    optimizer = BFGS(atoms, logfile=None)
    reached = optimizer.run(fmax=1e-6, steps=100)
    assert reached
    vibrations = Vibrations(atoms, name=str(tmp_path / "vibrations"))
    vibrations.run()
    hessian = vibrations.get_vibrations().get_hessian_2d() * BOHR_TO_ANGSTROM**2 / HARTREE_TO_EV
    chain = Chain(workdir=tmp_path / "campaign")
    record = StateRecord(
        stage="emt_nitrogen", level="ASE EMT finite-difference Hessian", wall_s=time.monotonic()-start,
        energy_hartree=atoms.get_potential_energy()/HARTREE_TO_EV, symbols=atoms.get_chemical_symbols(),
        geometry=atoms.positions.copy(), hessian=hessian, converged=bool(reached), exit_status="SUCCESS",
    )
    chain.stage_records[record.stage] = record
    results = chain.run_standard_isotopologue_campaign(record.stage)
    assert set(results) == {"iso_15N_1", "iso_15N_2"}
    assert all(len(result["vibrational_frequencies_cm_inv"]) == 1 for result in results.values())


def test_missing_requested_xtb_stops_pipeline(tmp_path, seed):
    chain = Chain(workdir=tmp_path / "campaign", xtb_cmd=str(tmp_path / "missing-xtb"))
    with pytest.raises(MissingBinaryError, match="xTB"):
        chain.run_canonical_pipeline(seed)
    assert not (chain.workdir / "s1.xyz").exists()
    assert not (chain.workdir / "s2.inp").exists()
    assert not chain.stage_records


def test_chain_rejects_source_runtime_paths():
    repository = Path(__file__).resolve().parents[2]
    with pytest.raises(Exception, match="Air-Gap Violation"):
        Chain(workdir=repository / "forbidden_chain_output")
    assert not (repository / "forbidden_chain_output").exists()


def test_chain_rejects_unsafe_stage_names(tmp_path, seed):
    chain = Chain(workdir=tmp_path / "campaign")
    with pytest.raises(ValueError, match="filename"):
        chain.run_stage(Stage("../escape", "r2SCAN-3c TightOpt"), seed, dry_run=True)
    assert not (tmp_path / "escape.inp").exists()


def test_xyz_preserves_empty_comment_and_rejects_nonfinite_coordinates(tmp_path):
    path = tmp_path / "atom.xyz"
    path.write_text("1\n\nH 0 0 0\n")
    assert read_xyz(path)[0] == ["H"]
    path.write_text("1\n\nH NaN 0 0\n")
    with pytest.raises(ValueError, match="finite"):
        read_xyz(path)
