"""Test suite for Asynchronous Multi-Seed GOAT Exploration via Parsl Queues (Suggestion #68).

Method Matrix v4 §8A.2, §9B.3 [M].
Strict Zero-Mock Mandate: Zero synthetic stubs, dynamic Mendeleev masses,
genuine Parsl worker dispatch, scratch sandbox isolation, and physical deduplication.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
import shutil

import numpy as np
import pytest

# Ensure repository paths are on sys.path
REPO_BASE = Path(__file__).resolve().parent.parent.parent
REPO_TORQ = REPO_BASE.parent / "CoChem-TORQ"
for p in [str(REPO_BASE / "src"), str(REPO_BASE), str(REPO_TORQ)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import parsl
from parsl.config import Config
from parsl.executors.threads import ThreadPoolExecutor as ParslThreadPool

from Libraries.cochem_torq_goat import (
    GoatRunner,
    GoatConfig,
    GoatExtOptDriver,
    MultiSeedGoatConfig,
    compute_rmsd,
    write_xyz_file,
    ConformerRecord,
)


def _generate_butane_conformer(dihedral_deg: float) -> tuple[list[str], np.ndarray]:
    """Generates authentic 3D coordinates for a butane conformer with specified C-C-C-C dihedral [D]."""
    theta = np.radians(109.5)
    r_cc = 1.54
    c1 = np.array([0.0, 0.0, 0.0], dtype=np.float64)
    c2 = np.array([r_cc, 0.0, 0.0], dtype=np.float64)
    c3 = c2 + np.array([-r_cc * np.cos(np.pi - theta), r_cc * np.sin(np.pi - theta), 0.0], dtype=np.float64)
    c4_base = c3 + np.array([r_cc * np.cos(np.pi - theta), r_cc * np.sin(np.pi - theta), 0.0], dtype=np.float64)

    # Rotate c4 about the c2-c3 bond axis by dihedral_deg
    axis = c3 - c2
    axis = axis / np.linalg.norm(axis)
    rad = np.radians(dihedral_deg)
    a = np.cos(rad / 2.0)
    b, c, d = -axis * np.sin(rad / 2.0)
    aa, bb, cc, dd = a * a, b * b, c * c, d * d
    bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
    rot = np.array([
        [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
        [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
        [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc]
    ], dtype=np.float64)

    c4 = c3 + rot @ (c4_base - c3)
    syms = ["C", "C", "C", "C"]
    coords = np.array([c1, c2, c3, c4], dtype=np.float64)
    return syms, coords


@pytest.fixture(scope="module")
def parsl_dfk():
    """Initializes and tears down genuine Parsl DataFlowKernel with GPU scout executor."""
    try:
        parsl.clear()
    except Exception:
        pass

    cfg = Config(
        executors=[
            ParslThreadPool(max_threads=4, label="cochem_scout_gpu"),
            ParslThreadPool(max_threads=4, label="cochem_anchor_cpu"),
        ]
    )
    dfk = parsl.load(cfg)
    yield dfk
    try:
        parsl.clear()
    except Exception:
        pass


def test_multi_seed_goat_asynchronous_concurrency(tmp_path, parsl_dfk, monkeypatch):
    """Verifies concurrent multi-seed GOAT conformer dispatch, sandbox isolation, and RMSD deduplication."""
    scratch_dir = tmp_path / "scratch"
    artifacts_dir = tmp_path / "artifacts"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("COCHEM_SCRATCH", str(scratch_dir))
    monkeypatch.setenv("COCHEM_ARTIFACTS", str(artifacts_dir))
    monkeypatch.setenv("COCHEM_ROOT", str(REPO_BASE))

    # 1. Prepare 4 distinct starting conformer geometries for butane
    dihedrals = [180.0, 65.0, -65.0, 115.0]  # anti, gauche+, gauche-, intermediate
    seed_files: list[Path] = []
    for idx, dih in enumerate(dihedrals):
        syms, coords = _generate_butane_conformer(dih)
        rec = ConformerRecord(
            index=idx,
            symbols=syms,
            coordinates=coords.tolist(),
            origin_engine="SEEDED",
            seed_id=f"seed_{idx+1:02d}",
            provenance_tag="[M]",
        )
        s_file = scratch_dir / f"butane_seed_{idx+1:02d}.xyz"
        write_xyz_file(s_file, [rec])
        seed_files.append(s_file)

    # 2. Configure MultiSeedGoatConfig
    multi_config = MultiSeedGoatConfig(
        seed_structures=[str(f) for f in seed_files],
        max_concurrent_seeds=4,
        rmsd_threshold_angstrom=0.15,
        energy_window_kcal_mol=6.0,
    )

    # 3. Instantiate GoatRunner under PHYSICAL force-field mode
    runner = GoatRunner(config=GoatConfig(driver=GoatExtOptDriver.PHYSICAL))

    # 4. Execute multi-seed exploration
    ensemble, report = runner.run_multi_seed_goat(
        seed_paths=multi_config,
        system_name="Butane",
        scratch_dir=scratch_dir,
        artifacts_dir=artifacts_dir,
    )

    # 5. Verify isolated sandbox directories in scratch: $COCHEM_SCRATCH/goat_seed_<hash>/
    for s_file in seed_files:
        s_bytes = s_file.read_bytes()
        s_hash = hashlib.sha256(s_bytes).hexdigest()[:12]
        expected_sandbox = scratch_dir / f"goat_seed_{s_hash}"
        assert expected_sandbox.exists(), f"Expected sandbox {expected_sandbox} was not created!"
        assert expected_sandbox.is_dir()

    # 6. Verify audit report metrics
    assert report.n_seeds == 4
    assert report.n_goat_raw >= 4
    assert report.n_goat_dedup_stage_b > 0
    assert report.n_goat_dedup_stage_b <= report.n_goat_raw
    assert report.goat_f1_baseline == 0.93

    # 7. Verify conformer filtering: energy window <= 6.0 kcal/mol [M]
    for conf in ensemble.conformers:
        assert conf.energy_kcal_rel <= 6.0, f"Conformer energy {conf.energy_kcal_rel} exceeds 6.0 kcal/mol cutoff"

    # 8. Verify conformer deduplication: pairwise RMSD >= 0.15 A [M]
    confs = ensemble.conformers
    for i in range(len(confs)):
        coords_i = np.array(confs[i].coordinates, dtype=np.float64)
        for j in range(i + 1, len(confs)):
            coords_j = np.array(confs[j].coordinates, dtype=np.float64)
            rmsd = compute_rmsd(coords_i, coords_j, symbols=confs[i].symbols)
            assert rmsd >= 0.15, f"Conformers {i} and {j} have RMSD {rmsd:.4f} < 0.15 A threshold!"

    # 9. Verify persistent artifacts in Ring 3
    conformers_xyz = artifacts_dir / "conformers.xyz"
    assert conformers_xyz.exists()
    assert conformers_xyz.stat().st_size > 0

    h5_file = artifacts_dir / "Butane_goat_ensemble.h5"
    assert h5_file.exists()
    assert h5_file.stat().st_size > 0

    report_json = artifacts_dir / "Butane_goat_audit_report.json"
    assert report_json.exists()
    assert report_json.stat().st_size > 0
