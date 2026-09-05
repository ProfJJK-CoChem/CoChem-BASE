"""C^2-Smooth Switching Envelope & Non-Blocking Socket IPC Zero-Mock Tests.

Method Matrix Reference: Method Matrix v4 §4.4, §8A, §10.2, §10.3, Suggestion #128.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. C^2-smooth quintic polynomial cutoff envelope continuity across boundary r_c.
2. Continuity of energy V(r) and force derivative F(r) = -dV/dr (|F(r+) - F(r-)| < 10^-7).
3. Conservative gradient conversion (g = -F) for ORCA engrad output under TolMaxG 1e-5.
4. Robust non-blocking socket IPC timeout and disconnection handling without process hangs.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest
import torch

from Libraries.cochem_torq_c2_cutoff import (
    quintic_c2_envelope,
    quintic_c2_first_derivative,
    quintic_c2_second_derivative,
    verify_cutoff_continuity,
)
from scripts.oet_client import (
    OETClient,
    OETDaemonConnectionError,
    convert_ase_forces_to_orca_gradient,
    write_engrad,
)


def test_c2_quintic_boundary_continuity():
    """Verify energy and force derivative continuity across boundary r_c (|F(r+) - F(r-)| < 1e-7) [M], [D]."""
    rc = 5.0  # Cutoff radius in Angstroms
    assert verify_cutoff_continuity(rc=rc, tolerance=1e-7) is True

    # Sweep infinitesimally across boundary: r- = rc - 1e-7, r+ = rc + 1e-7
    eps = 1e-7
    r_minus = torch.tensor([rc - eps], dtype=torch.float64)
    r_plus = torch.tensor([rc + eps], dtype=torch.float64)

    f_minus = quintic_c2_envelope(r_minus, rc=rc)
    f_plus = quintic_c2_envelope(r_plus, rc=rc)
    df_minus = quintic_c2_first_derivative(r_minus, rc=rc)
    df_plus = quintic_c2_first_derivative(r_plus, rc=rc)
    d2f_minus = quintic_c2_second_derivative(r_minus, rc=rc)
    d2f_plus = quintic_c2_second_derivative(r_plus, rc=rc)

    # Values at r+ must be exactly 0
    assert float(f_plus[0]) == 0.0
    assert float(df_plus[0]) == 0.0
    assert float(d2f_plus[0]) == 0.0

    # Step discontinuity across boundary must remain strictly < 1e-7
    assert abs(float(f_minus[0]) - float(f_plus[0])) < 1e-7
    assert abs(float(df_minus[0]) - float(df_plus[0])) < 1e-7
    assert abs(float(d2f_minus[0]) - float(d2f_plus[0])) < 1e-7


def test_conservative_gradient_sign_and_engrad_export(tmp_path: Path):
    """Verify gradient is strictly conservative (g = -F) and formats for ORCA [M]."""
    # Sample physical forces (eV / Angstrom) for 2 atoms
    forces_ev_ang = np.array([
        [0.100, -0.250, 0.050],
        [-0.100, 0.250, -0.050],
    ], dtype=np.float64)

    # Expected gradient g = -F converted to Eh / bohr
    grad_list = convert_ase_forces_to_orca_gradient(forces_ev_ang)
    assert len(grad_list) == 6

    # Verify sign flip: positive force component must yield negative gradient
    # F[0, 0] = +0.100 -> g[0] must be negative
    assert grad_list[0] < 0.0
    # F[0, 1] = -0.250 -> g[1] must be positive
    assert grad_list[1] > 0.0

    # Write ORCA .engrad file
    engrad_path = tmp_path / "test_job_EXT.engrad"
    written_path = write_engrad(
        engrad_path=engrad_path,
        num_atoms=2,
        energy_eh=-76.421500,
        gradient_eh_bohr=grad_list,
        dograd=True,
    )

    assert written_path.is_file()
    content = written_path.read_text(encoding="utf-8")
    assert "The current total energy in Eh" in content
    assert "-76.421500000000" in content
    assert "The current gradient in Eh/bohr" in content


def test_non_blocking_socket_ipc_timeout():
    """Verify non-blocking socket IPC timeout handling under simulated disconnection [M], [D]."""
    # Configure client pointing to an inactive local port with strict 0.5s timeout
    client = OETClient(
        host="127.0.0.1",
        port=59123,
        timeout=0.5,
        retries=1,
    )

    start_time = time.time()
    with pytest.raises((OETDaemonConnectionError, ConnectionRefusedError, OSError)):
        client.send_request({"type": "HEALTH_CHECK"})
    elapsed = time.time() - start_time

    # Must fail cleanly and fast (under 2.0 seconds) without hanging the process
    assert elapsed < 2.0, f"Socket communication hung for {elapsed:.2f} seconds exceeding non-blocking bound."
