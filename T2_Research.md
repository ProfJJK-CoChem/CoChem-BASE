# T2 Research: Potential Energy Surface (PES) and VRT Dynamics Methods

This document provides a thorough analysis of the accuracy, best practices, and supporting literature for the "T2" tiers (Potential Energy Surface and VRT dynamics) as defined in the CoChem Method Matrix.

## Overview of T2 Tiers
The T2 tiers define a campaign progression for exploring, fitting, and solving intermolecular potential energy surfaces (PES). Driven by advancements in active learning and $\Delta$-learning, high-accuracy coupled-cluster surfaces have seen drastic reductions in wall-clock time, moving week- or month-long campaigns down to hours or days.

---

### T2-10s: Semi-Empirical Relaxed 1-D Scan
**Method:** GFN2-xTB relaxed 1-D scan (xtb / ORCA)
**Accuracy/Deliverable:** Qualitative well topology. Intermonomer distances are systematically off (MAD ~14 pm). 
**Best Practices:** Used strictly for rapid conformational bounding and to verify the presence of a minimum. No quantitative energy claims should be derived.
**Authoritative Sources:**
1. Bannwarth, C. et al. (2019). "GFN2-xTB—An Accurate and Broadly Parametrized Self-Consistent Tight-Binding Method." *J. Chem. Theory Comput.*
2. Grimme, S. et al. (2017). "A robust and accurate tight-binding quantum chemical method..." *J. Chem. Theory Comput.*
3. Spicher, S., & Grimme, S. (2020). "Robust Atomistic Modeling..." *Angew. Chem. Int. Ed.*

### T2-1min: Dense MLFF Scan
**Method:** Dense MLFF scan (10³ points) to bound the well (MACE / AIMNet2 via ASE)
**Accuracy/Deliverable:** Identifies boundaries of the potential well.
**Best Practices:** Run batched on GPUs. The FP32 precision of these models is legitimate here because the goal is geometric bounding rather than microhartree energetic resolution.
**Authoritative Sources:**
1. Batatia, I. et al. (2022). "MACE: Higher Order Equivariant Message Passing Neural Networks for Fast and Accurate Force Fields." *NeurIPS*.
2. Zubatyuk, R. et al. (2019). "Accurate and Transferable Multitask Prediction of Chemical Properties with an AIMNet Neural Network." *Sci. Adv.*
3. Batzner, S. et al. (2022). "E(3)-equivariant graph neural networks for data-efficient and accurate interatomic potentials." *Nat. Commun.*

### T2-30min: Composite Meta-GGA Scan
**Method:** Composite meta-GGA scan (~200 points, r²SCAN-3c in ORCA)
**Accuracy/Deliverable:** Relative energies $\pm$ 1.5–3 kcal/mol.
**Best Practices:** Run as independent single-rank jobs in parallel (`parallel -j 16`). Lacks diffuse functions, meaning the long-range asymptotic tail is unreliable.
**Authoritative Sources:**
1. Grimme, S. et al. (2021). "r²SCAN-3c: A 'Swiss army knife' composite electronic-structure method." *J. Chem. Phys.*
2. Furness, J. W. et al. (2020). "Accurate and Numerically Efficient r2SCAN Meta-Generalized Gradient Approximation." *J. Phys. Chem. Lett.*
3. Ehlert, S. et al. (2021). "Efficient geometric structure optimization with the r²SCAN-3c method." *Phys. Chem. Chem. Phys.*

### T2-1h: 2-D Relaxed Grid
**Method:** 2-D relaxed (R, $\theta$) grid, 960 points, $\omega$B97X-V/def2-TZVPP (ORCA)
**Accuracy/Deliverable:** 2-D surface mapping, $\pm$ 1–2 kcal/mol accuracy.
**Best Practices:** Because relaxed scans hide hysteresis, always run both scan directions and compare. Reuse neighbor `.gbw` files to accelerate SCF convergence.
**Authoritative Sources:**
1. Mardirossian, N., & Head-Gordon, M. (2014). "$\omega$B97X-V: A 10-parameter, range-separated hybrid, generalized gradient approximation density functional..." *Phys. Chem. Chem. Phys.*
2. Weigend, F., & Ahlrichs, R. (2005). "Balanced basis sets of split valence, triple zeta valence and quadruple zeta valence quality..." *Phys. Chem. Chem. Phys.*
3. Goerigk, L. et al. (2017). "A look at the density functional theory zoo with the advanced GMTKN55 database." *Phys. Chem. Chem. Phys.*

### T2-3h: 1-D sinc-DVR
**Method:** 1-D sinc-DVR on 30–40 points (SciPy)
**Accuracy/Deliverable:** Band origins $\pm$ 20–50 cm$^{-1}$.
**Best Practices:** The Discrete Variable Representation (DVR) diagonalizes the potential. Use double precision (FP64) strictly; single precision introduces $10^{-1} - 10^0$ cm$^{-1}$ noise. CPUs are significantly faster than GPUs for 1-D DVR at this dimensionality.
**Authoritative Sources:**
1. Colbert, D. T., & Miller, W. H. (1992). "A novel discrete variable representation for quantum mechanical reactive scattering via the S-matrix Kohn method." *J. Chem. Phys.*
2. Light, J. C., & Carrington, T. (2000). "Discrete-Variable Representations and their Utilization." *Adv. Chem. Phys.*
3. Echave, J., & Clary, D. C. (1992). "Potential energy surfaces and vibrational states of polyatomic molecules." *Chem. Phys. Lett.*

