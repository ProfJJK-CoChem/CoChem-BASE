# Target Directory Inspection & Absolute Path Audit Analysis

**Target Directory**: `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`  
**Date**: 2026-08-11  
**Investigator**: Explorer Agent (`teamwork_preview_explorer_survey_2`)

---

## 1. Executive Summary

A comprehensive inspection of the target directory `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` was conducted. The directory currently houses **16 top-level files** (15 agent definition files + `ORIGINAL_REQUEST.md`) and **5 subdirectories** containing metadata/swarm operational files.

An exhaustive scan for occurrences of personal absolute paths (`<USER_HOME>` and `<COCHEM_WORKSPACE>`) revealed:
1. **Agent Definition Files (`*.agent.md`)**: All 15 agent files are currently clean of `<USER_HOME>` and `<COCHEM_WORKSPACE>`. They utilize generic placeholders (`<COCHEM_ROOT>` and `<GDRIVE_ROOT>`).
2. **`ORIGINAL_REQUEST.md`**: Contains 4 occurrences of `<USER_HOME>` and 4 occurrences of `<COCHEM_WORKSPACE>`.
3. **Subdirectory Metadata Files (`.agents/*`)**: Operational files inside `orchestrator/`, `sentinel/`, and `teamwork_preview_explorer_survey_1..3/` contain numerous occurrences of both `<USER_HOME>` and `<COCHEM_WORKSPACE>`.

---

## 2. Directory Structure and Inventory

### 2.1 Top-Level Files (16 total)

| File Name | Size (Bytes) | Category | Description / Purpose |
|---|---|---|---|
| `0rchestrator.agent.md` | 4,889 | Agent Config | Master orchestrator agent prompt & directives |
| `artist.agent.md` | 2,136 | Agent Config | Visual prompt-crafting agent prompt & directives |
| `cochem-audit.agent.md` | 3,521 | Agent Config | Quality assurance & code standards audit agent |
| `cochem-coder.agent.md` | 3,727 | Agent Config | Implementation & feature building agent |
| `cochem-debug.agent.md` | 3,667 | Agent Config | Debugging and triage agent |
| `cochem-helper.agent.md` | 3,554 | Agent Config | Outward-facing researcher support agent |
| `cochem-improve.agent.md` | 3,447 | Agent Config | Architecture audit & copy editing agent |
| `cochem-scribe.agent.md` | 2,592 | Agent Config | Technical writing & documentation agent |
| `cochem-sdp_manager.agent.md` | 4,613 | Agent Config | PMBOK/SWEBOK project management agent |
| `cochem-tester.agent.md` | 2,650 | Agent Config | PyTest & chaos fuzzing validation agent |
| `educator.agent.md` | 3,068 | Agent Config | STEM pedagogical design & grading agent |
| `researcher.agent.md` | 2,719 | Agent Config | Fact-finding & research compilation agent |
| `teacher.agent.md` | 2,556 | Agent Config | Direct student interaction & Socratic agent |
| `ui.agent.md` | 2,855 | Agent Config | UI/UX & data visualization design agent |
| `web_mcp.agent.md` | 2,221 | Agent Config | Web scraping & DOM sanitization agent |
| `ORIGINAL_REQUEST.md` | 3,181 | Project Log | Record of initial phase & follow-up user prompt |

### 2.2 Subdirectories (5 total)

| Subdirectory Name | Contained Files | Category | Purpose |
|---|---|---|---|
| `orchestrator/` | `BRIEFING.md`, `DISPATCH.md`, `progress.md` | Swarm Metadata | Orchestrator state tracking & dispatch history |
| `sentinel/` | `BRIEFING.md`, `handoff.md` | Swarm Metadata | Sentinel top-level monitor state & handoff |
| `teamwork_preview_explorer_survey_1/` | `BRIEFING.md`, `DISPATCH.md` | Agent Workspace | Explorer 1 workspace (Survey source config) |
| `teamwork_preview_explorer_survey_2/` | `BRIEFING.md`, `DISPATCH.md`, `progress.md` | Agent Workspace | Explorer 2 workspace (Target survey - current agent) |
| `teamwork_preview_explorer_survey_3/` | `BRIEFING.md`, `DISPATCH.md`, `progress.md` | Agent Workspace | Explorer 3 workspace (Sanitization strategy) |

---

## 3. Absolute Path Scan Findings

Every file in `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents` was scanned for occurrences of `<USER_HOME>` and `<COCHEM_WORKSPACE>` (including forward-slash variants).

### 3.1 Summary Matrix

