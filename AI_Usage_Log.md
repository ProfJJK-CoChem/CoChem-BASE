# CHEM 312L AI Usage & Provenance Log (`AI_Usage_Log.md`)

- **Course:** CHEM 312 / 312L — Organic Chemistry II Laboratory (Cumberland University)
- **External Spectroscopy Collaborator:** Tennessee Tech University (CP-FTMW Microwave Spectroscopy)
- **Team / Student Name:** _(fill in your name and Team ID, e.g., Team 1)_
- **Assigned Molecule / Reaction Track:** _(fill in your assigned molecule, complex, and NAS reaction)_
- **Public Fork URL:** `https://github.com/<your-username>/CoChem-BASE`

---

## Course Policy Summary

1. **Disclose every AI tool** (e.g., ChatGPT, Claude, Gemini, GitHub Copilot) used for writing help, debugging CLI commands, plotting, or literature study.
2. **Never fabricate or alter measured or computed data.** Every reported energy, vibrational frequency, barrier height, rotational constant, and SHA-256 hash in your Milestone PDFs (`M1`–`M4`) must come verbatim from your verified public-fork GitHub Actions runs, Codespace script outputs, or wet-lab Nicolet iS50 ATR-FTIR (`0.5 cm^-1`) spectra.
3. **Commit this file** (`AI_Usage_Log.md`, exact casing) in your public `CoChem-BASE` fork and attach/include it with every Canvas milestone submission (`M1`–`M4`). If you used **no AI tools** for a milestone, record `"None"` explicitly in the table below.

---

## Milestone AI Disclosure Table

| Milestone | Date (YYYY-MM-DD) | AI Tool & Model (or `None`) | Purpose / Prompt Summary | Verification Performed by Student |
| --- | --- | --- | --- | --- |
| **M1** (Conformers & Harmonics) | | | | Verified against `student_conformers.yml` Run URL & `handoff.json` SHA-256 |
| **M2** (ATR-FTIR & KK Correction) | | | | Verified against Nicolet iS50 CSV & `scripts/kk_atr_correct.py` JSON SHA-256 |
| **M3** (GVPT2, Fermi, NCI BSSE) | | | | Verified against `04_crest_nci_dimer_bsse.yml`, `05_gvpt2_6shard_anharmonic.yml`, & `scripts/fermi_deperturb.py` |
| **M4** (NAS, SPCAT 8–18 GHz, FactLedger) | | | | Verified against `06_aimnet2_neb_pyscf_rxn_profile.yml`, `07_spcat_8_18ghz_prediction.yml`, & `scripts/fact_ledger.py --verify` |

---

## Student Attestation

I certify that this log accurately discloses all AI assistance used during CHEM 312L, and that every scientific number, figure, and SHA-256 checksum reported in my Milestone PDFs and `cochem.student-handoff/2` bundles originates directly from verified calculations or laboratory measurements.

- **Signed (Typed Name & Date):** _`<Your Name>, <YYYY-MM-DD>`_
