"""Actual free-engine download failures preserve BASE's no-code setup interface."""

import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys

import pytest

from scripts.hosted_dashboard import prepare_free_engines, runtime_environment


def test_actual_download_failure_publishes_bounded_retry_diagnostics(tmp_path):
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
        pytest.skip("This test exercises the genuine Linux upstream download route")
    with socket.socket() as refused:
        refused.bind(("127.0.0.1", 0))
        proxy = f"http://127.0.0.1:{refused.getsockname()[1]}"
        # This bound socket has no listener: the actual urllib HTTPS proxy
        # connection is refused before any unverified archive can be accepted.
        result = prepare_free_engines(Path(sys.executable), tmp_path,
            environment={"https_proxy": proxy, "HTTPS_PROXY": proxy, "http_proxy": proxy,
                         "HTTP_PROXY": proxy, "no_proxy": "", "NO_PROXY": ""})
    assert result["status"] == "failed"
    assert set(result["engines"]) == {"xtb", "crest"}
    assert all(record["status"] == "failed" and len(record["message"]) <= 2000 for record in result["engines"].values())
    assert "Retry setup" in result["message"]
    assert json.loads((tmp_path / "free-engines/setup-status.json").read_text()) == result
    assert not (tmp_path / "free-engines/xtb/xtb-dist/bin/xtb").exists()
    assert runtime_environment(tmp_path)["COCHEM_ARTIFACT_DIR"] == str(tmp_path)


def test_failed_free_engine_paths_cannot_remain_bound_by_inherited_aliases(tmp_path):
    root = tmp_path / "free-engines"
    executable = root / "xtb/xtb-dist/bin/xtb"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"Actual incomplete installation bytes; never an accepted chemistry engine\n")
    (root / "setup-status.json").write_text(json.dumps({"engines": {"xtb": {"status": "failed"}}}), encoding="utf-8")
    code = """import os,sys
from pathlib import Path
from scripts.hosted_dashboard import runtime_environment
root=Path(sys.argv[1]); result=runtime_environment(root)
assert 'XTB_CMD' not in result and 'COCHEM_XTB_BIN' not in result and 'XTBPATH' not in result
assert str(root/'free-engines/xtb/xtb-dist/bin') not in result['PATH'].split(os.pathsep)
"""
    environment = {**os.environ, "XTB_CMD": str(executable), "COCHEM_XTB_BIN": str(executable),
        "XTBPATH": str(root / "xtb/xtb-dist/share/xtb"),
        "PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", "")}
    subprocess.run([sys.executable, "-B", "-c", code, str(tmp_path)], env=environment, check=True, timeout=30)


def test_free_engine_profile_redirect_is_rejected_before_installer_writes(tmp_path):
    profile = tmp_path / "profile"
    outside = tmp_path / "student-originals"
    profile.mkdir(); outside.mkdir()
    (profile / "free-engines").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="inside their external profile"):
        prepare_free_engines(Path(sys.executable), profile)
    assert list(outside.iterdir()) == []
