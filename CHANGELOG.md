# Changelog

## 1.0.0 — release preparation

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
