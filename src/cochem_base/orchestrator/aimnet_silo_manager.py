"""Provision the isolated AIMNet 0.2.0 CPU environment with exact dependencies."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from cochem_base.orchestrator.micro_silo_manager import (
    MicroSiloValidationError,
    isolated_environment,
    verify_micro_silo,
)
from cochem_base.orchestrator.ml_silo_manager import TORCH_CPU_WHEEL
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS

AIMNET_CPU_IMPORTS = ("torch", "aimnet", "warp", "nvalchemiops")


def provision_aimnet_silo(root: str | Path) -> dict:
    """Create or verify one immutable CPU silo; no checkpoint is downloaded.

    Model provenance and scientific validation belong to the consuming module.
    The CPU tensor/autograd probe proves native loading, not model accuracy or
    CUDA capability. Existing package drift is reported instead of repaired.
    """
    root = Path(root).resolve()
    from cochem.core.context import assert_writable_path

    assert_writable_path(root)
    if sys.version_info[:2] != (3, 12) or sys.platform != "linux" or platform.machine() != "x86_64":
        raise MicroSiloValidationError("Verified AIMNet CPU provisioner requires Linux x86-64 Python 3.12")
    python = root / "bin/python"
    if not python.exists():
        if root.exists() and any(root.iterdir()):
            raise MicroSiloValidationError("Refusing to overwrite a nonempty AIMNet silo")
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-I", "-m", "venv", str(root)], check=True,
                       env=isolated_environment(), timeout=120)
        commands = [
            [str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
             "--no-deps", "--report", str(root / "torch-install-report.json"), TORCH_CPU_WHEEL],
            [str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check", "--no-input",
             "--no-deps", "--report", str(root / "aimnet-install-report.json"),
             *[pin for pin in DEFAULT_PINS["aimnet2"] if not pin.startswith("torch==")]],
        ]
        for number, command in enumerate(commands):
            with (root / f"aimnet-install-{number}.log").open("x") as stream:
                subprocess.run(command, check=True, env=isolated_environment(), timeout=900,
                               stdout=stream, stderr=subprocess.STDOUT)
    # Warp emits a native initialization banner. Keep the generic JSON-stream
    # probe to torch and verify the remaining imports through the file probe.
    evidence = verify_micro_silo(root, python_version="3.12", requirements=DEFAULT_PINS["aimnet2"],
                                 imports=["torch"])
    # Use a file for structured evidence; native libraries may emit import logs.
    probe_path = root / "aimnet-cpu-native-probe.json"
    script = """import importlib, importlib.metadata, json, pathlib, sys, torch
from aimnet.calculators import AIMNet2Calculator
for name in ['aimnet', 'warp', 'nvalchemiops']:
 module = importlib.import_module(name)
 paths = [module.__file__] if getattr(module, '__file__', None) else list(module.__path__)
 assert paths and all(pathlib.Path(path).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve()) for path in paths), 'native module is outside the audited silo'
torch.set_num_threads(1)
assert torch.__version__ == '2.8.0+cpu' and torch.version.cuda is None, 'not the pinned CPU Torch build'
assert not torch.cuda.is_available(), 'CPU profile cannot establish CUDA capability'
x = torch.tensor([1., 2., 3.], dtype=torch.float64, device='cpu', requires_grad=True)
value = x.square().sum()
value.backward()
assert value.item() == 14. and torch.equal(x.grad, torch.tensor([2., 4., 6.], dtype=torch.float64)), 'native CPU autograd failed'
result = {'profile':'cpu','torch':torch.__version__,'aimnet':importlib.metadata.version('aimnet'),
 'warp':importlib.metadata.version('warp-lang'),'nvalchemi':importlib.metadata.version('nvalchemi-toolkit-ops'),
 'native_cpu_autograd':True,'cuda_capability_claimed':False,'model_inference_performed':False}
pathlib.Path(sys.argv[1]).write_text(json.dumps(result, sort_keys=True)+'\\n')
"""
    environment = isolated_environment()
    environment.update(CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
    try:
        process = subprocess.run([str(python), "-I", "-c", script, str(probe_path)], check=True,
                                 env=environment, timeout=60, capture_output=True, text=True)
        native = json.loads(probe_path.read_text())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise MicroSiloValidationError("AIMNet native CPU import/autograd probe failed: " +
                                       str(getattr(exc, "stderr", "") or exc)) from exc
    (root / "aimnet-cpu-native-probe.stdout").write_text(process.stdout)
    (root / "aimnet-cpu-native-probe.stderr").write_text(process.stderr)
    evidence["imports"] = list(AIMNET_CPU_IMPORTS)
    receipt = {"schema_version": "cochem-aimnet-cpu-install/1", "profile": "cpu",
               "cuda_capability_claimed": False, "torch_source": TORCH_CPU_WHEEL,
               "verification": evidence, "native_cpu_probe": native}
    temporary = root / "aimnet-provisioning-receipt.tmp"
    temporary.write_text(json.dumps(receipt, indent=2) + "\n")
    os.replace(temporary, root / "aimnet-provisioning-receipt.json")
    return evidence
