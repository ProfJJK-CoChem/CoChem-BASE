Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\Phase_1_Task_1_Prompt_2_requirements.md.
Original prompt:
# CoChem-SCRIBE Phase 1, Task 1 - Prompt 2: `requirements.txt`

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`
**Target File:** `requirements.txt`

**Objective:**
Create the initial `requirements.txt` file for CoChem-SCRIBE containing the core dependencies required for Stage 6 pipeline orchestration, HDF5 reading, templating, and UI generation.

**Instructions for Execution Agent:**
1. Ensure you are working in `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`. Create the directory if it does not exist.
2. Create a `requirements.txt` file at the root.
3. Include the following core dependencies:
   - `Jinja2`
   - `psutil`
   - `tiktoken`
   - `requests`
   - `tenacity`
   - `pandas`
   - `h5py`
   - `jupyter`
   - `voila`
   - `zstandard`
4. You may leave versions unpinned for now or use standard stable ranges, but these specific packages must be listed.
5. Save the file completely. Do not use placeholders.

Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.