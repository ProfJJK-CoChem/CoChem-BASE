"""Inspect real release artifacts for the BASE/canonical-provider boundary."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def release_artifacts(tmp_path_factory):
    root = Path(__file__).resolve().parents[2]
    work = tmp_path_factory.mktemp("base-release-ownership")
    source = work / "source"
    shutil.copytree(
        root,
        source,
        ignore=shutil.ignore_patterns(
            ".git",
            "build",
            "dist",
            "*.egg-info",
            "__pycache__",
            ".pytest_cache",
            ".venv",
        ),
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not any(
            word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY")
        )
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(work / "dist"),
            str(source),
        ],
        cwd=work,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    return work / "dist"


def test_base_wheel_does_not_publish_canonical_module_namespaces(release_artifacts):
    (wheel,) = release_artifacts.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())
    foreign = ("cochem_topos/", "cochem_torq/", "cochem/topos/", "cochem/torq/", "Libraries/")
    assert not sorted(name for name in members if name.startswith(foreign))
    for owned in (
        "cochem_base/intake/structure_formats.py",
        "cochem_base/intake/conformer_engine.py",
        "cochem_base/intake/conformer_deduplication.py",
        "cochem_base/geometry/nuclide_geometry.py",
        "scripts/manage_modules.py",
        "scripts/module_adapter_torq.py",
        "cochem_base/data/cochem_base_pes_store.py",
        "cochem_base/ml/krr.py",
        "cochem_base/ml/active_learning.py",
        "cochem_base/ml/_legacy_api.py",
        "cochem_base/core/scratch.py",
        "cochem_base/core_engine/cochem_core_auto_pes.py",
    ):
        assert owned in members


def test_base_source_distribution_excludes_obsolete_provider_copies(release_artifacts):
    (bundle,) = release_artifacts.glob("*.tar.gz")
    with tarfile.open(bundle) as archive:
        members = {name.partition("/")[2] for name in archive.getnames()}
    foreign = (
        "cochem_topos/",
        "src/cochem_torq/",
        "cochem/topos/",
        "src/cochem/topos/",
        "cochem/torq/",
        "Libraries/",
    )
    assert not sorted(name for name in members if name.startswith(foreign))
    assert "src/cochem_base/intake/conformer_engine.py" in members


def test_supported_base_ml_exports_keep_their_actual_implementation_identity():
    """Actual imports/configuration only; no model/native accuracy is asserted."""
    import importlib

    from cochem_base.core_engine.cochem_core_auto_pes import (
        ActiveLearningEngine,
        ExactKernelRidgeEstimator,
        NeuralCommitteeEstimator,
    )
    from cochem_base.data import PESStore
    from cochem_base.data.cochem_base_pes_store import PESStore as GuardedStore
    from cochem_base.ml import active_learning, krr

    assert PESStore is GuardedStore
    assert active_learning.ActiveLearningEngine is ActiveLearningEngine
    assert krr.KernelRidgeModel is ExactKernelRidgeEstimator
    assert krr.ExactKernelRidgeEstimator is ExactKernelRidgeEstimator
    assert NeuralCommitteeEstimator.__module__ == "cochem_base.core_engine.cochem_core_auto_pes"
    expected = {
        "cochem_base.ml": [
            "ExactKernelRidgeEstimator",
            "ActiveLearningEngine",
            "ActiveLearningManager",
            "ConformalCalibrationConfig",
            "DeltaMLDispersionConfig",
        ],
        "cochem_base.ml.baselines": ["DeltaMLDispersionConfig"],
        "cochem_base.ml.conformal": ["ConformalCalibrationConfig", "ConformalCalibrationError"],
        "cochem.ml.active_learning": ["ActiveLearningEngine", "ActiveLearningBatchConfig"],
        "cochem.ml.models": [
            "ExactKernelRidgeEstimator",
            "ForceMatchingLossConfig",
            "KrrRegularizationConfig",
        ],
        "cochem.ml.delta": ["DeltaMLDispersionConfig"],
        "cochem.ml.conformal": ["ConformalCalibrationConfig", "ConformalCalibrationError"],
    }
    for module_name, names in expected.items():
        module = importlib.import_module(module_name)
        assert all(name in module.__all__ for name in names)
        # Every advertised export must resolve without activating a TORQ object.
        for name in module.__all__:
            assert getattr(module, name) is not None
        unknown = "not_a_real_export"
        with pytest.raises(AttributeError, match="not_a_real_export"):
            getattr(module, unknown)
    assert (
        importlib.import_module("cochem.ml.models").ExactKernelRidgeEstimator
        is ExactKernelRidgeEstimator
    )
    assert not any(name == "Libraries" or name.startswith("Libraries.") for name in sys.modules)


@pytest.mark.parametrize(
    "module_name,names",
    [
        (
            "cochem_base.ml.baselines",
            [
                "BaselinePhysicsEngine",
                "DeltaMLEngine",
                "EMTBaselineEngine",
                "GFN2xTBEngine",
                "LennardJonesBaselineEngine",
                "PM6Engine",
                "UnitHarmonizer",
                "DispersionD3Layer",
                "DispersionD3Config",
                "compute_coordination_numbers",
            ],
        ),
        (
            "cochem_base.ml.conformal",
            [
                "CalibrationSample",
                "ConformalPredictor",
                "ConformalPredictorConfig",
                "ConformalInterval",
            ],
        ),
        (
            "cochem.ml.models",
            [
                "ANI2xModel",
                "ForceMatchingLoss",
                "compute_conservative_forces",
                "huber_force_loss",
                "huber_scalar_loss",
                "compute_angular_cosine_similarity",
                "cosine_cutoff_envelope",
                "quintic_c2_envelope",
            ],
        ),
    ],
)
def test_known_retired_scientific_names_explain_the_missing_contract(module_name, names):
    import importlib

    module = importlib.import_module(module_name)
    for name in names:
        assert name not in module.__all__
        with pytest.raises(ImportError, match="canonical TORQ has no verified managed") as failure:
            getattr(module, name)
        assert module_name + "." + name in str(failure.value)
    assert not any(name == "Libraries" or name.startswith("Libraries.") for name in sys.modules)


def test_scratch_compatibility_keeps_locking_and_refuses_retired_object_exports():
    import cochem.concurrency as concurrency
    from cochem.concurrency.atomic_file_lock import AtomicFileLock

    assert concurrency.AtomicFileLock is AtomicFileLock
    for name in ("EphemeralScratchSession", "resolve_hpc_safe_scratch"):
        with pytest.raises(ImportError, match="Stage 0 evidence"):
            getattr(concurrency, name)
    unknown = "not_a_real_export"
    with pytest.raises(AttributeError):
        getattr(concurrency, unknown)


def test_missing_scratch_authority_does_not_create_a_fallback_or_registry(tmp_path):
    from cochem_base.core.scratch import ScratchAuthorityError, admit_scratch

    missing = tmp_path / "never-created" / "cochem_system_config.json"
    before = tuple(tmp_path.iterdir())
    with pytest.raises(ScratchAuthorityError, match="Golden Registry is missing"):
        admit_scratch(missing)
    assert tuple(tmp_path.iterdir()) == before


@pytest.mark.parametrize(
    "flags",
    [
        ["-T", "2"],
        ["--T", "2"],
        ["--xnam", "/unrequested/xtb"],
        ["--gfn1"],
        ["--gff"],
        ["--gfn2//gfnff"],
        ["--ewin", "0.1"],
        ["--legacy"],
        ["--chrg", "1"],
        ["--uhf", "0"],
        ["--alpb", "water"],
        ["--gfn2=1"],
        ["--nci; echo wrong"],
        "--gfn2",
        "",
        False,
        0,
        (),
    ],
)
def test_crest_legacy_flags_cannot_override_the_bound_engine_or_resources(flags):
    from cochem_base.exceptions import EcosystemDependencyError
    from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine

    with pytest.raises(EcosystemDependencyError, match="no argument was silently dropped"):
        CRESTConformerEngine._validated_crest_flags(flags)


def test_crest_actual_caller_flags_and_default_are_preserved():
    from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine

    assert CRESTConformerEngine._validated_crest_flags(None) == [
        "--nci",
        "--nocross",
        "--noreftopo",
    ]
    actual_frontend_flags = ["--gfn2", "--nci", "--noreftopo"]
    original = list(actual_frontend_flags)
    assert CRESTConformerEngine._validated_crest_flags(actual_frontend_flags) == original
    assert actual_frontend_flags == original


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"charge": 0},
        {"multiplicity": 1},
        {"charge": 1, "multiplicity": 1},
        {"charge": 0, "multiplicity": 2},
        {"charge": False, "multiplicity": 1},
        {"charge": 0, "multiplicity": True},
        {"charge": 0.0, "multiplicity": 1},
        {"charge": 0, "multiplicity": 1, "net_charge": 1},
        {"charge": 0, "multiplicity": 1, "uhf": 2},
        {"charge": 0, "multiplicity": 1, "spin": 1},
        {"charge": 0, "multiplicity": 1, "unpaired_electrons": 1},
        {"charge": 0, "multiplicity": 1, "open_shell": True},
        {"charge": 0, "multiplicity": 1, "open_shell": None},
        {"charge": 0, "multiplicity": 1, "electronic_state": {"charge": 1, "multiplicity": 1}},
        {
            "charge": 0,
            "multiplicity": 1,
            "requested_electronic_state": {"charge": 0, "multiplicity": 1, "unpaired_electrons": 2},
        },
    ],
)
def test_crest_missing_other_or_conflicting_state_refuses_before_authority_or_calculation(state):
    from ase import Atoms
    from ase.calculators.emt import EMT

    from cochem_base.exceptions import EcosystemDependencyError
    from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine, TopologyCrusher

    seed = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.96], [0.93, 0.0, -0.24]])
    seed.info.update(state)
    # This actual empirical calculator would fill its cache if evaluated. It is
    # not a test double; neither geometry nor energy is evaluated by this guard.
    seed.calc = EMT()
    before = dict(seed.info)
    with pytest.raises(EcosystemDependencyError):
        CRESTConformerEngine().execute_secondary_search(seed)
    assert seed.calc.results == {} and seed.info == before
    with pytest.raises(EcosystemDependencyError):
        TopologyCrusher().deduplicate_ensemble_union(seed)
    assert seed.calc.results == {} and seed.info == before


def test_crest_explicit_state_request_and_ase_conflicts_are_not_defaulted_or_inferred():
    from ase import Atoms

    from cochem_base.exceptions import EcosystemDependencyError
    from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine

    seed = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.96], [0.93, 0.0, -0.24]])
    seed.set_initial_charges([0.0, 0.0, 0.0])
    seed.set_initial_magnetic_moments([0.0, 0.0, 0.0])
    with pytest.raises(EcosystemDependencyError, match="explicit ASE"):
        CRESTConformerEngine._requested_crest_state(seed)
    seed.info.update(charge=0, multiplicity=1, uhf=0)
    request = CRESTConformerEngine._requested_crest_state(seed)
    assert request["charge"] == 0 and request["multiplicity"] == 1
    assert request["unpaired_electrons"] == 0 and request["ground_state_status"] == "unverified"
    assert "requested neutral singlet" in request["profile_assumption"]
    seed.set_initial_charges([1.0, 0.0, 0.0])
    with pytest.raises(EcosystemDependencyError, match="atomic charges conflict"):
        CRESTConformerEngine._requested_crest_state(seed)
    seed.set_initial_charges([0.0, 0.0, 0.0])
    seed.set_initial_magnetic_moments([1.0, 0.0, 0.0])
    with pytest.raises(EcosystemDependencyError, match="magnetic moments conflict"):
        CRESTConformerEngine._requested_crest_state(seed)


def test_own_scratch_creation_preserves_neighbors_and_has_no_cleanup_authority(tmp_path):
    """Physical child-allocation contract only, not constructed Stage 0/engine authority."""
    from cochem_base.core.scratch import (
        ScratchAdmission,
        ScratchAuthorityError,
        _create_owned_crest_directory,
    )

    parent = tmp_path / "owned-data-scratch"
    parent.mkdir()
    neighbor = parent / "retained-neighbor.xyz"
    neighbor.write_bytes(b"Original user file; no scientific energy asserted.\n")
    # The private primitive verifies filesystem ownership only. Public admission
    # separately refuses this caller-constructed value without actual Stage 0.
    admission = ScratchAdmission(parent, (), tmp_path / "missing-registry", parent)
    with pytest.raises(ScratchAuthorityError, match="Golden Registry is missing"):
        admission.create_operation_directory("crest")
    with _create_owned_crest_directory(parent, parent) as child:
        assert (
            child.path.is_dir()
            and child.path.parent == parent
            and child.path.name.startswith("crest_")
        )
        assert os.fstat(child.fd).st_mode & 0o777 == 0o700
        child.verify()
        assert neighbor.read_bytes() == b"Original user file; no scientific energy asserted.\n"
        with pytest.raises(ScratchAuthorityError, match="only the owned CREST"):
            admission.create_operation_directory("unrelated")
        assert child.path.is_dir() and neighbor.is_file()
    outside = tmp_path / "outside-permission"
    outside.mkdir()
    with pytest.raises(ScratchAuthorityError, match="no longer available"):
        _create_owned_crest_directory(outside, parent)


def test_actual_phase_report_integrity_never_substitutes_for_complete_stage0(tmp_path):
    """Real phase-6 filesystem audit plus corruption copies; no full setup is fabricated."""
    import copy
    import hashlib
    import json

    from ci_tools.source_quarantine import source_paths
    from cochem_base.core.scratch import (
        ScratchAuthorityError,
        _canonical_report_digest,
        _read_phase_report,
        admit_scratch,
    )

    registry = tmp_path / "actual-partial-setup" / "Registry"
    registry.mkdir(parents=True)
    project = registry.parent
    scratch = project / "Scratch"
    scratch.mkdir()
    source = Path(__file__).resolve().parents[2]
    environment = {
        name: value for name, value in os.environ.items() if not name.startswith("SLURM_")
    }
    environment.update(
        PYTHONPATH=os.pathsep.join(source_paths(source)),
        PYTHONDONTWRITEBYTECODE="1",
        COCHEM_ARTIFACT_DIR=str(project),
        COCHEM_ARTIFACTS=str(project),
        COCHEM_DATABASE_DIR=str(project / "Databases"),
        COCHEM_SCRATCH_DIR=str(scratch),
        TMPDIR=str(scratch),
        COCHEM_CONFIG=str(registry / "cochem_system_config.json"),
    )
    program = """
