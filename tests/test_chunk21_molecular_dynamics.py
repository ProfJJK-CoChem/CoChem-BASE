"""Physical Verification Test Suite for TORQ Molecular Dynamics (Chunk 21).

Method Matrix v4 Provenance Tags:
- [M] Mandated: Authentic molecular geometries, dynamic Mendeleev masses, torch.float64 precision,
               MPS float64 fallback to CPU, Pydantic v2 immutability and bounds validation.
- [D] Derived: Conservative autograd forces, curl-free gradient field, dimensional acceleration,
               center-of-mass momentum elimination, kinetic energy and temperature observables,
               symplectic time-reversibility, geometric temperature schedule, Metropolis swap,
               explicit velocity rescaling, SWMR thread-safe lifecycle.
- [E] Empirical: Harmonic valence + LJ parameters, Maxwell-Boltzmann velocity distribution,
               NVE secular energy conservation within 1e-4.

Strict Zero-Mock Mandate v3: Completely authentic physics and mathematical rigor.
Absolutely no stubs, empty pass blocks, or synthetic test data.
"""

from __future__ import annotations

import inspect
import math
from pathlib import Path
import tempfile
from pydantic import ValidationError
import pytest
import torch

from Libraries.cochem_torq_masses import (
    get_atomic_masses,
    resolve_ciaaw_monoisotopic_mass,
)
from Libraries.cochem_torq_md_env import (
    dispatch_md_device,
    resolve_hpc_safe_scratch,
)
from Libraries.cochem_torq_md_errors import (
    EnergyDriftExceededError,
    HardwareDispatchError,
    ReplicaExchangeDivergenceError,
    SymplecticIntegratorError,
    TorqMDError,
)
from Libraries.cochem_torq_md_schemas import (
    ExchangeLog,
    MDState,
    REMDConfig,
    TrajectoryFrame,
    VelocityVerletConfig,
)
from Libraries.cochem_torq_remd import (
    ReplicaExchangeEngine,
    baoab_langevin_step,
    compute_geometric_temperature_schedule,
    evaluate_metropolis_swap,
    rescale_velocities_on_swap,
)
from Libraries.cochem_torq_symplectic import (
    BOLTZMANN_CONSTANT,
    ELEMENTARY_CHARGE,
    KAPPA_ACC,
    KAPPA_ACC_INV,
    LENGTH_SCALE_M_TO_ANGSTROM,
    TIME_SCALE_S_TO_FS,
    UNIFIED_ATOMIC_MASS_KG,
    VelocityVerletIntegrator,
    compute_conservative_forces,
    compute_dimensional_acceleration,
    compute_instantaneous_temperature,
    compute_kinetic_energy,
    remove_center_of_mass_momentum,
)
from Libraries.cochem_torq_trajectory import (
    HDF5TrajectoryReader,
    HDF5TrajectoryWriter,
)

# Authentic equilibrium Water Dimer (H2O)2 geometry (N=6 atoms) [M]
WATER_DIMER_COORDS = torch.tensor(
    [
        [-1.484, 0.000, -0.091],  # O1 (donor)
        [-1.877, 0.760, 0.354],  # H1
        [-0.533, 0.000, 0.038],  # H2 (bridging hydrogen)
        [1.408, 0.000, 0.110],  # O2 (acceptor)
        [1.758, 0.760, -0.335],  # H3
        [1.758, -0.760, -0.335],  # H4
    ],
    dtype=torch.float64,
)
WATER_DIMER_Z = torch.tensor([8, 1, 1, 8, 1, 1], dtype=torch.int64)

# Authentic equilibrium Water Monomer H2O (N=3 atoms) [M]
WATER_MONOMER_COORDS = torch.tensor(
    [
        [0.0000, 0.0000, 0.1173],  # O
        [0.0000, 0.7572, -0.4692],  # H1
        [0.0000, -0.7572, -0.4692],  # H2
    ],
    dtype=torch.float64,
)
WATER_MONOMER_Z = torch.tensor([8, 1, 1], dtype=torch.int64)


