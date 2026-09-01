"""Tripartite Air-Gap Webhook Receiver & Subprocess Brokering Test Suite (REQ-MOB-092).

Strict adherence to the Zero-Mock mandate:
- Spawns real detached receiver subprocess executing BaseHTTPRequestHandler bound to 127.0.0.1:0.
- Synchronizes dynamic port via stdout handshake and verifies PID using psutil.
- Dispatches Mobile Webhook Schema v2 JSON payload with X-CoChem-Signature HMAC-SHA256 over physical socket.
- Verifies Air-Gap Tier 1 (authenticated POST), Tier 2 (isolated scratch write, rejection of source dir writes), Tier 3 (atomic SQLite WAL ledger).
- Ruthless teardown via psutil process tree reaping.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Generator, Tuple

import psutil
import pytest
import requests

TEST_HMAC_SECRET: str = "cochem_test_secret_key_airgap_v2_physical"


@pytest.fixture
def airgap_receiver_daemon(
    tmp_path: Path,
) -> Generator[Tuple[int, int, Path, Path, Path, subprocess.Popen], None, None]:
    """Spawn detached Python receiver daemon and yield (port, pid, scratch_dir, src_dir, db_path, proc)."""
    scratch_dir = tmp_path / "scratch_isolated"
    src_dir = tmp_path / "protected_src"
    db_path = tmp_path / "airgap_transactions.db"

    scratch_dir.mkdir(parents=True, exist_ok=True)
    src_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parent.parent.parent
    src_root = repo_root / "src"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_root) + os.pathsep + env.get("PYTHONPATH", "")
    env["COCH_SRC"] = str(src_dir)
    env["COCHEM_HMAC_SECRET"] = TEST_HMAC_SECRET

    cmd = [
        sys.executable,
        "-m",
        "cochem.mobile.airgap_receiver",
        "--host",
        "127.0.0.1",
        "--port",
        "0",
        "--scratch-dir",
        str(scratch_dir),
        "--src-dir",
        str(src_dir),
        "--db-path",
        str(db_path),
        "--secret",
        TEST_HMAC_SECRET,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
        cwd=str(repo_root),
    )

    port: int = -1
    pid: int = -1

    try:
        # Read handshake from stdout
        assert proc.stdout is not None
        handshake_line = proc.stdout.readline()
        match = re.search(r"PORT=(\d+)\s+PID=(\d+)", handshake_line)
        assert match is not None, (
            f"Failed to parse handshake line from receiver: '{handshake_line}'"
        )

        port = int(match.group(1))
        pid = int(match.group(2))

        # Invariant: PID exists and is not the current test process PID
        assert psutil.pid_exists(pid)
        assert pid != os.getpid()

        # Healthcheck poll
        healthy = False
        for _ in range(30):
            try:
                resp = requests.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
                if resp.status_code == 200:
                    healthy = True
                    break
            except Exception:
                time.sleep(0.1)

        assert healthy is True, "AirGapReceiver daemon failed healthcheck on dynamic port."

        yield port, pid, scratch_dir, src_dir, db_path, proc

    finally:
        # Ruthless psutil process tree reaping
        if pid > 0 and psutil.pid_exists(pid):
            try:
                parent = psutil.Process(pid)
                for child in parent.children(recursive=True):
                    try:
                        child.kill()
                    except psutil.NoSuchProcess:
                        pass
                parent.kill()
            except psutil.NoSuchProcess:
                pass

        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


class TestWebhookTripartiteAirGap:
    """Rigorous physical tests for REQ-MOB-092 Tripartite Air-Gap Webhook Receiver."""

    def test_authenticated_webhook_dispatch_and_wal_logging(
        self,
        airgap_receiver_daemon: Tuple[int, int, Path, Path, Path, subprocess.Popen],
    ) -> None:
        """Test Air-Gap Tier 1 (valid HMAC), Tier 2 (scratch write), and Tier 3 (SQLite WAL ledger)."""
        port, pid, scratch_dir, src_dir, db_path, proc = airgap_receiver_daemon

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        payload = {
            "schema_version": "2.0",
            "job_id": job_id,
            "workflow_type": "CONFORMER_OPTIMIZATION",
            "smiles": "CCO",
            "metadata": {"user": "cochem-coder", "priority": "high"},
        }

        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(
            TEST_HMAC_SECRET.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-CoChem-Signature": signature,
        }

        url = f"http://127.0.0.1:{port}/webhook"
        response = requests.post(url, data=body_bytes, headers=headers, timeout=5.0)

        # Assert HTTP 200 and Tier 3 committed response
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        res_data = response.json()
        assert res_data["status"] == "SUCCESS"
        assert res_data["tier"] == "TIER_3_COMMITTED"
        assert res_data["job_id"] == job_id

        # Verify Tier 2: payload written to scratch directory
        scratch_file_path = Path(res_data["scratch_file"])
        assert scratch_file_path.exists()
        assert scratch_dir in scratch_file_path.parents

        saved_content = json.loads(scratch_file_path.read_text(encoding="utf-8"))
        assert saved_content["job_id"] == job_id
        assert saved_content["smiles"] == "CCO"

        # Verify Tier 3: SQLite WAL database contains committed transaction
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        with conn:
            # Check PRAGMA journal_mode is wal
            cur = conn.execute("PRAGMA journal_mode;")
            journal_mode = str(cur.fetchone()[0]).lower()
            assert journal_mode == "wal", f"Expected WAL journal mode, got {journal_mode}"

            cur = conn.execute(
                "SELECT job_id, signature, status, tier_passed, payload_size FROM airgap_transactions WHERE job_id = ?;",
                (job_id,),
            )
            row = cur.fetchone()
            assert row is not None, f"Transaction for {job_id} was not logged to SQLite WAL db."
            assert row[0] == job_id
            assert row[1] == signature
            assert row[2] == "COMMITTED"
            assert row[3] == "TIER_3_WAL"
            assert row[4] == len(body_bytes)
        conn.close()

    def test_source_directory_write_rejection_tier2(
        self,
        airgap_receiver_daemon: Tuple[int, int, Path, Path, Path, subprocess.Popen],
    ) -> None:
        """Test Air-Gap Tier 2: Payload attempting to target $COCH_SRC is strictly rejected (HTTP 403)."""
        port, pid, scratch_dir, src_dir, db_path, proc = airgap_receiver_daemon

        malicious_target = src_dir / "injected_module.py"
        payload = {
            "schema_version": "2.0",
            "job_id": f"evil_{uuid.uuid4().hex[:8]}",
            "target_file": str(malicious_target),
            "code": "print('Malicious Injection Attempt')",
        }

        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = hmac.new(
            TEST_HMAC_SECRET.encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-CoChem-Signature": signature,
        }

        url = f"http://127.0.0.1:{port}/webhook"
        response = requests.post(url, data=body_bytes, headers=headers, timeout=5.0)

        # Assert HTTP 403 Forbidden
        assert response.status_code == 403
        res_data = response.json()
        assert res_data["status"] == "ERROR"
        assert "Tier 2" in res_data["error"]

        # Assert target file was never created in source directory
        assert not malicious_target.exists(), "Source directory file was improperly created!"

    def test_unauthenticated_post_rejection_tier1(
        self,
        airgap_receiver_daemon: Tuple[int, int, Path, Path, Path, subprocess.Popen],
    ) -> None:
        """Test Air-Gap Tier 1: Post with missing or invalid signature is rejected (HTTP 401)."""
        port, pid, scratch_dir, src_dir, db_path, proc = airgap_receiver_daemon

        payload = {"job_id": "unauth_123", "data": "test"}
        body_bytes = json.dumps(payload).encode("utf-8")

        # 1. Missing signature header
        url = f"http://127.0.0.1:{port}/webhook"
        resp_missing = requests.post(url, data=body_bytes, timeout=5.0)
        assert resp_missing.status_code == 401
        assert "Tier 1" in resp_missing.json()["error"]

        # 2. Corrupted signature header
        resp_bad_sig = requests.post(
            url,
            data=body_bytes,
            headers={"X-CoChem-Signature": "deadbeef000000000000000000000000"},
            timeout=5.0,
        )
        assert resp_bad_sig.status_code == 401
        assert "Tier 1" in resp_bad_sig.json()["error"]