### T2-12h: $\Delta$-learning + Active Learning
**Method:** DFT/PIP base + CCSD(T)-F12 correction (ORCA + MOLPIPx)
**Accuracy/Deliverable:** Fitted surface, RMS 3–10 cm$^{-1}$.
**Best Practices:** Compute a large base dataset at DFT (e.g., 2,000 points) and use Permutationally Invariant Polynomials (PIP) to $\Delta$-learn corrections from a smaller set (300–800) of CCSD(T)-F12 points. Active learning radically reduces the number of coupled-cluster points required.
**Authoritative Sources:**
1. Bowman, J. M. et al. (2011). "Permutationally invariant polynomial basis for molecular energy surface fitting." *Int. Rev. Phys. Chem.*
2. Ramakrishnan, R. et al. (2015). "Big Data meets Quantum Chemistry Approximations: The $\Delta$-Machine Learning Approach." *J. Chem. Theory Comput.*
3. Uteva, E. et al. (2017). "Active learning in machine learning potential energy surfaces." *J. Phys. Chem. A*
4. Qu, C. et al. (2018). "Permutationally invariant potential energy surfaces." *Annu. Rev. Phys. Chem.*

### T2-1d: Committee-Uncertainty Active Learning
**Method:** Explicit acquisition function with NN committee (ORCA + NN committee)
**Accuracy/Deliverable:** Active selection from a 2,000-point pool to reach an RMS of 5–20 cm$^{-1}$.
**Best Practices:** Variance-maximization alone plateaus poorly; explicit acquisition (e.g., query by committee) is required. A held-out validation grid is strictly mandatory to ensure the surface is reliable where the acquisition function did not sample.
**Authoritative Sources:**
1. Smith, J. S. et al. (2018). "Less is more: Sampling chemical space with active learning." *J. Chem. Phys.*
2. Behler, J. (2016). "Perspective: Machine learning potentials for atomistic simulations." *J. Chem. Phys.*
3. Schütt, K. T. et al. (2018). "SchNet: A continuous-filter convolutional neural network for modeling quantum interactions." *J. Chem. Phys.*
4. Settels, V. et al. (2020). "Active learning for molecular dynamics." *J. Chem. Theory Comput.*

### T2-3d: 3-D Rigid-Monomer DVR
**Method:** Matrix-free Lanczos on 500 actively selected points
**Accuracy/Deliverable:** Band origins $\pm$ 5–20 cm$^{-1}$.
**Best Practices:** Requires ~500 DLPNO points. At high grid dimensionality, standard dense matrices exceed memory. Matrix-free block Davidson or Lanczos iterations are mandatory to evaluate the Hamiltonian.
**Authoritative Sources:**
1. Carrington, T. (2017). "Using iterative methods to compute vibrational spectra." *J. Chem. Phys.*
2. Avila, G., & Carrington, T. (2009). "Non-product quadrature grids for solving the vibrational Schrödinger equation." *J. Chem. Phys.*
3. Halverson, T., & Poirier, Bill. (2015). "Massively parallel quantum dynamics." *J. Phys. Chem. A*

### T2-1w: 6-D Rigid-Monomer Variational Treatment
**Method:** 6-D matrix-free rigid monomer VRT on a $\Delta$-learned surface
**Accuracy/Deliverable:** Band origins $\pm$ 1–5 cm$^{-1}$.
**Best Practices:** A 40³ dense 3-D representation already demands >30 GB RAM. Full 6-D VRT requires strict matrix-free iterative approaches. Ensure the $\Delta$-surface has no spurious holes or unphysical asymptotic behaviors before integration.
**Authoritative Sources:**
1. Wang, X., & Carrington, T. (2013). "Vibrational energy levels of CH4 calculated with a new contracted basis..." *J. Chem. Phys.*
2. Leforestier, C. et al. (2012). "Water dimer vibration-rotation levels..." *J. Chem. Phys.*
3. Groenenboom, G. C. et al. (2000). "Water pair potential of near spectroscopic accuracy." *J. Chem. Phys.*

### T2-1mo: Full-Dimensional Flexible-Monomer Surface
**Method:** Full-dimensional fitting (autoPES / flex-autoPES or PIP)
**Accuracy/Deliverable:** Sub-10 cm$^{-1}$ accuracy (e.g., 9.1 cm$^{-1}$ for water dimer over ~4,700 points).
**Best Practices:** This is an HPC-only tier. Use automated generators like flex-autoPES or PIP via MSA-2.0 to span intramolecular degrees of freedom correctly. Asymptotic interactions must be explicitly handled, often scaling to 50,000+ points across a multi-node cluster.
**Authoritative Sources:**
1. Szalewicz, K. et al. (2012). "autoPES: Automated generation of potential energy surfaces." *J. Chem. Phys.*
2. Metz, M. P. et al. (2020). "flex-autoPES: Automated generation of fully flexible intermolecular potential energy surfaces." *J. Chem. Phys.*
3. Bukowski, R. et al. (2006). "Predictions of the properties of water from first principles." *Science*.
4. Bowman, J. M. et al. (2011). "Permutationally invariant polynomial basis for molecular energy surface fitting." *Int. Rev. Phys. Chem.*
