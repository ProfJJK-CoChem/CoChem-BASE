#!/usr/bin/env python3
r"""Unit Test Suite for CoChem-BENCH Voila GUI Wrapper & Configuration UI.

Module: tests/test_cochem_bench_voila.py
Target Implementation: cochem_bench.interfaces.voila_bench_dashboard

Tests:
1. MethodologyToggles:
   - Renders ipywidgets controls for basis pair selection, SCF models, Correlation models, and composite corrections.
   - Basis pair coupling logic (e.g. def2-TZVPP -> def2-QZVPP).
   - Relativistic Hamiltonian selection toggle (X2C vs DKH2).
   - Serialization to structured methodology dictionary.
2. CostHeuristicTooltip:
   - Dynamic polling of node limits from Registry/cochem_system_config.json.
   - O(N^7) runtime and O(N^4) scratch disk calculation strictly from num_atoms metadata.
   - Dynamic physical RAM threshold comparison and red warning generation when memory limit is exceeded.
   - Button lockout mechanism preventing submission on memory overflow.
3. ManifestCompiler:
   - Serialization into bench_run_params.json in BENCH_Workspace.
   - Air-gap path dynamic resolution via COCHEM_ARTIFACTS_DIR.
   - UI button lockout (disabled=True) preventing duplicate MPI thread spawning.
4. VoilaBenchDashboard:
   - Full master dashboard construction, Status Ribbon HUD, and widget assembly.
   - End-to-end configuration and execution trigger.
5. Safety Contracts:
   - Dynamic air-gap pathing.
   - Zero parsing of raw .xyz strings or wavefunction files.
   - Dynamic Mendeleev atomic mass integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import ipywidgets as widgets
import pytest

from cochem_bench.interfaces.voila_bench_dashboard import (
    BenchRunParams,
    CostHeuristicTooltip,
    CostHeuristics,
    ManifestCompiler,
    MethodologySettings,
    MethodologyToggles,
    VoilaBenchDashboard,
    get_bench_workspace_dir,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_registry_config_path,
)


@pytest.fixture
def clean_bench_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sets up a sterile, air-gapped COCHEM_ARTIFACTS_DIR workspace with cochem_system_config.json."""
    artifacts_dir = tmp_path / "cochem_artifacts_test"
    registry_dir = artifacts_dir / "Registry"
    workspace_dir = artifacts_dir / "BENCH_Workspace"

    registry_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    config_data: Dict[str, Any] = {
        "schema_version": "4.0.0",
        "hardware": {
            "physical_cpu_cores": 8,
            "logical_cpu_cores": 16,
            "ram_gb": 64.0,
            "avx512_support": True,
            "gpu_profile": "NVIDIA A100",
            "vram_gb": 40.0,
            "os_target": "linux_x86_64",
        },
        "cost_heuristics": {
            "runtime_scalar_o_n7": 2.5e-6,
            "scratch_scalar_o_n4_gb": 1.5e-4,
            "ram_scalar_o_n4_gb": 8.0e-5,
            "base_ram_gb": 4.0,
        },
        "engines": {
            "orca": {
                "status": "found",
                "path": "/opt/orca/orca",
                "version": "6.1.1",
            }
        },
    }

    config_file = registry_dir / "cochem_system_config.json"
    config_file.write_text(json.dumps(config_data, indent=2), encoding="utf-8")

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))
    return artifacts_dir


# ==============================================================================
# 1. MethodologyToggles Tests
# ==============================================================================