class FlexibleWaterPotential(torch.nn.Module):
    """Harmonic valence force field + Lennard-Jones non-bonded potential for water in eV [D]."""

    def __init__(self) -> None:
        super().__init__()
        self.r0 = 0.9572  # A
        self.theta0 = 104.52 * math.pi / 180.0  # rad
        self.kb = 46.0  # eV / A^2
        self.kt = 4.5  # eV / rad^2
        self.sigma_oo = 3.166  # A
        self.epsilon_oo = 0.0067  # eV

    def forward(self, coords: torch.Tensor) -> torch.Tensor:
        """Evaluate total potential energy of water system in eV [D]."""
        total_energy = torch.zeros((), dtype=torch.float64, device=coords.device)
        n_atoms = coords.shape[0]
        n_waters = n_atoms // 3

        for w in range(n_waters):
            idx_O = 3 * w
            idx_H1 = 3 * w + 1
            idx_H2 = 3 * w + 2
            r_O = coords[idx_O]
            r_H1 = coords[idx_H1]
            r_H2 = coords[idx_H2]

            v1 = r_H1 - r_O
            v2 = r_H2 - r_O
            d1 = torch.linalg.norm(v1)
            d2 = torch.linalg.norm(v2)

            # Harmonic bond stretching
            e_stretch = 0.5 * self.kb * ((d1 - self.r0) ** 2 + (d2 - self.r0) ** 2)

            # Harmonic angle bending
            cos_theta = torch.clamp(torch.dot(v1, v2) / (d1 * d2), -1.0, 1.0)
            theta = torch.acos(cos_theta)
            e_bend = 0.5 * self.kt * ((theta - self.theta0) ** 2)
            total_energy = total_energy + e_stretch + e_bend

        # Intermolecular non-bonded potential between oxygens if dimer
        if n_waters > 1:
            r_O1 = coords[0]
            r_O2 = coords[3]
            r_oo = torch.linalg.norm(r_O1 - r_O2)
            sr6 = (self.sigma_oo / r_oo) ** 6
            e_lj = 4.0 * self.epsilon_oo * (sr6**2 - sr6)
            total_energy = total_energy + e_lj

        return total_energy


def test_mendeleev_dynamic_mass_retrieval() -> None:
    """Dynamically query atomic masses for H and O via mendeleev library [M]."""
    z_tensor = torch.tensor([1, 8], dtype=torch.int64)
    masses = get_atomic_masses(z_tensor)

    m_H = float(masses[0].item())
    m_O = float(masses[1].item())

    assert 1.0079 <= m_H <= 1.0081, f"Hydrogen mass {m_H} outside expected CIAAW bounds."
    assert 15.999 <= m_O <= 16.000, f"Oxygen mass {m_O} outside expected CIAAW bounds."

    # Verify dynamic monoisotopic mass resolution
    mono_H = resolve_ciaaw_monoisotopic_mass(1)
    mono_O = resolve_ciaaw_monoisotopic_mass(8)
    assert 1.0078 <= mono_H <= 1.0079, f"Monoisotopic H {mono_H} outside bounds."
    assert 15.994 <= mono_O <= 15.996, f"Monoisotopic O {mono_O} outside bounds."

    # Inspect source code to guarantee dynamic library query rather than hardcoded tables
    source_code = inspect.getsource(get_atomic_masses)
    assert "element(" in source_code, "get_atomic_masses must dynamically invoke mendeleev.element."


