# Audited AIMNet2 CPU inference

Stage 0 supports a separate `cochem_aimnet2_silo` using the official Python
distribution **`aimnet==0.2.0`**, not the obsolete `aimnet2calc` package name.
Request that silo explicitly in the deployment manifest's `requested_silos`
list. `COCHEM_AIMNET2_SILO` optionally selects its absolute installation path.
The core silo remains mandatory. Skipping heavy silos also skips AIMNet2.

The CPU profile has a closed, 52-package dependency lock, including
`torch==2.8.0+cpu`, `warp-lang==1.18.0`, and
`nvalchemi-toolkit-ops==0.4.1`. Its Torch wheel uses the independently checked
official wheel URL and SHA-256 shared with the MACE CPU provisioner. The
AIMNet2 silo contains neither MACE nor the TOPOS controller distribution.

The provisioner creates an isolated Python 3.12 Linux x86-64 environment,
installs only exact pins without dependency re-resolution, retains pip download
reports, checks package consistency and interpreter isolation, and performs a
bounded native CPU tensor/autograd probe. AIMNet, Warp, and nvalchemi import
origins must remain inside the silo. Warp's startup banner is retained outside
the structured native-probe JSON. Existing package drift is rejected; an
existing installation is not silently repaired or replaced.

This probe establishes native CPU loading, not neural-potential accuracy or
GPU availability. No model weights are downloaded by BASE. TOPOS supplies
explicit model files and hashes, validates the requested physical domain,
and compares the installed worker distribution against its exact controller
source. The separate `cochem-topos-ml-worker` wheel may be installed only after
its declared dependencies are present; it must not share a namespace with a
`cochem-topos` controller installation in this silo.

After the genuine eleven-phase Stage 0 setup completes, the registry binds
`engines.aimnet2` to this silo's interpreter, package version, executable hash,
and exact package lock. Do not modify the registry manually to enroll an
engine. Production inference must pass BASE execution authority and TOPOS's
request/model/worker checks. A prior direct calculation outside BASE is useful
scientific evidence but does not establish this execution authority.

To exercise the actual already-provisioned environment:

```sh
COCHEM_TEST_AIMNET_SILO=/absolute/path/to/cochem_aimnet2_silo \
  python -m pytest -q tests/base/test_aimnet_cpu_lock.py
```

The optional native test does not create a pretend engine when the silo is
absent. A complete TOPOS acceptance run separately evaluates all declared
committee members through the authenticated worker and retains the resulting
energies, forces, member spread, raw process logs, and authority receipt.
