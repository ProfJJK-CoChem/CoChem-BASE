# T3 and T4 Research: Equilibrium Geometries ($B_e$), Vibrational Averaging ($\Delta B_{\text{vib}}$), and Ground-State Rotational Constants ($B_0$)

This document provides a comprehensive, rigorous analysis of the computational methods, error propagation models, operational execution protocols, and authoritative literature supporting the twenty wall-clock tiers of **Table 3 (Equilibrium Geometry & $B_e$)** and twenty wall-clock tiers of **Table 4 (Vibrational Averaging & $B_0$)** in the CoChem Method Matrix (§13.3, §13.4).

---

## 1. Overview & Fundamental Spectroscopic Invariants

### 1.1 The $B_e$ vs. $B_0$ Distinction & Spending Hierarchy (§3.0, §3.3)
In microwave and millimeter-wave rotational spectroscopy of weakly bound van der Waals complexes and flexible molecules, conflating equilibrium rotational constants ($B_e$) with ground-state rotational constants ($B_0$) is the most severe conceptual defect in computational assignment pipelines.

- **Equilibrium Rotational Constant ($B_e$):** Evaluated strictly at the hypothetical potential energy minimum on the Born–Oppenheimer surface. **$B_e$ is not a physical observable.** State-of-the-art composite coupled-cluster schemes (e.g., junChS) achieve **$0.13\%$ Mean Absolute Error (MAE) in $B_e$ `[M]`** for molecules $\le 16$ atoms.
- **Ground-State Rotational Constant ($B_0$):** The true physical observable measured in supersonic jet chirped-pulse Fourier transform microwave (CP-FTMW) experiments. $B_0 = B_e + \Delta B_{\text{vib}}$, where the vibrational correction $\Delta B_{\text{vib}} = -\frac{1}{2}\sum_r \alpha_r^B$ typically constitutes **$0.1\text{–}0.7\%$ of $B_e$ `[M]`** in semi-rigid molecules, and can exceed **$1\text{–}30\%$ `[M]`** in floppy, large-amplitude intermolecular complexes (e.g., $\Delta R_0^e = 0.361\text{ \AA}$ in $\text{CH}_3^+\text{--He}$ `[M]`).
- **The Spending Priority Hierarchy (Binding, §3.3):**
  $$\text{① Best Affordable Geometry} \longrightarrow \text{② Cheap Anharmonic } \Delta B_{\text{vib}} \longrightarrow \text{③ Quartic Distortion (Free)} \longrightarrow \text{④ Dipole Components} \longrightarrow \text{⑤ }^{14}\text{N Quadrupole Tensor}$$
  *Rule:* Never buy a higher-level equilibrium structure ($B_e$) beyond the composite DFT/MP2 level until you have purchased an anharmonic vibrational correction ($\Delta B_{\text{vib}}$). Buying a $0.04\%$ $B_e$ without $\Delta B_{\text{vib}}$ does not move $B_0$ closer to experiment because $\Delta B_{\text{vib}}$ dominates the residual error.

```
       +-------------------------------------------------------------+
       |               Born–Oppenheimer PES Minimum                  |
       |  Equilibrium Geometry (Re)  -->  Be [Not an Observable]     |
       |  Reachable to 0.13 % [M] via CBS+CV Composite Schemes       |
       +-------------------------------------------------------------+
                                      |
                                      |  + Delta B_vib (Vibrational Averaging)
                                      |    (0.1 - 0.7 % semi-rigid; 1 - 30 % floppy [M])
                                      v
       +-------------------------------------------------------------+
       |               Vibrational Ground State (v = 0)              |
       |  Effective Geometry (R0)   -->  B0 [Microwave Observable]   |
       |  Product A: 0.3 - 0.5 % semi-rigid, 1 - 2 % floppy [D]      |
       |  Product B (Semi-Exp): 0.03 - 0.06 % [M]                    |
       |  Product C (Isotopologue Shifts): 0.02 - 0.1 % [M]          |
       +-------------------------------------------------------------+
```

### 1.2 The Three Spectroscopic Product Classes (§3.1)
Every computational campaign must identify its target product class prior to execution:
1. **Product A (De Novo Prediction):** No prior experimental microwave measurements exist. Target accuracy is **$0.3\text{–}0.5\%$ `[D]`** for semi-rigid species and **$1\text{–}2\%$ `[D]`** for floppy van der Waals complexes in $B_0$. (At $12\text{ GHz}$, $\pm 0.5\% = \pm 60\text{ MHz}$, leaving 60–240 candidate lines in a dense chirped-pulse spectrum).
2. **Product B (Semi-Experimental Anchoring / Known Parent):** A measured parent or close analogue exists. By scaling the theoretical equilibrium geometry to reproduce experimental rotational constants ($r_e^{\text{SE}}$) and substituting isotopic masses (Recipe R6), $B_0$ is reachable to **$0.03\text{–}0.06\%$ `[M]`**.
3. **Product C (Isotopologue / Differential Shifts):** Only isotopic shifts ($\Delta B = B_{\text{iso}} - B_{\text{parent}}$) or conformer energy differences are needed. Achieves **$0.02\text{–}0.1\%$ `[M]`** accuracy by re-analyzing a single converged force field at zero additional electronic structure cost.

### 1.3 Method Matrix Provenance Tagging Mandate (§12.5 Rule 7)
All quantitative metrics, error bounds, and scaling ratios in this document carry strict provenance tags:
- **`[M]`**: Directly measured from published experimental or high-level ab initio benchmark databases (e.g., S22, S66, ROT34, A21, Bologna 74-isotopologue).
- **`[D]`**: Derived mathematically via rigorous physical propagation formulas (e.g., $\Delta B/B = -2\Delta R/R$, Eckart–Watson Hamiltonian).
- **`[E]`**: Expert engineering estimate based on algorithmic complexity and hardware scaling.

---

## 2. Core Physical Models & Operational Protocols

### 2.1 Error Propagation & The Frozen-Monomer Architecture (§4.1, §4.5, §9A.1)
For a non-covalent complex approximated along its intermonomer separation $R$ with reduced mass $\mu$:
$$B = \frac{h}{8\pi^2 \mu R^2} = \frac{505379.1\text{ MHz}\cdot\text{u}\cdot\text{\AA}^2}{\mu R^2}, \qquad \frac{\Delta B}{B} = -2\,\frac{\Delta R}{R}$$

Rigid-rotor moment-of-inertia propagation demonstrates a fundamental physical asymmetry:
- **Monomer Covalent Bonds:** Error in monomer bond lengths dominates the out-of-plane/in-plane axis rotational constant **$A$** and has a negligible effect on $B$ and $C$. A $+0.010\text{ \AA}$ covalent bond error shifts $A$ by **$-1.711\%$ `[D]`**, but shifts $B$ by only **$-0.080\%$ `[D]`**.
- **Intermolecular Separation ($R$):** Error in the weak intermolecular distance $R$ dominates **$B$ and $C$** and has zero contribution to $A$. A $+0.010\text{ \AA}$ error in $R$ shifts $B$ by **$-0.675\%$ `[D]`** and $A$ by **$0.000\%$ `[D]`**.
- **Break-Even Analysis:** On $\text{CO}_2\cdots\text{H}_2\text{O}$ ($R = 2.836\text{ \AA}$), an intermolecular error of $\Delta R = 0.002\text{ \AA}$ produces the same error in $B$ as a **$16.8\text{ m\AA}$ uniform error across every covalent bond `[D]`**—an error no modern QM method commits covalently (e.g., fc-CCSD(T)/VTZ MAD is $0.003\text{ \AA}$ `[M]`).

> **The Frozen-Monomer Protocol Mandate (§9A.1):**
> *Freeze high-level/experimental monomers to fix constant $A$, and spend the computational budget optimizing the intermolecular coordinate $R$ with a high-level dispersion-corrected method to fix $B$ and $C$.*

```
       ========================================================================
       COORDINATE SENSITIVITY PROFILE IN NON-COVALENT COMPLEXES
       ========================================================================
       Monomer Covalent Bonds (r_intra)      --> Governs Rotational Constant A
       (Upgrading B3LYP -> CCSD(T) buys ~1.2 pp in A, but only 0.056 pp in B [D])
       ------------------------------------------------------------------------
       Intermolecular Separation (R_inter)   --> Governs Rotational Constants B & C
       (Tightening R error 0.020 A -> 0.005 A buys 1.0 pp (46 MHz) in B [D])
       ========================================================================
```

#### Frozen-Monomer Tracking Flags (§9A.2):
- `relaxed`: All intramolecular and intermolecular coordinates optimized simultaneously.
- `frozen-iso`: Monomers frozen at isolated-monomer geometries (experimental $r_e^{\text{SE}}$ or CCSD(T)/CBS). Safe for dispersion-bound complexes; must be flagged for strong hydrogen bonds where deformation energy reaches up to $9.5\text{ kcal/mol}$ `[M]`.
- `frozen-inc`: Monomers frozen at in-complex geometries optimized at a higher level (S66 convention).

*Operational Caveats:*
1. When using experimental monomers, always use semi-experimental equilibrium geometries ($r_e^{\text{SE}}$), **never vibrational ground-state geometries ($r_0$)**, or the monomer's vibrational correction is double-counted.
2. Always report the residual gradient on frozen coordinates; if it exceeds `TolMaxG` ($1\times 10^{-5}\text{ Eh/bohr}$), the constraint is doing active physical work and must be disclosed.

