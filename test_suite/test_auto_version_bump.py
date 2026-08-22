"""Zero-Mock Unit and Integration Tests for Version Auto-Bumping Hook (scripts/auto_version_bump.py).

Validates:
- File existence, UTF-8 encoding, and strict Unix LF line endings.
- Absolute Zero-Mock compliance (all tests run on physical directories via tmp_path).
- Semantic Versioning (SemVer 2.0.0) parsing, comparison, and bumping (major, minor, patch).
- Conventional Commit message analysis for automatic bump determination.
- Central version file updates in pyproject.toml and package __init__.py.
- Git repository operations (branch detection, commit inspection, pre-push, post-merge hook handling).
- Hook installation into .git/hooks.
- CLI execution via subprocess with strict exit codes and dry-run guarantees.
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

from auto_version_bump import (  # type: ignore[import-not-found]  # noqa: E402
    BumpType,
    analyze_commits_for_bump,
    bump_version_string,
    determine_next_version,
    find_version_files,
    get_git_hooks_dir,
    handle_post_merge_hook,
    handle_pre_push_hook,
    install_git_hook,
    is_main_branch,
    parse_semver,
    read_version_from_file,
    update_file_version,
    update_repository_version,
)


@pytest.fixture
def script_path() -> Path:
    """Fixture providing the absolute path to scripts/auto_version_bump.py."""
    path = SCRIPTS_DIR / "auto_version_bump.py"
    assert path.exists(), f"auto_version_bump.py does not exist at {path}"
    return path


def test_auto_version_bump_script_exists_and_non_empty(script_path: Path) -> None:
    """Verify that scripts/auto_version_bump.py exists and contains substantive code."""
    stat = script_path.stat()
    assert stat.st_size > 1000, f"Script size too small ({stat.st_size} bytes)"
    assert script_path.is_file(), "auto_version_bump.py must be a regular file"


def test_auto_version_bump_encoding_and_lf_endings(script_path: Path) -> None:
    """Validate that scripts/auto_version_bump.py has no UTF-8 BOM and strictly uses Unix LF line endings."""
    raw_bytes = script_path.read_bytes()
    assert not raw_bytes.startswith(b"\xef\xbb\xbf"), "auto_version_bump.py contains UTF-8 BOM"
    assert b"\r\n" not in raw_bytes, "auto_version_bump.py contains Windows CRLF line endings"
    assert b"\n" in raw_bytes, "auto_version_bump.py missing newline characters"


# =============================================================================
# SemVer 2.0.0 Parsing & Bumping Tests
# =============================================================================


def test_semver_parsing_standard() -> None:
    """Test parsing of standard semver strings."""
    v = parse_semver("0.1.0")
    assert v.major == 0
    assert v.minor == 1
    assert v.patch == 0
    assert v.prerelease is None
    assert v.build is None
    assert str(v) == "0.1.0"


def test_semver_parsing_with_prerelease_and_build() -> None:
    """Test parsing of semver strings with pre-release tags and build metadata."""
    v1 = parse_semver("1.2.3-alpha.1")
    assert v1.major == 1
    assert v1.minor == 2
    assert v1.patch == 3
    assert v1.prerelease == "alpha.1"
    assert str(v1) == "1.2.3-alpha.1"

    v2 = parse_semver("2.0.0-rc.2+build.123")
    assert v2.major == 2
    assert v2.minor == 0
    assert v2.patch == 0
    assert v2.prerelease == "rc.2"
    assert v2.build == "build.123"
    assert str(v2) == "2.0.0-rc.2+build.123"


def test_semver_parsing_invalid_raises() -> None:
    """Test that invalid semver strings raise ValueError."""
    with pytest.raises(ValueError):
        parse_semver("invalid-version")

    with pytest.raises(ValueError):
        parse_semver("1.2")

    with pytest.raises(ValueError):
        parse_semver("v1.2.3.4")


def test_semver_comparisons() -> None:
    """Test ordering and comparison of SemVer objects."""
    v1 = parse_semver("0.1.0")
    v2 = parse_semver("0.1.1")
    v3 = parse_semver("0.2.0")
    v4 = parse_semver("1.0.0")

    assert v1 < v2 < v3 < v4
    assert v1 == parse_semver("0.1.0")
    assert v4 > v3


def test_semver_bumping_rules() -> None:
    """Test semver bumping calculations for patch, minor, and major increments."""
    v = parse_semver("0.1.0")

    # Patch bump
    patch_v = v.bump(BumpType.PATCH)
    assert str(patch_v) == "0.1.1"

    # Minor bump (resets patch to 0)
    minor_v = v.bump(BumpType.MINOR)
    assert str(minor_v) == "0.2.0"

    # Major bump (resets minor and patch to 0)
    major_v = v.bump(BumpType.MAJOR)
    assert str(major_v) == "1.0.0"


def test_bump_version_string_helper() -> None:
    """Test bump_version_string helper function."""
    assert bump_version_string("0.1.0", "patch") == "0.1.1"
    assert bump_version_string("0.1.0", "minor") == "0.2.0"
    assert bump_version_string("0.1.0", "major") == "1.0.0"
    assert bump_version_string("1.2.3-alpha", "patch") == "1.2.4"


# =============================================================================
# Conventional Commits Analysis Tests
# =============================================================================


def test_analyze_commits_breaking_changes() -> None:
    """Test that breaking change indicators result in MAJOR bump."""
    commits_1 = ["feat!: change public API interface", "fix: minor bug"]
    assert analyze_commits_for_bump(commits_1) == BumpType.MAJOR

    commits_2 = ["fix: bug", "docs: update README\n\nBREAKING CHANGE: removed deprecated method"]
    assert analyze_commits_for_bump(commits_2) == BumpType.MAJOR

    commits_3 = ["refactor(core)!: rebuild state machine"]
    assert analyze_commits_for_bump(commits_3) == BumpType.MAJOR


def test_analyze_commits_features() -> None:
    """Test that feature commits result in MINOR bump when no breaking changes exist."""
    commits = [
        "feat: add new telemetry channel",
        "fix: buffer overflow in socket transport",
        "docs: update manual",
    ]
    assert analyze_commits_for_bump(commits) == BumpType.MINOR

    commits_scoped = ["feat(gui): implement dark mode palette"]
    assert analyze_commits_for_bump(commits_scoped) == BumpType.MINOR


def test_analyze_commits_fixes_and_chores() -> None:
    """Test that fixes, chores, refactors, docs result in PATCH bump."""
    commits_fix = ["fix: resolve off-by-one in loop", "chore: bump dependencies"]
    assert analyze_commits_for_bump(commits_fix) == BumpType.PATCH

    commits_chore = [
        "chore(deps): update ruff",
        "refactor: simplify imports",
        "test: add unit tests",
    ]
    assert analyze_commits_for_bump(commits_chore) == BumpType.PATCH


def test_analyze_commits_empty_or_unstructured() -> None:
    """Test that empty or non-conventional commits default to PATCH bump."""
    assert analyze_commits_for_bump([]) == BumpType.PATCH
    assert analyze_commits_for_bump(["random commit message", "update files"]) == BumpType.PATCH


# =============================================================================
# Physical File Reading & Updating Tests
# =============================================================================


def test_read_and_update_pyproject_toml(tmp_path: Path) -> None:
    """Validate reading and updating version in a physical pyproject.toml."""
    pyproject = tmp_path / "pyproject.toml"
    content = """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "cochem-base"
