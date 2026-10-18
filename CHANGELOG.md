# Changelog

## Unreleased

- Added the Pickett program build mechanism (CoChem-SpycFit D-SPYC-17 and
  D-SPYC-26): `scripts/provision_pickett.py` downloads the JPL calpgm sources
  pinned byte for byte in `scripts/pickett-distribution.json`, builds SPFIT,
  SPCAT, DPFIT and DPCAT with the shipped Makefile outside the checkout, runs
  the HCO and NO shipped examples on scratch copies and writes the receipt
  `cochem.pickett-installation/1` (source inventory, build recipe, program
  SHA-256 and status `accepted` or `built`, rights notices, every listed
  difference). The Codespaces setup script runs it automatically; a failed
  build disables only the SPFIT/SPCAT comparisons and can be retried from the
  interface. `cochem-cli pickett build|verify|status` and the workflow
  `pickett_build.yml` expose it. Programs stay off PATH; consumers read the
  receipt named by `COCHEM_PICKETT_RECEIPT`. Nothing downloaded or built is
  committed or redistributed.
- Removed the in-process Watson-Hamiltonian substitute from the SPCAT runner.
  A missing, unverified or failing SPCAT now raises
  `PickettProgramUnavailableError`; every catalog the runner writes is SPCAT
  output with a provenance sidecar.

## 1.0.0

This release defines CoChem-BASE as the ingestion, environment setup, Voilà
interface, validated calculation execution and ecosystem handoff module.
Publication and acceptance status are recorded in
[the release record](.docs/Release_1_0_0.md).

- Added Classroom50 course setup, instructor-managed private ORCA assets,
  consistent checksum-pinned manifests and separate archive-access, physical
  acceptance and student calculation workflows.
- Added portable GUI job export for GitHub Actions with shared input/resource
  validation and retained calculation evidence. The GUI keeps local and HPC
  environment choices separate.
- Verified the ORCA 6.1.1/Open MPI 4.1.8 runtime with actual serial and parallel
  CPU calculations. ORCA environment isolation prevents incompatible libraries
  and inherited thread counts from corrupting execution.
- Added molecular optimization and harmonic derivative acceptance, explicit
  geometry provenance and canonical result/HDF5 agreement checks.
- Executed real frozen-monomer R1/R2, dispersion/grid, spin-recovery,
  CREST/GOAT-union and isotope/Hessian integration checks, preserving achieved
  convergence and signed counterpoise warnings.
- Met the 10 cm⁻¹ held-out energy-error bound in a bounded real H2 interpolation
  protocol: 3.176715694 cm⁻¹ standalone RMSE, 8.242899532 cm⁻¹ maximum error.
  This does not certify other molecules, extrapolation or spectroscopic accuracy.
- Completed the 1,532-pass canonical local profile with only two declared
  physical Slurm deferrals and no source mutation. Hosted ORCA serial/parallel
  acceptance and student optimization/frequency jobs passed on GitHub Actions.
  Bounded CI passed Ubuntu/macOS/Windows controls and installed-wheel checks,
  native launcher diagnostics, actual Linux free-engine calculations and the
  rendered dashboard lifecycle; the release record tracks exact revisions.
- Kept generic tensor compression separate from the explicit trajectory API;
  an array's shape or field name no longer assigns trajectory semantics.
- Preserved unavailable observations as `null` while retaining measured zeroes;
  thermodynamic energies require declared units before conversion or export.
  Real HDF5/Parquet regression checks cover missing fields, nonfinite values
  and valid zero-valued measurements.
- Preserved fatal crash records when Git identity is unavailable, and bound
  available Git provenance to the executing source instead of an unrelated
  working directory or inherited Git overrides.
- Kept optional reporting, symmetry and language-model dependencies isolated;
  development/reporting profiles declare their required extras explicitly.
- Retained complete eleven-phase Stage 0 setup, independently checked engine
  identities, immutable source checks and explicit downstream handoff states.
- Prepared versioned Python distributions and installed CLI entry points.

Small chemistry examples validate the software pathway. They do not establish
universal chemical accuracy, complete downstream TOPOS/TORQ algorithms or
unexecuted native/GPU/Slurm platform acceptance.

## Earlier development

The earlier source tree reported version 0.1.0. Historical alpha audits and
architecture documents remain available under `.docs/`; they describe their
recorded revisions rather than the acceptance status of this release.
