"""Zero-Mock Unit and Integration Tests for Air-Gap Enforcement Trap (scripts/airgap_trap.py).

Defends the Tripartite Workspace Air-Gap within the CI/CD pipeline by ensuring
that static execution repositories remain free of heavy, transient, or restricted
computational artifacts (.h5, .xyz, .gbw, .tmp, .log).

Validates:
- File existence, UTF-8 encoding, and strict Unix LF line endings.
- Absolute Zero-Mock compliance (all tests run on physical directories via tmp_path).
- Accurate detection of blocked extensions (.h5, .xyz, .gbw, .tmp, .log).
- Case insensitivity for blocked extensions (.H5, .XYZ, .GBW, .TMP, .LOG).
- Safe scanning with paths containing spaces, special symbols, and Unicode.
- Proper directory exclusions (.git, .venv, .trash, __pycache__, .pytest_cache).
- Git repository scanning (null-byte safe git ls-files -z) and pure filesystem fallback.
- CLI execution via subprocess with strict exit code 0 (clean) and exit code 1 (violations).
- Clean status of the actual physical CoChem-BASE static repository.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Add repo root and scripts to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from airgap_trap import (  # noqa: E402
    BLOCKED_EXTENSIONS,
    AirgapScanResult,
    format_violation_report,
    is_blocked_file,
    scan_repository,
)


@pytest.fixture
def script_path() -> Path:
    """Fixture providing the absolute path to scripts/airgap_trap.py."""
    path = SCRIPTS_DIR / "airgap_trap.py"
    assert path.exists(), f"airgap_trap.py does not exist at {path}"
    return path


def test_airgap_trap_script_exists_and_non_empty(script_path: Path) -> None:
    """Verify that scripts/airgap_trap.py exists and contains substantive code."""
    stat = script_path.stat()
    assert stat.st_size > 1000, f"Script size too small ({stat.st_size} bytes)"
    assert script_path.is_file(), "airgap_trap.py must be a regular file"


def test_airgap_trap_encoding_and_lf_endings(script_path: Path) -> None:
    """Validate that scripts/airgap_trap.py has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = script_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "airgap_trap.py contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "airgap_trap.py contains Windows CRLF line endings"
    assert b"\n" in raw_bytes, "airgap_trap.py missing newline characters"


def test_is_blocked_file_canonical_extensions() -> None:
    """Validate is_blocked_file identifies canonical restricted extensions."""
    blocked_set = set(BLOCKED_EXTENSIONS)

    assert is_blocked_file(Path("dataset.h5"), blocked_set) == (True, ".h5")
    assert is_blocked_file(Path("geometry.xyz"), blocked_set) == (True, ".xyz")
    assert is_blocked_file(Path("orbitals.gbw"), blocked_set) == (True, ".gbw")
    assert is_blocked_file(Path("scratch.tmp"), blocked_set) == (True, ".tmp")
    assert is_blocked_file(Path("orca_run.log"), blocked_set) == (True, ".log")

    # Allowed extensions
    assert is_blocked_file(Path("main.py"), blocked_set) == (False, "")
    assert is_blocked_file(Path("README.md"), blocked_set) == (False, "")
    assert is_blocked_file(Path("config.json"), blocked_set) == (False, "")
    assert is_blocked_file(Path("pipeline.yml"), blocked_set) == (False, "")
    assert is_blocked_file(Path("pyproject.toml"), blocked_set) == (False, "")


def test_is_blocked_file_case_insensitivity() -> None:
    """Validate is_blocked_file operates case-insensitively."""
    blocked_set = set(BLOCKED_EXTENSIONS)

    assert is_blocked_file(Path("landscape.H5"), blocked_set) == (True, ".h5")
    assert is_blocked_file(Path("cluster.XYZ"), blocked_set) == (True, ".xyz")
    assert is_blocked_file(Path("wavefunction.GBW"), blocked_set) == (True, ".gbw")
    assert is_blocked_file(Path("temp_scratch.TMP"), blocked_set) == (True, ".tmp")
    assert is_blocked_file(Path("simulation.LOG"), blocked_set) == (True, ".log")
    assert is_blocked_file(Path("mixed_case.XyZ"), blocked_set) == (True, ".xyz")


