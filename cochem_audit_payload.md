Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\Phase_1_Task_1_Prompt_1_gitignore.md.
Original prompt:
# CoChem-SCRIBE Phase 1, Task 1 - Prompt 1: `.gitignore`

**Target Output Repository:** `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`
**Target File:** `.gitignore`

**Objective:**
Create the `.gitignore` file for the CoChem-SCRIBE repository to enforce the Bipartite Workspace Air-Gap and prevent repository pollution.

**Instructions for Execution Agent:**
1. Ensure you are working in `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`. Create the directory if it does not exist.
2. Create a `.gitignore` file at the root of the repository.
3. Populate it with the following strict air-gap constraints to block Python caches, LLM weights, Data Tier directories, HDF5 artifacts, LaTeX compilation waste, and compiled output archives:

```gitignore
# ==============================================================================
# CoChem-SCRIBE Strict Air-Gap Constraints
# ==============================================================================

# 1. Block Python Caches, Virtual Environments, and Local Secrets
__pycache__/
*.py[cod]
*$py.class
venv/
cochem_scribe_silo/
.env
.env.*

# 2. Block Massive LLM Weights (RESOURCE_GUARD Protection)
*.gguf
*.bin
*.pt
*.safetensors

# 3. Physically Block Data Tier Accidental Tracking
CoChem_Artifacts/
Report_Archive/
visual_assets/

# 4. Block Massive Tensors and HDF5 Artifacts
*.h5
*.hdf5
*.cube
*.xyz
*.parquet
*.sqlite

# 5. Block LaTeX Compilation Waste and Output Documents
*.aux
*.log
*.out
*.toc
*.pdf
*.bbl
*.blg
*.fls
*.fdb_latexmk
*.synctex.gz
*.tex
!formatters/**/*.tex
*.bib
*.md
!README.md

# 6. Block Compiled Output Archives
*.zip
*.tar.gz
*.tar.zst
*.zst
```

4. Write this file to the repository exactly as defined. Do not hallucinate or use placeholders. Save the file.

Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.