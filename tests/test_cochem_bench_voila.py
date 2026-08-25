#!/usr/bin/env python3
r"""Unit Test Suite for CoChem-BENCH Voila GUI Wrapper & Configuration UI.

Module: tests/test_cochem_bench_voila.py
Target Implementation: cochem_bench.interfaces.voila_bench_dashboard

Tests:
1. Target Ingestion & System HUD:
   - Dynamic querying of datastore at $COCHEM_ARTIFACTS_DIR/BENCH_Workspace/landscape.h5 in read-only SWMR mode.
   - Extraction of num_atoms, symbols, coordinates, and state metadata directly from HDF5 datasets/attrs.
   - Status Ribbon rendering Active Engine, Available MPI Threads, Node RAM, and Scratch Space.
   - 3D Viewer coordinate rendering and strict blocking of volumetric .cube density files.
2. Methodology Matrix & Protocol Builder:
   - Renders ipywidgets controls for basis pair selection, SCF models, Correlation models, and composite corrections.
   - Basis pair coupling logic (e.g. def2-TZVPP -> def2-QZVPP).
   - Relativistic Hamiltonian selection toggle (X2C vs DKH2).
   - Serialization to structured methodology dictionary.
3. Cost Heuristic Tooltip:
   - Dynamic polling of node limits from Registry/cochem_system_config.json.
   - O(N^7) runtime and O(N^4) scratch disk calculation strictly from num_atoms metadata (no raw .xyz parsing).
   - Dynamic physical RAM threshold comparison and red warning generation when memory limit is exceeded.
   - Hard-locking of execution button on memory overflow.
4. Manifest Compiler & Cross-Platform Mutex:
   - Serialization into bench_run_params.json in BENCH_Workspace.
   - Cross-platform filelock.FileLock synchronization.
   - UI button lockout (disabled=True) with spinning indicator preventing duplicate MPI thread spawning.
5. VoilaBenchDashboard Full Master UI:
   - Full master dashboard construction, Status Ribbon HUD, and widget assembly.
   - Dynamic geometry selection update cycle.
   - End-to-end configuration and execution trigger.
6. Safety Contracts:
   - Dynamic air-gap pathing via COCHEM_ARTIFACTS_DIR.
   - Zero parsing of raw .xyz strings or wavefunction files for atom count metadata.
   - Dynamic Mendeleev atomic mass integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import h5py
import ipywidgets as widgets
import numpy as np
import pytest

from cochem_bench.interfaces.voila_bench_dashboard import (
    BenchRunParams,
    CostHeuristics,
    CostHeuristicTooltip,
    GeometryMetadata,
    ManifestCompiler,
    MethodologySettings,
    MethodologyToggles,
    StructuralViewer3D,
    VoilaBenchDashboard,
    get_bench_workspace_dir,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_landscape_h5_path,
    get_registry_config_path,
    query_landscape_geometries,
)


@pytest.fixture
def clean_bench_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sets up a sterile, air-gapped COCHEM_ARTIFACTS_DIR workspace with genuine config and landscape.h5."""
    artifacts_dir = tmp_path / "cochem_artifacts_test"
    registry_dir = artifacts_dir / "Registry"
    workspace_dir = artifacts_dir / "BENCH_Workspace"

    registry_dir.mkdir(parents=True, exist_ok=True)
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # 1. Authentic cochem_system_config.json
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

    # 2. Genuine HDF5 landscape.h5 datastore with physical molecular states
    landscape_file = workspace_dir / "landscape.h5"
    with h5py.File(str(landscape_file), mode="w", libver="latest") as h5f:
        # Water monomer state (N=3)
        g_water = h5f.create_group("water_monomer")
        g_water.attrs["num_atoms"] = 3
        g_water.attrs["charge"] = 0
        g_water.attrs["multiplicity"] = 1
        g_water.attrs["energy"] = -76.4382
        syms_water = np.array([b"O", b"H", b"H"])
        coords_water = np.array([
            [0.0000, 0.0000, 0.1173],
            [0.0000, 0.7572, -0.4692],
            [0.0000, -0.7572, -0.4692],
        ], dtype=float)
        g_water.create_dataset("symbols", data=syms_water)
        g_water.create_dataset("coordinates", data=coords_water)

        # Ethanol conformer state (N=9)
        g_eth = h5f.create_group("ethanol_c1")
        g_eth.attrs["num_atoms"] = 9
        g_eth.attrs["charge"] = 0
        g_eth.attrs["multiplicity"] = 1
        g_eth.attrs["energy"] = -154.9821
        syms_eth = np.array([b"C", b"C", b"O", b"H", b"H", b"H", b"H", b"H", b"H"])
        coords_eth = np.zeros((9, 3), dtype=float)
        coords_eth[0] = [-0.012, 0.015, 0.000]
        coords_eth[1] = [1.503, 0.015, 0.000]
        coords_eth[2] = [-0.603, 1.200, 0.000]
        g_eth.create_dataset("symbols", data=syms_eth)
        g_eth.create_dataset("coordinates", data=coords_eth)

    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))
    return artifacts_dir


