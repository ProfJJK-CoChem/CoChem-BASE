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
)


@pytest.fixture
def temp_airgap_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Provides an isolated, clean temporary directory for testing."""
    test_dir = tmp_path / "CoChem_Test_Workspace"
    test_dir.mkdir(parents=True, exist_ok=True)
    yield test_dir
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


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


class TestScribeOrchestratorPipeline:
    """Integration: Full 5-Step Sequential Pipeline Execution."""

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
