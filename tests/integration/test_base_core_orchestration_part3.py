"""Comprehensive Physical Integration & Anti-Spoof Test Suite for CoChem-BASE Core Orchestration (Part 3).
Covers Prompts 1 through 6 strictly adhering to the Zero-Mock mandate.
"""

from __future__ import annotations

import ast
import hashlib
import os
import pathlib
import sqlite3
import tempfile
from typing import Any, Dict

import pytest

from cochem.core.cochem_sandbox import (
    SandboxConfig,
    SandboxContext,
    SandboxExecutionError,
    SandboxSecurityViolationError,
)
from cochem.core.cochem_constants import (
    PhysicalConstant,
    ElementProperties,
    PhysicalConstantsRegistry,
)
from cochem.plugins.ast_scanner import (
    PluginASTSecurityScanner,
    PluginSecurityViolationError,
    scan_plugin_source,
)
from cochem.plugins.cochem_plugin_manager import (
    PluginInterface,
    PluginLoadError,
    PluginMetadata,
    PluginRegistry,
)
from cochem.core.airgap_coordinator import (
    AirGapViolationError,
    TripartiteAirGapCoordinator,
    TripartiteStorageConfig,
    configure_sqlite_connection,
    get_tier_file_lock,
)


# ==============================================================================
# 1. Ephemeral Sandbox Context & Path Jailbreak Defense Tests
# ==============================================================================
def test_sandbox_lifecycle_and_valid_path_confinement(tmp_path: pathlib.Path) -> None:
    """Verify clean sandbox allocation, root confinement, and valid file resolution."""
    cfg = SandboxConfig(scratch_parent_dir=tmp_path, timeout_seconds=60.0)
    with SandboxContext(cfg) as sbx:
        assert sbx.root.exists()
        assert sbx.root.is_dir()

        child_file = sbx.root / "calc_output.dat"
        child_file.write_text("energy=-76.42", encoding="utf-8")

        validated = sbx.validate_path(child_file)
        assert validated == child_file.resolve()
        assert validated.exists()

        # Relative path inside sandbox
        rel_validated = sbx.validate_path(pathlib.Path("calc_output.dat"))
        assert rel_validated == child_file.resolve()

    # Verify directory was deleted upon context exit
    assert not sbx.root.exists()


def test_sandbox_path_traversal_rejection(tmp_path: pathlib.Path) -> None:
    """Verify path traversal outside sandbox root raises SandboxSecurityViolationError."""
    with SandboxContext(SandboxConfig(scratch_parent_dir=tmp_path)) as sbx:
        escape_targets = [
            pathlib.Path("../../../etc/shadow"),
            pathlib.Path("..") / "secret.key",
            pathlib.Path(tmp_path) / "unauthorized.txt",
        ]
        for target in escape_targets:
            with pytest.raises(SandboxSecurityViolationError):
                sbx.validate_path(target)


def test_sandbox_sibling_directory_collision_rejection(tmp_path: pathlib.Path) -> None:
    """Verify sibling directory path collision attacks are strictly rejected."""
    with SandboxContext(SandboxConfig(scratch_parent_dir=tmp_path)) as sbx:
        sibling_dir = pathlib.Path(str(sbx.root) + "_sibling")
        sibling_dir.mkdir(parents=True, exist_ok=True)
        sibling_target = sibling_dir / "adversarial.txt"
        sibling_target.write_text("breach", encoding="utf-8")

        with pytest.raises(SandboxSecurityViolationError):
            sbx.validate_path(sibling_target)

        sibling_target.unlink()
        sibling_dir.rmdir()


def test_sandbox_reserved_win32_device_names(tmp_path: pathlib.Path) -> None:
    """Verify reserved Win32 device names trigger SandboxSecurityViolationError."""
    with SandboxContext(SandboxConfig(scratch_parent_dir=tmp_path)) as sbx:
        reserved_devices = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM9",
            "LPT1",
            "LPT9",
            "con.txt",
            "nul.dat",
        ]
        for dev in reserved_devices:
            with pytest.raises(SandboxSecurityViolationError):
                sbx.validate_path(pathlib.Path(dev))
            with pytest.raises(SandboxSecurityViolationError):
                sbx.validate_path(sbx.root / dev)


