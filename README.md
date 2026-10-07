# CoChem-BASE

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

CoChem-BASE provides scientific input ingestion, environment setup, the Voilà
interface, validated calculation execution and handoffs to the CoChem ecosystem.
It preserves actual inputs, engine identity, resource allocation, outputs and
scientific records needed to assess a result.

**Students and instructors: start with the
[Classroom50 + ORCA GitHub Actions guide](.docs/GitHub_Classroom_ORCA_Setup.md).**
It covers private binary setup, correct GitHub permissions, each student's
assignment repository, GUI job export, calculations and retrieval of results.
Students using the instructor's provisioned route do not enter tokens in CoChem.

For CFOUR runtime access, classroom setup and host compatibility, follow the
[CFOUR setup guide](.docs/CFOUR_Actions_Setup.md). **ORCA and CFOUR are optional,
strongly recommended engines.** BASE remains usable when either is absent or
its optional installation fails; only dependent calculations are unavailable.

For private module downloads, isolated installations and TOPOS/TORQ geometry
handoffs, follow the [ecosystem modules guide](.docs/Ecosystem_Modules_Setup.md).
It explains `COCHEM_SOURCE_READ_TOKEN`, student-owned Codespaces, the
organization's shared Actions allowance, and which modules currently support
installation or execution.

Version **1.0.0 validates the supported Classroom50 / GitHub Actions route**,
including real ORCA optimization and harmonic calculations. The complete local
BASE profile passed 1,532 tests with two declared physical Slurm deferrals;
Ubuntu, macOS and Windows control and wheel checks also passed. The
[release record](.docs/Release_1_0_0.md) identifies exact revisions, evidence,
distribution records and remaining host/scientific boundaries.

## Choose a calculation environment

| Route | How to use it | Validation boundary |
| --- | --- | --- |
| Classroom50 / GitHub Actions | Accept the assignment, export a JSON job in Voilà, and run **ORCA calculation**. | Hosted installation and chemistry must pass for the selected source revision. See [ORCA evidence](.docs/ORCA_Actions_Setup.md). |
| Local Linux CPU | Complete Stage 0 and select an audited installed engine. | Local tests and real bounded calculations provide evidence for documented operations. |
| Windows / WSL2 | Submit Actions jobs from the interface; use WSL2 for local Linux ORCA. | The Linux archive does not run natively on Windows. WSL acceptance is separate from Linux cloud tests. |
| macOS | Use Actions or install the matching macOS engine build and complete setup. | Native macOS acceptance needs an appropriate host. Linux binaries and registries are not portable to it. |
| HPC / Slurm | Use permitted site engines/MPI and a registry generated in the allocation. | Physical Slurm-node and GPU acceptance remains deferred until a suitable host is supplied. |
| Codespaces interface | Host the interface in Codespaces and choose the calculation destination independently. | Local lifecycle/browser evidence is separate from an actual Codespaces rebuild. |

Selecting Actions preserves the local/HPC choices. Every execution host needs
its own engine paths, measured resource limits and Stage 0 registry.

## Student Actions calculations

The instructor prepares the private archive and grants selected repositories
access. All ORCA workflows read the same reviewed
[`scripts/orca-distribution.json`](scripts/orca-distribution.json). The supported
distribution is ORCA 6.1.1 for Linux x86-64 with Open MPI 4.1.8; its SHA-256 is
checked before extraction. The licensed binary is not included in this
repository, Python distributions or calculation artifacts.

