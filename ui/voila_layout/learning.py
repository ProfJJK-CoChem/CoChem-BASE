"""Offline, contextual scientific guidance for the BASE interface.

The text explains choices; it never selects parameters or certifies calculations.
Scientific scope follows SRS Chunk 17 plus proposal additions, the GUI charter
and wireframe, CoChem_User_Manual chapters 1–4 and 6, and Method_Matrix sections
9A and 20. Keep required instructions in hints; disclosures supply explanation.
"""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re
import unicodedata
from collections.abc import Iterable

import ipywidgets as widgets

from .help_content import CONTROL_HELP, HELP_CONTENT


@dataclass(frozen=True)
class _Guidance:
    hint: str
    question: str
    paragraphs: tuple[str, ...]


_HELP = {
    "workspace": _Guidance(
        "Choose where calculations will run, then check that environment's available engines before choosing a method.",
        "where my interface and calculations run",
        (
            "Codespaces is the computer that opens this interface in your browser or VS Code. GitHub Actions runs a calculation on a separate computer and returns its results. An engine available in one place is not necessarily available in the other.",
            "Choose GitHub Actions for the course's remote calculation route. Local uses the computer running BASE, which may itself be a Codespace rather than your laptop. HPC uses an institution's configured computing cluster, where jobs can wait in a queue before running.",
            "ORCA and CFOUR are optional, strongly recommended engines. Check their availability in the selected calculation environment. A successful access check confirms access; only a completed calculation establishes that a particular method ran successfully.",
        ),
    ),
    "scientific_inputs": _Guidance(
        "Select the input type and inspect the imported structure or data before using it in a calculation.",
        "which research inputs I can use",
        (
            "Molecular inputs include XYZ, MOL, SDF, MOL2 and PDB files, including supported multi-frame structures. Names or SMILES can generate starting geometries. You can supply monomers, complete complexes or other molecular structures; inspect the result because a generated geometry is only a starting guess.",
            "Other routes accept CREST/GOAT conformer pools with declared energy units, periodic CIF or supported structure JSON, geometry-bound Hessian files, native calculation or spectroscopy outputs, HDF5 trajectories, physical HDF5/NPZ arrays and PAW pseudopotentials. Each route checks its own required contents; a file extension alone does not establish validity.",
            "Original files are retained. Choose the intended frame, verify atom order and isotope labels, and supply charge, spin and fragments where needed. XYZ coordinates are in ångströms. Importing an energy or structure does not establish convergence or a minimum.",
        ),
    ),
    "charge_spin": _Guidance(
        "Enter the total charge and spin state of the whole selected structure; verify each fragment separately when required.",
        "charge and spin multiplicity",
        (
            "Charge counts electrons removed or added relative to the neutral atoms: +1 means one electron removed; −1 means one added. For a complex, use the total charge of all its components. Ordinary XYZ files do not reliably specify this information.",
            "Spin multiplicity is 2S + 1, where S is total electron spin. A singlet has multiplicity 1; a doublet has 2; a triplet has 3. Neutral water in its ground state is a singlet, but neutral oxygen in its ground state is a triplet: neutral does not mean singlet.",
            "Check electron count and the chemically intended state with your instructor when unsure. A compatible electron count does not identify the correct ground state. Review spin diagnostics after unrestricted calculations; successful convergence alone does not establish the intended spin state.",
        ),
    ),
    "method_basis": _Guidance(
        "Use the method and basis specified for your scientific question, and keep them consistent across structures you compare.",
        "methods, basis sets and dispersion",
        (
            "The method approximates how electrons behave. Hartree–Fock (HF) includes exchange but omits electron correlation. Density functional theory (DFT) uses approximate exchange and correlation functionals; different functionals can give different answers. Neither name alone specifies a complete calculation.",
            "A basis set supplies functions used to describe the electrons. Larger sets usually cost more and require convergence checks; they do not repair an unsuitable method. HF/STO-3G is useful for a small setup exercise, not validation of weak binding.",
            "Dispersion is important for van der Waals complexes. Some methods need a matching correction such as D4; others already include dispersion. Do not add D3/D4 to ωB97M-V or add corrections again to a composite method such as r²SCAN-3c. Check the saved method, basis and correction in the result.",
        ),
    ),
    "theory_tiers": _Guidance(
        "Treat the tier as a method family and cost guide; follow your assignment's method and check the actual result.",
        "the T0–T9 method tiers",
        (
            "Tiers group approaches: T0 covers force-field and machine-learned screening; T1 semiempirical methods; T2 minimal-basis HF; T3–T5 DFT families; T6 perturbation methods such as MP2; T7 local coupled cluster; T8 canonical coupled cluster; and T9 multireference methods such as CASSCF/NEVPT2.",
            "A higher number is not an accuracy guarantee. T9 addresses electronic states that need several configurations; it is not a universal upgrade and requires a justified active space. A screening geometry usually needs further refinement before a precision comparison.",
            "A tier is also not a promised runtime. Atom count, basis size, method, requested properties and available hardware all matter. Screening, periodic materials and precision spectroscopy have different requirements. Record the method actually executed and review any restriction or change reported for your job.",
        ),
    ),
    "solvent": _Guidance(
        "Choose gas phase or the intended solvent consistently for all structures in a comparison.",
        "gas phase and solvent models",
        (
            "Gas phase treats the molecule without a surrounding solvent model. Use it when that matches the experiment or assignment, such as an isolated molecular complex. A solution-phase question needs an explicitly chosen solvent treatment.",
            "Continuum models such as CPCM or SMD represent the surrounding liquid through averaged properties. They do not place individual solvent molecules around your structure. Adding explicit solvent molecules changes the system you calculate and requires a justified sampling strategy.",
            "Keep the solvent and model consistent when comparing energies. Check the saved input and output to confirm the intended treatment actually ran. Solvation energy alone is not a complete solution free energy: temperature, molecular motion and the concentration or pressure standard state also affect thermodynamic comparisons.",
        ),
    ),
    "calculation_types": _Guidance(
        "Choose the calculation that answers your question; an energy calculation alone does not optimize or validate a structure.",
        "energy, optimization, frequency and scan calculations",
        (
            "A single-point energy evaluates the supplied geometry without moving its nuclei. Geometry optimization changes allowed coordinates to find a nearby stationary structure. It depends on the starting geometry and does not prove that the lowest-energy isomer has been found.",
            "A frequency calculation examines curvature around a geometry. It helps classify a stationary point and provides harmonic vibrational information. Optimization plus frequencies is a common sequence when checking a proposed minimum.",
            "A scan evaluates a sequence of coordinate values. In a relaxed scan, other allowed coordinates can optimize; in a rigid scan they stay fixed. A scan maximum is not automatically a transition state. Conformer searches explore alternative structures. Run only operations supported by the selected engine and inspect their convergence and limitations before drawing conclusions.",
        ),
    ),
    "convergence_frequencies": _Guidance(
        "Check energy, gradient and geometry convergence, then inspect vibrational modes before treating a structure as a minimum.",
        "whether a calculation has reached a meaningful structure",
        (
            "Convergence means the calculation met specified numerical stopping criteria. Electronic convergence and geometry convergence are separate. A normal program exit or a small energy change alone does not establish that atomic forces and displacements are sufficiently small.",
            "At an unconstrained local minimum, vibrational modes should have positive curvature after overall translation and rotation are removed. An imaginary frequency signals negative curvature; inspect the associated motion. A small imaginary value can also reflect numerical issues, incomplete optimization or a very shallow surface.",
            "Weak complexes need particular care because intermolecular motions are soft. Review thresholds and numerical grids, and repeat a justified refinement when needed. A constrained minimum only minimizes the coordinates allowed to move. Harmonic frequencies approximate motion near one geometry; they do not automatically capture large-amplitude or anharmonic behavior.",
        ),
    ),
    "fragments_constraints": _Guidance(
        "Check which atoms belong to each monomer before using frozen-monomer recipes or interaction-energy calculations.",
        "fragments and frozen-monomer recipes R1 and R2",
        (
            "A fragment is a chemically meaningful component, such as one water molecule in a water dimer. Verify the atom numbers and each fragment's charge and spin. Distance-based bond detection can misidentify unusual geometries; it is not chemical proof of fragment membership.",
            "Frozen-monomer recipes keep internal bond lengths, bond angles and dihedral angles fixed while allowing the components' relative positions and orientations to change. R1 provides an initial constrained optimization. R2 uses higher-level monomer references and stricter production requirements; the reference source and atom mapping must match your system.",
            "These constraints change the question being solved. A constrained optimum is not necessarily a fully relaxed minimum, especially if binding deforms a monomer. Inspect residual forces on fixed coordinates and the recorded constraints. Counterpoise calculations address basis sharing between fragments; they do not establish a full binding free energy.",
        ),
    ),
    "hessian": _Guidance(
        "Use a saved Hessian only with its matching geometry, atom order, units and calculation record.",
        "a Hessian and when I can reuse it",
        (
            "A Hessian describes local energy curvature: it is a matrix of second derivatives with respect to atomic coordinates. Optimizers can use approximate starting curvature to choose steps. Frequency analysis needs appropriately calculated curvature at the geometry being analyzed.",
            "A model starting Hessian, such as XTB2 or Lindh, is not a measured vibrational spectrum. Reusing a compatible previous Hessian can help an optimization, but a file with the right dimensions alone is insufficient. Verify geometry, atom order, coordinate frame, units and calculation provenance.",
            "Use the dedicated starting-Hessian control only when your protocol requires reuse. For isotope analysis, use a qualified Cartesian harmonic Hessian with its original molecular geometry and recorded method. A Hessian from another structure or an incompatible coordinate convention can produce plausible-looking but incorrect frequencies.",
        ),
    ),
    "active_space": _Guidance(
        "Choose active electrons and orbitals from a justified chemical model; do not guess them to clear a spin warning.",
        "the active space for CASSCF and NEVPT2",
        (
            "Some electronic states cannot be described well by a single dominant electron configuration. CASSCF treats several arrangements within a selected set of orbitals. Its active space specifies the number of electrons and orbitals included in that treatment.",
            "For example, CAS(2,2) means two electrons distributed among two active orbitals. It can describe selected bond-breaking problems, but the numbers alone do not identify which orbitals are chemically relevant. A larger active space costs more and is not automatically an appropriate choice.",
            "Use a literature protocol or an instructor-reviewed orbital selection for your system. Check occupations, state character and consistency across compared structures. NEVPT2 adds correlation to a CASSCF reference; it does not repair a poorly chosen active space. A spin warning identifies a problem to investigate, not a unique replacement calculation.",
        ),
    ),
    "isotopes": _Guidance(
        "Keep isotope labels attached to the correct atoms and distinguish harmonic mass substitution from anharmonic predictions.",
        "what changes when I substitute an isotope",
        (
            "Isotopes have the same element and different neutron counts, such as carbon-12 and carbon-13. The nuclear mass changes. Within the usual Born–Oppenheimer approximation, changing the isotope does not change the electronic potential energy surface at a fixed geometry.",
            "A compatible Cartesian harmonic Hessian can be reanalyzed with different isotope masses without recalculating electronic energies. The changed masses alter harmonic frequencies and rotational constants. Verify atom indices, retained labels such as 13C, and the mass source before interpreting differences.",
            "This harmonic reuse does not supply a new anharmonic force field or all isotope-dependent vibrational corrections. Equilibrium rotational constants describe the geometry; measured ground-state constants include nuclear motion. Compare like quantities and retain the parent Hessian, original geometry and isotope substitutions with your report.",
        ),
    ),
    "periodic": _Guidance(
        "Verify the unit cell, atomic positions and element-specific pseudopotentials before submitting a periodic calculation.",
        "periodic structures and their numerical settings",
        (
            "A periodic calculation repeats a unit cell to represent an extended material. The cell vectors, atomic positions and units all matter; an isolated molecule placed in a cell is not automatically a model of the intended solid. Disordered or partially occupied structures need an explicit, justified model.",
            "Plane-wave settings use an energy cutoff to control the electronic basis and a k-point mesh to sample the repeating solid. PAW pseudopotential files supply element-specific information. Match their functional and recommendations to the selected calculation, then check convergence of the property you need.",
            "Use only the cell, spin and other capabilities currently available in the selected adapter. A completed energy calculation does not establish a converged band gap or optimized lattice. Compare results at consistent settings and retain the exact cell and pseudopotential identities.",
        ),
    ),
    "compare_results": _Guidance(
        "Compare consistent quantities and conditions; electronic energy differences alone are not equilibrium populations.",
        "energy differences, free energies and populations",
        (
            "The reported electronic energy E is the fixed-nuclei energy, including nuclear repulsion but excluding nuclear motion. Gibbs free energy G also includes temperature-dependent contributions and a standard state. A zero-point correction alone does not convert E into G.",
            "For isomer comparisons, use the same composition, method, basis, solvent and correction scheme. For binding or reactions, use a balanced combination of species and state whether monomer deformation and counterpoise corrections are included. Do not compare unrelated absolute energies as stability rankings.",
            "Equilibrium populations require consistent free energies, temperature and degeneracies; low-frequency motions can strongly affect the result. State the pressure or concentration standard state and low-frequency treatment. A population estimate also assumes interconversion can reach equilibrium: barriers or experimental preparation can produce different observed abundances. Preserve missing values as missing instead of treating them as zero.",
        ),
    ),
    "provenance": _Guidance(
        "Keep original inputs, calculation settings, convergence records and downloaded results together so your work can be checked.",
        "the calculation record and file checksums",
        (
            "Provenance means the record of where a result came from. For a calculation, retain the original structure, charge, spin, method, basis, solvent, constraints, engine version and numerical settings. Record the temperature and standard state for thermodynamic results.",
            "A run identifier connects the request to its outputs. A file checksum, such as SHA-256, detects changed bytes. These help establish which files were used and whether the retrieved files match; they do not prove that the chemistry or chosen approximation is correct.",
            "Before reporting a number, inspect convergence, warnings, units and the quantity's meaning. Keep raw outputs as well as plots and tables. If a calculation fails, retain its diagnostic record and original input so a corrected run can be compared without rewriting the earlier evidence.",
        ),
    ),
}

