"""CV compatibility helpers: algebra, candidate decks, ownership, and storage.

The committed ORCA observation is a genuine HF/STO-3G optimization/frequency
record with a byte-authenticated provenance file. Its replay establishes parser
behavior only. No test here establishes a native frozen-core/all-electron CV
protocol, scientific accuracy, or an alternative calculation executor.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import h5py
from mendeleev import element
import pytest

from cochem_base.bench_engine.cochem_bench_cv import (
    CoreValenceMapper, DualCorrelationEngine, DeltaExtractor,
    EphemeralScratchPurge, CVCorrectionError,
    CVExecutionError, CVParsingError, CVScratchPurgeError,
    commit_cv_to_hdf5, read_cv_from_hdf5, HARTREE_TO_KCAL_MOL,
)

# Illustrative starting coordinates for deck/data controls, not accepted minima.
WATER_COORDS = [("O", 0.0, 0.0, 0.117790), ("H", 0.0, 0.755453, -0.471161),
                ("H", 0.0, -0.755453, -0.471161)]
H2_COORDS = [("H", 0.0, 0.0, 0.370000), ("H", 0.0, 0.0, -0.370000)]
CO_COORDS = [("C", 0.0, 0.0, -0.645000), ("O", 0.0, 0.0, 0.485000)]
NATIVE_RECORD = Path(__file__).parent / "data" / "orca_6_1_1_water_hf_sto3g"


def _recorded_orca_observation() -> tuple[str, dict]:
    provenance = json.loads((NATIVE_RECORD / "provenance.json").read_text())
    data = (NATIVE_RECORD / "water.out.txt").read_bytes()
    entry = provenance["files"]["water.out.txt"]
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    assert len(data) == entry["bytes"]
    assert provenance["native_execution_status"] == "EXECUTION_VERIFIED"
    assert (provenance["method"], provenance["basis"]) == ("HF", "STO-3G")
    return data.decode(), provenance


def _principal_mass(symbol: str) -> float:
    measured = [isotope for isotope in element(symbol).isotopes
                if isotope.mass is not None and isotope.abundance is not None
                and isotope.abundance > 0]
    return float(max(measured, key=lambda isotope: isotope.abundance).mass)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file() and not path.is_symlink()}


def test_basis_set_mapping_cc_pv() -> None:
    mapper = CoreValenceMapper()
    for cardinality in ("D", "T", "Q", "5"):
        assert mapper.map_basis_set(f"cc-pV{cardinality}Z") == f"cc-pCV{cardinality}Z"


def test_basis_set_mapping_aug_cc_pv() -> None:
    mapper = CoreValenceMapper()
    for cardinality in ("D", "T", "Q", "5"):
        assert mapper.map_basis_set(f"aug-cc-pV{cardinality}Z") == f"aug-cc-pwCV{cardinality}Z"


def test_basis_set_mapping_def2_and_ano() -> None:
    for basis in ("def2-SVP", "def2-TZVP", "def2-QZVPP", "ano-pVTZ", "saug-ano-pVTZ"):
        assert CoreValenceMapper.map_basis_set(basis) == basis


def test_elemental_core_inspection_mendeleev() -> None:
    water_info = CoreValenceMapper.inspect_elemental_core(WATER_COORDS)
    assert water_info["has_core_electrons"] is True
    assert water_info["total_core_electrons"] == 2
    assert water_info["total_electrons"] == 10
    assert water_info["elements"] == ["O", "H"]
    expected_mass = _principal_mass("O") + 2 * _principal_mass("H")
    assert water_info["total_mass"] == pytest.approx(expected_mass, abs=1e-12)
    assert water_info["total_mass"] != float(element("O").mass) + 2 * float(element("H").mass)
    h2_info = CoreValenceMapper.inspect_elemental_core(H2_COORDS)
    assert h2_info["has_core_electrons"] is False
    assert h2_info["total_core_electrons"] == 0
    assert CoreValenceMapper.inspect_elemental_core(CO_COORDS)["total_core_electrons"] == 4


def test_elemental_core_preserves_ordered_explicit_nuclides() -> None:
    coordinates = [("Cl", 0., 0., 0.), ("C-13", 1., 0., 0.), ("D", 0., 1., 0.)]
    original = list(coordinates)
    record = CoreValenceMapper.inspect_elemental_core(coordinates)
    carbon13 = next(isotope.mass for isotope in element("C").isotopes if isotope.mass_number == 13)
    deuterium = next(isotope.mass for isotope in element("H").isotopes if isotope.mass_number == 2)
    masses = [_principal_mass("Cl"), float(carbon13), float(deuterium)]
    assert record["nuclear_identity"]["nuclides"] == ["Cl", "13C", "2H"]
    assert record["nuclear_identity"]["masses_u"] == pytest.approx(masses, abs=1e-12)
    assert record["nuclear_identity"]["mass_convention"] == "explicit_isotope_mass_else_principal_isotope_mass"
    assert record["total_mass"] == pytest.approx(sum(masses), abs=1e-12)
    assert record["elements"] == ["Cl", "C", "H"]
    assert coordinates == original


@pytest.mark.parametrize("label", ["999C", "Tc", "Gh"])
def test_elemental_core_refuses_unassigned_or_nonphysical_mass(label: str) -> None:
    with pytest.raises(ValueError):
        CoreValenceMapper.inspect_elemental_core([(label, 0., 0., 0.)])


def test_dual_correlation_engine_maxcore_calculation() -> None:
    assert DualCorrelationEngine(node_max_gb=16., nprocs=4, ram_safety_fraction=.75).calculate_maxcore_per_thread() == 3072


def test_dual_correlation_input_deck_generation() -> None:
    engine = DualCorrelationEngine(method="DLPNO-CCSD(T)", base_basis="aug-cc-pVQZ", node_max_gb=16., nprocs=4)
    decks = engine.generate_input_decks(WATER_COORDS, charge=-1, mult=2)
    assert decks["basis_set"] == "aug-cc-pwCVQZ"
    assert decks["original_basis"] == "aug-cc-pVQZ"
    assert "! DLPNO-CCSD(T) aug-cc-pwCVQZ" in decks["fc_input"]
    assert "NoFrozenCore" not in decks["fc_input"]
    assert "NoFrozenCore" in decks["ae_input"]
    for deck in (decks["fc_input"], decks["ae_input"]):
        assert "%maxcore 3072" in deck
        assert "%pal nprocs 4 end" in deck
        assert "* xyz -1 2" in deck
        coordinate_lines = deck.split("* xyz -1 2\n")[1].splitlines()[:3]
        assert [line.split()[0] for line in coordinate_lines] == [atom[0] for atom in WATER_COORDS]


def test_cuda_accelerator_environment_specification() -> None:
    before = dict(os.environ)
    assert DualCorrelationEngine().prepare_execution_env()["CUDA_VISIBLE_DEVICES"] == ""
    assert dict(os.environ) == before


def test_dual_correlation_input_file_writing(tmp_path: Path) -> None:
    decks = DualCorrelationEngine(base_basis="cc-pVTZ").generate_input_decks(WATER_COORDS, output_dir=tmp_path)
    assert (tmp_path / "orca_fc.inp").read_text() == decks["fc_input"]
    assert (tmp_path / "orca_ae.inp").read_text() == decks["ae_input"]


def test_parse_final_energy_from_recorded_native_stdout() -> None:
    text, provenance = _recorded_orca_observation()
    assert provenance["operation"] == "optimization_and_harmonic_frequencies"
    # This genuine optimization has six energy observations. The last belongs
    # to the accepted optimized geometry, not the starting-point observation.
    energy = DeltaExtractor.parse_final_energy_from_stdout(text)
    assert energy == -74.965901192193
    assert energy != -74.963063130292


def test_parse_final_energy_missing_raises() -> None:
    with pytest.raises(CVParsingError, match="FINAL SINGLE POINT ENERGY"):
        DeltaExtractor.parse_final_energy_from_stdout("")


def test_delta_extractor_mathematics() -> None:
    # Exact binary fractions are algebra inputs, not purported chemical results.
    result = DeltaExtractor.extract_delta(-1., -1.125, basis_set="algebra-only", method="algebra-only", node_id="difference")
    assert result.delta_e_cv_hartree == -.125
    assert result.delta_e_cv_kcal_mol == -.125 * HARTREE_TO_KCAL_MOL
    assert result.e_total_fc == -1.
    assert result.e_total_ae == -1.125


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf"), "-1.0"])
def test_delta_extractor_refuses_missing_or_nonfinite_observations(value) -> None:
    with pytest.raises(CVParsingError, match="finite real energies"):
        DeltaExtractor.extract_delta(value, -1.)
    with pytest.raises(CVParsingError, match="finite real energies"):
        DeltaExtractor.extract_delta(-1., value)


def test_extract_from_outputs_identical_native_observation_identity() -> None:
    text, provenance = _recorded_orca_observation()
    result = DeltaExtractor().extract_from_outputs(text, text, basis_set="STO-3G", method="HF",
                                                 metadata={"scope": "parser identity only", "observation": provenance})
    assert result.e_total_fc == result.e_total_ae == -74.965901192193
    assert result.delta_e_cv_hartree == 0.
    assert result.metadata["scope"] == "parser identity only"


def test_scratch_dir_creation_and_empty_retirement(tmp_path: Path) -> None:
    scratch = EphemeralScratchPurge.create_scratch_dir(tmp_path)
    assert scratch.is_dir()
    assert scratch.parent == tmp_path / "BENCH_Workspace" / "Scratch"
    assert scratch.name.startswith("job_")
    assert EphemeralScratchPurge.purge_scratch_dir(scratch)["directory_removed"] is True
    assert not scratch.exists()


def test_scratch_purge_only_owned_intermediates_preserves_inputs_results(tmp_path: Path) -> None:
    scratch = EphemeralScratchPurge.create_scratch_dir(tmp_path)
    outside = tmp_path / "student-results"
    outside.mkdir()
    (outside / "accepted.out").write_bytes(b"retained result bytes")
    for suffix in ("gbw", "tmp", "densities"):
        (scratch / f"calc.{suffix}").write_bytes(b"scratch control bytes")
    (scratch / "calc.inp").write_bytes(b"retained input bytes")
    (scratch / "calc.out").write_bytes(b"retained output bytes")
    before = _tree_bytes(outside)
    result = EphemeralScratchPurge.purge_scratch_dir(scratch)
    assert result["purged_count"] == 3
    assert result["directory_removed"] is False
    assert sorted(result["retained_files"]) == ["calc.inp", "calc.out"]
    assert (scratch / "calc.inp").read_bytes() == b"retained input bytes"
    assert (scratch / "calc.out").read_bytes() == b"retained output bytes"
    assert _tree_bytes(outside) == before


def test_scratch_foreign_directory_refused_with_byte_identity(tmp_path: Path) -> None:
    foreign = tmp_path / "student-runtime"
    foreign.mkdir()
    (foreign / "input.xyz").write_bytes(b"retained geometry")
    (foreign / "calc.gbw").write_bytes(b"retained accepted runtime data")
    before = _tree_bytes(foreign)
    with pytest.raises(CVScratchPurgeError, match="creator authority"):
        EphemeralScratchPurge.purge_scratch_dir(foreign)
    assert _tree_bytes(foreign) == before


def test_scratch_copied_marker_does_not_authorize_foreign_directory(tmp_path: Path) -> None:
    owned = EphemeralScratchPurge.create_scratch_dir(tmp_path)
    foreign = tmp_path / "foreign"
    shutil.copytree(owned, foreign)
    (foreign / "calc.tmp").write_bytes(b"foreign bytes")
    before = _tree_bytes(foreign)
    with pytest.raises(CVScratchPurgeError, match="creator authority"):
        EphemeralScratchPurge.purge_scratch_dir(foreign)
    assert _tree_bytes(foreign) == before


def test_scratch_replaced_directory_generation_refused(tmp_path: Path) -> None:
    owned = EphemeralScratchPurge.create_scratch_dir(tmp_path)
    original = owned.with_name("preserved-generation")
    owned.rename(original)
    shutil.copytree(original, owned)
    (owned / "calc.tmp").write_bytes(b"new generation bytes")
    before = _tree_bytes(tmp_path)
    with pytest.raises(CVScratchPurgeError, match="generation or ancestors changed"):
        EphemeralScratchPurge.purge_scratch_dir(owned)
    assert _tree_bytes(tmp_path) == before


def test_scratch_marker_tampering_refused_before_deletion(tmp_path: Path) -> None:
    owned = EphemeralScratchPurge.create_scratch_dir(tmp_path)
    (owned / ".cochem-cv-scratch-owner.json").write_bytes(b"changed authority")
    (owned / "calc.tmp").write_bytes(b"preserved intermediate")
    before = _tree_bytes(tmp_path)
    with pytest.raises(CVScratchPurgeError, match="marker changed"):
        EphemeralScratchPurge.purge_scratch_dir(owned)
    assert _tree_bytes(tmp_path) == before


@pytest.mark.skipif(not hasattr(os, "fork"), reason="This host has no process-fork primitive")
def test_scratch_fork_child_cannot_inherit_creator_authority(tmp_path: Path) -> None:
    before_environment = dict(os.environ)
    module = importlib.import_module("cochem_base.bench_engine.cochem_bench_cv")
    environment = dict(before_environment, PYTHONPATH=str(Path(module.__file__).parents[2]),
                       PYTHONDONTWRITEBYTECODE="1")
    code = """