1. Complete the [student quick start](.docs/GitHub_Classroom_ORCA_Setup.md#student-quick-start)
   and confirm the repository's physical ORCA acceptance passed.
2. In Voilà, select **GitHub Actions**, enter the course repository and approved
   branch, and configure the molecule in **No Code Matrix**.
3. Select **Prepare GitHub Actions job**, download the JSON and commit it under
   `jobs/` using the course's review process.
4. Open **Actions → ORCA calculation → Run workflow**, enter its `job_file`
   path, and start one job. Download its result artifact when it finishes.

The course workflow supports bounded molecular single points, optimizations
and harmonic frequencies: up to 50 atoms, one or two processes, at most 1024 MB
per process and 1800 seconds of chemistry execution. Defaults are two processes
and 512 MB per process. External checkpoints, R2 references, T9 recovery,
periodic calculations and VPT2 require other workflows.

Examples are [water single point](examples/jobs/water-single-point.json),
[water optimization](examples/jobs/water-optimization.json), and
[water optimization plus harmonic frequencies](examples/jobs/water-harmonic.json).
These HF/STO-3G examples validate execution, not research-level chemical accuracy.
A harmonic calculation at supplied coordinates does not certify a stationary
geometry; optimize first when appropriate.

## Launch the interface from source

Use Python 3.12 for the pinned Stage 0 environments. Classroom50 users should
clone their **accepted assignment repository**, using its **Code → Local** HTTPS
URL, and run the launcher inside that checkout. The clone example below is for
upstream development; it does not create or select your course assignment.

From an upstream development checkout:

```bash
git clone https://github.com/ProfJJK-CoChem/CoChem-BASE.git
cd CoChem-BASE
./Launch_CoChem_Mac_Linux.sh
```

An unpacked source distribution provides the same launcher. In Windows
PowerShell, use `.\Launch_CoChem_Windows.bat --native`. The launchers prepare the UI environment and open
`Start_Here.ipynb` with Voilà. To prepare without launching:

```bash
python3 scripts/bootstrap_environment.py
```

Interaction and calculation environments are separate choices. Actions exports
a portable request and gives submission instructions. Native execution requires
the selected host's audited setup. For a remote interface, use an authenticated
host connection and SSH port forwarding according to the site's access policy.

## Python installation and CLI

The wheel supplies Python packages and `cochem-cli`. The complete notebook and
launcher pathway uses a source checkout or source distribution. Installing the
package does not install licensed engines or authorize their use.

For development in a separate virtual environment:

```bash
python3.12 -m venv /path/outside/checkout/cochem-env
source /path/outside/checkout/cochem-env/bin/activate
python -m pip install -e '.[dev,ui,catalog,symmetry,scribe]'
cochem-cli --version
cochem-cli --help
```

The installed module form is `python -m cochem_base.cli`; source users can run
`python cli.py`. For a prepared host:

```bash
cochem-cli setup --all --artifact-dir /path/outside/checkout/artifacts
cochem-cli status --json
cochem-cli run --help
```

The default setup storage profile requires 50 GB free. Small hosted examples
use an explicit bounded profile after provisioner disk checks; that does not
reduce the requirements of larger calculations.

## Setup, data and scientific boundaries

Stage 0 executes eleven setup phases and records their results. Native
authorization uses the measured registry and verified executable identity;
a GUI selection alone does not authorize an unavailable engine.

Code and schemas stay in the source directory. Registries, HDF5 stores and
results use an external artifact directory; temporary calculation files use
external scratch storage. The source gate checks this boundary and retained
scientific fixture provenance.

Connected pathways include xTB, CREST, PySCF, ORCA and periodic Quantum ESPRESSO,
each subject to its installed capabilities and supported operations. The
[CFOUR guide](.docs/CFOUR_Actions_Setup.md) describes its bounded molecular
runtime and calculation pathway. VPT2 and other incomplete domain capabilities
remain explicit pending handoffs.
TOPOS and TORQ domain development belongs to their respective repositories.
BASE does not manufacture results for absent modules.

## Verification and architecture

The SRS baseline is Chunk 17 plus architectural proposal additions. See
[SRS implementation status](.docs/SRS_Implementation_Status.md),
[ORCA integration evidence](.docs/ORCA_Actions_Setup.md), and
[scientific acceptance](.docs/ORCA_Scientific_Acceptance.md).

In a prepared environment, run the canonical suite:

```bash
python ci_tools/base_ci.py all --output /path/outside/checkout/acceptance
```

Reports retain outcomes, exact external deferrals and source integrity.
Scientific checks use actual calculations where claimed. Download tests, unit
tests, browser checks and hosted physical acceptance establish different facts.
Small examples do not certify every method, molecule or a universal PES or
spectroscopic accuracy bound.

## Project and license

Principal Investigator / Architect: Dr. Joshua John Klaassen
([ORCID](https://orcid.org/0009-0007-1506-4401)).
Organization: [ProfJJK-CoChem](https://github.com/ProfJJK-CoChem).

CoChem-BASE uses [Apache-2.0](LICENSE). Separately installed engines and models
retain their own terms. See the [Method Matrix](Method_Matrix.md),
[user manual](CoChem_User_Manual.md), and [changelog](CHANGELOG.md). Historical
alpha documents describe their recorded revisions; current release claims
require the evidence in the release record.