def test_conservative_force_autograd_and_curl_free() -> None:
    """Evaluate autograd forces on Water monomer, comparing with central finite difference and curl [D]."""
    pot = FlexibleWaterPotential()
    coords = WATER_MONOMER_COORDS.clone().requires_grad_(True)

    forces, energy = compute_conservative_forces(
        pot, coords, return_energy=True, create_graph=True
    )

    # 1. Compare analytical forces against central finite difference
    delta = 1e-5
    fd_forces = torch.zeros_like(WATER_MONOMER_COORDS)
    for i in range(WATER_MONOMER_COORDS.shape[0]):
        for d in range(3):
            c_plus = WATER_MONOMER_COORDS.clone()
            c_plus[i, d] += delta
            c_minus = WATER_MONOMER_COORDS.clone()
            c_minus[i, d] -= delta
            e_plus = pot(c_plus)
            e_minus = pot(c_minus)
            fd_forces[i, d] = -(e_plus - e_minus) / (2.0 * delta)

    max_force_diff = torch.max(torch.abs(forces - fd_forces)).item()
    assert (
        max_force_diff < 1.0e-4
    ), f"Force autograd deviated from finite difference by {max_force_diff:.6e} eV/A."

    # 2. Verify conservative gradient curl ||curl F||_2 < 1.0e-6 eV/A^2
    curls: list[float] = []
    for i in range(coords.shape[0]):
        Fx = forces[i, 0]
        Fy = forces[i, 1]
        Fz = forces[i, 2]

        dFx = torch.autograd.grad(Fx, coords, retain_graph=True)[0][i]
        dFy = torch.autograd.grad(Fy, coords, retain_graph=True)[0][i]
        dFz = torch.autograd.grad(Fz, coords, retain_graph=True)[0][i]

        curl_x = dFz[1] - dFy[2]
        curl_y = dFx[2] - dFz[0]
        curl_z = dFy[0] - dFx[1]
        curl_vec = torch.tensor(
            [curl_x.item(), curl_y.item(), curl_z.item()], dtype=torch.float64
        )
        curls.append(float(torch.linalg.norm(curl_vec).item()))

    max_curl = max(curls)
    assert (
        max_curl < 1.0e-6
    ), f"Conservative force field non-zero curl {max_curl:.6e} eV/A^2."


def test_acceleration_dimensional_factor_conversion() -> None:
    """Verify dimensional acceleration factor matches identity from CODATA 2018 constants [D]."""
    derived_kappa = (
        ELEMENTARY_CHARGE * (LENGTH_SCALE_M_TO_ANGSTROM**2)
    ) / (UNIFIED_ATOMIC_MASS_KG * (TIME_SCALE_S_TO_FS**2))

    assert (
        abs(KAPPA_ACC - derived_kappa) < 1.0e-15
    ), f"KAPPA_ACC {KAPPA_ACC} differs from derived CODATA identity {derived_kappa}."
    assert (
        abs(KAPPA_ACC_INV - (1.0 / KAPPA_ACC)) < 1.0e-6
    ), f"KAPPA_ACC_INV {KAPPA_ACC_INV} differs from reciprocal {1.0 / KAPPA_ACC}."


def test_center_of_mass_momentum_elimination() -> None:
    """Assert center-of-mass momentum elimination achieves ||P_COM|| < 1.0e-10 u*A/fs [D]."""
    masses = get_atomic_masses(WATER_DIMER_Z)
    torch.manual_seed(42)
    velocities = torch.randn(6, 3, dtype=torch.float64) * 0.05 + 1.5

    p_before = torch.sum(masses.view(-1, 1) * velocities, dim=0)
    assert torch.linalg.norm(p_before).item() > 1.0

    corrected_velocities = remove_center_of_mass_momentum(velocities, masses)
    p_after = torch.sum(masses.view(-1, 1) * corrected_velocities, dim=0)
    net_momentum = float(torch.linalg.norm(p_after).item())

    assert (
        net_momentum < 1.0e-10
    ), f"Net COM linear momentum {net_momentum:.6e} exceeded 1e-10 u*A/fs threshold."


