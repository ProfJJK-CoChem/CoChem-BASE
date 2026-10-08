# Reviewed public sources and mandatory CoChem ecosystem

The canonical student route uses a **personal private repository** for
calculations in its owner's GitHub Actions allowance and **Codespaces** for the
interface. Follow [private student projects](Private_Student_Projects.md) and
the [exact private staging guide](../docs/private_student_engine_staging.md).
Codespaces uses the student's own authorized GitHub identity to stage reviewed
assets; Actions uses its owning repository authority. No cross-owner credential
is copied into the student project. Organization-owned course repositories have
different billing and are not this personal calculation route.

BASE, TOPOS and TORQ are separate producer/consumer packages with reviewed
immutable source and wheel identities. Public core sources use ordinary public
GitHub retrieval. Licensed ORCA/CFOUR assets follow private task staging and
are never part of a public source or module kit. A private optional sibling
requires the user's independently authorized read access.

## Source and operation authority

`scripts/module-distribution.json` is the reviewed catalog. A newer `main` does
not change an installed pin. Review a new catalog and its companion wheel,
setup-helper and BASE bootstrap identities before installing a replacement.
Keep separate interpreter environments: repositories can share Python package
names while requiring incompatible dependencies.

The modern TOPOS `topos_handoff` entry requires the complete reviewed mandatory
BASE/TOPOS/TORQ kit. Its current typed operation names include energy, gradient,
optimize, search, frequency, thermochemistry, association and matrix. Admission
of a typed request does not establish that its scientific capabilities, engines
or required references are available. The installed provider validates the full
request, physical authority, units and actual native evidence.

The older geometry SDK is a separately pinned profile, not an interchangeable
modern calculation provider. TORQ's separately advertised `geometry_analysis`
adapter evaluates supplied geometry; it does not optimize it or establish an
experimental rotational spectrum. Keep exact isotope/state/frame/unit lineage.
Do not relabel a connectivity heuristic as electronic structure.

## Mandatory kit installation

Use an extracted complete kit with all three reviewed noneditable wheels,
source identities, helper and inventory. Self-computed checksums are integrity
records, not a trust anchor. The current installed BASE distribution and the
reviewed catalog must agree independently. Editable or substituted packages,
missing files, symlinks and changed wheel/helper identities are rejected.

From the supported installed BASE interpreter, use the existing module manager:

```sh
python -I -m scripts.manage_modules list --json
python -I -m scripts.manage_modules install --modules topos \
  --root /external/approved-module-root \
  --ecosystem-kit /external/extracted-reviewed-kit --json
python -I -m scripts.manage_modules verify --modules topos \
  --root /external/approved-module-root --json
```

The paths are placeholders for actual external storage and kit bytes. Installation
must execute with the supported noneditable BASE environment, not a source-tree
override. Retain the real kit, install and verification records. Installing TOPOS
installs its mandatory companions; source fetch alone does not install a package.
Source-only catalog entries remain source-only, and packaging defects or absent
execution adapters are explicit failures rather than invented installed modules.

## Actions request route

`ecosystem_modules.yml` separates `fetch`, `install`, `geometry_analysis` and
`topos_request`. For modern TOPOS, select only `topos` and its complete request;
do not submit the old geometry operation. The mandatory kit is selected by an
actual successful same-repository run and exact artifact name/subdirectory on
an explicit private default-branch dispatch. No arbitrary artifact URL or
unreviewed substitute kit is accepted. Inspect `scripts/hosted_module_kit.py`
and the current workflow for the complete source, workflow and artifact binding.

Supply the actual committed request JSON and matching XYZ, resource/receiver
budget and provider profile. `scripts/module_request.py` validates the request
boundary; the installed provider retains its own capability and derivative gates.
The free-engine profile remains separate from any licensed profile. Licensed
TOPOS hosting requires an explicitly integrated private staging/owning-token
provisioning path and genuine deployment evidence; an offered workflow choice
or package installation does not qualify it.

Download the genuine same-run/attempt artifact and verify its source, kit,
request, native artifacts and manifest digests. A failed request retains its
failure evidence. No publication, chemistry or TORQ calculation is inferred from
import or receipt acknowledgment alone.

## Codespaces and other hosts

Use Codespaces for installation, request inspection, approval and submission.
Keep the dashboard port private. Same-owner devcontainer repository declarations
require real authorization and a new Codespace after permission changes; they
cannot grant access across owners. Public sources need no copied lab credential.
For private sources, use the student's existing authorized GitHub identity and
verify actual access before installing. Installation does not impersonate an
instructor or make private membership available in personal Actions.

Local Linux, WSL, macOS and HPC installations use their own compatible native
engines, Python profiles and genuine allocation registry. The installed module
does not submit a Slurm job or reuse another machine's CPU/RAM authority. Every
scientific operation needs its own available provider and retained evidence.

The [TOPOS student deployment guide](../docs/topos_student_deployment.md) explains
the BASE GUI's **Open complete TOPOS interface** control, the installed
`python -I -B -m scripts.module_dashboard` equivalent, private Codespaces port
forwarding, and canonical intake of previous GOAT/CREST starting states. It uses
the same reviewed mandatory environment and BASE registry as the typed receiver.

## Acceptance boundaries

Record source fetch, package installation, integrity verification, actual native
operation, independent scientific accuracy and deployed student lifecycle
separately. Unsupported quantities remain unavailable with their reasons.
Neither all-three-package presence nor a successful geometry result qualifies
the complete TOPOS/TORQ SRS. Current-source acceptance must retain nonempty real
receipts; prior runs remain bound to their own source.

See [TORQ's reviewed ensemble contract](https://github.com/ProfJJK-CoChem/CoChem-TORQ/blob/main/docs/TOPOS_HANDOFF.md)
and [TORQ readiness](https://github.com/ProfJJK-CoChem/CoChem-TORQ/blob/main/docs/development/release_candidate_readiness.md).
The reviewed ensemble-import environment and BASE's mandatory calculation kit
are different profiles and may carry different source pins.
