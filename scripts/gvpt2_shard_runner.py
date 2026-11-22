#!/usr/bin/env python3
"""Deterministic 6-Shard Barone GVPT2 Displaced-Geometry Hessian Runner & Aggregator.

CHEM 312 Module 3 (Tennessee Tech University) — Implements K=6 parallel shard
partitioning of displaced-geometry Cartesian/normal-mode Hessians and exact
central-difference cubic (phi_ijk) & semi-diagonal quartic (phi_iikk)
aggregation for Barone GVPT2 anharmonic vibrational frequencies with Martin
Fermi-resonance screening.

Key invariants:
  - Deterministic K=6 partitioning (shard_id in 0..5): 100% displacement
    coverage, 0 overlap across shards.
  - Fail-closed incomplete-shard guard: if ANY shard 0..5 or expected
    displacement is absent, downstream anharmonic results are explicitly marked
    "PENDING" (never fabricated or substituted with harmonic values).
  - Pure dimensionless reduced normal-coordinate VPT2 formulas (Barone 2005)
    with Martin Fermi Type-I/Type-II resonance screening.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

DEFAULT_N_SHARDS = 6
HARTREE_TO_CM1 = 219474.63136320


def parse_harmonic_frequencies_cm1(raw_freqs: Sequence[Any]) -> list[float]:
    """Convert PySCF thermo.harmonic_analysis frequencies (complex for imaginary modes) to signed cm^-1.

    PySCF represents imaginary modes as purely imaginary complex numbers ``1j * w``;
    taking ``np.real()`` silently zeroes them out. Any entry with ``|imag| > 1e-6``
    is returned as ``-abs(imag)`` so imaginary-mode guards fail fast.
    """
    parsed: list[float] = []
    for item in raw_freqs:
        val = complex(item)
        if abs(val.imag) > 1e-6:
            parsed.append(-abs(float(val.imag)))
        else:
            parsed.append(float(val.real))
    return parsed


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_xyz_single(path: Path) -> tuple[list[str], np.ndarray, str]:
    """Read a single-frame XYZ file and return (symbols, coords_angstrom, comment)."""
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 3:
        raise ValueError(f"Invalid XYZ file (too few lines): {path}")
    n_atoms = int(lines[0].strip())
    comment = lines[1].strip()
    if len(lines) < n_atoms + 2:
        raise ValueError(f"Truncated XYZ file {path}: expected {n_atoms} atoms.")
    symbols: list[str] = []
    coords: list[list[float]] = []
    for row in lines[2 : 2 + n_atoms]:
        parts = row.split()
        if len(parts) != 4:
            raise ValueError(f"Invalid XYZ atom row in {path}: {row!r}")
        symbols.append(parts[0])
        coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return symbols, np.asarray(coords, dtype=np.float64), comment


def format_xyz(symbols: Sequence[str], coords: np.ndarray, comment: str) -> str:
    rows = [str(len(symbols)), comment]
    for sym, xyz in zip(symbols, coords):
        rows.append(f"{sym:<2s} {xyz[0]:16.10f} {xyz[1]:16.10f} {xyz[2]:16.10f}")
    return "\n".join(rows) + "\n"


def partition_displacements_deterministic(
    n_modes: int,
    *,
    n_shards: int = DEFAULT_N_SHARDS,
) -> dict[int, list[dict[str, Any]]]:
    """Deterministically partition 2 * n_modes (+/-) displacements across K shards.

    Guarantees 100% coverage, 0 overlap, and balanced shard counts.
    """
    if n_modes < 1:
        raise ValueError(f"n_modes must be >= 1, got {n_modes}.")
    if n_shards < 1:
        raise ValueError(f"n_shards must be >= 1, got {n_shards}.")

    shards: dict[int, list[dict[str, Any]]] = {sid: [] for sid in range(n_shards)}
    seq_id = 0
    for mode_idx in range(n_modes):
        for sign in (+1, -1):
            sid = seq_id % n_shards
            sign_tag = "plus" if sign > 0 else "minus"
            shards[sid].append(
                {
                    "displacement_id": f"m{mode_idx:03d}_{sign_tag}",
                    "seq_id": seq_id,
                    "mode_index": mode_idx,
                    "sign": sign,
                    "shard_id": sid,
                }
            )
            seq_id += 1
    return shards


def build_gvpt2_plan(
    *,
    xyz_path: Path,
    output_dir: Path,
    n_shards: int = DEFAULT_N_SHARDS,
    step_size: float = 0.01,
    normal_modes_json: Path | None = None,
    write_xyz_files: bool = True,
) -> dict[str, Any]:
    """Generate equilibrium displacement plan partitioned across K=6 shards."""
    resolved_xyz = xyz_path.resolve()
    symbols, coords, comment = parse_xyz_single(resolved_xyz)
    n_atoms = len(symbols)
    out_dir = output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    coord_basis = "cartesian"
    harmonic_cm1: list[float] | None = None
    eq_hessian_q: list[list[float]] | None = None
    dx_bohr: list[list[float]] | None = None
    disp_vectors: list[np.ndarray] = []

    if normal_modes_json is not None:
        nm_path = normal_modes_json.resolve()
        nm_data = json.loads(nm_path.read_text(encoding="utf-8"))
        harmonic_cm1 = [float(w) for w in nm_data["harmonic_cm1"]]
        raw_vecs = np.asarray(nm_data["displacement_vectors"], dtype=np.float64)
        if raw_vecs.shape != (len(harmonic_cm1), n_atoms, 3):
            raise ValueError(
                f"Expected displacement_vectors shape {(len(harmonic_cm1), n_atoms, 3)}, got {raw_vecs.shape}."
            )
        disp_vectors = [raw_vecs[i] for i in range(len(harmonic_cm1))]
        if "eq_hessian_q" in nm_data:
            eq_hessian_q = [[float(v) for v in row] for row in nm_data["eq_hessian_q"]]
        if "dx_bohr" in nm_data and nm_data["dx_bohr"] is not None:
            dx_arr = np.asarray(nm_data["dx_bohr"], dtype=np.float64)
            if dx_arr.shape != (len(harmonic_cm1), 3 * n_atoms):
                raise ValueError(
                    f"Expected dx_bohr shape {(len(harmonic_cm1), 3 * n_atoms)}, got {dx_arr.shape}."
                )
            dx_bohr = dx_arr.tolist()
        coord_basis = "normal_mode"
    else:
        for atom_idx in range(n_atoms):
            for axis_idx in range(3):
                vec = np.zeros((n_atoms, 3), dtype=np.float64)
                vec[atom_idx, axis_idx] = 1.0
                disp_vectors.append(vec)

    n_modes = len(disp_vectors)
    shard_map = partition_displacements_deterministic(n_modes, n_shards=n_shards)

    displaced_dir = out_dir / "displaced_xyz"
    if write_xyz_files:
        displaced_dir.mkdir(parents=True, exist_ok=True)

    shards_payload: dict[str, list[dict[str, Any]]] = {}
    for sid in range(n_shards):
        enriched: list[dict[str, Any]] = []
        for entry in shard_map[sid]:
            m_idx = int(entry["mode_index"])
            sign = int(entry["sign"])
            disp_coords = coords + float(sign) * float(step_size) * disp_vectors[m_idx]
            item = dict(entry)
            item["step_size"] = float(step_size)
            if write_xyz_files:
                xyz_name = f"shard_{sid}_{entry['displacement_id']}.xyz"
                xyz_out = displaced_dir / xyz_name
                xyz_out.write_text(
                    format_xyz(
                        symbols,
                        disp_coords,
                        f"GVPT2 shard={sid} mode={m_idx} sign={sign:+d} step={step_size}",
                    ),
                    encoding="utf-8",
                )
                item["xyz_relpath"] = f"displaced_xyz/{xyz_name}"
                item["xyz_sha256"] = sha256_file(xyz_out)
            enriched.append(item)
        shards_payload[str(sid)] = enriched

    plan = {
        "schema": "cochem.gvpt2-shard-plan/1",
        "collaborator_institution": "Tennessee Tech University",
        "course_id": "CHEM312",
        "created_at_utc": _utc_now(),
        "coord_basis": coord_basis,
        "equilibrium_xyz": str(resolved_xyz),
        "equilibrium_xyz_sha256": sha256_file(resolved_xyz),
        "equilibrium_comment": comment,
        "symbols": symbols,
        "n_atoms": n_atoms,
        "n_modes": n_modes,
        "total_displacements": 2 * n_modes,
        "n_shards": int(n_shards),
        "step_size": float(step_size),
        "harmonic_cm1": harmonic_cm1,
        "eq_hessian_q": eq_hessian_q,
        "dx_bohr": dx_bohr,
        "shards": shards_payload,
    }
    plan_path = out_dir / "gvpt2_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return plan


def compute_gvpt2_from_reduced_hessians(
    harmonic_cm1: Sequence[float],
    eq_hessian_q: np.ndarray,
    displaced_hessians_q: Mapping[tuple[int, int], np.ndarray],
    step_q: float,
    *,
    fermi_delta_cm1: float = 200.0,
    fermi_martin_cm1: float = 1.0,
) -> dict[str, Any]:
    """Compute cubic phi_ijk, semi-diagonal quartic phi_iikk, Barone x_ij, and GVPT2 fundamentals.

    Inputs are expressed in dimensionless normal coordinates q_k (so H^(0)_ii = omega_i in cm^-1,
    dH_ij/dq_k = phi_ijk in cm^-1, d^2H_ii/dq_k^2 = phi_iikk in cm^-1).
    """
    omega = np.asarray(harmonic_cm1, dtype=np.float64)
    n_modes = int(omega.size)
    if np.any(omega <= 0.0):
        raise ValueError("All harmonic vibrational frequencies must be strictly positive for GVPT2.")
    h0 = np.asarray(eq_hessian_q, dtype=np.float64)
    if h0.shape != (n_modes, n_modes):
        raise ValueError(f"Expected equilibrium Hessian shape {(n_modes, n_modes)}, got {h0.shape}.")
    dq = float(step_q)
    if dq <= 0.0:
        raise ValueError(f"step_q must be > 0, got {dq}.")

    phi3_raw = np.zeros((n_modes, n_modes, n_modes), dtype=np.float64)
    phi4_semi = np.zeros((n_modes, n_modes), dtype=np.float64)

    for k in range(n_modes):
        if (k, +1) not in displaced_hessians_q or (k, -1) not in displaced_hessians_q:
            raise KeyError(f"Missing +/- displaced Hessians for normal mode {k}.")
        hp = np.asarray(displaced_hessians_q[(k, +1)], dtype=np.float64)
        hm = np.asarray(displaced_hessians_q[(k, -1)], dtype=np.float64)
        if hp.shape != (n_modes, n_modes) or hm.shape != (n_modes, n_modes):
            raise ValueError(f"Displaced Hessian for mode {k} has mismatched shape.")
        phi3_raw[:, :, k] = (hp - hm) / (2.0 * dq)
        phi4_semi[:, k] = (np.diag(hp) - 2.0 * np.diag(h0) + np.diag(hm)) / (dq * dq)

    # Symmetrize phi_ijk over all 6 index permutations for numerical stability
    phi3 = (
        phi3_raw
        + np.transpose(phi3_raw, (0, 2, 1))
        + np.transpose(phi3_raw, (1, 0, 2))
        + np.transpose(phi3_raw, (1, 2, 0))
        + np.transpose(phi3_raw, (2, 0, 1))
        + np.transpose(phi3_raw, (2, 1, 0))
    ) / 6.0
    # Symmetrize semi-diagonal quartic phi_iikk
    phi4 = 0.5 * (phi4_semi + phi4_semi.T)

    x_mat = np.zeros((n_modes, n_modes), dtype=np.float64)
    fermi_resonances: list[dict[str, Any]] = []

    # Diagonal anharmonicity x_ii (Barone 2005 Eq. 12)
    for i in range(n_modes):
        wi = float(omega[i])
        term = phi4[i, i] / 16.0
        for k in range(n_modes):
            wk = float(omega[k])
            c_iik = float(phi3[i, i, k])
            if abs(c_iik) < 1e-12:
                continue
            delta_f1 = abs(2.0 * wi - wk)
            # Martin Type-I variational test: K = phi_iik^4 / (256 * |2*wi - wk|^3)
            is_fermi_1 = False
            if k != i and delta_f1 < fermi_delta_cm1:
                martin_k = (c_iik ** 4) / (256.0 * max(delta_f1, 1e-9) ** 3)
                if martin_k > fermi_martin_cm1:
                    is_fermi_1 = True
                    fermi_resonances.append(
                        {
                            "type": "Fermi_I",
                            "fundamental_mode": k,
                            "overtone_mode": i,
                            "omega_fundamental_cm1": wk,
                            "two_omega_overtone_cm1": 2.0 * wi,
                            "detuning_cm1": wk - 2.0 * wi,
                            "phi_iik_cm1": c_iik,
                            "coupling_W_cm1": abs(c_iik) / (4.0 * math.sqrt(2.0)),
                            "martin_test_cm1": martin_k,
                        }
                    )
            if is_fermi_1:
                # GVPT2 deperturbed non-resonant remainder: remove singular 1/(2*wi - wk) pole
                # 8*wi^2 - 3*wk^2 / (wk*(4*wi^2 - wk^2)) = 2/wk + 1/(2*(2*wi + wk)) + 1/(2*(2*wi - wk))
                non_res = (2.0 / wk) + 0.5 / (2.0 * wi + wk)
                term -= (c_iik * c_iik / 16.0) * non_res
            else:
                denom = wk * (4.0 * wi * wi - wk * wk)
                term -= (c_iik * c_iik / 16.0) * (8.0 * wi * wi - 3.0 * wk * wk) / denom
        x_mat[i, i] = term

    # Off-diagonal anharmonicity x_ij (i < j)
    for i in range(n_modes):
        wi = float(omega[i])
        for j in range(i + 1, n_modes):
            wj = float(omega[j])
            val = 0.25 * float(phi4[i, j])
            for k in range(n_modes):
                wk = float(omega[k])
                val -= 0.25 * float(phi3[i, i, k]) * float(phi3[j, j, k]) / wk
                c_ijk = float(phi3[i, j, k])
                if abs(c_ijk) < 1e-12:
                    continue
                # Exact partial-fraction identity (Barone 2005 Eq. 13):
                # -0.5 * phi_ijk^2 * wk*(wk^2 - wi^2 - wj^2) / Delta_ijk
                # = (phi_ijk^2 / 8) * [ 1/(wi+wj+wk) - 1/(wi+wj-wk) + 1/(wi-wj+wk) + 1/(-wi+wj+wk) ]
                poles = (
                    (wi + wj + wk, +1.0, False, None),
                    (wi + wj - wk, -1.0, True, (k, i, j)),
                    (wi - wj + wk, +1.0, True, (j, i, k)),
                    (-wi + wj + wk, +1.0, True, (i, j, k)),
                )
                for denom_p, coeff_p, check_res, triad in poles:
                    if check_res and abs(denom_p) < fermi_delta_cm1 and triad is not None:
                        martin_k2 = (c_ijk ** 4) / (64.0 * max(abs(denom_p), 1e-9) ** 3)
                        if martin_k2 > fermi_martin_cm1:
                            if triad[0] == k:
                                fermi_resonances.append(
                                    {
                                        "type": "Fermi_II",
                                        "fundamental_mode": triad[0],
                                        "combination_modes": [triad[1], triad[2]],
                                        "detuning_cm1": float(omega[triad[0]] - omega[triad[1]] - omega[triad[2]]),
                                        "phi_ijk_cm1": c_ijk,
                                        "coupling_W_cm1": abs(c_ijk) / (2.0 * math.sqrt(2.0)),
                                        "martin_test_cm1": martin_k2,
                                    }
                                )
                            continue
                    if abs(denom_p) > 1e-12:
                        val += (c_ijk * c_ijk / 8.0) * (coeff_p / denom_p)
            x_mat[i, j] = val
            x_mat[j, i] = val

    # Fundamental anharmonic frequencies: nu_i = omega_i + 2*x_ii + 0.5*sum_{j!=i} x_ij
    fundamentals = np.empty(n_modes, dtype=np.float64)
    for i in range(n_modes):
        off_sum = float(np.sum(x_mat[i, :]) - x_mat[i, i])
        fundamentals[i] = float(omega[i]) + 2.0 * float(x_mat[i, i]) + 0.5 * off_sum

    zpve_harm = 0.5 * float(np.sum(omega))
    zpve_anharm = zpve_harm + 0.25 * float(np.sum(x_mat))

    return {
        "harmonic_cm1": [float(w) for w in omega],
        "anharmonic_fundamentals_cm1": [float(v) for v in fundamentals],
        "anharmonic_shifts_cm1": [float(v - w) for v, w in zip(fundamentals, omega)],
        "x_matrix_cm1": [[float(v) for v in row] for row in x_mat],
        "phi3_max_abs_cm1": float(np.max(np.abs(phi3))),
        "phi4_semi_diagonal_cm1": [[float(v) for v in row] for row in phi4],
        "zpve_harmonic_cm1": zpve_harm,
        "zpve_anharmonic_cm1": zpve_anharm,
        "fermi_resonances": fermi_resonances,
    }


def aggregate_shards(
    *,
    plan_path: Path,
    shards_dir: Path,
    output_dir: Path,
    fermi_delta_cm1: float = 200.0,
    fermi_martin_cm1: float = 1.0,
) -> dict[str, Any]:
    """Aggregate K=6 shard outputs into gvpt2_shard_manifest.json with strict PENDING guard."""
    resolved_plan = plan_path.resolve()
    plan = json.loads(resolved_plan.read_text(encoding="utf-8"))
    n_shards = int(plan["n_shards"])
    n_modes = int(plan["n_modes"])
    step_size = float(plan["step_size"])

    out_dir = output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    s_dir = shards_dir.resolve()

    completed_shards: list[int] = []
    missing_shards: list[int] = []
    shard_digests: dict[str, str] = {}
    displaced_hessians: dict[tuple[int, int], np.ndarray] = {}
    missing_displacements: list[str] = []

    for sid in range(n_shards):
        expected_entries = plan["shards"].get(str(sid), [])
        shard_file = s_dir / f"shard_{sid}.json"
        if not shard_file.is_file():
            missing_shards.append(sid)
            missing_displacements.extend(entry["displacement_id"] for entry in expected_entries)
            continue

        shard_digests[f"shard_{sid}.json"] = sha256_file(shard_file)
        shard_payload = json.loads(shard_file.read_text(encoding="utf-8"))
        results_by_id = shard_payload.get("displacements", {})
        shard_ok = True
        for entry in expected_entries:
            did = entry["displacement_id"]
            rec = results_by_id.get(did)
            if not isinstance(rec, Mapping) or "hessian" not in rec or rec["hessian"] is None:
                missing_displacements.append(did)
                shard_ok = False
                continue
            h_mat = np.asarray(rec["hessian"], dtype=np.float64)
            if not np.all(np.isfinite(h_mat)):
                missing_displacements.append(did)
                shard_ok = False
                continue
            displaced_hessians[(int(entry["mode_index"]), int(entry["sign"]))] = h_mat
        if shard_ok:
            completed_shards.append(sid)
        else:
            missing_shards.append(sid)

    is_complete = (len(missing_shards) == 0) and (len(missing_displacements) == 0)

    manifest: dict[str, Any] = {
        "schema": "cochem.gvpt2-shard-manifest/1",
        "collaborator_institution": "Tennessee Tech University",
        "course_id": "CHEM312",
        "created_at_utc": _utc_now(),
        "plan_path": str(resolved_plan),
        "plan_sha256": sha256_file(resolved_plan),
        "n_shards": n_shards,
        "n_modes": n_modes,
        "total_displacements": int(plan["total_displacements"]),
        "completed_shards": completed_shards,
        "missing_shards": missing_shards,
        "missing_displacements": missing_displacements,
        "shards_sha256": shard_digests,
        "complete": is_complete,
    }

    if not is_complete:
        manifest["status"] = "PENDING"
        manifest["gvpt2_results"] = {
            "status": "PENDING",
            "reason": f"Incomplete shards ({len(completed_shards)}/{n_shards} complete); refusing fabricated anharmonic values.",
            "anharmonic_fundamentals_cm1": "PENDING",
            "x_matrix_cm1": "PENDING",
            "zpve_anharmonic_cm1": "PENDING",
            "fermi_resonances": "PENDING",
        }
    else:
        harmonic_cm1 = plan.get("harmonic_cm1")
        eq_hess = plan.get("eq_hessian_q")
        if harmonic_cm1 is not None and eq_hess is not None:
            gvpt2_res = compute_gvpt2_from_reduced_hessians(
                harmonic_cm1,
                np.asarray(eq_hess, dtype=np.float64),
                displaced_hessians,
                step_q=step_size,
                fermi_delta_cm1=fermi_delta_cm1,
                fermi_martin_cm1=fermi_martin_cm1,
            )
            gvpt2_res["status"] = "COMPLETE"
            manifest["status"] = "COMPLETE"
            manifest["gvpt2_results"] = gvpt2_res
        else:
            # Cartesian finite-difference cubic tensor norms when normal-mode basis wasn't pre-supplied
            cubic_max_norm = 0.0
            for k in range(n_modes):
                diff = (displaced_hessians[(k, +1)] - displaced_hessians[(k, -1)]) / (2.0 * step_size)
                cubic_max_norm = max(cubic_max_norm, float(np.max(np.abs(diff))))
            manifest["status"] = "COMPLETE_CARTESIAN_RAW"
            manifest["gvpt2_results"] = {
                "status": "PENDING_NORMAL_MODE_PROJECTION",
                "cartesian_cubic_max_abs": cubic_max_norm,
                "anharmonic_fundamentals_cm1": "PENDING",
                "x_matrix_cm1": "PENDING",
                "zpve_anharmonic_cm1": "PENDING",
            }

    manifest_path = out_dir / "gvpt2_shard_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def run_pyscf_shard(
    *,
    plan_path: Path,
    shard_id: int,
    output_dir: Path,
    method: str = "B3LYP-D3BJ",
    basis: str = "def2-SVP",
    charge: int = 0,
    multiplicity: int = 1,
    solvation: str = "gas",
    solvent_name: str | None = None,
) -> Path:
    """Execute PySCF Cartesian Hessians for every displacement assigned to shard_id."""
    import sys

    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root / "student") not in sys.path:
        sys.path.insert(0, str(repo_root / "student"))
    import conformers  # noqa: E402
    from pyscf import gto, lib  # noqa: E402

    plan = json.loads(plan_path.resolve().read_text(encoding="utf-8"))
    key = str(int(shard_id))
    if key not in plan["shards"]:
        raise ValueError(f"Shard ID {shard_id} not in plan (valid: {sorted(plan['shards'])}).")

    method_spec, basis_label = conformers.normalize_method_and_basis(method, basis)
    lib.num_threads(2)

    out_dir = output_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_dir = plan_path.resolve().parent
    dx_bohr_raw = plan.get("dx_bohr")
    dx_bohr_mat = np.asarray(dx_bohr_raw, dtype=np.float64) if dx_bohr_raw is not None else None

    displacements_out: dict[str, Any] = {}
    for entry in plan["shards"][key]:
        did = entry["displacement_id"]
        xyz_file = plan_dir / entry["xyz_relpath"]
        symbols, coords, _ = parse_xyz_single(xyz_file)
        atoms = [(s, c.tolist()) for s, c in zip(symbols, coords)]
        mol = gto.M(atom=atoms, unit="Angstrom", basis=basis_label, charge=charge, spin=multiplicity - 1, verbose=2)
        mf = conformers._build_pyscf_mf(
            mol,
            method_spec,
            solvation=solvation,
            solvent_name=solvent_name if solvation != "gas" else None,
        )
        e_tot = float(mf.kernel())
        if not mf.converged:
            raise RuntimeError(f"PySCF SCF failed to converge for shard {shard_id} displacement {did}.")
        hess_raw = mf.Hessian().kernel()
        n_at = len(symbols)
        hess_2d = np.asarray(hess_raw, dtype=np.float64).transpose(0, 2, 1, 3).reshape(3 * n_at, 3 * n_at)
        if dx_bohr_mat is not None:
            hess_out = (dx_bohr_mat @ hess_2d @ dx_bohr_mat.T) * HARTREE_TO_CM1
            hess_basis = "reduced_normal_mode_cm1"
        else:
            hess_out = hess_2d
            hess_basis = "cartesian_hartree_bohr2"
        displacements_out[did] = {
            "mode_index": int(entry["mode_index"]),
            "sign": int(entry["sign"]),
            "energy_hartree": e_tot,
            "hessian_basis": hess_basis,
            "hessian_shape": [int(hess_out.shape[0]), int(hess_out.shape[1])],
            "hessian": hess_out.tolist(),
            "xyz_sha256": sha256_file(xyz_file),
        }

    shard_doc = {
        "schema": "cochem.gvpt2-shard-result/1",
        "collaborator_institution": "Tennessee Tech University",
        "shard_id": int(shard_id),
        "method": method_spec["label"],
        "basis": basis_label,
        "solvation": solvation,
        "solvent_name": solvent_name if solvation != "gas" else None,
        "completed_at_utc": _utc_now(),
        "displacements": displacements_out,
    }
    shard_out_path = out_dir / f"shard_{int(shard_id)}.json"
    shard_out_path.write_text(json.dumps(shard_doc, indent=2) + "\n", encoding="utf-8")
    return shard_out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Deterministic 6-shard Barone GVPT2 Hessian planner, shard runner, and aggregator (CHEM 312 M3)."
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan", help="Generate deterministic K=6 displaced-geometry shard plan.")
    p_plan.add_argument("--xyz", required=True, type=Path, help="Optimized equilibrium XYZ file.")
    p_plan.add_argument("--output-dir", required=True, type=Path, help="Directory for gvpt2_plan.json and displaced XYZs.")
    p_plan.add_argument("--n-shards", type=int, default=DEFAULT_N_SHARDS, help="Number of parallel shards (default: 6).")
    p_plan.add_argument("--step-size", type=float, default=0.01, help="Displacement step size (default: 0.01).")
    p_plan.add_argument("--normal-modes-json", type=Path, default=None, help="Optional harmonic normal-modes JSON.")

    p_run = sub.add_parser("run-shard", help="Execute PySCF Hessians for one shard_id in 0..5.")
    p_run.add_argument("--plan", required=True, type=Path, help="Path to gvpt2_plan.json.")
    p_run.add_argument("--shard-id", required=True, type=int, help="Shard index (0..5).")
    p_run.add_argument("--output-dir", required=True, type=Path, help="Directory to write shard_<id>.json.")
    p_run.add_argument("--method", default="B3LYP-D3BJ")
    p_run.add_argument("--basis", default="def2-SVP")
    p_run.add_argument("--charge", type=int, default=0)
    p_run.add_argument("--multiplicity", type=int, default=1)
    p_run.add_argument("--solvation", default="gas")
    p_run.add_argument("--solvent-name", default=None)

    p_agg = sub.add_parser("aggregate", help="Aggregate all 6 shards into gvpt2_shard_manifest.json.")
    p_agg.add_argument("--plan", required=True, type=Path, help="Path to gvpt2_plan.json.")
    p_agg.add_argument("--shards-dir", required=True, type=Path, help="Directory containing shard_0.json..shard_5.json.")
    p_agg.add_argument("--output-dir", required=True, type=Path, help="Directory for gvpt2_shard_manifest.json.")
    p_agg.add_argument("--fermi-delta-cm1", type=float, default=200.0)
    p_agg.add_argument("--fermi-martin-cm1", type=float, default=1.0)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "plan":
        res = build_gvpt2_plan(
            xyz_path=args.xyz,
            output_dir=args.output_dir,
            n_shards=args.n_shards,
            step_size=args.step_size,
            normal_modes_json=args.normal_modes_json,
        )
        print(json.dumps({k: v for k, v in res.items() if k != "shards"}, indent=2))
        return 0
    if args.command == "run-shard":
        out = run_pyscf_shard(
            plan_path=args.plan,
            shard_id=args.shard_id,
            output_dir=args.output_dir,
            method=args.method,
            basis=args.basis,
            charge=args.charge,
            multiplicity=args.multiplicity,
            solvation=args.solvation,
            solvent_name=args.solvent_name,
        )
        print(json.dumps({"shard_id": args.shard_id, "output": str(out), "sha256": sha256_file(out)}, indent=2))
        return 0
    if args.command == "aggregate":
        res = aggregate_shards(
            plan_path=args.plan,
            shards_dir=args.shards_dir,
            output_dir=args.output_dir,
            fermi_delta_cm1=args.fermi_delta_cm1,
            fermi_martin_cm1=args.fermi_martin_cm1,
        )
        print(json.dumps(res, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
