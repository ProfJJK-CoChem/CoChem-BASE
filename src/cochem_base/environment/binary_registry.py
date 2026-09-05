"""CoChem Ecosystem Dynamic Binary Registry.

Compliant with Method Matrix v4, 6-Tier Environment Matrix, and Anti-Spoofing Protocol v2.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from cochem_base.exceptions import BinaryNotFoundError


class BinaryRegistry:
    """Dynamic resolution registry for external computational chemistry binaries.

    Resolves executables (e.g., crest, xcfour, orca, xtb) dynamically across host
    environments using environment variable anchors and system PATH. Raises typed
    BinaryNotFoundError with tag '[MISSING DATA]' when executables are missing.
    """

    ENV_MAPPINGS: dict[str, list[str]] = {
        "crest": ["COCHEM_CREST_BIN", "CREST_BIN", "CREST_PATH"],
        "xcfour": ["COCHEM_CFOUR_BIN", "COCHEM_XCFOUR_BIN", "CFOUR_PATH", "CFOUR_ROOT"],
        "cfour": ["COCHEM_CFOUR_BIN", "COCHEM_XCFOUR_BIN", "CFOUR_PATH", "CFOUR_ROOT"],
        "orca": ["COCHEM_ORCA_BIN", "ORCA_BIN", "ORCA_PATH"],
        "xtb": ["COCHEM_XTB_BIN", "XTB_BIN", "XTB_PATH"],
    }

    @classmethod
    def resolve(cls, binary_name: str) -> Path:
        """Resolve an executable binary path from environment anchors or system PATH.

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
            If the binary is absent, with tag '[MISSING DATA]'.
        """
        clean_name = binary_name.strip().lower()

        # 1. Check specific environment variable anchors
        env_vars = cls.ENV_MAPPINGS.get(clean_name, [f"COCHEM_{clean_name.upper()}_BIN"])
        for var in env_vars:
            val = os.environ.get(var)
            if val:
                p = Path(val).resolve()
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
                        if sub.is_file() and (os.access(sub, os.X_OK) or os.name == "nt"):
                            return sub
                elif p.is_file():
                    return p

        # 2. Check standard system PATH resolution via shutil.which
        which_path = shutil.which(binary_name)
        if which_path:
            resolved = Path(which_path).resolve()
            if resolved.is_file():
                return resolved

        # 3. Check with .exe suffix on Windows platforms
        if os.name == "nt" and not binary_name.endswith(".exe"):
            which_exe = shutil.which(f"{binary_name}.exe")
            if which_exe:
                resolved = Path(which_exe).resolve()
                if resolved.is_file():
                    return resolved

        # 4. Binary missing: raise specific standardized exceptions with [MISSING DATA]
        if clean_name == "crest":
            raise BinaryNotFoundError(
                "[MISSING DATA] CREST executable not discovered in environment path or COCHEM_CREST_BIN. "
                "Provision CREST or configure GOAT-only conformer exploration."
            )
        elif clean_name in ("xcfour", "cfour"):
            raise BinaryNotFoundError(
                "[MISSING DATA] CFOUR executable (xcfour) not found. "
                "Cannot execute coupled-cluster analytic force fields."
            )
        else:
            raise BinaryNotFoundError(
                f"[MISSING DATA] {binary_name} executable not discovered in environment path"
            )


__all__ = ["BinaryRegistry"]
