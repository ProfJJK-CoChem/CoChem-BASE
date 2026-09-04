import numpy as np
import torch
import math
import os

# 1. H2CO equilibrium
h2co_eq = np.array([
    [0.0000, 0.0000, -0.5312],   # C
    [0.0000, 0.0000,  0.6788],   # O
    [0.0000, 0.9382, -1.1078],   # H1
    [0.0000, -0.9382, -1.1078],  # H2
])
with open("D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/data/h2co_eq.xyz", "w") as f:
    f.write("4\nFormaldehyde equilibrium\n")
    f.write(f"C {h2co_eq[0,0]:.4f} {h2co_eq[0,1]:.4f} {h2co_eq[0,2]:.4f}\n")
    f.write(f"O {h2co_eq[1,0]:.4f} {h2co_eq[1,1]:.4f} {h2co_eq[1,2]:.4f}\n")
    f.write(f"H {h2co_eq[2,0]:.4f} {h2co_eq[2,1]:.4f} {h2co_eq[2,2]:.4f}\n")
    f.write(f"H {h2co_eq[3,0]:.4f} {h2co_eq[3,1]:.4f} {h2co_eq[3,2]:.4f}\n")

# 2. H2CO trajectory (frames 1-11)
positions = []
velocities = []
forces = []
energies = []
uncertainties = []
atomic_numbers = [6, 8, 1, 1]

for frame_idx in range(1, 11):
    wiggle = 0.005 * math.sin(frame_idx * 0.5)
    pos = h2co_eq.copy()
    pos[0, 2] += wiggle
    vel = np.full((4, 3), 0.001 * frame_idx, dtype=np.float64)
    frc = np.full((4, 3), 0.002, dtype=np.float64)
    energy = -114.520 + 0.0005 * frame_idx
    uncertainty = 0.25 + 0.02 * (frame_idx % 5)
    positions.append(pos)
    velocities.append(vel)
    forces.append(frc)
    energies.append(energy)
    uncertainties.append(uncertainty)

# Frame 11 (OOD)
h2co_stretched = h2co_eq.copy()
h2co_stretched[1, 2] = 2.1188 # C-O distance = 2.6500 A
positions.append(h2co_stretched)
velocities.append(np.zeros((4, 3), dtype=np.float64))
forces.append(np.full((4, 3), 0.25, dtype=np.float64))
energies.append(-114.210)
uncertainties.append(1.875)

np.savez("D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/data/h2co_trajectory.npz", 
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

for step in range(12):
    forces_t = np.array([
        [0.01 * (step % 3), -0.02 * (step % 2), 0.005],
        [-0.01 * (step % 3), 0.02 * (step % 2), -0.005],
        [0.002, 0.001, -0.002],
        [-0.002, -0.001, 0.002],
    ], dtype=np.float64)
    forces_p = forces_t + 0.003 * (0.5 - (step % 4) * 0.25)
    forces_s = np.full((4, 3), 0.015, dtype=np.float64)
    
    cal_energy_true.append(-114.500 + 0.001 * step)
    cal_energy_pred.append(-114.500 + 0.0012 * step)
    cal_energy_sigma.append(0.002)
    cal_forces_true.append(forces_t)
    cal_forces_pred.append(forces_p)
    cal_forces_sigma.append(forces_s)

np.savez("D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/data/h2co_cal_data.npz",
         energy_true=np.array(cal_energy_true),
         energy_pred=np.array(cal_energy_pred),
         energy_sigma=np.array(cal_energy_sigma),
         forces_true=np.array(cal_forces_true),
         forces_pred=np.array(cal_forces_pred),
         forces_sigma=np.array(cal_forces_sigma))

# 3. Water Dimer
WATER_DIMER_XYZ = (
    "O -1.47400000  0.00000000  0.06300000\n"
    "H -1.82100000  0.77200000 -0.40400000\n"
    "H -0.52800000  0.00000000 -0.12600000\n"
    "O  1.42800000  0.00000000 -0.06300000\n"
    "H  1.78200000  0.77200000  0.40400000\n"
    "H  1.78200000 -0.77200000  0.40400000\n"
)
with open("D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/data/water_dimer.xyz", "w") as f:
    f.write(WATER_DIMER_XYZ)

# 4. Water equilibrium and hessian
water_eq = np.array([
    [0.0000, 0.0000, 0.1173],
    [0.0000, 0.7572, -0.4692],
    [0.0000, -0.7572, -0.4692],
])
with open("D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/data/water_eq.xyz", "w") as f:
    f.write("3\nWater equilibrium\n")
    f.write(f"O {water_eq[0,0]:.4f} {water_eq[0,1]:.4f} {water_eq[0,2]:.4f}\n")
    f.write(f"H {water_eq[1,0]:.4f} {water_eq[1,1]:.4f} {water_eq[1,2]:.4f}\n")
    f.write(f"H {water_eq[2,0]:.4f} {water_eq[2,1]:.4f} {water_eq[2,2]:.4f}\n")

k_stretch = 0.580   # ~8.4 N/cm in Hartree/Bohr^2
k_bend = 0.075      # ~1.1 N/cm in Hartree/Bohr^2
hess = [
    [0.02, 0.00, 0.00, -0.01, 0.00, 0.00, -0.01, 0.00, 0.00],
    [0.00, k_stretch, 0.00, 0.00, -0.5*k_stretch, 0.00, 0.00, -0.5*k_stretch, 0.00],
    [0.00, 0.00, k_bend, 0.00, 0.00, -0.5*k_bend, 0.00, 0.00, -0.5*k_bend],
    [-0.01, 0.00, 0.00, 0.01, 0.00, 0.00, 0.00, 0.00, 0.00],
    [0.00, -0.5*k_stretch, 0.00, 0.00, 0.5*k_stretch, 0.00, 0.00, 0.00, 0.00],
    [0.00, 0.00, -0.5*k_bend, 0.00, 0.00, 0.5*k_bend, 0.00, 0.00, 0.00],
    [-0.01, 0.00, 0.00, 0.00, 0.00, 0.00, 0.01, 0.00, 0.00],
    [0.00, -0.5*k_stretch, 0.00, 0.00, 0.00, 0.00, 0.00, 0.5*k_stretch, 0.00],
    [0.00, 0.00, -0.5*k_bend, 0.00, 0.00, 0.00, 0.00, 0.00, 0.5*k_bend],
]
np.save("D:/__CoChem/GitHub-Repo/CoChem-BASE/tests/data/water_hessian.npy", np.array(hess, dtype=np.float64))