import json, os, pathlib, sys
source=pathlib.Path(sys.argv[2]).resolve()
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
 startup=sys.modules.get('sitecustomize')
 assert startup is not None and pathlib.Path(startup.__file__).resolve()==source/'ci_tools/quarantine_startup/sitecustomize.py'
 guard=sys.modules['ci_tools.source_quarantine']
 assert pathlib.Path(guard.__file__).resolve()==source/'ci_tools/source_quarantine.py'
 assert guard._active is not None and guard._active['copied']==source
 assert guard._active['original']==pathlib.Path(os.environ['COCHEM_SOURCE_QUARANTINE_ORIGINAL']).resolve()
 assert guard._active['revision']==os.environ['COCHEM_SOURCE_QUARANTINE_REVISION']
import cochem_base.cli as cli
assert pathlib.Path(cli.__file__).resolve()==source/'src/cochem_base/cli.py'
success,status,report=cli.execute_phase(6,output_dir=sys.argv[1],min_disk_space_gb=1)
pathlib.Path(sys.argv[1],'actual-cli-phase6-result.json').write_text(json.dumps({'success':success,'status':status,'report':report}))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", program, str(registry), str(source)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    outcome = json.loads((registry / "actual-cli-phase6-result.json").read_text())
    success, status, report = outcome["success"], outcome["status"], outcome["report"]
    assert success and status == report["status"]
    assert Path(report["storage_paths"]["databases_directory"]) == project / "Databases"
    assert Path(report["storage_paths"]["scratch_directory"]) == scratch
    original = Path(report["artifact_path"])
    original_bytes = original.read_bytes()
    digest = _canonical_report_digest(report)
    verified = _read_phase_report(report, 6, digest, status)
    assert verified["sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert verified["canonical_report_sha256"] == digest
    assert verified["cli_execution_time_sec"] == report["execution_time_sec"]
    assert (
        verified["serialization_transform"]
        == "cochem.base.execute-phase.execution-time-enrichment/1"
    )
    assert "execution_time_sec" not in json.loads(original_bytes)
    for invalid_timing in (None, True, "unmeasured", -1):
        invalid = copy.deepcopy(report)
        invalid["execution_time_sec"] = invalid_timing
        with pytest.raises(ScratchAuthorityError, match="finite nonnegative measured CLI timing"):
            _read_phase_report(invalid, 6, _canonical_report_digest(invalid), status)
    changed = copy.deepcopy(report)
    changed["storage_paths"]["scratch_directory"] = str(tmp_path / "wrong-scratch")
    with pytest.raises(ScratchAuthorityError, match="published Stage 0 authority"):
        _read_phase_report(changed, 6, digest, status)
    # A separately declared integrity input tests retained-file corruption;
    # this is not a registry or evidence of an executed complete Stage 0.
    copy_path = tmp_path / "report-integrity-copy.json"
    copied = copy.deepcopy(report)
    copied["artifact_path"] = str(copy_path)
    copy_digest = _canonical_report_digest(copied)
    damaged = copy.deepcopy(copied)
    damaged["storage_paths"]["scratch_directory"] = str(tmp_path / "wrong-scratch")
    del damaged["execution_time_sec"]
    copy_path.write_text(json.dumps(damaged))
    with pytest.raises(ScratchAuthorityError, match="retained report changed"):
        _read_phase_report(copied, 6, copy_digest, status)
    for field_path in (
        ("storage_paths", "is_git_ignored"),
        ("archive_audit", "filters_applied", "compression_opts"),
    ):
        # Mutate only an explicitly identified copy of actual phase-6 output.
        # Both substitutions compare equal in Python but differ as JSON types.
        typed_copy_path = tmp_path / ("type-corrupted-" + field_path[-1] + ".json")
        embedded = copy.deepcopy(report)
        embedded["artifact_path"] = str(typed_copy_path)
        altered_raw = {
            key: copy.deepcopy(value)
            for key, value in embedded.items()
            if key != "execution_time_sec"
        }
        target = altered_raw
        for field in field_path[:-1]:
            target = target[field]
        observed = target[field_path[-1]]
        assert type(observed) in (bool, int)
        target[field_path[-1]] = int(observed) if type(observed) is bool else float(observed)
        assert target[field_path[-1]] == observed and type(target[field_path[-1]]) is not type(
            observed
        )
        typed_copy_path.write_text(json.dumps(altered_raw))
        with pytest.raises(ScratchAuthorityError, match="retained report changed"):
            _read_phase_report(embedded, 6, _canonical_report_digest(embedded), status)
    assert original.read_bytes() == original_bytes
    redirected = tmp_path / "redirected-report.json"
    redirected.symlink_to(original)
    copied["artifact_path"] = str(redirected)
    with pytest.raises(ScratchAuthorityError, match="symlink redirection"):
        _read_phase_report(copied, 6, _canonical_report_digest(copied), status)
    assert original.read_bytes() == original_bytes
    with pytest.raises(ScratchAuthorityError, match="Golden Registry is missing"):
        admit_scratch(registry / "cochem_system_config.json")


@pytest.mark.parametrize(
    "identity",
    [
        "ase_masses",
        "array_nuclides",
        "nuclear_identity",
        "mass_numbers",
        "masses_u",
        "nested_isotopes",
        "rdkit_isotope",
    ],
)
def test_crest_declared_nuclear_identity_refuses_before_calculator_or_engine(identity):
    from ase import Atoms
    from ase.calculators.emt import EMT
    from rdkit import Chem

    from cochem_base.exceptions import EcosystemDependencyError
    from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine, TopologyCrusher

    seed = Atoms("H2O", positions=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.96], [0.93, 0.0, -0.24]])
    seed.info.update(charge=0, multiplicity=1)
    if identity == "ase_masses":
        # Even numerically ordinary explicitly supplied masses are a declaration;
        # this route cannot silently discard their provenance.
        seed.set_masses(seed.get_masses())
    elif identity == "array_nuclides":
        import numpy as np

        seed.new_array("nuclides", np.array(["2H", "H", "O"]))
    elif identity == "nuclear_identity":
        seed.info[identity] = {"nuclides": ["2H", "H", "O"]}
    elif identity == "mass_numbers":
        seed.info[identity] = [2, None, None]
    elif identity == "masses_u":
        seed.info[identity] = [2.014, 1.008, 15.999]
    elif identity == "nested_isotopes":
        seed.info["metadata"] = {"isotopes": {"0": 2}}
    else:
        molecule = Chem.MolFromSmiles("[2H]O")
        assert molecule is not None
        seed.info["rdkit_mol"] = molecule
    seed.calc = EMT()
    with pytest.raises(EcosystemDependencyError, match="mass|identity|isotope"):
        CRESTConformerEngine().execute_secondary_search(seed)
    assert seed.calc.results == {}
    with pytest.raises(EcosystemDependencyError, match="mass|identity|isotope"):
        TopologyCrusher().deduplicate_ensemble_union(seed)
    assert seed.calc.results == {}


