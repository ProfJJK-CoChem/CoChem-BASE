import sys

from cochem.concurrency.subprocess_broker import SubprocessBroker


def test_tripartite_path_resolution(tmp_path):
    import os
    custom_scratch = tmp_path / "custom_scratch"
    custom_store = tmp_path / "custom_store"
    custom_scratch.mkdir()
    custom_store.mkdir()

    old_scratch = os.environ.get("COCH_SCRATCH")
    old_store = os.environ.get("COCH_STORE_DIR")
    os.environ["COCH_SCRATCH"] = str(custom_scratch)
    os.environ["COCH_STORE_DIR"] = str(custom_store)
    try:
        broker = SubprocessBroker(engine_name="test_engine")
        assert broker.base_scratch_dir == custom_scratch.resolve()
        assert broker.store_dir == custom_store.resolve()
    finally:
        if old_scratch is None:
            os.environ.pop("COCH_SCRATCH", None)
        else:
            os.environ["COCH_SCRATCH"] = old_scratch
        if old_store is None:
            os.environ.pop("COCH_STORE_DIR", None)
        else:
            os.environ["COCH_STORE_DIR"] = old_store

def test_sanitize_remediation_scratch_purges_transients(tmp_path):
    scratch = tmp_path / "scratch_remediate"
    scratch.mkdir()

    # Create various dirty transient files
    (scratch / "calc.tmp.01").write_text("temp", encoding="utf-8")
    (scratch / "orca.scfp_tmp.bin").write_text("scfp", encoding="utf-8")
    (scratch / "calc.prop.txt").write_text("prop", encoding="utf-8")
    (scratch / "run.lock").write_text("lock", encoding="utf-8")
    (scratch / "vib.hess").write_text("hess", encoding="utf-8")
    (scratch / "electron.densities").write_text("dens", encoding="utf-8")
    (scratch / "orbitals.gbw").write_text("gbw", encoding="utf-8")
    (scratch / "input.inp").write_text("! B3LYP", encoding="utf-8")

    # Case 1: preserve_gbw = False -> gbw and transients removed, input.inp preserved
    SubprocessBroker._sanitize_remediation_scratch(scratch, preserve_gbw=False)

    assert not (scratch / "calc.tmp.01").exists()
    assert not (scratch / "orca.scfp_tmp.bin").exists()
    assert not (scratch / "calc.prop.txt").exists()
    assert not (scratch / "run.lock").exists()
    assert not (scratch / "vib.hess").exists()
    assert not (scratch / "electron.densities").exists()
    assert not (scratch / "orbitals.gbw").exists()
    assert (scratch / "input.inp").exists()

def test_sanitize_remediation_scratch_preserves_gbw_on_request(tmp_path):
    scratch = tmp_path / "scratch_gbw"
    scratch.mkdir()

    (scratch / "dirty.tmp").write_text("temp", encoding="utf-8")
    (scratch / "orbitals.gbw").write_text("checkpoint_data", encoding="utf-8")

    # Case 2: preserve_gbw = True -> gbw preserved, tmp wiped
    SubprocessBroker._sanitize_remediation_scratch(scratch, preserve_gbw=True)

    assert not (scratch / "dirty.tmp").exists()
    assert (scratch / "orbitals.gbw").exists()
    assert (scratch / "orbitals.gbw").read_text(encoding="utf-8") == "checkpoint_data"

def test_promote_converged_outputs(tmp_path):
    import os
    store = tmp_path / "persistent_store"
    store.mkdir()
    scratch = tmp_path / "broker_scratch"
    scratch.mkdir()

    old_scratch = os.environ.get("COCH_SCRATCH")
    old_store = os.environ.get("COCH_STORE_DIR")
    os.environ["COCH_SCRATCH"] = str(scratch)
    os.environ["COCH_STORE_DIR"] = str(store)
    try:
        broker = SubprocessBroker(engine_name="test_engine")

        # Execute a simple command producing converged outputs: .out and .xyz
        code = (
            "import pathlib; "
            "pathlib.Path('calc.out').write_text('ORCA TERMINATED NORMALLY', encoding='utf-8'); "
            "pathlib.Path('calc.xyz').write_text('3\\nWater\\nO 0 0 0\\nH 0 1 0\\nH 1 0 0\\n', encoding='utf-8')"
        )
        cmd = [sys.executable, "-c", code]

        res = broker.execute(cmd)
        assert res.success is True

        # Check that outputs were promoted to store_dir
        assert (store / "calc.out").exists()
        assert (store / "calc.xyz").exists()
        assert "ORCA TERMINATED NORMALLY" in (store / "calc.out").read_text(encoding="utf-8")
    finally:
        if old_scratch is None:
            os.environ.pop("COCH_SCRATCH", None)
        else:
            os.environ["COCH_SCRATCH"] = old_scratch
        if old_store is None:
            os.environ.pop("COCH_STORE_DIR", None)
        else:
            os.environ["COCH_STORE_DIR"] = old_store
