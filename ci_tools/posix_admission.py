"""Wait for verified parent admission, then replace this PID with its command.

This launcher runs under an isolated stdlib interpreter. It cannot start the
requested command until its parent has retained the real session generation.
"""
from __future__ import annotations

import os
import stat
import sys


def main() -> int:
    if len(sys.argv) < 3:
        raise ValueError("POSIX admission requires a gate and an executable")
    descriptor = int(sys.argv[1])
    if descriptor < 3 or not stat.S_ISFIFO(os.fstat(descriptor).st_mode):
        raise ValueError("POSIX admission requires its inherited pipe")
    try:
        token = os.read(descriptor, 1)
        trailing = os.read(descriptor, 1)
    finally:
        os.close(descriptor)
    if token != b"\x01" or trailing:
        sys.stderr.write("[HARD_ABORT: PROCESS ADMISSION] Parent did not authorize execution\n")
        return 125
    try:
        os.execvpe(sys.argv[2], sys.argv[2:], os.environ)
    except OSError as error:
        sys.stderr.write(f"[HARD_ABORT: PROCESS EXECUTION] Requested executable did not start: {error}\n")
        return 127


if __name__ == "__main__":
    raise SystemExit(main())
