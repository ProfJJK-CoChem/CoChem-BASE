"""Authored beginner guidance; reading it never chooses or runs chemistry.

Plain strings are escaped by the presentation layer. This module has no widget,
provider, network, credential or calculation dependency. Controls name existing
GUI attributes; topic coverage and per-control guidance are distinct inventories.
"""
from __future__ import annotations


def _topic(title, aliases, what, why, when, where, how, limitations, controls=()):
    return dict(title=title, aliases=aliases, what=what, why=why, when=when,
                where=where, how=how, limitations=limitations, controls=controls)


HELP_CONTENT = {
    "first_calculation": _topic(
        "Run your first assigned calculation", ("getting started", "beginner", "what do I do", "first run", "homework"),
        "A calculation applies a scientific model to the particular structure and settings you supply. Start with the task and settings your instructor assigned.",
        "A program can finish successfully while answering a different question. Checking the molecule, electronic state and requested task prevents that mistake.",
        "Use this route for an assigned molecular calculation after your project has been connected to the course.",
        "Follow the header buttons 1 · Setup, 2 · Add your molecule, 3 · Run assigned calculation, then 4 · Read and save results. The navigation also calls these Start here, Your files, Calculations and Results.",
        ("In Setup, confirm the calculation computer and required program are available.",
         "Add your file, select the intended structure or frame, and use it as the starting geometry. Check the atoms, charge and spin.",
         "In Calculations, check the assigned operation, method, basis and surroundings. Submit once and follow its recorded status.",
         "Retrieve the matching completed result, read its warnings, and download its bundle before preparing your report."),
        ("Help does not assign a method, charge, spin or scientific protocol for your molecule.",
         "A setup/access check is not a chemistry result; an uploaded or drawn structure is not a verified minimum.")),
    "workspace": _topic(
        "Where the interface and calculations run", ("Codespaces", "GitHub Actions", "local computer", "where running", "setup", "two computers"),
        "The interface is the page with buttons. The calculation computer runs the chemistry program; these can be different computers.",
        "A program or file available in your Codespace is not automatically available to an Actions job on another computer.",
        "Check this before setup or submission, and whenever the selected calculation environment changes.",
        "1 · Setup / Start here → Run calculations on. Where this interface runs explains the separate interface setting.",
        ("Use the calculation route specified for the course; the remote course route uses GitHub Actions.",
         "Confirm the displayed GitHub project is your private research project. Check access in that environment.",
         "Local means the computer running BASE, which can itself be a Codespace. HPC requires an institution's configured cluster."),
        ("Access, billing, program availability and actual execution are separate checks.",
         "Do not create another project or enter credentials to work around an unexplained access error.")),
    "scientific_inputs": _topic(
        "Upload a structure or scientific dataset", ("upload", "what file", "XYZ", "MOL", "SDF", "MOL2", "PDB", "QCSchema", "CIF", "file contents"),
        "A structure file records atoms and their positions. Other scientific files can contain several structures, calculated properties, a Hessian or a periodic cell.",
        "The filename alone cannot tell BASE which record, units, isotope labels or electronic state you intend to use.",
        "Upload a starting structure before a molecular calculation. Use specialized input choices only for the data you actually have.",
        "2 · Add your molecule / Your files → File contents → Upload scientific inputs → Your uploaded file → Structure / frame.",
        ("For ordinary supported molecular files, start with Detect from file and upload the original file.",
         "Select the intended uploaded file and structure/frame, then choose Use selected starting geometry. Open Calculations → Starting structure to inspect its 3D picture and verify atoms, charge and spin before submitting.",
         "For a conformer pool or specialized dataset, choose the matching file contents and supply its actual recorded metadata."),
        ("Supported readers include molecular XYZ/MOL/SDF/MOL2/PDB/QCSchema and separate native-data, Hessian and periodic routes; every file must pass its own checks.",
         "An imported energy or structure is a supplied observation, not a new calculation or proof of convergence.")),
    "molecule_identity": _topic(
        "Check that this is your intended molecule", ("wrong molecule", "hydrogens", "atoms", "formula", "selected structure", "molecule identity"),
        "A molecule's identity includes which atoms are present and how they are connected. Charge, spin and isotope labels also matter to a calculation.",
        "Two files with the same name or molecular formula can describe different arrangements. A missing hydrogen or wrong charge changes the question.",
        "Check after importing, building, editing or selecting a calculated structure.",
        "2 · Add your molecule / Your files shows the retained file and frame. Calculations → Starting structure displays the selected geometry; charge and spin are also shown in the current-molecule summary.",
        ("Compare atom counts, elements, hydrogens and connectivity with your intended drawing.",
         "Check the chosen file/frame, electronic state and any isotope labels. Rotate the display to inspect overlapping atoms.",
         "If the structure is uncertain, keep the original and ask your instructor before submitting."),
        ("Displayed bonds are geometric drawing aids, not measured bond orders.",
         "A 3D display does not automatically identify a stereoisomer or assign an R/S configuration.")),
    "isomers": _topic(
        "Isomers, conformers and resonance drawings", ("same formula", "isomer", "diastereomer", "E Z", "cis trans", "conformer", "resonance", "different structures", "bond rotation", "two molecules"),
        "Isomers have the same molecular formula but different arrangements of atoms. Constitutional isomers have different connections; stereoisomers differ in spatial arrangement. Enantiomers are mirror-image stereoisomers; diastereomers are stereoisomers that are not mirror images, such as E/Z alkene pairs.",
        "These differences can affect energy, reactivity and spectra. You need to know which structures you are comparing before interpreting an energy difference.",
        "Use this when importing several structures, doing a conformer search or comparing calculated isomers.",
        "Upload separate candidate structures through Your files. Calculations → Advanced: other calculation tools → Other structures and energies contains conformer-search tools; Results compares compatible calculated structures.",
        ("First compare which atoms are connected. If connections differ, you have different constitutional structures.",
         "For the same connections, consider spatial arrangement. Conformers differ through motions such as bond rotation or ring puckering; their ease of interconversion depends on the barrier and conditions.",
         "Resonance drawings show alternative electron bookkeeping for the same nuclear arrangement. Do not treat them as separate molecules or conformers to rank.",
         "Only compare energies from scientifically compatible calculations, and keep unknown energies unknown."),
        ("A few candidate geometries do not establish every possible isomer or the global minimum.",
         "A duplicate-removal test does not prove that retained candidates are stable minima or equilibrium populations.")),
    "chirality": _topic(
        "Chirality and R/S labels", ("chiral", "chiralty", "chirality", "enantiomer", "mirror image", "R S", "optical rotation", "stereochemistry"),
        "A chiral structure cannot be superimposed on its mirror image by rotating and moving it. Such a mirror-image pair is called a pair of enantiomers.",
        "A drawing's appearance depends on your viewing direction. Confusing a rotated view with a different configuration can lead to a wrong molecular assignment.",
        "Check stereochemistry when your assignment concerns chiral molecules or when importing or building stereochemical structures.",
        "Inspect the selected structure in Calculations → Starting structure. Use your chemical drawing and instructor's stereochemical assignment alongside the 3D view.",
        ("Verify the connections and substituents, then check the specified stereochemistry in the source structure.",
         "R/S labels follow the Cahn–Ingold–Prelog priority rules for the relevant stereogenic feature; they are not labels for the direction you rotate the image.",
         "The signs (+)/(−) describe measured optical rotation under stated conditions. R does not generally mean (+), and S does not generally mean (−)."),
        ("The viewer is not an automatic stereochemical assignment or optical-rotation measurement tool.",
         "Enantiomers have the same ordinary rotational constants and many other properties in an achiral environment; those values alone cannot distinguish them.")),
    "charge_spin": _topic(
        "Total charge and spin multiplicity", ("charge", "spin", "singlet", "doublet", "triplet", "radical", "neutral", "electrons"),
        "Total charge describes the electron count relative to the neutral atoms. Spin multiplicity describes the total electron spin; it is a separate choice.",
        "The same atoms with a different charge or spin represent a different electronic state. Neutral does not mean singlet.",
        "Verify both for each selected molecule and each monomer when a calculation needs separate fragment states.",
        "Calculations → Starting structure or Method and settings → Total charge / Spin multiplicity. Check monomer charges and spins provides the separate fragment fields when needed.",
        ("A charge of +1 means one electron removed from the neutral atoms; −1 means one added. Use the charge of the whole selected system.",
         "Multiplicity is 2S + 1: singlet 1, doublet 2, triplet 3. Ground-state neutral water is a singlet, whereas ground-state neutral oxygen is a triplet; these examples do not assign your molecule's state.",
         "Use the state specified for your molecule and task. If uncertain, ask your instructor; electron-count compatibility alone does not identify the ground state.",
         "After unrestricted calculations, review the reported spin diagnostics as well as ordinary convergence."),
        ("A prefilled number is an interface value, not a chemical state determination.",
         "Do not change the spin merely to remove a warning or make a job run.")),
    "method_basis": _topic(
        "Method, basis set and dispersion", ("method", "basis set", "DFT", "Hartree Fock", "HF", "functional", "dispersion", "which method"),
        "The method is an approximation for electronic behavior. The basis set is the collection of functions used to represent the electrons.",
        "Results depend on both. Comparing values from different models can mix a molecular difference with a change in the calculation itself.",
        "Choose these before submitting a calculation, following the scientific protocol supplied for your study.",
        "3 · Run assigned calculation / Calculations → Method and settings → Engine, Method and Basis Set. Other method families are under the advanced disclosure.",
        ("Copy the assigned method and matching basis, then verify them in the saved run configuration.",
         "HF includes exchange but omits electron correlation. DFT uses an approximate exchange-correlation functional; different functionals give different predictions.",
         "Weak intermolecular attractions need suitable dispersion treatment. Some methods need a correction; others already contain it. Preserve BASE's safeguards against double counting.",
         "Check the method actually executed in the returned output before comparing structures."),
        ("A larger basis, higher cost or higher tier is not an accuracy guarantee.",
         "HF/STO-3G can exercise setup; it does not validate weak binding. Do not add D3/D4 to ωB97M-V or add corrections again to a composite method.")),
    "theory_tiers": _topic(
        "Theory families T0–T9", ("theory tier", "T0", "T1", "T2", "T3", "T9", "higher number", "method family"),
        "The tiers group types of scientific models and their usual cost. They do not score the quality of your particular answer.",
        "Choosing the highest number can waste resources or select a model unsuitable for the electronic state or property.",
        "Open these advanced choices only when your assigned protocol requires a different method family.",
        "Calculations → Method and settings → advanced method-family choices → Theory family.",
        ("T0 groups force-field/ML screening; T1 semiempirical methods; T2 minimal-basis HF; T3–T5 DFT families.",
         "T6 covers perturbation methods such as MP2; T7 local coupled cluster; T8 canonical coupled cluster; T9 multireference approaches such as CASSCF/NEVPT2.",
         "Use the assigned family and full method, then check the available operation and resource limits."),
        ("T9 is for states requiring several electronic configurations, not a universal upgrade.",
         "No tier promises a runtime or experimental accuracy for an untested molecule.")),
    "solvent": _topic(
        "Gas phase and solvent models", ("surroundings", "solvation", "solvent", "water", "CPCM", "SMD", "gas phase"),
        "Gas phase models an isolated system without a surrounding solvent model. A continuum solvent represents averaged effects of a surrounding liquid.",
        "Solvent can change relative energies and structures. All structures in a comparison need the intended, consistent surroundings.",
        "Set this when the assignment specifies gas phase or a solvent treatment.",
        "Calculations → Method and settings → Surroundings.",
        ("Use the surroundings named in the protocol; do not infer them from the molecule's name.",
         "A water continuum is not the same model as adding individual water molecules to your geometry.",
         "Confirm the solvent model actually recorded in the input and result."),
        ("A continuum does not explicitly sample individual solvent molecules.",
         "A solvation energy alone is not a complete solution free energy; motion, temperature and standard state also matter.")),
    "calculation_types": _topic(
        "What task should the program perform?", ("single point", "optimization", "optimisation", "frequency", "calculation operation", "energy only"),
        "A single point evaluates energy at the supplied geometry. Optimization changes allowed nuclear coordinates. Frequencies examine local energy curvature.",
        "These tasks answer different questions. An energy at one geometry does not improve that geometry or establish a minimum.",
        "Choose the operation named in your assignment before pressing the run button.",
        "3 · Run assigned calculation / Calculations → Run calculation. The operation controls depend on the selected calculation computer and engine.",
        ("For energy at a specified geometry, use the assigned single-point operation.",
         "For a nearby stationary structure, use the assigned optimization operation and inspect convergence.",
         "When the protocol calls for minimum classification, inspect appropriate frequencies at the optimized geometry as well.",
         "Read the current run-button label: it changes with the selected engine and task."),
        ("Optimization does not prove a global minimum, or even a local minimum without suitable classification.",
         "Only operations with a verified available provider can run; selecting a task cannot supply a missing scientific capability.")),
    "convergence_frequencies": _topic(
        "Did optimization find a meaningful structure?", ("convergence", "minimum", "imaginary frequency", "negative frequency", "forces", "SCF", "optimization finished"),
        "Convergence means specified numerical stopping criteria were met. It is different from demonstrating chemical accuracy or finding a minimum.",
        "A normal exit or nearly unchanged energy can coexist with unconverged forces, an incorrect electronic state or a saddle point.",
        "Read these checks before using a calculated geometry, energy or spectrum in a report.",
        "Retrieve the calculation in Calculations, then inspect its result and warnings under 4 · Read and save results / Results. Frequency and Hessian tools are in Spectra and properties.",
        ("Check electronic SCF convergence separately from geometry energy, gradient and displacement convergence.",
         "For a claimed unconstrained minimum, examine vibrational curvature after overall translation and rotation are removed.",
         "An imaginary mode indicates negative curvature; inspect its motion and numerical conditions. A small imaginary value can also reflect numerical problems or a shallow surface.",
         "Keep constrained results labelled: they minimize only the coordinates allowed to move."),
        ("Optimization completion is not proof of the lowest-energy isomer or experimental accuracy.",
         "Do not delete modes, relax thresholds or ignore a warning simply to label a structure a minimum.")),
    "fragments_constraints": _topic(
        "Monomers, fragments and frozen coordinates", ("fragment", "monomer", "complex", "two molecules", "R1", "R2", "freeze", "constraints"),
        "A monomer is one molecular component of a complex. A fragment definition tells the calculation which atoms belong to each component.",
        "Frozen-monomer and interaction-energy calculations depend on the correct partition, reference geometry and separate electronic states.",
        "Use these advanced settings only for an assigned fragment or frozen-monomer protocol.",
        "Calculations → Advanced: other calculation tools → Monomer constraints; starting-fragment details are also in Starting structure. Research tools may offer Check monomer charges and spins.",
        ("Check every atom's fragment membership and each fragment's assigned charge and spin.",
         "Frozen-monomer recipes fix internal bond lengths, angles and dihedrals while allowing specified relative motions.",
         "R1 is an initial constrained route. R2 requires appropriate validated monomer references and stricter production settings; use the supplied reference package.",
         "Inspect recorded constraints and residual forces, including those on fixed coordinates."),
        ("Automatically detected bonds/fragments are geometric suggestions, not chemical proof.",
         "A constrained optimum is not necessarily a fully relaxed minimum. Counterpoise corrects basis sharing, not every contribution to binding free energy.")),
    "hessian": _topic(
        "What is a Hessian?", ("Hessian", "READ", "second derivative", "starting Hessian", "curvature", "vibrational modes"),
        "A Hessian is a matrix of second derivatives of energy with respect to atomic positions. It describes the local curvature of the energy surface.",
        "Curvature helps an optimizer choose steps and supports vibrational analysis. The wrong geometry, atom order or units can produce plausible but incorrect results.",
        "Supply one only for a task that needs it, such as a specified READ restart or isotope reanalysis. Ordinary starting-geometry upload does not require one.",
        "More scientific tools → Spectra and properties → Hessian/isotope tools. Advanced starting-Hessian controls are under Calculations → Advanced: other calculation tools → Monomer constraints.",
        ("Select or upload a genuine compatible Hessian with its matching original geometry and calculation record.",
         "Check atom order, coordinate frame, units and method before loading it.",
         "Use model starting Hessians such as XTB2/Lindh only as your optimization protocol specifies; do not present them as calculated spectra."),
        ("Matching dimensions alone do not establish compatibility.",
         "Harmonic curvature does not supply all anharmonic or large-amplitude-motion effects.")),
    "active_space": _topic(
        "Advanced: multireference active space", ("active space", "CASSCF", "NEVPT2", "T9 recovery", "active orbitals", "spin contamination"),
        "An active space is a chemically chosen set of electrons and orbitals treated with several electronic arrangements.",
        "Some states cannot be described adequately by one dominant arrangement. Choosing inappropriate orbitals can still give misleading results.",
        "Use this only with an instructor-reviewed multireference protocol, including the orbital identities and state.",
        "Calculations → Method and settings → Advanced: multireference spin recovery (T9).",
        ("Enter the supplied active-electron count, orbital indices and chemical rationale.",
         "CAS(2,2), for example, means two electrons in two active orbitals; it does not identify which orbitals or assign a model for your molecule.",
         "Check occupations and state character; preserve the failed original calculation and recovery record."),
        ("Do not guess an active space to bypass a spin warning.",
         "A successful replacement single-point calculation does not complete an originally requested optimization, frequency or anharmonic calculation.")),
    "isotopes": _topic(
        "Isotopes and harmonic reanalysis", ("isotope", "13C", "carbon 13", "deuterium", "D2O", "18O", "mass substitution"),
        "Isotopes are atoms of the same element with different neutron counts. Their different masses change nuclear motion.",
        "Isotope shifts can help connect a structure with observed spectroscopy, but only when the atom labels and the compared quantities are correct.",
        "Use this for an assigned isotope comparison with a qualified matching Cartesian harmonic Hessian.",
        "More scientific tools → Spectra and properties → isotope reanalysis. Keep the chosen parent Hessian, geometry and atom labels visible in your record.",
        ("Identify which atom receives which isotope; retain the original atom order.",
         "Load the matching parent Hessian and select the intended substitution.",
         "Inspect the newly generated frequencies/constants and save their source and units."),
        ("Within the usual Born–Oppenheimer approximation, isotope substitution does not change the electronic potential at fixed geometry; harmonic mass reanalysis needs no new electronic-energy calculation.",
         "This reuse does not create an anharmonic force field or certify independent experimental isotope accuracy.")),
    "spectroscopy": _topic(
        "Calculated properties and experimental spectra", ("spectroscopy", "spectrum", "spectra", "IR", "infrared", "NMR", "peak", "vibration", "rotation"),
        "Spectroscopy studies how matter interacts with radiation. Different experiments, such as rotational, infrared and NMR spectroscopy, probe different properties.",
        "A calculated frequency or rotational constant is a model prediction. It is not automatically an observed experimental peak or a complete measured spectrum.",
        "Use this before interpreting the supported calculated observables or comparing them with an assigned experiment.",
        "Under More scientific tools, Spectra and properties reads supported native outputs and provides rotational-property, Hessian/isotope and numerical-data inspection tools.",
        ("Identify what the displayed quantity actually is: a rotational constant, harmonic vibrational mode or supplied numerical observation.",
         "Check units and whether a constant describes equilibrium geometry (Ae, Be, Ce) or includes nuclear-motion effects (A0, B0, C0).",
         "Compare a model prediction with the same type of experimental observable, using the method's stated limitations.",
         "Keep assignments, raw outputs and any experimental source separate in your report."),
        ("A harmonic mode is not proof of an experimental IR peak assignment; intensities, selection rules, conditions and anharmonic effects matter.",
         "This help does not enable NMR prediction, an experimental IR analysis pipeline or automatic spectral identification.")),
    "periodic": _topic(
        "Periodic structures and unit cells", ("periodic", "crystal", "solid", "unit cell", "CIF", "fractional coordinates", "material"),
        "A periodic model repeats a unit cell to represent an extended material. Both the cell vectors and atomic positions are part of the input.",
        "Wrong units, fractional-coordinate interpretation or composition can model a different material even if the picture looks plausible.",
        "Use this route only when your assignment concerns a periodic system rather than an isolated molecule.",
        "More scientific tools → Periodic structures → upload/select the periodic structure, validate it, select PAW files, then review the supported request.",
        ("Inspect the composition, cell and coordinate units from the supplied CIF or supported periodic JSON.",
         "Match every element to its assigned PAW file and numerical settings.",
         "Validate first; saving a request is not executing it. Read the actual operation and result status."),
        ("The bounded current native route is PBE/PAW single-point SCF; it does not establish band-gap prediction, cell optimization, spin/SOC or material-accuracy acceptance.",
         "A periodic input or SCF output alone does not demonstrate a stable crystal or converged material property.")),
    "compare_results": _topic(
        "Compare energies and population estimates", ("compare", "stable", "which is lower", "Boltzmann", "population", "free energy", "Gibbs", "isomer ranking"),
        "An energy comparison asks how compatible calculated structures differ under the same scientific model and conditions.",
        "Electronic energy and Gibbs free energy are different quantities. Mixing methods, compositions or states can create a meaningless ranking.",
        "Compare only after retrieving qualified compatible results for the question you were assigned.",
        "4 · Read and save results / Results → Advanced: compare structures and population models → Calculated structures → Compare calculated structures.",
        ("Select the intended calculated structures; clear the comparison selection if you want to start again.",
         "Choose the same recorded energy type, and inspect each result's method, basis, state and surroundings.",
         "Use a population model only when the required minima, free energies, temperature and other assumptions are justified.",
         "Download the tables with the comparison figure and keep its scientific qualifications."),
        ("Electronic energies omit nuclear-motion and entropy contributions; their weights are not measured equilibrium abundances.",
         "Equilibrium fractions need consistent free energies, temperature, degeneracies and standard state, plus accessible interconversion. Missing values must not become zero.")),
    "provenance": _topic(
        "Keep the calculation's evidence", ("provenance", "checksum", "SHA256", "run ID", "reproducible", "source", "audit"),
        "Provenance is the record linking a result to its original input, selected structure, settings, program and software versions.",
        "It lets you and your instructor identify which calculation produced a number and distinguish results that look similar.",
        "Keep this information for every reported result, including failed or corrected runs.",
        "Your files → File details and provenance; Calculations → retained calculation; Results → downloadable reports/bundles.",
        ("Retain the original file, selected frame, charge/spin, method/basis, surroundings, constraints and program version.",
         "Keep the request/run identifier with the matching retrieved output and warnings.",
         "Use file checksums to detect changed bytes, and include units and any temperature/standard state in your report."),
        ("A checksum proves byte identity, not chemical correctness.",
         "A successful engine exit, setup check or software installation is not full scientific validation.")),
    "geometry_builder": _topic(
        "Build a starting geometry", ("SMILES", "name", "builder", "draw molecule", "starting guess", "seed separation", "assemble"),
        "The builder creates a starting arrangement of atoms from supported molecular input, or places your selected monomers into a starting complex.",
        "A starting guess supplies coordinates for a later calculation; its appearance does not establish a stable or bound structure.",
        "Use it when your assignment allows you to prepare a starting geometry rather than supplying a finished calculation output.",
        "Calculations → Starting structure → Name or SMILES / Build starting geometry. Monomer assembly is in the advanced starting-complex disclosure.",
        ("Enter a supported name or SMILES from your course material and build the geometry.",
         "Inspect hydrogens, connectivity, charge, spin and intended stereochemistry.",
         "For monomer assembly, select your own saved monomers, verify their states, and use the assigned separation. Save the seed as a starting guess."),
        ("A generated geometry is not an optimized minimum or proof of binding.",
         "The builder/viewer does not certify stereochemistry, and an arbitrary separation is not an assigned scientific protocol.")),
    "input_frames": _topic(
        "Select a file, structure and frame", ("selected frame", "which structure", "multi frame", "SDF records", "PDB models", "retained input"),
        "One file can contain several structures or observations. Selecting the file and selecting the intended record are separate steps.",
        "Running frame one when you intended a later frame changes the geometry being calculated.",
        "Use these choices after upload and whenever you switch between starting structures or results.",
        "Your files → Your uploaded file → Structure / frame → Use selected starting geometry. Calculations also shows the Starting geometry selection.",
        ("Choose the correct retained file, then inspect every relevant structure/frame.",
         "Select the intended file record and read its retained metadata. Then use it as the starting geometry and open Calculations to inspect its 3D picture, atoms, state and isotope labels before submitting.",
         "In Calculations, verify the current molecule summary and picture before running; choosing a file/frame does not itself show a 3D preview in Your files."),
        ("Selecting a file does not certify its scientific quality or mean every frame was used.",
         "Using a calculated structure as a new starting input does not replace the original uploaded file.")),
    "data_preservation": _topic(
        "Original files, removal and backup", ("where my files", "original", "remove", "undo", "restore", "backup", "lost files", "save files"),
        "BASE retains uploaded originals separately from calculation drafts and results. Removing an item from a list changes its visibility rather than proving it was erased everywhere.",
        "You need the original input and raw result to check your work, retry safely and move between workspaces.",
        "Back up before creating a different Codespace, deleting a workspace or leaving an important completed calculation.",
        "Your files has Remove from list, Undo remove and Restore selected input. Keep your own copy of uploaded files; Calculations and Results provide available result downloads.",
        ("Use Remove from list to tidy a selection, or Undo remove / Restore selected input to recover an item.",
         "Keep a separate local copy of every file you upload, and download available completed calculation bundles to your own storage.",
         "Keep descriptive names, input hashes and run identifiers so you can distinguish revisions."),
        ("A new Codespace does not automatically copy another Codespace's local artifacts.",
         "Git Commit/Sync does not back up every file in BASE's external artifact directories. A browser download is not assignment submission.")),
    "engine_setup": _topic(
        "Chemistry programs and optional engines", ("engine", "do I need ORCA", "ORCA", "CFOUR", "xTB", "PySCF", "program unavailable", "setup failed", "why disabled"),
        "An engine is the program that performs a particular scientific calculation. BASE checks and connects available programs through this interface.",
        "A method must have a compatible available engine on the calculation computer. A disabled choice should explain its missing prerequisite.",
        "Check setup before choosing a method and when a program becomes unavailable.",
        "1 · Setup / Start here → Check ORCA & CFOUR for the remote route; Programs on your calculation computer for an approved local installation.",
        ("Read the availability message for the selected calculation environment.",
         "Use the assigned supported program. If a required program is unavailable, give the message to your instructor; do not silently substitute another method.",
         "For local use, Find installed engines and Use these executable paths are for already installed, approved executables."),
        ("ORCA and CFOUR are optional and strongly recommended. Their absence disables dependent operations while unrelated supported functions remain usable.",
         "Checking archive access is not installing an engine in every environment or completing a chemistry calculation. Students do not supply tokens or licensed archives here.")),
    "lab_access": _topic(
        "Connect your personal project to the lab", ("invitation", "lab app", "permission", "enrollment", "connect project", "403", "access denied"),
        "The lab invitation links your private personal project with the instructor's approved setup service through GitHub's permission controls.",
        "Course membership, App installation and a successful project setup request are different steps; none alone proves a chemistry calculation worked.",
        "Use this for initial course enrollment or an instructor-directed access repair.",
        "1 · Setup / Start here → Connect using an instructor invitation (personal projects). Use the complete links supplied by your instructor.",
        ("Check the current project belongs to your own GitHub account and is the intended private independent project.",
         "Save the instructor's setup and App links, authorize the App only for that project, and submit the prepared request as its owner.",
         "After confirmed provisioning, follow the course's new-Codespace instructions; preserve any earlier uploads first.",
         "If there is an error or no confirmed response, keep the request link and exact message for your instructor rather than creating repeated requests."),
        ("Never paste passwords, tokens, cookies or private keys into this interface or a help search.",
         "A repository connection does not grant unlimited compute, resolve billing, or refresh permissions in an old Codespace.")),
    "job_status": _topic(
        "What is my calculation doing?", ("job status", "queued", "waiting", "running", "how long", "finished", "why failed", "failed", "timeout"),
        "Status describes the recorded stage of a particular request: preparing, submitted, queued, running or finished with a reported outcome.",
        "Waiting for a computer is different from performing chemistry. A finished workflow can still contain failed, skipped or scientifically unqualified work.",
        "Use status after submitting once and before deciding whether to retrieve, cancel or retry.",
        "Calculations → Run calculation → Refresh calculation status. Previous calculations opens a retained request and its own status.",
        ("Check the request/run identifier and refresh its status.",
         "Queued/waiting means execution is not yet confirmed; running means work has started. Read the outcome and warnings when it finishes.",
         "Follow the linked run details if needed. Keep a startup, access, timeout or chemistry error with its request ID for diagnosis."),
        ("No fixed completion time is promised; molecule, method, basis, properties, hardware and service queues all affect it.",
         "Do not repeatedly submit to make a queued calculation start sooner. A status refresh does not run new chemistry.")),
    "cancellation_retry": _topic(
        "Stop a calculation and retry safely", ("cancel", "stop", "retry", "run again", "cancellation requested", "duplicate job"),
        "Cancellation asks the selected job to stop. Retrying creates or submits work again; it does not correct the scientific input by itself.",
        "A duplicate job can consume resources without fixing the original problem. Keep failed evidence so a corrected run can be understood.",
        "Cancel a job you intentionally want to stop. Retry after identifying the specific input, access or resource problem.",
        "Calculations → Cancel calculation, or the guided Stop current calculation button. The engine check and specialized search/HPC tools have their own cancel controls.",
        ("Confirm which request is active, then use its cancellation control once.",
         "Wait for an observed terminal status; cancellation requested is not yet confirmation that the job stopped.",
         "Read and retain the error/output. Correct only the justified setting or prerequisite, verify the selected input, then submit a new bounded request."),
        ("Cancellation can leave partial results, which must retain their partial/failed status.",
         "Do not change an assigned method, charge or spin solely to make a retry pass.")),
    "retrieve_results": _topic(
        "Retrieve the result that belongs to your job", ("retrieve", "download calculation bundle", "no results", "artifact", "matching result", "get output"),
        "Retrieval brings a completed remote job's retained artifacts into BASE so you can inspect and download them.",
        "A latest run or similarly named file may belong to another request. Request and artifact identity protect against interpreting the wrong result.",
        "Retrieve after the intended job reaches a suitable terminal status and its artifacts are available.",
        "Calculations → Refresh calculation status → Retrieve and inspect results. Use Previous calculations → Open selected calculation for an older retained job.",
        ("Select or confirm the intended request/run, then retrieve its results.",
         "Check operation, input identity, method, units, native outcome and warnings before using a value.",
         "Download calculation bundle and retain the raw output with any figures or exported tables."),
        ("Successful download does not mean numerical convergence or scientific accuracy.",
         "Missing or expired remote artifacts cannot be reconstructed from a run label alone.")),
    "read_results": _topic(
        "Read and save a calculated result", ("read results", "did my calculation succeed", "did it work", "successful calculation", "did calculation work", "interpret", "what does it mean", "where is my result", "report", "save answer"),
        "A useful result states what was calculated, its value and units, and the evidence and limitations that make the interpretation possible.",
        "An attractive plot or a number without its method, state and convergence record can support the wrong conclusion.",
        "Read these checks after retrieval and before submitting your work.",
        "4 · Read and save results opens Results. Use Spectra and properties for the supported native-property and Hessian/isotope tools.",
        ("Identify the molecule/selected structure and the actual operation performed.",
         "Read convergence, warnings, units and whether a value is supplied, newly calculated or derived from earlier data.",
         "Compare only compatible quantities; an electronic energy is not a Gibbs free energy and Be is not automatically B0.",
         "Download the matching calculation bundle and report data when those controls are available. Save displayed result summary saves only the text shown on screen; keep the raw evidence separately, then write your interpretation with its assumptions."),
        ("Unavailable or missing quantities stay unavailable; a blank is not zero.",
         "Downloading or saving a report is separate from the course's actual submission and instructor-collection process.")),
    "result_files": _topic(
        "Where results are saved and how to submit them", ("where my results", "file location", "output directory", "Classroom50", "submit report", "collection", "export"),
        "BASE keeps managed results outside application source. Download controls let you save selected bundles and report exports into your own storage.",
        "A private project link or successful download does not ensure your instructor can collect and read the assignment.",
        "Save a durable copy after completing important work and before changing or deleting a workspace.",
        "For retrieved remote calculations, Calculations offers the matching calculation-bundle link when available. Results offers available report/figure/table downloads. Save displayed result summary saves only the current text, not the complete native output or provenance archive.",
        ("Use the available calculation-bundle and report-data links for the result you intend to discuss. A displayed-summary download alone is not a raw-result backup.",
         "Choose a clear location on your computer and keep input/run identifiers with the files.",
         "Use the browser or VS Code graphical submission steps your instructor specifies for the actual Classroom50 assignment.",
         "Check the submitted report can be opened through that course route."),
        ("Your private personal repository is not automatically the instructor's collection location.",
         "Commit/Sync does not copy every managed result from outside source, and downloads alone do not submit an assignment.")),
    "updates": _topic(
        "Setup, compatible updates and restart", ("retry setup", "update", "restart", "rollback", "roll back", "software version"),
        "BASE manages its installed tools and compatible software updates. Restarting the interface starts its service again using the selected managed runtime.",
        "Interface software, hosted calculation workers and project workflow files have separate versions; a partial update can leave them incompatible.",
        "Use these controls when your instructor announces a reviewed update or setup reports a specific recoverable failure.",
        "1 · Setup / Start here → CoChem tools and updates → Retry setup / Check for updates / Apply compatible updates / Restart interface / Roll back update.",
        ("Save originals and completed bundles before a workspace change.",
         "Check the displayed status and apply only an available compatible update as directed.",
         "Restart when the interface offers it after a managed change; confirm the new status and that your retained inputs/results remain available.",
         "If an update fails, retain the error and use the supported rollback or instructor recovery route."),
        ("A disabled restart button is not proof that a restart happened.",
         "A runtime update does not publish replacement project workflows or grant new Codespaces permissions.")),
    "resources": _topic(
        "Time, memory, processors and storage", ("how long", "timeout", "cores", "RAM", "memory", "disk", "cost", "minutes", "resource limit"),
        "A calculation uses processors, memory, storage and time. The resource fields limit what the job is allowed to use.",
        "An oversized request may be refused; an insufficient limit can stop a legitimate calculation. More processors do not always make a small job faster.",
        "Review resource bounds before submission and when diagnosing an out-of-memory or time-limit failure.",
        "Calculations → Run calculation has the selected route's timeout, cores and memory controls. Advanced local setup has the disk requirement; HPC has separate scheduler requests.",
        ("Use the bounded resources supplied by your instructor and permitted by the actual worker.",
         "Read units carefully: seconds versus minutes, MB per core versus total memory, and GB of disk.",
         "Check your account's actual Actions/Codespaces payer and usage; keep a timeout or resource failure with the run record."),
        ("Education or team membership does not establish unlimited usage or a shared allowance.",
         "Changing numerical convergence or the scientific method is not an automatic remedy for a resource failure.")),
    "conformer_search": _topic(
        "Search for alternative conformations", ("TOPOS", "conformer search", "CREST", "GOAT", "search protocol", "deduplication", "ensemble"),
        "A conformer search explores alternative nuclear arrangements of the intended molecule or complex and retains candidate structures.",
        "One optimized starting geometry can miss other arrangements. A search helps identify candidates for later qualified calculations.",
        "Use it when your assignment explicitly requires conformational exploration and the needed search engine is available.",
        "Calculations → Advanced: other calculation tools → Other structures and energies. Use its available Calculation / Method choices and Start TOPOS calculation.",
        ("Check the intended structure and electronic state, then select the assigned supported search protocol and bounds.",
         "Read the search status and any partial or unavailable outcome.",
         "Inspect retained structures and use qualified follow-up calculations before ranking physical minima or populations."),
        ("Searches do not prove completeness or that every candidate is a minimum.",
         "Do not loosen duplicate thresholds to discard inconvenient candidates. Unknown or incompatible energies must not be ranked as measured values.")),
    "conformer_pools": _topic(
        "Merge recorded conformer pools", ("pool producer", "recorded energy", "merge", "sieve", "duplicate conformer", "energy ranking"),
        "A conformer pool is a collection of candidate structures and any genuinely recorded energies and scientific context.",
        "Duplicate removal and energy ranking require different checks. Missing or incomparable metadata can make a plausible ranking meaningless.",
        "Use this for genuine supported CREST/GOAT pool files, rather than ordinary coordinate-only starting files.",
        "Your files → Combine conformer ensembles and remove duplicates. Set Pool producer and Recorded energy unit before the specialized upload when required.",
        ("Declare the producer and actual energy units from the file; do not guess them from a magnitude.",
         "Select the pools, then declare common charge, spin, engine, method, basis and version only when they truly share those settings.",
         "Merge and sieve, inspect the retained conformers, and choose the intended geometry for a later calculation."),
        ("Supplying a text label does not establish scientific comparability or qualify a minimum.",
         "Coordinate-only or unknown-energy observations remain starting geometries and cannot establish equilibrium populations.")),
    "scans": _topic(
        "Potential-energy scans", ("TORQ", "PES", "scan", "dihedral", "separation", "scan points", "barrier"),
        "A scan calculates values along a chosen coordinate, such as the separation of two fragments. It samples a limited path through a larger energy surface.",
        "A curve can show how the chosen model responds along that path, but its maxima and minima need careful interpretation.",
        "Use only the scan operation and coordinate range assigned for your system.",
        "Calculations → Advanced: other calculation tools → Distance scans and bonding → Method / Basis set / Start distance (Å) / End distance (Å) / Number of points, then the available scan control.",
        ("Check the two fragment definitions, charge/spin and the assigned method/basis.",
         "Enter the intended coordinate range and number of points, keeping units explicit.",
         "Read which points actually computed and retain failures or uncomputed points with the curve."),
        ("The accepted bounded TORQ separation route is rigid: monomer internals and orientation stay fixed. It is not a relaxed or full multidimensional PES.",
         "A scan maximum is not automatically a transition state, and a short curve does not validate a barrier, minimum or universal accuracy.")),
    "orbital_analysis": _topic(
        "Bond indices and orbital-analysis names", ("bond order", "Wiberg", "Lowdin", "Löwdin", "NBO", "NAO", "charge analysis", "orbital backend"),
        "Population analysis interprets a calculated electronic state using a chosen mathematical convention. Bond indices and atomic charges depend on that convention.",
        "A reported index is not an exact integer bond count, and differently named analyses cannot be substituted for one another.",
        "Use an analysis only when your assignment calls for it and its genuine required backend is available.",
        "Calculations → Advanced: other calculation tools → Distance scans and bonding → orbital/bond-analysis controls. Check the exact enabled analysis name and returned report.",
        ("Use the assigned stable converged electronic calculation and compatible backend.",
         "Read the analysis name, method/basis, charge/spin and matrix/checkpoint provenance.",
         "Interpret trends within the same convention and retain the numeric table with any bond diagram."),
        ("AO Löwdin Wiberg indices are not NAO Wiberg indices or Natural Bond Orbital analysis.",
         "Unavailable NBO/NAO controls remain unavailable until an actual supported producer exists; help does not enable them.")),
    "software_modules": _topic(
        "BASE, TOPOS, TORQ and validated handoffs", ("module", "component", "provider", "recipient", "handoff", "install module", "capability"),
        "BASE is your entry point. TOPOS and TORQ provide their own reviewed scientific operations, which BASE installs and presents here.",
        "A module name alone does not establish that it is installed or that every scientific operation is available.",
        "Read module status during setup or when a required research operation is disabled.",
        "Start here → CoChem tools and updates shows setup. Advanced module handoff tools are in Results; available scientific operations stay in their relevant calculation panels.",
        ("Let BASE install the reviewed components; do not clone a separate module repository as a student workaround.",
         "Refresh availability and read the specific operation's prerequisite or failure.",
         "Use an advanced validated handoff only when the course protocol requires that input and recipient."),
        ("A validated handoff package is not proof that the recipient executed chemistry.",
         "An installed module or successful import is not acceptance of every scientific method.")),
    "hpc": _topic(
        "Advanced: institutional cluster jobs", ("HPC", "Slurm", "PBS", "scheduler", "queue", "partition", "walltime", "tasks per node"),
        "An HPC scheduler allocates an institution's computing resources. A submitted job may wait until the requested resources are available.",
        "Cluster names, queues, access and resource rules are specific to the institution; they cannot be inferred from a local interface setting.",
        "Use this route only with a configured, instructor-approved cluster connection and protocol.",
        "Start here → Run calculations on → HPC; Calculations exposes the corresponding scheduler connection, submit, status and retrieval controls.",
        ("Use the supplied scheduler/queue, core, memory and walltime settings.",
         "Check the HPC connection, submit once, and follow its retained scheduler job ID.",
         "Refresh, cancel or retrieve that specific job using the corresponding HPC controls."),
        ("Selecting Slurm/PBS does not create cluster access or prove a physical allocation works.",
         "A saved scheduler request is not an executed native job; retain the actual worker and result evidence.")),
    "periodic_settings": _topic(
        "Advanced: PAW files and periodic numerical settings", ("PAW", "pseudopotential", "cutoff", "Ry", "k point", "SCF steps", "periodic tolerance"),
        "PAW/pseudopotential files describe element-specific core treatment for the plane-wave calculation. Cutoffs and sampling control its numerical representation.",
        "Changing these settings can change energies and properties. An arbitrary low cutoff may run quickly while giving an unconverged answer.",
        "Use the assigned compatible PAW files and numerical-convergence protocol for a supported periodic calculation.",
        "More scientific tools → Periodic structures → Upload PAW files → each element's PAW file choice → wavefunction/density cutoffs and SCF settings.",
        ("Match each actual element to its intended PAW file and functional.",
         "Use the assigned explicit cutoffs, tolerance, maximum steps and sampling, with units checked.",
         "Validate the structure/settings, then inspect the native SCF outcome and convergence before interpreting it."),
        ("File availability and a successful request save do not establish periodic convergence.",
         "The current bounded route does not enable arbitrary gap, cell, magnetic or SOC calculations.")),
    "cbs": _topic(
        "Advanced: complete-basis extrapolation", ("CBS", "complete basis", "basis pair", "extrapolate", "correlation energy"),
        "Complete-basis extrapolation estimates a limiting energy from a specified sequence of compatible finite-basis calculations.",
        "The estimate depends on the chosen method, basis family, formula and available underlying calculations.",
        "Use it only for an assigned protocol with the required pair and actual supporting results.",
        "Calculations → Method and settings → Advanced: complete-basis extrapolation → CBS pair.",
        ("Select the exact assigned basis pair and method.",
         "Check that the required calculations actually completed and that their settings are compatible.",
         "Retain the finite-basis values, extrapolation convention and limitations with the final estimate."),
        ("Choosing a pair does not establish that extrapolation ran.",
         "A CBS energy estimate does not automatically certify a CBS geometry or experimental accuracy.")),
    "help_navigation": _topic(
        "Find help without changing your calculation", ("help", "teach me more", "search", "explain", "what why when where how"),
        "Help explains the interface and scientific concepts. It does not submit a job or select scientific parameters for you.",
        "You can learn a term or find a control while keeping the current input and settings intact.",
        "Use Help or Teach me more beside a task, or search with the words you naturally use.",
        "Use the persistent Help/search area or the nearby closed Teach me more disclosure.",
        ("Try a phrase such as why failed, where my files, same formula, spin or how long.",
         "Read What first, then open Why, When, Where and How for detail.",
         "Return to the named control; if the scientific choice remains uncertain, use your assignment or ask your instructor."),
        ("Help works offline without program access, an LLM account or an API key.",
         "It cannot determine your molecule's state, prescribe a method or diagnose an unseen failed run.")),
    "units": _topic(
        "Read the units before comparing numbers", ("units", "angstrom", "ångström", "Å", "Hartree", "Eh", "kcal", "kJ", "cm-1", "wavenumber", "MHz", "kelvin"),
        "A unit tells you what a number measures and its scale: distance, energy, temperature or a spectroscopic quantity.",
        "The same-looking number can mean something entirely different in another unit. A missing or guessed unit can invalidate a comparison.",
        "Check units on every imported quantity, setting, table column and plotted axis before comparing or reporting it.",
        "Read labels beside settings, Your files → File details and provenance, and the units in retrieved Results / Spectra and properties tables.",
        ("Å (ångström) is a distance: 1 Å is 0.1 nm, or one ten-billionth of a metre. Ordinary XYZ here uses ångströms; supported schema readers use their declared coordinate convention.",
         "Eh or Hartree is an energy unit. For a molecular energy difference, 1 Eh per molecule corresponds to approximately 2625.5 kJ/mol or 627.5 kcal/mol. Keep the actual source units and conversion convention with your report.",
         "cm−1 is wavenumber, commonly used for vibrational spectroscopy. MHz is a frequency unit used for rotational constants. K is absolute temperature in kelvin.",
         "Compare the same physical quantity under compatible settings, then convert its units explicitly when required by the assignment."),
        ("Do not compare unrelated absolute molecular energies as an isomer ranking; composition and electronic state must be compatible.",
         "This educational explanation does not relabel an imported value or replace the program's verified numerical conversions.")),
}


