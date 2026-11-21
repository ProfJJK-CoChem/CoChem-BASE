# From an XYZ file to an instructor handoff

In your public CoChem-BASE fork, open **Actions** and enable workflows if GitHub asks. Open **Student conformers (CREST, MACE, CPU PySCF)** and select **Run workflow** on the default branch. Leave **ethanol.xyz** selected for the first exercise. To study your own molecule, upload a single ASCII XYZ file to `examples/student_inputs/` on the default branch, then enter its filename in the workflow. Use only structures approved for public sharing. A public fork exposes committed molecules and workflow logs.

Each input contains 2–16 H, C, N or O atoms, coordinates in angstrom, and one neutral, closed-shell molecule. Supply a conventional XYZ atom count, comment line and one element and three coordinates per atom. Use letters, digits, hyphens or underscores in the filename. The workflow uses a GitHub-hosted CPU. Students need a GitHub account with write access to their fork and Actions enabled.

## Read the result

Use the [ethanol lab and worked comparison](ETHANOL_LAB.md) to calculate relative energies and interpret a bond-length change.

CREST uses the external xTB 6.7.1 binary and omits genetic crossing in this small-molecule classroom profile. The native log records that choice.

CREST 3.0.2 performs a bounded GFN2-xTB quick conformer search. The workflow retains the native ensemble, every separate candidate XYZ and the engine log. MACE-OFF24 medium evaluates energies and forces on those geometries using its pinned CPU checkpoint. It ranks by MACE single-point energy and sends the lowest candidate to CPU PySCF for an RHF/STO-3G geometry optimization with geomeTRIC. This small-basis result is a starting structure for further research. A local minimum requires a separate vibrational check. A quick search can miss conformers. The 32-frame limit fails visibly if more candidates are found.

Compare the CREST and MACE rankings in `ranking.json`. In `pyscf.json`, check SCF and optimizer convergence, energy in hartree and gradient in hartree/bohr. Compare the selected CREST geometry with `refined.xyz`. Which bonds or angles changed? Both candidate and refined geometries preserve atom order. The checkpoint is fetched from the [official academic model distribution](https://github.com/ACEsuit/mace-off) and its SHA-256 is checked before use.

## Submit to the instructor

1. Open the successful run summary and download **CoChem-student-handoff** under **Artifacts**.
2. Unzip the GitHub download once. It contains a `CoChem-…zip` and its matching `.sha256` file. Preserve the inner ZIP intact.
3. Open the shared Google Drive folder provided by your instructor, using your course Google account. Choose **New → File upload** and select both files. Check that both names appear, then provide the run URL with your submission. GitHub does not need access to your Drive.

## Receive for Pipeline 5.0.0

Download the pair from the course folder. Open the submitted run in the student's fork and copy the 64-character ZIP hash from the run summary. In a BASE checkout with Python 3.12, substitute that hash and your local paths in this command.

```sh
python student/handoff.py /path/to/CoChem-example.zip --expected-sha256 HASH_FROM_ACTIONS --stage /path/to/research-inbox
```

The receiver validates file membership, byte digests, atom order, the native CREST ensemble, the MACE selection and the converged PySCF result. It stages into a directory named for the ZIP SHA-256. The manifest records the producing repository, commit, run and attempt. `isomers/crest-NNN.xyz` supplies individual candidates. `refined.xyz` supplies the optimized candidate. `crest_conformers.xyz` is the native pool with energies in hartree. Retain the original ZIP alongside the run URL.

For a Pipeline 5.0.0 continuation, copy the received directory to storage accessible to the chosen Colab, GCP or workstation worker. Keep the ZIP digest with the research record. Point each research step at its selected `isomers/crest-NNN.xyz` or `refined.xyz` and record charge 0 and multiplicity 1 for this route. Choose the research method, resources and completion test, then submit through the instructor's normal SRS and manager queue. The instructor controls when the larger jobs start.
