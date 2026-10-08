"""Real pinned free inputs and filesystem refusals; no chemistry substitutes."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from scripts.install_qe_paw_inputs import (
    PSEUDOPOTENTIALS, REPOSITORY, external_path, install_inputs, verify_inputs,
)


@pytest.fixture(scope="module")
def official_inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("official-paw-source")
    configured = os.environ.get("COCHEM_QE_PSEUDO_DIR")
    if configured:
        source = Path(configured)
        verify_inputs(source)
        for pin in PSEUDOPOTENTIALS.values():
            shutil.copyfile(source / pin["filename"], root / pin["filename"])
    else:
        install_inputs(root, root / "acquisition.json")
    return root


def test_real_pinned_upf_inputs_are_reverified_without_replacing_original_bytes(official_inputs, tmp_path):
    before = {pin["filename"]: hashlib.sha256((official_inputs / pin["filename"]).read_bytes()).hexdigest()
              for pin in PSEUDOPOTENTIALS.values()}
    receipt_path = tmp_path / "verification.json"
    report = install_inputs(official_inputs, receipt_path)
    assert json.loads(receipt_path.read_text()) == report
    assert report["status"] == "verified"
    assert report["scientific_accuracy_established"] is False
    assert report["native_execution_verified"] is False
    assert {record["acquisition"] for record in report["pseudopotentials"].values()} == {"existing_bytes_reverified"}
    assert {symbol: record["upf_header"]["valence_electrons"] for symbol, record in report["pseudopotentials"].items()} == {"Ga": 13, "As": 5}
    assert all(record["upf_header"]["pseudo_type"] == "PAW" and record["upf_header"]["has_so"] is False
               for record in report["pseudopotentials"].values())
    assert before == {pin["filename"]: hashlib.sha256((official_inputs / pin["filename"]).read_bytes()).hexdigest()
                      for pin in PSEUDOPOTENTIALS.values()}


@pytest.mark.parametrize("symbol", ["Ga", "As"])
def test_actual_pinned_input_tampering_fails_before_reuse_and_is_recorded(official_inputs, tmp_path, symbol):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    for pin in PSEUDOPOTENTIALS.values():
        shutil.copyfile(official_inputs / pin["filename"], inputs / pin["filename"])
    changed = inputs / PSEUDOPOTENTIALS[symbol]["filename"]
    with changed.open("r+b") as target:
        target.seek(-1, os.SEEK_END)
        original = target.read(1)
        target.seek(-1, os.SEEK_END)
        target.write(bytes([original[0] ^ 1]))
    tampered_hash = hashlib.sha256(changed.read_bytes()).hexdigest()
    receipt = tmp_path / "rejection.json"
    with pytest.raises(ValueError, match="SHA-256 authentication failed"):
        install_inputs(inputs, receipt)
    assert hashlib.sha256(changed.read_bytes()).hexdigest() == tampered_hash
    report = json.loads(receipt.read_text())
    assert report["status"] == "failed" and "SHA-256 authentication failed" in report["error"]


def test_source_and_source_parent_are_rejected_before_writes():
    for forbidden in (REPOSITORY / "forbidden-paw-runtime", REPOSITORY, REPOSITORY.parent):
        with pytest.raises(ValueError, match="outside the source checkout"):
            external_path(forbidden)
    assert not (REPOSITORY / "forbidden-paw-runtime").exists()


def test_parent_traversal_is_rejected_before_directory_creation(tmp_path):
    with pytest.raises(ValueError, match="parent-directory traversal"):
        external_path(tmp_path / "uncreated" / ".." / "inputs")
    assert not (tmp_path / "uncreated").exists()


def test_redirected_input_or_receipt_cannot_overwrite_unrelated_files(tmp_path):
    originals = tmp_path / "originals"
    originals.mkdir()
    sentinel = originals / "student-original.txt"
    sentinel.write_bytes(b"Unrelated student input; preserved by the real path guard\n")
    alias = tmp_path / "redirect"
    alias.symlink_to(originals, target_is_directory=True)
    for directory, receipt in ((alias, tmp_path / "receipt.json"), (tmp_path / "inputs", alias / "receipt.json")):
        with pytest.raises(ValueError, match="symbolic links"):
            install_inputs(directory, receipt)
    assert not (tmp_path / "inputs").exists()
    assert list(originals.iterdir()) == [sentinel]


def test_receipt_cannot_replace_an_authenticated_input_filename(tmp_path):
    directory = tmp_path / "inputs"
    with pytest.raises(ValueError, match="may not overwrite a pinned input filename"):
        install_inputs(directory, directory / PSEUDOPOTENTIALS["Ga"]["filename"])
    assert not directory.exists()


@pytest.mark.parametrize("kind", ["directory", "oversized_file"])
def test_nonregular_or_oversized_cached_input_is_rejected_before_opening(tmp_path, kind):
    directory = tmp_path / "inputs"
    directory.mkdir()
    path = directory / PSEUDOPOTENTIALS["Ga"]["filename"]
    if kind == "directory":
        path.mkdir()
    else:
        with path.open("wb") as untrusted:
            untrusted.write(b"Deliberately untrusted input for a refusal control; no chemistry claim\n")
            untrusted.truncate(PSEUDOPOTENTIALS["Ga"]["size_bytes"] + 1)
    with pytest.raises(ValueError, match="regular file of exactly"):
        install_inputs(directory, tmp_path / "rejection.json")
    assert json.loads((tmp_path / "rejection.json").read_text())["status"] == "failed"


def test_actual_dashboard_paw_setup_reuses_verified_data_and_preserves_local_configuration(official_inputs, tmp_path):
    root = tmp_path / "profile"
    inputs = root / "free-engines/qe-paw"
    inputs.mkdir(parents=True)
    for pin in PSEUDOPOTENTIALS.values():
        shutil.copyfile(official_inputs / pin["filename"], inputs / pin["filename"])
    code = """import json,sys