# Every mapping below is an authored instruction for a particular GUI attribute.
# A topic may explain several related controls, but its count is not a claim that
# all widgets or every dynamically created descendant have been covered.
CONTROL_HELP = {}


def _controls(topic, location, advanced, hints):
    for control, hint in hints.items():
        if control in CONTROL_HELP:
            raise ValueError("A control must have one primary help topic: " + control)
        CONTROL_HELP[control] = dict(topic=topic, hint=hint, advanced=advanced, location=location)


_controls("workspace", "Start here", False, {
    "btn_install": "Open setup and check where this project's calculations will run.",
    "calc_env_dropdown": "Choose the calculation computer specified for the course; it can differ from the computer showing this page.",
    "interact_env_dropdown": "Describe where this interface runs; this does not move a calculation to another computer.",
    "gh_repo_input": "Confirm your intended private project as owner/repository before checking access or submitting.",
    "gh_branch_input": "Keep the instructor-approved project branch; a branch name selects project files, not a scientific method.",
})
_controls("first_calculation", "Header and navigation", False, {
    "btn_matrix": "Open Calculations to inspect your selected molecule and assigned settings before running.",
    "btn_inputs": "Open Your files to upload and select your own scientific input.",
    "btn_modules": "Open Results to interpret and download retained calculated values.",
    "btn_inspector": "Open supported native-property and Hessian/isotope inspection tools.",
    "btn_periodic": "Open the separate unit-cell route only for an assigned periodic system.",
    "btn_continue_inputs": "Continue to Your files after checking setup; this only changes the displayed page.",
    "btn_continue_calculation_settings": "Continue to the selected molecule's calculation settings; this does not submit work.",
})
_controls("lab_access", "Start here → instructor invitation", False, {
    "course_access_panel.project": "Check the personal project that will receive access; do not enter an instructor-owned project instead.",
    "course_access_panel.controller": "Paste your instructor's complete setup link; it is a web address, not a credential.",
    "course_access_panel.app_slug": "Paste the complete App installation link supplied by your instructor.",
    "course_access_panel.orca": "Request optional ORCA access only when your course uses it; requesting access does not run ORCA.",
    "course_access_panel.cfour": "Request optional CFOUR access only when your course uses it; requesting access does not run CFOUR.",
    "course_access_panel.btn_save": "Save these invitation links, then follow the App authorization and prepared-request steps.",
    "course_access_panel.btn_clear": "Clear a mistaken saved invitation; this does not withdraw existing GitHub permissions or delete files.",
    "course_access_panel.btn_refresh": "Recheck the project's reported granted access; a successful metadata check is not a completed calculation.",
})
_controls("engine_setup", "Start here → program access", False, {
    "btn_remote_engine_check": "Check which optional programs this project can obtain; read the engine-specific outcome.",
    "license_mode": "Choose which optional installed engine to check for the approved local setup.",
    "run_install_btn": "Run the supported setup for this calculation computer; installation does not execute your research calculation.",
    "btn_setup_retry": "Retry setup after the reported prerequisite has been corrected; retain the original error.",
})
_controls("engine_setup", "Start here → advanced local program setup", True, {
    "bin_orca": "Select the approved ORCA executable on the local calculation computer, not an archive or input file.",
    "bin_cfour": "Select the approved CFOUR executable on the local calculation computer.",
    "btn_detect_bins": "Look for already installed programs; discovery is followed by validation before execution.",
    "btn_save_bins": "Validate and use the selected executable locations; this is not a request to enter a download token.",
    "btn_refresh_wsl": "Read the available Windows/WSL status before using a local Linux engine route.",
})
_controls("updates", "Start here → CoChem tools and updates", False, {
    "btn_setup_updates": "Check for an available compatible software update when your instructor announces one.",
    "btn_setup_apply": "Apply the reviewed compatible update offered here; preserve a backup of important files first.",
    "btn_setup_rollback": "Use the supported previous managed version after an update problem; keep the failure record.",
    "btn_setup_restart": "Restart the managed interface when offered after an update or rollback, then confirm it is usable again.",
})
_controls("scientific_inputs", "Your files → upload", False, {
    "input_kind": "Choose what your file actually contains; Detect from file is the ordinary molecular starting route.",
    "input_upload": "Upload the original scientific file, then inspect its retained structures or data.",
    "xyz_upload": "Upload an XYZ starting geometry; verify the atom identities, coordinate units, charge and spin.",
    "btn_input_refresh": "Refresh the retained-input list without uploading another copy or running chemistry.",
    "btn_inbox_scan": "Import supported files already placed in the displayed VS Code inbox.",
    "btn_inbox_watch": "Watch that inbox for new files; this imports inputs rather than submitting calculations.",
    "btn_inbox_stop": "Stop watching the inbox; previously retained files remain available.",
})
_controls("input_frames", "Your files → choose a structure", False, {
    "input_library_choice": "Choose the retained original file whose structures or data you want to inspect.",
    "input_record_choice": "Choose the intended structure/frame within that file; a multi-record file has more than one possible input.",
    "btn_use_input_geometry": "Use the selected molecular record as the calculation's starting geometry, then check its displayed state.",
    "student_geometry_choice": "Select the intended saved starting geometry and verify the current-molecule summary.",
    "actions_calculated_geometry": "Choose the particular calculated geometry to inspect or reuse, retaining its original run identity.",
    "btn_actions_use_geometry": "Create a new starting input from that calculated structure; do not treat this as a new optimization.",
})
_controls("data_preservation", "Your files → retained input controls", False, {
    "btn_remove_input": "Hide the selected retained input from the active list; its original is retained for restoration.",
    "btn_remove_geometry": "Hide the selected geometry from the active list while retaining the original input.",
    "btn_undo_input_remove": "Undo the most recent input removal without re-uploading or changing its original bytes.",
    "btn_undo_geometry_remove": "Undo the most recent geometry removal.",
    "removed_input_choice": "Choose which removed item you want to restore; inspect its identity before restoring it.",
    "btn_restore_input": "Restore the selected removed input to the active list.",
    "btn_clear_r2_attachment": "Clear the selected R2 reference attachment from this draft; retain the original reference file.",
    "btn_clear_read_attachment": "Clear the selected starting-Hessian attachment without claiming another Hessian was calculated.",
})
_controls("molecule_identity", "Calculations → Starting structure", False, {
    "student_input_role": "Label the input's intended role, such as monomer or complex; the label does not verify its chemistry.",
    "student_input_label": "Give this geometry a useful name so you can distinguish it from other starting arrangements.",
    "btn_save_input_details": "Save the selected geometry's label, role and electronic-state details after checking them.",
})
_controls("charge_spin", "Calculations → electronic state", False, {
    "charge_input": "Use the assigned total charge of the entire selected structure; neutral does not determine its spin.",
    "multiplicity_input": "Use the intended spin multiplicity, 2S + 1; do not infer it from charge alone.",
    "geometry_charge": "Set the selected structure's total charge using its intended chemical state.",
    "geometry_multiplicity": "Set the selected structure's intended spin multiplicity; check the separate charge field too.",
    "btn_research_fragment_states": "Check each monomer's own charge and spin before a fragment-dependent research calculation.",
})
_controls("geometry_builder", "Calculations → Starting structure", False, {
    "smiles_input": "Enter a supported name or SMILES for a starting guess, then inspect the generated atoms and stereochemistry.",
    "btn_build_smiles": "Build a starting geometry; this does not establish an optimized minimum or experimental structure.",
})
_controls("geometry_builder", "Calculations → advanced starting-complex preparation", True, {
    "student_monomer_choices": "Select your saved monomer geometries with their verified electronic states.",
    "student_seed_separation": "Use the assigned starting separation in ångströms; a placement distance is not a predicted binding distance.",
    "btn_assemble_monomers": "Place the selected monomers into an initial complex seed while retaining their internal geometry.",
    "matrix_geometry": "Advanced coordinate editing changes the calculation draft; verify atoms, atom order, units and state afterward.",
})
_controls("method_basis", "Calculations → Method and settings", False, {
    "matrix_engine": "Choose an available compatible program for the assigned method; program access alone is not a calculation.",
    "matrix_method": "Use the exact method assigned for your scientific question, preserving it across comparisons.",
    "matrix_basis": "Use the basis specified with that method; a larger basis does not fix an unsuitable approximation.",
    "unphysical_override": "Preserve required dispersion safeguards; this control is not permission to bypass scientific policy.",
})
_controls("theory_tiers", "Calculations → advanced method family", True, {
    "matrix_tier": "Choose a method family only as the protocol requires; a higher tier number is not a quality score.",
    "product_class_selector": "Advanced scientific goal sets required safeguards; use the class supplied for the study rather than guessing from a molecule name.",
})
_controls("solvent", "Calculations → Method and settings → Surroundings", False, {
    "matrix_solvation": "Choose the assigned gas-phase or solvent model consistently across the structures being compared.",
})
_controls("cbs", "Calculations → advanced complete-basis extrapolation", True, {
    "matrix_cbs_pair": "Choose the required basis pair only for an assigned supported extrapolation; selecting it is not proof the underlying calculations ran.",
})
_controls("calculation_types", "Calculations → Run calculation", False, {
    "actions_operation": "Choose the assigned remote task: energy, optimization and frequencies answer different questions.",
    "native_operation": "Choose the assigned supported local operation before submitting.",
    "cfour_operation": "Choose an operation that this CFOUR route genuinely supports; unavailable operations cannot be completed by an unrelated single point.",
    "btn_execute": "Check the current molecule, state, method and task, then submit once using this button's current operation label.",
})
_controls("resources", "Calculations → route-specific resource limits", True, {
    "actions_timeout": "Set the permitted remote chemistry time limit in seconds; exceeding it stops the job rather than proving convergence.",
    "actions_cores": "Use the assigned processor count within the actual remote worker's bound.",
    "actions_memory": "Check this field's MB-per-core units; it is not necessarily the job's total memory.",
    "native_timeout": "Use a justified local time bound in seconds and preserve timeout diagnostics if the calculation stops.",
    "install_min_disk": "This is the setup disk-admission requirement in GB; do not lower it merely to label an inadequate machine ready.",
})
_controls("job_status", "Calculations → retained request and status", False, {
    "btn_actions_refresh": "Refresh the selected request's actual remote status; this does not submit another calculation.",
    "actions_history": "Select a previous retained calculation by its identifying record rather than assuming the newest run is yours.",
    "btn_actions_open": "Open the selected retained calculation and confirm its input, operation and run identity.",
})
_controls("cancellation_retry", "Calculations → active request", False, {
    "btn_cancel": "Request cancellation of the active calculation, then wait for an observed stopped outcome.",
    "guided_cancel": "Request stopping the current calculation; cancellation requested is not yet confirmation that it stopped.",
    "btn_remote_engine_cancel": "Cancel the selected program-access check; this is separate from cancelling a chemistry calculation.",
})
_controls("retrieve_results", "Calculations → completed request", False, {
    "btn_actions_retrieve": "Retrieve and inspect artifacts matched to this request/run, then read convergence and warnings.",
})
_controls("result_files", "Calculations → advanced output settings", True, {
    "btn_save_matrix": "Save the current configuration for reproducibility; saving does not execute chemistry or submit the assignment.",
    "artifact_output_path": "Advanced output storage is on the calculation computer; a path there is not automatically a file on your laptop.",
    "project_name": "Use a clear name for the saved configuration/output group; it does not rename your GitHub project or identify a chemical state.",
    "live_preview": "Read the actual run configuration before execution; a preview is not a completed calculation.",
})
_controls("conformer_search", "Calculations → Advanced: other calculation tools → Other structures and energies", True, {
    "topos_heuristic": "Choose the assigned available conformer-search protocol; different searches explore different candidates.",
    "topos_dedup": "Read the duplicate-removal tolerance with its exact meaning; preserve the required scientific thresholds.",
    "topos_walltime": "Bound this search in minutes; a stopped or partial search is not a completeness proof.",
    "btn_topos_refresh": "Refresh the actual search-engine availability before choosing a supported protocol.",
    "btn_topos_submit": "Start the assigned bounded conformer search after checking input and state.",
    "btn_topos_cancel": "Cancel this conformer-search request and keep its partial/failed status and retained candidates.",
    "btn_topos_promote": "Publish the eligible retained ensemble into the managed research inputs; this does not certify every candidate as a minimum.",
    "research_topos_operation": "Choose a genuinely available TOPOS operation; read its required input and qualification.",
    "research_topos_engine": "Select the assigned scientific method supported by this TOPOS operation.",
    "research_matrix_recipe": "Use the assigned optimization recipe, preserving its method, references and convergence requirements.",
    "research_candidates": "Choose the assigned candidate bound; a requested count does not establish exhaustive sampling.",
    "btn_research_topos": "Run the selected supported TOPOS research operation and retain its actual result status.",
    "btn_research_refresh": "Refresh operation-specific capability information; availability is not completed scientific work.",
})
_controls("conformer_pools", "Your files → combine conformer ensembles", True, {
    "input_pool_producer": "Declare the genuine producer of this pool rather than treating an arbitrary XYZ file as a completed search.",
    "input_pool_energy_unit": "Declare the energy unit actually recorded by the producer; never infer it by guessing a conversion.",
    "input_pool_choices": "Choose the retained pools to merge, checking composition and scientific compatibility.",
    "input_pool_declare_context": "Declare a common state/protocol only when every selected observation genuinely shares it.",
    "input_pool_charge": "Enter the common total charge actually used to produce these observations.",
    "input_pool_multiplicity": "Enter the common recorded spin multiplicity; an interface default is not evidence of it.",
    "input_pool_engine": "Record the actual calculation engine used for the selected energies.",
    "input_pool_method": "Record the exact shared method; a text label cannot make incompatible energies comparable.",
    "input_pool_basis": "Record the actual common basis, or the genuine no-basis convention of a parameterized model.",
    "input_pool_version": "Record the actual engine or model version with these observations.",
    "btn_sieve_inputs": "Merge and test duplicate candidates while retaining original observations and unknown quantities.",
    "input_unique_conformer": "Inspect a particular retained conformer, including its lineage and any missing qualification.",
    "btn_use_unique_conformer": "Use that candidate as a starting geometry; duplicate removal does not make it a verified minimum.",
})
_controls("fragments_constraints", "Calculations → Advanced: other calculation tools → Monomer constraints", True, {
    "student_fragment_atoms": "Check which atom indices belong to each monomer; a group label alone does not validate the chemistry.",
    "btn_detect_fragments": "Suggest monomer partitions from geometry, then inspect them before using a fragment-dependent calculation.",
    "cb_recipe_r1": "Freeze the assigned monomer internal coordinates while allowing the specified relative motion; do not call the result fully relaxed.",
    "cb_recipe_r2": "Use R2 only with the matching validated high-level reference monomers and assigned production protocol.",
    "r2_reference_manifest": "Select the validated reference-monomer record matching this geometry and atom mapping.",
    "scientific_r2_upload": "Upload the genuine assigned R2 reference package; missing reference calculations are not synthesized.",
    "fragment_preview": "Inspect the generated constraint block and atom indices; correct syntax alone does not prove an executed trajectory preserved rigidity.",
})
_controls("active_space", "Calculations → advanced T9 recovery", True, {
    "t9_config_path": "Select an instructor-reviewed active-space configuration for this system and operation.",
    "t9_enable": "Enable explicit recovery only with a justified active space and supported requested operation.",
    "t9_method": "Use the prescribed CASSCF/NEVPT2 recovery method; it does not repair a poor active-space choice.",
    "t9_basis": "Use the recovery basis required by the reviewed protocol and keep it in the result record.",
    "t9_electrons": "Enter the chemically justified active-electron count, not a guessed number to clear a warning.",
    "t9_orbitals": "Enter the actual distinct orbital indices supplied for this system; verify the stated indexing convention.",
    "t9_rationale": "Explain why those electrons and orbitals represent the electronic state being treated.",
})
_controls("hessian", "Spectra and properties / advanced starting Hessian", True, {
    "install_data_path": "Select an actual geometry-bound scientific bundle only for the specialized setup check that requires it.",
    "btn_validate_install_data": "Validate the supplied bundle; this does not create a Hessian or make it an ordinary setup prerequisite.",
    "scientific_read_upload": "Upload the genuine starting Hessian that matches this geometry, atom order, frame and units.",
    "scientific_initial_hessian": "Use the assigned model or compatible READ Hessian; a starting model is not a calculated spectrum.",
    "calculation_hessian_choice": "Choose the parent Hessian from the intended retained calculation, keeping its source identity.",
    "isotope_hessian_path": "Select a matching native or geometry-bound Hessian bundle, not a matrix from another structure.",
    "btn_load_hessian": "Load the matching geometry and Hessian together before the requested analysis.",
    "btn_clear_hessian": "Clear the current Hessian selection; originals and earlier calculation records remain separate.",
})
_controls("isotopes", "More scientific tools → Spectra and properties → isotope reanalysis", True, {
    "btn_run_isotope_reanalysis": "Reanalyze the compatible parent harmonic Hessian with the selected isotope masses; this is not a new electronic calculation.",
})
_controls("spectroscopy", "Spectra and properties", True, {
    "inspector_file_input": "Choose a supported genuine output or numerical file and identify what observable it actually contains.",
    "btn_parse_inspector": "Read supported calculated properties from the selected native output; this does not predict a missing spectrum.",
    "btn_read_hdf5": "Inspect bounded supplied HDF5/NPZ data while preserving source, units and missing quantities.",
})
_controls("scans", "Calculations → Advanced: other calculation tools → Distance scans and bonding", True, {
    "torq_dihedrals": "Specify only the coordinates the assigned scan operation genuinely supports; a field does not enable a new scan capability.",
    "torq_resolution": "Use the assigned sampling resolution and inspect which scan points actually compute.",
    "research_scan_method": "Use the assigned available scan method, consistent across every point.",
    "research_scan_basis": "Use the matching assigned basis at every scan point.",
    "research_scan_start": "Set the assigned initial mass-COM separation in ångströms for the rigid two-fragment route.",
    "research_scan_end": "Set the assigned final separation without treating the range as a validated minimum or barrier.",
    "research_scan_points": "Set the assigned bounded number of scan points; more points on one path do not make it a full PES.",
    "btn_research_torq": "Run the supported rigid separation scan and inspect computed, failed and uncomputed points.",
})
_controls("orbital_analysis", "Calculations → Advanced: other calculation tools → Distance scans and bonding orbital/bond analysis", True, {
    "research_orbital_backend": "Choose an actual available backend for the specifically named analysis.",
    "btn_research_nbo": "NBO requires a genuine compatible producer; an unavailable control is not replaced by Löwdin analysis.",
    "btn_research_wiberg": "Calculate AO Löwdin Wiberg indices from qualified electronic data and retain that exact convention.",
    "btn_research_wiberg_nao": "NAO Wiberg requires its own genuine producer; AO Löwdin indices do not satisfy this operation.",
})
_controls("compare_results", "Results → Advanced: compare structures and population models", True, {
    "research_energy_kind": "Choose one compatible recorded energy type; electronic energy and Gibbs free energy are not interchangeable.",
    "research_populations": "Request a population model only with the required qualified minima, conditions and comparable energies.",
    "research_isomer_choices": "Choose the calculated structures you actually intend to compare, checking their scientific compatibility.",
    "btn_research_compare": "Compare the selected compatible observations and retain the resulting table, figure and limitations.",
    "btn_research_clear_selection": "Clear which results are selected for comparison; saved calculations and files remain intact.",
    "research_temperature": "Use the scientifically intended temperature in kelvin when the operation requires it.",
    "research_result_temperature": "Use the temperature associated with the qualified free-energy comparison or population model.",
    "torq_qrrho": "Apply a low-frequency thermochemical treatment only as the protocol specifies; it does not qualify an unverified minimum.",
})
_controls("software_modules", "Results → advanced validated module handoff", True, {
    "module_recipient": "Select the intended scientific module and check its actual available operations.",
    "module_artifact": "Choose a valid retained input for this particular handoff, preserving its original identity.",
    "module_operation": "Specify only an operation the installed recipient genuinely advertises and supports.",
    "module_output": "Advanced package storage is a managed directory, not evidence that the recipient ran chemistry.",
    "btn_module_handoff": "Prepare a validated data handoff; its success does not certify recipient execution.",
    "btn_module_refresh": "Read installed module and operation availability before attempting the task.",
    "module_root": "Advanced module storage identifies managed installed components; do not select an arbitrary checkout to bypass verification.",
    "btn_module_install": "Let BASE install and verify the selected approved component; students do not manually clone module repositories.",
    "btn_module_run": "Run only the specifically available validated operation and inspect its actual result status.",
})
_controls("periodic", "Periodic structures", True, {
    "periodic_input_path": "Select the intended periodic input and verify its cell, composition and coordinate units.",
    "periodic_settings_path": "Select the assigned explicit PAW/settings record matching this periodic structure.",
    "periodic_output_path": "Advanced periodic result storage is on the calculation computer; retain its request and source identity.",
    "btn_periodic_inspect": "Validate the selected periodic input; validation is separate from running an SCF calculation.",
    "btn_periodic_save": "Save the supported typed periodic request after checking settings; saving is not execution.",
    "btn_periodic_run": "Run the supported bounded PBE/PAW single-point SCF operation, not an unimplemented cell or gap calculation.",
    "btn_periodic_cancel": "Request stopping this periodic calculation and retain its observed final or partial status.",
})
_controls("periodic_settings", "More scientific tools → Periodic structures → PAW settings", True, {
    "paw_input_upload": "Upload the actual approved element-specific PAW files; a filename alone does not establish compatibility.",
    "paw_ecutwfc": "Use the assigned wavefunction cutoff in Ry and the required convergence study.",
    "paw_ecutrho": "Use the compatible assigned density cutoff in Ry; do not infer it from a different file's defaults.",
    "paw_scf_tolerance": "Use the assigned SCF energy tolerance in Ry and inspect achieved convergence afterward.",
    "paw_scf_steps": "Bound SCF iterations; reaching the maximum is not a successful-convergence certificate.",
})
_controls("hpc", "Calculations → configured HPC route", True, {
    "scheduler_input": "Choose only the scheduler actually configured for your institution's connection.",
    "partition_input": "Use the real queue/partition supplied by the instructor or cluster administrator.",
    "nodes_input": "Respect the currently supported node count; a disabled field is not a hidden distributed-computing capability.",
    "tasks_per_node_input": "Use the assigned number of processor tasks within the actual allocation.",
    "mem_input": "Use the institution's permitted memory request and check its units and total/per-task meaning.",
    "walltime_input": "Use the assigned scheduler walltime format and limit; a timeout preserves an incomplete result.",
    "job_name_input": "Choose a useful scheduler-job label while retaining the actual job identifier.",
    "email_input": "Use an appropriate notification address only when the configured cluster supports it.",
    "btn_slurm_submit": "Submit the reviewed job to the configured scheduler once, then retain its returned job ID.",
    "btn_hpc_connect": "Check the configured cluster connection; selecting HPC alone does not establish access.",
    "btn_hpc_refresh": "Refresh the particular retained scheduler job's observed status.",
    "btn_hpc_retrieve": "Retrieve outputs matched to the intended scheduler job and inspect their native outcome.",
    "btn_hpc_cancel": "Request cancellation of this scheduler job and confirm the observed stopped status.",
    "hpc_history": "Choose the particular retained HPC job rather than assuming the latest scheduler entry is the intended one.",
    "btn_hpc_open": "Open that retained HPC job's identity, request and result information.",
})

