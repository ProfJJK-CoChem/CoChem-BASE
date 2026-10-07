# Product B structure ingestion

These two inputs describe the same ordered GaAs primitive cell. The JSON stores
lattice vectors as rows in an explicit laboratory frame. CIF stores cell lengths
and angles, so its Cartesian orientation is chosen by ASE during parsing. The
cell metric, fractional positions, atom identities and volume agree; a CIF file
does not define the JSON file's original Cartesian orientation.

The chosen 5.65 Å conventional lattice constant is an illustrative input. These
files are ingestion examples, not experimental references or an accuracy claim.
BASE validates the input, preserves its provenance, prepares a PAW request and
hands it to the shared execution service or a downstream module.

```python
import json
from pathlib import Path
from cochem_base.calc.periodic import ingest_periodic_structure

structure = ingest_periodic_structure("examples/product_b/gaas_fractional.json")
print(structure.cell_angstrom, structure.coordinates_fractional)
print(structure.source.source_sha256)

# Use the manifest from the pinned free QE/PAW installer. Runtime paths belong
# outside the checkout. These are actual file hashes, not publisher signatures.
manifest = json.loads(Path("/workspace/cochem-silos/qe/installation-manifest.json").read_text())
pseudos = {symbol: {"path": entry["path"], "sha256": entry["sha256"]}
           for symbol, entry in manifest["pseudopotentials"].items()}
request = structure.to_calculation_config({"pseudopotentials": pseudos})
Path("/workspace/cochem-runtime/gaas-request.json").write_text(json.dumps(request, indent=2))
```

`gaas_ordered.cif` uses the same parser API. Upload consumers can call
`parse_periodic_structure(contents, format="cif", filename="structure.cif")`.
JSON requires a schema version, coordinate system, coordinate units, cell units
and all three periodic boundaries. Fractional coordinates are dimensionless;
Cartesian coordinates and cell lengths may be in Å or bohr. Conversion uses the
canonical CODATA conversion and preserves the cell frame; molecular COM/Eckart
alignment is not applied. The source hash covers the original bytes. A second
digest binds the converted structure to its source record and is checked again
before any executable deck is written.

The ingestor rejects ambiguous JSON keys, multiple CIF blocks, unresolved site
disorder, partial/unknown occupancies, missing/nonfinite/singular/left-handed
cells, and lattice-equivalent duplicate atoms. The PAW execution validator also
rejects pseudopotential digest, element, PAW flag, XC functional, spin-orbit and
recommended-cutoff contradictions. It never substitutes a different species or
pseudopotential.

The existing native calculation is a neutral closed-shell PBE PAW singlepoint.
Its converged energy and forces can be retained as engine evidence. Band-gap or
equilibrium-lattice accuracy remains unassessed until a downstream workflow
provides the required independent reference comparison.
