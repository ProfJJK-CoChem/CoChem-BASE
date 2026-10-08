"""Evidence transport contracts; no engine outputs or installation success fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts import export_topos_evidence as export
from scripts.manage_modules import ModuleInstallationError


def test_missing_operation_retains_explicit_unavailable_without_scanning_native_tree(tmp_path):
    source = tmp_path / "controlled/topos"
    attempt = source / "execution/runs/uncompleted/attempts/native"
    attempt.mkdir(parents=True)
    (attempt / "GENBAS").write_text("Unexecuted transport fixture; not actual basis data")
    target = tmp_path / "uploaded/evidence"
    result = export.export_installed_topos(source, target, tmp_path / "Modules")
    assert result["status"] == "unavailable"
    assert result["snapshot_storage_verified"] is False
    assert {path.name for path in target.iterdir()} == {"export.json"}
    assert (attempt / "GENBAS").read_text().startswith("Unexecuted")


@pytest.mark.parametrize("location", ["source", "source-parent", "destination-parent"])
def test_declared_symlink_ancestors_reject_before_export(tmp_path, location):
    actual = tmp_path / "actual"
    actual.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(actual, target_is_directory=True)
    source, output = tmp_path / "source", tmp_path / "output"
    if location == "source":
        source = alias
    elif location == "source-parent":
        source = alias / "nested"
    else:
        output = alias / "export"
    with pytest.raises(ValueError, match="symbolic"):
        export.export_installed_topos(source, output, tmp_path / "Modules")
    assert not list(actual.iterdir())


@pytest.mark.parametrize("case", ["source-inside-output", "output-inside-source", "already-exists"])
def test_export_destination_cannot_capture_native_tree_or_replace_prior_evidence(tmp_path, case):
    source, output = tmp_path / "source", tmp_path / "output"
    if case == "source-inside-output":
        source = output / "native"
    elif case == "output-inside-source":
        output = source / "evidence"
    else:
        output.mkdir()
        (output / "sentinel").write_text("Previous evidence")
    with pytest.raises(ValueError, match="fresh separate"):
        export.export_installed_topos(source, output, tmp_path / "Modules")
    if case == "already-exists":
        assert (output / "sentinel").read_text() == "Previous evidence"


def test_copy_requires_the_previously_verified_identity_and_preserves_bytes(tmp_path):
    original, target = tmp_path / "original", tmp_path / "target"
    payload = b"Actual bytes of a non-scientific transport fixture\n"
    original.write_bytes(payload)
    with pytest.raises(ValueError, match="original identity"):
        export._copy_bound(original, target, "0" * 64)
    assert not target.exists()
    receipt = export._copy_bound(original, target, hashlib.sha256(payload).hexdigest())
    assert target.read_bytes() == original.read_bytes() == payload
    assert receipt == {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}


def test_rejected_installed_authority_has_no_raw_fallback(tmp_path):
    source = tmp_path / "controlled/topos"
    (source / "execution").mkdir(parents=True)
    (source / "execution/operation.json").write_text("{}")
    (source / "execution/GENBAS").write_text("Unexecuted transport fixture")
    target = tmp_path / "export"
    with pytest.raises(ModuleInstallationError, match="receipt|installation|installed"):
        export.export_installed_topos(source, target, tmp_path / "Modules")
    assert {p.name for p in target.iterdir()} == {"export-failure.json"}
    report = json.loads((target / "export-failure.json").read_text())
    assert report["status"] == "failed"
    assert report["snapshot_storage_verified"] is False
    assert not any(p.name == "GENBAS" for p in target.rglob("*"))


def test_workflow_moves_native_execution_outside_every_uploaded_root():
    import yaml

    document = yaml.safe_load((Path(__file__).parents[2] / ".github/workflows/ecosystem_modules.yml").read_text())
    steps = document["jobs"]["modules"]["steps"]
    calculation = next(s["run"] for s in steps if s.get("name") == "Execute the validated module request")
    selected = next(s for s in steps if s.get("name") == "Export only the bound scientific TOPOS snapshot")
    upload = next(s for s in steps if s.get("uses") == "actions/upload-artifact@v4")
    assert "root / 'controlled-execution'" in calculation
    assert "always()" in selected["if"]
    assert "-I -B -m scripts.export_topos_evidence" in selected["run"]
    assert "controlled-execution/topos" in selected["run"]
    assert "controlled-execution" not in upload["with"]["path"]
    assert steps.index(selected) < steps.index(upload)


def test_invalid_native_destination_fails_before_any_export(tmp_path):
    source = tmp_path / "controlled/topos"
    (source / "execution").mkdir(parents=True)
    (source / "execution/operation.json").write_text("{}")
    # A filename longer than the native filesystem permits is rejected by the
    # real OS before any authority check or evidence publication.
    destination = tmp_path / ("failed-export-" + "x" * 256)
    with pytest.raises(OSError):
        export.export_installed_topos(source, destination, tmp_path / "Modules")
    assert not any(path.name.startswith("failed-export-") for path in tmp_path.iterdir())
