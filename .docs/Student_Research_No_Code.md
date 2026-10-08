# Student guide: molecular research in CoChem

You use **one course repository containing CoChem-BASE**. BASE prepares the
interface, installs its analysis components, submits calculations and brings
results back. You do not open other CoChem repositories, install Python
packages, enter access tokens or type terminal commands.

Your instructor supplies the assignment link and approved scientific protocol.
**You supply your own monomer or complex starting structures**, made in
Avogadro 2 or another approved molecular editor. An example used during setup
is only an installation check.

## Start your workspace

1. Sign into GitHub and Classroom50 with your own account. Accept the course
   organization invitation if one is pending.
2. Open your instructor's Classroom50 assignment link and choose **Accept
   assignment**. When setup finishes, choose **Open repository**. Bookmark this
   repository; it holds your research workspace.
3. In that repository choose **Code → Codespaces → Create codespace on main**.
   If **New with options** appears instead, use your instructor's branch and
   the two-core machine. Review the requested permissions and confirm your
   personal account is the payer.
4. Wait for the automatic setup to finish. BASE installs the required analysis
   components itself. The first start can take several minutes. Do not start
   a second Codespace because setup is still running.
5. In VS Code's **Ports** panel, open **8866 — CoChem Voilà dashboard → Open in
   Browser**. Keep its visibility **Private**. This opens the CoChem interface.
6. Look at **CoChem setup and updates**. Required setup must finish before a
   dependent calculation is enabled. If setup reports a problem, use **Retry
   setup** once after the instructor fixes the reported access problem. Give
   the instructor the error message; do not try terminal installation commands.

The Codespace supplies the interface. A GitHub Actions calculation runs on a
separate worker and can continue after you close or stop the Codespace.

## Upload your structures

1. In Avogadro 2, save each structure as **XYZ**. Use a complete file with an
   atom-count line, comment line and one element plus three coordinates per
   atom. Coordinates are in ångströms. Include all atoms and explicit hydrogens.
2. Upload one or several files with **Upload .xyz** in **No Code Matrix**.
   You can supply a monomer, a complete complex, or several starting
   arrangements. You do not need an instructor-provided structure.
3. Select the desired file under **Starting geometry**. Select its **Input
   type** and inspect the displayed geometry and upload status. BASE preserves
   the original file and its identity separately from any working geometry.
4. In **Base Config**, set the **Charge** and **Multiplicity** required by your molecule. XYZ does
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

## Run your calculation

1. Select **GitHub Codespaces** as the interface environment and **GitHub
   Actions** as the calculation environment. BASE should identify your current
   assignment repository and approved branch. Check these refer to your
   assignment, rather than the upstream application repository.
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

### Use reference-dependent protocols when assigned

In **No Code Matrix → Fragments / Frozen**, **Upload R2 references** accepts a ZIP containing
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

In **Base Config → T9 recovery**, enable recovery only with the assigned
scientific active space. Set **Recovery method**, **Recovery basis**, **Active
electrons**, **Active MO indices** and **Active-space rationale**. Molecular
orbital indices start at zero. BASE supplies the authorized worker interpreter;
you never enter an executable path. Successful CASSCF/NEVPT2 single-point
recovery rejects the contaminated result; it does not complete an interrupted
optimization or frequency calculation.

These inputs remain scientific data. Use the same **Run on GitHub Actions**
and result-retrieval buttons; you do not upload engine binaries or run code.

## Read results and create your report

The **TOPOS** tab provides installed research operations such as optimizing a
starting geometry or searching isomer/association candidates. Select an enabled
**Research operation**, the instructor's **Research method**, and any required
monomer states, then use **Run TOPOS research**. It follows the selected
calculation environment through BASE.

The **TORQ** tab offers **Run TORQ potential energy scan** when its provider is
ready. Its current rigid scan moves one of two fragments along their initial
mass-center separation. Supply the fragment groups, method/basis, separation
range and number of evaluated points. A rigid scan is distinct from optimized
scan points or a multidimensional potential surface.

**Run Löwdin Wiberg analysis** uses an actual supported electronic calculation
to produce bond-index tables and a bond diagram in the Löwdin orthogonalized
atomic-orbital basis. It is distinct from natural atomic orbital Wiberg indices
and NBO donor–acceptor analysis. Those other buttons stay unavailable unless
the installed provider supplies the corresponding authentic analysis.

Open **Research results** for available tables, figures and report downloads.

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
assignment checkout. To submit a downloaded report through the repository,
drag its course-approved files into your assignment's **Explorer** folder in
VS Code, or use GitHub **Add file → Upload files**. Use VS Code **Source Control**
to commit the course files you intend to submit: select the files, enter a
descriptive message, choose **Commit**, then
**Sync Changes**. These are ordinary buttons, not terminal commands. Confirm
that the intended report appears in your repository on GitHub. Follow your
instructor's policy for large result files rather than committing an entire
runtime or binary archive.

## Get bug fixes without losing your work

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
access and you have synchronized the course files you wish to keep. An ordinary
module bug fix that uses existing permissions does not require granting new
repository permissions yourself.

## Finish a session

After saving your work, use the Codespaces menu to **Stop current codespace**.
Closing the browser alone does not stop it. Delete a Codespace only after your
important files are synchronized or downloaded; its persistent local results
can disappear when it is deleted.

For a problem report, supply the visible error, project/calculation identifier,
run link and the relevant starting XYZ through the course's approved channel.
Never include access tokens or licensed engine archives.
