# Install private CoChem modules for a Classroom50 course

CoChem-BASE supplies ingestion, environment setup, the interface and execution
handoffs. Each additional module supplies its own supported calculations.
Access to its repository, installation of its dependencies, and a successful
module handoff are separate checks. Installing source does not certify a
module's scientific methods.

This guide assumes the assignment and module repositories belong to
`ProfJJK-CoChem`. Replace that owner with your actual course organization when
appropriate. Use the [ORCA course guide](GitHub_Classroom_ORCA_Setup.md) for the
separate licensed engine installation.

## Which credential and allowance apply?

| Environment | Source access | Usage account |
| --- | --- | --- |
| GitHub Actions in a course organization assignment | Organization Actions secret `COCHEM_SOURCE_READ_TOKEN`, available to selected assignment repositories | Repository owner: the course organization. GitHub Team's included 3,000 standard-runner minutes per month are shared across the organization. |
| Student-owned Codespace | Student's GitHub identity, with authorized `contents: read` access to the declared module repositories | Student's personal Codespaces allowance. Verified GitHub Education students currently receive up to 180 core-hours per month; verify their current allowance. |
| Local Linux, WSL, macOS or HPC | User's authorized Git credentials or an approved local source checkout | Local machine or the HPC site's allocation. |

The ORCA archive still uses `PRIVATE_ORCA_ASSET_CREDENTIAL`. Classroom50 collection and
grading use their own credentials. Do not reuse the Classroom50 service token
as a module or ORCA reader.

## Instructor: provide Actions source access

The source token must already select the required private CoChem repositories
and have **Contents → Read-only** access. That setting is under **Permissions →
Add permissions → Contents** in GitHub's fine-grained token form. Downloading
source does not require Actions write or Codespaces management permission.
Check the token's expiration and organization approval status.

1. Sign in as an organization owner and open **ProfJJK-CoChem → Settings →
   Secrets and variables → Actions → Secrets**.
2. Choose **New organization secret**. Enter `COCHEM_SOURCE_READ_TOKEN` exactly.
3. Paste the source-read token into **Value**. GitHub cannot reveal a previously
   saved secret. Use the securely retained original; regenerate it if it is no
   longer available. Do not put the value in a source file, notebook or chat.
4. Under **Repository access**, choose **Selected repositories**. Select BASE,
   the reviewed course template if it runs installation checks, and each
   assignment repository whose users are authorized to read those modules.
5. Save the secret. A repository secret with the same name takes precedence;
   update or remove a stale duplicate when moving to the organization secret.
6. After Classroom50 creates each new assignment repository, edit the
   organization secret's selected-repository list and add that repository.
   Copying a template does not copy its secrets or grant secret access.

The token's repository selection controls **which source it can read**. The
organization secret's selection controls **which repositories can use it**.
An Actions secret in BASE alone is unavailable in other assignment repositories.
Organization secrets can serve private repositories on GitHub Team, including
an eligible Education Team organization; GitHub Free does not provide this
organization-secret access to private repositories.

Keep **Send secrets and variables to workflows from fork pull requests**
**disabled** in **Organization Settings → Actions → General → Fork pull
request workflows**, and in repository settings if applicable. Keep **Send
write tokens to workflows from pull requests** disabled too. These settings
are unnecessary for manual jobs on the reviewed assignment branch. They would
allow fork pull request code to receive credentials for other private
repositories. Do not use `pull_request_target` to bypass that boundary.

People who can edit and execute a credential-bearing workflow can use its
credential. Select only course repositories whose users may read the permitted
source. Use an instructor-controlled calculation repository when that access
must remain instructor-only.

## Instructor: prepare students' Codespaces access

Actions secrets are not automatically available in Codespaces. This route uses
the student's own authorized GitHub access and personal Codespaces allowance.

1. Open **ProfJJK-CoChem → Teams**. Reuse the Classroom50 course team, or create
   a team for the course. Add enrolled students under the team's **Members**
   tab; students must accept the organization invitations.
2. Open each module repository, such as `CoChem-TOPOS` and `CoChem-TORQ`, then
   **Settings → Collaborators & teams → Add teams**. Add the course team with
   **Read** access. Students also need their normal **Write** access to their
   assignment repository.
3. Open **Organization Settings → Codespaces → General**. Under **Codespace
   ownership**, select **User ownership**. Enable the intended members' access
   to Codespaces for the organization's private repositories. The organization
   does not need to sponsor Codespaces. Tell existing users before changing
   ownership because their current Codespaces may transfer to their accounts.
