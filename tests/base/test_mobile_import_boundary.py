"""Backend exports must remain usable without importing optional notebook UI."""

from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("package_root", [".", "src"])
def test_backend_imports_do_not_load_mobile_widgets(package_root, tmp_path):
    repository = Path(__file__).resolve().parents[2]
    preferred_root = (repository / package_root).resolve()
    code = """
import pathlib
import sys

sys.path[:0] = [sys.argv[1], sys.argv[2]]
import cochem.mobile as mobile
import cochem.mobile.inorganic as inorganic
import cochem_mobile as cloud
from cochem_mobile.core.sandbox_broker import ContainerEngine, QuarantineConfig, SandboxBroker
from cochem.mobile.inorganic.models import MetalCategory

assert pathlib.Path(mobile.__file__).resolve() == pathlib.Path(sys.argv[1]) / 'cochem/mobile/__init__.py'
assert cloud.core.SandboxBroker is SandboxBroker
assert cloud.MetalCategory is inorganic.MetalCategory is mobile.MetalCategory is MetalCategory
assert 'InorganicBuilderWidget' in dir(mobile)
assert 'InorganicBuilderWidget' in dir(inorganic)
assert 'InorganicBuilderWidget' in dir(cloud)
assert 'anywidget' not in sys.modules
assert 'cochem.mobile.inorganic.ui' not in sys.modules
assert 'cochem.mobile.sketcher_widget' not in sys.modules
broker = SandboxBroker(preferred_engine=ContainerEngine.SUBPROCESS)
result = broker.execute(
    command=[sys.executable, '-c', "print('CORE_BACKEND_OK')"],
    config=QuarantineConfig(timeout_seconds=5.0, work_dir=pathlib.Path.cwd()),
)
assert result.exit_code == 0, result.stderr
assert result.stdout.strip() == 'CORE_BACKEND_OK'
for package in (mobile, inorganic, cloud):
    try:
        package.__not_a_public_export__
    except AttributeError:
        pass
    else:
        raise AssertionError('unknown exports must raise AttributeError')
"""
    result = subprocess.run(
        [sys.executable, "-I", "-c", code, str(preferred_root), str(repository / "src")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
