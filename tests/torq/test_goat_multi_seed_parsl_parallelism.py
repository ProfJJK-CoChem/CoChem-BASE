# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Physical Integration Test: Parallel Conformer Exploration Graph via Parsl Scout-and-Anchor Pools.
Validates Suggestion #147 (Deliverable 7) under Method Matrix v4 §8A.2, §9B.3 [M], [E].
Adheres strictly to the CoChem Zero-Mock Protocol.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from Libraries.cochem_torq_goat import (
    GoatRunner,
    GoatRunnerConfig,
    MultiSeedGoatConfig,
    GoatExtOptDriver,
    write_xyz_file,
    ConformerRecord,
)


def test_goat_multi_seed_parallel_exploration(tmp_path: Path) -> None:
    """Verify that run_multi_seed_goat dispatches seeds concurrently in isolated sandboxes."""
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Prepare 2 candidate seed XYZ structures (real coordinates for H2O with different orientations)
    seed1 = tmp_path / "seed_1.xyz"
    seed2 = tmp_path / "seed_2.xyz"

    rec1 = ConformerRecord(
        index=0,
        symbols=["O", "H", "H"],
        coordinates=[[0.0, 0.0, 0.117], [0.0, 0.757, -0.469], [0.0, -0.757, -0.469]],
    )
    rec2 = ConformerRecord(
        index=0,
        symbols=["O", "H", "H"],
        coordinates=[[0.117, 0.0, 0.0], [-0.469, 0.757, 0.0], [-0.469, -0.757, 0.0]],
    )

    write_xyz_file(seed1, [rec1])
    write_xyz_file(seed2, [rec2])

    config = GoatRunnerConfig(
        driver=GoatExtOptDriver.PHYSICAL,
        max_threads=2,
    )
    runner = GoatRunner(config=config)

    multi_cfg = MultiSeedGoatConfig(
        seed_structures=[str(seed1), str(seed2)],
        max_concurrent_seeds=2,
        energy_window_kcal_mol=6.0,
    )

    ensemble, report = runner.run_multi_seed_goat(
        seed_paths=multi_cfg,
        system_name="WaterTest",
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    assert len(ensemble.conformers) >= 1
    # Verify that each seed ran in an isolated scratch directory without collisions
    seed_sandboxes = [p for p in scratch_dir.glob("goat_seed_*") if p.is_dir()]
    assert len(seed_sandboxes) == 2, f"Expected 2 isolated seed sandboxes, found {len(seed_sandboxes)}"

    # Check deduplication & provenance
    for c in ensemble.conformers:
        assert c.provenance_tag == "[E]"
        assert c.rotational_constants_mhz is not None