from pathlib import Path
from scripts.hosted_dashboard import prepare_paw_inputs,runtime_environment
root=Path(sys.argv[1]); result=prepare_paw_inputs(Path(sys.executable),root)
assert result['status']=='verified'
observed=runtime_environment(root)
assert observed['COCHEM_QE_PSEUDO_DIR']==sys.argv[2]
assert result['scientific_accuracy_established'] is False
print(json.dumps(result))
"""
    for explicit in (None, str(official_inputs)):
        environment = {key: value for key, value in os.environ.items() if key != "COCHEM_QE_PSEUDO_DIR"}
        if explicit is not None:
            environment["COCHEM_QE_PSEUDO_DIR"] = explicit
        subprocess.run([sys.executable, "-B", "-c", code, str(root), explicit or str(inputs)],
            env=environment, capture_output=True, text=True, check=True, timeout=30)


def test_actual_dashboard_download_refusal_preserves_base_and_disables_unavailable_paw(tmp_path):
    from scripts.hosted_dashboard import prepare_paw_inputs, runtime_environment

    with socket.socket() as refused:
        refused.bind(("127.0.0.1", 0))
        proxy = f"http://127.0.0.1:{refused.getsockname()[1]}"
        report = prepare_paw_inputs(Path(sys.executable), tmp_path,
            environment={"HTTPS_PROXY": proxy, "https_proxy": proxy, "HTTP_PROXY": proxy,
                         "http_proxy": proxy, "NO_PROXY": "", "no_proxy": ""})
    assert report["status"] == "failed" and len(report["error"]) <= 2000
    assert report["scientific_accuracy_established"] is False
    assert report["native_execution_verified"] is False
    assert not (tmp_path / "free-engines/qe-paw" / PSEUDOPOTENTIALS["Ga"]["filename"]).exists()
    assert runtime_environment(tmp_path)["COCHEM_ARTIFACT_DIR"] == str(tmp_path)
    assert json.loads((tmp_path / "free-engines/qe-paw/installation.json").read_text())["status"] == "failed"
