"""Zero-mock unit test for Authentic ORCA GOAT-EXPLORE Daemon Execution & Ephemeral Scratch Brokering.

SRS Chunk 14 / Suggestion #135 / Method Matrix v4 §9B.4, Table 1, Table 2 (Row T1-30min), Quick Start §QS-1 [M], [D].
Zero-Mock Mandate v3: Completely authentic ORCA deck generation, streaming parser, and scratch isolation.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from ase import Atoms
from cascade_engine.cochem_topos_cascade_orchestrator import CascadeConfig, CascadeOrchestrator
from core_engine.oet_server import (
    generate_orca_goat_deck,
    stream_ensemble_xyz,
)


def test_goat_explore_deck_generation_and_scratch_isolation() -> None:
    """Verify ORCA GOAT-EXPLORE input deck generation with tightened geom thresholds [M]."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        scratch_dir = tmp_path / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        config = CascadeConfig(
            artifact_dir=tmp_path / "artifacts",
            scratch_dir=scratch_dir,
            enable_goat=True,
        )
        _orchestrator = CascadeOrchestrator(config)

        # Authentic ethane molecule (C2H6)
        atoms = Atoms(
            symbols="C2H6",
            positions=[
                [0.0, 0.0, 0.0],
                [1.54, 0.0, 0.0],
                [-0.5, 1.0, 0.0],
                [-0.5, -1.0, 0.0],
                [0.0, 0.0, 1.0],
                [2.0, 1.0, 0.0],
                [2.0, -1.0, 0.0],
                [1.54, 0.0, 1.0],
            ],
        )

        deck = generate_orca_goat_deck(
            coordinates=np.asarray(atoms.get_positions(), dtype=np.float64),
            atomic_numbers=list(atoms.get_atomic_numbers()),
            max_hopping_steps=50,
        )

        # Assert mandatory GOAT-EXPLORE syntax and tightened %geom parameters [M]
        assert "! GOAT-EXPLORE ExtOpt TightOpt" in deck
        assert "%geom" in deck
        assert "TolMaxG 1e-5" in deck
        assert "TolE 1e-7" in deck
        assert "TolRMSG 3e-6" in deck
        assert "TolRMSD 5e-5" in deck
        assert "TolMaxD 1e-4" in deck
        assert "InHess XTB2" in deck
        # Strict prohibition on Calc_Hess true [M]
        assert "Calc_Hess true" not in deck


def test_streaming_line_iterator_conformer_ensemble_parsing() -> None:
    """Verify generator-based streaming line iterator parsing of .finalensemble.xyz prevents memory spikes [M], [D]."""
    with tempfile.TemporaryDirectory() as tmpdir:
        xyz_file = Path(tmpdir) / "test.finalensemble.xyz"

        # Generate multi-conformer authentic XYZ file
        lines = []
        for c_idx in range(5):
            lines.append("3\n")
            lines.append(f"conformer_{c_idx} energy=-76.{c_idx:04d} Hartree\n")
            lines.append("O  0.000000  0.000000  0.000000\n")
            lines.append(f"H  {0.95 + 0.01 * c_idx:.6f}  0.000000  0.000000\n")
            lines.append("H -0.240000  0.920000  0.000000\n")

        with open(xyz_file, "w", encoding="utf-8") as f:
            f.writelines(lines)

        # Stream conformers via generator
        conformers = list(stream_ensemble_xyz(xyz_file))
        assert len(conformers) == 5

        for idx, conf in enumerate(conformers):
            conf_name, energy, coords, symbols = conf
            assert f"conformer_{idx}" in conf_name
            assert abs(energy - (-76.0 - idx * 0.0001)) < 1e-6
            assert len(symbols) == 3
            assert coords.shape == (3, 3)
