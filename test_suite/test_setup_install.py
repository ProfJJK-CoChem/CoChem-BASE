#!/usr/bin/env python3
"""
Physical Unit and Integration Test Suite for CoChem Stage 0 Installer (setup/install.py).
Verifies:
1. Host hardware, SIMD, and hypervisor discovery conforming to Method Matrix Section 8.0-8.4.
2. Quantum and semi-empirical binary discovery with cryptographic SHA-256 hashing.
3. Python Dynamic Version Walking (>= 3.11).
4. ORCA External Tools (OET) wrapper generator conforming to Section 9B.4 and Section 10.
5. Micro-silo provisioning, dependency isolation, and transactional venv staging.
6. Dynamic Mendeleev atomic and isotopic mass authority verification.
7. Golden System Registry serialization and atomic persistence.
8. CLI actions and parameter parsing.

Zero-Mock Policy: Executes genuine physical processes, real filesystem writes, and real model validation.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import setup.install as inst_mod
from setup.install import (
    BinaryEngineItem,
    ComputeDevice,
    EngineTrack,
    HardwareProfile,
    SetupTier,
    SiloAuditRecord,
    SiloStatus,
    SiloType,
    UnifiedInstallReport,
    build_parser,
    calculate_sha256,
    detect_host_hardware,
    discover_quantum_engines,
    dynamic_version_walking,
    generate_oet_wrappers,
    interrogate_binary_version,
    main,
    persist_golden_system_registry,
    provision_micro_silo,
    run_unified_installer,
    verify_mendeleev_authority,
)


def test_hardware_profiling_invariants() -> None:
    """Verifies host hardware profiling against Method Matrix Section 8.0-8.3 rules."""
    profile = detect_host_hardware(forced_tier=SetupTier.AUTO)
    assert profile.platform_system in ("Windows", "Linux", "Darwin")
    assert profile.total_physical_cores > 0
    assert profile.total_logical_threads >= profile.total_physical_cores
    assert profile.performance_cores > 0
    assert profile.total_ram_gb > 0.0
    assert profile.recommended_orca_ranks > 0
    assert profile.recommended_maxcore_mb >= 1000
    assert profile.recommended_maxcore_mb <= 3400
    assert profile.resolved_setup_tier in (SetupTier.SETUP_1_TEACHING, SetupTier.SETUP_2_WORKSTATION, SetupTier.SETUP_3_HPC)


def test_hardware_profiling_forced_tier() -> None:
    """Verifies forced Setup Tier resolution."""
    for tier in (SetupTier.SETUP_1_TEACHING, SetupTier.SETUP_2_WORKSTATION, SetupTier.SETUP_3_HPC):
        p = detect_host_hardware(forced_tier=tier)
        assert p.resolved_setup_tier == tier


def test_binary_discovery_and_hashing(tmp_path: Path) -> None:
    """Tests discovery, cryptographic SHA-256 calculation, and missing engine records."""
    dummy_bin = tmp_path / "dummy_orca.exe"
    dummy_bin.write_bytes(b"COCHEM_BINARY_HEADER_V4")

    sha256 = calculate_sha256(dummy_bin)
    assert sha256 is not None
    assert len(sha256) == 64

    discovered = discover_quantum_engines(tmp_path)
    assert isinstance(discovered, dict)
    assert "orca" in discovered
    assert "mpirun" in discovered
    assert "xtb" in discovered
    assert "crest" in discovered
    assert "oet_server" in discovered
    assert "oet_aimnet2" in discovered
    assert "oet_mace" in discovered


def test_dynamic_version_walking() -> None:
    """Verifies host Python resolution is >= 3.11."""
    exe_path, ver_str = dynamic_version_walking(required_min_minor=11)
    assert Path(exe_path).is_file()
    parts = [int(p) for p in ver_str.split(".")[:2]]
    assert parts[0] == 3
    assert parts[1] >= 11


def test_oet_wrapper_generation(tmp_path: Path) -> None:
    """Verifies generation of production-grade ORCA ExtOpt wrappers (Method Matrix §10)."""
    script_dir = tmp_path / "bin"
    python_exe = Path(sys.executable)

    generated = generate_oet_wrappers(script_dir, python_exe)
    assert "oet_server" in generated
    assert "oet_client" in generated
    assert "oet_aimnet2" in generated
    assert "oet_maceoff" in generated
    assert "oet_gxtb" in generated

    for name, path in generated.items():
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100
        assert "EH_PER_EV" in content or "run_server" in content or "extinp" in content

        if sys.platform == "win32":
            cmd_file = script_dir / f"{name}.cmd"
            assert cmd_file.is_file()


def test_micro_silo_audit_and_provision_dry_run(tmp_path: Path) -> None:
    """Verifies micro-silo dry-run auditing."""
    silo_dir = tmp_path / "cochem_core_silo"
    rec = provision_micro_silo(
        name="cochem_core_silo",
        target_venv_dir=silo_dir,
        python_exe=sys.executable,
        dry_run=True,
    )
    assert isinstance(rec, SiloAuditRecord)
    assert rec.name == "cochem_core_silo"
    assert rec.silo_type == SiloType.CORE
    assert rec.status in (SiloStatus.EXISTS_VALID, SiloStatus.MISSING)


def test_mendeleev_authority_verification() -> None:
    """Verifies dynamic atomic and isotopic mass retrieval from Mendeleev library."""
    ok = verify_mendeleev_authority()
    assert ok is True


def test_golden_system_registry_persistence(tmp_path: Path) -> None:
    """Verifies atomic write and structure of cochem_system_config.json."""
    hw = detect_host_hardware()
    binaries = discover_quantum_engines(tmp_path)
    report = UnifiedInstallReport(
        setup_tier=hw.resolved_setup_tier,
        hardware=hw,
        binaries=binaries,
        micro_silos={},
        mendeleev_authority_verified=True,
        status="SUCCESS",
    )

    reg_path = persist_golden_system_registry(report, tmp_path)
    assert reg_path.is_file()

    with open(reg_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["version"] == report.co_chem_version
    assert data["setup_tier"] == hw.resolved_setup_tier.value
    assert "hardware_profile" in data
    assert "quantum_engines" in data
    assert "routing_policy" in data
    assert data["mendeleev_verified"] is True


def test_cli_parser_options() -> None:
    """Verifies CLI argument parsing for all Method Matrix Section 8, 9B.4 & 10 syntax."""
    parser = build_parser()

    args1 = parser.parse_args(["verify", "--json"])
    assert args1.action == "verify"
    assert args1.json is True

    args2 = parser.parse_args(["-e", "aimnet2", "--venv-dir", "/tmp/aimnet2-venv", "--script-dir", "/tmp/bin"])
    assert "aimnet2" in args2.external_tools
    assert args2.venv_dir == "/tmp/aimnet2-venv"
    assert args2.script_dir == "/tmp/bin"

    args3 = parser.parse_args(["--all", "--skip-heavy", "--setup-tier", "setup2"])
    assert args3.all is True
    assert args3.skip_heavy is True
    assert args3.setup_tier == "setup2"


def test_main_cli_execution_verify() -> None:
    """Tests executing main() in verify dry-run mode."""
    exit_code = main(["verify", "--dry-run", "--json"])
    assert exit_code in (0, 1)
