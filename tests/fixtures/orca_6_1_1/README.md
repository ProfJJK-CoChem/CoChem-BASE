# Genuine ORCA 6.1.1 canonical CCSD(T) reference records

These unchanged text inputs and outputs were calculated on 2026-10-07 with the
SHA-256-pinned ORCA 6.1.1 distribution and one CPU core. File digests are recorded
in `ci_tools/source_fixtures.json`; source run and independent PySCF provenance
are recorded in `provenance.json`.

`scripts/verify_r2.py` computed 14 actual cc-pVTZ/cc-pVQZ point pairs, minimized
HF(QZ) plus the Helgaker extrapolated T/Q correlation energy, and checked positive
curvature and bracketing independently at 0.001 and 0.002 angstrom increments.
The resulting H2 bond length is 0.741802 angstrom. These files are the final
single-point pair at that geometry. They alone do not establish a CBS optimized
geometry; the source reference-generation report retains the full minimization.

Independent PySCF 2.14.0 canonical CCSD(T) calculations at this geometry agree
with ORCA within 9.36e-11 Hartree. This is cross-engine implementation agreement
for a two-electron molecule, not experimental accuracy or general spectroscopic
certification. Replaying these files tests parsing, not fresh engine execution.

The outputs intentionally retain the genuine ORCA contributor banner. Its
DLPNO-related contributor descriptions must not misclassify canonical CCSD(T).
ORCA 6.1.1 reports the reference SCF energy in its TOTAL SCF ENERGY block and
E(0) in its correlated summary; it does not print the former assumed E(SCF) label.