4. Review the course template's `.devcontainer/devcontainer.json`. Its
   `customizations.codespaces.repositories` entries must explicitly name the
   approved module repositories with `contents: read`, for example:

   ```json
   {
     "customizations": {
       "codespaces": {
         "repositories": {
           "ProfJJK-CoChem/CoChem-TOPOS": {
             "permissions": {"contents": "read"}
           },
           "ProfJJK-CoChem/CoChem-TORQ": {
             "permissions": {"contents": "read"}
           }
         }
       }
     }
   }
   ```

   This fragment describes the relevant properties. Preserve the existing
   container image, lifecycle commands, ports and `customizations.vscode`
   settings when editing the actual file. Add each approved repository
   individually; requesting permission does not grant team membership.
5. Commit the configuration on the approved template branch. Update existing
   assignment copies as well. A changed template alone does not update all
   existing assignment source files.
6. Have a pilot student create a **new** Codespace from their assignment and
   authorize the requested repository read permissions. Confirm the displayed
   payer is the student's account. Rebuilding an existing Codespace does not
   update its repository permissions.

GitHub allows this declaration only for repositories with the **same owner**
as the assignment. If a different organization owns the source modules, arrange
separate user-authorized authentication before installing them. Do not assume
that adding an entry for another owner grants access.

## Student: check your source access

1. Accept the Classroom50 assignment and organization invitation, then open
   **your assignment repository**.
2. Choose **Code → Codespaces → Create codespace** on the instructor-approved
   branch. Review and authorize the module read permissions. Confirm your
   personal account is shown as the payer.
3. When setup finishes, open the terminal at the assignment root and run:

   ```bash
   git ls-remote https://github.com/ProfJJK-CoChem/CoChem-TOPOS.git HEAD
   git ls-remote https://github.com/ProfJJK-CoChem/CoChem-TORQ.git HEAD
   ```

   Each successful command prints a commit hash and `HEAD`. These commands
   verify read access without printing your credential; they do not install
   the modules. A 404 or authentication failure requires the instructor to
   check team access, repository permissions and whether this Codespace was
   created after the permission change.
4. Keep the dashboard port private. Stop the Codespace when finished. Commit
   and push course work before deleting a Codespace to release its storage.

For the organization's private assignment repositories, Actions consumes the
organization's allowance even when a student starts the job. Student Codespaces
core-hours cannot pay for Actions jobs. The course can keep its $0 paid-usage
limit; jobs will stop if its included allowance is exhausted.

## Fetch and install the approved modules

BASE's `scripts/module-distribution.json` records the repository and exact
reviewed commit for each supported installation. Keep the manifest supplied by
your instructor. Updating a repository's `main` branch does not change this
pin; new module revisions require a reviewed manifest update and acceptance.

The current catalog contains **21 downstream repositories**. Their present
capabilities differ:

| Step | Current scope | What success means |
| --- | --- | --- |
| Fetch source | All 21 catalog entries | Download and verify the source at the manifest's exact commit. No package installation or scientific execution is implied. |
| Install a Python distribution | Seven repositories declare package metadata: TOPOS, TORQ, SpycFit, MAGE, LUMOS, BENCH and KINETIC | A successful installation places the selected package and dependencies in an isolated environment and verifies their integrity. Metadata availability alone does not establish that the package builds or includes its scientific implementation. |
| Execute through BASE | TOPOS and TORQ `geometry_analysis` adapters | Run the supported geometry operation using that installed module and record the input, result and revision. Other modules currently have no BASE execution adapter. |
| Validate scientific workflows | Only the particular operations with retained acceptance evidence | Acceptance of one operation does not validate other methods, molecules or a module's complete scientific plan. |

The remaining 14 entries are **source-only** at the pinned revision because
their repositories lack package metadata: CURE, EHS, EVAL, GEOM, LABS, NODE,
ORACLE, ORB, PLAY, PULSE, SCAN, SCRIBE, SEED and SHIFT. Their manifest
`distribution` is `null`. Use `fetch` to obtain them; `install` must reject them
until the upstream module provides supported packaging. BASE does not invent a
package or mark a source-only module installed.

Two declared packages also have known upstream packaging defects at these pins:
MAGE's wheel build fails because setuptools cannot resolve its flat-layout
package discovery, and LUMOS's built wheel omits its root scientific/router
modules. Neither is advertised as a usable BASE calculation module. A wheel
build for SpycFit, BENCH or KINETIC likewise does not supply a BASE execution
adapter or complete scientific acceptance.

The installer creates a separate Python environment for each module under the
chosen root. This matters because CoChem repositories can contain overlapping
Python package names and different dependencies. Do not install every module
into BASE's dashboard environment with a single `pip install` command.

### In Codespaces