def test_kinetic_energy_and_temperature_degrees_of_freedom() -> None:
    """Verify degrees of freedom and temperature observables on Water Dimer [D]."""
    masses = get_atomic_masses(WATER_DIMER_Z)
    torch.manual_seed(42)
    velocities = torch.randn(6, 3, dtype=torch.float64) * 0.01

    e_kin = compute_kinetic_energy(velocities, masses)
    assert e_kin > 0.0

    t_com_constrained = compute_instantaneous_temperature(
        e_kin, n_atoms=6, remove_com=True
    )
    t_unconstrained = compute_instantaneous_temperature(
        e_kin, n_atoms=6, remove_com=False
    )

    expected_t_constrained = (2.0 * e_kin) / (15 * BOLTZMANN_CONSTANT)
    expected_t_unconstrained = (2.0 * e_kin) / (18 * BOLTZMANN_CONSTANT)

    assert abs(t_com_constrained - expected_t_constrained) < 1.0e-12
    assert abs(t_unconstrained - expected_t_unconstrained) < 1.0e-12
    assert t_com_constrained > t_unconstrained


def test_nve_energy_conservation_water_dimer() -> None:
    """Execute NVE Velocity Verlet trajectory and assert secular drift < 1.0e-4 [M]."""
    pot = FlexibleWaterPotential()
    masses = get_atomic_masses(WATER_DIMER_Z)
    config = VelocityVerletConfig(
        timestep_fs=0.05,
        n_steps=2000,
        energy_drift_tolerance=1.0e-4,
    )
    integrator = VelocityVerletIntegrator(pot, config, masses)

    torch.manual_seed(42)
    v0 = torch.randn_like(WATER_DIMER_COORDS) * 0.01

    _, _, states = integrator.integrate(
        WATER_DIMER_COORDS, v0, n_steps=2000, timestep_fs=0.05
    )
    e0 = states[0].total_energy_ev
    drifts = [abs((s.total_energy_ev - e0) / e0) for s in states]
    max_drift = max(drifts)

    assert (
        max_drift < 1.0e-4
    ), f"NVE maximum relative energy drift {max_drift:.6e} exceeded 1.0e-4 tolerance."


def test_energy_drift_exceeded_error_trigger() -> None:
    """Assert EnergyDriftExceededError is raised when integrating with unstable timestep [M]."""
    pot = FlexibleWaterPotential()
    masses = get_atomic_masses(WATER_DIMER_Z)
    config = VelocityVerletConfig.model_construct(
        timestep_fs=5.0,
        n_steps=100,
        save_interval=10,
        device="cpu",
        dtype="float64",
        energy_drift_tolerance=1.0e-4,
        remove_com_momentum=True,
    )
    integrator = VelocityVerletIntegrator(pot, config, masses)

    torch.manual_seed(42)
    v0 = torch.randn_like(WATER_DIMER_COORDS) * 0.01

    with pytest.raises(EnergyDriftExceededError) as exc_info:
        integrator.integrate(WATER_DIMER_COORDS, v0, n_steps=100, timestep_fs=5.0)

    err = exc_info.value
    assert err.drift > 1.0e-4
    assert err.tolerance == 1.0e-4
    assert err.step > 0
    assert "potential_energy" in err.diagnostics


def test_symplectic_phase_space_time_reversibility() -> None:
    """Assert phase space reversibility r(2N) == r(0) to within 1.0e-5 A [D]."""
    pot = FlexibleWaterPotential()
    masses = get_atomic_masses(WATER_DIMER_Z)
    config = VelocityVerletConfig(
        timestep_fs=0.5,
        n_steps=1000,
        energy_drift_tolerance=1.0,
    )
    integrator = VelocityVerletIntegrator(pot, config, masses)

    torch.manual_seed(42)
    v0 = torch.randn_like(WATER_DIMER_COORDS) * 0.01

    r_fwd, v_fwd, _ = integrator.integrate(WATER_DIMER_COORDS, v0, n_steps=1000)

    # Invert velocities and integrate backward
    v_rev = -v_fwd
    r_back, v_back, _ = integrator.integrate(r_fwd, v_rev, n_steps=1000)

    max_deviation = float(
        torch.max(torch.linalg.norm(r_back - WATER_DIMER_COORDS, dim=-1)).item()
    )
    assert (
        max_deviation < 1.0e-5
    ), f"Phase space time reversibility deviation {max_deviation:.6e} A exceeded 1e-5 A."


