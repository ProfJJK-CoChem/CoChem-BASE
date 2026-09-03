"""Unit tests for Deterministic Subprocess Broker & Fault Ladder.
Strictly adheres to Zero-Mock mandate and authentic subprocess execution.
"""

import pathlib
import sys
import uuid

import pytest

from cochem.concurrency.subprocess_broker import (
    DiagnosticTriageEngine,
    FailureCategory,
    SubprocessBroker,
    SubprocessExecutionResult,
)
from cochem.core.context import AirGapViolationError, ExecutionContext, scoped_context


@pytest.fixture
def broker_test_context(tmp_path: pathlib.Path) -> ExecutionContext:
    """Provide isolated tripartite execution context for subprocess broker tests."""
    src_dir = tmp_path / "cochem_src"
    data_dir = tmp_path / "cochem_data"
    artifacts_dir = tmp_path / "cochem_artifacts"
    exec_id = str(uuid.uuid4())
    scratch_dir = artifacts_dir / f"cochem_exec_{exec_id}"

    src_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    return ExecutionContext(
        execution_id=exec_id,
        session_name="subprocess_broker_test",
        src_dir=src_dir,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
        scratch_dir=scratch_dir,
        env_tier="Tier 1A",
    )


def test_triage_engine_orca_scf_escalation() -> None:
    """Verify triage engine escalates ORCA guess mappings: PModel -> Auto -> HCore."""
    triage = DiagnosticTriageEngine()
    failure_output = "ABORTING RUN: SCF NOT CONVERGED AFTER 125 ITERATIONS"

    cat, remedy = triage.triage_failure("ORCA", failure_output, exit_code=1, current_state={"guess": "PModel"})
    assert cat == FailureCategory.SCF_NON_CONVERGENCE
    assert remedy["guess"] == "Auto"

    cat2, remedy2 = triage.triage_failure("ORCA", failure_output, exit_code=1, current_state={"guess": "Auto"})
    assert remedy2["guess"] == "HCore"


def test_triage_engine_grid_integration_escalation() -> None:
    """Verify grid failure steps DFT numerical integration grid density monotonically."""
    triage = DiagnosticTriageEngine()
    failure_output = "NUMERICAL INTEGRATION ERROR: ACCURACY DEFGRID1 CANNOT BE SATISFIED"

    cat, remedy = triage.triage_failure("ORCA", failure_output, exit_code=2, current_state={"grid": "defgrid1"})
    assert cat == FailureCategory.GRID_INTEGRATION_FAILURE
    assert remedy["grid"] == "defgrid2"

    cat2, remedy2 = triage.triage_failure("ORCA", failure_output, exit_code=2, current_state={"grid": "defgrid2"})
    assert remedy2["grid"] == "defgrid3"


def test_triage_engine_pyscf_guess_escalation() -> None:
    """Verify PySCF solver escalates guess mapping: minao -> 1e -> atom."""
    triage = DiagnosticTriageEngine()
    failure_output = "SCF calculation does not converge with minao guess."

    cat, remedy = triage.triage_failure("PYSCF", failure_output, exit_code=1, current_state={"init_guess": "minao"})
    assert cat == FailureCategory.SCF_NON_CONVERGENCE
    assert remedy["init_guess"] == "1e"

    cat2, remedy2 = triage.triage_failure("PYSCF", failure_output, exit_code=1, current_state={"init_guess": "1e"})
    assert remedy2["init_guess"] == "atom"


def test_triage_engine_geometry_optimization_hessian_fallback() -> None:
    """Verify geometry stagnation triggers model Hessian fallback: Lindh -> GFN2-xTB -> r2SCAN-3c."""
    triage = DiagnosticTriageEngine()
    failure_output = "GEOMETRY OPTIMIZATION CYCLE 100 STAGNATED: TRUST RADIUS COLLAPSED"

    cat, remedy = triage.triage_failure(
        "ORCA", failure_output, exit_code=1, current_state={"model_hessian": "Lindh"}
    )
    assert cat == FailureCategory.GEOMETRY_OPTIMIZATION_STAGNATION
    assert remedy["model_hessian"] == "GFN2-xTB"

    cat2, remedy2 = triage.triage_failure(
        "ORCA", failure_output, exit_code=1, current_state={"model_hessian": "GFN2-xTB"}
    )
    assert remedy2["model_hessian"] == "r2SCAN-3c"


def test_triage_engine_crest_conformer_failure() -> None:
    """Verify CREST failure triggers fallback from GFN2-xTB to GFN-FF."""
    triage = DiagnosticTriageEngine()
    failure_output = "CREST CRITICAL ERROR: Interatomic distance below threshold r < 0.5 A"

    cat, remedy = triage.triage_failure("CREST", failure_output, exit_code=1, current_state={"method": "GFN2-xTB"})
    assert cat == FailureCategory.CONFORMER_SEARCH_FAILURE
    assert remedy["method"] == "GFN-FF"


def test_subprocess_broker_remediation_loop_success_on_retry(broker_test_context: ExecutionContext) -> None:
    """Verify SubprocessBroker executes, captures failure, applies remediation, and converges."""
    ctx = broker_test_context
    counter_file = ctx.scratch_dir / "attempt.txt"

    # Worker script that fails on attempt 1 with SCF convergence error, succeeds on attempt 2
    worker_script = (
        f"import pathlib, sys\n"
        f"p = pathlib.Path(r'{counter_file}')\n"
        f"count = int(p.read_text()) if p.exists() else 1\n"
        f"p.write_text(str(count + 1))\n"
        f"if count == 1:\n"
        f"    print('SCF NOT CONVERGED')\n"
        f"    sys.exit(1)\n"
        f"else:\n"
        f"    print('SCF CONVERGED: TOTAL ENERGY = -76.43215')\n"
        f"    sys.exit(0)\n"
    )

    with scoped_context(ctx):
        broker = SubprocessBroker(
            engine_name="ORCA",
            initial_params={"guess": "PModel"},
            scratch_dir=ctx.scratch_dir,
        )

        cmd = [sys.executable, "-c", worker_script]
        result = broker.execute_with_remediation(cmd)

        assert isinstance(result, SubprocessExecutionResult)
        assert result.success
        assert result.retries_attempted == 1
        assert result.final_params["guess"] == "Auto"
        assert "TOTAL ENERGY" in result.stdout


def test_subprocess_broker_max_retries_exhaustion(broker_test_context: ExecutionContext) -> None:
    """Verify broker stops after MAX_RETRIES=3 when worker persistently fails."""
    ctx = broker_test_context
    worker_script = "import sys\nprint('UNRECOVERABLE ERROR: SCF NOT CONVERGED')\nsys.exit(1)\n"

    with scoped_context(ctx):
        broker = SubprocessBroker(
            engine_name="ORCA",
            initial_params={"guess": "PModel"},
            scratch_dir=ctx.scratch_dir,
            max_retries=3,
        )

        cmd = [sys.executable, "-c", worker_script]
        result = broker.execute_with_remediation(cmd)

        assert not result.success
        assert result.retries_attempted == 3
        assert result.returncode != 0


def test_subprocess_broker_airgap_violation_rejection(broker_test_context: ExecutionContext) -> None:
    """Verify SubprocessBroker rejects un-sanitized scratch paths targeting $COCH_SRC."""
    ctx = broker_test_context

    with scoped_context(ctx):
        illegal_scratch = ctx.src_dir / "illegal_scratch"
        with pytest.raises(AirGapViolationError):
            SubprocessBroker(
                engine_name="ORCA",
                initial_params={},
                scratch_dir=illegal_scratch,
            )
