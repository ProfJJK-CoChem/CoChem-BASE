"""Application-independent subprocess execution for the CI plane (REQ-BASE-016).

Commands are argument vectors, never shell programs. Captured output is decoded
as UTF-8 strictly by default; invalid bytes and failing commands remain errors.
"""

from __future__ import annotations

import asyncio
import codecs
import locale
import math
import os
import subprocess
import sys
from collections.abc import Mapping, Sequence


def configure_utf8_streams() -> None:
    """Make available console streams capable of emitting scientific notation."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _command(args: Sequence[str | os.PathLike[str]]) -> list[str]:
    if isinstance(args, (str, bytes)) or not args:
        raise ValueError("args must be a nonempty argument vector, not a shell string")
    command = [os.fspath(arg) for arg in args]
    if any(not isinstance(arg, str) or "\0" in arg for arg in command):
        raise ValueError("command arguments must be text without NUL bytes")
    return command


def _environment(env: Mapping[str, str] | None) -> dict[str, str]:
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONIOENCODING"] = "utf-8"
    child_env["PYTHONUTF8"] = "1"
    return child_env


def _validate_timeout(timeout: float | None) -> None:
    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("timeout must be a finite positive number")


def run_process(
    args: Sequence[str | os.PathLike[str]],
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    check: bool = True,
    capture_output: bool = True,
    encoding_strategy: str = "strict",
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with explicit UTF-8 decoding and normal subprocess errors.

    ``env`` replaces the inherited environment, as with ``subprocess.run``.
    Python children always use UTF-8. ``encoding_strategy='locale'`` is an
    explicit compatibility option for an external program's native encoding;
    other strategies are standard codec error handlers (default: strict).
    No application module, shell, or working-directory mutation is involved.
    """
    command = _command(args)
    _validate_timeout(timeout)
    encoding = "utf-8"
    errors = encoding_strategy
    if encoding_strategy == "locale":
        encoding, errors = locale.getencoding(), "strict"
    codecs.lookup_error(errors)
    configure_utf8_streams()
    return subprocess.run(
        command,
        cwd=cwd,
        timeout=timeout,
        check=check,
        capture_output=capture_output,
        text=True,
        encoding=encoding,
        errors=errors,
        env=_environment(env),
        shell=False,
    )


async def async_run_process(
    args: Sequence[str | os.PathLike[str]],
    cwd: str | os.PathLike[str] | None = None,
    timeout: float | None = None,
    check: bool = True,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute without blocking the event loop; reap the child on cancellation.

    Unlike a thread wrapping ``subprocess.run``, cancelling this coroutine stops
    the actual child. Timeout errors include the captured bytes, matching the
    standard library's ``TimeoutExpired`` contract.
    """
    command = _command(args)
    _validate_timeout(timeout)
    configure_utf8_streams()
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=_environment(env),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    communication = asyncio.create_task(process.communicate())
    try:
        stdout, stderr = await asyncio.wait_for(asyncio.shield(communication), timeout)
    except (TimeoutError, asyncio.CancelledError) as exc:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                # The child exited between returncode inspection and kill.
                await process.wait()
        stdout, stderr = await communication
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from exc
    # Match subprocess.run(text=True)'s universal-newline contract on Windows.
    result = subprocess.CompletedProcess(
        command,
        process.returncode,
        stdout.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"),
        stderr.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"),
    )
    if check:
        result.check_returncode()
    return result