import json, os, pathlib, sys
from cochem_base.bench_engine import cochem_bench_cv as module
assert pathlib.Path(module.__file__).resolve() == pathlib.Path(sys.argv[1]).resolve()
scratch = module.EphemeralScratchPurge.create_scratch_dir(sys.argv[2])
(scratch / 'calc.tmp').write_bytes(b'parent generation intermediate')
before = {p.name: p.read_bytes() for p in scratch.iterdir()}
creator = os.getpid()
read_fd, write_fd = os.pipe()
child = os.fork()
if child == 0:
    os.close(read_fd)
    try:
        module.EphemeralScratchPurge.purge_scratch_dir(scratch)
    except module.CVScratchPurgeError as error:
        os.write(write_fd, str(error).encode())
        os.close(write_fd)
        os._exit(0)
    os.close(write_fd)
    os._exit(1)
os.close(write_fd)
reason = os.read(read_fd, 4096).decode()
os.close(read_fd)
_, status = os.waitpid(child, 0)
assert os.waitstatus_to_exitcode(status) == 0
assert {p.name: p.read_bytes() for p in scratch.iterdir()} == before
retired = module.EphemeralScratchPurge.purge_scratch_dir(scratch)
print(json.dumps({'creator_pid': creator, 'child_pid': child, 'reason': reason,
                  'bytes_unchanged': True, 'parent_reclaimed': retired['directory_removed']}))
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, module.__file__, str(tmp_path)],
                            env=environment, capture_output=True, text=True, timeout=30, check=True)
    receipt = json.loads(result.stdout)
    assert receipt["creator_pid"] != receipt["child_pid"]
    assert "creating process generation" in receipt["reason"]
    assert receipt["bytes_unchanged"] is True
    assert receipt["parent_reclaimed"] is True
    assert dict(os.environ) == before_environment


