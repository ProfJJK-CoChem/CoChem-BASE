"""REQ-BASE-016 / VR-06: real CI process and architectural boundary checks."""

from __future__ import annotations

import ast
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import psutil
import pytest

from ci_tools.anti_spoof_linter import (
    AntiSpoofLinterError,
    assert_compliant,
    check_file,
    run_linter,
)
from ci_tools.process_runner import async_run_process, run_process


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_runner_uses_utf8_in_a_cp1252_parent(tmp_path: Path) -> None:
    script = (
        "import sys; "
        "from ci_tools.process_runner import run_process; "
        "r = run_process([sys.executable, '-c', "
        "\"print('omega=ω Delta=Δ Angstrom=Å cm⁻¹')\"]); "
        "print(r.stdout, end=''); print(sys.stdout.encoding)"
    )
    child_env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONPATH=str(REPO_ROOT))
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=child_env,
        capture_output=True, check=True,
    )
    assert result.stdout.decode("utf-8").splitlines() == ["omega=ω Delta=Δ Angstrom=Å cm⁻¹", "utf-8"]


def test_arguments_are_literal_and_environment_is_not_mutated(tmp_path: Path) -> None:
    child_env = dict(os.environ, COCHEM_CI_VALUE="isolated", PYTHONIOENCODING="cp1252")
    argument = "x; echo unsafe && $(echo expansion)"
    result = run_process(
        [sys.executable, "-c", "import os,sys; print(os.getcwd()); print(sys.argv[1]); print(os.environ['COCHEM_CI_VALUE'])", argument],
        cwd=tmp_path, env=child_env,
    )
    assert result.stdout.splitlines() == [str(tmp_path), argument, "isolated"]
    assert child_env["PYTHONIOENCODING"] == "cp1252"
    with pytest.raises(ValueError, match="argument vector"):
        run_process("echo unsafe")


def test_invalid_utf8_and_exit_codes_fail_closed() -> None:
    with pytest.raises(UnicodeDecodeError):
        run_process([sys.executable, "-c", "import os; os.write(1, bytes([255]))"])
    with pytest.raises(subprocess.CalledProcessError) as error:
        run_process([sys.executable, "-c", "import sys; print('failure', file=sys.stderr); sys.exit(7)"])
    assert error.value.returncode == 7
    assert error.value.stderr == "failure\n"
    result = run_process([sys.executable, "-c", "raise SystemExit(7)"], check=False)
    assert result.returncode == 7


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan")])
def test_invalid_timeouts_are_rejected(timeout: float) -> None:
    with pytest.raises(ValueError, match="finite positive"):
        run_process([sys.executable, "-c", "print('ok')"], timeout=timeout)


def test_sync_timeout_reaps_child() -> None:
    with pytest.raises(subprocess.TimeoutExpired) as error:
        run_process([sys.executable, "-c", "import os,time; print(os.getpid(), flush=True); time.sleep(30)"], timeout=0.5)
    assert not psutil.pid_exists(int(error.value.stdout.strip()))


def test_async_execution_errors_and_timeout() -> None:
    async def exercise() -> None:
        result = await async_run_process([sys.executable, "-c", "print('ω Δ Å')"])
        assert result.stdout == "ω Δ Å\n"
        with pytest.raises(UnicodeDecodeError):
            await async_run_process([sys.executable, "-c", "import os; os.write(2, bytes([255]))"])
        with pytest.raises(subprocess.CalledProcessError) as error:
            await async_run_process([sys.executable, "-c", "raise SystemExit(9)"])
        assert error.value.returncode == 9
        with pytest.raises(subprocess.TimeoutExpired) as error:
            await async_run_process([sys.executable, "-c", "import os,time; print(os.getpid(), flush=True); time.sleep(30)"], timeout=0.5)
        assert not psutil.pid_exists(int(error.value.stdout.strip()))

    asyncio.run(exercise())


def test_async_cancellation_reaps_child(tmp_path: Path) -> None:
    async def exercise() -> None:
        pid_file = tmp_path / "pid.txt"
        task = asyncio.create_task(async_run_process([
            sys.executable, "-c",
            "import os,sys,time; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)",
            str(pid_file),
        ]))
        try:
            async with asyncio.timeout(10):
                while not pid_file.exists() or not pid_file.read_text():
                    await asyncio.sleep(0.01)
            pid = int(pid_file.read_text())
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert not psutil.pid_exists(pid)

    asyncio.run(exercise())