version = "0.1.0"
description = "Core shell"
"""
    pyproject.write_text(content, encoding="utf-8")

    current_ver = read_version_from_file(pyproject)
    assert current_ver == "0.1.0"

    updated = update_file_version(pyproject, "0.2.0")
    assert updated is True

    new_content = pyproject.read_text(encoding="utf-8")
    assert 'version = "0.2.0"' in new_content
    assert "[build-system]" in new_content
    assert read_version_from_file(pyproject) == "0.2.0"


def test_read_and_update_package_init_py(tmp_path: Path) -> None:
    """Validate reading and updating __version__ in a physical __init__.py file."""
    pkg_dir = tmp_path / "cochem_base"
    pkg_dir.mkdir(parents=True)
    init_file = pkg_dir / "__init__.py"
    content = '''"""CoChem-BASE core package."""
from .config_loader import load_system_config

__version__ = "0.1.0"

__all__ = ["__version__", "load_system_config"]
'''
    init_file.write_text(content, encoding="utf-8")

    current_ver = read_version_from_file(init_file)
    assert current_ver == "0.1.0"

    updated = update_file_version(init_file, "0.1.1")
    assert updated is True

    new_content = init_file.read_text(encoding="utf-8")
    assert '__version__ = "0.1.1"' in new_content
    assert "from .config_loader import load_system_config" in new_content
    assert read_version_from_file(init_file) == "0.1.1"


def test_find_version_files_in_workspace(tmp_path: Path) -> None:
    """Validate discovery of all central version files in a repository directory."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    pkg = tmp_path / "cochem_base"
    pkg.mkdir()
    init_py = pkg / "__init__.py"
    init_py.write_text('__version__ = "0.1.0"\n', encoding="utf-8")

    files = find_version_files(tmp_path)
    assert len(files) >= 2
    assert pyproject in files
    assert init_py in files