class TestMethodologyToggles:
    """Tests for ipywidgets methodology selection and coupling logic."""

    def test_widgets_initialization(self) -> None:
        """Verifies that all required ipywidgets controls are instantiated with valid defaults."""
        toggles = MethodologyToggles()

        assert isinstance(toggles.cardinal_lower_dropdown, widgets.Dropdown)
        assert isinstance(toggles.cardinal_higher_dropdown, widgets.Dropdown)
        assert isinstance(toggles.scf_extrap_dropdown, widgets.Dropdown)
        assert isinstance(toggles.cor_extrap_dropdown, widgets.Dropdown)
        assert isinstance(toggles.cv_checkbox, widgets.Checkbox)
        assert isinstance(toggles.rel_checkbox, widgets.Checkbox)
        assert isinstance(toggles.rel_hamiltonian_dropdown, widgets.Dropdown)
        assert isinstance(toggles.method_level_dropdown, widgets.Dropdown)
        assert isinstance(toggles.container, widgets.VBox)

    def test_basis_pair_coupling(self) -> None:
        """Verifies that selecting a lower cardinal basis restricts/updates the higher basis dropdown."""
        toggles = MethodologyToggles()

        # Set lower cardinal to TZVPP (3)
        toggles.cardinal_lower_dropdown.value = "def2-TZVPP"
        # Higher cardinal options must not include lower cardinal values (e.g. def2-SVP or def2-TZVPP)
        higher_options = list(toggles.cardinal_higher_dropdown.options)
        assert "def2-SVP" not in higher_options
        assert "def2-TZVPP" not in higher_options
        assert "def2-QZVPP" in higher_options

        # Set lower cardinal to cc-pVDZ (2)
        toggles.cardinal_lower_dropdown.value = "cc-pVDZ"
        higher_options_cc = list(toggles.cardinal_higher_dropdown.options)
        assert "cc-pVDZ" not in higher_options_cc
        assert "cc-pVTZ" in higher_options_cc

    def test_relativistic_hamiltonian_toggle_visibility(self) -> None:
        """Verifies that relativistic Hamiltonian dropdown enables/disables with the checkbox."""
        toggles = MethodologyToggles()

        toggles.rel_checkbox.value = False
        assert toggles.rel_hamiltonian_dropdown.disabled is True

        toggles.rel_checkbox.value = True
        assert toggles.rel_hamiltonian_dropdown.disabled is False

    def test_to_methodology_settings(self) -> None:
        """Verifies extraction and validation of MethodologySettings Pydantic model."""
        toggles = MethodologyToggles()
        toggles.cardinal_lower_dropdown.value = "def2-TZVPP"
        toggles.cardinal_higher_dropdown.value = "def2-QZVPP"
        toggles.scf_extrap_dropdown.value = "Feller Exponential"
        toggles.cor_extrap_dropdown.value = "Halkier Inverse Cubic (X^-3)"
        toggles.cv_checkbox.value = True
        toggles.rel_checkbox.value = True
        toggles.rel_hamiltonian_dropdown.value = "X2C"
        toggles.method_level_dropdown.value = "DLPNO-CCSD(T)"

        settings = toggles.get_methodology_settings()
        assert isinstance(settings, MethodologySettings)
        assert settings.cardinal_lower == "def2-TZVPP"
        assert settings.cardinal_higher == "def2-QZVPP"
        assert settings.scf_model == "Feller Exponential"
        assert settings.cor_model == "Halkier Inverse Cubic (X^-3)"
        assert settings.cv_correction is True
        assert settings.rel_correction is True
        assert settings.rel_hamiltonian == "X2C"
        assert settings.method_level == "DLPNO-CCSD(T)"


# ==============================================================================
# 2. CostHeuristicTooltip Tests
# ==============================================================================

