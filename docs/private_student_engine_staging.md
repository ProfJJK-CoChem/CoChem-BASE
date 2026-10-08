# Private engine staging for a student project

The interface runs in Codespaces. Calculations run in GitHub Actions in the
student's own **personal private repository**, using that repository's Actions
allowance. Codespaces uses the student's existing authorized GitHub CLI identity
to copy an approved laboratory release asset into a unique temporary draft
release in that project. Actions reads the exact staged asset with its own
repository token. There is no separate asset service or shared organization
credential in the student repository.

The implementation is `scripts/private_engine_assets.py`. It does not extract
credentials, reveal them with `gh auth token`, copy authentication files, record
credential values, commit archives, or upload licensed files as public Actions
artifacts. ORCA and CFOUR distribution identities come unchanged from the
existing reviewed distribution manifests and genuine installers. A descriptor
does not itself establish native scientific acceptance.

## First student pilot

No actual student-owned private project was supplied in this session. Private
provider staging, upload/readback, owning-token consumption, dispatch and cleanup
therefore remain **unrun**. Mathematical, local filesystem, process and source
transport checks are separate evidence lanes. They do not simulate GitHub or
qualify provider access.

1. Create/select the student's real personal private project. The student must
   own it, and the real authenticated GitHub API must report `private=true` and
   `owner.type=User`. Public and organization-owned destinations are rejected.
2. Open the interface in Codespaces with the student's authorized GitHub CLI
   identity. Confirm that identity can read the approved lab private release
   and can create draft releases in the student's project. Personal Codespaces
   permissions do not automatically grant cross-owner organization access;
   devcontainer declarations cannot supply that authorization. Missing actual
   access fails explicitly. Use supported GitHub authorization, without sharing
   credentials in chat or placing organization credentials in the project.
3. Commit the validated calculation JSON and the selected canonical workflow
   in the private project. Retain the exact branch, resulting commit, job-file
   SHA-256, cores and memory per core. Staging verifies those committed bytes
   through the real GitHub API. A calculation receipt cannot substitute another
   JSON file or alter resource controls from the same commit.
4. Stage one engine for that request. Keep the receipt, immutable intent and
   operational journal outside all Git checkouts, in a persistent private
   Codespaces directory. Compute the descriptor file pin from the exact
   independently reviewed descriptor; do not invent or replace checksums.
5. Dispatch with `asset_receipt`, `asset_receipt_sha256` and `asset_task_id`.
   The receipt is canonical JSON with no newline. The selected run name must
   contain the task's standalone 32-character hexadecimal identifier. Actions
   verifies the real run ID, source SHA, head branch/repository, workflow, live
   private repository, release marker, request and asset before reading bytes.
6. Verify genuine native provisioning and scientific jobs, and retain their
   own evidence. Local staged archive and installation cleanup belongs to the
   workflow. After the genuine owning-repository run is terminal, Codespaces
   invokes exact task cleanup and retains its private history.

A calculation staging invocation has this form; every uppercase placeholder
is supplied from the actual private project and reviewed file:

```sh
python scripts/private_engine_assets.py stage \
  --engine orca \
  --descriptor scripts/orca-distribution.json \
  --descriptor-sha256 REVIEWED_DESCRIPTOR_FILE_SHA256 \
  --repository STUDENT/PRIVATE_PROJECT \
  --ref refs/heads/main \
  --source-sha ACTUAL_COMMITTED_SHA \
  --workflow-path .github/workflows/orca_calculation.yml \
  --job-file jobs/approved-request.json \
  --input-sha256 ACTUAL_COMMITTED_JOB_SHA256 \
  --cores 2 --maxcore-mb 1024 \
  --receipt /workspaces/.cochem-private/request.json \
  --expires-hours 6
```

Use `--engine cfour` and the existing authentic CFOUR descriptor for the CFOUR
profile. Fixed acceptance/archive validation workflows require an explicit
null calculation intent, so the four job/resource CLI flags are omitted.
The controller supplies these contracts automatically; the command also
supports an independently inspectable first pilot.

## Receipt and transfer integrity

`schema_version=cochem.private-engine-staging/1` records the task/purpose,
complete reviewed distribution object, its canonical SHA-256, the original
descriptor-file SHA-256, actual source repository/release/asset IDs, version,
platform, architecture, source archive hash/size, exact destination identities,
project branch/commit/workflow/request, timestamps and full immutable intent
digest. No private download URLs or credential mappings enter the receipt.