At your assignment repository root, inspect the catalog and install the two
modules prepared for the initial course integration:

```bash
python3 scripts/manage_modules.py list --json
python3 scripts/manage_modules.py install --modules topos torq --root "$COCHEM_ARTIFACT_DIR/Modules" --json
python3 scripts/manage_modules.py verify --modules topos torq --root "$COCHEM_ARTIFACT_DIR/Modules" --json
```

The supplied devcontainer defines `COCHEM_ARTIFACT_DIR` as
`/home/vscode/CoChem_Artifacts`. The module root is outside the source checkout.
Wait for installation to finish and retain its JSON report. A failed dependency
installation or revision check must be resolved before running a module.
Installation uses your authorized Codespaces identity; the source token stored
as an Actions secret is not needed here.

For an approved source-only module, use its lowercase catalog name. For
example:

```bash
python3 scripts/manage_modules.py fetch --modules seed --root "$COCHEM_ARTIFACT_DIR/Modules" --json
```

The Codespace must have read access to that additional repository before the
fetch can succeed. Add its explicit repository permission and create a new
Codespace as described above; the initial configuration requests only TOPOS and
TORQ. A successful `fetch` is a source-download result, not an installation.

Module installation is explicit. The standard dashboard setup does not silently
download the entire ecosystem. An instructor preparing an environment can opt
into the supported selected modules with `COCHEM_MODULES=topos,torq` during
dashboard setup; students can use the commands above after initial setup.

With BASE installed and its environment activated, the same commands are
available as `cochem-cli modules list`, `cochem-cli modules fetch`,
`cochem-cli modules install` and `cochem-cli modules verify`, followed by the
same options. Codespaces' managed BASE environment is
`$COCHEM_ARTIFACT_DIR/ui-env`; the terminal's default `python3` is not
necessarily that environment's Python.

### In GitHub Actions

1. Ensure the reviewed template includes `.github/workflows/ecosystem_modules.yml`
   on its default branch and the assignment can use `COCHEM_SOURCE_READ_TOKEN`.
2. Open **Actions → CoChem ecosystem modules → Run workflow** and select the
   instructor-approved branch.
3. Choose the **action**: `fetch` for source download, `install` for package
   installation, or `geometry_analysis` for the supported TOPOS/TORQ operation.
   Enter **modules** as space-separated catalog names, for example `topos torq`.
   A source-only selection is valid for `fetch`; it must fail for `install` or
   execution. Run one installation check before starting multiple jobs.
4. For `geometry_analysis`, leave **xyz_file** at `examples/jobs/water.xyz`
   for the first course pilot, or provide the repository-relative path to the
   instructor's committed XYZ file. This action installs the selected modules
   before running them. The path is unused for `fetch` and `install`.
5. Inspect the completed run's checkout, installation and verification steps.
   Download `cochem-modules-<run-id>-<attempt>` from the run summary within its
   **14-day** retention period. Keep its run URL, `installations.json` and any
   geometry result reports with the course validation record.
   A green source download alone does not establish an installed module or a
   successful scientific handoff.

This workflow receives the source-read credential for its reviewed manual run.
It does not require enabling secret delivery to fork pull requests. Downloading
module code and executing it within this job also does not require Actions
write permission on the source repositories or their reusable-workflow sharing
settings.

### Run a supported handoff

The initial BASE adapters support TOPOS and TORQ `geometry_analysis` handoffs.
Use a single, complete XYZ geometry with ordinary element symbols and
coordinates in ångströms. BASE's shared handoff path currently does not accept
isotope-labelled atom symbols; the direct TORQ adapter's isotope support does
not extend that GUI contract.

| Recipient | Returned operation |
| --- | --- |
| TOPOS | Geometry ingestion, a connectivity topology hash and a fragment/complex flag from its empirical geometry heuristic. These are not proof of chemical bonding or a conformer search. |
| TORQ | Center of mass, principal inertias, principal-axis alignment and rigid-rotor constants of the supplied geometry. Ordinary element symbols use the provider's most abundant isotope. These are not optimized-geometry or measured spectral constants. |

To install and run from Voilà:

1. Open **Module handoff** and its **Module installation and execution** panel.
2. Select TOPOS or TORQ under **Recipient module**. Keep **Module storage** at
   the external root used for installation, or select the instructor's approved
   root.
3. Select **Install selected recipient** if the module is not already installed.
   Wait for the completion message. Installation runs in the background; the
   interface remains available. Use **Refresh module availability** to recheck.
4. In **Input artifact**, enter the path to the XYZ file on the computer hosting
   Voilà. For a Codespace, this is a file inside that Codespace, not a path on
   your laptop. Keep **Package directory** outside the source checkout.