def test_is_blocked_file_dotfiles_and_multipart() -> None:
    """Validate is_blocked_file detects dotfiles (.h5, .xyz) and multi-part extensions (data.h5.bak)."""
    blocked_set = set(BLOCKED_EXTENSIONS)

    # Direct dotfile names
    assert is_blocked_file(Path(".h5"), blocked_set) == (True, ".h5")
    assert is_blocked_file(Path(".XYZ"), blocked_set) == (True, ".xyz")
    assert is_blocked_file(Path(".gbw"), blocked_set) == (True, ".gbw")
    assert is_blocked_file(Path(".tmp"), blocked_set) == (True, ".tmp")
    assert is_blocked_file(Path(".log"), blocked_set) == (True, ".log")

    # Multi-part extensions
    assert is_blocked_file(Path("calculation.h5.bak"), blocked_set) == (True, ".h5")
    assert is_blocked_file(Path("coords.XYZ.old"), blocked_set) == (True, ".xyz")
    assert is_blocked_file(Path("run.tmp.1"), blocked_set) == (True, ".tmp")

    # False positive resistance
    assert is_blocked_file(Path("xyz_parser.py"), blocked_set) == (False, "")
    assert is_blocked_file(Path("h5py_loader.py"), blocked_set) == (False, "")
    assert is_blocked_file(Path("changelog.md"), blocked_set) == (False, "")