def test_scratch_source_and_runtime_creation_refused() -> None:
    import sys
    for protected in (Path(__file__).parents[1], Path(sys.prefix)):
        with pytest.raises(CVScratchPurgeError):
            EphemeralScratchPurge.create_scratch_dir(protected)


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires a separate host privilege")
def test_scratch_symlink_member_refused_before_deletion(tmp_path: Path) -> None:
    owned = EphemeralScratchPurge.create_scratch_dir(tmp_path)
    foreign = tmp_path / "accepted-result"
    foreign.write_bytes(b"foreign result bytes")
    (owned / "calc.gbw").symlink_to(foreign)
    (owned / "calc.tmp").write_bytes(b"owned bytes remain on refusal")
    before = _tree_bytes(tmp_path)
    with pytest.raises(CVScratchPurgeError, match="contains a symlink"):
        EphemeralScratchPurge.purge_scratch_dir(owned)
    assert _tree_bytes(tmp_path) == before
    assert (owned / "calc.gbw").is_symlink()


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires a separate host privilege")
def test_scratch_symlink_ancestor_refused_before_creation(tmp_path: Path) -> None:
    destination = tmp_path / "actual-artifacts"
    destination.mkdir()
    alias = tmp_path / "artifact-alias"
    alias.symlink_to(destination, target_is_directory=True)
    with pytest.raises(CVScratchPurgeError, match="nonsymlink"):
        EphemeralScratchPurge.create_scratch_dir(alias)
    assert list(destination.iterdir()) == []


