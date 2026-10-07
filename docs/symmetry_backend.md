# Molecular symmetry backend

Install the optional, tested MolSym backend for point-group classification:

```sh
python -m pip install '.[symmetry]'
```

The extra pins [MolSym 1.2.0](https://github.com/NASymmetry/MolSym). Its actual
classification and operation tables are tested against water (C2v), methane (Td),
benzene (D6h), and linear carbon dioxide (D0h). This checks molecular symmetry,
not electronic-structure or spectroscopic accuracy.

`analyze_molecular_symmetry` raises `SymmetryBackendUnavailableError` when MolSym
is unavailable and `SymmetryAnalysisError` when the requested calculation fails.
It does not infer a complete point group from planarity or inertia degeneracy.
Center-of-mass, inertia, Eckart alignment, and vibrational projection functions
operate independently of this optional backend.

MolSym 1.2.0 supplies linear point-group classification, but its finite character
table constructor does not handle infinite groups. Linear results therefore
identify the group and rotational symmetry number while recording the unavailable
character table in `unavailable_properties`. Complex character tables that cannot
be represented by the result's real-valued schema are similarly marked unavailable.
Requested coordinate symmetrization failures are explicit.

Nuclear spin statistical weights require separate spin/permutation calculations.
They remain empty and explicitly unavailable; the rotational symmetry number is
not used to invent those weights.
