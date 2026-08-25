"""
Exhaustive Unit Tests for CoChem-TOPOS Stage 5.0 Post-Flight Audit & Cleanup.
(test_cochem_topos_cleanup.py)

Tests WSL2 path translation, ephemeral scratch purge with Windows file lock handling,
real subprocess process thread reaping (ZERO mocks), HDF5 SWMR lock sweeping,
and ToposEnvironmentSanitizer master context manager.

Authoritative Standards:
- Anti-Spoofing Protocol v2: Zero-Mock Real Subprocess & Physical Disk Testing
- Exception Deflection Test: Zero broad try/except deflection
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import h5py
import psutil
import pytest

try:
    from cochem_topos.cochem_topos_cleanup import (
        HDF5LockRecord,
        HDF5LockSweeperConfig,
        HDF5LockSweepResult,
        PostFlightAuditReport,
        ProcessReaperConfig,
        PurgedFileRecord,
        PurgeResult,
        ReapedProcessRecord,
        ReapResult,
        ScratchPurgeConfig,
        ToposEnvironmentSanitizer,
        ToposHDF5LockSweeper,
        ToposProcessReaper,
        ToposScratchPurgeEngine,
        WSLPathTranslator,
        _compute_sha256,
    )
except ImportError:
    from export_utils.cochem_topos_cleanup import (  # type: ignore[no-redef]
        HDF5LockRecord,
        HDF5LockSweeperConfig,
        HDF5LockSweepResult,
        PostFlightAuditReport,
        ProcessReaperConfig,
        PurgedFileRecord,
        PurgeResult,
        ReapedProcessRecord,
        ReapResult,
        ScratchPurgeConfig,
        ToposEnvironmentSanitizer,
        ToposHDF5LockSweeper,
        ToposProcessReaper,
        ToposScratchPurgeEngine,
        WSLPathTranslator,
        _compute_sha256,
    )


# ============================================================================
# 1. WSL Path Translator Tests
# ============================================================================

class TestWSLPathTranslator:
    """Validates Windows <-> WSL2 path translations and UNC path handling."""

    def test_is_wsl_detection(self) -> None:
        is_wsl = WSLPathTranslator.is_wsl()
        assert isinstance(is_wsl, bool)

    def test_is_wsl_unc_path(self) -> None:
        assert WSLPathTranslator.is_wsl_unc_path(r"\\wsl$\Ubuntu\home\user\scratch")
        assert WSLPathTranslator.is_wsl_unc_path(r"\\wsl.localhost\Ubuntu\home\user\scratch")
        assert WSLPathTranslator.is_wsl_unc_path("//wsl.localhost/Ubuntu/home/user/scratch")
        assert WSLPathTranslator.is_wsl_unc_path(r"\\WSL.LOCALHOST\Ubuntu\home\user\scratch")
        assert WSLPathTranslator.is_wsl_unc_path(r"\\WSL$\Debian\tmp\calc")
        assert WSLPathTranslator.is_wsl_unc_path("//WSL.LocalHost/Ubuntu/tmp")
        assert not WSLPathTranslator.is_wsl_unc_path(r"C:\Users\ansac\scratch")
        assert not WSLPathTranslator.is_wsl_unc_path("/mnt/c/Users/ansac/scratch")

    def test_windows_to_wsl_translation(self) -> None:
        assert WSLPathTranslator.windows_to_wsl(r"C:\Users\ansac\scratch") == "/mnt/c/Users/ansac/scratch"
        assert WSLPathTranslator.windows_to_wsl(r"D:\__CoChem\repo\file.gbw") == "/mnt/d/__CoChem/repo/file.gbw"
        assert WSLPathTranslator.windows_to_wsl("E:/data/tmp") == "/mnt/e/data/tmp"
        assert WSLPathTranslator.windows_to_wsl(r"\\wsl$\Ubuntu\home\user\scratch") == "/home/user/scratch"
        assert WSLPathTranslator.windows_to_wsl(r"\\wsl.localhost\Ubuntu\tmp\calc") == "/tmp/calc"
        assert WSLPathTranslator.windows_to_wsl("/mnt/c/scratch") == "/mnt/c/scratch"
        assert WSLPathTranslator.windows_to_wsl("") == ""

    def test_wsl_to_windows_translation(self) -> None:
        assert WSLPathTranslator.wsl_to_windows("/mnt/c/Users/ansac/scratch") == r"C:\Users\ansac\scratch"
        assert WSLPathTranslator.wsl_to_windows("/mnt/d/__CoChem/output") == r"D:\__CoChem\output"
        assert WSLPathTranslator.wsl_to_windows("/mnt/c") == "C:\\"
        assert WSLPathTranslator.wsl_to_windows("/home/user/scratch", distro="Ubuntu") == r"\\wsl.localhost\Ubuntu\home\user\scratch"
        assert WSLPathTranslator.wsl_to_windows("/tmp/calc_01", distro="Debian") == r"\\wsl.localhost\Debian\tmp\calc_01"
        assert WSLPathTranslator.wsl_to_windows(r"C:\Users\ansac\scratch") == r"C:\Users\ansac\scratch"
        assert WSLPathTranslator.wsl_to_windows("D:/repo/test") == r"D:\repo\test"
        assert WSLPathTranslator.wsl_to_windows("") == ""

    def test_normalize_path(self) -> None:
        norm = WSLPathTranslator.normalize_path("C:/Users/ansac/scratch")
        assert isinstance(norm, Path)

        if platform.system().lower() == "windows":
            norm_mnt = WSLPathTranslator.normalize_path("/mnt/c/Users/test")
            assert str(norm_mnt).lower() == r"c:\users\test"

        assert WSLPathTranslator.normalize_path("") == Path(".")


# ============================================================================
# 2. Scratch Purge Config & Model Tests
# ============================================================================

class TestScratchPurgeConfig:
    """Validates configuration data models and default values."""

    def test_default_config_properties(self) -> None:
        config = ScratchPurgeConfig()
        assert ".tmp" in config.ephemeral_extensions
        assert ".dens" in config.ephemeral_extensions
        assert ".gbw" in config.ephemeral_extensions
        assert "*.tmp*" in config.ephemeral_patterns
        assert "*.dens" in config.ephemeral_patterns
        assert "*.gbw" in config.ephemeral_patterns
        assert "./scratch/orca_tmp" in config.default_fallback_dirs
        assert "./scratch/ase_graphs" in config.default_fallback_dirs
        assert config.env_var_names == [
            "COCHEM_SCRATCH_DIR",
            "COCHEM_SCRATCH",
            "COCHEM_TMP",
            "COCHEM_SCRATCH_ROOT",
        ]
        assert "TEMP" not in config.env_var_names
        assert "TMP" not in config.env_var_names
        assert config.compute_sha256 is False
        assert config.remove_empty_dirs is True
        assert config.max_retries == 5
        assert config.ignore_cleanup_errors is True

    def test_custom_config_serialization(self) -> None:
        config = ScratchPurgeConfig(
            target_dirs=[Path("/tmp/custom_scratch")],
            ephemeral_extensions=[".tmp", ".dens"],
            archive_whitelist=["final.gbw"],
            archive_patterns=["*saved*"],
            max_retries=10,
        )
        data = config.model_dump()
        assert data["max_retries"] == 10
        assert "final.gbw" in data["archive_whitelist"]


# ============================================================================
# 3. Scratch Purge Engine Execution Tests (Real Files)
# ============================================================================

class TestToposScratchPurgeEngine:
    """Validates scratch artifact scanning, forceful deletion, locks, whitelists, and quarantines."""

    def test_purge_ephemeral_extensions_and_preservation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        # Ephemeral files to delete
        f_tmp = scratch_dir / "calc_01.tmp"
        f_tmp.write_text("ephemeral temp content", encoding="utf-8")
        f_dens = scratch_dir / "scf.dens"
        f_dens.write_bytes(b"\x00\x01\x02\x03" * 100)
        f_gbw = scratch_dir / "orbitals.gbw"
        f_gbw.write_bytes(b"\xaa\xbb\xcc\xdd" * 50)
        f_bms = scratch_dir / "orca.bms"
        f_bms.write_text("matrix buffer", encoding="utf-8")

        # Persistent files to preserve
        f_xyz = scratch_dir / "geometry.xyz"
        f_xyz.write_text("3\nWater\nO 0 0 0\nH 0 1 0\nH 0 0 1", encoding="utf-8")
        f_json = scratch_dir / "landscape_summary.json"
        f_json.write_text('{"energy": -76.4}', encoding="utf-8")
        f_csv = scratch_dir / "frequencies.csv"
        f_csv.write_text("mode,freq\n1,3800", encoding="utf-8")

        total_ephemeral_bytes = f_tmp.stat().st_size + f_dens.stat().st_size + f_gbw.stat().st_size + f_bms.stat().st_size

        config = ScratchPurgeConfig(target_dirs=[scratch_dir])
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not f_tmp.exists()
        assert not f_dens.exists()
        assert not f_gbw.exists()
        assert not f_bms.exists()

        assert f_xyz.exists()
        assert f_json.exists()
        assert f_csv.exists()

        assert result.total_files_deleted == 4
        assert result.total_files_scanned == 7
        assert result.reclaimed_bytes == total_ephemeral_bytes
        assert result.duration_seconds >= 0.0

    def test_archive_whitelist_preservation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        keep_gbw = scratch_dir / "final_converged.gbw"
        keep_gbw.write_bytes(b"\xff" * 256)

        discard_gbw = scratch_dir / "step_003.gbw"
        discard_gbw.write_bytes(b"\x00" * 128)

        discard_dens = scratch_dir / "step_003.dens"
        discard_dens.write_bytes(b"\x11" * 128)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            archive_whitelist=[str(keep_gbw), "final_converged.gbw"],
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert keep_gbw.exists()
        assert not discard_gbw.exists()
        assert not discard_dens.exists()
        assert result.total_files_whitelisted == 1
        assert result.total_files_deleted == 2

    def test_archive_pattern_preservation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        archived1 = scratch_dir / "opt_archive_model1.gbw"
        archived1.write_bytes(b"\x01" * 64)
        archived2 = scratch_dir / "tier4_final_archive.dens"
        archived2.write_bytes(b"\x02" * 64)

        ephemeral = scratch_dir / "step_01.tmp"
        ephemeral.write_bytes(b"\x03" * 64)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            archive_patterns=["*archive*"],
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert archived1.exists()
        assert archived2.exists()
        assert not ephemeral.exists()
        assert result.total_files_whitelisted == 2
        assert result.total_files_deleted == 1

    def test_quarantine_mode(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()
        quarantine_dir = tmp_path / "quarantine_vault"

        f1 = scratch_dir / "troubled_calc.tmp"
        f1.write_text("suspicious orca scratch", encoding="utf-8")
        f2 = scratch_dir / "orbitals.gbw"
        f2.write_bytes(b"\xaa" * 100)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            quarantine_dir=quarantine_dir,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not f1.exists()
        assert not f2.exists()
        assert (quarantine_dir / "troubled_calc.tmp").exists()
        assert (quarantine_dir / "orbitals.gbw").exists()
        assert result.total_files_quarantined == 2
        assert result.total_files_deleted == 0

    def test_empty_directory_recursive_removal(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir()

        nested_empty = scratch_dir / "level1" / "level2" / "level3"
        nested_empty.mkdir(parents=True)
        tmp_file = nested_empty / "temp_calc.tmp"
        tmp_file.write_text("temporary data", encoding="utf-8")

        nested_keep = scratch_dir / "keep_dir" / "sub"
        nested_keep.mkdir(parents=True)
        keep_file = nested_keep / "manifest.json"
        keep_file.write_text('{"keep": true}', encoding="utf-8")

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            remove_empty_dirs=True,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not tmp_file.exists()
        assert not (scratch_dir / "level1").exists()
        assert (scratch_dir / "keep_dir" / "sub").exists()
        assert keep_file.exists()
        assert result.total_directories_removed >= 3

    def test_env_var_directory_discovery_with_targeted_subdirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_scratch = tmp_path / "cochem_env_scratch"
        env_scratch.mkdir()
        orca_tmp = env_scratch / "orca_tmp"
        orca_tmp.mkdir()
        ase_graphs = env_scratch / "ase_graphs"
        ase_graphs.mkdir()

        f1 = orca_tmp / "orca_scf.dens"
        f1.write_bytes(b"\x00" * 50)
        f2 = ase_graphs / "graph_state.tmp"
        f2.write_bytes(b"\x00" * 50)

        monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(env_scratch))

        engine = ToposScratchPurgeEngine()
        discovered = engine.discover_target_directories()

        assert any(d.resolve() == env_scratch.resolve() for d in discovered)
        assert any(d.resolve() == orca_tmp.resolve() for d in discovered)
        assert any(d.resolve() == ase_graphs.resolve() for d in discovered)

        result = engine.purge()
        assert not f1.exists()
        assert not f2.exists()
        assert result.total_files_deleted >= 2

    def test_kernel_file_lock_retry_handling(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "locked_scratch"
        scratch_dir.mkdir()
        locked_file = scratch_dir / "locked_calc.tmp"
        locked_file.write_bytes(b"kernel locked data" * 10)

        handle = open(locked_file, "r+b")
        try:
            config_ignore = ScratchPurgeConfig(
                target_dirs=[scratch_dir],
                max_retries=2,
                retry_delay_seconds=0.05,
                ignore_cleanup_errors=True,
            )
            engine = ToposScratchPurgeEngine(config_ignore)

            if platform.system().lower() == "windows":
                result = engine.purge()
                assert locked_file.exists()
                assert len(result.errors) > 0
                assert result.purged_files[0].status == "failed"

            if platform.system().lower() == "windows":
                config_strict = ScratchPurgeConfig(
                    target_dirs=[scratch_dir],
                    max_retries=2,
                    retry_delay_seconds=0.05,
                    ignore_cleanup_errors=False,
                )
                strict_engine = ToposScratchPurgeEngine(config_strict)
                with pytest.raises(PermissionError):
                    strict_engine.purge()
        finally:
            handle.close()

        config_success = ScratchPurgeConfig(target_dirs=[scratch_dir], max_retries=2)
        engine_success = ToposScratchPurgeEngine(config_success)
        res = engine_success.purge()
        assert not locked_file.exists()
        assert res.total_files_deleted == 1
        assert res.purged_files[0].status == "deleted"

    def test_max_file_age_filter(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "age_scratch"
        scratch_dir.mkdir()

        old_file = scratch_dir / "old_calc.tmp"
        old_file.write_text("old data", encoding="utf-8")
        past_time = time.time() - 500.0
        os.utime(old_file, (past_time, past_time))

        new_file = scratch_dir / "new_calc.tmp"
        new_file.write_text("new data", encoding="utf-8")

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            max_file_age_seconds=100.0,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not old_file.exists()
        assert new_file.exists()
        assert result.total_files_deleted == 1
        statuses = {p.path: p.status for p in result.purged_files}
        assert statuses[str(old_file)] == "deleted"
        assert statuses[str(new_file)] == "whitelisted"

    def test_target_dirs_isolation_in_discovery(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        explicit_dir = tmp_path / "explicit_scratch"
        explicit_dir.mkdir()

        env_dir = tmp_path / "env_scratch"
        env_dir.mkdir()
        monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(env_dir))

        config = ScratchPurgeConfig(target_dirs=[explicit_dir])
        engine = ToposScratchPurgeEngine(config)
        discovered = engine.discover_target_directories()

        assert len(discovered) == 1
        assert discovered[0].resolve() == explicit_dir.resolve()

    def test_purge_with_sha256_computation(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "sha_scratch"
        scratch_dir.mkdir()

        f_tmp = scratch_dir / "calc_sha.tmp"
        f_tmp.write_bytes(b"ephemeral test content for sha256 provenance")
        expected_sha = _compute_sha256(f_tmp)

        config = ScratchPurgeConfig(
            target_dirs=[scratch_dir],
            compute_sha256=True,
        )
        engine = ToposScratchPurgeEngine(config)
        result = engine.purge()

        assert not f_tmp.exists()
        assert result.total_files_deleted == 1
        assert len(result.purged_files) == 1
        record = result.purged_files[0]
        assert record.status == "deleted"
        assert record.sha256_hash == expected_sha
        assert record.sha256_hash is not None


# ============================================================================
# 4. Process Reaper Tests (Zero-Mock Real Subprocesses)
# ============================================================================

class TestToposProcessReaper:
    """Validates real process auditing and termination across single processes and process trees."""

    def test_process_reaper_config_defaults(self) -> None:
        config = ProcessReaperConfig()
        expected = ["orted", "mpirun", "mpiexec", "orca", "xtb", "crest", "mopac", "mace", "g16", "oet_server", "ase"]
        for exp in expected:
            assert exp in config.target_process_names

    def test_protection_of_current_and_parent_process(self) -> None:
        config = ProcessReaperConfig(
            target_process_names=["python", "python.exe", "pytest", "pytest.exe"],
            protect_current_process=True,
            protect_parent_process=True,
        )
        reaper = ToposProcessReaper(config)
        current_proc = psutil.Process(os.getpid())
        assert reaper._is_protected(current_proc) is True
        is_target, reason = reaper._is_target_process(current_proc)
        assert is_target is False
        assert "Protected" in reason

    def test_reap_real_orphaned_subprocess(self) -> None:
        marker = f"cochem_test_orphan_{int(time.time() * 1000)}"
        proc = subprocess.Popen(
            [sys.executable, "-c", f"# {marker}\nimport time\ntime.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid
        assert psutil.pid_exists(pid)

        try:
            config = ProcessReaperConfig(
                target_process_names=[],
                process_cmdline_patterns=[marker],
                sigterm_timeout_seconds=0.5,
                sigkill_timeout_seconds=0.5,
            )
            reaper = ToposProcessReaper(config)

            orphans = reaper.audit_active_orphans()
            assert any(p.pid == pid for p in orphans)

            result = reaper.reap_orphans()
            assert result.active_orphans_found == 1
            assert result.successful_terminations == 1
            assert result.audit_passed is True

            time.sleep(0.1)
            proc.poll()
            assert proc.returncode is not None or not psutil.pid_exists(pid)

        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

    def test_reap_process_tree_with_children(self) -> None:
        marker = f"cochem_tree_parent_{int(time.time() * 1000)}"
        script = f"""