HELP_TOPICS = tuple(_HELP)


_PROGRESS_LABELS = {
    "prepared": "request prepared; submission not yet confirmed",
    "submitted": "submission recorded",
    "awaiting_workflow": "waiting for GitHub to start the job",
    "dispatch_unconfirmed": "waiting for GitHub to confirm submission",
    "dispatching": "request received; waiting for the run to appear",
    "queued": "queued; waiting to run",
    "requested": "requested",
    "waiting": "waiting",
    "pending": "pending",
    "in_progress": "running",
    "completed": "completed",
    "rejected": "not accepted by GitHub",
    "success": "successful",
    "failure": "failed",
    "neutral": "finished without a success or failure result",
    "cancelled": "cancelled",
    "cancellation_requested": "cancellation requested; waiting for GitHub",
    "skipped": "not run",
    "timed_out": "stopped at the time limit",
    "action_required": "needs your attention on GitHub",
    "stale": "no longer current",
    "startup_failure": "the calculation computer could not start the job",
    "updates_available": "compatible updates are available",
    "current": "no compatible update is available",
    "applied": "update installed",
    "rolled_back": "previous version restored",
    "restart_requested": "interface restart requested",
    "complete": "complete",
}


def progress_label(code: str) -> str:
    """Explain an observed protocol state without inferring success or changing it."""
    return _PROGRESS_LABELS.get(str(code), "status not recognized; check details")