def test_sandbox_ntfs_alternate_data_stream_rejection(tmp_path: pathlib.Path) -> None:
    """Verify NTFS Alternate Data Streams (colon syntax) trigger SandboxSecurityViolationError."""
    with SandboxContext(SandboxConfig(scratch_parent_dir=tmp_path)) as sbx:
        ads_paths = [
            "data.txt:hidden",
            "output.log:$DATA",
            "test.dat:secret_stream",
        ]
        for ads in ads_paths:
            with pytest.raises(SandboxSecurityViolationError):
                sbx.validate_path(pathlib.Path(ads))


def test_sandbox_inactive_validation_rejection() -> None:
    """Verify uninitialized or cleaned-up sandbox raises SandboxExecutionError."""
    sbx = SandboxContext(SandboxConfig())
    with pytest.raises(SandboxExecutionError):
        sbx.validate_path(pathlib.Path("test.txt"))


# ==============================================================================
# 2. Centralized Physical Constants & Dynamic Mendeleev Registry Tests
# ==============================================================================
def test_dynamic_mendeleev_elemental_masses() -> None:
    """Validate dynamic retrieval of atomic weights for C, Fe, and U via mendeleev."""
    mass_c = PhysicalConstantsRegistry.get_element_mass("C")
    mass_fe = PhysicalConstantsRegistry.get_element_mass("Fe")
    mass_u = PhysicalConstantsRegistry.get_element_mass("U")

    assert 12.010 < mass_c < 12.012
    assert 55.84 < mass_fe < 55.85
    assert 238.02 < mass_u < 238.04


def test_dynamic_mendeleev_element_properties() -> None:
    """Validate elemental properties record retrieval from mendeleev."""
    carbon = PhysicalConstantsRegistry.get_element("C")
    assert isinstance(carbon, ElementProperties)
    assert carbon.atomic_number == 6
    assert carbon.symbol == "C"
    assert carbon.name == "Carbon"
    assert 12.010 < carbon.atomic_weight < 12.012
    assert carbon.provenance == "[M]"
    assert carbon.covalent_radius_pyykko is not None
    assert carbon.vdw_radius_bondi is not None

    iron = PhysicalConstantsRegistry.get_element(26)
    assert iron.symbol == "Fe"
    assert iron.atomic_number == 26


def test_fundamental_codata_physical_constants() -> None:
    """Verify CODATA 2018 constants dynamic query and exact SI provenance."""
    # Planck constant
    h = PhysicalConstantsRegistry.get_constant("Planck constant")
    assert isinstance(h, PhysicalConstant)
    assert abs(h.value - 6.62607015e-34) < 1e-42
    assert h.provenance == "[E]"

    # Speed of light
    c = PhysicalConstantsRegistry.get_constant("speed of light in vacuum")
    assert c.value == 299792458.0
    assert c.provenance == "[E]"

    # Avogadro constant
    na = PhysicalConstantsRegistry.get_constant("Avogadro constant")
    assert abs(na.value - 6.02214076e23) < 1e15
    assert na.provenance == "[E]"

    # Boltzmann constant
    kb = PhysicalConstantsRegistry.get_constant("Boltzmann constant")
    assert abs(kb.value - 1.380649e-23) < 1e-30
    assert kb.provenance == "[E]"

    # Thermodynamic standard states
    assert PhysicalConstantsRegistry.STANDARD_TEMPERATURE_K == 298.15
    assert PhysicalConstantsRegistry.STANDARD_PRESSURE_PA == 101325.0


def test_physical_constant_missing_key() -> None:
    """Verify querying an invalid constant key raises KeyError."""
    with pytest.raises(KeyError):
        PhysicalConstantsRegistry.get_constant("NonExistentConstant_9999")


# ==============================================================================
# 3. Hardened Allowlist-Based AST Security Scanner Tests
# ==============================================================================
def test_ast_scanner_blocks_dangerous_execution_vectors() -> None:
    """Verify scanner intercepts direct prohibited modules and commands."""
    malicious_snippets = [
        "import os\nos.system('dir')",
        "import sys\nsys.exit(1)",
        "import subprocess\nsubprocess.run(['dir'])",
        "import socket\ns = socket.socket()",
        "from socket import socket",
        "from subprocess import run",
        "from os import *",
    ]
    for code in malicious_snippets:
        with pytest.raises(PluginSecurityViolationError):
            scan_plugin_source(code)