---

### 2.2 Geometry Optimization Convergence Gate (§4.4)
Soft intermolecular modes ($k \approx 0.05\text{–}0.20\text{ mdyn/\AA} = 0.0032\text{–}0.013\text{ Eh/bohr}^2$) allow loose optimizers to stop far from the true minimum:
- Default `!Opt` ($g_{\text{max}} = 3\times 10^{-4}\text{ Eh/bohr}$) leaves $\Delta r = 3.6\text{ pm} \Rightarrow \Delta B/B \approx 2.1\%$ `[D]`.
- Default `!TightOpt` ($g_{\text{max}} = 1\times 10^{-4}\text{ Eh/bohr}$) leaves $\Delta r = 1.2\text{ pm} \Rightarrow \Delta B/B \approx 0.69\%$ `[D]`.
- **Mandatory `%geom` Block for all tiers claiming $\le 0.5\%$ in $B$ (§4.4):**
```orca
%geom
  TolE     1e-7      # Below VeryTightOpt
  TolRMSG  3e-6
  TolMaxG  1e-5      # 3x tighter than VeryTightOpt -> ~0.12 pm at k = 0.069 mdyn/A
  TolRMSD  5e-5
  TolMaxD  1e-4
end
```
Must be paired with `TightSCF` or `VeryTightSCF` and `DEFGRID3` to ensure numerical gradient noise sits well below `TolMaxG`. Intermolecular geometries cannot be converged to spectroscopic tightness on float32 MLFF potentials due to single-precision noise ($\sim 4\times 10^{-6}\text{ Eh}$).

---

### 2.3 Basis Set Superposition Error (BSSE) & Core-Valence Realities (§4.7, §4.8)
1. **BSSE as a First-Order Structural Error:** BSSE artificially contracts non-covalent complexes. On water dimer, uncorrected B3LYP/cc-pVTZ yields $R(\text{O}\cdots\text{O}) = 2.909\text{ \AA}$, while counterpoise-corrected optimization (`CP-OPT`) yields $2.950\text{ \AA}$ ($\Delta R = +4.1\text{ pm} \Rightarrow \Delta B/B \approx 2.8\%$ `[M]`). Non-augmented triple-zeta optimizations without `BSSEOptimization.cmp` are capped at $3\%$ accuracy in $B$.
2. **Frozen-Core Bias:** Across 74 isotopologues, frozen-core fc-CCSD(T)/cc-pVQZ exhibits a systematic **$-0.806\%$ bias in $B_e$ `[M]`** (max error $2.701\%$ `[M]`). All-electron ae-CCSD(T)/cc-pCVQZ eliminates this bias (mean error **$-0.037\%$ `[M]`**).
   - *Cost-effective recommendation:* CBS extrapolation with a small core-valence basis: $\text{fc/CBS(Q,5)} + \text{core/cc-pCVTZ}$ achieves **$0.107\%$ MAE `[M]`**.

---

### 2.4 Binding Prohibitions & Recipe Rules (§9A.5, §9A.7)
1. **Prohibition on Additive Diffuse Corrections (§9A.5, §9A.7 Rule 6):** Adding diffuse-function increments as an additive correction ("$\Delta\alpha$ approach") rather than computing directly in a diffuse basis degrades interaction energy MAE from **$1.52\%$ to $12.74\%$ `[M]`** and shifts equilibrium geometries by up to **$0.2\text{ \AA}$ on $\text{CH}_4\cdots\text{NH}_3$ `[M]`**. Diffuse sets must be present in the underlying basis of every leg (e.g., using calendar sets like `jun-cc-pVTZ`).
2. **Rejection of ONIOM / QM-QM2 (§9A.5):** Demoting atoms in a 5–10 atom complex is physically unviable: there are no covalent bonds to cut, no savings are realized, and the dimer is already within the high-level region.
3. **Trimers & Many-Body Dispersion (§9A.5):** Pairwise D3/D4 models omit non-additive three-body dispersion/induction, which accounts for **$15\text{–}20\%$ of total interaction energy `[M]`** in cyclic trimers.

---

### 2.5 CFOUR Operational Invariants & Execution Rules (§9.4, §9.5)
CFOUR is the gold standard for coupled-cluster analytic derivatives, but requires strict adherence to operational mandates:
1. **Global Memory Allocation:** Unlike ORCA's per-process `%maxcore`, CFOUR uses a **single global allocation** that defaults to $\approx 762\text{ MB}$. Omitting `MEMORY_SIZE=32, MEM_UNIT=GB` causes severe memory thrashing.
2. **Internal Coordinate `ZMAT` Mandate:** CFOUR requires input named `ZMAT` with `GENBAS` present. Variable names are strictly limited to **three characters**, and fields must be separated by single spaces.
3. **Linearity & Dummy Atoms:** Angles of 0° or 180° are strictly forbidden. Linear fragments (e.g., $\text{Ar}\cdots\text{HCN}$, $\text{OC}\cdots\text{HF}$) must use dummy atoms `X` (e.g., setting angle to 90° or 179°).
4. **The Cartesian Coordinate Trap:** Setting `COORDINATES=CARTESIAN` silently disables geometry optimization and analytic force fields, restricting CFOUR to single points.
5. **Coupled-Cluster Parallel Execution:** Parallel execution for CCSD(T) gradients and Hessians requires `ABCDTYPE=AOBASIS` and `CC_PROG=ECC`.
6. **VPT2 Anharmonicity Keywords:** `ANHARM=VPT2` computes the full cubic and semidiagonal quartic force field. `ANHARM=VIBROT` is restricted to totally symmetric cubic constants $\phi_{nij}$ and is **insufficient for $C_1$ complexes and lower-symmetry isotopologues**.
7. **SPFIT/SPCAT Transcription:** CFOUR has no documented Pickett export; constants must be transcribed via external script (`n.a.`).

---

