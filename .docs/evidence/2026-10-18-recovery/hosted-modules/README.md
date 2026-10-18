# Hosted TOPOS/TORQ installation and geometry handoff

Run [39092523800](https://github.com/ProfJJK-CoChem/CoChem-BASE/actions/runs/39092523800), attempt 1, completed successfully at BASE `9ce098e91c948ef4f384ecef91441ea84cbec80e` on 18 October 2026. It installed reviewed TORQ `4ce8eecba56e91e27c6abb32473b2ee4d44767c4` and TOPOS `b157b7e210aee5bdfa09c22270d77d794f52cdde`, then executed TOPOS structural geometry analysis for the unchanged committed three-atom water input.

The production client verified all 16 downloaded artifact members and reopened the retained results successfully. `original-results/` preserves all 16 unchanged artifact members, including their original complete publication manifest. `selected-evidence.json` inventories the artifact members and additional verification receipts. `hosted-module-readback.json` records the additional source, graph and provenance checks. TOPOS's executed provider hash also matches the separately fetched canonical pinned source.

An optional source credential was available to the workflow. This run does not establish credential-free hosted access. No ORCA/CFOUR calculation was requested; both licensed-engine installation steps were skipped. This is module installation and a structural graph check, not electronic-energy accuracy, all-module-operation validation, or a student-owned Codespace/App pilot.

The reports retain TOPOS's wheel hash and installed-distribution file hash, and the verified TORQ installation-receipt hash. Complete environment hashes and TORQ's wheel hash were not exported by this workflow. No runtime environments or archives are distributed in this evidence.
