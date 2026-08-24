Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\scribe_payload_builder_prompt.md.
Original prompt:
# CoChem-SCRIBE Task: Context-Safe Payload Builder & Prompt Synthesis

## Target Repository Path
**`D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`**

## Target File to Create/Modify
`harvesters/scribe_payload_builder.py`

## Mission Objective
Implement the `PayloadBuilder` class in `harvesters/scribe_payload_builder.py`. This class acts as the critical security checkpoint enforcing a "Mathematical Air-Gap" between factual physical chemistry and LLMs, and dynamically manages the token economy.

## Detailed Requirements (Implementation Tasks 21–29)
1. **Module State & Pipeline Context Construction:**
   - Initialize `PayloadBuilder` by ingesting aggregated data dictionaries and the active `cochem_deployment_manifest.json`.
   - Synthesize a concise "State of the Run" string derived from the manifest (e.g., "This dataset was generated using ORCA 6.1.1 for electronic structure, MACE-OFF23 for initial conformer routing, and CODATA 2022 constants.").

2. **The Master System Prompt & Strict Math Prohibition:**
   - Construct and prepend an immutable System Prompt to every request.
   - You MUST explicitly include this exact command in the prompt: *"You are an automated academic writer for the CoChem computational chemistry pipeline. You are strictly forbidden from inventing, calculating, or guessing physical constants, energies, frequencies, or geometric bond lengths. You must only provide narrative insight, methodology structuring, and analytical text based exclusively on the provided metadata. Use explicit injection tags such as `INSERT_THERMO_TABLE_HERE` where exact numerical data should be injected."*

3. **Dynamic Token Metrology (`tiktoken`):**
   - Integrate `tiktoken` strictly pinned to the `cl100k_base` encoding.
   - Calculate the exact token integer count before dispatching the prompt to Stage 6.2.

4. **Context-Chunking & Truncation Algorithm:**
   - Implement a strict safety threshold of **6,000 tokens**.
   - If the prompt exceeds 6,000 tokens, truncate data in this strict priority order:
     1. Drop lowest-energy conformer statistical arrays beyond the top 3 global minima.
     2. Drop high-frequency vibrational scalar noise (retaining defining fundamental frequencies).
     3. Drop detailed warning telemetry (retaining only "Fatal" and "Critical" hardware tags).
   - NEVER truncate: The global minimum Gibbs Free Energy (ΔG), ZPE, or deployment manifest software versions.

5. **Dynamic Prompt Targeting:**
   - Expose methods to synthesize different prompts based on UI constraints.
   - **Methodology Prompt:** Ask the LLM to write a 2-paragraph, APS-compliant computational methodology section based ONLY on the extracted deployment manifest and citation engine list.
   - **Insights / User Guide Prompt:** Ask the LLM to write a short "Thermodynamic Analysis" paragraph highlighting which conformer dominates the Boltzmann population based on energy gaps (targeting `CoChem_User_Guide.md`).

6. **The `LAM_TRIGGER` Physics Justification:**
   - Detect active physics flags in the HDF5 metadata.
   - If a Large-Amplitude Motion (LAM) was processed using a 1D or 2D Sinc-DVR (instead of standard VPT2), dynamically inject this command into the prompt: *"The telemetry indicates the system utilized a Sinc-DVR for torsional motion. Generate one paragraph scientifically justifying the use of Sinc-DVR over the standard rigid-rotor harmonic oscillator (RRHO) approximation for this highly flexible coordinate."*

7. **Dry-Run Boilerplate Fallbacks:**
   - If `RESOURCE_GUARD` forces the system offline or `--dry-run` is toggled, bypass token counting and AI inference completely.
   - Immediately return a static, hardcoded fallback string (e.g., *"Calculations were performed using the methods listed in the appended tables. [LLM BYPASSED VIA DRY-RUN]"*).

## CoChem Global Directives
- **Zero Truncation / No Mocks:** NEVER use placeholders like `...`, `pass`, or `TODO`. Write the 100% complete Python module. Do not invent or stub data schemas.
- **Root Cause & Exception Deflection Mandate:** Do not use broad `try/except` blocks to swallow errors. Do not use band-aids.
- **Strict Single-File Restriction:** ONLY write/modify `harvesters/scribe_payload_builder.py`. Do NOT write any test files during this prompt execution.

Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.