_controls("scientific_inputs", "Specialized tools → upload or choose retained input", True, {
    "install_input_upload": "Upload a genuine compatible Hessian bundle for the specialized check, not as an ordinary starting-geometry prerequisite.",
    "hessian_input_upload": "Upload the parent Hessian with its matching geometry and original calculation provenance.",
    "telemetry_input_upload": "Upload the actual supported native output from which calculated properties will be read.",
    "physical_data_input_upload": "Upload the genuine bounded numerical dataset with its source and units.",
    "periodic_input_upload": "Upload the intended unit-cell structure in a supported periodic format with explicit units.",
    "module_input_upload": "Upload a valid retained scientific input for the particular advanced module handoff.",
    "_input_selectors[*]": "Choose the retained input appropriate to this specialized tool; a selection from another tool is not automatically compatible.",
})
_controls("periodic_settings", "More scientific tools → Periodic structures → element files and k-grid", True, {
    "_paw_pseudopotential_choices[*]": "For this actual element, choose its approved compatible PAW file and retain the file's original identity.",
    "paw_kpoints[*]": "Use the assigned k-point sampling along each cell direction; sample convergence for the property of interest rather than assuming the displayed grid is sufficient.",
})
_controls("isotopes", "More scientific tools → Spectra and properties → Isotope effects", True, {
    "isotope_selectors[*]": "Choose the intended isotope for this specific atom, checking its position and the retained parent identity before reanalysis.",
})
_controls("charge_spin", "Advanced research → Check monomer charges and spins", True, {
    "_research_fragment_state_inputs[*]": "For each monomer, enter its own intended charge and multiplicity; the full complex's state is not automatically each fragment's state.",
})
_controls("first_calculation", "Header → four-step route", False, {
    "guided_step_buttons.install": "Open 1 · Setup to check access and program availability.",
    "guided_step_buttons.inputs": "Open 2 · Add your molecule to upload and select the intended structure.",
    "guided_step_buttons.matrix": "Open 3 · Run assigned calculation to review settings; navigation does not submit a job.",
    "guided_step_buttons.modules": "Open 4 · Read and save results to interpret and download retained output.",
})
_controls("help_navigation", "Help and optional-section controls", False, {
    "LearningHelp.search": "Search using your own words; this reads local explanations without changing the scientific settings or sending a job.",
    "LearningHelp.clear": "Clear the help question and close its explanations; inputs and calculations are unchanged.",
    "Disclosure.toggle": "Show or hide this optional section while retaining its current control values; opening it does not enable a missing scientific capability.",
    "context_help_buttons[*]": "Open the explanation beside this task; its What/Why/When/Where/How and individual-control hints do not alter the calculation.",
})
_controls("read_results", "Results → completed displayed result", False, {
    "result_summary_download": "Save displayed result summary downloads only the text currently shown after a completed result; it is not the native output, a full provenance archive or assignment submission.",
})


