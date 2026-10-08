# CFOUR calculations in a personal private project

Use the [personal private project workflow](ORCA_Actions_Setup.md). Codespaces provides the interface and stages an approved asset through the student’s authorized lab access; the student’s own private repository runs calculations in Actions. Organization secrets do not transfer into personal repositories.

The authoritative CFOUR descriptor is `scripts/cfour-distribution.json`. It pins the actual user-approved CFOUR 2.1 Linux x86-64 runtime, archive SHA-256, embedded runtime manifest and source inventory. The reviewed runtime uses GCC/GFortran 11.4.0, OpenMP and ILP64 OpenBLAS, with its declared glibc requirement. Do not replace these fields with an assumed CFOUR layout or version command.

The existing provisioning chain validates the archive, complete embedded inventory, the native ELF executables and runtime dependencies, basis data, and launcher behavior. Keep this chain when changing asset delivery. Asset staging changes how the approved archive reaches a private Actions runner; it does not establish a new scientific method or bypass runtime checks.

Students must have their own authorized read access to the private lab asset. Stage the exact approved release asset and retain its private task receipt. The calculation workflow must validate its private personal project, receipt digest, exact task and provider run before consuming the archive. Actual CFOUR native results determine success. Optional installation failure disables CFOUR-dependent operations with a reason; it never synthesizes results.

Licensed archives and runtime files must not enter Git or public artifacts. Clean up only the task-owned temporary private release after checking the actual Actions lifecycle. Retain failed native calculation evidence and legitimate earlier quantities.

A live student pilot must exercise source authorization, private staging, Actions provisioning, a genuine calculation, result download, cancellation and cleanup. Prior native CFOUR evidence and offline controller tests do not substitute for that pilot.
