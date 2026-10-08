# CoChem-BASE

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

CoChem-BASE provides scientific input ingestion, environment setup, the Voilà
interface, validated calculation execution and handoffs to the CoChem ecosystem.
It preserves actual inputs, engine identity, resource allocation, outputs and
scientific records needed to assess a result.

**Instructors: follow the
[Classroom50 assignment deployment guide](.docs/Classroom50_Assignment_Deployment.md)**
to prepare the release template, configure access, pilot one student and roll
the assignment out to the course. **Students: start with the
[graphical research guide](.docs/Student_Research_No_Code.md).**
Open **your accepted Classroom50 repository → Code → Codespaces → Create codespace**,
wait for automatic setup, then open the private **8866 CoChem Voilà dashboard**
from VS Code's Ports panel. The student route uses buttons and file uploads.
Students upload their own Avogadro 2 monomers or complexes. BASE automatically
installs its approved modules and provides calculation submission, monitoring,
result retrieval, scientific reports and compatible updates in the GUI.
Students using the instructor's provisioned route do not enter tokens in CoChem,
type terminal commands, edit Python/JSON or obtain another CoChem repository.
The [complete input-library guide](.docs/Student_Research_No_Code.md#use-the-scientific-input-library)
also covers MOL V2000/V3000, multi-record SDF, MOL2, PDB, QCSchema,
conformer pools, periodic structures, native outputs and geometry-bound Hessians.

For CFOUR runtime access, classroom setup and host compatibility, follow the
[CFOUR setup guide](.docs/CFOUR_Actions_Setup.md). **ORCA and CFOUR are optional,
strongly recommended engines.** BASE remains usable when either is absent or
its optional installation fails; only dependent calculations are unavailable.

For private module downloads, isolated installations and TOPOS/TORQ geometry
handoffs, follow the [ecosystem modules guide](.docs/Ecosystem_Modules_Setup.md).
It explains private credential bindings, automatic installation and execution.
For personal-owned private projects that use students' own Actions allowance,
follow the [instructor-managed GitHub App guide](.docs/Personal_Project_App_Deployment.md).
Students authorize their selected project without handling token values.

The **1.1.0 release candidate** adds automatic module setup, student geometry
uploads, direct Actions submission and retrieval, research reports and preserved
runtime updates. Its validation is recorded separately from earlier releases.
Version **1.0.1** brought the integrated CFOUR/module routes and SRS
closure work into the distribution. Its complete profile
passed **1,827 tests** with **two explicit physical Slurm deferrals** and no
failures. Hosted ORCA/CFOUR science, three-platform package/control checks and
a fresh local Voilà container also passed. The
[release and validation record](.docs/Release_1_0_1.md) identifies
actual tested revisions, application equivalence to the complete-profile
source `583a6d2`, supported operations and how to verify publication through
the actual GitHub release and its attached validation/checksum records. The older
[1.0.0 record](.docs/Release_1_0_0.md) remains historical. Existing Classroom50
assignment copies must be updated to the approved course source; pulling this
repository does not grant assignment secrets or private-module permissions.
Use the [single-student deployment pilot](.docs/Student_Deployment_Pilot.md)
before rolling a new template out to the course.

## Choose a calculation environment

| Route | How to use it | Validation boundary |
| --- | --- | --- |
| Classroom50 / GitHub Actions | Accept the assignment, open BASE in Codespaces, upload XYZ and select **Run on GitHub Actions**. | Exact submitted structures and approved scientific worker revisions bind the retained results. Hosted execution is distinct from actual student Codespaces acceptance. |
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

1. Accept the Classroom50 assignment, create its Codespace and wait for automatic
   setup. Open the private Voilà dashboard on port 8866.
2. Upload your own monomer or complex XYZ files and declare their charge and
   multiplicity. BASE preserves the original files separately from software.
3. Select **GitHub Actions**, the accepted assignment repository, a supported
   method and operation, then submit through BASE. No JSON editing, terminal
   command, separate module checkout or manual workflow dispatch is required.
4. Use BASE's status, cancellation and verified result retrieval controls.
   Review computed structures, tables, diagrams and provenance before writing
   your research report. Use BASE's update controls when a compatible fix is
   published; software updates preserve uploaded structures and results.

The [student research guide](.docs/Student_Research_No_Code.md) describes the
buttons and actual supported provider scope. Unavailable scientific providers
disable their dependent operations rather than returning illustrative numbers.

The course workflow supports bounded molecular single points, optimizations
and harmonic frequencies: up to 50 atoms, one or two processes, at most 1024 MB
per process and 1800 seconds of chemistry execution. Defaults are two processes
and 512 MB per process. The same BASE entrypoint also provides typed R2/READ input uploads, explicit T9
recovery and supported periodic requests, with original-source transport and
operation-specific scientific checks. VPT2 and other unavailable provider
operations remain explicitly gated; a successful upload does not certify them.

Examples are [water single point](examples/jobs/water-single-point.json),
[water optimization](examples/jobs/water-optimization.json), and
[water optimization plus harmonic frequencies](examples/jobs/water-harmonic.json).
These HF/STO-3G examples validate execution, not research-level chemical accuracy.
A harmonic calculation at supplied coordinates does not certify a stationary
geometry; optimize first when appropriate.

## Expert local and developer setup

The commands below prepare local workstations and development checkouts. Use
Python 3.12 for the pinned Stage 0 environments. Students using Classroom50
and Codespaces follow the graphical guide above; automatic BASE setup prepares
their workspace and hidden ecosystem components.

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

Interaction and calculation environments are separate choices. BASE submits
Actions requests and retrieves their verified results through the interface.
Native execution requires
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
