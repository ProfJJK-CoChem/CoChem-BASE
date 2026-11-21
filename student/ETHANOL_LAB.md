# Ethanol conformer lab

Starting from one ethanol geometry, find low-energy shapes, compare two energy rankings and submit a reproducible result to your instructor. You need a GitHub account, your own public fork with Actions enabled, and the course Google Drive link.

## Run the calculation

1. Open **Actions → Student conformers (CREST, MACE, CPU PySCF)** in your fork. Click **Run workflow**, choose `main`, and leave `ethanol.xyz` selected. [Workflow and student guide](README.md)
2. Open the finished run. Download the **CoChem-student-handoff** artifact and unzip the GitHub download once. Keep the inner ZIP and matching `.sha256` together. Extract a second copy of the inner ZIP to examine its contents.
3. Read the three outputs below. Compare energies within each method. GFN2-xTB, MACE and RHF use different energy models, so each ranking needs its own zero.

| File | Question it answers |
| --- | --- |
| `crest_conformers.xyz` and `isomers/*.xyz` | Which structures did CREST find with its quick GFN2-xTB search? Each frame has a recorded energy in hartree. |
| `ranking.json` | How did MACE-OFF24 medium score each of those same geometries? The lowest MACE single-point energy determines which file continues. |
| `pyscf.json` and `refined.xyz` | Where did the selected geometry end up after CPU RHF/STO-3G optimization? Check both the geometry and SCF convergence flags. |

## Interpret your run

- Record the candidate count and the lowest-energy filename for each ranking. For each method, subtract the lowest energy from every energy. Multiply the differences in hartree by 627.5095 to obtain kcal/mol.
- Measure the C–O bond between atoms 2 and 3 in the selected XYZ and in `refined.xyz`. Use the distance between the atoms. Their absolute positions can move when a molecule is reoriented.
- Explain why the two methods can select different candidates, and what additional calculation would test whether the refined geometry is a minimum. Consider how the quick search limits the set of structures you examined.

## Worked comparison from the public pilot

| CREST candidate | Relative GFN2-xTB energy (kcal/mol) | Relative MACE energy (kcal/mol) |
| --- | ---: | ---: |
| 001 | 0.000 | 0.119 |
| 002 | 1.306 | 1.050 |
| 003 | 1.551 | 0.000 |
| 004 | 3.596 | 3.007 |

CREST ranked 001 first. MACE selected 003. Its C–O bond length changed from 1.41269 Å to 1.43555 Å in PySCF. Both convergence checks passed, and the final RHF/STO-3G energy was −152.132674885361 hartree. A vibrational calculation would test for imaginary frequencies. This pilot recorded no Hessian. Report the values and filenames from your own run. [Verified pilot run](https://github.com/ansacs/CoChem-BASE/actions/runs/44848425878)

## Submit

Upload the unopened inner ZIP and its matching `.sha256` to the shared Google Drive folder in your assignment. Open that folder again to confirm that both files are present. Include the GitHub run URL with your write-up so your instructor can check the producing revision and digest. The instructor can retrieve every CREST structure and the refined geometry from this one bundle. [Instructor receiving instructions](README.md#receive-for-pipeline-500)
