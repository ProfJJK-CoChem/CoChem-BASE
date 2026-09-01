# T1 Research: Topology & Conformer Search Methods

This document provides a comprehensive analysis of the computational methods, accuracy benchmarks, execution protocols, and authoritative literature supporting the ten wall-clock tiers of **Table 1 (Conformer and Isomer Search)** in the CoChem Method Matrix (§13.1).

---

## 1. Overview of Table 1 & Search Architecture

Table 1 governs the discovery and structural enumeration of non-covalent complexes and flexible molecules across ten wall-clock tiers (from 10 seconds to 1 month). The table operates on a single track (ORCA 6.1 and its satellite tools, including CREST and `orca-external-tools`).

### Key Invariants & Protocols:
1. **The Scout-and-Anchor Concurrent Search Architecture (§8A.2):** For any new complex, exploration runs concurrently across two devices from identical seeds: CPU-bound semi-empirical GOAT (`! GOAT XTB2`) paired with GPU-accelerated MLFF GOAT (`! GOAT-EXPLORE ExtOpt` via `oet_server aimnet2 -d cuda`). This scout-and-anchor paradigm explores distinct potential surfaces simultaneously for zero additional wall-clock time.
2. **Two-Stage Deduplication Protocol (§9B.3, §13.1):**
   - **Stage A (Broad Structural Filtering):** Executed at engine defaults during early enumeration (RMSD $0.125\text{ \AA}$, $\Delta E = 0.100\text{ kcal/mol}$, $\Delta B = 1.0\text{–}2.5\%$).
   - **Stage B (Spectroscopic Deduplication Mandate):** Executed after QM re-optimization using CREGEN with the tightened rotational constant threshold `--bthr 0.001` ($0.1\% \approx 12\text{ MHz}$ at $12\text{ GHz}$). Default CREGEN/GOAT thresholds (`--bthr 0.01` or $1\% \approx 120\text{ MHz}$) are ten times too coarse for chirped-pulse Fourier transform microwave (CP-FTMW) rotational spectroscopy.
3. **The Completeness Argument:** Global optimization algorithms (GOAT and CREST) are stochastic heuristics; neither provides a mathematical completeness proof. For small complexes (5–10 atoms), exhaustive hand-enumeration of binding topologies is the only protocol capable of supporting a true completeness claim.

---

## 2. Detailed Breakdown of the Ten Table 1 Tiers