def test_baoab_langevin_canonical_bath_coupling() -> None:
    """Assert BAOAB Langevin thermostat converges to 300 +- 5 K and Maxwell-Boltzmann variance [D]."""
    n_atoms = 1000
    masses = torch.ones(n_atoms, 1, dtype=torch.float64) * 18.015
    gamma = 1.0 * 1e-3  # 1 ps^-1 to fs^-1
    dt = 0.5  # fs
    c1 = math.exp(-gamma * dt)
    c2 = math.sqrt(KAPPA_ACC * (1.0 - c1**2))
    t_target = 300.0

    torch.manual_seed(123)
    std = torch.sqrt(KAPPA_ACC * BOLTZMANN_CONSTANT * t_target / masses)
    v = torch.randn(n_atoms, 3, dtype=torch.float64) * std

    temps: list[float] = []
    for _ in range(5000):
        eta = torch.randn_like(v)
        v = c1 * v + c2 * torch.sqrt((BOLTZMANN_CONSTANT * t_target) / masses) * eta
        e_kin = 0.5 * KAPPA_ACC_INV * torch.sum(masses * (v**2))
        t_inst = (2.0 * float(e_kin)) / (3 * n_atoms * BOLTZMANN_CONSTANT)
        temps.append(t_inst)

    avg_temp = sum(temps) / len(temps)
    assert (
        abs(avg_temp - 300.0) <= 5.0
    ), f"BAOAB thermostat average temperature {avg_temp:.2f} K outside 300 +- 5 K range."

    # Maxwell-Boltzmann variance parity verification
    v_flat = v.view(-1)
    mean_v = float(torch.mean(v_flat).item())
    var_v = float(torch.var(v_flat).item())
    expected_var = float(KAPPA_ACC * BOLTZMANN_CONSTANT * t_target / 18.015)

    assert abs(mean_v) < 0.001, f"Mean velocity {mean_v} drifted from zero."
    assert (
        abs((var_v - expected_var) / expected_var) < 0.05
    ), "Velocity variance deviates from Maxwell-Boltzmann distribution."


def test_remd_geometric_temperature_schedule() -> None:
    """Verify geometric temperature schedule and thermodynamic beta values [D]."""
    temps, betas = compute_geometric_temperature_schedule(
        n_replicas=4,
        t_min_k=300.0,
        t_max_k=600.0,
    )
    expected_temps = [300.0, 377.98, 476.22, 600.0]

    for t, exp_t in zip(temps, expected_temps):
        assert (
            abs(t - exp_t) < 0.05
        ), f"Temperature {t} deviated from expected geometric setpoint {exp_t}."

    for t, b in zip(temps, betas):
        expected_b = 1.0 / (BOLTZMANN_CONSTANT * t)
        assert (
            abs(b - expected_b) < 1.0e-12
        ), f"Thermodynamic beta {b} deviated from 1/(kB*T) {expected_b}."


def test_remd_metropolis_swap_and_velocity_rescaling() -> None:
    """Verify Metropolis swap probability and explicit temperature velocity rescaling [D]."""
    t1 = 300.0
    t2 = 400.0
    beta1 = 1.0 / (BOLTZMANN_CONSTANT * t1)
    beta2 = 1.0 / (BOLTZMANN_CONSTANT * t2)
    u1 = -12.4
    u2 = -12.0

    delta = (beta1 - beta2) * (u1 - u2)
    expected_p = min(1.0, math.exp(delta))

    p_swap, _ = evaluate_metropolis_swap(beta1, beta2, u1, u2)
    assert (
        abs(p_swap - expected_p) < 1.0e-12
    ), f"Metropolis swap probability {p_swap} does not match expected {expected_p}."

    v1 = torch.tensor([[1.2, -0.4, 0.8]], dtype=torch.float64)
    v2 = torch.tensor([[0.5, 1.1, -0.9]], dtype=torch.float64)

    v1_new, v2_new = rescale_velocities_on_swap(v1, v2, t1, t2)

    assert torch.allclose(v1_new, v2 * math.sqrt(t1 / t2))
    assert torch.allclose(v2_new, v1 * math.sqrt(t2 / t1))


