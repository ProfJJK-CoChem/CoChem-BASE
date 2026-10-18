# GUI usability and scientific guidance: design evidence

Research accessed **18 October 2026**. This document explains the redesign's
choices and the evidence behind them. It does not certify usability, complete
SRS implementation or WCAG conformance. Rendered-browser checks and observation
of students doing real tasks are separate acceptance work.

## Requirements and scope

The user requires a professional scientific interface, a complete no-code
student workflow, explanations that can be opened beside unfamiliar settings,
less unexplained jargon, and clear guidance for interpreting results.

The repository's baseline remains [SRS Chunk 17](SRS_Chunk_17_CoChem_BASE_Architecture.md)
plus [proposal additions](SRS_Chunk_Proposal_CoChem_BASE_Architectural_Review.md).
The relevant requirements include conformer-pool ingestion and source records
(WBS 17.3.1), monomer partitioning (17.4.1), convergence and Hessian discipline
(17.5), and immutable crash records (proposal §3.6). Clearer presentation must
preserve those scientific checks and the full ingestion routine.

The [GUI charter](improvements/GUI_Architecture_Charter.md) requires a no-code
browser interface tied to real scientific state across Codespaces, WSL, Linux
HPC and macOS. The [wireframe specification](improvements/GUI_Wireframe_Spec.md)
requires system/environment status, actionable errors, labelled scientific
plots, contrast and keyboard operation. The historical
[usability audit](audits/adversary_task3_1_3_audit_report.md) records contextual
help, manual links, scientific notation, keyboard navigation and accessible
palettes. Its referenced Windows-path component specification is absent from
this checkout; the audit is corroborating evidence, not the missing document.

The exact phrase “pull-out explanations” was not found in the two main BASE
architecture files. It is an explicit user requirement, supported by the GUI
specifications and research below. No new SRS identifier is invented for it.

## Trace from requirements to the redesigned interface

This table records concrete source changes and retained controls. “Added” or
“retained” describes implementation in this redesign; it does not mean that
all scientific acceptance requirements have passed. Requirement numbers below
refer to **Chunk 17**, since the proposal reuses some numbers differently.

| Specification or user requirement | Concrete interface and source | Scope of this redesign |
| --- | --- | --- |
| GUI charter §§1–3: no-code entry point and environment support; wireframe §3.3 setup | **Start here**, **Run calculations on**, **Check ORCA & CFOUR**, **Where this interface runs**; [workspace_layout.py](../ui/voila_layout/workspace_layout.py) and existing setup controllers in [cochem_gui.py](../ui/voila_layout/cochem_gui.py) | Setup is grouped around a visible next action. Actions, local WSL/Linux/macOS and HPC routes are retained; real acceptance on every platform remains separate. |
| User: ORCA/CFOUR optional and strongly recommended | Existing engine checks and dependent-action restrictions, plus environment explanation in [learning.py](../ui/voila_layout/learning.py) | Missing licensed engines do not impose a universal block on ingestion or independent features. An access check is distinguished from a completed chemical calculation. |
| User: on-demand explanations and understandable terminology; wireframe §§3.4/4 | Adjacent **Explain…** disclosures, short visible hints and searchable **Scientific terms**; [learning.py](../ui/voila_layout/learning.py), [workspace_layout.py](../ui/voila_layout/workspace_layout.py) | Contextual chemistry guidance and a glossary are added. Looking up a term has no calculation-state binding. Student comprehension still requires observation. |
| Chunk 17 §6/WBS 17.3.1; User Manual §§2.1–2.4: broad ingestion | **Your files**, **File contents**, **Structure / frame**, **File details and provenance**, ensemble and inbox disclosures; [workspace_layout.py](../ui/voila_layout/workspace_layout.py) with retained canonical ingestion | Simplifies presentation while retaining molecular, multiframe, conformer, periodic, Hessian, native-output and numerical input routes. File validation is not evidence of a physical minimum. |
| Chunk 17 REQ-BASE-004/005: masses and geometry identity; user input-state requirements | **Starting structure**, **Total charge**, **Spin multiplicity**, structure preview and charge/spin/isotope explanations; [learning.py](../ui/voila_layout/learning.py) and [workspace_layout.py](../ui/voila_layout/workspace_layout.py) | Explains the chosen electronic state and retained atom/isotope identity; the existing mass and coordinate checks remain authoritative. |
| Chunk 17 §§4.1/4.2 and REQ-BASE-012/013: method families, products, dispersion and spin | **Scientific goal**, **Theory family**, method/basis/solvent help and **Advanced: multireference spin recovery (T9)**; [workspace_layout.py](../ui/voila_layout/workspace_layout.py), [learning.py](../ui/voila_layout/learning.py) | Human-readable labels preserve canonical product values. Product B directs the user through an explicit periodic-tool button. A tier or goal does not certify accuracy. |
| Chunk 17 REQ-BASE-007/008/011: frozen monomers, references and starting Hessian | **Monomer constraints**, **Provide R2 monomer references**, **Choose starting curvature for optimization**; [workspace_layout.py](../ui/voila_layout/workspace_layout.py) | Adds explanations of what may move, required references and curvature reuse; advanced engine syntax is secondary. Existing source/geometry checks are retained. |
| Chunk 17 REQ-BASE-014: harmonic isotope transformation | **Spectra and properties → Isotope effects**, matching-Hessian and isotope guidance; [workspace_layout.py](../ui/voila_layout/workspace_layout.py), [learning.py](../ui/voila_layout/learning.py) | Explains reuse of the electronic surface and distinguishes harmonic mass substitution from missing anharmonic corrections. |
| Wireframe §3.4; proposal §3.6; Chunk 17 REQ-BASE-009/010: helpful errors without weakening scientific gates | Visible recovery messages and expandable diagnostics in [cochem_gui.py](../ui/voila_layout/cochem_gui.py); corrected scientific teaching in [exceptions.py](../src/cochem_base/exceptions.py) | Removes unsafe generic grid-downgrade advice and incorrect product/minimum explanations. Detailed crash provenance remains a backend responsibility and is not replaced by friendly wording. |
| User: usable TOPOS/TORQ and scientifically meaningful outputs; wireframe §§3.3/4.4 | Operation-specific **TOPOS** and **TORQ** forms, rigid distance-scan guidance, NBO/NAO/Löwdin distinctions, **Results** comparison help; [research_panels.py](../ui/voila_layout/research_panels.py) and retained [student_reports.py](../src/cochem_base/interfaces/student_reports.py) | Explains actual operations and energy/population limits. It does not implement unavailable scientific providers or turn a one-dimensional rigid scan into a complete potential surface. |
| User: recover from mistakes; wireframe §4.2 | Retained **Remove from list**, **Undo remove**, restore, attachment-clear and comparison-clear controls; [input_management.py](../ui/voila_layout/input_management.py), [research_panels.py](../ui/voila_layout/research_panels.py) | Keeps reversible input management and retained original/result records. Opening help must not discard a draft. |
| Wireframe §§2/3.1/3.2/4.3: responsive layout, status and accessibility | Sidebar, shared visual hierarchy, focus styles and disclosures; [workspace_style.py](../ui/voila_layout/workspace_style.py), [workspace_layout.py](../ui/voila_layout/workspace_layout.py), [disclosure.py](../ui/voila_layout/disclosure.py) | Source implementation supports the redesigned presentation. Keyboard, contrast, zoom, assistive-technology and student task acceptance must be assessed in the rendered application. |