### 2.6 Vibrational Averaging & Dynamics Protocol (§13.4, §5.1, Appendix A)
1. **Classical MD Failure at Low Temperatures:** At $5\text{ K}$ ($k_B T = 3.48\text{ cm}^{-1}$), classical equipartition puts $1.74\text{ cm}^{-1}$ into each mode against zero-point energies of $15\text{ cm}^{-1}$ for intermolecular bends and $1500\text{ cm}^{-1}$ for stretches. A classical trajectory at $5\text{ K}$ is a frozen structure rattling in the harmonic bottom and yields $B_e$, missing ZPE elongation ($\Delta R_0^e = 0.361\text{ \AA}$ in $\text{CH}_3^+\text{--He}$ `[M]`). Classical barrier crossing is frozen ($e^{-28.7} \approx 3\times 10^{-13}$).
2. **Reinstatement as a Diagnostic Only:** Classical MD is restricted to three outputs: (a) basin count, (b) bounded upper estimate of $\Delta B_{\text{vib}}$, and (c) explicit "zero-point energy not included" flag. It must never emit an absolute rotational constant.
3. **Rigid-Monomer Path-Integral MD (PIMD):** Executed at $50\text{ K}$ on an MLFF surface with $P = 40$ beads (accounting for $\omega_{\text{max}} = 600\text{ cm}^{-1}$ with a 2.2 safety factor). Full-dimensional PIMD at $5\text{ K}$ is physically prohibited ($P > 863$ beads required).
4. **Tensor Averaging Identity:**
   $$A_0 = \frac{1}{2}\langle \mu_{xx} \rangle_0, \quad B_0 = \frac{1}{2}\langle \mu_{yy} \rangle_0, \quad C_0 = \frac{1}{2}\langle \mu_{zz} \rangle_0, \quad \mu_{\alpha\beta} = (I'^{-1})_{\alpha\beta}$$
   *Rule:* Always average the **inverse effective inertia tensor elements $\langle \mu_{\alpha\alpha} \rangle$**, then diagonalize. By Jensen's inequality $\langle 1/I \rangle \ge 1/\langle I \rangle$; averaging $I$ and inverting afterwards systematically underestimates $B_0$ by $3\sigma_R^2/R_0^2$.

---

## 3. Table 3: Equilibrium Geometry and $B_e$ (§13.3)

Table 3 governs the determination of equilibrium structures and $B_e$ across ten wall-clock tiers on both the ORCA and CFOUR tracks.

```
       ========================================================================================
       TABLE 3 TIERS AT A GLANCE (Equilibrium Geometries & Be)
       ========================================================================================
       Tier     ORCA Track (Table 3-O)               CFOUR Track (Table 3-C)
       ----------------------------------------------------------------------------------------
       10 s     T3O-10s: GFN2-xTB (±3-15% [M])       T3C-10s: Track Gap (None)
       1 min    T3O-1min: Recipe R1 (±1-3% [D])      T3C-1min: Track Gap (None)
       30 min   T3O-30min: wB97X-V/def2-TZVPP        T3C-30min: MP2/cc-pVDZ Sanity Check
       1 h      T3O-1h: wB97X-V/jun-cc-pVTZ          T3C-1h: CCSD(T)/cc-pVTZ Props/EFG
       3 h      T3O-3h: Recipe R2 (wB97M-V/QZ+CP)    T3C-3h: CCSD(T)/cc-pVTZ Opt (0.90% [M])
       12 h     T3O-12h: Recipe R4 (junChS 0.13% [M]) T3C-12h: CCSD(T)/cc-pVQZ Opt (0.43% [M])
       1 d      T3O-1d: MPQC CCSD(T)-F12 NumGrad     T3C-1d: ae-CCSD(T)/cc-pCVQZ (0.16% [M])
       3 d      T3O-3d: AUTOCI CCSD(T)-F12 Opt       T3C-3d: ChS Composite in CFOUR (0.13% [M])
       1 w      T3O-1w: HEAT/ChS Composite (0.04%)   T3C-1w: CBS+CV+fT+fQ Composite (0.04% [M])
       1 mo     T3O-1mo: Explicitly Correlated Ref   T3C-1mo: Full Composite + Rel + DBOC
       ========================================================================================
```

---

### 3.1 Table 3-O: ORCA Track (Tiers T3O-10s to T3O-1mo)

#### Tier T3O-10s: Semi-Empirical GFN2-xTB Equilibrium Structure
- **Method / Code:** `! XTB2 TightOpt` or `xtb --opt vtight --strict` (ORCA / xtb).
- **Delivers & Accuracy:** $B_e \pm 3\text{–}15\%$ `[M]`. Concurrency: `C`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** Intermonomer separations carry systematic errors ($14\text{ pm}$ MAD on S22 benchmark `[M]`). On pyrrole–Ne, tight-binding structures err by up to $46.34\%$ `[M]`.
- **Best Practices:** Use strictly for rapid structural screening, conformer topology generation, and isotopologue mass bookkeeping. Never report semi-empirical rotational constants as final predictions.
- **Authoritative Citations:**
  1. C. Bannwarth, S. Ehlert, S. Grimme, *J. Chem. Theory Comput.* 2019, 15, 1652–1671. [DOI: 10.1021/acs.jctc.8b01176](https://doi.org/10.1021/acs.jctc.8b01176)
  2. S. Grimme, C. Bannwarth, P. Shushkov, *J. Chem. Theory Comput.* 2017, 13, 1989–2009. [DOI: 10.1021/acs.jctc.7b00118](https://doi.org/10.1021/acs.jctc.7b00118)

---

#### Tier T3O-1min: Recipe R1 — Frozen Monomers + r²SCAN-3c Intermolecular Optimization
- **Method / Code:** `! r2SCAN-3c TightSCF DefGrid3` + §4.4 `%geom` + `%geom Constraints { ... } end` with `InHess XTB2` (ORCA).
- **Delivers & Accuracy:** $B_e \pm 1\text{–}3\%$; constant $A$ to $<0.2\%$ `[D]`. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-iso`.
- **Benchmark Errors & Limitations:** r²SCAN-3c lacks diffuse basis functions, making the intermolecular distance the primary residual error. ROT34 benchmark exhibits $A_{\text{MAX}} \approx 1.5\%$ `[M]`.
- **Best Practices:** Strictly dominates unconstrained r²SCAN-3c: achieves identical wall time while improving $A$ by $\sim 1.5\text{ percentage points}$. Do NOT include `D4` or `gCP` keywords (both are integral to the composite parameterization).
- **Authoritative Citations:**
  1. S. Grimme, A. Hansen, S. Ehlert, J.-M. Mewes, *J. Chem. Phys.* 2021, 154, 064103. [DOI: 10.1063/5.0040021](https://doi.org/10.1063/5.0040021)
  2. J. W. Furness, A. D. Kaplan, J. Ning, J. P. Perdew, J. Sun, *J. Phys. Chem. Lett.* 2020, 11, 8208–8215. [DOI: 10.1021/acs.jpclett.0c02405](https://doi.org/10.1021/acs.jpclett.0c02405)

---

#### Tier T3O-30min: $\omega$B97X-V / def2-TZVPP Full Optimization
- **Method / Code:** `! wB97X-V def2-TZVPP def2/J RIJCOSX TightSCF DefGrid3` + §4.4 `%geom` + `InHess XTB2` (ORCA).
- **Delivers & Accuracy:** $B_e \pm 0.5\text{–}3\%$ `[E]`. Concurrency: `P`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** BSSE artificially contracts the complex ($+4.1\text{ pm} \approx 2.8\%$ in $B$ on cc-pVTZ `[M]`). $\omega\text{B97X-D}$ rare-gas RMSD is $36.34\text{ pm}$ `[M]`.
- **Best Practices:** At triple-zeta quality, pair with `BSSEOptimization.cmp` or compute counterpoise-bracketed energies. Re-use converged `.gbw` files from 1-min tiers.
- **Authoritative Citations:**
  1. N. Mardirossian, M. Head-Gordon, *Phys. Chem. Chem. Phys.* 2014, 16, 9904–9924. [DOI: 10.1039/C3CP54374A](https://doi.org/10.1039/C3CP54374A)
  2. J. A. Plumley, J. J. Dannenberg, *J. Comput. Chem.* 2011, 32, 1519–1527. [DOI: 10.1002/jcc.21730](https://doi.org/10.1002/jcc.21730)

---

#### Tier T3O-1h: $\omega$B97X-V / jun-cc-pVTZ Optimization with Diffuse Functions
- **Method / Code:** `! wB97X-V jun-cc-pVTZ def2/J RIJCOSX TightSCF DefGrid3` (ORCA).
- **Delivers & Accuracy:** $B_e \pm 0.5\text{–}2\%$ `[E]`. Concurrency: `P`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** Calendar basis sets (`jun-`) reduce basis set truncation error and BSSE while avoiding linear dependence issues common to fully augmented `aug-` sets.
- **Best Practices:** Raise `%scf SThresh` if overlap matrix eigenvalues indicate near-linear dependence.
- **Authoritative Citations:**
  1. E. Papajak, D. G. Truhlar, *J. Chem. Theory Comput.* 2011, 7, 3027–3034. [DOI: 10.1021/ct200106a](https://doi.org/10.1021/ct200106a)
  2. S. Alessandrini, C. Puzzarini, *J. Phys. Chem. A* 2021, 125, 6401–6412. [DOI: 10.1021/acs.jpca.1c04845](https://doi.org/10.1021/acs.jpca.1c04845)

---

#### Tier T3O-3h: Recipe R2 — Frozen CCSD(T) Monomers + $\omega$B97M-V/def2-QZVPP + CP + VPT2
- **Method / Code:**
  1. `! wB97M-V def2-QZVPP def2/J RIJCOSX TightSCF DefGrid3` + §4.4 `%geom` + constraints (ORCA).
  2. Three-leg counterpoise single points at `! DLPNO-CCSD(T1) TightPNO cc-pVDZ-F12 (paired with CABS)`.
  3. Harmonic/Anharmonic force field at `! wB97X-V def2-TZVPP Freq VPT2 VeryTightSCF` or B3LYP-D4.
- **Delivers & Accuracy:** **$B_e \pm 0.4\text{–}1.5\%$; semi-rigid $\pm 0.3\text{–}0.5\%$; $A$ to $<0.2\%$ `[E]`**, plus $\Delta B_{\text{vib}}$ and CP-corrected binding energy. Concurrency: `P`. Product: `A`. Monomer flag: `frozen-iso`.
- **Benchmark Errors & Limitations:** $\omega\text{B97M-V}$ achieves $0.58\text{ pm}$ RMSD on A21 and $7.91\text{ pm}$ on rare gases `[M]`. Quadruple-zeta represents the DFT basis set limit for non-covalent interactions.
- **Best Practices:** **The single best de novo accuracy-per-core-hour row in the entire document.** Always report the residual gradient on frozen coordinates.
- **Authoritative Citations:**
  1. N. Mardirossian, M. Head-Gordon, *J. Chem. Phys.* 2016, 144, 214110. [DOI: 10.1063/1.4952647](https://doi.org/10.1063/1.4952647)
  2. V. Barone, *J. Chem. Phys.* 2005, 122, 014108. [DOI: 10.1063/1.1824881](https://doi.org/10.1063/1.1824881)

---

#### Tier T3O-12h: Recipe R4 — junChS Composite Scheme
- **Method / Code:** Parameter-wise geometric addition:
  $$R(\text{junChS}) = R[\text{fc-CCSD(T)/jun-cc-pVTZ}] + \Delta R[\text{MP2/CBS}(T\to Q), n^{-3}] + \Delta R[\text{MP2/CV}, \text{cc-pwCVTZ}]$$
- **Delivers & Accuracy:** **$B_e$ MAE $0.13\%$ for molecules $\le 16$ atoms `[M]`**. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-iso` or `relaxed`.
- **Benchmark Errors & Limitations:** Delivers $B_e$ only; does not include $\Delta B_{\text{vib}}$. Pyridine–$\text{H}_2\text{O}$ benchmark requires $16\text{ h } 12\text{ min}$ on 64 CPUs `[M]`.
- **Best Practices:** The published gold standard for sub-$0.2\%$ equilibrium constants. Never use additive diffuse corrections; use `jun-cc-pVnZ` directly.
- **Authoritative Citations:**
  1. C. Puzzarini, J. F. Stanton, *Phys. Chem. Chem. Phys.* 2023, 25, 1421–1443. [DOI: 10.1039/D2CP04706C](https://doi.org/10.1039/D2CP04706C)
  2. S. Alessandrini, C. Puzzarini, *J. Phys. Chem. A* 2021, 125, 6401–6412. [DOI: 10.1021/acs.jpca.1c04845](https://doi.org/10.1021/acs.jpca.1c04845)

---

#### Tier T3O-1d: MPQC CCSD(T)-F12 Numerical Gradient Optimization
- **Method / Code:** `! MPQC CCSD(T)-F12 TightPNO cc-pVDZ-F12 (paired with CABS) NumGrad Opt TightSCF` (ORCA).
- **Delivers & Accuracy:** $B_e \pm 0.3\text{–}0.8\%$ floppy, $\pm 0.15\text{–}0.5\%$ semi-rigid `[D]`. Concurrency: `S`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** Lacks analytic gradients for DLPNO: requires $6N = 60$ single-point energy evaluations per optimization cycle ($1,500$ points $\approx 375\text{ core-h}$ `[D]`).
- **Best Practices:** **Pareto-dominated by T3O-12h.** Use only when composite parameter-wise addition is suspected of severe coordinate coupling failure.
- **Authoritative Citations:**
  1. C. Riplinger, F. Neese, *J. Chem. Phys.* 2013, 138, 034106. [DOI: 10.1063/1.4773581](https://doi.org/10.1063/1.4773581)

---

#### Tier T3O-3d: Canonical CCSD(T)/cc-pVTZ-F12 AUTOCI Analytic Gradients
- **Method / Code:** `! AUTOCI-CCSD(T) cc-pVTZ-F12 (paired with CABS: OptRI, JKFIT, MP2FIT) Opt TightSCF` (ORCA Setup 3).
- **Delivers & Accuracy:** $B_e \pm 0.3\text{–}1\%$ `[M]`. Concurrency: `S`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** Frozen-core error on $A_e$ can reach $-6.56\%$ `[M]`. Memory demands reach $99\text{ GB}$ for four-external integrals if run conventional.
- **Best Practices:** Must specify AO-direct algorithms. For canonical coupled-cluster optimization, CFOUR (T3C-3d) or Molpro (junChS-F12) is strictly preferred.
- **Authoritative Citations:**
  1. M. E. Harding et al., *J. Chem. Theory Comput.* 2008, 4, 64–74. [DOI: 10.1021/ct700241n](https://doi.org/10.1021/ct700241n)

---

#### Tier T3O-1w: High-Order Composite CCSD(T)/CBS + $\Delta\text{core} + \Delta\text{T} + \Delta\text{Q}$
- **Method / Code:** Full focal-point / HEAT family composite geometry with core-valence and high-excitation corrections.
- **Delivers & Accuracy:** $B_e \pm 0.04\%$ semi-rigid closed-shell `[M]`; $1\text{–}2\%$ floppy `[D]`. Concurrency: `S`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** High-order correlation ($\Delta T, \Delta Q$) provides negligible improvement in floppy intermolecular coordinates compared to the residual $\Delta B_{\text{vib}}$ error.
- **Authoritative Citations:**
  1. M. E. Harding et al., *J. Chem. Phys.* 2008, 128, 114111. [DOI: 10.1063/1.2837651](https://doi.org/10.1063/1.2837651)

---

#### Tier T3O-1mo: Explicitly Correlated F12 Reference (Molpro junChS-F12)
- **Method / Code:** Molpro DF-CCSD(T)-F12 geometry optimization (commercial license required).
- **Delivers & Accuracy:** $B_e \sim 0.1\text{–}0.3\%$, interaction energy MUE $0.06\text{ kJ/mol}$ `[M]`. Concurrency: `S`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** ORCA 6.1 cannot compute F12 analytic gradients. Dominated by junChS-F12 under Molpro.
- **Authoritative Citations:**
  1. J. Lupi, S. Alessandrini, C. Puzzarini, V. Barone, *J. Chem. Theory Comput.* 2021, 17, 6974–6988. [DOI: 10.1021/acs.jctc.1c00827](https://doi.org/10.1021/acs.jctc.1c00827)

---

### 3.2 Table 3-C: CFOUR Track (Tiers T3C-10s to T3C-1mo)

#### Tiers T3C-10s & T3C-1min: Track Gaps (Stated Honestly)
- **Status:** **Cannot fill.** CFOUR has no semi-empirical, force-field, or DFT engines. Escalate to `T3O-10s` and `T3O-1min`.

---

#### Tier T3C-30min: MP2 / cc-pVDZ Optimization
- **Method / Code:** `*CFOUR(CALC=MP2, BASIS=PVDZ, COORDINATES=INTERNAL, MEMORY_SIZE=32, MEM_UNIT=GB)` with `*` appended to variable definitions.
- **Delivers & Accuracy:** Structural sanity check; **no $B_e$ accuracy claim**. Concurrency: `C`. Product: `A`. Monomer flag: `relaxed`.
- **Best Practices:** MP2 is not parallelized in CFOUR. Always specify `MEMORY_SIZE=32, MEM_UNIT=GB`.
- **Authoritative Citations:**
  1. J. F. Stanton et al., CFOUR Program Package, http://www.cfour.de.

---

#### Tier T3C-1h: CCSD(T) / cc-pVTZ Single Point with First-Order Properties
- **Method / Code:** `*CFOUR(CALC=CCSD(T), BASIS=PVTZ, PROPS=FIRST_ORDER, ABCDTYPE=AOBASIS, CC_PROG=ECC, MEMORY_SIZE=32, MEM_UNIT=GB)`.
- **Delivers & Accuracy:** Dipole moment components, Electric Field Gradients (EFG) $\to$ nuclear quadrupole coupling tensors $\chi$. No geometry optimization. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-inc`.
- **Best Practices:** Convert EFG to $\chi$ in kHz via: $\chi(\text{kHz}) = \text{EFG}(\text{a.u.}) \times Q(\text{mbarn}) \times 234.96474$.
- **Authoritative Citations:**
  1. C. Puzzarini et al., *J. Chem. Phys.* 2008, 128, 194108. [DOI: 10.1063/1.2912941](https://doi.org/10.1063/1.2912941)

---

#### Tier T3C-3h: CCSD(T) / cc-pVTZ Analytic Gradient Optimization
- **Method / Code:** `*CFOUR(CALC=CCSD(T), BASIS=PVTZ, COORDINATES=INTERNAL, GEO_CONV=5, GEO_MAXCYC=50, ABCDTYPE=AOBASIS, CC_PROG=ECC, MEMORY_SIZE=32, MEM_UNIT=GB)`.
- **Delivers & Accuracy:** $B_e$ MAE $0.90\%$ `[M]`. Concurrency: `C`. Product: `A`. Monomer flag: `relaxed` or `frozen-inc`.
- **Best Practices:** Internal coordinates (`ZMAT`) mandatory. Variable names limited to 3 characters; single-space separators; use dummy atoms `X` for linear chains.
- **Authoritative Citations:**
  1. J. Gauss, J. F. Stanton, *Chem. Phys. Lett.* 1997, 276, 70–77. [DOI: 10.1016/S0009-2614(97)00811-7](https://doi.org/10.1016/S0009-2614(97)00811-7)

---

#### Tier T3C-12h: CCSD(T) / cc-pVQZ Optimization
- **Method / Code:** `*CFOUR(CALC=CCSD(T), BASIS=PVQZ, COORDINATES=INTERNAL, ABCDTYPE=AOBASIS, CC_PROG=ECC, MEMORY_SIZE=32, MEM_UNIT=GB)`.
- **Delivers & Accuracy:** $B_e$ MAE $0.43\%$ `[M]` (max error $2.701\%$ `[M]`). Concurrency: `C`. Product: `A`. Monomer flag: `relaxed`.
- **Benchmark Errors & Limitations:** Frozen core at quadruple-zeta incurs a systematic **$-0.806\%$ bias `[M]`**.
- **Authoritative Citations:**
  1. Bologna 74-isotopologue benchmark, *Cris.Unibo.it*, 2022.

---

#### Tier T3C-1d: All-Electron CCSD(T) / cc-pCVQZ Optimization
- **Method / Code:** `*CFOUR(CALC=CCSD(T), BASIS=PCVQZ, FROZEN_CORE=OFF, COORDINATES=INTERNAL, ABCDTYPE=AOBASIS, CC_PROG=ECC, MEMORY_SIZE=32, MEM_UNIT=GB)`.
- **Delivers & Accuracy:** $B_e$ mean error **$-0.037\%$ `[M]`**, MAE **$0.164\%$ `[M]`** (max error $0.874\%$ `[M]`). Concurrency: `C`. Product: `A`. Monomer flag: `relaxed`.
- **Best Practices:** Core-valence quadruple-zeta is computationally intensive; the cost-effective alternative is $\text{fc/CBS(Q,5)} + \text{core/cc-pCVTZ}$ ($0.107\%$ MAE `[M]`).
- **Authoritative Citations:**
  1. C. Puzzarini, J. F. Stanton, *Phys. Chem. Chem. Phys.* 2023, 25, 1421–1443. [DOI: 10.1039/D2CP04706C](https://doi.org/10.1039/D2CP04706C)

---

#### Tier T3C-3d: ChS / junChS Composite in CFOUR
- **Method / Code:** Three-leg composite evaluated via CFOUR: fc-CCSD(T)/TZ + $\Delta$MP2/CBS + $\Delta$MP2/CV.
- **Delivers & Accuracy:** $B_e$ MAE $0.13\%$ `[M]`. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-inc`.
- **Best Practices:** Must report the basis extrapolation formula ($n^{-3}$ vs. $n^{-5}$ shifts $R$ by $3\text{–}5\text{ m\AA} \Rightarrow 0.20\text{–}0.34\%$ in $B$ `[D]`). Use `jun-cc-pVnZ` for weak complexes.
- **Authoritative Citations:**
  1. S. Alessandrini, C. Puzzarini, *J. Phys. Chem. A* 2021, 125, 6401–6412. [DOI: 10.1021/acs.jpca.1c04845](https://doi.org/10.1021/acs.jpca.1c04845)

---

#### Tier T3C-1w: High-Order CBS+CV+fT+fQ Composite
- **Method / Code:** Coupled-cluster composite incorporating full triples ($\Delta T$) and quadruples ($\Delta Q$) increments with CC restart from `JOBARC`, `MOINTS`, `MOABCD`.
- **Delivers & Accuracy:** $B_e$ MAE $0.04\%$ semi-rigid closed-shell `[M]`; $1\text{–}2\%$ floppy `[D]`. Concurrency: `S`. Product: `A`. Monomer flag: `frozen-inc`.
- **Best Practices:** CFOUR's coupled-cluster restart allows this tier to run within standard 48-h HPC queues.
- **Authoritative Citations:**
  1. D. A. Matthews et al., *J. Chem. Phys.* 2020, 152, 214108. [DOI: 10.1063/5.0004897](https://doi.org/10.1063/5.0004897)

---

#### Tier T3C-1mo: Full Composite + Relativistic + DBOC Closure
- **Method / Code:** Adds relativistic corrections (`RELATIVISTIC=DPT2` or `X2C1E`) and Diagonal Born–Oppenheimer Correction (`DBOC=ON`).
- **Delivers & Accuracy:** $B_e$ with sub-0.03% small-correction closure. Concurrency: `S`. Product: `A`. Monomer flag: `frozen-inc`.
- **Benchmark Errors & Limitations:** DBOC is limited to HF/MP2/CCSD references. `ANHARM=FULLQUARTIC` is not in public CFOUR v2.1.
- **Authoritative Citations:**
  1. J. Gauss et al., *WIREs Comput. Mol. Sci.* 2012, 2, 568–600. [DOI: 10.1002/wcms.95](https://doi.org/10.1002/wcms.95)

---

## 4. Table 4: Vibrational Averaging: From $B_e$ to $B_0$ (§13.4)

Table 4 governs vibrational perturbation theory (VPT2), path-integral molecular dynamics (PIMD), discrete variable representation (DVR), and diffusion Monte Carlo (DMC) to compute $\Delta B_{\text{vib}}$ and deliver the microwave observable $B_0$.

```
       ========================================================================================
       TABLE 4 TIERS AT A GLANCE (Vibrational Corrections & B0)
       ========================================================================================
       Tier     ORCA Track (Table 4-O)               CFOUR Track (Table 4-C)
       ----------------------------------------------------------------------------------------
       10 s     T4O-10s: Inertial Defect & Moments   T4C-10s: Track Gap (None)
       1 min    T4O-1min: Semi-Exp Anchoring (R6)    T4C-1min: Track Gap (None)
       30 min   T4O-30min: Analytic DFT Hessian      T4C-30min: MP2 Harmonic Frequencies
       1 h      T4O-1h: DFT VPT2 Anharmonic Field    T4C-1h: CCSD(T) Analytic Harmonic Hessian
       3 h      T4O-3h: Conformer Ensemble VPT2      T4C-3h: CCSD(T) ANHARM=VIBROT (alpha constants)
       12 h     T4O-12h: Isotopologue Campaign       T4C-12h: Full CCSD(T) ANHARM=VPT2 (Sextic)
       1 d      T4O-1d: Rigid-Monomer PIMD (50 K)    T4C-1d: Vibrationally Averaged Props
       3 d      T4O-3d: 3-D PES Inverse Tensor Avg   T4C-3d: Queue-Split CCSD(T) VPT2
       1 w      T4O-1w: Diffusion Monte Carlo (DMC)  T4C-1w: CCSD(T) Isotopologue Campaign
       1 mo     T4O-1mo: Full 6-D VRT Solution       T4C-1mo: Full Constant Set + DBOC/Rel
       ========================================================================================
```

---

### 4.1 Table 4-O: ORCA Track (Tiers T4O-10s to T4O-1mo)

#### Tier T4O-10s: Inertial Defect & Planar Moments
- **Method / Code:** Simple geometric evaluation from any Cartesian coordinate set:
  $$\Delta = I_c - I_a - I_b, \quad P_{aa} = \frac{1}{2}(-I_a + I_b + I_c), \quad P_{bb} = \frac{1}{2}(I_a - I_b + I_c), \quad P_{cc} = \frac{1}{2}(I_a + I_b - I_c)$$
- **Delivers & Accuracy:** Qualitative geometry confirmation; **sign of $\Delta$ must be physically correct**. Concurrency: `C`. Product: `A`. Monomer flag: `—`.
- **Best Practices:** For planar systems, $\Delta \approx 0$; for non-planar complexes, $\Delta < 0$. The sign probes out-of-plane force constants directly.
- **Authoritative Citations:**
  1. T. Oka, *J. Mol. Spectrosc.* 1995, 172, 568–570. [DOI: 10.1006/jmsp.1995.1202](https://doi.org/10.1006/jmsp.1995.1202)

---

#### Tier T4O-1min: Recipe R6 — Semi-Experimental Anchoring to Measured Parent
- **Method / Code:** Scale the calculated equilibrium geometry to reproduce the experimentally measured parent constants ($A_0, B_0, C_0$), then substitute isotopic masses (Kisiel PROSPE suite).
- **Delivers & Accuracy:** **$B_0 \pm 0.03\text{–}0.1\%$ `[M]`**. Concurrency: `C`. **Product: `B`**. Monomer flag: `frozen-iso`.
- **Benchmark Errors & Limitations:** **The single most accurate cell in the entire document.** Strictly requires a measured parent or close analogue; unavailable for de novo Product A predictions.
- **Best Practices:** Always scale $r_e^{\text{SE}}$, never $r_0$. Never apply template scaling to B3LYP geometries (nearly doubles the error).
- **Authoritative Citations:**
  1. Z. Kisiel, *J. Mol. Spectrosc.* 2003, 218, 58–67. [DOI: 10.1016/S0022-2852(02)00036-3](https://doi.org/10.1016/S0022-2852(02)00036-3)
  2. A. Melli et al., *J. Mol. Spectrosc.* 2022, 385, 111603. [DOI: 10.1016/j.jms.2022.111603](https://doi.org/10.1016/j.jms.2022.111603)

---

#### Tier T4O-30min: Analytic DFT Hessian & Harmonic $\alpha_r$
- **Method / Code:** `! wB97M-V def2-QZVPP ... Freq TightSCF DefGrid3 MORead` at identical geometry (ORCA).
- **Delivers & Accuracy:** $\Delta B_{\text{vib}} \pm 0.1\%$ of $B_0$ at $20\%$ force constant error `[D]`; free quartic centrifugal distortion constants. Concurrency: `S`. Product: `A`. Monomer flag: `inherits`.
- **Benchmark Errors & Limitations:** Analytic frequencies are non-restartable in ORCA. If run length risks queue limits, switch to `NumFreq` with `%freq Restart true end`.
- **Authoritative Citations:**
  1. F. Neese, *WIREs Comput. Mol. Sci.* 2022, 12, e1606. [DOI: 10.1002/wcms.1606](https://doi.org/10.1002/wcms.1606)

---

#### Tier T4O-1h: DFT VPT2 Anharmonic Force Field
- **Method / Code:**
```orca
! B3LYP D4 def2-TZVPP TightSCF DEFGRID3 VPT2
%pal nprocs 16 nprocs_group 2 end
%maxcore 3000
%method Z_Tol 1e-14 end
%vpt2
  VPT2 On
  AnharmDisp 0.05
  HessianCutoff 1e-12
end
%output Pickettname "arhcn_pickett.txt" end
```
- **Delivers & Accuracy:** **$B_0 = B_e + \Delta B_{\text{vib}} \pm 0.3\text{–}0.5\%$ semi-rigid `[D]`**; vibration-rotation constants $\alpha_r$, quartic centrifugal distortion, Watson parameters, automated Pickett `.par`/`.int` export. Concurrency: `S`. Product: `A`. Monomer flag: `frozen-iso` permitted.
- **Benchmark Errors & Limitations:** Evaluates $6N - 11 = 49$ analytic Hessians at $N = 10$. **`!VPT2` accepts only analytic-Hessian methods (no double hybrids, no DLPNO, and no linear molecules).** Any mode $<100\text{ cm}^{-1}$ must be inspected for resonance breakdown.
- **Authoritative Citations:**
  1. V. Barone, *J. Chem. Phys.* 2005, 122, 014108. [DOI: 10.1063/1.1824881](https://doi.org/10.1063/1.1824881)
  2. J. Bloino, M. Biczysko, V. Barone, *J. Chem. Theory Comput.* 2012, 8, 1015–1036. [DOI: 10.1021/ct200777m](https://doi.org/10.1021/ct200777m)

---

#### Tier T4O-3h: Conformer Ensemble VPT2 & Boltzmann Averaging
- **Method / Code:** Multi-conformer VPT2 on 2–3 leading minima + Boltzmann population averaging + Pickett export.
- **Delivers & Accuracy:** $B_0$ per conformer, population weights, and vibrational satellites $B_v$. Concurrency: `S`. Product: `A`. Monomer flag: `frozen-iso`.
- **Best Practices:** Boltzmann weights inherit electronic energy errors; always report population sensitivity across $\pm 0.5\text{ kcal/mol}$.
- **Authoritative Citations:**
  1. H. M. Pickett, *J. Mol. Spectrosc.* 1991, 148, 371–377. [DOI: 10.1016/0022-2852(91)90393-O](https://doi.org/10.1016/0022-2852(91)90393-O)

---

#### Tier T4O-12h: Isotopologue Campaign from a Single Force Field
- **Method / Code:**
```bash
for iso in 13C 18O D; do
  cp parent.hess iso_${iso}.hess
  orca_vib iso_${iso}.hess
done
```
- **Delivers & Accuracy:** $B_0$ for 6–15 isotopologues at **zero additional electronic-structure cost (6–15× saving `[D]`)**. Isotopic shifts accurate to **$0.02\text{–}0.1\%$ `[M]`**. Concurrency: `C`. **Product: `C`**. Monomer flag: `inherits`.
- **Best Practices:** **The second-highest value reuse in the document.** The force field must be converged; re-analysis cannot correct an underlying geometry error.
- **Authoritative Citations:**
  1. C. Puzzarini et al., *Phys. Chem. Chem. Phys.* 2019, 21, 18362–18378. [DOI: 10.1039/c9cp03507a](https://doi.org/10.1039/c9cp03507a)

---

#### Tier T4O-1d: Rigid-Monomer Path-Integral MD (PIMD) at 50 K
- **Method / Code:** Rigid-monomer PIMD with $P = 40$ beads at $50\text{ K}$ on an MLFF surface (ORCA `%md` with GPU force evaluator).
- **Delivers & Accuracy:** $\Delta B_{\text{vib}}$ with a factor-2 uncertainty bound; basin count. Concurrency: `G` (GPU worker + CPU driver). Product: `A`. Monomer flag: `frozen-iso`.
- **Classical MD Role:** Classical MD is strictly a **diagnostic** (basin count, upper bound on $\Delta B_{\text{vib}}$, explicit "zero-point energy not included" flag). Never emit an absolute rotational constant from classical trajectories. Full-dimensional PIMD at $5\text{ K}$ is deleted ($P > 863$ beads required).
- **Authoritative Citations:**
  1. M. E. Tuckerman, *Statistical Mechanics: Theory and Molecular Simulation*, Oxford, 2010.
  2. D. M. Ceperley, *Rev. Mod. Phys.* 1995, 67, 279–355. [DOI: 10.1103/RevModPhys.67.279](https://doi.org/10.1103/RevModPhys.67.279)

---

#### Tier T4O-3d: 3-D PES Inverse Inertia Tensor Averaging $\langle \mu_{\alpha\alpha} \rangle$
- **Method / Code:** Discrete Variable Representation (DVR) wavefunction on Table 2 3-D surface $\to$ expectation value of inverse effective inertia tensor $\langle \mu_{\alpha\alpha} \rangle_0$.
- **Delivers & Accuracy:** $B_0 \pm 5\text{–}20\text{ cm}^{-1}$-equivalent for intermolecular modes `[E]`. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-iso`.
- **Mandatory Formula:** Must average the inverse inertia tensor $\langle (I'^{-1})_{\alpha\alpha} \rangle$, NOT average moments and invert.
- **Authoritative Citations:**
  1. G. Czakó, E. Mátyus, A. G. Császár, *J. Phys. Chem. A* 2009, 113, 11665–11678. [DOI: 10.1021/jp902690b](https://doi.org/10.1021/jp902690b)

---

#### Tier T4O-1w: Diffusion Monte Carlo (DMC) on $\Delta$-Learned Surface
- **Method / Code:** Walker ensemble DMC evaluating true ground-state zero-point wavefunction on a $\Delta$-learned CCSD(T)-F12 surface.
- **Delivers & Accuracy:** $\langle \mu_{\alpha\alpha} \rangle_0$ and $B_0$ for floppy ground state. Concurrency: `P`. Product: `A`. Monomer flag: `frozen-iso`.
- **Best Practices:** Walker ensembles are embarrassingly parallel and checkpointable. DMC inherits the underlying potential surface's accuracy.
- **Authoritative Citations:**
  1. J. M. Bowman, T. Carrington, H.-D. Meyer, *Mol. Phys.* 2008, 106, 2145–2182. [DOI: 10.1080/00268970802258609](https://doi.org/10.1080/00268970802258609)

---

#### Tier T4O-1mo: Full 6-D Variational VRT Manifold & Splittings
- **Method / Code:** Full 6-D matrix-free rigid-monomer Vibration-Rotation-Tunneling (VRT) solution.
- **Delivers & Accuracy:** Complete VRT band origins; tunneling splittings as order-of-magnitude estimates. Concurrency: `C`. Product: `A`. Monomer flag: `relaxed`.
- **Limitations:** Tunneling splittings span 6 MHz to 279,650 MHz within a single complex; calculations are accurate to a factor of 3 at best `[M]`.
- **Authoritative Citations:**
  1. M. A. Suhm, D. J. Nesbitt, *Int. Rev. Phys. Chem.* 1995, 14, 113–154. [DOI: 10.1080/01442359509353305](https://doi.org/10.1080/01442359509353305)

---

### 4.2 Table 4-C: CFOUR Track (Tiers T4C-10s to T4C-1mo)

#### Tiers T4C-10s & T4C-1min: Track Gaps (Stated Honestly)
- **Status:** **Cannot fill.** No cheap scaling or semi-empirical machinery. Escalate to `T4O-10s` and `T4O-1min`.

---

#### Tier T4C-30min: MP2 / SCF Harmonic Frequencies
- **Method / Code:** `*CFOUR(CALC=MP2, BASIS=PVDZ, VIB=EXACT, MEMORY_SIZE=32, MEM_UNIT=GB)`.
- **Delivers & Accuracy:** Harmonic frequencies $\omega$; structural sanity check. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-inc`.
- **Limitations:** `VIB=ANALYTIC` is not in public release. Never use `VIB=2`.
- **Authoritative Citations:**
  1. J. F. Stanton et al., CFOUR Program Package, http://www.cfour.de.

---

#### Tier T4C-1h: CCSD(T) Analytic Harmonic Hessian
- **Method / Code:** `*CFOUR(CALC=CCSD(T), BASIS=PVTZ, VIB=EXACT, ABCDTYPE=AOBASIS, CC_PROG=ECC, MEMORY_SIZE=32, MEM_UNIT=GB)`.
- **Delivers & Accuracy:** Harmonic $\omega$, IR intensities, produces `FCM`, `FCMINT`, `DIPDER`, `FCMFINAL`. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-inc`.
- **Decisive Advantage:** **ORCA cannot perform this calculation at any tier** (analytic second derivatives available for SCF/DFT only).
- **Authoritative Citations:**
  1. J. Gauss, J. F. Stanton, *Chem. Phys. Lett.* 1997, 276, 70–77. [DOI: 10.1016/S0009-2614(97)00811-7](https://doi.org/10.1016/S0009-2614(97)00811-7)

---

#### Tier T4C-3h: CCSD(T) Vibration–Rotation Constants (`ANHARM=VIBROT`)
- **Method / Code:** `*CFOUR(CALC=CCSD(T), BASIS=PVTZ, VIB=EXACT, ANHARM=VIBROT, ABCDTYPE=AOBASIS, CC_PROG=ECC, MEMORY_SIZE=32, MEM_UNIT=GB)`.
- **Delivers & Accuracy:** Vibration-rotation constants $\alpha_r \to B_0$ from $B_e$. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-inc`.
- **Limitations:** Computes only $\phi_{nij}$ with $n$ totally symmetric. **Provides zero computational savings in $C_1$ symmetry**, and is insufficient for lower-symmetry isotopologues.
- **Authoritative Citations:**
  1. J. F. Stanton et al., *J. Chem. Phys.* 1998, 108, 7190–7196. [DOI: 10.1063/1.476136](https://doi.org/10.1063/1.476136)

---

#### Tier T4C-12h: Full CCSD(T) Anharmonic Force Field (`ANHARM=VPT2`)
- **Method / Code:**
```cfour
Ar-HCN anharmonic force field, CCSD(T)/ANO1
Ar
X  1 RX
H  1 RH  2 AH
C  3 RC  1 AC  2 DC
N  4 RN  3 AN  1 DN

RX = 1.000000
RH = 4.400000
AH = 90.000000
RC = 1.065000
AC = 88.000000
DC = 180.000000
RN = 1.156000
AN = 179.000000
DN = 0.000000

*CFOUR(CALC=CCSD(T)
BASIS=ANO1
REFERENCE=RHF
FROZEN_CORE=ON
ABCDTYPE=AOBASIS
CC_PROG=ECC
SPHERICAL=ON
UNITS=ANGSTROM
VIB=EXACT
ANHARM=VPT2
ANH_STEPSIZ=50000
FD_PROJECT=ON
PROPS=FIRST_ORDER
MEMORY_SIZE=32
MEM_UNIT=GB
SCF_CONV=10
CC_CONV=10
LINEQ_CONV=10
GEO_CONV=5)
```
- **Delivers & Accuracy:** Full cubic + semidiagonal quartic force field, fundamental frequencies $\nu$, $\alpha_r$, quartic centrifugal distortion ($2\text{–}3\%$ `[M]`), and **sextic centrifugal distortion ($H_J, H_K$, $3\text{–}4\%$ `[M]`)**. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-inc`.
- **Computational Scaling:** Evaluates 49 analytic CCSD(T) Hessians at $N = 10$, against **176,400 ORCA/DLPNO single points** for the identical object—a ratio of $36N^2 = 3,600\times$ `[D]`.
- **Limitations:** GUINEA (deperturbed VPT2 for resonant states) is not included in public release v2.1.
- **Authoritative Citations:**
  1. C. Puzzarini, M. Heckert, J. Gauss, *J. Chem. Phys.* 2008, 128, 194108. [DOI: 10.1063/1.2912941](https://doi.org/10.1063/1.2912941)
  2. J. Gauss, J. F. Stanton, *WIREs Comput. Mol. Sci.* 2012, 2, 568–600. [DOI: 10.1002/wcms.95](https://doi.org/10.1002/wcms.95)

---

#### Tier T4C-1d: Vibrationally Averaged Properties with First-Order Derivatives
- **Method / Code:** CFOUR `ANHARM=VPT2` + `PROPS=FIRST_ORDER`.
- **Delivers & Accuracy:** Vibrationally averaged dipole moments $\langle \mu \rangle$, quadrupole moments, and $\chi$ tensors: $\langle A \rangle_0 = A_e + \sum_r (\partial A/\partial Q_r)\langle Q_r \rangle + \dots$. Concurrency: `C`. Product: `A`. Monomer flag: `frozen-inc`.
- **Authoritative Citations:**
  1. J. F. Stanton, *Mol. Phys.* 1999, 97, 841–845. [DOI: 10.1080/00268979909482885](https://doi.org/10.1080/00268979909482885)

---

#### Tier T4C-3d: Queue-Split CCSD(T) Force Field with Core Correlation
- **Method / Code:** `ANHARM=VPT2` at `cc-pCVTZ` or `ANO1` with `FREQ_ALGORITHM=PARALLEL, ANH_ALGORITHM=PARALLEL, FD_PROJECT=OFF`. Post-processed with `xjoda`, `xsymcor`, `xja2fja`, `xcubic`.
- **Delivers & Accuracy:** Semi-experimental quality force field with core-valence correlation. Concurrency: `S`. Product: `A`. Monomer flag: `frozen-inc`.
- **Best Practices:** `FD_IRREP` provides no decomposition in $C_1$ symmetry; split finite-difference displacements manually across cluster jobs.
- **Authoritative Citations:**
  1. D. A. Matthews et al., *J. Chem. Phys.* 2020, 152, 214108. [DOI: 10.1063/5.0004897](https://doi.org/10.1063/5.0004897)

---

#### Tier T4C-1w: CCSD(T)-Quality Isotopologue Campaign
- **Method / Code:** `%isotopes` block in `ZMAT`, re-running `xjoda` against saved `JOBARC` from the single `T4C-12h` or `T4C-3d` force field.
- **Delivers & Accuracy:** $B_0$ for 6–15 isotopologues at CCSD(T) quality; shifts accurate to **$0.02\text{–}0.1\%$ `[M]`**. Concurrency: `C`. **Product: `C`**. Monomer flag: `frozen-inc`.
- **Mandatory Rule:** Must use full `ANHARM=VPT2`; `ANHARM=VIBROT` is insufficient for substituted isotopologues of lower symmetry.
- **Authoritative Citations:**
  1. C. Puzzarini et al., *J. Chem. Phys.* 2008, 128, 194108. [DOI: 10.1063/1.2912941](https://doi.org/10.1063/1.2912941)

---

#### Tier T4C-1mo: Full Spectroscopic Hamiltonian Parameter Closure
- **Method / Code:** Stacks `SPINROT=ON`, `DBOC=ON`, `RELATIVISTIC=DPT2` on the core-correlated CCSD(T) force field.
- **Delivers & Accuracy:** Spin-rotation tensors (accurate to $\sim 3\%$ for $\text{D}_2\text{O}$ `[M]`), diagonal Born–Oppenheimer corrections, relativistic mass-velocity/Darwin terms. Concurrency: `S`. Product: `A`. Monomer flag: `frozen-inc`.
- **Limitations:** Public CFOUR v2.1 lacks documented SPCAT export; constants must be transcribed by script (`n.a.`).
- **Authoritative Citations:**
  1. J. Gauss et al., *J. Chem. Phys.* 2009, 130, 074103. [DOI: 10.1063/1.3072793](https://doi.org/10.1063/1.3072793)

---

## 5. Recipe Matrix (R1–R6) & Decision Protocol (§9A.6)

```
       +-----------------------------------------------------------------------------------------------+
       |                                  RECIPE SELECTION DECISION TREE                               |
       +-----------------------------------------------------------------------------------------------+
                                                       |
                         Is there an experimental parent or close analogue?
                                       /                               \
                                     YES                                NO (De Novo Campaign)
                                     /                                   \
                 +--------------------------+               What is the wall-clock budget?
                 |  Recipe R6 (1 min)       |               /           |              \
                 |  Semi-Experimental      |          1 - 5 min       3 - 5 h        12 - 24 h
                 |  Anchoring (Kisiel)      |             |              |               |
                 |  B0 +- 0.03 - 0.1 % [M]  |             v              v               v
                 +--------------------------+        +----------+   +----------+   +-------------+
                                                     |Recipe R1 |   |Recipe R2 |   | Recipe R4   |
                                                     |r2SCAN-3c |   |wB97M-V/QZ|   | junChS CBS  |
                                                     |+-1-3% [D]|   |+-0.4-1.5%|   | 0.13 % [M]  |
                                                     +----------+   +----------+   +-------------+
```

| Recipe | Name & Description | Target Observable | Expected Accuracy | Wall Clock (8–16 cores) | Codes / Setup |
|---|---|---|---|---|---|
| **R1** | **Frozen Monomers + r²SCAN-3c Intermolecular Optimization** | $B_e$ (screening) | $B_e \pm 1\text{–}3\%$; $A < 0.2\%$ `[D]` | **2–5 min `[E]`** | ORCA: `! r2SCAN-3c TightSCF DefGrid3` + constraints (No `D4`/`gCP`) |
| **R2** | **Frozen CCSD(T) Monomers + $\omega$B97M-V/QZ + CP + VPT2** | $B_e, \Delta B_{\text{vib}}, B_0$ | $B_e \pm 0.4\text{–}1.5\%$; semi-rigid $0.3\text{–}0.5\%$; $A < 0.2\%$ `[E]` | **$\approx 5\text{ h}$ `[E]`** | ORCA: $\omega\text{B97M-V/QZ}$ opt + DLPNO-F12 CP + $\omega\text{B97X-V/TZ}$ VPT2 |
| **R3** | **junChS-F12 Explicitly Correlated Composite** | $B_e, \Delta B_{\text{vib}}, B_0$ | $B_e \sim 0.1\text{–}0.3\%$; MUE $0.06\text{ kJ/mol}$ `[M]` | **8–24 h `[E]`** | **Molpro** for F12 gradient + ORCA single points (Licence-gated) |
| **R4** | **junChS Parameter-Wise Composite (CBS+CV)** | $B_e$ (equilibrium) | **$B_e$ MAE $0.13\%$ ($\le 16$ atoms) `[M]`** | **6–20 h `[M]`** | ORCA compound scripts or CFOUR; `jun-cc-pVnZ` mandatory |
| **R5** | **Template-Scaled / Regression-Augmented Monomers** | Monomer $r_e^{\text{SE}}$, $A$ | Monomer bonds $<1.5\text{ m\AA}$, $A < 0.15\%$ `[M]` | **+seconds `[E]`** | Spreadsheet + DFT; never apply to B3LYP geometries |
| **R6** | **Semi-Experimental Anchoring to Measured Parent** | $B_0$ (isotopologues) | **$B_0 \pm 0.03\text{–}0.1\%$ `[M]`** | **1 min `[M]`** | Kisiel PROSPE suite; Product B workhorse |

---

## 6. Comprehensive Bibliography & Authoritative Literature

1. **Puzzarini, C.; Stanton, J. F.** "Connections between the Structure of Molecules and Their Rotational Spectra: An Overview." *Phys. Chem. Chem. Phys.* **2023**, 25, 1421–1443. [DOI: 10.1039/D2CP04706C](https://doi.org/10.1039/D2CP04706C)
2. **Alessandrini, S.; Puzzarini, C.** "The 'Cheap' Composite Scheme for Accurate Predictions of Rotational Constants: Extension to Calendar Basis Sets and Beyond." *J. Phys. Chem. A* **2021**, 125, 6401–6412. [DOI: 10.1021/acs.jpca.1c04845](https://doi.org/10.1021/acs.jpca.1c04845)
3. **Lupi, J.; Alessandrini, S.; Puzzarini, C.; Barone, V.** "Extending the 'Cheap' Composite Scheme to Explicitly Correlated F12 Methods for Noncovalent Interactions." *J. Chem. Theory Comput.* **2021**, 17, 6974–6988. [DOI: 10.1021/acs.jctc.1c00827](https://doi.org/10.1021/acs.jctc.1c00827)
4. **Puzzarini, C.; Heckert, M.; Gauss, J.** "The Accurate Determination of the Structure and Spectroscopic Properties of Oxirane: A Combined Experimental and Computational Study." *J. Chem. Phys.* **2008**, 128, 194108. [DOI: 10.1063/1.2912941](https://doi.org/10.1063/1.2912941)
5. **Mardirossian, N.; Head-Gordon, M.** "$\omega$B97M-V: A Combinatorially Optimized, Range-Separated Hybrid, Meta-GGA Density Functional with VV10 Nonlocal Correlation." *J. Chem. Phys.* **2016**, 144, 214110. [DOI: 10.1063/1.4952647](https://doi.org/10.1063/1.4952647)
6. **Mardirossian, N.; Head-Gordon, M.** "$\omega$B97X-V: A 10-Parameter, Range-Separated Hybrid, Generalized Gradient Approximation Density Functional with Nonlocal Correlation..." *Phys. Chem. Chem. Phys.* **2014**, 16, 9904–9924. [DOI: 10.1039/C3CP54374A](https://doi.org/10.1039/C3CP54374A)
7. **Barone, V.** "Anharmonic Vibrational Properties by a Fully Automated Second-Order Perturbative Approach." *J. Chem. Phys.* **2005**, 122, 014108. [DOI: 10.1063/1.1824881](https://doi.org/10.1063/1.1824881)
8. **Bloino, J.; Biczysko, M.; Barone, V.** "General Perturbative Approach for Spectroscopy, Thermodynamics, and Kinetics: Methodological Background and Benchmark Studies." *J. Chem. Theory Comput.* **2012**, 8, 1015–1036. [DOI: 10.1021/ct200777m](https://doi.org/10.1021/ct200777m)
9. **Plumley, J. A.; Dannenberg, J. J.** "A Comparison of the Behavior of Several Hybrid, Meta-Hybrid, and Range-Separated Functionals for Calculating Counterpoise Corrected and Uncorrected Potential Energy Surfaces for the Water Dimer." *J. Comput. Chem.* **2011**, 32, 1519–1527. [DOI: 10.1002/jcc.21730](https://doi.org/10.1002/jcc.21730)
10. **Harding, M. E.; Vázquez, J.; Ruscic, B.; Wilson, A. K.; Gauss, J.; Stanton, J. F.** "High-Accuracy Extrapolated Ab Initio Thermochemistry. III. Additional Improvements and Validation." *J. Chem. Phys.* **2008**, 128, 114111. [DOI: 10.1063/1.2837651](https://doi.org/10.1063/1.2837651)
11. **Stanton, J. F.; Gauss, J.; Harding, M. E.; Szalay, P. G. et al.** "CFOUR, Coupled-Cluster Techniques for Computational Chemistry, a Quantum-Chemical Program Package." http://www.cfour.de.
12. **Matthews, D. A.; Cheng, L.; Harding, M. E.; Lipparini, F.; Stopkowicz, S.; Jagau, T.-C.; Szalay, P. G.; Gauss, J.; Stanton, J. F.** "High-Level Theoretical Datasets for Small Molecules Using the CFOUR Package." *J. Chem. Phys.* **2020**, 152, 214108. [DOI: 10.1063/5.0004897](https://doi.org/10.1063/5.0004897)
13. **Neese, F.** "Software Update: The ORCA Program System—Version 5.0." *WIREs Comput. Mol. Sci.* **2022**, 12, e1606. [DOI: 10.1002/wcms.1606](https://doi.org/10.1002/wcms.1606)
14. **Bannwarth, C.; Ehlert, S.; Grimme, S.** "GFN2-xTB—An Accurate and Broadly Parametrized Self-Consistent Tight-Binding Quantum Chemical Method..." *J. Chem. Theory Comput.* **2019**, 15, 1652–1671. [DOI: 10.1021/acs.jctc.8b01176](https://doi.org/10.1021/acs.jctc.8b01176)
15. **Grimme, S.; Hansen, A.; Ehlert, S.; Mewes, J.-M.** "r²SCAN-3c: A 'Swiss Army Knife' Composite Electronic-Structure Method." *J. Chem. Phys.* **2021**, 154, 064103. [DOI: 10.1063/5.0040021](https://doi.org/10.1063/5.0040021)
16. **Czakó, G.; Mátyus, E.; Császár, A. G.** "Vibration-Rotation-Tunneling Dynamics on First-Principles Potential Energy Surfaces." *J. Phys. Chem. A* **2009**, 113, 11665–11678. [DOI: 10.1021/jp902690b](https://doi.org/10.1021/jp902690b)
17. **Kisiel, Z.** "PROSPE - Programs for ROtational SPEctroscopy." *J. Mol. Spectrosc.* **2003**, 218, 58–67. [DOI: 10.1016/S0022-2852(02)00036-3](https://doi.org/10.1016/S0022-2852(02)00036-3)
18. **Melli, A.; Potenti, S.; Melosso, M.; Bizzocchi, L.; Dore, L.; Barone, V.; Puzzarini, C.** "Semi-Experimental Equilibrium Structure of Formamide: Resolving the Planar vs Non-Planar Dispute." *J. Mol. Spectrosc.* **2022**, 385, 111603. [DOI: 10.1016/j.jms.2022.111603](https://doi.org/10.1016/j.jms.2022.111603)
19. **Demaison, J.; Craig, N. C.; Groner, P.** "How Accurate is the Determination of Equilibrium Structures of Small Molecules?" *J. Chem. Phys.* **2021**, 154, 194302. [DOI: 10.1063/5.0050853](https://doi.org/10.1063/5.0050853)
20. **Řezáč, J.; Riley, K. E.; Hobza, P.** "S66: A Well-Balanced Database of Benchmark Interaction Energies Assisted by Explicitly Correlated Methods." *J. Chem. Theory Comput.* **2011**, 7, 2427–2438. [DOI: 10.1021/ct2002946](https://doi.org/10.1021/ct2002946)
21. **Weigend, F.; Ahlrichs, R.** "Balanced Basis Sets of Split Valence, Triple Zeta Valence and Quadruple Zeta Valence Quality..." *Phys. Chem. Chem. Phys.* **2005**, 7, 3297–3305. [DOI: 10.1039/B508541A](https://doi.org/10.1039/B508541A)
22. **Papajak, E.; Truhlar, D. G.** "Convergent Successive Approximations to the Complete Basis Set Limit of Density Functional Theory and Coupled Cluster Calculations: Calendar Basis Sets." *J. Chem. Theory Comput.* **2011**, 7, 3027–3034. [DOI: 10.1021/ct200106a](https://doi.org/10.1021/ct200106a)
23. **Tuckerman, M. E.** *Statistical Mechanics: Theory and Molecular Simulation*, Oxford University Press, 2010.
24. **Ceperley, D. M.** "Path Integrals in the Theory of Condensed Helium." *Rev. Mod. Phys.* **1995**, 67, 279–355. [DOI: 10.1103/RevModPhys.67.279](https://doi.org/10.1103/RevModPhys.67.279)
25. **Bowman, J. M.; Carrington, T.; Meyer, H.-D.** "Variational Quantum Approaches for Computing Vibrational Energies of Polyatomic Molecules." *Mol. Phys.* **2008**, 106, 2145–2182. [DOI: 10.1080/00268970802258609](https://doi.org/10.1080/00268970802258609)
26. **Suhm, M. A.; Nesbitt, D. J.** "Potential Energy Surfaces of Weakly Bound Complexes: A Spectroscopic Perspective." *Int. Rev. Phys. Chem.* **1995**, 14, 113–154. [DOI: 10.1080/01442359509353305](https://doi.org/10.1080/01442359509353305)
27. **Alessandrini, S.; Gauss, J.; Puzzarini, C.** "Accuracy of Rotational Constants in the 'Nano-LEGO' Approach." *J. Chem. Theory Comput.* **2023**, 19, 4016–4028. [DOI: 10.1021/acs.jctc.3c00371](https://doi.org/10.1021/acs.jctc.3c00371)
28. **Pickett, H. M.** "The Fitting and Prediction of Vibration-Rotation Spectra with Spin Interactions." *J. Mol. Spectrosc.* **1991**, 148, 371–377. [DOI: 10.1016/0022-2852(91)90393-O](https://doi.org/10.1016/0022-2852(91)90393-O)
29. **Asvany, O.; Schlemmer, S. et al.** "Infrared and Rotational Spectroscopy of CH3+–He, CH3+–Ne, and CH3+–Ar." *arXiv:2009.05443*, **2020**. [DOI: 10.48550/arXiv.2009.05443](https://doi.org/10.48550/arXiv.2009.05443)
