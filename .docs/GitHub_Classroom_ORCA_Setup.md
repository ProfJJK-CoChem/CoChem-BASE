# Classroom50 and licensed Actions: instructor and student setup

The canonical student route uses a **personal private repository** for
calculations in its owner's GitHub Actions allowance and **Codespaces** for the
interface. Follow [private student projects](Private_Student_Projects.md) and
the [exact private staging guide](../docs/private_student_engine_staging.md).
Codespaces uses the student's own authorized GitHub identity to stage reviewed
assets; Actions uses its owning repository authority. No cross-owner credential
is copied into the student project. Organization-owned course repositories have
different billing and are not this personal calculation route.

## Student quick start

Open your actual personal private calculation project in Codespaces and follow
the browser-authentication/staging guide. Confirm the interface remains private,
prepare a supported ORCA or CFOUR job and review its exact method/state/basis.
Commit the request, then stage its exact bytes/commit/workflow/resources and
dispatch the receipt-bound job. Export alone does not execute chemistry.

Use `examples/jobs/water-single-point.json` or `water-harmonic.json` for bounded
ORCA practice; the CFOUR counterparts are `cfour-water-single-point.json` and
`cfour-water-harmonic.json`. HF/STO-3G neutral-singlet water exercises integration
and does not establish experimental frequency accuracy. The respective engine
guides retain supported operations, resource bounds and native acceptance checks.

Retain the actual run/attempt, original inputs, native outputs, scientific report,
digests and permitted result artifact. Submit results through the course's stated
Classroom50 process; a green scientific run is not automatically an assignment
grade. Inspect supported HDF5/harmonic bundles in Data Inspector without a local
licensed runtime. Cancel/status/download use the exact task identity. Cleanup
requires the genuine terminal run and deletes only its exact staged asset.

## Instructor setup

Use [the assignment deployment guide](Classroom50_Assignment_Deployment.md)
for Classroom50 setup, enrollment, template review and the one-student pilot.
Classroom50's management authority is separate from archive access. A student
personal project is a standalone private copy, not a public fork turned private.
Public BASE/TOPOS/TORQ source pins and the mandatory ecosystem kit remain reviewed
independently of licensed engine distribution. No shared archive credential is
copied into personal Actions.

For instructor-controlled collection repositories, verify actual organization
ownership and billing; that route does not use personal Actions minutes. Do not
infer cross-owner Codespaces access from a repository declaration or automatically
transfer licensed assets to another owner. Keep the course's review and license
authorization requirements.

### 2. Obtain the correct archive and record its checksum

For this workflow use exactly:

```text
orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz
```

This is the ORCA 6.1.1 Linux x86-64 shared build for Open MPI 4.1.8. A macOS,
ARM64, Windows or differently linked MPI build is not interchangeable. The
archive is about 472 MB in decimal units and expands to about 16.25 GiB; the
installer also requires 4 GiB of free reserve. The workflow prepares storage on
its disposable GitHub-hosted Linux runner and checks actual space before
extraction.

If the file is on Google Drive, download the original `.tar.xz` file first.
Do not extract, recompress or rename its contents before hashing. On Windows,
open **PowerShell** and run, adjusting the folder if necessary:

```powershell
$orcaArchive = Join-Path $env:USERPROFILE 'Downloads\orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz'
Get-Item -LiteralPath $orcaArchive | Select-Object Name, Length
(Get-FileHash -LiteralPath $orcaArchive -Algorithm SHA256).Hash.ToLowerInvariant()
```

WSL is not required to calculate this hash. On Linux, WSL or macOS:

```bash
# Linux / WSL
sha256sum orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz

# macOS
shasum -a 256 orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz
```

Record the 64-character checksum independently before upload. The reviewed
CoChem archive has checksum
`a0bc1d6d2c3c00620367bbc5dbf2b3a7018abc92d1ff65f06cec46f75350b9be`.
Use that value only for that exact reviewed archive. A different checksum must
be investigated against the original download, not changed merely to make a
failed run green.

### 3. Upload a private Release asset

1. Create a **private** repository owned by the course organization, for example
   `YOUR-COURSE/CoChem-ORCA`, initialized with a README.
2. Open that repository's **Releases** page and select **Draft a new release**
   or **Create a new release**. Create tag `orca-6.1.1` and title `ORCA 6.1.1`.
3. In the release editor, attach the original archive in the area for uploading
   release assets. Publish the release and verify that the `.tar.xz` appears
   under **Assets**. A Git tag without an attached published release asset is
   insufficient.
4. Keep repository access limited to authorized users. Do not include the
   archive in the course source repository or an Actions artifact/cache.

The normal Git push limit is 100 MiB per file. Uploading through a repository's
**Add file** page or committing the archive into Git is the wrong path. Release
assets have a separate limit of less than 2 GiB per file; this approximately
472 MB archive fits. You do not need Git LFS for this procedure.

Worked example used for CoChem's integration:

| Setting | Value |
| --- | --- |
| Asset repository | `ProfJJK-CoChem/CoChem-ORCA` |
| Release tag | `orca-6.1.1` |
| Asset filename | `orca_6_1_1_linux_x86-64_shared_openmpi418.tar.xz` |
| SHA-256 | `a0bc1d6d2c3c00620367bbc5dbf2b3a7018abc92d1ff65f06cec46f75350b9be` |

This is a private worked example, not a public download service or a credential
shared with every CoChem user. A new course must arrange its own authorized
access or private mirror of the approved archive.

### 6. Pin the approved distribution in the course source

Review `scripts/orca-distribution.json` in the course calculation repository.
Its `repository`, `release_tag`, `archive_name` and `sha256` must identify the
approved published asset. For a private mirror of the identical archive, change
the repository location and retain the verified filename, checksum and versions.
Keep `orca_version` at `6.1.1`, `openmpi_version` at `4.1.8`, `platform` at
`Linux`, and `architecture` at `x86_64` for this workflow.

Commit and review the manifest alongside the workflow. Do not turn an unverified
download response into the expected checksum. Repository variables are not a
substitute for reviewing and pinning the distribution manifest. Archive access,
physical acceptance and student jobs all read this same manifest; unreviewed repository overrides do not replace this identity.

Make sure the workflow files are on the repository's **default branch** before
expecting GitHub to show manual **Run workflow** controls. Configure Actions to
allow the reviewed workflows and required actions. The licensed acceptance
workflow does not run on untrusted pull requests. In **Organization Settings →
Actions → General → Fork pull request workflows**, leave **Send secrets and
variables to workflows from fork pull requests** disabled, and keep **Send
write tokens to workflows from pull requests** disabled. If a repository has
separate controls, keep the same settings there. Save the policy. Fork pull
requests can run permitted tests without these credentials; run private module
installation and ORCA jobs from the reviewed course branch. Never add
`pull_request_target` simply to grant an untrusted fork private archive authority.

### 7. Run the access check, physical acceptance and course pilot

Follow the student steps above in one pilot repository before distributing the
course. These are separate checks:

| Check | What a pass establishes |
| --- | --- |
| ORCA private archive access | The exact staged asset is accessible with owning authority and its SHA-256 is correct. |
| MPI installation | Pinned Open MPI 4.1.8 compiles and a genuine two-rank C++ collective executes. |
| ORCA provisioning | The complete approved archive is verified, extracted safely, and reports the required ORCA version. |
| BASE Stage 0 | The runner receives a fresh host-specific registry through all eleven setup phases. |
| ORCA calculation acceptance | Genuine serial and two-process water calculations converge through BASE; energies and published records agree. |
| Course pilot | Your approved student repository, permissions and assignment instructions work for an actual student account. |

A green BASE unit-test run or archive check does not replace the physical ORCA
acceptance. Keep the run URL, tested commit, artifact and instructor approval
in the course release record. Run a pilot again after changing the binary,
runtime, manifest, workflow, permissions or accepted BASE revision.

## Student pilot and other platforms

The personal-private Codespaces/staging/Actions/results/cleanup pilot is unrun.
Run it with a genuine authorized student project before course rollout, including
owning-token access to the private draft asset. Record each original result and
failure. Earlier upstream hosted ORCA observations are preserved separately in
[ORCA Actions setup](ORCA_Actions_Setup.md).

Local Linux/WSL, matching macOS builds and HPC installations require their own
supported native engines and actual execution-host allocation. Source download
and package installation cannot qualify unavailable scientific methods.

## Troubleshooting

- If private source access is denied, confirm approved lab membership and the
  student's stored browser login using the [private staging guide](../docs/private_student_engine_staging.md#browser-authentication-in-codespaces).
  Team membership alone does not extend an injected Codespaces repository token.
- If the receipt, request, workflow or resource identity changes, prepare and
  review a new task. A failed identity check cannot authorize a calculation.
- If a local registry checksum fails after a source update, retain the old
  record and run a fresh complete eleven-phase Stage 0 audit under the current
  code and installed engines. Do not rewrite its checksum manually.
- If an Actions run cannot start, check the personal repository owner's billing
  and runner settings. Retain failed-run diagnostics; queued or failed setup
  does not establish chemistry. The first genuine private staging pilot remains
  required before deploying the licensed route to the class.

## Official references

- [Classroom50 application](https://classroom50.org/)
- [Classroom50 official source and project identity](https://github.com/foundation50/classroom50)
- [Classroom50 quickstart](https://github.com/foundation50/classroom50/blob/main/wiki/Quickstart.md)
- [Classroom50 web teacher guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Teacher-Guide.md)
- [Classroom50 web student guide](https://github.com/foundation50/classroom50/blob/main/wiki/Web-Student-Guide.md)
- [Classroom50 assignment templates](https://github.com/foundation50/classroom50/blob/main/wiki/Assignment-Templates.md)
- [Fine-grained token management and prefilled forms](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [Permissions required for fine-grained tokens](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2026-03-10)
- [Release asset download permissions](https://docs.github.com/en/rest/releases/assets?apiVersion=2026-03-10#get-a-release-asset)
- [Using secrets in GitHub Actions](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
- [Creating and managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
