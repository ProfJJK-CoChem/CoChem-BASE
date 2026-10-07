"""Provision explicit MACE CPU or CUDA 12.8 profiles with exact package locks."""
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
from cochem_base.orchestrator.ml_cuda_sources import CUDA128_SOURCES
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS

TORCH_CPU_WHEEL = ('https://download-r2.pytorch.org/whl/cpu/'
                   'torch-2.8.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl'
                   '#sha256=cb9a8ba8137ab24e36bf1742cb79a1294bd374db570f09fc15a5e1318160db4e')


def mace_profile_lock(profile: str) -> str:
    if profile not in {"cpu", "cuda128"}:
        raise MicroSiloValidationError("MACE Torch profile must be explicitly cpu or cuda128")
    return "mace" if profile == "cpu" else "mace_cuda128"


def provision_mace_silo(root: str | Path, *, profile: str = "cpu") -> dict:
    """Create or verify exact CPU packages; never claim CUDA on CPU Torch.

    Immutable existing installations are verified, never repaired implicitly.
    Native Stage 0 still performs all package imports and registry publication.
    The direct Torch wheel's upstream SHA-256 is enforced by pip, with its
    download provenance retained independently of Stage 0 health checks.
    """
    lock = mace_profile_lock(profile)
    requirements = DEFAULT_PINS[lock]
    wheel_sources = ({"torch": TORCH_CPU_WHEEL} if profile == "cpu" else {
        name: source["url"] + "#sha256=" + source["sha256"]
        for name, source in CUDA128_SOURCES["packages"].items()
    })
    root = Path(root).resolve()
    from cochem.core.context import assert_writable_path
    assert_writable_path(root)
    if sys.version_info[:2] != (3, 12) or sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise MicroSiloValidationError('Reviewed MACE profiles require Linux x86-64 Python 3.12')
    python = root / 'bin/python'
    if not python.exists():
        if root.exists() and any(root.iterdir()):
            raise MicroSiloValidationError('Refusing to overwrite a nonempty ML silo')
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, '-I', '-m', 'venv', str(root)], check=True,
                       env=isolated_environment(), timeout=120)
        commands = [
            [str(python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
             '--no-deps', '--report', str(root/'torch-install-report.json'), *wheel_sources.values()],
            [str(python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
             '--no-deps', '--report', str(root/'mace-install-report.json'),
             *[pin for pin in requirements if pin.split('==', 1)[0] not in wheel_sources]],
        ]
        for number, command in enumerate(commands):
            with (root/f'install-{number}.log').open('x') as stream:
                subprocess.run(command, check=True, env=isolated_environment(), timeout=3600,
                               stdout=stream, stderr=subprocess.STDOUT)
    evidence = verify_micro_silo(root, python_version='3.12', requirements=requirements,
                                 imports=['torch', 'mace', 'e3nn'])
    probe = subprocess.run([str(python), '-I', '-c',
        "import json,torch; print(json.dumps({'cuda_runtime':torch.version.cuda,"
        "'cuda_available':torch.cuda.is_available(),'device_count':torch.cuda.device_count()}))"],
        check=True, capture_output=True, text=True, env=isolated_environment(), timeout=60)
    observed = json.loads(probe.stdout)
    expected_cuda = None if profile == 'cpu' else '12.8'
    if observed['cuda_runtime'] != expected_cuda:
        raise MicroSiloValidationError('Actual Torch CUDA runtime differs from the selected profile')
    receipt = {'schema_version':'cochem-mace-install/2', 'profile':profile,
               'cuda_capability_claimed':bool(profile == 'cuda128' and observed['cuda_available']),
               'torch_source':wheel_sources['torch'], 'wheel_sources':wheel_sources,
               'runtime_probe':observed, 'verification':evidence}
    evidence['dependency_profile'] = profile
    evidence['cuda_runtime'] = observed
    temporary = root/'mace-provisioning-receipt.tmp'
    temporary.write_text(json.dumps(receipt,indent=2)+'\n')
    os.replace(temporary, root/'mace-provisioning-receipt.json')
    return evidence
