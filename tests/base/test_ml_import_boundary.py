"""BASE mathematical primitives do not import the optional TORQ runtime."""

import os
from pathlib import Path
import subprocess
import sys


def test_local_ml_primitives_work_without_optional_torq_imports(tmp_path):
    source = Path(__file__).resolve().parents[2] / "src"
    code = """
import sys
import numpy as np
from cochem_base.ml import ActiveLearningManager, KernelRidgeModel
import cochem_base.ml.krr

assert not any(name == 'Libraries' or name.startswith('Libraries.') for name in sys.modules)
assert 'torch' not in sys.modules
points = np.asarray([[0.0], [0.5], [1.0]])
values = np.sin(points[:, 0])
model = KernelRidgeModel(alpha=1e-10)
model.fit(points, values)
assert np.allclose(model.predict(points), values, atol=1e-8)
assert ActiveLearningManager is not None
"""
    env = dict(os.environ, PYTHONPATH=str(source))
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