# Display labels are presentation descriptions, not executable attribute lookups.
_CONTROL_LABELS = {
    'result_summary_download': 'Save displayed result summary',
    'Disclosure.toggle': 'Show / Hide optional section',
    'LearningHelp.clear': 'Clear help',
    'LearningHelp.search': 'Help search:',
    '_input_selectors[*]': 'Choose a retained input for this tool',
    '_paw_pseudopotential_choices[*]': 'Each element’s PAW file',
    '_research_fragment_state_inputs[*]': 'Each monomer’s charge and multiplicity',
    'actions_calculated_geometry': 'Calculated geometry:',
    'actions_cores': 'Calculation cores:',
    'actions_history': 'Previous calculations:',
    'actions_memory': 'Memory per core (MB):',
    'actions_operation': 'Calculate:',
    'actions_timeout': 'Calculation timeout (s):',
    'artifact_output_path': 'Output Dir:',
    'bin_cfour': 'CFOUR Path:',
    'bin_orca': 'ORCA Path:',
    'btn_actions_open': 'Open selected calculation',
    'btn_actions_refresh': 'Refresh calculation status',
    'btn_actions_retrieve': 'Retrieve and inspect results / Retrieve calculation diagnostics',
    'btn_actions_use_geometry': 'Use calculated structure',
    'btn_assemble_monomers': 'Prepare complex starting seed',
    'btn_build_smiles': 'Build starting geometry',
    'btn_cancel': 'Cancel calculation',
    'btn_clear_hessian': 'Clear Hessian',
    'btn_clear_r2_attachment': 'Clear R2 reference',
    'btn_clear_read_attachment': 'Clear starting Hessian',
    'btn_continue_calculation_settings': 'Continue to calculation settings',
    'btn_continue_inputs': 'Continue to Your files',
    'btn_detect_bins': 'Find installed engines',
    'btn_detect_fragments': 'Auto-Detect Monomers',
    'btn_execute': 'Run selected calculation (label follows the selected task)',
    'btn_hpc_cancel': 'Cancel HPC job',
    'btn_hpc_connect': 'Check HPC connection',
    'btn_hpc_open': 'Open retained HPC job',
    'btn_hpc_refresh': 'Refresh HPC status',
    'btn_hpc_retrieve': 'Retrieve HPC results',
    'btn_inbox_scan': 'Import files from VS Code inbox',
    'btn_inbox_stop': 'Stop watching inbox',
    'btn_inbox_watch': 'Watch VS Code inbox',
    'btn_input_refresh': 'Refresh retained inputs',
    'btn_inputs': 'Your files',
    'btn_inspector': 'Spectra and properties',
    'btn_install': 'Start here',
    'btn_load_hessian': 'Load geometry and Hessian',
    'btn_matrix': 'Calculations',
    'btn_module_handoff': 'Prepare validated handoff',
    'btn_module_install': 'Install selected recipient',
    'btn_module_refresh': 'Refresh module availability',
    'btn_module_run': 'Run geometry analysis',
    'btn_modules': 'Results',
    'btn_parse_inspector': 'Read calculated properties',
    'btn_periodic': 'Periodic structures',
    'btn_periodic_cancel': 'Cancel periodic calculation',
    'btn_periodic_inspect': 'Validate periodic structure',
    'btn_periodic_run': 'Run periodic PBE/PAW single point',
    'btn_periodic_save': 'Save periodic calculation request',
    'btn_read_hdf5': 'Inspect HDF5 / NPZ data',
    'btn_refresh_wsl': 'Check WSL Status',
    'btn_remote_engine_cancel': 'Cancel check',
    'btn_remote_engine_check': 'Check ORCA & CFOUR',
    'btn_remove_geometry': 'Remove from list',
    'btn_remove_input': 'Remove from list',
    'btn_research_clear_selection': 'Clear comparison selection',
    'btn_research_compare': 'Compare calculated isomers',
    'btn_research_fragment_states': 'Check monomer charges and spins',
    'btn_research_nbo': 'Calculate NBO analysis',
    'btn_research_refresh': 'Check available calculations',
    'btn_research_topos': 'Start TOPOS calculation',
    'btn_research_torq': 'Start distance scan',
    'btn_research_wiberg': 'Calculate Löwdin Wiberg indices',
    'btn_research_wiberg_nao': 'Calculate NAO Wiberg indices',
    'btn_restore_input': 'Restore selected input',
    'btn_run_isotope_reanalysis': 'Re-analyze Isotopologue',
    'btn_save_bins': 'Use these executable paths',
    'btn_save_input_details': 'Save geometry details',
    'btn_save_matrix': 'Save configuration',
    'btn_setup_apply': 'Apply compatible updates',
    'btn_setup_restart': 'Restart interface',
    'btn_setup_retry': 'Retry setup',
    'btn_setup_rollback': 'Roll back update',
    'btn_setup_updates': 'Check for updates',
    'btn_sieve_inputs': 'Merge and sieve native conformer pools',
    'btn_slurm_submit': 'Submit Job',
    'btn_topos_cancel': 'Cancel conformer search',
    'btn_topos_promote': 'Publish conformer ensemble',
    'btn_topos_refresh': 'Refresh search engines',
    'btn_topos_submit': 'Start conformer search',
    'btn_undo_geometry_remove': 'Undo remove',
    'btn_undo_input_remove': 'Undo remove',
    'btn_use_input_geometry': 'Use selected starting geometry',
    'btn_use_unique_conformer': 'Use retained conformer geometry',
    'btn_validate_install_data': 'Validate scientific data',
    'calc_env_dropdown': 'Run calculations on:',
    'calculation_hessian_choice': 'Calculation Hessian:',
    'cb_recipe_r1': 'Freeze all monomer internals (bonds/angles/dihedrals)',
    'cb_recipe_r2': 'Recipe R2: reference monomers and intermolecular relaxation',
    'cfour_operation': 'CFOUR operation:',
    'charge_input': 'Total charge:',
    'context_help_buttons[*]': 'Help / Hide help beside a task',
    'course_access_panel.app_slug': "Instructor's App installation link:",
    'course_access_panel.btn_clear': 'Clear invitation',
    'course_access_panel.btn_refresh': 'Check granted access',
    'course_access_panel.btn_save': 'Save invitation',
    'course_access_panel.cfour': 'Request optional CFOUR access',
    'course_access_panel.controller': "Instructor's setup link:",
    'course_access_panel.orca': 'Request optional ORCA access',
    'course_access_panel.project': 'Current project:',
    'email_input': 'Email:',
    'fragment_preview': 'ORCA %geom:',
    'geometry_charge': 'Structure charge:',
    'geometry_multiplicity': 'Structure multiplicity:',
    'gh_branch_input': 'Project branch:',
    'gh_repo_input': 'GitHub project:',
    'guided_cancel': 'Stop current calculation',
    'guided_step_buttons.inputs': '2 · Add your molecule',
    'guided_step_buttons.install': '1 · Setup',
    'guided_step_buttons.matrix': '3 · Run assigned calculation',
    'guided_step_buttons.modules': '4 · Read and save results',
    'hessian_input_upload': 'Upload hessian',
    'hpc_history': 'HPC history:',
    'input_kind': 'File contents:',
    'input_library_choice': 'Your uploaded file:',
    'input_pool_basis': 'Recorded basis:',
    'input_pool_charge': 'Pool charge:',
    'input_pool_choices': 'Conformer pools:',
    'input_pool_declare_context': 'Declare common state and protocol for energy ranking',
    'input_pool_energy_unit': 'Recorded energy unit:',
    'input_pool_engine': 'Recorded engine:',
    'input_pool_method': 'Recorded method:',
    'input_pool_multiplicity': 'Pool multiplicity:',
    'input_pool_producer': 'Pool producer:',
    'input_pool_version': 'Engine / model version:',
    'input_record_choice': 'Structure / frame:',
    'input_unique_conformer': 'Retained conformer:',
    'input_upload': 'Upload scientific inputs',
    'inspector_file_input': 'Log / H5 File:',
    'install_data_path': 'Scientific data:',
    'install_input_upload': 'Upload Hessian bundle',
    'install_min_disk': 'Required disk (GB):',
    'interact_env_dropdown': 'Interface runs in:',
    'isotope_hessian_path': 'Hessian bundle:',
    'isotope_selectors[*]': 'Each atom’s isotope',
    'job_name_input': 'Job Name:',
    'license_mode': 'Optional engine check:',
    'live_preview': 'Run configuration:',
    'matrix_basis': 'Basis Set:',
    'matrix_cbs_pair': 'CBS pair:',
    'matrix_engine': 'Engine:',
    'matrix_geometry': 'Geometry (XYZ):',
    'matrix_method': 'Method:',
    'matrix_solvation': 'Surroundings:',
    'matrix_tier': 'Theory family:',
    'mem_input': 'Memory:',
    'module_artifact': 'Input artifact:',
    'module_input_upload': 'Upload module',
    'module_operation': 'Requested task:',
    'module_output': 'Package directory:',
    'module_recipient': 'Recipient module:',
    'module_root': 'Module storage:',
    'multiplicity_input': 'Spin multiplicity:',
    'native_operation': 'Calculate:',
    'native_timeout': 'Native timeout (s):',
    'nodes_input': 'Nodes:',
    'partition_input': 'Queue:',
    'paw_ecutrho': 'Density cutoff (Ry):',
    'paw_ecutwfc': 'Wavefunction cutoff (Ry):',
    'paw_input_upload': 'Upload PAW files',
    'paw_kpoints[*]': 'k-grid a / b / c',
    'paw_scf_steps': 'Maximum SCF steps:',
    'paw_scf_tolerance': 'SCF tolerance (Ry):',
    'periodic_input_path': 'Periodic input:',
    'periodic_input_upload': 'Upload periodic',
    'periodic_output_path': 'Periodic output:',
    'periodic_settings_path': 'PAW settings JSON:',
    'physical_data_input_upload': 'Upload physical data',
    'product_class_selector': 'Scientific goal:',
    'project_name': 'Calculation label:',
    'r2_reference_manifest': 'R2 reference manifest:',
    'removed_input_choice': 'Removed input:',
    'research_candidates': 'Starting candidates:',
    'research_energy_kind': 'Energy to compare:',
    'research_isomer_choices': 'Calculated structures:',
    'research_matrix_recipe': 'Predefined method:',
    'research_orbital_backend': 'NBO / NAO program:',
    'research_populations': 'Include a population model',
    'research_result_temperature': 'Temperature (K):',
    'research_scan_basis': 'Basis set:',
    'research_scan_end': 'End distance (Å):',
    'research_scan_method': 'Method:',
    'research_scan_points': 'Number of points:',
    'research_scan_start': 'Start distance (Å):',
    'research_temperature': 'Temperature (K):',
    'research_topos_engine': 'Method:',
    'research_topos_operation': 'Calculation:',
    'run_install_btn': 'Run Installation / Review Actions setup',
    'scheduler_input': 'Scheduler:',
    'scientific_initial_hessian': 'Initial Hessian:',
    'scientific_r2_upload': 'Upload R2 references',
    'scientific_read_upload': 'Upload READ Hessian',
    'smiles_input': 'Name or SMILES:',
    'student_fragment_atoms': 'Fragment atom groups:',
    'student_geometry_choice': 'Starting geometry:',
    'student_input_label': 'Geometry label:',
    'student_input_role': 'Input type:',
    'student_monomer_choices': 'Your monomers:',
    'student_seed_separation': 'Seed separation (Å):',
    't9_basis': 'Recovery basis:',
    't9_config_path': 'T9 active-space JSON:',
    't9_electrons': 'Active electrons:',
    't9_enable': 'Enable explicit T9 spin-contamination recovery',
    't9_method': 'Recovery method:',
    't9_orbitals': 'Active MO indices:',
    't9_rationale': 'Active-space rationale:',
    'tasks_per_node_input': 'Tasks/Node:',
    'telemetry_input_upload': 'Upload telemetry',
    'topos_dedup': 'Dedup Tol:',
    'topos_heuristic': 'Search protocol:',
    'topos_walltime': 'Search limit (min):',
    'torq_dihedrals': 'Active Dihedrals:',
    'torq_qrrho': 'Enable qRRHO',
    'torq_resolution': 'Scan Res:',
    'unphysical_override': 'Dispersion safeguards are required',
    'walltime_input': 'Walltime:',
    'xyz_upload': 'Upload .xyz',
}

