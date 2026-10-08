# Pilot one Classroom50 assignment before course rollout

For student-owned private projects using personal Actions minutes, follow the
[private student project guide](Private_Student_Projects.md). Organization secrets
do not transfer to personal repositories. Configure the private
`COCHEM_ORCA_ASSET_CREDENTIAL` and `COCHEM_CFOUR_ASSET_CREDENTIAL` variables to
select existing authorized secrets; their identifiers are never fixed in public
YAML. Any credential name in examples below is a placeholder, not the name of
an existing lab secret. Organization-owned course assignments remain a separate
route using organization Actions minutes.

BASE provides the source, setup, interface and reviewed calculation workflows.
A completed calculation in the upstream repository establishes its execution
path; a course deployment also needs the student's own assignment permissions,
Codespaces authorization and result retrieval to work.

Use the [ORCA/Classroom50 guide](GitHub_Classroom_ORCA_Setup.md),
[CFOUR guide](CFOUR_Actions_Setup.md) and
[private-module guide](Ecosystem_Modules_Setup.md) for the detailed setup.
ORCA and CFOUR are optional and strongly recommended. The free-engine dashboard
must remain usable if neither engine is configured.

## Instructor: prepare a single pilot assignment

1. Update the approved course template to the reviewed `v1.0.1` source after
   that release is published. Preserve the released workflows,
   `.devcontainer/devcontainer.json`, scripts, requirements and notebooks.
   An older template copy does not update when upstream changes.
2. Create the assignment through Classroom50 and have one enrolled pilot
   student accept it. Record the resulting assignment repository and source
   commit. Do not use an instructor's source checkout as student acceptance.
3. Make the approved `PRIVATE_ORCA_CREDENTIAL`, `PRIVATE_CFOUR_CREDENTIAL` and,
   when modules are needed, `COCHEM_SOURCE_READ_TOKEN` available to that
   assignment using selected-repository organization access or approved
   repository secrets. No token values belong in a notebook, input or report.
   Copying a template does not copy secrets. Leave fork pull-request secrets
   and write tokens disabled.
4. Grant the student/team read access to the approved private modules declared
   in the devcontainer. Confirm assignment access and accepted organization
   membership. Actions access and Codespaces access are separate.
5. Confirm user-owned Codespaces and the student's available allowance. Actions
   in an organization-owned assignment consumes that organization's allowance.
   Student Codespaces core-hours do not pay for Actions jobs.

## Student: create and check the interface

1. Open the accepted assignment repository on the instructor-approved branch.
   Create a **new** Codespace and authorize the declared module permissions.
   Confirm the payer is your student account. A rebuild does not apply newly
   declared repository permissions to an old Codespace.
2. Wait for the setup lifecycle to finish. Open the forwarded **CoChem Voilà
   dashboard** port, keeping its visibility private. Retain setup errors if
   it fails; a port opening alone does not establish a rendered dashboard.
3. Confirm structure ingestion, data inspection and the installed free-engine
   route work. Without a local licensed engine, its dependent local choices
   should be disabled. Choosing GitHub Actions prepares a remote request;
   that alone does not establish remote archive access or complete chemistry.
4. If the course uses TOPOS/TORQ, follow the module guide to verify repository
   read access, isolated installation and the supported geometry handoff.
   Installing a module does not validate all its scientific operations.

## Student: run and retrieve one calculation

1. Follow the engine guide's student workflow for one small reviewed example.
   Run **ORCA 6.1.1 calculation acceptance** or **CFOUR 2.1 calculation acceptance** first
   when required by the instructor, then run the corresponding **ORCA
   calculation** or **CFOUR calculation** workflow with its example job file.
2. Record the workflow URL, checked-out commit, job file, resource settings and
   result-artifact name. Confirm the workflow and scientific validation pass;
   an installation success alone is insufficient.
3. Download the result artifact from the completed run. Inspect the input,
   calculation report, native outputs and harmonic Hessian when requested.
   These small examples test integration; they are not experimental accuracy
   benchmarks.
4. Import the supported result into the interface, or retain it with the
   course submission as instructed. Commit and push course work, then stop
   the Codespace. Delete it when appropriate to release storage.

## Deployment record and current boundary

Record each observation rather than marking the entire pilot passed from one
successful step:

| Check | Evidence to retain |
| --- | --- |
| Student assignment access | Assignment repository, accepted invitation, source commit |
| Fresh Codespace | Student identity, creation time, requested permissions, payer, setup report |
| Interface | Rendered dashboard and ingestion result; licensed-engine absence behavior |
| Module access, when requested | Pinned revision, installation/verification report and supported handoff |
| Actual Actions chemistry | Run URL, source commit, resource settings and scientific acceptance report |
| Retrieval | Downloaded artifact and successful supported result inspection |

On 2026-10-07 the available cloud integration authenticated as the instructor,
listed zero existing Codespaces and found no student assignment repository in
the course organization. Repository Codespaces machine/permission checks
returned HTTP 403, `Resource not accessible by integration`. No student account
was impersonated and no billed Codespace was created. Actual student-identity
Classroom50/Codespaces acceptance therefore remains a course deployment check.
Local devcontainer tests and upstream hosted calculations have separate
evidence; they do not replace this pilot.

The actual local container pass used the configured Python 3.12 Bookworm image
and the new `scripts/setup_devcontainer.sh`. It reproduced missing GL/DBus
libraries, then verified their installation, native PySide/VTK imports, all
eleven Stage 0 phases, rendered Voilà lifecycle and genuine xTB GFN-FF/GFN2
energy/Hessian checks. ORCA and CFOUR were absent, and BASE remained operational.
The script supplies the system libraries that the stock Python image lacks.
No public port or billed Codespace was created. Editable installation
regenerated package metadata in the isolated source copy; all other tracked
bytes matched its recorded source revision. The final release's full source
and integrity gates are recorded separately.
