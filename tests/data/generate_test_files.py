import numpy as np
import math
from ase import Atoms
from ase.calculators.emt import EMT
from ase.optimize import BFGS
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase.md.verlet import VelocityVerlet
from ase.vibrations import Vibrations
from ase import units
import os

data_dir = "D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/data"
os.makedirs(data_dir, exist_ok=True)

# 1. H2CO equilibrium
# Formaldehyde (H2CO): C=O and two C-H bonds
h2co = Atoms('CH2O', positions=[[0,0,0],[0,1.2,0],[0.9,-0.5,0],[-0.9,-0.5,0]])
h2co.calc = EMT()
opt = BFGS(h2co)
opt.run(fmax=0.01)
h2co_eq = h2co.positions.copy()

with open(f"{data_dir}/h2co_eq.xyz", "w") as f:
    f.write("4\nFormaldehyde equilibrium (EMT)\n")
    for i, sym in enumerate(["C", "O", "H", "H"]):
        f.write(f"{sym} {h2co_eq[i,0]:.4f} {h2co_eq[i,1]:.4f} {h2co_eq[i,2]:.4f}\n")

# 2. H2CO trajectory (frames 1-11)
positions = []
velocities = []
forces = []
energies = []
uncertainties = []

# Thermalize
MaxwellBoltzmannDistribution(h2co, temperature_K=300)
dyn = VelocityVerlet(h2co, 1.0 * units.fs)

for frame_idx in range(1, 11):
    dyn.run(10)
    pos = h2co.get_positions()
    vel = h2co.get_velocities()
    frc = h2co.get_forces()
    energy = h2co.get_potential_energy() * 0.036749322 # eV to Hartree
    uncertainty = 0.25 + 0.02 * (frame_idx % 5)
    
    positions.append(pos)
    velocities.append(vel)
    forces.append(frc)
    energies.append(energy)
    uncertainties.append(uncertainty)

# Frame 11 (OOD - stretched C-O bond)
h2co_stretched = h2co.copy()
pos = h2co_stretched.get_positions()
pos[1, 1] += 1.5 # Stretch O atom away
h2co_stretched.set_positions(pos)
h2co_stretched.calc = EMT()

positions.append(h2co_stretched.get_positions())
velocities.append(np.zeros((4, 3)))
forces.append(h2co_stretched.get_forces())
energies.append(h2co_stretched.get_potential_energy() * 0.036749322)
uncertainties.append(1.875)

np.savez(f"{data_dir}/h2co_trajectory.npz", 
         positions=np.array(positions),
         velocities=np.array(velocities),
         forces=np.array(forces),
         energies=np.array(energies),
         uncertainties=np.array(uncertainties))

# Calibration data
cal_energy_true = []
cal_energy_pred = []
cal_energy_sigma = []
cal_forces_true = []
cal_forces_pred = []
cal_forces_sigma = []

dyn = VelocityVerlet(h2co, 1.0 * units.fs)
for step in range(12):
    dyn.run(5)
    f_t = h2co.get_forces()
    f_p = f_t + np.random.normal(0, 0.05, f_t.shape)
    f_s = np.full((4, 3), 0.015, dtype=np.float64)
    e_t = h2co.get_potential_energy() * 0.036749322
    
    cal_energy_true.append(e_t)
    cal_energy_pred.append(e_t + np.random.normal(0, 0.01))
    cal_energy_sigma.append(0.002)
    cal_forces_true.append(f_t)
    cal_forces_pred.append(f_p)
    cal_forces_sigma.append(f_s)

np.savez(f"{data_dir}/h2co_cal_data.npz",
         energy_true=np.array(cal_energy_true),
         energy_pred=np.array(cal_energy_pred),
         energy_sigma=np.array(cal_energy_sigma),
         forces_true=np.array(cal_forces_true),
         forces_pred=np.array(cal_forces_pred),
         forces_sigma=np.array(cal_forces_sigma))

# 3. Water Dimer
dimer = Atoms('H2OH2O', positions=[
    [-1.47, 0, 0.06], [-1.82, 0.77, -0.40], [-0.53, 0, -0.13],
    [1.43, 0, -0.06], [1.78, 0.77, 0.40], [1.78, -0.77, 0.40]
])
dimer.calc = EMT()
opt = BFGS(dimer)
opt.run(fmax=0.01)
with open(f"{data_dir}/water_dimer.xyz", "w") as f:
    f.write("6\nWater Dimer\n")
    for sym, pos in zip(dimer.symbols, dimer.positions):
        f.write(f"{sym} {pos[0]:.4f} {pos[1]:.4f} {pos[2]:.4f}\n")

# 4. Water equilibrium and hessian
water = Atoms('H2O', positions=[[0,0,0],[0.76,0.59,0],[-0.76,0.59,0]])
water.calc = EMT()
opt = BFGS(water)
opt.run(fmax=0.001)

with open(f"{data_dir}/water_eq.xyz", "w") as f:
    f.write("3\nWater equilibrium (EMT)\n")
    for sym, pos in zip(water.symbols, water.positions):
        f.write(f"{sym} {pos[0]:.4f} {pos[1]:.4f} {pos[2]:.4f}\n")

vib = Vibrations(water, name=f"{data_dir}/vib")
vib.run()
hess = vib.get_vibrations().get_hessian_2d()
np.save(f"{data_dir}/water_hessian.npy", hess)
vib.clean()

print("Generated physical files!")
