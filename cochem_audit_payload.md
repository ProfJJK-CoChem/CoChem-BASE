Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\Phase_1_Task_1_Prompt_3_readme.md.
Original prompt:
# CoChem-SCRIBE Phase 1, Task 1 - Prompt 3: `README.md`

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`
**Target File:** `README.md`

**Objective:**
Create the master `README.md` that explains the CoChem-SCRIBE topology, specifically the Bipartite Workspace Air-Gap and the 6-Tier Environment Matrix.

**Instructions for Execution Agent:**
1. Ensure you are working in `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`. Create the directory if it does not exist.
2. Create `README.md` at the root of the repository.
3. The README must comprehensively cover the following architectural mandates:
   - **Bipartite Workspace Air-Gap:** Explain that the system is divided into two environments:
     - **Execution Tier (`$HOME/CoChem-SCRIBE/`)**: Git-tracked, contains Python logic, UI dashboard, and templates. Read-only at runtime.
     - **Data Tier (`$HOME/CoChem_Artifacts/`)**: Mutable, localized scratch space for HDF5 reading, LLM API keys, and artifact generation.
   - **Environment Matrices:** Mention compatibility with the Interaction Matrix (Local-Windows/WSL, MacOS/OrbStack, Linux/Debian, Codespaces) and Calculation Matrix (same + GitHub Actions, HPC).
4. Provide basic setup or topology navigation information.
5. Do not include placeholders like `[Insert explanation here]`. Write professional, complete documentation based on this context. 
6. Save the fully formed `.md` file.

Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.