def hint_html(topic: str) -> str:
    """Return the essential instruction as visible, escaped text."""
    return f'<p class="cochem-hint">{escape(_HELP[topic].hint)}</p>'


def help_html(topic: str) -> str:
    """Return one closed native disclosure; every authored text value is escaped."""
    guidance = _HELP[topic]
    paragraphs = "".join(f"<p>{escape(text)}</p>" for text in guidance.paragraphs)
    return (
        '<details class="cochem-help"><summary>Explain '
        + escape(guidance.question)
        + "</summary>"
        + paragraphs
        + "</details>"
    )


# Definitions are deliberately local: searching help does not submit a job,
# contact an external service or change any scientific parameter.
_GLOSSARY = (
    ("Active space", "Electrons and orbitals selected for a multireference calculation. CAS(2,2) specifies two electrons in two orbitals; the orbital identities still need chemical justification."),
    ("Basis set", "Mathematical functions used to represent electrons. Compare the property of interest with systematically improved bases; a larger basis does not fix an unsuitable method."),
    ("Boltzmann population", "Electronic-energy weights are model estimates. Justified equilibrium fractions require consistent free energies, temperature and degeneracies, together with the assumption that interconversion reaches equilibrium."),
    ("Charge", "Total electric charge in units of the proton charge. Positive charge means electrons have been removed relative to the neutral atoms."),
    ("Codespaces", "The remote computer where you open the interface. A calculation sent to GitHub Actions runs on a separate computer."),
    ("Conformer", "A molecular arrangement related to another by changes such as bond rotations without changing covalent connectivity. A search candidate still needs validation as a minimum."),
    ("Convergence", "Satisfaction of specified numerical stopping criteria. Electronic convergence and geometry convergence are distinct; neither alone proves physical accuracy."),
    ("Counterpoise", "A correction for basis-set superposition error (BSSE): fragments are evaluated using the complex's basis functions. It is not a full free-energy correction."),
    ("Density functional theory (DFT)", "An electronic-structure approach using an approximate exchange-correlation functional. Different functionals and dispersion treatments can give different results."),
    ("Dispersion", "Attraction associated with correlated fluctuations of electrons. It matters for weak complexes; use a compatible treatment and avoid counting it twice."),
    ("Electronic energy (E)", "Reported fixed-nuclei energy, including nuclear repulsion. It excludes nuclear motion and does not by itself include zero-point, thermal or entropy contributions."),
    ("Fragment", "A defined component of a larger structure, such as one monomer of a dimer. Check atom membership, charge and spin before calculating fragment energies."),
    ("Free energy (G)", "Gibbs free energy includes energetic and entropic contributions at specified conditions. Comparisons require a consistent temperature, standard state and molecular-motion model."),
    ("Geometry optimization", "A search for a nearby stationary structure by adjusting allowed nuclear coordinates. The result depends on the starting geometry and constraints."),
    ("GitHub Actions", "A service that runs submitted calculations as jobs on separate computers and stores outputs for retrieval. Job access and available engines are checked for the chosen project."),
    ("Gradient", "The first derivative of energy with respect to coordinates; the force is its negative. Small gradients help establish that a geometry is stationary."),
    ("Hartree (Eh)", "An atomic unit of energy used in electronic-structure outputs. Keep units explicit when comparing values or converting energy differences."),
    ("Hartree–Fock (HF)", "An electronic-structure approximation with exchange but without electron correlation. Small-basis HF is useful for setup exercises, not reliable weak-binding predictions."),
    ("Hessian", "A matrix of second derivatives of energy describing local curvature. Its geometry, coordinate frame, atom order and units must accompany it."),
    ("High-performance computing (HPC)", "Institutional computing resources where a scheduler allocates processors and memory. Submitted jobs can wait in a queue before execution."),
    ("Imaginary frequency", "A vibrational mode with negative curvature, commonly printed as a negative frequency. Inspect its motion and numerical convergence before classifying the structure."),
    ("Isotope", "An atom of the same element with a different neutron count, such as carbon-13. Its mass changes nuclear motion; retain the correct atom label."),
    ("k-point mesh", "Sampling points used for the electronic calculation of a periodic solid. Test the property of interest for convergence with this sampling."),
    ("Monomer", "One molecular component of a complex. Its isolated geometry and its geometry within a complex can differ."),
    ("Natural Bond Orbital (NBO) analysis", "A model-based interpretation of calculated electron density in localized orbitals. Results depend on the electronic method and analysis settings; they are not direct observations of bonds."),
    ("Potential energy surface (PES)", "Energy as a function of nuclear coordinates. A one-coordinate scan is a slice or a constrained path through this surface, not the complete surface."),
    ("Provenance", "The retained record of input files, software, settings and transformations that produced a result. File checksums identify bytes; they do not establish chemical accuracy."),
    ("Pseudopotential / PAW", "An element-specific representation used in many plane-wave calculations to treat atomic cores efficiently. Match the file, functional and recommended cutoffs to the calculation."),
    ("Rotational constants", "Quantities related to moments of inertia. Equilibrium constants (Ae, Be, Ce) describe a geometry; ground-state constants (A0, B0, C0) also reflect nuclear motion."),
    ("Self-consistent field (SCF)", "An iterative solution of the electronic equations. SCF convergence does not mean the atomic geometry has been optimized."),
    ("Spin multiplicity", "The number 2S + 1, where S is total electron spin: singlet 1, doublet 2, triplet 3. Charge alone does not determine the spin state."),
    ("Standard state", "The reference pressure or concentration used to define thermodynamic quantities. State it explicitly, particularly when comparing association free energies."),
    ("Wiberg bond index", "A measure of bonding derived from an electronic population analysis. It depends on method, basis and analysis convention and is not an exact integer bond order."),
    ("Zero-point energy (ZPE)", "Nuclear vibrational energy remaining in the lowest vibrational state. A harmonic estimate uses calculated frequencies and is distinct from a full thermal free-energy correction."),
)


