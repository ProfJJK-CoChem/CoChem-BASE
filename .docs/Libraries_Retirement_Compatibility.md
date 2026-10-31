# BASE shared Libraries retirement proposal

This change removes BASE's obsolete shared `Libraries` package and its sibling
TORQ search-path mechanism. It preserves proper BASE storage, local ML/PES
implementations and execution obligations. It does not implement or qualify
new TORQ science. Source review, fresh BASE-only installed-wheel conformance and
the corrected CREST branch's genuine Stage 0/native proof remain required.

## Import and caller disposition

| Existing surface | Disposition |
| --- | --- |
| `cochem_base.data.PESStore` and `cochem_base.data.cochem_base_pes_store` | Same guarded implementation, conversions and schema; unchanged source. |
| `Libraries.cochem_base_pes_store` | Removed obsolete producer; current source search found no direct consumer. Use the proper BASE data API explicitly. No shared-namespace shim. |
| `cochem_base.core_engine.cochem_core_auto_pes` | Same AutoPES, DeltaPESModel, NeuralCommitteeEstimator, numerical/serialization and held-out validation contracts. |
| `cochem_base.ml.krr`, `.active_learning` | Same local implementations. Configured AutoPES/KRR/neural-committee assertions remain intact. |
| `cochem_base.ml`, `cochem.ml` | Lazy supported exports; importing a package no longer eagerly imports missing TORQ objects. Root and `src` facade exports retain their respective supported names. |
| ML configuration/error classes defined in BASE | Remain available as data contracts, without advertising an available scientific producer. |
| `cochem.ml.models.ExactKernelRidgeEstimator` | Still the actual BASE estimator, not another model substituted under that name. |
| `cochem.concurrency.AtomicFileLock` | Same BASE lock class. |
| `cochem.concurrency.EphemeralScratchSession`, `resolve_hpc_safe_scratch` | Explicit unavailable `ImportError`; these were broken TORQ-backed object exports. Actual BASE scratch admission lives in `cochem_base.core.scratch`. |

Known retired scientific names raise `ImportError` naming the exact API and
missing managed canonical capability when explicitly requested. Unknown names
raise `AttributeError`. `__all__` lists supported exports; no placeholder classes,
mock calculations, object RPC, sibling checkout import or coinstallation occurs.

The inherited source layout resolves `cochem.ml.models` to
`src/cochem/ml/models.py`; the wheel's explicit package mapping selects
`cochem/ml/models/__init__.py` and its `ensemble` submodule. Source checks follow
the source module's actual supported API. Installed package/committee-schema
imports require separate fresh-wheel verification; no path manipulation makes
one plane impersonate the other.

Retired baseline/delta/dispersion names: `BaselinePhysicsEngine`, `DeltaMLEngine`,
`EMTBaselineEngine`, `GFN2xTBEngine`, `LennardJonesBaselineEngine`, `PM6Engine`,
`UnitHarmonizer`, `DispersionD3Layer`, `DispersionD3Config`,
`compute_coordination_numbers`.

Retired calibration names: `CalibrationSample`, `ConformalPredictor`,
`ConformalPredictorConfig`, `ConformalInterval`. BASE's own
`ConformalCalibrationConfig` and `ConformalCalibrationError` remain available.

Retired model/committee names: `ANI2xModel`, `ForceMatchingLoss`,
`CommitteeEnsemble`, `CommitteePrediction`, `compute_committee_moments`,
`get_available_vram_mb`, `compute_angular_cosine_similarity`,
`compute_conservative_forces`, `huber_force_loss`, `huber_scalar_loss`,
`cosine_cutoff_envelope`, `quintic_c2_envelope`.

Every old BASE `Libraries.*` module/export is removed, including stale DVR,
committee and cutoff implementations. Existing native xTB/MLFF calculation
routes are separate from the retired Python object names. Their actual supported
operations still require verified providers and engine authority.

Canonical TORQ currently has managed geometry, bounded scan, Löwdin and explicitly
scoped orbital-analysis operations. It has no managed DVR, training, committee,
conformal-calibration or delta-PES contract suitable for these object APIs.
Those remain named full-SRS work. Retirement does not close them or certify
PES/model/experimental accuracy. The retained BASE ML/PES functionality is not
deleted merely because some historical names reference TORQ.

## BASE scratch admission and corrected CREST boundary

`admit_scratch` reads the selected canonical registry through the shared proper
BASE descriptor-bound filesystem helper. It creates no lock or other authority
file. It requires an operational status, nonempty valid checksum, and the
schema's complete unique eleven-phase Stage 0 authority. It derives the
actual supported CLI summary location from the registry's audited artifact root,
not a guessed temporary directory or a relocated registry's neighboring files.

