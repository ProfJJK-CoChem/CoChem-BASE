"""Termination escalation preserves the caller and unrelated sibling jobs."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("module_name", ["cochem.core.process_reaper", "src.cochem.core.process_reaper"])
def test_shared_process_group_escalation_preserves_caller_and_sibling(module_name):
    repo = Path(__file__).resolve().parents[2]
    script = r'''
import importlib
import os
import subprocess
import sys

manager = importlib.import_module(sys.argv[1]).ProcessTreeManager()
unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
target = subprocess.Popen([
    sys.executable, '-u', '-c',
    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready", flush=True); time.sleep(30)',
], stdout=subprocess.PIPE, text=True)
try:
    assert target.stdout.readline().strip() == 'ready'
    if os.name != 'nt':
        assert os.getpgid(target.pid) == os.getpgrp()
    manager.register_process(target.pid)
    result = manager.terminate_tree(target.pid, grace_timeout_sec=0.1)
    assert result['success']
    assert unrelated.poll() is None
    assert target.poll() is not None
finally:
    for process in (target, unrelated):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
    target.stdout.close()
'''
    result = subprocess.run(
        [sys.executable, "-c", script, module_name], cwd=repo,
        env=dict(os.environ, PYTHONPATH=os.pathsep.join([str(repo), str(repo / "src")])),
        start_new_session=(os.name != "nt"), capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
