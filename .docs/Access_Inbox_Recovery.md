# Durable student enrollment inbox

The private controller keeps the existing repository-wide lifecycle concurrency
group. GitHub allows one pending run in a concurrency group and may replace that
pending run when another request arrives. Setting `cancel-in-progress: false`
protects the running job; it does not preserve every pending job.

Enrollment therefore uses open GitHub issues as its durable inbox. Issue events
are wake-ups. Each surviving issue run sweeps the inbox, and a scheduled sweep
requests recovery every fifteen minutes. An instructor can also select **sweep**
under the controller workflow's **Run workflow** menu without choosing a project.
GitHub can delay scheduled runs; this is not a fifteen-minute delivery guarantee.
Actions billing, repository settings and runner availability must permit a job
to start. A failed or canceled wake-up does not erase the enrollment issue.

## Request processing and ownership

The controller fetches each issue's current state, immutable ID, original author
and structured body. The project owner must match that author. The workflow
actor, an issue editor and issue comments are never enrollment authority. Existing
team membership, selected App installation, private personal project identity,
approved source and credential-readability checks still apply before provisioning.
Student source never executes in the controller.

A signed controller Actions-variable record binds the immutable issue ID to a
fingerprint of its original author ID, project and selected engines. It records
pending work before provisioning and completed work before posting the success
comment. Repeated wake-ups, whitespace edits and reopening an unchanged completed
request do not rotate credentials again. A substantive request edit creates a new
desired request. After preparing its pending receipt, the controller fetches the
issue again immediately before provisioning; observed closure or changed data
prevents that attempt. Closing an issue cancels future inbox processing; it is
not credential withdrawal. GitHub provides no transaction joining an issue read
to subsequent project writes, so closure during an already-started operation
cannot guarantee cancellation of that operation.

Completion receipts also retain the immutable repository ID. If a different
repository later uses the same name, an old completed issue refuses the identity
mismatch; it neither grants access nor repeats the old connection notification.

A completed receipt proves that request was processed. It does not prove current
membership, continuing authorization, successful module installation, licensed
engine execution or actual student Codespace access. Existing lifecycle and
calculation authorization checks retain their separate scope and limitations.

If provisioning is interrupted before its completion receipt is saved, a later
sweep may execute the request again. The existing signed generation ownership
records retain staged credentials and restrict cleanup to controller-owned
labels. Recovery is at least once, with cleanup-safe retries; it is not an
exactly-once multi-API transaction. A saved completion receipt lets a failed
success comment be retried without repeating project mutations. An ambiguous
comment response can still produce a duplicate comment.

## Bounded progress and recovery

Each run scans at most ten pages of one hundred open issues or pull requests,
admits at most twenty lifecycle attempts, and stops admitting work after 420
seconds. The workflow retains its ten-minute hard timeout. The admission budget
does not cap an individual multi-API attempt; a hard timeout may interrupt it,
leaving durable request and ownership state for recovery.

A signed cursor retains both the current scan window and the last visited issue
ID. The next run continues visiting that window before advancing to the next
window. Reaching the end wraps the scan to its beginning. This prevents twenty
failing requests from repeatedly taking priority over request 21, and prevents
page 11 from being permanently excluded. Closing issues can shift page offsets;
recurring complete cycles recover such shifts. Delivery still requires recurring
successful runs and sufficient API, variable-storage and billing capacity; there
is no unbounded throughput guarantee.

Failures do not stop the rest of a cohort. Workflow output includes aggregate
counts and up to one hundred issue IDs/numbers with controlled error messages;
additional details are explicitly marked truncated. Issue bodies, reader values,
the App key and upstream error bodies are excluded. Invalid or unauthenticated
per-issue receipts refuse that request and permit later requests to continue.
An unauthenticated global cursor or unavailable controller store stops the run:
the instructor must restore the reviewed signing-key/store authority, preserving
the signed lifecycle ownership records.

The instructor can inspect the failed issue numbers in the Actions log, correct
the stated membership/App/source/configuration prerequisite through GitHub's
supported interface, and request another **sweep**. Students need no terminal
commands, token entry or workflow edits. Do not delete authenticated ownership
records to bypass a failed check.

## Instructor withdrawal and its boundary

Once an authenticated instructor **deprovision** operation actually starts, it
persists a signed project hold before attempting withdrawal. A hold prevents
queued, edited or partially processed enrollment requests from restoring access.
The hold key and signed payload bind the immutable project ID obtained through
selected App read access, so renaming the same project cannot evade the hold.
Provisioning must observe that same immutable ID before any project mutation;
replacing a name with another repository between the hold check and provisioning
is refused.
Instructor lifecycle operations use the same identity binding for hold changes,
provisioning, reconciliation and withdrawal; successful explicit provisioning
releases only the already verified project's numeric-ID hold without resolving
its name again.
Reusing a name for a different immutable repository does not inherit that hold;
ordinary authorization still applies. Rename migration of existing signed
lifecycle ownership records remains a separate fail-closed instructor concern.
**Reconcile** preserves the hold and continues withdrawal. Only an authenticated,
deliberate **provision** that succeeds releases it. Project files, originals and
downloaded data remain subject to the existing preservation behavior.

Manual lifecycle dispatches themselves are not durably queued by this change.
A pending instructor dispatch can still be canceled before it starts and before
it saves a hold. Submitting a dispatch is not evidence that withdrawal occurred.
The instructor must verify an executed lifecycle receipt and resulting stores;
retry a dispatch that never started. A successful student-inbox sweep does not
establish that a canceled maintenance request executed.

## Acceptance boundary

The local protocol checks exercise actual HTTP, RSA signatures and libsodium
sealed-box encryption against an explicitly local peer. The twenty-request check
uses twenty distinct owners and project stores, one surviving sweep, a repeated
sweep with zero additional project mutations, and no delivered controller key.
Separate protocol failure cases cover interrupted completion, refused writes,
failed comments, changed/closed issues, tampered receipts, withdrawal holds,
pagination and progress beyond twenty failures and ten pages.

These checks do not execute GitHub's scheduler or concurrency service, provision
real student accounts, prove controller billing, or execute licensed chemistry.
The actual App/controller enrollment, new student Codespace, authorization and
bounded genuine calculations remain live acceptance requirements.
