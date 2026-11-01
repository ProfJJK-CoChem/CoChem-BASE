"""Sanitized diagnostics from actual owned subprocess/filesystem failures."""
from __future__ import annotations

import errno
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ci_tools.source_quarantine import CONTEXT_KEYS, source_child_environment, source_paths

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/manage_modules.py"
PREFIX = "Owned workflow pip diagnostics: "
CHILD = r'''
import json, os, runpy, sys
from pathlib import Path
source, mode, root, selected = sys.argv[1:]
selected = Path(selected).resolve()
assert Path(source).resolve() == selected / "scripts/manage_modules.py"
from ci_tools import source_quarantine
assert Path(source_quarantine.__file__).resolve() == selected / "ci_tools/source_quarantine.py"
state = source_quarantine.activate_from_environment()
if os.environ.get("COCHEM_SOURCE_QUARANTINE_ROOT"):
    assert state is not None and state["copied"] == selected
    shim = sys.modules.get("sitecustomize")
    assert shim is not None
    assert Path(shim.__file__).resolve() == selected / "ci_tools/quarantine_startup/sitecustomize.py"
namespace = runpy.run_path(source, run_name="actual_workflow_pip_diagnostics")
owner = namespace["_run_workflow_pip"]
assert Path(owner.__code__.co_filename).resolve() == selected / "scripts/manage_modules.py"
assert Path(namespace["_workflow_pip_diagnostics"].__code__.co_filename).resolve() == selected / "scripts/manage_modules.py"
def report(body):
    print(json.dumps({"control": body, "source": {
        "root": str(selected), "active": state is not None,
        "pid": os.getpid(), "parent_pid": os.getppid(),
        "instance": state["instance"] if state is not None else None,
    }}))
if mode == "success":
    result = owner([sys.executable, "-I", "-B", "-c", "pass"], dict(os.environ), 5)
    report({"returncode": result})
elif mode == "missing":
    try:
        owner([str(Path(root) / "PRIVATE-PATH-DO-NOT-LOG-missing-interpreter")], dict(os.environ), 5)
    except FileNotFoundError as error:
        report({"exception_type": type(error).__name__, "errno": error.errno})
    else:
        raise AssertionError("A nonexistent interpreter unexpectedly launched")
elif mode == "format":
    errors = []
    try:
        open(Path(root) / "PRIVATE-PATH-DO-NOT-LOG-missing-file", "rb")
    except OSError as error:
        errors.append(error)
    try:
        descriptor = os.open(root, os.O_WRONLY)
    except OSError as error:
        errors.append(error)
    else:
        os.close(descriptor)
        raise AssertionError("Expected the real directory write-open failure")
    assert len(errors) == 2
    diagnostic = namespace["_workflow_pip_diagnostics"](
        "observe_darwin", errors[0], "posix_wait_leader", errors[1])
    assert diagnostic["primary"]["exception_type"] == type(errors[0]).__name__
    assert diagnostic["primary"]["errno"] == errors[0].errno
    assert diagnostic["cleanup"]["exception_type"] == type(errors[1]).__name__
    assert diagnostic["cleanup"]["errno"] == errors[1].errno
    PrivateExceptionName = type("PRIVATE-CLASS-DO-NOT-LOG", (Exception,), {})
    unknown = namespace["_workflow_pip_diagnostics"](
        "PRIVATE-PHASE-DO-NOT-LOG", PrivateExceptionName("PRIVATE-MESSAGE-DO-NOT-LOG"),
        "no_process", None)
    assert unknown["primary"] == {"phase": "unclassified_phase", "exception_type": "UnclassifiedException", "errno": None}
    report({"separate_real_errors": diagnostic, "unclassified": unknown})
else:
    raise AssertionError(mode)
'''


class WorkflowPipDiagnosticTests(unittest.TestCase):
    def run_control(self, mode):
        environment = source_child_environment(dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                               selected_source=ROOT)
        environment["PYTHONPATH"] = os.pathsep.join(source_paths(ROOT))
        with tempfile.TemporaryDirectory(prefix="workflow-pip-diagnostic-") as root:
            result = subprocess.run([sys.executable, "-B", "-c", CHILD,
                                     str(SOURCE), mode, root, str(ROOT)], stdin=subprocess.DEVNULL,
                                    env=environment, cwd=ROOT,
                                    capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("PRIVATE-", result.stdout + result.stderr)
        observed = json.loads(result.stdout)
        source = observed["source"]
        self.assertEqual(source["root"], str(ROOT))
        self.assertEqual(source["parent_pid"], os.getpid())
        active = bool(environment.get(CONTEXT_KEYS[0]))
        self.assertIs(source["active"], active)
        if active:
            evidence = Path(environment[CONTEXT_KEYS[2]])
            stem = str(source["pid"]) + "-" + source["instance"]
            for stage in ("initial", "final"):
                receipt = json.loads((evidence / (stem + "-" + stage + ".json")).read_text())
                self.assertIs(receipt["passed"], True)
                self.assertEqual(receipt["stage"], stage)
                self.assertEqual(receipt["pid"], source["pid"])
                self.assertEqual(receipt["parent_pid"], os.getpid())
                self.assertEqual(receipt["source_root"], str(ROOT))
                self.assertEqual(receipt["original_root"], environment[CONTEXT_KEYS[1]])
                self.assertEqual(receipt["source_revision"], environment[CONTEXT_KEYS[3]])
                self.assertEqual(receipt["startup_source_sha256"], hashlib.sha256(
                    (ROOT / "ci_tools/source_quarantine.py").read_bytes()).hexdigest())
                if stage == "final":
                    self.assertEqual(receipt["escaped"], [])
        return result, observed["control"]

    def test_actual_harmless_owned_child_preserves_success_without_failure_diagnostics(self):
        result, body = self.run_control("success")
        self.assertEqual(body, {"returncode": 0})
        self.assertNotIn(PREFIX, result.stderr)

    def test_actual_missing_interpreter_retains_primary_launch_errno_without_path(self):
        result, body = self.run_control("missing")
        self.assertEqual(body, {"exception_type": "FileNotFoundError", "errno": errno.ENOENT})
        lines = [line for line in result.stderr.splitlines() if line.startswith(PREFIX)]
        self.assertEqual(len(lines), 1)
        diagnostic = json.loads(lines[0][len(PREFIX):])
        self.assertEqual(diagnostic["primary"], {"phase": "launch", "exception_type": "FileNotFoundError", "errno": errno.ENOENT})
        self.assertEqual(diagnostic["cleanup"], {"phase": "no_process", "exception_type": None, "errno": None})

    def test_two_real_filesystem_errors_have_separate_allowlisted_metadata_only(self):
        _result, body = self.run_control("format")
        self.assertEqual(body["separate_real_errors"]["primary"]["phase"], "observe_darwin")
        self.assertEqual(body["separate_real_errors"]["cleanup"]["phase"], "posix_wait_leader")
        for layer in body["separate_real_errors"].values():
            self.assertEqual(set(layer), {"phase", "exception_type", "errno"})
            self.assertIs(type(layer["errno"]), int)


if __name__ == "__main__":
    unittest.main()
