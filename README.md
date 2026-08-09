# CoChem-BASE

**CoChem-BASE** is the central hardware-aware orchestrator for the CoChem computational chemistry suite.

It is responsible for:
- Executing the 10-Tier Temporal Wall Clock matrix via `asyncio`.
- Dynamically profiling hardware (CUDA vs CPU) and managing MLFF fallbacks (e.g., swapping `MACE-OFF24m` for `g-xTB` on CPU nodes).
- Initializing and managing the `cochem_state.h5` tensor, bypassing all flat JSON I/O bottlenecks.
- Scrubbing computational keywords (e.g., dynamically suppressing BSSE Counterpoise when TightPNO DLPNO-CCSD(T) is requested).
- Pre-flight schema validation across `TOPOS`, `TORQ`, `SpycFit`, and `SCRIBE` to prevent mid-pipeline crashes.

## Usage
Please refer to the authoritative [CoChem Master User Manual](CoChem_Master_User_Manual.md) for full execution instructions across the entire 5-module pipeline.