The actual CLI publishes `<audited artifact root>/Registry/setup_summary.json`.
Its embedded reports retain their producer-recorded `artifact_path` values.
Admission binds summary registry/root/status/dry-run state, each phase's canonical
report digest/status, and the actual bounded regular report files at those paths.
The CLI adds its measured `execution_time_sec` after each phase writes its raw
report. The enriched embedded report remains bound to the published canonical
digest; timing must be finite, nonnegative and not boolean. The raw report must
equal that embedded report with only this specific CLI field removed. Raw byte
hashes, enriched canonical hashes, measured timing and the named serialization
transform stay distinct; no other difference is accepted or described as equal
bytes. The initial draft's genuine-report refusal and exact eleven-field delta
are retained externally rather than rewritten as a pass.
Duplicate JSON keys, nonfinite JSON, symlink redirects, missing/changed reports
and evidence changed during admission are refused. This reuses the publisher's
canonical digest convention and `validate_stage0_scratch` phase-6/7 checks.

The registry scratch and actual phase-6/7 scratch must agree. Explicit conflicting
scratch environment values cannot redirect it. Source, immutable data and
installed runtime roots stay excluded. An active execution context can restrict
the operation to an existing child of the audited scratch; it cannot broaden
the permission. The resolver scaffolds no directory, creates no lock and rewrites
no authority. Paths retain their original absolute lexical spelling. Every
component is opened without following links; evidence is read through one
bounded regular single-link descriptor and rechecked against its current chain.
An ancestor rename or replacement cannot be normalized into apparent trust.

Creating a CREST operation revalidates the actual admission; a caller-created or
stale snapshot cannot grant permission. The private filesystem primitive creates
one exclusive `crest_<uuid>` child with mode 0700. It exposes no cleanup method.
The child remains a held `BoundDirectory` through input, diagnostics, execution
and ensemble reads. Its complete ancestor/device/inode chain is checked, rather
than only its leaf. Relative `input.xyz` plus the checked descriptor-alias cwd and
inherited directory descriptor prevent pathname replacement from redirecting
launch. Input and receipt publication use the shared atomic FD-relative helper;
no parallel filesystem implementation or global working-directory change occurs. No parent, neighbor, original archive or result
is deleted by this change.

The corrected legacy CREST consumer separately calls existing
`authorize_engine_execution` for **both** CREST and xTB, with the actual requested
thread count and matching audited allocation. `safe_subprocess_run` owns native
process containment, affinity/resource environment, timeout termination and
reaping; there is no new process controller. All accepted existing chemistry flags,
the 12 kcal/mol default energy window, requested energy window, 120-second
timeout and ensemble parser/original return fields remain intact.

This increment requires an explicit requested **neutral singlet with zero
unpaired electrons in the xTB execution profile**. It is not evidence that the
molecule's physical ground state is closed-shell. The actual caller contract is
integer `seed.info['charge'] = 0` and `seed.info['multiplicity'] = 1`, obtained
from the intended scientific request. Missing fields, bool/float/string state,
other states, conflicting charge/spin/unpaired/open-shell declarations and
incompatible explicitly supplied ASE charge/magnetic arrays are refused before
any engine. ASE's ordinary zero defaults, partial charges alone and electron
parity do not supply the missing request. The existing partial-charge consistency
convention is retained; no scientific convergence threshold changes.

This legacy route accepts only ordinary unlabelled element inputs with ASE's
unspecified/default masses. Any explicit ASE masses array, actual repository
isotope/nuclide/mass declaration (including nested nuclear metadata), or
isotope-bearing `rdkit_mol` is refused before calculator or engine work. Even
numerically default supplied masses remain an unsupported explicit declaration;
no isotope is inferred from an average mass. The receipt and returned conformer
metadata record this limited input profile, without claiming physical isotope
identity qualification. Canonical isotope-aware TOPOS functionality is separate.

The constructed command supplies explicit `--chrg 0 --uhf 0`; callers cannot
override them through flags. A copied seed and copied metadata fix the submitted
input context. The actual requested state/profile remain in the authorization
receipt and each returned ASE conformer's metadata; ground-state status remains
unverified. Existing conformer energy/source fields and return type are preserved.

The legacy union entrypoint validates this request before invoking a calculator
or GOAT/CREST search. Its original missing-energy refusal remains ahead of any
calculation, and its numerical union/deduplication body is unchanged. Both legacy
ASE callers pass state through, without a validated-state writer; the old
ConformerCandidate schema also lacks charge/multiplicity. These state-less callers
now fail closed. No caller or schema fills in zeros; a validated upstream state
handoff remains unfinished work. The ordinary canonical GUI uses its separate
qualified conformer route and is not replaced by this increment.

This route now explicitly invokes external GFN2-xTB with CREST's supported
`--gfn2 --legacy --xnam <audited absolute xTB>` mechanism. Canonical TOPOS already
uses this mechanism. PATH alone would not establish which engine ran because
stock CREST can use an in-process xTB library. This is an invocation-backend
correction, **not a blanket equivalence claim**. Actual child-executable witness
and genuine native qualification of this branch remain required.