| Location | File Pattern | Total Files | Files with `<USER_HOME>` | Files with `<COCHEM_WORKSPACE>` |
|---|---|---|---|---|
| `.agents/` | `*.agent.md` | 15 | **0** | **0** |
| `.agents/` | `ORIGINAL_REQUEST.md` | 1 | **1** | **1** |
| `.agents/orchestrator/` | `*.md` | 3 | **3** | **3** |
| `.agents/sentinel/` | `*.md` | 2 | **2** | **2** |
| `.agents/teamwork_preview_explorer_survey_1/` | `*.md` | 2 | **2** | **2** |
| `.agents/teamwork_preview_explorer_survey_2/` | `*.md` | 3 | **3** | **3** |
| `.agents/teamwork_preview_explorer_survey_3/` | `*.md` | 3 | **3** | **3** |

### 3.2 Detailed Line-by-Line Occurrences

#### 1. `ORIGINAL_REQUEST.md`
- **Line 36**: `...provided in <USER_HOME>\.gemini\config\agents...`
- **Line 38**: `Working directory: <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE`
- **Line 44**: `Copy the fixed agent configuration files from <USER_HOME>\.gemini\config\agents and completely overwrite the existing agent files in <COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents.`
- **Line 47**: `...specifically <USER_HOME> and <COCHEM_WORKSPACE>...`
- **Line 52**: `...files from <USER_HOME>\.gemini\config\agents.`
- **Line 53**: `Running a search for <USER_HOME> inside CoChem-BASE/.agents...`
- **Line 54**: `Running a search for <COCHEM_WORKSPACE> inside CoChem-BASE/.agents...`

#### 2. Subdirectory Metadata Files (`.agents/orchestrator/`, `.agents/sentinel/`, `.agents/teamwork_preview_explorer_survey_*`)
- `orchestrator/BRIEFING.md`: lines 4, 9, 15, 62, 63
- `orchestrator/DISPATCH.md`: lines 3, 4, 5, 8, 9, 11, 12, 13, 15
- `orchestrator/progress.md`: lines 8, 9
- `sentinel/BRIEFING.md`: lines 4, 8, 15, 16, 32
- `sentinel/handoff.md`: lines 4, 7
- `teamwork_preview_explorer_survey_1/BRIEFING.md`: lines 4, 9, 14, 15, 24
- `teamwork_preview_explorer_survey_1/DISPATCH.md`: lines 3, 4, 7, 8, 9, 11
- `teamwork_preview_explorer_survey_2/BRIEFING.md`: lines 4, 9, 58, 59
- `teamwork_preview_explorer_survey_2/DISPATCH.md`: lines 5, 6, 7, 11, 13, 17, 18
- `teamwork_preview_explorer_survey_2/progress.md`: lines 6, 7, 8
- `teamwork_preview_explorer_survey_3/BRIEFING.md`: lines 4, 9, 15, 16, 24, 25, 30
- `teamwork_preview_explorer_survey_3/DISPATCH.md`: lines 3, 4, 7, 8, 10, 11, 12, 14
- `teamwork_preview_explorer_survey_3/progress.md`: lines 7, 8, 10

---

## 4. Key Findings & Recommendations

1. **Agent Definition Baseline (`*.agent.md`)**:
   - The 15 existing agent definition files in `CoChem-BASE/.agents` already use sanitized tokens (`<COCHEM_ROOT>` and `<GDRIVE_ROOT>`). None contain raw user home or drive paths.
   - When overwriting from source (`<USER_HOME>\.gemini\config\agents`), the new files must be scrubbed to replace `<USER_HOME>` with `<USER_HOME>` and `<COCHEM_WORKSPACE>` with `<COCHEM_WORKSPACE>`.

2. **Acceptance Criteria Scope Warning**:
   - The project acceptance criteria state:
     - `Running a search for <USER_HOME> inside CoChem-BASE/.agents returns 0 results.`
     - `Running a search for <COCHEM_WORKSPACE> inside CoChem-BASE/.agents returns 0 results.`
   - If the verification tool or test script searches the *entire* `CoChem-BASE/.agents` directory (including subdirectories and `ORIGINAL_REQUEST.md`), those non-agent metadata files will trigger test failures unless sanitized or excluded during the final verification pass.

3. **Recommended Action Plan for Implementer**:
   - Overwrite all 15 `*.agent.md` files in `.agents/` with sanitized versions from source.
   - Decide whether metadata files (`ORIGINAL_REQUEST.md` and `.agents/*/*.md`) should also have absolute path strings sanitized or replaced with placeholders so that a global grep across `CoChem-BASE/.agents` yields strictly 0 hits.