The old wireframe's universal requirement for an HDF5/NPZ Hessian before
setup conflicts with the user's later explicit starting-geometry and
optional-engine requirements. The redesign follows those later instructions:
only operations that need a Hessian require one. It does not remove their
scientific input checks.

## Design decisions

| Decision | Implementation direction | Basis |
| --- | --- | --- |
| Show the immediate task | Keep the next action, required input, units, current status and short essential instructions visible. | Sources 1–3 |
| Make explanations discoverable | Put a named **Explain…** disclosure beside the relevant setting. Use descriptive questions rather than an unexplained icon or generic “More”. Avoid deeply nested help. | Sources 1–3, 6 |
| Explain scientific choices | State what a setting means, when it matters, an example, and what its result can establish. Keep legitimate chemistry terms and explain their first use. | Sources 4, 7, 8 |
| Support recognition | Keep the selected structure, electronic state and calculation location in view. Provide a searchable **Scientific terms** reference without changing the draft. | Sources 4, 7, 8 |
| Reduce visual competition | Use consistent headings, spacing, field labels and button hierarchy. Group related controls; show operation-specific options. Status must have words as well as color. | Sources 1, 5, 8 |
| Make errors recoverable | State what failed and the next action. Preserve inputs and selections. Keep exact diagnostic records under optional technical details. | Sources 3, 5, 8 |
| Preserve scientific meaning | Label quantities and units. Show method, convergence and interpretation limits. Keep full calculation records and full-precision exports available. | Source 9 and BASE scientific requirements |
| Verify actual interactions | Check mouse, keyboard, zoom, narrow layouts, input recovery, result interpretation and exports in the rendered interface. Assess student comprehension with actual tasks. | Sources 1, 5, 6, 8 |

These recommendations do not imply that hiding more content always helps.
Required guidance stays visible. Longer explanations are optional to open, but
must be easy to find at the moment a student needs them.

## Sources and retrieved evidence

All sources below were read on **18 October 2026**, through the agent-reach
skill's documented Jina Reader route with normal TLS verification. Native web
search and the Agent Reach command-line runtime were unavailable. Quotations
below are short excerpts of the retrieved source, not descriptions of CoChem
acceptance results.

