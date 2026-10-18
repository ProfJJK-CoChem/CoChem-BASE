# Module ownership inspection evidence

These are static inspection receipts for the
[module ownership audit](../../Module_Ownership_Audit_2026-10-18.md), not native
calculation results or completed migration acceptance.

The original BASE source observations use commit
`d423c02a5bf9f15dd9626d46e17b6650414633c1`. The repository may have advanced by
the time this documentation is published. Canonical repository `main` observations
are explicitly dated 2026-10-18 and bound to the full commits in the JSON.
The later revision recheck compares those original members with immutable
`2c655b47b1cc63eca3ab417946513c9763b0933e`; it does not reclassify the original
observations as runtime acceptance on that later source.

| File | What it establishes | SHA-256 |
| --- | --- | --- |
| [tracked-source-inventory.json](tracked-source-inventory.json) | Independent agent's tracked BASE file groups, source hashes, static imports and byte-identical paired TOPOS trees. Copied unchanged from its inspection output. Names/imports do not alone establish reachability or canonical scientific divergence. | `16a6a06546bb8d4a6d0221409eb792aa048434ebcef9416e787bde766409185d` |
| [base-torq-package-overlap.json](base-torq-package-overlap.json) | Every shared Python path between BASE's audited package-directory mappings and the existing pinned TORQ wheel, with both byte hashes: 115 paths, 37 different. Includes the exact TORQ wheel hash. | `3567bd290f95f5175f7356dd7dc7a274a13dbb4b11fd53ea0e4b2b3e61bad9a7` |
| [canonical-source-observations.json](canonical-source-observations.json) | Public visibility observation, reviewed pins, observed main commits and hashes of the canonical packaging/integration files inspected. | `6cef1a0b938fd73395fafdada84532da4024035bb5c80c4ec02fd32fe8576028` |
| [revision-recheck-2c655b4.json](revision-recheck-2c655b4.json) | Static comparison of all 107 inventory members, packaging, adapters and all 115 prior overlap paths against `2c655b4`. Ownership findings persist; the public-source credential prerequisite has been corrected. | `237d4a29245a660c9b10cc6e0a39ab8ca905f8aa1f3d6b20882f7074516574de` |

The overlap comparison reads the package-directory mapping from BASE's immutable
`pyproject.toml`, maps tracked Python source files to their candidate installed
paths, and compares those paths with Python members of the retained canonical
TORQ wheel. It is not a fresh BASE wheel build. Its 115-path count excludes
non-Python resources, dependency distributions and paths not shared by those two
inputs. Each row retains BASE's actual tracked source path so another auditor
can reconstruct the comparison without relying on a local checkout path.

The retained TORQ wheel belongs to the reviewed revision
`4ce8eecba56e91e27c6abb32473b2ee4d44767c4`; its SHA-256 is recorded in the
overlap JSON. The wheel itself is not included here. The original source
inventory's transient location was `/tmp/cochem-module-duplication-inventory.json`;
the checked-in copy is the durable evidence. No temporary environment path is
needed to read these reports.

An independent documentation review rechecked all **107 source member hashes**
in the inventory against `git show` at the recorded BASE commit. It also checked
the 92-file namespace total, the unchanged copied inventory digest and the
preservation of BASE's SRS duties. This was source verification, not an import or
scientific execution test.

No tests, provider imports or chemistry runs were performed for this ownership
inspection. Existing integration/chemistry receipts are separate evidence and
must not be reinterpreted as acceptance of a migration that has not happened.
