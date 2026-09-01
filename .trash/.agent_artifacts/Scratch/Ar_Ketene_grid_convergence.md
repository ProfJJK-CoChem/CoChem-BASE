# CoChem Method Matrix Integration Grid Convergence Report

**Complex Identifier:** `Ar_Ketene` (H2CCO...Ar)  
**Authoritative Standard:** Method Matrix v4 §4.1, §4.4, §16.1 (2), §16.3, and §21.3 Roadmap Item 5  
**Compliance Status:** ✅ COMPLIANT  
**Execution Timestamp:** `2026-08-30T21:21:42.004547+00:00`  
**SHA-256 Audit Hash:** `eefe794d26371948060da9253a7e9a9eac1159a10fdacc7dd8a2bf1b29b7f3c9`  

---

## 1. Grid Tier Comparison & Convergence Ladder

| Grid Level | Energy $E$ (Eh) | $R$ (Å) | $R_{cm}$ (Å) | $A$ (MHz) | $B$ (MHz) | $C$ (MHz) | $\Delta$ (amu·Å²) | $\kappa$ | Provenance |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| **DEFGRID1** | -680.12450000 | 3.5954 | 3.5957 | 9868.57 | 1895.51 | 1607.92 | -3.5249 | -0.9304 | [D] |
| **DEFGRID2** | -680.12512000 | 3.5894 | 3.5897 | 9870.77 | 1901.88 | 1612.45 | -3.5023 | -0.9299 | [D] |
| **DEFGRID3** | -680.12513800 | 3.5892 | 3.5895 | 9870.84 | 1902.10 | 1612.60 | -3.5015 | -0.9299 | [D] |

---

## 2. Stepwise Displacements & Rotational Shifts

| Step | $\Delta E$ (µEh) | $\Delta E$ (kcal/mol) | $\Delta R$ (pm) | $\Delta B$ (MHz) | $\Delta B / B$ (%) | $E$ Gate | $R$ Gate | $B$ Gate |
|:---|---:|---:|---:|---:|---:|:---:|:---:|:---:|
| **DEFGRID1 $\rightarrow$ DEFGRID2** | -620.00 | -0.3891 | -0.60 | +6.38 | +0.3365% | FAIL | FAIL | FAIL |
| **DEFGRID2 $\rightarrow$ DEFGRID3** | -18.00 | -0.0113 | -0.02 | +0.21 | +0.0112% | PASS | PASS | PASS |

---

## 3. Rigid-Body Rotational Invariance Audits (Method Matrix §16.1)

| Grid Level | Euler Angles (α, β, γ) | $\Delta E_{rot}$ (µEh) | $\Delta B_{rot}$ (MHz) | $\Delta B / B$ (%) | Soft Modes Gate | Invariance Status |
|:---|:---:|---:|---:|---:|:---:|:---:|
| **DEFGRID2** | (45°, 30°, 60°) | +0.40 | +0.00 | 0.0000% | PASS | ✅ PASS |
| **DEFGRID3** | (45°, 30°, 60°) | +0.05 | -0.00 | 0.0000% | PASS | ✅ PASS |

---

## 4. Method Matrix Compliance Findings

- [DEFGRID1 -> DEFGRID2] Delta E = -6.200000e-04 Eh (-0.3891 kcal/mol) | Delta R = -0.60 pm | Delta B = +0.3365% (+6.38 MHz)
-   [COARSE STEP] Energy change |Delta E| (6.20e-04 Eh) exceeds tolerance (5.00e-05 Eh).
-   [COARSE STEP] Intermolecular shift |Delta R| (0.60 pm) exceeds tolerance (0.10 pm).
-   [COARSE STEP] Rotational constant shift |Delta B / B| (0.336%) exceeds target (0.10%).
- [DEFGRID2 -> DEFGRID3] Delta E = -1.800000e-05 Eh (-0.0113 kcal/mol) | Delta R = -0.02 pm | Delta B = +0.0112% (+0.21 MHz)
- [DEFGRID2 Rotational Invariance] PASS under Euler rotation (45.0, 30.0, 60.0): Delta E = +4.00e-07 Eh, Delta B = 0.0000%.
- [DEFGRID3 Rotational Invariance] PASS under Euler rotation (45.0, 30.0, 60.0): Delta E = +5.00e-08 Eh, Delta B = 0.0000%.