def test_update_repository_version_synchronizes_all_files(tmp_path: Path) -> None:
    """Validate updating the entire repository synchronizes all discovered version files."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "cochem-base"\nversion = "0.1.0"\n', encoding="utf-8")

    pkg = tmp_path / "cochem_base"
    pkg.mkdir()
    init_py = pkg / "__init__.py"
    init_py.write_text('__version__ = "0.1.0"\n__all__ = ["__version__"]\n', encoding="utf-8")

    res = update_repository_version(
        repo_root=tmp_path,
        new_version="0.2.0",
        dry_run=False,
    )

    assert res.old_version == "0.1.0"
    assert res.new_version == "0.2.0"
    assert len(res.updated_files) == 2
    assert read_version_from_file(pyproject) == "0.2.0"
    assert read_version_from_file(init_py) == "0.2.0"


def test_update_repository_version_dry_run(tmp_path: Path) -> None:
    """Validate that dry-run mode computes new version without modifying files on disk."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    res = update_repository_version(
        repo_root=tmp_path,
        new_version="0.2.0",
        dry_run=True,
    )

    assert res.old_version == "0.1.0"
    assert res.new_version == "0.2.0"
    assert res.is_dry_run is True
    # File on disk must remain unchanged
    assert read_version_from_file(pyproject) == "0.1.0"


# =============================================================================
# Git Integration & Hook Tests (Physical Git Repo)
# =============================================================================


def test_git_repository_commit_analysis_and_bump(tmp_path: Path) -> None:
    """Validate git repository commits are inspected to determine version bump."""
    try:
        subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True, timeout=15)
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "TestCoder"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "coder@cochem.local"],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Git CLI not available")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")

    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "pyproject.toml"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "chore: initial commit"],
        check=True,
        capture_output=True,
        timeout=15,
    )

    # Add a feature commit
    (tmp_path / "feature.py").write_text("def new_feature(): pass\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "feature.py"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "feat: add awesome new feature"],
        check=True,
        capture_output=True,
        timeout=15,
    )

    next_ver, bump_type = determine_next_version(tmp_path, bump_override="auto")
    assert bump_type == BumpType.MINOR
    assert next_ver == "0.2.0"