def _glossary_html(query: str) -> str:
    search = query.strip().casefold()
    entries = [(term, definition) for term, definition in _GLOSSARY
               if search in f"{term} {definition}".casefold()]
    if not entries:
        return (
            '<p role="status" aria-live="polite">No terms match “'
            + escape(query.strip())
            + '”. Try a shorter word, such as spin or energy.</p>'
        )
    count = len(entries)
    status = f'{count} term{"s" if count != 1 else ""}'
    return (
        f'<p role="status" aria-live="polite">{status}. Select a term to read its explanation.</p>'
        + "".join(
            '<details class="cochem-help"><summary>' + escape(term)
            + "</summary><p>" + escape(definition) + "</p></details>"
            for term, definition in entries
        )
    )


def build_glossary() -> widgets.VBox:
    """Build a searchable offline glossary without any calculation-state binding."""
    heading = widgets.HTML('<h2>Scientific terms</h2>')
    search = widgets.Text(
        description="Search terms:",
        placeholder="e.g. basis set, spin, free energy",
        continuous_update=True,
        style={"description_width": "initial"},
        layout=widgets.Layout(width="100%"),
    )
    results = widgets.HTML(_glossary_html(""))

    def update(change: dict) -> None:
        results.value = _glossary_html(change["new"])

    search.observe(update, names="value")
    panel = widgets.VBox([heading, search, results], layout=widgets.Layout(width="100%"))
    panel.add_class("cochem-glossary")
    return panel


