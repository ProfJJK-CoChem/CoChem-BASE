"""Finite, neutral closed-shell teaching route, with native outputs at each stage."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
import urllib.request

from handoff import frames, read_input, seal

ROOT = Path(__file__).resolve().parents[1]
MODEL_URL = ("https://raw.githubusercontent.com/ACEsuit/mace-off/"
             "91a78c5a9c300d1104700d9352c8bfe449227737/mace_off24/MACE-OFF24_medium.model")
MODEL_SHA = "e5ccf5837f685899811a68754e7c994393bfd1a81720393b03c643b46c70bc69"


def save(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def refine(frame, destination):
    import numpy as np
    from pyscf import gto, lib, scf
    from pyscf.geomopt import geometric_solver

    lib.num_threads(1)
    mol = gto.M(atom=list(zip(frame["symbols"], frame["coords"])), unit="Angstrom",
                basis="sto-3g", spin=0, charge=0, verbose=4, output=str(destination / "pyscf.log"))
    mf = scf.RHF(mol)
    mf.conv_tol = 1e-10
    converged, optimized = geometric_solver.kernel(mf, maxsteps=60, assert_convergence=True)
    if not converged:
        raise RuntimeError("geomeTRIC geometry optimization did not converge")
    final = scf.RHF(optimized)
    final.conv_tol = 1e-10
    energy = final.kernel()
    if not final.converged or not math.isfinite(energy):
        raise RuntimeError("Final RHF calculation did not converge to a finite energy")
    gradient = final.nuc_grad_method().kernel()
    coords = optimized.atom_coords(unit="Angstrom")
    if gradient.shape != coords.shape or not np.isfinite(gradient).all() or not np.isfinite(coords).all():
        raise ValueError("Invalid final gradient or geometry")
    symbols = frame["symbols"]
    lines = [str(len(symbols)), f"{energy:.14f} RHF/STO-3G hartree; coordinates in angstrom"]
    lines.extend(f"{s} {x:.12f} {y:.12f} {z:.12f}" for s, (x, y, z) in zip(symbols, coords))
    (destination / "refined.xyz").write_text("\n".join(lines) + "\n", encoding="ascii")
    save(destination / "pyscf.json", {"energy_hartree": energy, "gradient_hartree_per_bohr": gradient.tolist(),
         "optimizer_converged": True, "scf_converged": True, "method": "RHF", "basis": "STO-3G",
         "hessian_calculated": False})


def input_file(filename):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}\.xyz", filename):
        raise ValueError("Select an XYZ filename from student/inputs")
    source = ROOT / "student" / "inputs" / filename
    if source.is_symlink() or source.resolve().parent != ROOT / "student" / "inputs":
        raise ValueError("XYZ must be an ordinary file in student/inputs")
    return source


def calculate(filename, work, out):
    import importlib.metadata as md

    source = input_file(filename)
    original = read_input(source)
    payload = work / "bundle"
    payload.mkdir(parents=True)
    conformers = payload / "isomers"
    conformers.mkdir()
    shutil.copyfile(source, payload / "input.xyz")
    native = work / "native"
    native.mkdir()
    shutil.copyfile(source, native / "input.xyz")
    sys.path.insert(0, str(ROOT / "scripts"))
    from verify_free_engines import execute

    engine_root = Path(os.environ["COCHEM_FREE_ROOT"])
    shutil.copyfile(engine_root / "engines.json", payload / "engines.json")
    env = dict(os.environ, XTBPATH=str(engine_root / "xtb/xtb-dist/share/xtb"))
    env["PATH"] = str(engine_root / "xtb/xtb-dist/bin") + os.pathsep + env["PATH"]
    argv = [str(engine_root / "crest/crest/crest"), "input.xyz", "--gfn2", "--quick", "--T", "1"]
    log = execute(argv, native, "crest.log", env, timeout=600)
    if "CREST terminated normally" not in log:
        raise RuntimeError("Native CREST normal termination missing")
    for name in ("crest.log", "crest_conformers.xyz"):
        shutil.copyfile(native / name, payload / name)
    ensemble = frames((payload / "crest_conformers.xyz").read_text(), energy=True)
    if len(ensemble) > 32:
        raise ValueError("Ensemble exceeds the 32-conformer CPU teaching budget")
    model = work / "MACE-OFF24_medium.model"
    with urllib.request.urlopen(MODEL_URL, timeout=90) as src, model.open("xb") as dst:
        shutil.copyfileobj(src, dst)
    with model.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != MODEL_SHA:
            raise ValueError("MACE checkpoint SHA-256 mismatch")
    evaluate = runpy.run_path(str(ROOT / "src/cochem_base/core_engine/mlff_worker.py"))["evaluate"]
    results = []
    for index, frame in enumerate(ensemble, start=1):
        if frame["symbols"] != original["symbols"]:
            raise ValueError("CREST changed the atom sequence")
        relative = f"isomers/crest-{index:03}.xyz"
        (payload / relative).write_text(frame["text"], encoding="ascii")
        calculation = evaluate({"elements": frame["symbols"], "coordinates_angstrom": frame["coords"],
                                "cores": 1, "checkpoint": str(model), "checkpoint_sha256": MODEL_SHA})
        if calculation["status"] != "SUCCESS":
            raise RuntimeError(f"MACE evaluation {index}: {calculation['status']}")
        results.append({"xyz": relative, "crest_energy_hartree": frame["energy"], "mace": calculation})
    winner = min(range(len(results)), key=lambda i: results[i]["mace"]["energy_hartree"])
    save(payload / "ranking.json", {"model": "MACE-OFF24-medium", "model_sha256": MODEL_SHA,
         "selection": "lowest MACE single-point energy; first CREST index breaks exact ties",
         "selected": results[winner]["xyz"], "candidates": results})
    refine(ensemble[winner], payload)
    receipt = {"input_name": filename, "charge": 0, "multiplicity": 1, "length_unit": "angstrom",
               "crest_options": argv[1:], "model_url": MODEL_URL, "selected": results[winner]["xyz"],
               "candidate_count": len(results), "refined_xyz": "refined.xyz",
               "repository": os.environ["GITHUB_REPOSITORY"], "commit": os.environ["GITHUB_SHA"],
               "run_id": os.environ["GITHUB_RUN_ID"], "attempt": os.environ["GITHUB_RUN_ATTEMPT"],
               "packages": {p: md.version(p) for p in ("torch", "mace-torch", "ase", "pyscf", "geometric")}}
    seal(payload, out, receipt)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filename")
    parser.add_argument("work", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    calculate(args.filename, args.work, args.output)