def test_is_main_branch_detection(tmp_path: Path) -> None:
    """Validate branch detection for main and master branches."""
    try:
        subprocess.run(
            ["git", "init", "-b", "main", str(tmp_path)],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "TestCoder"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "coder@cochem.local"],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Git CLI not available")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "pyproject.toml"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
        timeout=15,
    )

    assert is_main_branch(tmp_path, target_branches=["main", "master"]) is True

    # Checkout a feature branch
    subprocess.run(
        ["git", "-C", str(tmp_path), "checkout", "-b", "feature/my-branch"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    assert is_main_branch(tmp_path, target_branches=["main", "master"]) is False


def test_get_git_hooks_dir(tmp_path: Path) -> None:
    """Validate get_git_hooks_dir resolves standard git hooks directory."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    hooks_dir = get_git_hooks_dir(tmp_path)
    assert hooks_dir == git_dir / "hooks"


def test_get_git_hooks_dir_non_git_raises(tmp_path: Path) -> None:
    """Validate get_git_hooks_dir raises RuntimeError when not a git repository."""
    with pytest.raises(RuntimeError, match="Not a git repository"):
        get_git_hooks_dir(tmp_path)


def test_install_git_hook(tmp_path: Path) -> None:
    """Validate installation of pre-push or post-merge hooks into .git/hooks/."""
    git_hooks_dir = tmp_path / ".git" / "hooks"
    git_hooks_dir.mkdir(parents=True)

    hook_file = install_git_hook(repo_root=tmp_path, hook_name="pre-push")
    assert hook_file.exists()
    content = hook_file.read_text(encoding="utf-8")
    assert "auto_version_bump.py" in content
    assert "--hook-mode" in content


# =============================================================================
# CLI Execution via Subprocess Tests
# =============================================================================


def test_cli_help_flag() -> None:
    """Validate CLI --help flag returns 0 and prints usage."""
    cmd = [sys.executable, str(SCRIPTS_DIR / "auto_version_bump.py"), "--help"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert "usage: auto_version_bump" in proc.stdout


def test_cli_dry_run_execution(tmp_path: Path) -> None:
    """Validate CLI execution with --dry-run outputs expected next version without altering files."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-pkg"\nversion = "1.0.0"\n', encoding="utf-8")

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "auto_version_bump.py"),
        "--repo-root",
        str(tmp_path),
        "--bump",
        "minor",
        "--dry-run",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert "1.0.0 -> 1.1.0" in proc.stdout
    assert "[DRY RUN]" in proc.stdout

    # File remains 1.0.0
    assert read_version_from_file(pyproject) == "1.0.0"


def test_cli_bump_patch_execution(tmp_path: Path) -> None:
    """Validate CLI execution with --bump patch increments patch version in files."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n', encoding="utf-8")

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "auto_version_bump.py"),
        "--repo-root",
        str(tmp_path),
        "--bump",
        "patch",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert "0.1.0 -> 0.1.1" in proc.stdout
    assert read_version_from_file(pyproject) == "0.1.1"


def test_cli_set_specific_version(tmp_path: Path) -> None:
    """Validate CLI execution with --set-version explicitly updates version."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n', encoding="utf-8")

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "auto_version_bump.py"),
        "--repo-root",
        str(tmp_path),
        "--set-version",
        "2.5.0",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0
    assert "0.1.0 -> 2.5.0" in proc.stdout
    assert read_version_from_file(pyproject) == "2.5.0"


