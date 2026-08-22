Perform adversarial static analysis and logical review on implemented code for D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BASE\.in-progress\Doc5_01_phase1_audit_prompt.md.
Original prompt:
# Context
You are tasked with writing the setup orchestration script `cochem_setup_phase_1.py` for CoChem-BASE.

# Goal
Create `cochem_setup_phase_1.py` to perform Phase 1: OS & Hypervisor Audit.

# Requirements
- Programmatically verify the existence of OS-level toolchains (`gcc`, `make`, `git`).
- Perform a hard exit if a WSL2 9P mount is detected (e.g., `/mnt/c/`). Workspaces must be mapped to native `ext4` or `xfs` filesystems to guarantee POSIX compliance and I/O performance.
- Inspect the Linux kernel's virtual memory limits by evaluating `vm.max_map_count` and attempting an `ulimit -s` (stack auto-expansion). This prevents massive deep wave-function matrices from triggering arbitrary segmentation faults due to stack overflow.
- Ensure the script is idempotent and uses isolated, stateless execution.

# Constraints
- Target filepath: `D:\__CoChem\GitHub-Repo\CoChem-BASE\orchestrator\cochem_setup_phase_1.py`
- DO NOT use any mocks, stubs, or placeholder values in your code. Write real implementation logic.
- Ensure strict adherence to the Tripartite Workspace Air-Gap and Method Matrix rules.

Modified files content:

Validate Zero-Mock adherence. Target repo is D:\__CoChem\GitHub-Repo\CoChem-BASE.