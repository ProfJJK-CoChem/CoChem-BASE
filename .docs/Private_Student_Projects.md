# Private BASE projects: course deployment and expert alternatives

A student-owned **private, standalone repository** uses that student's GitHub
Actions allowance. An organization-owned repository uses the organization's
allowance, regardless of who starts a calculation. A private copy does not
inherit secrets from this public repository or from the lab organization.
GitHub team membership grants only the repository permissions assigned to the
team; it does not reveal organization secrets.

The selected course route uses the instructor-managed GitHub App. Students use
one BASE repository and browser controls; BASE installs and connects approved
TOPOS/TORQ components without separate student module repositories. They do not
create tokens, type terminal commands, edit Python/JSON or install chemistry
engines manually. License authorization remains a prerequisite. Engine archives,
credentials and installations stay outside Git.

## Supported course route: browser controls only

The instructor first follows the complete
[App deployment guide](Personal_Project_App_Deployment.md) to configure the
private access controller, active student-team membership, selected-project App
consent and reviewed source/engine access. It encrypts approved read-only readers
into the enrolled private project; students never receive the instructor App key.

1. Accept your course organization/team invitation. Open the instructor's approved
   BASE template and choose **Use this template → Create a new repository**.
   Select **your personal GitHub account**, choose a project name and **Private**.
   This is an independent template copy, not a public fork.
2. In your project choose **Code → Codespaces → Create codespace**. Wait for
   automatic BASE setup, then open the private **8866 CoChem Voilà dashboard**
   from VS Code's **Ports** panel. The initial Codespace is for enrollment.
3. In **Lab access**, enter the instructor's nonsecret access-repository name
   and exact App slug. Choose **Authorize lab app** and authorize **Only select
   repositories → this private project**.
4. Choose **Request project access** and submit the prefilled data-only issue.
   Wait for the controller's success comment. Give an issue/run link to your
   instructor if enrollment fails; do not create or paste a token.
5. After approval, stop the initial Codespace before beginning research uploads.
   Create a **fresh Codespace** for this private project. The App supplies the
   separately provisioned Codespaces source credential; BASE installs its
   approved components automatically. Reopen the private dashboard and confirm
   **CoChem setup and updates** has completed.
6. Refresh engine access in **Lab access**. Upload your own scientific files,
   declare the required state and metadata, select **GitHub Actions** and your
   enrolled private project, and submit through BASE. Use its status, cancellation,
   verified retrieval, scientific reports and compatible update controls.
7. Save your report through VS Code's Source Control interface. Follow the
   instructor's Classroom50 collection instructions separately and confirm the
   instructor can read your private submission. Stop the Codespace when finished.

The [complete student guide](Student_Research_No_Code.md) explains every control
and the full scientific input library. Avogadro 2 monomer/complex XYZ files are
common course inputs; they are not the only supported ingestion route.
[Classroom50 deployment](Classroom50_Assignment_Deployment.md) covers the roster,
collection and feedback service, with organization-owned calculations clearly
labeled as an alternate charged to the organization.

The App's public binding-variable names are `COCHEM_ORCA_ACCESS_SECRET`,
`COCHEM_CFOUR_ACCESS_SECRET` and `COCHEM_SOURCE_ACCESS_SECRET`. Their private values
select encrypted repository credentials; no organization-specific reader label
is fixed in public source. Actions and Codespaces use separate credential stores.
The Codespaces source reader is exposed only under the generic runtime name
`COCHEM_SOURCE_CREDENTIAL`. Additional repository declarations do not transfer
organization secrets or authorize cross-owner access by themselves.

ORCA and CFOUR are optional and strongly recommended. Failed access, installation
or verification makes dependent methods unavailable while BASE ingestion, setup,
the interface and independently available free capabilities remain usable. The
Codespace hosts the interface; Actions provisions selected engines on its worker.
Students do not need a licensed engine download in their Codespace to submit an
authorized Actions calculation.

## Expert alternatives for authorized repository owners

The procedures below retain manual configuration and local provisioning for
experienced maintainers using their own authorized repository-owner identity.
They are **not the course student instructions** and do not replace the App route.
An instructor should not ask students to follow these commands, create PATs,
assemble a CoChem kit or author request JSON. Configuration and archive checks do
not establish scientific accuracy or a live student deployment acceptance.

### Create a project manually

Use the instructor-approved BASE source containing this guide and the updated
workflows. From a local clone of that source, authenticate GitHub CLI as the
expert project owner and create a new private repository:

```bash
gh auth status
gh repo create OWNER/PROJECT --private --source . --remote project --push
```

Replace `OWNER/PROJECT` with your account and project name. Use a clean
checkout and an approved source branch. This creates a standalone copy; GitHub
does not permit a public repository's ordinary fork to become private. Confirm
the project is private before opening Codespaces or running licensed workflows.
Workflow files must be present on the project's default branch for the Actions
**Run workflow** controls to appear. Updates to upstream BASE are not copied
automatically; review and apply source updates deliberately.

### Configure Actions access manually

The repository owner must already be authorized to read the private engine
distributions. For this expert alternative, use an **expiring fine-grained GitHub
credential** restricted to the approved asset repositories with **Contents:
read-only**, completing required organization approval or SSO. A credential for
the project alone cannot read another owner's private engine repositories. The
instructor-managed App supplies access automatically for the supported course route.

In the expert owner's private project, save that value under an arbitrary private
Actions secret name. Enter the value through GitHub's secret editor or the CLI's
interactive prompt, never in a command argument, source file, issue or job JSON:

```bash
gh secret set PRIVATE_CREDENTIAL_NAME --repo OWNER/PROJECT
python3 scripts/configure_lab_project.py \
  --repository OWNER/PROJECT --credential-name PRIVATE_CREDENTIAL_NAME
```

`PRIVATE_CREDENTIAL_NAME` is a placeholder chosen by the expert owner, not the name of
an existing lab secret. The configurator verifies private personal ownership,
checks the secret's existence without reading its value, and writes the private
Actions variables `COCHEM_ORCA_ACCESS_SECRET` and
`COCHEM_CFOUR_ACCESS_SECRET`. Their values select that existing secret. Public
YAML contains only the variable lookup, never the lab's credential identifiers.
Configuration success does not verify the credential's value or execute chemistry.
Run these configuration commands with the repository owner's normal local GitHub CLI
login that can manage the private project. The engine's read-only credential and
a Codespaces repository token do not necessarily have permission to manage
Actions secrets or variables. GitHub's private project settings provide the same
configuration route without the CLI.

Check the configuration later without changing it:

```bash
python3 scripts/configure_lab_project.py --repository OWNER/PROJECT --check-only
```

For organization-owned projects, an organization owner may instead grant the
existing organization secrets to selected private repositories and configure the
same selector variables privately. No renaming of existing organization secrets
is required. This alternative uses organization Actions minutes. GitHub Free
organizations have additional restrictions on organization secrets in private
repositories; consult the current GitHub documentation.

### Optional licensed local provisioning for experts

Create a Codespace from the **private expert project**. Local licensed downloads
need their own authorized GitHub CLI identity able to read the private engine
repositories. Additional **Contents: read** declarations are limited by GitHub's
repository-owner and existing-access rules; personal projects cannot assume that
cross-owner declarations authorize lab assets. The App's Actions readers are not
automatically Codespaces engine credentials. Keep the forwarded dashboard port
private. A changed Codespaces credential or permission requires a fresh Codespace.

The normal devcontainer setup starts BASE without requiring licensed engines.
Actions students need no local installation. An expert who deliberately needs
licensed local calculations can invoke the separate provisioner:

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

### Reviewed ecosystem kits for experts

The optional kit tools and advanced module controls are for maintainers testing
a complete, instructor-reviewed BASE/TOPOS/TORQ kit. Supply an extracted kit only
when its catalog, immutable source revisions, wheel checksums, installed records
and provider operations have been independently accepted for that exact source.
A kit created for an older BASE version cannot replace current worker authority.
The historical `scripts/module-distribution-legacy-kit-1.0.1.json` remains an
unchanged expert compatibility record requiring its exact BASE 1.0.1 package.
The separate `scripts/module-distribution-expert-main-6160117.json` preserves the
incoming Qt-enabled main catalog and its source/wheel identities. It is an expert
kit record, not current student-installation authority or proof that a new kit
passed native acceptance. The default `scripts/module-distribution.json` supplies
current automatic installations with an immutable compatible BASE science source
and the separately approved TOPOS/TORQ revisions. Students use automatic setup and
scientific GUI controls; expert kit and request-file tools are separate.
New kit installation or export evidence must retain its own exact tested revision
and limitations rather than inherit older native acceptance results.

### Run and retrieve a manual expert calculation

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

The bounded molecular workflows allow 1–2 CPU processes/threads, 1–1024 MB per process
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
