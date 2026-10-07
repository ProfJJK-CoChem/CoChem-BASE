"""Provision the verified MACE 0.3.16 CPU silo without unpinned resolution."""
from __future__ import annotations
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from cochem_base.orchestrator.micro_silo_manager import (
    MicroSiloValidationError, isolated_environment, verify_micro_silo,
)
from cochem_base.orchestrator.silo_dependency_pins import DEFAULT_PINS

TORCH_CPU_WHEEL = ('https://download-r2.pytorch.org/whl/cpu/'
                   'torch-2.8.0%2Bcpu-cp312-cp312-manylinux_2_28_x86_64.whl'
                   '#sha256=cb9a8ba8137ab24e36bf1742cb79a1294bd374db570f09fc15a5e1318160db4e')


def provision_mace_silo(root: str | Path) -> dict:
    """Create or verify exact CPU packages; never claim CUDA on CPU Torch.

    Immutable existing installations are verified, never repaired implicitly.
    Native Stage 0 still performs all package imports and registry publication.
    The direct Torch wheel's upstream SHA-256 is enforced by pip, with its
    download provenance retained independently of Stage 0 health checks.
    """
    root = Path(root).resolve()
    from cochem.core.context import assert_writable_path
    assert_writable_path(root)
    if sys.version_info[:2] != (3, 12) or sys.platform != 'linux' or platform.machine() != 'x86_64':
        raise MicroSiloValidationError('Verified MACE CPU provisioner requires Linux x86-64 Python 3.12')
    python = root / 'bin/python'
    if not python.exists():
        if root.exists() and any(root.iterdir()):
            raise MicroSiloValidationError('Refusing to overwrite a nonempty ML silo')
        root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, '-I', '-m', 'venv', str(root)], check=True,
                       env=isolated_environment(), timeout=120)
        commands = [
            [str(python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
             '--no-deps', '--report', str(root/'torch-install-report.json'), TORCH_CPU_WHEEL],
            [str(python), '-I', '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
             '--no-deps', '--report', str(root/'mace-install-report.json'),
             *[pin for pin in DEFAULT_PINS['mace'] if not pin.startswith('torch==')]],
        ]
        for number, command in enumerate(commands):
            with (root/f'install-{number}.log').open('x') as stream:
                subprocess.run(command, check=True, env=isolated_environment(), timeout=900,
                               stdout=stream, stderr=subprocess.STDOUT)
    evidence = verify_micro_silo(root, python_version='3.12', requirements=DEFAULT_PINS['mace'],
                                 imports=['torch', 'mace', 'e3nn'])
    receipt = {'schema_version':'cochem-mace-cpu-install/1', 'profile':'cpu', 'cuda_capability_claimed':False,
               'torch_source':TORCH_CPU_WHEEL, 'verification':evidence}
    temporary = root/'mace-provisioning-receipt.tmp'
    temporary.write_text(json.dumps(receipt,indent=2)+'\n')
    os.replace(temporary, root/'mace-provisioning-receipt.json')
    return evidence