MAX_HELP_QUERY = 240
MAX_HELP_RESULTS = 12
_SEARCH_STOP_WORDS = frozenset(
    "a an and are as at be can could did do does for from has have how i if in is it "
    "me my of on or should that the their them there these they this to use using "
    "was we were what when where which why will with would you your".split()
)
_SEARCH_WORDS = {
    "chiralty": "chirality", "chiral": "chirality", "conformers": "conformer",
    "isomers": "isomer", "enantiomers": "enantiomer", "resonance": "resonance",
    "frequencies": "frequency", "vibrations": "vibration", "spectra": "spectrum",
    "optimisation": "optimization", "optimise": "optimization",
    "optimize": "optimization", "optimizing": "optimization",
    "electrons": "electron", "orbitals": "orbital", "atoms": "atom",
    "molecules": "molecule", "results": "result", "calculations": "calculation",
    "files": "file", "charges": "charge", "isotopes": "isotope",
}
_SUGGESTED_TOPICS = (
    "first_calculation", "isomers", "chirality", "spectroscopy", "charge_spin", "read_results",
)


@dataclass(frozen=True)
class HelpTopic:
    """An authored explanation, never a generated answer about a calculation."""

    id: str
    title: str
    aliases: tuple[str, ...]
    what: str
    why: str
    when: str
    where: str
    how: tuple[str, ...]
    limitations: tuple[str, ...]
    controls: tuple[str, ...]


