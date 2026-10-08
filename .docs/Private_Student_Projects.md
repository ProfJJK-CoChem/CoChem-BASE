# Private student projects: Codespaces and licensed Actions calculations

A student-owned **private, standalone repository** uses that student's GitHub
Actions allowance. An organization-owned repository uses the organization's
allowance, regardless of who starts a calculation. A private copy does not
inherit secrets from this public repository or from the lab organization.
GitHub team membership grants only the repository permissions assigned to the
team; it does not reveal organization secrets.

This workflow separates personal project ownership from authorized read access
to the lab's private ORCA and CFOUR distributions. License authorization remains
a prerequisite. Engine archives, credentials and installations stay outside Git.

## Create the project

Use the instructor-approved BASE source containing this guide and the updated
workflows. From a local clone of that source, authenticate GitHub CLI as the
student and create a new private repository:

```bash
gh auth status
gh repo create STUDENT/PROJECT --private --source . --remote student --push
```

Replace `STUDENT/PROJECT` with the student's account and project name. Use a clean
checkout and an approved source branch. This creates a standalone copy; GitHub
does not permit a public repository's ordinary fork to become private. Confirm
the project is private before opening Codespaces or running licensed workflows.
Workflow files must be present on the project's default branch for the Actions
**Run workflow** controls to appear. Updates to upstream BASE are not copied
automatically; review and apply source updates deliberately.

## Authorize Actions without sharing the lab's organization credentials

The instructor first grants the student's lab team read access to the private
engine repositories. The student then creates their **own expiring fine-grained
GitHub credential**, selecting the lab organization as resource owner, only the
two engine distribution repositories, and **Contents: read-only**. Complete any
organization approval or SSO requirements. A credential for the student's project
alone cannot read a different owner's private engine repositories.

In the student's private project, save that value under an arbitrary private
Actions secret name. Enter the value through GitHub's secret editor or the CLI's
interactive prompt, never in a command argument, source file, issue or job JSON:

```bash
gh secret set PRIVATE_CREDENTIAL_NAME --repo STUDENT/PROJECT
python3 scripts/configure_lab_project.py \
  --repository STUDENT/PROJECT --credential-name PRIVATE_CREDENTIAL_NAME
```

`PRIVATE_CREDENTIAL_NAME` is a placeholder chosen by the student, not the name of
an existing lab secret. The configurator verifies private personal ownership,
checks the secret's existence without reading its value, and writes the private
Actions variables `COCHEM_ORCA_ASSET_CREDENTIAL` and
`COCHEM_CFOUR_ASSET_CREDENTIAL`. Their values select that existing secret. Public
YAML contains only the variable lookup, never the lab's credential identifiers.
Configuration success does not verify the credential's value or execute chemistry.
Run these configuration commands with the student's normal local GitHub CLI
login that can manage the private project. The engine's read-only credential and
a Codespaces repository token do not necessarily have permission to manage
Actions secrets or variables. GitHub's private project settings provide the same
configuration route without the CLI.

Check the configuration later without changing it:

```bash
python3 scripts/configure_lab_project.py --repository STUDENT/PROJECT --check-only
```

For organization-owned projects, an organization owner may instead grant the
existing organization secrets to selected private repositories and configure the
same selector variables privately. No renaming of existing organization secrets
is required. This alternative uses organization Actions minutes. GitHub Free
organizations have additional restrictions on organization secrets in private
repositories; consult the current GitHub documentation.

## Open Codespaces and install the licensed engines

Create a Codespace from the **private student project**. Review and authorize
the devcontainer's additional **Contents: read** requests for the lab engine
repositories. These permissions use the student's Codespaces authorization;
Actions secrets are a separate mechanism. Changed permissions require a new
Codespace. Keep the forwarded dashboard port private.

The normal devcontainer setup starts the BASE dashboard without downloading
licensed distributions. To provision authorized engines in this private Codespace:

```bash
python3 scripts/setup_licensed_engines.py --engine both
```

This command checks private project visibility before downloading, uses the
pinned distribution checksums and existing provisioners, installs outside the
source tree, and retains engine paths for the dashboard. Follow its printed
Stage0 refresh instructions before calculations. After provisioning, stop and
resume the Codespace so its running dashboard reloads the new engine environment;
calling `start` on an already-running dashboard only reuses that process. A missing authorization, bad
checksum, insufficient disk, or unsupported host fails explicitly. ORCA requires
Linux x86-64, its pinned Open MPI runtime, and substantial storage: the approved
archive expands to approximately 17.4 GB before dependencies and safety reserves.
Choose a Codespace with sufficient storage and verify its cost with the instructor.

## Run and retrieve a calculation

1. Export an ORCA or CFOUR job JSON from BASE, or start with a committed example
   in `examples/jobs/`. Commit the input to the private project.
2. Run the corresponding installation/scientific acceptance workflow first.
   Successful configuration or archive access is not a passed calculation.
3. Open **Actions → ORCA calculation** or **CFOUR calculation → Run workflow**.
   Select the branch containing the input and enter its repository-relative
   `job_file`, CPU count and memory allocation. Licensed workflows run manually
   and reject public repositories before checkout or distribution download.
4. Retain the completed run URL and its scientific artifact. Inspect convergence,
   normal termination, `calculation-report.json`, inputs, native outputs and the
   canonical scientific archive. Failed runs retain diagnostics.

Current student workflows allow 1–2 CPU processes/threads, 1–1024 MB per process
or allocated thread, and at most 1800 seconds for a submitted calculation. CFOUR
uses the approved OpenMP build; ORCA uses the pinned MPI runtime. Installation
time is separate. These routes do not certify every method matrix row, R2, VPT2,
GPU execution or full TOPOS release acceptance. The TOPOS protected worker's
provider profile remains separate from these BASE ORCA/CFOUR calculation routes.
Licensed installations and downloads are removed from ephemeral Actions runners;
archives are never uploaded with results.

The personal repository owner's billing settings must permit the run. Budget
limits or failed payments can prevent a runner from starting; a queued or skipped
job has performed no chemistry. Standard public-runner pricing does not make a
private project free of all compute and storage costs.

## Authoritative GitHub references

- [Actions billing: usage is charged to the repository owner](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
- [Actions repository and organization secrets and access policies](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets).
- [Codespaces additional repository permissions and authorization](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces).
- [Codespaces account-specific secrets](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-your-account-specific-secrets-for-github-codespaces).

Reviewed against GitHub documentation on 2026-10-08. Hosted Codespaces creation
and current-source licensed calculations require genuine deployment acceptance;
local control tests alone do not establish those outcomes.
