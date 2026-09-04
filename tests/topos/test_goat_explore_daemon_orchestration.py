import os
os.environ["JAX_ENABLE_X64"] = "True"

import tempfile
from pathlib import Path

import numpy as np
import pytest
from mendeleev import element

from core_engine.oet_server import (
    GoatExploreDaemon,
    deduplicate_conformers,
    generate_orca_goat_deck,
    parse_ensemble_xyz,
)
from cochem_base.schemas import GoatExploreDaemonConfig


def test_goat_explore_daemon_and_deck_generation():
    """Verify persistent oet_server daemon lifecycle, deck generation, and RMSD deduplication (Suggestion #56 / Method Matrix v4 §9B.4, Table 2 [M], [D])."""
    # Dynamic Mendeleev check
    c_elem = element("C")
    h_elem = element("H")
    assert c_elem.atomic_number == 6
    assert h_elem.atomic_number == 1

    with tempfile.TemporaryDirectory() as tmpdir:
        scratch_path = Path(tmpdir) / "scratch"
        socket_file = Path(tmpdir) / "oet_server.sock"

        cfg = GoatExploreDaemonConfig(
            socket_path=str(socket_file),
            scratch_dir=str(scratch_path),
            max_hopping_steps=100,
            tight_opt_threshold=True,
            rmsd_dedup_threshold=0.15,
        )

        daemon = GoatExploreDaemon(cfg)

        # 1. Start daemon in background and verify socket and lock
        daemon.start()
        assert daemon.lock_file.exists()
        assert socket_file.exists()

        # 2. Verify ORCA GOAT-EXPLORE input deck generation
        coords = np.array(
            [
                [0.0, 0.0, 0.0],
                [1.54, 0.0, 0.0],
                [-0.5, 1.0, 0.0],
                [-0.5, -1.0, 0.0],
                [2.0, 1.0, 0.0],
                [2.0, -1.0, 0.0],
            ],
            dtype=np.float64,
        )
        z_list = [6, 6, 1, 1, 1, 1]

        deck = daemon.generate_orca_input(coords, z_list, charge=0, multiplicity=1)

        # Assert mandatory ORCA directives and tightened %geom tolerances [M]
        assert "! GOAT-EXPLORE ExtOpt TightOpt" in deck
        assert "%geom" in deck
        assert "TolMaxG 1e-5" in deck
        assert "TolE 1e-7" in deck
        assert "TolRMSG 3e-6" in deck
        assert "TolRMSD 5e-5" in deck
        assert "TolMaxD 1e-4" in deck
        assert "InHess XTB2" in deck
        # Strict ban on Calc_Hess true [M]
        assert "Calc_Hess true" not in deck

        # 3. Create mock-free authentic .finalensemble.xyz containing 10 conformers:
        # 7 distinct conformers (spacing 0.4 A) and 3 near-duplicates (within 0.02 A RMSD)
        ensemble_lines = []
        # 7 distinct conformers
        for i in range(7):
            ensemble_lines.append("6")
            ensemble_lines.append(f"conformer_{i} energy=-78.{i:04d}")
            c_dist = 1.4 + 0.4 * i
            ensemble_lines.append(f"C  0.000000  0.000000  0.000000")
            ensemble_lines.append(f"C  {c_dist:.6f}  0.000000  0.000000")
            ensemble_lines.append("H -0.500000  1.000000  0.000000")
            ensemble_lines.append("H -0.500000 -1.000000  0.000000")
            ensemble_lines.append(f"H  {c_dist + 0.5:.6f}  1.000000  0.000000")
            ensemble_lines.append(f"H  {c_dist + 0.5:.6f} -1.000000  0.000000")

        # 3 near-duplicates of conformers 0, 1, 2 (shifted by only 0.01 A, RMSD < 0.05 A)
        for i in range(3):
            ensemble_lines.append("6")
            ensemble_lines.append(f"conformer_dup_{i} energy=-78.{i:04d}")
            c_dist = 1.4 + 0.4 * i + 0.01
            ensemble_lines.append(f"C  0.000000  0.000000  0.000000")
            ensemble_lines.append(f"C  {c_dist:.6f}  0.000000  0.000000")
            ensemble_lines.append("H -0.500000  1.000000  0.000000")
            ensemble_lines.append("H -0.500000 -1.000000  0.000000")
            ensemble_lines.append(f"H  {c_dist + 0.5:.6f}  1.000000  0.000000")
            ensemble_lines.append(f"H  {c_dist + 0.5:.6f} -1.000000  0.000000")

        xyz_file = scratch_path / "orca_job.finalensemble.xyz"
        xyz_file.write_text("\n".join(ensemble_lines) + "\n", encoding="utf-8")

        # Ingest and deduplicate
        raw_confs = parse_ensemble_xyz(xyz_file)
        assert len(raw_confs) == 10

        unique_confs = daemon.process_ensemble_results(xyz_file)
        assert len(unique_confs) == 7, f"Expected exactly 7 unique conformers, got {len(unique_confs)}"

        # 4. Trigger shutdown and assert process tree cleanly terminates
        daemon.shutdown()
        assert not daemon.lock_file.exists()