def test_ast_scanner_blocks_dunder_and_reflection_gadgets() -> None:
    """Verify scanner intercepts dunder navigation, builtins, and dynamic evaluation."""
    gadget_snippets = [
        "x = ().__class__.__bases__[0].__subclasses__()",
        "getattr(__builtins__, 'eval')('1+1')",
        "f = open('output.txt', 'w')",
        "exec('a = 1')",
        "eval('2 + 2')",
        "v = globals()",
        "l = locals()",
        "compile('x = 1', '<str>', 'exec')",
    ]
    for code in gadget_snippets:
        with pytest.raises(PluginSecurityViolationError):
            scan_plugin_source(code)


def test_ast_scanner_allows_whitelisted_scientific_code() -> None:
    """Verify legitimate scientific plugin code passes scan without error."""
    clean_scientific_code = '''
import math
from dataclasses import dataclass
import numpy
from cochem.plugins.cochem_plugin_manager import PluginInterface, PluginMetadata

@dataclass
class ValidComputeModel:
    coefficient: float = 1.0

class ValidScientificPlugin(PluginInterface):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="valid_test_plugin",
            version="1.0.0",
            author="CoChem Test",
            description="Verified scientific unit plugin"
        )

    def initialize(self, context: dict) -> None:
        self.ready = bool(context)

    def execute(self, payload: dict) -> dict:
        val = payload.get("input_val", 0.0)
        return {"result": math.sqrt(abs(val))}

    def teardown(self) -> None:
        self.ready = False
'''
    scan_plugin_source(clean_scientific_code)


# ==============================================================================
# 4. OS-Agnostic Plugin Lifecycle & Fault Tolerance Tests
# ==============================================================================
def test_plugin_lifecycle_and_fault_tolerance(tmp_path: pathlib.Path) -> None:
    """Verify registry registers compliant plugins and isolates non-compliant scripts."""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # 1. Compliant Plugin
    valid_plugin_file = plugin_dir / "valid_calc_plugin.py"
    valid_plugin_file.write_text(
        '''
import math
from cochem.plugins.cochem_plugin_manager import PluginInterface, PluginMetadata

class CompliantCalculator(PluginInterface):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="calc_plugin",
            version="1.0.0",
            author="QA Unit",
            description="Authentic calculation plugin"
        )

    def initialize(self, context: dict) -> None:
        self.init_val = context.get("multiplier", 2.0)

    def execute(self, payload: dict) -> dict:
        x = payload.get("x", 4.0)
        return {"output": x * self.init_val}

    def teardown(self) -> None:
        self.init_val = 0.0
''',
        encoding="utf-8",
    )

    # 2. Malicious Plugin Attempting Subprocess Execution
    malicious_plugin_file = plugin_dir / "malicious_script.py"
    malicious_plugin_file.write_text(
        '''
import os
class MaliciousPlugin:
    def execute(self):
        return os.system('echo compromised')
''',
        encoding="utf-8",
    )

    registry = PluginRegistry(plugin_dir=plugin_dir)
    registered = registry.scan_and_register()

    # The compliant plugin must be registered
    assert "calc_plugin" in registered
    assert len(registered) == 1

    # The malicious plugin must have been skipped without halting the system
    plugin = registry.get_plugin("calc_plugin")
    plugin.initialize({"multiplier": 3.0})
    result = registry.execute_plugin("calc_plugin", {"x": 5.0})
    assert result == {"output": 15.0}
    plugin.teardown()

    # Querying unregistered plugin raises KeyError
    with pytest.raises(KeyError):
        registry.get_plugin("non_existent_plugin")


# ==============================================================================
# 5. Tripartite Storage Air-Gap Coordinator & Concurrency Governor Tests
# ==============================================================================
def test_tripartite_airgap_disjointness_validation(tmp_path: pathlib.Path) -> None:
    """Verify disjoint storage roots validate cleanly and overlapping topologies fail."""
    code_dir = tmp_path / "code_root"
    art_dir = tmp_path / "artifacts_root"
    scr_dir = tmp_path / "scratch_root"

    code_dir.mkdir()
    art_dir.mkdir()
    scr_dir.mkdir()

    cfg = TripartiteStorageConfig(
        code_root=code_dir,
        artifacts_root=art_dir,
        scratch_root=scr_dir,
    )
    coordinator = TripartiteAirGapCoordinator(cfg)
    assert coordinator.config.code_root == code_dir.resolve()

    # Overlapping scratch inside artifacts
    bad_cfg = TripartiteStorageConfig(
        code_root=code_dir,
        artifacts_root=art_dir,
        scratch_root=art_dir / "nested_scratch",
    )
    with pytest.raises(AirGapViolationError):
        TripartiteAirGapCoordinator(bad_cfg)


