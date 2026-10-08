"""Verify the real CPU JAX precision context and live Mendeleev database."""

import json
import subprocess
import sys

from scripts.manage_modules import _build_env


def run_gate(code: str) -> dict:
    result = subprocess.run([sys.executable, "-B", "-c", code], env=_build_env(),
        capture_output=True, text=True, timeout=60, check=True)
    return json.loads(result.stdout)


def test_real_cpu_precision_and_dynamic_database_are_verified_and_cached():
    report = run_gate("""import json
from dataclasses import asdict
import jax
from cochem_base.validators.preflight import validate_ingestion_toolchain
jax.config.update('jax_enable_x64', False)
first=validate_ingestion_toolchain()
assert validate_ingestion_toolchain() is first
assert jax.config.jax_enable_x64
print(json.dumps(asdict(first)))
""")
    assert report["jax_dtype"] == "float64"
    assert report["jax_backend"] == "cpu"
    assert report["dynamic_mass_verified"] is True
    assert report["jax_version"] == report["jaxlib_version"] == "0.8.1"


def test_changed_precision_context_fails_closed_after_initial_verification():
    report = run_gate("""import json
import jax
from cochem_base.exceptions import PreflightValidationError
from cochem_base.validators.preflight import validate_ingestion_toolchain
validate_ingestion_toolchain()
jax.config.update('jax_enable_x64', False)
try:
    validate_ingestion_toolchain()
except PreflightValidationError as error:
    print(json.dumps({'rejected':True,'message':str(error),'x64':jax.config.jax_enable_x64}))
else:
    raise AssertionError('A real changed-to-float32 JAX context was admitted')
""")
    assert report["rejected"] is True
    assert report["x64"] is False
    assert "not float64" in report["message"]


def test_genuine_thread_local_disabled_precision_context_is_rejected():
    report = run_gate("""import json
import jax
from cochem_base.exceptions import PreflightValidationError
from cochem_base.validators.preflight import validate_ingestion_toolchain
with jax.experimental.enable_x64(False):
    try:
        validate_ingestion_toolchain()
    except PreflightValidationError as error:
        print(json.dumps({'rejected':True,'message':str(error)}))
    else:
        raise AssertionError('A real thread-local float32 context was admitted')
""")
    assert report["rejected"] is True
    assert "float64" in report["message"]
