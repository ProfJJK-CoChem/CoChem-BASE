# ORCA calculations in a personal private project

The canonical student route is a personal private copy of CoChem-BASE. Its owner’s GitHub Actions allowance pays for calculations; Codespaces hosts the interface. Organization secrets are available to organization-owned repositories and are not inherited by a personal copy.

## Student setup

1. Create a **private** project repository in your personal account using the public BASE template, with your project name. Confirm that GitHub displays **Private** before opening the interface.
2. Accept the lab invitation and obtain read access to the instructor’s private engine repository. Membership alone does not authorize a Codespaces credential to access that repository.
3. Open your project in Codespaces. Use the private-project calculation panel with an authenticated GitHub identity that can read the approved lab asset and write releases and dispatch Actions in your own project. Additional-repository Codespaces permissions are limited by GitHub’s owner rules; a personal project cannot assume that an organization repository declaration grants access. Missing access must be resolved through authorized GitHub sign-in before staging.
4. Select the instructor’s approved ORCA distribution and calculation input. Review the exact version, archive checksum, task identity and resource limits. Stage the calculation assets and dispatch the owning project’s calculation workflow.
5. Use status, cancellation and result download in the same panel. Keep the retained task receipt and calculation provenance. After the run reaches a terminal state, clean up its temporary private release. An interrupted session can reconcile the original task; it must not create substitute results or delete another task’s assets.

The staging transaction checks the repository’s actual private visibility and personal owner, downloads an exact approved release asset, verifies its SHA-256, uploads it to a temporary private release, and verifies an authenticated readback. Actions consumes the same receipt and archive using its own repository identity. Lab credentials are never transferred to student projects.

## Browser authentication

Use [the Codespaces browser-authentication instructions](../docs/private_student_engine_staging.md#browser-authentication-in-codespaces) before private staging. The default interface selects the student's stored native GitHub CLI identity for each private operation, so the scoped Codespaces injection does not shadow browser login. The owning Actions workflow independently retains its platform authentication. No personal or organization credential is copied into the project.

## Scientific and licensing checks

The reviewed distribution descriptor records ORCA 6.1.1, its Linux x86-64 archive and OpenMPI 4.1.8. Installation verifies the archive and real executable before any calculation. A successful download is not scientific acceptance: the actual calculation must complete and its native outputs must be validated independently.

Licensed archives and installed executables remain outside Git. The temporary release is private; workflows must not upload the archive or installed runtime as calculation artifacts. The instructor must confirm that the students and the approved distribution route satisfy the engine’s license. Students receive only assets to which their own lab membership already grants access.

The ORCA distribution is large. Check disk, runtime dependencies and approved runner resources before provisioning. Failed installation or missing native outputs leaves the operation unavailable; there is no replacement engine or generated success output.

## Troubleshooting

| Problem | Required check |
| --- | --- |
| Lab repository returns 404 | Student membership, approved GitHub authorization and exact source repository; do not copy the lab’s shared credential. |
| Staging rejects the project | It must be genuinely private, personally owned, and owned by the authenticated student. |
| Actions cannot obtain the asset | Receipt identity, expiry, task/release ownership, actual workflow/run binding and owning-project permissions. |
| Job never starts | Inspect GitHub Actions billing, included usage and repository policy. Codespaces usage cannot pay for Actions. |
| Job ends without native results | Retain its failed evidence and error; do not label it a completed scientific calculation. |
| Temporary assets remain after cancellation | Use the original task’s cleanup or repair path after checking the actual provider lifecycle. |

Live Codespaces-to-Actions acceptance requires a genuine authorized private student project. Offline software checks do not qualify that provider journey.