def test_airgap_workspace_creation_and_artifact_publication(tmp_path: pathlib.Path) -> None:
    """Verify sandboxed workspace creation, path traversal defense, and artifact publication."""
    code_dir = tmp_path / "code_root"
    art_dir = tmp_path / "artifacts_root"
    scr_dir = tmp_path / "scratch_root"
    code_dir.mkdir()
    art_dir.mkdir()
    scr_dir.mkdir()

    coordinator = TripartiteAirGapCoordinator(
        TripartiteStorageConfig(code_root=code_dir, artifacts_root=art_dir, scratch_root=scr_dir)
    )

    # Path traversal attempt in job_id
    with pytest.raises(AirGapViolationError):
        coordinator.create_sandboxed_workspace(job_id="../../escaped_job")

    # Legitimate workspace
    sbx = coordinator.create_sandboxed_workspace(job_id="job_42")
    with sbx as ctx:
        scratch_output = ctx.root / "final_state.json"
        scratch_output.write_text('{"converged": true, "energy": -40.123}', encoding="utf-8")

        # Publish artifact
        dest_path, sha = coordinator.publish_artifact(
            source_path=scratch_output,
            relative_dest=pathlib.Path("runs/job_42_state.json"),
            compute_sha256=True,
        )

        assert dest_path.exists()
        assert dest_path.resolve().is_relative_to(art_dir.resolve())
        assert sha is not None
        assert len(sha) == 64

        # Verify content transferred intact
        assert dest_path.read_text(encoding="utf-8") == '{"converged": true, "energy": -40.123}'


def test_airgap_concurrency_governor(tmp_path: pathlib.Path) -> None:
    """Verify OS-agnostic file locking and SQLite WAL mode configuration."""
    lock_file = tmp_path / "orchestrator.lock"
    lock = get_tier_file_lock(lock_file, timeout_sec=5.0)
    with lock:
        assert lock.is_locked

    # SQLite WAL configuration verification
    db_path = tmp_path / "concurrency_test.db"
    conn = sqlite3.connect(str(db_path))
    configure_sqlite_connection(conn)

    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    assert mode.upper() == "WAL"

    cursor.execute("PRAGMA busy_timeout;")
    timeout_val = cursor.fetchone()[0]
    assert timeout_val >= 30000

    cursor.execute("PRAGMA foreign_keys;")
    fk_val = cursor.fetchone()[0]
    assert fk_val == 1
    conn.close()


# ==============================================================================
# 6. Anti-Spoofing & Zero-Mock AST Audit
# ==============================================================================
def test_zero_mock_ast_audit_across_production_files() -> None:
    """AST audit certifying zero occurrences of stubs, empty pass blocks, or forbidden constructs."""
    from ci_tools.anti_spoof_linter import check_file, load_amnesty

    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent
    amnesty_set = load_amnesty(repo_root)
    total_violations: list[str] = []

    target_production_files = [
        "src/cochem/core/cochem_sandbox.py",
        "src/cochem/core/cochem_constants.py",
        "src/cochem/plugins/ast_scanner.py",
        "src/cochem/plugins/cochem_plugin_manager.py",
        "src/cochem/core/airgap_coordinator.py",
    ]

    for rel_path in target_production_files:
        full_path = repo_root / rel_path
        assert full_path.is_file(), f"Target file '{rel_path}' does not exist!"

        violations = check_file(full_path, repo_root, amnesty_set=amnesty_set)
        for v in violations:
            total_violations.append(f"{v.file_path}:{v.line} [{v.category}] {v.message}")

    assert len(total_violations) == 0, (
        f"Zero-stub compliance violations detected ({len(total_violations)}):\n"
        + "\n".join(total_violations)
    )