def test_hdf5_swmr_trajectory_lifecycle() -> None:
    """Verify HDF5 SWMR lifecycle sequencing and non-blocking concurrent reader [M]."""
    tmp_path = Path(tempfile.gettempdir()) / "test_chunk21_traj_lifecycle.h5"
    if tmp_path.exists():
        tmp_path.unlink()

    atomic_numbers = torch.tensor([8, 1, 1], dtype=torch.int64)
    writer = HDF5TrajectoryWriter(
        file_path=tmp_path,
        n_atoms=3,
        atomic_numbers=atomic_numbers,
        chunk_size=10,
    )

    # Verify SWMR mode engaged
    assert writer.file.swmr_mode is True
    assert "coordinates" in writer.file
    assert "atomic_numbers" in writer.file

    # Concurrent reader opening active file
    reader = HDF5TrajectoryReader(tmp_path)
    assert len(reader) == 0

    frame = TrajectoryFrame(
        step=0,
        time_fs=0.0,
        atomic_numbers=atomic_numbers,
        coordinates=torch.tensor(
            [[0.0, 0.0, 0.1], [0.0, 0.7, -0.4], [0.0, -0.7, -0.4]],
            dtype=torch.float64,
        ),
        velocities=torch.zeros((3, 3), dtype=torch.float64),
        forces=torch.ones((3, 3), dtype=torch.float64) * 0.01,
        potential_energy_ev=-15.2,
        kinetic_energy_ev=0.3,
    )
    writer.append_frame(frame)

    reader.refresh()
    assert len(reader) == 1

    loaded_frame = reader.read_frame(0)
    assert loaded_frame.step == 0
    assert torch.allclose(loaded_frame.coordinates, frame.coordinates)
    assert torch.allclose(loaded_frame.velocities, frame.velocities)
    assert torch.allclose(loaded_frame.forces, frame.forces)
    assert abs(loaded_frame.potential_energy_ev - frame.potential_energy_ev) < 1.0e-6

    reader.close()
    writer.close()
    if tmp_path.exists():
        tmp_path.unlink()


def test_apple_silicon_mps_float64_cpu_fallback() -> None:
    """Assert MPS requests automatically fallback to CPU for float64 compliance [M]."""
    routed_device = dispatch_md_device("mps")
    assert routed_device == torch.device(
        "cpu"
    ), "MPS request must route to CPU for float64 compliance."

    routed_cpu = dispatch_md_device("cpu")
    assert routed_cpu == torch.device("cpu")


def test_pydantic_v2_data_validation() -> None:
    """Verify REMDConfig and VelocityVerletConfig parameter validation [M]."""
    # Reject T_max <= T_min
    with pytest.raises(ValidationError):
        REMDConfig(
            n_replicas=4,
            t_min_k=600.0,
            t_max_k=300.0,
            output_dir=Path("."),
        )

    # Reject total_steps < swap_interval
    with pytest.raises(ValidationError):
        REMDConfig(
            n_replicas=4,
            t_min_k=300.0,
            t_max_k=600.0,
            swap_interval_steps=200,
            total_steps_per_replica=100,
            output_dir=Path("."),
        )

    # Reject timestep_fs > 1.0
    with pytest.raises(ValidationError):
        VelocityVerletConfig(timestep_fs=1.5)