def test_cli_invalid_version_fails(tmp_path: Path) -> None:
    """Validate CLI execution with invalid version returns exit code 1."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n', encoding="utf-8")

    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "auto_version_bump.py"),
        "--repo-root",
        str(tmp_path),
        "--set-version",
        "invalid..version",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert proc.returncode == 1
    assert "Error" in proc.stderr or "Invalid" in proc.stderr


def test_semver_prerelease_ordering_spec_11_4() -> None:
    """Validate SemVer 2.0.0 section 11.4 dot-separated and numeric identifier precedence."""
    # 1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0
    versions = [
        parse_semver("1.0.0-alpha"),
        parse_semver("1.0.0-alpha.1"),
        parse_semver("1.0.0-alpha.beta"),
        parse_semver("1.0.0-beta"),
        parse_semver("1.0.0-beta.2"),
        parse_semver("1.0.0-beta.11"),
        parse_semver("1.0.0-rc.1"),
        parse_semver("1.0.0"),
    ]
    for i in range(len(versions) - 1):
        assert versions[i] < versions[i + 1], f"Expected {versions[i]} < {versions[i + 1]}"
        assert versions[i + 1] > versions[i], f"Expected {versions[i + 1]} > {versions[i]}"
        assert not (versions[i] > versions[i + 1])
        assert versions[i] <= versions[i + 1]


def test_install_git_hook_worktree_pointer(tmp_path: Path) -> None:
    """Validate install_git_hook resolves git hooks directory through .git pointer file."""
    # Simulate worktree / submodule .git pointer file
    real_git_dir = tmp_path / "actual_git_dir"
    real_git_dir.mkdir(parents=True)

    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    (worktree_root / ".git").write_text(f"gitdir: {real_git_dir}\n", encoding="utf-8")

    hook_path = install_git_hook(worktree_root, hook_name="post-merge")
    assert hook_path == real_git_dir / "hooks" / "post-merge"
    assert hook_path.exists()
    assert "auto_version_bump.py" in hook_path.read_text(encoding="utf-8")


def test_handle_pre_push_hook_execution(tmp_path: Path) -> None:
    """Validate handle_pre_push_hook increments version when targeting main branch."""
    try:
        subprocess.run(
            ["git", "init", "-b", "main", str(tmp_path)],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "TestCoder"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "coder@cochem.local"],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Git CLI not available")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "pyproject.toml"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "feat: initial commit"],
        check=True,
        capture_output=True,
        timeout=15,
    )

    # Push to main via stdin
    stdin_line = "refs/heads/main 1111 refs/heads/main 2222"
    exit_code = handle_pre_push_hook(tmp_path, dry_run=False, stdin_input=stdin_line)
    assert exit_code == 0
    assert read_version_from_file(pyproject) == "0.2.0"

    # Switch to feature branch and push feature branch -> should skip
    subprocess.run(
        ["git", "-C", str(tmp_path), "checkout", "-b", "feature/my-feat"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    stdin_feature = "refs/heads/feature/my-feat 1111 refs/heads/feature/my-feat 2222"
    exit_code = handle_pre_push_hook(tmp_path, dry_run=False, stdin_input=stdin_feature)
    assert exit_code == 0
    assert read_version_from_file(pyproject) == "0.2.0"


def test_handle_post_merge_hook_execution(tmp_path: Path) -> None:
    """Validate handle_post_merge_hook increments version when on main branch."""
    try:
        subprocess.run(
            ["git", "init", "-b", "main", str(tmp_path)],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "TestCoder"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "coder@cochem.local"],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Git CLI not available")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nversion = "0.1.0"\n', encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "pyproject.toml"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "fix: small bugfix"],
        check=True,
        capture_output=True,
        timeout=15,
    )

    exit_code = handle_post_merge_hook(tmp_path, dry_run=False)
    assert exit_code == 0
    assert read_version_from_file(pyproject) == "0.1.1"


def test_cli_install_hook_and_hook_mode_execution(tmp_path: Path) -> None:
    """Validate CLI execution with --install-hook and --hook-mode flags."""
    try:
        subprocess.run(
            ["git", "init", "-b", "main", str(tmp_path)],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "TestCoder"],
            check=True,
            capture_output=True,
            timeout=15,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "coder@cochem.local"],
            check=True,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pytest.skip("Git CLI not available")

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test-pkg"\nversion = "0.1.0"\n', encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "pyproject.toml"],
        check=True,
        capture_output=True,
        timeout=15,
    )
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-m", "fix: initial commit"],
        check=True,
        capture_output=True,
        timeout=15,
    )

    # 1. Test CLI --install-hook
    cmd_install = [
        sys.executable,
        str(SCRIPTS_DIR / "auto_version_bump.py"),
        "--repo-root",
        str(tmp_path),
        "--install-hook",
        "pre-push",
    ]
    proc_install = subprocess.run(cmd_install, capture_output=True, text=True, timeout=15)
    assert proc_install.returncode == 0
    assert "Successfully installed" in proc_install.stdout
    assert (tmp_path / ".git" / "hooks" / "pre-push").exists()

    # 2. Test CLI --hook-mode post-merge
    cmd_hook_mode = [
        sys.executable,
        str(SCRIPTS_DIR / "auto_version_bump.py"),
        "--repo-root",
        str(tmp_path),
        "--hook-mode",
        "post-merge",
    ]
    proc_hook = subprocess.run(cmd_hook_mode, capture_output=True, text=True, timeout=15)
    assert proc_hook.returncode == 0
    assert "Merge to main branch detected" in proc_hook.stdout
    assert read_version_from_file(pyproject) == "0.1.1"