def _text_parts(value: str | Iterable[str]) -> tuple[str, ...]:
    return (value,) if isinstance(value, str) else tuple(value)


def _help_topics() -> tuple[HelpTopic, ...]:
    # The content module contains plain local text only; no provider discovery,
    # credential lookup or scientific state is consulted while reading help.
    return tuple(
        HelpTopic(
            id=topic_id, title=record["title"], aliases=_text_parts(record["aliases"]),
            what=record["what"], why=record["why"], when=record["when"],
            where=record["where"], how=_text_parts(record["how"]),
            limitations=_text_parts(record["limitations"]),
            controls=_text_parts(record["controls"]),
        )
        for topic_id, record in HELP_CONTENT.items()
    )


def _normalized(text: str) -> str:
    # Possessives should not turn every "molecule's" into a match for the
    # stereochemical label S in a student's R/S question.
    text = re.sub(r"['’]s\b", "", text.casefold())
    decomposed = unicodedata.normalize("NFKD", text)
    return " ".join(re.findall(r"[^\W_]+", "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )))


def _tokens(text: str) -> frozenset[str]:
    return frozenset(
        _SEARCH_WORDS.get(word, word)
        for word in _normalized(text).split() if word not in _SEARCH_STOP_WORDS
    )


def _control_entries(topic_id: str) -> tuple[tuple[str, dict], ...]:
    return tuple((control, metadata) for control, metadata in CONTROL_HELP.items()
                 if metadata["topic"] == topic_id)


def _topic_score(topic: HelpTopic, query: str, words: frozenset[str]) -> float:
    title = _normalized(topic.title)
    controls = _control_entries(topic.id)
    labels = tuple(metadata["label"] for _, metadata in controls if metadata.get("label"))
    aliases = tuple(_normalized(alias) for alias in (*topic.aliases, *labels))
    title_words = _tokens(topic.title)
    alias_words = _tokens(" ".join((*topic.aliases, *labels)))
    introduction = _tokens(topic.what)
    body = _tokens(" ".join((topic.why, topic.when, topic.where, *topic.how, *topic.limitations)))
    control_words = _tokens(" ".join(
        text for _, metadata in controls for text in (metadata["hint"], metadata["location"])
    ))
    # As-you-type prefixes apply to deliberate topic/control names and aliases.
    # Incidental body text still requires a complete word.
    title_matches = frozenset(word for word in words if word in title_words or (
        len(word) >= 2 and any(token.startswith(word) for token in title_words)))
    alias_matches = frozenset(word for word in words if word in alias_words or (
        len(word) >= 2 and any(token.startswith(word) for token in alias_words)))
    matched = title_matches | alias_matches | (words & (introduction | body | control_words))
    if not matched:
        return 0
    # Weight deliberate names/aliases above incidental words in long answers.
    # Coverage keeps an answer matching a whole question above a partial match.
    score = (12 * len(title_matches) + 9 * len(alias_matches)
             + 6 * len(words & control_words) + 4 * len(words & introduction) + len(words & body))
    score *= len(matched) / len(words)
    if query == title or query in aliases:
        score += 100
    elif len(query) > 2 and (query in title or any(query in alias for alias in aliases)):
        score += 35
    return score


def search_topics(query: str, limit: int = 6) -> tuple[HelpTopic, ...]:
    """Rank bounded, local explanations for words or ordinary-language questions.

    Matching is deterministic lexical lookup with authored aliases, including
    common spelling variants. It does not interpret uploaded files or ask an AI.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_HELP_RESULTS:
        raise ValueError(f"Help result limit must be an integer from 1 to {MAX_HELP_RESULTS}.")
    query = str(query)[:MAX_HELP_QUERY].strip()
    topics = _help_topics()
    if not query:
        by_id = {topic.id: topic for topic in topics}
        return tuple(by_id[topic_id] for topic_id in _SUGGESTED_TOPICS if topic_id in by_id)[:limit]
    words = _tokens(query)
    if not words:
        return ()
    normalized = _normalized(query)
    ranked = [(topic, _topic_score(topic, normalized, words)) for topic in topics]
    ranked.sort(key=lambda match: (-match[1], match[0].title.casefold(), match[0].id))
    return tuple(topic for topic, score in ranked if score > 0)[:limit]


def coverage_index(control_ids: Iterable[str] | None = None) -> dict:
    """Report authored control coverage; never imply every GUI item is covered.

    Supply an actual control inventory to obtain its unmapped identifiers. An
    omitted inventory means coverage of other controls has not been assessed.
    """
    control_topics: dict[str, list[str]] = {}
    topics = _help_topics()
    for topic in topics:
        for control in topic.controls:
            control_topics.setdefault(control, []).append(topic.id)
    for control, metadata in CONTROL_HELP.items():
        topic_id = metadata["topic"]
        if topic_id not in HELP_CONTENT:
            raise ValueError(f"Help inventory references unknown topic: {topic_id}")
        if topic_id not in control_topics.setdefault(control, []):
            control_topics[control].append(topic_id)
    return {
        "topic_ids": tuple(topic.id for topic in topics),
        "control_topics": {control: tuple(ids) for control, ids in control_topics.items()},
        "control_metadata": {control: dict(metadata) for control, metadata in CONTROL_HELP.items()},
        "unmapped_controls": tuple(sorted(set(control_ids or ()) - set(control_topics))),
        "inventory_supplied": control_ids is not None,
        "scope": "Authored help for the listed controls only. Other controls require an inventory review.",
    }


def _paragraphs(texts: Iterable[str]) -> str:
    return "".join(f"<p>{escape(text)}</p>" for text in texts)


def _control_help_html(topic_id: str) -> str:
    entries = _control_entries(topic_id)
    if not entries:
        return ""
    items = []
    for control, metadata in entries:
        label = metadata.get("label", "")
        title = '<strong>' + escape(label) + '.</strong> ' if label else ""
        advanced = " Advanced setting." if metadata.get("advanced") else ""
        items.append(
            '<li data-help-control="' + escape(control) + '"><p>' + title
            + escape(metadata["hint"]) + '</p><p>Where: ' + escape(metadata["location"])
            + escape(advanced) + '</p></li>'
        )
    return (
        '<details class="cochem-help-controls"><summary>Help for individual controls</summary>'
        '<p>These item instructions share the explanation and scientific limits above.</p><ul>'
        + "".join(items) + '</ul></details>'
    )


def topic_html(topic: HelpTopic | str, *, opened: bool = False) -> str:
    """Render escaped teaching text; advanced explanation starts collapsed."""
    if isinstance(topic, str):
        matches = {item.id: item for item in _help_topics()}
        topic = matches[topic]
    steps = "".join(f"<li>{escape(step)}</li>" for step in topic.how)
    return (
        '<details class="cochem-help-topic" data-help-topic="' + escape(topic.id) + '"'
        + (" open" if opened else "")
        + '><summary>' + escape(topic.title) + '</summary>'
        + '<p><strong>What it means.</strong> ' + escape(topic.what) + '</p>'
        + '<details class="cochem-help-depth"><summary>'
        + 'Teach me more: why, when, where and how</summary>'
        + '<p><strong>Why it matters.</strong> ' + escape(topic.why) + '</p>'
        + '<p><strong>When to use it.</strong> ' + escape(topic.when) + '</p>'
        + '<p><strong>Where to find it.</strong> ' + escape(topic.where) + '</p>'
        + '<p><strong>How to proceed</strong></p><ol>' + steps + '</ol>'
        + '<p><strong>Scientific limits</strong></p>' + _paragraphs(topic.limitations)
        + '</details>' + _control_help_html(topic.id) + '</details>'
    )


def build_topic_answer(topic_id: str) -> widgets.HTML:
    """Build an inline contextual answer from the same authored search content."""
    answer = widgets.HTML(topic_html(topic_id, opened=True))
    answer.add_class("cochem-context-answer")
    return answer


class LearningHelp:
    """Independent widget controller with no calculation or account bindings."""

    _READY = (
        'Offline help is ready. Search a chemistry word or ask a question, '
        'such as “what is chirality?”. No account or calculation engine is needed.'
    )

    def __init__(self) -> None:
        self.search = widgets.Text(
            description="Help search:", placeholder="Try chirality, charge, or a question",
            continuous_update=True, style={"description_width": "initial"},
            layout=widgets.Layout(flex="1 1 18rem", width="auto", min_width="0"),
        )
        self.clear = widgets.Button(
            description="Clear help", tooltip="Clear the help question and close its explanations",
            layout=widgets.Layout(width="auto"),
        )
        self.status = widgets.HTML()
        self._result_html = widgets.HTML()
        self.results = widgets.VBox(layout=widgets.Layout(width="100%"))
        self.results.add_class("cochem-help-results")
        toolbar = widgets.Box(
            [self.search, self.clear],
            layout=widgets.Layout(display="flex", flex_flow="row wrap", width="100%"),
        )
        toolbar.add_class("cochem-help-search")
        self.widget = widgets.VBox(
            [toolbar, self.status, self.results], layout=widgets.Layout(width="100%"),
        )
        self.widget.add_class("cochem-learning-help")
        self.search.observe(self._search_changed, names="value")
        self.clear.on_click(self._clear_clicked)
        self._set_status(self._READY)

    def _set_status(self, message: str) -> None:
        self.status.value = '<p role="status" aria-live="polite">' + escape(message) + '</p>'

    def _replace_results(self, topics: Iterable[HelpTopic], *, opened: bool = False) -> None:
        # Keep one output model while typing instead of allocating fresh widget,
        # layout and style models for every result on every keystroke.
        self._result_html.value = "".join(topic_html(topic, opened=opened) for topic in topics)
        self.results.children = (self._result_html,) if self._result_html.value else ()

    def _search_changed(self, change: dict) -> None:
        query = change["new"][:MAX_HELP_QUERY].strip()
        if not query:
            self._replace_results(())
            self._set_status(self._READY)
            return
        topics = search_topics(query)
        self._replace_results(topics)
        if not topics:
            self._set_status(
                f'No help topics match “{query}”. Try a shorter chemistry word, such as '
                'chirality, charge, frequency or energy. Clear help to start again.'
            )
            return
        count = len(topics)
        self._set_status(
            f'{count} topic{"s" if count != 1 else ""} shown for “{query}”. '
            'Select a title to read it. At most 6 topics are shown; add a word to narrow the search.'
        )

    def _clear_clicked(self, _button: widgets.Button) -> None:
        self.search.value = ""
        # Setting an already-empty Text does not notify observers. Close a
        # contextual answer too, even when its search field was already empty.
        self._replace_results(())
        self._set_status(self._READY)
        self.search.focus()

    def open_topic(self, topic_id: str) -> bool:
        """Show one contextual answer; an unknown ID receives an explicit status."""
        topic = next((item for item in _help_topics() if item.id == topic_id), None)
        self.search.value = ""
        if topic is None:
            self._replace_results(())
            self._set_status(f'Help topic “{str(topic_id)[:MAX_HELP_QUERY]}” is not available. Try Help search.')
            self.search.focus()
            return False
        self._replace_results((topic,), opened=True)
        self._set_status(f'Contextual help: {topic.title}. Open “Teach me more” for the next steps and limitations.')
        self.search.focus()
        return True


def build_learning_help() -> LearningHelp:
    """Create compact, persistent help available before account or engine setup."""
    return LearningHelp()