The canonical encoding is UTF-8 JSON using sorted keys, separators `,` and `:`,
`ensure_ascii=False`, `allow_nan=False`, and no newline. Duplicate object keys,
unknown identity fields, unsafe paths, coercible IDs, nonfinite values and
changed hashes fail. Files are mode 0600; archives/receipts stay outside Git,
symlink paths are rejected, and a ready receipt cannot be overwritten.

The immutable intent is written before provider mutation. Its hash binds the
complete source/descriptor/ref/request tuple into the actual draft release
marker. Progress goes into a separate private journal. This prevents mutable
recovery metadata from silently changing the original provenance.

Source and destination downloads use exact numeric asset IDs through the real
authenticated `gh api` transport, stream under an exact byte-count/time bound,
and independently check the complete SHA-256. Upload uses the exact approved
`uploads.github.com` route, requires actual HTTP 201, checks exact returned
identity and performs a complete authenticated SHA/size readback before ready.
Provider digest metadata is also checked when supplied; it does not replace the
independent byte check.

The reviewed native GitHub CLI transport strips authentication after a
cross-host redirect and does not inject it again at storage hosts. Upload uses
`gh api --input` with a non-replayable file body; `gh release upload` is avoided
because its body can replay on HTTP 307/308. Verbose/debug output and forced
terminal/color output are disabled, and private provider stderr is discarded.
Actual process exit and HTTP status must agree. Metadata is bounded while read.

The reviewed installed CLI is gh 2.46.0-3, backed by upstream
[`api/http_client.go`](https://github.com/cli/cli/blob/b54f7a3bde50df3c31fdd68b638a0c0378a0ad58/api/http_client.go),
[`pkg/cmd/api/http.go`](https://github.com/cli/cli/blob/b54f7a3bde50df3c31fdd68b638a0c0378a0ad58/pkg/cmd/api/http.go)
and Go's redirect policy. This source review is not a live private-transfer
observation or reproducible native CLI build. Stock gh exposes no separate
redirect-host/HTTPS allowlist; the adapter uses fixed authenticated GitHub
API routes, accepts no user-provided URLs and relies on the genuine GitHub
transport for its storage redirects. A stricter independent host policy would
need a separately qualified transport.

## Expiry, cancellation and recovery

Asset-access expiry is positive and at most 24 hours. Actions and repair check
expiry before downloading and revalidate after transfer. The historical loader
can explicitly accept an expired receipt for observing/cancelling a run or
terminal cleanup; that option never relaxes asset consumption.

```sh
python scripts/private_engine_assets.py repair \
  --receipt /workspaces/.cochem-private/request.json
python scripts/private_engine_assets.py cleanup \
  --receipt /workspaces/.cochem-private/request.json \
  --receipt-sha256 RETAINED_READY_RECEIPT_SHA256 \
  --run-id ACTUAL_TASK_RUN_ID
```

Cleanup requires the genuine terminal run bound to the task, repository, branch,
source and workflow. It first changes the provider-visible release marker to
close new consumer admission, then audits the complete bounded run inventory.
Any active run using that workflow/source blocks deletion. Cleanup deletes only
the exact task-owned asset ID and confirms absence. It retains an empty private
draft release as the ownership ledger: GitHub has no atomic “delete release if
its asset set is unchanged” operation, so deleting the whole release after an
asset check could delete an unrelated concurrently added file.

A private GitHub 404 alone is not proof of deletion. Recovery revalidates the
authenticated owner/private repository and complete accessible draft-release
and asset inventories. Lost access, ambiguous identities and incomplete
inventories remain unresolved. A crash after successful exact asset deletion
can be reconciled without deleting another asset. Creation/upload recovery
reconstructs only the uniquely marked task release, verifies the original
intent and performs actual readback; missing/incomplete uploads remain retained
for explicit review rather than inventing a ready receipt.

GitHub draft releases have no automatic TTL. Expiry denies this adapter's new
downloads; it does not delete provider storage. Keep the Codespaces private
intent/journal until cleanup succeeds, and review abandoned tasks before
deleting the Codespace. An interrupted task does not authorize broad release,
tag or archive deletion.
