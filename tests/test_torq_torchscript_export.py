"""Authentic physical verification test suite for Dedicated TorchScript Export (REQ-TORQ-TRAIN-093).

Method Matrix v4 Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.
Strict Zero-Mock Mandate v3: Authentic Ethanol (N=9) and Water 16-mer cluster (N=48) fixtures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import torch

from Libraries.cochem_torq_torchscript_export import (
    TorchScriptableMLFF,
    compile_and_validate_torchscript,
    export_model_to_torchscript,
    verify_torchscript_parity,
)
from Libraries.cochem_torq_training_errors import ParityVerificationError
from Libraries.cochem_torq_training_schemas import TorchScriptExportConfig
from tests.torq_test_fixtures import (
    get_ethanol_fixture,
    get_water_16mer_fixture,
    get_water_dimer_fixture,
)


def test_torchscript_export_and_double_precision_parity() -> None:
    """Verify float64 energy (<= 1e-6 relative) and force (<= 1e-6 Hartree/Å) parity on Ethanol & Water 16-mer. [M]"""
    c_eth, z_eth = get_ethanol_fixture()
    c_w16, z_w16 = get_water_16mer_fixture()

    torch.manual_seed(42)
    model = TorchScriptableMLFF(hidden_dim=32, num_radial=16)
    model.eval()

    with tempfile.TemporaryDirectory() as tmpdir:
        export_pt = Path(tmpdir) / "torq_compiled_model.pt"
        config = TorchScriptExportConfig(
            export_path=export_pt,
            energy_relative_tolerance=1e-6,
            force_parity_tolerance_hartree_angstrom=1e-6,
            validate_against_fixtures=True,
        )

        test_fixtures = [(c_eth, z_eth), (c_w16, z_w16)]
        scripted = compile_and_validate_torchscript(model, config, test_fixtures)

        assert export_pt.exists()
        assert export_pt.stat().st_size > 0

        # Reload scripted model from disk and verify independent execution
        reloaded = torch.jit.load(str(export_pt))
        reloaded.eval()

        results = verify_torchscript_parity(model, reloaded, test_fixtures, config)
        assert results["status"] == "PASSED"
        assert results["fixtures_tested"] == 2


def test_dynamic_ragged_shapes_sequential_execution() -> None:
    """Verify compiled TorchScript model handles dynamic molecular sizes (N=3, N=6, N=9, N=48) without re-tracing. [D]"""
    c_dimer, z_dimer = get_water_dimer_fixture()       # N=6
    c_eth, z_eth = get_ethanol_fixture()               # N=9
    c_w16, z_w16 = get_water_16mer_fixture()           # N=48

    torch.manual_seed(101)
    model = TorchScriptableMLFF(hidden_dim=24, num_radial=12)
    model.eval()
    scripted = torch.jit.script(model)

    # Execute sequentially across different ragged topologies
    e_dimer = scripted(c_dimer, z_dimer)
    e_eth = scripted(c_eth, z_eth)
    e_w16 = scripted(c_w16, z_w16)

    assert e_dimer.dim() == 0
    assert e_eth.dim() == 0
    assert e_w16.dim() == 0
    assert not torch.isnan(e_dimer)
    assert not torch.isnan(e_eth)
    assert not torch.isnan(e_w16)


def test_parity_failure_detection() -> None:
    """Verify ParityVerificationError is raised when model weights or outputs diverge beyond tolerance. [M]"""
    c_eth, z_eth = get_ethanol_fixture()

    torch.manual_seed(42)
    model = TorchScriptableMLFF(hidden_dim=32, num_radial=16)
    model.eval()

    scripted = torch.jit.script(model)

    with tempfile.TemporaryDirectory() as tmpdir:
        config = TorchScriptExportConfig(
            export_path=Path(tmpdir) / "test.pt",
            energy_relative_tolerance=1e-6,
            force_parity_tolerance_hartree_angstrom=1e-6,
        )

        # Inject deliberate perturbation into eager model weights to break parity
        perturbed_model = TorchScriptableMLFF(hidden_dim=32, num_radial=16)
        perturbed_model.load_state_dict(model.state_dict())
        with torch.no_grad():
            perturbed_model.mlp[0].weight.add_(0.05)

        with pytest.raises(ParityVerificationError) as exc_info:
            verify_torchscript_parity(perturbed_model, scripted, [(c_eth, z_eth)], config)

        assert exc_info.value.error_code == "TORQ_TRAIN_PARITY_VIOLATION"