def test_scratch_consumers_refuse_replaced_ancestor_and_bounded_irregular_evidence(tmp_path):
    import json

    from cochem_base.core.managed_files import open_directory_chain
    from cochem_base.core.scratch import (
        ScratchAuthorityError,
        _create_owned_crest_directory,
        _read_document,
    )

    audited = tmp_path / "audited"
    audited.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_bytes(b"Retain outside ownership exactly.\n")
    (audited / "evidence.json").write_text(
        json.dumps({"observation": "bounded filesystem fixture only"})
    )
    original, source = _read_document(audited / "evidence.json", "Actual test document")
    assert original["observation"] == "bounded filesystem fixture only"
    assert source["parent_directory_chain"]
    with open_directory_chain(audited) as before:
        original_chain = before.chain
        audited.rename(tmp_path / "retained-old-audited")
        audited.symlink_to(outside, target_is_directory=True)
        with pytest.raises(ScratchAuthorityError, match="identity changed"):
            _create_owned_crest_directory(
                audited, audited, expected_chain=original_chain, expected_base_chain=original_chain
            )
        with pytest.raises(ScratchAuthorityError, match="symlink redirection"):
            _read_document(audited / "sentinel.txt", "Replaced ancestor evidence")
    assert sentinel.read_bytes() == b"Retain outside ownership exactly.\n"
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel.txt"]
    oversized = tmp_path / "oversized.json"
    # Sparse, bounded test fixture: size refusal must precede reading >16 MiB.
    with oversized.open("wb") as stream:
        stream.truncate(16 * 1024 * 1024 + 1)
    with pytest.raises(ScratchAuthorityError, match="evidence budget"):
        _read_document(oversized, "Oversized evidence")
    linked = tmp_path / "linked.json"
    os.link(sentinel, linked)
    with pytest.raises(ScratchAuthorityError, match="changed identity"):
        _read_document(linked, "Hardlinked evidence")
    pipe = tmp_path / "not-a-document"
    os.mkfifo(pipe)
    with pytest.raises(ScratchAuthorityError, match="changed identity"):
        _read_document(pipe, "FIFO evidence")
    assert sentinel.read_bytes() == b"Retain outside ownership exactly.\n"


