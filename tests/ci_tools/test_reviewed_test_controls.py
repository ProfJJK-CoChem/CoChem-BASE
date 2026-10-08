"""Exact control grants cannot authorize native or scientific substitutions."""
from __future__ import annotations

import ast
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from ci_tools.anti_spoof_linter import run_linter
from ci_tools.reviewed_test_controls import (
    APPROVED_SCOPES,
    _identity,
    _index,
    ast_sha256,
    is_reviewed_control,
    validate_test_controls,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def control_layout(tmp_path):
    root = tmp_path / "checkout"
    for relative in {path for path, _ in APPROVED_SCOPES}:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    manifest = tmp_path / "controls.json"
    shutil.copyfile(ROOT / "ci_tools/reviewed_test_controls.json", manifest)
    return root, manifest


def findings(root):
    return run_linter([root / path for path in sorted({path for path, _ in APPROVED_SCOPES})], root)[1]


def rewrite(manifest, payload):
    manifest.write_text(json.dumps(payload), encoding="utf-8")


def refresh_integrity(root, manifest):
    """Simulate regenerating every JSON hash after an unauthorized source edit."""
    payload = json.loads(manifest.read_text())
    for record in payload["controls"]:
        path = root / record["path"]
        scopes, calls = _index(ast.parse(path.read_text()))
        call, function = calls[(record["line"], record["col"])]
        record.update(file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      function=function, function_ast_sha256=ast_sha256(scopes[function]),
                      call_ast_sha256=ast_sha256(call), call=ast.unparse(call))
        record["target"], record["replacement"] = _identity(call)
    rewrite(manifest, payload)


def test_exact_controls_classify_only_intercepts_and_preserve_raw_linter(control_layout):
    root, manifest = control_layout
    raw = findings(root)
    records = validate_test_controls(root, manifest, raw)
    intercepts = [item for rows in raw.values() for item in rows if item.category == "MONKEYPATCH_INTERCEPT"]
    assert len(records) == len(intercepts) == 92
    assert all(is_reviewed_control(item, records) for item in intercepts)
    assert all(not is_reviewed_control(item, records) for rows in raw.values() for item in rows
               if item.category != "MONKEYPATCH_INTERCEPT")
    assert findings(root) == raw


@pytest.mark.parametrize("field,value", [
    ("path", "src/cochem_base/core_engine/engine.py"),
    ("function", "test_unreviewed_native_acceptance"),
    ("line", 1), ("col", 0), ("call_ast_sha256", "0" * 64),
    ("target", "native_engine.run"), ("replacement", "successful_physics"),
    ("category", "OBFUSCATION"), ("category", "PYTEST_SKIP"),
    ("scientific_execution_performed", True), ("boundary", ""),
])
def test_manifest_location_identity_and_category_mutations_fail(control_layout, field, value):
    root, manifest = control_layout
    payload = json.loads(manifest.read_text())
    payload["controls"][0][field] = value
    rewrite(manifest, payload)
    with pytest.raises(ValueError):
        validate_test_controls(root, manifest, findings(root))


@pytest.mark.parametrize("change", ["duplicate", "missing", "unused"])
def test_registry_requires_one_to_one_observed_sites(control_layout, change):
    root, manifest = control_layout
    payload = json.loads(manifest.read_text())
    if change == "duplicate":
        payload["controls"].append(dict(payload["controls"][0]))
    elif change == "missing":
        payload["controls"].pop()
    rewrite(manifest, payload)
    raw = findings(root)
    if change == "unused":
        raw = {}
    with pytest.raises(ValueError):
        validate_test_controls(root, manifest, raw)


def test_whole_owner_byte_change_is_rejected(control_layout):
    root, manifest = control_layout
    path = root / json.loads(manifest.read_text())["controls"][0]["path"]
    path.write_text(path.read_text() + "\n# Unreviewed owner edit.\n")
    with pytest.raises(ValueError, match="owner bytes changed"):
        validate_test_controls(root, manifest, findings(root))


@pytest.mark.parametrize("relative,before,after", [
    ("tests/base/test_lab_project_configuration.py", 'subprocess, "run", control.run', 'subprocess, "Popen", control.run'),
    ("tests/base/test_lab_project_configuration.py", 'subprocess, "run", control.run', 'subprocess, "safe_subprocess_run", control.run'),
    ("tests/base/test_safe_subprocess_owned_cleanup.py", "child = real_popen(command, **kwargs)", "child = object()"),
    ("tests/base/test_mandatory_ecosystem.py", "{'status': 'failed', 'published': False}", "{'status': 'completed', 'published': True}"),
    ("tests/base/test_licensed_codespaces.py", 'setup, "checked_installer", installer', 'setup, "run_native_engine", installer'),
])
def test_fresh_manifest_hashes_cannot_authorize_native_or_completed_science(control_layout, relative, before, after):
    root, manifest = control_layout
    path = root / relative
    source = path.read_text()
    assert source.count(before) == 1
    path.write_text(source.replace(before, after))
    refresh_integrity(root, manifest)
    with pytest.raises(ValueError, match="owner bytes changed|fresh manifest hash is not authorization"):
        validate_test_controls(root, manifest, findings(root))


def test_fresh_hash_cannot_grant_production_path(control_layout):
    root, manifest = control_layout
    payload = json.loads(manifest.read_text())
    record = payload["controls"][0]
    target = root / "src/engine.py"
    target.parent.mkdir()
    shutil.copyfile(root / record["path"], target)
    record.update(path="src/engine.py", file_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    rewrite(manifest, payload)
    with pytest.raises(ValueError, match="production and native paths cannot be granted"):
        validate_test_controls(root, manifest, findings(root))


def test_unrelated_mock_and_obfuscation_findings_are_never_classified(control_layout):
    root, manifest = control_layout
    records = validate_test_controls(root, manifest, findings(root))
    path = root / "tests/base/test_export_topos_evidence.py"
    path.write_text(path.read_text() + "\nimport unittest.mock\nexec('unauthorized')\n")
    refresh_integrity(root, manifest)
    raw = findings(root)
    with pytest.raises(ValueError, match="owner bytes changed"):
        validate_test_controls(root, manifest, raw)
    forbidden = [item for rows in raw.values() for item in rows if item.category in {"MOCK_IMPORT", "OBFUSCATION"}]
    assert {item.category for item in forbidden} == {"MOCK_IMPORT", "OBFUSCATION"}
    assert all(not is_reviewed_control(item, records) for item in forbidden)


def test_changed_external_replacement_helper_is_rejected_even_with_fresh_json_hash(control_layout):
    root, manifest = control_layout
    path = root / "tests/base/test_lab_project_configuration.py"
    # The approved test call and enclosing function stay identical; changing its
    # separately defined helper must still require a new source review.
    original_scopes, _ = _index(ast.parse(path.read_text()))
    source = path.read_text()
    before = "self.calls.append((argv, kwargs))"
    assert source.count(before) == 1
    path.write_text(source.replace(before, "raise RuntimeError('Unreviewed replacement helper')"))
    changed_scopes, _ = _index(ast.parse(path.read_text()))
    function = "test_cli_success_and_failure_never_print_private_identifier"
    assert ast_sha256(original_scopes[function]) == ast_sha256(changed_scopes[function])
    assert ast_sha256(original_scopes["run"]) != ast_sha256(changed_scopes["run"])
    refresh_integrity(root, manifest)
    with pytest.raises(ValueError, match="owner bytes changed"):
        validate_test_controls(root, manifest, findings(root))


def test_symlinked_owner_and_manifest_are_rejected(control_layout, tmp_path):
    root, manifest = control_layout
    raw = findings(root)
    linked_manifest = tmp_path / "linked-controls.json"
    linked_manifest.symlink_to(manifest)
    with pytest.raises(ValueError, match="symlink"):
        validate_test_controls(root, linked_manifest, raw)
    path = root / "tests/base/test_export_topos_evidence.py"
    outside = tmp_path / "outside.py"
    path.rename(outside)
    path.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        validate_test_controls(root, manifest, raw)
