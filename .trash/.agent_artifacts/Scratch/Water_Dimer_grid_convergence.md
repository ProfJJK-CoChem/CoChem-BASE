# CoChem Method Matrix Integration Grid Convergence Report

**Complex Identifier:** `Water_Dimer` ((H2O)2)  
**Authoritative Standard:** Method Matrix v4 §4.1, §4.4, §16.1 (2), §16.3, and §21.3 Roadmap Item 5  
**Compliance Status:** ✅ COMPLIANT  
**Execution Timestamp:** `2026-08-30T21:24:09.216889+00:00`  
**SHA-256 Audit Hash:** `aefe1bb5aebdd4fcf3d8e22fab70fb2df3181a25fb487307587ab72e65eb6d8f`  

---

## 1. Grid Tier Comparison & Convergence Ladder

| Grid Level | Energy $E$ (Eh) | $R$ (Å) | $R_{cm}$ (Å) | $A$ (MHz) | $B$ (MHz) | $C$ (MHz) | $\Delta$ (amu·Å²) | $\kappa$ | Provenance |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| **DEFGRID1** | -152.88412050 | 2.0150 | 2.9840 | 210234.56 | 6116.35 | 6109.90 | -2.3166 | -0.9999 | [D] |
| **DEFGRID2** | -152.88458920 | 2.0108 | 2.9793 | 210343.48 | 6135.09 | 6128.74 | -2.3173 | -0.9999 | [D] |
| **DEFGRID3** | -152.88460140 | 2.0106 | 2.9791 | 210344.01 | 6135.72 | 6129.38 | -2.3174 | -0.9999 | [D] |

---

## 2. Stepwise Displacements & Rotational Shifts

| Step | $\Delta E$ (µEh) | $\Delta E$ (kcal/mol) | $\Delta R$ (pm) | $\Delta B$ (MHz) | $\Delta B / B$ (%) | $E$ Gate | $R$ Gate | $B$ Gate |
|:---|---:|---:|---:|---:|---:|:---:|:---:|:---:|
| **DEFGRID1 $\rightarrow$ DEFGRID2** | -468.70 | -0.2941 | -0.43 | +18.74 | +0.3064% | FAIL | FAIL | FAIL |
| **DEFGRID2 $\rightarrow$ DEFGRID3** | -12.20 | -0.0077 | -0.01 | +0.63 | +0.0102% | PASS | PASS | PASS |

---

## 3. Rigid-Body Rotational Invariance Audits (Method Matrix §16.1)

| Grid Level | Euler Angles (α, β, γ) | $\Delta E_{rot}$ (µEh) | $\Delta B_{rot}$ (MHz) | $\Delta B / B$ (%) | Soft Modes Gate | Invariance Status |
|:---|:---:|---:|---:|---:|:---:|:---:|
| **DEFGRID2** | (45°, 30°, 60°) | +0.40 | -0.00 | 0.0000% | PASS | ✅ PASS |
| **DEFGRID3** | (45°, 30°, 60°) | +0.05 | -0.00 | 0.0000% | PASS | ✅ PASS |

---

## 4. Method Matrix Compliance Findings

- [DEFGRID1 -> DEFGRID2] Delta E = -4.687000e-04 Eh (-0.2941 kcal/mol) | Delta R = -0.43 pm | Delta B = +0.3064% (+18.74 MHz)
-   [COARSE STEP] Energy change |Delta E| (4.69e-04 Eh) exceeds tolerance (5.00e-05 Eh).
-   [COARSE STEP] Intermolecular shift |Delta R| (0.43 pm) exceeds tolerance (0.10 pm).
-   [COARSE STEP] Rotational constant shift |Delta B / B| (0.306%) exceeds target (0.10%).
- [DEFGRID2 -> DEFGRID3] Delta E = -1.220000e-05 Eh (-0.0077 kcal/mol) | Delta R = -0.01 pm | Delta B = +0.0102% (+0.63 MHz)
- [DEFGRID2 Rotational Invariance] PASS under Euler rotation (45.0, 30.0, 60.0): Delta E = +4.00e-07 Eh, Delta B = 0.0000%.
- [DEFGRID3 Rotational Invariance] PASS under Euler rotation (45.0, 30.0, 60.0): Delta E = +5.00e-08 Eh, Delta B = 0.0000%.