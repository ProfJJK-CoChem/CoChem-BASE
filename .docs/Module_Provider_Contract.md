# CoChem module provider contract

BASE is the sole student installation, ingestion, setup and GUI entry point. A student opens the BASE repository, supplies monomer or complex XYZ files, selects a calculation in BASE and views its results in BASE. Providers run in separate verified environments; students do not open another module repository, install its dependencies in a terminal, edit JSON or open its separate GUI.

This contract defines compatible provider transport and presentation. The provider owns its scientific methods, engine qualification, native execution and accuracy evidence. Installation and callable discovery establish neither scientific completion nor universal chemical accuracy.

## Installed provider identity

Publish the wheel's entry point under `cochem.modules`, using the canonical module ID:

```toml
[project.entry-points."cochem.modules"]
torq = "cochem_torq.ecosystem:module_provider"
```

The entry point is a zero-argument metadata function. Discovery-only metadata remains supported for old geometry adapters. Scientific extensions declare the exact versioned contract:

```python
def module_provider():
    return {
        "module_id": "torq",
        "distribution": "CoChem-TORQ",
        "integration_contract": "cochem.module-handoff/1",
        "scientific_api_version": "cochem.module-provider/1",
        "operations": ["nbo_analysis", "wiberg_nao"],
        "execute_handoff": "cochem_torq.ecosystem:execute_handoff",
        "scientific_apis": {
            "nbo_analysis": {
                "available": False,
                "reason": "The separately licensed NBO runtime is unavailable.",
                "required_engines": ["orca", "nbo"],
                "supported_engines": ["orca"],
                "scope": "Native NBO donor–acceptor analysis of the selected real wavefunction.",
            },
            "wiberg_nao": {
                "available": False,
                "reason": "A qualified native NAO producer is unavailable.",
                "required_engines": ["pyscf"],
                "supported_engines": ["pyscf"],
                "scope": "Wiberg bond indices in the natural atomic orbital basis.",
            },
        },
    }
```

The example reports unavailable operations deliberately; it is not a working NBO implementation. Set `available` from actual runtime and method qualification. Merely listing an operation, importing a distribution or finding a filename must not activate it. Declare the engines the implementation actually needs; do not copy the example's engine lists into a different implementation.

When an operation is available, its definition must also contain `runtime_receipts`, keyed by every `required_engines` entry. Each receipt records `available: true`, the observed nonempty `version`, and a real file's `sha256`. Native programs (`orca`, `cfour`, `nbo`) use an actual `executable_path`; the library engine `pyscf` uses its actual `module_file`. BASE independently checks that the observed file exists, native programs are executable and its bytes match. These paths come from the trusted provider's runtime discovery, never from student request options. The native handler still owns exact version, licence, full installation and method/state qualification and must recheck the fresh execution authority before launch. File existence and a version label alone are not scientific accuracy evidence.

The handler can also be returned as an actual Python function. It must live in the installed `cochem_torq.*` namespace, be present in the wheel's file record and accept all three keyword parameters below. BASE hashes its installed source, verifies its isolated installation before and after execution and accepts only reviewed operations intersecting its actual runtime capability report.

## Execution boundary

```python
def execute_handoff(*, handoff_path, output_directory, registry):
    """Return a strict cochem.module-operation/1 dictionary."""
```

`handoff_path` is the retained BASE `cochem.module-handoff/1` manifest. Its copied artifact is relative to that manifest and has an exact size, SHA-256 and scientific metadata. `output_directory` is the job's owned artifact directory. `registry` is a fresh, job-specific Stage 0 registry path, or `None` for a genuinely registry-independent operation. A missing required registry or engine prevents execution; it does not authorize fallback to another method.

The receiver must:

1. Read and validate the manifest's schema, canonical recipient, operation and options. Verify the artifact's bytes, size, kind, nuclear identity and ordered coordinates. Reject paths escaping the package, links, unsupported options and nonfinite values.
2. Preserve the student's original input and isotope identity. Electronic engine decks can use the corresponding elemental labels, while all handoffs retain the ordered nuclides.
3. Qualify the exact engine, method, basis, charge, multiplicity and resources. Check the fresh Stage 0 authority and every additionally required native runtime. ORCA does not include a separately licensed NBO program merely because ORCA itself is installed.
4. Run actual calculations in isolated owned directories, obeying the admitted process, memory, wall-time and cancellation limits. Preserve native inputs, outputs, version, executable hash, geometry and convergence evidence. No fabricated quantities, zero defaults for absent results, method substitutions or unexecuted scan energies are permitted.
5. Publish strict JSON with finite present values and explicit unavailable quantities. A failed or unrun point has no measured energy. Retain successful lower-stage measurements after higher-stage failure; report `partial`, `failed`, `timed-out`, `cancelled` or `unavailable` truthfully.
6. Recheck unchanged handoff and source bytes. Return the exact provider-file hash and input artifact hash. BASE then independently revalidates the installation and receipt.

For the advanced TORQ analysis operations, BASE's data-only options are:

```json
{
  "engine": "orca",
  "method": {"name": "HF", "basis": "def2-SVP"},
  "charge": 0,
  "multiplicity": 1,
  "cores": 2,
  "memory_mb": 1024
}
```

This is a transport example, not an approved vdW protocol. Select only engine/method/state combinations actually qualified by the installed provider. The current classroom transport bounds are charge −4 through +4, multiplicity 1 through 5, one or two processes and 256–2048 MiB total provider memory. A provider can impose narrower bounds. No user-supplied executable path, Python module, command, arbitrary source repository or environment variable is accepted through these options.

BASE owns the form that produces these requests. Students do not author them.

## Native operation receipt

The result is a dictionary of this shape:

```json
{
  "schema_version": "cochem.module-operation/1",
  "module_id": "torq",
  "operation": "wiberg_nao",
  "status": "completed",
  "input_sha256": "<SHA-256 of copied student XYZ>",
  "provider_file": "<actual installed handler source path>",
  "provider_sha256": "<SHA-256 of that handler file>",
  "scope": "Wiberg bond indices in the natural atomic orbital basis of the selected native wavefunction.",
  "result": {
    "analysis_performed": true,
    "analysis_kind": "wiberg_nao",
    "atoms": ["<ordered nuclear label>"],
    "coordinates_angstrom": [["<actual x>", "<actual y>", "<actual z>"]],
    "bonds": [{"atom_i": "<zero-based index>", "atom_j": "<zero-based index>", "value": "<actual measured index>"}],
    "units": {"bond_index": "dimensionless"},
    "provenance": {
      "native_input_sha256": "<actual hash>",
      "native_output_sha256": "<actual hash>",
      "engine_version": "<actual version>",
      "engine_binary_sha256": "<actual hash>",
      "artifact_manifest": "<safe relative manifest path>"
    }
  }
}
```

Angle-bracket entries above are documentation placeholders and must be replaced by actual typed values. Coordinate, bond and energy values in executed receipts are numbers, never these strings.

All atom indices refer to the preserved order of the complete input geometry. Do not turn arbitrary graph connectivity into measured bond indices. NAO Wiberg, Löwdin-orthogonalized AO Wiberg and Mayer indices remain separately named observables; they must not be relabelled as one another.

For `nbo_analysis`, the integrated report expects:

```json
{
  "analysis_performed": true,
  "analysis_kind": "nbo",
  "transitions": [
    {
      "donor": "<native donor orbital label>",
      "acceptor": "<native acceptor orbital label>",
      "stabilization_kcal_mol": "<actual finite nonnegative E(2)>"
    }
  ],
  "units": {"stabilization": "kcal/mol"},
  "provenance": "<actual native program/version/hash and retained artifact receipts>"
}
```

The graph displays labelled donor→acceptor interactions. Multicenter orbital labels remain intact. It does not invent orbital shapes, map them to guessed single atoms or infer missing transitions. Provide additional authentic occupancy, energy and orbital information in separate explicitly named fields when available.

## Native research scans and integrated reports

BASE's current reviewed TORQ adapter also supports actual `research_scan` and `wiberg_lowdin` operations through the installed `PySCFBackend`. `research_scan` moves fragment B rigidly along the original mass-center separation direction; intramolecular geometry and orientation remain fixed. The student selects two complete atom-index fragments and actual distances in the GUI. Each point has its own native request, result and hash manifest. Immutable progress receipts retain the computed points and explicitly mark the remaining points `not_run`.

`wiberg_lowdin` reads the verified real restricted SCF checkpoint, forms the spin-summed density and AO overlap matrix, and computes:

\[
P_{\mathrm{L\ddot{o}wdin}} = S^{1/2}P_{\mathrm{AO}}S^{1/2},\qquad
W_{AB}=\sum_{\mu\in A,\nu\in B}(P_{\mathrm{L\ddot{o}wdin},\mu\nu})^2.
\]

It checks actual geometry, energy, electron count, positive overlap eigenvalues and total charge. The restricted reference is explicitly identified; an MP2 checkpoint's HF density is not presented as a correlated MP2 bond analysis.

BASE's `student_reports` produces self-contained HTML, SVG, CSV and JSON views with exact retained source receipts. The GUI discovers these results automatically from verified Actions downloads and resolves safe artifact-relative paths. Original runner absolute paths remain unchanged in provenance; consumers do not require those paths to exist in Codespaces.

Energy comparisons require common composition, electronic state, method, basis and thermodynamic definition. Electronic-energy Boltzmann weights are explicitly an energy-only model. Genuine Gibbs fractions require a common temperature and standard state. Populations require actual minimum evidence; starting geometries, SCF convergence or the lowest sampled scan point are insufficient. Do not advertise complete isomer populations from an incomplete conformer search.

A compatible future TORQ provider can implement these versioned native analysis operations without another BASE GUI or a student terminal-install step. Publish its wheel/source revision, update the reviewed distribution manifest after acceptance and let BASE's normal update, install, probe and execution route expose only the capabilities actually available.
