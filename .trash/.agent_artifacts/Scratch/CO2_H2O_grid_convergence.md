# CoChem Method Matrix Integration Grid Convergence Report

**Complex Identifier:** `CO2_H2O` (CO2...H2O)  
**Authoritative Standard:** Method Matrix v4 §4.1, §4.4, §16.1 (2), §16.3, and §21.3 Roadmap Item 5  
**Compliance Status:** ✅ COMPLIANT  
**Execution Timestamp:** `2026-08-30T21:21:34.302132+00:00`  
**SHA-256 Audit Hash:** `e966c3d3be94ea47e6f7ae49ce0abdbd946cfe1e825b21421f212d704b9f2c1d`  

---

## 1. Grid Tier Comparison & Convergence Ladder

| Grid Level | Energy $E$ (Eh) | $R$ (Å) | $R_{cm}$ (Å) | $A$ (MHz) | $B$ (MHz) | $C$ (MHz) | $\Delta$ (amu·Å²) | $\kappa$ | Provenance |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| **DEFGRID1** | -264.48123000 | 2.8460 | 2.9109 | 11390.22 | 4591.11 | 3322.28 | -2.3289 | -0.6855 | [D] |
| **DEFGRID2** | -264.48201500 | 2.8360 | 2.9010 | 11430.08 | 4622.13 | 3341.63 | -2.3166 | -0.6834 | [D] |
| **DEFGRID3** | -264.48203800 | 2.8356 | 2.9006 | 11432.08 | 4623.40 | 3342.45 | -2.3160 | -0.6833 | [D] |

---

## 2. Stepwise Displacements & Rotational Shifts

| Step | $\Delta E$ (µEh) | $\Delta E$ (kcal/mol) | $\Delta R$ (pm) | $\Delta B$ (MHz) | $\Delta B / B$ (%) | $E$ Gate | $R$ Gate | $B$ Gate |
|:---|---:|---:|---:|---:|---:|:---:|:---:|:---:|
| **DEFGRID1 $\rightarrow$ DEFGRID2** | -785.00 | -0.4926 | -1.00 | +31.02 | +0.6755% | FAIL | FAIL | FAIL |
| **DEFGRID2 $\rightarrow$ DEFGRID3** | -23.00 | -0.0144 | -0.04 | +1.27 | +0.0274% | PASS | PASS | PASS |

---

## 3. Rigid-Body Rotational Invariance Audits (Method Matrix §16.1)

| Grid Level | Euler Angles (α, β, γ) | $\Delta E_{rot}$ (µEh) | $\Delta B_{rot}$ (MHz) | $\Delta B / B$ (%) | Soft Modes Gate | Invariance Status |
|:---|:---:|---:|---:|---:|:---:|:---:|
| **DEFGRID2** | (45°, 30°, 60°) | +0.40 | -0.00 | 0.0000% | PASS | ✅ PASS |
| **DEFGRID3** | (45°, 30°, 60°) | +0.05 | -0.00 | 0.0000% | PASS | ✅ PASS |

---

## 4. Method Matrix Compliance Findings

- [DEFGRID1 -> DEFGRID2] Delta E = -7.850000e-04 Eh (-0.4926 kcal/mol) | Delta R = -1.00 pm | Delta B = +0.6755% (+31.02 MHz)
-   [COARSE STEP] Energy change |Delta E| (7.85e-04 Eh) exceeds tolerance (5.00e-05 Eh).
-   [COARSE STEP] Intermolecular shift |Delta R| (1.00 pm) exceeds tolerance (0.10 pm).
-   [COARSE STEP] Rotational constant shift |Delta B / B| (0.676%) exceeds target (0.10%).
- [DEFGRID2 -> DEFGRID3] Delta E = -2.300000e-05 Eh (-0.0144 kcal/mol) | Delta R = -0.04 pm | Delta B = +0.0274% (+1.27 MHz)
- [DEFGRID2 Rotational Invariance] PASS under Euler rotation (45.0, 30.0, 60.0): Delta E = +4.00e-07 Eh, Delta B = 0.0000%.
- [DEFGRID3 Rotational Invariance] PASS under Euler rotation (45.0, 30.0, 60.0): Delta E = +5.00e-08 Eh, Delta B = 0.0000%.