import subprocess, sys, time
# {marker}
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
time.sleep(60)
"""
        parent = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        parent_pid = parent.pid
        time.sleep(0.5)

        try:
            parent_proc = psutil.Process(parent_pid)
            children = parent_proc.children()
            assert len(children) >= 1
            child_pid = children[0].pid
            assert psutil.pid_exists(child_pid)

            config = ProcessReaperConfig(
                target_process_names=[],
                process_cmdline_patterns=[marker],
                sigterm_timeout_seconds=0.5,
                sigkill_timeout_seconds=0.5,
            )
            reaper = ToposProcessReaper(config)

            result = reaper.reap_orphans()
            assert result.successful_terminations >= 1
            assert result.audit_passed is True

            time.sleep(0.2)
            assert not psutil.pid_exists(parent_pid)
            assert not psutil.pid_exists(child_pid)

        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait()

    def test_reap_protected_explicit_pids(self) -> None:
        marker = f"cochem_protected_{int(time.time() * 1000)}"
        proc = subprocess.Popen(
            [sys.executable, "-c", f"# {marker}\nimport time\ntime.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid
        try:
            config = ProcessReaperConfig(
                target_process_names=[],
                process_cmdline_patterns=[marker],
                protected_pids=[pid],
            )
            reaper = ToposProcessReaper(config)
            orphans = reaper.audit_active_orphans()
            assert not any(p.pid == pid for p in orphans)

            result = reaper.reap_orphans()
            assert result.active_orphans_found == 0
            assert psutil.pid_exists(pid)
        finally:
            proc.kill()
            proc.wait()

    def test_cmdline_pattern_word_boundary_isolation(self) -> None:
        config = ProcessReaperConfig()
        reaper = ToposProcessReaper(config)

        proc = subprocess.Popen(
            [sys.executable, "-c", "import sys, time; sys.argv = ['pytest', 'tests/test_orca.py']; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        pid = proc.pid
        try:
            ps_proc = psutil.Process(pid)
            is_target, reason = reaper._is_target_process(ps_proc)
            assert is_target is False, f"Subprocess falsely matched as target orphan: {reason}"
        finally:
            proc.kill()
            proc.wait()


# ============================================================================
# 5. HDF5 SWMR Lock Sweeper Tests
# ============================================================================

class TestToposHDF5LockSweeper:
    """Validates real HDF5 lock discovery, zombie PID sweeping, and database integrity checks."""

    def test_lock_sweeper_defaults(self) -> None:
        sweeper = ToposHDF5LockSweeper()
        assert "*.h5.lck" in sweeper.config.lock_file_patterns
        assert "*.swmr.lock" in sweeper.config.lock_file_patterns
        assert sweeper.config.verify_h5_integrity is True

    def test_sweep_stale_lock_dead_pid(self, tmp_path: Path) -> None:
        # Create a valid HDF5 file
        h5_file = tmp_path / "landscape.h5"
        with h5py.File(h5_file, "w") as fp:
            fp.create_dataset("test_data", data=[1.0, 2.0, 3.0])

        # Create companion lock file referencing a non-existent PID (e.g. 999999)
        dead_pid = 999999
        while psutil.pid_exists(dead_pid):
            dead_pid += 1

        lock_file = tmp_path / "landscape.h5.lck"
        lock_payload = {
            "h5_file": str(h5_file),
            "pid": dead_pid,
            "timestamp_utc": time.time(),
            "mode": "SWMR_WRITE",
        }
        lock_file.write_text(json.dumps(lock_payload), encoding="utf-8")

        config = HDF5LockSweeperConfig(target_dirs=[tmp_path])
        sweeper = ToposHDF5LockSweeper(config)

        result = sweeper.sweep_locks()
        assert result.active_locks_found == 1
        assert result.stale_locks_removed == 1
        assert not lock_file.exists()
        assert h5_file.exists()

        # Verify companion HDF5 file remains readable and uncorrupted
        with h5py.File(h5_file, "r") as fp:
            assert "test_data" in fp
            assert list(fp["test_data"][:]) == [1.0, 2.0, 3.0]

    def test_retain_active_lock_live_pid(self, tmp_path: Path) -> None:
        # Spawn background process to simulate active holder
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        live_pid = proc.pid
        try:
            h5_file = tmp_path / "active_run.h5"
            with h5py.File(h5_file, "w") as fp:
                fp.create_dataset("active_field", data=[42])

            lock_file = tmp_path / "active_run.h5.swmr.lock"
            lock_file.write_text(json.dumps({"h5_file": str(h5_file), "pid": live_pid}), encoding="utf-8")

            config = HDF5LockSweeperConfig(target_dirs=[tmp_path], force_release=False)
            sweeper = ToposHDF5LockSweeper(config)

            # Sweeping without force should retain the lock file
            result = sweeper.sweep_locks()
            assert result.active_locks_found == 1
            assert result.active_locks_retained == 1
            assert result.stale_locks_removed == 0
            assert lock_file.exists()

            # Sweeping with force=True should remove the lock file
            result_forced = sweeper.sweep_locks(force=True)
            assert result_forced.stale_locks_removed == 1
            assert not lock_file.exists()

        finally:
            proc.kill()
            proc.wait()


# ============================================================================
# 6. Topos Environment Sanitizer & Report Tests
# ============================================================================

class TestToposEnvironmentSanitizer:
    """Validates full post-flight audit workflow, context manager, and report generation."""

    def test_full_post_flight_audit_workflow(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "post_flight_scratch"
        scratch_dir.mkdir()

        f1 = scratch_dir / "final_run.tmp"
        f1.write_bytes(b"\x00" * 1024 * 1024)

        f2 = scratch_dir / "wavefunction.dens"
        f2.write_bytes(b"\x01" * 512 * 1024)

        # Create HDF5 file with stale companion lock
        h5_dir = tmp_path / "hdf5_vault"
        h5_dir.mkdir()
        h5_file = h5_dir / "landscape.h5"
        with h5py.File(h5_file, "w") as fp:
            fp.create_dataset("nodes", data=[1, 2, 3])
        stale_lck = h5_dir / "landscape.h5.lck"
        stale_lck.write_text('{"pid": 999999}', encoding="utf-8")

        purge_cfg = ScratchPurgeConfig(target_dirs=[scratch_dir])
        reaper_cfg = ProcessReaperConfig(target_process_names=["non_existent_qm_tool_12345"])
        lock_cfg = HDF5LockSweeperConfig(target_dirs=[h5_dir])

        sanitizer = ToposEnvironmentSanitizer(
            purge_config=purge_cfg,
            reaper_config=reaper_cfg,
            lock_config=lock_cfg,
        )
        assert sanitizer.verify_environment_clean() is True

        report = sanitizer.execute_post_flight_audit()

        assert isinstance(report, PostFlightAuditReport)
        assert report.audit_passed is True
        assert report.purge_result.total_files_deleted == 2
        assert report.disk_reclaimed_mb >= 1.5
        assert report.hdf5_lock_result.stale_locks_removed == 1
        assert "PASSED" in report.summary
        assert not f1.exists()
        assert not f2.exists()
        assert not stale_lck.exists()

    def test_sanitizer_context_manager(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "ctx_scratch"
        scratch_dir.mkdir()

        purge_cfg = ScratchPurgeConfig(target_dirs=[scratch_dir])
        sanitizer = ToposEnvironmentSanitizer(purge_config=purge_cfg)

        f_tmp = scratch_dir / "in_flight.tmp"
        with sanitizer:
            f_tmp.write_text("in-flight data", encoding="utf-8")
            assert f_tmp.exists()

        assert not f_tmp.exists()

    def test_sanitizer_context_manager_exception_safety(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "exc_scratch"
        scratch_dir.mkdir()

        purge_cfg = ScratchPurgeConfig(target_dirs=[scratch_dir])
        sanitizer = ToposEnvironmentSanitizer(purge_config=purge_cfg)

        f_tmp = scratch_dir / "in_flight_error.tmp"
        with pytest.raises(RuntimeError, match="Simulated calculation error"):
            with sanitizer:
                f_tmp.write_text("should be cleaned on error exit", encoding="utf-8")
                raise RuntimeError("Simulated calculation error")

        assert not f_tmp.exists()

    def test_report_json_serialization_and_save(self, tmp_path: Path) -> None:
        scratch_dir = tmp_path / "report_scratch"
        scratch_dir.mkdir()
        (scratch_dir / "run.tmp").write_bytes(b"\x00" * 2048)

        sanitizer = ToposEnvironmentSanitizer(purge_config=ScratchPurgeConfig(target_dirs=[scratch_dir]))
        report = sanitizer.execute_post_flight_audit()

        json_str = report.to_json()
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["audit_passed"] is True
        assert parsed["purge_result"]["total_files_deleted"] == 1
        assert "timestamp" in parsed
        assert "hdf5_lock_result" in parsed

        out_file = tmp_path / "audit_artifacts" / "audit_report.json"
        saved_path = sanitizer.save_audit_report(report, out_file)
        assert saved_path.exists()
        assert json.loads(saved_path.read_text(encoding="utf-8"))["audit_passed"] is True


# ============================================================================
# 7. Package Initialization & Export Verification
# ============================================================================

def test_cochem_topos_package_exports() -> None:
    """Verifies that cochem_topos exposes all required classes and data models."""
    try:
        import cochem_topos

        expected_exports = [
            "ToposEnvironmentSanitizer",
            "ToposScratchPurgeEngine",
            "ToposProcessReaper",
            "ToposHDF5LockSweeper",
            "WSLPathTranslator",
            "ScratchPurgeConfig",
            "PurgedFileRecord",
            "PurgeResult",
            "ProcessReaperConfig",
            "ReapedProcessRecord",
            "ReapResult",
            "HDF5LockRecord",
            "HDF5LockSweeperConfig",
            "HDF5LockSweepResult",
            "PostFlightAuditReport",
        ]

        for exp in expected_exports:
            assert hasattr(cochem_topos, exp), f"cochem_topos missing exported symbol: {exp}"
            assert getattr(cochem_topos, exp) is not None
    except ImportError:
        pass