def test_linter_cli_is_strict_without_a_flag(tmp_path: Path) -> None:
    target = tmp_path / "invalid.py"
    target.write_text("def unfinished():\n    pass\n", encoding="utf-8")
    result = run_process(
        [sys.executable, str(REPO_ROOT / "ci_tools/anti_spoof_linter.py"), "--json", str(target)],
        check=False,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 1
    assert report["violations_count"] >= 1
    with pytest.raises(AntiSpoofLinterError):
        assert_compliant([target], tmp_path)


@pytest.mark.parametrize("statement", [
    "import src.cochem_base",
    "from cochem_base.physics import isotopes",
    "import importlib; importlib.import_module('cochem_base.physics')",
    "from importlib import import_module as load; load('cochem_base.physics')",
    "import importlib as loaders; loaders.import_module('cochem_' + 'base.physics')",
])
def test_application_imports_are_rejected_even_with_amnesty(tmp_path: Path, statement: str) -> None:
    target = tmp_path / "ci_tools" / "sentinel.py"
    target.parent.mkdir()
    target.write_text(statement, encoding="utf-8")
    violations = check_file(target, tmp_path, {"ci_tools/sentinel.py"})
    assert any(v.category == "CI_APPLICATION_IMPORT" for v in violations)


@pytest.mark.parametrize("relative_path", ["anti_spoof_linter.py", "api_mocks/worker.py"])
def test_linter_cannot_be_bypassed_by_renaming(tmp_path: Path, relative_path: str) -> None:
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("import unittest.mock\n", encoding="utf-8")
    violations = check_file(target, tmp_path, set())
    assert any(v.category == "MOCK_IMPORT" for v in violations)


def test_missing_audit_target_fails(tmp_path: Path) -> None:
    exit_code, violations = run_linter([tmp_path / "absent.py"], tmp_path)
    assert exit_code == 1
    assert violations


def test_relative_repository_root_preserves_ci_boundary(tmp_path: Path) -> None:
    target = tmp_path / "ci_tools" / "sentinel.py"
    target.parent.mkdir()
    target.write_text("from cochem_base import physics\n", encoding="utf-8")
    relative_root = Path(os.path.relpath(tmp_path, Path.cwd()))
    exit_code, violations = run_linter([target], relative_root)
    assert exit_code == 1
    assert any(v.category == "CI_APPLICATION_IMPORT" for vs in violations.values() for v in vs)


def test_all_ci_tools_are_application_independent() -> None:
    for path in sorted((REPO_ROOT / "ci_tools").glob("*.py")):
        violations = check_file(path, REPO_ROOT, set())
        assert not [v for v in violations if v.category == "CI_APPLICATION_IMPORT"], path
        ast.parse(path.read_text(encoding="utf-8"))


def test_runner_imports_with_only_the_standard_library(tmp_path: Path) -> None:
    command = (
        "import importlib.util,sys; "
        "s=importlib.util.spec_from_file_location('process_runner',sys.argv[1]); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "r=m.run_process([sys.executable,'-c',\"print('ω')\"]); print(r.stdout,end='')"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-S", "-c", command, str(REPO_ROOT / "ci_tools/process_runner.py")],
        cwd=tmp_path, capture_output=True, check=True,
    )
    assert result.stdout.decode("utf-8").splitlines() == ["ω"]


def test_quarantine_uses_platform_temp_and_utf8() -> None:
    import tempfile
    from ci_tools.zero_trust_runner import QuarantineEnvironment

    with QuarantineEnvironment() as quarantine:
        assert quarantine.quarantine_dir.parent == Path(tempfile.gettempdir()).resolve()
        result = quarantine.run_command([sys.executable, "-c", "print('ω Δ Å')"])
        assert result.passed
        assert result.stdout == "ω Δ Å\n"
        directory = quarantine.quarantine_dir
    assert not directory.exists()


def test_quarantine_preserves_explicit_import_path(tmp_path: Path) -> None:
    from ci_tools.zero_trust_runner import QuarantineEnvironment

    with QuarantineEnvironment(base_dir=tmp_path) as quarantine:
        result = quarantine.run_command(
            [sys.executable, "-c", "import os; print(os.environ['PYTHONPATH'])"],
            env_overrides={"PYTHONPATH": "explicit-path", "COCHEM_ROOT": str(tmp_path)},
        )
        assert result.passed
        assert result.stdout == "explicit-path\n"


def test_quarantine_does_not_claim_library_tracker_or_other_callers_children(tmp_path: Path) -> None:
    import os
    import textwrap

    script = textwrap.dedent("""
        import subprocess, sys
        from multiprocessing import resource_tracker
        from multiprocessing.shared_memory import SharedMemory
        from ci_tools.zero_trust_runner import QuarantineEnvironment

        memory = SharedMemory(create=True, size=16)
        tracker_pid = resource_tracker._resource_tracker._pid
        unrelated = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.readline()'],
                                     stdin=subprocess.PIPE, text=True)
        try:
            with QuarantineEnvironment() as quarantine:
                result = quarantine.run_command([sys.executable, '-c', "print('isolated command')"])
                assert result.passed
            assert unrelated.poll() is None, 'quarantine killed another caller child'
            assert resource_tracker._resource_tracker._pid == tracker_pid
            assert resource_tracker._resource_tracker._check_alive(), 'quarantine killed library tracker'
        finally:
            if unrelated.poll() is None:
                unrelated.stdin.write('done\\n')
                unrelated.stdin.flush()
            unrelated.wait(timeout=5)
            unrelated.stdin.close()
            memory.close()
            memory.unlink()
        print('all owners retained their children')
    """)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    result = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, env=env,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert "all owners retained their children" in result.stdout
    assert "ChildProcessError" not in result.stderr
    assert "Exception ignored" not in result.stderr
    assert "resource_tracker:" not in result.stderr
