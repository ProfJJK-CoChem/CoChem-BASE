Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-SCRIBE\.in-progress\prompt_test_cochem_scribe_master.md.
Original prompt:
# Role and Context
You are a CoChem execution agent tasked with implementing Phase 4, Task 11 tests of the CoChem-SCRIBE orchestrator.

# Target Path
Repository Base: `D:\__CoChem\GitHub-Repo\CoChem-SCRIBE`
Target File: `core/test_cochem_scribe_master.py`

# Instructions
Implement the integration test for the `ScribeOrchestrator`.

1. **E2E Genuine Integration Test (Task 96):** In strict adherence to the **Zero-Mock Anti-Spoofing Protocol**, provide a complete, authentic End-to-End (E2E) pipeline test that executes the orchestrator normally (without `--dry-run`) via CLI using a genuine, minimal input dataset.
2. It must verify the true end-to-end generation of the final `.zip` archive without hitting real network APIs (configured via local file `--config-path`) but without spoofing the internal core logic or execution flow.

# Constraints
* Absolutely NO `unittest.mock`, NO `MagicMock`, NO monkeypatching of core internal logic.
* Use a local minimal file/HDF5 dataset instead of an API call to prevent hitting real network, but the steps (Harvest, Payload, Template, Compile, Zip) MUST run their real logic.
* You must verify the final `.zip` archive exists and is correctly permissioned.

Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.