1. **Nielsen Norman Group: [Progressive Disclosure](https://www.nngroup.com/articles/progressive-disclosure/).**
   “You have to disclose everything that users frequently need up front.”
   It also says progression to further detail must be obvious, and warns that
   designs beyond two disclosure levels often cause users to get lost. This
   supports visible core controls plus clearly labelled optional explanations.
   A rigid sequence is less suitable when scientific settings must be compared
   and revised together.

2. **GOV.UK Design System: [Details](https://design-system.service.gov.uk/components/details/)
   and [Accordion](https://design-system.service.gov.uk/components/accordion/).**
   Details: “Do not use the details component to hide information that the
   majority of your users will need.” Accordion: “Not all users will notice
   them or understand how they work.” Simplify and structure content before
   hiding it; use concise, descriptive disclosure labels.

3. **GOV.UK Design System: [Text input](https://design-system.service.gov.uk/components/text-input/)
   and [Error message](https://design-system.service.gov.uk/components/error-message/).**
   “Use hint text for help that’s relevant to the majority of users.”
   “Do not clear any form fields when showing the Error message component.
   Keep both passing and failing answers.” The guidance also requires errors
   to explain what happened and how to fix it. A placeholder does not replace
   a persistent label, unit or hint; lengthy explanations belong beside a
   field rather than inside its screen-reader description.

4. **GOV.UK: [Use clear language](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/clear-language/).**
   “Where you need to use specialist terms, you can. They’re not always jargon.
   You just need to explain what they mean the first time you use them.”
   This supports retaining terms such as basis set, multiplicity and
   counterpoise while removing unnecessary internal software terminology.
   It also recommends reviewing sentences longer than 25 words; this is an
   editing aid, not a measure of scientific correctness.

5. **W3C: [Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/).**
   Relevant criteria include keyboard operation (2.1.1), visible and
   unobscured focus (2.4.7/2.4.11), labels/instructions (3.3.2), error
   identification/suggestions (3.3.1/3.3.3), name/role/value (4.1.2) and
   status messages (4.1.3). Ordinary text contrast is at least 4.5:1, with
   the standard's exceptions; relevant non-text controls require 3:1.
   Reflow (1.4.10) addresses 320 CSS-pixel width or equivalent zoom, allowing
   exceptions for inherently two-dimensional content such as data tables.
   A tablet screenshot alone does not establish this requirement. Target size
   (2.5.8) specifies 24 by 24 CSS pixels with defined exceptions. Definitions
   of unusual terms and abbreviation expansion (3.1.3/3.1.4) are **AAA**,
   not AA; they are additional targets here because the user requires them.

6. **W3C WAI: [Disclosure pattern](https://www.w3.org/WAI/ARIA/apg/patterns/disclosure/)
   and [Content on hover or focus](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html).**
   The disclosure button operates with Enter and Space and exposes its
   expanded/collapsed state. Native disclosure semantics or a correctly
   implemented button are preferable to a clickable visual header alone.
   Applicable hover/focus content must be dismissible, hoverable and
   persistent. Teaching material must therefore be accessible without a
   mouse-only tooltip. APG is an implementation pattern, not a complete
   accessibility certification.

7. **The Carpentries: [Memory and Cognitive Load](https://carpentries.github.io/instructor-training/05-memory.html).**
   “Minimally-guided instruction requires learners to simultaneously master
   a domain’s factual content AND its search and problem-solving strategies.”
   The lesson recommends guided practice, feedback and a running glossary.
   For CoChem, students should spend their attention on chemical choices and
   interpretation, with help next to their current task. The lesson's older
   discussion of “7±2” must not become a rigid allowed number of controls.

8. **Nielsen Norman Group: [10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/).**
   “Offer help in context, instead of giving users a long tutorial to
   memorize.” It also requires the interface to speak the user's language,
   support undo, expose system status and provide concise task-oriented help.
   A manual link supplements contextual guidance; it does not replace it.

9. **Wilkinson et al.: [The FAIR Guiding Principles for scientific data management and stewardship](https://www.nature.com/articles/sdata201618),
   DOI: 10.1038/sdata.2016.18.**
   The principles apply to “the algorithms, tools, and workflows that led
   to that data.” All components support transparency, reproducibility and
   reuse. The application to GUI layout is a design inference: readable
   results should retain links to inputs, settings and calculation records,
   with machine-readable exports. FAIR does not prescribe a particular
   screen layout or require publication of licensed binaries or private data.

The old GOV.UK writing URL redirected; the current publishing-guidance page
above was used. GO FAIR returned a challenge page, so the original Nature
article was used. An attempted Carpentries expertise page returned 404 and a
PLOS figures article returned HTTP 403; neither contributes evidence here.

## What acceptance must demonstrate

- A student can find upload, choose the intended structure/task and identify
  the next action without opening developer diagnostics.
- Named explanations are reachable by mouse and keyboard, expose their state,
  and remain distinct from required instructions and current errors.
- Looking up a term or opening help preserves the calculation draft.
- Failed validation preserves original data and gives a specific recovery
  path; removal and undo do not silently delete research evidence.
- Results distinguish electronic energy, free energy, calculated weights and
  justified equilibrium populations. A rendered table cannot establish
  convergence, a physical minimum, chemical accuracy or provider availability.
- Scientific values remain readable at narrow widths and zoom; essential
  controls retain labels, focus and sufficient contrast.
- Student observation measures completion, mistakes, discoverability and
  comprehension. Automated tests and screenshots support this assessment;
  they cannot establish it alone.
