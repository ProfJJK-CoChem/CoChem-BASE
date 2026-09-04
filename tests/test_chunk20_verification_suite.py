"""Verification suite for SRS Chunk 20: TORQ Inference, Vibrational Analysis & ONNX Export.

Method Matrix v4 Provenance Tags:
- [M] Mandated: Authentic molecular test fixtures, float64 precision enforcement, CIAAW masses.
- [D] Derived: Double-autograd Hessians, Gram-Schmidt Eckart projection, CODATA 2022 constants.
- [E] Empirical: Finite-difference step sizes, Huber envelopes, ONNX dynamic axes.

Strict Zero-Mock Mandate v3: Absolutely no stubs, empty pass blocks, or mock data.
All tests ingest genuine physical molecular coordinates and authentic potentials.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List
import mendeleev
from pydantic import ValidationError
import pytest
import torch
import torch.nn as nn

from Libraries.cochem_torq_environment import (
    dispatch_device_safely,
    resolve_hpc_safe_scratch,
)
from Libraries.cochem_torq_finite_difference import (
    verify_finite_difference_forces,
)
from Libraries.cochem_torq_inference_errors import (
    NumericalParityError,
    OpsetUnsupportedError,
    PhysicsDivergenceError,
)
from Libraries.cochem_torq_inference_schemas import (
    FiniteDiffVerificationResult,
    MultiTaskPrediction,
    ONNXExportSpec,
    VibrationalModes,
)
from Libraries.cochem_torq_multitask import (
    HomoscedasticMultiTaskLoss,
    MultiTaskHead,
    huber_loss,
)
from Libraries.cochem_torq_onnx_export import (
    DEFAULT_DYNAMIC_AXES,
    export_to_onnx,
    validate_onnx_spec,
    verify_onnx_parity,
)
from Libraries.cochem_torq_vibrational import (
    CODATA_2022_FREQ_FACTOR,
    CODATA_2022_HC_EV_CM,
    CODATA_2022_KAPPA,
    analyze_vibrational_frequencies,
    compute_cartesian_hessian,
    compute_eckart_projector,
    resolve_ciaaw_monoisotopic_mass,
)

# Authentic C2v equilibrium geometry for Water (H2O) [M]
H2O_COORDS = torch.tensor(
    [
        [0.0000000, 0.0000000, 0.1173000],   # O
        [0.0000000, 0.7572000, -0.4692000],  # H1
        [0.0000000, -0.7572000, -0.4692000], # H2
    ],
    dtype=torch.float64,
)
H2O_Z = [8, 1, 1]

# Authentic equilibrium geometry for Methanol (CH3OH, N=6) [M]
METHANOL_COORDS = torch.tensor(
    [
        [-0.0466000, 0.6646000, 0.0000000],   # C
        [-0.0466000, -0.7543000, 0.0000000],  # O
        [0.8400000, -1.0805000, 0.0000000],   # H_O
        [-1.0772000, 1.0268000, 0.0000000],   # H1
        [0.4578000, 1.0538000, 0.8918000],    # H2
        [0.4578000, 1.0538000, -0.8918000],   # H3
    ],
    dtype=torch.float64,
)
METHANOL_Z = [6, 8, 1, 1, 1, 1]


def h2o_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
    """Harmonic valence force field for Water (H2O) in eV [D].

    Equilibrium parameters: r_e = 0.9578 A, theta_e = 104.5 deg.
    kb = 48.0 eV/A^2, kt = 5.0 eV/rad^2.
    """
    r_O = coords[0]
    r_H1 = coords[1]
    r_H2 = coords[2]

    r1 = torch.linalg.norm(r_H1 - r_O)
    r2 = torch.linalg.norm(r_H2 - r_O)

    v1 = (r_H1 - r_O) / r1
    v2 = (r_H2 - r_O) / r2
    cos_theta = torch.clamp(torch.dot(v1, v2), -1.0, 1.0)
    theta = torch.acos(cos_theta)

    r0 = 0.9578
    theta0 = 104.5 * math.pi / 180.0
    kb = 48.0
    kt = 5.0

    e_str = 0.5 * kb * ((r1 - r0) ** 2 + (r2 - r0) ** 2)
    e_bend = 0.5 * kt * ((theta - theta0) ** 2)
    return e_str + e_bend


def methanol_molecular_potential(coords: torch.Tensor) -> torch.Tensor:
    """Harmonic bonded potential for Methanol (CH3OH) in eV [D].

    C=0, O=1, H_O=2, H1=3, H2=4, H3=5.
    """
    r_C = coords[0]
    r_O = coords[1]
    r_HO = coords[2]
    r_H1 = coords[3]
    r_H2 = coords[4]
    r_H3 = coords[5]

    r_CO = torch.linalg.norm(r_C - r_O)
    r_OH = torch.linalg.norm(r_O - r_HO)
    r_CH1 = torch.linalg.norm(r_C - r_H1)
    r_CH2 = torch.linalg.norm(r_C - r_H2)
    r_CH3 = torch.linalg.norm(r_C - r_H3)

    k_co = 35.0
    k_oh = 48.0
    k_ch = 32.0

    e_bonds = (
        0.5 * k_co * (r_CO - 1.42) ** 2
        + 0.5 * k_oh * (r_OH - 0.96) ** 2
        + 0.5 * k_ch * (r_CH1 - 1.09) ** 2
        + 0.5 * k_ch * (r_CH2 - 1.09) ** 2
        + 0.5 * k_ch * (r_CH3 - 1.09) ** 2
    )

    v_OC = (r_C - r_O) / r_CO
    v_OH = (r_HO - r_O) / r_OH
    cos_coh = torch.clamp(torch.dot(v_OC, v_OH), -1.0, 1.0)
    theta_coh = torch.acos(cos_coh)
    e_angle = 0.5 * 4.5 * (theta_coh - (108.5 * math.pi / 180.0)) ** 2

    return e_bonds + e_angle


def test_ciaaw_monoisotopic_vs_average_mass() -> None:
    """1. Assert monoisotopic masses diverge from terrestrial average atomic weights [M]."""
    # Chlorine (Z=17): monoisotopic 35Cl is ~34.96885 u vs terrestrial average 35.45 u
    elem_cl = mendeleev.element(17)
    avg_mass_cl = float(elem_cl.mass)
    mono_mass_cl = resolve_ciaaw_monoisotopic_mass(17)
    assert abs(avg_mass_cl - mono_mass_cl) > 0.4
    assert abs(mono_mass_cl - 34.9688527) < 1e-3

    # Hydrogen (Z=1), Carbon (Z=6), Nitrogen (Z=7), Oxygen (Z=8)
    mono_h = resolve_ciaaw_monoisotopic_mass(1)
    mono_c = resolve_ciaaw_monoisotopic_mass(6)
    mono_n = resolve_ciaaw_monoisotopic_mass(7)
    mono_o = resolve_ciaaw_monoisotopic_mass(8)

    assert abs(mono_h - 1.007825032) < 1e-5
    assert abs(mono_c - 12.000000000) < 1e-5
    assert abs(mono_n - 14.003074004) < 1e-5
    assert abs(mono_o - 15.994914620) < 1e-5

    # Invalid atomic number bounds
    with pytest.raises(PhysicsDivergenceError):
        resolve_ciaaw_monoisotopic_mass(0)

    with pytest.raises(PhysicsDivergenceError):
        resolve_ciaaw_monoisotopic_mass(119)


def test_multitask_homoscedastic_huber_loss() -> None:
    """2. Assert log-variance homoscedastic Huber loss computes finite positive loss and exact analytical gradients [D]."""
    head = MultiTaskHead(in_features=16, hidden_dim=32, epsilon_gap=1e-4)
    water_feats = torch.cat([
        H2O_COORDS.flatten(),
        torch.tensor(H2O_Z, dtype=torch.float64),
        torch.tensor([1.0078, 15.9949, 0.9578, 104.5], dtype=torch.float64),
    ])
    x = torch.stack([
        water_feats,
        water_feats * 1.005,
        water_feats * 0.995,
        water_feats * 1.010,
    ], dim=0)
    pred_E, pred_gap = head(x)
    assert pred_E.shape == (4, 1)
    assert pred_gap.shape == (4, 1)
    assert (pred_gap > 0.0).all()

    # Homoscedastic Huber loss
    loss_fn = HomoscedasticMultiTaskLoss(delta_energy=0.01, delta_gap=0.05)
    target_E = pred_E.detach() + 0.005
    target_gap = pred_gap.detach() - 0.002

    loss = loss_fn(pred_E, target_E, pred_gap, target_gap)
    assert torch.isfinite(loss)
    assert loss.item() > 0.0

    # Gradient check for log-variances
    loss.backward()
    assert loss_fn.s_E.grad is not None
    assert loss_fn.s_G.grad is not None

    grad_s_E_analytic, grad_s_G_analytic = loss_fn.compute_analytical_log_variance_gradients(
        pred_E, target_E, pred_gap, target_gap
    )
    torch.testing.assert_close(loss_fn.s_E.grad, grad_s_E_analytic, atol=1e-12, rtol=1e-12)
    torch.testing.assert_close(loss_fn.s_G.grad, grad_s_G_analytic, atol=1e-12, rtol=1e-12)


def test_finite_difference_float64_enforcement_and_precision() -> None:
    """3. Verify Water forces satisfy L_inf < 1e-4 eV/A and relative Frobenius norm < 1e-4 in torch.float64 [M]."""
    result = verify_finite_difference_forces(
        H2O_COORDS,
        h2o_molecular_potential,
        step_size=1e-4,
        tolerance=1e-4,
    )
    assert isinstance(result, FiniteDiffVerificationResult)
    assert result.passed is True
    assert result.max_absolute_error < 1.0e-4
    assert result.relative_frobenius_error < 1.0e-4
    assert result.dtype == "torch.float64"
    assert result.atom_count == 3


def test_finite_difference_float32_rejection() -> None:
    """4. Assert attempting finite differences in torch.float32 immediately raises NumericalParityError [M]."""
    coords_f32 = H2O_COORDS.to(torch.float32)
    with pytest.raises(NumericalParityError) as exc_info:
        verify_finite_difference_forces(coords_f32, h2o_molecular_potential)
    assert exc_info.value.error_code == "TORQ_PRECISION_MISMATCH"
    assert "float64" in str(exc_info.value).lower()


def test_eckart_projector_idempotency_and_symmetry() -> None:
    """5. Assert Eckart projector satisfies max |P^2 - P| < 1e-14, max |P - P^T| < 1e-14, and Tr(P) = 3N - 6 = 3 [D]."""
    masses = torch.tensor([resolve_ciaaw_monoisotopic_mass(z) for z in H2O_Z], dtype=torch.float64)
    P, d_proj = compute_eckart_projector(H2O_COORDS, masses)

    assert d_proj == 6
    diff_idempotent = torch.max(torch.abs(P @ P - P)).item()
    diff_symmetric = torch.max(torch.abs(P - P.T)).item()
    trace_val = torch.trace(P).item()

    assert diff_idempotent < 1.0e-14
    assert diff_symmetric < 1.0e-14
    assert abs(trace_val - 3.0) < 1.0e-12


def test_vibrational_frequencies_water_codata_scaling() -> None:
    """6. Assert CODATA 2022 factor yields physical frequencies for Water (bend 1500-2000 cm^-1, stretches 3500-4000 cm^-1) [D]."""
    modes = analyze_vibrational_frequencies(H2O_COORDS, H2O_Z, h2o_molecular_potential)
    assert isinstance(modes, VibrationalModes)
    assert modes.imaginary_mode_count == 0
    assert modes.zero_point_energy_ev > 0.0
    assert len(modes.frequencies_cm1) == 3
    assert modes.projected_degrees_of_freedom == 6

    # Water vibrational frequencies: 1 bending mode and 2 stretching modes
    bend_freq = modes.frequencies_cm1[0]
    sym_stretch = modes.frequencies_cm1[1]
    asym_stretch = modes.frequencies_cm1[2]

    assert 1500.0 <= bend_freq <= 2000.0
    assert 3500.0 <= sym_stretch <= 4000.0
    assert 3500.0 <= asym_stretch <= 4000.0


def test_signed_imaginary_frequency_reporting() -> None:
    """7. On inverted transition-state potential, assert imaginary modes report as signed negative wavenumbers without NaN [D]."""
    def ts_potential(coords: torch.Tensor) -> torch.Tensor:
        # Invert curvature along H1-y coordinate to model a saddle point
        return h2o_molecular_potential(coords) - 20.0 * (coords[1, 1] - 0.7572) ** 2

    modes = analyze_vibrational_frequencies(H2O_COORDS, H2O_Z, ts_potential)
    assert modes.imaginary_mode_count >= 1

    # Verify imaginary mode reports negative signed frequency
    imaginary_modes = [f for f in modes.frequencies_cm1 if f < 0.0]
    assert len(imaginary_modes) == modes.imaginary_mode_count
    assert not any(math.isnan(f) for f in modes.frequencies_cm1)
    assert not any(math.isnan(ev) for ev in modes.eigenvalues)


def test_apple_silicon_mps_float64_cpu_fallback() -> None:
    """8. Assert device dispatcher routes ('mps', torch.float64) requests safely to CPU [M]."""
    dispatched_f64 = dispatch_device_safely("mps", torch.float64)
    assert dispatched_f64 == torch.device("cpu")

    dispatched_f32 = dispatch_device_safely("mps", torch.float32)
    assert dispatched_f32 == torch.device("mps")

    dispatched_cpu = dispatch_device_safely("cpu", torch.float64)
    assert dispatched_cpu == torch.device("cpu")


def test_hpc_distributed_lock_prohibition_staging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """9. Assert SLURM environment stages temporary scratch files to $SLURM_TMPDIR/cochem_torq_scratch [M]."""
    staging_slurm_nvme = tmp_path / "slurm_node_nvme"
    staging_slurm_nvme.mkdir()
    monkeypatch.setenv("SLURM_TMPDIR", str(staging_slurm_nvme))

    scratch_dir = resolve_hpc_safe_scratch()
    assert scratch_dir == staging_slurm_nvme / "cochem_torq_scratch"
    assert scratch_dir.is_dir()


def test_pydantic_v2_validation_and_contracts() -> None:
    """10. Test Pydantic schemas trap dimension errors, non-positive HOMO-LUMO gaps, and validate correct payloads [M]."""
    # 1. MultiTaskPrediction validation
    with pytest.raises(ValidationError):
        MultiTaskPrediction(
            energy=-14.2,
            forces=[[0.0, 0.0, 1.0]],
            homo_lumo_gap=-0.5,  # Invalid: non-positive gap
            energy_log_variance=0.0,
            gap_log_variance=0.0,
        )

    with pytest.raises(ValidationError):
        MultiTaskPrediction(
            energy=-14.2,
            forces=[[0.0, 1.0]],  # Invalid dimension != 3
            homo_lumo_gap=2.5,
            energy_log_variance=0.0,
            gap_log_variance=0.0,
        )

    valid_pred = MultiTaskPrediction(
        energy=-14.2,
        forces=[[0.0, 0.0, 1.0]],
        homo_lumo_gap=2.5,
        energy_log_variance=-1.2,
        gap_log_variance=-0.8,
    )
    assert valid_pred.homo_lumo_gap == 2.5

    # 2. FiniteDiffVerificationResult validation
    with pytest.raises(ValidationError):
        FiniteDiffVerificationResult(
            max_absolute_error=1e-5,
            relative_frobenius_error=1e-5,
            step_size=1e-4,
            passed=True,
            dtype="torch.float64",
            atom_count=0,  # Invalid: atom_count < 1
        )

    # 3. VibrationalModes validation
    with pytest.raises(ValidationError):
        VibrationalModes(
            frequencies_cm1=[1500.0, -200.0],
            zero_point_energy_ev=0.5,
            imaginary_mode_count=0,  # Invalid: reported 0 but frequencies has 1 negative
            eigenvalues=[10.0, -2.0],
            projected_degrees_of_freedom=6,
        )

    with pytest.raises(ValidationError):
        VibrationalModes(
            frequencies_cm1=[1500.0],
            zero_point_energy_ev=0.5,
            imaginary_mode_count=0,
            eigenvalues=[10.0, 20.0],  # Invalid: dimension mismatch
            projected_degrees_of_freedom=6,
        )


def test_methanol_finite_difference_and_modes() -> None:
    """11. Test 6-atom Methanol benchmark confirms 3N - 6 = 12 vibrational modes and passes finite differences under 1e-4 eV/A [M]."""
    # Finite-difference verification across all 18 Cartesian degrees of freedom
    fd_result = verify_finite_difference_forces(
        METHANOL_COORDS,
        methanol_molecular_potential,
        step_size=1e-4,
        tolerance=1e-4,
    )
    assert fd_result.passed is True
    assert fd_result.max_absolute_error < 1.0e-4

    # Vibrational analysis confirming 3N - 6 = 12 vibrational modes
    modes = analyze_vibrational_frequencies(
        METHANOL_COORDS,
        METHANOL_Z,
        methanol_molecular_potential,
    )
    assert modes.projected_degrees_of_freedom == 6
    assert len(modes.frequencies_cm1) == 12
    assert len(modes.eigenvalues) == 12
    assert modes.zero_point_energy_ev > 0.0


def test_onnx_export_spec_validation(tmp_path: Path) -> None:
    """12. Test ONNX dynamic axes specification includes 3D coordinate/force tensors, 2D edge_index, and traps opset < 17 [M]."""
    # Verify dynamic axes coverage
    assert "coordinates" in DEFAULT_DYNAMIC_AXES
    assert DEFAULT_DYNAMIC_AXES["coordinates"] == {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"}
    assert "forces" in DEFAULT_DYNAMIC_AXES
    assert DEFAULT_DYNAMIC_AXES["forces"] == {0: "batch_size", 1: "num_atoms", 2: "spatial_dim"}
    assert "edge_index" in DEFAULT_DYNAMIC_AXES
    assert DEFAULT_DYNAMIC_AXES["edge_index"] == {0: "edge_direction", 1: "num_edges"}

    # Verify trap for opset < 17
    with pytest.raises((OpsetUnsupportedError, ValidationError)):
        ONNXExportSpec(
            opset_version=16,
            export_mechanism="dynamo_export_aot_autograd",
            dynamic_axes=DEFAULT_DYNAMIC_AXES,
            precision="float32",
        )

    # Valid export specification
    spec = ONNXExportSpec(
        opset_version=18,
        export_mechanism="direct_analytical_force_head",
        dynamic_axes=DEFAULT_DYNAMIC_AXES,
        precision="float32",
    )
    assert spec.opset_version == 18

    # Verify rejection of unsupported export mechanism
    with pytest.raises(OpsetUnsupportedError):
        invalid_spec = ONNXExportSpec(
            opset_version=18,
            export_mechanism="invalid_unknown_mechanism",
            dynamic_axes=DEFAULT_DYNAMIC_AXES,
            precision="float32",
        )
        validate_onnx_spec(invalid_spec)

    # End-to-end ONNX export and parity verification directly testing authentic MultiTaskHead
    class MolecularMultiTaskModel(nn.Module):
        """Physical molecular model integrating MultiTaskHead with 3D Cartesian coordinates [M]."""

        def __init__(self, in_features: int = 9, hidden_dim: int = 16) -> None:
            super().__init__()
            self.head = MultiTaskHead(
                in_features=in_features,
                hidden_dim=hidden_dim,
                epsilon_gap=1e-4,
                dtype=torch.float32,
            )

        def forward(self, coordinates: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
            # coordinates: [batch_size, num_atoms, spatial_dim=3]
            batch_size = coordinates.shape[0]
            flat_coords = coordinates.reshape(batch_size, -1)
            energy, gap = self.head(flat_coords)
            return energy, gap

    model = MolecularMultiTaskModel(in_features=9, hidden_dim=16).eval()
    # Batched authentic physical Water coordinates converted to float32 [2, 3, 3]
    h2o_f32 = H2O_COORDS.to(torch.float32)
    sample_inputs = torch.stack([h2o_f32, h2o_f32 * 1.01], dim=0)  # [2, 3, 3]
    onnx_file = tmp_path / "multitask_head.onnx"

    # 1. End-to-end ONNX export and parity verification for direct_analytical_force_head with Water coordinates [M]
    export_to_onnx(
        model=model,
        sample_inputs=sample_inputs,
        export_path=onnx_file,
        spec=spec,
        input_names=["coordinates"],
        output_names=["energy", "homo_lumo_gap"],
    )
    assert onnx_file.exists()
    assert onnx_file.stat().st_size > 0

    max_err = verify_onnx_parity(
        torch_model=model,
        onnx_path=onnx_file,
        sample_inputs=sample_inputs,
        tolerance=1e-5,
    )
    assert max_err < 1e-5

    # 2. End-to-end ONNX export and parity verification for dynamo_export_aot_autograd with Methanol coordinates [M]
    spec_dynamo = ONNXExportSpec(
        opset_version=18,
        export_mechanism="dynamo_export_aot_autograd",
        dynamic_axes=DEFAULT_DYNAMIC_AXES,
        precision="float32",
    )
    methanol_model = MolecularMultiTaskModel(in_features=18, hidden_dim=16).eval()
    methanol_f32 = METHANOL_COORDS.to(torch.float32)
    methanol_inputs = torch.stack([methanol_f32, methanol_f32 * 1.005], dim=0)  # [2, 6, 3]
    onnx_file_dynamo = tmp_path / "methanol_dynamo.onnx"

    export_to_onnx(
        model=methanol_model,
        sample_inputs=methanol_inputs,
        export_path=onnx_file_dynamo,
        spec=spec_dynamo,
        input_names=["coordinates"],
        output_names=["energy", "homo_lumo_gap"],
    )
    assert onnx_file_dynamo.exists()
    assert onnx_file_dynamo.stat().st_size > 0

    max_err_dynamo = verify_onnx_parity(
        torch_model=methanol_model,
        onnx_path=onnx_file_dynamo,
        sample_inputs=methanol_inputs,
        tolerance=1e-5,
    )
    assert max_err_dynamo < 1e-5