@pytest.mark.parametrize(
    ("payload", "require_energy", "error_type"),
    [
        (b"1\nE=-1.0 Hartree\nH 0 0 0\n", True, None),
        (b"\xef\xbb\xbf1\r\n-1.0\r\nH 0 0 0\r\n", True, None),
        (b"1\rcomment\rH 0 0 0\r", False, None),
        (b"1\nenergy=-1.0 eV\nH 0 0 0\n", True, ValueError),
        (b"1\ncomment without energy\nH 0 0 0\n", True, ValueError),
        (b"2\n-1.0\nH 0 0 0\n", True, ValueError),
        (b"1\n-1.0\nH nan 0 0\n", True, ValueError),
        (b"1\n-1.0\nH 0 0 \xff\n", True, UnicodeError),
        (b"", True, ValueError),
    ],
)
def test_xyz_bound_bytes_seam_preserves_path_parser_results_and_refusals(
    tmp_path,
    payload,
    require_energy,
    error_type,
):
    """Declared grammar fixtures only; these bytes are not native scientific evidence."""
    import hashlib

    import numpy as np

    from cochem_base.topos_runner import _parse_xyz, _parse_xyz_bytes

    path = tmp_path / "declared-parser-input.xyz"
    path.write_bytes(payload)
    if error_type is not None:
        with pytest.raises(error_type) as from_path:
            _parse_xyz(path, require_energy=require_energy)
        with pytest.raises(error_type) as from_bytes:
            _parse_xyz_bytes(payload, source_path=path, require_energy=require_energy)
        assert type(from_path.value) is type(from_bytes.value)
        assert str(from_path.value) == str(from_bytes.value)
    else:
        from_path = _parse_xyz(path, require_energy=require_energy)
        from_bytes = _parse_xyz_bytes(payload, source_path=path, require_energy=require_energy)
        assert len(from_path) == len(from_bytes) == 1
        left, right = from_path[0], from_bytes[0]
        assert left.symbols == right.symbols == ("H",)
        assert left.energy == right.energy
        assert left.conformer_id == right.conformer_id == f"{tmp_path.name}:0"
        assert left.source == right.source == hashlib.sha256(payload).hexdigest()
        np.testing.assert_array_equal(left.coordinates, right.coordinates)
    assert path.read_bytes() == payload