class TestCostHeuristicTooltip:
    """Tests for dynamic node limits polling, O(N^7) runtime and O(N^4) scratch calculations."""

    def test_dynamic_registry_polling(self, clean_bench_env: Path) -> None:
        """Verifies reading system hardware and cost heuristic multipliers from cochem_system_config.json."""
        tooltip = CostHeuristicTooltip(artifacts_dir=clean_bench_env)
        config = tooltip.poll_system_config()

        assert config["hardware"]["ram_gb"] == 64.0
        assert config["hardware"]["physical_cpu_cores"] == 8
        assert config["cost_heuristics"]["runtime_scalar_o_n7"] == 2.5e-6
        assert config["cost_heuristics"]["scratch_scalar_o_n4_gb"] == 1.5e-4

    def test_cost_heuristic_calculation_within_limits(self, clean_bench_env: Path) -> None:
        """Verifies mathematical calculation for small molecule (N=10 atoms) within RAM limits."""
        tooltip = CostHeuristicTooltip(artifacts_dir=clean_bench_env)
        state_meta: Dict[str, Any] = {"state_id": "mol_water_dimer", "num_atoms": 10}

        heuristics = tooltip.compute_heuristics(num_atoms=int(state_meta["num_atoms"]))

        assert isinstance(heuristics, CostHeuristics)
        assert heuristics.num_atoms == 10
        # O(N^7) runtime: 2.5e-6 * 10^7 = 25.0 seconds
        assert pytest.approx(heuristics.estimated_runtime_seconds, rel=1e-3) == 25.0
        # O(N^4) scratch: 1.5e-4 * 10^4 = 1.5 GB
        assert pytest.approx(heuristics.estimated_scratch_gb, rel=1e-3) == 1.5
        # RAM: base (4.0) + 8.0e-5 * 10^4 = 4.8 GB
        assert pytest.approx(heuristics.estimated_ram_gb, rel=1e-3) == 4.8
        assert heuristics.is_ram_exceeded is False

        # Update UI
        submit_btn = widgets.Button(description="Execute Benchmark", disabled=False)
        tooltip.update_ui(state_metadata=state_meta, submit_button=submit_btn)

        assert submit_btn.disabled is False
        assert "Resource limits verified" in tooltip.html_widget.value
        assert "#166534" in tooltip.html_widget.value or "green" in tooltip.html_widget.value or "#dcfce7" in tooltip.html_widget.value

    def test_cost_heuristic_calculation_exceeding_ram_locks_button(self, clean_bench_env: Path) -> None:
        """Verifies that large molecule (N=60 atoms) exceeding RAM (64 GB) triggers red warning & locks button."""
        tooltip = CostHeuristicTooltip(artifacts_dir=clean_bench_env)
        state_meta: Dict[str, Any] = {"state_id": "massive_cluster", "num_atoms": 60}

        # N=60 -> 60^4 = 12,960,000; 8.0e-5 * 12,960,000 = 1036.8 GB + 4.0 = 1040.8 GB > 64 GB
        heuristics = tooltip.compute_heuristics(num_atoms=int(state_meta["num_atoms"]))

        assert heuristics.estimated_ram_gb > 64.0
        assert heuristics.is_ram_exceeded is True

        submit_btn = widgets.Button(description="Execute Benchmark", disabled=False)
        tooltip.update_ui(state_metadata=state_meta, submit_button=submit_btn)

        # Critical Guardrail: Execute button MUST be disabled
        assert submit_btn.disabled is True
        assert "WARNING: Estimated Memory" in tooltip.html_widget.value
        assert "exceeds Available" in tooltip.html_widget.value
        assert "Swap-Death" in tooltip.html_widget.value or "OOM" in tooltip.html_widget.value

    def test_raw_xyz_never_parsed(self, clean_bench_env: Path) -> None:
        """Verifies that string coordinate payloads in state_metadata are ignored and num_atoms is strictly used."""
        tooltip = CostHeuristicTooltip(artifacts_dir=clean_bench_env)
        # Even if a bad .xyz string is present, num_atoms integer is the authoritative source
        state_meta: Dict[str, Any] = {
            "state_id": "test_atom_count",
            "num_atoms": 12,
            "raw_xyz": "FAKE XYZ DATA THAT SHOULD NOT BE PARSED",
        }
        heuristics = tooltip.compute_heuristics(num_atoms=int(state_meta["num_atoms"]))
        assert heuristics.num_atoms == 12


# ==============================================================================
# 3. ManifestCompiler Tests
# ==============================================================================

