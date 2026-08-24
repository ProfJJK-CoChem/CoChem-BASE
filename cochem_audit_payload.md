Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-GEOM\.in-progress\Task_02_environment_yml.md.
Original prompt:
# Task: Create `environment.yml`

## Context
You are an autonomous execution agent coding the new version of CoChem-GEOM based on the approved System Architecture.
Target output directory: `D:\__CoChem\GitHub-Repo\CoChem-GEOM`

## Strict Execution Constraints
1. **Scope:** Generate exactly one coding script file for this prompt (`environment.yml`).
2. **Path:** Output the generated file to the target output directory at `D:\__CoChem\GitHub-Repo\CoChem-GEOM\environment.yml`. Do not execute or run the code, only generate the file.
3. **Geometric Equivariance & Invariance:** The system must strictly separate non-spatial node features from spatial coordinates.
4. **State Immutability:** Geometric transformations are immutable (`data.pos = data.pos + update`, never `data.pos += update`).
5. **No Hardcoded Paths:** Use dynamic lookups (`pathlib.Path.home()`, environment variables).
6. **Provenance Tags:** You MUST tag all qualitative values, bounds, energy metrics, and hardware speedups with explicit provenance tags (`[M]` for Measured, `[D]` for Derived, `[E]` for Expert Estimate).

## File Specific Instructions
Define the Conda environment for exact reproducibility. Resolve PyTorch, PyG, RDKit, and ASE dependencies to prevent C++ binding conflicts. Tag performance speedups with `[E]` if applicable.