def test_hdf5_cv_helper_persistence_preserves_unrelated_group(tmp_path: Path) -> None:
    h5_file = tmp_path / "landscape.h5"
    with h5py.File(h5_file, "w") as output:
        output.create_dataset("unrelated_students/results", data=[1, 2, 3])
    result = DeltaExtractor.extract_delta(-1., -1.125, basis_set="algebra-only", method="algebra-only", node_id="difference")
    commit_cv_to_hdf5(h5_file, result)
    loaded = read_cv_from_hdf5(h5_file, "difference")
    assert loaded["e_total_fc"] == -1.
    assert loaded["e_total_ae"] == -1.125
    assert loaded["delta_e_cv_hartree"] == -.125
    assert loaded["delta_e_cv_kcal_mol"] == -.125 * HARTREE_TO_KCAL_MOL
    assert loaded["basis_set"] == "algebra-only"
    assert loaded["method"] == "algebra-only"
    with h5py.File(h5_file) as retained:
        assert retained["unrelated_students/results"][:].tolist() == [1, 2, 3]


def test_read_cv_from_hdf5_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_cv_from_hdf5(tmp_path / "missing_landscape.h5", "missing")


def test_hdf5_source_and_runtime_targets_refused_without_creation() -> None:
    result = DeltaExtractor.extract_delta(-1., -1.125, method="algebra-only")
    for protected in (Path(__file__).parents[1], Path(sys.prefix)):
        target = protected / "cv-refused-helper-test.h5"
        assert not target.exists()
        with pytest.raises(CVCorrectionError):
            commit_cv_to_hdf5(target, result)
        assert not target.exists()
        assert not target.with_name(target.name + ".lock").exists()


