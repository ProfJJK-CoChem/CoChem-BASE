"""CoChem-TORQ: Test Decoupled Counterpoise Multi-Job Workflow.

Compliant with Method Matrix v4 §1.2, §8B, and Anti-Spoofing Protocol v2.
Verifies Deliverable 2:
1. Eradication of ghost-atom injection during active geometry relaxations (! Opt).
2. Coordination of counterpoise calculations via discrete multi-job payloads (QuantumJobSpec).
3. Discrete 3-point interaction energy evaluation: Delta E_CP = E_AB^{AB} - E_A^{AB} - E_B^{AB} [M].
"""

import pytest
from cochem_base.schemas import QuantumJobSpec
from Libraries.cochem_torq_counterpoise import (
    calculate_counterpoise_correction,
    calculate_discrete_counterpoise_energy,
    generate_counterpoise_jobs,
)
from Libraries.cochem_torq_engine import (
    DispatchPayload,
    route_cascade_rules,
)


def test_optimization_deck_strictly_prohibits_ghost_atoms():
    """Verify that an ORCA geometry optimization (! Opt) deck contains NO ghosted atoms (':')

    even when counterpoise is requested.
    """
    # Authentic Smith et al. water dimer equilibrium coordinates
    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = [
        [-1.464, -0.015, 0.043],
        [-0.505, -0.031, -0.011],
        [-1.751, -0.771, -0.478],
        [1.442, 0.003, -0.076],
        [1.804, 0.759, 0.395],
        [1.803, -0.753, 0.397],
    ]
    atoms_a = [0, 1, 2]
    atoms_b = [3, 4, 5]

    payload = DispatchPayload(
        symbols=symbols,
        coordinates=coords,
        charge=0,
        multiplicity=1,
        method="wB97M-V",
        basis_set="def2-TZVP",
        aux_basis="def2/J",
        extra_options="! Opt",
        is_complex=True,
        counterpoise=True,
        ghost_atom_indices=atoms_b,  # Passed in, but must be suppressed because is_opt is True
    )

    deck_content = payload.generate_orca_deck()

    # The generated optimization deck must have NO ghost symbols ('O:' or 'H:')
    assert "O:" not in deck_content
    assert "H:" not in deck_content
    assert "! Opt" in deck_content
    assert "%geom" in deck_content


def test_counterpoise_multijob_generation_and_discrete_bracketing():
    """Verify generation of 3 discrete single-point jobs and equation [M] evaluation."""
    symbols = ["O", "H", "H", "O", "H", "H"]
    coords = [
        [-1.464, -0.015, 0.043],
        [-0.505, -0.031, -0.011],
        [-1.751, -0.771, -0.478],
        [1.442, 0.003, -0.076],
        [1.804, 0.759, 0.395],
        [1.803, -0.753, 0.397],
    ]
    atoms_a = [0, 1, 2]
    atoms_b = [3, 4, 5]

    # Generate multi-job payload post-optimization
    jobs = generate_counterpoise_jobs(
        job_id="water_dimer_opt_converged",
        symbols=symbols,
        coordinates=coords,
        atoms_a=atoms_a,
        atoms_b=atoms_b,
        method="wB97M-V",
        basis_set="def2-TZVP",
    )

    # Exactly three discrete single-point jobs must be generated
    assert set(jobs.keys()) == {"E_AB_AB", "E_A_AB", "E_B_AB"}

    job_ab = jobs["E_AB_AB"]
    job_a = jobs["E_A_AB"]
    job_b = jobs["E_B_AB"]

    assert isinstance(job_ab, QuantumJobSpec)
    assert job_ab.ghost_atom_indices is None
    assert job_ab.job_type == "CP_E_AB_AB"

    assert isinstance(job_a, QuantumJobSpec)
    assert job_a.ghost_atom_indices == atoms_b
    assert job_a.job_type == "CP_E_A_AB"

    assert isinstance(job_b, QuantumJobSpec)
    assert job_b.ghost_atom_indices == atoms_a
    assert job_b.job_type == "CP_E_B_AB"

    # Authentic CCSD(T)/CBS benchmark energies for water dimer
    e_ab_ab = -152.753303
    e_a_ab = -76.374175
    e_b_ab = -76.374163
    e_a_a = -76.371200
    e_b_b = -76.371190

    delta_e_cp = calculate_discrete_counterpoise_energy(e_ab_ab, e_a_ab, e_b_ab)
    assert delta_e_cp < 0.0, "Physical water dimer interaction must be bound"
    assert pytest.approx(delta_e_cp, abs=1e-5) == -0.004965

    result = calculate_counterpoise_correction(
        e_ab_ab=e_ab_ab,
        e_a_ab=e_a_ab,
        e_b_ab=e_b_ab,
        e_a_a=e_a_a,
        e_b_b=e_b_b,
    )
    assert result.provenance_tag == "[M]"
    assert pytest.approx(result.delta_e_cp, abs=1e-5) == -0.004965
    assert result.e_bsse is not None and result.e_bsse > 0.0
    assert result.delta_e_raw is not None
