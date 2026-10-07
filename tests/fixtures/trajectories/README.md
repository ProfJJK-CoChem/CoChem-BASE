`xtb-6.7.1-water-optimization.xyz` is the unmodified `xtbopt.log` from an actual
xTB 6.7.1 (`edcfbbe`) water optimization performed in this cloud environment.
The five frames contain native xTB energies in Hartree and coordinates in
Angstrom, not generated reference energies.

Original artifact:
`/workspace/cochem-runtime/chain-pass2-jt1upcd8/campaign/xtbopt.log`

Recorded program call in the companion `s1_xtb.out`:
`/workspace/cochem-silos/xtb/xtb-dist/bin/xtb water.xyz --opt vtight --strict --chrg 0 --uhf 0`

SHA-256:
`9338f7e83af9c64b32baecab821c42080ea9c88f231a4dbcdb2c1e74c90607de`

This fixture verifies parsing and transport of recorded results. Replaying it
does not constitute another live engine calculation or validate ORCA execution.