@pytest.mark.skipif(os.name == "nt", reason="Windows symlink creation requires a separate host privilege")
@pytest.mark.parametrize("redirection", ["target", "parent", "lock"])
def test_hdf5_symlink_redirection_refused_preserving_existing_bytes(tmp_path: Path, redirection: str) -> None:
    accepted = tmp_path / "accepted"
    accepted.mkdir()
    actual = accepted / "scientific-results.h5"
    with h5py.File(actual, "w") as output:
        output.create_dataset("retained-results", data=[1, 2, 3])
    if redirection == "target":
        target = tmp_path / "redirected.h5"
        target.symlink_to(actual)
    elif redirection == "parent":
        alias = tmp_path / "redirected-parent"
        alias.symlink_to(accepted, target_is_directory=True)
        target = alias / "new-results.h5"
    else:
        target = tmp_path / "new-results.h5"
        target.with_name(target.name + ".lock").symlink_to(actual)
    before = _tree_bytes(tmp_path)
    result = DeltaExtractor.extract_delta(-1., -1.125, method="algebra-only")
    with pytest.raises(CVCorrectionError, match="nonsymlink"):
        commit_cv_to_hdf5(target, result)
    assert _tree_bytes(tmp_path) == before


def test_hdf5_absent_authority_does_not_guess_current_directory(tmp_path: Path) -> None:
    before_environment = dict(os.environ)
    module = importlib.import_module("cochem_base.bench_engine.cochem_bench_cv")
    environment = dict(before_environment, PYTHONPATH=str(Path(module.__file__).parents[2]),
                       PYTHONDONTWRITEBYTECODE="1")
    environment.pop("COCHEM_ARTIFACTS_DIR", None)
    environment.pop("COCHEM_ARTIFACT_DIR", None)
    code = """
import json, pathlib, sys
from cochem_base.bench_engine import cochem_bench_cv as module
assert pathlib.Path(module.__file__).resolve() == pathlib.Path(sys.argv[1]).resolve()
try:
    module.resolve_hdf5_path()
except module.CVCorrectionError as error:
    print(json.dumps({'refused': True, 'reason': str(error)}))
else:
    raise AssertionError('Missing authority was accepted')
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, module.__file__], cwd=tmp_path,
                            env=environment, capture_output=True, text=True, timeout=30, check=True)
    assert json.loads(result.stdout)["refused"] is True
    assert list(tmp_path.iterdir()) == []
    assert dict(os.environ) == before_environment


def test_canonical_cv_public_interface_has_no_alternative_executor() -> None:
    module = importlib.import_module("cochem_base.bench_engine.cochem_bench_cv")
    package = importlib.import_module("cochem_base.bench_engine")
    assert package.CoreValenceMapper is module.CoreValenceMapper
    assert package.DualCorrelationEngine is module.DualCorrelationEngine
    assert not hasattr(module, "run_cv_pipeline")
    assert not hasattr(package, "run_cv_pipeline")
    assert not hasattr(module.DualCorrelationEngine, "execute_job")
    assert not hasattr(module.DualCorrelationEngine, "execute_dual_sp")
    assert issubclass(CVExecutionError, CVCorrectionError)
    assert issubclass(CVParsingError, CVCorrectionError)
    assert issubclass(CVScratchPurgeError, CVCorrectionError)


def test_canonical_bench_context_preserves_optional_engine_alias(tmp_path: Path) -> None:
    """Data-model compatibility only; this context authorizes no execution."""
    from cochem_base.bench_engine.cochem_bench_ingest import (
        BenchConfigSchema, BenchHardwareSchema, BenchRunContext,
    )
    configuration = BenchConfigSchema(hardware=BenchHardwareSchema(ram_gb=16., cpu_physical_cores=4))
    context = BenchRunContext(
        config_hash=hashlib.sha256(configuration.model_dump_json().encode()).hexdigest(),
        safe_maxcore_mb=3072, target_mpi_threads=4, node_id="datamodel-only",
        timestamp="2026-10-08T00:00:00Z", orca_path=None,
        hdf5_path=tmp_path / "landscape.h5", scratch_path=tmp_path / "scratch",
        numa_nodes=1, resource_warning=False, config=configuration,
    )
    assert context.orca_binary_path is context.orca_path is None
    assert context.config is configuration
    assert context.hdf5_path == tmp_path / "landscape.h5"


def test_scratch_dir_creation_with_actual_environment(tmp_path: Path) -> None:
    parent_before = dict(os.environ)
    module = importlib.import_module("cochem_base.bench_engine.cochem_bench_cv")
    environment = dict(parent_before, COCHEM_ARTIFACTS_DIR=str(tmp_path),
                       PYTHONPATH=str(Path(module.__file__).parents[2]), PYTHONDONTWRITEBYTECODE="1")
    code = """
import json, pathlib, sys
from cochem_base.bench_engine import cochem_bench_cv as module
assert pathlib.Path(module.__file__).resolve() == pathlib.Path(sys.argv[1]).resolve()
scratch = module.EphemeralScratchPurge.create_scratch_dir()
result = module.EphemeralScratchPurge.purge_scratch_dir(scratch)
print(json.dumps({'scratch': str(scratch), 'removed': result['directory_removed']}))
"""
    result = subprocess.run([sys.executable, "-B", "-c", code, module.__file__],
                            env=environment, capture_output=True, text=True, timeout=30, check=True)
    receipt = json.loads(result.stdout)
    scratch = Path(receipt["scratch"])
    assert scratch.parent == tmp_path / "BENCH_Workspace" / "Scratch"
    assert receipt["removed"] is True
    assert not scratch.exists()
    assert dict(os.environ) == parent_before