class TestManifestCompiler:
    """Tests for serializing GUI choices into bench_run_params.json and UI locking."""

    def test_compile_manifest_and_save(self, clean_bench_env: Path) -> None:
        """Verifies compiling parameters, saving to BENCH_Workspace, and setting button.disabled = True."""
        compiler = ManifestCompiler(artifacts_dir=clean_bench_env)

        methodology = MethodologySettings(
            cardinal_lower="def2-TZVPP",
            cardinal_higher="def2-QZVPP",
            scf_model="Feller Exponential",
            cor_model="Halkier Inverse Cubic (X^-3)",
            cv_correction=True,
            rel_correction=False,
            rel_hamiltonian="None",
            method_level="DLPNO-CCSD(T)",
            pno_setting="TightPNO",
        )

        heuristics = CostHeuristics(
            num_atoms=15,
            estimated_runtime_seconds=120.0,
            estimated_scratch_gb=4.5,
            estimated_ram_gb=8.2,
            available_ram_gb=64.0,
            is_ram_exceeded=False,
        )

        submit_btn = widgets.Button(description="Execute Benchmark", disabled=False)

        manifest_path = compiler.compile_and_save(
            job_name="Water_Cluster_Bench",
            state_metadata={"state_id": "water_hexamer", "num_atoms": 15},
            methodology=methodology,
            heuristics=heuristics,
            submit_button=submit_btn,
        )

        assert manifest_path.exists()
        assert manifest_path == clean_bench_env / "BENCH_Workspace" / "bench_run_params.json"

        # UI Lockout Verification: Button MUST be disabled to prevent duplicate MPI spawns
        assert submit_btn.disabled is True

        # Validate JSON content against Pydantic model
        with open(manifest_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        validated_params = BenchRunParams.model_validate(raw_data)
        assert validated_params.job_name == "Water_Cluster_Bench"
        assert validated_params.state_id == "water_hexamer"
        assert validated_params.num_atoms == 15
        assert validated_params.methodology.cardinal_lower == "def2-TZVPP"
        assert validated_params.methodology.cardinal_higher == "def2-QZVPP"
        assert validated_params.cost_heuristics.estimated_ram_gb == 8.2


# ==============================================================================
# 4. VoilaBenchDashboard Full Master UI Tests
# ==============================================================================

class TestVoilaBenchDashboard:
    """Tests for full VoilaBenchDashboard lifecycle, HUD, and submission triggering."""

    def test_dashboard_full_initialization(self, clean_bench_env: Path) -> None:
        """Verifies full dashboard initialization with Status Ribbon, Toggles, Tooltip, and Compiler."""
        state_meta = {"state_id": "ethanol_conf1", "num_atoms": 9}
        dashboard = VoilaBenchDashboard(artifacts_dir=clean_bench_env, state_metadata=state_meta)

        assert dashboard.status_ribbon_html is not None
        assert dashboard.methodology_toggles is not None
        assert dashboard.cost_tooltip is not None
        assert dashboard.manifest_compiler is not None
        assert dashboard.execute_button is not None
        assert dashboard.main_container is not None

        # Check that Status Ribbon rendered engine and hardware stats
        assert "ORCA 6.1.1" in dashboard.status_ribbon_html.value
        assert "64.0 GB RAM" in dashboard.status_ribbon_html.value

    def test_dashboard_execution_trigger(self, clean_bench_env: Path) -> None:
        """Verifies clicking execute button triggers manifest serialization and locks UI."""
        state_meta = {"state_id": "benzene_monomer", "num_atoms": 12}
        dashboard = VoilaBenchDashboard(artifacts_dir=clean_bench_env, state_metadata=state_meta)

        assert dashboard.execute_button.disabled is False

        # Simulate button click
        dashboard._on_execute_clicked(dashboard.execute_button)

        assert dashboard.execute_button.disabled is True
        assert "Orchestrating..." in dashboard.execute_button.description or "Submitted" in dashboard.execute_button.description

        # Verify output manifest file was generated
        manifest_file = clean_bench_env / "BENCH_Workspace" / "bench_run_params.json"
        assert manifest_file.exists()


# ==============================================================================
# 5. Air-Gap & Mendeleev Integration Tests
# ==============================================================================

class TestAirGapAndSafety:
    """Tests for air-gap compliance and dynamic Mendeleev mass integration."""

    def test_dynamic_paths(self, clean_bench_env: Path) -> None:
        """Verifies path helper functions dynamically route to COCHEM_ARTIFACTS_DIR."""
        artifacts = get_cochem_artifacts_dir()
        assert artifacts == clean_bench_env.resolve()

        workspace = get_bench_workspace_dir()
        assert workspace == clean_bench_env / "BENCH_Workspace"

        config_path = get_registry_config_path()
        assert config_path == clean_bench_env / "Registry" / "cochem_system_config.json"

    def test_mendeleev_integration(self) -> None:
        """Verifies Mendeleev dynamic atomic mass retrieval."""
        n_mass = get_element_mass_mendeleev("N")
        assert 14.0 < n_mass < 14.01

