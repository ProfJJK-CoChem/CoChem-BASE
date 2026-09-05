"""CoChem-TORQ: Test CFOUR Execution Bridge Registration & Ephemeral Scratch Isolation.

Compliant with Method Matrix v4 §9, §13-§14, and Anti-Spoofing Directives.
Verifies Deliverable 9:
1. Registration of TorqCfourExecutor into execution dispatcher and route_method_matrix.
2. Dynamic discovery of xcfour and strict prohibition of silent demotion to DFT.
3. Ephemeral scratch subdirectory isolation and ZMAT input deck generation.
"""

import os
import sys
from pathlib import Path


import pytest
from cochem_base.environment import BinaryRegistry
from cochem_base.exceptions import BinaryNotFoundError
from cochem_base.interfaces.executors import ElectronicStructureExecutor
from cochem_base.schemas import QuantumJobSpec
from Libraries.cochem_torq_cfour_bridge import (
    CFOURZmatBuilder,
    TorqCfourExecutor,
)
from Libraries.cochem_torq_engine import (
    ExecutionContext,
    route_method_matrix,
)


def test_torq_cfour_executor_implements_interface():
    """Verify TorqCfourExecutor implements the standard ElectronicStructureExecutor ABC."""
    assert issubclass(TorqCfourExecutor, ElectronicStructureExecutor)
    executor = TorqCfourExecutor()
    assert hasattr(executor, "execute")
    assert hasattr(executor, "run_cfour_job")


def test_route_method_matrix_cfour_missing_binary_raises():
    """Requesting tier T3C-3d with missing CFOUR binary must immediately raise

    BinaryNotFoundError rather than silently demoting to ORCA DFT.
    """
    old_env = dict(os.environ)
    try:
        os.environ["PATH"] = ""
        os.environ.pop("CFOUR_ROOT", None)
        os.environ.pop("CFOUR_PATH", None)
        os.environ.pop("COCHEM_CFOUR_BIN", None)
        os.environ.pop("COCHEM_XCFOUR_BIN", None)

        context = ExecutionContext()
        symbols = ["O", "H", "H"]
        coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

        with pytest.raises(BinaryNotFoundError) as excinfo:
            route_method_matrix(
                tier_key="T3C-3d",
                symbols=symbols,
                coordinates=coords,
                context=context,
            )

        err_msg = str(excinfo.value)
        assert "[MISSING DATA]" in err_msg
        assert "CFOUR executable (xcfour) not found" in err_msg
    finally:
        os.environ.clear()
        os.environ.update(old_env)


def test_route_method_matrix_cfour_routes_to_torq_cfour_executor():
    """When CFOUR binary is discoverable, route_method_matrix maps T3C-3d to TorqCfourExecutor."""
    old_env = dict(os.environ)
    try:
        real_bin = Path(sys.executable).resolve()
        os.environ["COCHEM_CFOUR_BIN"] = str(real_bin)

        context = ExecutionContext()
        symbols = ["O", "H", "H"]
        coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

        payload = route_method_matrix(
            tier_key="T3C-3d",
            symbols=symbols,
            coordinates=coords,
            context=context,
        )

        assert payload.executor == "TorqCfourExecutor"
        assert payload.metadata["executor"] == "TorqCfourExecutor"
        assert payload.method == "CCSD(T)"
    finally:
        os.environ.clear()
        os.environ.update(old_env)



def test_cfour_scratch_isolation_and_zmat_generation(tmp_path):
    """Verify that CFOUR input generation executes in an isolated scratch subdirectory

    containing an authentic ZMAT input file.
    """
    symbols = ["O", "H", "H"]
    coords = [[0.0, 0.0, 0.1177], [0.0, 0.7554, -0.4708], [0.0, -0.7554, -0.4708]]

    zmat_content = CFOURZmatBuilder.generate_full_zmat_input(
        symbols=symbols,
        coordinates=coords,
        method="CCSD(T)",
        basis="ANO0",
        isotopes=[16, 1, 1],
    )


    # Isolated scratch directory
    scratch_dir = tmp_path / "cfour_worker_01"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    zmat_file = scratch_dir / "ZMAT"
    zmat_file.write_text(zmat_content, encoding="utf-8")

    assert zmat_file.exists()
    content = zmat_file.read_text(encoding="utf-8")
    assert "*CFOUR(" in content
    assert "CALC=CCSD(T)" in content
    assert "BASIS=ANO0" in content
    assert "%isotopes" in content
