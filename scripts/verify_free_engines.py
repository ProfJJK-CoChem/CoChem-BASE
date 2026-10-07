#!/usr/bin/env python3
"""Run bounded physical CPU calculations using the isolated free engine silos.

This validates installation and selected calculations, not the complete method
matrix, conformer completeness, spectroscopic accuracy, or GPU execution.
Evidence and engine working files are written outside the source checkout.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time

from install_free_engines import external_path


WATER = "3\nWater in angstrom\nO 0.000000 0.000000 0.000000\nH 0.000000 -0.757000 0.587000\nH 0.000000 0.757000 0.587000\n"
ETHANOL = "9\nEthanol in angstrom\nC -0.748 0.015 0.024\nC 0.748 -0.015 -0.024\nO 1.250 1.290 0.025\nH -1.129 -0.526 0.899\nH -1.166 -0.494 -0.851\nH -1.129 1.055 0.024\nH 1.128 -0.556 -0.899\nH 1.128 -0.556 0.851\nH 2.205 1.215 0.025\n"


def execute(argv: list[str], directory: Path, log: str, env: dict[str, str], timeout: int = 300) -> str:
    log_path = directory / log
    with log_path.open("w") as output:
        process = subprocess.Popen(argv, cwd=directory, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=os.name != "nt",
                                   creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
                # The launcher may have exited while descendants remain alive.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait(timeout=15)
            raise RuntimeError(f"Calculation exceeded {timeout}s; owned process tree stopped; partial log: {log_path}") from None
    content = log_path.read_text()
    if process.returncode:
        raise RuntimeError(f"{argv[0]} exited {process.returncode}; see {directory / log}")
    return content


def check_xtb(root: Path, directory: Path, env: dict[str, str]) -> dict:
    binary = root / "xtb/xtb-dist/bin/xtb"
    (directory / "water.xyz").write_text(WATER)
    results = {}
    for method, switches in (("GFN-FF", ["--gfnff", "--opt", "tight"]),
                              ("GFN2-xTB", ["--gfn", "2", "--ohess", "tight"])):
        work = directory / method
        work.mkdir()
        (work / "water.xyz").write_text(WATER)
        text = execute([str(binary), "water.xyz", *switches, "--chrg", "0", "--uhf", "0"], work, "calculation.log", env)
        energies = re.findall(r"TOTAL ENERGY\s+(-?\d+\.\d+)", text)
        if not energies or "GEOMETRY OPTIMIZATION CONVERGED" not in text:
            raise RuntimeError(f"Missing converged {method} energy in {work}")
        energy = float(energies[-1])
        if not math.isfinite(energy) or not (work / "xtbopt.xyz").is_file():
            raise RuntimeError(f"Invalid {method} calculation artifacts")
        result = {"energy_hartree": energy, "converged": True, "log": str(work / "calculation.log")}
        if method == "GFN2-xTB":
            if not (work / "hessian").is_file() or not (work / "vibspectrum").is_file():
                raise RuntimeError("GFN2-xTB did not produce its Hessian and spectrum")
            hessian_text = (work / "hessian").read_text()
            if not hessian_text.startswith("$hessian"):
                raise RuntimeError("Invalid xTB Hessian format")
            values = [float(value) for line in hessian_text.splitlines()[1:] if not line.startswith("$") for value in line.split()]
            if len(values) != 81 or not all(math.isfinite(value) for value in values):
                raise RuntimeError("Incomplete or non-finite water Hessian")
            if max(abs(values[9*i+j]-values[9*j+i]) for i in range(9) for j in range(9)) > 1e-8:
                raise RuntimeError("Water Hessian is not symmetric")
            result["hessian"] = str(work / "hessian")
            result["vibrational_spectrum"] = str(work / "vibspectrum")
        results[method] = result
    return results


def check_crest(root: Path, directory: Path, env: dict[str, str]) -> dict:
    (directory / "ethanol.xyz").write_text(ETHANOL)
    text = execute([str(root / "crest/crest/crest"), "ethanol.xyz", "--gfn2", "--quick", "--T", "1"], directory, "calculation.log", env, timeout=300)
    ensemble = directory / "crest_conformers.xyz"
    if not ensemble.is_file() or "CREST terminated normally" not in text:
        raise RuntimeError("CREST did not finish a conformer search and publish its ensemble")
    lines = ensemble.read_text().splitlines()
    count = 0
    energies = []
    offset = 0
    while offset < len(lines):
        atoms = int(lines[offset])
        if atoms != 9 or offset + atoms + 2 > len(lines):
            raise RuntimeError("CREST ensemble contains an invalid molecule")
        energies.append(float(lines[offset + 1].split()[0]))
        symbols = []
        for line in lines[offset + 2: offset + atoms + 2]:
            fields = line.split()
            if len(fields) != 4 or not all(math.isfinite(float(value)) for value in fields[1:]):
                raise RuntimeError("CREST coordinates are non-finite")
            symbols.append(fields[0])
        if sorted(symbols) != sorted(["C", "C", "O", *["H"]*6]):
            raise RuntimeError("CREST conformer composition differs from ethanol")
        offset += atoms + 2
        count += 1
    if not count or not all(math.isfinite(energy) for energy in energies):
        raise RuntimeError("CREST ensemble is empty or invalid")
    return {"conformers": count, "energies_hartree": energies,
            "ensemble": str(ensemble), "log": str(directory / "calculation.log")}


def check_gxtb(root: Path, directory: Path, env: dict[str, str]) -> dict:
    (directory / "water.xyz").write_text(WATER)
    text = execute([str(root / "gxtb/xtb-6.7.1/bin/xtb"), "water.xyz", "--gxtb", "--opt", "tight"], directory, "calculation.log", env)
    energies = re.findall(r"TOTAL ENERGY\s+(-?\d+\.\d+)", text)
    if not energies or "GEOMETRY OPTIMIZATION CONVERGED" not in text or "g-xTB" not in text:
        raise RuntimeError("g-xTB did not report its method and converged optimization")
    energy = float(energies[-1])
    if not math.isfinite(energy):
        raise RuntimeError("Non-finite g-xTB energy")
    return {"energy_hartree": energy, "converged": True, "log": str(directory / "calculation.log")}


def check_mopac(root: Path, directory: Path, env: dict[str, str]) -> dict:
    (directory / "water.mop").write_text("PM7 PRECISE XYZ GNORM=0.01\nWater PM7 geometry optimization\nFree CPU engine verification\nO 0.0 1 0.0 1 0.0 1\nH 0.0 1 -0.757 1 0.587 1\nH 0.0 1 0.757 1 0.587 1\n\n")
    execute([str(root / "mopac/mopac-23.2.1-linux/bin/mopac"), "water.mop"], directory, "calculation.log", env)
    text = (directory / "water.out").read_text()
    energies = re.findall(r"FINAL HEAT OF FORMATION\s*=\s*(-?\d+\.\d+)\s+KCAL/MOL", text)
    gradient_converged = "GRADIENTS WERE INITIALLY ACCEPTABLY SMALL" in text or bool(re.search(r"GRADIENT\s*=\s*[\d.]+ IS LESS THAN CUTOFF", text))
    if not energies or not gradient_converged or "JOB ENDED NORMALLY" not in text:
        raise RuntimeError("MOPAC did not report a converged PM7 calculation")
    energy = float(energies[-1])
    if not math.isfinite(energy):
        raise RuntimeError("Non-finite MOPAC heat of formation")
    return {"method": "PM7", "heat_of_formation_kcal_mol": energy, "converged": True, "output": str(directory / "water.out")}


PYSCF_PROBE = r'''
import json
import numpy as np
from pyscf import gto, scf, dft, lib
from dftd4.pyscf import energy as add_d4
lib.num_threads(1)
results = {}
for label, basis, xc in [('HF/STO-3G', 'sto-3g', None), ('PBE-D4/def2-SVP', 'def2-svp', 'pbe'), ('B3LYP-D4/def2-TZVP', 'def2-tzvp', 'b3lyp')]:
    mol = gto.M(atom='O 0 0 0; H 0 -.757 .587; H 0 .757 .587', basis=basis, unit='Angstrom', verbose=0, max_memory=512)
    if xc is None:
        mf = scf.RHF(mol)
    else:
        mf = dft.RKS(mol)
        mf.xc = xc
        mf.grids.level = 3
        mf = add_d4(mf)
    mf.conv_tol = 1e-10
    energy = mf.kernel()
    assert mf.converged and np.isfinite(energy) and -80 < energy < -70
    gradient = mf.nuc_grad_method().kernel()
    assert gradient.shape == (3, 3) and np.isfinite(gradient).all()
    assert np.linalg.norm(gradient.sum(axis=0)) < 1e-4
    if xc is None:
        assert abs(energy - (-74.963063129729)) < 1e-8
        hessian = mf.Hessian().kernel()
        assert hessian.shape == (3, 3, 3, 3) and np.isfinite(hessian).all()
        assert np.max(np.abs(hessian-hessian.transpose(1,0,3,2))) < 1e-8
    results[label] = {'energy_hartree': float(energy), 'converged': bool(mf.converged), 'gradient_norm_hartree_per_bohr': float(np.linalg.norm(gradient)), 'basis_functions': mol.nao_nr()}
    if xc:
        results[label]['dispersion_hartree'] = float(mf.scf_summary['dispersion'])
print('COCHEM_RESULT=' + json.dumps(results))
'''


OPENMM_PROBE = r'''
import json
import numpy as np
import openmm
from openmm import app, unit
topology = app.Topology()
chain = topology.addChain()
for _ in range(2):
    residue = topology.addResidue('HOH', chain)
    oxygen = topology.addAtom('O', app.element.oxygen, residue)
    for name in ('H1', 'H2'):
        hydrogen = topology.addAtom(name, app.element.hydrogen, residue)
        topology.addBond(oxygen, hydrogen)
forcefield = app.ForceField('tip3p.xml')
system = forcefield.createSystem(topology, nonbondedMethod=app.NoCutoff, constraints=app.HBonds)
integrator = openmm.VerletIntegrator(.0005*unit.picoseconds)
context = openmm.Context(system, integrator, openmm.Platform.getPlatformByName('Reference'))
positions = np.array([[0,0,0],[.09572,0,0],[-.023999,.092663,0],[.29,0,0],[.38572,0,0],[.266001,.092663,0]])
context.setPositions(positions*unit.nanometers)
before = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
openmm.LocalEnergyMinimizer.minimize(context, maxIterations=200)
after = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
assert np.isfinite([before, after]).all() and after <= before + 1e-7
context.setVelocitiesToTemperature(50*unit.kelvin, 2026)
integrator.step(20)
state = context.getState(getEnergy=True, getForces=True)
energy = state.getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
forces = state.getForces(asNumpy=True).value_in_unit(unit.kilojoule_per_mole/unit.nanometers)
assert np.isfinite(energy) and np.isfinite(forces).all()
assert np.linalg.norm(forces.sum(axis=0)) < 1e-6
print('COCHEM_RESULT=' + json.dumps({'model':'TIP3P water dimer','platform':'Reference','initial_energy_kj_mol':before,'minimized_energy_kj_mol':after,'final_energy_kj_mol':energy,'steps':20,'version':openmm.__version__}))
'''


def check_python(root: Path, name: str, directory: Path, env: dict[str, str]) -> dict:
    interpreter = root / name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    probe = PYSCF_PROBE if name == "pyscf" else OPENMM_PROBE
    (directory / "calculation.py").write_text(probe)
    text = execute([str(interpreter), "-I", str(directory / "calculation.py")], directory, "calculation.log", env)
    results = [line.removeprefix("COCHEM_RESULT=") for line in text.splitlines() if line.startswith("COCHEM_RESULT=")]
    if len(results) != 1:
        raise RuntimeError(f"Missing unique {name} calculation result")
    return {"calculations": json.loads(results[0]), "log": str(directory / "calculation.log")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=external_path)
    parser.add_argument("--engines", nargs="+", choices=["xtb", "crest", "gxtb", "mopac", "pyscf", "openmm"], default=["xtb", "crest", "gxtb", "mopac", "pyscf", "openmm"])
    parser.add_argument("--output", required=True, type=external_path)
    arguments = parser.parse_args()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="science-", dir=arguments.output.parent))
    env = {key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "VIRTUAL_ENV"}}
    env.update(OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", OMP_STACKSIZE="512M",
               XTBPATH=str(arguments.root / "xtb/xtb-dist/share/xtb"))
    env["PATH"] = str(arguments.root / "xtb/xtb-dist/bin") + os.pathsep + env.get("PATH", "")
    report = {"root": str(arguments.root), "work_directory": str(work), "threads": 1, "engines": {}}
    failed = False
    for name in arguments.engines:
        directory = work / name
        directory.mkdir()
        started = time.monotonic()
        try:
            if name == "xtb":
                result = check_xtb(arguments.root, directory, env)
            elif name == "crest":
                result = check_crest(arguments.root, directory, env)
            elif name == "gxtb":
                result = check_gxtb(arguments.root, directory, env)
            elif name == "mopac":
                result = check_mopac(arguments.root, directory, env)
            else:
                result = check_python(arguments.root, name, directory, env)
            report["engines"][name] = {"status": "passed", "elapsed_seconds": time.monotonic() - started, **result}
        except Exception as error:
            failed = True
            report["engines"][name] = {"status": "failed", "elapsed_seconds": time.monotonic() - started, "error": str(error)}
        arguments.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{name}: {report['engines'][name]['status']}", flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
