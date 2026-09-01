"""# zero-stub anti-spoof verification
Unit and integration tests for NFTP Phase 1: Deterministic Classifier (ci_tools/file_triage_classifier.py).

Physically validates:
- identify_module for single-module repos, multi-module roots, and root scripts.
- Inverted trash logic resolution: files inside .trash/ and trash/ classified as TRASH.
- Dynamic build debris and .egg-info purging across all modules.
- Root-level dist/ and build/ directory artifact purging.
- Configuration and infrastructure files (pytest.ini, tox.ini, .coveragerc, MANIFEST.in, *.ini) classified as KEEP.
- Temp and stale file extensions (.tmp, .temp, .py_broken, .conda_trash) classified as TRASH.
- Full run_classifier execution and per-module manifest serialization.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ci_tools.file_triage_classifier import (
    CONFIRMED_TRASH_MODULES,
    KEEP_EXTENSIONS,
    KEEP_NAMES,
    PURGE_DIRS,
    TRASH_PATTERNS,


    classify_file,
    identify_module,
    run_classifier,
)


def test_identify_module_single_repo() -> None:
    """Validate identify_module when repo_root is a CoChem-* repository."""
    repo_root = Path("D:/__CoChem/GitHub-Repo/CoChem-TOPOS")
    target_file = repo_root / "ci_tools" / "file_triage_classifier.py"
    assert identify_module(target_file, repo_root) == "CoChem-TOPOS"

    base_root = Path("D:/__CoChem/GitHub-Repo/CoChem-BASE")
    base_file = base_root / "src" / "cochem_base" / "core.py"
    assert identify_module(base_file, base_root) == "CoChem-BASE"


def test_identify_module_multi_repo_umbrella() -> None:
    """Validate identify_module when repo_root is an umbrella multi-module root."""
    umbrella_root = Path("D:/__CoChem/GitHub-Repo")
    module_file = umbrella_root / "CoChem-TOPOS" / "ci_tools" / "file_triage_classifier.py"
    assert identify_module(module_file, umbrella_root) == "CoChem-TOPOS"

    other_module = umbrella_root / "CoChem-TORQ" / "src" / "main.py"
    assert identify_module(other_module, umbrella_root) == "CoChem-TORQ"

    root_script = umbrella_root / "orchestrate_all.py"
    assert identify_module(root_script, umbrella_root) is None


def test_trash_directory_classification(tmp_path: Path) -> None:
    """Validate that files inside .trash/ and trash/ are classified as TRASH, never KEEP."""
    repo_root = tmp_path / "CoChem-TOPOS"
    repo_root.mkdir()

    # Source file in .trash/
    trash_source = repo_root / ".trash" / "train.py"
    trash_source.parent.mkdir(parents=True)
    trash_source.write_text("print('abandoned')", encoding="utf-8")

    verdict, reason = classify_file(trash_source, repo_root, "CoChem-TOPOS")
    assert verdict == "TRASH"
    assert "scratch" in reason.lower() or "temp" in reason.lower()

    # Nested file in .trash/
    nested_trash = repo_root / ".trash" / "sub" / "pipeline.py"
    nested_trash.parent.mkdir(parents=True)
    nested_trash.write_text("print('old')", encoding="utf-8")

    verdict, _ = classify_file(nested_trash, repo_root, "CoChem-TOPOS")
    assert verdict == "TRASH"

    # File in trash/ without leading dot
    alt_trash = repo_root / "trash" / "runner.py"
    alt_trash.parent.mkdir(parents=True)
    alt_trash.write_text("print('alt')", encoding="utf-8")

    verdict, _ = classify_file(alt_trash, repo_root, "CoChem-TOPOS")
    assert verdict == "TRASH"


def test_egg_info_and_build_debris_purged(tmp_path: Path) -> None:
    """Validate dynamic .egg-info detection, dist/ and build/ directory artifact purging."""
    repo_root = tmp_path / "CoChem-TOPOS"
    repo_root.mkdir()

    # Module-specific .egg-info files
    egg_info_dir = repo_root / "cochem_topos.egg-info"
    egg_info_dir.mkdir()
    pkg_info = egg_info_dir / "PKG-INFO"
    pkg_info.write_text("Metadata-Version: 2.1", encoding="utf-8")
    sources_txt = egg_info_dir / "SOURCES.txt"
    sources_txt.write_text("setup.py", encoding="utf-8")
    requires_txt = egg_info_dir / "requires.txt"
    requires_txt.write_text("numpy", encoding="utf-8")



    verdict_pkg, _ = classify_file(pkg_info, repo_root, "CoChem-TOPOS")
    assert verdict_pkg == "PURGE"

    verdict_src, _ = classify_file(sources_txt, repo_root, "CoChem-TOPOS")
    assert verdict_src == "PURGE"

    verdict_req, _ = classify_file(requires_txt, repo_root, "CoChem-TOPOS")
    assert verdict_req == "PURGE"

    # dist/ wheel and archive artifacts
    dist_dir = repo_root / "dist"
    dist_dir.mkdir()
    wheel_file = dist_dir / "cochem_topos-0.1.0-py3-none-any.whl"
    wheel_file.write_bytes(b"PK")
    tar_file = dist_dir / "cochem_topos-0.1.0.tar.gz"
    tar_file.write_bytes(b"\x1f\x8b")

    verdict_whl, _ = classify_file(wheel_file, repo_root, "CoChem-TOPOS")
    assert verdict_whl == "PURGE"

    verdict_tar, _ = classify_file(tar_file, repo_root, "CoChem-TOPOS")
    assert verdict_tar == "PURGE"

    # build/ intermediate artifacts
    build_dir = repo_root / "build" / "lib" / "cochem_topos"
    build_dir.mkdir(parents=True)
    build_file = build_dir / "mod.py"
    build_file.write_text("pass", encoding="utf-8")

    verdict_build, _ = classify_file(build_file, repo_root, "CoChem-TOPOS")
    assert verdict_build == "PURGE"


def test_standard_configuration_files_kept(tmp_path: Path) -> None:
    """Validate that standard configuration files (.ini, pytest.ini, tox.ini, etc.) are KEEP."""
    repo_root = tmp_path / "CoChem-TOPOS"
    repo_root.mkdir()

    cfg_names = [
        "pytest.ini",
        "tox.ini",
        ".coveragerc",
        "MANIFEST.in",
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        "requirements.txt",
        "conftest.py",
        ".gitignore",
    ]

    for name in cfg_names:
        cfg_file = repo_root / name
        cfg_file.write_text("# config", encoding="utf-8")
        verdict, _ = classify_file(cfg_file, repo_root, "CoChem-TOPOS")
        assert verdict == "KEEP", f"Expected {name} to be KEEP, got {verdict}"

    # General .ini configuration files
    custom_ini = repo_root / "configs" / "logging.ini"
    custom_ini.parent.mkdir(parents=True)
    custom_ini.write_text("[loggers]\nkeys=root", encoding="utf-8")
    verdict_ini, _ = classify_file(custom_ini, repo_root, "CoChem-TOPOS")
    assert verdict_ini == "KEEP"


def test_temp_and_stale_extensions_trashed(tmp_path: Path) -> None:
    """Validate that temp and stale file extensions (.tmp, .temp, .py_broken, .conda_trash) are TRASH."""
    repo_root = tmp_path / "CoChem-TOPOS"
    repo_root.mkdir()

    stale_files = [
        "pipeline_state.tmp",
        "scratch_record.temp",
        "parser_v1.py_broken",
        "env_state.conda_trash",
        "env_state.conda_trash_1289",
        "audit_trace.bak",
        "audit_trace.bak.1",
        "temp_inspect.py",
        "session.lock",
        "cochem_system_config.json.bak",
    ]

    for name in stale_files:
        stale_file = repo_root / name
        stale_file.write_text("stale data", encoding="utf-8")
        verdict, _ = classify_file(stale_file, repo_root, "CoChem-TOPOS")
        assert verdict == "TRASH", f"Expected {name} to be TRASH, got {verdict}"


def test_source_docs_and_test_verdicts(tmp_path: Path) -> None:
    """Validate source files, test files, markdown docs, and notebooks."""
    repo_root = tmp_path / "CoChem-TOPOS"
    repo_root.mkdir()

    # Source code inside module
    src_file = repo_root / "src" / "cochem_topos" / "engine.py"
    src_file.parent.mkdir(parents=True)
    src_file.write_text("def run():\n    return 42\n", encoding="utf-8")
    v_src, _ = classify_file(src_file, repo_root, "CoChem-TOPOS")
    assert v_src == "KEEP"

    # Root level script without module
    root_script = repo_root / "run_debug.py"
    root_script.write_text("print('debug')", encoding="utf-8")
    v_root, _ = classify_file(root_script, repo_root, None)
    assert v_root == "TRIAGE"

    # Test file (aggressive strategy requires verification)
    test_file = repo_root / "tests" / "test_engine.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    v_test, _ = classify_file(test_file, repo_root, "CoChem-TOPOS")
    assert v_test == "TRIAGE"

    # Regular doc vs Draco blueprint
    doc_file = repo_root / "docs" / "manual.md"
    doc_file.parent.mkdir(parents=True)
    doc_file.write_text("# Manual", encoding="utf-8")
    v_doc, _ = classify_file(doc_file, repo_root, "CoChem-TOPOS")
    assert v_doc == "KEEP"

    draco_file = repo_root / "docs" / "Draco_Blueprint_v1.md"
    draco_file.write_text("# Blueprint", encoding="utf-8")
    v_draco, _ = classify_file(draco_file, repo_root, "CoChem-TOPOS")
    assert v_draco == "TRIAGE"


def test_run_classifier_end_to_end(tmp_path: Path) -> None:
    """Validate full repository walk, manifest generation, and global summary."""
    repo_root = tmp_path / "CoChem-TOPOS"
    repo_root.mkdir()
    out_dir = tmp_path / "output_manifests"

    # Create mixed file structure
    (repo_root / "README.md").write_text("# TOPOS", encoding="utf-8")
    (repo_root / "pytest.ini").write_text("[pytest]", encoding="utf-8")
    (repo_root / "setup.py").write_text("from setuptools import setup", encoding="utf-8")

    src_dir = repo_root / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("code = 1", encoding="utf-8")

    trash_dir = repo_root / ".trash"
    trash_dir.mkdir()
    (trash_dir / "old_app.py").write_text("dead = 1", encoding="utf-8")

    egg_dir = repo_root / "cochem_topos.egg-info"
    egg_dir.mkdir()
    (egg_dir / "PKG-INFO").write_text("info", encoding="utf-8")

    dist_dir = repo_root / "dist"
    dist_dir.mkdir()
    (dist_dir / "pkg.whl").write_bytes(b"binary")

    summary = run_classifier(repo_root, out_dir)

    assert summary["total_files_walked"] > 0
    assert "CoChem-TOPOS" in summary["per_module_counts"]
    counts = summary["per_module_counts"]["CoChem-TOPOS"]

    assert counts.get("KEEP", 0) >= 3  # README.md, pytest.ini, setup.py, app.py
    assert counts.get("TRASH", 0) >= 1  # .trash/old_app.py

    summary_json = out_dir / "triage_summary.json"
    assert summary_json.is_file()
    summary_data = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary_data["total_files_walked"] == summary["total_files_walked"]

    manifest_json = out_dir / "CoChem-TOPOS_triage_manifest.json"
    assert manifest_json.is_file()
    manifest_data = json.loads(manifest_json.read_text(encoding="utf-8"))
    assert manifest_data["module"] == "CoChem-TOPOS"
    assert any(".trash" in f for f in manifest_data["files"].get("TRASH", []))
