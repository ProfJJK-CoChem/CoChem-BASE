# Agent Configuration Directory Analysis Report

**Date**: 2026-08-11
**Source Directory**: `<USER_HOME>\.gemini\config\agents`
**Target Directory**: `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`
**Explorer Agent**: `teamwork_preview_explorer_survey_1`

---

## 1. Executive Summary

A comprehensive survey of the source directory `<USER_HOME>\.gemini\config\agents` was conducted. The directory contains **15 agent configuration files** (all formatted as Markdown with YAML frontmatter, matching pattern `*.agent.md`). There are **0 subdirectories**. The total file size of all 15 files is **48,294 bytes (48.3 KB)**.

All 15 files are valid Antigravity agent definition files that specify system prompts, capabilities, write permissions, subagent orchestration flags, MCP tool access, and authoritative knowledge sources.

---

## 2. Directory Structure & Inventory

### Directory Summary
- **Path**: `<USER_HOME>\.gemini\config\agents`
- **Total Subdirectories**: 0
- **Total Files**: 15
- **Aggregate Size**: 48,294 bytes

### Detailed File Inventory Table

| # | Filename | Size (Bytes) | Lines | Agent Name (`name`) | Enabled Tools Flags |
|---|---|---|---|---|---|
| 1 | `0rchestrator.agent.md` | 4,979 | 61 | `0rchestrator` | write: true, subagent: true, mcp: true |
| 2 | `artist.agent.md` | 2,208 | 39 | `Artist` | write: true, subagent: false, mcp: true |
| 3 | `cochem-audit.agent.md` | 3,582 | 56 | `cochem-audit` | write: true, subagent: false, mcp: true |
| 4 | `cochem-coder.agent.md` | 3,770 | 56 | `cochem-coder` | write: true, subagent: false, mcp: true |
| 5 | `cochem-debug.agent.md` | 3,135 | 49 | `CoChem-Debug` | write: true, subagent: false, mcp: true |
| 6 | `cochem-helper.agent.md` | 3,598 | 53 | `cochem-helper` | write: true, subagent: false, mcp: true |
| 7 | `cochem-improve.agent.md` | 3,284 | 49 | `CoChem-Improve` | write: true, subagent: false, mcp: true |
| 8 | `cochem-scribe.agent.md` | 2,654 | 46 | `cochem-scribe` | write: true, subagent: false, mcp: true |
| 9 | `cochem-sdp_manager.agent.md` | 4,690 | 59 | `cochem-sdp_manager` | write: true, subagent: false, mcp: true |
| 10 | `cochem-tester.agent.md` | 2,701 | 42 | `cochem-test` | write: true, subagent: false, mcp: true |
| 11 | `educator.agent.md` | 3,130 | 45 | `educator` | write: true, subagent: false, mcp: true |
| 12 | `researcher.agent.md` | 2,763 | 46 | `Researcher` | write: true, subagent: false, mcp: true |
| 13 | `teacher.agent.md` | 2,618 | 41 | `teacher` | write: true, subagent: false, mcp: true |
| 14 | `ui.agent.md` | 2,917 | 43 | `UI` | write: true, subagent: false, mcp: true |
| 15 | `web_mcp.agent.md` | 2,265 | 38 | `Web_MCP` | write: true, subagent: false, mcp: true |

---

## 3. Configuration & Associated File Analysis

### File Schema & Structure
Each `.agent.md` file follows the standard Antigravity agent specification structure:
1. **YAML Frontmatter** (bounded by `---`):
   - `name`: String identifier for the agent role
   - `description`: Single/multi-line summary of agent capabilities and responsibilities
   - `argument-hint`: User guidance prompt string
   - `enable_write_tools`: Boolean (all set to `true`)
   - `enable_subagent_tools`: Boolean (set to `true` for `0rchestrator`, omitted/false for others)
   - `enable_mcp_tools`: Boolean (all set to `true`)
2. **Markdown Body**:
   - `# IDENTITY AND ROLE`: Defines the core persona and scope
   - `# AUTHORITATIVE KNOWLEDGE SOURCES`: Lists primary reference manuals and matrix files
   - `# CORE DIRECTIVES`: Specific workflow rules, steps, and operational guidelines

### Path Analysis in Source Files
All 15 source files contain hardcoded absolute path references under the `# AUTHORITATIVE KNOWLEDGE SOURCES` section pointing to local user paths:
- `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\Method_Matrix.md`
- `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\CoChem_User_Manual.md`
- `<COCHEM_WORKSPACE>\GitHub-Repo\Resources`
- `<GDRIVE_ROOT>\__Books`
- `<COCHEM_WORKSPACE>\GitHub-Repo\Resources\PMBOK-2021` (in `0rchestrator` and `cochem-sdp_manager`)
- `<COCHEM_WORKSPACE>\GitHub-Repo\Resources\SWEBOKv3-published` (in `0rchestrator` and `cochem-sdp_manager`)

*Note for downstream implementation*: In requirement R2 of `ORIGINAL_REQUEST.md`, these absolute paths must be sanitized when overwriting into `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`, replacing `<COCHEM_WORKSPACE>` with `<COCHEM_WORKSPACE>` and scrubbing any `<USER_HOME>` user home references.

---

## 4. Cross-Reference with Target Directory

Comparison with `<COCHEM_WORKSPACE>\GitHub-Repo\CoChem-BASE\.agents`:
- Target directory currently contains 14 agent `.agent.md` files plus subdirectories (`orchestrator`, `sentinel`, `teamwork_preview_explorer_survey_1..3`) and `ORIGINAL_REQUEST.md`.
- All 15 source files in `<USER_HOME>\.gemini\config\agents` are the updated, complete set of fixed agent configurations ready for deployment.