### Tier T1-10s: Hand-Enumerated Binding Topologies
- **Method / Code:** Hand-enumerated binding topologies followed by `! XTB2 TightOpt` (or `xtb --opt vtight --strict`) per seed (ORCA / xtb).
- **Delivers & Accuracy:** Generates an ensemble of 3–9 pre-optimized candidate seeds; **no accuracy claim**. Semi-empirical tight-binding intermonomer separations carry systematic errors; on the S22 non-covalent benchmark, GFN2-xTB exhibits a maximum center-of-mass error of $32\text{ pm}$ ($\approx 14\%$ error in rotational constant $B$).
- **Best Practices:** Hand enumeration across all plausible binding sites is the sole foundation for completeness in van der Waals complexes (e.g., HFIP$\cdots$Ne/Ar). In automated toolchains, pass `--strict` to trap convergence anomalies. Semi-empirical geometries and energies must never be used directly for final reported spectroscopic constants.
- **Authoritative Citations:**
  - C. Bannwarth, S. Ehlert, S. Grimme, "GFN2-xTB—An Accurate and Broadly Parametrized Self-Consistent Tight-Binding Quantum Chemical Method with Multipole Electrostatics and Density-Dependent Dispersion Contributions," *J. Chem. Theory Comput.* 2019, 15, 3, 1652–1671. [DOI: 10.1021/acs.jctc.8b01176](https://doi.org/10.1021/acs.jctc.8b01176)
  - S. Grimme, C. Bannwarth, P. Shushkov, "A Robust and Accurate Tight-Binding Quantum Chemical Method for Structures, Vibrational Frequencies, and Noncovalent Interactions of Large Molecular Systems Approaching DFT Quality (GFN-xTB)," *J. Chem. Theory Comput.* 2017, 13, 5, 1989–2009. [DOI: 10.1021/acs.jctc.7b00118](https://doi.org/10.1021/acs.jctc.7b00118)

---

### Tier T1-1min: Automated Semi-Empirical GOAT Search
- **Method / Code:** `! GOAT XTB2 PAL8`, GFN-FF uphill push (`%goat maxen 12.0 confdegen auto gfnuphill gfnff end` in ORCA).
- **Delivers & Accuracy:** Full GOAT conformer ensemble at $N \le 10$ atoms ($\sim 100 \times N_{\text{at}}$ optimizations). Qualitative semi-empirical energetic ranking only.
- **Best Practices:** Explicitly declare `maxen 12.0` in the `%goat` block to resolve the documentation ambiguity between the ORCA manual table ($6.0\text{ kcal/mol}$) and descriptive text ($12.0\text{ kcal/mol}$). Set `confdegen auto` because GOAT defaults to $g_i = 1$. Restrict GFN-FF to early Stage A topological breadth generation.
- **Authoritative Citations:**
  - S. Spicher, S. Grimme, "Robust atomistic modeling of materials, organometallic and biochemical systems," *Angew. Chem. Int. Ed.* 2020, 59, 15665–15673. [DOI: 10.1002/anie.202004239](https://doi.org/10.1002/anie.202004239)
  - F. Neese et al., *ORCA 6.1 Manual: Geometry Optimization and Application Tool (GOAT)*, Max-Planck-Institut für Kohlenforschung / FACCTS GmbH, 2024.

---

### Tier T1-30min: MLFF-Driven GOAT Free-Topology Exploration
- **Method / Code:** `! GOAT-EXPLORE ExtOpt TightOpt PAL8` + `%scf TolE 1e-5 end` + `oet_server aimnet2 -d cuda` (ORCA + AIMNet2 via `orca-external-tools`).
- **Delivers & Accuracy:** Free-topology exploration across multiple seeds in parallel; Stage A deduplication executes here. Machine learning force fields suffer from single-precision (FP32) floating-point noise ($\sim 4 \times 10^{-6}\text{ Eh}$) and non-covalent interaction energy errors of **$3.5\text{–}7.3\text{ kcal/mol}$ on S30L** and **$29.9\text{ kcal/mol}$ on PLA15**.
- **Best Practices & Execution Guards (§9B.4):**
  - **Numerical Noise Guard:** Must pair `! TightOpt` with `%scf TolE 1e-5 end`. Because FP32 noise ($\sim 4 \times 10^{-6}\text{ Eh}$) sits at or below ORCA's default `TolE = 5e-6 Eh`, unadjusted thresholds cause the optimizer to chatter and trap in numerical noise.
  - **Window Parameter Guard:** Mandate explicit `maxen 12.0` in the `%goat` block.
  - **Persistent Server Architecture:** Standalone execution re-imports the PyTorch stack on every gradient evaluation ($\sim 30\text{ s}$ per call vs $\sim 48\text{ ms}$ in steady state). Over $\sim 100 \times N_{\text{at}}$ calls, running `oet_server aimnet2 --nthreads 4 -d cuda &` paired with `oet_client` is mandatory.
  - **Virtual Environment Isolation:** AIMNet2 and UMA (`fairchem`) have mutually incompatible dependencies; maintain strictly isolated Python $\ge 3.11$ virtual environments.
  - **Strict Role Invariant:** MLFFs are rapid enumerators, never energetic judges. Never report MLFF geometries or energetic rankings as final results; escalate all unique candidates to DFT.
- **Authoritative Citations:**
  - D. M. Anstine, R. Zubatyuk, O. Isayev, "AIMNet2: a neural network potential to meet your neutral, charged, organic, and elemental-organic needs," *Chem. Sci.* 2025, 16(23), 10228–10244. [DOI: 10.1039/D4SC08572H](https://doi.org/10.1039/D4SC08572H)
  - I. Batatia et al., "MACE-POLAR-1: Accurate Intermolecular and Polarization Modeling via Equivariant Neural Potentials," *arXiv:2602.19411*, 2026.

---

### Tier T1-1h: CREST Metadynamics Sampling
- **Method / Code:** `crest seed.xyz --nci --gfn2 --ewin 12 --nocross --noreftopo --T 8` (CREST).
- **Delivers & Accuracy:** Independent second ensemble via root-mean-square Cartesian metadynamics (iMTD-GC). Vulnerable to starting-structure sensitivity (capable of missing basins up to $50\text{ kJ/mol}$ lower than the input seed) and Cartesian bias that can disrupt hydrogen bonds and dissociate weak complexes after $\sim 4.2\text{ ps}$.
- **Best Practices & Cluster Flag Invariants (§9B.3):**
  - **`--noreftopo` Flag Mandate:** By default, CREGEN discards structures whose bond topology differs from the input. In non-covalent cluster and isomer searches, changed contact topology is the true physical signal; disabling topology filtering via `--noreftopo` is mandatory.
  - **`--nocross` Flag Mandate:** Disables genetic crossing, which operates correctly on isolated covalent molecules but corrupts non-covalent cluster geometries.
  - **`--nci` Mode & Bias Attenuation:** Auto-applies ellipsoidal bounding walls; if dissociation persists, reduce push bias (`--wscal 0.9` or reduced `kpush`).
  - Deploy $\ge 3$ chemically distinct starting structures and combine results into a union ensemble with GOAT.
- **Authoritative Citations:**
  - P. Pracht, S. Grimme, C. Bannwarth et al., "CREST—A program for the exploration of low-energy molecular chemical space," *J. Chem. Phys.* 2024, 160, 114110. [DOI: 10.1063/5.0197592](https://doi.org/10.1063/5.0197592)
  - S. Grimme, "Exploration of Chemical Compound, Conformer, and Reaction Space with Meta-Dynamics Simulations Based on Tight-Binding Quantum Chemical Methods," *J. Chem. Theory Comput.* 2019, 15, 5, 2847–2862. [DOI: 10.1021/acs.jctc.9b00143](https://doi.org/10.1021/acs.jctc.9b00143)

---

### Tier T1-3h: Union Merge, Screening, r²SCAN-3c Optimization & Spectroscopic Deduplication
- **Method / Code:** Union merge (`cat *.finalensemble.xyz crest_conformers.xyz > union.xyz`) $\to$ `crest --screen union.xyz --gfn2 --ewin 12 --T 8` $\to$ `! r2SCAN-3c TightOpt Freq TightSCF DefGrid3` $\to$ `crest --cregen … --bthr 0.001` (CREST + ORCA).
- **Delivers & Accuracy:** Production deduplicated QM ensemble; executes **Stage B deduplication**. Relative ensemble energies accurate to $\pm 1\text{–}3\text{ kcal/mol}$. Rotational constant errors across the ROT34 benchmark drop to $A_{\text{MAX}} \approx 1.5\%$.
- **Best Practices & Stage B Protocol Mandate (§9B.3, §13.1):**
  - **Tightened Spectroscopic Deduplication:** Stage B deduplication requires `--bthr 0.001` ($0.1\% \approx 12\text{ MHz}$ at $12\text{ GHz}$). Default CREGEN/GOAT thresholds (`--bthr 0.01` or $1\% \approx 120\text{ MHz}$) are 10$\times$ too coarse for rotational spectroscopy and will falsely collapse distinguishable microwave isomers.
  - **Common-Level Re-Optimization:** Re-optimize the entire pooled union at one common QM level (r²SCAN-3c) *before* CREGEN clustering to eliminate artifacts from differing engine conventions.
  - **Composite Keyword Rules:** Do not append `D4` or `gCP` keywords; the r²SCAN-3c method inherently includes customized D4 dispersion and geometrical counterpoise corrections.
  - **Diagnostic Reporting:** Report the number of conformers found by GOAT alone, by CREST alone, the overlap count, and the final union count.
- **Authoritative Citations:**
  - S. Grimme, A. Hansen, S. Ehlert, J.-M. Mewes, "r2SCAN-3c: A 'Swiss army knife' composite electronic-structure method," *J. Chem. Phys.* 2021, 154, 064103. [DOI: 10.1063/5.0040021](https://doi.org/10.1063/5.0040021)
  - J. W. Furness, A. D. Kaplan, J. Ning, J. P. Perdew, J. Sun, "Accurate and Numerically Efficient r2SCAN Meta-Generalized Gradient Approximation," *J. Phys. Chem. Lett.* 2020, 11, 8208–8215. [DOI: 10.1021/acs.jpclett.0c02405](https://doi.org/10.1021/acs.jpclett.0c02405)

---

### Tier T1-12h: QM-Level GOAT Refinement
- **Method / Code:** `! GOAT r2SCAN-3c` + `%PAL NPROCS 16` on the 2–3 leading isomers (ORCA).
- **Delivers & Accuracy:** Refined QM-level potential energy surface search around assigned candidate minima, yielding converged wavefunctions (`.gbw`) per conformer.
- **Best Practices:** r²SCAN-3c GOAT incurs substantial computational cost at DFT level. ORCA official guidelines recommend 32 cores and warn of multi-day runtimes for unconstrained searches. If thread allocation is restricted to 16 cores, deploy `GOAT-COARSE` with rigid monomer fragments to restrict sampling to the 6 intermolecular degrees of freedom.
- **Authoritative Citations:**
  - F. Neese, "Software update: The ORCA program system—Version 5.0," *WIREs Comput. Mol. Sci.* 2022, 12, e1606. [DOI: 10.1002/wcms.1606](https://doi.org/10.1002/wcms.1606)

---

### Tier T1-1d: Entropy Convergence Tier
- **Method / Code:** `! GOAT-ENTROPY XTB2` + `crest --entropy` on identical seeds (ORCA + CREST).
- **Delivers & Accuracy:** Quantitative **evidence of conformational convergence**: establishes $\Delta S_{\text{conf}} < 0.1\text{ cal}\cdot\text{mol}^{-1}\cdot\text{K}^{-1}$ against a converged CREST ensemble entropy.
- **Best Practices:** This tier produces rigorous statistical convergence diagnostics rather than new geometric minima. Crucially, the $S_{\text{conf}}$ values from GOAT and CREST cannot be compared directly unless `CONFDEGEN auto` is specified in GOAT (as GOAT defaults to $g_i = 1$, whereas CREST automatically folds rotamer degeneracies into $S_{\text{conf}}$).
- **Authoritative Citations:**
  - S. Grimme, "Exploration of Chemical Space for Determining Conformational Ensembles, Free Energies, and Conformational Entropy," *Chem. Sci.* 2019, 10, 6062–6071. [DOI: 10.1039/C9SC01919J](https://doi.org/10.1039/C9SC01919J)

---

### Tier T1-3d: $\omega$B97X-V / def2-TZVPP Refinement & Rare-Gas Benchmark Realities
- **Method / Code:** `! wB97X-V def2-TZVPP def2/J RIJCOSX TightOpt TightSCF DEFGRID3` + §4.4 `%geom` + `InHess XTB2` on Stage-B survivors (ORCA). No new searching.
- **Delivers & Accuracy:** Production equilibrium geometries capable of feeding a $0.1\%$ rotational constant target ($B_e$); relative energies accurate to $\Delta E \pm 0.3\text{–}1.0\text{ kcal/mol}$.
- **Rare-Gas Benchmark Realities (§12.5 Rule 3, §13.3):**
  - **$\omega\text{B97X-V}$ Accuracy:** For the non-covalent A21 benchmark set, $\omega\text{B97X-V}$ achieves an RMSD of **$0.58\text{ pm}$**, and on ultra-weak rare-gas dispersion complexes, its RMSD is **$7.91\text{ pm}$**.
  - **The $\omega\text{B97X-D}$ Out-of-Domain Failure:** The older $\omega\text{B97X-D}$ functional exhibits a catastrophic 60-fold degradation from $0.58\text{ pm}$ on A21 to **$36.34\text{ pm}$ ($0.363\text{ \AA}$)** on rare gases, demonstrating how standard GMTKN55/S66 benchmarks fail out-of-domain for ultra-weak dispersion complexes.
  - *Fact Check:* Never confuse the $36.34\text{ pm}$ error of $\omega\text{B97X-D}$ with $\omega\text{B97X-V}$.
- **Best Practices:** Pair with `TightSCF`, `DEFGRID3`, and utilize an xTB model Hessian (`InHess XTB2`) or an MLFF Hessian (`.carthess`, §8A.3) to reduce geometry optimization cycles by $2.0\text{–}2.5\times$. Never append empirical D3/D4 dispersion corrections (the VV10 non-local correlation functional is built-in).
- **Authoritative Citations:**
  - N. Mardirossian, M. Head-Gordon, "$\omega$B97X-V: A 10-parameter, range-separated hybrid, generalized gradient approximation density functional with nonlocal correlation, designed by a survival-of-the-fittest strategy," *Phys. Chem. Chem. Phys.* 2014, 16, 9904–9924. [DOI: 10.1039/c3cp54374a](https://doi.org/10.1039/c3cp54374a)
  - F. Weigend, R. Ahlrichs, "Balanced basis sets of split valence, triple zeta valence and quadruple zeta valence quality for H to Rn: Design and assessment of accuracy," *Phys. Chem. Chem. Phys.* 2005, 7, 3297–3305. [DOI: 10.1039/B508541A](https://doi.org/10.1039/B508541A)

---

### Tier T1-1w: MACE / Foundation Model Fine-Tuning
- **Method / Code:** Fine-tune MACE (`mace_run_train --foundation_model=small --multiheads_finetuning=True`) or AIMNet2 on 100–500 system-specific DFT single points, then re-execute GOAT + CREST (MACE + ORCA).
- **Delivers & Accuracy:** Reusable fine-tuned machine learning potential checkpoint; provides high-coverage insurance against missed local basins.
- **Best Practices:** Multihead fine-tuning and replay buffers are mandatory to prevent catastrophic forgetting of baseline potential features. This tier is experimental: required dataset sizes are system-dependent (`n.a.`). Fine-tuning provides sampling breadth but does not bypass the requirement for final ab initio DFT/CCSD(T) structural optimization.
- **Authoritative Citations:**
  - I. Batatia, D. P. Kovács, G. N. C. Simm, C. Ortner, G. Csányi, "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields," *Advances in Neural Information Processing Systems (NeurIPS)* 2022, 35, 11423–11436. [DOI: 10.48550/arXiv.2206.07697](https://doi.org/10.48550/arXiv.2206.07697)
  - D. P. Kovács et al., "Evaluation of the MACE Force Field Architecture by Fitting on the SPICE Dataset," *J. Chem. Theory Comput.* 2023, 19, 12, 3508–3519. [DOI: 10.1021/acs.jctc.3c00347](https://doi.org/10.1021/acs.jctc.3c00347)

---

### Tier T1-1mo: Exhaustive Union Completeness & Pareto Dominance
- **Method / Code:** Exhaustive multi-seed $\times$ multi-engine (GOAT + CREST) $\times$ `--v4` / `GOAT-DIVERSITY` union, followed by DLPNO-CCSD(T1)/CBS re-ranking.
- **Delivers & Accuracy:** The theoretical maximum coverage claim and completeness ceiling obtainable via automated search workflows.
- **Best Practices & Pareto Dominance (§8A.2, §13.1):**
  - **Pareto-Dominated Status:** This exhaustive tier is largely superseded and Pareto-dominated for reported observables by the concurrent two-device scout-and-anchor pipeline (§8A.2), which achieves comparable ensemble diversity at a fraction of the wall-clock time.
  - Retain strictly as an ultimate fallback and completeness insurance for complex, multi-well non-covalent potential energy landscapes.
- **Authoritative Citations:**
  - C. Riplinger, F. Neese, "An efficient and near linear scaling pair natural orbital based local coupled cluster method," *J. Chem. Phys.* 2013, 138, 034106. [DOI: 10.1063/1.4773581](https://doi.org/10.1063/1.4773581)
  - C. Riplinger, B. Sandhoefer, A. Hansen, F. Neese, "Natural triple excitations in local coupled cluster calculations with pair natural orbitals," *J. Chem. Phys.* 2013, 139, 134101. [DOI: 10.1063/1.4821834](https://doi.org/10.1063/1.4821834)
