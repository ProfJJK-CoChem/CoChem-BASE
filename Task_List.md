# CoChem-BASE Prompt Ingestion Orchestration WBS

**Objective**: Ingest 78 prompts from `D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.prompts` into code inside `D:\__CoChem\GitHub-Repo\CoChem-BASE` using a Python State Machine Orchestrator to comply with the N>1 delegation boundary rule.

## Phase 1: Python State Machine Orchestrator Development
- [x] **Task 1.1: Design state machine architecture for prompt processing pipeline.** (Agent: `cochem-architect`)
    - [x] Sub-task 1.1.1: Define strict kanban states (e.g., `PENDING`, `RESEARCHING`, `CODING`, `AUDITING`, `REFINING`, `COMPLETED`, `COUNCIL_REVIEW`, `FAILED`). (Agent: `cochem-architect`)
    - [x] Sub-task 1.1.2: Specify transition logic for 10-cycle TDD loops within the `CODING` state, explicitly defining a fallback transition to `COUNCIL_REVIEW` or `FAILED` if the loop exhausts 10 cycles without passing tests. (Agent: `cochem-architect`)
    - [x] Sub-task 1.1.3: Design error-handling, fallback state transitions for failed audits, and strict state isolation logic (hard clearing of context between prompts). (Agent: `cochem-architect`)
- [x] **Task 1.2: Implement core Python State Machine orchestration script.** (Agent: `python-developer`)
    - [x] Sub-task 1.2.1: Initialize state machine framework (e.g., `transitions` library). (Agent: `python-developer`)
    - [x] Sub-task 1.2.2: Implement directory scanning for `D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.prompts` to queue the 78 items sequentially. (Agent: `python-developer`)
    - [x] Sub-task 1.2.3: Implement headless CLI execution wrappers for `agy` to spawn appropriate agents per state (Research, Coding, Audit, Improve). (Agent: `python-developer`)
    - [x] Sub-task 1.2.4: Implement strict agent lifecycle management to kill the previous state's agent *before* spawning the agent for the next state, preventing state leaks. (Agent: `python-developer`)
    - [x] Sub-task 1.2.5: Implement file moving logic to transfer successfully completed prompts to `.finished_coding_prompts`. (Agent: `python-developer`)
- [ ] **Task 1.3: Adversarial audit and validation of the Orchestrator Script.** (Agent: `cochem-audit`)
    - [ ] Sub-task 1.3.1: Conduct security, robustness, and state-leakage audit on the orchestration script, validating immutable state transitions. (Agent: `cochem-audit`)
    - [ ] Sub-task 1.3.2: Elevate issues to council if orchestrator design violates the Zero-Mock mandate or N>1 rules. (Agent: `cochem-council`)
    - [ ] Sub-task 1.3.3: Apply refinements to orchestrator script based on council feedback. (Agent: `cochem-improve`)

## Phase 2: Orchestrated Prompt Processing (Iterated 78x via State Machine)
*Note: The following tasks represent the state machine lifecycle for a SINGLE prompt. The Orchestrator script dynamically invokes agents for these steps, executing one prompt entirely before moving to the next.*

- [ ] **Task 2.1: Prompt Analysis & Context Gathering** (Agent: `researcher`)
    - [ ] Sub-task 2.1.1: Read target prompt from the `.prompts` directory. (Agent: `researcher`)
    - [ ] Sub-task 2.1.2: Cross-reference prompt with `Software Requirements Specification (SRS) - CoChem-BASE`. (Agent: `researcher`)
    - [ ] Sub-task 2.1.3: Cross-reference prompt requirements with the method matrix. (Agent: `researcher`)
    - [ ] Sub-task 2.1.4: Elevate to Agent Council if specifications are missing or ambiguous. (Agent: `cochem-council`)
- [ ] **Task 2.2: TDD Code Generation (Strict Zero-Mock)** (Agent: `python-developer`)
    - [ ] Sub-task 2.2.1: Write initial unit tests for prompt specifications. Tests MUST test physical integrations/implementations; absolutely no mocks (`unittest.mock`, `pytest-mock`, etc.) allowed as per the Zero-Mock mandate. (Agent: `qa-engineer`)
    - [ ] Sub-task 2.2.2: Execute up to 10-cycle TDD loops to write code satisfying the tests in `D:\__CoChem\GitHub-Repo\CoChem-BASE` (physical testing only). If 10 cycles fail, elevate to `COUNCIL_REVIEW`. (Agent: `python-developer`)
    - [ ] Sub-task 2.2.3: Finalize code draft for audit. (Agent: `python-developer`)
- [ ] **Task 2.3: Adversarial Audit & Council Elevation** (Agent: `cochem-audit`)
    - [ ] Sub-task 2.3.1: Perform adversarial static analysis and logical review on the generated code. (Agent: `cochem-audit`)
    - [ ] Sub-task 2.3.2: If issues are found, elevate to Agent Council for resolution strategies and procedural review. (Agent: `cochem-council`)
    - [ ] Sub-task 2.3.3: Implement Council-recommended fixes and refinements. (Agent: `cochem-improve`)
- [ ] **Task 2.4: Completion & Cleanup** (Agent: `orchestrator`)
    - [ ] Sub-task 2.4.1: Declare prompt execution officially finished after passing adversarial audit. (Agent: `cochem-audit`)
    - [ ] Sub-task 2.4.2: Move the prompt markdown file to `D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.finished_coding_prompts`. (Agent: `orchestrator-script`)
    - [ ] Sub-task 2.4.3: Ensure the final agent from the audit/improve phase is killed, strictly enforcing full context clearing before the orchestrator pulls the next prompt. (Agent: `orchestrator-script`)
