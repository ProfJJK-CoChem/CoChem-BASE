"""Fail closed source startup for ordinary quarantined Python descendants."""
import os
import sys
from pathlib import Path

try:
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from ci_tools.source_quarantine import activate_from_environment
    activate_from_environment()
except BaseException:
    # Python normally prints and ignores sitecustomize errors. A rejected source
    # boundary must terminate before any selected user/test program executes.
    os.write(2, b"[HARD_ABORT: SOURCE QUARANTINE ESCAPE] Python source startup refused\n")
    os._exit(1)
