"""Lab-workstation panel: folder assignment, job list, status rendering and result display."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import time
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from cochem_base.interfaces.workstation_panel import WorkstationQueuePanel

CALCULATION = {"geometry": "O 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043", "engine": "pyscf", "method": "HF",
               "basis_set": "sto-3g", "charge": 0, "multiplicity": 1, "is_opt": False, "is_freq": False}


WORKSTATION_KEY = Ed25519PrivateKey.generate()  # stands in for the workstation's signing key
PUBLIC_KEY = WORKSTATION_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
FINGERPRINT = hashlib.sha256(PUBLIC_KEY).hexdigest()


def _sign(status: dict, input_hashes: dict) -> None:
    """Add the runner's signed statement (``Signer.attest``) to a status document."""
    statement = {"schema": "cochem.workstation-attestation/1", "client_job_id": status["client_job_id"],
                 "label": status["label"], "state": status["state"], "input_hashes": input_hashes,
                 "result_file": status["result_file"], "result_sha256": status["result_sha256"]}
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    status["attestation"] = {"schema": "cochem.workstation-attestation/1", "algorithm": "ed25519",
                             "public_key": base64.b64encode(PUBLIC_KEY).decode(), "key_fingerprint": FINGERPRINT,
                             "statement": base64.b64encode(payload).decode(),
                             "signature": base64.b64encode(WORKSTATION_KEY.sign(payload)).decode()}


def _wait(predicate, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached")


def _panel(tmp_path: Path) -> tuple[WorkstationQueuePanel, Path]:
    (tmp_path / "Drive").mkdir()
    panel = WorkstationQueuePanel(artifact_dir=tmp_path / "artifacts", start_polling=False)
    folder = tmp_path / "Drive" / "alice"
    panel.folder.value, panel.student.value, panel.memory.value = str(folder), "alice", 4
    panel.trusted_keys.value = FINGERPRINT
    panel.assign()
    _wait(lambda: not panel.btn_assign.disabled and "Folder" in panel.settings_status.value and not panel.busy)
    return panel, folder


def test_assignment_validation_messages(tmp_path):
    panel = WorkstationQueuePanel(artifact_dir=tmp_path / "artifacts", start_polling=False)
    assert "Assign your workstation Drive folder" in panel.ready_reason()
    panel.folder.value, panel.student.value = "relative/folder", "alice"
    panel.assign()
    _wait(lambda: not panel.btn_assign.disabled and "not assigned" in panel.settings_status.value)
    panel.cores.value = "many"
    panel.assign()
    assert "Cores must be" in panel.settings_status.value


def test_submit_status_and_failed_result_rendering(tmp_path):
    panel, folder = _panel(tmp_path)
    assert panel.ready_reason() == ""
    panel.submit(CALCULATION)
    _wait(lambda: panel.history.value != "" and not panel.busy)
    submission = json.loads(panel.history.value)
    assert (folder / "inbox" / submission["job_name"] / "calculation.json").is_file()
    payload = (folder / "inbox" / submission["job_name"] / "calculation.json").read_bytes()

    label = submission["job_name"] + "__a1b2c3d4"
    job = folder / "jobs" / label
    job.mkdir(parents=True)
    (folder / "inbox" / submission["job_name"]).rename(job / "input")
    status = {"schema": "cochem.workstation-job-status/1", "label": label, "client_job_id": submission["client_job_id"],
              "state": "PAUSED", "message": "owner is running a game", "attempts": 1, "queue_position": 2,
              "resources": {"cores": 4, "memory_per_core_mb": 768}, "repairs": ["cores reduced from 8 to 4"],
              "progress": {"optimization_cycle": 3, "_queue_position": 2}, "output_tail": ["SCF iteration 7"]}
    (job / "status.json").write_text(json.dumps(status))
    panel.refresh()
    _wait(lambda: "PAUSED" in panel.job_status.value and not panel.busy)
    rendered = panel.job_status.value
    assert "owner uses the machine" in rendered and "cores reduced from 8 to 4" in rendered
    assert "optimization_cycle = 3" in rendered and "_queue_position" not in rendered and "SCF iteration 7" in rendered
    assert panel.btn_retrieve.disabled and not panel.btn_cancel.disabled

    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        bundle.writestr("_runner/job_summary.json", json.dumps({
            "schema": "cochem.workstation-job-summary/1", "client_job_id": submission["client_job_id"],
            "input_hashes": {"calculation.json": hashlib.sha256(payload).hexdigest()}}))
        bundle.writestr("cochem_base_run.log", "Calculation was not accepted: example diagnostics\n")
    archive = stream.getvalue()
    (job / f"{label}_results.zip").write_bytes(archive)
    status.update(state="FAILED", message="cochem-cli exited with code 1", result_file=f"{label}_results.zip",
                  result_sha256=hashlib.sha256(archive).hexdigest())
    _sign(status, {"calculation.json": hashlib.sha256(payload).hexdigest()})
    (job / "status.json").write_text(json.dumps(status))
    panel.refresh()
    _wait(lambda: not panel.btn_retrieve.disabled and not panel.busy)
    panel.retrieve()
    _wait(lambda: "No accepted scientific result" in panel.result.value)
    assert "cochem-cli exited with code 1" in panel.result.value
    assert panel.download.value.startswith("<a download=")


def test_history_survives_a_new_panel(tmp_path):
    panel, _folder = _panel(tmp_path)
    panel.submit(CALCULATION)
    _wait(lambda: panel.history.value != "" and not panel.busy)
    reopened = WorkstationQueuePanel(artifact_dir=tmp_path / "artifacts", start_polling=False)
    assert reopened.folder.value.endswith("alice") and reopened.student.value == "alice"
    assert json.loads(reopened.history.options[0][1])["request_id"] == json.loads(panel.history.value)["request_id"]


def test_a_second_operation_is_refused_while_one_is_in_flight(tmp_path):
    panel, folder = _panel(tmp_path)
    outcomes = []
    assert panel._reserve()  # e.g. the background poller is mid-refresh
    assert panel.submit(CALCULATION, on_result=lambda sent, text: outcomes.append(sent)) is False
    assert outcomes == [False] and "Wait for the current" in panel.job_status.value
    assert not (folder / "inbox").exists() or not any((folder / "inbox").iterdir())
    panel._release()
    assert panel.submit(CALCULATION, on_result=lambda sent, text: outcomes.append(sent)) is True
    _wait(lambda: len(outcomes) == 2)
    assert outcomes == [False, True] and "Queued for the lab workstation" in panel.job_status.value
    assert len(list((folder / "inbox").iterdir())) == 1


def test_workstation_key_is_saved_and_advertised_keys_are_shown(tmp_path):
    panel, folder = _panel(tmp_path)
    reopened = WorkstationQueuePanel(artifact_dir=tmp_path / "artifacts", start_polling=False)
    assert reopened.trusted_keys.value == FINGERPRINT
    panel._render_health([{"node_id": "lab-ws", "stale": False, "mode": "full", "cores_available": 8, "queued": 0,
                           "reasons": [], "key_fingerprint": FINGERPRINT}])
    assert f"reports signing key {FINGERPRINT}" in panel.health.value