5. Select **Run geometry analysis**. It creates a fresh validated handoff from
   the current input and executes the selected module in its own environment.
   Wait for the completion or failure message and inspect the displayed result
   path and operation report. Each run receives its own result directory.

**Prepare validated handoff** is a separate export action: it records the
module, requested operation and input but does not execute them. Its requested
task field does not add support for operations without an execution adapter.

To run an exported handoff from the assignment checkout, use the same module
root used during installation:

```bash
"$COCHEM_ARTIFACT_DIR/ui-env/bin/python" scripts/run_module_handoff.py --handoff path/to/handoff.json --output "$COCHEM_ARTIFACT_DIR/module-result" --root "$COCHEM_ARTIFACT_DIR/Modules"
```

This Codespaces example uses the installed BASE environment. On another host,
use the Python from that host's activated BASE environment. Replace
`path/to/handoff.json` with the exported file and choose a new output directory
for each run; existing results are not overwritten. Review the result's module
identity, operation, input geometry and revision provenance. A geometry
analysis does not establish an electronic-structure energy, optimized geometry,
reaction barrier, anharmonic spectrum or a completed TORQ reaction workflow.
Those operations need their own available module interfaces and scientific
acceptance. Unsupported operations must remain unavailable rather than being
reported as successful.

TORQ preserves an undefined rotational constant for a zero-inertia axis as
JSON `null` with a reason. It likewise records an undefined asymmetry parameter
for a spherical top. Missing or undefined observables are not zero-valued
measurements; unexpected invalid/nonfinite results fail the operation.

When using the Actions workflow's `geometry_analysis` action, **xyz_file** is
the path to the committed XYZ input inside the assignment repository. Use the
instructor's reviewed input path, not a URL or a file path on your laptop.

## Local Linux, WSL, macOS and HPC

Use your own repository membership with an approved Git credential manager or
SSH configuration. An Actions secret is not automatically available on your
computer or cluster. For a standard GitHub CLI installation, `gh auth login`
followed by `gh auth setup-git` configures your own Git HTTPS authentication;
follow institutional policy on shared HPC hosts. Avoid embedding tokens in
clone URLs or shell commands.

Use the same reviewed module revisions as the course manifest. Install into the
environment supported by each module, and generate a fresh BASE registry on
the execution host. A Linux ORCA/MPI binary is not a macOS binary; Windows users
must use a compatible WSL installation for that Linux build. HPC calculations
must follow the site's scheduler and allocation rules. Successful source
download does not validate native scientific execution on these platforms.

The installer commands above also accept an explicit local root. For example,
from a Linux, WSL or macOS checkout:

```bash
python3 scripts/manage_modules.py install --modules topos torq --root "$HOME/CoChem_Artifacts/Modules" --json
python3 scripts/manage_modules.py verify --modules topos torq --root "$HOME/CoChem_Artifacts/Modules" --json
```

On HPC, choose a permitted persistent project path and run installation where
the site's network and software policies allow it. Installing source and its
Python environment does not submit a Slurm job or choose an engine allocation.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Module source token exists in BASE but an assignment cannot download | Add the assignment repository to the organization secret's selected repositories; template copies do not inherit access. |
| Token is selected for every module but download returns 404 | Check token owner, Contents read access, expiry, organization approval and the saved secret value. Private resources can return 404 when access is missing. |
| Actions works but Codespaces does not | Actions and Codespaces use separate credentials. Check student team membership, declared same-owner repository permissions and creation of a new Codespace. |
| Permission was added and a rebuild did not help | Create a new Codespace after committing the changed permissions. |
| Organization is shown as Codespaces payer | Check User ownership in the organization settings before course rollout; inspect the payer shown for the individual Codespace. |
| Actions is blocked although the student has free usage left | The organization owns the assignment repository, so its Actions allowance and policy apply. Student personal allowances are separate. |
| Module is installed but has no runnable BASE operation | Check that the module supplies the expected execution interface and supports the requested operation. Installation alone does not establish a runnable scientific handoff. |

## Official references

- [GitHub Actions secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [GitHub Actions organization policies](https://docs.github.com/en/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization)
- [Codespaces access to additional repositories](https://docs.github.com/en/codespaces/managing-your-codespaces/managing-repository-access-for-your-codespaces)
- [Who owns and pays for Codespaces](https://docs.github.com/en/codespaces/managing-codespaces-for-your-organization/choosing-who-owns-and-pays-for-codespaces-in-your-organization)
- [Student Education benefits](https://docs.github.com/en/education/about-github-education/github-education-for-students/about-github-education-for-students)
- [Actions billing and included allowances](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
