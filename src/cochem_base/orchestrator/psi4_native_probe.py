"""Audit Psi4's actual compiled core, not its version-only Python launcher."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path


def probe_psi4_native(executable: str | Path, timeout_seconds: float = 15.0,
                      environment: dict[str, str] | None = None) -> tuple[str | None, dict[str, str], str | None]:
    """Run an actual bounded He/HF loader probe and fingerprint native components.

    Psi4 --version can succeed when importing psi4.core fails (for example an
    incompatible LibXC). Only this successful native calculation establishes
    availability. Scientific method support is still validated by its consumer.
    """
    binary = Path(executable).resolve()
    driver = """import hashlib
import json
from pathlib import Path
import sys
import psi4
psi4.set_memory(268435456)
psi4.set_num_threads(1)
psi4.core.set_output_file('native.out', False)
psi4.set_options({'basis': 'sto-3g', 'scf_type': 'pk', 'reference': 'rhf'})
molecule = psi4.geometry('0 1\\nHe 0 0 0\\nunits angstrom\\nsymmetry c1')
energy = psi4.energy('hf', molecule=molecule)
components = {}
for path in (Path(psi4.core.__file__).resolve(), Path(sys.executable).resolve()):
    with path.open('rb') as stream:
        components[str(path)] = hashlib.file_digest(stream, 'sha256').hexdigest()
Path('native-probe.json').write_text(json.dumps({'version': psi4.__version__, 'energy_hartree': float(energy), 'components': components}, allow_nan=False))
"""
    try:
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError("Psi4 launcher is absent or not executable")
        env = dict(environment or os.environ)
        for key in ("OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
            env[key] = "1"
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        with tempfile.TemporaryDirectory(prefix="cochem-psi4-native-") as directory:
            folder = Path(directory)
            (folder / "probe.py").write_text(driver)
            completed = subprocess.run([str(binary), "probe.py", "driver.out"], cwd=folder, env=env,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       timeout=timeout_seconds, check=False)
            receipt = folder / "native-probe.json"
            if completed.returncode != 0 or not receipt.is_file():
                raise ValueError("Psi4 native import/HF probe failed; version-only launcher output is insufficient")
            result = json.loads(receipt.read_text())
            observed = result["version"]
            energy = float(result["energy_hartree"])
            if not re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:[A-Za-z0-9.+_-]*)", observed):
                raise ValueError("Native Psi4 version is malformed")
            if not math.isfinite(energy) or not -3.5 < energy < -2.0:
                raise ValueError("Native He/HF probe did not return a physically consistent electronic energy")
            components = result["components"]
            if not isinstance(components, dict) or len(components) != 2:
                raise ValueError("Native compiled core and interpreter fingerprints are required")
            for name, expected in components.items():
                path = Path(name)
                if not path.is_absolute() or not path.is_file():
                    raise ValueError("Native Psi4 component does not name an existing absolute file")
                with path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                        raise ValueError("Native Psi4 component changed during audit")
            return observed, components, None
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        return None, {}, str(exc)
