"""Compatibility entry point for the canonical real student browser acceptance.

Use ``--help`` for supported options. The old implementation addressed internal
path widgets that are no longer displayed and is retired. Its legacy ``--setup``,
``--topos``, ``--pyscf``, ``--hessian``, ``--module-handoff`` and periodic JSON-path
switches are not forwarded as equivalent scientific acceptance.

The canonical harness exercises real upload/selection, retained input recovery,
and optional explicitly requested native or hosted calculation lanes. Separate
native engine suites retain their own scientific execution coverage.
"""
import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("student_entrypoint_browser_acceptance.py")),
                   run_name="__main__")