for _control_id, _guidance in CONTROL_HELP.items():
    _guidance["label"] = _CONTROL_LABELS[_control_id]


def _extra_guidance(topic, location, kind, entries):
    _controls(topic, location, kind != "navigation", {key: value[1] for key, value in entries.items()})
    for key, (label, _) in entries.items():
        CONTROL_HELP[key].update(label=label, kind=kind)


_extra_guidance("help_navigation", "Navigation / Help", "navigation", {
    "btn_terms": ("Scientific terms", "Open local help; no engine, account or calculation submission is required."),
    "build_glossary.search": ("Scientific-terms search", "Filter the local terminology explanations; this does not change a calculation or contact an online model."),
})
_extra_guidance("first_calculation", "Task navigation", "navigation", {
    "btn_goal_periodic": ("Open periodic-structure calculations", "Open the separate periodic tools for an assigned unit-cell question; this navigation does not execute a material calculation."),
    "navigation_buttons[*]": ("Continue / open a named scientific tool", "Open the page or tool named on this navigation button. This changes the displayed panel, not scientific parameters or job status."),
})
_extra_guidance("lab_access", "Start here → instructor invitation", "read_only_status", {
    "course_access_panel.links": ("Authorize lab app / Request project access links", "Follow the supplied authorization and owner-authored request links for this project; opening a link is not confirmed provisioning."),
    "course_access_panel.status": ("Invitation and project-access status", "Read this project's actual access result and error. A setup receipt is not a completed calculation or a grant of unlimited usage."),
    "gh_guidance": ("Remote setup guidance", "Follow the specific project setup prerequisite; preserve a failed request's link rather than entering credentials into help."),
})
_extra_guidance("engine_setup", "Start here → program status", "read_only_status", {
    "remote_engine_status": ("Remote ORCA/CFOUR access result", "Read each engine's own checked state; available archive access does not establish engine execution or numerical acceptance."),
    "licensed_engine_status": ("Local optional-engine status", "Read which locally audited engines are available and why a dependent operation is disabled."),
    "local_setup_output": ("Local setup report", "Read the installation/discovery result and its specific error; a process starting is not proof a scientific operation completed."),
    "wsl_status_html": ("Windows/WSL status", "Read the actual host observation before selecting a compatible local execution route."),
    "install_data_status": ("Specialized scientific-bundle validation", "Read whether this supplied bundle passed its specific checks; it is not a newly computed Hessian."),
})
_extra_guidance("workspace", "Header / Start here", "read_only_status", {
    "header_status": ("Overall interface status", "Read the observed interface status, then check the particular request's outcome before calling a calculation successful."),
    "header_env": ("Interface environment", "This readout identifies where the interface runs; the chosen calculation computer can be different."),
    "calculation_environment_status": ("Calculation environment", "Confirm where this request will run and which route-specific checks apply."),
    "footer_message": ("Interface message", "Read the message and its named recovery step; an alert is not resolved by hiding it."),
})
_extra_guidance("job_status", "Calculations → observed request status", "read_only_status", {
    "actions_status": ("Actions calculation status", "Follow the selected request/run through waiting, running and its observed terminal outcome; a workflow conclusion alone is not scientific qualification."),
    "execution_description": ("Current execution description", "Read the selected operation and route before submission; this description does not itself execute it."),
    "telemetry_html": ("Calculation telemetry", "Read the actual recorded observations with units and their job identity. Missing measurements must remain missing."),
})
_extra_guidance("retrieve_results", "Calculations → request-bound downloads", "download_link", {
    "actions_results_download": ("Download calculation bundle", "Save the available bundle matched to this request/run, keeping its raw results, warnings and provenance."),
    "actions_job_download": ("Saved request/configuration download", "Read what this download contains: a request/configuration is separate from the result of executed chemistry."),
})
_extra_guidance("read_results", "Calculations / Results", "read_only_data", {
    "calculation_result": ("Displayed calculation result", "Check the actual operation, values, units, convergence and warnings. The displayed summary is only part of the scientific record."),
    "research_report_output": ("Calculated research report", "Read the report's actual quantity, source and qualifications; a supplied or derived value is not automatically a fresh engine result."),
    "research_report_download": ("Report figure/table downloads", "Save the available matching report data with its figures; this is separate from a complete native-result backup and assignment submission."),
})
_extra_guidance("scientific_inputs", "Your files", "read_only_status", {
    "input_library_status": ("Scientific-input import status", "Read which original was admitted and which reader handled it; upload acceptance is not physical validation of a minimum."),
    "input_library_rejections": ("Rejected input details", "Read the actionable file/record error; keep the original and earlier valid inputs when correcting it."),
    "student_upload_status": ("Starting-geometry status", "Confirm the selected geometry was retained. Inspect its picture in Calculations after using it as the starting geometry."),
    "input_library_table": ("Retained file details and hashes", "Read filenames, types and recorded source hashes to identify originals; this table is not a new calculation or an original-file download control."),
})
_extra_guidance("data_preservation", "Your files → list management", "read_only_status", {
    "input_management_status": ("Remove/restore status", "Read which list item changed and whether it was restored; this status does not certify erasure from every storage location."),
})
_extra_guidance("conformer_pools", "Your files → conformer ensembles", "read_only_status", {
    "input_pool_status": ("Conformer-pool merge status", "Read the retained candidates, exclusions and missing metadata; successful duplicate processing is not an equilibrium-population certificate."),
})
_extra_guidance("updates", "Start here → CoChem tools and updates", "read_only_status", {
    "student_setup_status": ("Managed setup/update status", "Read the actual installed/update/restart state and error. A requested or disabled action is not a completed restart."),
})
_extra_guidance("method_basis", "Calculations → method settings", "read_only_status", {
    "engine_warning": ("Engine/method warning", "Read why the selected combination is unavailable or needs attention; do not substitute a different method without scientific guidance."),
    "dispersion_warning": ("Dispersion warning", "Preserve the required dispersion checks; a warning is not permission to add a correction twice."),
    "mlff_warning": ("Screening-model limitations", "A screening or machine-learned starting guess does not establish a precision spectroscopic or binding prediction."),
    "tier_help": ("Theory-family explanation", "Read the model's intended scope and cost; a higher tier number is not proof of accuracy."),
})
_extra_guidance("theory_tiers", "Header / advanced scientific goal", "read_only_data", {
    "product_class_card": ("Selected scientific goal and requirements", "Read the actual selected goal's requirements. A goal label sets obligations; it does not certify the current result meets them."),
})
_extra_guidance("molecule_identity", "Calculations → Starting structure", "read_only_data", {
    "viewer_output": ("3D view of the selected structure", "Inspect the selected atoms after using the input as the starting geometry; view rotation changes the picture, not stereochemical identity or electronic results."),
})
_extra_guidance("fragments_constraints", "Calculations → advanced Monomer constraints", "read_only_data", {
    "fragments_output": ("Fragment/constraint report", "Check the atom partition and recorded constraints against the intended chemistry; geometric detection is not chemical proof."),
    "scientific_input_status": ("Reference/Hessian attachment status", "Check the selected genuine reference and its compatibility; a matching filename is not sufficient provenance."),
})
_extra_guidance("active_space", "Calculations → advanced T9 recovery", "read_only_status", {
    "t9_guidance": ("Active-space recovery guidance", "Read the exact required electronic-state and operation limits; a warning does not specify a unique active space."),
})
_extra_guidance("provenance", "Calculations → advanced reproducibility output", "read_only_data", {
    "matrix_output": ("Saved calculation configuration", "Confirm the recorded settings correspond to the intended draft; saving them does not run chemistry."),
    "output_destination_guidance": ("Managed result storage", "Read where this route retains output; computer-side storage is separate from a download onto your own device."),
})
_extra_guidance("hpc", "Configured HPC route", "read_only_status", {
    "slurm_status_output": ("Scheduler submission/status", "Follow the actual scheduler job ID; a prepared request is not a physical cluster run."),
    "hpc_connection_status": ("HPC connection result", "Read the specific institution connection check; a selected scheduler does not supply access."),
    "hpc_results_download": ("HPC result download", "Save only outputs matched to the intended scheduler request and inspect their native outcome."),
})
_extra_guidance("spectroscopy", "More scientific tools → Spectra and properties", "read_only_data", {
    "inspector_banner": ("Equilibrium versus ground-state constants", "Compare like quantities: equilibrium Ae/Be/Ce describe a geometry; A0/B0/C0 also reflect nuclear motion. This explanation does not certify a selected result."),
    "inspector_rot_table": ("Rotational constants table", "Distinguish equilibrium Ae/Be/Ce from ground-state A0/B0/C0 and retain the units and scientific qualification."),
    "hdf5_results_table": ("Supplied HDF5/NPZ data", "Read the bounded supplied numerical values with source and units; absent data is not an invented successful result."),
})
_extra_guidance("isotopes", "More scientific tools → Spectra and properties → Isotope effects", "read_only_data", {
    "isotope_hessian_status": ("Parent-Hessian identity", "Check the actual selected parent geometry, Hessian, atom order and hash before isotope analysis."),
    "isotope_results_table": ("Isotope reanalysis table", "Read the new harmonic mass-reanalysis values and their retained parent source; this is not a fresh electronic calculation."),
    "isotope_modes_plot": ("Isotope mode plot", "Read axes, units and parent/substituted identities; a plotted harmonic mode is not an experimental peak assignment."),
})
_extra_guidance("software_modules", "Advanced validated module tools", "read_only_status", {
    "module_capabilities": ("Module capability report", "Read which installed operation is genuinely available; module discovery is not scientific execution."),
    "module_handoff_status": ("Validated handoff status", "Read whether the data package was accepted; this does not certify recipient execution."),
    "module_install_status": ("Module installation status", "Read the reviewed component's actual installation and integrity outcome; it does not validate every method."),
})
_extra_guidance("periodic", "More scientific tools → Periodic structures", "read_only_status", {
    "periodic_structure_status": ("Periodic structure validation", "Check the admitted cell/composition/units and remaining PAW prerequisites; input validation is not an SCF or material-accuracy result."),
})
_extra_guidance("conformer_search", "Advanced structures and energies tools", "read_only_status", {
    "topos_status": ("Advanced native search status", "Read the actual native conformer-search stage and any incomplete or cancelled outcome."),
    "topos_capabilities": ("Advanced native search availability", "Read which genuine search engines can be used for this bounded protocol."),
    "topos_results": ("Native search candidates", "Inspect retained candidate structures and actual observations; candidate retention does not qualify minima or populations."),
    "research_capabilities": ("Available research calculations", "Read the operation-specific provider gate; a missing scientific producer cannot be supplied by a help explanation."),
    "research_matrix_guidance": ("Predefined method explanation", "Read the actual complete assigned method combination and its scope before choosing it."),
    "research_status": ("Research calculation status", "Read the particular research job's observed result and retained warnings before interpreting its table or curve."),
})
_extra_guidance("orbital_analysis", "Advanced distance scans and bonding → Bond analysis", "read_only_status", {
    "research_bond_capability": ("Bond-analysis availability", "Read why NBO, NAO or Löwdin analysis is unavailable; these names describe different conventions and cannot substitute for each other."),
})
_extra_guidance("compare_results", "Results → advanced structure comparison", "read_only_status", {
    "research_comparison_status": ("Comparison status", "Read which selected compatible energy observations were compared and which requirements or values remain missing."),
})


