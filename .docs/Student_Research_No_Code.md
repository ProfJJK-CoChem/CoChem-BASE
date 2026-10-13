# Scientific inputs and research in CoChem

## Start your workspace

**New to CoChem? [Start with the quick guide](GET_STARTED.md).** It explains
opening the dashboard, ORCA/CFOUR access and the first calculation.

This page is a reference: open only the section you need. You supply your own
starting structures and scientific files. CoChem-BASE prepares its analysis
components and brings their results into the same interface.

- [Upload structures](#upload-your-structures)
- [Other scientific files, conformers and measured outputs](#use-the-scientific-input-library)
- [Run and retrieve a calculation](#run-your-calculation)
- [Read results and create a report](#read-results-and-create-your-report)
- [Get updates](#get-bug-fixes-without-losing-your-work)

## Upload your structures

<details>
<summary><strong>Show instructions</strong></summary>

1. In Avogadro 2, save each structure as **XYZ**. Use a complete file with an
   atom-count line, comment line and one element plus three coordinates per
   atom. Coordinates are in ångströms. Include all atoms and explicit hydrogens.
2. Open **Your files**, choose **Upload scientific inputs** and select one
   or several files. You can supply a monomer, a complete complex or several
   starting arrangements. You do not need an instructor-provided structure.
3. Select the file and its **Structure / frame**, then choose **Use selected
   starting geometry**. Check the displayed molecule and **Input type**. BASE
   keeps the original separately from any working geometry. If you uploaded
   the wrong file, choose **Remove from list**; use **Undo remove** or
   **Show removed inputs → Restore selected input** to bring it back.
4. In **Method and settings**, set the **Charge** and **Multiplicity** required by your molecule. XYZ does
   not reliably store these values. For a complex, supply fragment definitions
   and the charges/multiplicities of its components whenever the selected
   research operation requests them. Do not guess a default for an ion,
   radical or fragment-dependent calculation.
5. Give the project a meaningful name and choose **Save geometry details**.
   Keep separate starting arrangements identifiable so their results can be
   compared later.

If you are starting from separate monomers, select each uploaded file, choose
**Monomer A** or **Monomer B**, set its electronic state and choose **Save
geometry details**. Select the intended components under **Your monomers**,
choose a **Seed separation (Å)** and choose **Prepare complex starting seed**.
BASE preserves each monomer's internal geometry and documents the translated
starting arrangement. It does not claim that this seed is a stable complex or
has a binding energy. Select an available association/search calculation next.

A monomer can be optimized on its own. Combining two monomers, generating
complex arrangements, freezing monomer coordinates, scanning a coordinate and
computing interaction energies are distinct operations. Select a capability
that is actually available in the interface. A missing provider or required
input leaves that operation unavailable with an explanation.

</details>

## Use the scientific input library

<details>
<summary><strong>Show instructions</strong></summary>

XYZ is the usual Avogadro 2 route for this course. BASE also accepts complete
scientific source files through **Your files**. You choose files and frames;
BASE retains the untouched original alongside its validated interpretation.

| Your source file | What BASE retains and exposes |
| --- | --- |
| XYZ or a multi-frame XYZ | All ordered frames and isotope labels. A coordinate-only ensemble remains starting structures. |
| MOL V2000/V3000 or multi-record SDF | Every molecular record, explicit hydrogens, isotope labels, formal charges and any declared spin state. |
| MOL2 | Ordered atoms, Cartesian coordinates, Tripos types, bonds and recorded partial charges. Partial charges do not supply a molecular spin or formal charge. |
| PDB | All unambiguous MODEL records and their atom order. Resolve alternate locations or partial occupancy before import. |
| MolSSI QCSchema v1/v2 JSON | Ordered nuclei, source Bohr coordinates converted to ångströms, declared charge/spin, isotope and fragment information. |
| CIF or an explicitly unit-labelled periodic structure | Ordered species, lattice, periodic boundaries, source units and source hash. Resolve disorder or partial occupancy first. |
| ORCA .hess or a geometry-bound NPZ/HDF5 Hessian | Ordered geometry, complete Cartesian Hessian, source evidence and units. An imported matrix alone does not establish a physical minimum. |
| Native ORCA/CFOUR spectroscopy output | Actually printed constants and corrections, with missing observables kept missing. |
| Canonical trajectory HDF5 or numerical NPZ/HDF5 | Bounded dataset previews, measured records and declared units/provenance. External file references and pickled arrays are rejected. |
| PAW UPF pseudopotential | Untouched potential, element, header and hash; the selected calculation must separately pass its native scientific checks. |

1. Choose **Your files** on the left.
2. Leave **Scientific input type → Detect from file** for ordinary structures,
   or select the appropriate type for a Hessian, spectroscopy output or data
   archive. Choose **Upload scientific inputs** and select your files.
3. Read the validation message and **Verified retained scientific inputs**
   table. A rejected file stays out of calculation choices; valid earlier
   uploads remain available. Keep the error for your instructor.
4. Choose the file under **Retained input** and the desired **Structure / frame**.
   SDF and multi-frame files keep every record; selecting one does not delete
   the others.
5. Choose **Use selected starting geometry**. BASE opens the molecule panel
   with that ordered frame. Confirm charge and multiplicity in **Method and settings**
   when the source did not declare them. Supply the scientific state explicitly
   before running a calculation.

Counterpoise/ghost centers are preserved during inspection with zero mass and
nuclear charge. A normal physical-atom calculation cannot select them as real
nuclei; it requires an available counterpoise-capable adapter.

For a file already in VS Code, drag it into **Student input inbox** in the
Explorer sidebar, alongside **CoChem-BASE**, then choose
**Import files from VS Code inbox**. **Watch VS Code inbox** imports completed
new files; **Stop watching inbox** stops that watcher. The original files,
record selections and source hashes remain available when the dashboard restarts.

</details>

## Import and compare conformer pools

<details>
<summary><strong>Show instructions</strong></summary>

Choose **Scientific input type → CREST / ORCA GOAT conformer pool**, select the
actual **Pool producer** and its **Recorded energy unit**, and upload the native
ensemble. Every energy-bearing frame needs its recorded finite energy. Use
**Explicit energy labels and units** for an independently supplied pool with
explicit energy/unit declarations in every comment.

Choose the intended **Conformer pools**, enter any verified common charge,
spin and comparison protocol requested by the form, and choose **Merge and
sieve native conformer pools**. Compare only energies produced under compatible
methods, bases and conditions. The result preserves every original observation
and explains which representative was retained, which duplicate was grouped,
which comparable member was outside the energy window and which member remains
unranked. Missing energies, states or protocols remain unranked and retained.
A geometric sieve does not certify minima, thermodynamic populations or chemical
accuracy; those require their own accepted calculation evidence.

</details>

## Inspect measured outputs and isotope changes

<details>
<summary><strong>Show instructions</strong></summary>

Open **Spectra and properties**, select the rotational-observables tab,
upload/select **Native output** and choose
**Parse Observables**. The panel distinguishes constants from the supplied
geometry, validated equilibrium results when evidence exists, and measured
vibrational corrections. It keeps an absent ground-state constant or correction
marked as missing.

For harmonic isotope analysis, open **Isotopic Re-analysis**, choose **Upload
hessian** or an existing **Retained Hessian**, then **Load geometry and Hessian**.
Choose the isotope substitutions and **Re-analyze Isotopologue**. This reuses
the supplied Cartesian force field without another electronic calculation.
Anharmonic corrections and stationary-minimum qualification need additional
native evidence; an uploaded model Hessian is not presented as an accepted
physical force field.

For a numerical archive, choose **Data tables (HDF5/NPZ)**, upload/select **Physical
data**, and choose **Inspect HDF5 / NPZ data**. Check dataset names, dimensions,
units and source alongside the bounded values. Missing units/provenance are
shown explicitly.

</details>

## Prepare a periodic request

<details>
<summary><strong>Show instructions</strong></summary>

Use **Periodic structures** only for an assigned periodic-materials project.
Upload/select the ordered periodic structure and inspect its cell and species.
Upload the authentic **PAW files**, assign one compatible PBE PAW potential per
species, and enter the instructor's wavefunction/density cutoffs and k-grid in
the labelled controls. Review the complete request before submitting it through
BASE. The interface and worker validate original source hashes and potential
headers; an accepted input alone does not certify the required band-gap or
lattice accuracy.

</details>

## Build an initial molecule in BASE

<details>
<summary><strong>Show instructions</strong></summary>

The **Molecule Builder** also accepts an explicit SMILES string or a supported
chemical name under **Name or SMILES**. Choose **Build starting geometry** and
inspect the generated structure, resolved identity and builder provenance.
This produces an initial guess. It does not provide a measured energy or claim
a minimum. Your own Avogadro 2 structures remain the usual course inputs.

</details>

## Run your calculation

<details>
<summary><strong>Show instructions</strong></summary>

1. In **Start here**, select **GitHub Actions** under **Run calculations on**.
   BASE should identify your current project. For a personal student project,
   confirm it shows your
   `username/project`, rather than upstream BASE or an organization collection
   repository.
2. Choose the engine, operation and scientific settings specified by your
   instructor. Do not use a small installation-check method as a substitute
   for the assigned van der Waals research protocol.
3. Review the calculation summary, resource limits and warnings. Choose **Run
   on GitHub Actions**. BASE submits the request; you do not download JSON,
   edit a workflow or commit a job file to launch it.
4. Keep the displayed calculation identifier and run link. Use **Refresh
   calculation status** to check progress. Start only one calculation per
   request. **Cancel calculation** cancels that specific run when supported.
5. When the run succeeds, choose **Retrieve and inspect results**. BASE checks
   that the artifact belongs to your request and verifies its recorded files
   before opening it. A failed run's diagnostics are not a successful result.
6. Save **Download calculation bundle** in your course-approved storage. The
   bundle keeps the input, native outputs, settings, versions and result
   evidence together. GitHub artifacts expire; retrieve them promptly.

A selected licensed engine must be available on the calculation worker. ORCA
and CFOUR are optional, strongly recommended components of CoChem. Their
absence does not prevent geometry upload or independent supported analysis;
methods that require the unavailable engine cannot be run.

</details>

## Use reference-dependent protocols when assigned

<details>
<summary><strong>Show instructions</strong></summary>

In **Calculations → Fragments / Frozen**, **Upload R2 references** accepts a ZIP containing
the reference manifest, original monomer geometries, original canonical
CCSD(T) outputs for both basis sizes, and any referenced geometry-optimization
evidence. Use the authentic package produced for your monomers by the approved
reference workflow. A starting XYZ alone does not establish a CCSD(T)/CBS
reference. BASE checks the package's source identities; the calculation also
checks the native outputs and their scientific consistency. Select **Recipe
R2** only for the assigned production protocol.

**Upload READ Hessian** accepts an authentic ORCA `.hess` from the exact ordered
geometry you select. Choose **Initial Hessian → Read uploaded Cartesian
Hessian** only after uploading it. A Hessian from another structure or
coordinate frame is rejected. BASE retains the original and records any
required frame transformation; this does not calculate a new electronic
Hessian.

In **Method and settings → T9 recovery**, enable recovery only with the assigned
scientific active space. Set **Recovery method**, **Recovery basis**, **Active
electrons**, **Active MO indices** and **Active-space rationale**. Molecular
orbital indices start at zero. BASE supplies the authorized worker interpreter;
you never enter an executable path. Successful CASSCF/NEVPT2 single-point
recovery rejects the contaminated result; it does not complete an interrupted
optimization or frequency calculation.

These inputs remain scientific data. Use the same **Run on GitHub Actions**
and result-retrieval buttons; you do not upload engine binaries or run code.

</details>

## Read results and create your report

<details>
<summary><strong>Show instructions</strong></summary>

In **Calculations**, open **TOPOS: structures and energies** to optimize a
starting geometry or search for isomer/association candidates. Select the enabled
**Calculation**, the instructor's **Method**, and any required monomer states,
then choose **Start TOPOS calculation**. It follows the selected
calculation environment through BASE.

In **Calculations**, open **TORQ: energy scans and bonding → Distance scan**
and choose **Start distance scan** when it is available. Its current rigid scan
moves one of two fragments along their initial mass-center separation. Supply the fragment groups, method/basis, separation
range and number of evaluated points. A rigid scan is distinct from optimized
scan points or a multidimensional potential surface.

**Bond analysis → Calculate Löwdin Wiberg indices** uses a supported
electronic calculation
to produce bond-index tables and a bond diagram in the Löwdin orthogonalized
atomic-orbital basis. It is distinct from natural atomic orbital Wiberg indices
and NBO donor–acceptor analysis. The separate **Calculate NAO Wiberg indices**
and **Calculate NBO analysis**
buttons stay unavailable unless the installed program supplies the
corresponding analysis. ORCA access alone does not make NBO available.

Open **Results** for available tables, figures and report downloads.
**Clear comparison selection** clears highlighted choices while retaining
every saved calculation and report.

Use the available analysis panels to compare verified calculations. BASE can
present tables and figures supplied by an installed provider, and can make
reports from supported authenticated result data. Missing data remain missing.

Before interpreting a comparison, check that the structures have the same
composition and that the underlying methods, bases, charge, spin state,
convergence and correction conventions are appropriate for that comparison.

- **Energy differences** require actual energies and a stated reference.
- **Isomer populations** require a temperature, degeneracies and a chosen
  energy or free-energy convention, plus verified minimum structures with
  vibrational evidence. Electronic-energy weights omit entropy and zero-point
  corrections; they are not thermodynamic equilibrium populations. A starting
  geometry or a successful single-point energy does not establish a minimum.
- **Potential-energy diagrams and scans** require actual evaluated points.
  Connecting sparse points visually does not prove there are no intervening
  minima or barriers.
- **NBO and Wiberg results** require supported native analysis output. An
  unavailable licensed analysis component cannot be replaced with invented
  occupancies, bond indices or diagrams.

Save the original starting files, final structures, calculation bundle and
report. BASE's managed runtime/results directories are separate from your
personal project checkout. To save a downloaded report through the repository,
drag its course-approved files into your project's **Explorer** folder in
VS Code, or use GitHub **Add file → Upload files**. Use VS Code **Source Control**
to commit the course files you intend to submit: select the files, enter a
descriptive message, choose **Commit**, then
**Sync Changes**. These are ordinary buttons, not terminal commands. Confirm
that the intended report appears in your private project on GitHub. Submit the
project/report URL through your instructor's Classroom50 instructions and confirm
the instructor can access the intended report; enrollment alone does not grant
collection access to a private personal repository. Follow the course policy for
large files rather than committing an entire runtime or binary archive.

</details>

## Get bug fixes without losing your work

<details>
<summary><strong>Show instructions</strong></summary>

1. Finish, cancel or wait for an active calculation before applying a setup
   update. Save your course report and retrieve any completed results first.
2. Open **CoChem setup and updates → Check for updates**. The interface shows
   which compatible application/component revisions are available.
3. Choose **Apply compatible updates** for the instructor-approved update.
   BASE installs components in managed storage and records exact versions;
   your original structures and results must remain intact.
4. If BASE requests a refresh, choose **Restart interface** and reopen the
   dashboard. Your saved starting geometries and their input types, states and
   fragment groups reopen without another upload. Recheck the setup status
   before starting another calculation.
5. If an update fails, retain the error and use the offered rollback/retry
   controls as directed. Do not install from another repository manually.

New permissions require a **new Codespace**, after your instructor corrects
access and you have synchronized the course files you wish to keep. Approve the
project permissions GitHub shows when creating it. Rebuilding an existing
Codespace does not refresh those permissions. An ordinary module bug fix that
uses existing permissions does not require this step.

If CoChem says a project workflow is missing or out of date, give that message
and your project link to the instructor. **Check for updates** updates the
managed CoChem installation; it does not replace your project's GitHub workflow
files. The instructor must update those project files before you retry.

</details>

## Finish a session

<details>
<summary><strong>Show instructions</strong></summary>

After saving your work, use the Codespaces menu to **Stop current codespace**.
Closing the browser alone does not stop it. Delete a Codespace only after your
important files are synchronized or downloaded; its persistent local results
can disappear when it is deleted.

For a problem report, supply the visible error, project/calculation identifier,
run link and the relevant starting XYZ through the course's approved channel.
Never include access tokens or licensed engine archives.

</details>