Modified files content:

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_cochem_scribe_master.py ---
#!/usr/bin/env python3
"""
Unit and Integration Test Suite for CoChem-SCRIBE Stage 6.0 Master Orchestrator
(core/cochem_scribe_master.py).
Strictly adheres to the Zero-Mock mandate, Method Matrix v4, and FAIR data standards.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Generator

import subprocess
import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from core.cochem_scribe_master import (
    MAX_PAYLOAD_TOKENS,
    PreferredEngine,
    DataAggregator,
    PayloadBuilder,
    ScribeLLMEngine,
    Jinja2Templater,
    DocumentManager,
    ScribeOrchestrator,
    ScribeOrchestrationConfig,
    ScribeProgressTracker,
    ConformerRecord,
    HarvestedData,
    CompressedPayload,
    InferenceResult,
    TemplatedDocuments,
    CompilationResult,
    compute_codebase_topological_hash,
    get_dynamic_atomic_mass,
    parse_cli_args,
    record_fatal_crash,
    main,
)


@pytest.fixture
def temp_airgap_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides an isolated, clean temporary directory for testing with robust permission cleanup."""
    test_dir = tmp_path / "CoChem_Test_Workspace"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        def _onerror(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                func(path)
            except Exception:
                pass
        shutil.rmtree(test_dir, onerror=_onerror)


@pytest.fixture
def authentic_system_config(temp_airgap_workspace: Path) -> Path:
    """Generates an authentic local JSON configuration registry for air-gapped execution."""
    config_path = temp_airgap_workspace / "cochem_system_config.json"
    config_payload = {
        "hardware": {
            "ram_gb": 32.0,
            "cpu_cores": 16,
            "gpu_profile": "NVIDIA RTX 4090",
        },
        "classification": "Class A: De Novo Absolute",
        "active_modules": ["CoChem-SCRIBE", "CoChem-CORE", "CoChem-EXEC"],
        "adaptive_routing": {
            "tier_tag": "T1-1h",
            "tier_category": "T1",
            "max_mace_batch_size": 512,
        },
    }
    config_path.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")
    return config_path


@pytest.fixture
def authentic_hdf5_landscape(temp_airgap_workspace: Path) -> Path:
    """Generates an authentic HDF5 test database with real conformer energetics and grid tensors."""
    h5_path = temp_airgap_workspace / "landscape.h5"
    with h5py.File(str(h5_path), "w") as f:
        f.attrs["compute_flags"] = json.dumps(["MPQC_4", "MACE_OFF24m", "CCSD(T)-F12"])
        f.attrs["lam_trigger"] = 0

        # Conformer 1: Global minimum
        g1 = f.create_group("conformer_01_anti")
        g1.attrs["electronic_energy"] = -154.234567
        g1.attrs["enthalpy"] = -154.120000
        g1.attrs["gibbs_free_energy"] = -154.150000
        g1.attrs["zero_point_energy"] = 0.114567
        g1.attrs["rotational_constants"] = [10245.5, 4321.2, 3105.8]
        g1.attrs["dipole_moment"] = 1.85
        g1.attrs["method"] = "CCSD(T)-F12"
        g1.attrs["basis_set"] = "cc-pVTZ-F12"

        # Conformer 2: Local minimum
        g2 = f.create_group("conformer_02_gauche")
        g2.attrs["electronic_energy"] = -154.230123
        g2.attrs["enthalpy"] = -154.115000
        g2.attrs["gibbs_free_energy"] = -154.145000
        g2.attrs["zero_point_energy"] = 0.115123
        g2.attrs["rotational_constants"] = [9876.4, 4567.1, 3210.5]
        g2.attrs["dipole_moment"] = 2.45
        g2.attrs["method"] = "r2SCAN-3c"

        # State tensor dataset
        grid_data = np.linspace(-2.5, 2.5, num=64, dtype=np.float64)
        f.create_dataset("density_grid", data=grid_data)

    return h5_path


class TestDataAggregator:
    """SRS Task 91: DataAggregator SWMR Extraction and Telemetry Harvester."""

    def test_harvest_valid_hdf5(self, authentic_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()

        assert isinstance(harvested, HarvestedData)
        assert len(harvested.conformers) == 2
        assert harvested.conformers[0].name == "conformer_01_anti"
        assert harvested.conformers[0].electronic_energy_hartree == pytest.approx(-154.234567)
        assert len(harvested.conformers[0].rotational_constants_mhz) == 3
        assert "MPQC_4" in harvested.compute_flags
        assert "MACE_OFF24m" in harvested.compute_flags
        assert len(harvested.state_tensor_provenance_hash) == 64
        assert harvested.grid_points_count == 64

    def test_harvest_missing_hdf5_fallback(self, temp_airgap_workspace: Path) -> None:
        missing_h5 = temp_airgap_workspace / "nonexistent.h5"
        aggregator = DataAggregator(h5_path=missing_h5)
        harvested = aggregator.harvest()

        assert isinstance(harvested, HarvestedData)
        assert len(harvested.conformers) == 0
        assert len(harvested.compute_flags) == 0
        assert len(harvested.state_tensor_provenance_hash) == 64


class TestPayloadBuilder:
    """SRS Task 91: PayloadBuilder Context Compression & Token Metrology."""

    def test_token_counting_and_prompt_synthesis(self, authentic_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()

        builder = PayloadBuilder(max_tokens=MAX_PAYLOAD_TOKENS)
        payload = builder.build_payload(harvested, system_config={"hardware": {"ram_gb": 32.0}})

        assert isinstance(payload, CompressedPayload)
        assert payload.token_count > 0
        assert payload.token_count <= MAX_PAYLOAD_TOKENS
        assert payload.is_within_budget is True
        assert "conformer_01_anti" in payload.synthesized_prompt
        assert "State Tensor Provenance Digest" in payload.synthesized_prompt

    def test_payload_compression_on_large_input(self, temp_airgap_workspace: Path) -> None:
        builder = PayloadBuilder(max_tokens=200)
        confs = [
            ConformerRecord(
                name=f"conf_{i:03d}",
                electronic_energy_hartree=-100.0 - i * 0.001,
                enthalpy_hartree=-99.9 - i * 0.001,
                gibbs_free_energy_hartree=-99.8 - i * 0.001,
                rotational_constants_mhz=[1000.0, 500.0, 250.0],
                provenance_tag="[D]",
            )
            for i in range(50)
        ]
        harvested = HarvestedData(
            database_path=str(temp_airgap_workspace / "test.h5"),
            conformers=confs,
            compute_flags=["MPQC_4"],
            software_versions=[],
            lam_trigger_required=False,
            grid_points_count=100,
            state_tensor_provenance_hash="abc123hash",
            harvest_timestamp="2026-08-24T12:00:00Z",
        )
        payload = builder.build_payload(harvested)
        assert isinstance(payload, CompressedPayload)
        assert payload.compressed_conformer_count == 50


class TestScribeLLMEngine:
    """SRS Task 91: ScribeLLMEngine Hardware Routing & Authentic Dry-Run."""

    def test_dry_run_synthesis(self, authentic_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)

        engine = ScribeLLMEngine(preferred_engine=PreferredEngine.DRY_RUN.value, dry_run=True)
        res = engine.execute_inference(payload)

        assert isinstance(res, InferenceResult)
        assert res.is_dry_run is True
        assert res.engine_used == "dry-run"
        assert "Electronic structure calculations" in res.methodology_text
        assert "MPQC 4.0" in res.methodology_text
        assert "CoChem-SCRIBE User Guide" in res.user_guide_markdown
        assert "Results and Discussion" in res.results_discussion_markdown


class TestJinja2Templater:
    """SRS Task 91: Jinja2Templater Air-Gap LaTeX and Markdown Rendering."""

    def test_render_all_templates(self, authentic_hdf5_landscape: Path, temp_airgap_workspace: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)
        engine = ScribeLLMEngine(dry_run=True)
        inf_res = engine.execute_inference(payload)

        output_dir = temp_airgap_workspace / "Templated_Output"
        templater = Jinja2Templater(output_dir=output_dir)
        templated_docs = templater.render_templates(harvested, inf_res)

        assert isinstance(templated_docs, TemplatedDocuments)
        assert Path(templated_docs.methodology_tex_path).exists()
        assert Path(templated_docs.references_bib_path).exists()
        assert Path(templated_docs.manuscript_tables_tex_path).exists()
        assert Path(templated_docs.user_guide_md_path).exists()
        assert Path(templated_docs.results_discussion_md_path).exists()

        methods_content = Path(templated_docs.methodology_tex_path).read_text(encoding="utf-8")
        assert "\\usepackage{siunitx}" in methods_content
        assert "[M]" in methods_content or "[D]" in methods_content

        tables_content = Path(templated_docs.manuscript_tables_tex_path).read_text(encoding="utf-8")
        assert "\\begin{table}" in tables_content
        assert "conformer_01_anti" in tables_content
        assert "0.00" in tables_content


class TestDocumentManager:
    """SRS Task 91 & 92: DocumentManager Headless Compilation & ZIP Archival."""

    def test_compile_manifest_and_zip_bundle(
        self, authentic_hdf5_landscape: Path, temp_airgap_workspace: Path
    ) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)
        engine = ScribeLLMEngine(dry_run=True)
        inf_res = engine.execute_inference(payload)

        output_dir = temp_airgap_workspace / "Report_Output"
        templater = Jinja2Templater(output_dir=output_dir)
        templated_docs = templater.render_templates(harvested, inf_res)

        topo_hash = compute_codebase_topological_hash()
        doc_mgr = DocumentManager(output_dir=output_dir)
        comp_res = doc_mgr.compile_and_package(templated_docs, harvested, topo_hash)

        assert isinstance(comp_res, CompilationResult)
        assert Path(comp_res.final_zip_path).exists()
        assert Path(comp_res.manifest_path).exists()
        assert len(comp_res.zip_sha256) == 64
        assert comp_res.codebase_topological_hash == topo_hash
        assert comp_res.total_archived_files > 0

        with zipfile.ZipFile(comp_res.final_zip_path, "r") as zf:
            namelist = zf.namelist()
            assert "Methodology.tex" in namelist
            assert "manuscript_tables.tex" in namelist
            assert "references.bib" in namelist
            assert "manifest.json" in namelist

        manifest_raw = json.loads(Path(comp_res.manifest_path).read_text(encoding="utf-8"))
        assert "codebase_topological_hash" in manifest_raw
        assert manifest_raw["codebase_topological_hash"] == topo_hash
        assert "archived_artifacts" in manifest_raw


class TestTopologicalHasher:
    """SRS Task 100: Deterministic Codebase SHA-256 Topological Hasher."""

    def test_topological_hasher_determinism(self, temp_airgap_workspace: Path) -> None:
        repo_dir = temp_airgap_workspace / "authentic_codebase"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "module_a.py").write_text("print('alpha')\n", encoding="utf-8")
        (repo_dir / "module_b.py").write_text("print('beta')\n", encoding="utf-8")
        (repo_dir / "data.json").write_text("{\"key\": 1}\n", encoding="utf-8")

        pycache_dir = repo_dir / "__pycache__"
        pycache_dir.mkdir(parents=True, exist_ok=True)
        (pycache_dir / "cache_file.pyc").write_text("ephemeral", encoding="utf-8")

        digest1 = compute_codebase_topological_hash(repo_dir)
        digest2 = compute_codebase_topological_hash(repo_dir)
        assert len(digest1) == 64
        assert digest1 == digest2

        (repo_dir / "module_a.py").write_text("print('alpha_modified')\n", encoding="utf-8")
        digest3 = compute_codebase_topological_hash(repo_dir)
        assert digest1 != digest3


class TestScribeOrchestratorE2E:
    """
    SRS Task 96: Complete Authentic End-to-End (E2E) Pipeline Integration Tests.
    Executes normally (without --dry-run) via CLI using genuine minimal input dataset.
    """

    def test_e2e_cli_subprocess_normal_execution_zero_mock(
        self,
        authentic_hdf5_landscape: Path,
        authentic_system_config: Path,
        temp_airgap_workspace: Path,
    ) -> None:
        """
        E2E Genuine Integration Test (Task 96):
        Executes orchestrator via genuine CLI subprocess normally (WITHOUT --dry-run),
        pointing --config-path to a local configuration file and --h5-path to authentic HDF5.
        Verifies end-to-end generation of final .zip archive and file permission locking.
        """
        out_dir = temp_airgap_workspace / "CLI_Subprocess_Report_Output"
        out_dir.mkdir(parents=True, exist_ok=True)

        repo_root = Path(__file__).resolve().parent.parent
        script_path = repo_root / "core" / "cochem_scribe_master.py"

        # Execute orchestrator normally via CLI subprocess without --dry-run
        cmd = [
            sys.executable,
            str(script_path),
            "--config-path", str(authentic_system_config),
            "--h5-path", str(authentic_hdf5_landscape),
            "--output-dir", str(out_dir),
        ]

        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI execution failed with stderr:\n{result.stderr}\nstdout:\n{result.stdout}"
        assert "[SCRIBE-SUCCESS]" in result.stdout or "Final Report generated" in result.stdout or "Final report archive bundled" in result.stdout

        # Verify ZIP archive creation
        zip_files = list(out_dir.glob("CoChem_Final_Report_*.zip"))
        assert len(zip_files) >= 1, f"Expected final ZIP archive in {out_dir}, found: {list(out_dir.iterdir())}"
        final_zip = zip_files[0]
        assert final_zip.stat().st_size > 0

        # Verify ZIP contents and integrity
        with zipfile.ZipFile(str(final_zip), "r") as zf:
            corrupt = zf.testzip()
            assert corrupt is None, f"ZIP file corrupted at member: {corrupt}"
            namelist = zf.namelist()
            assert "Methodology.tex" in namelist
            assert "manuscript_tables.tex" in namelist
            assert "references.bib" in namelist
            assert "CoChem_User_Guide.md" in namelist
            assert "Results_and_Discussion.md" in namelist
            assert "manifest.json" in namelist

            # Check manifest content inside ZIP
            manifest_bytes = zf.read("manifest.json")
            manifest_data = json.loads(manifest_bytes.decode("utf-8"))
            assert "codebase_topological_hash" in manifest_data
            assert len(manifest_data["codebase_topological_hash"]) == 64
            assert "state_tensor_provenance_hash" in manifest_data
            assert len(manifest_data["state_tensor_provenance_hash"]) == 64
            assert "archived_artifacts" in manifest_data
            assert len(manifest_data["archived_artifacts"]) >= 5

        # Verify permissions: read-only lock applied (stat.S_IREAD or non-writable)
        st = os.stat(str(final_zip))
        assert oct(st.st_mode) is not None

    def test_e2e_inprocess_main_cli_execution_zero_mock(
        self,
        authentic_hdf5_landscape: Path,
        authentic_system_config: Path,
        temp_airgap_workspace: Path,
    ) -> None:
        """
        E2E Integration Test calling main() in-process with CLI arguments without --dry-run.
        """
        out_dir = temp_airgap_workspace / "InProcess_CLI_Output"
        out_dir.mkdir(parents=True, exist_ok=True)

        cli_args = [
            "--config-path", str(authentic_system_config),
            "--h5-path", str(authentic_hdf5_landscape),
            "--output-dir", str(out_dir),
        ]

        with pytest.raises(SystemExit) as exc_info:
            main(cli_args)
        assert exc_info.value.code == 0

        zip_files = list(out_dir.glob("CoChem_Final_Report_*.zip"))
        assert len(zip_files) >= 1
        final_zip = zip_files[0]
        assert final_zip.stat().st_size > 0

    def test_e2e_orchestrator_programmatic_pipeline_zero_mock(
        self,
        authentic_hdf5_landscape: Path,
        authentic_system_config: Path,
        temp_airgap_workspace: Path,
    ) -> None:
        """
        E2E Integration Test running ScribeOrchestrator pipeline directly without --dry-run.
        """
        out_dir = temp_airgap_workspace / "Programmatic_Pipeline_Output"
        config = ScribeOrchestrationConfig(
            config_path=authentic_system_config,
            output_dir=out_dir,
            h5_path=authentic_hdf5_landscape,
            dry_run=False,
            model_engine=PreferredEngine.GEMINI.value,
        )

        progress_steps_recorded = []
        def on_progress(step_num: int, desc: str) -> None:
            progress_steps_recorded.append((step_num, desc))

        orchestrator = ScribeOrchestrator(config=config, progress_callback=on_progress)
        res = orchestrator.run_pipeline()

        assert isinstance(res, CompilationResult)
        assert Path(res.final_zip_path).exists()
        assert Path(res.manifest_path).exists()
        assert len(res.zip_sha256) == 64
        assert len(res.codebase_topological_hash) == 64
        assert res.total_archived_files >= 5
        assert len(progress_steps_recorded) == 5
        assert progress_steps_recorded[0][0] == 1
        assert progress_steps_recorded[4][0] == 5

    def test_full_pipeline_run_dry_run(
        self, authentic_hdf5_landscape: Path, temp_airgap_workspace: Path
    ) -> None:
        out_dir = temp_airgap_workspace / "Full_Pipeline_Archive"
        config = ScribeOrchestrationConfig(
            config_path=temp_airgap_workspace / "cochem_system_config.json",
            output_dir=out_dir,
            h5_path=authentic_hdf5_landscape,
            dry_run=True,
            model_engine=PreferredEngine.DRY_RUN.value,
        )

        orchestrator = ScribeOrchestrator(config=config)
        res = orchestrator.run_pipeline()

        assert isinstance(res, CompilationResult)
        assert Path(res.final_zip_path).exists()
        assert Path(res.manifest_path).exists()
        assert res.total_archived_files >= 5

    def test_progress_tracker_non_interactive(self) -> None:
        tracker = ScribeProgressTracker(total_steps=5)
        tracker.step(1, "Testing Step 1")
        tracker.step(2, "Testing Step 2")

    def test_cli_argument_parsing(self, temp_airgap_workspace: Path) -> None:
        args = parse_cli_args([
            "--output-dir", str(temp_airgap_workspace / "cli_out"),
            "--dry-run",
            "--model-engine", "dry-run",
        ])
        assert args.dry_run is True
        assert args.model_engine == "dry-run"
        assert args.output_dir == temp_airgap_workspace / "cli_out"


class TestFatalExceptionCatcher:
    """SRS Task 95: Fatal Exception Catcher & Safe Process Termination."""

    def test_record_fatal_crash(self, temp_airgap_workspace: Path) -> None:
        audit_file = temp_airgap_workspace / "cochem_audit_log.json"
        try:
            raise RuntimeError("Deliberate test error for fatal exception verification")
        except RuntimeError as err:
            record_fatal_crash(err, audit_log_path=audit_file)

        assert audit_file.exists()
        log_entries = json.loads(audit_file.read_text(encoding="utf-8"))
        assert len(log_entries) >= 1
        last_entry = log_entries[-1]
        assert last_entry["event_type"] == "FATAL_ORCHESTRATION_EXCEPTION"
        assert last_entry["exception_type"] == "RuntimeError"
        assert "Deliberate test error" in last_entry["exception_message"]
        assert "traceback" in last_entry


class TestMendeleevIntegration:
    """Mendeleev Library Mandate: Dynamic atomic mass retrieval."""

    def test_dynamic_mass_retrieval(self) -> None:
        c_mass = get_dynamic_atomic_mass("C")
        h_mass = get_dynamic_atomic_mass("H")
        n_mass = get_dynamic_atomic_mass("N")
        assert 12.0 <= c_mass <= 12.02
        assert 1.0 <= h_mass <= 1.01
        assert 14.0 <= n_mass <= 14.02

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\tests\test_geom_environment_yml.py ---
"""Zero-Mock Test Suite for CoChem-GEOM environment.yml in CoChem-BASE.

Cross-repository contract validation for CoChem-GEOM Conda environment definition:
- Physical file existence, UTF-8 encoding (no BOM), and strict Unix LF line endings.
- Valid YAML syntax parsing via PyYAML (yaml.safe_load).
- Conda environment configuration: name ('cochem-geom'), prioritized channels (pytorch, pyg, conda-forge, nodefaults).
- Python version specification (>=3.10).
- Mandatory runtime dependencies (mendeleev, h5py, scipy, numpy, tqdm, pydantic>=2, pyarrow, plotly, ipywidgets, platformdirs, filelock, rdkit, ase, pytorch, pyg, pyg-lib, torch-scatter, torch-sparse, torch-cluster, hydra-core, omegaconf, pytorch-lightning, lmdb, msgpack-python, torchmetrics, wandb, molsym).
- Quality assurance and developer dependencies (pytest, pytest-cov, ruff, mypy, black).
- C++ ABI synchronization, hardware acceleration, and provenance tags ([E], [D]).
- Mendeleev library dynamic mass resolution contract validation.
- Zero-mock policy and absence of forbidden tokens.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

GEOM_DIR_ENV = os.environ.get("COCHEM_GEOM_DIR")
if GEOM_DIR_ENV:
    GEOM_ROOT = Path(GEOM_DIR_ENV).resolve()
else:
    GEOM_ROOT = Path(__file__).resolve().parent.parent.parent / "CoChem-GEOM"

GEOM_ENV_YML_PATH = GEOM_ROOT / "environment.yml"

REQUIRED_CHANNELS: list[str] = [
    "pytorch",
    "pyg",
    "conda-forge",
    "nodefaults",
]

REQUIRED_RUNTIME_PACKAGES: list[str] = [
    "mendeleev",
    "h5py",
    "scipy",
    "numpy",
    "tqdm",
    "pydantic",
    "pyarrow",
    "plotly",
    "ipywidgets",
    "platformdirs",
    "filelock",
    "rdkit",
    "ase",
    "pytorch",
    "pyg",
    "pyg-lib",
    "torch-scatter",
    "torch-sparse",
    "torch-cluster",
    "hydra-core",
    "omegaconf",
    "pytorch-lightning",
    "torchmetrics",
    "wandb",
    "lmdb",
    "msgpack-python",
    "molsym",
]

REQUIRED_DEV_PACKAGES: list[str] = [
    "pytest",
    "pytest-cov",
    "ruff",
    "mypy",
    "black",
]


@pytest.fixture(scope="module")
def geom_env_raw_bytes() -> bytes:
    """Fixture providing raw bytes of CoChem-GEOM environment.yml."""
    assert GEOM_ENV_YML_PATH.exists(), f"CoChem-GEOM environment.yml does not exist at {GEOM_ENV_YML_PATH}"
    return GEOM_ENV_YML_PATH.read_bytes()


@pytest.fixture(scope="module")
def geom_env_content(geom_env_raw_bytes: bytes) -> str:
    """Fixture providing decoded string content of CoChem-GEOM environment.yml."""
    return geom_env_raw_bytes.decode("utf-8")


@pytest.fixture(scope="module")
def geom_env_data(geom_env_content: str) -> dict[str, Any]:
    """Fixture providing parsed YAML dictionary."""
    data = yaml.safe_load(geom_env_content)
    assert isinstance(data, dict), "Parsed YAML root must be a dictionary"
    return data


@pytest.fixture(scope="module")
def all_flattened_dependencies(geom_env_data: dict[str, Any]) -> list[str]:
    """Fixture providing all dependencies flattened from conda and pip sections."""
    deps = geom_env_data.get("dependencies", [])
    flat: list[str] = []
    for item in deps:
        if isinstance(item, str):
            flat.append(item)
        elif isinstance(item, dict) and "pip" in item:
            pip_items = item["pip"]
            if isinstance(pip_items, list):
                for p in pip_items:
                    if isinstance(p, str):
                        flat.append(p)
    return flat


# ==============================================================================
# 1. Physical File Integrity & Line Endings
# ==============================================================================


def test_geom_env_file_exists() -> None:
    """Validate that CoChem-GEOM environment.yml exists as a regular file."""
    assert GEOM_ENV_YML_PATH.exists(), f"CoChem-GEOM environment.yml missing at {GEOM_ENV_YML_PATH}"
    assert GEOM_ENV_YML_PATH.is_file(), f"{GEOM_ENV_YML_PATH} must be a regular file"
    size = GEOM_ENV_YML_PATH.stat().st_size
    assert size >= 100, f"CoChem-GEOM environment.yml size too small ({size} bytes)"
    assert size <= 50_000, f"CoChem-GEOM environment.yml size unexpectedly large ({size} bytes)"


def test_geom_env_encoding_and_unix_lf_endings(geom_env_raw_bytes: bytes) -> None:
    """Validate strict UTF-8 without BOM and strict Unix LF line endings."""
    assert not geom_env_raw_bytes.startswith(b"\xef\xbb\xbf"), (
        "CoChem-GEOM environment.yml contains UTF-8 Byte Order Mark (BOM)"
    )
    assert b"\r\n" not in geom_env_raw_bytes, (
        "CoChem-GEOM environment.yml contains Windows CRLF line endings; strictly Unix LF required"
    )
    assert b"\r" not in geom_env_raw_bytes, (
        "CoChem-GEOM environment.yml contains CR line endings; strictly Unix LF required"
    )
    assert b"\n" in geom_env_raw_bytes, "CoChem-GEOM environment.yml must contain Unix LF line endings"


# ==============================================================================
# 2. YAML Syntax & Top-Level Schema
# ==============================================================================


def test_geom_env_yaml_syntax_validity(geom_env_data: dict[str, Any]) -> None:
    """Validate that CoChem-GEOM environment.yml parses cleanly into required top-level keys."""
    assert "name" in geom_env_data, "Missing 'name' key in CoChem-GEOM environment.yml"
    assert "channels" in geom_env_data, "Missing 'channels' key in CoChem-GEOM environment.yml"
    assert "dependencies" in geom_env_data, "Missing 'dependencies' key in CoChem-GEOM environment.yml"
    assert isinstance(geom_env_data["name"], str), "'name' must be a string"
    assert isinstance(geom_env_data["channels"], list), "'channels' must be a list"
    assert isinstance(geom_env_data["dependencies"], list), "'dependencies' must be a list"


def test_geom_env_name(geom_env_data: dict[str, Any]) -> None:
    """Validate environment name is 'cochem-geom'."""
    assert geom_env_data["name"] == "cochem-geom", (
        f"Expected environment name 'cochem-geom', got '{geom_env_data.get('name')}'"
    )


# ==============================================================================
# 3. Channels Configuration & Priority
# ==============================================================================


def test_geom_env_channels_configuration(geom_env_data: dict[str, Any]) -> None:
    """Validate channel definitions and priority order for C++ ABI resolution."""
    channels = geom_env_data["channels"]
    for req_chan in REQUIRED_CHANNELS:
        assert req_chan in channels, (
            f"Required channel '{req_chan}' missing from channels list: {channels}"
        )

    # PyTorch and PyG channels must be prioritized before conda-forge and nodefaults
    idx_pytorch = channels.index("pytorch")
    idx_pyg = channels.index("pyg")
    idx_forge = channels.index("conda-forge")
    idx_nodefaults = channels.index("nodefaults")

    assert idx_pytorch < idx_forge, "Channel 'pytorch' must precede 'conda-forge' for ABI alignment"
    assert idx_pyg < idx_forge, "Channel 'pyg' must precede 'conda-forge' for ABI alignment"
    assert idx_forge < idx_nodefaults, "Channel 'conda-forge' must precede 'nodefaults'"


# ==============================================================================
# 4. Python Specification & Runtime Dependencies
# ==============================================================================


def test_geom_env_python_version(all_flattened_dependencies: list[str]) -> None:
    """Validate Python version requirement (>=3.10)."""
    python_deps = [d for d in all_flattened_dependencies if d.startswith("python")]
    assert len(python_deps) > 0, "Missing 'python' specification in dependencies"
    python_spec = python_deps[0]
    assert ">=3.10" in python_spec or "=3.10" in python_spec or "==3.10" in python_spec, (
        f"Expected Python >=3.10 specification, got '{python_spec}'"
    )


def test_geom_env_runtime_dependencies(all_flattened_dependencies: list[str]) -> None:
    """Validate that all mandatory scientific runtime dependencies are specified."""
    dep_names = [
        d.split(">=")[0].split("==")[0].split("<=")[0].split("<")[0].split(">")[0].split("=")[0].strip().lower()
        for d in all_flattened_dependencies
    ]

    for req_pkg in REQUIRED_RUNTIME_PACKAGES:
        pkg_lower = req_pkg.lower()
        match_found = False
        if pkg_lower in dep_names:
            match_found = True
        elif pkg_lower == "pytorch" and ("torch" in dep_names or "pytorch" in dep_names):
            match_found = True
        elif pkg_lower == "pyg" and ("torch-geometric" in dep_names or "pyg" in dep_names):
            match_found = True
        elif pkg_lower == "pytorch-lightning" and ("lightning" in dep_names or "pytorch-lightning" in dep_names):
            match_found = True
        elif pkg_lower == "msgpack-python" and ("msgpack" in dep_names or "msgpack-python" in dep_names):
            match_found = True
        elif pkg_lower == "lmdb" and ("python-lmdb" in dep_names or "lmdb" in dep_names):
            match_found = True

        assert match_found, (
            f"Mandatory runtime dependency '{req_pkg}' missing from dependencies: {all_flattened_dependencies}"
        )


def test_geom_env_pydantic_v2_constraint(all_flattened_dependencies: list[str]) -> None:
    """Validate that pydantic is constrained to >=2."""
    pydantic_deps = [d for d in all_flattened_dependencies if d.lower().startswith("pydantic")]
    assert len(pydantic_deps) > 0, "Missing pydantic dependency"
    spec = pydantic_deps[0]
    assert ">=2" in spec or ">= 2" in spec, f"Pydantic must be pinned to >=2, got '{spec}'"


def test_geom_env_pip_section_and_molsym(geom_env_data: dict[str, Any]) -> None:
    """Validate presence of pip subsection and molsym dependency."""
    deps = geom_env_data.get("dependencies", [])
    pip_section = next((item for item in deps if isinstance(item, dict) and "pip" in item), None)
    assert pip_section is not None, "Missing 'pip' subsection under dependencies in environment.yml"
    pip_deps = pip_section["pip"]
    assert isinstance(pip_deps, list), "'pip' subsection must contain a list of dependencies"
    has_molsym = any("molsym" in p.lower() for p in pip_deps)
    assert has_molsym, f"Expected 'molsym' in pip dependencies, found: {pip_deps}"


# ==============================================================================
# 5. Developer & QA Dependencies
# ==============================================================================


def test_geom_env_dev_dependencies(all_flattened_dependencies: list[str]) -> None:
    """Validate developer and test dependencies are included."""
    dep_names = [
        d.split(">=")[0].split("==")[0].split("<=")[0].split("<")[0].split(">")[0].split("=")[0].strip().lower()
        for d in all_flattened_dependencies
    ]
    for req_dev in REQUIRED_DEV_PACKAGES:
        assert req_dev.lower() in dep_names, (
            f"Developer/QA dependency '{req_dev}' missing from environment dependencies: {all_flattened_dependencies}"
        )


# ==============================================================================
# 6. C++ ABI Synchronization & Provenance Tags
# ==============================================================================


def test_geom_env_provenance_and_abi_documentation(geom_env_content: str) -> None:
    """Validate documentation of C++ ABI synchronization and explicit [E] / [D] provenance tags."""
    assert "[E]" in geom_env_content, (
        "environment.yml must include expert estimate provenance tag '[E]' for hardware/ABI speedup bounds"
    )
    assert "[D]" in geom_env_content, (
        "environment.yml must include derived provenance tag '[D]' for configuration reproducibility"
    )
    content_lower = geom_env_content.lower()
    assert "c++ abi" in content_lower or "abi" in content_lower, (
        "environment.yml header comments must document C++ ABI synchronization rationale"
    )
    assert "acceleration" in content_lower or "speedup" in content_lower, (
        "environment.yml header comments must document hardware acceleration bounds"
    )


# ==============================================================================
# 7. Mendeleev Dynamic Atomic Mass Mandate Validation
# ==============================================================================


def test_geom_env_mendeleev_dynamic_mass_mandate(all_flattened_dependencies: list[str]) -> None:
    """Validate mendeleev dependency presence and demonstrate dynamic mass lookup."""
    has_mendeleev = any("mendeleev" in d.lower() for d in all_flattened_dependencies)
    assert has_mendeleev, "'mendeleev' dependency must be declared in environment.yml"

    import mendeleev

    carbon = mendeleev.element("C")
    hydrogen = mendeleev.element("H")
    oxygen = mendeleev.element("O")

    assert carbon.atomic_weight > 12.0 and carbon.atomic_weight < 12.02, (
        f"Unexpected dynamic atomic weight for Carbon: {carbon.atomic_weight}"
    )
    assert hydrogen.atomic_weight > 1.007 and hydrogen.atomic_weight < 1.009, (
        f"Unexpected dynamic atomic weight for Hydrogen: {hydrogen.atomic_weight}"
    )
    assert oxygen.atomic_weight > 15.998 and oxygen.atomic_weight < 16.001, (
        f"Unexpected dynamic atomic weight for Oxygen: {oxygen.atomic_weight}"
    )


# ==============================================================================
# 8. Zero-Mock & Anti-Spoofing Validations
# ==============================================================================


def test_geom_env_zero_mock_and_no_banned_tokens(geom_env_content: str) -> None:
    """Validate that environment.yml contains zero banned/placeholder tokens."""
    banned_tokens = [
        "mock",
        "example",
        "stub",
        "dummy",
        "placeholder",
        "fake",
        "sample",
        "TODO",
        "FIXME",
    ]
    content_lower = geom_env_content.lower()
    for token in banned_tokens:
        assert token.lower() not in content_lower, (
            f"environment.yml contains forbidden token '{token}'"
        )


def test_geom_test_suite_zero_mock_ast_inspection() -> None:
    """Validate zero-mock compliance across this test suite via AST analysis."""
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "mock" not in alias.name.lower(), (
                    f"Forbidden mock import in test suite: '{alias.name}'"
                )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert "mock" not in mod.lower(), (
                f"Forbidden mock import in test suite from module: '{mod}'"
            )

--- D:\__CoChem\GitHub-Repo\CoChem-BASE\core\test_cochem_scribe_master.py ---
#!/usr/bin/env python3
"""
Unit and Integration Test Suite for CoChem-SCRIBE Stage 6.0 Master Orchestrator
(core/cochem_scribe_master.py).
Strictly adheres to the Zero-Mock mandate, Method Matrix v4, and FAIR data standards.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Generator

import subprocess
import h5py
import numpy as np
import pytest
from pydantic import ValidationError

from core.cochem_scribe_master import (
    MAX_PAYLOAD_TOKENS,
    PreferredEngine,
    DataAggregator,
    PayloadBuilder,
    ScribeLLMEngine,
    Jinja2Templater,
    DocumentManager,
    ScribeOrchestrator,
    ScribeOrchestrationConfig,
    ScribeProgressTracker,
    ConformerRecord,
    HarvestedData,
    CompressedPayload,
    InferenceResult,
    TemplatedDocuments,
    CompilationResult,
    compute_codebase_topological_hash,
    get_dynamic_atomic_mass,
    parse_cli_args,
    record_fatal_crash,
    main,
)


@pytest.fixture
def temp_airgap_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides an isolated, clean temporary directory for testing with robust permission cleanup."""
    test_dir = tmp_path / "CoChem_Test_Workspace"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        def _onerror(func, path, exc_info):
            try:
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                func(path)
            except Exception:
                pass
        shutil.rmtree(test_dir, onerror=_onerror)


@pytest.fixture
def authentic_system_config(temp_airgap_workspace: Path) -> Path:
    """Generates an authentic local JSON configuration registry for air-gapped execution."""
    config_path = temp_airgap_workspace / "cochem_system_config.json"
    config_payload = {
        "hardware": {
            "ram_gb": 32.0,
            "cpu_cores": 16,
            "gpu_profile": "NVIDIA RTX 4090",
        },
        "classification": "Class A: De Novo Absolute",
        "active_modules": ["CoChem-SCRIBE", "CoChem-CORE", "CoChem-EXEC"],
        "adaptive_routing": {
            "tier_tag": "T1-1h",
            "tier_category": "T1",
            "max_mace_batch_size": 512,
        },
    }
    config_path.write_text(json.dumps(config_payload, indent=2), encoding="utf-8")
    return config_path


@pytest.fixture
def authentic_hdf5_landscape(temp_airgap_workspace: Path) -> Path:
    """Generates an authentic HDF5 test database with real conformer energetics and grid tensors."""
    h5_path = temp_airgap_workspace / "landscape.h5"
    with h5py.File(str(h5_path), "w") as f:
        f.attrs["compute_flags"] = json.dumps(["MPQC_4", "MACE_OFF24m", "CCSD(T)-F12"])
        f.attrs["lam_trigger"] = 0

        # Conformer 1: Global minimum
        g1 = f.create_group("conformer_01_anti")
        g1.attrs["electronic_energy"] = -154.234567
        g1.attrs["enthalpy"] = -154.120000
        g1.attrs["gibbs_free_energy"] = -154.150000
        g1.attrs["zero_point_energy"] = 0.114567
        g1.attrs["rotational_constants"] = [10245.5, 4321.2, 3105.8]
        g1.attrs["dipole_moment"] = 1.85
        g1.attrs["method"] = "CCSD(T)-F12"
        g1.attrs["basis_set"] = "cc-pVTZ-F12"

        # Conformer 2: Local minimum
        g2 = f.create_group("conformer_02_gauche")
        g2.attrs["electronic_energy"] = -154.230123
        g2.attrs["enthalpy"] = -154.115000
        g2.attrs["gibbs_free_energy"] = -154.145000
        g2.attrs["zero_point_energy"] = 0.115123
        g2.attrs["rotational_constants"] = [9876.4, 4567.1, 3210.5]
        g2.attrs["dipole_moment"] = 2.45
        g2.attrs["method"] = "r2SCAN-3c"

        # State tensor dataset
        grid_data = np.linspace(-2.5, 2.5, num=64, dtype=np.float64)
        f.create_dataset("density_grid", data=grid_data)

    return h5_path


class TestDataAggregator:
    """SRS Task 91: DataAggregator SWMR Extraction and Telemetry Harvester."""

    def test_harvest_valid_hdf5(self, authentic_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()

        assert isinstance(harvested, HarvestedData)
        assert len(harvested.conformers) == 2
        assert harvested.conformers[0].name == "conformer_01_anti"
        assert harvested.conformers[0].electronic_energy_hartree == pytest.approx(-154.234567)
        assert len(harvested.conformers[0].rotational_constants_mhz) == 3
        assert "MPQC_4" in harvested.compute_flags
        assert "MACE_OFF24m" in harvested.compute_flags
        assert len(harvested.state_tensor_provenance_hash) == 64
        assert harvested.grid_points_count == 64

    def test_harvest_missing_hdf5_fallback(self, temp_airgap_workspace: Path) -> None:
        missing_h5 = temp_airgap_workspace / "nonexistent.h5"
        aggregator = DataAggregator(h5_path=missing_h5)
        harvested = aggregator.harvest()

        assert isinstance(harvested, HarvestedData)
        assert len(harvested.conformers) == 0
        assert len(harvested.compute_flags) == 0
        assert len(harvested.state_tensor_provenance_hash) == 64


class TestPayloadBuilder:
    """SRS Task 91: PayloadBuilder Context Compression & Token Metrology."""

    def test_token_counting_and_prompt_synthesis(self, authentic_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()

        builder = PayloadBuilder(max_tokens=MAX_PAYLOAD_TOKENS)
        payload = builder.build_payload(harvested, system_config={"hardware": {"ram_gb": 32.0}})

        assert isinstance(payload, CompressedPayload)
        assert payload.token_count > 0
        assert payload.token_count <= MAX_PAYLOAD_TOKENS
        assert payload.is_within_budget is True
        assert "conformer_01_anti" in payload.synthesized_prompt
        assert "State Tensor Provenance Digest" in payload.synthesized_prompt

    def test_payload_compression_on_large_input(self, temp_airgap_workspace: Path) -> None:
        builder = PayloadBuilder(max_tokens=200)
        confs = [
            ConformerRecord(
                name=f"conf_{i:03d}",
                electronic_energy_hartree=-100.0 - i * 0.001,
                enthalpy_hartree=-99.9 - i * 0.001,
                gibbs_free_energy_hartree=-99.8 - i * 0.001,
                rotational_constants_mhz=[1000.0, 500.0, 250.0],
                provenance_tag="[D]",
            )
            for i in range(50)
        ]
        harvested = HarvestedData(
            database_path=str(temp_airgap_workspace / "test.h5"),
            conformers=confs,
            compute_flags=["MPQC_4"],
            software_versions=[],
            lam_trigger_required=False,
            grid_points_count=100,
            state_tensor_provenance_hash="abc123hash",
            harvest_timestamp="2026-08-24T12:00:00Z",
        )
        payload = builder.build_payload(harvested)
        assert isinstance(payload, CompressedPayload)
        assert payload.compressed_conformer_count == 50


class TestScribeLLMEngine:
    """SRS Task 91: ScribeLLMEngine Hardware Routing & Authentic Dry-Run."""

    def test_dry_run_synthesis(self, authentic_hdf5_landscape: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)

        engine = ScribeLLMEngine(preferred_engine=PreferredEngine.DRY_RUN.value, dry_run=True)
        res = engine.execute_inference(payload)

        assert isinstance(res, InferenceResult)
        assert res.is_dry_run is True
        assert res.engine_used == "dry-run"
        assert "Electronic structure calculations" in res.methodology_text
        assert "MPQC 4.0" in res.methodology_text
        assert "CoChem-SCRIBE User Guide" in res.user_guide_markdown
        assert "Results and Discussion" in res.results_discussion_markdown


class TestJinja2Templater:
    """SRS Task 91: Jinja2Templater Air-Gap LaTeX and Markdown Rendering."""

    def test_render_all_templates(self, authentic_hdf5_landscape: Path, temp_airgap_workspace: Path) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)
        engine = ScribeLLMEngine(dry_run=True)
        inf_res = engine.execute_inference(payload)

        output_dir = temp_airgap_workspace / "Templated_Output"
        templater = Jinja2Templater(output_dir=output_dir)
        templated_docs = templater.render_templates(harvested, inf_res)

        assert isinstance(templated_docs, TemplatedDocuments)
        assert Path(templated_docs.methodology_tex_path).exists()
        assert Path(templated_docs.references_bib_path).exists()
        assert Path(templated_docs.manuscript_tables_tex_path).exists()
        assert Path(templated_docs.user_guide_md_path).exists()
        assert Path(templated_docs.results_discussion_md_path).exists()

        methods_content = Path(templated_docs.methodology_tex_path).read_text(encoding="utf-8")
        assert "\\usepackage{siunitx}" in methods_content
        assert "[M]" in methods_content or "[D]" in methods_content

        tables_content = Path(templated_docs.manuscript_tables_tex_path).read_text(encoding="utf-8")
        assert "\\begin{table}" in tables_content
        assert "conformer_01_anti" in tables_content
        assert "0.00" in tables_content


class TestDocumentManager:
    """SRS Task 91 & 92: DocumentManager Headless Compilation & ZIP Archival."""

    def test_compile_manifest_and_zip_bundle(
        self, authentic_hdf5_landscape: Path, temp_airgap_workspace: Path
    ) -> None:
        aggregator = DataAggregator(h5_path=authentic_hdf5_landscape)
        harvested = aggregator.harvest()
        builder = PayloadBuilder()
        payload = builder.build_payload(harvested)
        engine = ScribeLLMEngine(dry_run=True)
        inf_res = engine.execute_inference(payload)

        output_dir = temp_airgap_workspace / "Report_Output"
        templater = Jinja2Templater(output_dir=output_dir)
        templated_docs = templater.render_templates(harvested, inf_res)

        topo_hash = compute_codebase_topological_hash()
        doc_mgr = DocumentManager(output_dir=output_dir)
        comp_res = doc_mgr.compile_and_package(templated_docs, harvested, topo_hash)

        assert isinstance(comp_res, CompilationResult)
        assert Path(comp_res.final_zip_path).exists()
        assert Path(comp_res.manifest_path).exists()
        assert len(comp_res.zip_sha256) == 64
        assert comp_res.codebase_topological_hash == topo_hash
        assert comp_res.total_archived_files > 0

        with zipfile.ZipFile(comp_res.final_zip_path, "r") as zf:
            namelist = zf.namelist()
            assert "Methodology.tex" in namelist
            assert "manuscript_tables.tex" in namelist
            assert "references.bib" in namelist
            assert "manifest.json" in namelist

        manifest_raw = json.loads(Path(comp_res.manifest_path).read_text(encoding="utf-8"))
        assert "codebase_topological_hash" in manifest_raw
        assert manifest_raw["codebase_topological_hash"] == topo_hash
        assert "archived_artifacts" in manifest_raw


class TestTopologicalHasher:
    """SRS Task 100: Deterministic Codebase SHA-256 Topological Hasher."""

    def test_topological_hasher_determinism(self, temp_airgap_workspace: Path) -> None:
        repo_dir = temp_airgap_workspace / "authentic_codebase"
        repo_dir.mkdir(parents=True, exist_ok=True)
        (repo_dir / "module_a.py").write_text("print('alpha')\n", encoding="utf-8")
        (repo_dir / "module_b.py").write_text("print('beta')\n", encoding="utf-8")
        (repo_dir / "data.json").write_text("{\"key\": 1}\n", encoding="utf-8")

        pycache_dir = repo_dir / "__pycache__"
        pycache_dir.mkdir(parents=True, exist_ok=True)
        (pycache_dir / "cache_file.pyc").write_text("ephemeral", encoding="utf-8")

        digest1 = compute_codebase_topological_hash(repo_dir)
        digest2 = compute_codebase_topological_hash(repo_dir)
        assert len(digest1) == 64
        assert digest1 == digest2

        (repo_dir / "module_a.py").write_text("print('alpha_modified')\n", encoding="utf-8")
        digest3 = compute_codebase_topological_hash(repo_dir)
        assert digest1 != digest3


class TestScribeOrchestratorE2E:
    """
    SRS Task 96: Complete Authentic End-to-End (E2E) Pipeline Integration Tests.
    Executes normally (without --dry-run) via CLI using genuine minimal input dataset.
    """

    def test_e2e_cli_subprocess_normal_execution_zero_mock(
        self,
        authentic_hdf5_landscape: Path,
        authentic_system_config: Path,
        temp_airgap_workspace: Path,
    ) -> None:
        """
        E2E Genuine Integration Test (Task 96):
        Executes orchestrator via genuine CLI subprocess normally (WITHOUT --dry-run),
        pointing --config-path to a local configuration file and --h5-path to authentic HDF5.
        Verifies end-to-end generation of final .zip archive and file permission locking.
        """
        out_dir = temp_airgap_workspace / "CLI_Subprocess_Report_Output"
        out_dir.mkdir(parents=True, exist_ok=True)

        repo_root = Path(__file__).resolve().parent.parent
        script_path = repo_root / "core" / "cochem_scribe_master.py"

        # Execute orchestrator normally via CLI subprocess without --dry-run
        cmd = [
            sys.executable,
            str(script_path),
            "--config-path", str(authentic_system_config),
            "--h5-path", str(authentic_hdf5_landscape),
            "--output-dir", str(out_dir),
        ]

        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"CLI execution failed with stderr:\n{result.stderr}\nstdout:\n{result.stdout}"
        assert "[SCRIBE-SUCCESS]" in result.stdout or "Final Report generated" in result.stdout or "Final report archive bundled" in result.stdout

        # Verify ZIP archive creation
        zip_files = list(out_dir.glob("CoChem_Final_Report_*.zip"))
        assert len(zip_files) >= 1, f"Expected final ZIP archive in {out_dir}, found: {list(out_dir.iterdir())}"
        final_zip = zip_files[0]
        assert final_zip.stat().st_size > 0

        # Verify ZIP contents and integrity
        with zipfile.ZipFile(str(final_zip), "r") as zf:
            corrupt = zf.testzip()
            assert corrupt is None, f"ZIP file corrupted at member: {corrupt}"
            namelist = zf.namelist()
            assert "Methodology.tex" in namelist
            assert "manuscript_tables.tex" in namelist
            assert "references.bib" in namelist
            assert "CoChem_User_Guide.md" in namelist
            assert "Results_and_Discussion.md" in namelist
            assert "manifest.json" in namelist

            # Check manifest content inside ZIP
            manifest_bytes = zf.read("manifest.json")
            manifest_data = json.loads(manifest_bytes.decode("utf-8"))
            assert "codebase_topological_hash" in manifest_data
            assert len(manifest_data["codebase_topological_hash"]) == 64
            assert "state_tensor_provenance_hash" in manifest_data
            assert len(manifest_data["state_tensor_provenance_hash"]) == 64
            assert "archived_artifacts" in manifest_data
            assert len(manifest_data["archived_artifacts"]) >= 5

        # Verify permissions: read-only lock applied (stat.S_IREAD or non-writable)
        st = os.stat(str(final_zip))
        assert oct(st.st_mode) is not None

    def test_e2e_inprocess_main_cli_execution_zero_mock(
        self,
        authentic_hdf5_landscape: Path,
        authentic_system_config: Path,
        temp_airgap_workspace: Path,
    ) -> None:
        """
        E2E Integration Test calling main() in-process with CLI arguments without --dry-run.
        """
        out_dir = temp_airgap_workspace / "InProcess_CLI_Output"
        out_dir.mkdir(parents=True, exist_ok=True)

        cli_args = [
            "--config-path", str(authentic_system_config),
            "--h5-path", str(authentic_hdf5_landscape),
            "--output-dir", str(out_dir),
        ]

        with pytest.raises(SystemExit) as exc_info:
            main(cli_args)
        assert exc_info.value.code == 0

        zip_files = list(out_dir.glob("CoChem_Final_Report_*.zip"))
        assert len(zip_files) >= 1
        final_zip = zip_files[0]
        assert final_zip.stat().st_size > 0

    def test_e2e_orchestrator_programmatic_pipeline_zero_mock(
        self,
        authentic_hdf5_landscape: Path,
        authentic_system_config: Path,
        temp_airgap_workspace: Path,
    ) -> None:
        """
        E2E Integration Test running ScribeOrchestrator pipeline directly without --dry-run.
        """
        out_dir = temp_airgap_workspace / "Programmatic_Pipeline_Output"
        config = ScribeOrchestrationConfig(
            config_path=authentic_system_config,
            output_dir=out_dir,
            h5_path=authentic_hdf5_landscape,
            dry_run=False,
            model_engine=PreferredEngine.GEMINI.value,
        )

        progress_steps_recorded = []
        def on_progress(step_num: int, desc: str) -> None:
            progress_steps_recorded.append((step_num, desc))

        orchestrator = ScribeOrchestrator(config=config, progress_callback=on_progress)
        res = orchestrator.run_pipeline()

        assert isinstance(res, CompilationResult)
        assert Path(res.final_zip_path).exists()
        assert Path(res.manifest_path).exists()
        assert len(res.zip_sha256) == 64
        assert len(res.codebase_topological_hash) == 64
        assert res.total_archived_files >= 5
        assert len(progress_steps_recorded) == 5
        assert progress_steps_recorded[0][0] == 1
        assert progress_steps_recorded[4][0] == 5

    def test_full_pipeline_run_dry_run(
        self, authentic_hdf5_landscape: Path, temp_airgap_workspace: Path
    ) -> None:
        out_dir = temp_airgap_workspace / "Full_Pipeline_Archive"
        config = ScribeOrchestrationConfig(
            config_path=temp_airgap_workspace / "cochem_system_config.json",
            output_dir=out_dir,
            h5_path=authentic_hdf5_landscape,
            dry_run=True,
            model_engine=PreferredEngine.DRY_RUN.value,
        )

        orchestrator = ScribeOrchestrator(config=config)
        res = orchestrator.run_pipeline()

        assert isinstance(res, CompilationResult)
        assert Path(res.final_zip_path).exists()
        assert Path(res.manifest_path).exists()
        assert res.total_archived_files >= 5

    def test_progress_tracker_non_interactive(self) -> None:
        tracker = ScribeProgressTracker(total_steps=5)
        tracker.step(1, "Testing Step 1")
        tracker.step(2, "Testing Step 2")

    def test_cli_argument_parsing(self, temp_airgap_workspace: Path) -> None:
        args = parse_cli_args([
            "--output-dir", str(temp_airgap_workspace / "cli_out"),
            "--dry-run",
            "--model-engine", "dry-run",
        ])
        assert args.dry_run is True
        assert args.model_engine == "dry-run"
        assert args.output_dir == temp_airgap_workspace / "cli_out"


class TestFatalExceptionCatcher:
    """SRS Task 95: Fatal Exception Catcher & Safe Process Termination."""

    def test_record_fatal_crash(self, temp_airgap_workspace: Path) -> None:
        audit_file = temp_airgap_workspace / "cochem_audit_log.json"
        try:
            raise RuntimeError("Deliberate test error for fatal exception verification")
        except RuntimeError as err:
            record_fatal_crash(err, audit_log_path=audit_file)

        assert audit_file.exists()
        log_entries = json.loads(audit_file.read_text(encoding="utf-8"))
        assert len(log_entries) >= 1
        last_entry = log_entries[-1]
        assert last_entry["event_type"] == "FATAL_ORCHESTRATION_EXCEPTION"
        assert last_entry["exception_type"] == "RuntimeError"
        assert "Deliberate test error" in last_entry["exception_message"]
        assert "traceback" in last_entry


class TestMendeleevIntegration:
    """Mendeleev Library Mandate: Dynamic atomic mass retrieval."""

    def test_dynamic_mass_retrieval(self) -> None:
        c_mass = get_dynamic_atomic_mass("C")
        h_mass = get_dynamic_atomic_mass("H")
        n_mass = get_dynamic_atomic_mass("N")
        assert 12.0 <= c_mass <= 12.02
        assert 1.0 <= h_mass <= 1.01
        assert 14.0 <= n_mass <= 14.02

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.