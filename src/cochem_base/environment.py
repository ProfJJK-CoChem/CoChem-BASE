"""
CoChem Ecosystem Dynamic Environment & Path Registries.
Compliant with Method Matrix v4, 6-Tier Environment Matrix, and Zero-Mock Mandate.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from cochem_base.exceptions import BinaryNotFoundError


class BinaryRegistry:
    """Dynamic resolution registry for external computational chemistry binaries.

    Resolves executables (e.g. crest, xcfour, orca, xtb) using environment variables
    and system PATH. Emits standardized BinaryNotFoundError with '[MISSING DATA]'
    when prerequisites are missing.
    """

    # Mapping of binary aliases to specific environment variables
    ENV_MAPPINGS = {
        "crest": ["COCHEM_CREST_BIN", "CREST_BIN", "CREST_PATH"],
        "xcfour": ["COCHEM_CFOUR_BIN", "COCHEM_XCFOUR_BIN", "CFOUR_PATH", "CFOUR_ROOT"],
        "cfour": ["COCHEM_CFOUR_BIN", "COCHEM_XCFOUR_BIN", "CFOUR_PATH", "CFOUR_ROOT"],
        "orca": ["COCHEM_ORCA_BIN", "ORCA_BIN", "ORCA_PATH"],
        "xtb": ["COCHEM_XTB_BIN", "XTB_BIN", "XTB_PATH"],
    }

    @classmethod
    def resolve(cls, binary_name: str) -> Path:
        """Resolve an executable binary path from environment or system PATH.

        Parameters
        ----------
        binary_name : str
            Name of the binary to resolve (e.g., 'crest', 'xcfour', 'orca', 'xtb').

        Returns
        -------
        Path
            Absolute, resolved filesystem Path to the executable.

        Raises
        ------
        BinaryNotFoundError
            If the binary is not found, with '[MISSING DATA] <binary> executable not discovered in environment path'.
        """
        clean_name = binary_name.strip().lower()

        # 1. Check specific environment variables
        env_vars = cls.ENV_MAPPINGS.get(clean_name, [f"COCHEM_{clean_name.upper()}_BIN"])
        for var in env_vars:
            val = os.environ.get(var)
            if val:
                p = Path(val).resolve()
                # If CFOUR_ROOT points to directory, check bin/xcfour or xcfour
                if p.is_dir():
                    for sub in [
                        p / "bin" / clean_name,
                        p / "bin" / f"{clean_name}.exe",
                        p / clean_name,
                        p / f"{clean_name}.exe",
                        p / "bin" / "xcfour",
                        p / "bin" / "xcfour.exe",
                        p / "xcfour",
                        p / "xcfour.exe",
                    ]:
                        if sub.is_file() and os.access(sub, os.X_OK):
                            return sub
                        elif sub.is_file() and os.name == "nt":
                            return sub
                elif p.is_file():
                    return p

        # 2. Check standard shutil.which resolution
        which_path = shutil.which(binary_name)
        if which_path:
            resolved = Path(which_path).resolve()
            if resolved.is_file():
                return resolved

        # 3. Check with .exe extension if on Windows
        if os.name == "nt" and not binary_name.endswith(".exe"):
            which_exe = shutil.which(f"{binary_name}.exe")
            if which_exe:
                resolved = Path(which_exe).resolve()
                if resolved.is_file():
                    return resolved

        # Binary not discovered
        raise BinaryNotFoundError(
            f"[MISSING DATA] {binary_name} executable not discovered in environment path"
        )


class PathRegistry:
    """Authoritative filesystem registry for CoChem artifacts and scratch paths.

    Complies with Tripartite Filesystem Air-Gap (Ring 1 Static, Ring 2 Scratch, Ring 3 Artifacts).
    """

    @classmethod
    def get_artifacts_dir(cls) -> Path:
        """Resolve persistent artifacts directory backed by COCHEM_ARTIFACTS_DIR.

        Returns
        -------
        Path
            Resolved directory path guaranteed to exist on disk.
        """
        env_path = os.environ.get("COCHEM_ARTIFACTS_DIR") or os.environ.get("COCHEM_ARTIFACTS")
        if env_path:
            p = Path(env_path).resolve()
        else:
            p = Path(tempfile.gettempdir()) / "cochem" / "artifacts"

        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def create_scratch_dir(cls, prefix: str = "scratch") -> Path:
        """Create a dynamic, isolated scratch subdirectory for worker execution.

        Parameters
        ----------
        prefix : str
            Prefix identifier for the temporary directory.

        Returns
        -------
        Path
            Unique, newly created scratch directory.
        """
        env_scratch = os.environ.get("COCHEM_SCRATCH_DIR") or os.environ.get("SLURM_TMPDIR") or os.environ.get("TMPDIR")
        if env_scratch:
            base_dir = Path(env_scratch).resolve()
        else:
            base_dir = Path(tempfile.gettempdir()) / "cochem" / "scratch"

        base_dir.mkdir(parents=True, exist_ok=True)
        scratch_path = Path(tempfile.mkdtemp(prefix=f"{prefix}_", dir=str(base_dir))).resolve()
        return scratch_path
