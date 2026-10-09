The optional `cochem-cfour-h-o-junchs-basis-v1` profile is a separately sealed
copy of the approved CFOUR 2.1 installation. The original licensed installation
is verified before and after derivation and remains untouched. The profile
retains every original binary, helper, library and ECP file, and binds a new
complete inventory to the exact augmented binary-adjacent GENBAS.

The reviewed addon combines public Basis Set Exchange version-0 H/O
`jun-cc-pV(T+d)Z` and `jun-cc-pV(Q+d)Z` entries and O `cc-pwCVTZ` with the
approved native H `PWCVTZ` block. Native H `PWCVTZ` is numerically identical to
native H `PVTZ`; hydrogen has no core and BSE has no H weighted-core entry.
Requested H/O seasonal basis headers are mapped to `jun-cc-pVTZ` and
`jun-cc-pVQZ`; all numerical tokens remain unchanged. The tight-d extension in
the published seasonal naming applies to second-row elements, which this H/O
profile does not admit. The original inventory and mixed-provenance addon are
retained under the derived installation's `provenance/` directory. They remain
private licensed artifacts; do not publish or bundle the native H block or
derived GENBAS with public source.

The independently pinned derived inventory is
`1177884eeb859d9a3a332aa9d7781eab69cf3a8346982b872f1626c16dc21961`.
The addon SHA-256 is
`c2672f678dc3daf75ffb3ce198615ade4a5f4fc1778b93a35c5fc35ee93ecf3c`.
Unknown profiles, changed addon bytes, changed native files, and unrecorded
files fail verification. This establishes provisioning identity and native
startup only; calculations and scientific reference comparisons remain
separate requirements.

After obtaining the exact reviewed addon as a private local artifact, create a
fresh installation outside the source checkout:

```sh
python -m scripts.provision_cfour_basis_profile \
  --parent /absolute/path/to/approved/cfour \
  --addon /absolute/path/to/private/reviewed-addon.GENBAS \
  --install-root /absolute/path/to/new/cfour-h-o-junchs
```

Select the derived `bin/xcfour` process locally and rerun BASE Stage 0. A runtime
registry created for the original installation does not authorize the derived
seal. The existing original provisioning script continues to accept only the
unchanged original distribution.

Public source authority: [Basis Set Exchange API](https://molssi-bse.github.io/basis_set_exchange/web_api.html).
Exact versioned source URLs and SHA-256 values are retained in the code-level
`BASIS_PROFILE` identity; the three BSE `.cfour` source files were downloaded
over verified TLS and preserved before conversion. H/O scope must be reviewed
again before adding another element.