def test_clean_directory_scan_passes(tmp_path: Path) -> None:
    """Validate that a clean directory passes air-gap checks with 0 violations."""
    # Populate standard allowed files
    (tmp_path / "main.py").write_text("print('Hello CoChem')", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Project CoChem", encoding="utf-8")
    (tmp_path / "config.json").write_text('{"mode": "production"}', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'", encoding="utf-8")

    sub = tmp_path / "src" / "pkg"
    sub.mkdir(parents=True)
    (sub / "module.py").write_text("def run(): pass", encoding="utf-8")

    result: AirgapScanResult = scan_repository(tmp_path, use_git=False)

    assert result.is_clean is True
    assert result.violation_count == 0
    assert len(result.violations) == 0
    assert result.scanned_files_count == 5


def test_blocked_extensions_detected_in_filesystem_scan(tmp_path: Path) -> None:
    """Validate that each blocked artifact type is detected with accurate metadata."""
    # Create one of each restricted file type
    (tmp_path / "matrix.h5").write_bytes(b"\x00" * 32)
    (tmp_path / "water_dimer.xyz").write_text("6\n\nO 0 0 0\nH 0 0 1\n", encoding="utf-8")
    (tmp_path / "mo_coeff.gbw").write_bytes(b"\x00" * 64)
    (tmp_path / "scratch_001.tmp").write_text("temp", encoding="utf-8")
    (tmp_path / "calc_output.log").write_text("ORCA TERMINATED", encoding="utf-8")
    (tmp_path / "clean_code.py").write_text("import sys", encoding="utf-8")

    result: AirgapScanResult = scan_repository(tmp_path, use_git=False)

    assert result.is_clean is False
    assert result.violation_count == 5

    found_exts = {v.extension for v in result.violations}
    assert found_exts == {".h5", ".xyz", ".gbw", ".tmp", ".log"}


def test_nested_subdirectories_detection(tmp_path: Path) -> None:
    """Validate detection of restricted artifacts placed deep within directory hierarchies."""
    nested = tmp_path / "level1" / "level2" / "level3" / "computations"
    nested.mkdir(parents=True)

    (nested / "deep_calc.h5").write_bytes(b"\x00" * 16)
    (nested / "valid_script.py").write_text("x = 1", encoding="utf-8")

    result: AirgapScanResult = scan_repository(tmp_path, use_git=False)

    assert result.is_clean is False
    assert result.violation_count == 1
    assert result.violations[0].extension == ".h5"
    assert "deep_calc.h5" in result.violations[0].relative_path


def test_safe_scanning_spaces_and_unicode(tmp_path: Path) -> None:
    """Validate safe scanning of paths containing spaces and Unicode characters."""
    special_dir = tmp_path / "Folder with Spaces & Symbols" / "Квантовая_Химия"
    special_dir.mkdir(parents=True)

    (special_dir / "Конформер 01.xyz").write_text("3\n\nH2O", encoding="utf-8")
    (special_dir / "clean script.py").write_text("pass", encoding="utf-8")

    result: AirgapScanResult = scan_repository(tmp_path, use_git=False)

    assert result.is_clean is False
    assert result.violation_count == 1
    assert result.violations[0].extension == ".xyz"


def test_excluded_directories_are_ignored(tmp_path: Path) -> None:
    """Validate that excluded directories (.git, .venv, .trash, etc.) are ignored."""
    for excluded in [".git", ".venv", ".trash", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"]:
        ex_dir = tmp_path / excluded
        ex_dir.mkdir(parents=True, exist_ok=True)
        (ex_dir / f"restricted_{excluded}.tmp").write_text("scratch", encoding="utf-8")
        (ex_dir / f"cached_{excluded}.log").write_text("log", encoding="utf-8")
        (ex_dir / f"data_{excluded}.h5").write_bytes(b"\x00" * 8)

    # Valid root code file
    (tmp_path / "app.py").write_text("x = 42", encoding="utf-8")

    result: AirgapScanResult = scan_repository(tmp_path, use_git=False)

    assert result.is_clean is True
    assert result.violation_count == 0
    assert result.scanned_files_count == 1


def test_custom_additional_extensions(tmp_path: Path) -> None:
    """Validate custom additional blocked extensions."""
    (tmp_path / "output.dat").write_text("data", encoding="utf-8")
    (tmp_path / "source.py").write_text("pass", encoding="utf-8")

    # Default scan should pass (dat is not in default blocked set)
    res_default = scan_repository(tmp_path, use_git=False)
    assert res_default.is_clean is True

    # Scan with custom .dat blocked
    res_custom = scan_repository(tmp_path, blocked_extensions=[".dat"], use_git=False)
    assert res_custom.is_clean is False
    assert res_custom.violation_count == 1
    assert res_custom.violations[0].extension == ".dat"


def test_git_repository_scanning_with_null_bytes(tmp_path: Path) -> None:
    """Validate git ls-files -z scanning on a physical git repository."""
    # Initialize a physical git repo in tmp_path
    try:
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "TestAgent"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@cochem.local"], check=True, capture_output=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Git CLI not available for git-specific integration test")

    (tmp_path / "allowed.py").write_text("y = 10", encoding="utf-8")
    (tmp_path / "geometry.xyz").write_text("3\n\nN2", encoding="utf-8")

    subprocess.run(["git", "-C", str(tmp_path), "add", "allowed.py", "geometry.xyz"], check=True, capture_output=True)

    result = scan_repository(tmp_path, use_git=True)

    assert result.scan_method == "git_ls_files"
    assert result.is_clean is False
    assert result.violation_count == 1
    assert result.violations[0].extension == ".xyz"


def test_scan_invalid_paths(tmp_path: Path) -> None:
    """Validate proper exception raising on invalid directory paths."""
    with pytest.raises(FileNotFoundError):
        scan_repository(tmp_path / "non_existent_folder_xyz_123")

    dummy_file = tmp_path / "file.txt"
    dummy_file.write_text("not a dir", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        scan_repository(dummy_file)


def test_format_violation_report_structure(tmp_path: Path) -> None:
    """Validate that format_violation_report generates structured remediation text."""
    (tmp_path / "scratch.tmp").write_text("data", encoding="utf-8")
    result = scan_repository(tmp_path, use_git=False)

    report = format_violation_report(result)
    assert "[AIR-GAP ENFORCEMENT TRAP]" in report
    assert "VIOLATIONS DETECTED" in report
    assert "scratch.tmp" in report
    assert "REMEDIATION REQUIRED" in report


def test_cli_clean_repository_exit_code_zero(tmp_path: Path) -> None:
    """Validate CLI execution returns exit code 0 when repository is clean."""
    (tmp_path / "code.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "doc.md").write_text("# Doc", encoding="utf-8")

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "airgap_trap.py"),
        "--repo-root",
        str(tmp_path),
        "--no-git",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0, f"Expected 0, got {proc.returncode}. STDERR: {proc.stderr}"
    assert "[PASSED] CLEAN" in proc.stdout


def test_cli_violation_repository_exit_code_one(tmp_path: Path) -> None:
    """Validate CLI execution returns exit code 1 when restricted artifacts exist."""
    (tmp_path / "forbidden.gbw").write_bytes(b"\x00" * 16)

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "airgap_trap.py"),
        "--repo-root",
        str(tmp_path),
        "--no-git",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 1, f"Expected 1, got {proc.returncode}"
    assert "[FAILED] VIOLATIONS DETECTED" in proc.stderr
    assert "forbidden.gbw" in proc.stderr


def test_cli_help_flag() -> None:
    """Validate CLI --help returns exit code 0 and prints usage information."""
    cmd = [sys.executable, str(SCRIPTS_DIR / "airgap_trap.py"), "--help"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0
    assert "usage: airgap_trap" in proc.stdout


def test_real_cochem_base_repo_is_airgap_compliant() -> None:
    """Validate that the actual physical CoChem-BASE static repository is currently 100% air-gap clean."""
    result: AirgapScanResult = scan_repository(REPO_ROOT, use_git=True)

    if not result.is_clean:
        violation_details = "\n".join([f"{v.relative_path} ({v.extension})" for v in result.violations])
        pytest.fail(f"Static CoChem-BASE repo contains restricted artifacts:\n{violation_details}")

    assert result.is_clean is True
    assert result.violation_count == 0
