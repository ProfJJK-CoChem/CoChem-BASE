# Additional review of the student kit and test allowances

The merge preserves incoming main
`11c7399a13f7d134ac80e1966d5a65c071ac6459`, including its two commits after
`587403de61feefd50ad3cfe6fbac58d3a683fce2`, in Git history. Both independent
reviews researched the original Chunk 17 and proposal requirements before
deciding the four changed paths.

Three incoming CI paths refresh the hash allowance for intercepted GUI
callbacks and test that allowance. These paths are already physically retired
from the selected implementation. Proposal sections 4.1 and 6.1.6 prohibit
monkeypatched execution; the new allowance does not satisfy that requirement.
The canonical implementation keeps its real process, failure-admission and
browser checks without reactivating those allowances.

The fourth path advances the separate manual TOPOS kit and its source/wheel
digests. Its exact bytes are preserved in
[this expert inspection catalog](../scripts/module-distribution-expert-main-11c7399a.json),
SHA-256 `0aed855ced49f37bd713c4b9cf8730385fde4cf1ceaa75d9a80b7c0274f99357`.
The selected automatic TOPOS and TORQ providers and BASE scientific source pin
remain unchanged from `1ce8a3b256704c4c006da81ca57ff82f1a17da9a`.
The inspection catalog establishes provenance, not compatibility or scientific
acceptance.

Only this document, that inspection catalog and its explicit infrastructure-ring
entry are added. Production, GUI, CI driver and selected-test source bytes remain
identical to the tested scientific candidate. The earlier
[integration review](Incoming_Main_587403de_Review.md) and
[conformance trace](SRS_Student_1_1_Conformance_Trace.md) retain the applicable
architecture decisions and acceptance limits.