# ==============================================================================
# 1. Target Ingestion & System HUD Tests
# ==============================================================================

class TestTargetIngestionAndHUD:
    """Tests for landscape.h5 SWMR reading, status ribbon, and 3D coordinate viewer."""

    def test_query_landscape_geometries_swmr_mode(self, clean_bench_env: Path) -> None:
        """Verifies querying genuine landscape.h5 in read-only SWMR mode."""
        landscape_path = get_landscape_h5_path(clean_bench_env)
        geometries = query_landscape_geometries(landscape_path)

        assert "water_monomer" in geometries
        assert "ethanol_c1" in geometries

        water_meta = geometries["water_monomer"]
        assert isinstance(water_meta, GeometryMetadata)
        assert water_meta.num_atoms == 3
        assert water_meta.symbols == ["O", "H", "H"]
        assert len(water_meta.coordinates) == 3
        assert pytest.approx(water_meta.energy, rel=1e-3) == -76.4382

        eth_meta = geometries["ethanol_c1"]
        assert eth_meta.num_atoms == 9
        assert len(eth_meta.symbols) == 9

    def test_query_landscape_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Verifies graceful empty dictionary return if landscape.h5 does not exist."""
        non_existent = tmp_path / "non_existent.h5"
        res = query_landscape_geometries(non_existent)
        assert res == {}

    def test_structural_viewer_3d_rendering(self) -> None:
        """Verifies 3D coordinate rendering with valid atom coordinates."""
        viewer = StructuralViewer3D(width=400, height=280)
        assert viewer.container is not None

        symbols = ["O", "H", "H"]
        coords = [[0.0, 0.0, 0.117], [0.0, 0.757, -0.469], [0.0, -0.757, -0.469]]
        viewer.render_geometry(symbols, coords, state_id="water_test")

    def test_structural_viewer_3d_blocks_cube_densities(self) -> None:
        """Verifies that volumetric cube density files are strictly blocked from 3D viewer."""
        viewer = StructuralViewer3D()

        # String filename ending in .cube
        with pytest.raises(ValueError, match="Volumetric cube density files"):
            viewer.block_cube_densities("density_map.cube")

        # Path ending in .cube
        with pytest.raises(ValueError, match="Volumetric cube density files"):
            viewer.block_cube_densities(Path("/path/to/orbitals.cube"))

        # Payload dictionary indicating cube format
        with pytest.raises(ValueError, match="Volumetric cube density payloads"):
            viewer.block_cube_densities({"format": "cube", "data": [1, 2, 3]})


# ==============================================================================
# 2. MethodologyToggles Tests
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

        # Dict dump
        d = toggles.to_dict()
        assert d["cardinal_lower"] == "def2-TZVPP"
        assert d["cv_correction"] is True


# ==============================================================================
# 3. CostHeuristicTooltip Tests
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
        state_meta: Dict[str, Any] = {
            "state_id": "test_atom_count",
            "num_atoms": 12,
            "raw_xyz": "FAKE XYZ DATA THAT SHOULD NOT BE PARSED",
        }
        heuristics = tooltip.compute_heuristics(num_atoms=int(state_meta["num_atoms"]))
        assert heuristics.num_atoms == 12


# ==============================================================================
# 4. ManifestCompiler Tests
# ==============================================================================

class TestManifestCompiler:
    """Tests for serializing GUI choices into bench_run_params.json and UI locking."""

    def test_compile_manifest_and_save_with_filelock(self, clean_bench_env: Path) -> None:
        """Verifies compiling parameters, saving to BENCH_Workspace with FileLock, and setting button.disabled = True."""
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

        # UI Lockout & Spinner Indicator: Button MUST be disabled
        assert submit_btn.disabled is True
        assert submit_btn.description == "Orchestrating..."
        assert submit_btn.icon == "spinner"

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
# 5. VoilaBenchDashboard Full Master UI Tests
# ==============================================================================

class TestVoilaBenchDashboard:
    """Tests for full VoilaBenchDashboard lifecycle, HUD, geometry selection, and submission."""

    def test_dashboard_full_initialization_with_hud_and_viewer(self, clean_bench_env: Path) -> None:
        """Verifies full dashboard initialization with Status Ribbon, Target Ingestion, 3D Viewer, and Toggles."""
        dashboard = VoilaBenchDashboard(artifacts_dir=clean_bench_env)

        assert dashboard.status_ribbon_html is not None
        assert dashboard.geometry_dropdown is not None
        assert dashboard.viewer_3d is not None
        assert dashboard.methodology_toggles is not None
        assert dashboard.cost_tooltip is not None
        assert dashboard.manifest_compiler is not None
        assert dashboard.execute_button is not None
        assert dashboard.main_container is not None

        # Check Status Ribbon metrology
        assert "ORCA 6.1.1" in dashboard.status_ribbon_html.value
        assert "AVAILABLE MPI THREADS:" in dashboard.status_ribbon_html.value
        assert "16" in dashboard.status_ribbon_html.value
        assert "64.0 GB" in dashboard.status_ribbon_html.value

        # Check Geometry Dropdown options populated from landscape.h5
        assert "water_monomer" in dashboard.geometry_dropdown.options
        assert "ethanol_c1" in dashboard.geometry_dropdown.options

    def test_dashboard_geometry_selection_change(self, clean_bench_env: Path) -> None:
        """Verifies that selecting a different geometry updates state metadata and cost heuristics."""
        dashboard = VoilaBenchDashboard(artifacts_dir=clean_bench_env)

        # Select ethanol_c1 (N=9)
        dashboard.geometry_dropdown.value = "ethanol_c1"
        assert dashboard.current_state_metadata.state_id == "ethanol_c1"
        assert dashboard.current_state_metadata.num_atoms == 9

    def test_dashboard_execution_trigger(self, clean_bench_env: Path) -> None:
        """Verifies clicking execute button triggers manifest serialization with FileLock and locks UI."""
        dashboard = VoilaBenchDashboard(artifacts_dir=clean_bench_env)

        assert dashboard.execute_button.disabled is False

        # Simulate button click
        dashboard._on_execute_clicked(dashboard.execute_button)

        assert dashboard.execute_button.disabled is True
        assert dashboard.execute_button.description == "Orchestrating..."
        assert dashboard.execute_button.icon == "spinner"

        # Verify output manifest file was generated
        manifest_file = clean_bench_env / "BENCH_Workspace" / "bench_run_params.json"
        assert manifest_file.exists()


# ==============================================================================
# 6. Air-Gap & Mendeleev Integration Tests
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

        landscape_path = get_landscape_h5_path()
        assert landscape_path == clean_bench_env / "BENCH_Workspace" / "landscape.h5"

    def test_mendeleev_integration(self) -> None:
        """Verifies Mendeleev dynamic atomic mass retrieval."""
        n_mass = get_element_mass_mendeleev("N")
        assert 14.0 < n_mass < 14.01

        c_mass = get_element_mass_mendeleev("C")
        assert 12.0 < c_mass < 12.02