The complete in-repository caller search found defaults
`--nci --nocross --noreftopo`, the frontend's explicit
`--gfn2 --nci --noreftopo`, and internal pass-through calls. Those four boolean
flags are preserved. Other caller tokens, alternate methods, executable paths,
thread/resource overrides, energy-window overrides or unknown arguments are
refused clearly; none is silently dropped. The bound operation supplies its own
audited `--xnam`, requested `-T` and existing `--ewin`.

Input, available captured `process_stdout.log`/`process_stderr.log`, any actual
native ensemble and `execution_authorizations.json` remain in the uniquely owned
scratch directory on success and handled failure. The existing broker is called with
`capture_output=True`, `text=False`, `stream_to_disk=False`, without live callbacks.
Actual available raw captured output is written through bound descriptors after
the existing subprocess broker returns or raises;
its plain-path streaming leaf opener is not used. Receipts distinguish decoded
text transcripts from raw exception bytes and explicitly report unavailable or
partial output. Timeout cleanup cannot recover output emitted after the broker's
partial capture; cancellation/interruption may supply no captured output. These
limits are retained, not represented as complete raw logs. The receipt records actual authorizations,
request/command/backend, scratch-source hashes, input hash and returned process
or parsing status. `ensemble_parsed` is a parser outcome, not minimum/population
or full scientific qualification. `last_work_directory` exposes the retained
location in the current engine object. No archive, download or reopen feature
is introduced. Process cleanup and scientific-file retention are separate.

The held cwd and newly bound consumer I/O do **not** establish race resistance
for all inherited launch-related I/O. In reviewed f96 source,
`core_engine/execution_authority.py:authorize_engine_execution` resolves and reads
its registry by pathname (around lines 49–54). The unchanged subprocess broker's
`verify_scratch_quota_and_io` resolves the cwd, creates/checks the directory and
opens its 64 KiB probe by pathname (around lines 1067–1124), while crash handling
uses existing pathname-based crash publication (around lines 1734–1756), including
`core_engine/crash_provenance.py::snapshot_process_context` and
`record_process_crash`. These exact functions, alongside
`core_engine/cochem_core_subprocess_broker.py::safe_subprocess_run` /
`verify_scratch_quota_and_io` and
`core_engine/execution_authority.py::authorize_engine_execution`, remain the
unresolved end-to-end filesystem backlog. Concurrent ancestor replacement can affect those inherited operations. This
increment neither bypasses their checks/caches nor claims to repair them. Its
scope is descriptor-bound scratch admission, consumer-owned input/log/receipt/
ensemble I/O, and Popen's actual cwd capability. The shared helper checks the
available descriptor alias (`/proc` or `/dev/fd`) and refuses if no supported
capability exists; actual final qualification remains Linux-only.

The ensemble read is bounded to **64 MiB**. An oversized, growing, redirected,
hardlinked or irregular member causes the operation to fail without returning
conformers; output is never truncated into a scientific result. The original
native files and available diagnostics remain retained. The unchanged parser
now receives the one immutable bounded byte snapshot through a private bytes
seam; its path entrypoint delegates after reading once. Digest, parent label,
energy/units, coordinates and nuclear-label grammar are unchanged. This is an
I/O seam, not an alternative parser or new model.

## Preserve original archives and measured-data semantics

No existing HDF5, uploaded original, native result, registry or phase report is
migrated or rewritten. The guarded proper BASE store remains byte-unchanged.
It rejects missing/nonfinite energies, conflicting units/protected rewrites and
malformed measured arrays before replacing a record. Different campaign,
trajectory, IPC and tensor stores are not consolidated by class name.

The removed producer could serialize a missing energy as an ordinary finite
zero. Without independent provenance, those bytes cannot distinguish its default
from a genuine explicitly supplied zero. Do not reinterpret every zero as missing
or retrospectively certify historical records. Existing values and provenance
stay as retained; missing quantities remain unavailable. The explicit-zero test
is declared schema input, not invented native chemistry.

Deleted source bytes are retained in Git history and the external proposal's
original baseline archive and five-file preservation inventory. Reverting source
is not an archive-schema migration and must not overwrite user data.

## Required acceptance before integration/release

The two existing ownership/measured-data test files retain their original
scientific assertions and add supported-export identity, explicit legacy refusal,
packaging exclusion, scratch/flag integrity and measured-data refusal controls.
The phase-report integrity test executes only an actual phase-6 filesystem audit;
it never fabricates a complete setup or engine authority. Filesystem allocation
checks are not scientific/native qualification.

Root must review the exact external diff, regenerate source-bound authority using
the supported procedure, and run appropriate immutable-source controls. A fresh
BASE-only wheel outside checkouts must contain no `Libraries` payload, have valid
RECORD/origins and import supported BASE APIs with no TORQ coinstallation/sibling
tree. Genuine complete Stage 0 and the **corrected CREST branch** must then prove
actual audited CREST/xTB child identities, requested resources, retained logs/
input/ensemble and failure behavior. Historical GUI or other CREST routes cannot
substitute for this branch. No scientific threshold, source guard or provider
isolation may be relaxed to obtain a pass.
