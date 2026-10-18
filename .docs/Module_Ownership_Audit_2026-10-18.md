# BASE, TOPOS and TORQ module ownership audit

**Status: unresolved ownership defects; documentation and handoff, not migration acceptance.**

BASE genuinely downloads the reviewed TOPOS and TORQ sources from their canonical
GitHub repositories and executes them in separate verified environments. It also
ships overlapping module namespaces and implements some TORQ scientific work in
its adapter. Both facts matter: removing the isolated installer would make the
problem worse, while keeping it does not resolve the duplicated ownership.

This inspection is bound to BASE revision
[`d423c02a5bf9f15dd9626d46e17b6650414633c1`](https://github.com/ProfJJK-CoChem/CoChem-BASE/tree/d423c02a5bf9f15dd9626d46e17b6650414633c1).
Later GUI wording and public-source access fixes are separate changes. The
findings below do not assert that those changes completed this migration.

## Requirements and intended ownership

The governing baseline is [SRS Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md)
plus the additions in the [BASE architectural proposal](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md).
Their requirement numbers are not interchangeable. The user's explicit deployment
direction also applies: students obtain BASE only; BASE installs the other modules
from their canonical repositories and presents their capabilities in its GUI.

Chunk 17 WBS 17.1.3 requires isolated environments without Python search-path
leakage. Proposal §3.2 assigns registry authority to BASE; §3.3 requires native
environment isolation. Chunk 17 REQ-BASE-006 assigns conformer-pool ingestion and
the two-stage structural sieve to BASE, and proposal §3.14 assigns CREST/GOAT
execution and merging to BASE. These scientific duties must survive cleanup.
The SRS also assigns BASE geometry, engine execution and validation work; it does
not justify deleting every file with a TOPOS or TORQ name.

| Owner | Responsibility after migration |
| --- | --- |
| BASE | Installation, verified version selection, optional-engine setup, registry and resource authority, ingestion, SRS-required BASE geometry/conformer processing, subprocess containment, immutable handoffs, student GUI and result presentation. |
| TOPOS | Canonical TOPOS scientific workflows, provider contract and its native scientific results, using BASE execution authority. |
| TORQ | Canonical TORQ scans, electronic/bond analyses and other TORQ scientific products, with typed provider operations and native evidence. |
| BASE adapters | Validate and transport requests, invoke the verified provider, validate returned identity/status/artifacts, and preserve cancellation and failure evidence. Do not maintain a second implementation of the provider's science. |

## What the current implementation actually does

The [reviewed catalog](https://github.com/ProfJJK-CoChem/CoChem-BASE/blob/d423c02a5bf9f15dd9626d46e17b6650414633c1/scripts/module-distribution.json#L157)
selects official repositories and exact commits. `scripts/manage_modules.py`
`fetch_module()` fetches that commit and checks out a detached source tree;
`install_module()` builds a wheel from a disposable copy and installs it into its
own environment. Source, wheel, installed-package and environment identities are
retained and rechecked. Package names alone are insufficient evidence of installation.

`src/cochem_base/interfaces/module_execution.py` invokes the receipt's Python
interpreter with `-I -B`, excludes inherited Python/source overrides, uses a fresh
working directory, and checks provider-file origin and hashes. The local research
GUI calls `execute_provider_request()`, which reaches this adapter path. The
Actions worker uses the same request/execution service after provider installation.
The inspected isolated route is configured and guarded to import the canonical
TORQ wheel rather than BASE's bundled namespace; this audit did not execute that
route.

The TOPOS adapter's old `core_engine.01_INGEST_GC` geometry fallback is compatibility
support for an older installed provider. The current pinned TOPOS exposes `topos`
and follows the modern branch. This fallback is not evidence that the current
student route substitutes BASE's `cochem_topos` files for the canonical TOPOS source.

## Confirmed defects

1. **Overlapping packaged namespaces.** BASE's `pyproject.toml` explicitly includes
   `cochem_topos`, `cochem_torq`, `cochem.torq`, shared `cochem.*`, `Libraries` and
   `scripts` packages. `MANIFEST.in` also includes the containing trees in source
   distributions. The tracked-source inventory identifies compatibility
   wrappers, real scientific implementations and internally duplicated trees.
   It does not classify all of them as unused.
2. **Actual package-path collisions.** BASE's package-directory mappings at the
   audited revision overlap the retained canonical TORQ wheel at **115 Python
   paths; 37 have different bytes**. Examples include
   `cochem/concurrency/subprocess_broker.py`, `cochem/core/context.py`,
   `cochem/core/process_reaper.py`, `cochem_torq/__init__.py` and
   `Libraries/cochem_torq_dvr.py`. Installing both distributions in one interpreter
   can overwrite files; installation order must not define scientific authority.
   This is a static comparison against an existing TORQ wheel, not a newly built
   BASE-wheel acceptance run. Non-Python resources and dependency-package
   collisions were outside this count.
3. **Scientific work remains in the BASE TORQ adapter.** In
   `scripts/module_adapter_torq.py`, `research_scan()` constructs mass-COM scan
   geometries and drives evaluations; `wiberg_lowdin()` reconstructs a density,
   orthogonalizes it, and computes bond indices and charges. The electronic
   evaluations come from canonical TORQ's real PySCF backend, but the scan/analysis
   implementation belongs in TORQ. BASE records its adapter hash separately;
   these findings do not establish fabricated calculation results.
4. **Public-module access was incorrectly treated as private access.** At the
   audited BASE revision, GUI submission and the student Actions installation
   step reject absent private-source authorization even for these public
   repositories. This has a separate correction path. Public source access does
   not establish licensed-engine access, student account permissions, or a
   completed student Codespace pilot.

The second inventory agent found 30 files under `cochem/topos/` and 30 under
`src/cochem/topos/`, identical pair-for-pair at the audited revision. BASE also has
six `cochem_topos/` files, 17 `cochem/torq/` files, and nine `src/cochem_torq/`
files: **92 tracked namespace files** in these five groups. The [complete inventory](evidence/2026-10-18-module-ownership/tracked-source-inventory.json)
contains additional groups and static import references. An import inventory is
not proof that a branch can never execute.

## Canonical repository observations and update incompatibility

Both repositories were observed as public on 2026-10-18. The observed `main`
commits may advance; they are not recommended replacements without qualification.

| Module | BASE's reviewed pin | Observed canonical `main` |
| --- | --- | --- |
| TOPOS | [`b157b7e210aee5bdfa09c22270d77d794f52cdde`](https://github.com/ProfJJK-CoChem/CoChem-TOPOS/commit/b157b7e210aee5bdfa09c22270d77d794f52cdde) | [`a6f763c5efce85b6cc3ed7870427f4a6686f3d5d`](https://github.com/ProfJJK-CoChem/CoChem-TOPOS/commit/a6f763c5efce85b6cc3ed7870427f4a6686f3d5d) |
| TORQ | [`4ce8eecba56e91e27c6abb32473b2ee4d44767c4`](https://github.com/ProfJJK-CoChem/CoChem-TORQ/commit/4ce8eecba56e91e27c6abb32473b2ee4d44767c4) | [`e0019e7b0150e56a425942a06094b55cb60e0b73`](https://github.com/ProfJJK-CoChem/CoChem-TORQ/commit/e0019e7b0150e56a425942a06094b55cb60e0b73) |

The pinned TOPOS supports a verified TORQ sidecar receipt and a compatible BASE
version range. This lets TOPOS use BASE authority while TORQ remains in a separate
environment. The observed TOPOS `main` removes `_verified_torq_sidecar()` and its
discovery branch, and declares both `CoChem-BASE==1.0.1` and
`CoChem-TORQ==0.1.0` as ordinary dependencies. Moving BASE's pin to that revision
without another change would bring the overlapping distributions back together
and select a different BASE dependency. **Do not repair this by bypassing package
integrity checks or importing a checkout through `sys.path`.**

At both inspected TORQ commits, `cochem_torq.ecosystem:module_provider` returns
discovery metadata and contract names. It does not advertise the scientific
operation metadata and callable expected by BASE's `_extension_provider()`.
That metadata is not execution authority. The BASE adapter currently delegates
only qualified `nbo_analysis` and `wiberg_nao` extensions through that future
contract; no such executable contract was found in the inspected TORQ entry point.

## Handoff for the canonical module agents

### TORQ: publish the scientific provider, then remove the duplicate implementation

Implement and qualify the provider **in CoChem-TORQ**, not in a new bundled copy
inside BASE. Extend the existing `cochem.modules` entry point with a versioned
operation contract. BASE currently recognizes `scientific_api_version =
"cochem.module-provider/1"` together with `integration_contract =
"cochem.module-handoff/1"`. Agree any incompatible evolution with BASE and version
it explicitly; a matching version string alone must never grant an operation.

The contract needs a unique operation list, explicit scope and availability for
each operation, actual required-runtime observations, and a callable owned by
the installed TORQ wheel. The receiving callable accepts `handoff_path`,
`output_directory` and `registry`. Request identity, atom order/isotopes, electronic
state, units, resource limits and output identity must remain explicit.

| Operation | Required migration behavior |
| --- | --- |
| `geometry_analysis` | Move the remaining TORQ-owned geometry-analysis assembly behind its canonical API; preserve defined/undefined axes, isotope treatment and actual provider evidence. |
| `research_scan` | Own scan validation, explicit nuclear masses, mass-COM geometry construction, native electronic evaluations, partial-point status and retained artifacts. Preserve the present rigid two-fragment scope. A relaxed or multidimensional scan is a separately specified operation, not an unnoticed change to this one. |
| `wiberg_lowdin` | Own restricted converged/stable checkpoint validation, density/overlap checks, Löwdin orthogonalization, charges and bond-index calculation. Preserve the name and definition; these are not NAO Wiberg indices or NBO analysis. |
| `nbo_analysis`, `wiberg_nao` | Advertise only an actual executable canonical producer with its required runtime evidence. Missing optional runtime disables the affected operation. Do not substitute Mayer or Löwdin indices. |

Return the existing strict `cochem.module-operation/1` envelope or a coordinated
versioned successor, including module/operation/input identities, status, exact
scientific scope, result artifacts and provider-file hash. Distinguish completed,
partial, failed, cancelled and unavailable work. A successful serialization or
import is not a successful scientific calculation.

### TOPOS: retain separate environments and canonical BASE authority

Restore the verified separate-TORQ receipt contract, or introduce an equivalently
verified file/process protocol. Do not require a shared interpreter until package
ownership is demonstrably disjoint. Keep its actual BASE registry, executable
authorization, resource ceilings, immutable scientific record and native evidence
checks. Publish compatible dependency metadata, then provide a precise commit for
BASE to qualify. Existing source-discovery and real handoff tests must establish
which distribution and files execute.

### BASE: remove obsolete ownership after the canonical APIs are ready

Keep the reviewed installer and isolated execution path. Inventory import clients
before removing foreign namespaces from wheel and source packaging; relocate genuinely BASE-owned
implementations into BASE namespaces where needed. Remove obsolete copies rather
than leaving a fallback that silently preserves the old science. Update the TORQ
adapter to transport, validate and delegate the operations above. Keep student
forms, result visualization and provenance inspection in BASE. Preserve all
input modes, isotope identity, optional-engine behavior and local/WSL/macOS/HPC/
Actions routes.

Pin the qualified canonical revisions only after integration evidence passes.
Preserve existing projects' structures, jobs and results through upgrades and
rollback. Do not let the presence of an importable bundled namespace enable a
module or label it installed.

## Acceptance criteria for the migration

1. **Source ownership:** build the release wheels in clean environments; inventory
   every installed file and confirm BASE no longer publishes the removed module
   namespaces. Retain source commit and wheel hashes. If any distributions remain
   in separate environments because of other overlaps, prove that boundary and
   document the remaining overlaps rather than claiming they are gone.
2. **Origin and negative checks:** run from outside the checkouts, with no editable
   installs or Python search-path overrides. The adapter must reject missing,
   changed, mismatched or ambiguous providers and changed handoffs; it must not
   fall back to a BASE scientific copy. Verify interpreter, callable, wheel RECORD
   and provider source before and after execution.
3. **Scientific equivalence:** retain the original assertions and thresholds in
   `tests/base/test_module_adapter_torq.py`, module execution/handoff tests,
   student research/report tests and affected scientific suites. Move tests with
   ownership when necessary and add BASE boundary tests. Do not delete numerical
   assertions or replace actual native execution with a fabricated provider to
   make the migration pass.
4. **Mass and scan invariants:** preserve explicit isotope aliases, measured
   principal-isotope convention, rejection of unspecified radioelement mass, and
   preview/execution agreement. The existing mixed-fragment test requires the
   requested mass-COM separation within `1e-12` angstrom. Preserve rigid internal
   geometry, collision checks, actual per-point artifacts and honest failed or
   uncomputed points. Rerun real native scans; compare like-for-like method,
   electronic state, geometry and engine versions using the existing acceptance
   tolerances.
5. **Bond-analysis invariants:** preserve converged stable restricted SCF evidence,
   checkpoint geometry and energy identity, overlap positivity, density symmetry,
   electron count, total charge and immutable matrices. Existing implementation
   checks include checkpoint-energy agreement within `1e-8` hartree, minimum
   overlap eigenvalue above `1e-10`, and density/charge conservation within `1e-7`.
   Any justified scientific change needs an independent review and its own
   acceptance evidence, not a weakened migration gate.
6. **Real end-to-end work:** fresh BASE installation must download the canonical
   modules and execute a bounded native scan and bond analysis through the GUI
   and Actions, with downloadable results whose provider identity is inspectable.
   Verify optional-engine absence, cancellation, partial/failure reporting and
   result retrieval. Prove student Codespace/account access in its own pilot;
   instructor-run jobs do not establish it.
7. **No SRS regression:** run the complete required BASE profile and relevant
   canonical module profiles. Preserve BASE's SRS-assigned ingestion, registry,
   geometry, conformer and native execution responsibilities. Independently
   review any intentional pinned-source/hash-gate update. Publish exact tested
   revisions and unresolved external prerequisites.

## Evidence and limits of this audit

The audit performed read-only source/AST inspection, GitHub repository metadata
and Git-ref inspection, canonical source comparison, and byte comparison against
an existing pinned TORQ wheel. It did not execute chemistry, import the provider,
rebuild BASE, install combined distributions, or rerun acceptance tests. The clones
used the available session Git context; this audit does not claim a separate
credential-free fetch acceptance. No upstream files were changed.

Portable evidence is listed in the [evidence README](evidence/2026-10-18-module-ownership/README.md).
It includes exact source revisions, file hashes and all 115 compared paths. It
contains no licensed executables, runtime archives or authentication values.
The package overlap, upstream compatibility and provider ownership work remains
open until the criteria above are demonstrated and published.