# These objects remain in the controller source but are replaced, hidden, or
# used only as private path bindings by the current student presentation.
# Inventorying them must never imply a student can find or use them as controls.
_SOURCE_RETAINED_NOT_DISPLAYED = {
    "torq_dihedrals": "The retained legacy dihedral field is not shown. The current TORQ tool offers its explicitly supported rigid distance scan, not an enabled torsion scan.",
    "torq_resolution": "The retained legacy resolution field is not shown. Use Number of points in the supported Distance scan form.",
    "torq_qrrho": "The retained legacy qRRHO checkbox is not shown and does not enable a qualified thermochemistry producer.",
    "topos_dedup": "This retained duplicate-tolerance widget is not displayed. BASE's scientific duplicate safeguards remain enforced; this is not a control for loosening them.",
    "unphysical_override": "This retained safeguard display is not shown and is not a user override. Required dispersion checks cannot be bypassed here.",
    "artifact_output_path": "The direct output-path field is hidden in the student presentation. Use available managed-result downloads; a hidden path is not a required student input.",
    "install_data_path": "This internal path binding is replaced by a retained-input chooser in the student presentation. Ordinary starting geometry does not require a Hessian.",
    "isotope_hessian_path": "This internal path binding is replaced by the retained Hessian chooser. Select the matching original rather than typing a filesystem path.",
    "inspector_file_input": "This internal path binding is replaced by native-output/retained-data choosers. Select the appropriate supported original file.",
    "periodic_input_path": "This internal path binding is replaced by the periodic file upload/chooser. Validate the selected cell and coordinate units.",
    "periodic_settings_path": "This old settings-path field is not the current student entry route. Use the explicit element-file, cutoff, k-grid and SCF controls.",
    "periodic_output_path": "This internal output path is not a required student control. Read the actual request/result and use its available managed download links.",
    "module_artifact": "This internal path binding is replaced by the advanced validated-module input chooser.",
    "module_root": "This internal storage field is not shown. BASE manages verified module storage; no manual module checkout path is needed.",
    "module_operation": "This internal operation-path field is not shown. Use only an actual available recipient operation; no hidden field enables a missing provider.",
    "module_output": "This internal package-output path is not shown. A handoff package is separate from proof of recipient execution.",
}
for _control_id, _explanation in _SOURCE_RETAINED_NOT_DISPLAYED.items():
    CONTROL_HELP[_control_id].update(
        hint=_explanation,
        location="Not displayed as a control in the current student layout; see the supported tool described in this topic.",
        visibility="source_retained_not_displayed",
    )


for _control_id in ('topos_heuristic', 'topos_walltime', 'btn_topos_refresh', 'btn_topos_submit', 'btn_topos_cancel', 'btn_topos_promote'):
    CONTROL_HELP[_control_id]["location"] = "Calculations → Advanced: other calculation tools → Other structures and energies → Advanced native conformer search"


for _control_id, _guidance in CONTROL_HELP.items():
    _guidance.setdefault("kind", "dynamic_family" if "*" in _control_id else "interactive_attribute")
    _guidance.setdefault("visibility", "conditional_or_current; verify actual rendered tree")


for _topic_id, _content in HELP_CONTENT.items():
    _content["controls"] = tuple(control for control, entry in CONTROL_HELP.items()
                                 if entry["topic"] == _topic_id)