@pytest.mark.parametrize(
    ("requested_symbols", "accepted"),
    [
        (["O", "H"], True),
        (["H", "O"], False),
        (["O", "H", "H"], False),
        (["N", "H"], False),
    ],
)
def test_crest_actual_parsed_frame_preserves_requested_ordered_elements(
    requested_symbols, accepted
):
    """Actual ASE/frame contracts only; declared parser bytes are not native evidence."""
    from ase import Atoms

    from cochem_base.exceptions import EcosystemDependencyError
    from cochem_base.topology.cochem_topos_crusher import CRESTConformerEngine
    from cochem_base.topos_runner import _parse_xyz_bytes

    payload = b"2\nE=-1.0 Hartree\nO 0 0 0\nH 0 0 0.96\n"
    frame = _parse_xyz_bytes(
        payload, source_path=Path("declared-guard-frame.xyz"), require_energy=True
    )[0]
    positions = [[0.0, 0.0, float(index)] for index in range(len(requested_symbols))]
    requested = Atoms(requested_symbols, positions=positions)
    original_frame_symbols = frame.symbols
    original_requested_symbols = requested.get_chemical_symbols()
    if accepted:
        assert (
            CRESTConformerEngine._validate_ordered_crest_elements(frame, requested)
            is None
        )
    else:
        with pytest.raises(
            EcosystemDependencyError,
            match="changed the ordered unlabelled input elements",
        ):
            CRESTConformerEngine._validate_ordered_crest_elements(frame, requested)
    assert frame.symbols == original_frame_symbols == ("O", "H")
    assert (
        requested.get_chemical_symbols()
        == original_requested_symbols
        == requested_symbols
    )
    assert requested.calc is None
